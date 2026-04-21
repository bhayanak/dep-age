"""Tests for cache module."""

from pathlib import Path

from dep_age.enrichment.cache import Cache


class TestCache:
    def test_set_and_get(self, tmp_path: Path):
        cache = Cache(tmp_path / "test-cache")
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        cache.close()

    def test_get_missing(self, tmp_path: Path):
        cache = Cache(tmp_path / "test-cache")
        assert cache.get("nonexistent") is None
        cache.close()

    def test_overwrite(self, tmp_path: Path):
        cache = Cache(tmp_path / "test-cache")
        cache.set("key1", "first")
        cache.set("key1", "second")
        assert cache.get("key1") == "second"
        cache.close()
