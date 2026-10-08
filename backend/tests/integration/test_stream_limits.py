import asyncio
import json
import unittest

from fastapi import FastAPI
from starlette.requests import Request

from backend.app.api.stream import router as stream_router
from backend.app.config import AppEnvironment, Settings
from backend.app.dependencies import get_stream_service
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError, register_exception_handlers
from backend.app.observability.metrics import MetricsRegistry
from backend.app.services.stream_service import RelayResponse


class _GatedService:
    def __init__(self, release: asyncio.Event) -> None:
        self.release = release
        self.calls = 0

    async def stream(
        self, media_id: str, client_range: str | None, quality: str = "auto"
    ) -> RelayResponse:
        self.calls += 1

        async def body():
            yield b"first"
            await self.release.wait()
            yield b"last"

        async def close() -> None:
            return

        return RelayResponse(200, {"content-type": "video/mp4"}, body(), close)


class _FailingService:
    async def stream(
        self, media_id: str, client_range: str | None, quality: str = "auto"
    ) -> RelayResponse:
        raise ApplicationError(
            ErrorCategory.UPSTREAM_TIMEOUT,
            "The upstream media service timed out.",
        )


def _app(service, *, max_streams: int = 1) -> tuple[FastAPI, MetricsRegistry]:
    app = FastAPI()
    registry = MetricsRegistry()
    app.state.settings = Settings(
        AppEnvironment.TEST,
        max_active_streams_per_ip=max_streams,
    )
    app.state.metrics = registry
    app.include_router(stream_router)
    app.dependency_overrides[get_stream_service] = lambda: service
    register_exception_handlers(app)
    return app, registry


class StreamLimitIntegrationTests(unittest.TestCase):
    def test_rejects_excess_stream_before_opening_upstream_and_tracks_metrics(self) -> None:
        async def scenario() -> None:
            release = asyncio.Event()
            first_chunk_sent = asyncio.Event()
            service = _GatedService(release)
            app, registry = _app(service)
            limiter_request = _request(app)
            from backend.app.dependencies import get_stream_limiter

            limiter = get_stream_limiter(limiter_request)
            response = await _stream_request(app, service, limiter, "media-1")
            scope = _scope(app)
            sent: list[dict] = []

            async def receive() -> dict:
                await asyncio.Event().wait()
                return {"type": "http.disconnect"}

            async def send(message: dict) -> None:
                sent.append(message)
                if message["type"] == "http.response.body" and message.get("body"):
                    first_chunk_sent.set()

            response_task = asyncio.create_task(response(scope, receive, send))
            try:
                await asyncio.wait_for(first_chunk_sent.wait(), timeout=2)
                with self.assertRaises(ApplicationError) as raised:
                    await _stream_request(app, service, limiter, "media-2")
                self.assertEqual(
                    raised.exception.category, ErrorCategory.LOCAL_RATE_LIMITED
                )
                self.assertEqual(raised.exception.retry_after, 1)
                self.assertEqual(service.calls, 1)
                self.assertEqual(
                    registry.snapshot()["stream_active_connections"]["value"], 1
                )
            finally:
                release.set()
            await response_task

            snapshot = registry.snapshot()
            self.assertEqual(snapshot["stream_requests_total"]["value"], 2)
            self.assertEqual(snapshot["stream_active_connections"]["value"], 0)
            self.assertEqual(snapshot["stream_bytes_forwarded_total"]["value"], 9)
            self.assertEqual(snapshot["stream_first_byte_ms"]["count"], 1)
            self.assertEqual(
                b"".join(
                    message.get("body", b"")
                    for message in sent
                    if message["type"] == "http.response.body"
                ),
                b"firstlast",
            )

        asyncio.run(scenario())

    def test_releases_slot_when_downstream_cancels_response(self) -> None:
        async def scenario() -> None:
            release = asyncio.Event()
            first_chunk_sent = asyncio.Event()
            service = _GatedService(release)
            app, registry = _app(service)
            from backend.app.dependencies import get_stream_limiter

            limiter = get_stream_limiter(_request(app))
            response = await _stream_request(app, service, limiter, "media-1")

            async def receive() -> dict:
                await asyncio.Event().wait()
                return {"type": "http.disconnect"}

            async def send(message: dict) -> None:
                if message["type"] == "http.response.body" and message.get("body"):
                    first_chunk_sent.set()

            response_task = asyncio.create_task(
                response(_scope(app), receive, send)
            )
            await asyncio.wait_for(first_chunk_sent.wait(), timeout=2)
            response_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await response_task

            self.assertEqual(
                registry.snapshot()["stream_active_connections"]["value"], 0
            )

        asyncio.run(scenario())

    def test_releases_slot_and_counts_upstream_error_on_open_failure(self) -> None:
        async def scenario() -> None:
            service = _FailingService()
            app, registry = _app(service)
            from backend.app.dependencies import get_stream_limiter

            limiter = get_stream_limiter(_request(app))
            with self.assertRaises(ApplicationError) as raised:
                await _stream_request(app, service, limiter, "media-1")
            self.assertEqual(raised.exception.category, ErrorCategory.UPSTREAM_TIMEOUT)
            error_response = await app.exception_handlers[ApplicationError](
                _request(app), raised.exception
            )
            self.assertEqual(error_response.status_code, 504)
            self.assertEqual(
                json.loads(error_response.body)["category"],
                ErrorCategory.UPSTREAM_TIMEOUT.value,
            )
            snapshot = registry.snapshot()
            self.assertEqual(snapshot["stream_active_connections"]["value"], 0)
            self.assertEqual(snapshot["stream_upstream_errors_total"]["value"], 1)

        asyncio.run(scenario())


def _request(app: FastAPI) -> Request:
    return Request(_scope(app))


def _scope(app: FastAPI) -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/stream/media",
        "raw_path": b"/api/stream/media",
        "query_string": b"",
        "headers": [],
        "client": ("198.51.100.20", 12345),
        "server": ("testserver", 80),
        "app": app,
    }


async def _stream_request(app, service, limiter, media_id: str):
    from backend.app.api.stream import stream_media

    return await stream_media(
        media_id,
        _request(app),
        range_header=None,
        quality="auto",
        service=service,
        limiter=limiter,
    )


if __name__ == "__main__":
    unittest.main()
