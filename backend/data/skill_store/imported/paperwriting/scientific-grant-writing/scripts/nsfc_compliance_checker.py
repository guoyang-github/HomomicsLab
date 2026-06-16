#!/usr/bin/env python3
"""
NSFC Proposal Compliance Checker

Checks National Natural Science Foundation of China (NSFC) proposal documents
for common formatting and compliance issues.

Usage:
    python nsfc_compliance_checker.py <proposal_file.md>
    python nsfc_compliance_checker.py <proposal_file.md> --program-type general|youth|key

Supported file formats: .md (Markdown), .txt
"""

import argparse
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class CheckResult:
    """Result of a single compliance check."""
    category: str
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    details: str = ""


@dataclass
class ComplianceReport:
    """Full compliance report for a proposal."""
    filename: str
    program_type: str
    results: List[CheckResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == "PASS")

    @property
    def warn_count(self) -> int:
        return sum(1 for r in self.results if r.status == "WARN")

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == "FAIL")

    def print_report(self):
        print(f"\n{'='*60}")
        print(f"NSFC Proposal Compliance Report")
        print(f"{'='*60}")
        print(f"File: {self.filename}")
        print(f"Program Type: {self.program_type.upper()}")
        print(f"{'-'*60}")

        # Group by category
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = []
            categories[r.category].append(r)

        for category, results in categories.items():
            print(f"\n[{category}]")
            for r in results:
                icon = "✓" if r.status == "PASS" else "⚠" if r.status == "WARN" else "✗"
                print(f"  {icon} [{r.status}] {r.message}")
                if r.details:
                    print(f"      Details: {r.details}")

        print(f"\n{'='*60}")
        print(f"Summary: {self.pass_count} passed, {self.warn_count} warnings, {self.fail_count} failures")
        if self.fail_count > 0:
            print("Status: ❌ NOT COMPLIANT - Please fix failures before submission")
        elif self.warn_count > 0:
            print("Status: ⚠️ MOSTLY COMPLIANT - Please review warnings")
        else:
            print("Status: ✓ COMPLIANT")
        print(f"{'='*60}\n")


class NSFCComplianceChecker:
    """Checker for NSFC proposal compliance."""

    def __init__(self, content: str, program_type: str = "general"):
        self.content = content
        self.program_type = program_type.lower()
        self.lines = content.split('\n')
        self.text_only = re.sub(r'[#*|`\-\[\]()]', ' ', content)

    def check_all(self) -> List[CheckResult]:
        """Run all compliance checks."""
        results = []
        results.extend(self.check_title())
        results.extend(self.check_structure())
        results.extend(self.check_abstract())
        results.extend(self.check_references())
        results.extend(self.check_sections_completeness())
        results.extend(self.check_budget())
        results.extend(self.check_formatting())
        results.extend(self.check_program_specific())
        return results

    def check_title(self) -> List[CheckResult]:
        """Check project title compliance."""
        results = []

        # Find title
        title_match = re.search(r'^#\s+(.+)$', self.content, re.MULTILINE)
        if not title_match:
            results.append(CheckResult(
                "Title",
                "FAIL",
                "Project title not found (should be a level-1 heading)"
            ))
            return results

        title = title_match.group(1).strip()

        # Check length (Chinese characters count as 1, but usually 25 chars limit)
        # For markdown, we count visible characters
        title_clean = re.sub(r'\s+', '', title)
        if len(title_clean) > 30:
            results.append(CheckResult(
                "Title",
                "WARN",
                f"Project title is {len(title_clean)} characters",
                "NSFC recommends title within 25 Chinese characters. Consider shortening."
            ))
        else:
            results.append(CheckResult(
                "Title",
                "PASS",
                f"Project title length OK ({len(title_clean)} characters)"
            ))

        # Check for English in Chinese title (common issue)
        if re.search(r'[a-zA-Z]{3,}', title):
            results.append(CheckResult(
                "Title",
                "WARN",
                "Title contains English words",
                "NSFC titles are typically in Chinese. Consider using Chinese unless necessary."
            ))

        return results

    def check_structure(self) -> List[CheckResult]:
        """Check overall document structure."""
        results = []

        # Check for major sections
        required_sections = [
            ("立项依据", ["立项依据", "研究背景", "国内外研究现状"]),
            ("研究内容", ["研究内容", "研究目标", "关键科学问题"]),
            ("研究方案", ["研究方案", "技术路线", "可行性分析"]),
            ("创新之处", ["创新", "特色"]),
            ("年度计划", ["年度计划", "预期成果"]),
            ("研究基础", ["研究基础", "工作条件"]),
        ]

        for section_name, keywords in required_sections:
            found = any(kw in self.content for kw in keywords)
            if found:
                results.append(CheckResult(
                    "Structure",
                    "PASS",
                    f"Section '{section_name}' found"
                ))
            else:
                results.append(CheckResult(
                    "Structure",
                    "FAIL",
                    f"Section '{section_name}' not found",
                    f"Expected keywords: {', '.join(keywords)}"
                ))

        return results

    def check_abstract(self) -> List[CheckResult]:
        """Check abstract/summary compliance."""
        results = []

        # NSFC requires a 400-character Chinese abstract
        # Try to find abstract section
        abstract_patterns = [
            r'摘要[：:]\s*(.+?)(?=\n##|\n#{2,}|\Z)',
            r'项目简介[：:]\s*(.+?)(?=\n##|\n#{2,}|\Z)',
        ]

        abstract_found = False
        abstract_text = ""

        for pattern in abstract_patterns:
            match = re.search(pattern, self.content, re.DOTALL)
            if match:
                abstract_found = True
                abstract_text = match.group(1).strip()
                break

        if not abstract_found:
            results.append(CheckResult(
                "Abstract",
                "WARN",
                "Abstract section not clearly identified",
                "NSFC requires a 400-character abstract. Ensure it is included."
            ))
            return results

        # Count characters (Chinese characters + English words)
        # Simple estimation: count all non-whitespace characters
        char_count = len(re.sub(r'\s+', '', abstract_text))

        if char_count > 450:
            results.append(CheckResult(
                "Abstract",
                "WARN",
                f"Abstract is approximately {char_count} characters",
                "NSFC abstract should be within 400 Chinese characters. Please shorten."
            ))
        elif char_count < 200:
            results.append(CheckResult(
                "Abstract",
                "WARN",
                f"Abstract is only approximately {char_count} characters",
                "Abstract seems too short. Aim for 300-400 characters for completeness."
            ))
        else:
            results.append(CheckResult(
                "Abstract",
                "PASS",
                f"Abstract length OK (~{char_count} characters)"
            ))

        return results

    def check_references(self) -> List[CheckResult]:
        """Check references section."""
        results = []

        # Find references section
        ref_section = re.search(
            r'(?:参考文献|主要参考文献)[：:]?\s*\n((?:\d+\.\s*.+\n?)+)',
            self.content,
            re.MULTILINE
        )

        if not ref_section:
            results.append(CheckResult(
                "References",
                "WARN",
                "References section not found",
                "NSFC proposals should include 20-40 references."
            ))
            return results

        ref_text = ref_section.group(1)
        ref_lines = [line.strip() for line in ref_text.split('\n') if line.strip()]
        ref_count = len(ref_lines)

        if ref_count < 15:
            results.append(CheckResult(
                "References",
                "WARN",
                f"Only {ref_count} references found",
                "NSFC typically expects 20-40 references. Consider adding more."
            ))
        elif ref_count > 50:
            results.append(CheckResult(
                "References",
                "WARN",
                f"{ref_count} references found",
                "Consider reducing to focus on most relevant references."
            ))
        else:
            results.append(CheckResult(
                "References",
                "PASS",
                f"Reference count OK ({ref_count})"
            ))

        # Check for recent references (last 5 years)
        current_year = 2024  # Could be dynamic
        recent_refs = 0
        for line in ref_lines:
            years = re.findall(r'20\d{2}', line)
            for year in years:
                if int(year) >= current_year - 5:
                    recent_refs += 1
                    break

        if ref_count > 0:
            recent_ratio = recent_refs / ref_count
            if recent_ratio < 0.5:
                results.append(CheckResult(
                    "References",
                    "WARN",
                    f"Only {recent_ratio*100:.0f}% of references are from the last 5 years",
                    "NSFC prefers recent literature. Aim for at least 50-60% from the last 5 years."
                ))
            else:
                results.append(CheckResult(
                    "References",
                    "PASS",
                    f"Recent references OK ({recent_ratio*100:.0f}% from last 5 years)"
                ))

        return results

    def check_sections_completeness(self) -> List[CheckResult]:
        """Check if all required sections are present with adequate content."""
        results = []

        # Check research content section length
        content_match = re.search(
            r'(?:研究内容|项目的研究内容)[：:]?\s*\n(.+?)(?=\n#{1,3}\s*(?:研究目标|拟解决的关键科学问题|研究方案|可行性))',
            self.content,
            re.DOTALL
        )

        if content_match:
            content_text = content_match.group(1)
            content_length = len(content_text.strip())
            if content_length < 1000:
                results.append(CheckResult(
                    "Content",
                    "WARN",
                    "Research content section seems brief",
                    f"Research content is about {content_length} characters. Consider expanding to 2000+ characters for adequate detail."
                ))
            else:
                results.append(CheckResult(
                    "Content",
                    "PASS",
                    f"Research content section has adequate length (~{content_length} chars)"
                ))

        # Check innovation section
        innovation_match = re.search(
            r'(?:创新|特色与创新)[：:]?\s*\n(.+?)(?=\n#{1,3}\s*(?:年度计划|预期成果|研究基础|经费))',
            self.content,
            re.DOTALL
        )

        if innovation_match:
            innovation_text = innovation_match.group(1)
            innovation_points = len(re.findall(r'创新点\s*\d', innovation_text))
            if innovation_points < 2:
                # Check for bullet points or numbered items
                bullet_points = len(re.findall(r'^\s*[-*]\s+', innovation_text, re.MULTILINE))
                if bullet_points < 2:
                    results.append(CheckResult(
                        "Innovation",
                        "WARN",
                        "Few innovation points identified",
                        "NSFC typically expects 2-4 innovation points. Consider explicitly listing them."
                    ))
                else:
                    results.append(CheckResult(
                        "Innovation",
                        "PASS",
                        f"Found {bullet_points} potential innovation points"
                    ))
            else:
                results.append(CheckResult(
                    "Innovation",
                    "PASS",
                    f"Found {innovation_points} explicitly numbered innovation points"
                ))
        else:
            results.append(CheckResult(
                "Innovation",
                "WARN",
                "Innovation section not clearly identified",
                "Ensure '创新之处' or '特色与创新' section is clearly labeled."
            ))

        return results

    def check_budget(self) -> List[CheckResult]:
        """Check budget section."""
        results = []

        # NSFC has different budget requirements
        budget_keywords = ["经费", "预算", "直接费用", "device", "equipment"]
        has_budget = any(kw in self.content for kw in budget_keywords)

        if not has_budget:
            results.append(CheckResult(
                "Budget",
                "WARN",
                "Budget section not found",
                "NSFC requires budget information. Ensure budget section is included."
            ))
        else:
            results.append(CheckResult(
                "Budget",
                "PASS",
                "Budget section found"
            ))

        return results

    def check_formatting(self) -> List[CheckResult]:
        """Check general formatting issues."""
        results = []

        # Check for figures/diagrams references
        figure_refs = len(re.findall(r'图\s*\d+|Figure\s*\d+|!\[', self.content))
        if figure_refs < 1:
            results.append(CheckResult(
                "Formatting",
                "WARN",
                "No figures/diagrams found",
                "NSFC proposals benefit from technical roadmaps and diagrams. Consider adding at least 1-2 figures."
            ))
        else:
            results.append(CheckResult(
                "Formatting",
                "PASS",
                f"Found {figure_refs} figure references"
            ))

        # Check for excessive jargon (simplified check)
        # Look for very long sentences
        sentences = re.split(r'[。\.!?]', self.content)
        long_sentences = [s for s in sentences if len(s.strip()) > 200]
        if len(long_sentences) > 5:
            results.append(CheckResult(
                "Formatting",
                "WARN",
                f"Found {len(long_sentences)} very long sentences",
                "Consider breaking long sentences for better readability."
            ))

        return results

    def check_program_specific(self) -> List[CheckResult]:
        """Check program-specific requirements."""
        results = []

        if self.program_type == "youth":
            # Youth program: should not have too many aims
            aims = len(re.findall(r'研究内容[一二三四五]', self.content))
            if aims > 4:
                results.append(CheckResult(
                    "Program-Specific",
                    "WARN",
                    f"Found {aims} research content items",
                    "Youth programs typically have 2-3 research contents. Consider focusing."
                ))
            else:
                results.append(CheckResult(
                    "Program-Specific",
                    "PASS",
                    f"Research content count appropriate for youth program ({aims})"
                ))

            # Check age-related content (should acknowledge youth status)
            if "35" not in self.content and "青年" not in self.content:
                results.append(CheckResult(
                    "Program-Specific",
                    "WARN",
                    "No explicit youth program positioning found",
                    "Consider explicitly positioning your proposal as an early independent research effort."
                ))

        elif self.program_type == "key":
            # Key program: should have more comprehensive content
            if len(self.content) < 10000:
                results.append(CheckResult(
                    "Program-Specific",
                    "WARN",
                    "Proposal seems relatively brief for a key program",
                    "Key programs typically require more comprehensive proposals. Consider expanding."
                ))
            else:
                results.append(CheckResult(
                    "Program-Specific",
                    "PASS",
                    "Proposal length appropriate for key program"
                ))

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Check NSFC proposal for compliance issues"
    )
    parser.add_argument(
        "filename",
        help="Path to the proposal file (.md or .txt)"
    )
    parser.add_argument(
        "--program-type",
        choices=["general", "youth", "key"],
        default="general",
        help="Type of NSFC program (default: general)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file for the report (default: print to stdout)"
    )

    args = parser.parse_args()

    # Read file
    filepath = Path(args.filename)
    if not filepath.exists():
        print(f"Error: File '{args.filename}' not found.", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding='utf-8')

    # Run checks
    checker = NSFCComplianceChecker(content, args.program_type)
    results = checker.check_all()

    # Generate report
    report = ComplianceReport(
        filename=str(filepath),
        program_type=args.program_type,
        results=results
    )

    # Output
    if args.output:
        # Redirect stdout to file
        import io
        from contextlib import redirect_stdout

        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            report.print_report()

        Path(args.output).write_text(output_buffer.getvalue(), encoding='utf-8')
        print(f"Report saved to {args.output}")
    else:
        report.print_report()

    # Exit with error code if failures exist
    if report.fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
