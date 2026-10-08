from __future__ import annotations

import time
from typing import Generic, TypeVar

T = TypeVar("T")


class SourceCache(Generic[T]):
    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[tuple[str, str], tuple[float, T]] = {}

    def get(self, key: tuple[str, str]) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: tuple[str, str], value: T) -> None:
        self._entries[key] = (time.monotonic() + self.ttl_seconds, value)

    def delete(self, key: tuple[str, str]) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()
