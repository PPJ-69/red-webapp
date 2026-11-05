from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from backend.app.config import (
    ConfigurationError,
    Settings,
    UpstreamProviderMode,
)
from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError

from .auth import AuthManager
from .redgifs_client import RedgifsClient


def _token_reader(token_file: Path) -> Callable[[], Awaitable[str]]:
    async def read_token() -> str:
        try:
            token = token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ApplicationError(
                ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                "The configured provider token file is unavailable.",
            ) from exc
        if not token or token.lower().startswith("bearer "):
            raise ApplicationError(
                ErrorCategory.UPSTREAM_AUTHENTICATION_FAILED,
                "The configured provider token file must contain a raw token.",
            )
        return token

    return read_token


async def create_upstream_provider(
    settings: Settings,
) -> RedgifsClient | None:
    if settings.upstream_provider is UpstreamProviderMode.DISABLED:
        return None
    if settings.upstream_provider is not UpstreamProviderMode.REDGIFS:
        raise ConfigurationError("The selected upstream provider is unsupported.")
    auth_manager = (
        AuthManager(_token_reader(settings.redgifs_token_file))
        if settings.redgifs_token_file is not None
        else None
    )
    provider = RedgifsClient(auth_manager=auth_manager)
    try:
        await provider.authenticate()
    except Exception:
        await provider.aclose()
        raise
    return provider
