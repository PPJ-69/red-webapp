import json
import logging
import re
import sys
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import FastAPI, Request

correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="-")

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "session",
    "signature",
    "api_key",
    "private_key",
)
_SENSITIVE_QUERY_KEYS = {
    "auth",
    "auth_key",
    "awsaccesskeyid",
    "googleaccessid",
    "hdnea",
    "hdnts",
    "key",
    "sig",
    "signature",
    "token",
    "access_token",
    "expires",
    "expires_at",
    "policy",
    "credential",
    "x-amz-credential",
    "x-amz-signature",
    "x-amz-security-token",
}
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_HEADER_SECRET_PATTERN = re.compile(
    r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie)\s*[:=]\s*"
    r"[^\r\n]*"
)
_SESSION_VALUE_PATTERN = re.compile(
    r"(?i)\b(session(?:[_ -]?(?:id|token|data|state|contents?))?)\s*[:=]\s*"
    r"(['\"]?)[^\s,;'\"]+"
)
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def _sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9_]", "", key.casefold())
    return any(part.replace("_", "") in normalized.replace("_", "") for part in _SENSITIVE_KEY_PARTS)


def _redact_url(match: re.Match[str]) -> str:
    raw_url = match.group(0)
    trailing = ""
    while raw_url and raw_url[-1] in ".,)]}":
        trailing = raw_url[-1] + trailing
        raw_url = raw_url[:-1]
    try:
        parts = urlsplit(raw_url)
        netloc = parts.netloc
        if "@" in netloc:
            _, host = netloc.rsplit("@", 1)
            netloc = f"[REDACTED]@{host}"
        query = [
            (
                key,
                "[REDACTED]"
                if _sensitive_key(key)
                or key.casefold() in _SENSITIVE_QUERY_KEYS
                or key.casefold().startswith("x-amz-")
                else value,
            )
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit(
            (parts.scheme, netloc, parts.path, urlencode(query), parts.fragment)
        ) + trailing
    except ValueError:
        return "[REDACTED_URL]"


def redact_text(value: str) -> str:
    stripped = value.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            pass
        else:
            return json.dumps(redact_value(decoded), separators=(",", ":"))
    value = _HEADER_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    value = _SESSION_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    value = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    return _URL_PATTERN.sub(_redact_url, value)


def redact_value(value: Any, key: str | None = None) -> Any:
    if key is not None and _sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(child_key): redact_value(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value))


class JsonLogFormatter(logging.Formatter):
    _STANDARD_FIELDS = frozenset(
        (
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
        )
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in self._STANDARD_FIELDS and not key.startswith("_"):
                payload[key] = redact_value(value, key)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("red_webapp")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)
    return logger


def log_event(event: str, **fields: Any) -> None:
    logger = configure_logging()
    logger.info(
        "%s",
        redact_text(event),
        extra={
            **{key: redact_value(value, key) for key, value in fields.items()},
            "correlation_id": correlation_id_context.get(),
        },
    )


def _status_category(status_code: int) -> str:
    if status_code < 400:
        return "success"
    if status_code < 500:
        return "client_error"
    return "server_error"


def install_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        correlation_id = str(uuid4())
        request.state.correlation_id = correlation_id
        token = correlation_id_context.set(correlation_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            route = request.scope.get("route")
            operation = getattr(route, "path", request.url.path)
            try:
                log_event(
                    "http_request_completed",
                    operation=operation,
                    request_type=request.method,
                    status=status_code,
                    status_category=getattr(
                        request.state,
                        "error_category",
                        _status_category(status_code),
                    ),
                    duration_ms=round((time.perf_counter() - started) * 1000, 3),
                )
            finally:
                correlation_id_context.reset(token)
