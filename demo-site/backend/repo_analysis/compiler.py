from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from models.pen import (
    Attribute,
    AttributeEvidence,
    Cardinality,
    DataFlow,
    DataStore,
    DiagramLayout,
    Entity,
    ExternalEntity,
    LayoutEdge,
    LayoutNode,
    PenFile,
    Process,
    Relationship,
    RelationshipEndpoint,
    WarningEntry,
)

from .models import FactRecord


def _safe_id_part(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {"/", "-", "_", " ", ".", ":", "{" , "}"}:
            cleaned.append("_")
    result = "".join(cleaned).strip("_")
    while "__" in result:
        result = result.replace("__", "_")
    return result[:56] or hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _flow_id(from_id: str, to_id: str, kind: str) -> str:
    digest = hashlib.sha1(f"{from_id}|{to_id}|{kind}".encode("utf-8")).hexdigest()[:12]
    return f"flow_{digest}"


def _stable_project_id(repo_root: Path) -> str:
    digest = hashlib.sha1(str(repo_root.resolve()).lower().encode("utf-8")).hexdigest()[:12]
    return f"proj_{digest}"


def _accepted(facts: list[FactRecord], fact_type: str) -> list[FactRecord]:
    return [fact for fact in facts if fact.type == fact_type and fact.status == "accepted"]


def compile_pen_from_facts(
    facts: list[FactRecord],
    project_name: str,
    repo_root: Path,
) -> PenFile:
    pen = PenFile()
    pen.project.id = _stable_project_id(repo_root)
    pen.project.name = project_name
    pen.dfd.system_boundary.id = "boundary_repo_system"
    pen.dfd.system_boundary.name = project_name
    pen.sources = []

    model_subject_to_entity = _compile_erd(pen, facts)
    _compile_dfd(pen, facts, repo_root, model_subject_to_entity)

    used_gitkb = any(fact.type in {"code.symbol", "code.call_edge"} and fact.status == "accepted" for fact in facts)
    model_count = len(pen.erd.entities)
    route_count = len(_accepted(facts, "api.route"))
    pen.review.warnings.append(WarningEntry(
        rule_id="REPO-ANALYSIS-SUMMARY",
        severity="warning",
        node_kind="global",
        message=(
            f"Repo analysis generated from {repo_root} using "
            f"{route_count} route facts, {model_count} model entities, "
            f"and {'GitKB/code graph evidence' if used_gitkb else 'deterministic AST evidence only'}."
        ),
    ))
    return pen


def _compile_erd(pen: PenFile, facts: list[FactRecord]) -> dict[str, Entity]:
    model_facts = _accepted(facts, "app.model")
    attribute_facts = _accepted(facts, "app.attribute")
    relationship_facts = _accepted(facts, "app.relationship")

    model_subject_to_entity: dict[str, Entity] = {}
    attributes_by_model: dict[str, list[FactRecord]] = defaultdict(list)
    for fact in attribute_facts:
        attributes_by_model[str(fact.attributes.get("model_subject"))].append(fact)

    entities: list[Entity] = []
    for fact in sorted(model_facts, key=lambda item: item.subject):
        name = str(fact.attributes.get("name") or _safe_id_part(fact.subject))
        entity = Entity(
            id=f"ent_{_safe_id_part(name)}",
            name=name,
            display_name=str(fact.attributes.get("display_name") or name.replace("_", " ").title()),
            source_evidence=[AttributeEvidence(source_id=evidence_id) for evidence_id in fact.evidence_ids],
            confidence=fact.confidence,
            review_status="accepted" if fact.confidence >= 0.85 else "needs_review",
        )
        for attr_fact in sorted(attributes_by_model.get(fact.subject, []), key=lambda item: item.subject):
            attr = _attribute_from_fact(attr_fact)
            if attr.name not in {existing.name for existing in entity.attributes}:
                entity.attributes.append(attr)
        if not any(attr.key_role == "primary" for attr in entity.attributes):
            entity.attributes.insert(0, Attribute(
                id=f"attr_{_safe_id_part(name)}_id",
                name="id",
                display_name="Id",
                pg_type="uuid",
                key_role="primary",
                nullable=False,
                default=None,
                confidence=min(fact.confidence, 0.72),
                review_status="needs_review",
            ))
        model_subject_to_entity[fact.subject] = entity
        entities.append(entity)

    relationships: list[Relationship] = []
    for fact in sorted(relationship_facts, key=lambda item: item.subject):
        source_entity = model_subject_to_entity.get(str(fact.attributes.get("from_model_subject")))
        target_entity = model_subject_to_entity.get(str(fact.attributes.get("to_model_subject")))
        if source_entity is None or target_entity is None:
            continue
        source_attr_name = str(fact.attributes.get("attribute_name") or "")
        source_attr = next((attr for attr in source_entity.attributes if attr.name == source_attr_name), None)
        target_attr = next((attr for attr in target_entity.attributes if attr.key_role == "primary"), None)
        if source_attr is None or target_attr is None:
            continue
        rel_name = f"{source_entity.name}_{source_attr.name}_{target_entity.name}"
        relationships.append(Relationship(
            id=f"rel_{_safe_id_part(rel_name)}",
            name=source_attr.name,
            **{
                "from": RelationshipEndpoint(entity_id=source_entity.id, attribute_id=source_attr.id),
                "to": RelationshipEndpoint(entity_id=target_entity.id, attribute_id=target_attr.id),
            },
            cardinality=Cardinality(
                from_min=0,
                from_max="many",
                to_min=0 if source_attr.nullable else 1,
                to_max="many" if fact.attributes.get("relationship_many") else 1,
            ),
            evidence=fact.evidence_ids,
            confidence=fact.confidence,
            review_status="accepted" if fact.confidence >= 0.8 else "needs_review",
        ))

    pen.erd.entities = entities
    pen.erd.relationships = relationships
    pen.layout.erd = _layout_erd(entities, relationships)
    return model_subject_to_entity


def _attribute_from_fact(fact: FactRecord) -> Attribute:
    name = str(fact.attributes.get("name") or "field")
    key_role = str(fact.attributes.get("key_role") or "none")
    if key_role not in {"primary", "foreign", "unique", "audit", "business_key", "none"}:
        key_role = "none"
    return Attribute(
        id=f"attr_{_safe_id_part(str(fact.attributes.get('model_class', 'model')))}_{_safe_id_part(name)}",
        name=name,
        display_name=str(fact.attributes.get("display_name") or name.replace("_", " ").title()),
        pg_type=str(fact.attributes.get("pg_type") or "text"),
        key_role=key_role,  # type: ignore[arg-type]
        nullable=bool(fact.attributes.get("nullable", True)),
        default=None,
        evidence=[AttributeEvidence(source_id=evidence_id) for evidence_id in fact.evidence_ids],
        confidence=fact.confidence,
        review_status="accepted" if fact.confidence >= 0.85 else "needs_review",
    )


def _compile_dfd(
    pen: PenFile,
    facts: list[FactRecord],
    repo_root: Path,
    model_subject_to_entity: dict[str, Entity],
) -> None:
    route_facts = _accepted(facts, "api.route")
    call_facts = _accepted(facts, "code.call_edge")

    client = ExternalEntity(
        id="ext_user_or_client",
        name="User or Client",
        description="External caller inferred from API routes.",
        source="auto",
        source_evidence=sorted({evidence_id for fact in route_facts for evidence_id in fact.evidence_ids}),
        source_facts=[fact.id for fact in route_facts],
    )
    pen.dfd.external_entities = [client] if route_facts else []

    stores = _compile_data_stores(model_subject_to_entity, facts)
    pen.dfd.data_stores = stores

    grouped_routes = _group_routes(route_facts)
    processes: list[Process] = []
    flows: list[DataFlow] = []

    for index, (group_key, group_routes) in enumerate(sorted(grouped_routes.items()), start=1):
        process_id = f"proc_{_safe_id_part(group_key)}"
        process = Process(
            id=process_id,
            number=str(index),
            name=_process_name(group_key, group_routes),
            description=_process_description(group_routes),
            user_modified=False,
            source_evidence=sorted({evidence_id for fact in group_routes for evidence_id in fact.evidence_ids}),
            source_facts=[fact.id for fact in group_routes],
        )
        process.level_1_diagram = _level_1_for_routes(process, group_routes) if len(group_routes) > 2 else None
        processes.append(process)

        request_flow_id = _flow_id(client.id, process_id, "request")
        response_flow_id = _flow_id(process_id, client.id, "response")
        flows.extend([
            DataFlow(**{
                "id": request_flow_id,
                "from": client.id,
                "to": process_id,
                "data_name": f"{process.name} request",
                "user_modified": False,
                "source_evidence": process.source_evidence,
                "source_facts": process.source_facts,
            }),
            DataFlow(**{
                "id": response_flow_id,
                "from": process_id,
                "to": client.id,
                "data_name": f"{process.name} response",
                "user_modified": False,
                "source_evidence": process.source_evidence,
                "source_facts": process.source_facts,
            }),
        ])

        for store in _stores_for_route_group(group_key, stores):
            flows.extend([
                DataFlow(**{
                    "id": _flow_id(process_id, store.id, "write"),
                    "from": process_id,
                    "to": store.id,
                    "data_name": f"Persist {store.name}",
                    "mapped_erd_entities": [store.mapped_erd_entity] if store.mapped_erd_entity else [],
                    "source_evidence": process.source_evidence,
                    "source_facts": process.source_facts,
                }),
                DataFlow(**{
                    "id": _flow_id(store.id, process_id, "read"),
                    "from": store.id,
                    "to": process_id,
                    "data_name": f"Read {store.name}",
                    "mapped_erd_entities": [store.mapped_erd_entity] if store.mapped_erd_entity else [],
                    "source_evidence": process.source_evidence,
                    "source_facts": process.source_facts,
                }),
            ])

    if not processes and stores:
        processes.append(Process(
            id="proc_model_intelligence",
            number="1",
            name="Model Intelligence",
            description="Model/type structures inferred from repository source.",
            source_evidence=sorted({evidence_id for store in stores for evidence_id in store.source_evidence}),
            source_facts=sorted({fact_id for store in stores for fact_id in store.source_facts}),
        ))

    _add_call_graph_processes(processes, flows, call_facts)

    pen.dfd.processes = processes
    pen.dfd.data_flows = _dedupe_flows(flows)
    pen.layout.dfd = _layout_dfd(pen.dfd.external_entities, processes, stores, pen.dfd.data_flows)
    pen.layout.dfd_level_1 = {
        process.id: _layout_dfd(
            process.level_1_diagram.external_entities,
            process.level_1_diagram.processes,
            process.level_1_diagram.data_stores,
            process.level_1_diagram.data_flows,
        )
        for process in processes
        if process.level_1_diagram is not None
    }


def _compile_data_stores(model_subject_to_entity: dict[str, Entity], facts: list[FactRecord]) -> list[DataStore]:
    model_facts = {fact.subject: fact for fact in _accepted(facts, "app.model")}
    if len(model_subject_to_entity) > 16:
        return _compile_grouped_data_stores(model_subject_to_entity, model_facts)

    stores: list[DataStore] = []
    for subject, entity in sorted(model_subject_to_entity.items(), key=lambda item: item[1].name):
        fact = model_facts.get(subject)
        stores.append(DataStore(
            id=f"store_{entity.id.removeprefix('ent_')}",
            name=entity.display_name,
            description=f"Repository model inferred from {entity.name}.",
            mapped_erd_entity=entity.id,
            user_modified=False,
            source_evidence=[evidence.source_id for evidence in entity.source_evidence],
            source_facts=[fact.id] if fact else [_fact_id_for_model_subject(subject)],
        ))
    return stores


def _compile_grouped_data_stores(
    model_subject_to_entity: dict[str, Entity],
    model_facts: dict[str, FactRecord],
) -> list[DataStore]:
    groups: dict[str, dict[str, Any]] = {}
    for subject, entity in model_subject_to_entity.items():
        fact = model_facts.get(subject)
        source_path = str(fact.attributes.get("source_path") if fact else "")
        group_key, group_name = _store_group_for_source(source_path, entity)
        group = groups.setdefault(group_key, {
            "name": group_name,
            "entities": [],
            "evidence": set(),
            "facts": set(),
        })
        group["entities"].append(entity)
        group["evidence"].update(evidence.source_id for evidence in entity.source_evidence)
        if fact:
            group["facts"].add(fact.id)

    stores: list[DataStore] = []
    for key, group in sorted(groups.items()):
        entities = group["entities"]
        stores.append(DataStore(
            id=f"store_{_safe_id_part(key)}",
            name=str(group["name"]),
            description=f"Grouped repository data models: {', '.join(entity.display_name for entity in entities[:8])}.",
            mapped_erd_entity=entities[0].id if len(entities) == 1 else None,
            user_modified=False,
            source_evidence=sorted(group["evidence"]),
            source_facts=sorted(group["facts"]),
        ))
    return stores


def _store_group_for_source(source_path: str, entity: Entity) -> tuple[str, str]:
    path = source_path.replace("\\", "/").lower()
    if "backend/models/pen" in path or "frontend/src/types/pen" in path:
        return "penfile_models", "PenFile Models"
    if "backend/models/source" in path:
        return "source_table_models", "Source Table Models"
    if "backend/repo_analysis" in path:
        return "repo_analysis_models", "Repo Analysis Models"
    if "backend/main" in path:
        return "api_contract_models", "API Contract Models"
    if "/types/" in path or "/models/" in path:
        parent = source_path.replace("\\", "/").split("/")[-2] if "/" in source_path else "models"
        return f"{parent}_models", f"{parent.replace('_', ' ').title()} Models"
    return "application_models", "Application Models"


def _fact_id_for_model_subject(subject: str) -> str:
    digest = hashlib.sha1(f"app.model|{subject}".encode("utf-8")).hexdigest()[:16]
    return f"fact_{digest}"


def _group_routes(route_facts: list[FactRecord]) -> dict[str, list[FactRecord]]:
    grouped: dict[str, list[FactRecord]] = defaultdict(list)
    for fact in route_facts:
        path = str(fact.attributes.get("path") or "/")
        handler = str(fact.attributes.get("handler") or "")
        grouped[_route_group_key(path, handler)].append(fact)
    return grouped


def _route_group_key(path: str, handler: str) -> str:
    first_segment = next((part for part in path.split("/") if part and not part.startswith("{")), "")
    if first_segment in {"schema", "projects", "project"}:
        return "project_schema_api"
    if first_segment in {"repo", "repository"} or "repo" in handler:
        return "repo_analysis_api"
    if first_segment in {"ingest", "upload"} or "upload" in handler or "ingest" in handler:
        return "source_ingestion_api"
    if first_segment in {"export", "exports"} or "export" in handler:
        return "export_api"
    if first_segment in {"chat", "proposal", "proposals", "review"}:
        return "review_api"
    if first_segment:
        return f"{_safe_id_part(first_segment)}_api"
    words = handler.split("_")
    return f"{_safe_id_part(words[0] if words else 'api')}_api"


def _group_display_name(group_key: str) -> str:
    overrides = {
        "project_schema_api": "Project Schema API",
        "repo_analysis_api": "Repo Analysis API",
        "source_ingestion_api": "Source Ingestion API",
        "export_api": "Export API",
        "review_api": "Review API",
    }
    return overrides.get(group_key, group_key.replace("_", " ").title())


def _process_name(group_key: str, route_facts: list[FactRecord]) -> str:
    if len(route_facts) == 1:
        handler = str(route_facts[0].attributes.get("handler") or "")
        if handler:
            return handler.strip("_").replace("_", " ").title()
    return _group_display_name(group_key)


def _process_description(route_facts: list[FactRecord]) -> str:
    route_lines = [
        f"{fact.attributes.get('method')} {fact.attributes.get('path')}"
        for fact in sorted(route_facts, key=lambda item: str(item.attributes.get("path")))
    ]
    return "Grouped API process inferred from routes: " + ", ".join(route_lines) + "."


def _stores_for_route_group(group_key: str, stores: list[DataStore]) -> list[DataStore]:
    if not stores:
        return []
    keywords_by_group = {
        "project_schema_api": {"pen", "project", "schema", "layout", "entity", "relationship", "dfd", "erd"},
        "repo_analysis_api": {"repo", "analysis", "inventory", "evidence", "fact", "git", "source"},
        "source_ingestion_api": {"source", "table", "column", "file", "csv", "excel"},
        "export_api": {"pen", "entity", "relationship", "postgres", "schema"},
        "review_api": {"review", "proposal", "issue", "warning"},
    }
    keywords = keywords_by_group.get(group_key, set())
    matched = [
        store for store in stores
        if any(keyword in store.name.lower().replace(" ", "_") for keyword in keywords)
    ]
    return matched[:4]


def _level_1_for_routes(parent: Process, route_facts: list[FactRecord]) -> Any:
    processes: list[Process] = []
    flows: list[DataFlow] = []
    ext = ExternalEntity(
        id=f"ext_{parent.id}_caller",
        name="API Caller",
        source="auto",
        source_evidence=parent.source_evidence,
        source_facts=parent.source_facts,
    )
    for index, fact in enumerate(sorted(route_facts, key=lambda item: item.subject), start=1):
        method = str(fact.attributes.get("method"))
        path = str(fact.attributes.get("path"))
        handler = str(fact.attributes.get("handler"))
        proc_id = f"{parent.id}_route_{_safe_id_part(method + '_' + path)}"
        route_process = Process(
            id=proc_id,
            number=f"{parent.number}.{index}" if parent.number else str(index),
            name=handler.replace("_", " ").title(),
            description=f"{method} {path} handled by {handler}.",
            source_evidence=fact.evidence_ids,
            source_facts=[fact.id],
        )
        processes.append(route_process)
        flows.extend([
            DataFlow(**{
                "id": _flow_id(ext.id, proc_id, "request"),
                "from": ext.id,
                "to": proc_id,
                "data_name": f"{method} {path} request",
                "source_evidence": fact.evidence_ids,
                "source_facts": [fact.id],
            }),
            DataFlow(**{
                "id": _flow_id(proc_id, ext.id, "response"),
                "from": proc_id,
                "to": ext.id,
                "data_name": f"{method} {path} response",
                "source_evidence": fact.evidence_ids,
                "source_facts": [fact.id],
            }),
        ])
    from models.pen import DfdModel, SystemBoundary

    return DfdModel(
        level=1,
        system_boundary=SystemBoundary(id=f"boundary_{parent.id}", name=parent.name),
        external_entities=[ext],
        processes=processes,
        data_flows=flows,
        data_stores=[],
    )


def _add_call_graph_processes(processes: list[Process], flows: list[DataFlow], call_facts: list[FactRecord]) -> None:
    if not call_facts:
        return
    existing_by_key = {process.id for process in processes}
    process_by_symbol: dict[str, Process] = {}
    interesting = [
        fact for fact in call_facts
        if _is_interesting_call(str(fact.attributes.get("caller")), str(fact.attributes.get("callee")))
    ][:12]
    for fact in interesting:
        for symbol in (str(fact.attributes.get("caller")), str(fact.attributes.get("callee"))):
            proc_id = f"proc_symbol_{_safe_id_part(symbol)}"
            if proc_id not in existing_by_key:
                process = Process(
                    id=proc_id,
                    number=str(len(processes) + 1),
                    name=symbol.strip("_").replace("_", " ").title(),
                    description="Code graph process inferred from GitKB call evidence.",
                    source_evidence=fact.evidence_ids,
                    source_facts=[fact.id],
                )
                processes.append(process)
                existing_by_key.add(proc_id)
                process_by_symbol[symbol] = process
            else:
                process_by_symbol[symbol] = next(process for process in processes if process.id == proc_id)
        caller_process = process_by_symbol[str(fact.attributes.get("caller"))]
        callee_process = process_by_symbol[str(fact.attributes.get("callee"))]
        if caller_process.id != callee_process.id:
            flows.append(DataFlow(**{
                "id": _flow_id(caller_process.id, callee_process.id, "call"),
                "from": caller_process.id,
                "to": callee_process.id,
                "data_name": "Function call",
                "source_evidence": fact.evidence_ids,
                "source_facts": [fact.id],
            }))


def _is_interesting_call(caller: str, callee: str) -> bool:
    terms = {"compile", "build", "analyze", "propagate", "export", "parse", "layout", "repo", "dfd", "erd"}
    combined = f"{caller} {callee}".lower()
    return any(term in combined for term in terms)


def _dedupe_flows(flows: list[DataFlow]) -> list[DataFlow]:
    seen: set[str] = set()
    result: list[DataFlow] = []
    for flow in flows:
        if flow.id in seen:
            continue
        seen.add(flow.id)
        result.append(flow)
    return result


def _layout_erd(entities: list[Entity], relationships: list[Relationship]) -> DiagramLayout:
    if not entities:
        return DiagramLayout()

    columns = max(2, min(7, int(len(entities) ** 0.5) + 1))
    x_gap = 380.0
    y_gap = 72.0
    card_width = 300.0

    heights = [
        max(160.0, 76.0 + len(entity.attributes) * 26.0)
        for entity in entities
    ]
    row_heights: list[float] = []
    for start in range(0, len(entities), columns):
        row_heights.append(max(heights[start:start + columns]))

    row_y: list[float] = []
    y = 80.0
    for row_height in row_heights:
        row_y.append(y)
        y += row_height + y_gap

    nodes: list[LayoutNode] = []
    for index, entity in enumerate(entities):
        col = index % columns
        row = index // columns
        nodes.append(LayoutNode(
            id=entity.id,
            x=80.0 + col * x_gap,
            y=row_y[row],
            width=card_width,
            height=heights[index],
        ))
    return DiagramLayout(
        nodes=nodes,
        edges=[LayoutEdge(id=relationship.id, route="orthogonal") for relationship in relationships],
    )


def _layout_dfd(
    external_entities: list[ExternalEntity],
    processes: list[Process],
    stores: list[DataStore],
    flows: list[DataFlow],
) -> DiagramLayout:
    nodes: list[LayoutNode] = []
    for index, node in enumerate(external_entities):
        nodes.append(LayoutNode(id=node.id, x=40.0, y=80.0 + index * 160.0, width=220.0, height=80.0))
    for index, node in enumerate(processes):
        col = index % 3
        row = index // 3
        nodes.append(LayoutNode(id=node.id, x=360.0 + col * 300.0, y=60.0 + row * 150.0, width=250.0, height=96.0))
    for index, node in enumerate(stores):
        col = index % 2
        row = index // 2
        nodes.append(LayoutNode(id=node.id, x=1320.0 + col * 290.0, y=80.0 + row * 130.0, width=240.0, height=76.0))
    return DiagramLayout(
        nodes=nodes,
        edges=[LayoutEdge(id=flow.id, route="orthogonal") for flow in flows],
    )
