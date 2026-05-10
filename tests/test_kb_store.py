from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dataroot.kb.base import DocumentRecord
from dataroot.kb.local_store import LocalMarkdownStore


class LocalMarkdownStoreTests(unittest.TestCase):
    def test_write_search_and_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalMarkdownStore(Path(temp_dir) / "kb")
            store.init()
            store.write(
                DocumentRecord(
                    doc_type="note",
                    slug="notes/source",
                    title="Source",
                    frontmatter={},
                    body="Links to [[notes/target]] and mentions nitrate.",
                )
            )
            store.write(
                DocumentRecord(
                    doc_type="note",
                    slug="notes/target",
                    title="Target",
                    frontmatter={},
                    body="Target body.",
                )
            )

            results = store.search("nitrate")
            self.assertEqual(results[0].slug, "notes/source")

            graph = store.graph("notes/source", direction="outbound", depth=1)
            self.assertIn("notes/target", graph.nodes)
            self.assertEqual(graph.edges[0].source, "notes/source")
            self.assertEqual(graph.edges[0].target, "notes/target")


if __name__ == "__main__":
    unittest.main()
