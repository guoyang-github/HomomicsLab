"""HomomicsLab CLI entry point."""

import argparse
import sys

from homomics_lab.cli.commands.init import init_domain
from homomics_lab.cli.commands.validate import validate_domain
from homomics_lab.cli.commands.install import install_domain
from homomics_lab.cli.commands.generate import generate_domain
from homomics_lab.cli.commands.list import list_domains
from homomics_lab.cli.commands.trace import register_trace_parser


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homomics",
        description="HomomicsLab CLI - Manage bioinformatics domains",
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
    list_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed info",
    )

    # trace
    register_trace_parser(subparsers)

    return parser


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

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
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
