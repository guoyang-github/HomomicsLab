"""Tests for CodeAct cache."""

from homomics_lab.execution.code_cache import CodeActCache


def test_cache_round_trip(tmp_path):
    cache = CodeActCache(tmp_path)
    assert cache.get("task", "python") is None

    cache.put("task", "python", "print('hello')")
    assert cache.get("task", "python") == "print('hello')"


def test_cache_key_is_case_insensitive(tmp_path):
    cache = CodeActCache(tmp_path)
    cache.put("Task", "Python", "code")
    assert cache.get("task", "python") == "code"


def test_cache_context_affects_key(tmp_path):
    cache = CodeActCache(tmp_path)
    cache.put("task", "python", "code_a", context={"input": "a"})
    cache.put("task", "python", "code_b", context={"input": "b"})
    assert cache.get("task", "python", context={"input": "a"}) == "code_a"
    assert cache.get("task", "python", context={"input": "b"}) == "code_b"


def test_cache_clear(tmp_path):
    cache = CodeActCache(tmp_path)
    cache.put("task", "python", "code")
    assert cache.clear() == 1
    assert cache.get("task", "python") is None
