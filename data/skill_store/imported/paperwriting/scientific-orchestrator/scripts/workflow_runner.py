#!/usr/bin/env python3
"""Validate workflow progress and generate progress reports."""

import json
import sys
from pathlib import Path

from state_manager import load_state, save_state, VALID_STAGES, VALID_WORKFLOW_STATUSES

# Workflow definitions: workflow_id -> ordered list of stages
WORKFLOW_DEFINITIONS = {
    "paper_pipeline": [
        "ideation",
        "literature",
        "design",
        "analysis",
        "visualization",
        "illustration",
        "manuscript",
        "review",
        "communication",
    ],
    "data_to_paper": [
        "visualization",
        "illustration",
        "manuscript",
        "review",
        "communication",
    ],
    "paper_to_presentation": [
        "illustration",
        "communication",
    ],
    "grant_pipeline": [
        "ideation",
        "literature",
        "design",
        "grant",
    ],
    "quick_poster": [
        "ideation",
        "illustration",
        "communication",
    ],
    "review_and_revise": [
        "review",
        "manuscript",
        "communication",
    ],
}

# Stage dependencies: stage -> list of prerequisite stages
STAGE_DEPENDENCIES = {
    "literature": ["ideation"],
    "design": ["literature"],
    "analysis": ["design"],
    "visualization": ["analysis"],
    "illustration": ["design"],
    "manuscript": ["visualization"],
    "review": ["manuscript"],
    "communication": ["manuscript"],
    "grant": ["design"],
}


def validate_state(state: dict) -> list[dict]:
    """Validate a project state and return list of issues."""
    issues = []

    # Check required fields
    required_fields = [
        "project_id",
        "created_at",
        "updated_at",
        "current_stage",
        "completed_stages",
        "workflows",
    ]
    for field in required_fields:
        if field not in state:
            issues.append(
                {"severity": "error", "field": field, "message": "Missing required field"}
            )

    # Check current_stage validity
    if state.get("current_stage") not in VALID_STAGES and state.get(
        "current_stage"
    ) != "unknown":
        issues.append(
            {
                "severity": "error",
                "field": "current_stage",
                "message": f"Invalid stage: {state['current_stage']}",
            }
        )

    # Check completed_stages validity
    for stage in state.get("completed_stages", []):
        if stage not in VALID_STAGES:
            issues.append(
                {
                    "severity": "warning",
                    "field": "completed_stages",
                    "message": f"Unknown stage in completed list: {stage}",
                }
            )

    # Check workflow definitions
    for wf_id, wf in state.get("workflows", {}).items():
        if wf.get("status") not in VALID_WORKFLOW_STATUSES:
            issues.append(
                {
                    "severity": "warning",
                    "field": f"workflows.{wf_id}.status",
                    "message": f"Invalid status: {wf.get('status')}",
                }
            )

        current_step = wf.get("current_step", 0)
        total_steps = wf.get("total_steps", 0)
        if current_step > total_steps:
            issues.append(
                {
                    "severity": "error",
                    "field": f"workflows.{wf_id}",
                    "message": f"current_step ({current_step}) > total_steps ({total_steps})",
                }
            )

    # Check dependency satisfaction
    current = state.get("current_stage")
    completed = set(state.get("completed_stages", []))
    if current in STAGE_DEPENDENCIES:
        for prereq in STAGE_DEPENDENCIES[current]:
            if prereq not in completed and prereq != current:
                issues.append(
                    {
                        "severity": "warning",
                        "field": "dependencies",
                        "message": f"Stage '{current}' depends on '{prereq}' which is not completed",
                    }
                )

    return issues


def get_workflow_progress(state: dict, workflow_id: str) -> dict:
    """Calculate progress for a specific workflow."""
    if workflow_id not in WORKFLOW_DEFINITIONS:
        return {
            "error": f"Unknown workflow: {workflow_id}",
            "known_workflows": list(WORKFLOW_DEFINITIONS.keys()),
        }

    stages = WORKFLOW_DEFINITIONS[workflow_id]
    completed = set(state.get("completed_stages", []))
    current = state.get("current_stage")

    stage_status = []
    completed_count = 0

    for stage in stages:
        if stage in completed:
            status = "completed"
            completed_count += 1
        elif stage == current:
            status = "in_progress"
        else:
            status = "pending"

        # Check if dependencies are satisfied
        deps = STAGE_DEPENDENCIES.get(stage, [])
        missing_deps = [d for d in deps if d not in completed and d != stage]

        stage_status.append(
            {
                "stage": stage,
                "status": status,
                "dependencies": deps,
                "missing_dependencies": missing_deps,
                "can_start": len(missing_deps) == 0 or status != "pending",
            }
        )

    total = len(stages)
    percent = (completed_count / total * 100) if total > 0 else 0

    # Find next actionable stage
    next_stage = None
    for ss in stage_status:
        if ss["status"] == "in_progress":
            next_stage = ss["stage"]
            break
        elif ss["status"] == "pending" and ss["can_start"]:
            next_stage = ss["stage"]
            break

    return {
        "workflow_id": workflow_id,
        "total_stages": total,
        "completed_stages": completed_count,
        "in_progress_stages": 1 if current in stages and current not in completed else 0,
        "percent_complete": round(percent, 1),
        "next_stage": next_stage,
        "stage_status": stage_status,
    }


def report(base_dir: Path, workflow_id: str | None = None, project_id: str | None = None) -> dict:
    """Generate a full progress report."""
    state = load_state(base_dir, project_id)
    issues = validate_state(state)

    # Determine which workflow to report on
    if workflow_id is None:
        workflow_id = state.get("active_workflow", "paper_pipeline")

    progress = get_workflow_progress(state, workflow_id)

    # Also report on all workflows in state
    all_workflows = {}
    for wf_id in state.get("workflows", {}):
        all_workflows[wf_id] = get_workflow_progress(state, wf_id)

    return {
        "project_id": state.get("project_id"),
        "current_stage": state.get("current_stage"),
        "completed_stages": state.get("completed_stages", []),
        "active_workflow": workflow_id,
        "validation_issues": issues,
        "primary_workflow": progress,
        "all_workflows": all_workflows,
        "metadata": state.get("metadata", {}),
    }


def print_report(report_data: dict) -> None:
    """Print a human-readable report."""
    print(f"Workflow Progress Report")
    print(f"{'=' * 60}")
    print(f"Project ID:      {report_data['project_id']}")
    print(f"Current Stage:   {report_data['current_stage'].upper()}")
    print(
        f"Completed:       {', '.join(report_data['completed_stages']) or '(none)'}"
    )
    print(f"Active Workflow: {report_data['active_workflow']}")
    print()

    # Validation issues
    if report_data["validation_issues"]:
        print("Validation Issues:")
        for issue in report_data["validation_issues"]:
            icon = "ERROR" if issue["severity"] == "error" else "WARN"
            print(f"  [{icon}] {issue['field']}: {issue['message']}")
        print()

    # Primary workflow progress
    primary = report_data["primary_workflow"]
    if "error" in primary:
        print(f"Workflow Error: {primary['error']}")
    else:
        print(
            f"Progress: {primary['completed_stages']}/{primary['total_stages']} stages complete ({primary['percent_complete']}%)"
        )
        if primary["next_stage"]:
            print(f"Next Stage: {primary['next_stage'].upper()}")
        print()

        print("Stage Breakdown:")
        for ss in primary["stage_status"]:
            icon = {
                "completed": "[x]",
                "in_progress": "[>]",
                "pending": "[ ]",
            }.get(ss["status"], "[?]")
            deps = ""
            if ss["missing_dependencies"]:
                deps = f" (needs: {', '.join(ss['missing_dependencies'])})"
            print(
                f"  {icon} {ss['stage']:15s} {ss['status']:12s}{deps}"
            )

    print()
    print("Metadata:")
    for key, value in report_data["metadata"].items():
        if value:
            if isinstance(value, list):
                print(f"  {key}: {', '.join(value)}")
            else:
                print(f"  {key}: {value}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate and report workflow progress."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Working directory (default: current directory)",
    )
    parser.add_argument(
        "--project-id", type=str, default=None, help="Target specific project ID"
    )
    parser.add_argument(
        "--workflow", type=str, default=None, help="Workflow to report on"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation, skip progress report",
    )

    args = parser.parse_args()

    base_dir = Path(args.dir).resolve()

    if not base_dir.exists():
        print(f"Error: Directory not found: {base_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.validate_only:
            state = load_state(base_dir, args.project_id)
            issues = validate_state(state)
            if args.json:
                print(json.dumps({"issues": issues}, indent=2, ensure_ascii=False))
            else:
                if issues:
                    print(f"Found {len(issues)} issue(s):")
                    for issue in issues:
                        icon = "ERROR" if issue["severity"] == "error" else "WARN"
                        print(f"  [{icon}] {issue['field']}: {issue['message']}")
                else:
                    print("State validation passed. No issues found.")
        else:
            result = report(base_dir, args.workflow, args.project_id)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print_report(result)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
