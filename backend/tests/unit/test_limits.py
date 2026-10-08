import unittest

from starlette.requests import Request

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.observability.metrics import MetricsRegistry
from backend.app.security.limits import StreamLimiter, client_ip_for_request


def _request(peer: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (peer, 1234),
            "server": ("localhost", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


class ClientIpTests(unittest.TestCase):
    def test_ignores_forwarded_header_from_untrusted_peer(self) -> None:
        request = _request("198.51.100.8", "203.0.113.20")

        self.assertEqual(
            client_ip_for_request(request, ("10.0.0.0/8",)),
            "198.51.100.8",
        )

    def test_uses_client_address_only_through_trusted_proxy_chain(self) -> None:
        request = _request(
            "10.0.0.2",
            "203.0.113.20, 10.0.0.1",
        )

        self.assertEqual(
            client_ip_for_request(request, ("10.0.0.0/8",)),
            "203.0.113.20",
        )

    def test_invalid_forwarded_chain_falls_back_to_peer(self) -> None:
        request = _request("10.0.0.2", "203.0.113.20, invalid")

        self.assertEqual(
            client_ip_for_request(request, ("10.0.0.0/8",)),
            "10.0.0.2",
        )


class StreamLimiterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = MetricsRegistry()
        self.limiter = StreamLimiter(1, self.registry)

    def test_caps_each_ip_and_releases_idempotently(self) -> None:
        lease = self.limiter.acquire("198.51.100.1")
        self.assertEqual(
            self.registry.snapshot()["stream_active_connections"]["value"], 1
        )
        with self.assertRaises(ApplicationError) as raised:
            self.limiter.acquire("198.51.100.1")
        self.assertEqual(
            raised.exception.category, ErrorCategory.LOCAL_RATE_LIMITED
        )
        self.assertEqual(raised.exception.retry_after, 1)

        other_ip_lease = self.limiter.acquire("198.51.100.2")
        lease.release()
        lease.release()
        other_ip_lease.release()

        self.assertEqual(
            self.registry.snapshot()["stream_active_connections"]["value"], 0
        )

    def test_invalid_limit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            StreamLimiter(0, self.registry)


if __name__ == "__main__":
    unittest.main()
