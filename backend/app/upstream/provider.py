from typing import Protocol

from ..domain.models import (
    Creator,
    InternalSourceTarget,
    MediaItem,
    SearchQuery,
    SearchResult,
    SourceResolution,
)


class UpstreamMediaProvider(Protocol):
    async def authenticate(self) -> None: ...

    async def search(self, query: SearchQuery) -> SearchResult: ...

    async def get_media(self, media_id: str) -> MediaItem: ...

    async def get_creator(self, username: str) -> Creator: ...

    async def suggest_tags(self, query: str) -> list[str]: ...

    async def resolve_source(
        self, media_id: str, quality: str
    ) -> InternalSourceTarget: ...


class MediaResolver(Protocol):
    async def resolve(self, media_id: str, quality: str) -> SourceResolution: ...
