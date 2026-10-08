from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import Creator, InternalSourceTarget, MediaItem, SearchQuery, SearchResult

from .auth import AuthManager
from .mapper import normalize_creator, normalize_media_item, normalize_search_result
from .transport import UpstreamTransport


class RedgifsClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.redgifs.com/v2",
        transport: UpstreamTransport | None = None,
        auth_manager: AuthManager | None = None,
        fixtures: Mapping[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._fixtures = dict(fixtures or {})

        if auth_manager is None:
            async def token_factory() -> str:
                if self._fixtures:
                    return "fixture-token"
                value = os.getenv("REDGIFS_TOKEN") or os.getenv("REDGIFS_API_TOKEN")
                if value:
                    return value
                raise ApplicationError(
                    ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                    "RedGIFs token is not configured.",
                )

            auth_manager = AuthManager(token_factory, ttl_seconds=300.0)
        self.auth_manager = auth_manager
        self.transport = transport or UpstreamTransport(auth_manager=self.auth_manager)

    async def authenticate(self) -> None:
        await self.auth_manager.get_token()

    async def _request_json(self, method: str, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        if self._fixtures:
            key = f"{method.lower()}:{path}"
            fixture = self._fixtures.get(key)
            if fixture is not None:
                return fixture

        response = await self.transport.request(
            method,
            f"{self.base_url}{path}",
            params=params,
        )
        return response.json()

    async def search(self, query: SearchQuery) -> SearchResult:
        terms = []
        if query.query:
            terms.append(query.query)
        for tag in query.tags:
            terms.append(f"#{tag}")
        params: dict[str, Any] = {
            "q": " ".join(terms).strip(),
            "page": query.page,
            "limit": query.limit,
        }
        if query.mode:
            params["mode"] = query.mode
        if query.order:
            params["order"] = query.order
        payload = await self._request_json("GET", "/search", params=params)
        return normalize_search_result(payload, query=query)

    async def get_media(self, media_id: str) -> MediaItem:
        payload = await self._request_json("GET", f"/media/{media_id}")
        if isinstance(payload, Mapping):
            if payload.get("media") is not None and isinstance(payload["media"], Mapping):
                payload = payload["media"]
            return normalize_media_item(payload)
        raise ApplicationError(
            ErrorCategory.PROVIDER_ERROR,
            "RedGIFs media response was not a JSON object.",
        )

    async def get_creator(self, username: str) -> Creator:
        payload = await self._request_json("GET", f"/creators/{username}")
        if not isinstance(payload, Mapping):
            raise ApplicationError(
                ErrorCategory.PROVIDER_ERROR,
                "RedGIFs creator response was not a JSON object.",
            )
        creator = normalize_creator(payload.get("creator") or payload.get("user") or payload)
        if creator is None:
            raise ApplicationError(
                ErrorCategory.PROVIDER_ERROR,
                "RedGIFs did not return a usable creator payload.",
            )
        return creator

    async def suggest_tags(self, query: str) -> list[str]:
        payload = await self._request_json("GET", "/tags", params={"q": query})
        if isinstance(payload, Mapping):
            tags = payload.get("tags") or payload.get("items") or []
        else:
            tags = []
        if isinstance(tags, list):
            return [str(tag) for tag in tags if str(tag)]
        return []

    async def resolve_source(self, media_id: str, quality: str) -> InternalSourceTarget:
        item = await self.get_media(media_id)
        preferred = None
        quality_name = (quality or "auto").lower()
        for source in item.sources:
            if quality_name == "auto":
                preferred = source
                break
            rendered = source.playback_url.lower()
            if quality_name in rendered:
                preferred = source
                break
        if preferred is None and item.sources:
            preferred = item.sources[0]
        if preferred is None:
            raise ApplicationError(
                ErrorCategory.UNSUPPORTED_MEDIA,
                "RedGIFs did not expose a usable source for this media item.",
            )
        return InternalSourceTarget(url=preferred.playback_url, headers={})
