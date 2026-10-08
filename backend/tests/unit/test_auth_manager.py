import asyncio
import unittest

import httpx2 as httpx

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.upstream.auth import AuthManager


class AuthManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_401_refreshes_once_and_retries_success(self) -> None:
        tokens = iter(["expired-token", "fresh-token"])

        async def token_factory() -> str:
            return next(tokens)

        calls: list[str] = []

        async def request(token: str) -> httpx.Response:
            calls.append(token)
            if token == "expired-token":
                return httpx.Response(401)
            return httpx.Response(200)

        manager = AuthManager(token_factory, ttl_seconds=60.0)
        result = await manager.call(request)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(calls, ["expired-token", "fresh-token"])
        self.assertEqual(manager.token, "fresh-token")

    async def test_concurrent_calls_share_one_refresh(self) -> None:
        calls = 0

        async def token_factory() -> str:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.02)
            return f"token-{calls}"

        manager = AuthManager(token_factory, ttl_seconds=60.0)
        values = await asyncio.gather(manager.get_token(), manager.get_token())

        self.assertEqual(values, ["token-1", "token-1"])
        self.assertEqual(calls, 1)

    async def test_token_is_never_exposed_in_exception_text(self) -> None:
        async def token_factory() -> str:
            return "super-secret-token"

        manager = AuthManager(token_factory, ttl_seconds=60.0)

        async def request(_token: str) -> httpx.Response:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                f"Authorization failed for token {_token}.",
            )

        with self.assertRaises(ApplicationError) as ctx:
            await manager.call(request)

        self.assertNotIn("super-secret-token", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
