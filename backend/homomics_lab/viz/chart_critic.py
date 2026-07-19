"""ChartCritic — VLM-based visual feedback for agent-produced charts.

Inspired by the self-check loop in systems like CellVoyager: after the agent
renders a chart, a vision-capable LLM inspects the image and reports concrete
problems (empty figure, missing axes, garbled labels, truncated data, legend
occlusion, chart type not matching the intent). The caller can then feed the
suggestion back into code generation for a bounded repair pass.

Design rules (always on and self-gating, never a new failure point):

* No enable switch: the critic activates whenever the resolved model is
  vision-capable (``supports_vision_model``) and silently skips otherwise.
* Cheap rule pre-checks run first (missing/zero-byte file, blank image via
  PIL statistics). When a rule can decide, no LLM call is made.
* When the configured model is not vision-capable, or the VLM call fails for
  any reason, the critic silently degrades to ``ok=True`` and logs at debug
  level so the main analysis flow is never blocked.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Image suffixes treated as charts when scanning result dicts.
CHART_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# Conservative name prefixes of models known to accept image inputs via the
# OpenAI-compatible ``image_url`` message shape. Anything else is treated as
# text-only and skipped (silent degrade). Matching is done on the lowercased
# model name.
_VISION_MODEL_PREFIXES = (
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4-vision",
    "gpt-5",
    "chatgpt-4o",
    "claude-3",
    "claude-sonnet-4",
    "claude-opus-4",
    "gemini",
    "qwen-vl",
    "qwen2-vl",
    "qwen2.5-vl",
    "glm-4v",
    "llava",
    "pixtral",
    "minicpm-v",
    "internvl",
    "moondream",
    "kimi-latest",
    "moonshot-v1-8k-vision",
    "moonshot-v1-32k-vision",
    "moonshot-v1-128k-vision",
)

# Issue categories the VLM is asked to report.
ISSUE_CATEGORIES = (
    "empty_chart",  # 空图：坐标系/画布存在但没有数据
    "missing_axes",  # 轴缺失：坐标轴、刻度或轴标题缺失
    "garbled_labels",  # 标签乱码：文本渲染为方块/问号/重叠不可读
    "truncated_data",  # 数据异常截断：明显只画出了部分数据
    "legend_occlusion",  # 图例遮挡：图例盖住数据区域
    "intent_mismatch",  # 类型不匹配意图：图表类型与用户意图不符
)

_SEVERITIES = ("none", "low", "high")

# Pixel standard deviation below which an image is considered blank/uniform.
_BLANK_STDDEV_THRESHOLD = 2.0

_CRITIQUE_PROMPT = """You are a meticulous chart reviewer for a bioinformatics analysis agent.
Inspect the attached chart image and decide whether it correctly serves the analysis intent.

Analysis intent: {intent}

Report only concrete, visible problems from these categories:
- empty_chart: the canvas/axes render but no data is plotted
- missing_axes: axes, ticks, or axis titles are missing
- garbled_labels: text renders as boxes/question marks or is unreadably overlapping
- truncated_data: only part of the expected data appears to be plotted
- legend_occlusion: the legend covers the data area
- intent_mismatch: the chart type does not match the analysis intent

Respond with STRICT JSON only, no markdown fences:
{{"ok": true/false, "issues": [<category>, ...], "severity": "none"|"low"|"high", "suggestion": "<one concrete fix instruction, empty when ok>"}}

Use severity "high" only when the chart is misleading or unusable for the intent;
use "low" for cosmetic issues. When in doubt, answer ok=true with severity "none"."""


@dataclass
class ChartCritique:
    """Structured assessment of one chart image."""

    ok: bool
    issues: List[str] = field(default_factory=list)
    severity: str = "none"  # "none" | "low" | "high"
    suggestion: str = ""
    # What produced this critique: "rule" (cheap pre-check), "vlm" (vision
    # model), or "skipped" (no vision capability / VLM failure → degraded).
    source: str = "skipped"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": list(self.issues),
            "severity": self.severity,
            "suggestion": self.suggestion,
            "source": self.source,
        }


def supports_vision_model(model: Optional[str]) -> bool:
    """Return True when the model name is known to accept image inputs."""
    if not model:
        return False
    name = model.lower()
    return any(name.startswith(prefix) for prefix in _VISION_MODEL_PREFIXES)


def collect_chart_paths(result: Any, max_charts: int = 3) -> List[Path]:
    """Collect existing chart image paths from a CodeAct result payload.

    Scans the ``result`` dict (one nesting level) for string values that point
    to existing image files, plus the usual ``output_files``/``plot_path``
    style keys. Returns at most ``max_charts`` unique paths, stable-ordered.
    """
    if not isinstance(result, dict):
        return []

    candidates: List[str] = []

    def _add(value: Any) -> None:
        if isinstance(value, (str, Path)):
            candidates.append(str(value))
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, (str, Path)):
                    candidates.append(str(item))
                elif isinstance(item, dict):
                    _add(item.get("path") or item.get("file"))
        elif isinstance(value, dict):
            for v in value.values():
                _add(v)

    for key, value in result.items():
        if key in ("output_files", "output_paths", "artifacts", "plot_path", "output_path", "output_file"):
            _add(value)
        elif isinstance(value, (str, Path)) and Path(value).suffix.lower() in CHART_SUFFIXES:
            candidates.append(str(value))

    seen: set = set()
    charts: List[Path] = []
    for raw in candidates:
        path = Path(raw)
        if path.suffix.lower() not in CHART_SUFFIXES:
            continue
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        charts.append(path)
        if len(charts) >= max_charts:
            break
    return charts


class ChartCritic:
    """Critique chart images with cheap rules first, then a vision LLM."""

    def __init__(self, llm_client: Optional[Any] = None, model: Optional[str] = None):
        self._llm_client = llm_client
        self._model = model

    async def critique(
        self,
        image_path: Path,
        intent: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> ChartCritique:
        """Assess one chart image. Never raises; degrades to ``ok=True``."""
        try:
            rule = self._rule_precheck(image_path)
            if rule is not None:
                return rule
        except Exception:
            logger.debug("chart rule precheck failed for %s", image_path, exc_info=True)
            # A failing pre-check must not block the flow; fall through to VLM.

        try:
            return await self._vlm_critique(Path(image_path), intent, context or {})
        except Exception:
            logger.debug("chart VLM critique failed for %s", image_path, exc_info=True)
            return ChartCritique(ok=True, source="skipped")

    def has_vision_capability(self) -> bool:
        """True when a vision-capable, configured LLM is available for critique.

        Used by callers to short-circuit before doing any critique work. The
        critique path itself remains self-gating; this is a cheap pre-flight.
        """
        client = self._llm_client
        if client is None:
            return False
        if not supports_vision_model(self._resolve_model()):
            return False
        is_configured = getattr(client, "is_configured", None)
        return bool(is_configured()) if callable(is_configured) else True

    # ------------------------------------------------------------------
    # Rule pre-checks
    # ------------------------------------------------------------------

    def _rule_precheck(self, image_path: Path) -> Optional[ChartCritique]:
        """Cheap deterministic checks; return None when inconclusive."""
        path = Path(image_path)
        if not path.is_file() or path.stat().st_size == 0:
            return ChartCritique(
                ok=False,
                issues=["empty_chart"],
                severity="high",
                suggestion="The chart file is missing or empty; ensure the plotting code actually saves a non-empty figure.",
                source="rule",
            )

        # Blank/uniform image detection via PIL statistics (no LLM needed).
        try:
            from PIL import Image, ImageStat
        except ImportError:
            return None
        try:
            with Image.open(path) as img:
                gray = img.convert("L")
                # Downscale for speed; statistics are stable at small sizes.
                gray.thumbnail((256, 256))
                stddev = ImageStat.Stat(gray).stddev[0]
        except Exception:
            logger.debug("cannot decode chart image %s", path, exc_info=True)
            return ChartCritique(
                ok=False,
                issues=["empty_chart"],
                severity="high",
                suggestion="The chart file cannot be decoded as an image; check the figure export code and file format.",
                source="rule",
            )
        if stddev < _BLANK_STDDEV_THRESHOLD:
            return ChartCritique(
                ok=False,
                issues=["empty_chart"],
                severity="high",
                suggestion="The chart is blank (uniform pixels); verify the data passed to the plotting call is non-empty.",
                source="rule",
            )
        return None

    # ------------------------------------------------------------------
    # VLM critique
    # ------------------------------------------------------------------

    def _resolve_model(self) -> Optional[str]:
        if self._model:
            return self._model
        client = self._llm_client
        if client is None:
            return None
        model = getattr(client, "_legacy_model", None)
        if model:
            return model
        router = getattr(client, "router", None)
        return getattr(router, "primary_model", None) if router is not None else None

    async def _vlm_critique(
        self,
        image_path: Path,
        intent: str,
        context: Dict[str, Any],
    ) -> ChartCritique:
        client = self._llm_client
        model = self._resolve_model()
        if client is None or not supports_vision_model(model):
            logger.debug("chart critique skipped: no vision-capable model (model=%s)", model)
            return ChartCritique(ok=True, source="skipped")

        is_configured = getattr(client, "is_configured", None)
        if callable(is_configured) and not is_configured():
            logger.debug("chart critique skipped: LLM client not configured")
            return ChartCritique(ok=True, source="skipped")

        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        prompt = _CRITIQUE_PROMPT.format(intent=intent or context.get("task_description") or "data visualization")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ]
        raw = await client.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=400,
            model=model,
        )
        return self._parse_critique(raw)

    @staticmethod
    def _parse_critique(raw: Any) -> ChartCritique:
        """Parse the VLM JSON response into a ChartCritique (tolerant)."""
        if not isinstance(raw, str) or not raw.strip():
            return ChartCritique(ok=True, source="skipped")
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            logger.debug("chart critique: unparseable VLM response, degrading to ok")
            return ChartCritique(ok=True, source="skipped")
        try:
            data = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            logger.debug("chart critique: invalid JSON from VLM, degrading to ok")
            return ChartCritique(ok=True, source="skipped")
        if not isinstance(data, dict):
            return ChartCritique(ok=True, source="skipped")

        issues = [str(issue) for issue in (data.get("issues") or []) if isinstance(issue, str) and issue]
        severity = str(data.get("severity") or "none").lower()
        if severity not in _SEVERITIES:
            severity = "high" if issues else "none"
        ok = bool(data.get("ok", not issues))
        if severity == "high":
            ok = False
        return ChartCritique(
            ok=ok,
            issues=issues,
            severity=severity,
            suggestion=str(data.get("suggestion") or ""),
            source="vlm",
        )
