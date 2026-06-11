"""RegressionTester — lightweight regression test suite for skills.

Uses stable reference data + deterministic execution to detect
output drift from locked baselines.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..skills.models import SkillDefinition


@dataclass
class TestBaseline:
    """A recorded baseline for a skill regression test."""

    skill_id: str
    test_case_id: str
    test_input: Dict[str, Any]
    expected_output_signature: str  # hash of key output fields
    expected_keys: List[str]
    recorded_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegressionResult:
    """Result of running a regression test."""

    skill_id: str
    test_case_id: str
    passed: bool
    key_matches: List[str] = field(default_factory=list)
    missing_keys: List[str] = field(default_factory=list)
    extra_keys: List[str] = field(default_factory=list)
    signature_match: bool = False
    error: Optional[str] = None
    duration_ms: Optional[float] = None


def _output_signature(data: Dict[str, Any]) -> str:
    """Create a stable signature from output keys and scalar values."""
    import hashlib

    # Sort keys, stringify scalars
    flat = {}
    for k, v in sorted(data.items()):
        if isinstance(v, (str, int, float, bool)):
            flat[k] = v
        elif isinstance(v, (list, tuple)) and len(v) <= 5:
            flat[k] = str(v)
        elif v is None:
            flat[k] = None
    text = json.dumps(flat, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class RegressionTester:
    """Manages regression baselines and runs regression tests."""

    BASELINE_DIR = "regression_baselines"

    def __init__(self, workspace_dir: Path, skill_registry=None):
        self.workspace_dir = workspace_dir
        self.baseline_dir = workspace_dir / ".metadata" / self.BASELINE_DIR
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.registry = skill_registry

    def record_baseline(
        self,
        skill: SkillDefinition,
        test_case_id: str,
        test_input: Dict[str, Any],
        actual_output: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TestBaseline:
        """Record a baseline from a known good execution."""
        baseline = TestBaseline(
            skill_id=skill.id,
            test_case_id=test_case_id,
            test_input=test_input,
            expected_output_signature=_output_signature(actual_output),
            expected_keys=list(actual_output.keys()),
            recorded_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

        baseline_path = self.baseline_dir / f"{skill.id}__{test_case_id}.json"
        baseline_path.write_text(
            json.dumps(
                {
                    "skill_id": baseline.skill_id,
                    "test_case_id": baseline.test_case_id,
                    "test_input": baseline.test_input,
                    "expected_output_signature": baseline.expected_output_signature,
                    "expected_keys": baseline.expected_keys,
                    "recorded_at": baseline.recorded_at,
                    "metadata": baseline.metadata,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return baseline

    def load_baseline(
        self, skill_id: str, test_case_id: str
    ) -> Optional[TestBaseline]:
        """Load a recorded baseline."""
        baseline_path = self.baseline_dir / f"{skill_id}__{test_case_id}.json"
        if not baseline_path.exists():
            return None

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        return TestBaseline(
            skill_id=data["skill_id"],
            test_case_id=data["test_case_id"],
            test_input=data["test_input"],
            expected_output_signature=data["expected_output_signature"],
            expected_keys=data["expected_keys"],
            recorded_at=data["recorded_at"],
            metadata=data.get("metadata", {}),
        )

    def test_against_baseline(
        self,
        skill_id: str,
        test_case_id: str,
        actual_output: Dict[str, Any],
        exact_signature: bool = True,
        required_keys: Optional[List[str]] = None,
    ) -> RegressionResult:
        """Compare actual output against stored baseline."""
        baseline = self.load_baseline(skill_id, test_case_id)
        if baseline is None:
            return RegressionResult(
                skill_id=skill_id,
                test_case_id=test_case_id,
                passed=False,
                error="No baseline found",
            )

        actual_keys = set(actual_output.keys())
        expected_keys = set(baseline.expected_keys)
        if required_keys:
            expected_keys.update(required_keys)

        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)

        signature = _output_signature(actual_output)
        sig_match = signature == baseline.expected_output_signature

        passed = (
            len(missing) == 0
            and (not exact_signature or sig_match)
        )

        return RegressionResult(
            skill_id=skill_id,
            test_case_id=test_case_id,
            passed=passed,
            key_matches=sorted(actual_keys & expected_keys),
            missing_keys=missing,
            extra_keys=extra,
            signature_match=sig_match,
        )

    def list_baselines(self, skill_id: Optional[str] = None) -> List[Tuple[str, str]]:
        """List all recorded baselines."""
        results = []
        if not self.baseline_dir.exists():
            return results

        for path in self.baseline_dir.glob("*.json"):
            # Format: skill_id__test_case_id.json
            name = path.stem
            if "__" in name:
                sid, tcid = name.split("__", 1)
                if skill_id is None or sid == skill_id:
                    results.append((sid, tcid))
        return sorted(results)
