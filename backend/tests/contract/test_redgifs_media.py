import unittest
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.domain.models import SearchQuery
from backend.app.upstream.redgifs_client import RedgifsClient
from backend.tests.contract.provider_contract import ProviderContract

FIXTURES = {
    "get:/gifs/search": {
        "gifs": [
            {
                "id": "sample-media",
                "userName": "sample",
                "tags": ["sample", "test"],
                "width": 640,
                "height": 360,
                "duration": 12.5,
                "urls": {
                    "hd": "https://cdn.example.invalid/media/sample-hd.mp4",
                    "sd": "https://cdn.example.invalid/media/sample-sd.mp4",
                    "thumbnail": "https://images.example.invalid/sample.jpg",
                    "poster": "https://images.example.invalid/sample-poster.jpg",
                },
            }
        ],
        "page": 1,
        "pages": 1,
    },
    "get:/feeds/trending/popular": {
        "gifs": [],
        "page": 1,
        "pages": 1,
    },
    "get:/users/sample/search": {
        "gifs": [],
        "page": 1,
        "pages": 1,
    },
    "get:/gifs/sample-media": {
        "gif": {
            "id": "sample-media",
            "description": "Example item",
            "userName": "sample",
            "tags": ["sample", "test"],
            "width": 640,
            "height": 360,
            "duration": 12.5,
            "urls": {
                "hd": "https://cdn.example.invalid/media/sample-hd.mp4",
                "sd": "https://cdn.example.invalid/media/sample-sd.mp4",
                "thumbnail": "https://images.example.invalid/sample.jpg",
                "poster": "https://images.example.invalid/sample-poster.jpg",
            },
        }
    },
    "get:/users/sample": {
        "user": {"id": "sample", "username": "sample", "displayName": "Sample User"},
    },
    "get:/search/tags": {"tags": ["sample", "test"]},
}


class RedgifsMediaContractTests(ProviderContract, unittest.IsolatedAsyncioTestCase):
    def make_provider(self):
        return RedgifsClient(fixtures=FIXTURES)

    async def test_empty_browse_uses_live_trending_feed(self) -> None:
        result = await self.make_provider().search(SearchQuery(mode="trending"))

        self.assertEqual(result.page, 1)
        self.assertFalse(result.has_more)

    async def test_creator_query_uses_live_user_feed(self) -> None:
        result = await self.make_provider().search(
            SearchQuery(query="@sample", order="latest")
        )

        self.assertEqual(result.page, 1)
        self.assertFalse(result.has_more)

    async def test_client_fetches_temporary_token_without_a_configured_token(
        self,
    ) -> None:
        auth_http = AsyncMock()
        response = MagicMock()
        response.json.return_value = {"token": "local-test-token"}
        auth_http.get.return_value = response
        transport = AsyncMock()

        with patch(
            "backend.app.upstream.redgifs_client.httpx.AsyncClient",
            return_value=auth_http,
        ) as client_factory:
            provider = RedgifsClient(
                base_url="https://api.example.invalid/v2",
                transport=transport,
            )
            try:
                await provider.authenticate()
            finally:
                await provider.aclose()

        client_factory.assert_called_once()
        auth_http.get.assert_awaited_once_with(
            "https://api.example.invalid/v2/auth/temporary"
        )
        auth_http.aclose.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
