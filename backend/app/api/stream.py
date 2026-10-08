from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from backend.app.dependencies import get_stream_service
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.services.stream_service import RelayResponse, StreamService

router = APIRouter(tags=["stream"])


class _RelayStreamingResponse(StreamingResponse):
    def __init__(self, relay: RelayResponse, headers: dict[str, str]) -> None:
        super().__init__(
            relay.body,
            status_code=relay.status_code,
            headers=headers,
        )
        self._close_relay = relay.close

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self._close_relay()


@router.get("/api/stream/{media_id}")
async def stream_media(
    media_id: str,
    request: Request,
    range_header: str | None = Header(default=None, alias="Range"),
    quality: str = Query(default="auto", pattern=r"^(auto|hd|sd)$"),
    service: StreamService = Depends(get_stream_service),
) -> StreamingResponse:
    if set(request.query_params) - {"quality"}:
        raise ApplicationError(
            ErrorCategory.INVALID_REQUEST,
            "Only the quality selector is accepted as a query parameter.",
        )
    relay = await service.stream(media_id, range_header, quality)
    headers = dict(relay.headers)
    headers["cache-control"] = "no-store"
    headers.setdefault("x-content-type-options", "nosniff")
    return _RelayStreamingResponse(relay, headers)
