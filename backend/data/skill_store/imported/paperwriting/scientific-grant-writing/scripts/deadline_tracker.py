#!/usr/bin/env python3
"""
Grant Deadline Tracker
Track submission deadlines, milestones, and generate reminders.
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


class DeadlineTracker:
    """Track grant deadlines and milestones."""

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or Path("deadlines.json")
        self.deadlines: List[Dict] = []
        self.load()

    def load(self) -> None:
        """Load deadlines from JSON file."""
        if self.data_file.exists():
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.deadlines = json.load(f)
        else:
            self.deadlines = []

    def save(self) -> None:
        """Save deadlines to JSON file."""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.deadlines, f, indent=2)

    def add_deadline(
        self,
        title: str,
        date_str: str,
        agency: str,
        description: str = "",
        priority: str = "medium",
        reminders: Optional[List[int]] = None,
    ) -> None:
        """Add a new deadline."""
        try:
            deadline_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {date_str}") from exc

        entry = {
            "id": len(self.deadlines) + 1,
            "title": title,
            "date": date_str,
            "agency": agency,
            "description": description,
            "priority": priority,
            "reminders": reminders or [30, 14, 7, 1],
            "completed": False,
            "created": datetime.now().strftime("%Y-%m-%d"),
        }
        self.deadlines.append(entry)
        self.save()
        print(f"Added deadline: {title} ({date_str})")

    def add_milestone(
        self,
        proposal_title: str,
        milestone: str,
        date_str: str,
    ) -> None:
        """Add an internal milestone for a proposal."""
        title = f"[{proposal_title}] {milestone}"
        self.add_deadline(
            title=title,
            date_str=date_str,
            agency="internal",
            description=f"Internal milestone for {proposal_title}",
            priority="medium",
        )

    def list_deadlines(self, show_completed: bool = False) -> None:
        """List all tracked deadlines."""
        today = datetime.now()

        active = [d for d in self.deadlines if not d["completed"]]
        completed = [d for d in self.deadlines if d["completed"]]

        if not active and not completed:
            print("No deadlines tracked.")
            return

        print("\n" + "=" * 70)
        print("ACTIVE DEADLINES")
        print("=" * 70)

        # Sort by date
        active.sort(key=lambda x: x["date"])

        for d in active:
            deadline_date = datetime.strptime(d["date"], "%Y-%m-%d")
            days_remaining = (deadline_date - today).days

            if days_remaining < 0:
                status = "OVERDUE"
                status_color = ""
            elif days_remaining <= 7:
                status = f"URGENT ({days_remaining}d)"
            elif days_remaining <= 30:
                status = f"SOON ({days_remaining}d)"
            else:
                status = f"{days_remaining} days"

            print(f"\n[{d['id']}] {d['title']}")
            print(f"    Agency: {d['agency']} | Date: {d['date']} | Status: {status}")
            if d["description"]:
                print(f"    Description: {d['description']}")

        if show_completed and completed:
            print("\n" + "=" * 70)
            print("COMPLETED DEADLINES")
            print("=" * 70)
            for d in completed:
                print(f"[DONE] {d['title']} ({d['date']})")

    def check_reminders(self) -> List[Dict]:
        """Check for deadlines needing reminders."""
        today = datetime.now()
        reminders_due = []

        for d in self.deadlines:
            if d["completed"]:
                continue

            deadline_date = datetime.strptime(d["date"], "%Y-%m-%d")
            days_remaining = (deadline_date - today).days

            for reminder_days in d.get("reminders", []):
                if days_remaining == reminder_days:
                    reminders_due.append({
                        "deadline": d,
                        "days": reminder_days,
                    })

        return reminders_due

    def mark_completed(self, deadline_id: int) -> None:
        """Mark a deadline as completed."""
        for d in self.deadlines:
            if d["id"] == deadline_id:
                d["completed"] = True
                self.save()
                print(f"Marked as completed: {d['title']}")
                return
        print(f"Deadline {deadline_id} not found")

    def generate_timeline(self, proposal_title: str, deadline_date: str) -> None:
        """Generate a standard milestone timeline for a proposal."""
        deadline = datetime.strptime(deadline_date, "%Y-%m-%d")

        milestones = [
            ("Team assembly and role confirmation", 180),
            ("Literature review complete", 150),
            ("Specific aims/outline finalized", 120),
            ("First draft complete", 90),
            ("Internal review and feedback", 60),
            ("Revised draft complete", 45),
            ("Budget and biosketches finalized", 30),
            ("Final internal review", 14),
            ("Submission to institutional office", 7),
            ("Final submission", 2),
        ]

        print(f"\nMilestone Timeline for: {proposal_title}")
        print(f"Submission Deadline: {deadline_date}")
        print("=" * 60)

        for milestone_name, days_before in milestones:
            milestone_date = deadline - timedelta(days=days_before)
            date_str = milestone_date.strftime("%Y-%m-%d")
            self.add_milestone(proposal_title, milestone_name, date_str)
            print(f"{date_str}  ({days_before:>3}d before)  {milestone_name}")

        self.save()


def main():
    parser = argparse.ArgumentParser(
        description="Track grant submission deadlines and milestones"
    )
    parser.add_argument(
        "--data",
        default="deadlines.json",
        help="JSON file to store deadlines",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add deadline
    add_parser = subparsers.add_parser("add", help="Add a new deadline")
    add_parser.add_argument("title", help="Deadline title")
    add_parser.add_argument("date", help="Deadline date (YYYY-MM-DD)")
    add_parser.add_argument("--agency", default="unknown", help="Funding agency")
    add_parser.add_argument("--desc", default="", help="Description")
    add_parser.add_argument(
        "--priority",
        choices=["low", "medium", "high"],
        default="medium",
        help="Priority level",
    )

    # List deadlines
    list_parser = subparsers.add_parser("list", help="List all deadlines")
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="Show completed deadlines too",
    )

    # Generate timeline
    timeline_parser = subparsers.add_parser(
        "timeline", help="Generate milestone timeline"
    )
    timeline_parser.add_argument("proposal", help="Proposal name")
    timeline_parser.add_argument("deadline", help="Submission deadline (YYYY-MM-DD)")

    # Check reminders
    subparsers.add_parser("reminders", help="Check for reminder alerts")

    # Mark complete
    done_parser = subparsers.add_parser("done", help="Mark deadline as completed")
    done_parser.add_argument("id", type=int, help="Deadline ID")

    args = parser.parse_args()

    tracker = DeadlineTracker(Path(args.data))

    if args.command == "add":
        try:
            tracker.add_deadline(
                args.title,
                args.date,
                args.agency,
                args.desc,
                args.priority,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "list":
        tracker.list_deadlines(show_completed=args.all)
    elif args.command == "timeline":
        try:
            tracker.generate_timeline(args.proposal, args.deadline)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "reminders":
        reminders = tracker.check_reminders()
        if reminders:
            print(f"\nREMINDERS ({len(reminders)} due today):")
            for r in reminders:
                d = r["deadline"]
                print(f"  [{d['id']}] {d['title']} - {r['days']} days remaining")
        else:
            print("No reminders due today.")
    elif args.command == "done":
        tracker.mark_completed(args.id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
