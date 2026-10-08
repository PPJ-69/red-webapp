from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget, MediaSource, SourceResolution
from backend.app.upstream.provider import UpstreamMediaProvider

from .source_cache import SourceCache


class MediaResolver:
    def __init__(self, provider: UpstreamMediaProvider, ttl_seconds: float = 300.0) -> None:
        self.provider = provider
        self.cache = SourceCache[MediaSource](ttl_seconds=ttl_seconds)
        self._resolution_cache = SourceCache[SourceResolution](
            ttl_seconds=ttl_seconds
        )

    def _classify(self, target: InternalSourceTarget) -> tuple[str, bool]:
        direct_enabled = os.getenv("ENABLE_DIRECT_MEDIA", "true").lower() not in {"0", "false", "no"}
        if not direct_enabled or target.headers:
            return "relay", True
        return "direct", False

    async def resolve(self, media_id: str, quality: str = "auto") -> MediaSource:
        key = (media_id.strip(), (quality or "auto").lower())
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        return (await self.resolve_resolution(media_id, quality)).descriptor

    async def resolve_resolution(self, media_id: str, quality: str = "auto") -> SourceResolution:
        if not media_id or not media_id.strip():
            raise ApplicationError(
                ErrorCategory.INVALID_MEDIA_ID,
                "A media ID is required.",
            )

        key = (media_id.strip(), (quality or "auto").lower())
        cached = self._resolution_cache.get(key)
        if cached is not None:
            return cached

        await self.provider.get_media(media_id)
        target = await self.provider.resolve_source(media_id, quality)
        kind, requires_relay = self._classify(target)
        relay_path = f"/api/stream/{quote(media_id, safe='')}?{urlencode({'quality': quality})}"
        descriptor = MediaSource(
            playbackUrl=relay_path if requires_relay else target.url,
            mimeType="video/mp4",
            kind=kind,
            requiresRelay=requires_relay,
            expiresAt=datetime.now(timezone.utc) + timedelta(seconds=self.cache.ttl_seconds),
        )
        resolution = SourceResolution(descriptor=descriptor, target=target)
        self.cache.set(key, descriptor)
        self._resolution_cache.set(key, resolution)
        return resolution

    def invalidate(self, media_id: str, quality: str = "auto") -> None:
        key = (media_id.strip(), (quality or "auto").lower())
        self.cache.delete(key)
        self._resolution_cache.delete(key)
