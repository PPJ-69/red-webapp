from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode, urlsplit

from backend.app.config import DEFAULT_SOURCE_CACHE_TTL_SECONDS
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget, MediaSource, SourceResolution
from backend.app.observability.metrics import MetricsRegistry, metrics
from backend.app.upstream.provider import UpstreamMediaProvider

from .source_cache import SourceCache


class MediaResolver:
    def __init__(
        self,
        provider: UpstreamMediaProvider,
        ttl_seconds: float = DEFAULT_SOURCE_CACHE_TTL_SECONDS,
        metrics_registry: MetricsRegistry | None = None,
        enable_hls: bool = False,
    ) -> None:
        self.provider = provider
        self._metrics = metrics_registry if metrics_registry is not None else metrics
        self._enable_hls = enable_hls
        self.cache = SourceCache[MediaSource](ttl_seconds=ttl_seconds)
        self._resolution_cache = SourceCache[SourceResolution](
            ttl_seconds=ttl_seconds
        )

    def _classify(self, target: InternalSourceTarget) -> tuple[str, bool]:
        direct_enabled = os.getenv("ENABLE_DIRECT_MEDIA", "true").lower() not in {"0", "false", "no"}
        if (
            _is_hls_target(target)
            or not direct_enabled
            or target.headers
        ):
            return "relay", True
        return "direct", False

    async def resolve(
        self,
        media_id: str,
        quality: str = "auto",
        supports_hls: bool = False,
    ) -> MediaSource:
        prefer_hls = self._enable_hls and supports_hls
        key = (media_id.strip(), (quality or "auto").lower(), prefer_hls)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        return (
            await self.resolve_resolution(media_id, quality, supports_hls)
        ).descriptor

    async def resolve_resolution(
        self,
        media_id: str,
        quality: str = "auto",
        supports_hls: bool = False,
    ) -> SourceResolution:
        if not media_id or not media_id.strip():
            raise ApplicationError(
                ErrorCategory.INVALID_MEDIA_ID,
                "A media ID is required.",
            )

        prefer_hls = self._enable_hls and supports_hls
        key = (media_id.strip(), (quality or "auto").lower(), prefer_hls)
        cached = self._resolution_cache.get(key)
        if cached is not None:
            return cached

        await self.provider.get_media(media_id)
        if prefer_hls:
            target = await self.provider.resolve_source(
                media_id, quality, prefer_hls=True
            )
        else:
            target = await self.provider.resolve_source(media_id, quality)
        kind, requires_relay = self._classify(target)
        self._metrics.record_source_resolution(kind)
        relay_params = {"quality": quality}
        if _is_hls_target(target):
            relay_params["hls"] = "1"
        relay_path = (
            f"/api/stream/{quote(media_id, safe='')}?"
            f"{urlencode(relay_params)}"
        )
        descriptor = MediaSource(
            playbackUrl=relay_path if requires_relay else target.url,
            mimeType=target.mime_type or "video/mp4",
            kind=kind,
            requiresRelay=requires_relay,
            expiresAt=datetime.now(timezone.utc) + timedelta(seconds=self.cache.ttl_seconds),
        )
        resolution = SourceResolution(descriptor=descriptor, target=target)
        self.cache.set(key, descriptor)
        self._resolution_cache.set(key, resolution)
        return resolution

    def invalidate(self, media_id: str, quality: str = "auto") -> None:
        normalized = (media_id.strip(), (quality or "auto").lower())
        for prefer_hls in (False, True):
            key = (*normalized, prefer_hls)
            self.cache.delete(key)
            self._resolution_cache.delete(key)

    def cache_mp4_fallback(
        self, media_id: str, quality: str, resolution: SourceResolution
    ) -> None:
        key = (media_id.strip(), (quality or "auto").lower(), True)
        self.cache.set(key, resolution.descriptor)
        self._resolution_cache.set(key, resolution)


def _is_hls_target(target: InternalSourceTarget) -> bool:
    mime_type = (target.mime_type or "").split(";", 1)[0].strip().lower()
    path = urlsplit(target.url).path.lower()
    return mime_type in {
        "application/vnd.apple.mpegurl",
        "application/x-mpegurl",
        "audio/mpegurl",
        "audio/x-mpegurl",
    } or path.endswith(".m3u8")
