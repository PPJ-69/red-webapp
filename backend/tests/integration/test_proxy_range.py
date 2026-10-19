from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.stream import router as stream_router
from backend.app.dependencies import get_stream_service
from backend.app.domain.errors import register_exception_handlers
from backend.app.main import lifespan
from backend.app.observability.logging import install_request_context
from backend.app.security.headers import install_security_headers
from backend.app.services.media_resolver import MediaResolver
from backend.app.services.stream_service import StreamService
from backend.app.upstream.stream_transport import StreamTransport
from backend.tests.fakes.fake_provider import FakeMediaProvider
from backend.tests.fixtures.fake_cdn import FakeCDN


_FORWARDED_RESPONSE_HEADERS = (
    "accept-ranges",
    "cache-control",
    "content-length",
    "content-range",
    "content-type",
    "etag",
    "last-modified",
    "x-correlation-id",
    "x-content-type-options",
)


def _local_cdn_validator(base_url: str):
    expected = urlsplit(base_url)

    def validate(target: str) -> str:
        parsed = urlsplit(target)
        if (
            parsed.scheme != "http"
            or parsed.hostname != expected.hostname
            or parsed.port != expected.port
        ):
            raise ValueError("Test target is outside the local fake CDN.")
        return target

    return validate


@contextmanager
def _streaming_proxy(client: TestClient) -> Iterator[tuple[str, int]]:
    class ProxyHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            request_headers = {}
            if self.headers.get("Range") is not None:
                request_headers["Range"] = self.headers["Range"]
            try:
                with client.stream(
                    "GET", self.path, headers=request_headers
                ) as response:
                    self.send_response(response.status_code)
                    for name in _FORWARDED_RESPONSE_HEADERS:
                        value = response.headers.get(name)
                        if value is not None:
                            self.send_header(name, value)
                    self.end_headers()
                    for chunk in response.iter_raw():
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ProxyHandler)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        name="range-proxy-test",
        daemon=True,
    )
    thread.start()
    try:
        host, port = server.server_address
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _app(service: StreamService, transport: StreamTransport) -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.state.stream_transport = transport
    app.include_router(stream_router)
    app.dependency_overrides[get_stream_service] = lambda: service
    register_exception_handlers(app)
    install_request_context(app)
    install_security_headers(app)
    return app


def _get_through_proxy(
    address: tuple[str, int], range_header: str | None
) -> tuple[int, dict[str, str], bytes]:
    connection = HTTPConnection(*address, timeout=5)
    headers = {"Range": range_header} if range_header is not None else {}
    try:
        connection.request("GET", "/api/stream/sample-media", headers=headers)
        response = connection.getresponse()
        response_headers = {
            name.lower(): value for name, value in response.getheaders()
        }
        return response.status, response_headers, response.read()
    finally:
        connection.close()


class ProxyRangeIntegrationTests(unittest.TestCase):
    def test_nginx_config_forwards_ranges_without_buffering_and_caps_headers(self) -> None:
        root = Path(__file__).resolve().parents[3]
        config = (
            root / "deploy" / "reverse-proxy" / "nginx.conf"
        ).read_text(encoding="utf-8")

        for directive in (
            "proxy_set_header Range $http_range;",
            "proxy_set_header If-Range $http_if_range;",
            "proxy_set_header X-Forwarded-For $remote_addr;",
            "proxy_buffering off;",
            "proxy_request_buffering off;",
            "proxy_max_temp_file_size 0;",
            "proxy_read_timeout 610s;",
            "large_client_header_buffers 2 8k;",
            "client_max_body_size 1k;",
            "ssl_protocols TLSv1.2 TLSv1.3;",
        ):
            with self.subTest(directive=directive):
                self.assertIn(directive, config)

        compose = (
            root / "deploy" / "docker-compose.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(compose.count("\n    read_only: true\n"), 2)
        self.assertIn("TRUSTED_PROXY_IPS: 172.30.0.2/32", compose)
        self.assertIn("stop_grace_period: 30s", compose)

    def test_range_and_repeated_seek_work_through_streaming_proxy(self) -> None:
        with FakeCDN(chunk_delay=0) as cdn:
            transport = StreamTransport(
                target_validator=_local_cdn_validator(cdn.base_url),
                chunk_size=4096,
                connect_timeout_seconds=2,
                header_timeout_seconds=2,
                idle_timeout_seconds=5,
                total_timeout_seconds=10,
            )
            service = StreamService(
                MediaResolver(FakeMediaProvider(cdn_base_url=cdn.base_url)),
                transport,
            )
            app = _app(service, transport)
            close_called = threading.Event()
            original_close = transport.aclose

            async def tracked_close() -> None:
                close_called.set()
                await original_close()

            transport.aclose = tracked_close
            with patch.dict(os.environ, {"APP_ENV": "test"}):
                with TestClient(app) as backend_client:
                    with _streaming_proxy(backend_client) as proxy_address:
                        status, headers, first = _get_through_proxy(
                            proxy_address, "bytes=4-15"
                        )
                        self.assertEqual(status, 206)
                        self.assertEqual(headers["content-range"], "bytes 4-15/272")
                        self.assertEqual(first, cdn.sample_bytes[4:16])

                        status, headers, second = _get_through_proxy(
                            proxy_address, "bytes=32-47"
                        )
                        self.assertEqual(status, 206)
                        self.assertEqual(headers["content-range"], "bytes 32-47/272")
                        self.assertEqual(second, cdn.sample_bytes[32:48])

                self.assertTrue(close_called.is_set())

            self.assertEqual(cdn.active_connections, 0)
            self.assertEqual(cdn.connections_opened, cdn.connections_closed)


if __name__ == "__main__":
    unittest.main()
