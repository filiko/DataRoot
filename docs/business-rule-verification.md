---
purpose: Steering doc for business-rule verification — how rules are verified across English ↔ ERD ↔ real systems (middleware/SaaS).
prerequisites: data-access-map.md, architecture.md
read-when: Designing or building business-rule verification; deciding how rules relate to ERD structure and to the systems employees actually use.
---

# Business-Rule Verification — docs/business-rule-verification.md

This is a **steering doc**, not a line-level build spec. It frames *what business-rule
verification means in DataRoot* before we implement it, so the build is pointed the
right way.

The thesis, in one sentence: **a business rule is only "verified" when it is traced
across three layers — the English requirement, the ERD structure that encodes it, and
the real systems/surfaces where the data is actually entered and extracted.** Checking
the diagram alone is not verification; the systems the business runs on
(middleware/SaaS/tools) are where a rule is actually enforced or violated.

← Related: [data-access-map.md](data-access-map.md) (the System Map) ·
[architecture.md](architecture.md) ·
[generators/diagram_rules.md](../demo-site/backend/generators/diagram_rules.md) (the rules engine) ·
[glossary.md](glossary.md)

---

## §1 Purpose & thesis

A business rule is an English-language requirement: *"a customer may place many orders,"*
*"a batch must be released before it can ship,"* *"an order must reference a valid device."*
DataRoot already stores these as `BusinessRule` objects, draws the structural ones as ERDs,
and (since the System Map work) inventories the systems data lives in. **Verification** is
the missing connective tissue: deciding, with evidence, whether a stated rule actually
holds — and *where*.

The three layers and why all three are required:

| Layer | What it is | What it can prove | What it can't |
|---|---|---|---|
| **English rule** | the requirement, in words | intent | nothing by itself |
| **ERD structure** | cardinality, keys, FKs | the *model* permits/forbids it | not whether real data obeys it |
| **Real systems** | SaaS/API/DB surfaces + connectors where employees input/extract data | where the rule is enforced or violable in practice | not the intent |

> **Why middleware/SaaS is not optional.** The same rule has different verification answers
> depending on where the data lives. "An order must reference a valid device" is a foreign
> key *in one database* — but if `Order` lives in SaaS C and `Device` in SaaS B, it's a
> **cross-system seam**: nothing in either system's schema enforces it, and it can only be
> verified by observing both surfaces and the connector between them. Employees create
> orders in one tool and devices in another; the rule lives in the *seam*, not the diagram.
> This is why verification and the System Map are the same project, not two.

## §2 Theory backbone (operational, not a textbook)

Business rules **determine cardinality and connectivity** (Watt, *Database Design 2nd Ed.*
Ch 9, *Integrity Rules and Constraints*; Hernandez, *Database Design for Mere Mortals*; IBM
DB2 relationship-design guidance). The English→structure translation DataRoot uses:

| Rule wording | ERD meaning | DataRoot encoding (`models/pen.py`) |
|---|---|---|
| may | optional → minimum 0 | `Cardinality.from_min/to_min = 0`; FK attribute `nullable = true` |
| must | mandatory → minimum 1 | `from_min/to_min = 1`; FK `nullable = false` |
| one / only one | maximum 1 | `from_max/to_max = 1` |
| many / one or more | maximum many | `from_max/to_max = "many"` |
| many-to-many | needs an associative entity | both sides `"many"` → must have a join `Entity` (else ERD-02) |
| cannot be duplicated | uniqueness / candidate key | `Attribute.key_role = "unique"` or `"business_key"` |
| must refer to an existing thing | referential integrity (FK→PK) | relationship FK endpoint → real PK on the to-entity |
| depends on another thing to exist | weak / identifying relationship | `Entity.kind = "weak_entity"` + identifying relationship |

The three classical integrity rules (Ch 9) are the structural verification basis:
**entity integrity** (every entity has a primary key), **referential integrity** (every FK
points at an existing PK), **domain integrity** (values respect type/constraints). DataRoot's
`generators/diagram_rules.py` checks some structure today (orphans, M:N-without-join) but
**not** referential integrity, cardinality/optionality coherence, uniqueness, or weak-entity
— those are the structural checks this work adds.

## §3 The three layers in DataRoot terms

| Layer | Model | Where |
|---|---|---|
| English rule | `BusinessRule` (`title`, `statement`, `condition`, `category`, `status` enforced/gap/deferred, `verified_by`, `enforced_at`, `entity_id`, `process_id`) | `demo-site/backend/models/pen.py` |
| ERD structure | `Entity` (`kind`), `Attribute` (`key_role`), `Relationship` + `Cardinality` (`from_min/from_max/to_min/to_max`), `RelationshipEndpoint` (`entity_id`, `attribute_id`) | `models/pen.py` |
| Real systems | `EnterpriseSystem` → `AccessSurface` → `DataObject`/`DataField` (`sensitivity`), `Connector` (`from_system`/`to_systems`), `DataFlow`, `Evidence` | `src/dataroot/systemmap/models.py` |

Cross-references that already exist to thread the layers together:
`BusinessRule.entity_id → Entity.id`; `DataObject.maps_to_entity_id → Entity.id`;
`Connector.enforced_at` / `BusinessRule.enforced_at → code file:line`; `Evidence.locator →`
the proving source (`repo_file`, `openapi_spec`, `db_metadata`, `mcp_descriptor`, …).

**Gap to flag:** `BusinessRule` links to an `entity_id`/`process_id` but **not to a
`Relationship`** (so a rule about cardinality can't yet name *which* relationship) and **not
to a `system`/`surface`** (so a rule can't yet name *where* its data lives). §9 proposes
adding those links.

## §4 Business-rule taxonomy → which layer verifies it

Every rule is one of three kinds; the kind determines the verifying layer and the evidence:

1. **Structural rule** — cardinality, optionality, uniqueness, referential, weak-entity.
   *Verified against the ERD* via integrity checks (Ch 9). Evidence: the ERD itself.
   (`category` ≈ `invariant`.)
2. **Behavioral rule** — validations, state machines, gates, lifecycle ("a batch must be
   released before shipping"). *Verified against code/process* — the `enforced_at` pointers
   and the P1 detectors (`systemmap_provider.collect_business_rules`). Evidence: `repo_file`.
   (`category` ∈ `validation`/`state_machine`/`gate`/`lifecycle`.)
3. **Cross-system rule** — a value must exist in / flow to another system. *Verified against
   the System Map* — connectors, shared-ID seams, data flows. Evidence: `openapi_spec`/
   `db_metadata`/`mcp_descriptor` from the two surfaces + the connector.

A single rule can have more than one kind (e.g. a referential rule that is also cross-system);
it is then verified on every applicable layer and its status is the weakest of them.

## §5 The verification model

Every rule is assessed on three **dimensions**:

- **(a) Structural consistency** — does the ERD encode the rule correctly? (FK exists and
  points to a real PK; mandatory side ⇒ non-nullable FK; M:N ⇒ join entity; unique rule ⇒
  unique/business key.)
- **(b) Enforcement evidence** — is there code or a DB constraint that actually enforces it?
  (`enforced_at` resolves to real code; a validator/guard/CHECK exists.)
- **(c) System grounding** — which system/surface *owns* the data, where do employees enter/
  extract it, and can the rule be violated there? (Mapped via `DataObject`/`AccessSurface`/
  `Connector`.)

Result vocabulary, mapped onto the existing `BusinessRule.status` + an explicit new state:

| Status | Meaning |
|---|---|
| **enforced** | consistent on every applicable dimension, with evidence |
| **gap** | a dimension contradicts the rule (e.g. ERD allows what the rule forbids; no enforcement found; cross-system value unguarded) |
| **deferred** | intentionally not enforced yet (human-marked) |
| **unverifiable / needs-source** *(new)* | can't be checked because the owning system/surface isn't mapped yet — points the user at what to connect |

`verified_by` carries the evidence trail: which dimension(s) passed and the proving
`Evidence`/locator (e.g. `"structural: rel_x cardinality"`, `"repo_file: …:120-140"`,
`"seam: saas_c.Order.device_id→saas_b.Device.id"`). Findings on dimension (a) also surface as
diagram-quality warnings (`pen.review.warnings`) through the existing `apply_rules_gate`.

## §6 Why middleware/SaaS is intrinsic (worked argument)

Take "**an order must reference a valid device.**"

- **One database:** referential rule. ERD FK `Order.device_id → Device.id`, `nullable=false`.
  Verified on dimensions (a)+(b): FK present + DB enforces it. `status=enforced`.
- **Two SaaS systems** (Order in SaaS C, Device in SaaS B): the *same English rule* is now a
  **cross-system seam**. Neither system's schema enforces it; SaaS C will happily store an
  `Order` with a `device_id` SaaS B never heard of. It's verifiable only by (c): observing
  `DataObject Order` (SaaS C) and `DataObject Device` (SaaS B), confirming the shared field,
  and finding the `Connector` (and ideally a sync/validation) that reconciles them. If no
  connector exists → `status=gap` (the business *believes* the rule but nothing enforces it).
  If neither surface is mapped → `unverifiable / needs-source`.

The lesson: **the verification answer is a property of where the data lives, not of the
sentence.** That's why we can't verify rules without the System Map — and why "business rule
verification" *is* the middleware/SaaS work, framed from the rules side.

## §7 Worked generic example (SaaS A / B / C)

*Abstract systems only — Nexus is an example pack, never the reference.*

- **Structural rule** — "a customer may place many orders; each order must belong to exactly
  one customer." → ERD `CUSTOMER 1 ── 0..* ORDER`, FK `Order.customer_id` non-null. Verify (a):
  cardinality + non-null FK + FK→PK. Evidence: ERD. Likely `enforced`.
- **Behavioral rule** — "n9102 status must be one of {pass, fail, pending}." → SaaS B's
  `Device.n9102_status` enum. Verify (b): the validator/enum in B's OpenAPI/code (`enforced_at`).
  Evidence: `openapi_spec`/`repo_file`.
- **Cross-system rule** — "every fulfilled order must reference a device that passed n9102."
  → seam: `saas_c.Order.device_id → saas_b.Device.id` **and** B's `n9102_status = pass`. Verify
  (c): both surfaces mapped + a `Connector` + the status check. Evidence: the two
  `DataObject`s + `Connector`. If the connector exists but nothing checks `n9102_status`
  → `gap`.

Each rule shows its status, the verifying dimension(s), and the evidence at each hop.

## §8 Architecture & phased roadmap (steering, not code)

Reuse-first. Phases are sequenced so each is independently shippable.

- **V0 — Structural integrity checks (ERD, Ch 9).** Extend `generators/diagram_rules.py`
  with new `ERD-05+` rules: referential integrity (FK endpoint → real PK), cardinality/
  optionality coherence (mandatory ⇒ non-null FK), uniqueness (unique rule ⇒ unique key),
  weak-entity-needs-identifying-relationship. Emits `WarningEntry`s through the existing
  `apply_rules_gate`. *Reuses:* the whole rules-gate + `WarningsBanner`.
- **V1 — Rule↔ERD statement verification.** A verifier that reads each `BusinessRule`,
  applies the §2 translation table to its `statement`, finds the relationship(s) on its
  `entity_id`, compares expected vs. actual cardinality/optionality, and sets `status` +
  `verified_by`. *Reuses:* `BusinessRule.status`, `BusinessRulesPanel` (already renders status).
- **V2 — System grounding.** Tie each rule to the System Map: which `DataObject`/`AccessSurface`
  owns its data (via `maps_to_entity_id`), and detect **cross-system seams** from shared
  identifiers → `Connector`s. Rules whose data spans systems get dimension-(c) verification;
  unmapped ones become `unverifiable / needs-source`. *Reuses:* `systemmap_provider`,
  `systemmap_to_pen`, the connector model; *new:* shared-ID seam detection.
- **V3 — Surfacing + evidence.** Show per-rule verification status + evidence trail in
  `BusinessRulesPanel`/`ConnectorsPanel`, and the structural findings in `WarningsBanner`,
  with click-through to the proving `Evidence`.

## §9 Open decisions (resolve before building)

1. **Link rules precisely.** Add `relationship_id` (and optional `surface_id`/`system_id`) to
   `BusinessRule` so a cardinality rule names its relationship and a cross-system rule names
   its surface? *Recommended:* yes — add optional fields, backward-compatible; precise linkage
   is what makes (a) and (c) checkable rather than heuristic.
2. **How to parse rule statements (V1).** Deterministic keyword translation (§2 table) vs.
   LLM-assisted extraction? *Recommended:* deterministic keyword pass first (transparent,
   testable, no model dependency), with an LLM-assist as an optional enrichment later.
3. **Where verification runs.** Inside the rules-gate on every mutation (like structural
   warnings) vs. an explicit "Verify rules" action? *Recommended:* structural (V0) in the
   gate; rule↔ERD + system grounding (V1/V2) on-demand + cached (they're heavier and touch the
   System Map).
4. **Representing "which system enforces/owns a rule."** A new field on `BusinessRule`, or
   derive it live from `DataObject.maps_to_entity_id`? *Recommended:* derive live in V2; only
   persist if performance demands it.
5. **Seam confidence threshold (V2).** How strong must a shared-ID match be to assert a
   cross-system rule is grounded (name + type + sample overlap)? *Recommended:* name+type match
   proposes a seam at `review_status=needs_review`; never auto-assert `enforced`.

## §10 Acceptance checklist (for this doc)

A builder can, from this doc alone: (1) explain the three-layer model and why middleware/SaaS
is intrinsic; (2) classify any rule as structural/behavioral/cross-system and name the verifying
layer + evidence; (3) apply the §2 table to turn an English rule into expected ERD structure
and say what a violation looks like; (4) trace the SaaS A/B/C example across all three layers;
(5) name what's reused vs. new per phase (V0–V3); (6) state each open decision with its
recommended default.

← Back to [data-access-map.md](data-access-map.md)
