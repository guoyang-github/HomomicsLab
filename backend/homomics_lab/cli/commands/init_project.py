"""`homomics init-project` command: scaffold a local HomomicsLab project."""

import argparse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


TEMPLATES: Dict[str, Dict[str, str]] = {
    "blank": {
        "domain": "generic",
        "description": "Blank HomomicsLab project.",
        "default_phases": "",
    },
    "metagenomics": {
        "domain": "metagenomics",
        "description": "16S / metagenomics analysis project.",
        "default_phases": "qc,denoising,taxonomy,functional,visualization",
    },
    "genomics": {
        "domain": "genomics",
        "description": "General genomics analysis project.",
        "default_phases": "qc,alignment,variant_calling,annotation",
    },
    "rnaseq": {
        "domain": "rnaseq",
        "description": "Bulk RNA-seq differential expression project.",
        "default_phases": "qc,alignment,quantification,de_analysis,visualization",
    },
}


def _project_yaml(name: str, template_key: str) -> str:
    tmpl = TEMPLATES[template_key]
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    phases = (
        "\n  - " + "\n  - ".join(tmpl["default_phases"].split(","))
        if tmpl["default_phases"]
        else ""
    )
    return f"""project:
  id: {project_id}
  name: {name}
  description: {tmpl['description']}
  domain: {tmpl['domain']}
  created_at: {created_at}
  default_phases:{phases}

settings:
  auto_save: true
  result_dir: ./results
  data_dir: ./data
  workspace_dir: ./workspace
"""


def _memory_md(name: str) -> str:
    return f"""# {name}

Experiment log for HomomicsLab project `{name}`.

## Notes

- Created at: {datetime.now(timezone.utc).isoformat()}
- Use this file to record hypotheses, decisions, and results.
"""


def register_init_project_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "init-project",
        help="Initialize a local HomomicsLab project directory",
    )
    parser.add_argument("name", help="Project name")
    parser.add_argument(
        "--template",
        "-t",
        choices=list(TEMPLATES.keys()),
        default="blank",
        help="Project template",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Parent directory for the new project",
        default=".",
    )


def init_project(args: argparse.Namespace) -> int:
    name = args.name
    template = args.template
    parent_dir = Path(args.output).resolve()
    parent_dir.mkdir(parents=True, exist_ok=True)

    project_dir = parent_dir / name
    if project_dir.exists():
        print(f"Error: directory already exists: {project_dir}", file=__import__("sys").stderr)
        return 1

    project_dir.mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "results").mkdir()
    (project_dir / "workspace").mkdir()
    (project_dir / "homomics.yaml").write_text(
        _project_yaml(name, template), encoding="utf-8"
    )
    (project_dir / "MEMORY.md").write_text(
        _memory_md(name), encoding="utf-8"
    )

    print(f"Created project '{name}' at {project_dir}")
    print(f"Template: {template}")
    return 0
