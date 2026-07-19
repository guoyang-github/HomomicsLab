"""Tests for source attribution and anti-hallucination helpers."""

from homomics_lab.agent.source_attribution import (
    ensure_source_section,
    extract_sources,
    format_source_list,
    source_section_present,
)


class TestExtractSources:
    def test_extracts_url_and_title_from_web_search(self):
        outputs = [
            {
                "count": 2,
                "results": [
                    {"title": "Paper A", "url": "https://example.com/a"},
                    {"title": "Paper B", "url": "https://example.com/b"},
                ],
            }
        ]
        sources = extract_sources(outputs)
        assert len(sources) == 2
        assert sources[0]["type"] == "url"
        assert sources[0]["url"] == "https://example.com/a"
        assert sources[0]["title"] == "Paper A"

    def test_extracts_pmid_and_doi(self):
        outputs = [
            {
                "articles": [
                    {"pmid": "12345", "title": "Article One"},
                    {"doi": "10.1000/x", "title": "Article Two"},
                ]
            }
        ]
        sources = extract_sources(outputs)
        assert len(sources) == 2
        assert sources[0]["type"] == "pmid"
        assert sources[0]["id"] == "12345"
        assert sources[1]["type"] == "doi"
        assert sources[1]["id"] == "10.1000/x"

    def test_deduplicates_by_url(self):
        outputs = [
            {"url": "https://same.org/x", "title": "One"},
            {"url": "https://same.org/x", "title": "Two"},
        ]
        sources = extract_sources(outputs)
        assert len(sources) == 1

    def test_skips_entries_without_identifiers(self):
        outputs = [{"snippet": "some text without source"}]
        sources = extract_sources(outputs)
        assert sources == []


class TestFormatSourceList:
    def test_returns_markdown_block(self):
        sources = [
            {"type": "url", "id": "", "url": "https://example.com", "title": "Example"},
            {"type": "pmid", "id": "123", "url": "", "title": "PubMed"},
        ]
        block = format_source_list(sources)
        assert "### 来源 / Sources" in block
        assert "[Example](https://example.com)" in block
        assert "PMID: 123" in block

    def test_returns_empty_when_no_sources(self):
        assert format_source_list([]) == ""


class TestEnsureSourceSection:
    def test_appends_when_missing(self):
        text = "The answer is 42."
        sources = [{"type": "url", "url": "https://x.com", "title": "X", "id": ""}]
        result = ensure_source_section(text, sources)
        assert "The answer is 42." in result
        assert "### 来源 / Sources" in result

    def test_does_not_append_when_present(self):
        text = "Answer.\n\nSources: https://x.com"
        sources = [{"type": "url", "url": "https://y.com", "title": "Y", "id": ""}]
        result = ensure_source_section(text, sources)
        assert result == text

    def test_returns_original_when_no_sources(self):
        text = "Answer."
        assert ensure_source_section(text, []) == text


class TestSourceSectionPresent:
    def test_detects_chinese_and_english_headers(self):
        assert source_section_present("### 来源：...")
        assert source_section_present("Sources: ...")
        assert source_section_present("References: ...")
        assert not source_section_present("Just an answer.")
