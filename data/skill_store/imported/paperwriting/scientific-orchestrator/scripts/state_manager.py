#!/usr/bin/env python3
"""CRUD operations for the scientific project state file."""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_FILE = ".scientific-project.json"

# Valid stages matching the state model specification
VALID_STAGES = [
    "ideation",
    "literature",
    "design",
    "analysis",
    "visualization",
    "illustration",
    "manuscript",
    "review",
    "communication",
    "grant",
]

VALID_WORKFLOW_STATUSES = ["not_started", "in_progress", "paused", "completed"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_project_id() -> str:
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6]
    return f"proj-{date_prefix}-{suffix}"


def find_state_file(base_dir: Path, project_id: str | None = None) -> Path | None:
    """Find a state file in the directory."""
    if project_id:
        specific = base_dir / f".scientific-project-{project_id}.json"
        if specific.exists():
            return specific

    default = base_dir / DEFAULT_STATE_FILE
    if default.exists():
        return default

    # Look for any state file
    candidates = list(base_dir.glob(".scientific-project*.json"))
    if candidates:
        return candidates[0]

    return None


def load_state(base_dir: Path, project_id: str | None = None) -> dict:
    """Load project state from file."""
    state_file = find_state_file(base_dir, project_id)
    if not state_file:
        raise FileNotFoundError(
            f"No project state file found in {base_dir}. "
            f"Run with --init to create one."
        )

    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(base_dir: Path, state: dict, project_id: str | None = None) -> Path:
    """Save project state to file."""
    if project_id:
        state_file = base_dir / f".scientific-project-{project_id}.json"
    else:
        state_file = base_dir / DEFAULT_STATE_FILE

    state["updated_at"] = now_iso()

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return state_file


def init_state(
    base_dir: Path,
    workflow: str = "paper_pipeline",
    title: str = "",
    target_journal: str = "",
    deadline: str = "",
    research_field: str = "",
) -> dict:
    """Initialize a new project state."""
    existing = find_state_file(base_dir)
    if existing:
        raise FileExistsError(
            f"State file already exists: {existing}. "
            f"Use --force to overwrite, or update the existing state."
        )

    now = now_iso()
    state = {
        "project_id": generate_project_id(),
        "created_at": now,
        "updated_at": now,
        "version": "1.0.0",
        "current_stage": "ideation",
        "completed_stages": [],
        "active_workflow": workflow,
        "workflows": {
            workflow: {
                "status": "in_progress",
                "current_step": 1,
                "total_steps": 8,
                "started_at": now,
                "completed_at": None,
            }
        },
        "artifacts": {stage: [] for stage in VALID_STAGES},
        "metadata": {
            "title": title,
            "description": "",
            "target_journal": target_journal,
            "target_conference": "",
            "funding_agency": "",
            "deadline": deadline,
            "research_field": research_field,
            "keywords": [],
            "notes": "",
        },
    }

    save_state(base_dir, state)
    return state


def complete_stage(base_dir: Path, stage: str, project_id: str | None = None) -> dict:
    """Mark a stage as complete and advance current stage."""
    state = load_state(base_dir, project_id)

    if stage not in VALID_STAGES:
        raise ValueError(
            f"Invalid stage: {stage}. Valid stages: {', '.join(VALID_STAGES)}"
        )

    # Add to completed if not already there
    if stage not in state["completed_stages"]:
        state["completed_stages"].append(stage)

    # Advance current_stage to the next in sequence
    stage_order = VALID_STAGES
    if stage in stage_order:
        idx = stage_order.index(stage)
        if idx + 1 < len(stage_order):
            state["current_stage"] = stage_order[idx + 1]
        else:
            state["current_stage"] = stage  # Stay at last stage

    # Update workflow progress
    workflow_id = state.get("active_workflow")
    if workflow_id and workflow_id in state.get("workflows", {}):
        wf = state["workflows"][workflow_id]
        if wf.get("status") == "in_progress":
            wf["current_step"] = wf.get("current_step", 1) + 1
            if wf["current_step"] >= wf.get("total_steps", 1):
                wf["status"] = "completed"
                wf["completed_at"] = now_iso()

    save_state(base_dir, state, project_id)
    return state


def add_artifact(
    base_dir: Path, stage: str, artifact_path: str, project_id: str | None = None
) -> dict:
    """Add an artifact path to a stage."""
    state = load_state(base_dir, project_id)

    if stage not in VALID_STAGES:
        raise ValueError(
            f"Invalid stage: {stage}. Valid stages: {', '.join(VALID_STAGES)}"
        )

    if artifact_path not in state["artifacts"][stage]:
        state["artifacts"][stage].append(artifact_path)

    save_state(base_dir, state, project_id)
    return state


def set_workflow(
    base_dir: Path, workflow: str, total_steps: int = 8, project_id: str | None = None
) -> dict:
    """Set or switch the active workflow."""
    state = load_state(base_dir, project_id)

    # Pause current workflow if exists
    current_wf = state.get("active_workflow")
    if current_wf and current_wf in state.get("workflows", {}):
        if state["workflows"][current_wf].get("status") == "in_progress":
            state["workflows"][current_wf]["status"] = "paused"

    state["active_workflow"] = workflow

    if workflow not in state.get("workflows", {}):
        state["workflows"][workflow] = {
            "status": "in_progress",
            "current_step": 1,
            "total_steps": total_steps,
            "started_at": now_iso(),
            "completed_at": None,
        }
    else:
        state["workflows"][workflow]["status"] = "in_progress"

    save_state(base_dir, state, project_id)
    return state


def update_metadata(
    base_dir: Path, key: str, value: str, project_id: str | None = None
) -> dict:
    """Update a metadata field."""
    state = load_state(base_dir, project_id)

    valid_keys = [
        "title",
        "description",
        "target_journal",
        "target_conference",
        "funding_agency",
        "deadline",
        "research_field",
        "notes",
    ]

    if key not in valid_keys:
        raise ValueError(
            f"Invalid metadata key: {key}. Valid keys: {', '.join(valid_keys)}"
        )

    state["metadata"][key] = value
    save_state(base_dir, state, project_id)
    return state


def add_keyword(
    base_dir: Path, keyword: str, project_id: str | None = None
) -> dict:
    """Add a keyword to the project."""
    state = load_state(base_dir, project_id)

    if keyword not in state["metadata"].get("keywords", []):
        state["metadata"]["keywords"].append(keyword)

    save_state(base_dir, state, project_id)
    return state


def show_state(base_dir: Path, project_id: str | None = None) -> None:
    """Print a human-readable summary of project state."""
    state = load_state(base_dir, project_id)

    print(f"Project State Summary")
    print(f"{'=' * 50}")
    print(f"Project ID:    {state['project_id']}")
    print(f"Created:       {state['created_at'][:10]}")
    print(f"Last Updated:  {state['updated_at'][:10]}")
    print(f"Version:       {state['version']}")
    print()
    print(f"Current Stage: {state['current_stage'].upper()}")
    print(f"Completed:     {', '.join(state['completed_stages']) or '(none)'}")
    print()
    print(f"Active Workflow: {state.get('active_workflow', 'none')}")
    for wf_id, wf in state.get("workflows", {}).items():
        print(f"  {wf_id}:")
        print(f"    Status: {wf.get('status', 'unknown')}")
        print(
            f"    Progress: {wf.get('current_step', 0)}/{wf.get('total_steps', 0)}"
        )
    print()
    print("Metadata:")
    for key, value in state["metadata"].items():
        if value:
            if isinstance(value, list):
                print(f"  {key}: {', '.join(value)}")
            else:
                print(f"  {key}: {value}")
    print()
    print("Artifacts:")
    for stage, artifacts in state["artifacts"].items():
        if artifacts:
            print(f"  [{stage}]")
            for art in artifacts:
                print(f"    - {art}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage scientific project state files."
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

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # init
    init_parser = subparsers.add_parser("init", help="Initialize a new project state")
    init_parser.add_argument(
        "--workflow", type=str, default="paper_pipeline", help="Workflow template"
    )
    init_parser.add_argument("--title", type=str, default="", help="Project title")
    init_parser.add_argument(
        "--target-journal", type=str, default="", help="Target journal"
    )
    init_parser.add_argument("--deadline", type=str, default="", help="Deadline (YYYY-MM-DD)")
    init_parser.add_argument("--field", type=str, default="", help="Research field")
    init_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing state"
    )

    # complete-stage
    complete_parser = subparsers.add_parser(
        "complete-stage", help="Mark a stage as complete"
    )
    complete_parser.add_argument("stage", type=str, help="Stage name to complete")

    # add-artifact
    artifact_parser = subparsers.add_parser(
        "add-artifact", help="Add an artifact to a stage"
    )
    artifact_parser.add_argument("stage", type=str, help="Stage name")
    artifact_parser.add_argument("path", type=str, help="Artifact file path")

    # set-workflow
    wf_parser = subparsers.add_parser(
        "set-workflow", help="Set or switch active workflow"
    )
    wf_parser.add_argument("workflow", type=str, help="Workflow ID")
    wf_parser.add_argument(
        "--steps", type=int, default=8, help="Total steps in workflow"
    )

    # update-metadata
    meta_parser = subparsers.add_parser(
        "update-metadata", help="Update a metadata field"
    )
    meta_parser.add_argument("key", type=str, help="Metadata key")
    meta_parser.add_argument("value", type=str, help="Metadata value")

    # add-keyword
    kw_parser = subparsers.add_parser("add-keyword", help="Add a keyword")
    kw_parser.add_argument("keyword", type=str, help="Keyword to add")

    # show
    subparsers.add_parser("show", help="Display current project state")

    args = parser.parse_args()

    base_dir = Path(args.dir).resolve()

    if not base_dir.exists():
        print(f"Error: Directory not found: {base_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.command == "init":
            if args.force:
                existing = find_state_file(base_dir)
                if existing:
                    existing.unlink()
            state = init_state(
                base_dir,
                workflow=args.workflow,
                title=args.title,
                target_journal=args.target_journal,
                deadline=args.deadline,
                research_field=args.field,
            )
            state_file = find_state_file(base_dir)
            print(f"Initialized project state: {state['project_id']}")
            print(f"State file: {state_file}")
            print(f"Workflow: {args.workflow}")
            print(f"Current stage: {state['current_stage']}")

        elif args.command == "complete-stage":
            state = complete_stage(base_dir, args.stage, args.project_id)
            print(f"Stage '{args.stage}' marked complete.")
            print(f"Current stage is now: {state['current_stage']}")

        elif args.command == "add-artifact":
            state = add_artifact(base_dir, args.stage, args.path, args.project_id)
            print(f"Added artifact '{args.path}' to stage '{args.stage}'.")

        elif args.command == "set-workflow":
            state = set_workflow(base_dir, args.workflow, args.steps, args.project_id)
            print(f"Active workflow set to: {args.workflow}")

        elif args.command == "update-metadata":
            state = update_metadata(base_dir, args.key, args.value, args.project_id)
            print(f"Updated metadata: {args.key} = {args.value}")

        elif args.command == "add-keyword":
            state = add_keyword(base_dir, args.keyword, args.project_id)
            print(f"Added keyword: {args.keyword}")

        elif args.command == "show":
            show_state(base_dir, args.project_id)

        else:
            parser.print_help()

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
