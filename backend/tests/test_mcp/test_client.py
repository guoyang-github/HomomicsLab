"""Tests for the BioMCPClient in embedded, stdio, and SSE modes."""

import sys
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from homomics_lab.mcp.client import BioMCPClient


@pytest.mark.asyncio
async def test_embedded_list_tools():
    client = BioMCPClient(mode="embedded")
    await client.connect()
    tools = await client.list_tools()
    names = {tool["name"] for tool in tools}
    assert names >= {"pubmed_search", "pubmed_fetch", "uniprot_search", "geo_search"}
    await client.close()


@pytest.mark.asyncio
async def test_embedded_call_unknown_tool():
    client = BioMCPClient(mode="embedded")
    await client.connect()
    with pytest.raises(ValueError, match="Unknown tool"):
        await client.call_tool("not_a_tool", {})
    await client.close()


@pytest.mark.asyncio
async def test_stdio_mode_with_minimal_server():
    """Spin up a minimal stdio MCP server and exercise the full stdio flow."""
    server_code = '''
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("test-bio")

@mcp.tool()
async def echo(message: str) -> dict:
    return {"message": message}

@mcp.tool()
async def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    mcp.run(transport="stdio")
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        server_path = Path(tmpdir) / "mcp_test_server.py"
        server_path.write_text(server_code)

        client = BioMCPClient(
            mode="stdio",
            server_script=f"{sys.executable} {server_path}",
        )
        try:
            await client.connect()

            tools = await client.list_tools()
            names = {tool["name"] for tool in tools}
            assert "echo" in names
            assert "add" in names

            result = await client.call_tool("echo", {"message": "hello mcp"})
            assert result["is_error"] is False
            assert any("hello mcp" in str(item) for item in result["content"])

            result = await client.call_tool("add", {"a": 2, "b": 3})
            assert result["is_error"] is False
            assert any("5" in str(item) for item in result["content"])
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_stdio_mode_requires_server_script():
    client = BioMCPClient(mode="stdio", server_script=None)
    with pytest.raises(ValueError, match="server_script"):
        await client.connect()


@pytest.mark.asyncio
async def test_sse_mode_requires_server_url():
    client = BioMCPClient(mode="sse", server_url=None)
    with pytest.raises(ValueError, match="server_url"):
        await client.connect()


@pytest.mark.asyncio
async def test_sse_mode_connect_uses_sse_client():
    """Mock sse_client so we don't need a real HTTP server."""
    fake_read = AsyncMock()
    fake_write = AsyncMock()
    fake_session = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=None)
    fake_session.initialize = AsyncMock()
    fake_session.list_tools = AsyncMock()
    fake_session.call_tool = AsyncMock()

    @asynccontextmanager
    async def fake_sse_client(url):
        assert url == "http://localhost:9999/sse"
        yield (fake_read, fake_write)

    with patch("homomics_lab.mcp.client.sse_client", side_effect=fake_sse_client):
        with patch("homomics_lab.mcp.client.ClientSession", return_value=fake_session):
            client = BioMCPClient(mode="sse", server_url="http://localhost:9999/sse")
            try:
                await client.connect()
                assert client._session is fake_session
                fake_session.initialize.assert_awaited_once()
            finally:
                await client.close()


