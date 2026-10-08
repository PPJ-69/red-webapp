from __future__ import annotations

import asyncio
from collections.abc import Callable
from urllib.parse import urlsplit
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.stream import router as stream_router
from backend.app.config import AppEnvironment, Settings
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError, register_exception_handlers
from backend.app.domain.models import (
    InternalSourceTarget,
    MediaSource,
    SourceResolution,
)
from backend.app.dependencies import get_stream_service
from backend.app.observability.logging import install_request_context
from backend.app.observability.metrics import MetricsRegistry
from backend.app.services.media_resolver import MediaResolver
from backend.app.services.stream_service import StreamService
from backend.app.upstream.stream_transport import StreamTransport
from backend.tests.conftest import fake_cdn_server
from backend.tests.fakes.fake_provider import FakeMediaProvider
from backend.tests.fixtures.fake_cdn import FakeCDNFault


def _local_cdn_validator(base_url: str) -> Callable[[str], str]:
    expected = urlsplit(base_url)

    def validate(target: str) -> str:
        parsed = urlsplit(target)
        if (
            parsed.scheme != "http"
            or parsed.hostname != expected.hostname
            or parsed.port != expected.port
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Test target is outside the fake CDN.")
        return target

    return validate


def _service(
    cdn_url: str,
    *,
    provider: FakeMediaProvider | None = None,
    chunk_size: int = 4096,
    idle_timeout_seconds: float = 1,
    total_timeout_seconds: float = 10,
) -> tuple[StreamService, StreamTransport]:
    provider = provider or FakeMediaProvider(cdn_base_url=cdn_url)
    transport = StreamTransport(
        target_validator=_local_cdn_validator(cdn_url),
        chunk_size=chunk_size,
        connect_timeout_seconds=1,
        header_timeout_seconds=1,
        idle_timeout_seconds=idle_timeout_seconds,
        total_timeout_seconds=total_timeout_seconds,
    )
    return StreamService(MediaResolver(provider), transport), transport


class _TargetResolver:
    def __init__(self, target_url: str) -> None:
        self.target_url = target_url

    async def resolve_resolution(
        self, media_id: str, quality: str = "auto"
    ) -> SourceResolution:
        target = InternalSourceTarget(
            url=self.target_url,
            headers={"X-Fake-Provider": "test"},
        )
        return SourceResolution(
            descriptor=MediaSource(playbackUrl=f"/api/stream/{media_id}"),
            target=target,
        )

    def invalidate(self, media_id: str, quality: str = "auto") -> None:
        return


def _test_app(service: StreamService) -> FastAPI:
    app = FastAPI()
    app.state.settings = Settings(AppEnvironment.TEST)
    app.state.metrics = MetricsRegistry()
    app.include_router(stream_router)
    register_exception_handlers(app)
    install_request_context(app)
    app.dependency_overrides[get_stream_service] = lambda: service
    return app


class StreamRelayIntegrationTests(unittest.TestCase):
    def test_full_response_is_streamed_with_safe_headers(self) -> None:
        with fake_cdn_server() as cdn:
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get("/api/stream/sample-media")
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, cdn.sample_bytes)
        self.assertEqual(response.headers["content-type"], "video/x-msvideo")
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertNotIn("x-fake-provider", response.headers)

    def test_range_requests_support_seek_semantics(self) -> None:
        with fake_cdn_server() as cdn:
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    first = client.get(
                        "/api/stream/sample-media",
                        headers={"Range": "bytes=4-15"},
                    )
                    second = client.get(
                        "/api/stream/sample-media",
                        headers={"Range": "bytes=32-47"},
                    )
                    suffix = client.get(
                        "/api/stream/sample-media",
                        headers={"Range": "bytes=-8"},
                    )
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(first.status_code, 206)
        self.assertEqual(first.content, cdn.sample_bytes[4:16])
        self.assertEqual(first.headers["content-range"], f"bytes 4-15/{cdn.sample_size}")
        self.assertEqual(second.status_code, 206)
        self.assertEqual(second.content, cdn.sample_bytes[32:48])
        self.assertEqual(second.headers["content-range"], f"bytes 32-47/{cdn.sample_size}")
        self.assertEqual(suffix.status_code, 206)
        self.assertEqual(suffix.content, cdn.sample_bytes[-8:])
        self.assertEqual(
            suffix.headers["content-range"],
            f"bytes {cdn.sample_size - 8}-{cdn.sample_size - 1}/{cdn.sample_size}",
        )

    def test_invalid_and_unsatisfiable_ranges_return_416(self) -> None:
        with fake_cdn_server() as cdn:
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    invalid = client.get(
                        "/api/stream/sample-media",
                        headers={"Range": "bytes=not-valid"},
                    )
                    unsatisfiable = client.get(
                        "/api/stream/sample-media",
                        headers={"Range": f"bytes={cdn.sample_size}-"},
                    )
            finally:
                asyncio.run(transport.aclose())

        for response in (invalid, unsatisfiable):
            self.assertEqual(response.status_code, 416)
            self.assertEqual(
                response.headers["content-range"],
                f"bytes */{cdn.sample_size}",
            )
            self.assertEqual(response.content, b"")

    def test_multi_range_is_treated_as_no_range(self) -> None:
        with fake_cdn_server() as cdn:
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get(
                        "/api/stream/sample-media",
                        headers={"Range": "bytes=0-1,4-5"},
                    )
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, cdn.sample_bytes)
        self.assertNotIn("content-range", response.headers)

    def test_upstream_ignoring_range_returns_full_response(self) -> None:
        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.NO_RANGE_SUPPORT)
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get(
                        "/api/stream/sample-media",
                        headers={"Range": "bytes=4-15"},
                    )
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, cdn.sample_bytes)
        self.assertNotIn("content-range", response.headers)

    def test_upstream_redirect_is_not_followed(self) -> None:
        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.REDIRECT)
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get("/api/stream/sample-media")
                self.assertTrue(cdn.wait_for_closed_connections(1))
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["category"],
            ErrorCategory.PROVIDER_ERROR.value,
        )
        self.assertEqual(cdn.connections_opened, 1)

    def test_upstream_errors_map_to_stable_error_envelopes(self) -> None:
        expected = (
            (FakeCDNFault.FORBIDDEN, 403, ErrorCategory.FORBIDDEN.value),
            (FakeCDNFault.NOT_FOUND, 404, ErrorCategory.NOT_FOUND.value),
            (FakeCDNFault.RATE_LIMITED, 429, ErrorCategory.RATE_LIMITED.value),
            (FakeCDNFault.SERVER_ERROR, 502, ErrorCategory.PROVIDER_ERROR.value),
        )
        with fake_cdn_server() as cdn:
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    for fault, status, category in expected:
                        with self.subTest(fault=fault):
                            cdn.set_fault(fault)
                            response = client.get("/api/stream/sample-media")
                            self.assertEqual(response.status_code, status)
                            self.assertEqual(response.json()["category"], category)
                            if fault is FakeCDNFault.RATE_LIMITED:
                                self.assertEqual(response.headers["retry-after"], "1")

                    cdn.set_fault(FakeCDNFault.UNAUTHORIZED)
                    response = client.get("/api/stream/sample-media")
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["category"],
            ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED.value,
        )

    def test_required_upstream_header_is_sent_only_to_cdn(self) -> None:
        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.REQUIRED_AUTH_HEADER)
            service, transport = _service(cdn.base_url)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get("/api/stream/sample-media")
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content[:4], b"RIFF")
        self.assertNotIn("x-fake-provider", response.headers)

    def test_expired_signature_re_resolves_once(self) -> None:
        class RotatingResolver:
            def __init__(self, cdn_url: str) -> None:
                self.calls = 0
                self.cdn_url = cdn_url

            async def resolve_resolution(
                self, media_id: str, quality: str = "auto"
            ) -> SourceResolution:
                self.calls += 1
                signature = "expired" if self.calls == 1 else "valid"
                target = InternalSourceTarget(
                    url=(
                        f"{self.cdn_url}/media/{media_id}.avi"
                        f"?signature={signature}"
                    ),
                    headers={"X-Fake-Provider": "test"},
                )
                descriptor = MediaSource(playbackUrl="/api/stream/sample-media")
                return SourceResolution(descriptor=descriptor, target=target)

            def invalidate(self, media_id: str, quality: str = "auto") -> None:
                return

        with fake_cdn_server() as cdn:
            resolver = RotatingResolver(cdn.base_url)
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url)
            )
            service = StreamService(resolver, transport)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get("/api/stream/sample-media")
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, cdn.sample_bytes)
        self.assertEqual(resolver.calls, 2)
        self.assertTrue(cdn.wait_for_closed_connections(2))

    def test_plain_forbidden_response_does_not_retry_or_bypass(self) -> None:
        class CountingResolver:
            calls = 0

            async def resolve_resolution(
                self, media_id: str, quality: str = "auto"
            ) -> SourceResolution:
                self.calls += 1
                target = InternalSourceTarget(
                    url=f"{cdn.base_url}/media/{media_id}.avi",
                    headers={"X-Fake-Provider": "test"},
                )
                return SourceResolution(
                    descriptor=MediaSource(playbackUrl="/api/stream/item"),
                    target=target,
                )

            def invalidate(self, media_id: str, quality: str = "auto") -> None:
                return

        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.FORBIDDEN)
            resolver = CountingResolver()
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url)
            )
            service = StreamService(resolver, transport)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get("/api/stream/item")
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(resolver.calls, 1)

    def test_client_disconnect_closes_upstream_connection(self) -> None:
        async def cancel_body(service: StreamService) -> None:
            relay = await service.stream("sample-media", None)
            body = relay.body
            await body.__anext__()
            await body.aclose()

        with fake_cdn_server(chunk_delay=0.02) as cdn:
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url),
                chunk_size=1024,
                idle_timeout_seconds=1,
            )
            service = StreamService(
                _TargetResolver(f"{cdn.base_url}/synthetic/100000000"),
                transport,
            )
            try:
                asyncio.run(cancel_body(service))
                self.assertTrue(cdn.wait_for_closed_connections(1, timeout=4))
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(cdn.connections_opened, 1)
        self.assertEqual(cdn.connections_closed, 1)
        self.assertEqual(cdn.active_connections, 0)

    def test_relay_closes_upstream_if_downstream_never_starts_iteration(self) -> None:
        async def close_before_iteration(service: StreamService) -> None:
            relay = await service.stream("sample-media", None)
            await relay.close()

        with fake_cdn_server(chunk_delay=0.02) as cdn:
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url),
                chunk_size=1024,
                idle_timeout_seconds=1,
            )
            service = StreamService(
                _TargetResolver(f"{cdn.base_url}/synthetic/100000000"),
                transport,
            )
            try:
                asyncio.run(close_before_iteration(service))
                self.assertTrue(cdn.wait_for_closed_connections(1, timeout=4))
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(cdn.connections_opened, 1)
        self.assertEqual(cdn.connections_closed, 1)
        self.assertEqual(cdn.active_connections, 0)

    def test_total_stream_timeout_closes_upstream(self) -> None:
        async def drain_body(service: StreamService) -> None:
            relay = await service.stream("sample-media", None)
            async for _chunk in relay.body:
                pass

        with fake_cdn_server(chunk_delay=0.01) as cdn:
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url),
                chunk_size=1024,
                idle_timeout_seconds=1,
                total_timeout_seconds=0.03,
            )
            service = StreamService(
                _TargetResolver(f"{cdn.base_url}/synthetic/100000000"),
                transport,
            )
            try:
                with self.assertRaises(ApplicationError) as raised:
                    asyncio.run(drain_body(service))
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(raised.exception.category, ErrorCategory.UPSTREAM_TIMEOUT)
        self.assertTrue(cdn.wait_for_closed_connections(1))

    def test_idle_timeout_interrupts_and_closes_upstream(self) -> None:
        async def read_body(service: StreamService) -> None:
            relay = await service.stream("sample-media", None)
            await relay.body.__anext__()

        with fake_cdn_server(chunk_delay=0.1) as cdn:
            cdn.set_fault(FakeCDNFault.SLOW)
            service, transport = _service(
                cdn.base_url,
                chunk_size=1024,
                idle_timeout_seconds=0.02,
            )
            try:
                with self.assertRaises(ApplicationError) as raised:
                    asyncio.run(read_body(service))
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(raised.exception.category, ErrorCategory.UPSTREAM_TIMEOUT)
        self.assertTrue(cdn.wait_for_closed_connections(1))

    def test_mid_stream_upstream_disconnect_is_classified_and_closed(self) -> None:
        async def drain_body(service: StreamService) -> None:
            relay = await service.stream("sample-media", None)
            async for _chunk in relay.body:
                pass

        with fake_cdn_server() as cdn:
            cdn.set_fault(FakeCDNFault.MID_STREAM_DISCONNECT)
            service, transport = _service(cdn.base_url)
            try:
                with self.assertRaises(ApplicationError) as raised:
                    asyncio.run(drain_body(service))
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(
            raised.exception.category,
            ErrorCategory.CONNECTION_INTERRUPTED,
        )
        self.assertTrue(cdn.wait_for_closed_connections(1))

    def test_stream_route_has_no_arbitrary_target_parameter(self) -> None:
        route = next(
            route
            for route in stream_router.routes
            if getattr(route, "path", None) == "/api/stream/{media_id}"
        )

        self.assertEqual(route.methods, {"GET"})
        self.assertEqual(
            {parameter.name for parameter in route.dependant.path_params},
            {"media_id"},
        )
        self.assertEqual(
            {parameter.alias for parameter in route.dependant.header_params},
            {"Range"},
        )
        self.assertEqual(
            {parameter.name for parameter in route.dependant.query_params},
            {"quality"},
        )

    def test_arbitrary_url_query_is_rejected_before_resolution(self) -> None:
        class CountingResolver(_TargetResolver):
            calls = 0

            async def resolve_resolution(
                self, media_id: str, quality: str = "auto"
            ) -> SourceResolution:
                self.calls += 1
                return await super().resolve_resolution(media_id, quality)

        with fake_cdn_server() as cdn:
            resolver = CountingResolver(f"{cdn.base_url}/media/sample.avi")
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url)
            )
            service = StreamService(resolver, transport)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get(
                        "/api/stream/sample-media",
                        params={"url": "http://127.0.0.1/private"},
                    )
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["category"],
            ErrorCategory.INVALID_REQUEST.value,
        )
        self.assertEqual(resolver.calls, 0)

    def test_quality_selector_is_forwarded_without_accepting_a_url(self) -> None:
        class QualityResolver(_TargetResolver):
            requested_quality: str | None = None

            async def resolve_resolution(
                self, media_id: str, quality: str = "auto"
            ) -> SourceResolution:
                self.requested_quality = quality
                return await super().resolve_resolution(media_id, quality)

        with fake_cdn_server() as cdn:
            resolver = QualityResolver(
                f"{cdn.base_url}/media/sample-media-hd.avi"
            )
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url)
            )
            service = StreamService(resolver, transport)
            try:
                with TestClient(_test_app(service)) as client:
                    response = client.get(
                        "/api/stream/sample-media?quality=hd"
                    )
            finally:
                asyncio.run(transport.aclose())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(resolver.requested_quality, "hd")

    def test_untrusted_target_is_rejected_before_network_access(self) -> None:
        async def stream(service: StreamService) -> None:
            await service.stream("sample-media", None)

        provider = FakeMediaProvider()
        transport = StreamTransport(allowed_hosts=())
        service = StreamService(MediaResolver(provider), transport)
        try:
            with self.assertRaises(ApplicationError) as raised:
                asyncio.run(stream(service))
        finally:
            asyncio.run(transport.aclose())

        self.assertEqual(raised.exception.category, ErrorCategory.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
