from __future__ import annotations

from collections.abc import Sequence

from backend.app.domain.models import SearchQuery


def _coerce_int(value: object, default: int) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_token(value: str) -> str:
    return value.strip().strip("\"'`[](){}<>,;: ")


def _tag_name(value: str) -> str:
    candidate = _clean_token(value).lstrip("#")
    return candidate.strip()


def _creator_name(value: str) -> str:
    candidate = _clean_token(value)
    if not candidate:
        return ""
    lowered = candidate.lower()
    if lowered.startswith("@"):
        return _clean_token(candidate[1:])
    if lowered.startswith("user:"):
        return _clean_token(candidate[5:])
    if lowered.startswith("creator:"):
        return _clean_token(candidate[8:])
    return candidate


def parse_search_tokens(
    raw_query: str | None = None,
    *,
    extra_tags: Sequence[str] | None = None,
    creator: str | None = None,
) -> tuple[str, list[str], list[str]]:
    text_parts: list[str] = []
    tags: list[str] = []
    creators: list[str] = []

    if raw_query:
        pieces = [part for item in raw_query.split() for part in item.split(",")]
        for piece in pieces:
            token = _clean_token(piece)
            if not token:
                continue
            lowered = token.lower()
            if token.startswith("#"):
                tag = _tag_name(token)
                if tag and tag not in tags:
                    tags.append(tag)
                continue
            if lowered.startswith("@") or lowered.startswith("user:") or lowered.startswith("creator:"):
                name = _creator_name(token)
                if name and name not in creators:
                    creators.append(name)
                continue
            text_parts.append(token)

    for tag in extra_tags or ():
        value = _tag_name(str(tag))
        if value and value not in tags:
            tags.append(value)

    if creator:
        value = _creator_name(str(creator))
        if value and value not in creators:
            creators.append(value)

    query_text = " ".join(text_parts)
    return query_text, tags, creators


def normalize_search_query(
    query: str | SearchQuery | None = None,
    *,
    tags: Sequence[str] | None = None,
    creator: str | None = None,
    mode: str | None = None,
    order: str | None = None,
    page: int | str | None = None,
    limit: int | str | None = None,
) -> SearchQuery:
    if isinstance(query, SearchQuery):
        normalized = query.model_copy(deep=True)
        normalized.mode = mode or normalized.mode or "search"
        normalized.order = order or normalized.order
        normalized.page = max(1, _coerce_int(page or normalized.page, normalized.page))
        normalized.limit = max(1, min(100, _coerce_int(limit or normalized.limit, normalized.limit)))
        if tags:
            merged_tags = []
            for tag in tags:
                value = _tag_name(str(tag))
                if value and value not in merged_tags:
                    merged_tags.append(value)
            normalized.tags = merged_tags
        if creator:
            creator_name = _creator_name(str(creator))
            if creator_name:
                base_text = normalized.query or ""
                prefix = f"@{creator_name} "
                if not base_text.startswith(prefix) and not base_text.startswith(f"@{creator_name}"):
                    normalized.query = f"{prefix}{base_text}".strip()
        return normalized

    raw_query = str(query or "")
    text_query, normalized_tags, creators = parse_search_tokens(raw_query, extra_tags=tags, creator=creator)
    creator_bits = " ".join(f"@{name}" for name in creators)
    if creator_bits:
        text_query = " ".join(part for part in (text_query, creator_bits) if part).strip()
    normalized_page = max(1, _coerce_int(page, 1))
    normalized_limit = max(1, min(100, _coerce_int(limit, 20)))
    if mode is None:
        mode = "trending" if not text_query and not normalized_tags and not raw_query and not creator else "search"
    return SearchQuery(
        mode=mode,
        query=text_query or None,
        tags=normalized_tags,
        order=order,
        page=normalized_page,
        limit=normalized_limit,
    )
