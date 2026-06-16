"""Tests for LiteratureRetriever."""

from unittest.mock import patch

from homomics_lab.agent.literature_retriever import LiteratureRetriever


class MockResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_retrieve_returns_pubmed_records():
    search_response = b'{"esearchresult": {"idlist": ["12345", "67890"]}}'
    summary_response = b'{"result": {"12345": {"title": "Paper One", "source": "Nature", "pubdate": "2024"}, "67890": {"title": "Paper Two", "source": "Science", "pubdate": "2023"}, "uids": ["12345", "67890"]}}'

    retriever = LiteratureRetriever(max_results=2)

    def fake_urlopen(url, **kwargs):
        if "esearch" in url:
            return MockResponse(search_response)
        return MockResponse(summary_response)

    with patch("homomics_lab.agent.literature_retriever.urlopen", fake_urlopen):
        records = retriever.retrieve("single cell RNA-seq")

    assert len(records) == 2
    assert records[0]["pmid"] == "12345"
    assert "pubmed.ncbi.nlm.nih.gov" in records[0]["url"]


def test_retrieve_falls_back_on_network_error():
    retriever = LiteratureRetriever()
    with patch("homomics_lab.agent.literature_retriever.urlopen", side_effect=Exception("network down")):
        records = retriever.retrieve("anything")

    assert records == []
