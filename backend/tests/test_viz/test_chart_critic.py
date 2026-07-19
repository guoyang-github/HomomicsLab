"""Tests for the VLM chart feedback loop (viz/chart_critic.py + orchestrator wiring).

All LLM interactions are mocked; no real services are started.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from PIL import Image

from homomics_lab.agent.orchestrator_executors import TaskExecutors
from homomics_lab.agent.turn_responder import ResultAssembler
from homomics_lab.tasks.models import TaskNode
from homomics_lab.viz.chart_critic import (
    ChartCritic,
    ChartCritique,
    collect_chart_paths,
    supports_vision_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_png(path: Path, blank: bool = False) -> Path:
    """Write a real PNG: uniform white (blank) or two-tone noise (content)."""
    size = (64, 64)
    if blank:
        img = Image.new("RGB", size, (255, 255, 255))
    else:
        img = Image.new("RGB", size, (255, 255, 255))
        # Left half black so pixel stddev is far above the blank threshold.
        for x in range(size[0] // 2):
            for y in range(size[1]):
                img.putpixel((x, y), (0, 0, 0))
    img.save(path, format="PNG")
    return path


class StubLLMClient:
    """Minimal LLM stub recording calls; can raise to simulate API failure."""

    def __init__(self, response: Optional[str] = None, exc: Optional[Exception] = None):
        self._response = response
        self._exc = exc
        self.calls: List[Any] = []

    def is_configured(self) -> bool:
        return True

    async def chat_completion(self, messages=None, **kwargs) -> str:
        self.calls.append(messages)
        if self._exc is not None:
            raise self._exc
        return self._response or ""


class QueueCritic:
    """ChartCritic stand-in returning queued critiques."""

    def __init__(self, queue: List[ChartCritique]):
        self._queue = list(queue)
        self.calls: List[str] = []

    def has_vision_capability(self) -> bool:
        return True

    async def critique(self, image_path, intent: str = "", context=None) -> ChartCritique:
        self.calls.append(str(image_path))
        if self._queue:
            return self._queue.pop(0)
        return ChartCritique(ok=True, source="vlm")


def _make_executors() -> tuple:
    """TaskExecutors over a stub orchestrator that captures progress states."""
    states: List[Any] = []
    orch = SimpleNamespace(
        skill_registry=None,
        _emit_progress=lambda **kw: states.append(kw),
        _report_progress=lambda state: states.append(state),
    )
    return TaskExecutors(orch), states


def _make_task() -> TaskNode:
    return TaskNode(id="t1", name="plot_umap", description="Plot a UMAP of clusters")


def _chart_events(states: List[Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for state in states:
        usage = getattr(state, "resource_usage", None) or {}
        for event in usage.get("agent_events", []):
            if event.get("type") == "chart_critique":
                events.append(event)
    return events


# ---------------------------------------------------------------------------
# Rule pre-checks
# ---------------------------------------------------------------------------


class TestRulePrecheck:
    @pytest.mark.asyncio
    async def test_zero_byte_file_flagged_without_llm(self, tmp_path):
        chart = tmp_path / "empty.png"
        chart.write_bytes(b"")
        client = StubLLMClient(response='{"ok": true}')
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(chart, intent="umap")
        assert critique.ok is False
        assert critique.issues == ["empty_chart"]
        assert critique.severity == "high"
        assert critique.source == "rule"
        assert client.calls == []  # rule decided; no LLM call made

    @pytest.mark.asyncio
    async def test_missing_file_flagged_without_llm(self, tmp_path):
        client = StubLLMClient(response='{"ok": true}')
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(tmp_path / "nope.png", intent="umap")
        assert critique.ok is False
        assert critique.severity == "high"
        assert critique.source == "rule"
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_blank_image_flagged_without_llm(self, tmp_path):
        chart = _write_png(tmp_path / "blank.png", blank=True)
        client = StubLLMClient(response='{"ok": true}')
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(chart, intent="umap")
        assert critique.ok is False
        assert "empty_chart" in critique.issues
        assert critique.severity == "high"
        assert critique.source == "rule"
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_non_blank_image_passes_rule_precheck(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response='{"ok": true, "issues": [], "severity": "none"}')
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.source == "vlm"
        assert len(client.calls) == 1  # rule inconclusive → VLM consulted


# ---------------------------------------------------------------------------
# Vision capability / silent degradation
# ---------------------------------------------------------------------------


class TestDegradation:
    def test_supports_vision_model_prefixes(self):
        assert supports_vision_model("gpt-4o") is True
        assert supports_vision_model("gpt-4o-mini") is True
        assert supports_vision_model("claude-3-5-sonnet-20241022") is True
        assert supports_vision_model("qwen-vl-max") is True
        assert supports_vision_model("deepseek-chat") is False
        assert supports_vision_model("qwen-turbo") is False
        assert supports_vision_model(None) is False
        assert supports_vision_model("") is False

    @pytest.mark.asyncio
    async def test_non_vision_model_degrades_silently(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response='{"ok": false, "severity": "high"}')
        critique = await ChartCritic(llm_client=client, model="deepseek-chat").critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.source == "skipped"
        assert client.calls == []  # never called: model cannot see images

    @pytest.mark.asyncio
    async def test_vlm_call_failure_degrades_to_ok(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(exc=RuntimeError("API down"))
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.source == "skipped"

    @pytest.mark.asyncio
    async def test_unparseable_vlm_response_degrades_to_ok(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response="I cannot inspect images.")
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.source == "skipped"

    @pytest.mark.asyncio
    async def test_no_llm_client_still_runs_rules(self, tmp_path):
        blank = _write_png(tmp_path / "blank.png", blank=True)
        critique = await ChartCritic(llm_client=None).critique(blank, intent="umap")
        assert critique.ok is False
        assert critique.source == "rule"
        content = _write_png(tmp_path / "content.png")
        critique = await ChartCritic(llm_client=None).critique(content, intent="umap")
        assert critique.ok is True
        assert critique.source == "skipped"


# ---------------------------------------------------------------------------
# Auto-detection: model resolved from the client, no enable switch
# ---------------------------------------------------------------------------


class TestAutoDetection:
    @pytest.mark.asyncio
    async def test_vision_model_from_client_activates_critic(self, tmp_path):
        # No explicit model: resolved from the client; vision-capable -> active.
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response='{"ok": true, "issues": [], "severity": "none"}')
        client._legacy_model = "gpt-4o-mini"
        critique = await ChartCritic(llm_client=client).critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.source == "vlm"
        assert len(client.calls) == 1

    @pytest.mark.asyncio
    async def test_text_only_model_from_client_skips_silently(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response='{"ok": false, "severity": "high"}')
        client._legacy_model = "deepseek-chat"
        critique = await ChartCritic(llm_client=client).critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.source == "skipped"
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_model_resolved_from_router_primary(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response='{"ok": true, "issues": [], "severity": "none"}')
        client.router = SimpleNamespace(primary_model="qwen-vl-max")
        critique = await ChartCritic(llm_client=client).critique(chart, intent="umap")
        assert critique.source == "vlm"
        assert len(client.calls) == 1

    @pytest.mark.asyncio
    async def test_no_model_anywhere_skips_silently(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response='{"ok": false, "severity": "high"}')
        critique = await ChartCritic(llm_client=client).critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.source == "skipped"
        assert client.calls == []


# ---------------------------------------------------------------------------
# VLM critique parsing
# ---------------------------------------------------------------------------


class TestVlmCritique:
    @pytest.mark.asyncio
    async def test_issues_parsed_from_vlm_json(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        payload = (
            '{"ok": false, "issues": ["garbled_labels", "legend_occlusion"], '
            '"severity": "high", "suggestion": "Use a font with CJK support and move the legend outside."}'
        )
        client = StubLLMClient(response=f"```json\n{payload}\n```")
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(chart, intent="细胞注释柱状图")
        assert critique.ok is False
        assert critique.issues == ["garbled_labels", "legend_occlusion"]
        assert critique.severity == "high"
        assert "legend" in critique.suggestion
        assert critique.source == "vlm"
        # Image was sent as an OpenAI-compatible base64 image_url part.
        content = client.calls[0][0]["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_ok_chart_parsed(self, tmp_path):
        chart = _write_png(tmp_path / "content.png")
        client = StubLLMClient(response='{"ok": true, "issues": [], "severity": "none", "suggestion": ""}')
        critique = await ChartCritic(llm_client=client, model="gpt-4o").critique(chart, intent="umap")
        assert critique.ok is True
        assert critique.severity == "none"
        assert critique.source == "vlm"


# ---------------------------------------------------------------------------
# collect_chart_paths
# ---------------------------------------------------------------------------


class TestCollectChartPaths:
    def test_collects_plot_path_and_output_files(self, tmp_path):
        png = _write_png(tmp_path / "a.png")
        csv = tmp_path / "b.csv"
        csv.write_text("x,y\n1,2\n", encoding="utf-8")
        result = {
            "plot_path": str(png),
            "output_files": [str(csv), str(png), str(tmp_path / "missing.png")],
        }
        charts = collect_chart_paths(result)
        assert charts == [png]  # de-duped, images only, must exist

    def test_nested_and_scalar_image_values(self, tmp_path):
        png = _write_png(tmp_path / "deep.png")
        result = {"stats": {"n": 3}, "figure": str(png)}
        assert collect_chart_paths(result) == [png]

    def test_empty_when_no_charts(self, tmp_path):
        assert collect_chart_paths({}) == []
        assert collect_chart_paths({"output_files": [str(tmp_path / "x.csv")]}) == []
        assert collect_chart_paths("not a dict") == []


# ---------------------------------------------------------------------------
# Orchestrator feedback loop (critique → one bounded repair → annotate)
# ---------------------------------------------------------------------------


def _enable_critic(monkeypatch, max_retries: int = 1):
    # The opt-in switch was removed in Phase 2 (chart critic is always on and
    # self-gates on vision capability); only the retry bound is configurable,
    # as the CHART_CRITIC_MAX_RETRIES module constant.
    monkeypatch.setattr(
        "homomics_lab.agent.orchestrator_executors.CHART_CRITIC_MAX_RETRIES",
        max_retries,
    )


def _vision_client(response: Optional[str] = None) -> StubLLMClient:
    """Stub LLM client whose resolved model is vision-capable."""
    client = StubLLMClient(response=response)
    client._legacy_model = "gpt-4o"
    return client


class TestChartFeedbackLoop:
    @pytest.mark.asyncio
    async def test_no_charts_is_passthrough(self, monkeypatch):
        _enable_critic(monkeypatch)
        executors, _ = _make_executors()
        result = {"success": True, "result": {"stats": {"n": 1}}}
        out = await executors._critique_charts_and_repair(_make_task(), {}, result, "prompt", _vision_client(), lambda p: None)
        assert out is result
        assert "chart_critiques" not in out

    @pytest.mark.asyncio
    async def test_ok_charts_emit_event_without_repair(self, monkeypatch, tmp_path):
        _enable_critic(monkeypatch)
        executors, states = _make_executors()
        png = _write_png(tmp_path / "a.png")
        result = {"success": True, "result": {"plot_path": str(png)}}
        critic = QueueCritic([ChartCritique(ok=True, source="vlm")])
        monkeypatch.setattr(
            "homomics_lab.agent.orchestrator_executors.ChartCritic",
            lambda llm_client=None: critic,
        )

        async def rerun(prompt):  # pragma: no cover - must not be called
            raise AssertionError("rerun must not be called for ok charts")

        out = await executors._critique_charts_and_repair(_make_task(), {}, result, "prompt", _vision_client(), rerun)
        assert out is result
        assert out["chart_critiques"][0]["ok"] is True
        events = _chart_events(states)
        assert len(events) == 1
        assert events[0]["success"] is True
        assert events[0]["artifacts"] == [str(png)]

    @pytest.mark.asyncio
    async def test_high_severity_triggers_single_repair(self, monkeypatch, tmp_path):
        _enable_critic(monkeypatch, max_retries=1)
        executors, states = _make_executors()
        png = _write_png(tmp_path / "a.png")
        fixed_png = _write_png(tmp_path / "a_fixed.png")
        result = {"success": True, "result": {"plot_path": str(png)}}
        repaired = {"success": True, "result": {"plot_path": str(fixed_png)}}
        bad = ChartCritique(
            ok=False,
            issues=["garbled_labels"],
            severity="high",
            suggestion="set a CJK-capable font",
            source="vlm",
        )
        critic = QueueCritic([bad, ChartCritique(ok=True, source="vlm")])
        monkeypatch.setattr(
            "homomics_lab.agent.orchestrator_executors.ChartCritic",
            lambda llm_client=None: critic,
        )
        rerun_prompts: List[str] = []

        async def rerun(prompt):
            rerun_prompts.append(prompt)
            return repaired

        out = await executors._critique_charts_and_repair(_make_task(), {}, result, "original prompt", _vision_client(), rerun)
        assert out is repaired  # repaired result replaces the original
        assert len(rerun_prompts) == 1  # exactly one repair attempt
        assert "original prompt" in rerun_prompts[0]
        assert "CJK-capable font" in rerun_prompts[0]  # suggestion fed back
        assert "chart_critique_note" not in out
        assert len(out["chart_critiques"]) == 2  # initial + post-repair
        assert len(_chart_events(states)) == 2
        assert len(critic.calls) == 2

    @pytest.mark.asyncio
    async def test_failed_repair_keeps_original_and_annotates(self, monkeypatch, tmp_path):
        _enable_critic(monkeypatch, max_retries=1)
        executors, _ = _make_executors()
        png = _write_png(tmp_path / "a.png")
        result = {"success": True, "result": {"plot_path": str(png)}}
        bad = ChartCritique(
            ok=False,
            issues=["empty_chart"],
            severity="high",
            suggestion="verify the plotted data is non-empty",
            source="rule",
        )
        # Both the initial and the post-repair critique come back bad.
        critic = QueueCritic([bad, bad])
        monkeypatch.setattr(
            "homomics_lab.agent.orchestrator_executors.ChartCritic",
            lambda llm_client=None: critic,
        )
        rerun_calls = 0

        async def rerun(prompt):
            nonlocal rerun_calls
            rerun_calls += 1
            return {"success": True, "result": {"plot_path": str(png)}}

        out = await executors._critique_charts_and_repair(_make_task(), {}, result, "prompt", _vision_client(), rerun)
        assert out is result  # original charts kept
        assert rerun_calls == 1  # bounded: no infinite loop
        note = out.get("chart_critique_note", "")
        assert note
        assert "empty_chart" in note

    @pytest.mark.asyncio
    async def test_repair_exception_keeps_original(self, monkeypatch, tmp_path):
        _enable_critic(monkeypatch, max_retries=1)
        executors, _ = _make_executors()
        png = _write_png(tmp_path / "a.png")
        result = {"success": True, "result": {"plot_path": str(png)}}
        bad = ChartCritique(
            ok=False,
            issues=["empty_chart"],
            severity="high",
            suggestion="fix",
            source="rule",
        )
        monkeypatch.setattr(
            "homomics_lab.agent.orchestrator_executors.ChartCritic",
            lambda llm_client=None: QueueCritic([bad]),
        )

        async def rerun(prompt):
            raise RuntimeError("sandbox exploded")

        out = await executors._critique_charts_and_repair(_make_task(), {}, result, "prompt", _vision_client(), rerun)
        assert out is result
        assert "chart_critique_note" in out

    @pytest.mark.asyncio
    async def test_critic_crash_degrades_to_original(self, monkeypatch, tmp_path):
        _enable_critic(monkeypatch)
        executors, _ = _make_executors()
        png = _write_png(tmp_path / "a.png")
        result = {"success": True, "result": {"plot_path": str(png)}}

        class CrashCritic:
            def has_vision_capability(self) -> bool:
                return True

            async def critique(self, *a, **k):
                raise RuntimeError("boom")

        monkeypatch.setattr(
            "homomics_lab.agent.orchestrator_executors.ChartCritic",
            lambda llm_client=None: CrashCritic(),
        )
        out = await executors._critique_charts_and_repair(_make_task(), {}, result, "prompt", _vision_client(), lambda p: None)
        assert out is result  # never a new failure point


# ---------------------------------------------------------------------------
# Summary annotation surfacing
# ---------------------------------------------------------------------------


class TestSummaryAnnotation:
    def test_envelopes_from_results_propagates_note(self, tmp_path):
        png = _write_png(tmp_path / "a.png")
        results = {
            "t1": {
                "status": "success",
                "result": {"plot_path": str(png)},
                "output_files": [str(png)],
                "chart_critique_note": "图表自动质检发现问题：blank",
            }
        }
        envelopes = ResultAssembler.envelopes_from_results(results)
        assert envelopes
        assert envelopes[0]["kind"] == "image"
        assert envelopes[0]["chart_critique_note"] == "图表自动质检发现问题：blank"

    def test_summarize_appends_note(self, tmp_path):
        png = _write_png(tmp_path / "a.png")
        envelopes = [
            {
                "kind": "image",
                "mime": "image/png",
                "name": png.name,
                "path": str(png),
                "chart_critique_note": "图表自动质检发现问题：blank",
            }
        ]
        md = ResultAssembler.summarize(envelopes, "plot something", None)
        assert "图表自动质检发现问题" in md
