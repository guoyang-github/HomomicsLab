"""Tests for the MCP server marketplace."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homomics_lab.mcp.client import BioMCPClient
from homomics_lab.mcp.marketplace import MCPMarketplace, MCPServerEntry
from homomics_lab.tools.registry import ToolRegistry


@pytest.fixture
def marketplace_paths():
    """Temporary paths for marketplace state/catalog/venv."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        yield {
            "state_path": base / "mcp_servers.json",
            "catalog_path": base / "mcp_catalog.json",
            "venv_dir": base / "mcp_venvs",
        }


@pytest.fixture
def marketplace(marketplace_paths):
    return MCPMarketplace(**marketplace_paths)


@pytest.mark.asyncio
async def test_builtin_catalog_seeded(marketplace):
    servers = marketplace.list_servers()
    assert any(s.id == "homomics-bio" for s in servers)
    bio = marketplace.get_server("homomics-bio")
    assert bio is not None
    assert bio.transport == "embedded"
    assert bio.builtin is True
    assert bio.enabled is True


@pytest.mark.asyncio
async def test_list_servers_includes_user_added(marketplace):
    marketplace.add_server(
        MCPServerEntry(
            id="my-sse",
            name="My SSE Server",
            transport="sse",
            url="http://localhost:9999/sse",
        )
    )
    servers = marketplace.list_servers()
    ids = {s.id for s in servers}
    assert "homomics-bio" in ids
    assert "my-sse" in ids


@pytest.mark.asyncio
async def test_add_server_rejects_builtin_and_duplicates(marketplace):
    with pytest.raises(ValueError, match="built-in"):
        marketplace.add_server(
            MCPServerEntry(id="homomics-bio", name="Bio", transport="embedded", builtin=True)
        )

    marketplace.add_server(
        MCPServerEntry(id="unique", name="Unique", transport="sse", url="http://x/sse")
    )
    with pytest.raises(ValueError, match="already exists"):
        marketplace.add_server(
            MCPServerEntry(id="unique", name="Unique", transport="sse", url="http://x/sse")
        )


@pytest.mark.asyncio
async def test_remove_server_non_builtin(marketplace):
    marketplace.add_server(
        MCPServerEntry(id="removable", name="Removable", transport="sse", url="http://x/sse")
    )
    removed = marketplace.remove_server("removable")
    assert removed is True
    assert marketplace.get_server("removable") is None

    with pytest.raises(ValueError, match="built-in"):
        await marketplace.remove_server("homomics-bio")


@pytest.mark.asyncio
async def test_enable_embedded_server_registers_tools(marketplace):
    registry = ToolRegistry()
    entry = await marketplace.enable_server("homomics-bio", registry)
    assert entry.enabled is True
    assert len(entry.tools) >= 4
    assert registry.get("pubmed_search") is not None
    assert registry.get("uniprot_search") is not None


@pytest.mark.asyncio
async def test_disable_server_unregisters_tools(marketplace):
    registry = ToolRegistry()
    await marketplace.enable_server("homomics-bio", registry)
    assert registry.get("pubmed_search") is not None

    await marketplace.disable_server("homomics-bio", registry)
    assert registry.get("pubmed_search") is None
    assert registry.list_by_source("mcp") == []


@pytest.mark.asyncio
async def test_register_enabled_servers_at_startup(marketplace):
    registry = ToolRegistry()
    await marketplace.register_enabled_servers(registry)
    # homomics-bio is enabled by default
    assert registry.get("pubmed_search") is not None


@pytest.mark.asyncio
async def test_unregister_by_source(marketplace):
    registry = ToolRegistry()
    await marketplace.enable_server("homomics-bio", registry)
    removed = registry.unregister_by_source("mcp")
    assert "pubmed_search" in removed
    assert registry.list_by_source("mcp") == []


@pytest.mark.asyncio
async def test_health_check_embedded(marketplace):
    result = await marketplace.health_check("homomics-bio")
    assert result["status"] == "ok"
    assert result["tool_count"] >= 4


@pytest.mark.asyncio
async def test_health_check_stdio_failure(marketplace):
    marketplace.add_server(
        MCPServerEntry(
            id="bad-stdio",
            name="Bad Stdio",
            transport="stdio",
            command="/nonexistent/python",
            args=["-m", "none"],
        )
    )
    result = await marketplace.health_check("bad-stdio")
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_enable_stdio_server_with_mocked_client(marketplace):
    registry = ToolRegistry()
    marketplace.add_server(
        MCPServerEntry(
            id="mock-stdio",
            name="Mock Stdio",
            transport="stdio",
            command="python",
            args=["-m", "mock_server"],
            installed=True,
        )
    )

    fake_client = AsyncMock(spec=BioMCPClient)
    fake_client.connect = AsyncMock()
    fake_client.list_tools = AsyncMock(
        return_value=[
            {
                "name": "echo",
                "description": "Echo tool",
                "parameters": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            }
        ]
    )

    with patch.object(marketplace, "_connect_server", return_value=fake_client):
        entry = await marketplace.enable_server("mock-stdio", registry)

    assert entry.enabled is True
    assert registry.get("echo") is not None
    assert registry.get("echo").metadata.get("mcp_server") == "mock-stdio"


@pytest.mark.asyncio
async def test_install_server_requires_stdio_package(marketplace):
    marketplace.add_server(
        MCPServerEntry(
            id="no-package",
            name="No Package",
            transport="stdio",
            command="python",
            args=["-m", "server"],
        )
    )
    with pytest.raises(ValueError, match="Package is required"):
        await marketplace.install_server("no-package")


@pytest.mark.asyncio
async def test_install_server_updates_entry(marketplace):
    """install_server should mark the entry installed and set command/args.

    The actual venv/pip work is mocked so the test does not require network.
    """
    marketplace.add_server(
        MCPServerEntry(
            id="pip-install",
            name="Pip Install",
            transport="stdio",
            package="pip",
        )
    )

    def _fake_create_and_install(id_: str, package: str) -> None:
        entry = marketplace._state.get(id_)
        if entry is not None:
            entry.command = "/fake/venv/bin/python"
            entry.args = ["-m", package]

    with patch.object(marketplace, "_create_and_install", side_effect=_fake_create_and_install):
        entry = await marketplace.install_server("pip-install")

    assert entry.installed is True
    assert entry.install_status == "installed"
    assert entry.command == "/fake/venv/bin/python"
    assert entry.args == ["-m", "pip"]


@pytest.mark.asyncio
async def test_state_persists(marketplace_paths):
    marketplace = MCPMarketplace(**marketplace_paths)
    marketplace.add_server(
        MCPServerEntry(id="persisted", name="Persisted", transport="sse", url="http://x/sse")
    )

    marketplace2 = MCPMarketplace(**marketplace_paths)
    entry = marketplace2.get_server("persisted")
    assert entry is not None
    assert entry.name == "Persisted"


@pytest.mark.asyncio
async def test_catalog_persists_builtin(marketplace_paths):
    MCPMarketplace(**marketplace_paths)
    catalog = json.loads(marketplace_paths["catalog_path"].read_text(encoding="utf-8"))
    assert any(item["id"] == "homomics-bio" for item in catalog)
