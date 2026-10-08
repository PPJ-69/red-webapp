from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from backend.app.api.media import router as media_router
from backend.app.api.stream import router as stream_router
from backend.app.config import AppEnvironment, Settings
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError, register_exception_handlers
from backend.app.domain.models import Creator, InternalSourceTarget, MediaItem
from backend.app.observability.logging import install_request_context
from backend.app.observability.metrics import MetricsRegistry
from backend.app.services.media_resolver import MediaResolver
from backend.app.upstream.stream_transport import StreamTransport
from backend.tests.fakes.fake_provider import FakeMediaProvider
from backend.tests.fixtures.fake_cdn import FakeCDN, FakeCDNFault


class _PocProvider(FakeMediaProvider):
    _media_ids = ("sample-media", "sample-media-two", "sample-media-failure")

    async def get_media(self, media_id: str) -> MediaItem:
        if media_id not in self._media_ids:
            raise ApplicationError(ErrorCategory.NOT_FOUND, "The requested item was not found.")
        return MediaItem(
            id=media_id,
            title={
                "sample-media": "Sample media",
                "sample-media-two": "Second sample",
                "sample-media-failure": "Failure retry sample",
            }[media_id],
            creator=Creator(id="poc-creator", username="poc"),
            duration=12.5,
        )

    async def resolve_source(
        self, media_id: str, quality: str
    ) -> InternalSourceTarget:
        if media_id not in self._media_ids:
            raise ApplicationError(ErrorCategory.NOT_FOUND, "The requested media was not found.")
        return InternalSourceTarget(
            url=f"{self._cdn_base_url}/media/{media_id}-{quality}.avi",
            headers={"X-Fake-Provider": "test"},
        )


def create_poc_app(cdn: FakeCDN) -> FastAPI:
    parsed_cdn = urlsplit(cdn.base_url)

    def validate_poc_target(target: str) -> str:
        parsed = urlsplit(target)
        if (
            parsed.scheme != "http"
            or parsed.hostname != parsed_cdn.hostname
            or parsed.port != parsed_cdn.port
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("POC target is outside the local fake CDN.")
        return target

    transport = StreamTransport(
        target_validator=validate_poc_target,
        chunk_size=16 * 1024,
        connect_timeout_seconds=2,
        header_timeout_seconds=2,
        idle_timeout_seconds=10,
        total_timeout_seconds=120,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        cdn.start()
        try:
            yield
        finally:
            await transport.aclose()
            cdn.close()

    app = FastAPI(
        title="Development Streaming POC",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = Settings(
        AppEnvironment.TEST,
        max_active_streams_per_ip=4,
    )
    app.state.metrics = MetricsRegistry()
    app.state.upstream_provider = _PocProvider(cdn_base_url=cdn.base_url)
    app.state.media_resolver = MediaResolver(app.state.upstream_provider)
    app.state.stream_transport = transport
    app.include_router(media_router)
    app.include_router(stream_router)

    @app.post("/__poc/fault")
    async def set_fault(
        fault: str = Query(pattern=r"^(clear|server_error)$"),
    ) -> dict[str, str]:
        cdn.set_fault(
            None if fault == "clear" else FakeCDNFault.SERVER_ERROR
        )
        return {"fault": fault}

    @app.post("/__poc/fixture")
    async def set_fixture(request: Request) -> dict[str, int]:
        if request.headers.get("content-type") != "video/webm":
            raise HTTPException(status_code=415, detail="Expected video/webm.")
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Fixture is too large.")
        body = await request.body()
        if not body or len(body) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Fixture is empty or too large.")
        cdn.set_sample_body(body, "video/webm")
        return {"bytes": len(body)}

    @app.get("/__poc/stats")
    async def stats() -> JSONResponse:
        opened, closed, active = cdn.connection_counts
        metrics = app.state.metrics.snapshot()
        return JSONResponse(
            {
                "cdnConnectionsOpened": opened,
                "cdnConnectionsClosed": closed,
                "cdnConnectionsActive": active,
                "streamActiveConnections": metrics[
                    "stream_active_connections"
                ]["value"],
            }
        )

    register_exception_handlers(app)
    install_request_context(app)
    return app
