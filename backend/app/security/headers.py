from __future__ import annotations

from collections.abc import Iterable

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.config import Settings

_ALLOWED_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_ALLOWED_HEADERS = frozenset({"content-type", "range", "x-correlation-id"})
_EXPOSED_HEADERS = (
    "Accept-Ranges, Content-Length, Content-Range, ETag, Last-Modified, "
    "Retry-After, X-Correlation-ID"
)


def content_security_policy(settings: Settings) -> str:
    connect_sources = ["'self'", *settings.cors_allowed_origins]
    return "; ".join(
        (
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' https: data:",
            "media-src 'self' https:",
            f"connect-src {' '.join(connect_sources)}",
        )
    )


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = _settings(scope)
        request_headers = _headers_dict(scope.get("headers", ()))
        origin = request_headers.get("origin")
        if (
            scope.get("method") == "OPTIONS"
            and origin is not None
            and "access-control-request-method" in request_headers
        ):
            await self._send_preflight(
                send,
                settings,
                request_headers,
                origin,
            )
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (
                        name if isinstance(name, bytes) else name.encode("latin-1"),
                        value if isinstance(value, bytes) else value.encode("latin-1"),
                    )
                    for name, value in message.get("headers", [])
                ]
                _set_header(
                    headers,
                    b"content-security-policy",
                    content_security_policy(settings).encode("latin-1"),
                )
                _set_header(headers, b"referrer-policy", b"no-referrer")
                _set_header(headers, b"x-content-type-options", b"nosniff")
                _set_header(headers, b"x-frame-options", b"DENY")
                _set_header(
                    headers,
                    b"permissions-policy",
                    b"accelerometer=(), camera=(), display-capture=(), "
                    b"fullscreen=(self), geolocation=(), microphone=()",
                )
                if scope.get("path", "").startswith("/api/session"):
                    _set_header(headers, b"cache-control", b"no-store")
                if origin is not None:
                    _append_vary(headers, b"Origin")
                    if origin in settings.cors_allowed_origins:
                        _set_header(
                            headers,
                            b"access-control-allow-origin",
                            origin.encode("latin-1"),
                        )
                        _set_header(
                            headers,
                            b"access-control-expose-headers",
                            _EXPOSED_HEADERS.encode("latin-1"),
                        )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_security_headers)

    async def _send_preflight(
        self,
        send: Send,
        settings: Settings,
        headers: dict[str, str],
        origin: str,
    ) -> None:
        method = headers["access-control-request-method"].upper()
        requested_headers = {
            value.strip().lower()
            for value in headers.get("access-control-request-headers", "").split(",")
            if value.strip()
        }
        allowed_origin = origin in settings.cors_allowed_origins
        allowed = (
            allowed_origin
            and method in _ALLOWED_METHODS
            and requested_headers <= _ALLOWED_HEADERS
        )
        response_headers: list[tuple[bytes, bytes]] = [
            (b"content-length", b"0"),
            (b"content-security-policy", content_security_policy(settings).encode("latin-1")),
            (b"referrer-policy", b"no-referrer"),
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (
                b"permissions-policy",
                b"accelerometer=(), camera=(), display-capture=(), "
                b"fullscreen=(self), geolocation=(), microphone=()",
            ),
            (b"vary", b"Origin"),
        ]
        if allowed_origin:
            response_headers.extend(
                (
                    (b"access-control-allow-origin", origin.encode("latin-1")),
                    (
                        b"access-control-allow-methods",
                        ", ".join(sorted(_ALLOWED_METHODS)).encode("latin-1"),
                    ),
                    (
                        b"access-control-allow-headers",
                        ", ".join(sorted(_ALLOWED_HEADERS)).encode("latin-1"),
                    ),
                    (b"access-control-max-age", b"600"),
                )
            )
        await send(
            {
                "type": "http.response.start",
                "status": 200 if allowed else 400,
                "headers": response_headers,
            }
        )
        await send({"type": "http.response.body", "body": b""})


def install_security_headers(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)


def _settings(scope: Scope) -> Settings:
    app = scope.get("app")
    settings = getattr(getattr(app, "state", None), "settings", None)
    if settings is None:
        raise RuntimeError("Application settings must be initialized before serving.")
    return settings


def _headers_dict(headers: Iterable[tuple[bytes, bytes]]) -> dict[str, str]:
    return {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in headers
    }


def _set_header(
    headers: list[tuple[bytes, bytes]], name: bytes, value: bytes
) -> None:
    headers[:] = [(key, old_value) for key, old_value in headers if key.lower() != name]
    headers.append((name, value))


def _append_vary(headers: list[tuple[bytes, bytes]], value: bytes) -> None:
    current = [
        old_value.decode("latin-1")
        for name, old_value in headers
        if name.lower() == b"vary"
    ]
    if any(existing.strip() == "*" for existing in current):
        return
    values = {
        item.strip().lower(): item.strip()
        for existing in current
        for item in existing.split(",")
        if item.strip()
    }
    values.setdefault(value.decode("latin-1").lower(), value.decode("latin-1"))
    _set_header(headers, b"vary", ", ".join(values.values()).encode("latin-1"))
