"""Audit logging for tool invocations.

Records who called which tool, with what arguments, and whether it succeeded.
Currently a lightweight file-based logger; can be swapped for structured
observability or CBKB later.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)


def log_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    success: bool,
    error_message: Optional[str] = None,
    latency_ms: float = 0.0,
    caller: Optional[str] = None,
) -> None:
    """Append a tool invocation record to the audit log.

    Audit logging is best-effort and never raises to the caller.
    """
    if not getattr(settings, "audit_log_enabled", False):
        return

    try:
        log_path = settings.audit_log_path or (settings.data_dir / "audit.log")
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "tool_call",
            "caller": caller or "agent_skill_executor",
            "tool_name": tool_name,
            "arguments": arguments,
            "success": success,
            "error_message": error_message,
            "latency_ms": round(latency_ms, 2),
        }
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        logger.warning("Failed to write tool audit log: %s", exc)
