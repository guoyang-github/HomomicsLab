"""Tests for CodeAct foundation features: retrieval context + tool bindings."""


import pytest

from homomics_lab.agent.retrieval import RetrievedTool, RetrievalContext
from homomics_lab.skills.code_act import (
    _build_tool_module,
    _format_retrieval_context,
    execute_code,
    run_code_act,
)
from homomics_lab.tools.registry import ToolRegistry


@pytest.fixture
def tool_registry():
    registry = ToolRegistry()
    registry.register_builtin(
        name="echo_tool",
        description="Echo input back",
        handler=lambda message: f"echo: {message}",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
    )
    return registry


def test_format_retrieval_context_includes_tools_and_sops():
    ctx = RetrievalContext(
        query="qc",
        intent_type="single_cell_analysis",
        skills=[],
        tools=[RetrievedTool("echo_tool", "Echo input", {}, "low", "builtin")],
        data_sources=[],
        literature=[],
        sops=[{"name": "QC SOP", "template": {"min_genes": 200}}],
        anomalies=[],
        parameter_lore=[],
    )
    text = _format_retrieval_context(ctx)
    assert "echo_tool" in text
    assert "QC SOP" in text


def test_build_tool_module_exposes_registered_tools(tool_registry):
    module_source = _build_tool_module(tool_registry)
    assert "homomics_tool" in module_source
    assert "echo_tool" in module_source


def test_tool_module_invokes_tool_via_subprocess(tmp_path):
    """Test the generated tool helper invokes a real builtin tool via subprocess."""
    import importlib.util

    # Use a registry that only contains builtins so the subprocess sees the same tools.
    from homomics_lab.tools.builtin import register_all_builtin_tools
    from homomics_lab.tools.registry import ToolRegistry

    registry = ToolRegistry()
    register_all_builtin_tools(registry)

    module_path = tmp_path / "_homomics_tools.py"
    module_path.write_text(_build_tool_module(registry), encoding="utf-8")

    spec = importlib.util.spec_from_file_location("_homomics_tools", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.homomics_tool("file_list", directory=".")

    assert isinstance(result, list)
    assert not (isinstance(result, dict) and "error" in result)


@pytest.mark.asyncio
async def test_run_code_act_rule_based_without_llm(tmp_path):
    result = await run_code_act(
        task="QC filter single-cell h5ad",
        language="python",
        context={"input_path": str(tmp_path / "adata.h5ad")},
        working_dir=tmp_path,
        llm_client=None,
    )

    assert result["code"]
    assert result["exit_code"] == 0 or result["exit_code"] == -1


def test_execute_code_saves_artifact(tmp_path):
    code = "result = {'ok': True}"
    # We don't await because this is a quick sync check on artifact creation;
    # the function is async but the file write happens synchronously inside.
    import asyncio

    asyncio.run(execute_code(code, language="python", working_dir=tmp_path, save_artifact=True))

    assert (tmp_path / "__code_act_source__.py").exists()
    assert "result = {'ok': True}" in (tmp_path / "__code_act_source__.py").read_text()


@pytest.mark.asyncio
async def test_run_code_act_records_regression_baseline(tmp_path):
    await run_code_act(
        task="simple computation",
        language="python",
        context={},
        working_dir=tmp_path,
        llm_client=None,
    )

    baseline_dir = tmp_path / ".metadata" / "regression_baselines"
    assert baseline_dir.exists()
    assert any(baseline_dir.glob("codeact:*__python_default.json"))

