from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from typing import Iterator

import httpcore2
import httpx2 as httpx

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget
from backend.app.security.validation import (
    ValidatedUpstreamTarget,
    resolve_validated_upstream_target,
)


_HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "range",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class _PinnedNetworkBackend(httpcore2.AsyncNetworkBackend):
    def __init__(
        self, backend: httpcore2.AsyncNetworkBackend | None = None
    ) -> None:
        self._backend = backend or httpcore2.AnyIOBackend()
        self._validated_addresses: ContextVar[dict[str, tuple[str, ...]] | None] = (
            ContextVar("validated_upstream_addresses", default=None)
        )

    @contextmanager
    def pin(self, target: ValidatedUpstreamTarget) -> Iterator[None]:
        token = self._validated_addresses.set(
            {target.hostname: target.addresses}
        )
        try:
            yield
        finally:
            self._validated_addresses.reset(token)

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Sequence[tuple[int, int, int | bytes]] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        addresses_by_host = self._validated_addresses.get()
        addresses = (
            addresses_by_host.get(host.lower())
            if addresses_by_host is not None
            else None
        )
        if not addresses:
            raise httpcore2.ConnectError(
                "No validated address is available for the upstream host."
            )

        last_error: Exception | None = None
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore2.ConnectError, httpcore2.ConnectTimeout) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore2.ConnectError("No validated address could be connected.")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Sequence[tuple[int, int, int | bytes]] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        raise httpcore2.ConnectError("Unix sockets are not allowed for upstream media.")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self, network_backend: _PinnedNetworkBackend) -> None:
        super().__init__(trust_env=False)

        limits = httpx.Limits()
        self._pool = httpcore2.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=True, trust_env=False),
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            http1=True,
            http2=False,
            network_backend=network_backend,
        )


class UpstreamStream:
    def __init__(
        self,
        response: httpx.Response,
        *,
        chunk_size: int,
        total_timeout_seconds: float,
    ) -> None:
        self.status_code = response.status_code
        self.headers: Mapping[str, str] = response.headers
        self._response = response
        self._chunk_size = chunk_size
        self._total_timeout_seconds = total_timeout_seconds
        self._closed = False

    async def iter_chunks(self) -> AsyncIterator[bytes]:
        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                async for chunk in self._response.aiter_raw(
                    chunk_size=self._chunk_size
                ):
                    if chunk:
                        yield chunk
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_TIMEOUT,
                "The upstream media stream timed out.",
            ) from exc
        except httpx.HTTPError as exc:
            raise ApplicationError(
                ErrorCategory.CONNECTION_INTERRUPTED,
                "The upstream media stream was interrupted.",
            ) from exc
        except TimeoutError as exc:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_TIMEOUT,
                "The upstream media stream exceeded its time limit.",
            ) from exc

    async def read_error_body(self, limit: int = 4096) -> str:
        body = bytearray()
        try:
            async for chunk in self._response.aiter_raw(chunk_size=min(limit, 1024)):
                remaining = limit - len(body)
                body.extend(chunk[:remaining])
                if len(body) >= limit:
                    break
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_TIMEOUT,
                "The upstream error response timed out.",
            ) from exc
        except httpx.HTTPError as exc:
            raise ApplicationError(
                ErrorCategory.CONNECTION_INTERRUPTED,
                "The upstream error response was interrupted.",
            ) from exc
        return body.decode("utf-8", errors="replace")

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            await self._response.aclose()


class StreamTransport:
    def __init__(
        self,
        *,
        allowed_hosts: Sequence[str] = (),
        connect_timeout_seconds: float = 5.0,
        header_timeout_seconds: float = 15.0,
        idle_timeout_seconds: float = 30.0,
        total_timeout_seconds: float = 600.0,
        chunk_size: int = 64 * 1024,
        target_validator: Callable[[str], str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if chunk_size < 1 or min(
            connect_timeout_seconds,
            header_timeout_seconds,
            idle_timeout_seconds,
            total_timeout_seconds,
        ) <= 0:
            raise ValueError("Stream chunk size and timeout values must be positive.")
        self.connect_timeout_seconds = connect_timeout_seconds
        self.header_timeout_seconds = header_timeout_seconds
        self.idle_timeout_seconds = idle_timeout_seconds
        self.total_timeout_seconds = total_timeout_seconds
        self.chunk_size = chunk_size
        self._allowed_hosts = tuple(allowed_hosts)
        if client is not None and target_validator is None:
            raise ValueError(
                "A custom client requires an explicit target validator."
            )
        self._target_validator = target_validator
        self._network_backend: _PinnedNetworkBackend | None = None
        timeout = httpx.Timeout(
            idle_timeout_seconds,
            connect=connect_timeout_seconds,
            read=idle_timeout_seconds,
            write=idle_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        if client is not None:
            self._client = client
        elif target_validator is None:
            self._network_backend = _PinnedNetworkBackend()
            self._client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
                transport=_PinnedAsyncHTTPTransport(self._network_backend),
            )
        else:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                trust_env=False,
            )

    async def open(
        self,
        target: InternalSourceTarget,
        *,
        range_header: str | None = None,
    ) -> UpstreamStream:
        validated_target: ValidatedUpstreamTarget | None = None
        try:
            if self._target_validator is None:
                validated_target = resolve_validated_upstream_target(
                    target.url, allowed_hosts=self._allowed_hosts
                )
                safe_url = validated_target.url
            else:
                safe_url = self._target_validator(target.url)
        except ValueError as exc:
            raise ApplicationError(
                ErrorCategory.FORBIDDEN,
                "The upstream media target was rejected.",
            ) from exc

        headers = self._request_headers(target.headers, range_header)
        request = self._client.build_request("GET", safe_url, headers=headers)
        started_at = time.monotonic()
        try:
            pin_context = (
                self._network_backend.pin(validated_target)
                if self._network_backend is not None and validated_target is not None
                else nullcontext()
            )
            with pin_context:
                async with asyncio.timeout(
                    min(self.header_timeout_seconds, self.total_timeout_seconds)
                ):
                    response = await self._client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_TIMEOUT,
                "The upstream media request timed out.",
            ) from exc
        except TimeoutError as exc:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_TIMEOUT,
                "The upstream media response headers timed out.",
            ) from exc
        except httpx.HTTPError as exc:
            raise ApplicationError(
                ErrorCategory.PROVIDER_UNAVAILABLE,
                "The upstream media service is unavailable.",
            ) from exc

        remaining_total_timeout = self.total_timeout_seconds - (
            time.monotonic() - started_at
        )
        if remaining_total_timeout <= 0:
            await response.aclose()
            raise ApplicationError(
                ErrorCategory.UPSTREAM_TIMEOUT,
                "The upstream media request exceeded its time limit.",
            )

        return UpstreamStream(
            response,
            chunk_size=self.chunk_size,
            total_timeout_seconds=remaining_total_timeout,
        )

    @staticmethod
    def _request_headers(
        source_headers: Mapping[str, str], range_header: str | None
    ) -> dict[str, str]:
        headers = {"Accept-Encoding": "identity"}
        for name, value in source_headers.items():
            normalized_name = name.strip().lower()
            if (
                not normalized_name
                or normalized_name in _HOP_BY_HOP_HEADERS
                or "\r" in name
                or "\n" in name
                or "\r" in value
                or "\n" in value
            ):
                continue
            headers[normalized_name] = value.strip()
        if range_header is not None:
            headers["Range"] = range_header
        return headers

    async def aclose(self) -> None:
        await self._client.aclose()
