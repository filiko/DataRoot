"""Build the pre-baked Austin permits demo project (austin_permits.dfd.json).

The 4 curated CSVs in demo_data/austin/ are ingested via the backend
/ingest/spreadsheet endpoint (which auto-builds entities + attributes + layout).
DFDMaker's FK inference does not detect the cross-table joins, so this script
adds the 3 relationships that make the knowledge graph connected, gives the
project a stable id/name, and lays the ERD out as a clean 2x2 grid.

Re-run after re-ingesting:  python demo_data/build_austin_dfd.py <raw_ingest.json>
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO_SITE = HERE.parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "austin_ingest_raw.json"
OUT = DEMO_SITE / "austin_permits.dfd.json"

ingest = json.loads(RAW.read_text(encoding="utf-8-sig"))
pen = ingest["pen"] if "pen" in ingest else ingest

# ── Stable project identity ──────────────────────────────────────────────────
pen["project"]["id"] = "proj_austin_permits"
pen["project"]["name"] = "Austin Permits Knowledge Base"
pen["project"]["revision"] = 0

# ── Relationships that connect the knowledge graph ───────────────────────────
def rel(rid, name, fe, fa, te, ta, card, constraint, evidence, conf=1.0):
    return {
        "id": rid,
        "name": name,
        "from": {"entity_id": fe, "attribute_id": fa},
        "to": {"entity_id": te, "attribute_id": ta},
        "cardinality": card,
        "postgres": {
            "constraint_name": constraint,
            "on_delete": "restrict",
            "on_update": "cascade",
        },
        "dfd_process_id": None,
        "evidence": [evidence],
        "confidence": conf,
        "review_status": "accepted",
    }

many_to_one = {"from_min": 0, "from_max": "many", "to_min": 1, "to_max": 1}
many_to_many = {"from_min": 0, "from_max": "many", "to_min": 0, "to_max": "many"}

pen["erd"]["relationships"] = [
    rel(
        "rel_plan_reviews_permits", "reviews",
        "ent_plan_reviews", "attr_plan_reviews_permit_id",
        "ent_permits", "attr_permits_permit_id",
        many_to_one, "fk_plan_reviews_permit_id",
        "plan_reviews.permit_id references permits.permit_id",
    ),
    rel(
        "rel_code_tasks_complaints", "tracks",
        "ent_code_tasks", "attr_code_tasks_case_id",
        "ent_code_complaints", "attr_code_complaints_case_id",
        many_to_one, "fk_code_tasks_case_id",
        "code_tasks.case_id references code_complaints.case_id",
    ),
    rel(
        "rel_permits_complaints_address", "shares address with",
        "ent_permits", "attr_permits_address",
        "ent_code_complaints", "attr_code_complaints_address",
        many_to_many, "join_permits_complaints_address",
        "permits.address matches code_complaints.address (normalized address join)",
        conf=0.9,
    ),
]

# ── Clean 2x2 ERD layout so the graph reads well on load ─────────────────────
positions = {
    "ent_permits": (60, 60),
    "ent_plan_reviews": (470, 60),
    "ent_code_complaints": (60, 470),
    "ent_code_tasks": (470, 470),
}
erd_layout = pen.setdefault("layout", {}).setdefault("erd", {})
for node in erd_layout.get("nodes", []):
    if node["id"] in positions:
        node["x"], node["y"] = positions[node["id"]]
erd_layout["edges"] = [
    {"id": r["id"], "route": "orthogonal"} for r in pen["erd"]["relationships"]
]

OUT.write_text(json.dumps(pen, indent=2), encoding="utf-8")
print(f"wrote {OUT}")
print(f"  entities: {len(pen['erd']['entities'])}")
print(f"  relationships: {len(pen['erd']['relationships'])}")
