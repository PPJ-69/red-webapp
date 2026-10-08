from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_media_resolver
from backend.app.domain.models import MediaSource
from backend.app.services.media_resolver import MediaResolver

router = APIRouter(tags=["media"])


@router.get("/api/media/{media_id}/source", response_model=MediaSource)
async def resolve_media_source(
    media_id: str,
    quality: str = Query(default="auto", pattern=r"^(auto|hd|sd)$"),
    resolver: MediaResolver = Depends(get_media_resolver),
) -> MediaSource:
    return await resolver.resolve(media_id, quality)
