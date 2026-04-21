from __future__ import annotations

from pathlib import Path

import diskcache

from dep_age.config import CACHE_TTL_SECONDS


class Cache:
    def __init__(self, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(cache_dir))
        self._ttl = CACHE_TTL_SECONDS

    def get(self, key: str) -> str | None:
        val = self._cache.get(key)
        if isinstance(val, str):
            return val
        return None

    def set(self, key: str, value: str) -> None:
        self._cache.set(key, value, expire=self._ttl)

    def close(self) -> None:
        self._cache.close()
