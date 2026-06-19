"""Generation eval runner — English business rules → LLM ERD → score vs answer key.

    python -m evals.run_erd_eval        # from demo-site/backend
    python evals/run_erd_eval.py

Skips cleanly (exit 0) when MINIMAX_API_KEY is unset. The LLM generation runs on
MiniMax at temperature 0; the scoring is deterministic. Thresholds are eval
targets, not hard unit-test gates — a below-threshold run prints FAIL and exits 1
so CI can flag a regression, but the numbers themselves are the signal.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # demo-site/backend on path

from evals.erd_score import score_erd  # noqa: E402
from evals.watt_corpus import EXERCISES  # noqa: E402
from generators.erd_from_text import generate_erd_from_text  # noqa: E402
from llm import minimax  # noqa: E402

ENTITY_RECALL_MIN = 0.9
CARDINALITY_ACCURACY_MIN = 0.8


def run() -> list[dict]:
    """Generate + score each exercise. Returns one result row per exercise."""
    rows: list[dict] = []
    for ex in EXERCISES:
        result = generate_erd_from_text(ex.paragraph)
        if not result.ok:
            rows.append({"key": ex.key, "error": result.error})
            continue
        score = score_erd(result.pen, ex.build())
        rows.append({"key": ex.key, "title": ex.title, "score": score.as_dict()})
    return rows


def _passed(score: dict) -> bool:
    return (score["entity_recall"] >= ENTITY_RECALL_MIN
            and score["cardinality_accuracy"] >= CARDINALITY_ACCURACY_MIN)


def main() -> int:
    if not minimax.is_configured():
        print("ERD generation eval SKIPPED — set MINIMAX_API_KEY to run.")
        return 0

    print("ERD generation eval — generating ERDs from English business rules,")
    print(f"scoring vs the Watt Appendix B answer keys (CC BY 4.0).")
    print(f"targets: entity_recall ≥ {ENTITY_RECALL_MIN}, "
          f"cardinality_accuracy ≥ {CARDINALITY_ACCURACY_MIN}\n")

    all_pass = True
    for row in run():
        if row.get("error"):
            print(f"✗ {row['key']}: GENERATION FAILED — {row['error']}")
            all_pass = False
            continue
        s = row["score"]
        ok = _passed(s)
        all_pass = all_pass and ok
        print(f"{'✓' if ok else '✗'} {row['title']} [{row['key']}]")
        print(f"    entities      P={s['entity_precision']} R={s['entity_recall']} F1={s['entity_f1']}")
        print(f"    relationships P={s['relationship_precision']} R={s['relationship_recall']} F1={s['relationship_f1']}")
        print(f"    pk_accuracy={s['pk_accuracy']}  cardinality_accuracy={s['cardinality_accuracy']}")
        if s["missing_entities"]:
            print(f"    missing: {', '.join(s['missing_entities'])}")
        if s["extra_entities"]:
            print(f"    extra:   {', '.join(s['extra_entities'])}")
        print()

    print("RESULT:", "PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
