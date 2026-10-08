import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.tests.fakes.fake_provider import FakeMediaProvider


class MediaSourceApiIntegrationTests(unittest.TestCase):
    def test_media_source_endpoint_returns_resolved_descriptor(self) -> None:
        app.state.upstream_provider = FakeMediaProvider()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                response = client.get("/api/media/sample-media/source", params={"quality": "auto"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["playbackUrl"], "/api/stream/sample-media?quality=auto"
        )
        self.assertEqual(payload["kind"], "relay")
        self.assertNotIn("cdn.example.invalid", response.text)
        self.assertIn("requiresRelay", payload)
        self.assertIn("expiresAt", payload)


if __name__ == "__main__":
    unittest.main()
