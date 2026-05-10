from __future__ import annotations

import unittest

from dataroot.link.address_match import address_key, normalize_address


class NormalizeAddressTests(unittest.TestCase):
    def test_empty_inputs(self) -> None:
        self.assertEqual(normalize_address(None), "")
        self.assertEqual(normalize_address(""), "")
        self.assertEqual(normalize_address("   "), "")

    def test_uppercases_and_strips_punctuation(self) -> None:
        self.assertEqual(normalize_address("1623 s. lamar blvd."), "1623 S LAMAR BLVD")

    def test_normalizes_suffix_long_to_short(self) -> None:
        self.assertEqual(normalize_address("1623 S Lamar Boulevard"), "1623 S LAMAR BLVD")
        self.assertEqual(normalize_address("100 Main Street"), "100 MAIN ST")
        self.assertEqual(normalize_address("400 W 2nd Avenue"), "400 W 2ND AVE")

    def test_normalizes_direction_long_to_short(self) -> None:
        self.assertEqual(normalize_address("1623 South Lamar Blvd"), "1623 S LAMAR BLVD")
        self.assertEqual(normalize_address("100 Northwest Loop"), "100 NW LOOP")

    def test_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_address("1623   S   LAMAR    BLVD"), "1623 S LAMAR BLVD")

    def test_keeps_unit_suffix_in_normalize(self) -> None:
        self.assertEqual(
            normalize_address("7010 Easy Wind Dr Unit 130"),
            "7010 EASY WIND DR UNIT 130",
        )


class AddressKeyTests(unittest.TestCase):
    def test_empty_inputs(self) -> None:
        self.assertEqual(address_key(None), "")
        self.assertEqual(address_key(""), "")

    def test_drops_unit_trailer(self) -> None:
        self.assertEqual(address_key("7010 EASY WIND DR UNIT 130"), "7010 EASY WIND DR")
        self.assertEqual(address_key("100 Main St Suite 200"), "100 MAIN ST")
        self.assertEqual(address_key("100 Main St Apt 4B"), "100 MAIN ST")
        self.assertEqual(address_key("100 Main St #4"), "100 MAIN ST")
        self.assertEqual(address_key("100 Main St Bldg C"), "100 MAIN ST")

    def test_idempotent(self) -> None:
        first = address_key("1623 S. Lamar Boulevard")
        second = address_key(first)
        self.assertEqual(first, "1623 S LAMAR BLVD")
        self.assertEqual(second, "1623 S LAMAR BLVD")

    def test_matching_variants_share_key(self) -> None:
        variants = [
            "1623 S LAMAR BOULEVARD",
            "1623 S Lamar Blvd",
            "1623 S. Lamar Blvd.",
            "1623 South Lamar Boulevard",
        ]
        keys = {address_key(v) for v in variants}
        self.assertEqual(keys, {"1623 S LAMAR BLVD"})

    def test_unit_variants_share_key(self) -> None:
        with_unit = address_key("7010 EASY WIND DR UNIT 130")
        without_unit = address_key("7010 Easy Wind Dr")
        self.assertEqual(with_unit, without_unit)

    def test_no_unit_returns_full_normalized(self) -> None:
        self.assertEqual(address_key("400 W 2nd Ave"), "400 W 2ND AVE")


if __name__ == "__main__":
    unittest.main()
