"""Fetch bounded Socrata slices for the Austin Permits Live Ask workspace.

Pulls four City of Austin / Austin Development Services public datasets from
data.austintexas.gov, applies the column renames the DataRoot linker expects
(``permit_number`` -> ``permit_id``, ``foldernumber`` -> ``case_task_id``), and
writes the CSVs into ``ExampleData/AustinPermits/raw/<subdir>/<filename>.csv``.

Stdlib only -- no requests/pandas dependency. Run from the repo root::

    python scripts/fetch_austin.py
    python scripts/fetch_austin.py --limit 2000        # smaller slice
    python scripts/fetch_austin.py --slug 3syk-w9eu    # single dataset

Always edit ``ExampleData/AustinPermits/SOURCES.md`` after a fetch with the
new fetch date and any SoQL filter changes.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "ExampleData" / "AustinPermits" / "raw"
USER_AGENT = "DataRoot/AustinPermitsFetcher (open-data hackathon demo)"


@dataclass(frozen=True)
class DatasetConfig:
    slug: str
    title: str
    subdir: str
    filename: str
    where: str = ""
    order: str = ""
    rename_columns: dict[str, str] = field(default_factory=dict)


DATASETS: list[DatasetConfig] = [
    DatasetConfig(
        slug="3syk-w9eu",
        title="Issued Construction Permits",
        subdir="permits",
        filename="issued_construction_permits.csv",
        where="issue_date > '2025-01-01T00:00:00'",
        order="issue_date DESC",
        rename_columns={"permit_number": "permit_id"},
    ),
    DatasetConfig(
        slug="n8ck-xkda",
        title="Plan Review Cases",
        subdir="reviews",
        filename="plan_review_cases.csv",
        where="update_date > '2025-01-01T00:00:00'",
        order="update_date DESC",
        rename_columns={"permit_number": "permit_id"},
    ),
    DatasetConfig(
        slug="6wtj-zbtb",
        title="Austin Code Complaint Cases",
        subdir="code_complaints",
        filename="code_complaint_cases.csv",
        where="opened_date > '2025-01-01T00:00:00'",
        order="opened_date DESC",
        rename_columns={"foldernumber": "case_task_id"},
    ),
    DatasetConfig(
        slug="ttd7-isgm",
        title="Austin Code Task List",
        subdir="code_tasks",
        filename="code_task_list.csv",
        where="duetostart > '2025-01-01T00:00:00'",
        order="duetostart DESC",
        rename_columns={"foldernumber": "case_task_id"},
    ),
]


def fetch_dataset(config: DatasetConfig, limit: int) -> tuple[list[str], list[list[str]]]:
    params: dict[str, str] = {"$limit": str(limit)}
    if config.where:
        params["$where"] = config.where
    if config.order:
        params["$order"] = config.order
    url = f"https://data.austintexas.gov/resource/{config.slug}.csv?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv"})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read().decode("utf-8")
    reader = csv.reader(io.StringIO(body))
    rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def apply_renames(headers: list[str], rename_map: dict[str, str]) -> list[str]:
    if not rename_map:
        return headers
    return [rename_map.get(name, name) for name in headers]


def write_csv(target: Path, headers: list[str], rows: list[list[str]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def run(limit: int, slug_filter: str | None) -> int:
    selected = [d for d in DATASETS if slug_filter is None or d.slug == slug_filter]
    if slug_filter and not selected:
        print(f"error: unknown slug {slug_filter!r}; choose one of {[d.slug for d in DATASETS]}", file=sys.stderr)
        return 2

    print(f"fetching {len(selected)} dataset(s) into {RAW_ROOT}")
    for config in selected:
        print(f"  {config.slug}  {config.title} -> {config.subdir}/{config.filename}")
        try:
            headers, rows = fetch_dataset(config, limit)
        except Exception as exc:
            print(f"    FAILED: {exc}", file=sys.stderr)
            return 1
        if not headers:
            print("    empty response", file=sys.stderr)
            continue
        renamed = apply_renames(headers, config.rename_columns)
        if renamed != headers:
            changed = [f"{src}->{dst}" for src, dst in config.rename_columns.items() if src in headers]
            print(f"    renamed columns: {', '.join(changed)}")
        target = RAW_ROOT / config.subdir / config.filename
        write_csv(target, renamed, rows)
        print(f"    wrote {len(rows)} rows")

    print("done. now run: dataroot profile ExampleData/AustinPermits/raw && dataroot link")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Austin open-data slices for DataRoot.")
    parser.add_argument("--limit", type=int, default=10000, help="Per-dataset row cap (default 10000)")
    parser.add_argument("--slug", type=str, default=None, help="Fetch only this Socrata slug")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    sys.exit(run(args.limit, args.slug))
