from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.app.domain.models import (
    Creator,
    MediaItem,
    MediaSource,
    SearchQuery,
    SearchResult,
)


def _coerce_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(value: Any, *keys: str) -> Any:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                return value[key]
    return None


def normalize_creator(payload: Mapping[str, Any] | None) -> Creator | None:
    if not payload:
        return None
    creator_id = _coerce_str(_first(payload, "id", "userId", "user_id"), "")
    username = _coerce_str(_first(payload, "username", "name", "user_name"), "")
    if not creator_id and not username:
        return None
    if not creator_id:
        creator_id = username
    if not username:
        username = creator_id
    return Creator(
        id=creator_id,
        username=username,
        display_name=_coerce_str(_first(payload, "displayName", "display_name"), "") or None,
        profile_image_url=_coerce_str(
            _first(payload, "profileImageUrl", "profile_image_url"),
            "",
        )
        or None,
    )


def _source_candidates(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources = payload.get("sources")
    if isinstance(sources, Sequence) and not isinstance(sources, (str, bytes)):
        return [source for source in sources if isinstance(source, Mapping)]
    raw_url = _coerce_str(_first(payload, "url", "playbackUrl", "playback_url"), "")
    if raw_url:
        return [{"playbackUrl": raw_url}]
    return []


def normalize_media_item(payload: Mapping[str, Any]) -> MediaItem:
    media_id = _coerce_str(_first(payload, "id", "mediaId", "media_id"), "")
    title = _coerce_str(_first(payload, "title", "name"), "")
    if not media_id or not title:
        raise ValueError("Media payload does not include a usable id/title.")

    creator_payload = payload.get("creator") or payload.get("user") or {}
    creator = normalize_creator(creator_payload if isinstance(creator_payload, Mapping) else None)

    tags: list[str] = []
    raw_tags = payload.get("tags") or []
    if isinstance(raw_tags, Sequence) and not isinstance(raw_tags, (str, bytes)):
        tags = [str(tag) for tag in raw_tags if str(tag)]
    elif isinstance(raw_tags, str):
        tags = [segment.strip() for segment in raw_tags.split(",") if segment.strip()]

    width = _coerce_int(_first(payload, "width", "frameWidth", "frame_width"))
    height = _coerce_int(_first(payload, "height", "frameHeight", "frame_height"))
    duration = _coerce_float(_first(payload, "duration", "length"))

    thumbnail_url = _coerce_str(
        _first(payload, "thumbnailUrl", "thumbnail_url", "posterUrl", "poster_url"),
        "",
    ) or None
    poster_url = _coerce_str(_first(payload, "posterUrl", "poster_url"), "") or None

    sources: list[MediaSource] = []
    for candidate in _source_candidates(payload):
        playback_url = _coerce_str(
            _first(candidate, "playbackUrl", "playback_url", "url"),
            "",
        )
        if not playback_url:
            continue
        mime_type = _coerce_str(_first(candidate, "mimeType", "mime_type"), "") or None
        sources.append(MediaSource(playbackUrl=playback_url, mimeType=mime_type))

    return MediaItem(
        id=media_id,
        title=title,
        description=_coerce_str(_first(payload, "description"), "") or None,
        creator=creator,
        tags=tags,
        width=width,
        height=height,
        duration=duration,
        thumbnail_url=thumbnail_url,
        poster_url=poster_url,
        sources=sources,
    )


def normalize_search_result(payload: Mapping[str, Any], *, query: SearchQuery | None = None) -> SearchResult:
    items_payload = payload.get("items") or payload.get("gifs") or payload.get("media") or []
    if not isinstance(items_payload, Sequence) or isinstance(items_payload, (str, bytes)):
        items_payload = []

    items = []
    for item_payload in items_payload:
        if isinstance(item_payload, Mapping):
            try:
                items.append(normalize_media_item(item_payload))
            except ValueError:
                continue

    page = _coerce_int(_first(payload, "page", "currentPage", "current_page")) or (query.page if query else 1)
    limit = _coerce_int(_first(payload, "limit", "pageSize", "per_page")) or (query.limit if query else 20)
    has_more = bool(_first(payload, "hasMore", "has_more"))
    total = _coerce_int(_first(payload, "total", "count"))
    return SearchResult(
        items=items,
        page=max(1, page),
        limit=max(1, min(100, limit)),
        hasMore=has_more,
        total=total,
    )
