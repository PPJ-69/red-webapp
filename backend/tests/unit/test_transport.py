import asyncio
import unittest

import httpx2 as httpx

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.upstream.auth import AuthManager
from backend.app.upstream.transport import UpstreamTransport


class MockAsyncClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls = 0

    async def request(self, *args, **kwargs):
        self.calls += 1
        if self.calls > len(self.responses):
            raise AssertionError("No mock response left.")
        return self.responses[self.calls - 1]


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_429_retry_after_is_honored(self) -> None:
        transport = UpstreamTransport()
        transport._client = MockAsyncClient(
            [
                httpx.Response(429, text="slow down", headers={"Retry-After": "0"}),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        response = await transport.request("GET", "https://example.invalid")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(transport._client.calls, 2)

    async def test_non_retryable_codes_fail_immediately(self) -> None:
        transport = UpstreamTransport()
        transport._client = MockAsyncClient([httpx.Response(404, text="missing")])

        with self.assertRaises(ApplicationError) as ctx:
            await transport.request("GET", "https://example.invalid")

        self.assertEqual(ctx.exception.category, ErrorCategory.NOT_FOUND)

    async def test_timeout_raises_upstream_timeout_category(self) -> None:
        transport = UpstreamTransport()

        async def fail(*args, **kwargs):
            raise httpx.TimeoutException("timed out")

        transport._client = type("Client", (), {"request": fail})()

        with self.assertRaises(ApplicationError) as ctx:
            await transport.request("GET", "https://example.invalid")

        self.assertEqual(ctx.exception.category, ErrorCategory.UPSTREAM_TIMEOUT)

    async def test_auth_manager_refreshes_on_401(self) -> None:
        async def token_factory() -> str:
            await asyncio.sleep(0)
            return "fresh-token"

        manager = AuthManager(token_factory, ttl_seconds=60.0)
        transport = UpstreamTransport(auth_manager=manager)

        responses = iter(
            [
                httpx.Response(401),
                httpx.Response(200, text="ok"),
            ]
        )

        async def request(*args, **kwargs):
            return next(responses)

        transport._client = type("Client", (), {"request": request})()
        response = await transport.request("GET", "https://example.invalid")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(manager.token, "fresh-token")


if __name__ == "__main__":
    unittest.main()
