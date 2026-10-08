from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from typing import Any

import httpx2 as httpx

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError, classify_upstream_status

from .auth import AuthManager


class UpstreamTransport:
    def __init__(
        self,
        *,
        auth_manager: AuthManager | None = None,
        timeout: httpx.Timeout = httpx.Timeout(5.0, connect=5.0, read=15.0, write=15.0, pool=5.0),
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
        jitter_seconds: float = 0.25,
    ) -> None:
        self.auth_manager = auth_manager
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.jitter_seconds = jitter_seconds
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _sleep_for_retry(self, attempt: int) -> float:
        delay = self.backoff_base_seconds * (2**attempt)
        return delay + random.uniform(0.0, self.jitter_seconds)

    @staticmethod
    def _parse_retry_after(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return max(0, int(value))
        except ValueError:
            return None

    @staticmethod
    def _redact_value(value: str) -> str:
        if not value:
            return value
        lowered = value.lower()
        if "token" in lowered or "secret" in lowered or "auth" in lowered:
            return "[REDACTED]"
        return value

    def _coerce_error_message(self, text: Any) -> str:
        if text is None:
            return "Upstream request failed."
        if isinstance(text, str):
            redacted = self._redact_value(text)
            return redacted[:200] or "Upstream request failed."
        return "Upstream request failed."

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        timeout: httpx.Timeout | None = None,
    ) -> httpx.Response:
        attempts = self.max_retries + 1
        last_response: httpx.Response | None = None
        last_exception: Exception | None = None

        for attempt in range(attempts):
            request_headers = dict(headers or {})
            if self.auth_manager is not None and "Authorization" not in request_headers:
                token = await self.auth_manager.get_token()
                request_headers["Authorization"] = f"Bearer {token}"

            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=request_headers,
                    params=params,
                    json=json,
                    timeout=timeout or self.timeout,
                )
            except httpx.TimeoutException as exc:  # pragma: no cover - explicit failure branch
                last_exception = exc
                if attempt >= self.max_retries:
                    raise ApplicationError(
                        ErrorCategory.UPSTREAM_TIMEOUT,
                        "The upstream request timed out.",
                    ) from exc
                await asyncio.sleep(self._sleep_for_retry(attempt))
                continue
            except httpx.HTTPError as exc:
                last_exception = exc
                if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
                    category = ErrorCategory.PROVIDER_UNAVAILABLE
                    message = "The upstream provider is unavailable."
                elif isinstance(exc, (httpx.ReadError, httpx.WriteError)):
                    category = ErrorCategory.CONNECTION_INTERRUPTED
                    message = "The upstream connection was interrupted."
                else:
                    category = ErrorCategory.PROVIDER_ERROR
                    message = "The upstream provider returned an error."
                raise ApplicationError(category, message) from exc

            last_response = response
            status_code = response.status_code

            if status_code == 401 and self.auth_manager is not None and attempt == 0:
                await self.auth_manager.refresh()
                continue

            if status_code in {400, 404, 416}:
                raise ApplicationError(
                    classify_upstream_status(status_code),
                    self._coerce_error_message(response.text),
                    retry_after=self._parse_retry_after(response.headers.get("Retry-After")),
                )

            if status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                delay = retry_after if retry_after is not None else self._sleep_for_retry(attempt)
                await asyncio.sleep(delay)
                continue

            if status_code >= 400:
                raise ApplicationError(
                    classify_upstream_status(status_code),
                    self._coerce_error_message(response.text),
                    retry_after=self._parse_retry_after(response.headers.get("Retry-After")),
                )

            return response

        if last_response is not None:
            status_code = last_response.status_code
            raise ApplicationError(
                classify_upstream_status(status_code),
                self._coerce_error_message(last_response.text),
                retry_after=self._parse_retry_after(last_response.headers.get("Retry-After")),
            )
        if last_exception is not None:
            raise ApplicationError(
                ErrorCategory.PROVIDER_UNAVAILABLE,
                "The upstream provider is unavailable.",
            ) from last_exception
        raise ApplicationError(
            ErrorCategory.PROVIDER_UNAVAILABLE,
            "The upstream provider is unavailable.",
        )

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> httpx.Response:
        return await self.request("GET", url, headers=headers, params=params, timeout=timeout)

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: Any = None,
        timeout: httpx.Timeout | None = None,
    ) -> httpx.Response:
        return await self.request("POST", url, headers=headers, json=json, timeout=timeout)
