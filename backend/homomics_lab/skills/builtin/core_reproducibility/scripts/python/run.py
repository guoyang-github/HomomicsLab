"""Core reproducibility skill: capture execution provenance."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Build a provenance record from the execution log."""
    execution_log = skill_inputs["execution_log"]
    artifacts = skill_inputs.get("artifacts", [])

    # Skeleton implementation.
    # In production this calls the ReproducibilityEngine.
    steps = execution_log.get("steps", [])
    provenance = {
        "workflow_id": execution_log.get("workflow_id", "unknown"),
        "steps": [
            {
                "skill_id": step.get("skill_id"),
                "inputs": step.get("inputs"),
                "runtime": step.get("runtime"),
            }
            for step in steps
        ],
        "artifacts": artifacts,
        "recorded_at": execution_log.get("recorded_at"),
    }

    return {"provenance": provenance}


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
