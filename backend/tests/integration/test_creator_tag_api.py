import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.tests.fakes.fake_provider import FakeMediaProvider


class CreatorTagApiIntegrationTests(unittest.TestCase):
    def test_creator_endpoint_returns_canonical_creator(self) -> None:
        app.state.upstream_provider = FakeMediaProvider()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                response = client.get("/api/creator/sample")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "sample")

    def test_tag_suggestions_endpoint_returns_strings(self) -> None:
        app.state.upstream_provider = FakeMediaProvider()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                response = client.get("/api/tags/suggest", params={"q": "sam"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("sample", response.json())

    def test_invalid_creator_and_tag_input_is_rejected(self) -> None:
        app.state.upstream_provider = FakeMediaProvider()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                creator_response = client.get("/api/creator/" + ("x" * 101))
                tag_response = client.get("/api/tags/suggest", params={"q": ""})

        self.assertEqual(creator_response.status_code, 400)
        self.assertEqual(creator_response.json()["category"], "invalid_request")
        self.assertEqual(tag_response.status_code, 400)
        self.assertEqual(tag_response.json()["category"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
