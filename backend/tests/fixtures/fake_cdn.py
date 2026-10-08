from __future__ import annotations

import re
import threading
import time
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, urlsplit


_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)\Z", re.IGNORECASE)
_CHUNK_SIZE = 16 * 1024


class FakeCDNFault(str, Enum):
    SLOW = "slow"
    MID_STREAM_DISCONNECT = "mid_stream_disconnect"
    UNAUTHORIZED = "401"
    FORBIDDEN = "403"
    NOT_FOUND = "404"
    RATE_LIMITED = "429"
    SERVER_ERROR = "500"
    EXPIRED_SIGNATURE = "expired_signature"
    REQUIRED_AUTH_HEADER = "required_auth_header"
    MISSING_CONTENT_LENGTH = "missing_content_length"
    NO_RANGE_SUPPORT = "no_range_support"


_STATUS_FAULTS = {
    FakeCDNFault.UNAUTHORIZED: (401, "Unauthorized"),
    FakeCDNFault.FORBIDDEN: (403, "Forbidden"),
    FakeCDNFault.NOT_FOUND: (404, "Not Found"),
    FakeCDNFault.RATE_LIMITED: (429, "Too Many Requests"),
    FakeCDNFault.SERVER_ERROR: (500, "Injected Server Error"),
}


class _FakeCDNServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        sample_body: bytes,
        chunk_delay: float,
    ) -> None:
        self.sample_body = sample_body
        self.chunk_delay = chunk_delay
        self.state_lock = threading.Lock()
        self.fault_lock = threading.Lock()
        self.fault: FakeCDNFault | None = None
        self.connections_opened = 0
        self.connections_closed = 0
        self.active_connections = 0
        super().__init__(server_address, _FakeCDNHandler)

    def set_fault(self, fault: FakeCDNFault | None) -> None:
        with self.fault_lock:
            self.fault = fault

    def get_fault(self) -> FakeCDNFault | None:
        with self.fault_lock:
            return self.fault

    def connection_opened(self) -> None:
        with self.state_lock:
            self.connections_opened += 1
            self.active_connections += 1

    def connection_closed(self) -> None:
        with self.state_lock:
            self.connections_closed += 1
            self.active_connections -= 1

    def connection_counts(self) -> tuple[int, int, int]:
        with self.state_lock:
            return (
                self.connections_opened,
                self.connections_closed,
                self.active_connections,
            )


class _FakeCDNHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    @property
    def fake_server(self) -> _FakeCDNServer:
        server = self.server
        if not isinstance(server, _FakeCDNServer):
            raise TypeError("Fake CDN handler is attached to an unexpected server.")
        return server

    def setup(self) -> None:
        super().setup()
        self.fake_server.connection_opened()

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            self.fake_server.connection_closed()

    def log_message(self, _format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        route = urlsplit(self.path)
        size, is_synthetic = self._resolve_object(route.path)
        if size is None:
            self._send_error(404, "Not Found")
            return

        fault = self.fake_server.get_fault()
        if fault in _STATUS_FAULTS:
            status, message = _STATUS_FAULTS[fault]
            self._send_error(status, message)
            return
        if fault is FakeCDNFault.EXPIRED_SIGNATURE or (
            parse_qs(route.query).get("signature") == ["expired"]
        ):
            self._send_error(403, "Expired signature")
            return
        if fault is FakeCDNFault.REQUIRED_AUTH_HEADER and self.headers.get(
            "X-Fake-Provider"
        ) != "test":
            self._send_error(401, "Required test authorization header is missing")
            return

        range_header = self.headers.get("Range")
        if fault is FakeCDNFault.NO_RANGE_SUPPORT:
            range_header = None
        parsed_range = self._parse_range(range_header, size)
        if parsed_range is False:
            self.send_response(416)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        start, end, partial = parsed_range
        content_length = max(0, end - start + 1)
        status = 206 if partial else 200
        self.send_response(status)
        self.send_header("Content-Type", "video/x-msvideo" if not is_synthetic else "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if fault is not FakeCDNFault.MISSING_CONTENT_LENGTH:
            self.send_header("Content-Length", str(content_length))
        self.end_headers()

        body_length = content_length
        if fault is FakeCDNFault.MID_STREAM_DISCONNECT and content_length > 1:
            body_length = max(1, content_length // 2)
        bytes_sent = 0
        while bytes_sent < body_length:
            chunk_length = min(_CHUNK_SIZE, body_length - bytes_sent)
            chunk = self._read_chunk(start + bytes_sent, chunk_length, is_synthetic)
            if fault is FakeCDNFault.SLOW:
                time.sleep(self.fake_server.chunk_delay)
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                break
            bytes_sent += len(chunk)

    def _resolve_object(self, path: str) -> tuple[int | None, bool]:
        if path.startswith("/media/"):
            return len(self.fake_server.sample_body), False
        match = re.fullmatch(r"/synthetic/(\d+)", path)
        if match is not None:
            return int(match.group(1)), True
        return None, False

    @staticmethod
    def _parse_range(
        value: str | None, size: int
    ) -> tuple[int, int, bool] | bool:
        if value is None:
            return (0, max(-1, size - 1), False)
        match = _RANGE_PATTERN.fullmatch(value.strip())
        if match is None or "," in value:
            return False
        first, last = match.groups()
        if not first and not last:
            return False
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
            if start >= size or end < start:
                return False
        else:
            suffix_length = int(last)
            if suffix_length == 0 or size == 0:
                return False
            start = max(0, size - suffix_length)
            end = size - 1
        return (start, end, True)

    def _read_chunk(self, offset: int, length: int, synthetic: bool) -> bytes:
        if synthetic:
            return next(iter_synthetic_body(length, offset), b"")
        return self.fake_server.sample_body[offset : offset + length]

    def _send_error(self, status: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        if status == 429:
            self.send_header("Retry-After", "1")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


class FakeCDN:
    """Loopback-only CDN fixture with bounded synthetic streaming and fault injection."""

    def __init__(
        self,
        *,
        chunk_delay: float = 0.05,
        fixture_path: Path | None = None,
    ) -> None:
        sample_path = fixture_path or Path(__file__).with_name("sample.avi")
        sample_body = sample_path.read_bytes()
        self._server = _FakeCDNServer(("127.0.0.1", 0), sample_body, chunk_delay)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.01},
            name="fake-cdn",
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def sample_size(self) -> int:
        return len(self._server.sample_body)

    @property
    def sample_bytes(self) -> bytes:
        return self._server.sample_body

    @property
    def connection_counts(self) -> tuple[int, int, int]:
        return self._server.connection_counts()

    @property
    def connections_opened(self) -> int:
        return self.connection_counts[0]

    @property
    def connections_closed(self) -> int:
        return self.connection_counts[1]

    @property
    def active_connections(self) -> int:
        return self.connection_counts[2]

    def set_fault(self, fault: FakeCDNFault | None) -> None:
        self._server.set_fault(fault)

    def start(self) -> FakeCDN:
        self._thread.start()
        return self

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def wait_for_closed_connections(
        self, expected: int, timeout: float = 2.0
    ) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.connections_closed >= expected:
                return True
            time.sleep(0.01)
        return self.connections_closed >= expected

    def __enter__(self) -> FakeCDN:
        return self.start()

    def __exit__(self, *_exc: object) -> None:
        self.close()


def iter_synthetic_body(size: int, start: int = 0) -> Iterator[bytes]:
    """Yield deterministic bounded chunks without allocating the whole object."""
    remaining = max(0, size)
    offset = start
    while remaining:
        length = min(_CHUNK_SIZE, remaining)
        yield bytes((index % 251 for index in range(offset, offset + length)))
        offset += length
        remaining -= length
