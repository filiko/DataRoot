from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.link import link_workspace
from dataroot.profile.parsers import MAX_ROW_DOCS_PER_TABLE
from dataroot.profile import profile_workspace


class ProfileLinkTests(unittest.TestCase):
    def test_profile_and_link_repeated_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "data"
            root.mkdir()
            (root / "measurements.csv").write_text(
                "station_id,nitrate_mg_l,note\n"
                "STATION_001,12.4,above limit\n"
                "STATION_002,4.1,ok\n",
                encoding="utf-8",
            )
            (root / "stations.csv").write_text(
                "station_id,name\n"
                "STATION_001,North Well\n"
                "STATION_002,South Well\n",
                encoding="utf-8",
            )
            (root / "field.csv").write_text(
                "block_id,note\n"
                "A-FLD-BLOCK-3,full block identifier should not be truncated\n",
                encoding="utf-8",
            )
            (root / "nested.json").write_text(
                '{"sample": {"sample_id": "SAMP-JSON-001", "station_id": "STATION_001", '
                '"nitrate_mg_l": 13.5, "depth_m": 7}}',
                encoding="utf-8",
            )
            (root / "notebook.md").write_text(
                "---\n"
                "experiment: nitrate_review\n"
                "owner: AReed\n"
                "---\n"
                "# Notebook\n\n"
                "See [[relationships/STATION_001]] for station context and sample SAMP-2024-002.\n\n"
                "| sample_id | nitrate_mg_l | station_id |\n"
                "| --- | --- | --- |\n"
                "| SAMP-MD-001 | 14.2 | STATION_001 |\n",
                encoding="utf-8",
            )
            store = LocalMarkdownStore(Path(temp_dir) / "kb")

            profile = profile_workspace(root, store)
            self.assertEqual(profile.skipped_files, 0)
            self.assertGreater(profile.records_written, 1)
            measurement = store.read("measurements/measurements.csv/nitrate_mg_l")
            self.assertEqual(measurement.doc_type, "measurement")
            self.assertEqual(measurement.frontmatter["unit"], "mg/L")
            self.assertEqual(measurement.frontmatter["max_value"], 12.4)
            json_measurement = store.read("measurements/nested.json/sample.nitrate_mg_l")
            self.assertEqual(json_measurement.frontmatter["max_value"], 13.5)
            json_candidate = store.read("candidates/nested.json/sample.station_id/station_001")
            self.assertEqual(json_candidate.frontmatter["json_path"], "sample.station_id")
            notebook = store.read("source_files/notebook.md")
            self.assertEqual(notebook.frontmatter["parsed_frontmatter"]["experiment"], "nitrate_review")
            self.assertEqual(notebook.frontmatter["wikilinks"], ["relationships/STATION_001"])
            markdown_table = store.read("tables/notebook.md/table_1")
            self.assertEqual(markdown_table.doc_type, "table")
            markdown_measurement = store.read("measurements/notebook.md/table_1/nitrate_mg_l")
            self.assertEqual(markdown_measurement.frontmatter["max_value"], 14.2)
            wikilink_candidate = store.read("candidates/notebook.md/wikilink/relationships/station_001")
            self.assertEqual(wikilink_candidate.frontmatter["detected_from"], "wikilink")

            linked = link_workspace(store)
            self.assertGreater(linked.relationship_docs, 0)

            hits = store.search("STATION_001")
            self.assertTrue(any(hit.slug == "relationships/station_001" for hit in hits))

            graph = store.graph("relationships/station_001", depth=1)
            self.assertTrue(any(slug.startswith("row_groups/measurements.csv") for slug in graph.nodes))
            self.assertTrue(any(slug.startswith("row_groups/stations.csv") for slug in graph.nodes))
            self.assertTrue(any(hit.slug == "relationships/a-fld-block-3" for hit in store.search("A-FLD-BLOCK-3")))
            measurement_graph = store.graph("measurements/measurements.csv/nitrate_mg_l", depth=1)
            self.assertIn("columns/measurements.csv/nitrate_mg_l", measurement_graph.nodes)
            self.assertIn("tables/measurements.csv", measurement_graph.nodes)

    def test_large_csv_uses_chunked_row_groups_after_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "data"
            root.mkdir()
            lines = ["sample_id,value_mg_l"]
            for index in range(MAX_ROW_DOCS_PER_TABLE + 3):
                lines.append(f"SAMP-LARGE-{index:04d},{index}")
            (root / "large.csv").write_text("\n".join(lines), encoding="utf-8")
            store = LocalMarkdownStore(Path(temp_dir) / "kb")

            profile_workspace(root, store)

            row_groups = store.list(doc_type="row_group")
            chunk_rows = [record for record in row_groups if record.frontmatter.get("row_grouping") == "chunk"]
            single_rows = [record for record in row_groups if record.frontmatter.get("row_grouping") == "single_row"]
            self.assertEqual(len(single_rows), MAX_ROW_DOCS_PER_TABLE)
            self.assertEqual(len(chunk_rows), 1)
            self.assertEqual(chunk_rows[0].frontmatter["row_count"], 3)


if __name__ == "__main__":
    unittest.main()
