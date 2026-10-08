from __future__ import annotations

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.upstream.provider import UpstreamMediaProvider


class TagService:
    def __init__(self, provider: UpstreamMediaProvider) -> None:
        self.provider = provider

    async def suggest_tags(self, search_text: str) -> list[str]:
        cleaned = search_text.strip()
        if not cleaned or len(cleaned) > 100:
            raise ApplicationError(
                ErrorCategory.INVALID_REQUEST,
                "Tag query must be between 1 and 100 characters.",
            )
        return await self.provider.suggest_tags(cleaned)
