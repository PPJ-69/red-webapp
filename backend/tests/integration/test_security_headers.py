from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.dependencies import get_stream_service
from backend.app.main import app
from backend.tests.integration.test_stream_relay import _service
from backend.tests.conftest import fake_cdn_server


class SecurityHeadersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_service_override = app.dependency_overrides.get(
            get_stream_service
        )

    def tearDown(self) -> None:
        if self.previous_service_override is None:
            app.dependency_overrides.pop(get_stream_service, None)
        else:
            app.dependency_overrides[get_stream_service] = (
                self.previous_service_override
            )

    def test_api_headers_and_cors_allow_deny_matrix(self) -> None:
        environment = {
            **os.environ,
            "APP_ENV": "test",
            "CORS_ALLOWED_ORIGINS": "https://frontend.example",
        }
        with patch.dict(os.environ, environment, clear=True), TestClient(app) as client:
            response = client.get("/health/live")
            preflight_allowed = client.options(
                "/api/search",
                headers={
                    "Origin": "https://frontend.example",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "x-correlation-id",
                },
            )
            preflight_denied = client.options(
                "/api/search",
                headers={
                    "Origin": "https://attacker.example",
                    "Access-Control-Request-Method": "GET",
                },
            )
            preflight_denied_method = client.options(
                "/api/search",
                headers={
                    "Origin": "https://frontend.example",
                    "Access-Control-Request-Method": "POST",
                },
            )
            preflight_denied_header = client.options(
                "/api/search",
                headers={
                    "Origin": "https://frontend.example",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization",
                },
            )
            unknown_origin = client.get(
                "/health/live", headers={"Origin": "https://attacker.example"}
            )

        self.assertEqual(response.status_code, 200)
        self.assert_security_headers(response.headers)
        self.assertEqual(
            preflight_allowed.headers["access-control-allow-origin"],
            "https://frontend.example",
        )
        self.assertIn("GET", preflight_allowed.headers["access-control-allow-methods"])
        self.assertNotIn("access-control-allow-credentials", preflight_allowed.headers)
        self.assertEqual(preflight_denied.status_code, 400)
        self.assertNotIn("access-control-allow-origin", preflight_denied.headers)
        self.assertEqual(preflight_denied_method.status_code, 400)
        self.assertNotIn(
            "POST", preflight_denied_method.headers["access-control-allow-methods"]
        )
        self.assertEqual(preflight_denied_header.status_code, 400)
        self.assertNotIn("access-control-allow-origin", unknown_origin.headers)

    def test_headers_are_applied_to_stream_responses(self) -> None:
        with fake_cdn_server() as cdn:
            service, transport = _service(cdn.base_url)
            app.dependency_overrides[get_stream_service] = lambda: service
            with patch.dict(
                os.environ,
                {
                    **os.environ,
                    "APP_ENV": "test",
                    "CORS_ALLOWED_ORIGINS": "",
                },
                clear=True,
            ):
                try:
                    with TestClient(app) as client:
                        response = client.get("/api/stream/sample-media")
                finally:
                    asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 200)
        self.assert_security_headers(response.headers)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_cors_defaults_to_same_origin_only(self) -> None:
        with patch.dict(
            os.environ,
            {**os.environ, "APP_ENV": "test", "CORS_ALLOWED_ORIGINS": ""},
            clear=True,
        ), TestClient(app) as client:
            same_origin = client.get(
                "/health/live", headers={"Origin": "http://testserver"}
            )
            preflight = client.options(
                "/api/search",
                headers={
                    "Origin": "http://testserver",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(same_origin.status_code, 200)
        self.assertNotIn("access-control-allow-origin", same_origin.headers)
        self.assertEqual(preflight.status_code, 400)

    def assert_security_headers(self, headers) -> None:
        self.assertEqual(
            headers["content-security-policy"].split("; ")[0],
            "default-src 'self'",
        )
        self.assertIn("script-src 'self'", headers["content-security-policy"])
        self.assertIn("script-src 'self';", headers["content-security-policy"])
        self.assertIn("object-src 'none'", headers["content-security-policy"])
        self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])
        self.assertEqual(headers["referrer-policy"], "no-referrer")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["x-frame-options"], "DENY")
        self.assertIn("fullscreen=(self)", headers["permissions-policy"])


if __name__ == "__main__":
    unittest.main()
