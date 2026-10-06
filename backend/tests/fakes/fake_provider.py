from collections.abc import Mapping
from enum import Enum

from pydantic import ValidationError

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import (
    Creator,
    InternalSourceTarget,
    MediaItem,
    SearchQuery,
    SearchResult,
)


class FakeProviderFault(str, Enum):
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    AUTH_EXPIRED = "auth_expired"
    MALFORMED_ITEM = "malformed_item"


class FakeMediaProvider:
    def __init__(
        self, faults: Mapping[str, FakeProviderFault] | None = None
    ) -> None:
        self._faults = dict(faults or {})
        self._media = MediaItem(
            id="sample-media",
            title="Sample media",
            creator=Creator(id="sample-creator", username="sample"),
            tags=["sample", "test"],
            width=640,
            height=360,
            duration=12.5,
            thumbnailUrl="https://images.example.invalid/sample.jpg",
        )
        self._creator = self._media.creator

    def _raise_configured_fault(self, operation: str) -> None:
        fault = self._faults.get(operation)
        if fault is FakeProviderFault.NOT_FOUND:
            raise ApplicationError(ErrorCategory.NOT_FOUND, "The requested item was not found.")
        if fault is FakeProviderFault.RATE_LIMITED:
            raise ApplicationError(
                ErrorCategory.RATE_LIMITED,
                "The provider rate limit was reached.",
                retry_after=30,
            )
        if fault is FakeProviderFault.AUTH_EXPIRED:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                "Provider authentication has expired.",
            )
        if fault is FakeProviderFault.MALFORMED_ITEM:
            MediaItem.model_validate({"title": "Malformed fake item"})

    async def authenticate(self) -> None:
        self._raise_configured_fault("authenticate")

    async def search(self, query: SearchQuery) -> SearchResult:
        self._raise_configured_fault("search")
        items = [self._media] if query.page == 1 else []
        return SearchResult(
            items=items,
            page=query.page,
            limit=query.limit,
            hasMore=False,
            total=len(items),
        )

    async def get_media(self, media_id: str) -> MediaItem:
        self._raise_configured_fault("get_media")
        if media_id != self._media.id:
            raise ApplicationError(ErrorCategory.NOT_FOUND, "The requested media was not found.")
        return self._media

    async def get_creator(self, username: str) -> Creator:
        self._raise_configured_fault("get_creator")
        if username != self._creator.username:
            raise ApplicationError(ErrorCategory.NOT_FOUND, "The requested creator was not found.")
        return self._creator

    async def suggest_tags(self, query: str) -> list[str]:
        self._raise_configured_fault("suggest_tags")
        prefix = query.casefold()
        return [tag for tag in self._media.tags if tag.casefold().startswith(prefix)]

    async def resolve_source(
        self, media_id: str, quality: str
    ) -> InternalSourceTarget:
        self._raise_configured_fault("resolve_source")
        if media_id != self._media.id:
            raise ApplicationError(ErrorCategory.NOT_FOUND, "The requested media was not found.")
        return InternalSourceTarget(
            url=f"https://cdn.example.invalid/media/{media_id}-{quality}.mp4",
            headers={"X-Fake-Provider": "test"},
        )
