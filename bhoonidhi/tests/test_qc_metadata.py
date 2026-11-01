"""
Unit tests for Bhoonidhi Ground Station QC Metadata Extractor.
Tests SAR and Optical property mapping, coordinates formatting, and null tolerance.
"""

import unittest

from bhoonidhi.qc_metadata import QCMetadata, _format_lat_lon, extract_qc_metadata


class TestQCMetadata(unittest.TestCase):

    def test_format_lat_lon(self):
        self.assertEqual(_format_lat_lon(10.772663, 42.937782), "10.7727° N, 42.9378° E")
        self.assertEqual(_format_lat_lon(-15.5, -60.25), "15.5000° S, 60.2500° W")
        self.assertEqual(_format_lat_lon(None, None), "N/A")
        self.assertEqual(_format_lat_lon("invalid", "text"), "invalid, text")

    def test_extract_sar_properties(self):
        sar_item = {
            "id": "E04_SAR_FR1_29OCT2026_25976_2889_8_S63_STUC00ETD_H_HV_D_F",
            "collection": "EOS-04_SAR-FRS1_L2A",
            "properties": {
                "CycleNumber": 99,
                "Imaging_Date": "29-OCT-2026",
                "Dumping_Date": "29-OCT-2026",
                "Dumping_Orbit": 25976,
                "ID": "E04_SAR_FR1_29OCT2026_25976_2889_8_S63_STUC00ETD_H_HV_D_F",
                "StripId": 2889,
                "SceneNumber": 8,
                "Mode": "FRS1",
                "GenerationTime": "2026-10-29T12:50:36",
                "Scene_Identifier": "25976_25975_2889_8",
                "StationId": "S63",
                "SceneCenterLat": 10.772663,
                "SceneCenterLon": 42.937782,
                "InputResolutionAcross": 2.40,
                "InputResolutionAlong": 3.00,
                "Platform": "EOS-04",
                "Instrument": "SAR",
                "Online": "Y",
            },
            "preview_status": "downloaded",
            "preview_file_path": "/path/to/thumb.jpg",
        }

        qc = extract_qc_metadata(sar_item)
        self.assertEqual(qc.cycle_number, "99")
        self.assertEqual(qc.date_of_pass, "29-OCT-2026")
        self.assertEqual(qc.date_of_dump, "29-OCT-2026")
        self.assertEqual(qc.dumping_orbit_number, "25976")
        self.assertEqual(qc.track_number, "2889")
        self.assertEqual(qc.frame_number, "8")
        self.assertEqual(qc.mode_id, "FRS1")
        self.assertEqual(qc.generation_datetime, "2026-10-29T12:50:36")
        self.assertEqual(qc.session_number, "S63")
        self.assertEqual(qc.scene_centre_lat_lon, "10.7727° N, 42.9378° E")
        self.assertEqual(qc.input_resolution, "2.4m (Across) x 3.0m (Along)")
        self.assertEqual(qc.online_status, "Y")
        self.assertEqual(qc.rfi_likelihood, "Not Reported (Nominal)")

        display_pairs = qc.to_display_pairs()
        self.assertEqual(len(display_pairs), 14)
        field_names = [f[0] for f in display_pairs]
        self.assertIn("CYCLE NUMBER", field_names)
        self.assertIn("DATE OF PASS", field_names)
        self.assertIn("RFI LIKELIHOOD", field_names)

    def test_extract_optical_properties(self):
        optical_item = {
            "id": "R2W29OCT2026080577007900061PSANSTLC00GTDD",
            "collection": "ResourceSat-2_AWIFS_L2",
            "properties": {
                "Platform": "RS2",
                "Instrument": "AWIF",
                "Imaging_Date": "2026-10-29 00:00:00",
                "Dumping_Date": "2026-10-29 00:00:00",
                "Dumping_Orbit": "080577",
                "Path": 79,
                "Row": 61,
                "ProductCode": "STLC00GTD",
                "Subscene_ID": "D",
                "CentreLatLon": ["57.948817", "14.937264"],
                "Online": "N",
            },
            "preview_status": "downloaded",
        }

        qc = extract_qc_metadata(optical_item)
        self.assertEqual(qc.cycle_number, "N/A")
        self.assertEqual(qc.dumping_orbit_number, "080577")
        self.assertEqual(qc.track_number, "79")
        self.assertEqual(qc.frame_number, "61")
        self.assertEqual(qc.session_number, "Subscene D")
        self.assertEqual(qc.scene_centre_lat_lon, "57.9488° N, 14.9373° E")
        self.assertEqual(qc.input_resolution, "56.0m (Nominal)")

    def test_extract_empty_or_null_item(self):
        empty_item = {}
        qc = extract_qc_metadata(empty_item)
        self.assertEqual(qc.item_id, "UNKNOWN")
        self.assertEqual(qc.collection_id, "UNKNOWN")
        self.assertEqual(qc.cycle_number, "N/A")
        self.assertEqual(qc.date_of_pass, "N/A")
        self.assertEqual(qc.scene_centre_lat_lon, "N/A")
        self.assertEqual(qc.online_status, "Unknown")
        self.assertEqual(len(qc.to_display_pairs()), 14)


if __name__ == "__main__":
    unittest.main()

