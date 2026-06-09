"""Tests for context compressor."""

import pytest

from homomics_lab.context.compressor import ContextCompressor
from homomics_lab.context.relevance_filter import ContextItem


class TestContextCompressor:
    def test_compress_empty(self):
        compressor = ContextCompressor()
        result = compressor.compress([], "analyze single cell data")
        assert result == []

    def test_compress_within_budget(self):
        compressor = ContextCompressor(max_items=5)
        items = [
            ContextItem(content="Step 1: Load data", type="chat", hours_since_created=0.5),
            ContextItem(content="Step 2: QC filtering", type="result", hours_since_created=0.3),
            ContextItem(content="Step 3: Clustering", type="result", hours_since_created=0.1),
        ]
        result = compressor.compress(items, "clustering analysis")
        assert len(result) == 3
        # All items should be preserved as they're within budget

    def test_compress_exceeds_budget(self):
        compressor = ContextCompressor(max_items=2)
        items = [
            ContextItem(content="Old conversation about loading data", type="chat", hours_since_created=5.0),
            ContextItem(content="QC results show good quality", type="result", hours_since_created=2.0),
            ContextItem(content="Clustering found 12 cell types", type="result", hours_since_created=0.5, is_upstream_result=True),
        ]
        result = compressor.compress(items, "clustering analysis")
        assert len(result) <= 2
        # Most relevant items should be kept

    def test_compress_summarizes_long_items(self):
        compressor = ContextCompressor(max_items=5, max_chars_per_item=100)
        long_content = "This is a very long result text. " * 50
        items = [
            ContextItem(content=long_content, type="result", hours_since_created=0.5),
        ]
        result = compressor.compress(items, "analysis")
        assert len(result) == 1
        assert len(result[0].content) <= 500  # Should be summarized
        assert "Key points" in result[0].content or len(result[0].content) < len(long_content)

    def test_deduplicate_similar_items(self):
        compressor = ContextCompressor()
        items = [
            ContextItem(content="Quality control passed with good metrics", type="result"),
            ContextItem(content="Quality control passed with good metrics", type="result"),
            ContextItem(content="Clustering completed successfully", type="result"),
        ]
        result = compressor._deduplicate(items)
        assert len(result) == 2  # One duplicate removed

    def test_pinned_items_preserved(self):
        compressor = ContextCompressor(max_items=2)
        items = [
            ContextItem(content="Pinned important info", type="chat", is_pinned=True),
            ContextItem(content="Regular item 1", type="chat"),
            ContextItem(content="Regular item 2", type="chat"),
            ContextItem(content="Regular item 3", type="chat"),
        ]
        result = compressor.compress(items, "analysis")
        # Pinned item should always be included
        assert any(item.is_pinned for item in result)

    def test_similarity_metric(self):
        compressor = ContextCompressor()
        assert compressor._similarity("hello world", "hello world") == 1.0
        assert compressor._similarity("hello world", "foo bar") == 0.0
        sim = compressor._similarity("hello world test", "hello world")
        assert 0 < sim < 1.0
