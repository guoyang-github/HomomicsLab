"""Phase Gate — post-execution success criteria evaluation."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from homomics_lab.agent.plan.models import DataState, SuccessCriterion
from homomics_lab.tasks.models import TaskNode


@dataclass
class GateResult:
    """Outcome of evaluating a task against its success criteria."""

    passed: bool
    criterion: Optional[SuccessCriterion] = None
    actual_value: Any = None
    expected: Any = None
    operator: str = ""
    message: str = ""


class PhaseGateEvaluator:
    """Evaluate whether a task's output satisfies its success criteria."""

    def __init__(self, data_state: Optional[DataState] = None):
        self.data_state = data_state or DataState()

    async def evaluate(
        self,
        task: TaskNode,
        result: Dict[str, Any],
    ) -> GateResult:
        """Evaluate all success criteria for a task.

        Returns the first failing criterion, or a passed result if all pass.
        """
        if not task.success_criteria:
            return GateResult(passed=True)

        for criterion_dict in task.success_criteria:
            criterion = self._normalize_criterion(criterion_dict)
            actual = self._resolve_metric(criterion.metric, result)
            expected = criterion.threshold

            passed = self._compare(actual, criterion.operator, expected)
            if not passed:
                message = criterion.message or (
                    f"Gate failed: {criterion.metric}={actual} "
                    f"does not satisfy {criterion.operator} {expected}"
                )
                try:
                    message = message.format(
                        actual=actual,
                        expected=expected,
                        metric=criterion.metric,
                    )
                except Exception:
                    pass
                return GateResult(
                    passed=False,
                    criterion=criterion,
                    actual_value=actual,
                    expected=expected,
                    operator=criterion.operator,
                    message=message,
                )

        return GateResult(passed=True)

    @staticmethod
    def _normalize_criterion(criterion: Any) -> SuccessCriterion:
        if isinstance(criterion, SuccessCriterion):
            return criterion
        if isinstance(criterion, dict):
            return SuccessCriterion(**criterion)
        raise ValueError(f"Invalid success criterion: {criterion}")

    def _resolve_metric(
        self,
        metric: str,
        result: Dict[str, Any],
    ) -> Any:
        """Resolve a metric path against the task result or data state."""
        if metric.startswith("data_state."):
            key = metric.split(".", 1)[1]
            return self.data_state.get(key)

        path = metric.split(".")
        value = result
        for part in path:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    @staticmethod
    def _compare(actual: Any, operator: str, expected: Any) -> bool:
        """Compare actual value against expected using the given operator."""
        op = operator.strip()

        if actual is None:
            return False

        try:
            if op == "==":
                return actual == expected
            if op == "!=":
                return actual != expected
            if op in (">", ">=", "<", "<="):
                return PhaseGateEvaluator._numeric_compare(actual, op, expected)
            if op == "in":
                return actual in expected
            if op in ("not_in", "not in"):
                return actual not in expected
            if op == "contains":
                return expected in actual
        except Exception:
            return False

        # Unknown operator fails closed.
        return False

    @staticmethod
    def _numeric_compare(actual: Any, op: str, expected: Any) -> bool:
        """Coerce values to float and compare."""
        actual_num = float(actual)
        expected_num = float(expected)

        if op == ">":
            return actual_num > expected_num
        if op == ">=":
            return actual_num >= expected_num
        if op == "<":
            return actual_num < expected_num
        if op == "<=":
            return actual_num <= expected_num
        return False
