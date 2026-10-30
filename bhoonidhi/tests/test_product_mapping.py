"""
Unit tests for Bhoonidhi Product and Collection Mapping.
"""

import unittest
from bhoonidhi.product_mapping import resolve_product_types, ResolutionResult


class TestProductMapping(unittest.TestCase):

    def test_exact_canonical_match(self):
        res = resolve_product_types("ResourceSat-2_AWIFS_L2")
        self.assertEqual(res.resolved, ["ResourceSat-2_AWIFS_L2"])
        self.assertEqual(res.unresolved, [])
        self.assertFalse(res.has_unresolved)

    def test_case_and_alias_normalization(self):
        # awifs, eos-04, s1a, cartodem
        res = resolve_product_types(["awifs", "EOS-04", "s1a", "CartoDEM 30m"])
        expected = [
            "ResourceSat-2_AWIFS_L2",
            "EOS-04_SAR-MRS_L2A",
            "Sentinel-1A_SAR-IW_GRD",
            "CartoSat-1_PAN_CartoDEM_30m",
        ]
        self.assertEqual(res.resolved, expected)
        self.assertEqual(res.unresolved, [])

    def test_deduplication_and_deterministic_order(self):
        # Repetitive inputs should be deduplicated while preserving first-seen order
        inputs = ["awifs", "rs2 awifs", "ResourceSat-2_AWIFS_L2", "eos04", "awifs"]
        res = resolve_product_types(inputs)
        self.assertEqual(res.resolved, ["ResourceSat-2_AWIFS_L2", "EOS-04_SAR-MRS_L2A"])

    def test_unresolved_inputs_with_suggestions(self):
        # "unknown_satellite" has no match; "cartosat_unknown" should suggest CartoSat
        inputs = ["sentinel-1a", "unknown_sensor", "cartosat_special"]
        res = resolve_product_types(inputs)
        self.assertEqual(res.resolved, ["Sentinel-1A_SAR-IW_GRD"])
        self.assertIn("unknown_sensor", res.unresolved)
        self.assertIn("cartosat_special", res.unresolved)
        self.assertTrue(res.has_unresolved)

        # Check candidate suggestions
        self.assertIn("cartosat_special", res.suggestions)
        self.assertIn("CartoSat-1_PAN_CartoDEM_30m", res.suggestions["cartosat_special"])

    def test_invalid_input_type(self):
        with self.assertRaises(TypeError):
            resolve_product_types(12345)  # type: ignore

    def test_empty_input(self):
        res = resolve_product_types([])
        self.assertEqual(res.resolved, [])
        self.assertEqual(res.unresolved, [])

    def test_unknown_aliases_not_falsely_mapped(self):
        inputs = ["landsat_8", "modis_terra", "random_string_123"]
        res = resolve_product_types(inputs)
        self.assertEqual(res.resolved, [])
        self.assertEqual(res.unresolved, inputs)
        self.assertTrue(res.has_unresolved)


if __name__ == "__main__":
    unittest.main()

