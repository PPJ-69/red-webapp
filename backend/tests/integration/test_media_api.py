import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.domain.models import MediaItem, MediaSource
from backend.tests.fakes.fake_provider import FakeMediaProvider


class MediaApiIntegrationTests(unittest.TestCase):
    def test_media_metadata_endpoint_returns_canonical_item(self) -> None:
        class ProviderWithSources(FakeMediaProvider):
            async def get_media(self, media_id: str) -> MediaItem:
                item = await super().get_media(media_id)
                return item.model_copy(
                    update={
                        "sources": [
                            MediaSource(
                                playbackUrl="https://cdn.example.invalid/media.mp4?token=secret"
                            )
                        ]
                    }
                )

        app.state.upstream_provider = ProviderWithSources()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                response = client.get("/api/media/sample-media")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "sample-media")
        self.assertEqual(response.json()["title"], "Sample media")
        self.assertIn("creator", response.json())
        self.assertIn("tags", response.json())
        self.assertEqual(response.json()["sources"], [])
        self.assertNotIn("token=secret", response.text)

    def test_unknown_media_returns_not_found(self) -> None:
        app.state.upstream_provider = FakeMediaProvider()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                response = client.get("/api/media/unknown")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
