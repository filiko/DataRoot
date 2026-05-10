---
purpose: How DataRoot ingests files into KB documents.
prerequisites: CONTEXT.md, docs/architecture.md §3
read-when: Building parsers, document emission, or testing ingestion.
---

# Ingestion — docs/ingestion.md

Parsers, document-emission behavior, and per-file-type handling for
DataRoot's Stage 1 workspace profiler.

← Back to [CONTEXT.md](../CONTEXT.md)

## Stage 1 — profile_workspace

`dataroot profile <path>` walks a directory recursively, dispatches
by file extension to a parser, produces normalized KB document records
for each thing it finds, and hands those records to KBStore.

## File type handling

### CSV (.csv)

Use pandas.read_csv. For each file:

- Create one `source_file` doc with: path, size, encoding (guess via chardet), delimiter, line_count, sample_bytes.
- Create one `table` doc with: row_count, column_count, header_row, delimiter, sample_rows (first 5).
- Create one `column` doc per column with: name, inferred_type (string/int/float/date/bool), null_pct, unique_count, sample_values (first 10), is_likely_pk (unique_count ≈ row_count), is_likely_fk (detected via name patterns like *_id, id_, foreign_), is_likely_measurement (numeric with unit-like name), unit (detected from column name or sample values like "mg_l", "ppb").

### XLSX (.xlsx)

Use openpyxl or pandas.read_excel. Same as CSV but also:

- Detect sheet names. If multiple sheets, treat each sheet as a separate table within the same source_file doc.
- sample_rows comes from the first sheet.

### JSON (.json)

Use json.load. Handle both:

- Array of objects → treat as a table (each object is a row).
- Single object → treat as a nested document, profile key paths as pseudo-columns.

Create `source_file` and `table` docs. For nested objects, also create `measurement` docs for numeric leaf values and `candidate_entity` docs for string IDs found in the tree.

### Markdown (.md)

Parse frontmatter (YAML block at top). Detect:

- Table syntax (| col | col |) → extract columns.
- List syntax for ID patterns (e.g., - **Cultivar:** A-CUL-TOM-014).
- Wikilink syntax [[slug]] for cross-references.

Create `source_file` doc and `table` doc if tables found. Create `candidate_entity` docs for detected IDs.

### FASTA (.fasta, .fa, .fna)

Split on `>`. For each sequence:

- Parse header: `>{gene_id}|{cultivar_id}|{variant}|{produces_compound_id}`.
- Create one `source_file` doc for the file.
- Create one `candidate_entity` doc per entry with the parsed fields.
- The sequence itself is stored as sample_bytes in the doc body.

### Other files

If present and not recognized, create a `source_file` doc with type "unknown" and sample_bytes of the first 512 bytes.

## KB document types produced

### source_file

```yaml
type: source_file
slug: source_files/path/to/file.csv
title: file.csv
path: path/to/file.csv
size_bytes: 12345
file_type: csv
encoding: utf-8
line_count: 847
sample_bytes: "ID,Name,Value\n1,Foo,0.5..."
```

### table

```yaml
type: table
slug: tables/path/to/file.csv
title: file.csv
source_file: source_files/path/to/file.csv
row_count: 847
column_count: 8
header_row: ["ID", "Name", "Value", ...]
delimiter: ","
sample_rows:
  - ["1", "Foo", "0.5", ...]
  - ["2", "Bar", "0.3", ...]
```

### column

```yaml
type: column
slug: columns/path/to/file.csv/station_id
title: station_id
table: tables/path/to/file.csv
name: station_id
position: 0
inferred_type: string
null_pct: 0
unique_count: 42
is_likely_pk: false
is_likely_fk: true
is_likely_measurement: false
sample_values: ["STATION_001", "STATION_002", ...]
```

### candidate_entity

```yaml
type: candidate_entity
slug: candidates/path/to/file.csv/entry_1
title: A-CUL-TOM-014
detected_from: fasta_header
raw_value: "A-GEN-PMR3|A-CUL-TOM-014|A-TRT-PMR|variant=pmr_resistant"
fields:
  gene_id: TPS-LIM
  cultivar_id: A-CUL-TOM-014
  variant: variant_A
  produces_compound: LIMONENE
```

### measurement

```yaml
type: measurement
slug: measurements/path/to/file.csv/nitrate_mg_l
title: nitrate_mg_l
table: tables/path/to/file.csv
column: columns/path/to/file.csv/nitrate_mg_l
unit: mg/L
detected_from: column_name_pattern
sample_values: [8.2, 12.7, 3.1, ...]
```

## Document emission behavior

The profiler emits a list of `(doc_type, doc_slug, frontmatter, body)`
records. It does not own persistence. It calls the configured KBStore
adapter, whose preferred implementation is GitKBStore:

- `write(record, commit_message=None)` persists the record through GitKB.
- `update(slug, content, commit_message=None)` edits existing records through GitKB.
- `read(slug)`, `search(query)`, and `graph(slug, depth)` are adapter calls over GitKB tools.
- Markdown/frontmatter remains the transport shape because that is GitKB's document model.
- Wikilinks in body are indexed by GitKB as graph edges.

DataRoot should not bypass GitKB with a separate application store. A
LocalMarkdownStore exists only for narrow unit tests; the CLI path requires
the real GitKB CLI.

← Back to [CONTEXT.md](../CONTEXT.md)
