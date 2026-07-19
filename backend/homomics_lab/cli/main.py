"""HomomicsLab CLI entry point."""

import argparse
import sys
import traceback

from homomics_lab.logging_config import configure_logging
from homomics_lab.cli.commands.init import init_domain
from homomics_lab.cli.commands.validate import validate_domain
from homomics_lab.cli.commands.install import install_domain
from homomics_lab.cli.commands.generate import generate_domain
from homomics_lab.cli.commands.list import list_domains
from homomics_lab.cli.commands.trace import register_trace_parser
from homomics_lab.cli.commands.benchmark import register_benchmark_parser, run_benchmark
from homomics_lab.cli.commands.run import register_run_parser, run_run
from homomics_lab.cli.commands.plans import register_plans_parser, run_plans
from homomics_lab.cli.commands.jobs import register_jobs_parser, run_jobs
from homomics_lab.cli.commands.init_project import (
    register_init_project_parser,
    init_project,
)
from homomics_lab.cli.commands.export import register_export_parser, run_export
from homomics_lab.cli.commands.seed import register_seed_parser, run_seed
from homomics_lab.cli.commands.skill import register_skill_parser, run_skill


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homomics",
        description="HomomicsLab CLI - Manage bioinformatics domains",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (DEBUG logging and full tracebacks)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # domain init
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new domain scaffold",
    )
    init_parser.add_argument("name", help="Domain name (e.g. metagenomics)")
    init_parser.add_argument(
        "--phases",
        help="Comma-separated phase IDs (e.g. qc,denoising,taxonomy)",
        default="",
    )
    init_parser.add_argument(
        "--output",
        "-o",
        help="Output directory",
        default=".",
    )
    init_parser.add_argument(
        "--template",
        "-t",
        help="Template to use",
        choices=["blank", "metagenomics", "genomics", "proteomics"],
        default="blank",
    )

    # domain validate
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a domain.yaml file",
    )
    validate_parser.add_argument(
        "path",
        help="Path to domain.yaml",
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings",
    )

    # domain install
    install_parser = subparsers.add_parser(
        "install",
        help="Install a domain from a directory or git repo",
    )
    install_parser.add_argument(
        "source",
        help="Path to domain directory or git URL",
    )
    install_parser.add_argument(
        "--domains-dir",
        "-d",
        help="HomomicsLab domains directory",
        default="./domains",
    )

    # domain generate (LLM-assisted)
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a domain from natural language description (LLM-assisted)",
    )
    generate_parser.add_argument(
        "description",
        help="Natural language description of the domain workflow",
    )
    generate_parser.add_argument(
        "--output",
        "-o",
        help="Output directory",
        default=".",
    )
    generate_parser.add_argument(
        "--model",
        help="LLM model to use",
        default="gpt-4",
    )

    # domain list
    list_parser = subparsers.add_parser(
        "list",
        help="List all installed domains",
    )
    list_parser.add_argument(
        "--domains-dir",
        "-d",
        help="HomomicsLab domains directory",
        default="./domains",
    )

    # trace
    register_trace_parser(subparsers)

    # benchmark
    register_benchmark_parser(subparsers)

    # run skill
    register_run_parser(subparsers)

    # plans / jobs
    register_plans_parser(subparsers)
    register_jobs_parser(subparsers)

    # init-project
    register_init_project_parser(subparsers)

    # export
    register_export_parser(subparsers)

    # seed
    register_seed_parser(subparsers)

    # skill
    register_skill_parser(subparsers)

    return parser


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)

    configure_logging(
        level="DEBUG" if args.verbose else "INFO",
        json_format=False,
    )

    if args.command is None:
        parser.print_help()
        raise SystemExit(1)

    try:
        if args.command == "init":
            init_domain(args)
        elif args.command == "validate":
            validate_domain(args)
        elif args.command == "install":
            install_domain(args)
        elif args.command == "generate":
            generate_domain(args)
        elif args.command == "list":
            list_domains(args)
        elif args.command == "benchmark":
            return run_benchmark(args)
        elif args.command == "run":
            return run_run(args)
        elif args.command == "plans":
            return run_plans(args)
        elif args.command == "jobs":
            return run_jobs(args)
        elif args.command == "init-project":
            return init_project(args)
        elif args.command == "export":
            return run_export(args)
        elif args.command == "seed":
            return run_seed(args)
        elif args.command == "skill":
            return run_skill(args)
        return 0
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
