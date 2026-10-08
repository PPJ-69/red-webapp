from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.dependencies import get_upstream_provider
from backend.app.domain.models import Creator
from backend.app.services.creator_service import CreatorService
from backend.app.upstream.provider import UpstreamMediaProvider

router = APIRouter(tags=["creators"])


@router.get("/api/creator/{username}", response_model=Creator)
async def get_creator(
    username: str,
    provider: UpstreamMediaProvider = Depends(get_upstream_provider),
) -> Creator:
    service = CreatorService(provider)
    return await service.get_creator(username)
