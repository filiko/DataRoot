# AustinPermits — Source Datasets and Attribution

All data in this workspace is **City of Austin / Austin Development Services
public data**, retrieved from `data.austintexas.gov` via the Socrata API and
used under the **City of Austin Open Data Terms**:

> https://data.austintexas.gov/stories/s/ranj-cccq

Cite this attribution wherever values from these datasets are surfaced to a
user (rendered on a Miro board, returned by an MCP tool, etc.).

## Datasets

| # | Slug         | Title                         | Portal URL                                              | Local path                                                       |
|---|--------------|-------------------------------|---------------------------------------------------------|------------------------------------------------------------------|
| 1 | `3syk-w9eu`  | Issued Construction Permits   | https://data.austintexas.gov/d/3syk-w9eu                | `raw/permits/issued_construction_permits.csv`                    |
| 2 | `n8ck-xkda`  | Plan Review Cases             | https://data.austintexas.gov/d/n8ck-xkda                | `raw/reviews/plan_review_cases.csv`                              |
| 3 | `6wtj-zbtb`  | Austin Code Complaint Cases   | https://data.austintexas.gov/d/6wtj-zbtb                | `raw/code_complaints/code_complaint_cases.csv`                   |
| 4 | `ttd7-isgm`  | Austin Code Task List         | https://data.austintexas.gov/d/ttd7-isgm                | `raw/code_tasks/code_task_list.csv`                              |

All four datasets are published by the City of Austin / Austin Development
Services and are updated daily or more frequently. Refresh cadence and field
schemas are documented on each dataset's portal page.

## Fetch parameters

The slices are pulled by `scripts/fetch_austin.py` with the following SoQL
filters and per-dataset row caps. Update this section every time the script is
re-run with new parameters or against a new fetch date.

| Slug         | `$where`                                                  | `$order`                  | `$limit`  | Last fetched |
|--------------|-----------------------------------------------------------|---------------------------|-----------|--------------|
| `3syk-w9eu`  | `issue_date > '2025-01-01T00:00:00'`                      | `issue_date DESC`         | 10000     | 2026-05-10   |
| `n8ck-xkda`  | `update_date > '2025-01-01T00:00:00'`                     | `update_date DESC`        | 10000     | 2026-05-10   |
| `6wtj-zbtb`  | `opened_date > '2025-01-01T00:00:00'`                     | `opened_date DESC`        | 10000     | 2026-05-10   |
| `ttd7-isgm`  | `duetostart > '2025-01-01T00:00:00'`                      | `duetostart DESC`         | 10000     | 2026-05-10   |

The default filters are conservative — adjust the `$where` clauses to widen or
narrow the slice for a particular demo, then update the row above with the new
parameters and fetch date.

## Column renames applied at fetch time

The DataRoot linker keys identity off columns ending in `_id`, so the fetch
script renames a small number of Socrata columns before writing the CSVs:

| Dataset slugs       | Original column   | Renamed to       |
|---------------------|-------------------|------------------|
| `3syk-w9eu`, `n8ck-xkda` | `permit_number`   | `permit_id`      |
| `6wtj-zbtb`, `ttd7-isgm` | `foldernumber`    | `case_task_id`   |

These renames preserve the human-readable identifiers in the row slugs and
make the cross-dataset joins on permit number / case-task identifier work
without further configuration.

## Bounded-query and safe-use notes

- All four datasets are **public open data**; no scraping behind authentication
  and no use of any private/sensitive fields.
- The MCP server (`src/dataroot/mcp/server.py`) enforces hard upper bounds on
  every tool: search returns at most 50 hits, list returns at most 100, table
  queries return at most 200, graph traversal is capped at depth 3.
- Address joins between datasets are **heuristic** — `address_key` strips
  punctuation and unit/suite trailers and normalizes USPS suffixes. Do not
  treat an address join as an exact identity match; cite the source rows on
  both sides whenever an address-derived claim is surfaced.
