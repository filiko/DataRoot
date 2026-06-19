---
purpose: Builder spec for DataRoot's generic enterprise data-access mapping layer (the "System Map").
prerequisites: architecture.md, ingestion.md, mcp-server.md
read-when: Designing or building source-agnostic discovery of SaaS/API/MCP/DB/repo data surfaces, the rules that govern them, and the diagrams/docs generated from them.
---

# Enterprise Data Access Map — docs/data-access-map.md

This is a **builder spec**, not marketing copy. It defines the missing core of
DataRoot: a generic, source-agnostic **System Map** that inventories every data
surface an organization can reach (SaaS MCP tools, REST/OpenAPI endpoints,
databases, repos, event streams), the **business rules** that govern that data,
the **connectors/middleware** that move it between systems, and the **data
flows** across them — then projects all of that into the diagrams and docs
DataRoot already knows how to render (ERD, DFD, schema, rule, connector views).

Examples in this doc are deliberately **generic SaaS A / B / C**. DataRoot's
core is source-agnostic; the Nexus and CompanyA/CompanyB packs are *examples*,
never a hardcoded reference (same stance as
[architecture.md §1](architecture.md): "the core works on any folder").

← Related: [architecture.md](architecture.md) · [ingestion.md](ingestion.md) ·
[mcp-server.md](mcp-server.md) · [glossary.md](glossary.md)

---

## §1 Purpose & non-goals

**Capability statement.** Given an organization that runs enterprise SaaS A, B,
and C — plus internal repos, databases, and MCP/REST endpoints — DataRoot should
be able to answer, with evidence:

- **What data can we access?** Every readable/writable surface and its
  field-level contract.
- **Where does it flow?** Which system produces it, which consumes it, what
  middleware sits between them.
- **What governs it?** The invariants, lifecycle gates, validations, and
  state machines enforced on it, and *where* they're enforced.
- **What can we generate from it?** ERD, DFD, schema/contract docs, a
  business-rule catalog, and a connector/middleware map — each traceable to a
  source of evidence.

Concretely, the recurring example: *"SaaS A's MCP gives us theta/iota
operational data, SaaS B's API gives us n9102 device/compliance data, SaaS C
gives us customer-order-fulfillment data."* DataRoot must turn that sentence
into a complete, evidence-backed inventory and a set of generated diagrams.

**Non-goals (this layer).**

- Not a data pipeline / ETL runtime. The System Map *describes* flows; it does
  not move bytes.
- Not a live query federation layer. (DataRoot already has bounded read tools
  over a profiled workspace — see [mcp-server.md](mcp-server.md).)
- Not production IAM. We *record* auth scopes/sensitivity as metadata; we do not
  enforce them.
- Not "perfect understanding of arbitrary systems." Discovery is best-effort +
  evidence-graded; humans confirm semantics automation can't prove.

---

## §2 Current state & the gap

### What exists today (reuse these)

- **Standalone core — `src/dataroot/`.** A *file* profiler (CSV/XLSX/JSON/MD/
  FASTA) → GitKB document graph → deterministic/agent query, plus an MCP
  **server** (`src/dataroot/mcp/server.py`) exposing 8 bounded read tools
  (`list_datasets`, `summarize_workspace`, `kb_search`, `kb_list`, `kb_show`,
  `query_table`, `kb_graph`, `ask`). Domain inference is heuristic
  (`src/dataroot/domain.py`); config + `.dataroot/` live in
  `src/dataroot/config.py`. See [architecture.md](architecture.md).
- **Diagram model — `demo-site/backend/models/pen.py`.** The canonical
  `PenFile` (`ErdModel` + `DfdModel` + layout/styles/postgres/review). Crucially
  it *already* carries a behavioral layer on `DfdModel`: `BusinessRule` and
  `Connector` (with `enforced_at` file:line traceability).
- **Repo analysis — `demo-site/backend/repo_analysis/`.** A deterministic
  evidence→fact→PenFile pipeline:
  `inventory.py` → `fastapi_provider.py` (FastAPI route decorators) +
  `model_provider.py` (Pydantic/SQLAlchemy classes) →
  `EvidenceRecord`/`FactRecord` (`models.py`) → `compiler.py` compiles a
  `PenFile`. Reached via `POST /schema/repo-analysis` (`demo-site/backend/main.py`).
- **Ingestion surfaces — `demo-site/backend/main.py`.** Spreadsheet/CSV upload,
  text, blank, bundled examples, repo path/upload, raw `.dfd.json` import.
- **UI — `demo-site/frontend/`.** Editors plus existing `ConnectorsPanel.tsx`
  and `BusinessRulesPanel.tsx` (the behavioral layer already has a home).

### The gap (what this spec adds)

| Capability | Today | Needed |
|---|---|---|
| Source-agnostic inventory of *systems → surfaces → objects → fields* | ❌ none (only files/single-repo) | **System Map** (§3) |
| MCP **client** to introspect external SaaS MCP servers (`tools/list` + schemas) | ❌ server only | MCP discovery adapter (§4) |
| OpenAPI / GraphQL / DB / event-source ingestion | ❌ none | OpenAPI, DB adapters (§4) |
| Middleware / auth / external-service-call detection in repos | ❌ routes + models only | Repo adapter *extensions* (§4) |
| `BusinessRule` / `Connector` **synthesis** | ❌ hand-authored in fixtures | Rule/flow extraction (§5) |
| Connector/source **registry** | ❌ ad-hoc `PenFile.sources` | `.dataroot/connectors.yaml` (§4) |
| Data **sensitivity/classification**, field-level lineage | ❌ `AttributeEvidence` only | `DataField.sensitivity` + typed `Evidence` (§3) |
| Auth **scopes** | ⚠️ workspace-level only | `AccessSurface.auth.scopes` (§3) |

---

## §3 The System Map — canonical model

The System Map is the **source of truth**. The PenFile ERD/DFD and GitKB
documents are **projections** generated from it (§6). It lives in the standalone
core as a new module (`src/dataroot/systemmap/`), keeping `demo-site` a consumer.

Every record carries two things, no exceptions:

- **`evidence: list[Evidence]`** — where this fact came from (typed).
- **`confidence: float`** and a **`review_status`** — so auto-discovered facts
  can be surfaced for human confirmation (mirrors `Attribute.review_status` and
  `FactRecord.status` already in the codebase).

Each field below is tagged **[auto]** (discoverable by an adapter), **[manual]**
(human-supplied — semantics automation can't prove), or **[mixed]**.

### EnterpriseSystem
A SaaS app, internal service, database, MCP server, repo, file store, or event bus.

```
id            str
name          str                                   [auto/manual]
vendor        str | None                            [manual]
kind          saas | internal_service | database |  [auto]
              mcp_server | repo | file_store | event_bus
environment   prod | staging | dev | None           [manual]
owner         str | None    # team/person of record [manual]
description   str | None                            [mixed]
evidence      list[Evidence]
confidence    float
review_status accepted | needs_review | rejected
```

### AccessSurface
A concrete way to read/write data from a system. One system has many surfaces.

```
id             str
system_id      str
kind           mcp_tool | openapi_endpoint | graphql |    [auto]
               webhook | db_table | event_stream |
               file_export | sdk_method
operation      read | write | subscribe                   [auto]
name           str          # tool name, "GET /devices",  [auto]
                            # table name, event topic
address        str          # URL+method | tool name |    [auto]
                            # DSN.table | topic
auth: {
  method       none | api_key | oauth2 | bearer | basic | [auto]
               mtls | iam
  scopes       list[str]    # e.g. ["devices:read"]       [mixed]
}
rate_limits    str | None                                 [auto/manual]
pagination     str | None   # cursor | offset | page | …  [auto]
request_schema_ref   str | None  # -> DataObject.id       [auto]
response_schema_ref  str | None  # -> DataObject.id       [auto]
evidence       list[Evidence]
confidence     float
review_status  …
```

### DataObject
A business object / payload shape exposed by one or more surfaces.

```
id              str
system_id       str
surface_ids     list[str]
name            str                                   [auto]
description     str | None                            [mixed]
maps_to_entity_id  str | None  # PenFile Entity.id     (set during projection)
evidence        list[Evidence]
confidence      float
review_status   …
```

### DataField
A field on a DataObject. The field-level contract + classification.

```
id            str
object_id     str
name          str                                       [auto]
type          str          # native type / JSON type     [auto]
nullable      bool                                       [auto]
sensitivity   public | internal | confidential |         [manual]
              pii | secret
owner         str | None                                 [manual]
source_path   str          # JSON pointer | column |      [auto]
                          # "$.data[].id"
description   str | None                                 [mixed]
evidence      list[Evidence]
confidence    float
review_status …
```

### BusinessRule  *(generalize the existing `pen.py` shape)*
The invariant/gate/validation/state-machine that governs data. Same fields as
`models/pen.py::BusinessRule`, with `context` generalized to a polymorphic scope:

```
id            str
scope         { kind: system|surface|object|process|flow, ref_id: str }  # was: context
title         str
statement     str          # plain language                     [mixed]
category      invariant | state_machine | gate |                 [auto/manual]
              validation | lifecycle
condition     str | None   # pseudo-code, e.g. "cn.finishedAt === null"  [auto]
enforced_at   list[str]    # "path:line_start-line_end" pointers [auto]  (== EvidenceRecord locator)
spec_source   str | None                                          [manual]
severity      constraint | warning | best_practice                [manual]
status        enforced | gap | deferred                           [auto/manual]
evidence      list[Evidence]
review_status …
```

### Connector  *(generalize the existing `pen.py` shape)*
A cross-system seam / shared middleware: trigger → effect, with the payload
contract and the code that wires it. Same fields as `models/pen.py::Connector`,
generalized from "context" to "system":

```
id            str
name          str
kind          seam | webhook | fan_out | middleware |    [auto/manual]
              shared_service | auth | etl | sync          (etl/sync are new)
trigger       str | None   # what initiates it             [mixed]
effect        str | None   # what it causes downstream     [mixed]
from_system   str | None   # was: from_context             [auto]
to_systems    list[str]    # was: to_contexts              [auto]
contract      str | None   # payload / key contract         [auto/manual]
enforced_at   list[str]    # code file:line pointers        [auto]
status        wired | deferred
evidence      list[Evidence]
review_status …
```

### DataFlow
Source surface/object → (via process or connector) → destination.

```
id              str
from_ref        { kind: system|surface|object|process, id: str }   [auto]
to_ref          { kind: …, id: str }                                [auto]
via             str | None   # Process.id or Connector.id           [auto]
data_object_ids list[str]                                           [auto]
trigger         str | None   # endpoint call, webhook, schedule, …  [auto/manual]
evidence        list[Evidence]
confidence      float
```

### Evidence  *(generalize `repo_analysis/models.py::EvidenceRecord`)*
Typed provenance attached to every record above. This is the single most
important field in the model — nothing enters the System Map without it.

```
id          str
kind        mcp_descriptor | openapi_spec | repo_file |   [auto]
            db_metadata | doc | sample_payload | manual
locator     str   # "path:line_start-line_end" | URL |    [auto]
                  # "mcp://server/tool" | "db://dsn/table"
excerpt     str | None    # the proving snippet           [auto]
confidence  float
captured_at str   # ISO timestamp
```

> **Reuse note.** `Evidence` is `EvidenceRecord` (already in
> `repo_analysis/models.py`) with a `kind` enum widened beyond repo sources.
> `enforced_at` on rules/connectors is the existing file:line convention from
> the Nexus fixtures — it becomes a typed `Evidence(kind=repo_file)`.

**Canonical-vs-projection rule.** The System Map is authoritative.
ERD/DFD/schema/rule/connector outputs are *derived* and can always be
regenerated; never edit a projection as if it were the source.

---

## §4 Acquisition — connector registry + discovery

### The registry

Users register each `EnterpriseSystem` once, with the credentials/endpoints an
adapter needs to introspect it. Stored in `.dataroot/connectors.yaml`
(consistent with the existing `.dataroot/` config handled by
`src/dataroot/config.py`):

```yaml
systems:
  - id: saas_a
    name: SaaS A
    kind: mcp_server
    discover:
      transport: stdio            # how to reach it for tools/list
      command: ["npx", "saas-a-mcp"]
    auth: { method: oauth2, scopes: [theta:read, iota:read] }

  - id: saas_b
    name: SaaS B
    kind: saas
    discover:
      openapi_url: https://api.saas-b.example/openapi.json
    auth: { method: bearer }

  - id: warehouse
    name: Internal Warehouse
    kind: database
    discover:
      dsn_env: WAREHOUSE_DSN      # never store secrets in the file
```

Secrets are referenced by env var, never inlined. Each registered system gets an
`EnterpriseSystem` record immediately; its surfaces/objects/fields are filled by
the matching adapter.

### Discovery adapters

Each adapter takes a registry entry, introspects what it can, and emits System
Map records with `Evidence`. For every adapter the spec states: **inputs →
auto-derived → needs-manual → evidence emitted.**

**MCP adapter** — *new (no MCP client exists today; the repo only ships a
server).*
- *Input:* stdio/HTTP MCP endpoint from the registry.
- *Auto:* connect → `tools/list` → one `AccessSurface(kind=mcp_tool)` per tool;
  parse each tool's `inputSchema`/`outputSchema` (JSON Schema) → `DataObject` +
  `DataField`s; `operation` inferred from tool semantics (read vs write).
- *Manual:* `sensitivity`, business meaning of opaque fields, owner.
- *Evidence:* `kind=mcp_descriptor`, `locator="mcp://saas_a/<tool>"`, excerpt =
  the tool descriptor JSON.

**OpenAPI/REST adapter** — *new.*
- *Input:* `openapi.json` URL (or uploaded spec).
- *Auto:* each path+method → `AccessSurface(kind=openapi_endpoint)`; request/
  response bodies → `DataObject`/`DataField` (incl. nullable, types, `$ref`
  resolution); `securitySchemes` → `auth.method` + `scopes`; pagination params;
  declared webhooks → `AccessSurface(kind=webhook)`.
- *Manual:* sensitivity, ownership, semantics of generic fields.
- *Evidence:* `kind=openapi_spec`, `locator` = spec URL + JSON pointer.

**Repo adapter** — *reuse + extend.*
- *Reuse:* `repo_analysis/fastapi_provider.py` (routes), `model_provider.py`
  (ORM/Pydantic models), `compiler.py` (fact→Pen), the `EvidenceRecord`/
  `FactRecord` pipeline.
- *Extend (new):* detect (a) **middleware & auth guards** (decorators/
  dependencies) → `Connector(kind=middleware|auth)`; (b) **outbound HTTP/SDK
  calls** (requests/httpx/SDK clients) → `Connector` + `DataFlow` to the target
  system; (c) **validators / DB constraints / state transitions** →
  `BusinessRule` with `enforced_at` file:line.
- *Evidence:* `kind=repo_file`, `locator="path:line_start-line_end"`.

**Database adapter** — *new.*
- *Input:* DSN (via env).
- *Auto:* `information_schema` → tables → `AccessSurface(kind=db_table)` +
  `DataObject`; columns → `DataField` (type, nullable); PK/FK → object
  relationships; CHECK/NOT NULL/unique → candidate `BusinessRule`s.
- *Manual:* sensitivity (PII columns), ownership, business naming.
- *Evidence:* `kind=db_metadata`, `locator="db://<dsn>/<table>"`.

**Docs / manual adapter** — *new (lightweight).*
- *Input:* policy docs, data dictionaries, SME annotations.
- *Fills:* `description`, `owner`, `sensitivity`, business `statement`s for
  rules, and any cross-system semantics automation can't prove.
- *Evidence:* `kind=doc` or `kind=manual`.

Adapters never overwrite a `review_status=accepted` human edit; they propose
(`needs_review`) and let the existing review flow (`PenFile.review`, the
demo-site review cards) confirm.

---

## §5 Rule & flow extraction methodology

**Business rules** are synthesized (not just hand-authored) from:

| Signal | Source | Becomes |
|---|---|---|
| Field validators / schema constraints | repo, OpenAPI, DB | `BusinessRule(category=validation)` |
| State machines / status transitions | repo (enums + transition fns) | `BusinessRule(category=state_machine)` |
| Route guards / permission checks | repo middleware/auth | `BusinessRule(category=gate)` |
| DB constraints (CHECK/unique/NOT NULL) | DB adapter | `BusinessRule(category=invariant)` |
| Lifecycle ("X cannot be deleted once finalized") | docs + code | `BusinessRule(category=lifecycle)` |

Every synthesized rule carries `enforced_at` (the code/DB locator) and a
`status` of `enforced` (proven), `gap` (stated in a doc but no enforcement
found), or `deferred`. A `gap` is itself a useful finding.

**Data flows & connectors** are derived from:
- Surface inputs/outputs (what a tool/endpoint reads vs returns).
- Service-to-service calls (one system's repo calls another's API/MCP).
- Webhook/event triggers and scheduled syncs (`Connector(kind=webhook|sync)`).
- DB reads/writes.
- **Shared identifiers across systems** — the strongest cross-system seam signal
  (e.g. SaaS C's order carries SaaS B's `device_id`). Middleware/SaaS seams are
  **first-class `Connector`s**, never just diagram labels.

---

## §6 Output contract — projections

The System Map projects into the artifacts DataRoot already produces. Two
targets, both reusing existing code.

### → PenFile (diagrams) — reuse `repo_analysis/compiler.py` + `generators/pen_builder.py`

| System Map | PenFile (`models/pen.py`) |
|---|---|
| `DataObject` | `Entity` (set `maps_to_entity_id` back-link) |
| `DataField` | `Attribute` (+ `sensitivity` → metadata) |
| object relationships (PK/FK, shared IDs) | `Relationship` |
| `EnterpriseSystem` (external) / `AccessSurface` | DFD `ExternalEntity` / `Process` |
| `DataFlow` | `DataFlow` |
| `BusinessRule` | `DfdModel.business_rules[]` (pass-through, already supported) |
| `Connector` | `DfdModel.connectors[]` (pass-through, already supported) |
| `Evidence` | `Attribute.evidence` / rule+connector `enforced_at` |

The fact→Pen compilation pattern in `repo_analysis/compiler.py` is the template;
the System Map is just a richer, multi-source fact set feeding the same step.

### → GitKB (searchable graph) — reuse the existing MCP tools

Emit one GitKB document per record with new doc types: `system`,
`access_surface`, `data_object`, `data_field`, `data_flow`, `business_rule`,
`connector`, `evidence`. Wikilinks encode the graph (object→fields,
surface→object, flow→systems). This makes the entire map queryable through the
**existing** server tools (`kb_search`, `kb_list`, `kb_show`, `kb_graph`,
`summarize_workspace`) with **zero new tool code** — see [mcp-server.md](mcp-server.md).

### Generated views (each a projection, each evidence-traceable)
- **ERD** — persistent data objects, fields, keys, ownership.
- **DFD** — systems, processes, stores, external actors, flows, endpoint/tool
  triggers.
- **Schema/contract docs** — per surface (API/MCP) and per object, field-level
  with sensitivity + auth.
- **Business-rule catalog** — grouped by scope, each with enforcement evidence
  and `enforced`/`gap`/`deferred` status.
- **Connector/middleware map** — auth boundaries, shared services, fan-outs,
  webhooks, cross-SaaS seams.

---

## §7 Worked example — SaaS A / B / C (generic)

Three systems, one ecosystem. *(Abstract on purpose — no real vendor/domain.)*

**SaaS A — MCP server, operational data.**
- `EnterpriseSystem{ id: saas_a, kind: mcp_server }`
- MCP adapter `tools/list` → `AccessSurface{ kind: mcp_tool, name: "get_theta", operation: read }` and `"get_iota"`.
- `get_theta`'s `outputSchema` → `DataObject{ name: ThetaReading }` with
  `DataField`s `id [auto]`, `value:number [auto]`, `captured_at:timestamp
  [auto]`, `subject_ref:string [auto, sensitivity: internal (manual)]`.
- Evidence: `mcp_descriptor`, `locator: mcp://saas_a/get_theta`.

**SaaS B — REST/OpenAPI, device/compliance data.**
- `EnterpriseSystem{ id: saas_b, kind: saas }`
- OpenAPI adapter → `AccessSurface{ kind: openapi_endpoint, name: "GET /devices/{id}", auth: {method: bearer, scopes: [devices:read]} }`.
- Response → `DataObject{ name: Device }`: `device_id [auto]`,
  `n9102_status:enum [auto]`, `compliance_expires_at:date [auto]`,
  `owner_email:string [auto, sensitivity: pii (manual)]`.
- A validator in B's spec ("`n9102_status` ∈ {pass,fail,pending}") →
  `BusinessRule{ category: validation, enforced_at: openapi://saas_b#/paths/devices }`.

**SaaS C — order fulfillment.**
- `EnterpriseSystem{ id: saas_c, kind: saas }`, surface `"GET /orders"` →
  `DataObject{ name: Order }`: `order_id`, `customer_id [pii]`,
  `device_id [auto]`, `status [auto]`, `fulfilled_at`.

**Cross-system seam (the payoff).** `Order.device_id` matches `Device.device_id`
→ a `Connector{ kind: seam, from_system: saas_c, to_systems: [saas_b],
contract: "Order.device_id → Device.device_id", trigger: "order references a
device" }`, plus a `DataFlow{ from: saas_c/Order, to: saas_b/Device }`.

**Projections.** ERD shows `ThetaReading`, `Device`, `Order` with the
`Order→Device` relationship; DFD shows A/B/C as external systems with processes
(`get_theta`, `GET /devices`, `GET /orders`) and the seam as a connector; the
schema doc lists every field with type + sensitivity + auth; the rule catalog
lists the `n9102_status` validation with its evidence; the connector map shows
the C→B seam. **Nothing in this example names Nexus.**

---

## §8 Phased implementation roadmap

| Phase | Deliverable | Reuses | New |
|---|---|---|---|
| **P0** | System Map Pydantic models + `.dataroot/connectors.yaml` registry schema | `repo_analysis/models.py` (Evidence/Fact), `config.py` | `src/dataroot/systemmap/` — implemented |
| **P1** | **MCP client adapter** (highest leverage) + repo-adapter extensions (middleware/auth/external calls/validators) | `fastapi_provider.py`, `model_provider.py` | MCP client; new detectors |
| **P2** | OpenAPI adapter + DB adapter | — | both |
| **P3** | Projection layer: System Map → PenFile + GitKB doc emission | `compiler.py`, `pen_builder.py`, GitKB store | projector |
| **P4** | Generated views + UI surfacing | `ConnectorsPanel.tsx`, `BusinessRulesPanel.tsx`, MCP tools | view generators |

P1's MCP client is the single most valuable missing piece: it's what turns
"SaaS A's MCP gives us theta/iota data" from a sentence into an inventory.

**P0 implementation note.** The initial core now lives in
`src/dataroot/systemmap/`: canonical Pydantic models, stable IDs, connector
registry loading, and a generic SaaS A/B/C fixture. Tests are in
`tests/test_systemmap.py`.

---

## §9 Acceptance checklist

The spec (and later the implementation) is on track when a builder can, from
this doc plus the referenced code:

1. Explain SaaS A/B/C end-to-end **without mentioning Nexus**.
2. Trace one MCP tool → `DataObject` → `DataField`s → `BusinessRule` →
   `DataFlow` → DFD Process, with `Evidence` at each hop.
3. Trace one REST endpoint → schema fields + auth/middleware → downstream flow.
4. State, per field, what is **[auto]** vs **[manual]**.
5. Show how every generated ERD/DFD/schema/rule item traces back to typed
   `Evidence`.
6. Name what's **reused** (`repo_analysis/compiler.py`, `pen_builder.py`, GitKB
   MCP tools, `BusinessRule`/`Connector`) vs **new** (MCP client, OpenAPI/DB
   adapters, rule/connector synthesis, connector registry).

**Implementation-round test fixtures (future):** MCP descriptor → System Map ·
OpenAPI spec → System Map · FastAPI repo → System Map · System Map → PenFile
ERD/DFD · rules/connectors survive the round-trip.

← Back to [architecture.md](architecture.md)
