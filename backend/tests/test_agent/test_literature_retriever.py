"""Tests for the async LiteratureRetriever and its adapters."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homomics_lab.agent.literature_retriever import (
    BioRxivAdapter,
    EuropePMCAdapter,
    LiteratureAdapter,
    LiteratureRetriever,
    LiteratureRetrieverError,
    PubMedAdapter,
)


def _make_json_response(payload: dict, status: int = 200):
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=payload)
    response.raise_for_status = MagicMock()
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    return response


def _make_failing_session(status: int = 500):
    response = MagicMock()
    response.status = status
    response.raise_for_status = MagicMock(side_effect=Exception(f"HTTP {status}"))
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.get = MagicMock(return_value=response)
    session.close = AsyncMock()
    return session


def _make_session_from_mapping(url_to_response: dict):
    """Return a mock session whose .get returns the response matching a substring."""
    session = MagicMock()

    def fake_get(url, **kwargs):
        for key, response in url_to_response.items():
            if key in url:
                return response
        raise ValueError(f"Unexpected URL: {url}")

    session.get = MagicMock(side_effect=fake_get)
    session.close = AsyncMock()
    return session


class TestPubMedAdapter:
    @pytest.mark.asyncio
    async def test_search_returns_records(self):
        search_payload = {"esearchresult": {"idlist": ["12345", "67890"]}}
        summary_payload = {
            "result": {
                "12345": {"title": "Paper One", "source": "Nature", "pubdate": "2024"},
                "67890": {"title": "Paper Two", "source": "Science", "pubdate": "2023"},
                "uids": ["12345", "67890"],
            }
        }

        session = _make_session_from_mapping({
            "esearch": _make_json_response(search_payload),
            "esummary": _make_json_response(summary_payload),
        })

        adapter = PubMedAdapter(session=session)
        records = await adapter.search("single cell RNA-seq", 2)

        assert len(records) == 2
        assert records[0]["pmid"] == "12345"
        assert records[0]["title"] == "Paper One"
        assert "pubmed.ncbi.nlm.nih.gov" in records[0]["url"]
        session.close.assert_not_awaited()  # provided session must not be closed

    @pytest.mark.asyncio
    async def test_search_raises_on_http_error(self):
        session = _make_failing_session(500)
        adapter = PubMedAdapter(session=session)
        with pytest.raises(LiteratureRetrieverError):
            await adapter.search("anything", 5)


class TestEuropePMCAdapter:
    @pytest.mark.asyncio
    async def test_search_returns_records(self):
        payload = {
            "resultList": {
                "result": [
                    {
                        "id": "PMC123",
                        "pmid": "11111",
                        "doi": "10.1/test",
                        "pmcid": "PMC123",
                        "title": "Europe Paper",
                        "source": "PLoS One",
                        "pubYear": "2023",
                    }
                ]
            }
        }
        session = MagicMock()
        session.get = MagicMock(return_value=_make_json_response(payload))
        session.close = AsyncMock()

        adapter = EuropePMCAdapter(session=session)
        records = await adapter.search("rna-seq", 5)

        assert len(records) == 1
        assert records[0]["title"] == "Europe Paper"
        assert records[0]["pmid"] == "11111"
        assert records[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/11111/"


class TestBioRxivAdapter:
    @pytest.mark.asyncio
    async def test_search_returns_records(self):
        payload = {
            "collection": [
                {
                    "doi": "10.1101/2023.01.01.123456",
                    "title": "BioRxiv Preprint",
                    "date": "2023-01-01",
                }
            ]
        }
        session = MagicMock()
        session.get = MagicMock(return_value=_make_json_response(payload))
        session.close = AsyncMock()

        adapter = BioRxivAdapter(session=session)
        records = await adapter.search("covid19", 5)

        assert len(records) == 1
        assert records[0]["title"] == "BioRxiv Preprint"
        assert "biorxiv.org" in records[0]["url"]


class TestLiteratureRetriever:
    @pytest.mark.asyncio
    async def test_retrieve_merges_and_deduplicates(self):
        pubmed_records = [
            {"pmid": "1", "title": "Shared Title", "source": "PubMed", "pubdate": "2024"},
            {"pmid": "2", "title": "Only PubMed", "source": "PubMed", "pubdate": "2024"},
        ]
        europe_records = [
            {"pmid": "1", "title": "Shared Title", "source": "Europe PMC", "pubdate": "2024"},
            {"pmid": "3", "title": "Only Europe", "source": "Europe PMC", "pubdate": "2023"},
        ]
        biorxiv_records = [
            {"doi": "10.1101/only", "title": "Only bioRxiv", "date": "2023-01-01"},
        ]

        class FakeAdapter(LiteratureAdapter):
            name = "fake"

            def __init__(self, records):
                self._records = records

            async def search(self, query, max_results):
                return self._records

        retriever = LiteratureRetriever(adapters=[
            FakeAdapter(pubmed_records),
            FakeAdapter(europe_records),
            FakeAdapter(biorxiv_records),
        ])

        results = await retriever.retrieve("query", max_results=10)

        assert len(results) == 4
        titles = {r["title"] for r in results}
        assert titles == {"Shared Title", "Only PubMed", "Only Europe", "Only bioRxiv"}

    @pytest.mark.asyncio
    async def test_retrieve_returns_partial_results_on_adapter_failure(self):
        success_records = [{"pmid": "1", "title": "OK", "source": "PubMed"}]

        class SuccessAdapter(LiteratureAdapter):
            name = "success"

            async def search(self, query, max_results):
                return success_records

        class FailAdapter(LiteratureAdapter):
            name = "fail"

            async def search(self, query, max_results):
                raise LiteratureRetrieverError("boom")

        retriever = LiteratureRetriever(adapters=[SuccessAdapter(), FailAdapter()])
        results = await retriever.retrieve("query", max_results=10)

        assert results == success_records

    @pytest.mark.asyncio
    async def test_retrieve_raises_when_all_adapters_fail(self):
        class FailAdapter(LiteratureAdapter):
            name = "fail"

            async def search(self, query, max_results):
                raise LiteratureRetrieverError("boom")

        retriever = LiteratureRetriever(adapters=[FailAdapter()])
        with pytest.raises(LiteratureRetrieverError):
            await retriever.retrieve("query", max_results=10)

    @pytest.mark.asyncio
    async def test_cache_avoids_second_request(self):
        records = [{"pmid": "1", "title": "Cached", "source": "PubMed"}]

        class CountingAdapter(LiteratureAdapter):
            name = "counting"

            def __init__(self):
                self.calls = 0

            async def search(self, query, max_results):
                self.calls += 1
                return records

        adapter = CountingAdapter()
        retriever = LiteratureRetriever(adapters=[adapter])

        first = await retriever.retrieve("query", max_results=5)
        second = await retriever.retrieve("query", max_results=5)

        assert first == records
        assert second == records
        assert adapter.calls == 1

    @pytest.mark.asyncio
    async def test_retrieve_respects_max_results(self):
        records = [{"pmid": str(i), "title": f"Paper {i}", "source": "PubMed"} for i in range(20)]

        class BulkAdapter(LiteratureAdapter):
            name = "bulk"

            async def search(self, query, max_results):
                return records[:max_results]

        retriever = LiteratureRetriever(adapters=[BulkAdapter()], max_results=3)
        results = await retriever.retrieve("query")

        assert len(results) == 3

    def test_retrieve_sync(self):
        records = [{"pmid": "1", "title": "Sync", "source": "PubMed"}]

        class SyncAdapter(LiteratureAdapter):
            name = "sync"

            async def search(self, query, max_results):
                return records

        retriever = LiteratureRetriever(adapters=[SyncAdapter()])
        results = retriever.retrieve_sync("query", max_results=5)

        assert results == records


class TestPubMedAdapterWithMockedClientSession:
    @pytest.mark.asyncio
    async def test_uses_api_key_when_provided(self, monkeypatch):
        payload = {"esearchresult": {"idlist": []}}
        response = _make_json_response(payload)
        session = MagicMock()
        session.get = MagicMock(return_value=response)
        session.close = AsyncMock()

        adapter = PubMedAdapter(email="test@example.com", api_key="secret", session=session)
        await adapter.search("query", 5)

        call_args = session.get.call_args
        url = call_args[0][0]
        assert "api_key=secret" in url
        assert "email=test%40example.com" in url
