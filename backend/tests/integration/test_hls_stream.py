from __future__ import annotations

import re
import unittest
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.stream import router as stream_router
from backend.app.api.media import router as media_router
from backend.app.config import AppEnvironment, Settings
from backend.app.dependencies import get_media_resolver, get_stream_service
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget
from backend.app.observability.logging import install_request_context
from backend.app.observability.metrics import MetricsRegistry
from backend.app.services.media_resolver import MediaResolver
from backend.app.services.stream_service import StreamService
from backend.app.domain.errors import register_exception_handlers
from backend.tests.fakes.fake_provider import FakeMediaProvider


_MASTER = (
    b"#EXTM3U\n"
    b"#EXT-X-STREAM-INF:BANDWIDTH=1000000\n"
    b"variant.m3u8\n"
)
_VOD = (
    b"#EXTM3U\n"
    b"#EXT-X-PLAYLIST-TYPE:VOD\n"
    b"#EXT-X-MAP:URI=\"init.mp4\"\n"
    b"#EXTINF:2.0,\n"
    b"segment-1.m4s\n"
    b"#EXT-X-ENDLIST\n"
)
_INIT = b"initialization-data"
_SEGMENT = b"segment-data"


class _HlsProvider(FakeMediaProvider):
    async def resolve_source(
        self, media_id: str, quality: str, *, prefer_hls: bool = False
    ) -> InternalSourceTarget:
        if prefer_hls:
            return InternalSourceTarget(
                url="https://cdn.example.invalid/hls/master.m3u8",
                headers={"X-Fake-Provider": "test"},
                mime_type="application/vnd.apple.mpegurl",
            )
        return await super().resolve_source(media_id, quality)


class _HlsOnlyProvider(_HlsProvider):
    async def resolve_source(
        self, media_id: str, quality: str, *, prefer_hls: bool = False
    ) -> InternalSourceTarget:
        if not prefer_hls:
            raise ApplicationError(
                ErrorCategory.UNSUPPORTED_MEDIA,
                "No supported MP4 source is available.",
            )
        return await super().resolve_source(
            media_id, quality, prefer_hls=prefer_hls
        )


class _MemoryStream:
    def __init__(
        self, content: bytes, content_type: str, range_header: str | None
    ) -> None:
        self.status_code = 200
        self.body = content
        self._closed = False
        self.headers: dict[str, str] = {
            "content-type": content_type,
            "content-length": str(len(content)),
            "accept-ranges": "bytes",
        }
        if range_header:
            start_text, end_text = range_header.removeprefix("bytes=").split("-", 1)
            start = int(start_text or 0)
            end = min(int(end_text), len(content) - 1) if end_text else len(content) - 1
            self.body = content[start : end + 1]
            self.status_code = 206
            self.headers["content-length"] = str(len(self.body))
            self.headers["content-range"] = (
                f"bytes {start}-{end}/{len(content)}"
            )

    async def iter_chunks(self) -> AsyncIterator[bytes]:
        yield self.body

    async def read_error_body(self, limit: int = 4096) -> str:
        return self.body[:limit].decode("utf-8", errors="replace")

    async def aclose(self) -> None:
        self._closed = True


class _MemoryTransport:
    def __init__(self, *, master_playlist: bytes = _MASTER) -> None:
        self.requests: list[tuple[str, str | None]] = []
        self.master_playlist = master_playlist

    async def open(
        self,
        target: InternalSourceTarget,
        *,
        range_header: str | None = None,
    ) -> _MemoryStream:
        parsed = urlsplit(target.url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "cdn.example.invalid"
            or target.headers.get("X-Fake-Provider") != "test"
        ):
            raise AssertionError("The HLS relay opened an unvalidated target.")
        self.requests.append((target.url, range_header))
        content_by_path = {
            "/hls/master.m3u8": (
                self.master_playlist,
                "application/vnd.apple.mpegurl",
            ),
            "/hls/variant.m3u8": (_VOD, "application/vnd.apple.mpegurl"),
            "/hls/init.mp4": (_INIT, "video/mp4"),
            "/hls/segment-1.m4s": (_SEGMENT, "video/iso.segment"),
            "/media/sample-media-auto.mp4": (b"mp4-fallback", "video/mp4"),
        }
        content, content_type = content_by_path[parsed.path]
        return _MemoryStream(content, content_type, range_header)


def _test_app(service: StreamService) -> FastAPI:
    app = FastAPI()
    app.state.settings = Settings(AppEnvironment.TEST)
    app.state.metrics = MetricsRegistry()
    app.include_router(stream_router)
    app.include_router(media_router)
    app.dependency_overrides[get_stream_service] = lambda: service
    register_exception_handlers(app)
    install_request_context(app)
    return app


class HlsStreamIntegrationTests(unittest.TestCase):
    def test_vod_master_playlist_and_resources_are_relayed_by_opaque_tokens(self) -> None:
        provider = _HlsProvider()
        transport = _MemoryTransport()
        resolver = MediaResolver(provider, enable_hls=True)
        service = StreamService(resolver, transport)

        with TestClient(_test_app(service)) as client:
            master_response = client.get(
                "/api/stream/sample-media?quality=auto&hls=true"
            )
            self.assertEqual(master_response.status_code, 200)
            master = master_response.text
            self.assertNotIn("cdn.example.invalid", master)
            self.assertNotIn("Bearer", master)

            variant_path = next(
                line
                for line in master.splitlines()
                if line.startswith("/api/stream/")
            )
            variant_response = client.get(variant_path)
            self.assertEqual(variant_response.status_code, 200)
            self.assertNotIn("cdn.example.invalid", variant_response.text)

            map_match = re.search(
                r'URI="(/api/stream/[^"]+)"', variant_response.text
            )
            segment_path = next(
                line
                for line in variant_response.text.splitlines()
                if line.startswith("/api/stream/")
            )
            self.assertIsNotNone(map_match)
            map_path = map_match.group(1)
            map_response = client.get(map_path)
            segment_response = client.get(
                segment_path, headers={"Range": "bytes=1-3"}
            )

        self.assertEqual(map_response.content, _INIT)
        self.assertEqual(segment_response.status_code, 206)
        self.assertEqual(segment_response.content, _SEGMENT[1:4])
        self.assertIn(("https://cdn.example.invalid/hls/segment-1.m4s", "bytes=1-3"), transport.requests)
        self.assertIn(
            "application/vnd.apple.mpegurl",
            master_response.headers["content-type"],
        )

    def test_source_endpoint_selects_hls_only_when_browser_supports_it(self) -> None:
        resolver = MediaResolver(_HlsProvider(), enable_hls=True)
        service = StreamService(resolver, _MemoryTransport())
        app = _test_app(service)
        app.dependency_overrides[get_media_resolver] = lambda: resolver

        with TestClient(app) as client:
            hls_response = client.get(
                "/api/media/sample-media/source?supportsHls=true"
            )
            mp4_response = client.get(
                "/api/media/sample-media/source?supportsHls=false"
            )

        self.assertEqual(hls_response.status_code, 200)
        self.assertEqual(
            hls_response.json()["mimeType"],
            "application/vnd.apple.mpegurl",
        )
        self.assertIn("hls=1", hls_response.json()["playbackUrl"])
        self.assertEqual(mp4_response.status_code, 200)
        self.assertEqual(mp4_response.json()["mimeType"], "video/mp4")

    def test_unsupported_hls_playlist_falls_back_to_mp4_and_caches_selection(self) -> None:
        unsupported_playlist = (
            b"#EXTM3U\n"
            b"#EXT-X-KEY:METHOD=AES-128,URI=\"key.bin\"\n"
            b"#EXTINF:2.0,\n"
            b"segment.ts\n"
            b"#EXT-X-ENDLIST\n"
        )
        transport = _MemoryTransport(master_playlist=unsupported_playlist)
        resolver = MediaResolver(_HlsProvider(), enable_hls=True)
        service = StreamService(resolver, transport)
        app = _test_app(service)
        app.dependency_overrides[get_media_resolver] = lambda: resolver

        with TestClient(app) as client:
            response = client.get(
                "/api/stream/sample-media?quality=auto&hls=true"
            )
            repeated = client.get(
                "/api/stream/sample-media?quality=auto&hls=true"
            )
            source = client.get(
                "/api/media/sample-media/source?supportsHls=true"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"mp4-fallback")
        self.assertEqual(response.headers["content-type"], "video/mp4")
        self.assertEqual(repeated.content, b"mp4-fallback")
        self.assertEqual(source.json()["mimeType"], "video/mp4")
        self.assertEqual(
            [url for url, _ in transport.requests].count(
                "https://cdn.example.invalid/hls/master.m3u8"
            ),
            1,
        )

    def test_unsupported_hls_without_mp4_returns_stable_error(self) -> None:
        unsupported_playlist = (
            b"#EXTM3U\n"
            b"#EXT-X-KEY:METHOD=AES-128,URI=\"key.bin\"\n"
            b"#EXTINF:2.0,\n"
            b"segment.ts\n"
            b"#EXT-X-ENDLIST\n"
        )
        service = StreamService(
            MediaResolver(_HlsOnlyProvider(), enable_hls=True),
            _MemoryTransport(master_playlist=unsupported_playlist),
        )

        with TestClient(_test_app(service)) as client:
            response = client.get(
                "/api/stream/sample-media?quality=auto&hls=true"
            )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(
            response.json()["category"], ErrorCategory.UNSUPPORTED_MEDIA.value
        )

    def test_resource_token_is_bound_to_media_id_and_rejects_query_urls(self) -> None:
        transport = _MemoryTransport()
        service = StreamService(
            MediaResolver(_HlsProvider(), enable_hls=True), transport
        )
        with TestClient(_test_app(service)) as client:
            response = client.get(
                "/api/stream/sample-media?quality=auto&hls=true"
            )
            token = re.search(
                r"/hls/([A-Za-z0-9_-]+)", response.text
            ).group(1)
            unknown_media = client.get(
                f"/api/stream/other-media/hls/{token}"
            )
            arbitrary_url = client.get(
                f"/api/stream/sample-media/hls/{token}?url=https://evil.invalid"
            )

        self.assertEqual(unknown_media.status_code, 404)
        self.assertEqual(arbitrary_url.status_code, 400)


if __name__ == "__main__":
    unittest.main()
