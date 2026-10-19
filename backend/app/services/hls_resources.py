from __future__ import annotations

from dataclasses import dataclass
import secrets
import time

from backend.app.domain.enums import ErrorCategory
from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import InternalSourceTarget


@dataclass(frozen=True)
class HlsResource:
    media_id: str
    target: InternalSourceTarget
    is_playlist: bool
    depth: int
    expires_at: float


class HlsResourceRegistry:
    def __init__(
        self,
        *,
        ttl_seconds: float = 3600.0,
        max_resources: int = 10_000,
    ) -> None:
        if ttl_seconds <= 0 or max_resources < 1:
            raise ValueError("HLS resource limits must be positive.")
        self._ttl_seconds = ttl_seconds
        self._max_resources = max_resources
        self._resources: dict[str, HlsResource] = {}

    def register(
        self,
        media_id: str,
        target: InternalSourceTarget,
        *,
        is_playlist: bool,
        depth: int,
    ) -> str:
        return self.register_many(
            media_id, [(target, is_playlist, depth)]
        )[0]

    def register_many(
        self,
        media_id: str,
        resources: list[tuple[InternalSourceTarget, bool, int]],
    ) -> list[str]:
        self._purge_expired()
        if len(self._resources) + len(resources) > self._max_resources:
            raise ApplicationError(
                ErrorCategory.PROVIDER_UNAVAILABLE,
                "The HLS resource limit has been reached.",
            )
        expires_at = time.monotonic() + self._ttl_seconds
        tokens = [secrets.token_urlsafe(24) for _ in resources]
        for token, (target, is_playlist, depth) in zip(
            tokens, resources, strict=True
        ):
            self._resources[token] = HlsResource(
                media_id=media_id,
                target=target,
                is_playlist=is_playlist,
                depth=depth,
                expires_at=expires_at,
            )
        return tokens

    def resolve(self, media_id: str, token: str) -> HlsResource:
        self._purge_expired()
        resource = self._resources.get(token)
        if resource is None or resource.media_id != media_id:
            raise ApplicationError(
                ErrorCategory.NOT_FOUND,
                "The HLS resource is unavailable.",
            )
        return resource

    def clear(self) -> None:
        self._resources.clear()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [
            token
            for token, resource in self._resources.items()
            if resource.expires_at <= now
        ]
        for token in expired:
            self._resources.pop(token, None)
