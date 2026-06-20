"""Tests for the lightweight evaluation harness."""

import json

from homomics_lab.evaluation.harness import (
    EvaluationCase,
    evaluate_case,
    load_cases,
    run_evaluation,
    save_report,
)


def test_evaluate_case_passes_on_exact_match():
    case = EvaluationCase(name="add", input={"x": 1, "y": 2}, expected=3)
    result = evaluate_case(case, lambda d: d["x"] + d["y"])
    assert result.passed
    assert result.predicted == 3


def test_evaluate_case_fails_on_mismatch():
    case = EvaluationCase(name="add", input={"x": 1, "y": 2}, expected=3)
    result = evaluate_case(case, lambda d: d["x"] - d["y"])
    assert not result.passed


def test_evaluate_case_reports_error():
    case = EvaluationCase(name="fail", input=None, expected=1)
    result = evaluate_case(case, lambda _: (_).missing)
    assert not result.passed
    assert "error" in result.metrics


def test_run_evaluation_aggregates_metrics():
    cases = [
        EvaluationCase(name="a", input="a", expected=["a", "b"]),
        EvaluationCase(name="b", input="b", expected=["b", "c"]),
    ]

    def evaluator(inp: str):
        return [inp, "b"]

    report = run_evaluation(cases, evaluator)
    assert report.total == 2
    assert report.passed == 1  # only the exact-match case passes
    assert "f1" in report.avg_metrics
    assert 0 < report.avg_metrics["f1"] <= 1


def test_load_cases(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps({"name": "c1", "input": 1, "expected": 2}) + "\n" +
        json.dumps({"name": "c2", "input": 3, "expected": 4}) + "\n"
    )
    cases = load_cases(path)
    assert len(cases) == 2
    assert cases[0].name == "c1"


def test_save_report(tmp_path):
    report = run_evaluation(
        [EvaluationCase(name="ok", input=1, expected=1)],
        lambda x: x,
    )
    out = tmp_path / "report.json"
    save_report(report, out)
    data = json.loads(out.read_text())
    assert data["passed"] == 1
    assert data["pass_rate"] == 1.0
