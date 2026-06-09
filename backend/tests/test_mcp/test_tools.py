"""Tests for MCP bioinformatics tools (with mocked HTTP responses)."""

import json
from unittest.mock import patch, MagicMock

import pytest

from homomics_lab.mcp.tools import BioDatabaseTools
from homomics_lab.mcp.client import BioMCPClient


@pytest.fixture
def tools():
    return BioDatabaseTools()


@pytest.fixture
async def client():
    c = BioMCPClient(mode="embedded")
    await c.connect()
    return c


class TestPubMedSearch:
    @pytest.mark.asyncio
    async def test_pubmed_search(self, tools):
        """PubMed search returns structured results."""
        mock_search = {
            "esearchresult": {
                "count": "2",
                "idlist": ["12345", "67890"],
            }
        }
        mock_summary = {
            "result": {
                "12345": {
                    "title": "Single Cell Analysis",
                    "authors": [{"name": "Smith J"}],
                    "fulljournalname": "Nature",
                    "pubdate": "2024 Jan",
                    "elocationid": "doi:10.1234/test",
                },
                "67890": {
                    "title": "Spatial Transcriptomics",
                    "authors": [{"name": "Wang L"}],
                    "fulljournalname": "Science",
                    "pubdate": "2024 Feb",
                },
                "uids": ["12345", "67890"],
            }
        }

        with patch.object(tools, '_fetch_json') as mock_fetch:
            mock_fetch.side_effect = [mock_search, mock_summary]
            result = await tools.pubmed_search("single cell", retmax=5)

        assert result["count"] == "2"
        assert len(result["articles"]) == 2
        assert result["articles"][0]["title"] == "Single Cell Analysis"
        assert result["articles"][0]["pmid"] == "12345"

    @pytest.mark.asyncio
    async def test_pubmed_search_empty(self, tools):
        """Empty search returns empty results."""
        mock_search = {"esearchresult": {"count": "0", "idlist": []}}

        with patch.object(tools, '_fetch_json') as mock_fetch:
            mock_fetch.return_value = mock_search
            result = await tools.pubmed_search("xyznonexistent")

        assert result["count"] == "0"
        assert result["articles"] == []

    @pytest.mark.asyncio
    async def test_pubmed_fetch(self, tools):
        """Fetch returns article with abstract."""
        mock_summary = {
            "result": {
                "12345": {
                    "title": "Test Article",
                    "authors": [{"name": "Author A"}],
                    "fulljournalname": "Test Journal",
                    "pubdate": "2024",
                },
                "uids": ["12345"],
            }
        }

        with patch.object(tools, '_fetch_json', return_value=mock_summary), \
             patch.object(tools, '_fetch_text', return_value="Test abstract content."):
            result = await tools.pubmed_fetch("12345")

        assert result["pmid"] == "12345"
        assert result["title"] == "Test Article"
        assert "abstract" in result

    @pytest.mark.asyncio
    async def test_pubmed_error_handling(self, tools):
        """Network errors are caught gracefully."""
        with patch.object(tools, '_fetch_json', side_effect=Exception("Network error")):
            result = await tools.pubmed_search("test")

        assert "error" in result
        assert result["count"] == "0"


class TestUniProtSearch:
    @pytest.mark.asyncio
    async def test_uniprot_search(self, tools):
        """UniProt search returns protein info."""
        mock_data = {
            "results": [
                {
                    "primaryAccession": "P12345",
                    "uniProtkbId": "ABC_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {
                            "fullName": {"value": "Test Protein"}
                        }
                    },
                    "genes": [{"geneName": {"value": "ABC1"}}],
                    "organism": {"scientificName": "Homo sapiens"},
                    "sequence": {"length": 300},
                }
            ]
        }

        with patch.object(tools, '_fetch_json', return_value=mock_data):
            result = await tools.uniprot_search("ABC1")

        assert result["count"] == 1
        assert result["results"][0]["accession"] == "P12345"
        assert result["results"][0]["genes"] == ["ABC1"]


class TestGEOSearch:
    @pytest.mark.asyncio
    async def test_geo_search(self, tools):
        """GEO search returns dataset info."""
        mock_search = {
            "esearchresult": {
                "count": "1",
                "idlist": ["200123"],
            }
        }
        mock_summary = {
            "result": {
                "200123": {
                    "title": "GSE12345",
                    "summary": "Test dataset summary",
                    "taxon": "Homo sapiens",
                    "gpl": "GPL123",
                    "n_samples": "10",
                },
                "uids": ["200123"],
            }
        }

        with patch.object(tools, '_fetch_json') as mock_fetch:
            mock_fetch.side_effect = [mock_search, mock_summary]
            result = await tools.geo_search("single cell")

        assert result["count"] == "1"
        assert len(result["datasets"]) == 1
        assert result["datasets"][0]["title"] == "GSE12345"


class TestMCPClient:
    @pytest.mark.asyncio
    async def test_client_list_tools(self):
        """Client lists available tools."""
        client = BioMCPClient(mode="embedded")
        tools = await client.list_tools()

        tool_names = {t["name"] for t in tools}
        assert "pubmed_search" in tool_names
        assert "uniprot_search" in tool_names
        assert "geo_search" in tool_names

    @pytest.mark.asyncio
    async def test_client_call_tool(self):
        """Client calls tools via unified interface."""
        client = BioMCPClient(mode="embedded")
        await client.connect()

        mock_result = {"count": "0", "articles": []}
        with patch.object(client._tools, 'pubmed_search', return_value=mock_result):
            result = await client.call_tool("pubmed_search", {"query": "test", "retmax": 5})

        assert result == mock_result

    @pytest.mark.asyncio
    async def test_client_unknown_tool(self):
        """Calling unknown tool raises error."""
        client = BioMCPClient(mode="embedded")
        await client.connect()

        with pytest.raises(ValueError, match="Unknown tool"):
            await client.call_tool("nonexistent", {})
