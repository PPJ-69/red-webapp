from __future__ import annotations

import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from backend.app.dependencies import get_stream_limiter, get_stream_service
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.observability.metrics import MetricsRegistry, metrics
from backend.app.security.limits import (
    StreamLease,
    StreamLimiter,
    client_ip_for_request,
)
from backend.app.services.stream_service import RelayResponse, StreamService

router = APIRouter(tags=["stream"])


class _RelayStreamingResponse(StreamingResponse):
    def __init__(
        self,
        relay: RelayResponse,
        headers: dict[str, str],
        lease: StreamLease,
        registry: MetricsRegistry,
        started_at: float,
    ) -> None:
        super().__init__(
            _observe_body(relay.body, registry, started_at),
            status_code=relay.status_code,
            headers=headers,
        )
        self._close_relay = relay.close
        self._lease = lease

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                await self._close_relay()
            finally:
                self._lease.release()


async def _observe_body(
    body: AsyncIterator[bytes],
    registry: MetricsRegistry,
    started_at: float,
) -> AsyncIterator[bytes]:
    first_byte_observed = False
    try:
        async for chunk in body:
            if chunk:
                if not first_byte_observed:
                    registry.observe(
                        "stream_first_byte_ms",
                        (time.perf_counter() - started_at) * 1000,
                    )
                    first_byte_observed = True
                registry.increment("stream_bytes_forwarded_total", len(chunk))
            yield chunk
    except Exception:
        registry.increment("stream_upstream_errors_total")
        raise


_UPSTREAM_ERROR_CATEGORIES = {
    ErrorCategory.FORBIDDEN,
    ErrorCategory.NOT_FOUND,
    ErrorCategory.RATE_LIMITED,
    ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
    ErrorCategory.PROVIDER_UNAVAILABLE,
    ErrorCategory.PROVIDER_ERROR,
    ErrorCategory.UPSTREAM_TIMEOUT,
    ErrorCategory.CONNECTION_INTERRUPTED,
}


@router.get("/api/stream/{media_id}")
async def stream_media(
    media_id: str,
    request: Request,
    range_header: str | None = Header(default=None, alias="Range"),
    quality: str = Query(default="auto", pattern=r"^(auto|hd|sd)$"),
    service: StreamService = Depends(get_stream_service),
    limiter: StreamLimiter = Depends(get_stream_limiter),
) -> StreamingResponse:
    registry = getattr(request.app.state, "metrics", metrics)
    registry.increment("stream_requests_total")
    started_at = time.perf_counter()
    if set(request.query_params) - {"quality"}:
        raise ApplicationError(
            ErrorCategory.INVALID_REQUEST,
            "Only the quality selector is accepted as a query parameter.",
        )
    settings = getattr(request.app.state, "settings", None)
    trusted_proxies = settings.trusted_proxy_ips if settings is not None else ()
    client_ip = client_ip_for_request(request, trusted_proxies)
    lease = limiter.acquire(client_ip)
    response_created = False
    try:
        try:
            relay = await service.stream(media_id, range_header, quality)
        except ApplicationError as exc:
            if exc.category in _UPSTREAM_ERROR_CATEGORIES:
                registry.increment("stream_upstream_errors_total")
            raise
        except Exception:
            registry.increment("stream_upstream_errors_total")
            raise
        headers = dict(relay.headers)
        headers["cache-control"] = "no-store"
        headers.setdefault("x-content-type-options", "nosniff")
        response = _RelayStreamingResponse(
            relay, headers, lease, registry, started_at
        )
        response_created = True
        return response
    finally:
        if not response_created:
            lease.release()
