---
purpose: FK inference, ID extraction, and wikilink rules.
prerequisites: CONTEXT.md, docs/architecture.md §3, docs/ingestion.md
read-when: Building the linker, testing cross-reference inference.
---

# Linking — docs/linking.md

FK inference, ID extraction, wikilink rules, and confidence scoring
for DataRoot's generic linker.

← Back to [CONTEXT.md](../CONTEXT.md)

## Stage 2 — dataroot link

After `dataroot profile` has written generic KB docs, `dataroot link`
walks the docs and adds [[wikilinks]] between them. This turns the
flat list of profile docs into a traversable graph.

## Link types and rules

### file → table

Link each `source_file` doc to the `table` docs that came from it.

Wikilink: `[[source_files/path/to/file.csv]] → [[tables/path/to/file.csv]]`

### table → column

Link each `table` doc to its `column` docs.

Wikilink: `[[tables/path/to/file.csv]] → [[columns/path/to/file.csv/column_name]]`

### likely primary keys

If a `column` doc has `is_likely_pk: true` and `unique_count ≈ row_count`:

- Link the column to the table's row_group docs (if any exist).
- The column is the natural key for joining.

Wikilink: `[[columns/path/to/file.csv/id]] → [[tables/path/to/file.csv]] (PK)`

### likely foreign keys

If column A in table X and column B in table Y share:

- Same name pattern (e.g., both have `_id` suffix)
- Overlapping values in the first 100 rows

Then add a wikilink from column A to column B.

Wikilink: `[[columns/path/to/file.csv/station_id]] → [[columns/other/file.csv/station_id]] (FK, confidence)`

Confidence: 0.9 if value overlap > 80%, 0.7 if > 50%, 0.5 otherwise.

### repeated IDs across tables

If the same string ID value appears in more than one table's column
(e.g., "STATION_001" appears in both water_quality.csv and stations.csv):

- Create a `relationship` doc for the ID.
- Link all columns that contain this ID to the relationship doc.

Wikilink: `[[columns/path/to/file.csv/station_id]] → [[relationships/station_001]] (repeated ID)`

### date/time columns

If two tables both have a date/datetime column:

- Create a `relationship` doc for temporal co-occurrence.
- If the same date appears in both tables, link them.

Wikilink: `[[tables/table_a]] → [[relationships/temporal/2024-01-15]] → [[tables/table_b]]`

### geo/location columns

If columns have names or values that look like locations (lat/lon, city names, station IDs):

- Link rows that share a location to a `candidate_entity` doc for that location.

Wikilink: `[[tables/water_quality/station_001]] → [[candidates/locations/station_001]]`

### measurement/unit columns

If a `column` doc has `is_likely_measurement: true`:

- Link the measurement doc to its parent table.
- Link to the unit doc if a unit was detected.

Wikilink: `[[measurements/path/to/file.csv/nitrate_mg_l]] → [[tables/path/to/file.csv]] (measurement)`

### text mentions

Regex scan over body content of all docs for known ID patterns:

- `AGT-[A-Z]{2,3}-[0-9]{3}` — cultivar IDs
- `[A-Z]{2,3}-[0-9]{4}-[0-9]{3}` — trial IDs
- `station_[0-9]{3}` — station IDs
- Any column name that appears as a value in another doc's body

For each match, add a wikilink with confidence 0.6.

## Confidence scoring

All inferred wikilinks carry a confidence score. If GitKB supports
edge metadata, store it there. Otherwise store it as a comment in
the wikilink:

```
[[cultivars/A-CUL-TOM-014|cultivar match (FK, 1.0)]]
[[stations/station_001|relationship (FK, 0.9)]]
[[tables/water_quality|repeated ID (0.7)]]
```

Confidence thresholds:

- 1.0: Direct FK match (column name matches target table's PK column name, values align)
- 0.9: Strong FK candidate (>80% value overlap)
- 0.8: FASTA header parse
- 0.7: Moderate FK candidate (>50% value overlap)
- 0.6: Text mention in body
- 0.5: Weak candidate, human review recommended

## Deterministic vs. fuzzy

The linker is mostly deterministic Python code. It calls Codex (Role B)
only for:

- Ambiguous column name mapping (e.g., "ID" could refer to multiple tables)
- Fuzzy text matches where regex isn't reliable
- Names that could be aliases for the same entity

When calling Codex for fuzzy resolution, pass the domain spec to help
with alias resolution.

## After dataroot link

After linking, the agent can use kb_graph to traverse from any doc.
The graph shows all inferred relationships with confidence scores.

← Back to [CONTEXT.md](../CONTEXT.md)
