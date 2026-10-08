from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget, MediaSource, SourceResolution
from backend.app.upstream.provider import UpstreamMediaProvider

from .source_cache import SourceCache


class MediaResolver:
    def __init__(self, provider: UpstreamMediaProvider, ttl_seconds: float = 300.0) -> None:
        self.provider = provider
        self.cache = SourceCache[MediaSource](ttl_seconds=ttl_seconds)

    def _classify(self, target: InternalSourceTarget) -> tuple[str, bool]:
        direct_enabled = os.getenv("ENABLE_DIRECT_MEDIA", "true").lower() not in {"0", "false", "no"}
        if target.headers and not direct_enabled:
            return "relay", True
        if target.headers:
            return "relay", True
        return "direct", False

    async def resolve(self, media_id: str, quality: str = "auto") -> MediaSource:
        if not media_id or not media_id.strip():
            raise ApplicationError(
                ErrorCategory.INVALID_MEDIA_ID,
                "A media ID is required.",
            )

        key = (media_id.strip(), (quality or "auto").lower())
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        await self.provider.get_media(media_id)
        target = await self.provider.resolve_source(media_id, quality)
        kind, requires_relay = self._classify(target)
        descriptor = MediaSource(
            playbackUrl=target.url,
            mimeType="video/mp4",
            kind=kind,
            requiresRelay=requires_relay,
            expiresAt=datetime.now(timezone.utc) + timedelta(seconds=self.cache.ttl_seconds),
        )
        self.cache.set(key, descriptor)
        return descriptor

    async def resolve_resolution(self, media_id: str, quality: str = "auto") -> SourceResolution:
        await self.provider.get_media(media_id)
        target = await self.provider.resolve_source(media_id, quality)
        descriptor = MediaSource(
            playbackUrl=target.url,
            mimeType="video/mp4",
            kind="relay" if target.headers else "direct",
            requiresRelay=bool(target.headers),
            expiresAt=datetime.now(timezone.utc) + timedelta(seconds=self.cache.ttl_seconds),
        )
        return SourceResolution(descriptor=descriptor, target=target)
