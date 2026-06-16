"""Core planning skill: decompose a request into an executable plan."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Generate a structured plan from the user request."""
    request = skill_inputs["request"]
    context = skill_inputs.get("context", {})
    constraints = skill_inputs.get("constraints", [])

    # Skeleton implementation: return a minimal plan structure.
    # In production this calls the PlanEngine / LLM planner.
    plan = {
        "goal": request,
        "phases": [
            {"phase": "understand", "description": "Clarify intent and constraints"},
            {"phase": "select_skills", "description": "Select appropriate skills"},
            {"phase": "execute", "description": "Execute the selected skills"},
            {"phase": "interpret", "description": "Interpret and present results"},
        ],
        "selected_skills": [],
        "constraints": constraints,
        "context": context,
    }

    return {
        "plan": plan,
        "reasoning": "Decomposed request into standard analysis phases.",
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
