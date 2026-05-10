from __future__ import annotations

import csv
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "ExampleData" / "CompanyA_AgriTrait" / "raw"


class DemoSpineTests(unittest.TestCase):
    def test_company_a_spine_holds(self) -> None:
        cultivar = _row_by_value(RAW / "registries" / "cultivar_registry.csv", "cultivar_id", "A-CUL-TOM-014")
        self.assertIn("A-TRT-DRT", cultivar["target_trait_ids"])
        self.assertIn("A-GEN-PMR3", cultivar["marker_ids"])
        self.assertEqual(cultivar["breeding_stage"], "field_ready")

        greenhouse = _rows_by_value(RAW / "trials" / "greenhouse_trials_2026_q1.csv", "cultivar_id", "A-CUL-TOM-014")
        self.assertTrue(any(row["trait_id"] == "A-TRT-DRT" and row["pass_fail"] == "pass" for row in greenhouse))
        self.assertTrue(any(row["trait_id"] == "A-TRT-PMR" and row["pass_fail"] == "pass" for row in greenhouse))

        field = _rows_by_value(RAW / "trials" / "field_trials_2025.csv", "cultivar_id", "A-CUL-TOM-014")
        self.assertTrue(any(row["pass_fail"] == "pass" for row in field))

        inventory = _rows_by_value(RAW / "inventory" / "seed_inventory.csv", "cultivar_id", "A-CUL-TOM-014")
        self.assertTrue(any(row["release_status"] == "released" for row in inventory))

        held = _row_by_value(RAW / "registries" / "cultivar_registry.csv", "cultivar_id", "A-CUL-TOM-022")
        self.assertIn("validation", held["notes"].lower())
        failure_rows = _rows_by_value(RAW / "trials" / "field_trials_2025.csv", "cultivar_id", "A-CUL-TOM-022")
        self.assertTrue(any(row["pass_fail"] == "fail" and row["notes"] for row in failure_rows))

    def test_water_quality_smoke_dataset_has_nitrate_exceedances(self) -> None:
        path = ROOT / "ExampleData" / "water_quality" / "raw" / "water_quality_measurements_2024.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        exceeders = {row["station_id"] for row in rows if float(row["nitrate_mg_l"]) > 10}
        self.assertEqual(exceeders, {"STATION_001", "STATION_002"})


def _row_by_value(path: Path, column: str, value: str) -> dict[str, str]:
    rows = _rows_by_value(path, column, value)
    if not rows:
        raise AssertionError(f"{value} not found in {path}")
    return rows[0]


def _rows_by_value(path: Path, column: str, value: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row[column] == value]


if __name__ == "__main__":
    unittest.main()
