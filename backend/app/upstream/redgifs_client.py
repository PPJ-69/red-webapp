from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit

import httpx2 as httpx
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import (
    Creator,
    InternalSourceTarget,
    MediaItem,
    MediaSource,
    SearchQuery,
    SearchResult,
)

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
        self._auth_client: httpx.AsyncClient | None = None

        if auth_manager is None:
            async def token_factory() -> str:
                if self._fixtures:
                    return "fixture-token"
                if self._auth_client is None:
                    self._auth_client = httpx.AsyncClient(
                        timeout=httpx.Timeout(10.0, connect=5.0)
                    )
                try:
                    response = await self._auth_client.get(
                        f"{self.base_url}/auth/temporary"
                    )
                    response.raise_for_status()
                    payload = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    raise ApplicationError(
                        ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                        "RedGIFs temporary authentication failed.",
                    ) from exc
                token = payload.get("token") if isinstance(payload, Mapping) else None
                if not isinstance(token, str) or not token.strip():
                    raise ApplicationError(
                        ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                        "RedGIFs did not return a usable temporary token.",
                    )
                return token

            auth_manager = AuthManager(token_factory, ttl_seconds=300.0)
        self.auth_manager = auth_manager
        self.transport = transport or UpstreamTransport(auth_manager=self.auth_manager)

    async def aclose(self) -> None:
        try:
            await self.transport.aclose()
        finally:
            if self._auth_client is not None:
                await self._auth_client.aclose()

    async def authenticate(self) -> None:
        await self.auth_manager.get_token()

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
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
        creator = _creator_from_query(query.query)
        params: dict[str, Any] = {"page": query.page, "count": query.limit}
        order = _redgifs_order(query.order)
        if order:
            params["order"] = order

        if creator is not None:
            path = f"/users/{quote(creator, safe='')}/search"
        elif (
            query.mode == "trending"
            or not query.query and not query.tags
        ):
            path = "/feeds/trending/popular"
        else:
            path = "/gifs/search"
            terms = [query.query] if query.query else []
            terms.extend(query.tags)
            params["search_text"] = " ".join(terms)
            params["type"] = "g"

        payload = await self._request_json("GET", path, params=params)
        return normalize_search_result(payload, query=query)

    async def get_media(self, media_id: str) -> MediaItem:
        payload = await self._request_json(
            "GET", f"/gifs/{quote(media_id, safe='')}"
        )
        if isinstance(payload, Mapping):
            if payload.get("gif") is not None and isinstance(
                payload["gif"], Mapping
            ):
                payload = payload["gif"]
            return normalize_media_item(payload)
        raise ApplicationError(
            ErrorCategory.PROVIDER_ERROR,
            "RedGIFs media response was not a JSON object.",
        )

    async def get_creator(self, username: str) -> Creator:
        payload = await self._request_json(
            "GET", f"/users/{quote(username, safe='')}"
        )
        if not isinstance(payload, Mapping):
            raise ApplicationError(
                ErrorCategory.PROVIDER_ERROR,
                "RedGIFs creator response was not a JSON object.",
            )
        creator = normalize_creator(
            payload.get("creator") or payload.get("user") or payload
        )
        if creator is None:
            raise ApplicationError(
                ErrorCategory.PROVIDER_ERROR,
                "RedGIFs did not return a usable creator payload.",
            )
        return creator

    async def suggest_tags(self, query: str) -> list[str]:
        payload = await self._request_json(
            "GET", "/search/tags", params={"query": query}
        )
        if isinstance(payload, Mapping):
            tags = payload.get("tags") or payload.get("items") or []
        else:
            tags = []
        if isinstance(tags, list):
            suggestions: list[str] = []
            for tag in tags:
                value = (
                    tag.get("name") or tag.get("tag")
                    if isinstance(tag, Mapping)
                    else tag
                )
                if value:
                    suggestions.append(str(value))
            return suggestions
        return []

    async def resolve_source(
        self, media_id: str, quality: str, *, prefer_hls: bool = False
    ) -> InternalSourceTarget:
        item = await self.get_media(media_id)
        hls_sources = [source for source in item.sources if _is_hls_source(source)]
        mp4_sources = [source for source in item.sources if _is_mp4_source(source)]
        candidates = hls_sources if prefer_hls and hls_sources else mp4_sources
        quality_name = (quality or "auto").lower()
        preferred = next(
            (
                source
                for source in candidates
                if quality_name == "auto"
                or quality_name in source.playback_url.lower()
            ),
            candidates[0] if candidates else None,
        )
        if preferred is None:
            raise ApplicationError(
                ErrorCategory.UNSUPPORTED_MEDIA,
                "RedGIFs did not expose a supported MP4 or HLS VOD source.",
            )
        return InternalSourceTarget(
            url=preferred.playback_url,
            headers={},
            mime_type=_source_mime_type(preferred),
        )


def _creator_from_query(query: str | None) -> str | None:
    if query is None:
        return None
    value = query.strip()
    if value.startswith("@") and len(value) > 1 and not any(
        character.isspace() for character in value
    ):
        return value[1:]
    return None


def _redgifs_order(order: str | None) -> str | None:
    if order is None:
        return None
    return {
        "latest": "new",
        "score": "top",
    }.get(order.lower(), order.lower())


def _source_mime_type(source: MediaSource) -> str | None:
    if source.mime_type:
        return source.mime_type.split(";", 1)[0].strip().lower()
    path = urlsplit(source.playback_url).path.lower()
    if path.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if path.endswith(".mp4"):
        return "video/mp4"
    return None


def _is_hls_source(source: MediaSource) -> bool:
    return _source_mime_type(source) in {
        "application/vnd.apple.mpegurl",
        "application/x-mpegurl",
        "audio/mpegurl",
        "audio/x-mpegurl",
    }


def _is_mp4_source(source: MediaSource) -> bool:
    return _source_mime_type(source) == "video/mp4"
