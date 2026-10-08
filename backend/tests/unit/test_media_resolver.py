import unittest

from backend.app.domain.models import MediaSource
from backend.app.services.media_resolver import MediaResolver
from backend.tests.fakes.fake_provider import FakeMediaProvider


class MediaResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_returns_public_source_descriptor(self) -> None:
        resolver = MediaResolver(FakeMediaProvider())

        source = await resolver.resolve("sample-media", "auto")

        self.assertIsInstance(source, MediaSource)
        self.assertTrue(source.playback_url.startswith("https://"))
        self.assertIn(source.kind, {"direct", "relay"})
        self.assertIsNotNone(source.expires_at)

    async def test_resolver_cache_reuses_descriptor_for_same_key(self) -> None:
        resolver = MediaResolver(FakeMediaProvider())

        first = await resolver.resolve("sample-media", "auto")
        second = await resolver.resolve("sample-media", "auto")

        self.assertEqual(first.playback_url, second.playback_url)
        self.assertEqual(first.kind, second.kind)


if __name__ == "__main__":
    unittest.main()
