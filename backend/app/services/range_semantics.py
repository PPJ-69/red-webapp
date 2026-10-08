from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass


_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)\Z", re.IGNORECASE)
_CONTENT_RANGE_PATTERN = re.compile(
    r"bytes\s+(?:(\d+)-(\d+)/(\d+|\*)|\*/(\d+))\Z",
    re.IGNORECASE,
)
_FORWARDED_HEADERS = (
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified",
    "cache-control",
)


class InvalidRangeHeader(ValueError):
    pass


@dataclass(frozen=True)
class ByteRange:
    start: int | None
    end: int | None
    suffix_length: int | None = None

    def as_header(self) -> str:
        if self.suffix_length is not None:
            return f"bytes=-{self.suffix_length}"
        return f"bytes={self.start or 0}-{'' if self.end is None else self.end}"


@dataclass(frozen=True)
class RangeResponse:
    status_code: int
    headers: dict[str, str]


def parse_range_header(value: str | None) -> ByteRange | None:
    """Parse one byte range; absent and multi-range headers both mean no range."""
    if value is None or not value.strip():
        return None

    normalized = value.strip()
    if "," in normalized:
        return None

    match = _RANGE_PATTERN.fullmatch(normalized)
    if match is None:
        raise InvalidRangeHeader("Only a single byte range is supported.")

    first, last = match.groups()
    if not first and not last:
        raise InvalidRangeHeader("The byte range is empty.")
    if not first:
        return ByteRange(start=None, end=None, suffix_length=int(last))

    start = int(first)
    end = int(last) if last else None
    if end is not None and end < start:
        raise InvalidRangeHeader("The byte range end precedes its start.")
    return ByteRange(start=start, end=end)


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for name, value in headers.items():
        key = name.lower()
        normalized_value = value.strip()
        if key not in _FORWARDED_HEADERS or "\r" in value or "\n" in value:
            continue
        if key == "content-length" and not normalized_value.isdecimal():
            continue
        if key == "content-range" and not _CONTENT_RANGE_PATTERN.fullmatch(
            normalized_value
        ):
            continue
        if key == "accept-ranges" and normalized_value.lower() not in {
            "bytes",
            "none",
        }:
            continue
        selected[key] = normalized_value
    return selected


def _known_size(status_code: int, headers: Mapping[str, str]) -> int | None:
    content_range = _CONTENT_RANGE_PATTERN.fullmatch(
        headers.get("content-range", "").strip()
    )
    if content_range is not None:
        total = content_range.group(3) or content_range.group(4)
        if total is not None and total != "*":
            return int(total)

    if status_code == 200:
        content_length = headers.get("content-length", "").strip()
        if content_length.isdecimal():
            return int(content_length)
    return None


def _range_is_unsatisfiable(byte_range: ByteRange, size: int) -> bool:
    if byte_range.suffix_length is not None:
        return byte_range.suffix_length == 0 or size == 0
    return byte_range.start is not None and byte_range.start >= size


def _local_416(headers: dict[str, str], size: int) -> RangeResponse:
    result = {
        key: value
        for key, value in headers.items()
        if key in {"content-type", "etag", "last-modified", "cache-control"}
    }
    result.update(
        {
            "accept-ranges": "bytes",
            "content-length": "0",
            "content-range": f"bytes */{size}",
        }
    )
    return RangeResponse(status_code=416, headers=result)


def map_range_response(
    client_range: str | None,
    upstream_status: int,
    upstream_headers: Mapping[str, str],
) -> RangeResponse:
    """Map an upstream response to safe downstream status and headers."""
    normalized_headers = {
        name.lower(): value for name, value in upstream_headers.items()
    }
    result_headers = _safe_headers(normalized_headers)
    result_headers.setdefault("cache-control", "no-store")
    size = _known_size(upstream_status, normalized_headers)

    try:
        byte_range = parse_range_header(client_range)
    except InvalidRangeHeader:
        if size is not None:
            return _local_416(result_headers, size)
        byte_range = None

    if byte_range is not None and size is not None:
        if _range_is_unsatisfiable(byte_range, size):
            return _local_416(result_headers, size)

    if upstream_status == 416:
        result_headers["accept-ranges"] = result_headers.get("accept-ranges", "bytes")
        if size is not None:
            result_headers["content-range"] = f"bytes */{size}"
        return RangeResponse(status_code=416, headers=result_headers)

    if upstream_status == 206:
        result_headers["accept-ranges"] = result_headers.get("accept-ranges", "bytes")
        content_range = _CONTENT_RANGE_PATTERN.fullmatch(
            result_headers.get("content-range", "")
        )
        if (
            content_range is not None
            and content_range.group(1) is not None
            and int(content_range.group(2)) >= int(content_range.group(1))
        ):
            start, end = int(content_range.group(1)), int(content_range.group(2))
            result_headers.setdefault("content-length", str(end - start + 1))
        return RangeResponse(status_code=206, headers=result_headers)

    result_headers.pop("content-range", None)
    return RangeResponse(status_code=upstream_status, headers=result_headers)
