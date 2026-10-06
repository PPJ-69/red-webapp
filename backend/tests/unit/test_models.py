import unittest

from pydantic import ValidationError

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.models import (
    Creator,
    ErrorEnvelope,
    MediaItem,
    MediaSource,
    SearchQuery,
    SearchResult,
)


class CanonicalModelTests(unittest.TestCase):
    def test_media_fields_are_nullable_and_use_camel_case_aliases(self) -> None:
        item = MediaItem(id="media-1", title="Sample")

        self.assertIsNone(item.description)
        self.assertIsNone(item.creator)
        self.assertEqual(item.tags, [])
        self.assertEqual(item.model_dump(by_alias=True)["thumbnailUrl"], None)

    def test_source_uses_playback_url_and_rejects_unknown_internal_fields(self) -> None:
        source = MediaSource(playbackUrl="/api/stream/media-1")

        self.assertEqual(source.model_dump(by_alias=True)["playbackUrl"], "/api/stream/media-1")
        with self.assertRaises(ValidationError):
            MediaSource(playbackUrl="/api/stream/media-1", sourceTarget={"url": "secret"})

    def test_media_item_supports_canonical_metadata(self) -> None:
        item = MediaItem(
            id="media-1",
            title="Sample",
            creator=Creator(id="creator-1", username="sample"),
            tags=["sample"],
            width=640,
            height=360,
            duration=12.5,
            thumbnailUrl="https://example.invalid/thumb.jpg",
            sources=[MediaSource(playbackUrl="/api/stream/media-1")],
        )

        self.assertEqual(item.model_dump(by_alias=True)["thumbnailUrl"], "https://example.invalid/thumb.jpg")
        self.assertEqual(item.sources[0].playback_url, "/api/stream/media-1")

    def test_search_contracts_validate_pagination(self) -> None:
        query = SearchQuery(query="cats", page=2, limit=50)
        result = SearchResult(items=[], page=query.page, limit=query.limit, hasMore=False)

        self.assertEqual(result.model_dump(by_alias=True)["hasMore"], False)
        with self.assertRaises(ValidationError):
            SearchQuery(limit=101)

    def test_error_envelope_serializes_correlation_and_retry_fields(self) -> None:
        envelope = ErrorEnvelope(
            category=ErrorCategory.RATE_LIMITED,
            message="Try again later.",
            correlationId="request-1",
            retryAfter=30,
        )

        self.assertEqual(
            envelope.model_dump(mode="json", by_alias=True),
            {
                "category": "rate_limited",
                "message": "Try again later.",
                "correlationId": "request-1",
                "retryAfter": 30,
            },
        )


if __name__ == "__main__":
    unittest.main()
