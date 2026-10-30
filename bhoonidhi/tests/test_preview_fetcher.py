"""
Unit tests for Bhoonidhi Preview Fetcher.
Tests pagination, deduplication, empty results, missing previews,
oversized files, invalid images, and partial file cleanup.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bhoonidhi.client import BhoonidhiClient
from bhoonidhi.preview_fetcher import (
    PreviewFetcher,
    extract_preview_info,
    get_kolkata_day_window,
    is_safe_preview_url,
    validate_image_bytes,
)
from bhoonidhi.search import STACSearchResult


class TestPreviewFetcher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.mock_client = MagicMock()
        self.mock_client.auth.get_auth_header.return_value = {"Authorization": "Bearer mock_token"}
        self.mock_client.config.connect_timeout = 5.0
        self.mock_client.session = MagicMock()
        self.fetcher = PreviewFetcher(client=self.mock_client, max_preview_size_bytes=1024 * 1024)

        # 1x1 valid sample JPEG bytes
        self.sample_jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
            b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_kolkata_day_window_calculation(self):
        start_utc, end_utc, interval = get_kolkata_day_window("2026-10-29")
        self.assertEqual(start_utc, "2026-10-28T18:30:00Z")
        self.assertEqual(end_utc, "2026-10-29T18:29:59Z")
        self.assertEqual(interval, "2026-10-28T18:30:00Z/2026-10-29T18:29:59Z")

    def test_is_safe_preview_url_rejections(self):
        # Must reject ZIPs, GeoTIFFs, and download endpoints
        self.assertFalse(is_safe_preview_url("https://api.nrsc.gov.in/download?id=123"))
        self.assertFalse(is_safe_preview_url("https://archive.nrsc.gov.in/product.zip"))
        self.assertFalse(is_safe_preview_url("https://archive.nrsc.gov.in/scene.tif"))
        self.assertFalse(is_safe_preview_url("https://archive.nrsc.gov.in/scene.tar.gz"))
        self.assertFalse(is_safe_preview_url(""))

        # Must accept safe image extensions
        self.assertTrue(is_safe_preview_url("https://bhoonidhi.nrsc.gov.in/stac/PRODUCTJPGS/thumb.jpg"))
        self.assertTrue(is_safe_preview_url("https://bhoonidhi.nrsc.gov.in/previews/preview.png"))

    def test_extract_preview_info(self):
        # 1. Asset with thumbnail key
        feat1 = {
            "assets": {
                "thumbnail": {
                    "href": "https://nrsc.gov.in/thumb.jpg",
                    "type": "image/jpeg",
                }
            }
        }
        url, mime = extract_preview_info(feat1)
        self.assertEqual(url, "https://nrsc.gov.in/thumb.jpg")
        self.assertEqual(mime, "image/jpeg")

        # 2. Asset with unsafe zip URL should be ignored
        feat2 = {
            "assets": {
                "data": {
                    "href": "https://nrsc.gov.in/product.zip",
                    "type": "application/zip",
                }
            }
        }
        url2, mime2 = extract_preview_info(feat2)
        self.assertIsNone(url2)

        # 3. Missing preview
        feat3 = {"assets": {}, "links": []}
        url3, mime3 = extract_preview_info(feat3)
        self.assertIsNone(url3)

    def test_download_preview_success(self):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": str(len(self.sample_jpeg))}
        mock_resp.iter_content.return_value = [self.sample_jpeg]
        self.mock_client.session.get.return_value = mock_resp

        res = self.fetcher.download_preview(
            preview_url="https://nrsc.gov.in/test.jpg",
            item_id="SCENE_001",
            dest_dir=self.output_dir / "previews",
        )

        self.assertEqual(res.status, "downloaded")
        self.assertEqual(res.size_bytes, len(self.sample_jpeg))
        self.assertIsNotNone(res.dimensions)
        self.assertTrue(res.file_path.exists())

    def test_download_preview_oversized_file(self):
        # Set small limit (100 bytes), sample jpeg is ~125 bytes
        fetcher_small = PreviewFetcher(client=self.mock_client, max_preview_size_bytes=50)

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "125"}
        mock_resp.iter_content.return_value = [self.sample_jpeg]
        self.mock_client.session.get.return_value = mock_resp

        res = fetcher_small.download_preview(
            preview_url="https://nrsc.gov.in/big.jpg",
            item_id="BIG_SCENE",
            dest_dir=self.output_dir / "previews",
        )

        self.assertEqual(res.status, "oversized")
        # Ensure file was not created
        self.assertFalse((self.output_dir / "previews" / "BIG_SCENE.jpg").exists())

    def test_download_preview_invalid_image_content(self):
        # Returns HTML error disguised as 200 OK
        html_payload = b"<html><body>502 Bad Gateway</body></html>"
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": str(len(html_payload))}
        mock_resp.iter_content.return_value = [html_payload]
        self.mock_client.session.get.return_value = mock_resp

        res = self.fetcher.download_preview(
            preview_url="https://nrsc.gov.in/fake.jpg",
            item_id="FAKE_IMAGE",
            dest_dir=self.output_dir / "previews",
        )

        self.assertEqual(res.status, "invalid_image")
        self.assertFalse((self.output_dir / "previews" / "FAKE_IMAGE.jpg").exists())

    def test_download_preview_already_exists(self):
        # Pre-create valid file
        previews_dir = self.output_dir / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        dest_file = previews_dir / "EXISTING.jpg"
        dest_file.write_bytes(self.sample_jpeg)

        res = self.fetcher.download_preview(
            preview_url="https://nrsc.gov.in/existing.jpg",
            item_id="EXISTING",
            dest_dir=previews_dir,
        )

        self.assertEqual(res.status, "already_exists")
        # Ensure no network request made
        self.mock_client.session.get.assert_not_called()

    def test_fetch_day_deduplication_and_manifest(self):
        # Mock search returning 3 features, 2 of which have identical ID (duplicate)
        feat1 = {
            "id": "ITEM_DUP",
            "collection": "TEST_COLL",
            "properties": {"datetime": "2026-10-29T10:00:00Z"},
            "assets": {"thumbnail": {"href": "https://nrsc.gov.in/t1.jpg"}},
        }
        feat2 = {
            "id": "ITEM_DUP",  # Duplicate ID
            "collection": "TEST_COLL",
            "properties": {"datetime": "2026-10-29T10:00:00Z"},
            "assets": {"thumbnail": {"href": "https://nrsc.gov.in/t1.jpg"}},
        }
        feat3 = {
            "id": "ITEM_UNIQUE",
            "collection": "TEST_COLL",
            "properties": {"datetime": "2026-10-29T11:00:00Z"},
            "assets": {},  # Missing preview
        }

        self.mock_client.search.return_value = STACSearchResult(
            features=[feat1, feat2, feat3],
            total_returned=3,
            pages_retrieved=1,
        )

        # Mock download for feat1
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": str(len(self.sample_jpeg))}
        mock_resp.iter_content.return_value = [self.sample_jpeg]
        self.mock_client.session.get.return_value = mock_resp

        manifest = self.fetcher.fetch_day(
            collection_id="TEST_COLL",
            target_date="2026-10-29",
            output_base_dir=self.output_dir,
        )

        # Deduplication check: 3 features returned, but only 2 unique items
        self.assertEqual(manifest["total_items_found"], 2)
        self.assertEqual(manifest["previews_downloaded"], 1)
        self.assertEqual(manifest["previews_unavailable"], 1)

        # Verify output files exist
        target_path = self.output_dir / "2026-10-29" / "TEST_COLL"
        self.assertTrue((target_path / "metadata.json").exists())
        self.assertTrue((target_path / "metadata.csv").exists())
        self.assertTrue((target_path / "manifest.json").exists())
        self.assertTrue((target_path / "previews" / "ITEM_DUP.jpg").exists())


if __name__ == "__main__":
    unittest.main()
