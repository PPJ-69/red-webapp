import unittest

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.upstream.redgifs_client import RedgifsClient


def _provider(sources: list[dict[str, str]]) -> RedgifsClient:
    return RedgifsClient(
        fixtures={
            "get:/media/sample-media": {
                "id": "sample-media",
                "title": "Sample media",
                "sources": sources,
            }
        }
    )


class HlsSourceSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_mp4_is_selected_when_hls_is_not_preferred(self) -> None:
        provider = _provider(
            [
                {
                    "playbackUrl": "https://cdn.example.invalid/master.m3u8",
                    "mimeType": "application/vnd.apple.mpegurl",
                },
                {
                    "playbackUrl": "https://cdn.example.invalid/video-hd.mp4",
                    "mimeType": "video/mp4",
                },
            ]
        )

        target = await provider.resolve_source("sample-media", "auto")

        self.assertEqual(target.url, "https://cdn.example.invalid/video-hd.mp4")
        self.assertEqual(target.mime_type, "video/mp4")

    async def test_hls_is_selected_only_when_preferred(self) -> None:
        provider = _provider(
            [
                {
                    "playbackUrl": "https://cdn.example.invalid/video.mp4",
                    "mimeType": "video/mp4",
                },
                {
                    "playbackUrl": "https://cdn.example.invalid/master.m3u8",
                    "mimeType": "application/vnd.apple.mpegurl",
                },
            ]
        )

        target = await provider.resolve_source(
            "sample-media", "auto", prefer_hls=True
        )

        self.assertEqual(target.url, "https://cdn.example.invalid/master.m3u8")
        self.assertEqual(
            target.mime_type, "application/vnd.apple.mpegurl"
        )

    async def test_preferred_hls_falls_back_to_mp4_when_unavailable(self) -> None:
        provider = _provider(
            [
                {
                    "playbackUrl": "https://cdn.example.invalid/video.mp4",
                    "mimeType": "video/mp4",
                }
            ]
        )

        target = await provider.resolve_source(
            "sample-media", "auto", prefer_hls=True
        )

        self.assertEqual(target.mime_type, "video/mp4")

    async def test_hls_only_source_is_unsupported_when_not_preferred(self) -> None:
        provider = _provider(
            [
                {
                    "playbackUrl": "https://cdn.example.invalid/master.m3u8",
                    "mimeType": "application/vnd.apple.mpegurl",
                }
            ]
        )

        with self.assertRaises(ApplicationError) as raised:
            await provider.resolve_source("sample-media", "auto")

        self.assertEqual(
            raised.exception.category, ErrorCategory.UNSUPPORTED_MEDIA
        )


if __name__ == "__main__":
    unittest.main()
