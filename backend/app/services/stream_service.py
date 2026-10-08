from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError, classify_upstream_status
from backend.app.domain.models import InternalSourceTarget, SourceResolution
from backend.app.services.range_semantics import (
    InvalidRangeHeader,
    RangeResponse,
    map_range_response,
    parse_range_header,
)


class SourceResolver(Protocol):
    async def resolve_resolution(
        self, media_id: str, quality: str = "auto"
    ) -> SourceResolution: ...

    def invalidate(self, media_id: str, quality: str = "auto") -> None: ...


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
    def __init__(self, resolver: SourceResolver, transport: StreamOpener) -> None:
        self._resolver = resolver
        self._transport = transport

    async def stream(
        self, media_id: str, client_range: str | None, quality: str = "auto"
    ) -> RelayResponse:
        try:
            byte_range = parse_range_header(client_range)
        except InvalidRangeHeader:
            byte_range = None
        normalized_range = byte_range.as_header() if byte_range is not None else None

        resolution = await self._resolver.resolve_resolution(media_id, quality)
        upstream = await self._transport.open(
            resolution.target, range_header=normalized_range
        )

        try:
            should_resolve_again = await self._should_resolve_again(upstream)
        except ApplicationError:
            await upstream.aclose()
            raise
        if should_resolve_again:
            await upstream.aclose()
            self._resolver.invalidate(media_id, quality)
            resolution = await self._resolver.resolve_resolution(media_id, quality)
            upstream = await self._transport.open(
                resolution.target, range_header=normalized_range
            )

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
