"""Tests for the skill result cache (memoization)."""


import pytest

from homomics_lab.skills.cache import SkillCache


@pytest.fixture
def cache(tmp_path):
    return SkillCache(cache_dir=tmp_path)


class TestSkillCache:
    def test_get_missing_returns_none(self, cache):
        assert cache.get("missing", {"x": 1}) is None

    def test_put_and_get(self, cache):
        cache.put("add", {"a": 1, "b": 2}, {"sum": 3})
        assert cache.get("add", {"a": 1, "b": 2}) == {"sum": 3}

    def test_inputs_order_independent_key(self, cache):
        cache.put("add", {"a": 1, "b": 2}, {"sum": 3})
        assert cache.get("add", {"b": 2, "a": 1}) == {"sum": 3}

    def test_different_inputs_different_key(self, cache):
        cache.put("add", {"a": 1, "b": 2}, {"sum": 3})
        assert cache.get("add", {"a": 1, "b": 3}) is None

    def test_fingerprint_changes_key(self, cache):
        cache.put("add", {"a": 1, "b": 2}, {"sum": 3}, fingerprint="v1")
        assert cache.get("add", {"a": 1, "b": 2}, fingerprint="v1") == {"sum": 3}
        assert cache.get("add", {"a": 1, "b": 2}, fingerprint="v2") is None

    def test_invalidate(self, cache):
        cache.put("add", {"a": 1, "b": 2}, {"sum": 3})
        assert cache.invalidate("add", {"a": 1, "b": 2}) is True
        assert cache.get("add", {"a": 1, "b": 2}) is None
        assert cache.invalidate("add", {"a": 1, "b": 2}) is False

    def test_clear(self, cache):
        cache.put("a", {"x": 1}, 1)
        cache.put("b", {"x": 2}, 2)
        removed = cache.clear()
        assert removed == 2
        assert cache.get("a", {"x": 1}) is None
        assert cache.get("b", {"x": 2}) is None

    def test_compute_key_stability(self, cache):
        key1 = cache._compute_key("skill", {"a": 1, "b": 2}, "fp")
        key2 = cache._compute_key("skill", {"b": 2, "a": 1}, "fp")
        key3 = cache._compute_key("skill", {"a": 1, "b": 2}, "other")
        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 64  # sha256 hex digest

    def test_corrupted_cache_returns_none(self, cache):
        cache.put("add", {"a": 1, "b": 2}, {"sum": 3})
        key = cache._compute_key("add", {"a": 1, "b": 2}, "")
        path = cache.cache_dir / f"{key}.pkl"
        path.write_text("not a pickle")
        assert cache.get("add", {"a": 1, "b": 2}) is None

    def test_cache_result_reference_roundtrip(self, cache):
        from homomics_lab.data import ResultReference

        ref = ResultReference(inline=False, path="/tmp/result.parquet", format="parquet", size=1024)
        cache.put("big", {"path": "/tmp/result.parquet"}, ref)
        loaded = cache.get("big", {"path": "/tmp/result.parquet"})
        assert isinstance(loaded, ResultReference)
        assert loaded.path == "/tmp/result.parquet"
