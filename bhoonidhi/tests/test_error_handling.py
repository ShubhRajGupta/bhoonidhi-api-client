"""
Unit tests for Bhoonidhi Error Response Parsing and Exception Hierarchy.
"""

import unittest
from bhoonidhi.exceptions import (
    BhoonidhiAuthError,
    BhoonidhiConcurrencyError,
    BhoonidhiError,
    BhoonidhiNotFoundError,
    BhoonidhiRateLimitError,
    BhoonidhiServerError,
    ProductNotOnlineError,
    parse_bhoonidhi_error_response,
)


class TestErrorHandling(unittest.TestCase):

    def test_parse_lowercase_error_schema(self):
        # Format 1: {"errorCode": "AUTH001", "description": "Invalid credentials"}
        raw = '{"errorCode": "AUTH001", "description": "Invalid credentials"}'
        parsed = parse_bhoonidhi_error_response(401, raw)
        self.assertEqual(parsed["status_code"], 401)
        self.assertEqual(parsed["error_code"], "AUTH001")
        self.assertEqual(parsed["description"], "Invalid credentials")
        self.assertIsNone(parsed["action"])

    def test_parse_uppercase_error_schema(self):
        # Format 2: {"ErrorCode": "DOW412", "Description": "Max sessions reached", "Action": "Retry after 60s"}
        raw = '{"ErrorCode": "DOW412", "Description": "Max sessions reached", "Action": "Retry after 60s"}'
        parsed = parse_bhoonidhi_error_response(412, raw)
        self.assertEqual(parsed["status_code"], 412)
        self.assertEqual(parsed["error_code"], "DOW412")
        self.assertEqual(parsed["description"], "Max sessions reached")
        self.assertEqual(parsed["action"], "Retry after 60s")

    def test_parse_non_json_error(self):
        raw = "502 Bad Gateway: NGINX reverse proxy failed"
        parsed = parse_bhoonidhi_error_response(502, raw)
        self.assertEqual(parsed["status_code"], 502)
        self.assertIsNone(parsed["error_code"])
        self.assertIn("502 Bad Gateway", parsed["description"])

    def test_exception_string_formatting(self):
        err = BhoonidhiError(
            message="Operation failed",
            status_code=412,
            error_code="DOW412",
            action="Reduce concurrency",
        )
        s = str(err)
        self.assertIn("Operation failed", s)
        self.assertIn("HTTP 412", s)
        self.assertIn("Code: DOW412", s)
        self.assertIn("Action: Reduce concurrency", s)


if __name__ == "__main__":
    unittest.main()

