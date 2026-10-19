from __future__ import annotations

import re
from collections.abc import Callable
import secrets
from urllib.parse import quote, urljoin, urlsplit

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget
from backend.app.services.hls_resources import HlsResourceRegistry


MAX_PLAYLIST_BYTES = 1024 * 1024
MAX_PLAYLIST_REFERENCES = 5_000
MAX_PLAYLIST_DEPTH = 4
HLS_MIME_TYPE = "application/vnd.apple.mpegurl"
_URI_ATTRIBUTE = re.compile(r'(?P<prefix>\bURI=")(?P<uri>[^"]+)(?P<suffix>")')
_UNSUPPORTED_TAGS = (
    "#EXT-X-KEY:",
    "#EXT-X-SESSION-KEY:",
    "#EXT-X-PART:",
    "#EXT-X-PART-INF:",
    "#EXT-X-SERVER-CONTROL:",
    "#EXT-X-PRELOAD-HINT:",
    "#EXT-X-RENDITION-REPORT:",
    "#EXT-X-SKIP:",
    "#EXT-X-CONTENT-STEERING:",
    "#EXT-X-I-FRAMES-ONLY",
)


def rewrite_vod_playlist(
    content: bytes,
    *,
    media_id: str,
    base_url: str,
    headers: dict[str, str],
    registry: HlsResourceRegistry,
    depth: int = 0,
) -> bytes:
    if len(content) > MAX_PLAYLIST_BYTES:
        raise _unsupported("The HLS playlist exceeds the supported size.")
    if depth > MAX_PLAYLIST_DEPTH:
        raise _unsupported("The HLS playlist nesting is too deep.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _unsupported("The HLS playlist is not valid UTF-8.") from exc

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1]:
        lines.pop()
    if not lines or lines[0].strip() != "#EXTM3U":
        raise _unsupported("The upstream response is not an HLS playlist.")

    is_master = False
    has_endlist = False
    has_extinf = False
    pending_variant = False
    reference_count = 0
    pending_resources: list[tuple[InternalSourceTarget, bool, int]] = []
    markers: list[str] = []
    rewritten: list[str] = [lines[0]]

    def internal_uri(uri: str, *, is_playlist: bool) -> str:
        nonlocal reference_count
        reference_count += 1
        if reference_count > MAX_PLAYLIST_REFERENCES:
            raise _unsupported("The HLS playlist contains too many resources.")
        target_url = urljoin(base_url, uri)
        parsed = urlsplit(target_url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise _unsupported("The HLS playlist contains an unsafe resource URI.")

        inherited_headers = headers if _same_origin(base_url, target_url) else {}
        pending_resources.append(
            (
                InternalSourceTarget(url=target_url, headers=inherited_headers),
                is_playlist,
                depth + 1,
            )
        )
        marker = f"__HLS_REF_{secrets.token_urlsafe(18)}__"
        markers.append(marker)
        return marker

    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            rewritten.append(raw_line)
            continue

        upper = line.upper()
        if any(upper.startswith(tag) for tag in _UNSUPPORTED_TAGS):
            raise _unsupported("The upstream HLS feature is not supported.")
        if upper.startswith("#EXT-X-PLAYLIST-TYPE:") and upper != "#EXT-X-PLAYLIST-TYPE:VOD":
            raise _unsupported("Only VOD HLS playlists are supported.")
        if upper.startswith("#EXT-X-ENDLIST"):
            has_endlist = True
        if upper.startswith("#EXTINF:"):
            has_extinf = True
        if upper.startswith("#EXT-X-STREAM-INF:"):
            is_master = True
            pending_variant = True
        if upper.startswith("#EXT-X-MEDIA:"):
            is_master = True

        if line.startswith("#"):
            if "URI=" in upper:
                if upper.startswith("#EXT-X-MAP:"):
                    line = _rewrite_uri_attribute(
                        line,
                        lambda uri: internal_uri(uri, is_playlist=False),
                    )
                elif upper.startswith("#EXT-X-MEDIA:"):
                    line = _rewrite_uri_attribute(
                        line,
                        lambda uri: internal_uri(uri, is_playlist=True),
                    )
                else:
                    raise _unsupported(
                        "The HLS playlist uses an unsupported URI-bearing tag."
                    )
            rewritten.append(line)
            continue

        if pending_variant:
            rewritten.append(internal_uri(line, is_playlist=True))
            pending_variant = False
        else:
            rewritten.append(internal_uri(line, is_playlist=False))

    if pending_variant:
        raise _unsupported("The HLS master playlist is missing a variant URI.")
    if is_master:
        if reference_count == 0:
            raise _unsupported("The HLS master playlist contains no variants.")
    elif not has_endlist or not has_extinf:
        raise _unsupported("Only complete VOD HLS media playlists are supported.")

    tokens = registry.register_many(media_id, pending_resources)
    output = "\n".join(rewritten) + "\n"
    for marker, token in zip(markers, tokens, strict=True):
        replacement = (
            f"/api/stream/{quote(media_id, safe='')}/hls/{token}"
        )
        output = output.replace(marker, replacement)
    return output.encode("utf-8")


def _rewrite_uri_attribute(line: str, rewrite: Callable[[str], str]) -> str:
    match = _URI_ATTRIBUTE.search(line)
    if match is None:
        raise _unsupported("The HLS URI attribute is malformed.")
    return (
        line[: match.start()]
        + match.group("prefix")
        + rewrite(match.group("uri"))
        + match.group("suffix")
        + line[match.end() :]
    )


def _same_origin(left: str, right: str) -> bool:
    left_parts = urlsplit(left)
    right_parts = urlsplit(right)
    try:
        left_origin = (
            left_parts.scheme.lower(),
            (left_parts.hostname or "").lower(),
            left_parts.port,
        )
        right_origin = (
            right_parts.scheme.lower(),
            (right_parts.hostname or "").lower(),
            right_parts.port,
        )
    except ValueError as exc:
        raise _unsupported("The HLS playlist contains an invalid resource URI.") from exc
    return left_origin == right_origin


def _unsupported(message: str) -> ApplicationError:
    return ApplicationError(ErrorCategory.UNSUPPORTED_MEDIA, message)
