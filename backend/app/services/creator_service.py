from __future__ import annotations

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import Creator
from backend.app.upstream.provider import UpstreamMediaProvider


class CreatorService:
    def __init__(self, provider: UpstreamMediaProvider) -> None:
        self.provider = provider

    async def get_creator(self, username: str) -> Creator:
        cleaned = username.strip()
        if not cleaned or len(cleaned) > 100:
            raise ApplicationError(
                ErrorCategory.INVALID_REQUEST,
                "Username must be between 1 and 100 characters.",
            )
        return await self.provider.get_creator(cleaned)
