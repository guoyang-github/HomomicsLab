"""Benchmark CLI for intent recognition and other evaluable subsystems."""

import argparse
import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer


def _build_intent_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "intent",
        help="Evaluate CascadeIntentAnalyzer against a labeled dataset",
    )
    parser.add_argument(
        "dataset",
        type=Path,
        help="Path to JSON dataset (list of {message, expected_analysis_type, ...})",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write results to JSON file (default: stdout)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Consider top-k alternatives as correct",
    )
    parser.add_argument(
        "--no-domain-registry",
        action="store_true",
        help="Disable domain registry loading",
    )
    parser.add_argument(
        "--field",
        type=str,
        default="analysis_type",
        help="Field to evaluate (analysis_type, domain, scope, interaction_mode)",
    )
    return parser


def register_benchmark_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "benchmark",
        help="Run benchmarks against HomomicsLab subsystems",
    )
    benchmark_subparsers = parser.add_subparsers(dest="benchmark_command", required=True)
    _build_intent_parser(benchmark_subparsers)


async def _evaluate_intent(
    dataset_path: Path,
    field: str,
    top_k: int,
    use_domain_registry: bool,
) -> Dict[str, Any]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Dataset must be a JSON list of examples")

    analyzer = CascadeIntentAnalyzer(use_domain_registry=use_domain_registry)

    correct = 0
    total = len(raw)
    per_class: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    details: List[Dict[str, Any]] = []
    clarification_count = 0

    for example in raw:
        message = example.get("message", "")
        expected = example.get(f"expected_{field}", example.get(field, ""))
        if not message or not expected:
            continue

        intent = await analyzer.analyze(message)
        actual = getattr(intent, field, None) or ""
        alternatives = []
        for m in intent.metadata.get("alternatives", []):
            if isinstance(m, dict):
                alternatives.append(m.get(field, m.get("analysis_type", "")))
            else:
                alternatives.append(getattr(m, field, None) or m.analysis_type)

        is_correct = actual == expected
        if not is_correct and top_k > 1:
            is_correct = expected in alternatives[: top_k - 1]

        if is_correct:
            correct += 1
            per_class[expected]["tp"] += 1
        else:
            per_class[expected]["fn"] += 1
            if actual:
                per_class[actual]["fp"] += 1

        confusion[str(expected)][str(actual)] += 1

        if getattr(intent, "analysis_type", None) == "clarification":
            clarification_count += 1

        details.append({
            "message": message,
            "expected": expected,
            "actual": actual,
            "correct": is_correct,
            "confidence": getattr(intent, "confidence", 0.0),
            "alternatives": alternatives[:top_k],
        })

    # Compute precision/recall/f1 per class
    metrics: Dict[str, Dict[str, float]] = {}
    for label, counts in per_class.items():
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics[label] = {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}

    accuracy = correct / total if total > 0 else 0.0

    result = {
        "benchmark": "intent",
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 3),
        "top_k": top_k,
        "field": field,
        "clarification_rate": round(clarification_count / total, 3) if total > 0 else 0.0,
        "per_class": metrics,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "details": details,
    }
    return result


def run_benchmark(args: argparse.Namespace) -> int:
    if args.benchmark_command == "intent":
        result = asyncio.run(
            _evaluate_intent(
                dataset_path=args.dataset,
                field=args.field,
                top_k=args.top_k,
                use_domain_registry=not args.no_domain_registry,
            )
        )
        output_text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(output_text, encoding="utf-8")
            print(f"Results written to {args.output}")
        else:
            print(output_text)
        return 0 if result["accuracy"] >= 0.0 else 1
    return 1
