"""`homomics plans` command: list persisted execution plans."""

import argparse
import asyncio
import json
from typing import Any, Dict

from homomics_lab.plan.store import PlanStore
from homomics_lab.plan.models import PlanStatus


def register_plans_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "plans",
        help="List execution plans",
    )
    _status_choices = [
        getattr(PlanStatus, attr)
        for attr in dir(PlanStatus)
        if not attr.startswith("_") and isinstance(getattr(PlanStatus, attr), str)
    ]
    parser.add_argument(
        "--status",
        "-s",
        choices=_status_choices,
        default=None,
        help="Filter by plan status",
    )
    parser.add_argument(
        "--project-id",
        "-p",
        default=None,
        help="Filter by project ID",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSON",
    )


def _plan_row(plan) -> Dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "session_id": plan.session_id,
        "project_id": plan.project_id,
        "status": plan.status,
        "version": plan.version,
        "intent_analysis_type": plan.intent_analysis_type,
        "intent_complexity": plan.intent_complexity,
        "is_fallback": plan.is_fallback,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


async def _list_plans(args: argparse.Namespace) -> int:
    store = PlanStore()
    status = args.status if args.status else None
    plans = await store.list_all(project_id=args.project_id, status=status)

    rows = [_plan_row(p) for p in plans]

    if args.json_output:
        print(json.dumps(rows, indent=2, default=str))
        return 0

    if not rows:
        print("No plans found.")
        return 0

    headers = [
        "plan_id",
        "status",
        "project_id",
        "session_id",
        "version",
        "intent_analysis_type",
        "updated_at",
    ]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row.get(h) or "")))

    def fmt(row):
        return "  ".join(
            str(row.get(h) or "").ljust(widths[h]) for h in headers
        )

    print(fmt({h: h for h in headers}))
    print("-" * (sum(widths.values()) + 2 * (len(headers) - 1)))
    for row in rows:
        print(fmt(row))
    return 0


def run_plans(args: argparse.Namespace) -> int:
    return asyncio.run(_list_plans(args))
