"""Tiny in-memory TTL cache. Sufficient for single-instance Railway dev/prod."""
import time
from typing import Any, Callable


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def get_or_set(self, key: str, ttl_seconds: float, producer: Callable[[], Any]):
        cached = self.get(key)
        if cached is not None:
            return cached
        value = producer()
        self.set(key, value, ttl_seconds)
        return value


cache = TTLCache()
