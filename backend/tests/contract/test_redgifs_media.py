import unittest

from backend.app.upstream.redgifs_client import RedgifsClient
from backend.tests.contract.provider_contract import ProviderContract

FIXTURES = {
    "get:/search": {
        "items": [
            {
                "id": "sample-media",
                "title": "Sample media",
                "description": "Example item",
                "creator": {"id": "sample", "username": "sample"},
                "tags": ["sample", "test"],
                "width": 640,
                "height": 360,
                "duration": 12.5,
                "thumbnailUrl": "https://images.example.invalid/sample.jpg",
                "posterUrl": "https://images.example.invalid/sample-poster.jpg",
                "sources": [{"playbackUrl": "https://cdn.example.invalid/media/sample.mp4", "mimeType": "video/mp4"}],
            }
        ],
        "page": 1,
        "limit": 20,
        "hasMore": False,
        "total": 1,
    },
    "get:/media/sample-media": {
        "id": "sample-media",
        "title": "Sample media",
        "description": "Example item",
        "creator": {"id": "sample", "username": "sample"},
        "tags": ["sample", "test"],
        "width": 640,
        "height": 360,
        "duration": 12.5,
        "thumbnailUrl": "https://images.example.invalid/sample.jpg",
        "posterUrl": "https://images.example.invalid/sample-poster.jpg",
        "sources": [{"playbackUrl": "https://cdn.example.invalid/media/sample.mp4", "mimeType": "video/mp4"}],
    },
    "get:/creators/sample": {
        "creator": {"id": "sample", "username": "sample", "displayName": "Sample User"},
    },
    "get:/tags": {"tags": ["sample", "test"]},
}


class RedgifsMediaContractTests(ProviderContract, unittest.IsolatedAsyncioTestCase):
    def make_provider(self):
        return RedgifsClient(fixtures=FIXTURES)


if __name__ == "__main__":
    unittest.main()
