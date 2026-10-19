from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError, classify_upstream_status
from backend.app.domain.models import InternalSourceTarget, SourceResolution
from backend.app.services.hls_playlist import (
    HLS_MIME_TYPE,
    MAX_PLAYLIST_BYTES,
    rewrite_vod_playlist,
)
from backend.app.services.hls_resources import HlsResourceRegistry
from backend.app.services.range_semantics import (
    InvalidRangeHeader,
    RangeResponse,
    map_range_response,
    parse_range_header,
)


class SourceResolver(Protocol):
    async def resolve_resolution(
        self,
        media_id: str,
        quality: str = "auto",
        supports_hls: bool = False,
    ) -> SourceResolution: ...

    def invalidate(self, media_id: str, quality: str = "auto") -> None: ...

    def cache_mp4_fallback(
        self, media_id: str, quality: str, resolution: SourceResolution
    ) -> None: ...


class StreamSource(Protocol):
    status_code: int
    headers: Mapping[str, str]

    async def iter_chunks(self) -> AsyncIterator[bytes]: ...

    async def read_error_body(self, limit: int = 4096) -> str: ...

    async def aclose(self) -> None: ...


class StreamOpener(Protocol):
    async def open(
        self,
        target: InternalSourceTarget,
        *,
        range_header: str | None = None,
    ) -> StreamSource: ...


@dataclass(frozen=True)
class RelayResponse:
    status_code: int
    headers: dict[str, str]
    body: AsyncIterator[bytes]
    close: Callable[[], Awaitable[None]]


class StreamService:
    def __init__(
        self,
        resolver: SourceResolver,
        transport: StreamOpener,
        *,
        hls_resource_ttl_seconds: float = 3600.0,
    ) -> None:
        self._resolver = resolver
        self._transport = transport
        self.hls_resources = HlsResourceRegistry(
            ttl_seconds=hls_resource_ttl_seconds
        )

    async def stream(
        self,
        media_id: str,
        client_range: str | None,
        quality: str = "auto",
        supports_hls: bool = False,
    ) -> RelayResponse:
        try:
            byte_range = parse_range_header(client_range)
        except InvalidRangeHeader:
            byte_range = None
        normalized_range = byte_range.as_header() if byte_range is not None else None

        resolution, upstream = await self._resolve_and_open(
            media_id,
            quality,
            normalized_range,
            supports_hls=supports_hls,
        )

        if _is_hls_target(resolution.target):
            if client_range is not None:
                await upstream.aclose()
                upstream = await self._transport.open(
                    resolution.target, range_header=None
                )
            try:
                return await self._rewrite_playlist_response(
                    upstream,
                    media_id=media_id,
                    target=resolution.target,
                    depth=0,
                )
            except ApplicationError as exc:
                if (
                    not supports_hls
                    or exc.category != ErrorCategory.UNSUPPORTED_MEDIA
                ):
                    raise
                try:
                    fallback, fallback_upstream = await self._resolve_and_open(
                        media_id,
                        quality,
                        normalized_range,
                        supports_hls=False,
                    )
                except ApplicationError as fallback_error:
                    if fallback_error.category == ErrorCategory.UNSUPPORTED_MEDIA:
                        raise exc from fallback_error
                    raise
                if _is_hls_target(fallback.target):
                    await fallback_upstream.aclose()
                    raise exc
                self._resolver.cache_mp4_fallback(
                    media_id, quality, fallback
                )
                return await self._stream_upstream(
                    fallback_upstream, client_range
                )

        return await self._stream_upstream(upstream, client_range)

    async def _resolve_and_open(
        self,
        media_id: str,
        quality: str,
        range_header: str | None,
        *,
        supports_hls: bool,
    ) -> tuple[SourceResolution, StreamSource]:
        if supports_hls:
            resolution = await self._resolver.resolve_resolution(
                media_id, quality, supports_hls=True
            )
        else:
            resolution = await self._resolver.resolve_resolution(media_id, quality)
        upstream = await self._transport.open(
            resolution.target, range_header=range_header
        )
        try:
            should_resolve_again = await self._should_resolve_again(upstream)
        except ApplicationError:
            await upstream.aclose()
            raise
        if should_resolve_again:
            await upstream.aclose()
            self._resolver.invalidate(media_id, quality)
            if supports_hls:
                resolution = await self._resolver.resolve_resolution(
                    media_id, quality, supports_hls=True
                )
            else:
                resolution = await self._resolver.resolve_resolution(
                    media_id, quality
                )
            upstream = await self._transport.open(
                resolution.target, range_header=range_header
            )
        return resolution, upstream

    async def stream_hls_resource(
        self,
        media_id: str,
        token: str,
        client_range: str | None,
    ) -> RelayResponse:
        resource = self.hls_resources.resolve(media_id, token)
        if resource.is_playlist and client_range is not None:
            raise ApplicationError(
                ErrorCategory.INVALID_REQUEST,
                "Range requests are not supported for HLS playlists.",
            )
        upstream = await self._transport.open(
            resource.target,
            range_header=client_range if not resource.is_playlist else None,
        )
        try:
            should_resolve_again = await self._should_resolve_again(upstream)
        except ApplicationError:
            await upstream.aclose()
            raise
        if should_resolve_again:
            await upstream.aclose()
            raise ApplicationError(
                ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                "The upstream HLS resource expired; resolve the source again.",
            )
        if resource.is_playlist:
            return await self._rewrite_playlist_response(
                upstream,
                media_id=media_id,
                target=resource.target,
                depth=resource.depth,
            )
        return await self._stream_upstream(upstream, client_range)

    async def _rewrite_playlist_response(
        self,
        upstream: StreamSource,
        *,
        media_id: str,
        target: InternalSourceTarget,
        depth: int,
    ) -> RelayResponse:
        if upstream.status_code >= 400:
            try:
                category = classify_upstream_status(upstream.status_code)
                if upstream.status_code == 401:
                    category = ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED
                raise ApplicationError(
                    category,
                    self._error_message(upstream.status_code),
                    retry_after=self._retry_after(
                        upstream.headers.get("retry-after")
                    ),
                )
            finally:
                await upstream.aclose()
        if upstream.status_code != 200:
            await upstream.aclose()
            raise ApplicationError(
                ErrorCategory.UNSUPPORTED_MEDIA,
                "The upstream HLS playlist returned an unsupported status.",
            )

        try:
            content = await _read_limited(upstream, MAX_PLAYLIST_BYTES)
            rewritten = rewrite_vod_playlist(
                content,
                media_id=media_id,
                base_url=target.url,
                headers=dict(target.headers),
                registry=self.hls_resources,
                depth=depth,
            )
        finally:
            await upstream.aclose()

        async def body() -> AsyncIterator[bytes]:
            yield rewritten

        return RelayResponse(
            status_code=200,
            headers={
                "content-type": HLS_MIME_TYPE,
                "content-length": str(len(rewritten)),
                "cache-control": "no-store",
            },
            body=body(),
            close=_close_nothing,
        )

    async def _stream_upstream(
        self, upstream: StreamSource, client_range: str | None
    ) -> RelayResponse:
        if upstream.status_code >= 400 and upstream.status_code != 416:
            try:
                retry_after = self._retry_after(upstream.headers.get("retry-after"))
                category = classify_upstream_status(upstream.status_code)
                if upstream.status_code == 401:
                    category = ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED
                raise ApplicationError(
                    category,
                    self._error_message(upstream.status_code),
                    retry_after=retry_after,
                )
            finally:
                await upstream.aclose()

        if upstream.status_code not in {200, 206, 416}:
            await upstream.aclose()
            raise ApplicationError(
                ErrorCategory.PROVIDER_ERROR,
                "The upstream media service returned an unsupported response.",
            )

        mapped: RangeResponse = map_range_response(
            client_range, upstream.status_code, upstream.headers
        )
        if mapped.status_code == 416:
            await upstream.aclose()
            return RelayResponse(
                mapped.status_code,
                mapped.headers,
                _empty_body(),
                _close_nothing,
            )

        async def close() -> None:
            await upstream.aclose()

        async def body() -> AsyncIterator[bytes]:
            try:
                async for chunk in upstream.iter_chunks():
                    yield chunk
            finally:
                await close()

        return RelayResponse(mapped.status_code, mapped.headers, body(), close)

    async def _should_resolve_again(self, upstream: StreamSource) -> bool:
        if upstream.status_code == 401:
            return True
        if upstream.status_code != 403:
            return False
        body = await upstream.read_error_body()
        lowered = body.casefold()
        return "expired" in lowered and "signature" in lowered

    @staticmethod
    def _retry_after(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return max(0, int(value))
        except ValueError:
            return None

    @staticmethod
    def _error_message(status_code: int) -> str:
        if status_code == 401:
            return "The upstream media source rejected authentication."
        if status_code == 403:
            return "The upstream media source denied access."
        if status_code == 404:
            return "The requested media was not found upstream."
        if status_code == 429:
            return "The upstream media service is rate limited."
        return "The upstream media service returned an error."


async def _empty_body() -> AsyncIterator[bytes]:
    if False:
        yield b""


async def _close_nothing() -> None:
    return


async def _read_limited(upstream: StreamSource, limit: int) -> bytes:
    body = bytearray()
    try:
        async for chunk in upstream.iter_chunks():
            if len(body) + len(chunk) > limit:
                raise ApplicationError(
                    ErrorCategory.UNSUPPORTED_MEDIA,
                    "The HLS playlist exceeds the supported size.",
                )
            body.extend(chunk)
    except ApplicationError:
        raise
    return bytes(body)


def _is_hls_target(target: InternalSourceTarget) -> bool:
    mime_type = (target.mime_type or "").split(";", 1)[0].strip().lower()
    return mime_type in {
        HLS_MIME_TYPE,
        "application/x-mpegurl",
        "audio/mpegurl",
        "audio/x-mpegurl",
    } or urlsplit(target.url).path.lower().endswith(".m3u8")
