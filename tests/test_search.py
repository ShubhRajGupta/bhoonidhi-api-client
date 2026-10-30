"""
Unit tests for Bhoonidhi STAC Search and Pagination.
"""

import unittest
from unittest.mock import MagicMock, call

from bhoonidhi.auth import BhoonidhiAuth
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.credentials import BhoonidhiCredentials
from bhoonidhi.exceptions import STACSearchError
from bhoonidhi.search import BhoonidhiSearch


class TestSTACSearch(unittest.TestCase):

    def setUp(self):
        self.creds = BhoonidhiCredentials(user_id="user", password="password")
        self.config = BhoonidhiConfig(base_url="https://mock-bhoonidhi.nrsc.gov.in", search_rate_delay=0)
        self.session = MagicMock()
        self.auth = BhoonidhiAuth(credentials=self.creds, config=self.config, session=self.session)
        self.auth._access_token = "valid_token"
        self.auth._expires_at = 9999999999
        self.search = BhoonidhiSearch(auth=self.auth, config=self.config, session=self.session)

    def test_bbox_validation(self):
        # Valid bbox: [west, south, east, north]
        self.search.validate_bbox([72.5, 18.5, 78.5, 28.5])

        # Invalid bounds
        with self.assertRaises(ValueError):
            self.search.validate_bbox([190.0, 10.0, 80.0, 20.0])  # west > 180
        with self.assertRaises(ValueError):
            self.search.validate_bbox([85.0, 10.0, 75.0, 20.0])  # west > east
        with self.assertRaises(ValueError):
            self.search.validate_bbox([75.0, 25.0, 85.0, 15.0])  # south > north

    def test_geometry_validation(self):
        # Valid closed polygon: [lon, lat]
        valid_poly = {
            "type": "Polygon",
            "coordinates": [[[77.0, 28.0], [78.0, 28.0], [78.0, 29.0], [77.0, 29.0], [77.0, 28.0]]],
        }
        self.search.validate_geometry(valid_poly)

        # Unclosed polygon
        unclosed_poly = {
            "type": "Polygon",
            "coordinates": [[[77.0, 28.0], [78.0, 28.0], [78.0, 29.0], [77.0, 29.0]]],
        }
        with self.assertRaises(ValueError):
            self.search.validate_geometry(unclosed_poly)

    def test_search_payload_construction(self):
        payload = self.search.build_search_payload(
            collections=["EOS-04_SAR-MRS_L2A"],
            bbox=[72.0, 18.0, 74.0, 20.0],
            datetime_range="2023-01-01T00:00:00Z/2023-01-31T23:59:59Z",
            limit=250,
            online_only=True,
        )
        self.assertEqual(payload["collections"], ["EOS-04_SAR-MRS_L2A"])
        self.assertEqual(payload["bbox"], [72.0, 18.0, 74.0, 20.0])
        self.assertEqual(payload["limit"], 250)
        self.assertEqual(payload["filter-lang"], "cql2-json")
        self.assertEqual(payload["filter"], {"op": "eq", "args": [{"property": "Online"}, "Y"]})

    def test_pagination_following_next_link(self):
        page1_resp = MagicMock()
        page1_resp.status_code = 200
        page1_resp.json.return_value = {
            "type": "FeatureCollection",
            "features": [{"id": "item1"}, {"id": "item2"}],
            "links": [
                {
                    "rel": "next",
                    "href": "https://mock-bhoonidhi.nrsc.gov.in/data/search?page=2",
                    "method": "GET",
                }
            ],
        }

        page2_resp = MagicMock()
        page2_resp.status_code = 200
        page2_resp.json.return_value = {
            "type": "FeatureCollection",
            "features": [{"id": "item3"}],
            "links": [],  # End of pages
        }

        self.session.request.side_effect = [page1_resp, page2_resp]

        result = self.search.search(collections=["ResourceSat-2_AWIFS_L2"], max_pages=10)
        self.assertEqual(result.total_returned, 3)
        self.assertEqual(len(result.features), 3)
        self.assertEqual(result.pages_retrieved, 2)
        self.assertFalse(result.pagination_capped)

    def test_anti_ssrf_unexpected_pagination_host(self):
        # A malicious or unexpected next link pointing to external server
        page1_resp = MagicMock()
        page1_resp.status_code = 200
        page1_resp.json.return_value = {
            "type": "FeatureCollection",
            "features": [{"id": "item1"}],
            "links": [
                {
                    "rel": "next",
                    "href": "https://attacker-controlled.site/data/search?page=2",
                }
            ],
        }
        self.session.request.return_value = page1_resp

        with self.assertRaises(STACSearchError) as ctx:
            self.search.search(collections=["EOS-04_SAR-MRS_L2A"])

        self.assertIn("Security violation", str(ctx.exception))
        self.assertIn("attacker-controlled.site", str(ctx.exception))

    def test_pagination_safety_cap(self):
        # Infinite next link simulation
        infinite_resp = MagicMock()
        infinite_resp.status_code = 200
        infinite_resp.json.return_value = {
            "type": "FeatureCollection",
            "features": [{"id": "item"}],
            "links": [
                {
                    "rel": "next",
                    "href": "https://mock-bhoonidhi.nrsc.gov.in/data/search?page=next",
                }
            ],
        }
        self.session.request.return_value = infinite_resp

        result = self.search.search(collections=["Sentinel-1A_SAR-IW_GRD"], max_pages=3)
        self.assertEqual(result.pages_retrieved, 3)
        self.assertTrue(result.pagination_capped)

    def test_empty_search_404_no_results_found(self):
        empty_resp = MagicMock()
        empty_resp.status_code = 404
        empty_resp.text = '{"ErrorCode":"404","Description":"NO RESULTS FOUND","Action":"No results found. Please modify the inputs and try again."}'
        self.session.request.return_value = empty_resp

        result = self.search.search(collections=["EOS-04_SAR-MRS_L2A"])
        self.assertEqual(result.total_returned, 0)
        self.assertEqual(result.features, [])
        self.assertFalse(result.pagination_capped)

    def test_pagination_strips_fields_from_next_body(self):
        page1_resp = MagicMock()
        page1_resp.status_code = 200
        page1_resp.json.return_value = {
            "type": "FeatureCollection",
            "features": [{"id": "item1"}],
            "links": [
                {
                    "rel": "next",
                    "href": "https://mock-bhoonidhi.nrsc.gov.in/data/search",
                    "method": "POST",
                    "body": {
                        "collections": ["EOS-04_SAR-FRS2_L2A"],
                        "token": "next:token:123",
                        "fields": {"exclude": ["assets.data", "properties.MetaData"]},
                    },
                }
            ],
        }

        page2_resp = MagicMock()
        page2_resp.status_code = 200
        page2_resp.json.return_value = {
            "type": "FeatureCollection",
            "features": [{"id": "item2"}],
            "links": [],
        }

        self.session.request.side_effect = [page1_resp, page2_resp]

        result = self.search.search(collections=["EOS-04_SAR-FRS2_L2A"], max_pages=2)
        self.assertEqual(result.total_returned, 2)
        # Check that second request body did NOT contain 'fields'
        second_call = self.session.request.call_args_list[1]
        sent_body = second_call.kwargs.get("json", {})
        self.assertNotIn("fields", sent_body)
        self.assertEqual(sent_body.get("token"), "next:token:123")


if __name__ == "__main__":
    unittest.main()
