"""Structured progress event contract for agent / subagent executions.

Agent loops stream live progress as :class:`~homomics_lab.hpc.state.ExecutionState`
objects through the job pubsub; the SSE endpoint serializes each state with
``ExecutionState.to_dict()``.  Two channels carry subagent attribution:

1. **State top level** — a child execution stamps every state it emits with
   ``actor`` (``"subagent:<skill_id>"``) and ``parent_id`` (the parent
   job/task id).  Both keys are omitted entirely for top-level executions, so
   older consumers see exactly the pre-contract payload shape.
2. **Structured tool events** — tool-level events travel inside
   ``ExecutionState.resource_usage["agent_events"]`` (a list of event dicts,
   see below).  Each event dict also carries ``actor`` / ``parent_id`` for
   child executions so downstream tooling can re-attribute them out of band.

Lifecycle: a child execution emits RUNNING states during its loop and exactly
one terminal state (``COMPLETED`` or ``FAILED``) when it finishes, all tagged
with the same ``actor`` / ``parent_id``.  Top-level executions emit no
terminal state from the agent loop; their lifecycle is owned by the job
runner.

Event dict schema (v1)
----------------------
- ``type``: str — event kind.  Currently emitted by the agent skill loop:
  ``"tool_start"`` | ``"tool_end"`` | ``"llm_retry"`` | ``"artifact"``.
- ``timestamp``: float — unix seconds when the event was created.
- ``actor``: str, optional — present **only** for child executions, formatted as
  ``"subagent:<skill_id>"``.  Top-level executions omit this key entirely.
- ``parent_id``: str, optional — present **only** for child executions; the id
  of the parent job/task this execution belongs to.  ``actor`` and
  ``parent_id`` always appear together.
- ``tool``: str, optional — tool name for ``tool_start`` / ``tool_end``.
- ``arguments``: dict, optional — tool arguments (or an ``{"summary": ...}``
  preview for long argument blobs).
- ``success``: bool, optional — tool outcome for ``tool_end``.
- ``output``: str, optional — truncated preview (<= ``MAX_EVENT_OUTPUT_CHARS``).
- ``error_message``: str, optional — truncated (<= ``MAX_EVENT_ERROR_CHARS``).
- ``artifacts``: list[str], optional — produced file paths for ``artifact``.
- ``latency_ms``: float, optional — tool call latency for ``tool_end``.

Backward compatibility: top-level executions emit neither ``actor`` nor
``parent_id`` anywhere, so older frontends see exactly the pre-contract shape.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

# Truncation bounds for free-text fields inside an event dict.
MAX_EVENT_OUTPUT_CHARS = 2000
MAX_EVENT_ERROR_CHARS = 1000

SUBAGENT_ACTOR_PREFIX = "subagent:"


def subagent_actor(skill_id: str) -> str:
    """Return the actor id for a skill executed as a subagent."""
    return f"{SUBAGENT_ACTOR_PREFIX}{skill_id}"


def parent_context_fields(
    actor: Optional[str],
    parent_id: Optional[str],
) -> Dict[str, str]:
    """Return the attribution fields for a child execution, or ``{}``.

    Both fields are only ever present together; a top-level execution (no
    ``parent_id``) yields an empty dict that can be merged into
    ``ExecutionState.resource_usage`` without changing its shape.
    """
    if actor is None or parent_id is None:
        return {}
    return {"actor": actor, "parent_id": parent_id}


def build_agent_event(
    event_type: str,
    *,
    actor: Optional[str] = None,
    parent_id: Optional[str] = None,
    tool: Optional[str] = None,
    arguments: Optional[Dict[str, Any]] = None,
    success: Optional[bool] = None,
    output: Optional[str] = None,
    error_message: Optional[str] = None,
    artifacts: Optional[List[str]] = None,
    latency_ms: Optional[float] = None,
    timestamp: Optional[float] = None,
) -> Dict[str, Any]:
    """Build one structured agent event dict (see module docstring).

    ``actor`` / ``parent_id`` are included only when both are provided, so a
    top-level execution produces events that are indistinguishable from the
    pre-contract shape.  Free-text fields are truncated to keep pubsub payloads
    bounded.
    """
    event: Dict[str, Any] = {
        "type": event_type,
        "timestamp": timestamp if timestamp is not None else time.time(),
    }
    event.update(parent_context_fields(actor, parent_id))
    if tool is not None:
        event["tool"] = tool
    if arguments is not None:
        event["arguments"] = arguments
    if success is not None:
        event["success"] = success
    if output is not None:
        event["output"] = output[:MAX_EVENT_OUTPUT_CHARS]
    if error_message is not None:
        event["error_message"] = error_message[:MAX_EVENT_ERROR_CHARS]
    if artifacts is not None:
        event["artifacts"] = artifacts
    if latency_ms is not None:
        event["latency_ms"] = latency_ms
    return event
