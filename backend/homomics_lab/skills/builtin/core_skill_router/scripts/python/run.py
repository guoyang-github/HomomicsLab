"""Core skill router: select appropriate skills for a task."""

import json
import sys


def main(skill_inputs: dict) -> dict:
    """Return skill recommendations for the task."""
    task = skill_inputs["task"]
    candidates = skill_inputs.get("candidates", [])
    data_state = skill_inputs.get("data_state", {})

    # Skeleton implementation: prefer exact keyword matches.
    # In production this uses SkillDAG + semantic search + schema compatibility.
    task_lower = task.lower()
    selected = []
    for candidate in candidates:
        skill_id = candidate if isinstance(candidate, str) else candidate.get("id", "")
        keywords = candidate.get("keywords", []) if isinstance(candidate, dict) else []
        if any(kw.lower() in task_lower for kw in keywords):
            selected.append(skill_id)

    if not selected and candidates:
        first = candidates[0]
        selected.append(first if isinstance(first, str) else first.get("id", ""))

    return {
        "selected_skills": selected,
        "rationale": f"Selected skills based on task keywords and data state keys: {list(data_state.keys())}.",
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
