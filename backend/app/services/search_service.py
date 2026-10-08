from __future__ import annotations

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import SearchQuery, SearchResult
from backend.app.upstream.provider import UpstreamMediaProvider

from .query_normalization import normalize_search_query


class SearchService:
    def __init__(self, provider: UpstreamMediaProvider) -> None:
        self.provider = provider

    async def search(
        self,
        *,
        query: str | SearchQuery | None = None,
        tags: list[str] | None = None,
        creator: str | None = None,
        mode: str | None = None,
        order: str | None = None,
        page: int | str | None = None,
        limit: int | str | None = None,
    ) -> SearchResult:
        normalized = normalize_search_query(
            query,
            tags=tags,
            creator=creator,
            mode=mode,
            order=order,
            page=page,
            limit=limit,
        )
        if normalized.page < 1:
            raise ApplicationError(
                ErrorCategory.INVALID_REQUEST,
                "Page must be a positive integer.",
            )
        if normalized.limit < 1 or normalized.limit > 100:
            raise ApplicationError(
                ErrorCategory.INVALID_REQUEST,
                "Limit must be between 1 and 100.",
            )
        return await self.provider.search(normalized)
