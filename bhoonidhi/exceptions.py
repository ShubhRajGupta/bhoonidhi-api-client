"""
Bhoonidhi API Exceptions and Error Parsers.
Defines domain exceptions and defensive error response parsing supporting
both Bhoonidhi error schemas (errorCode/description and ErrorCode/Description/Action).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


class BhoonidhiError(Exception):
    """Base exception for all Bhoonidhi API errors."""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        action: Optional[str] = None,
        raw_response: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.action = action
        self.raw_response = raw_response

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")
        if self.error_code:
            parts.append(f"Code: {self.error_code}")
        if self.action:
            parts.append(f"Action: {self.action}")
        return " | ".join(parts)


class BhoonidhiAuthError(BhoonidhiError):
    """Raised on authentication failures, bad credentials, or expired refresh tokens (HTTP 401)."""
    pass


class BhoonidhiSessionLimitError(BhoonidhiError):
    """Raised when maximum active user sessions are exceeded (HTTP 403)."""
    pass


class BhoonidhiNotFoundError(BhoonidhiError):
    """Raised when a requested resource or download item is not found (HTTP 404)."""
    pass


class BhoonidhiConcurrencyError(BhoonidhiError):
    """Raised when download concurrency limits are exceeded (HTTP 412)."""
    pass


class BhoonidhiRateLimitError(BhoonidhiError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class BhoonidhiServerError(BhoonidhiError):
    """Raised on internal server errors or gateway timeouts (HTTP 500/502/503/504)."""
    pass


class ProductNotOnlineError(BhoonidhiError):
    """Raised when attempting to download a product with Online == 'N'."""
    pass


class STACSearchError(BhoonidhiError):
    """Raised when STAC search queries or pagination fail."""
    pass


class DownloadIntegrityError(BhoonidhiError):
    """Raised when transferred file size or integrity checks fail."""
    pass


def parse_bhoonidhi_error_response(status_code: int, response_text: str) -> Dict[str, Optional[str]]:
    """
    Defensively parse error details from Bhoonidhi response body.
    Supports both observed Bhoonidhi formats:
      1) {"errorCode": "...", "description": "..."}
      2) {"ErrorCode": "...", "Description": "...", "Action": "..."}
    """
    error_code: Optional[str] = None
    description: Optional[str] = None
    action: Optional[str] = None

    if response_text:
        try:
            data = json.loads(response_text)
            if isinstance(data, dict):
                error_code = data.get("errorCode") or data.get("ErrorCode") or data.get("code")
                description = data.get("description") or data.get("Description") or data.get("message")
                action = data.get("action") or data.get("Action")
        except Exception:
            description = response_text[:200]

    return {
        "status_code": status_code,
        "error_code": str(error_code) if error_code is not None else None,
        "description": str(description) if description is not None else None,
        "action": str(action) if action is not None else None,
    }

