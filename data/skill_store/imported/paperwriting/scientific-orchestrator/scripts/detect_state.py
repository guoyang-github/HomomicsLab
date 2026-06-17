#!/usr/bin/env python3
"""Detect project state by scanning for artifact files in the working directory."""

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Artifact detection rules: stage -> list of (glob_pattern, min_count, confidence_boost)
ARTIFACT_RULES = {
    "ideation": [
        ("research_question.md", 1, "high"),
        ("risk_assessment.md", 1, "high"),
        ("decision_tree.md", 1, "medium"),
        ("hypothesis.md", 1, "medium"),
    ],
    "literature": [
        ("literature_review.md", 1, "high"),
        ("knowledge_gaps.md", 1, "high"),
        ("*.bib", 10, "medium"),
        ("references/*.md", 5, "low"),
    ],
    "design": [
        ("experimental_design.md", 1, "high"),
        ("hypothesis_framework.md", 1, "high"),
        ("statistical_plan.md", 1, "medium"),
        ("protocol.md", 1, "medium"),
    ],
    "analysis": [
        ("data/*", 1, "low"),
        ("results/*", 1, "low"),
        ("*.csv", 1, "low"),
        ("*.xlsx", 1, "low"),
        ("analysis.py", 1, "medium"),
        ("analysis.R", 1, "medium"),
        ("*.ipynb", 1, "medium"),
    ],
    "visualization": [
        ("figures/*.png", 1, "low"),
        ("figures/*.pdf", 1, "high"),
        ("figures/*.tiff", 1, "high"),
        ("figures/*.svg", 1, "high"),
        ("figure_captions.md", 1, "medium"),
    ],
    "illustration": [
        ("schematics/*", 1, "high"),
        ("diagrams/*", 1, "high"),
        ("*schematic*.png", 1, "medium"),
        ("*diagram*.png", 1, "medium"),
    ],
    "manuscript": [
        ("manuscript.md", 1, "high"),
        ("manuscript.docx", 1, "high"),
        ("*.tex", 1, "high"),
        ("abstract.md", 1, "medium"),
        ("introduction.md", 1, "medium"),
        ("methods.md", 1, "medium"),
        ("results.md", 1, "medium"),
        ("discussion.md", 1, "medium"),
    ],
    "review": [
        ("review_report.md", 1, "high"),
        ("reviewer_response.md", 1, "high"),
        ("revision_notes.md", 1, "high"),
    ],
    "communication": [
        ("*.pptx", 1, "high"),
        ("poster.pdf", 1, "high"),
        ("poster.tex", 1, "high"),
        ("slides.tex", 1, "high"),
        ("website/*", 1, "medium"),
        ("docs/*", 1, "medium"),
    ],
    "grant": [
        ("proposal.pdf", 1, "high"),
        ("proposal.md", 1, "high"),
        ("budget.xlsx", 1, "medium"),
        ("budget.csv", 1, "medium"),
        ("timeline.gantt", 1, "medium"),
        ("timeline.md", 1, "medium"),
        ("biosketch.md", 1, "medium"),
        ("specific_aims.md", 1, "high"),
        ("project_summary.md", 1, "high"),
        ("*立项依据*.md", 1, "high"),
    ],
}

# Confidence scoring weights
CONFIDENCE_WEIGHTS = {"high": 3, "medium": 2, "low": 1}
CONFIDENCE_THRESHOLD = 3  # Minimum score to consider stage "detected"


def count_matches(base_dir: Path, pattern: str, min_count: int) -> tuple[int, str]:
    """Count files matching pattern. Returns (count, representative_path)."""
    if "/" in pattern:
        # Directory-specific pattern
        parts = pattern.split("/")
        subdir = parts[0]
        file_pattern = parts[1]
        search_dir = base_dir / subdir
        if not search_dir.exists():
            return 0, ""
        matches = list(search_dir.glob(file_pattern))
    else:
        matches = list(base_dir.glob(pattern))

    if not matches:
        return 0, ""

    return len(matches), str(matches[0].relative_to(base_dir))


def detect_stage(base_dir: Path) -> dict[str, dict]:
    """Detect which stages have artifacts in the directory."""
    detected = {}

    for stage, rules in ARTIFACT_RULES.items():
        score = 0
        found_artifacts = []

        for pattern, min_count, confidence in rules:
            count, rep_path = count_matches(base_dir, pattern, min_count)
            if count >= min_count:
                score += CONFIDENCE_WEIGHTS[confidence]
                found_artifacts.append(
                    {"pattern": pattern, "count": count, "example": rep_path}
                )

        if score >= CONFIDENCE_THRESHOLD:
            detected[stage] = {
                "detected": True,
                "confidence_score": score,
                "artifacts": found_artifacts,
            }
        else:
            detected[stage] = {
                "detected": False,
                "confidence_score": score,
                "artifacts": found_artifacts,
            }

    return detected


def infer_current_stage(detected: dict[str, dict]) -> str:
    """Infer the current project stage from detected artifacts."""
    # Stage order for progression inference
    stage_order = [
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

    detected_stages = [s for s in stage_order if detected.get(s, {}).get("detected")]

    if not detected_stages:
        return "unknown"

    # The "current" stage is the highest detected stage in the order
    # (assumes progress is sequential)
    return detected_stages[-1]


def find_state_files(base_dir: Path) -> list[Path]:
    """Find existing project state files."""
    return list(base_dir.glob(".scientific-project*.json"))


def generate_project_id() -> str:
    """Generate a unique project ID."""
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6]
    return f"proj-{date_prefix}-{suffix}"


def reconstruct_state(base_dir: Path) -> dict:
    """Reconstruct project state from detected artifacts."""
    detected = detect_stage(base_dir)
    current_stage = infer_current_stage(detected)

    completed_stages = []
    stage_order = [
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

    # All stages before current are considered completed
    if current_stage in stage_order:
        current_idx = stage_order.index(current_stage)
        completed_stages = stage_order[:current_idx]

    # Collect artifact paths
    artifacts = {stage: [] for stage in stage_order}
    for stage, info in detected.items():
        if info["detected"]:
            for art in info["artifacts"]:
                if art["example"]:
                    artifacts[stage].append(art["example"])

    # Deduplicate artifact paths
    for stage in artifacts:
        artifacts[stage] = list(dict.fromkeys(artifacts[stage]))

    now = datetime.now(timezone.utc).isoformat()

    return {
        "project_id": generate_project_id(),
        "created_at": now,
        "updated_at": now,
        "version": "1.0.0",
        "current_stage": current_stage,
        "completed_stages": completed_stages,
        "active_workflow": "unknown",
        "workflows": {},
        "artifacts": artifacts,
        "metadata": {
            "title": "",
            "description": "",
            "target_journal": "",
            "target_conference": "",
            "funding_agency": "",
            "deadline": "",
            "research_field": "",
            "keywords": [],
            "notes": f"Auto-detected from directory scan on {now[:10]}",
        },
        "_detected": detected,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect project state from artifact files in a directory."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable report",
    )
    parser.add_argument(
        "--init-state",
        action="store_true",
        help="Write reconstructed state to .scientific-project.json",
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default="paper_pipeline",
        help="Workflow to assign if initializing state (default: paper_pipeline)",
    )
    args = parser.parse_args()

    base_dir = Path(args.dir).resolve()

    if not base_dir.exists():
        print(f"Error: Directory not found: {base_dir}", file=sys.stderr)
        sys.exit(1)

    # Check for existing state files
    state_files = find_state_files(base_dir)

    detected = detect_stage(base_dir)
    current_stage = infer_current_stage(detected)

    if args.json:
        state = reconstruct_state(base_dir)
        if state_files:
            state["_existing_state_files"] = [str(f.name) for f in state_files]
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return

    # Human-readable report
    print(f"Project State Detection Report")
    print(f"Directory: {base_dir}")
    print(f"{'=' * 50}")

    if state_files:
        print(f"\nExisting state file(s) found:")
        for sf in state_files:
            print(f"  - {sf.name}")
        print(
            "\n(Run with --init-state to overwrite or use state_manager.py to update)"
        )

    print(f"\nInferred current stage: {current_stage.upper()}")
    print(f"\nStage detection details:")

    for stage in ARTIFACT_RULES:
        info = detected[stage]
        status = "DETECTED" if info["detected"] else "not detected"
        score = info["confidence_score"]
        print(f"\n  [{stage:15s}] {status:12s} (score: {score})")
        for art in info["artifacts"]:
            print(f"    - {art['pattern']}: {art['count']} match(es)")

    print(f"\n{'=' * 50}")
    print(f"Recommended next skill: ", end="")

    skill_map = {
        "unknown": "scientific-ideation (start a new project)",
        "ideation": "scientific-literature-review",
        "literature": "scientific-research-design",
        "design": "(external: data collection / analysis)",
        "analysis": "scientific-visualization",
        "visualization": "scientific-illustration",
        "illustration": "scientific-manuscript",
        "manuscript": "scientific-peer-review",
        "review": "scientific-communication (or submit)",
        "communication": "(project complete)",
        "grant": "(proposal submitted)",
    }
    print(skill_map.get(current_stage, "unknown"))

    if args.init_state:
        state = reconstruct_state(base_dir)
        state["active_workflow"] = args.workflow
        state["workflows"] = {
            args.workflow: {
                "status": "in_progress",
                "current_step": 1,
                "total_steps": 8,
                "started_at": state["created_at"],
                "completed_at": None,
            }
        }
        # Remove internal detection metadata before saving
        state.pop("_detected", None)

        state_path = base_dir / ".scientific-project.json"
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"\nState written to: {state_path}")


if __name__ == "__main__":
    main()
