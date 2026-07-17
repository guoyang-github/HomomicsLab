"""ExplorationEngine — hypothesis-driven exploration for open research questions.

Inspired by the academic frontier (CellVoyager's exploration blueprint and the
Google co-scientist hypothesis generation-review loop), this module adds an
upstream "exploration mode" on top of the existing execution stack:

  1. ``generate_blueprint`` — LLM generates 2..N testable hypotheses for an
     open-ended research question, each with a concrete verification analysis
     ("test whether X holds: run analysis Y on the data; if Z, supported").
  2. ``blueprint_to_task_tree`` — each hypothesis becomes a task branch in a
     standard ``TaskTree`` so verification runs through the *existing*
     Orchestrator / CodeAct base; no new executor is introduced.
  3. ``critique_result`` — LLM self-critique of each branch result, yielding
     ``supported | refuted | inconclusive`` plus an optional single follow-up
     hypothesis (depth-capped to prevent unbounded exploration).
  4. ``synthesize`` — a deterministic Markdown report with a
     hypothesis-evidence-conclusion table and suggested next steps.

The engine never executes anything itself: execution is always delegated to
an injected executor callable backed by the existing Orchestrator.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from homomics_lab.agent.plan.display_plan import DisplayStep
from homomics_lab.config import settings
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)

VERDICTS = {"supported", "refuted", "inconclusive"}

# Executor contract: run one exploration task through the existing execution
# stack and return the task's result dict (or None when it produced nothing).
ExplorationExecutor = Callable[[TaskNode], Awaitable[Optional[Dict[str, Any]]]]


@dataclass
class Hypothesis:
    """A single testable hypothesis with its verification plan and verdict."""

    id: str
    statement: str
    verification: str  # concrete analysis used to test the hypothesis
    success_signal: str = ""  # observation that would support the hypothesis
    depth: int = 1  # blueprint hypotheses are depth 1; follow-ups go deeper
    parent_id: Optional[str] = None
    verdict: Optional[str] = None  # supported | refuted | inconclusive
    confidence: float = 0.0
    reasoning: str = ""
    result_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Hypothesis":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dict(data).items() if k in known})


@dataclass
class ExplorationBlueprint:
    """The hypothesis set generated for an open research question."""

    question: str
    hypotheses: List[Hypothesis] = field(default_factory=list)
    data_context: str = ""
    file_paths: List[str] = field(default_factory=list)
    # Follow-up hypotheses appended during the critique loop (depth >= 2).
    follow_ups: List[Hypothesis] = field(default_factory=list)

    def all_hypotheses(self) -> List[Hypothesis]:
        """Return blueprint hypotheses plus any executed follow-ups, in order."""
        return [*self.hypotheses, *self.follow_ups]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "data_context": self.data_context,
            "file_paths": list(self.file_paths),
            "follow_ups": [h.to_dict() for h in self.follow_ups],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExplorationBlueprint":
        data = dict(data or {})
        return cls(
            question=data.get("question", ""),
            hypotheses=[Hypothesis.from_dict(h) for h in data.get("hypotheses", [])],
            data_context=data.get("data_context", ""),
            file_paths=list(data.get("file_paths", []) or []),
            follow_ups=[Hypothesis.from_dict(h) for h in data.get("follow_ups", [])],
        )


@dataclass
class CritiqueResult:
    """Self-critique verdict for one hypothesis branch."""

    verdict: str  # supported | refuted | inconclusive
    confidence: float = 0.0
    reasoning: str = ""
    follow_up: Optional[Hypothesis] = None


@dataclass
class ExplorationReport:
    """Final outcome of an exploration run."""

    question: str
    hypotheses: List[Hypothesis]
    markdown: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "markdown": self.markdown,
        }


def _extract_json_object(raw: str) -> Dict[str, Any]:
    """Parse the first JSON object from an LLM response.

    Tolerates Markdown code fences and surrounding prose; raises ValueError
    when no object can be parsed.
    """
    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in LLM response")
    return json.loads(text[start : end + 1])


class ExplorationEngine:
    """Generate, verify and critique hypothesis-driven exploration blueprints."""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        max_hypotheses: Optional[int] = None,
        max_depth: Optional[int] = None,
    ):
        self._llm_client = llm_client
        self.max_hypotheses = max(
            2, max_hypotheses or settings.exploration_max_hypotheses
        )
        self.max_depth = max(1, max_depth or settings.exploration_max_depth)

    # ------------------------------------------------------------------
    # a. Blueprint generation
    # ------------------------------------------------------------------
    async def generate_blueprint(
        self,
        question: str,
        data_context: str = "",
        file_paths: Optional[List[str]] = None,
    ) -> Optional[ExplorationBlueprint]:
        """Generate 2..max_hypotheses testable hypotheses via the LLM.

        Returns ``None`` when the LLM is unavailable or its output cannot be
        parsed, so callers can fall back to the standard workflow path.
        """
        client = self._llm_client
        if client is None or not client.is_configured():
            return None

        prompt = self._build_blueprint_prompt(question, data_context)
        try:
            raw = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior computational biology researcher who "
                            "designs hypothesis-driven exploration plans."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=2000,
            )
            data = _extract_json_object(raw)
        except Exception:
            logger.warning("Exploration blueprint generation failed", exc_info=True)
            return None

        hypotheses = self._parse_hypotheses(data)
        if not hypotheses:
            return None
        return ExplorationBlueprint(
            question=question,
            hypotheses=hypotheses,
            data_context=data_context,
            file_paths=list(file_paths or []),
        )

    def _build_blueprint_prompt(self, question: str, data_context: str) -> str:
        return (
            "A user posed an open-ended research question about their dataset.\n\n"
            f"Question: {question}\n\n"
            f"Available data: {data_context or 'data files attached to the project'}\n\n"
            f"Generate 2-{self.max_hypotheses} testable hypotheses that together "
            "address the question from different angles. For each hypothesis provide:\n"
            "- statement: a specific, falsifiable hypothesis (one sentence)\n"
            "- verification: ONE concrete analysis to run on the data to test it "
            "(what to compute or plot)\n"
            "- success_signal: the observation that would support the hypothesis "
            "('if X, then supported')\n\n"
            "Rules:\n"
            "- Each verification must be a single concrete analysis step.\n"
            "- Hypotheses must be mutually distinct.\n"
            "- Use the same language as the question for statement/verification/"
            "success_signal.\n\n"
            'Return ONLY a JSON object: {"hypotheses": [{"statement": "...", '
            '"verification": "...", "success_signal": "..."}]}'
        )

    def _parse_hypotheses(self, data: Dict[str, Any]) -> List[Hypothesis]:
        """Parse and normalize the LLM blueprint payload."""
        raw_items = data.get("hypotheses")
        if not isinstance(raw_items, list):
            return []
        hypotheses: List[Hypothesis] = []
        for item in raw_items[: self.max_hypotheses]:
            if not isinstance(item, dict):
                continue
            statement = str(item.get("statement") or "").strip()
            verification = str(item.get("verification") or "").strip()
            if not statement or not verification:
                continue
            hypotheses.append(
                Hypothesis(
                    id=f"h{len(hypotheses) + 1}",
                    statement=statement,
                    verification=verification,
                    success_signal=str(item.get("success_signal") or "").strip(),
                    depth=1,
                )
            )
        return hypotheses

    # ------------------------------------------------------------------
    # b. Blueprint -> TaskTree (executed by the existing Orchestrator)
    # ------------------------------------------------------------------
    def blueprint_to_task_tree(self, blueprint: ExplorationBlueprint) -> TaskTree:
        """Convert a blueprint into a standard task tree.

        Each hypothesis becomes an independent branch (no inter-task
        dependencies). Tasks bind no skill, so they execute through the
        CodeAct base like any other skill-less task.
        """
        tasks = [
            self.hypothesis_to_task(blueprint, hypothesis)
            for hypothesis in blueprint.hypotheses
        ]
        tree = TaskTree(tasks=tasks)
        tree.display_steps = [
            DisplayStep(
                id=f"explore_{hypothesis.id}",
                description=(
                    f"{self._display_label(hypothesis)}：{hypothesis.statement}"
                ),
                phase_type="exploration",
                analysis_type="exploration",
            )
            for hypothesis in blueprint.hypotheses
        ]
        return tree

    def hypothesis_to_task(
        self, blueprint: ExplorationBlueprint, hypothesis: Hypothesis
    ) -> TaskNode:
        """Build the single verification task for one hypothesis."""
        parameters: Dict[str, Any] = {
            "exploration_hypothesis_id": hypothesis.id,
            "hypothesis": hypothesis.statement,
            "verification": hypothesis.verification,
            "success_signal": hypothesis.success_signal,
            "user_request": (
                f"{blueprint.question}\n\n"
                f"检验假设：{hypothesis.statement}\n"
                f"验证分析：{hypothesis.verification}\n"
                f"支持判据：若 {hypothesis.success_signal} 则支持该假设"
            ),
            "data_context": blueprint.data_context,
        }
        for idx, path in enumerate(blueprint.file_paths or [], start=1):
            parameters[f"input_file_{idx}"] = path
        return TaskNode(
            id=f"explore_{hypothesis.id}",
            name=self._display_label(hypothesis),
            description=(
                f"检验假设「{hypothesis.statement}」是否成立："
                f"对数据做如下分析——{hypothesis.verification}；"
                f"若 {hypothesis.success_signal} 则支持该假设。"
            ),
            phase="exploration",
            parameters=parameters,
            derivation="exploration",
        )

    @staticmethod
    def _display_label(hypothesis: Hypothesis) -> str:
        """Human-readable milestone label, e.g. '假设 1 验证' / '假设 1 后续验证'."""
        match = re.match(r"h(\d+)(?:_f(\d+))?$", hypothesis.id)
        ordinal = match.group(1) if match else hypothesis.id
        if hypothesis.depth <= 1:
            return f"假设 {ordinal} 验证"
        return f"假设 {ordinal} 后续验证"

    # ------------------------------------------------------------------
    # c. Self-critique
    # ------------------------------------------------------------------
    async def critique_result(
        self,
        hypothesis: Hypothesis,
        result: Optional[Dict[str, Any]],
    ) -> CritiqueResult:
        """Let the LLM judge whether a branch result supports the hypothesis.

        On any failure the verdict degrades to ``inconclusive`` rather than
        raising, so the exploration loop always terminates with a report.
        """
        if result is None:
            return CritiqueResult(
                verdict="inconclusive",
                confidence=0.0,
                reasoning="验证分析未产生可用结果，无法判定。",
            )
        client = self._llm_client
        if client is None or not client.is_configured():
            return CritiqueResult(
                verdict="inconclusive",
                confidence=0.0,
                reasoning="LLM 不可用，未能进行假设评判。",
            )

        try:
            result_text = json.dumps(result, ensure_ascii=False, default=str)[:3000]
        except Exception:
            result_text = str(result)[:3000]
        prompt = (
            f"Hypothesis: {hypothesis.statement}\n"
            f"Verification analysis: {hypothesis.verification}\n"
            f"Support criterion: if {hypothesis.success_signal}, the hypothesis "
            "is supported.\n\n"
            f"Analysis result (possibly truncated):\n{result_text}\n\n"
            "Judge whether the result supports the hypothesis. Be critical: only "
            "mark 'supported' when the evidence directly matches the support "
            "criterion.\n"
            "Return ONLY a JSON object:\n"
            "{\n"
            '  "verdict": "supported" | "refuted" | "inconclusive",\n'
            '  "confidence": <float between 0.0 and 1.0>,\n'
            '  "reasoning": "<brief evidence-based explanation>",\n'
            '  "follow_up": null or {"statement": "...", "verification": "...", '
            '"success_signal": "..."}\n'
            "}\n"
            "Propose at most ONE follow_up hypothesis, and only when a deeper "
            "question directly implied by this result deserves one more analysis; "
            "otherwise use null. Use the same language as the hypothesis."
        )
        try:
            raw = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a critical reviewer evaluating whether an "
                            "analysis result supports a hypothesis."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            data = _extract_json_object(raw)
        except Exception:
            logger.warning("Exploration critique failed", exc_info=True)
            return CritiqueResult(
                verdict="inconclusive",
                confidence=0.0,
                reasoning="评判过程出错，无法判定。",
            )

        verdict = str(data.get("verdict") or "").strip().lower()
        if verdict not in VERDICTS:
            verdict = "inconclusive"
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))
        follow_up = self._parse_follow_up(data.get("follow_up"), parent=hypothesis)
        return CritiqueResult(
            verdict=verdict,
            confidence=confidence,
            reasoning=str(data.get("reasoning") or "").strip(),
            follow_up=follow_up,
        )

    def _parse_follow_up(self, data: Any, parent: Hypothesis) -> Optional[Hypothesis]:
        """Parse an optional follow-up hypothesis from the critique payload."""
        if not isinstance(data, dict):
            return None
        statement = str(data.get("statement") or "").strip()
        verification = str(data.get("verification") or "").strip()
        if not statement or not verification:
            return None
        return Hypothesis(
            id=f"{parent.id}_f1",
            statement=statement,
            verification=verification,
            success_signal=str(data.get("success_signal") or "").strip(),
            depth=parent.depth + 1,
            parent_id=parent.id,
        )

    # ------------------------------------------------------------------
    # Driver loop: blueprint -> execute -> critique -> follow-up -> report
    # ------------------------------------------------------------------
    async def explore(
        self,
        question: str,
        data_context: str = "",
        file_paths: Optional[List[str]] = None,
        executor: Optional[ExplorationExecutor] = None,
    ) -> Optional[ExplorationReport]:
        """Run the full exploration loop and return a synthesized report.

        Returns ``None`` when no blueprint can be generated (caller should
        fall back to the standard workflow path).
        """
        blueprint = await self.generate_blueprint(
            question, data_context=data_context, file_paths=file_paths
        )
        if blueprint is None:
            return None
        await self.run_blueprint(blueprint, executor=executor)
        return ExplorationReport(
            question=question,
            hypotheses=blueprint.all_hypotheses(),
            markdown=self.synthesize(question, blueprint.all_hypotheses()),
        )

    async def run_blueprint(
        self,
        blueprint: ExplorationBlueprint,
        task_results: Optional[Dict[str, Optional[Dict[str, Any]]]] = None,
        executor: Optional[ExplorationExecutor] = None,
    ) -> ExplorationBlueprint:
        """Critique every hypothesis branch and chase depth-limited follow-ups.

        ``task_results`` maps hypothesis id -> already-executed branch result
        (used when the blueprint tree ran through the standard job path).
        Branches without a precomputed result are executed via ``executor``.
        Follow-up hypotheses are executed at most one per parent and only
        while ``parent.depth < max_depth``.
        """
        task_results = task_results or {}
        queue: List[Hypothesis] = list(blueprint.hypotheses)
        while queue:
            hypothesis = queue.pop(0)
            result = task_results.get(hypothesis.id)
            if (
                result is None
                and hypothesis.id not in task_results
                and executor is not None
            ):
                task = self.hypothesis_to_task(blueprint, hypothesis)
                try:
                    result = await executor(task)
                except Exception:
                    logger.warning(
                        "Exploration branch %s execution failed",
                        hypothesis.id,
                        exc_info=True,
                    )
                    result = None
            if result is not None:
                try:
                    hypothesis.result_summary = json.dumps(
                        result, ensure_ascii=False, default=str
                    )[:500]
                except Exception:
                    hypothesis.result_summary = str(result)[:500]

            critique = await self.critique_result(hypothesis, result)
            hypothesis.verdict = critique.verdict
            hypothesis.confidence = critique.confidence
            hypothesis.reasoning = critique.reasoning

            follow_up = critique.follow_up
            if (
                follow_up is not None
                and hypothesis.depth < self.max_depth
                and executor is not None
            ):
                blueprint.follow_ups.append(follow_up)
                queue.append(follow_up)
        return blueprint

    # ------------------------------------------------------------------
    # d. Report synthesis (deterministic — no LLM)
    # ------------------------------------------------------------------
    def synthesize(self, question: str, hypotheses: List[Hypothesis]) -> str:
        """Render the hypothesis-evidence-conclusion report as Markdown."""
        verdict_labels = {
            "supported": "支持",
            "refuted": "不支持",
            "inconclusive": "无法确定",
            None: "未评判",
        }
        supported = [h for h in hypotheses if h.verdict == "supported"]
        refuted = [h for h in hypotheses if h.verdict == "refuted"]
        inconclusive = [
            h for h in hypotheses if h.verdict not in ("supported", "refuted")
        ]

        lines = [
            f"## 探索报告：{question}",
            "",
            (
                f"共验证 {len(hypotheses)} 个假设：{len(supported)} 个支持、"
                f"{len(refuted)} 个不支持、{len(inconclusive)} 个无法确定。"
            ),
            "",
            "| 假设 | 验证分析 | 结论 | 置信度 | 依据 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for idx, hypothesis in enumerate(hypotheses, start=1):
            label = f"H{idx}"
            if hypothesis.depth > 1:
                label = f"H{idx}（后续假设，源自 {hypothesis.parent_id}）"
            verdict = verdict_labels.get(hypothesis.verdict, "无法确定")
            reasoning = self._clip(hypothesis.reasoning, 120)
            lines.append(
                f"| {label} {self._clip(hypothesis.statement, 80)} "
                f"| {self._clip(hypothesis.verification, 80)} "
                f"| {verdict} "
                f"| {hypothesis.confidence:.2f} "
                f"| {reasoning} |"
            )

        lines.extend(["", "### 建议下一步"])
        next_steps = self._suggest_next_steps(supported, refuted, inconclusive)
        lines.extend(f"- {step}" for step in next_steps)
        return "\n".join(lines)

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        text = (text or "").replace("|", "\\|").replace("\n", " ").strip()
        return text if len(text) <= limit else text[: limit - 1] + "…"

    @staticmethod
    def _suggest_next_steps(
        supported: List[Hypothesis],
        refuted: List[Hypothesis],
        inconclusive: List[Hypothesis],
    ) -> List[str]:
        steps: List[str] = []
        if supported:
            best = max(supported, key=lambda h: h.confidence)
            steps.append(
                f"围绕支持度最高的假设（{best.statement}）设计验证性实验或扩大样本量复核。"
            )
        if refuted:
            steps.append(
                "已排除的方向：" + "；".join(h.statement for h in refuted) + "。"
            )
        if inconclusive:
            steps.append(
                "对无法确定的假设补充数据或更换统计方法后重新验证："
                + "；".join(h.statement for h in inconclusive)
                + "。"
            )
        if not steps:
            steps.append("暂无明确结论，建议补充数据后重新探索。")
        return steps
