# AustinPermits — Texas Open Data Live Ask

This workspace exercises DataRoot's same Live Ask pipeline against **real public
data** from the City of Austin: construction permits, plan reviews, code
complaints, and code enforcement tasks. It satisfies the Brainforge / Vicinity
**Texas Open Data Track** requirements.

## Datasets

Four bounded slices from `data.austintexas.gov` — see `SOURCES.md` for slugs,
URLs, fetch dates, SoQL filters, and attribution.

| Slug         | Title                         | Local path                                                        |
|--------------|-------------------------------|-------------------------------------------------------------------|
| `3syk-w9eu`  | Issued Construction Permits   | `raw/permits/issued_construction_permits.csv`                     |
| `n8ck-xkda`  | Plan Review Cases             | `raw/reviews/plan_review_cases.csv`                               |
| `6wtj-zbtb`  | Austin Code Complaint Cases   | `raw/code_complaints/code_complaint_cases.csv`                    |
| `ttd7-isgm`  | Austin Code Task List         | `raw/code_tasks/code_task_list.csv`                               |

The slices are small (default 10K rows each, recent-window only) so `dataroot
profile` and `dataroot link` complete in seconds.

## How the data is shaped for the linker

DataRoot's linker keys identity off columns ending in `_id`. The Socrata
exports use slightly different column names, so `scripts/fetch_austin.py`
applies these renames at fetch time:

| Original column   | Renamed to       |
|-------------------|------------------|
| `permit_number`   | `permit_id`      |
| `foldernumber`    | `case_task_id`   |

Without the renames the row slugs would be opaque project IDs; with them, every
permit row is keyed on its human-readable permit number.

For the address-driven joins between Code Complaint Cases and the Code Task
List (and between Plan Reviews and Issued Permits when the project description
or address ties them together), the linker needs `DATAROOT_LINK_ADDRESS_JOIN=1`
set so that `src/dataroot/link/address_match.py` runs and emits cross-table
relationship docs keyed on the normalized address.

## Run the Live Ask locally

```bash
git kb --version                        # must succeed; on Windows install via WSL per top-level README
python scripts/fetch_austin.py          # downloads + renames the 4 slices
export DATAROOT_LINK_ADDRESS_JOIN=1     # enable address-keyed cross-table links
dataroot profile ExampleData/AustinPermits/raw
dataroot link
uvicorn dataroot.server.app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/miro/ and pick "Austin Permits Explorer"
```

The Miro panel accepts arbitrary free-form questions — the workspace is **not**
tuned to specific demo prompts. Whatever the user types is routed through
`query.answer_question` and rendered to a Miro board with evidence cards
labeled by source dataset slug.

## Run the MCP server

```bash
python -m dataroot.mcp     # stdio server; see skills/dataroot-texas/SKILL.md
```

## Attribution

All data is City of Austin / Austin Development Services public data, used
under the City of Austin Open Data Terms
(`https://data.austintexas.gov/stories/s/ranj-cccq`). Per-dataset slugs, URLs,
and exact SoQL filters are recorded in `SOURCES.md` and must be cited whenever
the workspace surfaces values to a user.

## Related docs

- Hackathon submission overview: [`../../SUBMISSION.md`](../../SUBMISSION.md)
- Top-level project README: [`../../README.md`](../../README.md)
- MCP server tool reference: [`../../docs/mcp-server.md`](../../docs/mcp-server.md)
- Claude Code skill: [`../../skills/dataroot-texas/SKILL.md`](../../skills/dataroot-texas/SKILL.md)
- Hosted-deploy / Miro app setup: [`../../docs/deploy.md`](../../docs/deploy.md)
