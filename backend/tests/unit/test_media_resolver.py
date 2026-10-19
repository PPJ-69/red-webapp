import unittest
from unittest.mock import patch

from fastapi import FastAPI
from starlette.requests import Request

from backend.app.config import AppEnvironment, Settings
from backend.app.dependencies import get_media_resolver
from backend.app.domain.models import InternalSourceTarget, MediaItem, MediaSource
from backend.app.observability.metrics import MetricsRegistry
from backend.app.services.media_resolver import MediaResolver
from backend.tests.fakes.fake_provider import FakeMediaProvider


class MediaResolverTests(unittest.IsolatedAsyncioTestCase):
    async def test_dependency_uses_configured_source_cache_ttl(self) -> None:
        app = FastAPI()
        app.state.settings = Settings(
            AppEnvironment.TEST,
            source_cache_ttl_seconds=45.5,
            enable_hls=True,
        )
        app.state.upstream_provider = FakeMediaProvider()
        request = Request({"type": "http", "app": app})

        resolver = get_media_resolver(request)

        self.assertEqual(resolver.cache.ttl_seconds, 45.5)
        self.assertEqual(resolver._resolution_cache.ttl_seconds, 45.5)
        self.assertTrue(resolver._enable_hls)

    async def test_resolve_returns_public_source_descriptor(self) -> None:
        resolver = MediaResolver(FakeMediaProvider())

        source = await resolver.resolve("sample-media", "auto")

        self.assertIsInstance(source, MediaSource)
        self.assertEqual(
            source.playback_url, "/api/stream/sample-media?quality=auto"
        )
        self.assertIn(source.kind, {"direct", "relay"})
        self.assertIsNotNone(source.expires_at)

    async def test_resolver_cache_reuses_descriptor_for_same_key(self) -> None:
        resolver = MediaResolver(FakeMediaProvider())

        first = await resolver.resolve("sample-media", "auto")
        second = await resolver.resolve("sample-media", "auto")

        self.assertEqual(first.playback_url, second.playback_url)
        self.assertEqual(first.kind, second.kind)

    async def test_source_resolution_cache_reuses_internal_target(self) -> None:
        class CountingProvider(FakeMediaProvider):
            get_media_calls = 0
            resolve_source_calls = 0

            async def get_media(self, media_id: str) -> MediaItem:
                self.get_media_calls += 1
                return await super().get_media(media_id)

            async def resolve_source(
                self, media_id: str, quality: str
            ) -> InternalSourceTarget:
                self.resolve_source_calls += 1
                return await super().resolve_source(media_id, quality)

        provider = CountingProvider()
        resolver = MediaResolver(provider)

        descriptor = await resolver.resolve("sample-media", "auto")
        resolution = await resolver.resolve_resolution("sample-media", "auto")

        self.assertEqual(descriptor, resolution.descriptor)
        self.assertEqual(provider.get_media_calls, 1)
        self.assertEqual(provider.resolve_source_calls, 1)

    async def test_invalidate_refreshes_cached_source_target(self) -> None:
        class RotatingProvider(FakeMediaProvider):
            resolve_source_calls = 0

            async def resolve_source(
                self, media_id: str, quality: str
            ) -> InternalSourceTarget:
                self.resolve_source_calls += 1
                target = await super().resolve_source(media_id, quality)
                return InternalSourceTarget(
                    url=f"{target.url}&generation={self.resolve_source_calls}",
                    headers=target.headers,
                )

        provider = RotatingProvider()
        resolver = MediaResolver(provider)
        first = await resolver.resolve_resolution("sample-media")

        resolver.invalidate("sample-media")
        second = await resolver.resolve_resolution("sample-media")

        self.assertNotEqual(first.target.url, second.target.url)
        self.assertEqual(provider.resolve_source_calls, 2)

    async def test_disabling_direct_media_routes_headerless_source_through_relay(self) -> None:
        class HeaderlessProvider(FakeMediaProvider):
            async def resolve_source(
                self, media_id: str, quality: str
            ) -> InternalSourceTarget:
                target = await super().resolve_source(media_id, quality)
                return InternalSourceTarget(url=target.url)

        with patch.dict("os.environ", {"ENABLE_DIRECT_MEDIA": "false"}):
            source = await MediaResolver(HeaderlessProvider()).resolve(
                "sample-media"
            )

        self.assertEqual(
            source.playback_url, "/api/stream/sample-media?quality=auto"
        )
        self.assertTrue(source.requires_relay)
        self.assertTrue(source.requires_relay)

    async def test_hls_is_opt_in_browser_gated_and_always_relayed(self) -> None:
        class FormatProvider(FakeMediaProvider):
            async def resolve_source(
                self,
                media_id: str,
                quality: str,
                *,
                prefer_hls: bool = False,
            ) -> InternalSourceTarget:
                if prefer_hls:
                    return InternalSourceTarget(
                        url="https://cdn.example.invalid/master.m3u8",
                        mime_type="application/vnd.apple.mpegurl",
                    )
                return InternalSourceTarget(
                    url="https://cdn.example.invalid/video.mp4",
                    mime_type="video/mp4",
                )

        resolver = MediaResolver(FormatProvider(), enable_hls=True)
        with patch.dict("os.environ", {"ENABLE_DIRECT_MEDIA": "true"}):
            hls = await resolver.resolve(
                "sample-media", supports_hls=True
            )
            mp4 = await resolver.resolve("sample-media", supports_hls=False)

        self.assertTrue(hls.requires_relay)
        self.assertEqual(
            hls.mime_type, "application/vnd.apple.mpegurl"
        )
        self.assertEqual(
            hls.playback_url,
            "/api/stream/sample-media?quality=auto&hls=1",
        )
        self.assertFalse(mp4.requires_relay)
        self.assertEqual(mp4.mime_type, "video/mp4")
    async def test_records_direct_and_relay_resolution_share(self) -> None:
        class HeaderlessProvider(FakeMediaProvider):
            async def resolve_source(
                self, media_id: str, quality: str
            ) -> InternalSourceTarget:
                target = await super().resolve_source(media_id, quality)
                return InternalSourceTarget(url=target.url)

        metrics = MetricsRegistry()
        with patch.dict("os.environ", {"ENABLE_DIRECT_MEDIA": "true"}):
            await MediaResolver(
                HeaderlessProvider(), metrics_registry=metrics
            ).resolve("sample-media")
            await MediaResolver(
                FakeMediaProvider(), metrics_registry=metrics
            ).resolve("sample-media")

        self.assertEqual(
            metrics.snapshot()["direct_vs_relay_ratio"]["value"], 0.5
        )


if __name__ == "__main__":
    unittest.main()
