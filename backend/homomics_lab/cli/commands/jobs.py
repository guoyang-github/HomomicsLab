"""`homomics jobs` command: list persisted jobs."""

import argparse
import asyncio
import json
from typing import Any, Dict

from homomics_lab.jobs.repository import JobRepository


def register_jobs_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "jobs",
        help="List execution jobs",
    )
    parser.add_argument(
        "--project-id",
        "-p",
        default=None,
        help="Filter by project ID",
    )
    parser.add_argument(
        "--status",
        "-s",
        default=None,
        help="Filter by job status",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSON",
    )


def _job_row(job) -> Dict[str, Any]:
    return {
        "job_id": job.job_id,
        "project_id": job.project_id,
        "session_id": job.session_id,
        "plan_id": job.plan_id,
        "status": job.status,
        "mode": job.mode,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


async def _list_jobs(args: argparse.Namespace) -> int:
    repo = JobRepository()
    jobs = await repo.list_all(project_id=args.project_id)

    if args.status:
        jobs = [j for j in jobs if j.status == args.status]

    rows = [_job_row(j) for j in jobs]

    if args.json_output:
        print(json.dumps(rows, indent=2, default=str))
        return 0

    if not rows:
        print("No jobs found.")
        return 0

    headers = [
        "job_id",
        "status",
        "project_id",
        "session_id",
        "plan_id",
        "mode",
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


def run_jobs(args: argparse.Namespace) -> int:
    return asyncio.run(_list_jobs(args))
