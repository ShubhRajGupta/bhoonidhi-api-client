"""
Unit tests for Bhoonidhi Download Pipeline.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bhoonidhi.auth import BhoonidhiAuth
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.credentials import BhoonidhiCredentials
from bhoonidhi.download import BhoonidhiDownloader, sanitize_filename
from bhoonidhi.exceptions import DownloadIntegrityError


class TestDownloadPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)
        self.creds = BhoonidhiCredentials(user_id="user", password="password")
        self.config = BhoonidhiConfig(
            base_url="https://mock-bhoonidhi.nrsc.gov.in",
            download_dir=self.out_dir,
            max_concurrent_downloads=2,
        )
        self.session = MagicMock()
        self.auth = BhoonidhiAuth(credentials=self.creds, config=self.config, session=self.session)
        self.auth._access_token = "valid_token"
        self.auth._expires_at = 9999999999
        self.downloader = BhoonidhiDownloader(auth=self.auth, config=self.config, session=self.session)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_filename_sanitization(self):
        self.assertEqual(sanitize_filename("../../etc/passwd"), "etc_passwd")
        self.assertEqual(sanitize_filename("EOS04_SAR_2023.zip"), "EOS04_SAR_2023.zip")
        self.assertEqual(sanitize_filename("RS2:AWIFS*L2?"), "RS2_AWIFS_L2")

    def test_offline_product_skipped(self):
        feature = {
            "id": "item_offline_01",
            "collection": "ResourceSat-2_AWIFS_L2",
            "properties": {"Online": "N"},
        }
        res = self.downloader.download_feature(feature, output_dir=self.out_dir)
        self.assertEqual(res.status, "skipped_offline")
        self.assertIn("Browse & Order required", res.error_message or "")

    def test_successful_download_streaming_and_atomic_rename(self):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "13"}
        mock_response.iter_content.return_value = [b"chunk1_", b"chunk2"]

        self.session.get.return_value = mock_response

        res = self.downloader.download_product(
            item_id="RS2_AWIFS_001",
            collection_id="ResourceSat-2_AWIFS_L2",
            output_dir=self.out_dir,
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.bytes_downloaded, 13)
        expected_file = self.out_dir / "RS2_AWIFS_001.zip"
        self.assertTrue(expected_file.exists())
        self.assertEqual(expected_file.read_bytes(), b"chunk1_chunk2")

        # Ensure no lingering .part file
        part_file = self.out_dir / "RS2_AWIFS_001.zip.part"
        self.assertFalse(part_file.exists())

    def test_pre_existing_file_skipped_without_overwrite(self):
        # Create pre-existing destination file
        existing_file = self.out_dir / "PRE_EXISTING.zip"
        existing_file.write_bytes(b"existing_content")

        res = self.downloader.download_product(
            item_id="PRE_EXISTING",
            collection_id="ResourceSat-2_AWIFS_L2",
            output_dir=self.out_dir,
            overwrite=False,
        )
        self.assertEqual(res.status, "already_exists")
        self.assertEqual(res.bytes_downloaded, len(b"existing_content"))
        # Verify no network request was made
        self.session.get.assert_not_called()

    def test_download_412_concurrency_retry(self):
        # First call returns 412 (concurrency exceeded), second returns 200
        mock_412 = MagicMock()
        mock_412.__enter__.return_value = mock_412
        mock_412.status_code = 412

        mock_200 = MagicMock()
        mock_200.__enter__.return_value = mock_200
        mock_200.status_code = 200
        mock_200.headers = {"Content-Length": "4"}
        mock_200.iter_content.return_value = [b"data"]

        self.session.get.side_effect = [mock_412, mock_200]

        with patch("time.sleep") as mock_sleep:
            res = self.downloader.download_product(
                item_id="CONCURRENCY_TEST",
                collection_id="EOS-04_SAR-MRS_L2A",
                output_dir=self.out_dir,
            )
            self.assertEqual(res.status, "success")
            mock_sleep.assert_called()

    def test_cleanup_temporary_part_file_on_integrity_error(self):
        # Truncated download: header says 100 bytes, but only 20 received
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "100"}
        mock_response.iter_content.return_value = [b"12345678901234567890"]  # 20 bytes

        self.session.get.return_value = mock_response

        res = self.downloader.download_product(
            item_id="RS2_AWIFS_TRUNCATED",
            collection_id="ResourceSat-2_AWIFS_L2",
            output_dir=self.out_dir,
        )

        self.assertEqual(res.status, "failed")
        self.assertIn("File transfer truncated", res.error_message or "")

        # Crucial check: neither final file nor .part file should remain
        final_file = self.out_dir / "RS2_AWIFS_TRUNCATED.zip"
        part_file = self.out_dir / "RS2_AWIFS_TRUNCATED.zip.part"
        self.assertFalse(final_file.exists())
        self.assertFalse(part_file.exists())

    def test_download_404_absent_online_storage(self):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.status_code = 404
        mock_response.text = '{"errorCode": "D004", "description": "Product not found on online storage"}'

        self.session.get.return_value = mock_response

        res = self.downloader.download_product(
            item_id="EOS4_MISSING",
            collection_id="EOS-04_SAR-MRS_L2A",
            output_dir=self.out_dir,
        )

        self.assertEqual(res.status, "failed")
        self.assertIn("404 Not Found", res.error_message or "")
        self.assertIn("online storage", res.error_message or "")

    def test_batch_download_bounded_concurrency(self):
        features = [
            {"id": f"item_{i}", "collection": "EOS-04_SAR-MRS_L2A", "properties": {"Online": "Y"}}
            for i in range(4)
        ]

        with patch.object(self.downloader, "download_feature") as mock_dl:
            mock_dl.side_effect = lambda f, *args, **kwargs: MagicMock(
                item_id=f["id"], status="success", bytes_downloaded=100
            )

            # Request concurrency=10, should be clamped to 5
            results = self.downloader.download_batch(features, concurrency=10)
            self.assertEqual(len(results), 4)
            self.assertEqual(mock_dl.call_count, 4)

    def test_download_401_invalid_session_detected_reauth(self):
        # 1st attempt: 401 Invalid session detected
        mock_401 = MagicMock()
        mock_401.__enter__.return_value = mock_401
        mock_401.status_code = 401
        mock_401.text = '{"ErrorCode":"401","Description":"UNAUTHORIZED","Action":"Invalid session detected! Please login."}'

        # 2nd attempt after re-auth: 200 OK
        mock_200 = MagicMock()
        mock_200.__enter__.return_value = mock_200
        mock_200.status_code = 200
        mock_200.headers = {"Content-Length": "8"}
        mock_200.iter_content.return_value = [b"streamed"]

        self.session.get.side_effect = [mock_401, mock_200]

        def fake_reauth():
            self.auth._access_token = "refreshed_token"
            self.auth._expires_at = 9999999999
            return "refreshed_token"

        with patch.object(self.auth, "authenticate", side_effect=fake_reauth) as mock_reauth:
            res = self.downloader.download_product(
                item_id="RS2_REAUTH_TEST",
                collection_id="ResourceSat-2_AWIFS_L2",
                output_dir=self.out_dir,
            )
            self.assertEqual(res.status, "success")
            self.assertEqual(res.bytes_downloaded, 8)
            mock_reauth.assert_called_once()
            self.assertTrue((self.out_dir / "RS2_REAUTH_TEST.zip").exists())

    def test_download_uses_bearer_authorization_header(self):
        mock_200 = MagicMock()
        mock_200.__enter__.return_value = mock_200
        mock_200.status_code = 200
        mock_200.headers = {"Content-Length": "5"}
        mock_200.iter_content.return_value = [b"hello"]
        self.session.get.return_value = mock_200

        res = self.downloader.download_product(
            item_id="SEN1A_TEST",
            collection_id="Sentinel-1A_SAR-IW_GRD",
            output_dir=self.out_dir,
        )
        self.assertEqual(res.status, "success")
        args, kwargs = self.session.get.call_args
        # Header must be Authorization: Bearer <token>
        self.assertIn("Authorization", kwargs["headers"])
        self.assertTrue(kwargs["headers"]["Authorization"].startswith("Bearer "))
        # Token must NOT be in query parameters
        self.assertNotIn("token", kwargs["params"])
        self.assertEqual(kwargs["params"]["id"], "SEN1A_TEST")
        self.assertEqual(kwargs["params"]["collection"], "Sentinel-1A_SAR-IW_GRD")


if __name__ == "__main__":
    unittest.main()
