"""Core interpretation skill: explain analysis outputs."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Interpret skill outputs and produce a human-readable summary."""
    outputs = skill_inputs["outputs"]
    question = skill_inputs.get("question", "")
    audience = skill_inputs.get("audience", "biologist")

    # Skeleton implementation.
    # In production this calls the InterpretationEngine / LLM.
    findings = []
    for key, value in outputs.items():
        findings.append(f"{key}: {value}")

    return {
        "summary": f"Interpretation for {audience} audience. " + (question or "General summary of results."),
        "key_findings": findings[:10],
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
