"""
Bhoonidhi Authentication and Token Lifecycle Manager.
Implements token acquisition, caching, reuse, refresh token rotation,
and bounded re-authentication on 401 without credential leakage.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional
import requests

from bhoonidhi.config import BhoonidhiConfig
from bhoonidhi.credentials import BhoonidhiCredentials
from bhoonidhi.exceptions import (
    BhoonidhiAuthError,
    BhoonidhiRateLimitError,
    parse_bhoonidhi_error_response,
)

logger = logging.getLogger(__name__)


class BhoonidhiAuth:
    """Manages Bhoonidhi OAuth tokens and lifecycle."""

    def __init__(
        self,
        credentials: Optional[BhoonidhiCredentials] = None,
        config: Optional[BhoonidhiConfig] = None,
        session: Optional[requests.Session] = None,
    ):
        self.credentials = credentials or BhoonidhiCredentials.load()
        self.config = config or BhoonidhiConfig.from_env()
        self.session = session or requests.Session()

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_type: str = "Bearer"
        self._expires_at: float = 0.0

        # Safety window in seconds before actual expiry to refresh preemptively
        self._expiry_buffer: float = 60.0

    @property
    def is_authenticated(self) -> bool:
        """Returns True if a valid, non-expired access token is available."""
        return self._access_token is not None and (time.time() + self._expiry_buffer < self._expires_at)

    def get_auth_header(self) -> Dict[str, str]:
        """Returns the Authorization header with a valid bearer token, refreshing if needed."""
        token = self.get_valid_token()
        return {"Authorization": f"Bearer {token}"}

    def get_valid_token(self) -> str:
        """
        Returns a valid access token.
        Reuses cached token if still within validity window; otherwise refreshes or re-authenticates.
        """
        if self.is_authenticated and self._access_token:
            return self._access_token

        # Try refresh token first if available
        if self._refresh_token:
            try:
                return self.refresh_access_token()
            except Exception as e:
                logger.warning("Token refresh failed; falling back to credential authentication: %s", type(e).__name__)

        # Fall back to full authentication with credentials
        return self.authenticate()

    def authenticate(self) -> str:
        """
        Authenticate using username and password (grant_type: password).
        POST /auth/token
        """
        url = f"{self.config.base_url}/auth/token"
        payload = {
            "userId": self.credentials.user_id,
            "password": self.credentials.password,
            "grant_type": "password",
        }

        try:
            resp = self.session.post(
                url,
                json=payload,
                timeout=(self.config.connect_timeout, self.config.request_timeout),
            )
        except requests.RequestException as e:
            raise BhoonidhiAuthError(f"Network error during authentication: {type(e).__name__}") from e

        if resp.status_code == 200:
            return self._apply_token_response(resp.json())

        # Error handling
        parsed = parse_bhoonidhi_error_response(resp.status_code, resp.text)
        desc = parsed.get("description") or "Authentication failed."
        code = parsed.get("error_code")
        action = parsed.get("action")

        if resp.status_code == 429:
            retry_after = None
            if "Retry-After" in resp.headers:
                try:
                    retry_after = int(resp.headers["Retry-After"])
                except ValueError:
                    pass
            raise BhoonidhiRateLimitError(
                f"Rate limit exceeded during authentication (20 req/hour max): {desc}",
                retry_after=retry_after,
                status_code=429,
                error_code=code,
                action=action,
            )

        raise BhoonidhiAuthError(
            f"Authentication failed: {desc}",
            status_code=resp.status_code,
            error_code=code,
            action=action,
        )

    def refresh_access_token(self) -> str:
        """
        Refresh access token using refresh_token grant.
        POST /auth/token
        """
        if not self._refresh_token:
            raise BhoonidhiAuthError("No refresh token available.")

        url = f"{self.config.base_url}/auth/token"
        payload = {
            "userId": self.credentials.user_id,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            resp = self.session.post(
                url,
                json=payload,
                timeout=(self.config.connect_timeout, self.config.request_timeout),
            )
        except requests.RequestException as e:
            raise BhoonidhiAuthError(f"Network error during token refresh: {type(e).__name__}") from e

        if resp.status_code == 200:
            return self._apply_token_response(resp.json())

        # Invalidate cached tokens on failure
        self._access_token = None
        self._refresh_token = None
        self._expires_at = 0.0

        parsed = parse_bhoonidhi_error_response(resp.status_code, resp.text)
        raise BhoonidhiAuthError(
            f"Token refresh failed: {parsed.get('description') or 'Invalid refresh token.'}",
            status_code=resp.status_code,
            error_code=parsed.get("error_code"),
            action=parsed.get("action"),
        )

    def _apply_token_response(self, data: dict) -> str:
        """Extract and store token fields from response."""
        access_token = data.get("access_token")
        if not access_token:
            raise BhoonidhiAuthError("Response missing required 'access_token' field.")

        self._access_token = access_token
        # Update refresh token if returned (supporting token rotation)
        if "refresh_token" in data and data["refresh_token"]:
            self._refresh_token = data["refresh_token"]

        self._token_type = data.get("token_type", "Bearer")
        expires_in = data.get("expires_in", 1200)
        try:
            expires_in_sec = float(expires_in)
        except (ValueError, TypeError):
            expires_in_sec = 1200.0

        self._expires_at = time.time() + expires_in_sec
        return self._access_token

    def invalidate(self) -> None:
        """Invalidate current access and refresh tokens locally."""
        self._access_token = None
        self._refresh_token = None
        self._expires_at = 0.0

