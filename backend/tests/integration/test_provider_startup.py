from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.upstream.redgifs_client import RedgifsClient


class ProviderStartupTests(unittest.TestCase):
    def test_disabled_provider_fails_closed_with_service_unavailable(self) -> None:
        app.state.upstream_provider = None
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "UPSTREAM_PROVIDER": "disabled",
                "REDGIFS_TOKEN_FILE": "",
            },
        ):
            with TestClient(app) as client:
                response = client.get("/api/search", params={"q": "test"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["category"], "provider_unavailable")

    def test_explicit_provider_configuration_wires_client_without_live_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "provider-token"
            token_file.write_text("startup-test-token", encoding="utf-8")
            environment = {
                "APP_ENV": "production",
                "UPSTREAM_PROVIDER": "redgifs",
                "REDGIFS_TOKEN_FILE": str(token_file),
            }

            with patch.dict(os.environ, environment):
                with TestClient(app) as client:
                    provider = app.state.upstream_provider
                    self.assertIsInstance(provider, RedgifsClient)
                    self.assertEqual(
                        provider.auth_manager.token,
                        "startup-test-token",
                    )
                    provider.transport.request = AsyncMock()
                    response = client.get("/health/ready")
                    self.assertEqual(response.status_code, 200)
                    provider.transport.request.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
