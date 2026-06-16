"""Tests for the CodeAct engine."""

from pathlib import Path

import pytest

from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.skills.code_act import (
    _build_python_wrapper,
    execute_code,
    generate_code,
    run_code_act,
)


class TestGenerateCode:
    def test_generate_load_code(self):
        code = generate_code("load pbmc h5ad file", "python", {})
        assert "sc.read_h5ad" in code
        assert "adata.n_obs" in code

    def test_generate_qc_code(self):
        code = generate_code("run QC and filter mito genes", "python", {"input_path": "in.h5ad"})
        assert "calculate_qc_metrics" in code
        assert "pct_counts_mt" in code

    def test_generate_normalize_code(self):
        code = generate_code("normalize counts", "python", {})
        assert "normalize_total" in code
        assert "log1p" in code

    def test_generate_bash_code(self):
        code = generate_code("list files", "bash", {"input_path": "/tmp/data.txt"})
        assert "ls -la" in code
        assert "/tmp" in code

    def test_generate_unsupported_language(self):
        code = generate_code("do something", "cpp", {})
        assert "Unsupported language" in code


class TestGenerateCodeWithLLM:
    def test_generate_code_uses_llm_when_configured(self):
        llm = FakeLLMClient(
            response="```python\nresult = {'llm': True}\n```"
        )
        code = generate_code("any task", "python", {}, llm_client=llm)
        assert "result = {'llm': True}" in code

    def test_generate_code_falls_back_when_llm_not_configured(self):
        # Passing None simulates no LLM; rule-based fallback should be used.
        code = generate_code("load h5ad", "python", {}, llm_client=None)
        assert "sc.read_h5ad" in code

    @pytest.mark.asyncio
    async def test_run_code_act_uses_llm_code(self, tmp_path):
        llm = FakeLLMClient(
            response="```python\nprint('from llm')\nresult = {'value': 99}\n```"
        )
        result = await run_code_act(
            "custom task",
            "python",
            context={},
            working_dir=tmp_path,
            llm_client=llm,
        )
        assert result["success"] is True
        assert "from llm" in result["stdout"]
        assert result["result"]["value"] == 99


class TestExecuteCode:
    @pytest.mark.asyncio
    async def test_execute_python_success(self, tmp_path):
        code = "result = {'value': 42}\nprint('hello')"
        exec_result = await execute_code(code, "python", working_dir=tmp_path)

        assert exec_result["success"] is True
        assert "hello" in exec_result["stdout"]
        assert exec_result["result"].get("value") == 42
        assert (tmp_path / "__skill_result__.json").exists()

    @pytest.mark.asyncio
    async def test_execute_bash_success(self, tmp_path):
        code = "echo 'bash-ok'\ntrue"
        exec_result = await execute_code(code, "bash", working_dir=tmp_path)

        assert exec_result["success"] is True
        assert "bash-ok" in exec_result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_unsupported_language(self, tmp_path):
        exec_result = await execute_code("x", "cpp", working_dir=tmp_path)

        assert exec_result["success"] is False
        assert "Unsupported language" in exec_result["stderr"]

    @pytest.mark.asyncio
    async def test_execute_timeout(self, tmp_path):
        code = "import time\ntime.sleep(100)"
        exec_result = await execute_code(code, "python", working_dir=tmp_path, timeout_seconds=0.1)

        assert exec_result["success"] is False
        assert "timed out" in exec_result["stderr"].lower()


class TestRunCodeAct:
    @pytest.mark.asyncio
    async def test_run_code_act_generic(self, tmp_path):
        result = await run_code_act("summarize context", "python", context={"x": 1}, working_dir=tmp_path)

        assert "code" in result
        assert result["success"] is True
        assert "Context" in result["stdout"]

    @pytest.mark.asyncio
    async def test_run_code_act_scanpy_load(self, tmp_path):

        repo_root = Path(__file__).resolve().parents[3]
        mock_path = repo_root / "backend" / "data" / "mock_pbmc.h5ad"
        if not mock_path.exists():
            pytest.skip("mock_pbmc.h5ad not available")

        result = await run_code_act(
            "load pbmc h5ad",
            "python",
            context={"input_path": str(mock_path)},
            working_dir=tmp_path,
        )

        assert result["success"] is True
        assert "cells" in result["result"]
        assert result["result"]["cells"] > 0


def test_build_python_wrapper():
    wrapper = _build_python_wrapper("x = 1")
    assert "x = 1" in wrapper
    assert "__skill_result__.json" in wrapper
    assert "if 'result' not in locals()" in wrapper
