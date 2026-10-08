import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.tests.fakes.fake_provider import FakeMediaProvider


class SearchApiIntegrationTests(unittest.TestCase):
    def test_search_endpoint_returns_provider_results(self) -> None:
        app.state.upstream_provider = FakeMediaProvider()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                response = client.get("/api/search", params={"q": "sample", "tags": ["test"], "page": 1, "limit": 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["id"], "sample-media")
        self.assertEqual(response.json()["page"], 1)
        self.assertEqual(response.json()["limit"], 20)

    def test_search_endpoint_validates_limits(self) -> None:
        app.state.upstream_provider = FakeMediaProvider()
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(app) as client:
                response = client.get("/api/search", params={"page": 0})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["category"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
