"""Tests for report template utilities."""

import pytest

from homomics_lab.reports.templates import ReportTemplateEngine


class TestMarkdownToHtml:
    @pytest.mark.parametrize(
        "markdown_text, expected_substrings",
        [
            ("# Heading\n\nparagraph", ["<h1>Heading</h1>", "<p>paragraph</p>"]),
            ("- item 1\n- item 2", ["<ul>", "<li>item 1</li>", "<li>item 2</li>", "</ul>"]),
            ("1. first\n2. second", ["<ol>", "<li>first</li>", "<li>second</li>", "</ol>"]),
            (
                "| a | b |\n|---|---|\n| 1 | 2 |",
                ["<table>", "<th>a</th>", "<td>1</td>"],
            ),
            (
                "```python\nprint('hi')\n```",
                ["<pre", "<code", "print('hi')"],
            ),
        ],
    )
    def test_markdown_renders_html(self, markdown_text, expected_substrings):
        html = ReportTemplateEngine._markdown_to_html(markdown_text)
        for substr in expected_substrings:
            assert substr in html

    def test_malicious_html_is_sanitized(self):
        text = "<script>alert('xss')</script>\n\n[link](javascript:alert(1))"
        html = ReportTemplateEngine._markdown_to_html(text)
        assert "<script>" not in html
        assert "javascript:" not in html

    def test_allowed_links_preserved(self):
        text = "[Homomics](https://homomics.lab)"
        html = ReportTemplateEngine._markdown_to_html(text)
        assert '<a href="https://homomics.lab">Homomics</a>' in html
