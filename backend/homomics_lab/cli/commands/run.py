"""`homomics run` command: execute a skill from the CLI."""

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List

from homomics_lab.bootstrap import bootstrap_worker_context
from homomics_lab.skills.runtime import UntrustedSkillError


def _coerce_value(value: str) -> Any:
    """Coerce a CLI string value to a Python scalar when possible."""
    value = value.strip()
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value == "null" or value == "none":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    # Try JSON for lists/dicts; fall back to raw string.
    if (value.startswith("[") and value.endswith("]")) or (
        value.startswith("{") and value.endswith("}")
    ):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def _parse_run_args(raw: List[str]) -> Dict[str, Any]:
    """Parse `--arg key=value` pairs into a dictionary."""
    parsed: Dict[str, Any] = {}
    for item in raw:
        if "=" not in item:
            raise argparse.ArgumentTypeError(
                f"Invalid argument '{item}'. Expected key=value."
            )
        key, value = item.split("=", 1)
        parsed[key.strip()] = _coerce_value(value)
    return parsed


def register_run_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "run",
        help="Execute a skill by ID",
    )
    parser.add_argument("skill_id", help="Skill ID to execute")
    parser.add_argument(
        "--arg",
        "-a",
        dest="args",
        action="append",
        default=[],
        help="Input argument as key=value (can be repeated)",
    )
    parser.add_argument(
        "--trust",
        action="store_true",
        help="Trust an external/community skill without prompting",
    )
    parser.add_argument(
        "--working-dir",
        "-w",
        help="Working directory for skill execution",
        default=None,
    )


async def _run_skill(args: argparse.Namespace) -> int:
    from pathlib import Path

    inputs = _parse_run_args(args.args)
    if args.working_dir:
        working_dir = Path(args.working_dir).resolve()
        working_dir.mkdir(parents=True, exist_ok=True)
    else:
        working_dir = Path.cwd()

    ctx = await bootstrap_worker_context()
    executor = ctx["skill_executor"]
    skill_store = ctx["skill_store"]

    skill = executor.registry.get(args.skill_id)
    if skill is None:
        print(f"Error: Skill '{args.skill_id}' not found", file=sys.stderr)
        return 1

    source = skill.metadata.get("source") or "builtin"
    if source in {"external", "community", "imported"} and not skill.metadata.get("trusted"):
        if args.trust:
            skill_store.trust_skill(args.skill_id, trusted=True)
        elif sys.stdin.isatty():
            prompt = (
                f"Skill '{args.skill_id}' from source '{source}' is not trusted. "
                "Trust and run? [y/N]: "
            )
            answer = input(prompt).strip().lower()
            if answer.startswith("y"):
                skill_store.trust_skill(args.skill_id, trusted=True)
            else:
                print("Aborted.", file=sys.stderr)
                return 1
        else:
            raise UntrustedSkillError(
                f"Skill '{args.skill_id}' from source '{source}' is not trusted. "
                f"Run with --trust or use 'homomics trust {args.skill_id}'."
            )

    executor.working_dir = working_dir
    result = await executor.execute(args.skill_id, inputs)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("success", True) else 1


def run_run(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_run_skill(args))
    except UntrustedSkillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
