"""CLI command to export project provenance as RO-Crate."""

import argparse
import shutil
import sys
from pathlib import Path

from homomics_lab.config import settings
from homomics_lab.provenance.recorder import ProvenanceRecorder
from homomics_lab.provenance.rocrate import ROCrateExporter


def register_export_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "export",
        help="Export a project archive or RO-Crate",
    )
    parser.add_argument("project_id", help="Project identifier")
    parser.add_argument(
        "--format",
        choices=["rocrate"],
        default="rocrate",
        help="Export format",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output directory or file path",
        default=None,
    )
    parser.set_defaults(func=run_export)


def run_export(args: argparse.Namespace) -> int:
    recorder = ProvenanceRecorder()
    provenance_records = recorder.list_by_project(args.project_id)

    if args.format == "rocrate":
        output_dir = Path(args.output) if args.output else Path(settings.data_dir) / "exports" / f"{args.project_id}_rocrate"
        output_dir.mkdir(parents=True, exist_ok=True)
        exporter = ROCrateExporter(output_dir)
        exporter.export(args.project_id, provenance_records)

        zip_path = output_dir.with_suffix(".zip")
        shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
        print(f"RO-Crate exported to: {zip_path}")
        return 0

    print(f"Unsupported export format: {args.format}", file=sys.stderr)
    return 1
