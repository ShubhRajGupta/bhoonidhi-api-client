"""
Integration unit tests for BhoonidhiClient high-level facade.
"""

import unittest
from unittest.mock import MagicMock, patch

from bhoonidhi.client import BhoonidhiClient
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.credentials import BhoonidhiCredentials


class TestBhoonidhiClient(unittest.TestCase):

    def setUp(self):
        self.creds = BhoonidhiCredentials(user_id="isro_user", password="secret_password")
        self.config = BhoonidhiConfig(base_url="https://mock-bhoonidhi.nrsc.gov.in")
        self.client = BhoonidhiClient(credentials=self.creds, config=self.config)

    def test_get_collections(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "collections": [
                {"id": "ResourceSat-2_AWIFS_L2", "title": "AWIFS L2"},
                {"id": "EOS-04_SAR-MRS_L2A", "title": "EOS-04 SAR"},
            ]
        }
        self.client.session.get = MagicMock(return_value=mock_resp)
        self.client.auth._access_token = "valid_token"
        self.client.auth._expires_at = 9999999999

        colls = self.client.get_collections()
        self.assertEqual(len(colls), 2)
        self.assertEqual(colls[0]["id"], "ResourceSat-2_AWIFS_L2")

    def test_resolve_product_types(self):
        result = self.client.resolve_product_types(["awifs", "eos-04"])
        self.assertEqual(result.resolved, ["ResourceSat-2_AWIFS_L2", "EOS-04_SAR-MRS_L2A"])
        self.assertFalse(result.has_unresolved)


if __name__ == "__main__":
    unittest.main()

