"""HTML/Markdown report templates."""

from datetime import datetime, timezone
from typing import Any, List

from .models import AnalysisReport, ReportFigure, ReportSection, ReportTable


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {
            --primary: #2c5282;
            --secondary: #4a5568;
            --bg: #f7fafc;
            --card-bg: #ffffff;
            --border: #e2e8f0;
            --text: #1a202c;
            --text-muted: #718096;
            --success: #38a169;
            --warning: #d69e2e;
            --danger: #e53e3e;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 0;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 2rem; }
        header {
            background: linear-gradient(135deg, var(--primary), #1a365d);
            color: white;
            padding: 3rem 2rem;
            margin-bottom: 2rem;
            border-radius: 0 0 1rem 1rem;
        }
        header h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; }
        header .meta { opacity: 0.85; font-size: 0.9rem; }
        .summary-card {
            background: var(--card-bg);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid var(--primary);
        }
        .summary-card h2 { font-size: 1.25rem; margin-bottom: 0.75rem; color: var(--primary); }
        .section {
            background: var(--card-bg);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .section h2 {
            font-size: 1.25rem;
            color: var(--primary);
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
            margin-bottom: 1rem;
        }
        .section h3 { font-size: 1.1rem; color: var(--secondary); margin: 1.25rem 0 0.5rem; }
        .section p { margin-bottom: 0.75rem; }
        .section ul, .section ol { margin-left: 1.5rem; margin-bottom: 0.75rem; }
        .figure {
            margin: 1.5rem 0;
            text-align: center;
        }
        .figure img {
            max-width: 100%;
            border-radius: 0.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .figure-caption {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
            font-style: italic;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.9rem;
        }
        .data-table th, .data-table td {
            padding: 0.6rem 0.8rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        .data-table th {
            background: #edf2f7;
            font-weight: 600;
            color: var(--secondary);
        }
        .data-table tr:hover { background: #f7fafc; }
        .table-caption {
            font-size: 0.875rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            font-style: italic;
        }
        .timeline {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-top: 1rem;
        }
        .timeline-item {
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            padding: 0.75rem;
            border-radius: 0.5rem;
            background: #f7fafc;
        }
        .timeline-number {
            width: 28px; height: 28px;
            border-radius: 50%;
            background: var(--primary);
            color: white;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.8rem; font-weight: 600;
            flex-shrink: 0;
        }
        .timeline-content { flex: 1; }
        .timeline-content .name { font-weight: 600; }
        .timeline-content .desc { font-size: 0.85rem; color: var(--text-muted); }
        .timeline-content .meta { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; }
        .status-completed { color: var(--success); }
        .status-failed { color: var(--danger); }
        .status-running { color: var(--warning); }
        .badge {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 1rem;
            font-size: 0.75rem;
            font-weight: 500;
            margin-left: 0.5rem;
        }
        .badge-success { background: #c6f6d5; color: #276749; }
        .badge-failed { background: #fed7d7; color: #c53030; }
        .badge-running { background: #fefcbf; color: #b7791f; }
        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }
        .parameters {
            background: #f7fafc;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 1rem;
        }
        .parameters code {
            background: #edf2f7;
            padding: 0.15rem 0.35rem;
            border-radius: 0.25rem;
            font-size: 0.85rem;
        }
        @media print {
            body { background: white; }
            header { border-radius: 0; page-break-after: avoid; }
            .section { box-shadow: none; border: 1px solid var(--border); page-break-inside: avoid; }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>{title}</h1>
            <div class="meta">
                {meta_lines}
            </div>
        </div>
    </header>
    <div class="container">
        {content}
    </div>
    <footer>
        <div class="container">
            Generated by HomomicsLab on {generated_at}
        </div>
    </footer>
</body>
</html>
"""


MARKDOWN_TEMPLATE = """# {title}

{meta_lines}

---

{content}

---

*Generated by HomomicsLab on {generated_at}*
"""


class ReportTemplateEngine:
    """Render analysis reports to HTML or Markdown."""

    def render_html(self, report: AnalysisReport) -> str:
        """Render report as a self-contained HTML document."""
        meta_lines = self._build_meta_html(report)
        content = self._build_content_html(report)

        # Use replace instead of format to avoid CSS braces being interpreted
        return (
            HTML_TEMPLATE.replace("{title}", report.title)
            .replace("{meta_lines}", meta_lines)
            .replace("{content}", content)
            .replace(
                "{generated_at}",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            )
        )

    def render_markdown(self, report: AnalysisReport) -> str:
        """Render report as Markdown."""
        meta_lines = self._build_meta_md(report)
        content = self._build_content_md(report)

        return MARKDOWN_TEMPLATE.format(
            title=report.title,
            meta_lines=meta_lines,
            content=content,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )

    def _build_meta_html(self, report: AnalysisReport) -> str:
        """Build metadata HTML lines."""
        lines: List[str] = []
        meta = report.metadata
        if meta.project_name:
            lines.append(f"<span>Project: {meta.project_name}</span>")
        if meta.analysis_type:
            lines.append(f"<span>Analysis: {meta.analysis_type.replace('_', ' ').title()}</span>")
        lines.append(f"<span>Created: {meta.created_at.strftime('%Y-%m-%d %H:%M UTC')}</span>")
        if meta.author:
            lines.append(f"<span>Author: {meta.author}</span>")
        if meta.tags:
            lines.append(f"<span>Tags: {', '.join(meta.tags)}</span>")
        return " &nbsp;|&nbsp; ".join(lines)

    def _build_meta_md(self, report: AnalysisReport) -> str:
        """Build metadata Markdown lines."""
        lines: List[str] = []
        meta = report.metadata
        if meta.project_name:
            lines.append(f"**Project:** {meta.project_name}")
        if meta.analysis_type:
            lines.append(f"**Analysis:** {meta.analysis_type.replace('_', ' ').title()}")
        lines.append(f"**Created:** {meta.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
        if meta.author:
            lines.append(f"**Author:** {meta.author}")
        if meta.tags:
            lines.append(f"**Tags:** {', '.join(meta.tags)}")
        return "\n".join(lines)

    def _build_content_html(self, report: AnalysisReport) -> str:
        """Build main content HTML."""
        parts: List[str] = []

        # Executive summary
        if report.summary:
            parts.append('<div class="summary-card">')
            parts.append('<h2>Executive Summary</h2>')
            parts.append(self._markdown_to_html(report.summary))
            parts.append("</div>")

        # Analysis steps timeline
        if report.analysis_steps:
            parts.append('<div class="section">')
            parts.append('<h2>Analysis Pipeline</h2>')
            parts.append('<div class="timeline">')
            for step in report.analysis_steps:
                badge_class = f"badge-{step.status}" if step.status else ""
                badge_text = step.status.upper() if step.status else ""
                duration = f"{step.duration_seconds:.1f}s" if step.duration_seconds else ""
                parts.append('<div class="timeline-item">')
                parts.append(f'<div class="timeline-number">{step.step_number}</div>')
                parts.append('<div class="timeline-content">')
                parts.append(f'<div class="name">{step.name} <span class="badge {badge_class}">{badge_text}</span></div>')
                if step.description:
                    parts.append(f'<div class="desc">{step.description}</div>')
                meta_parts = []
                if step.skill_id:
                    meta_parts.append(f"Skill: <code>{step.skill_id}</code>")
                if duration:
                    meta_parts.append(f"Duration: {duration}")
                if meta_parts:
                    parts.append(f'<div class="meta">{" | ".join(meta_parts)}</div>')
                parts.append("</div></div>")
            parts.append("</div></div>")

        # Sections
        for section in report.sections:
            parts.append(self._render_section_html(section))

        # Parameters
        if report.metadata.parameters:
            parts.append('<div class="section">')
            parts.append('<h2>Analysis Parameters</h2>')
            parts.append('<div class="parameters">')
            parts.append("<table class='data-table'>")
            parts.append("<tr><th>Parameter</th><th>Value</th></tr>")
            for key, value in report.metadata.parameters.items():
                parts.append(f"<tr><td><code>{key}</code></td><td><code>{value}</code></td></tr>")
            parts.append("</table></div></div>")

        return "\n".join(parts)

    def _build_content_md(self, report: AnalysisReport) -> str:
        """Build main content Markdown."""
        parts: List[str] = []

        if report.summary:
            parts.append("## Executive Summary")
            parts.append(report.summary)
            parts.append("")

        if report.analysis_steps:
            parts.append("## Analysis Pipeline")
            for step in report.analysis_steps:
                status = f" [{step.status.upper()}]" if step.status else ""
                duration = f" ({step.duration_seconds:.1f}s)" if step.duration_seconds else ""
                parts.append(f"{step.step_number}. **{step.name}**{status}{duration}")
                if step.description:
                    parts.append(f"   - {step.description}")
                if step.skill_id:
                    parts.append(f"   - Skill: `{step.skill_id}`")
                parts.append("")

        for section in report.sections:
            parts.append(self._render_section_md(section))

        if report.metadata.parameters:
            parts.append("## Analysis Parameters")
            parts.append("| Parameter | Value |")
            parts.append("|-----------|-------|")
            for key, value in report.metadata.parameters.items():
                parts.append(f"| `{key}` | `{value}` |")
            parts.append("")

        return "\n".join(parts)

    def _render_section_html(self, section: ReportSection) -> str:
        """Render a single section to HTML."""
        parts: List[str] = []
        parts.append('<div class="section">')
        parts.append(f"<h2>{section.title}</h2>")

        if section.content:
            parts.append(self._markdown_to_html(section.content))

        for table in section.tables:
            parts.append(self._render_table_html(table))

        for figure in section.figures:
            parts.append(self._render_figure_html(figure))

        parts.append("</div>")
        return "\n".join(parts)

    def _render_section_md(self, section: ReportSection) -> str:
        """Render a single section to Markdown."""
        parts: List[str] = []
        parts.append(f"## {section.title}")
        parts.append("")

        if section.content:
            parts.append(section.content)
            parts.append("")

        for table in section.tables:
            parts.append(self._render_table_md(table))

        for figure in section.figures:
            parts.append(self._render_figure_md(figure))

        return "\n".join(parts)

    def _render_table_html(self, table: ReportTable) -> str:
        """Render a data table to HTML."""
        if table.caption:
            caption = f'<div class="table-caption">{table.caption}</div>'
        else:
            caption = ""

        rows_html = []
        rows_html.append("<tr>" + "".join(f"<th>{h}</th>" for h in table.headers) + "</tr>")
        for row in table.rows:
            rows_html.append("<tr>" + "".join(f"<td>{self._fmt_cell(c)}</td>" for c in row) + "</tr>")

        return f"""{caption}
<table class="data-table">
{chr(10).join(rows_html)}
</table>"""

    def _render_table_md(self, table: ReportTable) -> str:
        """Render a data table to Markdown."""
        parts: List[str] = []
        if table.caption:
            parts.append(f"*{table.caption}*")
        parts.append("| " + " | ".join(table.headers) + " |")
        parts.append("| " + " | ".join(["---"] * len(table.headers)) + " |")
        for row in table.rows:
            parts.append("| " + " | ".join(str(self._fmt_cell(c)) for c in row) + " |")
        parts.append("")
        return "\n".join(parts)

    def _render_figure_html(self, figure: ReportFigure) -> str:
        """Render a figure to HTML."""
        return f"""<div class="figure">
<img src="data:image/png;base64,{figure.image_base64}" alt="{figure.caption}" width="{figure.width}">
<div class="figure-caption">{figure.caption}</div>
</div>"""

    def _render_figure_md(self, figure: ReportFigure) -> str:
        """Render a figure to Markdown."""
        # In markdown, embed as base64 data URI
        return f"![{figure.caption}](data:image/png;base64,{figure.image_base64})\n\n*{figure.caption}*\n"

    @staticmethod
    def _fmt_cell(value: Any) -> str:
        """Format a table cell value."""
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value)

    def render_pdf(self, report: AnalysisReport) -> bytes:
        """Render report as PDF using WeasyPrint.

        Converts the HTML report to PDF, preserving all CSS styling.
        """
        html_content = self.render_html(report)

        try:
            from weasyprint import HTML

            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        except Exception as e:
            raise RuntimeError(f"PDF generation failed: {e}")

    @staticmethod
    def _markdown_to_html(text: str) -> str:
        """Simple Markdown to HTML conversion."""
        lines = text.split("\n")
        result: List[str] = []
        in_list = False
        list_type = ""

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("# "):
                if in_list:
                    result.append(f"</{list_type}>")
                    in_list = False
                result.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("## "):
                if in_list:
                    result.append(f"</{list_type}>")
                    in_list = False
                result.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("### "):
                if in_list:
                    result.append(f"</{list_type}>")
                    in_list = False
                result.append(f"<h3>{stripped[4:]}</h3>")
            elif stripped.startswith("- "):
                if not in_list or list_type != "ul":
                    if in_list:
                        result.append(f"</{list_type}>")
                    result.append("<ul>")
                    in_list = True
                    list_type = "ul"
                result.append(f"<li>{stripped[2:]}</li>")
            elif stripped.startswith(("1. ", "2. ", "3. ", "4. ", "5. ", "6. ", "7. ", "8. ", "9. ")):
                if not in_list or list_type != "ol":
                    if in_list:
                        result.append(f"</{list_type}>")
                    result.append("<ol>")
                    in_list = True
                    list_type = "ol"
                result.append(f"<li>{stripped[3:]}</li>")
            elif stripped == "":
                if in_list:
                    result.append(f"</{list_type}>")
                    in_list = False
                result.append("<br>")
            else:
                if in_list:
                    result.append(f"</{list_type}>")
                    in_list = False
                result.append(f"<p>{stripped}</p>")

        if in_list:
            result.append(f"</{list_type}>")

        return "\n".join(result)
