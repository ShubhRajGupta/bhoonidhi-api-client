"""
Unit tests for Bhoonidhi Authentication and Token Lifecycle.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from bhoonidhi.auth import BhoonidhiAuth
from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.credentials import BhoonidhiCredentials
from bhoonidhi.exceptions import BhoonidhiAuthError, BhoonidhiRateLimitError


class TestBhoonidhiAuth(unittest.TestCase):

    def setUp(self):
        self.creds = BhoonidhiCredentials(user_id="isro_user", password="secret_password")
        self.config = BhoonidhiConfig(base_url="https://mock-bhoonidhi.nrsc.gov.in")
        self.session = MagicMock()
        self.auth = BhoonidhiAuth(credentials=self.creds, config=self.config, session=self.session)

    def test_successful_authentication(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "mock_access_token_123",
            "refresh_token": "mock_refresh_token_456",
            "token_type": "Bearer",
            "expires_in": 1200,
        }
        self.session.post.return_value = mock_resp

        token = self.auth.authenticate()
        self.assertEqual(token, "mock_access_token_123")
        self.assertTrue(self.auth.is_authenticated)
        self.assertEqual(self.auth.get_auth_header(), {"Authorization": "Bearer mock_access_token_123"})

        # Check payload
        self.session.post.assert_called_once()
        args, kwargs = self.session.post.call_args
        self.assertIn("https://mock-bhoonidhi.nrsc.gov.in/auth/token", args)
        self.assertEqual(kwargs["json"]["userId"], "isro_user")
        self.assertEqual(kwargs["json"]["grant_type"], "password")

    def test_token_reuse_without_extra_requests(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "reused_token",
            "refresh_token": "ref_token",
            "expires_in": 1200,
        }
        self.session.post.return_value = mock_resp

        # First call hits API
        t1 = self.auth.get_valid_token()
        # Second and third calls should reuse cached token
        t2 = self.auth.get_valid_token()
        t3 = self.auth.get_valid_token()

        self.assertEqual(t1, "reused_token")
        self.assertEqual(t2, "reused_token")
        self.assertEqual(t3, "reused_token")
        self.assertEqual(self.session.post.call_count, 1)

    def test_refresh_token_rotation(self):
        # Initial token
        self.auth._access_token = "old_token"
        self.auth._refresh_token = "initial_refresh_token"
        self.auth._expires_at = time.time() - 10  # Expired

        mock_refresh_resp = MagicMock()
        mock_refresh_resp.status_code = 200
        mock_refresh_resp.json.return_value = {
            "access_token": "new_refreshed_token",
            "refresh_token": "rotated_refresh_token",  # Rotated refresh token
            "expires_in": 1200,
        }
        self.session.post.return_value = mock_refresh_resp

        new_token = self.auth.get_valid_token()
        self.assertEqual(new_token, "new_refreshed_token")
        self.assertEqual(self.auth._refresh_token, "rotated_refresh_token")

        # Verify refresh call payload
        args, kwargs = self.session.post.call_args
        self.assertEqual(kwargs["json"]["grant_type"], "refresh_token")
        self.assertEqual(kwargs["json"]["refresh_token"], "initial_refresh_token")

    def test_failed_authentication_bad_credentials(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"errorCode": "AUTH002", "description": "Invalid user credentials"}'
        self.session.post.return_value = mock_resp

        with self.assertRaises(BhoonidhiAuthError) as ctx:
            self.auth.authenticate()

        self.assertIn("Invalid user credentials", str(ctx.exception))
        self.assertNotIn("secret_password", str(ctx.exception))

    def test_auth_rate_limiting_429(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "60"}
        mock_resp.text = '{"errorCode": "RATE429", "description": "Too many auth requests"}'
        self.session.post.return_value = mock_resp

        with self.assertRaises(BhoonidhiRateLimitError) as ctx:
            self.auth.authenticate()

        self.assertEqual(ctx.exception.retry_after, 60)
        self.assertIn("Rate limit exceeded", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

