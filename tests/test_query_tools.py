from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dataroot.agent.tools import ToolExecutor
from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.link import link_workspace
from dataroot.profile import profile_workspace
from dataroot.query import answer_question
from dataroot.query_tools import query_table, threshold_exceedances


class QueryToolTests(unittest.TestCase):
    def test_threshold_answer_finds_water_quality_exceedances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = _profile_water_quality(Path(temp_dir))

            rows = threshold_exceedances(store, "Which stations exceeded nitrate limits in 2024?")
            station_ids = {row.row_data["station_id"] for row in rows}
            self.assertEqual(station_ids, {"STATION_001", "STATION_002"})

            answer = answer_question(store, "Which stations exceeded nitrate limits in 2024?")
            self.assertIn("STATION_001", answer)
            self.assertIn("STATION_002", answer)
            self.assertIn("[citation: row_groups/water_quality_measurements_2024.csv/samp-2024-002]", answer)
            self.assertIn("<provenance>", answer)

    def test_tool_executor_query_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = _profile_water_quality(Path(temp_dir))
            executor = ToolExecutor(store)

            rows = executor(
                "query_table",
                {
                    "table_slug": "tables/water_quality_measurements_2024.csv",
                    "filters": [{"field": "nitrate_mg_l", "op": ">", "value": 10}],
                },
            )

            self.assertEqual({row["row_data"]["station_id"] for row in rows}, {"STATION_001", "STATION_002"})

    def test_company_a_readiness_answer_is_synthesized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(__file__).resolve().parents[1]
            data_root = repo_root / "ExampleData" / "CompanyA_AgriTrait" / "raw"
            store = LocalMarkdownStore(Path(temp_dir) / "kb")
            profile_workspace(data_root, store)

            answer = answer_question(
                store,
                "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?",
            )

            self.assertIn("Best candidate: A-CUL-TOM-014 / Solara-14", answer)
            self.assertIn("A-GEN-PMR3", answer)
            self.assertIn("[citation: row_groups/registries/cultivar_registry.csv/a-cul-tom-014]", answer)
            self.assertIn("[citation: row_groups/trials/greenhouse_trials_2026_q1.csv/a-trl-gh-001]", answer)
            self.assertIn("[citation: row_groups/trials/field_trials_2025.csv/a-trl-fd-002]", answer)
            self.assertIn("[citation: row_groups/inventory/seed_inventory.csv/a-inv-seed-02]", answer)
            self.assertIn("A-CUL-TOM-022", answer)
            self.assertIn("<provenance>", answer)

    def test_company_b_fermentation_answer_is_synthesized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(__file__).resolve().parents[1]
            data_root = repo_root / "ExampleData" / "CompanyB_Fermentation" / "raw"
            store = LocalMarkdownStore(Path(temp_dir) / "kb")
            profile_workspace(data_root, store)

            answer = answer_question(
                store,
                "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?",
            )

            self.assertIn("Best candidate: B-STR-YE-017 / Yeast EsterMax 17", answer)
            self.assertIn("B-GEN-AAT1;B-GEN-EHT1", answer)
            self.assertIn("[citation: row_groups/registries/strain_registry.csv/b-str-ye-017]", answer)
            self.assertIn("[citation: row_groups/fermentation_runs/fermentation_runs_2026_q1.csv/b-run-ferm-033]", answer)
            self.assertIn("[citation: row_groups/assays/gcms_metabolite_assays_2026_q1.csv/b-assay-gcms-018]", answer)
            self.assertIn("[citation: row_groups/inventory/strain_inventory.csv/b-inv-str-017]", answer)
            self.assertIn("[citation: row_groups/bioreactor_ops/bioreactor_schedule.csv/b-br-r2]", answer)
            self.assertIn("B-STR-YE-021", answer)
            self.assertIn("<provenance>", answer)


def _profile_water_quality(temp_dir: Path) -> LocalMarkdownStore:
    repo_root = Path(__file__).resolve().parents[1]
    data_root = repo_root / "ExampleData" / "water_quality" / "raw"
    store = LocalMarkdownStore(temp_dir / "kb")
    profile_workspace(data_root, store)
    link_workspace(store)
    return store


if __name__ == "__main__":
    unittest.main()
