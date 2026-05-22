# Miro Fundamental Functionality

This document is the non-negotiable behavior contract for the DataRoot Miro demo board. If renderer code changes, these behaviors must stay intact unless this file is intentionally updated in the same change.

## Demo Sections

- The board has one protected top area named `DataRoot Provenance`.
- `dataroot miro-refresh-board` is append-only by default and must not delete existing board content unless `--replace-existing` is explicitly passed.
- Each mock company has a `Standard Demo` section and a `Live Ask` section.
- Each section keeps the same top skeleton: `Question`, `DataRoot Parsing & Retrieval`, `Evidence Path`, and `Final Answer`.
- `Final Answer` is positioned under `Question`.
- Dynamic evidence below the top skeleton is grouped into source/type columns, using dataset or table source first and provenance stage only when no source label is available.

## Required Arrows

- Every section must have a fixed right-angle arrow from `Question` to `Final Answer`.
- Every section must have the fixed right-angle flow chain:
  - `Question -> DataRoot Parsing & Retrieval`
  - `DataRoot Parsing & Retrieval -> Evidence Path`
  - `Evidence Path -> Final Answer`
- Every answer with evidence cards must draw up to two evidence support arrows from specific cards in the reference/data-type sections to `Final Answer`.
- Evidence support arrow selection order is:
  - `primary`
  - `secondary`
  - `normal`
- Selection preserves planner/card order inside each priority bucket.
- If one eligible evidence card exists, draw one support arrow.
- If no eligible evidence cards exist, draw no support arrows and record that fact in audit/proof metadata.

## Live Ask Updates

- Each `Live Ask` section has one editable text item labeled `Type your question here:` in the top frame.
- Live ask updates preserve the user's editable question text item and do not recreate it if it already exists.
- A live ask updates only the selected company's `Live Ask` section.
- Existing top skeleton shapes are patched in place.
- Existing fixed top arrows are patched or created in place; they must not be deleted by evidence refresh cleanup.
- The `Final Answer` shape must use the actual live answer text, shortened to one or two sentences, not retrieval/status copy.
- Dynamic reference/data-type sections are replaced for the new answer.
- Old evidence support arrows are deleted with their old evidence cards.
- New support arrows are created after the new reference/data-type cards are rendered.

## Routing

- Miro connectors must use `shape: "elbowed"` for right-angle routing.
- Fixed top arrows use explicit endpoint sides and must not share the same route into `Final Answer`.
- `Question -> Final Answer` enters `Final Answer` at the top.
- `Evidence Path -> Final Answer` enters `Final Answer` from the right.
- Evidence support arrows connect from evidence card left sides to the bottom of `Final Answer`.
- Evidence support arrows carry no label.
