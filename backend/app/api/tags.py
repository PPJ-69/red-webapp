from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_upstream_provider
from backend.app.services.tag_service import TagService
from backend.app.upstream.provider import UpstreamMediaProvider

router = APIRouter(tags=["tags"])


@router.get("/api/tags/suggest")
async def suggest_tags(
    q: str = Query(default="", min_length=1, max_length=100),
    provider: UpstreamMediaProvider = Depends(get_upstream_provider),
) -> list[str]:
    service = TagService(provider)
    return await service.suggest_tags(q)
