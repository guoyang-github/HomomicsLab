"""Tool call approval mechanism for high-risk tools.

When ``settings.interactive_mode`` is enabled, tools marked with
``risk_level == "high"`` require explicit user approval before execution.
The approval store is persistent by default; an in-memory store is provided
for tests and single-instance deployments.
"""

from typing import Dict, Optional

from homomics_lab.tools.approval_store import PersistentApprovalStore


class ToolApprovalRequired(Exception):
    """Raised when a high-risk tool call requires user approval."""

    def __init__(
        self,
        call_id: str,
        tool_name: str,
        arguments: Dict,
        risk_level: str,
    ):
        self.call_id = call_id
        self.tool_name = tool_name
        self.arguments = arguments
        self.risk_level = risk_level
        super().__init__(
            f"Tool '{tool_name}' (risk={risk_level}) requires approval. "
            f"Call ID: {call_id}"
        )


class ToolApprovalStore(PersistentApprovalStore):
    """Backward-compatible alias for the persistent approval store."""

    pass


# Global persistent approval store. Use a fresh instance on import so tests
# can swap it without side effects.
_default_approval_store: Optional[PersistentApprovalStore] = None


def get_default_approval_store() -> PersistentApprovalStore:
    global _default_approval_store
    if _default_approval_store is None:
        _default_approval_store = PersistentApprovalStore()
    return _default_approval_store


def reset_default_approval_store() -> None:
    global _default_approval_store
    _default_approval_store = None
