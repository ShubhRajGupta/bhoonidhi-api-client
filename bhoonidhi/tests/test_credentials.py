"""
Unit tests for Credentials loading, parsing, and masking.
"""

import os
import tempfile
import unittest
from pathlib import Path

from bhoonidhi.credentials import BhoonidhiCredentials, parse_env_file
from bhoonidhi.config import BhoonidhiConfig


class TestCredentials(unittest.TestCase):

    def test_direct_initialization(self):
        creds = BhoonidhiCredentials(user_id="test_user", password="secret_password_123")
        self.assertEqual(creds.user_id, "test_user")
        self.assertEqual(creds.password, "secret_password_123")

    def test_sensitive_masking(self):
        creds = BhoonidhiCredentials(user_id="isro_scientist", password="super_secret_token")
        repr_str = repr(creds)
        str_val = str(creds)
        self.assertNotIn("super_secret_token", repr_str)
        self.assertNotIn("super_secret_token", str_val)
        self.assertIn("password='***'", repr_str)
        self.assertTrue(repr_str.startswith("<BhoonidhiCredentials"))

    def test_empty_credentials_rejected(self):
        with self.assertRaises(ValueError):
            BhoonidhiCredentials(user_id="", password="valid_password")
        with self.assertRaises(ValueError):
            BhoonidhiCredentials(user_id="valid_user", password="   ")

    def test_parse_env_file(self):
        content = (
            "# This is a comment\n"
            "BHOONIDHI_USER_ID=my_user\n"
            "BHOONIDHI_PASSWORD='my_secret_pass'\n"
            "BHOONIDHI_BASE_URL=\"https://custom-api.gov.in\"\n"
            "EMPTY_VAL=\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        try:
            parsed = parse_env_file(temp_path)
            self.assertEqual(parsed.get("BHOONIDHI_USER_ID"), "my_user")
            self.assertEqual(parsed.get("BHOONIDHI_PASSWORD"), "my_secret_pass")
            self.assertEqual(parsed.get("BHOONIDHI_BASE_URL"), "https://custom-api.gov.in")
            self.assertEqual(parsed.get("EMPTY_VAL"), "")
        finally:
            Path(temp_path).unlink()

    def test_load_from_explicit_env_file(self):
        content = (
            "BHOONIDHI_USER_ID=loaded_user\n"
            "BHOONIDHI_PASSWORD=loaded_pass\n"
        )
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_path = f.name

        try:
            # Temporarily clear env vars to test file loading
            old_user = os.environ.pop("BHOONIDHI_USER_ID", None)
            old_pass = os.environ.pop("BHOONIDHI_PASSWORD", None)

            creds = BhoonidhiCredentials.load(env_path=temp_path)
            self.assertEqual(creds.user_id, "loaded_user")
            self.assertEqual(creds.password, "loaded_pass")
        finally:
            Path(temp_path).unlink()
            if old_user:
                os.environ["BHOONIDHI_USER_ID"] = old_user
            if old_pass:
                os.environ["BHOONIDHI_PASSWORD"] = old_pass

    def test_config_concurrency_ceiling(self):
        # Concurrency must not exceed 5
        config_high = BhoonidhiConfig(max_concurrent_downloads=10)
        self.assertEqual(config_high.max_concurrent_downloads, 5)

        config_low = BhoonidhiConfig(max_concurrent_downloads=0)
        self.assertEqual(config_low.max_concurrent_downloads, 1)

        config_normal = BhoonidhiConfig(max_concurrent_downloads=3)
        self.assertEqual(config_normal.max_concurrent_downloads, 3)


if __name__ == "__main__":
    unittest.main()

