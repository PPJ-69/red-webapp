import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app


class HealthIntegrationTests(unittest.TestCase):
    def test_health_endpoints_and_openapi_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            original_directory = Path.cwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ, {"APP_ENV": "test"}):
                    before = set(Path(directory).iterdir())
                    with TestClient(app) as client:
                        self.assertEqual(client.get("/health/live").json(), {"status": "ok"})
                        self.assertEqual(client.get("/health/ready").json(), {"status": "ok"})
                        schema = client.get("/openapi.json").json()
                    after = set(Path(directory).iterdir())
            finally:
                os.chdir(original_directory)

        self.assertEqual(after, before)
        components = schema["components"]["schemas"]
        for model in (
            "Creator",
            "MediaSource",
            "MediaItem",
            "SearchResult",
            "SearchQuery",
            "ErrorEnvelope",
        ):
            self.assertIn(model, components)
        self.assertIn(
            "/health/live", schema["paths"]
        )
        self.assertIn("/health/ready", schema["paths"])
        self.assertIn(
            "playbackUrl", components["MediaSource"]["properties"]
        )

    def test_startup_fails_without_required_environment(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "APP_ENV must be set"):
                with TestClient(app):
                    pass


if __name__ == "__main__":
    unittest.main()
