"""Tool call approval mechanism for high-risk tools.

When ``settings.interactive_mode`` is enabled, tools marked with
``risk_level == "high"`` require explicit user approval before execution.
The approval store tracks pending and approved call IDs in memory.
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ToolApprovalRequest:
    """Pending approval for a high-risk tool call."""

    call_id: str
    tool_name: str
    arguments: Dict
    risk_level: str
    approved: bool = False
    metadata: Dict = field(default_factory=dict)


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


class ToolApprovalStore:
    """In-memory store for pending tool call approvals."""

    def __init__(self):
        self._requests: Dict[str, ToolApprovalRequest] = {}

    def create_request(
        self,
        tool_name: str,
        arguments: Dict,
        risk_level: str,
    ) -> ToolApprovalRequest:
        """Create a pending approval request."""
        call_id = str(uuid.uuid4())
        request = ToolApprovalRequest(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
        )
        self._requests[call_id] = request
        return request

    def get(self, call_id: str) -> Optional[ToolApprovalRequest]:
        return self._requests.get(call_id)

    def approve(self, call_id: str) -> bool:
        """Approve a pending request. Returns True if found."""
        request = self._requests.get(call_id)
        if request is None:
            return False
        request.approved = True
        return True

    def reject(self, call_id: str) -> bool:
        """Reject a pending request. Returns True if found."""
        request = self._requests.get(call_id)
        if request is None:
            return False
        request.approved = False
        return True

    def is_approved(self, call_id: str) -> bool:
        request = self._requests.get(call_id)
        return request is not None and request.approved

    def list_pending(self):
        return [r for r in self._requests.values() if not r.approved]


# Global in-memory store (sufficient for single-instance deployments;
# replace with Redis/database for multi-node worker setups).
_default_approval_store = ToolApprovalStore()


def get_default_approval_store() -> ToolApprovalStore:
    return _default_approval_store
