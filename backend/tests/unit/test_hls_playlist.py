import unittest
import re
import time
from urllib.parse import urlsplit

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget
from backend.app.services.hls_playlist import rewrite_vod_playlist
from backend.app.services.hls_resources import HlsResourceRegistry


class HlsPlaylistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = HlsResourceRegistry(ttl_seconds=60)

    def test_rewrites_master_variant_without_exposing_upstream_url(self) -> None:
        output = rewrite_vod_playlist(
            (
                "#EXTM3U\n"
                "#EXT-X-STREAM-INF:BANDWIDTH=1000000\n"
                "variant/index.m3u8\n"
            ).encode(),
            media_id="sample-media",
            base_url="https://cdn.example.invalid/hls/master.m3u8",
            headers={"Authorization": "Bearer secret"},
            registry=self.registry,
        ).decode()

        self.assertNotIn("cdn.example.invalid", output)
        self.assertNotIn("Bearer secret", output)
        resource_path = output.splitlines()[-1]
        token = urlsplit(resource_path).path.rsplit("/", 1)[-1]
        resource = self.registry.resolve("sample-media", token)
        self.assertTrue(resource.is_playlist)
        self.assertEqual(
            resource.target.url,
            "https://cdn.example.invalid/hls/variant/index.m3u8",
        )
        self.assertEqual(
            resource.target.headers, {"Authorization": "Bearer secret"}
        )

    def test_rewrites_vod_segments_and_initialization_map(self) -> None:
        output = rewrite_vod_playlist(
            (
                "#EXTM3U\n"
                "#EXT-X-PLAYLIST-TYPE:VOD\n"
                "#EXT-X-MAP:URI=\"init.mp4\"\n"
                "#EXTINF:4.0,\n"
                "segment-1.m4s\n"
                "#EXT-X-ENDLIST\n"
            ).encode(),
            media_id="sample-media",
            base_url="https://cdn.example.invalid/hls/video.m3u8",
            headers={},
            registry=self.registry,
        ).decode()

        tokens = re.findall(r"/api/stream/[^/]+/hls/([A-Za-z0-9_-]+)", output)
        self.assertEqual(len(tokens), 2)
        map_token, segment_token = tokens
        self.assertFalse(
            self.registry.resolve("sample-media", map_token).is_playlist
        )
        self.assertFalse(
            self.registry.resolve("sample-media", segment_token).is_playlist
        )
        self.assertEqual(
            self.registry.resolve("sample-media", map_token).target.url,
            "https://cdn.example.invalid/hls/init.mp4",
        )

    def test_does_not_forward_privileged_headers_to_other_origins(self) -> None:
        output = rewrite_vod_playlist(
            (
                "#EXTM3U\n"
                "#EXTINF:4.0,\n"
                "https://media.example.invalid/segment.m4s\n"
                "#EXT-X-ENDLIST\n"
            ).encode(),
            media_id="sample-media",
            base_url="https://cdn.example.invalid/hls/video.m3u8",
            headers={"Authorization": "Bearer secret"},
            registry=self.registry,
        )
        token = output.decode().splitlines()[2].rsplit("/", 1)[-1]
        self.assertEqual(
            self.registry.resolve("sample-media", token).target.headers, {}
        )

    def test_rejects_live_encrypted_low_latency_and_unknown_uri_features(self) -> None:
        playlists = (
            "#EXTM3U\n#EXTINF:4,\nsegment.m4s\n",
            "#EXTM3U\n#EXT-X-PLAYLIST-TYPE:EVENT\n",
            "#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"key.bin\"\n",
            "#EXTM3U\n#EXT-X-PART:DURATION=1,URI=\"part.m4s\"\n",
            "#EXTM3U\n#EXT-X-I-FRAME-STREAM-INF:URI=\"iframe.m3u8\"\n",
            "#EXTM3U\n#EXT-X-DATERANGE:URI=\"outside\"\n",
        )
        for playlist in playlists:
            with self.subTest(playlist=playlist), self.assertRaises(
                ApplicationError
            ) as raised:
                rewrite_vod_playlist(
                    playlist.encode(),
                    media_id="sample-media",
                    base_url="https://cdn.example.invalid/hls/video.m3u8",
                    headers={},
                    registry=self.registry,
                )
            self.assertEqual(
                raised.exception.category, ErrorCategory.UNSUPPORTED_MEDIA
            )

    def test_rejects_unsafe_resource_urls_and_wrong_media_token(self) -> None:
        with self.assertRaises(ApplicationError):
            rewrite_vod_playlist(
                (
                    "#EXTM3U\n#EXTINF:4,\njavascript:alert(1)\n"
                    "#EXT-X-ENDLIST\n"
                ).encode(),
                media_id="sample-media",
                base_url="https://cdn.example.invalid/hls/video.m3u8",
                headers={},
                registry=self.registry,
            )

        token = self.registry.register(
            "sample-media",
            InternalSourceTarget("https://cdn.example.invalid/segment.m4s"),
            is_playlist=False,
            depth=1,
        )
        with self.assertRaises(ApplicationError) as raised:
            self.registry.resolve("another-media", token)
        self.assertEqual(raised.exception.category, ErrorCategory.NOT_FOUND)

    def test_resource_tokens_expire(self) -> None:
        registry = HlsResourceRegistry(ttl_seconds=0.001)
        token = registry.register(
            "sample-media",
            InternalSourceTarget("https://cdn.example.invalid/segment.m4s"),
            is_playlist=False,
            depth=1,
        )
        time.sleep(0.01)

        with self.assertRaises(ApplicationError) as raised:
            registry.resolve("sample-media", token)
        self.assertEqual(raised.exception.category, ErrorCategory.NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
