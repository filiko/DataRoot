# Diagram Rules Catalog

This is the canonical catalog of structural rules the DFDMaker autogenerator
follows for ERDs (crow's-foot notation) and DFDs (Yourdon/Coad notation).

Each rule has:

| Field | Meaning |
|---|---|
| **id** | Stable identifier (e.g. `DFD-01`). Code references rules by this id. |
| **severity** | `blocking` (cannot save / corrupt) or `warn` (works but degraded). |
| **strategy** | `auto_regenerate` (engine fixes silently if safe) or `warn` (surface to user). |
| **scope** | Which side(s) of the diagram the rule applies to. |
| **detector** | Name of the function in `diagram_rules.py` that implements detection. |

The engine runs detectors after `propagate_erd_to_dfd()` so detection always
happens against the freshly-derived DFD.

**Source-of-truth principle.** The engine never mutates `pen.sources` or
`pen.erd`. It only regenerates derived DFD overlay objects. ERD-side issues
(e.g. an orphan entity) are surfaced as warnings — the user decides whether
to add a relationship, mark the entity rejected, or leave it as-is.

**user_modified is sacred.** Any DFD object with `user_modified=True` is
never auto-regenerated or removed; it can only become a warning.

---

## ERD rules

### ERD-01 — Orphan entity
- **severity:** warn
- **strategy:** warn
- **scope:** ERD
- **detector:** `_detect_erd_01_orphan_entity`

An ERD `Entity` participates in zero `Relationship`s. The entity itself is
valid (it carries attributes / business meaning), but it does not connect to
any other entity, so the auto-built DFD has nothing to flow into or out of
the corresponding DataStore. Result: a floating data store on the canvas.

We do not auto-delete entities. The user must either add a relationship,
mark the entity `review_status: rejected`, or accept that this is a
standalone reference table that will not appear in the DFD.

### ERD-02 — Direct M2M without join
- **severity:** blocking
- **strategy:** auto_regenerate (via existing `generate_erd_m2m_proposals`)
- **scope:** ERD
- **detector:** delegates to `sync_engine.validate()` (`DIRECT_M2M_NO_JOIN`)

A `Relationship` has cardinality `many-to-many` and there is no join entity.
This is not representable in a relational schema. The existing M2M proposal
flow handles this; the rules engine surfaces it as a blocking warning until
the user accepts a proposal.

### ERD-03 — Self-referential M2M without join
- **severity:** warn
- **strategy:** warn
- **scope:** ERD
- **detector:** `_detect_erd_03_self_m2m`

A relationship `from_.entity_id == to.entity_id` with cardinality
many-to-many and no join entity. We warn rather than block because it can be
intentional (e.g. a graph-style modeling decision) but is usually a mistake.

### ERD-04 — Orphan FK attribute
- **severity:** warn
- **strategy:** warn
- **scope:** ERD
- **detector:** `_detect_erd_04_orphan_fk`

An attribute has `key_role: foreign` but no `Relationship` references it
from either endpoint. The FK constraint will not be emitted by the SQL
exporter; the user should either add a relationship or change the key role.

### ERD-05 — Broken relationship endpoint (referential integrity)
- **severity:** warn
- **strategy:** warn
- **scope:** ERD
- **detector:** `_detect_erd_05_dangling_endpoint`

A `Relationship`'s `from`/`to` endpoint references a missing entity, or an
`attribute_id` that does not exist on the named entity. This is referential
integrity *of the model itself* — the relationship cannot be rendered or
exported correctly. (Part of the business-rule verification layer; see
[`docs/business-rule-verification.md`](../../../docs/business-rule-verification.md).)

### ERD-06 — Mandatory reference with nullable foreign key
- **severity:** warn
- **strategy:** warn
- **scope:** ERD
- **detector:** `_detect_erd_06_mandatory_nullable_fk`

For a many-to-one relationship whose referenced (`to`) side is mandatory
(`to_min ≥ 1`, `to_max = 1`), the foreign key on the `from` side
(`key_role: foreign`) must be NOT NULL. A nullable FK contradicts the stated
cardinality — the model claims every row must reference a parent, but the
column allows none. This is the structural half of "business rules determine
cardinality" (Watt Ch 9). Fix: make the FK NOT NULL, or set the relationship
optional (`to_min = 0`).

### ERD-07 — Entity without a primary key (entity integrity)
- **severity:** warn
- **strategy:** warn
- **scope:** ERD
- **detector:** `_detect_erd_07_entity_integrity`

An `Entity` has no attribute with `key_role: primary`. Entity integrity (Ch 9)
requires every entity's rows to be uniquely identifiable. The SQL exporter can
still add a surrogate key, but the modelled intent is missing — surface it so
the user confirms the identifier.

---

## DFD rules

### DFD-01 — Floating data store
- **severity:** warn
- **strategy:** auto_regenerate when `not user_modified` AND mapped ERD
  entity has zero relationships; else warn
- **scope:** DFD
- **detector:** `_detect_dfd_01_floating_store`

A `DataStore` has zero incoming and zero outgoing `DataFlow`s. The engine
removes autogen orphans whose mapped ERD entity is itself unrelated (i.e.
nothing the system can wire). Stores the user has touched, or whose mapped
entity has relationships the system somehow failed to wire, become
warnings.

### DFD-02 — Black hole process
- **severity:** warn
- **strategy:** auto_regenerate when `not user_modified` AND
  `mapped_relationship_id` is set; else warn
- **scope:** DFD
- **detector:** `_detect_dfd_02_black_hole`

(Yourdon/DeMarco anti-pattern.) A `Process` has incoming flows but no
outgoing flows. Data goes in and never comes out — an information sink that
violates the DFD principle that processes transform inputs into outputs.

### DFD-03 — Miracle process
- **severity:** warn
- **strategy:** auto_regenerate when `not user_modified` AND
  `mapped_relationship_id` is set; else warn
- **scope:** DFD
- **detector:** `_detect_dfd_03_miracle`

(Yourdon/DeMarco anti-pattern.) A `Process` has outgoing flows but no
incoming flows — data appears out of thin air, with no source. Either the
input flow is missing or the process should be an external entity.

### DFD-04 — Grey hole process
- **severity:** warn
- **strategy:** warn (cannot auto-fix without semantic analysis)
- **scope:** DFD
- **detector:** `_detect_dfd_04_grey_hole`

(Yourdon/DeMarco anti-pattern.) A `Process` produces output data that
cannot be derived from its inputs. Heuristic: the process has both inputs
and outputs but the outputs reference ERD attributes that none of its
inputs provide. Surfaced as a warning only.

### DFD-05 — Disconnected process
- **severity:** warn
- **strategy:** auto_regenerate when `not user_modified` AND
  `mapped_relationship_id is None`; else warn
- **scope:** DFD
- **detector:** `_detect_dfd_05_disconnected_process`

A `Process` has zero in-flows and zero out-flows. Pure noise on the canvas.

### DFD-06 — Floating external entity
- **severity:** warn
- **strategy:** auto_regenerate when `source == "auto"`; else warn
- **scope:** DFD
- **detector:** `_detect_dfd_06_floating_external`

An `ExternalEntity` has zero flows. External entities are typically created
manually, so we only auto-remove ones whose `source` field is `"auto"`.

### DFD-07 — Direct store-to-store flow
- **severity:** warn
- **strategy:** warn
- **scope:** DFD
- **detector:** delegates to `sync_engine.validate()`
  (`FLOW_MANUAL_STORE_TO_STORE`)

A `DataFlow` connects two `DataStore`s with no `Process` in between. In
classical DFD notation, every flow into or out of a store must pass through
a process. Already detected by the existing `validate()`; surfaced here
under a stable rule id.

### DFD-08 — Direct external-to-external flow
- **severity:** warn
- **strategy:** warn
- **scope:** DFD
- **detector:** `_detect_dfd_08_external_to_external`

A `DataFlow` connects two `ExternalEntity` nodes directly. Outside the
system boundary; not part of a DFD.

### DFD-09 — Broken flow endpoint
- **severity:** blocking
- **strategy:** auto_regenerate (delete dangling flow)
- **scope:** DFD
- **detector:** delegates to `sync_engine.validate()`
  (`FLOW_MISSING_FROM_NODE` / `FLOW_MISSING_TO_NODE`)

A `DataFlow.from_` or `to` references a node that does not exist. Already
detected by existing `validate()`; the regeneration step drops dangling
flows.

### DFD-10 — Read-only data store
- **severity:** warn
- **strategy:** warn
- **scope:** DFD
- **detector:** `_detect_dfd_10_read_only_store`

A `DataStore` has only outgoing flows — nothing writes to it. Suggests the
diagram is missing the process that creates / updates this data.

### DFD-11 — Write-only data store
- **severity:** warn
- **strategy:** warn
- **scope:** DFD
- **detector:** `_detect_dfd_11_write_only_store`

A `DataStore` has only incoming flows — nothing reads from it. Suggests
the data is being captured but never consumed.

---

## References

- Yourdon, E. & Coad, P. — *Object-Oriented Analysis* (DFD anti-patterns:
  black hole, miracle, grey hole)
- DeMarco, T. — *Structured Analysis and System Specification*
- Chen, P. & Codd, E. — entity-relationship modeling fundamentals
- Crow's-foot notation overview:
  https://www.freecodecamp.org/news/crows-foot-notation-relationship-symbols-and-how-to-read-diagrams/
