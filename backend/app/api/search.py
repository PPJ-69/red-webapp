from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_upstream_provider
from backend.app.domain.models import SearchResult
from backend.app.services.search_service import SearchService
from backend.app.upstream.provider import UpstreamMediaProvider

router = APIRouter(tags=["search"])


@router.get("/api/search", response_model=SearchResult)
async def search(
    q: str | None = Query(default=None, alias="q"),
    tags: list[str] | None = Query(default=None),
    creator: str | None = Query(default=None),
    mode: str | None = Query(default="search"),
    order: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    provider: UpstreamMediaProvider = Depends(get_upstream_provider),
) -> SearchResult:
    service = SearchService(provider)
    return await service.search(
        query=q,
        tags=tags,
        creator=creator,
        mode=mode,
        order=order,
        page=page,
        limit=limit,
    )
