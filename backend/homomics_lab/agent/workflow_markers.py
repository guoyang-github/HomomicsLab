"""Domain pipeline phase markers for CodeAct executions.

For domain-owned tasks (``domain != generic``) executed as a single CodeAct
script, the generated script is asked to print one marker line at each domain
phase boundary::

    __homomics_phase__:<phase_type>:start
    __homomics_phase__:<phase_type>:done:{<json params>}
    __homomics_phase__:<phase_type>:failed:{<json params>}

The orchestrator turns these markers into ``phase`` progress events (plus
one ``workflow_skeleton`` event at execution start) so the frontend can
render the domain pipeline DAG with real execution progress.  The sandbox
streams output lines back through an ``on_output_line`` callback so markers
are reported in near real time; a deduplicated batch scan of the captured
stdout/stderr after execution stays as the fallback for backends that cannot
stream.  Marking is best effort: a script that prints no markers produces no
phase events and no errors — the skeleton stays ``pending``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

MARKER_PREFIX = "__homomics_phase__"

# Anchored full-line match: a marker line must contain nothing else.
MARKER_RE = re.compile(r"__homomics_phase__:(\w+):(start|done|failed)(?::(.*))?")

# Domain placeholder values that mean "no real domain ownership" — tasks
# carrying one of these get zero marker injection and zero workflow events.
GENERIC_DOMAIN_VALUES = frozenset({"generic", "general", "builtin"})

# Hard budget for the injected convention text (prompt size control).
MAX_CONVENTION_CHARS = 500


def parse_marker_line(line: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """Parse one stdout/stderr line into ``(phase, status, params)``.

    Returns ``None`` when the line is not exactly a marker.  A malformed JSON
    tail on ``done``/``failed`` degrades silently to ``params={}``.
    """
    match = MARKER_RE.fullmatch(line.strip())
    if match is None:
        return None
    phase, status, raw_params = match.group(1), match.group(2), match.group(3)
    params: Dict[str, Any] = {}
    if raw_params:
        try:
            parsed = json.loads(raw_params)
            if isinstance(parsed, dict):
                params = parsed
        except Exception:
            params = {}
    return phase, status, params


def scan_marker_lines(text: str) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Extract every marker from a captured output blob, in order."""
    markers: List[Tuple[str, str, Dict[str, Any]]] = []
    for line in (text or "").splitlines():
        marker = parse_marker_line(line)
        if marker is not None:
            markers.append(marker)
    return markers


def _normalize_phase_entries(raw: Any) -> List[Dict[str, str]]:
    """Normalize a phase list into ``[{"phase_type", "name"}]`` dicts."""
    phases: List[Dict[str, str]] = []
    if not isinstance(raw, list):
        return phases
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        phase_type = (
            entry.get("phase_type") or entry.get("analysis_type") or entry.get("id")
        )
        if not phase_type or not isinstance(phase_type, str):
            continue
        name = entry.get("name") or entry.get("description") or phase_type
        phases.append({"phase_type": phase_type, "name": str(name)})
    return phases


def extract_domain_pipeline(task: Any) -> Optional[Tuple[str, List[Dict[str, str]]]]:
    """Return ``(domain, phases)`` when the task has real domain ownership.

    Phase list resolution order (first non-empty wins):

    1. ``parameters["domain_phases"]`` — the domain pipeline phases stamped at
       plan time (already trimmed by ``preflight.skip_phases``).
    2. ``parameters["display_subtasks"]`` — standalone-skill sub-steps.
    3. The task's own ``phase`` field (when it is a real phase id).

    Returns ``None`` for generic / domain-less tasks or when no phase
    information exists at all — callers must then inject nothing and emit no
    workflow events.
    """
    params = getattr(task, "parameters", None) or {}
    domain = params.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        return None
    domain = domain.strip()
    if domain.lower() in GENERIC_DOMAIN_VALUES:
        return None

    phases = _normalize_phase_entries(params.get("domain_phases"))
    if not phases:
        phases = _normalize_phase_entries(params.get("display_subtasks"))
    if not phases:
        own_phase = getattr(task, "phase", "") or ""
        if own_phase and own_phase != "execution":
            name = (
                getattr(task, "description", "")
                or getattr(task, "name", "")
                or own_phase
            )
            phases = [{"phase_type": own_phase, "name": name}]
    if not phases:
        return None
    return domain, phases


def build_marker_convention(phases: List[Dict[str, str]]) -> str:
    """Build the prompt snippet describing the marker convention (<= 500 chars).

    The phase order list is trimmed from the tail when the text would exceed
    :data:`MAX_CONVENTION_CHARS`; the script is still free to mark any phase.
    """
    ids = [p["phase_type"] for p in phases]
    for keep in range(len(ids), 0, -1):
        order = ", ".join(ids[:keep])
        if keep < len(ids):
            order += f" (+{len(ids) - keep} more)"
        text = (
            "Progress markers (required): this analysis covers domain phases, in order: "
            f"{order}. At each phase boundary print one marker line and nothing else on "
            "that line:\n"
            f'  print("{MARKER_PREFIX}:<phase>:start")\n'
            f'  print("{MARKER_PREFIX}:<phase>:done:" + json.dumps({{main params}}))\n'
            f'  on error: print("{MARKER_PREFIX}:<phase>:failed:" + json.dumps({{"error": str(e)}}))\n'
            "Mark phases in the given order; phases you do not perform may be left "
            "unmarked (best effort)."
        )
        if len(text) <= MAX_CONVENTION_CHARS:
            return text
    # Unreachable in practice (a single id fits), but never exceed the budget.
    return text[:MAX_CONVENTION_CHARS]
