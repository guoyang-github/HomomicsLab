"""homomics skill - Skill management commands (validate, ...)."""

import sys
from pathlib import Path
from typing import List

from homomics_lab.skills.loader import SkillValidationResult, validate_skill_contract


def register_skill_parser(subparsers):
    """Register the ``skill`` command group."""
    skill_parser = subparsers.add_parser(
        "skill",
        help="Manage skills (validate, ...)",
    )
    skill_subparsers = skill_parser.add_subparsers(dest="skill_command")

    validate_parser = skill_subparsers.add_parser(
        "validate",
        help="Validate SKILL.md files against the minimal skill contract",
    )
    validate_parser.add_argument(
        "path",
        help="Skill directory, a directory containing skill directories, or a SKILL.md file",
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings as well as errors",
    )


def _collect_skill_dirs(path: Path) -> List[Path]:
    """Resolve the CLI path argument to a list of skill directories."""
    if path.is_file() and path.name == "SKILL.md":
        return [path.parent]
    if path.is_dir():
        if (path / "SKILL.md").exists():
            return [path]
        return sorted(
            child
            for child in path.iterdir()
            if child.is_dir() and (child / "SKILL.md").exists()
        )
    return []


def _print_result(result: SkillValidationResult) -> None:
    """Print one structured line per skill."""
    if result.errors:
        status = "ERRORS"
    elif result.warnings:
        status = "WARNINGS"
    else:
        status = "OK"
    issues = "; ".join(result.errors + result.warnings)
    line = f"{status:<8} {result.name}"
    if issues:
        line += f": {issues}"
    print(line)


def run_skill(args) -> int:
    """Dispatch ``homomics skill <subcommand>``."""
    if getattr(args, "skill_command", None) == "validate":
        return _run_validate(args)
    print("Error: missing skill subcommand (available: validate)", file=sys.stderr)
    return 1


def _run_validate(args) -> int:
    """Validate one or more skills against the minimal SKILL.md contract."""
    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path not found: {path}", file=sys.stderr)
        return 1

    skill_dirs = _collect_skill_dirs(path)
    if not skill_dirs:
        print(f"Error: No SKILL.md found under: {path}", file=sys.stderr)
        return 1

    results = [validate_skill_contract(skill_dir) for skill_dir in skill_dirs]
    for result in results:
        _print_result(result)

    n_errors = sum(1 for r in results if r.errors)
    n_warnings = sum(1 for r in results if r.warnings and not r.errors)
    n_ok = len(results) - n_errors - n_warnings
    print()
    print(
        f"Summary: {len(results)} skill(s): {n_ok} OK, {n_warnings} with warnings, {n_errors} with errors"
    )

    if n_errors:
        return 1
    if args.strict and n_warnings:
        return 1
    return 0
