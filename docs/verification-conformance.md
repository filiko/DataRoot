# Verification Conformance: how we know the verifier is correct

DataRoot's business-rule verification has four layers (V0 structural integrity,
V1 rule↔cardinality, V2 cross-system seams/grounding, P3 projection — see
[business-rule-verification.md](business-rule-verification.md)). This document
answers a separate question: **what authoritative standard do we measure those
layers against, and where is that encoded as runnable tests?**

## Is there a representative example we can verify against?

**Yes, for the ERD / business-rule core (V0 + V1).** Watt & Eng's *Database
Design* is a standard teaching text whose exercises pair an English business-rule
paragraph with a published **answer key** — entities, primary keys, relationships,
cardinality, optionality, and the associative entities that resolve
many-to-many relationships. That is exactly the labeled input→expected-ERD data a
conformance corpus needs.

> **Watt, A. & Eng, N. (2014). *Database Design – 2nd Edition.* BCcampus /
> OpenTextBC. Appendix B "Sample ERD Exercises" + Ch. 9 "Integrity Rules and
> Constraints". Licensed CC BY 4.0.**
> https://opentextbc.ca/dbdesign01/back-matter/appendix-b-erd-exercises/

The CC BY 4.0 license lets us reproduce the exercises in the test suite with
attribution. We encode **Exercise 1 (Manufacturer)** and **Exercise 2 (Car
Dealership)**.

**No, for the cross-system layer (V2).** There is no textbook with answer-keyed
*cross-system* exercises analogous to Watt. Cross-system data rules are governed
by a pattern/principle literature, not a graded-exercise tradition. We ground V2
on the authoritative principle sources and author a labeled corpus from them:

- **Helland, P. (2005). "Data on the Outside vs. Data on the Inside." CIDR /
  ACM Queue.** Data that crosses a service/system boundary is referenced by
  immutable key and is *not* enforced by either database. This is the precise
  justification for treating a cross-system reference as a **seam** (needs-review,
  never auto-asserted) rather than a foreign key.
- **Hohpe, G. & Woolf, B. (2003). *Enterprise Integration Patterns.*** The
  integration styles (File Transfer / Shared Database / RPC / Messaging) and the
  vocabulary for how systems exchange data across a boundary.
- **DAMA-DMBOK, Ch. 8 (Data Integration & Interoperability).** Referential
  integrity and authoritative-source designation across systems.

The practical representative example for V2 is therefore the **SaaS A/B/C System
Map fixture** (`src/dataroot/systemmap/fixtures.py::generic_saas_abc_map`),
extended with authored variants — built to the Helland/EIP/DMBOK principles.

## The corpus, by tier

### Tier 1 — verification conformance (V0 + V1), deterministic

`demo-site/backend/evals/watt_corpus.py` holds the answer-key `PenFile`s and the
verbatim rule text; `demo-site/backend/tests/test_textbook_erd_conformance.py`
asserts the verifier agrees with the textbook:

| Corpus case | Source | What it pins |
|---|---|---|
| Manufacturer / Car Dealership clean ERD | Watt B-1 / B-2 | answer keys raise **no** ERD-02/05/06/07 |
| M:N resolved by junction (CompSupp, Build, WorkOn) | Watt B-1 / B-2 | a properly-resolved M:N does **not** trip ERD-02 |
| "A salesperson may sell many cars, but each car is sold by only one salesperson" | Watt B-2 | two-sided sentence → V1 **enforced** (one-to-many) |
| "A car that is serviced may or may not need parts" | Watt B-2 | optionality narrative → rule **left untouched** |
| "A product cannot exist without components" | Watt B-1 | mandatory-only participation → **left untouched** (not clobbered) |
| nullable FK on a mandatory reference | Ch. 9 | → **ERD-06** |
| dangling relationship endpoint | Ch. 9 (referential integrity) | → **ERD-05** |
| entity with no primary key | Ch. 9 (entity integrity) | → **ERD-07** |
| unresolved M:N (direct, no junction, pending join proposal) | Watt B (resolve-M:N step) | → **ERD-02** |
| rule contradicting the relationship cardinality | Watt translation table | → V1 **gap** |
| verbatim sentences → `parse_cardinality_expectation` | Watt translation table | may→optional, must→mandatory, only-one→max 1, many→max many, two-sided→one-to-many |

### Tier 2 — generation eval (V0 + V1), LLM, scored

The literal textbook task: *read the paragraph, produce the ERD.*

- `generators/erd_from_text.py` — prompts an LLM (MiniMax, **temperature 0**)
  with the business-rule paragraph + the `ErdModel` JSON schema, then validates
  the response with `PenFile.model_validate` + `apply_rules_gate`.
- `evals/erd_score.py` — a **pure, deterministic** scorer: entity / relationship
  precision-recall-F1 (name-matched), PK accuracy, and cardinality-shape accuracy
  against the Watt answer key.
- `evals/run_erd_eval.py` — runs both exercises and prints a scorecard with
  targets (entity recall ≥ 0.9, cardinality accuracy ≥ 0.8).

The scorer logic is unit-tested without any API key
(`tests/test_erd_score.py`: scoring the answer key against itself is perfect;
each corruption degrades exactly the right metric). The live LLM generation runs
only when `MINIMAX_API_KEY` is set (otherwise the eval and its pytest cases skip
cleanly). The LLM generation runs on MiniMax by design, off the main model.

### Tier 3 — V2 cross-system corpus (authored, principle-grounded)

`tests/test_systemmap_seams.py` checks `detect_cross_system_seams` and
`ground_business_rules` on the SaaS A/B/C fixture and authored variants:
single-system vs cross-system-grounded (via connector and via a detected seam)
vs cross-system-gap, plus regression guards — a **blank/unrelated connector must
not suppress a real seam**, and **identifier-like field names (`uuid`, `grid`,
`valid`) must not parse as foreign references**.

## The corpus is the regression gate

These tests encode *correct* behavior, so they go red on the verifier defects
the code review surfaced. Reaching green required (and now locks in):

1. `business_rule_verification` — don't clobber a rule's status to `gap` when it
   has no resolvable relationship and no explicit structural link; the canonical
   two-sided "many … but only one" sentence now parses as one-to-many.
2. `seams._connector_covers` — a blank/unrelated contract no longer suppresses a
   distinct seam.
3. `seams._REF_SUFFIX` — a separator is required before the `id`/`ref`/`key`
   suffix, and bare `uuid` is no longer treated as a reference.

(Two other review findings — the repo-analysis HTTP-client over-detection in
`repo_analysis/systemmap_provider.py` and the `system_map_to_pen` id collisions —
are real but are **not** exercised by this corpus, which operates on hand-built
ERDs and System Maps rather than repo analysis.)

## Running it

```bash
# Tier 1 + Tier 2 scorer (deterministic; no API key needed)
cd demo-site/backend
../../.venv/bin/python -m pytest tests/test_textbook_erd_conformance.py tests/test_erd_score.py -q

# Tier 2 live generation eval (needs MINIMAX_API_KEY)
MINIMAX_API_KEY=… ../../.venv/bin/python -m evals.run_erd_eval

# Tier 3 cross-system corpus
cd ../..
.venv/bin/python -m pytest tests/test_systemmap_seams.py -q
```
