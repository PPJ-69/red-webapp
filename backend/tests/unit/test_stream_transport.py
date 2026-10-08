from __future__ import annotations

import asyncio
import unittest

import httpcore2

from backend.app.security.validation import ValidatedUpstreamTarget
from backend.app.upstream.stream_transport import (
    StreamTransport,
    _PinnedNetworkBackend,
    _PinnedAsyncHTTPTransport,
)


class RecordingNetworkBackend:
    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: object | None = None,
    ) -> object:
        self.hosts.append(host)
        if host == "93.184.216.34":
            raise httpcore2.ConnectError("first resolved address is unreachable")
        return object()

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: object | None = None,
    ) -> object:
        raise AssertionError("Relay must never use Unix sockets.")

    async def sleep(self, seconds: float) -> None:
        return


class PinnedNetworkBackendTests(unittest.TestCase):
    def test_tcp_uses_only_addresses_validated_for_the_origin_host(self) -> None:
        delegate = RecordingNetworkBackend()
        backend = _PinnedNetworkBackend(delegate)
        target = ValidatedUpstreamTarget(
            url="https://media.example.invalid/video.mp4",
            hostname="media.example.invalid",
            addresses=("93.184.216.34", "8.8.8.8"),
        )

        with backend.pin(target):
            connection = asyncio.run(
                backend.connect_tcp("media.example.invalid", 443, timeout=1)
            )

        self.assertIsNotNone(connection)
        self.assertEqual(delegate.hosts, ["93.184.216.34", "8.8.8.8"])

    def test_unpinned_host_is_rejected_before_connect(self) -> None:
        delegate = RecordingNetworkBackend()
        backend = _PinnedNetworkBackend(delegate)

        with self.assertRaises(httpcore2.ConnectError):
            asyncio.run(backend.connect_tcp("unexpected.example.invalid", 443))

        self.assertEqual(delegate.hosts, [])

    def test_unix_socket_connections_are_never_allowed(self) -> None:
        backend = _PinnedNetworkBackend(RecordingNetworkBackend())

        with self.assertRaises(httpcore2.ConnectError):
            asyncio.run(backend.connect_unix_socket("local.sock"))

    def test_production_transport_uses_the_pinned_network_backend(self) -> None:
        async def create_and_close() -> StreamTransport:
            transport = StreamTransport(allowed_hosts=("media.example.invalid",))
            await transport.aclose()
            return transport

        transport = asyncio.run(create_and_close())

        self.assertIsInstance(transport._client._transport, _PinnedAsyncHTTPTransport)


if __name__ == "__main__":
    unittest.main()
