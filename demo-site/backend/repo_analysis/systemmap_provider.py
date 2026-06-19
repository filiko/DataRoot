"""System Map provider — AST-based detection of middleware, outbound calls, and business rules.

This module extends repo analysis to detect:
(a) Middleware and auth guards via AST (@app.middleware, Depends(), decorator patterns)
(b) Outbound HTTP/SDK calls (requests.get/post, httpx, SDK clients)
(c) Validators and state-transitions (pydantic validators, enum transitions, state machines)

It produces Connector and BusinessRule records that feed into the System Map.
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any

from .models import EvidenceRecord, FactRecord, RepositoryInventory

# HTTP clients to detect
HTTP_CLIENT_PATTERNS = {
    "requests": {"get", "post", "put", "patch", "delete", "options", "head", "request"},
    "httpx": {"get", "post", "put", "patch", "delete", "options", "head", "request", "Client"},
    "aiohttp": {"ClientSession", "get", "post", "put", "patch", "delete"},
    "urllib": {"request"},
    "urllib3": {"request"},
}

# Auth-related imports and patterns
AUTH_IMPORTS = {
    "fastapi.security", "fastapi.security.http", "fastapi.security.oauth2",
    "starlette.middleware", "starlette.authentication",
    "authlib", "pyjwt", "jwt", "passlib", "bcrypt",
    "httpauth", "django.contrib.auth", "flask_httpauth",
}

# Middleware patterns
MIDDLEWARE_PATTERNS = {
    "middleware", "add_middleware", "Middleware",
    "cors", "CORSMiddleware", "TrustedHostMiddleware",
    "SessionMiddleware", "AuthenticationMiddleware",
}

# State machine and validator patterns
STATE_MACHINE_PATTERNS = {
    "state", "status", "workflow", "lifecycle",
    "transition", "next_state", "set_state", "change_state",
}

# Pydantic validator names
PYDANTIC_VALIDATORS = {
    "validator", "root_validator", "field_validator",
    "before", "after", "model_validator",
}


def _stable_id(prefix: str, *parts: str) -> str:
    """Generate a stable ID from parts."""
    raw = "|".join(str(p) for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    sanitized = re.sub(r"[^a-z0-9_]", "_", raw.lower())
    return f"{prefix}_{sanitized[:32]}_{digest}"


def _literal_string(node: ast.AST | None) -> str | None:
    """Extract string literal from AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def _call_name(node: ast.AST) -> str | None:
    """Get the name of a Call node's function."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _full_call_name(node: ast.AST) -> str | None:
    """Get the full dotted name of a Call node's function."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _full_call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _get_imports(tree: ast.AST) -> dict[str, set[str]]:
    """Collect all imports from an AST tree, mapping module -> {names}."""
    imports: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                imports[name] = imports.get(name, set()) | {alias.name}
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                imports[name] = imports.get(name, set()) | {f"{module}.{alias.name}" if module else alias.name}
    return imports


def _is_auth_related_import(imports: dict[str, set[str]], name: str) -> bool:
    """Check if a name is from an auth-related module."""
    modules = imports.get(name, set())
    return any(mod.startswith(auth_mod) for mod in modules for auth_mod in AUTH_IMPORTS)


def _extract_url_from_call(call_node: ast.Call) -> str | None:
    """Extract URL from a call's positional or keyword args."""
    # First positional arg
    if call_node.args:
        url = _literal_string(call_node.args[0])
        if url:
            return url
    # Keyword arg: url, url_path, endpoint, uri
    for keyword in call_node.keywords:
        if keyword.arg in {"url", "url_path", "endpoint", "uri", "path"}:
            return _literal_string(keyword.value)
    return None


def _detect_http_client(call_node: ast.Call) -> tuple[str, str] | None:
    """Detect if a call is an HTTP client call. Returns (client, method) or None."""
    func_name = _call_name(call_node.func)
    if not func_name:
        return None

    # requests.get(...) or requests.post(...)
    if isinstance(call_node.func, ast.Attribute) and isinstance(call_node.func.value, ast.Name):
        client = call_node.func.value.id
        method = func_name
        if client in HTTP_CLIENT_PATTERNS and method in HTTP_CLIENT_PATTERNS.get(client, set()):
            return client, method

    # httpx.Client().get(...) - detect Client() construction
    if func_name in {"get", "post", "put", "patch", "delete", "options", "head"}:
        if isinstance(call_node.func, ast.Attribute):
            return "httpx", func_name

    return None


def _detect_middleware_decorator(decorator: ast.AST, imports: dict[str, set[str]]) -> str | None:
    """Detect if a decorator is a middleware or auth guard. Returns kind or None."""
    # @app.middleware("http")
    if isinstance(decorator, ast.Call):
        func_name = _call_name(decorator.func)
        if func_name in {"middleware", "add_middleware"}:
            return "middleware"
        if func_name == "Middleware":
            return "middleware"

    # Direct attribute: @app.middleware
    if isinstance(decorator, ast.Attribute):
        if decorator.attr in MIDDLEWARE_PATTERNS:
            return "middleware"

    # Decorator name
    dec_name = _full_call_name(decorator)
    if dec_name:
        if "middleware" in dec_name.lower():
            return "middleware"
        if "auth" in dec_name.lower() or "security" in dec_name.lower():
            return "auth"
        if "cors" in dec_name.lower():
            return "middleware"

    return None


def _detect_auth_dependency(call_node: ast.Call, imports: dict[str, set[str]]) -> bool:
    """Detect if a call is a Depends() with auth-related dependency."""
    func_name = _call_name(call_node.func)
    if func_name == "Depends":
        return True
    if func_name and _is_auth_related_import(imports, func_name):
        return True
    return False


def _detect_validator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str] | None:
    """Detect if a function is a Pydantic validator. Returns (kind, condition) or None."""
    for decorator in node.decorator_list:
        dec_name = _full_call_name(decorator)
        if not dec_name:
            # Handle bare name (e.g., @validator without module prefix)
            if isinstance(decorator, ast.Call):
                func_name = _call_name(decorator.func)
                if func_name in PYDANTIC_VALIDATORS:
                    field_name = None
                    if decorator.args:
                        field_name = _literal_string(decorator.args[0])
                    elif decorator.keywords:
                        for kw in decorator.keywords:
                            if kw.arg == "fields":
                                field_name = _literal_string(kw.value)
                                break
                    return func_name, field_name or "unknown"
            elif isinstance(decorator, ast.Name):
                if decorator.id in PYDANTIC_VALIDATORS:
                    return decorator.id, "unknown"
            continue
        # Check for @validator, @root_validator, @field_validator
        for validator_name in PYDANTIC_VALIDATORS:
            if validator_name in dec_name:
                # Extract field name from validator
                field_name = None
                if isinstance(decorator, ast.Call) and decorator.args:
                    field_name = _literal_string(decorator.args[0])
                elif isinstance(decorator, ast.Call):
                    for kw in decorator.keywords:
                        if kw.arg == "fields":
                            field_name = _literal_string(kw.value)
                            break
                return validator_name, field_name or "unknown"
    return None


def _detect_enum_transition(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str] | None:
    """Detect if a function is an enum/state transition. Returns (from_state, to_state) or None."""
    func_name = node.name.lower()
    # Pattern: transition_<from>_<to>, change_<from>_to_<to>, etc.
    transition_patterns = [
        r"(?:transition|change|set|update)_(.+?)_(?:to|2|_)_(.+)",
        r"(?:from|to)_(.+?)_(?:to|2|_)_(.+)",
        r"^(.+?)_(?:to|2|go_to)_(.+)$",
    ]
    for pattern in transition_patterns:
        match = re.match(pattern, func_name)
        if match:
            return match.group(1), match.group(2)

    # Check for state machine patterns in body
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            if child.attr in STATE_MACHINE_PATTERNS:
                return func_name, "next_state"
        if isinstance(child, ast.Name):
            if child.id in STATE_MACHINE_PATTERNS:
                return func_name, "next_state"
    return None


def _build_enforced_at(path: str, line_start: int | None, line_end: int | None) -> list[str]:
    """Build enforced_at list from path and line numbers."""
    if line_start is None:
        return [f"{path}"]
    if line_end and line_end != line_start:
        return [f"{path}:{line_start}-{line_end}"]
    return [f"{path}:{line_start}"]


# ============================================================================
# Evidence Collection Functions
# ============================================================================


def collect_middleware_connectors(
    repo_root: Path,
    inventory: RepositoryInventory,
) -> list[EvidenceRecord]:
    """Detect middleware and auth guards via AST.

    Finds:
    - @app.middleware and similar middleware decorators
    - Depends() calls with auth dependencies
    - Auth-related decorators and guards

    Returns EvidenceRecord list with Connector(kind=middleware|auth).
    """
    repo_root = repo_root.resolve()
    records: list[EvidenceRecord] = []
    python_files = [
        item for item in inventory.files
        if item.included and item.language == "python"
    ]

    for item in python_files:
        path = repo_root / item.path
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        imports = _get_imports(tree)
        lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Check function-level middleware
            for decorator in node.decorator_list:
                kind = _detect_middleware_decorator(decorator, imports)
                if kind:
                    line_start = getattr(decorator, "lineno", node.lineno)
                    excerpt = lines[line_start - 1].strip() if 0 < line_start <= len(lines) else None
                    record_id = _stable_id("ev", "middleware", item.path, str(line_start), node.name)
                    records.append(EvidenceRecord(
                        id=record_id,
                        type="middleware_guard",
                        source="python_ast",
                        path=item.path,
                        line_start=line_start,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        excerpt=excerpt,
                        tags=["middleware", kind],
                        confidence=0.9,
                        attributes={
                            "kind": kind,
                            "handler": node.name,
                            "handler_line_start": node.lineno,
                        },
                    ))

            # Check for Depends() in function signature
            for default in node.args.defaults:
                if isinstance(default, ast.Call):
                    if _detect_auth_dependency(default, imports):
                        line_start = getattr(default, "lineno", node.lineno)
                        excerpt = lines[line_start - 1].strip() if 0 < line_start <= len(lines) else None
                        record_id = _stable_id("ev", "auth_guard", item.path, str(line_start), node.name)
                        records.append(EvidenceRecord(
                            id=record_id,
                            type="auth_guard",
                            source="python_ast",
                            path=item.path,
                            line_start=line_start,
                            line_end=line_start,
                            excerpt=excerpt,
                            tags=["auth", "dependency"],
                            confidence=0.85,
                            attributes={
                                "kind": "auth",
                                "handler": node.name,
                                "dependency_call": _full_call_name(default),
                            },
                        ))

    return records


def collect_outbound_connectors(
    repo_root: Path,
    inventory: RepositoryInventory,
) -> list[EvidenceRecord]:
    """Detect outbound HTTP/SDK calls via AST.

    Finds:
    - requests.get/post/etc calls
    - httpx client calls
    - Other HTTP client patterns

    Returns EvidenceRecord list with Connector(kind=seam) and DataFlow targets.
    """
    repo_root = repo_root.resolve()
    records: list[EvidenceRecord] = []
    python_files = [
        item for item in inventory.files
        if item.included and item.language == "python"
    ]

    for item in python_files:
        path = repo_root / item.path
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            http_call = _detect_http_client(node)
            if http_call:
                client, method = http_call
                line_start = getattr(node, "lineno", 1)
                excerpt = lines[line_start - 1].strip() if 0 < line_start <= len(lines) else None
                url = _extract_url_from_call(node)

                record_id = _stable_id("ev", "outbound", item.path, str(line_start), client, method)
                records.append(EvidenceRecord(
                    id=record_id,
                    type="outbound_call",
                    source="python_ast",
                    path=item.path,
                    line_start=line_start,
                    line_end=getattr(node, "end_lineno", line_start),
                    excerpt=excerpt,
                    tags=["outbound", "http", client],
                    confidence=0.85,
                    attributes={
                        "client": client,
                        "method": method.upper(),
                        "url": url,
                        "target_system": _extract_target_system(url) if url else None,
                    },
                ))

    return records


def _extract_target_system(url: str | None) -> str | None:
    """Extract target system identifier from URL."""
    if not url:
        return None
    # Extract domain from URL
    match = re.match(r"https?://([^/]+)", url)
    if match:
        domain = match.group(1)
        # Remove port and common prefixes
        domain = re.sub(r":\d+", "", domain)
        return domain
    return None


def collect_business_rules(
    repo_root: Path,
    inventory: RepositoryInventory,
) -> list[EvidenceRecord]:
    """Detect validators and state-transitions via AST.

    Finds:
    - Pydantic validators (@validator, @field_validator, @model_validator)
    - Enum/state transitions (functions with state machine patterns)
    - State machine patterns in code

    Returns EvidenceRecord list with BusinessRule(category=validation|state_machine).
    """
    repo_root = repo_root.resolve()
    records: list[EvidenceRecord] = []
    python_files = [
        item for item in inventory.files
        if item.included and item.language == "python"
    ]

    for item in python_files:
        path = repo_root / item.path
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Check for Pydantic validators
            validator_info = _detect_validator(node)
            if validator_info:
                validator_kind, field_name = validator_info
                line_start = node.lineno
                excerpt = lines[line_start - 1].strip() if 0 < line_start <= len(lines) else None

                record_id = _stable_id("ev", "validator", item.path, str(line_start), node.name)
                records.append(EvidenceRecord(
                    id=record_id,
                    type="pydantic_validator",
                    source="python_ast",
                    path=item.path,
                    line_start=line_start,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    excerpt=excerpt,
                    tags=["validator", "pydantic", validator_kind],
                    confidence=0.9,
                    attributes={
                        "validator_kind": validator_kind,
                        "field_name": field_name,
                        "handler": node.name,
                        "category": "validation",
                    },
                ))

            # Check for state machine / enum transitions
            transition_info = _detect_enum_transition(node)
            if transition_info:
                from_state, to_state = transition_info
                line_start = node.lineno
                excerpt = lines[line_start - 1].strip() if 0 < line_start <= len(lines) else None

                record_id = _stable_id("ev", "state_transition", item.path, str(line_start), node.name)
                records.append(EvidenceRecord(
                    id=record_id,
                    type="state_transition",
                    source="python_ast",
                    path=item.path,
                    line_start=line_start,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    excerpt=excerpt,
                    tags=["state_machine", "transition"],
                    confidence=0.8,
                    attributes={
                        "from_state": from_state,
                        "to_state": to_state,
                        "handler": node.name,
                        "category": "state_machine",
                    },
                ))

    return records


# ============================================================================
# Fact and System Map Conversion
# ============================================================================


def middleware_evidence_to_facts(records: list[EvidenceRecord]) -> list[FactRecord]:
    """Convert middleware/auth evidence to facts."""
    facts: list[FactRecord] = []
    for record in records:
        if record.type not in ("middleware_guard", "auth_guard"):
            continue

        kind = str(record.attributes.get("kind", "middleware"))
        handler = str(record.attributes.get("handler", "unknown"))

        facts.append(FactRecord(
            id=_stable_id("fact", "connector", record.path, handler, kind),
            type="connector",
            subject=f"connector:{kind}:{handler}",
            attributes={
                "name": f"{kind.title()} guard for {handler}",
                "kind": kind,
                "handler": handler,
                "source_path": record.path,
                "enforced_at": _build_enforced_at(
                    record.path or "",
                    record.line_start,
                    record.line_end,
                ),
            },
            evidence_ids=[record.id],
            confidence=record.confidence,
            status="candidate",
        ))
    return facts


def outbound_evidence_to_facts(records: list[EvidenceRecord]) -> list[FactRecord]:
    """Convert outbound call evidence to facts."""
    facts: list[FactRecord] = []
    for record in records:
        if record.type != "outbound_call":
            continue

        client = str(record.attributes.get("client", "unknown"))
        method = str(record.attributes.get("method", "GET"))
        url = record.attributes.get("url")
        target = record.attributes.get("target_system")

        facts.append(FactRecord(
            id=_stable_id("fact", "connector", record.path, client, method),
            type="connector",
            subject=f"connector:outbound:{client}:{method}",
            attributes={
                "name": f"{client} {method} call",
                "kind": "seam",
                "client": client,
                "method": method,
                "url": url,
                "target_system": target,
                "source_path": record.path,
                "enforced_at": _build_enforced_at(
                    record.path or "",
                    record.line_start,
                    record.line_end,
                ),
            },
            evidence_ids=[record.id],
            confidence=record.confidence,
            status="candidate",
        ))

        # Also create a data flow fact if we have a target
        if target:
            facts.append(FactRecord(
                id=_stable_id("fact", "flow", record.path, client, method, target),
                type="data_flow",
                subject=f"flow:outbound:{client}:{method}:{target}",
                attributes={
                    "from_system": "local",
                    "to_system": target,
                    "via": f"connector:outbound:{client}:{method}",
                    "trigger": f"{client} {method}",
                    "source_path": record.path,
                },
                evidence_ids=[record.id],
                confidence=record.confidence * 0.8,
                status="candidate",
            ))
    return facts


def business_rule_evidence_to_facts(records: list[EvidenceRecord]) -> list[FactRecord]:
    """Convert business rule evidence to facts."""
    facts: list[FactRecord] = []
    for record in records:
        if record.type not in ("pydantic_validator", "state_transition"):
            continue

        category = str(record.attributes.get("category", "validation"))
        handler = str(record.attributes.get("handler", "unknown"))

        if record.type == "pydantic_validator":
            validator_kind = str(record.attributes.get("validator_kind", "validator"))
            field_name = str(record.attributes.get("field_name", "unknown"))
            facts.append(FactRecord(
                id=_stable_id("fact", "rule", record.path, handler),
                type="business_rule",
                subject=f"rule:validation:{handler}",
                attributes={
                    "title": f"Pydantic {validator_kind} on {field_name}",
                    "category": category,
                    "condition": f"@validator {field_name}",
                    "handler": handler,
                    "source_path": record.path,
                    "enforced_at": _build_enforced_at(
                        record.path or "",
                        record.line_start,
                        record.line_end,
                    ),
                },
                evidence_ids=[record.id],
                confidence=record.confidence,
                status="candidate",
            ))
        elif record.type == "state_transition":
            from_state = str(record.attributes.get("from_state", ""))
            to_state = str(record.attributes.get("to_state", ""))
            facts.append(FactRecord(
                id=_stable_id("fact", "rule", record.path, handler),
                type="business_rule",
                subject=f"rule:state_machine:{handler}",
                attributes={
                    "title": f"State transition: {from_state} → {to_state}",
                    "category": category,
                    "condition": f"{from_state} -> {to_state}",
                    "from_state": from_state,
                    "to_state": to_state,
                    "handler": handler,
                    "source_path": record.path,
                    "enforced_at": _build_enforced_at(
                        record.path or "",
                        record.line_start,
                        record.line_end,
                    ),
                },
                evidence_ids=[record.id],
                confidence=record.confidence,
                status="candidate",
            ))
    return facts


def evidence_to_systemmap(
    middleware_records: list[EvidenceRecord],
    outbound_records: list[EvidenceRecord],
    rule_records: list[EvidenceRecord],
) -> dict[str, Any]:
    """Convert all evidence records to System Map format.

    Returns a dict with systems, connectors, business_rules, and data_flows
    that can be used to create a SystemMap instance.
    """
    # Import here to avoid circular imports
    from dataroot.systemmap import (
        BusinessRule,
        Connector,
        DataFlow,
        EnterpriseSystem,
        Evidence,
        Ref,
        stable_id as systemmap_stable_id,
    )

    systems: list[dict] = []
    connectors: list[dict] = []
    business_rules: list[dict] = []
    data_flows: list[dict] = []

    # Track seen systems - include a "local" system for the repo being analyzed
    seen_systems: dict[str, str] = {}
    local_system_id = systemmap_stable_id("system", "local")
    seen_systems["local"] = local_system_id
    systems.append({
        "id": local_system_id,
        "name": "Local Repository",
        "kind": "repo",
        "evidence": [{
            "id": "ev_system_local",
            "kind": "repo_file",
            "locator": "analysis_context",
            "excerpt": "Local repository being analyzed",
            "confidence": 1.0,
        }],
        "confidence": 1.0,
        "review_status": "accepted",
    })

    # Process middleware connectors
    for record in middleware_records:
        kind = str(record.attributes.get("kind", "middleware"))
        handler = str(record.attributes.get("handler", "unknown"))
        enforced_at = _build_enforced_at(record.path or "", record.line_start, record.line_end)

        connector_id = systemmap_stable_id("connector", kind, handler)
        connectors.append({
            "id": connector_id,
            "name": f"{kind.title()} guard for {handler}",
            "kind": kind,
            "enforced_at": enforced_at,
            "evidence": [{
                "id": record.id,
                "kind": "repo_file",
                "locator": f"{record.path}:{record.line_start}" if record.path else "unknown",
                "excerpt": record.excerpt,
                "confidence": record.confidence,
            }],
            "confidence": record.confidence,
            "review_status": "needs_review",
        })

    # Process outbound connectors and data flows
    for record in outbound_records:
        client = str(record.attributes.get("client", "unknown"))
        method = str(record.attributes.get("method", "GET"))
        target = record.attributes.get("target_system")
        enforced_at = _build_enforced_at(record.path or "", record.line_start, record.line_end)

        connector_id = systemmap_stable_id("connector", "outbound", client, method)
        
        # Resolve target system ID if we have a target
        to_systems: list[str] = []
        if target:
            if target not in seen_systems:
                system_id = systemmap_stable_id("system", target)
                seen_systems[target] = system_id
                systems.append({
                    "id": system_id,
                    "name": target,
                    "kind": "saas",
                    "evidence": [{
                        "id": f"ev_system_{target}",
                        "kind": "repo_file",
                        "locator": f"inferred from {record.path}",
                        "excerpt": f"Outbound call to {target}",
                        "confidence": 0.7,
                    }],
                    "confidence": 0.7,
                    "review_status": "needs_review",
                })
            to_systems = [seen_systems[target]]

        connectors.append({
            "id": connector_id,
            "name": f"{client} {method} call",
            "kind": "seam",
            "to_systems": to_systems,
            "enforced_at": enforced_at,
            "evidence": [{
                "id": record.id,
                "kind": "repo_file",
                "locator": f"{record.path}:{record.line_start}" if record.path else "unknown",
                "excerpt": record.excerpt,
                "confidence": record.confidence,
            }],
            "confidence": record.confidence,
            "review_status": "needs_review",
        })

        # Create data flow if we have a target
        if target:
            flow_id = systemmap_stable_id("flow", client, method, target)
            data_flows.append({
                "id": flow_id,
                "from_ref": {"kind": "system", "id": local_system_id},
                "to_ref": {"kind": "system", "id": seen_systems[target]},
                "via": connector_id,
                "evidence": [{
                    "id": record.id,
                    "kind": "repo_file",
                    "locator": f"{record.path}:{record.line_start}" if record.path else "unknown",
                    "excerpt": record.excerpt,
                    "confidence": record.confidence,
                }],
                "confidence": record.confidence * 0.8,
            })

    # Process business rules
    for record in rule_records:
        category = str(record.attributes.get("category", "validation"))
        handler = str(record.attributes.get("handler", "unknown"))
        enforced_at = _build_enforced_at(record.path or "", record.line_start, record.line_end)

        if record.type == "pydantic_validator":
            validator_kind = str(record.attributes.get("validator_kind", "validator"))
            field_name = str(record.attributes.get("field_name", "unknown"))
            rule_id = systemmap_stable_id("rule", "validation", handler, field_name)
            business_rules.append({
                "id": rule_id,
                "scope": {"kind": "process", "id": f"proc_{handler}"},
                "title": f"Pydantic {validator_kind} on {field_name}",
                "statement": f"Field {field_name} must pass {validator_kind} validation",
                "category": category,
                "condition": f"@validator {field_name}",
                "enforced_at": enforced_at,
                "status": "enforced",
                "evidence": [{
                    "id": record.id,
                    "kind": "repo_file",
                    "locator": f"{record.path}:{record.line_start}" if record.path else "unknown",
                    "excerpt": record.excerpt,
                    "confidence": record.confidence,
                }],
                "confidence": record.confidence,
                "review_status": "needs_review",
            })
        elif record.type == "state_transition":
            from_state = str(record.attributes.get("from_state", ""))
            to_state = str(record.attributes.get("to_state", ""))
            rule_id = systemmap_stable_id("rule", "state_machine", handler)
            business_rules.append({
                "id": rule_id,
                "scope": {"kind": "process", "id": f"proc_{handler}"},
                "title": f"State transition: {from_state} → {to_state}",
                "statement": f"State can transition from {from_state} to {to_state}",
                "category": category,
                "condition": f"{from_state} -> {to_state}",
                "enforced_at": enforced_at,
                "status": "enforced",
                "evidence": [{
                    "id": record.id,
                    "kind": "repo_file",
                    "locator": f"{record.path}:{record.line_start}" if record.path else "unknown",
                    "excerpt": record.excerpt,
                    "confidence": record.confidence,
                }],
                "confidence": record.confidence,
                "review_status": "needs_review",
            })

    return {
        "systems": systems,
        "connectors": connectors,
        "business_rules": business_rules,
        "data_flows": data_flows,
    }
