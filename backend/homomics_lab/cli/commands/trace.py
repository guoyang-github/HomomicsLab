"""CLI command to display execution traces."""

import argparse
import asyncio
import json
from typing import Any, Dict, List, Optional

from homomics_lab.observability.trace_store import ExecutionTrace, TraceStore


def register_trace_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "trace",
        help="Show the execution trace for a job or plan",
    )
    parser.add_argument("trace_id", help="Job or plan id")
    parser.add_argument(
        "--format",
        choices=["tree", "json"],
        default="tree",
        help="Output format",
    )
    parser.set_defaults(func=run_trace)


def run_trace(args: argparse.Namespace) -> None:
    trace = asyncio.run(_fetch_trace(args.trace_id))
    if trace is None:
        print(f"Trace not found: {args.trace_id}")
        raise SystemExit(1)

    if args.format == "json":
        print(json.dumps(trace.model_dump(mode="json"), indent=2, ensure_ascii=False))
    else:
        _print_tree(trace)


async def _fetch_trace(trace_id: str) -> Optional[ExecutionTrace]:
    return await TraceStore().get_trace(trace_id)


def _print_tree(trace: ExecutionTrace) -> None:
    print(f"Trace: {trace.trace_id}")
    print(f"Status: {trace.status}")
    if trace.error_message:
        print(f"Error: {trace.error_message}")
    print("")

    nodes_by_parent: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for node in trace.nodes:
        nodes_by_parent.setdefault(node.parent_id, []).append(node.model_dump(mode="json"))

    def _render(node_id: str, indent: int = 0) -> None:
        for node in nodes_by_parent.get(node_id, []):
            prefix = "  " * indent
            duration = ""
            if node.get("ended_at") and node.get("started_at"):
                duration = f" ({_fmt_duration(node['started_at'], node['ended_at'])})"
            print(
                f"{prefix}- [{node['status']}] {node['node_type']}:{node['name']}{duration}"
            )
            if node.get("error"):
                print(f"{prefix}  error: {node['error']}")
            _render(node["node_id"], indent + 1)

    # Find root nodes (parent_id None)
    roots = nodes_by_parent.get(None, [])
    if not roots and trace.nodes:
        # Fallback: render all top-level nodes.
        roots = [n.model_dump(mode="json") for n in trace.nodes]
    for root in roots:
        print(f"- [{root['status']}] {root['node_type']}:{root['name']}")
        if root.get("error"):
            print(f"  error: {root['error']}")
        _render(root["node_id"], 1)


def _fmt_duration(started: str, ended: str) -> str:
    from datetime import datetime

    try:
        s = datetime.fromisoformat(started.replace("Z", "+00:00"))
        e = datetime.fromisoformat(ended.replace("Z", "+00:00"))
        return f"{(e - s).total_seconds():.2f}s"
    except Exception:
        return ""
