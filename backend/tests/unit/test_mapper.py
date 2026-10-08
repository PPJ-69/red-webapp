import unittest

from backend.app.domain.models import SearchQuery
from backend.app.upstream.mapper import normalize_media_item, normalize_search_result


class MapperTests(unittest.TestCase):
    def test_normalize_media_item_from_redgifs_payload(self) -> None:
        payload = {
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

        item = normalize_media_item(payload)

        self.assertEqual(item.id, "sample-media")
        self.assertEqual(item.creator.username, "sample")
        self.assertEqual(item.tags, ["sample", "test"])
        self.assertEqual(item.sources[0].playback_url, "https://cdn.example.invalid/media/sample.mp4")

    def test_normalize_search_result_keeps_canonical_records(self) -> None:
        payload = {
            "items": [
                {
                    "id": "sample-media",
                    "title": "Sample media",
                    "creator": {"id": "sample", "username": "sample"},
                    "sources": [{"playbackUrl": "https://cdn.example.invalid/media/sample.mp4"}],
                }
            ],
            "page": 1,
            "limit": 20,
            "hasMore": False,
            "total": 1,
        }

        result = normalize_search_result(payload, query=SearchQuery())

        self.assertEqual(result.total, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].id, "sample-media")


if __name__ == "__main__":
    unittest.main()
