"""
Unit tests for Bhoonidhi Satellite Platform Collection Mapping.
Tests satellite name resolution, alias normalization, and fleet expansion.
"""

import unittest

from bhoonidhi.product_mapping import SATELLITE_COLLECTIONS, get_satellite_collections


class TestPlatformMapping(unittest.TestCase):

    def test_canonical_satellite_resolution(self):
        eos4_cols = get_satellite_collections("EOS-04")
        self.assertEqual(len(eos4_cols), 4)
        self.assertIn("EOS-04_SAR-FRS1_L2A", eos4_cols)
        self.assertIn("EOS-04_SAR-FRS2_L2A", eos4_cols)
        self.assertIn("EOS-04_SAR-MRS_L2B", eos4_cols)
        self.assertIn("EOS-04_SAR-CRS_L2B", eos4_cols)

        rs2_cols = get_satellite_collections("ResourceSat-2")
        self.assertEqual(len(rs2_cols), 3)
        self.assertIn("ResourceSat-2_AWIFS_L2", rs2_cols)
        self.assertIn("ResourceSat-2_LISS3_L2", rs2_cols)

    def test_satellite_aliases(self):
        self.assertEqual(get_satellite_collections("eos04"), get_satellite_collections("EOS-04"))
        self.assertEqual(get_satellite_collections("eos-4"), get_satellite_collections("EOS-04"))
        self.assertEqual(get_satellite_collections("rs2"), get_satellite_collections("ResourceSat-2"))
        self.assertEqual(get_satellite_collections("resourcesat2"), get_satellite_collections("ResourceSat-2"))
        self.assertEqual(get_satellite_collections("sentinel1"), get_satellite_collections("Sentinel-1A"))
        self.assertEqual(get_satellite_collections("s1a"), get_satellite_collections("Sentinel-1A"))

    def test_fleet_or_all(self):
        fleet_cols = get_satellite_collections("ALL")
        self.assertGreaterEqual(len(fleet_cols), 10)
        self.assertIn("EOS-04_SAR-FRS1_L2A", fleet_cols)
        self.assertIn("ResourceSat-2_AWIFS_L2", fleet_cols)
        self.assertIn("Sentinel-1A_SAR-IW_GRD", fleet_cols)

    def test_unknown_satellite(self):
        self.assertEqual(get_satellite_collections("UNKNOWN_SAT"), [])
        self.assertEqual(get_satellite_collections(""), [])


if __name__ == "__main__":
    unittest.main()
