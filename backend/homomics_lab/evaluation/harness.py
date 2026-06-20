"""Lightweight evaluation harness for skill/plan correctness.

A test case is a JSON object with ``input`` and ``expected`` fields. The
harness calls an evaluator callable and computes pass rate, precision, recall,
and F1 for set-based expected outputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union


@dataclass
class EvaluationCase:
    name: str
    input: Any
    expected: Any
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    case_name: str
    passed: bool
    predicted: Any = None
    expected: Any = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    total: int
    passed: int
    failed: int
    pass_rate: float
    avg_metrics: Dict[str, float] = field(default_factory=dict)
    results: List[EvaluationResult] = field(default_factory=list)


def _set_f1(predicted: Sequence, expected: Sequence) -> Dict[str, float]:
    pred_set = set(str(x) for x in predicted)
    exp_set = set(str(x) for x in expected)
    tp = len(pred_set & exp_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(exp_set) if exp_set else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def evaluate_case(
    case: EvaluationCase,
    evaluator: Callable[[Any], Any],
    scorer: Optional[Callable[[Any, Any], Dict[str, float]]] = None,
) -> EvaluationResult:
    """Run a single evaluation case."""
    try:
        predicted = evaluator(case.input)
    except Exception as exc:
        return EvaluationResult(
            case_name=case.name,
            passed=False,
            predicted=str(exc),
            expected=case.expected,
            metrics={"error": 1.0},
        )

    passed = predicted == case.expected
    metrics: Dict[str, float] = {}
    if scorer is not None:
        metrics = scorer(predicted, case.expected)
    elif isinstance(case.expected, list):
        metrics = _set_f1(predicted if isinstance(predicted, list) else [], case.expected)

    return EvaluationResult(
        case_name=case.name,
        passed=passed,
        predicted=predicted,
        expected=case.expected,
        metrics=metrics,
    )


def run_evaluation(
    cases: Sequence[EvaluationCase],
    evaluator: Callable[[Any], Any],
    scorer: Optional[Callable[[Any, Any], Dict[str, float]]] = None,
) -> EvaluationReport:
    """Evaluate a list of cases and aggregate metrics."""
    results = [evaluate_case(case, evaluator, scorer) for case in cases]
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    metric_keys = {k for r in results for k in r.metrics.keys()}
    avg_metrics: Dict[str, float] = {}
    for key in metric_keys:
        values = [r.metrics[key] for r in results if key in r.metrics]
        avg_metrics[key] = sum(values) / len(values) if values else 0.0

    return EvaluationReport(
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=passed / total if total else 0.0,
        avg_metrics=avg_metrics,
        results=results,
    )


def load_cases(path: Union[str, Path]) -> List[EvaluationCase]:
    """Load evaluation cases from a JSONL file."""
    cases: List[EvaluationCase] = []
    with open(Path(path), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            cases.append(
                EvaluationCase(
                    name=record.get("name", f"case_{len(cases)}"),
                    input=record["input"],
                    expected=record["expected"],
                    metadata=record.get("metadata", {}),
                )
            )
    return cases


def save_report(report: EvaluationReport, path: Union[str, Path]) -> None:
    """Save an evaluation report as JSON."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "total": report.total,
                "passed": report.passed,
                "failed": report.failed,
                "pass_rate": report.pass_rate,
                "avg_metrics": report.avg_metrics,
                "results": [
                    {
                        "case_name": r.case_name,
                        "passed": r.passed,
                        "predicted": r.predicted,
                        "expected": r.expected,
                        "metrics": r.metrics,
                    }
                    for r in report.results
                ],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
