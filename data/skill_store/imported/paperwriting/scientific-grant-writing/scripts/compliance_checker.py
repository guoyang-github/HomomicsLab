#!/usr/bin/env python3
"""
Grant Proposal Compliance Checker
Verify formatting requirements for NSF, NIH, DOE, and DARPA proposals.
"""

import sys
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple


class ComplianceChecker:
    """Check grant proposal compliance with agency requirements."""

    # Agency-specific requirements
    REQUIREMENTS = {
        "nih": {
            "page_limits": {
                "specific_aims": 1,
                "research_strategy": 12,
                "introduction_resubmission": 1,
                "biosketch": 5,
            },
            "font_size": 11,
            "margins_inches": 0.5,
            "line_spacing": "single",
            "font_whitelist": ["Arial", "Helvetica", "Palatino Linotype", "Georgia"],
        },
        "nsf": {
            "page_limits": {
                "project_description": 15,
                "project_summary": 1,
                "biosketch": 2,
                "budget_justification": 3,
            },
            "font_size": 11,
            "margins_inches": 1.0,
            "line_spacing": "single",
            "font_whitelist": ["Arial", "Helvetica", "Palatino Linotype", "Georgia"],
        },
        "doe": {
            "page_limits": {
                "technical_narrative": 20,
                "project_abstract": 1,
            },
            "font_size": 11,
            "margins_inches": 1.0,
            "line_spacing": "single",
        },
        "darpa": {
            "page_limits": {
                "technical_volume": 30,
                "management_plan": 5,
                "cost_volume": None,
            },
            "font_size": 11,
            "margins_inches": 1.0,
            "line_spacing": "single",
        },
    }

    REQUIRED_SECTIONS = {
        "nih": [
            "Specific Aims",
            "Research Strategy",
            "Significance",
            "Innovation",
            "Approach",
            "Biosketch",
        ],
        "nsf": [
            "Project Summary",
            "Project Description",
            "References Cited",
            "Biosketch",
            "Budget Justification",
            "Data Management Plan",
        ],
        "doe": [
            "Abstract",
            "Technical Narrative",
            "References",
            "Budget",
            "Biosketch",
        ],
        "darpa": [
            "Technical Approach",
            "Schedule",
            "Deliverables",
            "Team Qualifications",
            "Cost Proposal",
        ],
    }

    def __init__(self, agency: str):
        self.agency = agency.lower()
        if self.agency not in self.REQUIREMENTS:
            raise ValueError(f"Unknown agency: {agency}. Use: nih, nsf, doe, darpa")
        self.req = self.REQUIREMENTS[self.agency]
        self.issues: List[Dict] = []

    def check_page_count(self, filepath: Path, section_name: str, max_pages: int) -> bool:
        """Estimate page count from markdown/text file."""
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception as e:
            self.issues.append({
                "type": "error",
                "message": f"Cannot read {filepath}: {e}",
            })
            return False

        # Rough estimate: ~3000 characters per page (11pt, single spaced, 1" margins)
        chars_per_page = 3000
        estimated_pages = len(text) / chars_per_page

        if max_pages and estimated_pages > max_pages:
            self.issues.append({
                "type": "error",
                "message": (
                    f"{section_name}: ~{estimated_pages:.1f} pages "
                    f"exceeds limit of {max_pages} pages"
                ),
            })
            return False
        return True

    def check_file_exists(self, filepath: Path, description: str) -> bool:
        """Check if a required file exists."""
        if not filepath.exists():
            self.issues.append({
                "type": "warning",
                "message": f"Missing required file: {description} ({filepath})",
            })
            return False
        return True

    def check_font_mentions(self, filepath: Path) -> None:
        """Check for font size violations in text."""
        text = filepath.read_text(encoding="utf-8")
        min_size = self.req.get("font_size", 11)

        # Look for font size declarations smaller than required
        small_font_pattern = re.compile(r"font-size:\s*(\d+)pt", re.IGNORECASE)
        for match in small_font_pattern.finditer(text):
            size = int(match.group(1))
            if size < min_size:
                self.issues.append({
                    "type": "error",
                    "message": f"Font size {size}pt found (minimum: {min_size}pt)",
                })

    def check_sections_present(self, text: str) -> None:
        """Check if required sections are present in the document."""
        required = self.REQUIRED_SECTIONS.get(self.agency, [])
        text_lower = text.lower()

        for section in required:
            section_variants = [
                section.lower(),
                section.lower().replace(" ", ""),
                section.lower().replace(" ", "_"),
            ]
            if not any(var in text_lower for var in section_variants):
                self.issues.append({
                    "type": "warning",
                    "message": f"Required section not found: {section}",
                })

    def check_proposal(self, directory: Path) -> Dict:
        """Run all compliance checks on a proposal directory."""
        self.issues = []

        # Check for common files
        md_files = list(directory.glob("*.md"))
        if not md_files:
            self.issues.append({
                "type": "error",
                "message": f"No markdown files found in {directory}",
            })
            return {"valid": False, "issues": self.issues}

        # Combine all markdown text for section checking
        all_text = ""
        for md_file in md_files:
            all_text += md_file.read_text(encoding="utf-8") + "\n"

        self.check_sections_present(all_text)

        # Check page limits for known files
        page_limits = self.req.get("page_limits", {})
        for section, limit in page_limits.items():
            # Try to find matching file
            candidates = [
                directory / f"{section}.md",
                directory / f"{section.replace('_', '-')}.md",
                directory / f"{section.replace('_', ' ')}.md",
            ]
            for candidate in candidates:
                if candidate.exists():
                    self.check_page_count(candidate, section, limit)
                    break

        # Check font mentions in all files
        for md_file in md_files:
            self.check_font_mentions(md_file)

        errors = [i for i in self.issues if i["type"] == "error"]
        warnings = [i for i in self.issues if i["type"] == "warning"]

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_issues": len(self.issues),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Check grant proposal compliance with agency requirements"
    )
    parser.add_argument("directory", help="Proposal directory to check")
    parser.add_argument(
        "--agency",
        required=True,
        choices=["nih", "nsf", "doe", "darpa"],
        help="Funding agency requirements to check against",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all checks performed",
    )
    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    checker = ComplianceChecker(args.agency)
    result = checker.check_proposal(directory)

    print(f"\n{'=' * 60}")
    print(f"COMPLIANCE CHECK: {args.agency.upper()}")
    print(f"{'=' * 60}")
    print(f"Directory: {directory}")
    print(f"Status: {'PASS' if result['valid'] else 'FAIL'}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Warnings: {len(result['warnings'])}")

    if result["errors"]:
        print(f"\nERRORS:")
        for issue in result["errors"]:
            print(f"  - {issue['message']}")

    if result["warnings"]:
        print(f"\nWARNINGS:")
        for issue in result["warnings"]:
            print(f"  - {issue['message']}")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
