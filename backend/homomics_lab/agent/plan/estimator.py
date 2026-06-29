"""Estimate execution cost and duration for plan phases.

Estimates combine:
  1. Historical skill execution metrics (SkillPerformanceTracker)
  2. Declared skill runtime resources (SkillResources.time, cpu, memory)
  3. Static heuristics for LLM token usage
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from homomics_lab.agent.plan.models import Phase
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.tracker import SkillPerformanceTracker


# Cost rates used when no tracker history is available (USD per unit).
_DEFAULT_COST_PER_SECOND = 0.0  # compute cost folded into time-derived heuristic
_DEFAULT_LLM_INPUT_TOKEN_COST = 5e-7  # ~$0.50 / 1M tokens (placeholder)
_DEFAULT_LLM_OUTPUT_TOKEN_COST = 1.5e-6  # ~$1.50 / 1M tokens (placeholder)


def parse_duration_string(value: str) -> float:
    """Parse a duration string like '2h30m', '30m', '1.5h' into seconds.

    Falls back to 600 seconds (10 minutes) for unparseable values.
    """
    if value is None:
        return 600.0
    value = str(value).strip()
    if not value:
        return 600.0

    # Pure number: treat as minutes.
    try:
        return float(value) * 60.0
    except ValueError:
        pass

    total = 0.0
    matched = False
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([hms])", value.lower()):
        matched = True
        number = float(number)
        if unit == "h":
            total += number * 3600.0
        elif unit == "m":
            total += number * 60.0
        else:
            total += number
    if matched:
        return total if total > 0 else 600.0
    return 600.0


def _schema_property_count(schema: Optional[Any]) -> int:
    """Count top-level properties in a JSON schema-like object."""
    if not isinstance(schema, dict):
        return 0
    properties = schema.get("properties")
    return len(properties) if isinstance(properties, dict) else 0


def estimate_phase(
    phase: Phase,
    tracker: Optional[SkillPerformanceTracker] = None,
) -> None:
    """Populate execution estimates on a phase in place.

    If a SkillPerformanceTracker is supplied, historical averages take
    precedence. Otherwise estimates are derived from the skill's declared
    runtime resources.
    """
    skill = phase.selected_skill
    if skill is None:
        _apply_default_estimate(phase)
        return

    # 1. Try historical metrics.
    history = _get_historical_estimates(skill.id, tracker)
    if history is not None:
        phase.estimated_duration_seconds = history["duration_seconds"]
        phase.estimated_cost_usd = history["cost_usd"]
        phase.estimated_cpu_cores = skill.runtime.resources.cpu or 2
        phase.estimated_memory_gb = _parse_memory(skill.runtime.resources.memory)
        phase.estimated_input_tokens, phase.estimated_output_tokens = _estimate_tokens(skill)
        return

    # 2. Fall back to declared runtime resources.
    phase.estimated_duration_seconds = parse_duration_string(skill.runtime.resources.time)
    phase.estimated_cost_usd = _heuristic_cost_from_resources(
        phase.estimated_duration_seconds,
        skill.runtime.resources.cpu,
        _parse_memory(skill.runtime.resources.memory),
    )
    phase.estimated_cpu_cores = skill.runtime.resources.cpu or 2
    phase.estimated_memory_gb = _parse_memory(skill.runtime.resources.memory)
    phase.estimated_input_tokens, phase.estimated_output_tokens = _estimate_tokens(skill)


def _apply_default_estimate(phase: Phase) -> None:
    phase.estimated_duration_seconds = 600.0
    phase.estimated_cost_usd = 0.0
    phase.estimated_input_tokens = 500
    phase.estimated_output_tokens = 250
    phase.estimated_cpu_cores = 2
    phase.estimated_memory_gb = 4.0


def _get_historical_estimates(
    skill_id: str,
    tracker: Optional[SkillPerformanceTracker],
) -> Optional[Dict[str, Any]]:
    if tracker is None:
        return None
    stats = tracker.get_stats(skill_id)
    total = stats.get("total_executions", 0)
    if total == 0:
        return None
    avg_duration_ms = stats.get("avg_duration_ms", 0.0)
    duration_seconds = (avg_duration_ms / 1000.0) if avg_duration_ms else 600.0
    total_cost = stats.get("total_cost_usd", 0.0) or 0.0
    cost_usd = total_cost / total
    return {"duration_seconds": duration_seconds, "cost_usd": cost_usd}


def _parse_memory(value: Optional[str]) -> Optional[float]:
    """Parse a memory string like '4G', '512M', '2.5G' into GB."""
    if value is None:
        return None
    value = str(value).strip().upper()
    if not value:
        return None
    match = re.match(r"(\d+(?:\.\d+)?)\s*([KMGT]?B?)", value)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2)
    if unit.startswith("K"):
        return number / (1024 * 1024)
    if unit.startswith("M"):
        return number / 1024
    if unit.startswith("T"):
        return number * 1024
    return number  # GB default


def _heuristic_cost_from_resources(
    duration_seconds: float,
    cpu_cores: int,
    memory_gb: Optional[float],
) -> float:
    """Very rough compute cost estimate based on time, CPU and memory."""
    hours = duration_seconds / 3600.0
    cost = hours * (cpu_cores or 2) * 0.05  # $0.05 per CPU-hour placeholder
    if memory_gb:
        cost += hours * memory_gb * 0.01  # $0.01 per GB-hour placeholder
    return round(cost, 6)


def _estimate_tokens(skill: SkillDefinition) -> tuple:
    """Heuristic token estimates from input/output schema size."""
    input_props = _schema_property_count(skill.input_schema)
    output_props = _schema_property_count(skill.output_schema)
    input_tokens = 200 + input_props * 50
    output_tokens = 200 + output_props * 80
    return input_tokens, output_tokens


def default_tracker(db_path: Optional[Path] = None) -> SkillPerformanceTracker:
    """Return a SkillPerformanceTracker at the default metrics DB path."""
    if db_path is None:
        db_path = Path("./homomics_lab_metrics.db")
    return SkillPerformanceTracker(db_path=db_path)
