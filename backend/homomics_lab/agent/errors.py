"""Structured exception taxonomy for agent turns.

These exceptions let the TurnRunner produce user-friendly, actionable
responses instead of generic "something went wrong" messages.
"""

from typing import Any, Dict, Optional


class TurnError(Exception):
    """Base class for recoverable agent-turn errors."""

    def __init__(
        self,
        message: str,
        recovery_action: str = "escalate",
        context: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.recovery_action = recovery_action
        self.context = context or {}
        self.retryable = retryable

    def to_payload(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "recovery_action": self.recovery_action,
            "retryable": self.retryable,
            "context": self.context,
        }


class IntentError(TurnError):
    """Failed to understand or classify user intent."""

    def __init__(self, message: str = "I didn't understand that request.", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, recovery_action="clarify", retryable=True, context=context)


class PlanError(TurnError):
    """Failed to build or validate an execution plan."""

    def __init__(self, message: str = "I couldn't build a plan for that request.", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, recovery_action="clarify", retryable=True, context=context)


class ToolError(TurnError):
    """Tool call failed or returned an error."""

    def __init__(self, message: str = "A tool call failed.", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, recovery_action="retry", retryable=True, context=context)


class ExecutionError(TurnError):
    """Skill/execution engine failed."""

    def __init__(self, message: str = "Execution failed.", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, recovery_action="retry", retryable=True, context=context)


class SafetyError(TurnError):
    """Request blocked for safety/risk reasons."""

    def __init__(self, message: str = "This request requires human approval.", context: Optional[Dict[str, Any]] = None):
        super().__init__(message, recovery_action="approve", retryable=False, context=context)
