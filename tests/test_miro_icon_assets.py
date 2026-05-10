from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "miro"
OUTLINE_ICON = ASSET_DIR / "dataroot-outline.svg"
COLOR_ICON = ASSET_DIR / "dataroot-color.svg"


class MiroIconAssetTests(unittest.TestCase):
    def test_miro_app_icons_are_square_svg_assets(self) -> None:
        for path in [OUTLINE_ICON, COLOR_ICON]:
            self.assertTrue(path.exists(), path)
            self.assertLess(path.stat().st_size, 5000)

            root = ET.fromstring(path.read_text(encoding="utf-8"))
            self.assertTrue(root.tag.endswith("svg"))
            self.assertEqual(root.attrib.get("viewBox"), "0 0 32 32")
            self.assertEqual(root.attrib.get("width"), "32")
            self.assertEqual(root.attrib.get("height"), "32")

    def test_outline_icon_is_monochrome_without_gradients(self) -> None:
        text = OUTLINE_ICON.read_text(encoding="utf-8")
        self.assertNotIn("gradient", text.lower())

        colors = {
            match.group(2).lower()
            for match in re.finditer(r'\b(fill|stroke)="([^"]+)"', text)
            if match.group(2).lower() != "none"
        }
        self.assertEqual(colors, {"#1a1a1a"})


if __name__ == "__main__":
    unittest.main()
