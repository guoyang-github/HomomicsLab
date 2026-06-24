"""Core HITL skill: surface a checkpoint for human resolution.

When invoked without a ``resolution`` input, the skill returns a HITL
checkpoint payload that tells the Orchestrator to pause the task and wait
for human input. When resumed with a ``resolution`` input, it echoes the
resolution back so downstream phases can use it.
"""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Create a HITL checkpoint or finalize a resolved one."""
    if "resolution" in skill_inputs:
        # Resumed execution: the human has provided a resolution.
        return {
            "status": "completed",
            "resolution": skill_inputs["resolution"],
        }

    checkpoint_type = skill_inputs.get("checkpoint_type", "approval")
    message = skill_inputs.get("message", "Please confirm before continuing.")
    options = skill_inputs.get("options", [])
    payload = skill_inputs.get("payload", {})

    # Normalize options to a list of dicts.
    normalized_options = []
    for option in options:
        if isinstance(option, dict):
            normalized_options.append(option)
        else:
            normalized_options.append({"id": str(option), "label": str(option)})
    if not normalized_options:
        normalized_options = [
            {"id": "approve", "label": "Approve", "description": "Proceed with the action"},
            {"id": "cancel", "label": "Cancel", "description": "Skip this step"},
        ]

    return {
        "status": "awaiting_human",
        "hitl": {
            "trigger_reason": "policy",
            "context_summary": message,
            "options": normalized_options,
            "metadata": {
                "checkpoint_type": checkpoint_type,
                "payload": payload,
            },
        },
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
