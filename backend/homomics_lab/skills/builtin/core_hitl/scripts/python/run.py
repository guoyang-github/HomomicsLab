"""Core HITL skill: surface a checkpoint for human resolution."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Create a HITL checkpoint and return a placeholder resolution."""
    checkpoint_type = skill_inputs["checkpoint_type"]
    message = skill_inputs["message"]
    options = skill_inputs.get("options", [])
    payload = skill_inputs.get("payload", {})

    # Skeleton implementation.
    # In production this interfaces with the HITL orchestrator / API.
    resolution = {
        "approved": checkpoint_type != "warning",
        "choice": options[0] if options else None,
        "text": None,
        "payload": payload,
    }

    return {
        "resolution": resolution,
        "checkpoint": {
            "type": checkpoint_type,
            "message": message,
            "options": options,
        },
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
