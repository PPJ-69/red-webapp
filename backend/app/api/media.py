from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_media_resolver, get_upstream_provider
from backend.app.domain.models import MediaItem, MediaSource
from backend.app.services.media_resolver import MediaResolver
from backend.app.upstream.provider import UpstreamMediaProvider

router = APIRouter(tags=["media"])


@router.get("/api/media/{media_id}", response_model=MediaItem)
async def get_media(
    media_id: str,
    provider: UpstreamMediaProvider = Depends(get_upstream_provider),
) -> MediaItem:
    item = await provider.get_media(media_id)
    return item.model_copy(update={"sources": []})


@router.get("/api/media/{media_id}/source", response_model=MediaSource)
async def resolve_media_source(
    media_id: str,
    quality: str = Query(default="auto", pattern=r"^(auto|hd|sd)$"),
    resolver: MediaResolver = Depends(get_media_resolver),
) -> MediaSource:
    return await resolver.resolve(media_id, quality)
