from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError

T = TypeVar("T")


class AuthManager:
    def __init__(
        self,
        token_factory: Callable[[], Awaitable[str]],
        *,
        ttl_seconds: float = 300.0,
        refresh_leeway_seconds: float = 30.0,
    ) -> None:
        self._token_factory = token_factory
        self._ttl_seconds = ttl_seconds
        self._refresh_leeway_seconds = refresh_leeway_seconds
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._refresh_lock = asyncio.Lock()

    @property
    def token(self) -> str | None:
        return self._token

    def _has_valid_token(self) -> bool:
        return self._token is not None and time.monotonic() < (
            self._expires_at - self._refresh_leeway_seconds
        )

    async def get_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh and self._has_valid_token():
            return self._token

        async with self._refresh_lock:
            if not force_refresh and self._has_valid_token():
                return self._token
            token = await self._token_factory()
            self._token = token
            self._expires_at = time.monotonic() + self._ttl_seconds
            return token

    async def refresh(self) -> str:
        return await self.get_token(force_refresh=True)

    async def call(
        self,
        request_fn: Callable[[str], Awaitable[T]],
        *,
        refresh_on_401: bool = True,
    ) -> T:
        token = await self.get_token()
        result = await request_fn(token)
        if not refresh_on_401:
            return result

        status_code = getattr(result, "status_code", None)
        if status_code == 401:
            token = await self.refresh()
            result = await request_fn(token)
        return result

    async def __call__(
        self,
        request_fn: Callable[[str], Awaitable[T]],
        *,
        refresh_on_401: bool = True,
    ) -> T:
        return await self.call(request_fn, refresh_on_401=refresh_on_401)


class UpstreamAuthError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED, message)
