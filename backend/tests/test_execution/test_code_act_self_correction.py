"""Tests for the CodeAct in-engine self-correction loop.

Covers run_code_act's repair cycle: a failed execution feeds the failing code
and its stderr back to the LLM, the repaired snippet is re-scanned and
re-executed, and only the final working snippet reaches the CodeAct cache.
"""

import pytest

from homomics_lab.config import settings
from homomics_lab.execution import code_act
from homomics_lab.execution.code_act import run_code_act
from homomics_lab.execution.code_cache import CodeActCache
from homomics_lab.llm_client import FakeLLMClient


class SequentialFakeLLM(FakeLLMClient):
    """Fake LLM that returns a different canned response per call."""

    def __init__(self, responses):
        super().__init__(response="")
        self._responses = list(responses)
        self.calls = 0

    async def chat_completion(self, messages, **kwargs):
        self.calls += 1
        if self._responses:
            return self._responses.pop(0)
        return ""


def _py(code: str) -> str:
    return f"```python\n{code}\n```"


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Give each test a cold, private CodeAct cache."""
    monkeypatch.setattr(settings, "codeact_cache_enabled", True)
    monkeypatch.setattr(settings, "codeact_cache_dir", tmp_path / "codeact_cache")


@pytest.mark.asyncio
async def test_self_correction_succeeds_on_second_attempt(tmp_path):
    """First execution fails with stderr; the LLM repair then succeeds."""
    llm = SequentialFakeLLM(
        [
            _py("raise ValueError('boom')"),
            _py("result = {'fixed': True}"),
        ]
    )
    result = await run_code_act(
        "flaky task",
        "python",
        context={},
        working_dir=tmp_path,
        llm_client=llm,
    )

    assert result["success"] is True
    assert result["attempts"] == 2
    assert result["result"]["fixed"] is True
    assert "fixed" in result["code"]
    assert len(result["fix_history"]) == 1
    assert result["fix_history"][0]["attempt"] == 1
    assert "boom" in result["fix_history"][0]["stderr"]
    # One generation call + one repair call.
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_self_correction_exhausts_max_fix_attempts(tmp_path):
    """When repairs keep failing, the run fails with the full attempt history."""
    llm = SequentialFakeLLM(
        [
            _py("raise ValueError('boom-1')"),
            _py("raise ValueError('boom-2')"),
            _py("raise ValueError('boom-3')"),
        ]
    )
    result = await run_code_act(
        "always failing task",
        "python",
        context={},
        working_dir=tmp_path,
        llm_client=llm,
        max_fix_attempts=2,
    )

    assert result["success"] is False
    # 1 initial execution + 2 repair iterations.
    assert result["attempts"] == 3
    assert len(result["fix_history"]) == 3
    assert [h["attempt"] for h in result["fix_history"]] == [1, 2, 3]
    assert all(h["stderr"] for h in result["fix_history"])
    assert "boom-3" in result["stderr"]
    # One generation call + two repair calls.
    assert llm.calls == 3


@pytest.mark.asyncio
async def test_identical_repair_stops_early(tmp_path):
    """An unchanged repair is not re-executed; the loop stops instead."""
    llm = SequentialFakeLLM(
        [
            _py("raise ValueError('same')"),
            _py("raise ValueError('same')"),
        ]
    )
    result = await run_code_act(
        "identical repair task",
        "python",
        context={},
        working_dir=tmp_path,
        llm_client=llm,
    )

    assert result["success"] is False
    # The identical repair is never executed, so only the initial attempt ran.
    assert result["attempts"] == 1
    assert len(result["fix_history"]) == 1
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_no_retry_without_llm(tmp_path, monkeypatch):
    """Without an LLM the engine keeps its single-attempt behavior."""
    execute_calls = []

    async def failing_execute(
        code, language, working_dir=None, tool_registry=None, save_artifact=True
    ):
        execute_calls.append(code)
        return {
            "success": False,
            "stdout": "",
            "stderr": "boom",
            "exit_code": 1,
            "result": {},
        }

    monkeypatch.setattr(code_act, "execute_code", failing_execute)

    result = await run_code_act(
        "offline task",
        "python",
        context={},
        working_dir=tmp_path,
        llm_client=None,
    )

    assert result["success"] is False
    assert result["attempts"] == 1
    assert len(execute_calls) == 1
    assert len(result["fix_history"]) == 1
    assert "boom" in result["fix_history"][0]["stderr"]


@pytest.mark.asyncio
async def test_safety_block_is_not_retried(tmp_path):
    """A HITL safety-gate block must not be routed around by regeneration."""
    llm = SequentialFakeLLM(
        [
            _py("import os\nos.system('echo hi')"),
            _py("result = {'fixed': True}"),
        ]
    )
    result = await run_code_act(
        "dangerous task",
        "python",
        context={},
        working_dir=tmp_path,
        llm_client=llm,
    )

    assert result["success"] is False
    assert result["attempts"] == 1
    assert result["fix_history"] == []
    assert "approval" in result["stderr"].lower()
    # No repair call was made.
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_cache_stores_only_final_working_code(tmp_path, monkeypatch):
    """The cache holds the repaired snippet, never the failing draft."""
    workdir = tmp_path / "work"
    llm = SequentialFakeLLM(
        [
            _py("raise ValueError('boom')"),
            _py("result = {'fixed': True}"),
        ]
    )
    result = await run_code_act(
        "cache me",
        "python",
        context={},
        working_dir=workdir,
        llm_client=llm,
    )
    assert result["success"] is True

    cache = CodeActCache(settings.codeact_cache_dir)
    cached = cache.get("cache me", "python", {})
    assert cached is not None
    assert "fixed" in cached
    assert "boom" not in cached

    # A second run hits the cache: no LLM call, single successful attempt.
    llm2 = SequentialFakeLLM([])
    result2 = await run_code_act(
        "cache me",
        "python",
        context={},
        working_dir=workdir,
        llm_client=llm2,
    )
    assert result2["success"] is True
    assert result2["attempts"] == 1
    assert result2["fix_history"] == []
    assert llm2.calls == 0


@pytest.mark.asyncio
async def test_failed_run_caches_nothing(tmp_path):
    """A run that exhausts all repairs must not poison the cache."""
    llm = SequentialFakeLLM(
        [
            _py("raise ValueError('boom-1')"),
            _py("raise ValueError('boom-2')"),
        ]
    )
    result = await run_code_act(
        "never cache me",
        "python",
        context={},
        working_dir=tmp_path,
        llm_client=llm,
        max_fix_attempts=1,
    )
    assert result["success"] is False

    cache = CodeActCache(settings.codeact_cache_dir)
    assert cache.get("never cache me", "python", {}) is None
