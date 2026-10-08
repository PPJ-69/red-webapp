import unittest

import httpx2 as httpx

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import classify_upstream_error, classify_upstream_status


class ErrorClassificationTests(unittest.TestCase):
    def test_classify_upstream_status(self) -> None:
        self.assertEqual(classify_upstream_status(401), ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED)
        self.assertEqual(classify_upstream_status(403), ErrorCategory.FORBIDDEN)
        self.assertEqual(classify_upstream_status(404), ErrorCategory.NOT_FOUND)
        self.assertEqual(classify_upstream_status(429), ErrorCategory.RATE_LIMITED)
        self.assertEqual(classify_upstream_status(500), ErrorCategory.PROVIDER_ERROR)
        self.assertEqual(classify_upstream_status(503), ErrorCategory.PROVIDER_UNAVAILABLE)
        self.assertEqual(classify_upstream_status(504), ErrorCategory.UPSTREAM_TIMEOUT)

    def test_classify_upstream_error_handles_httpx_timeouts(self) -> None:
        self.assertEqual(
            classify_upstream_error(httpx.TimeoutException("timeout")),
            ErrorCategory.UPSTREAM_TIMEOUT,
        )

    def test_classify_upstream_error_defaults_to_provider_error(self) -> None:
        self.assertEqual(
            classify_upstream_error(ValueError("unexpected")),
            ErrorCategory.PROVIDER_ERROR,
        )


if __name__ == "__main__":
    unittest.main()
