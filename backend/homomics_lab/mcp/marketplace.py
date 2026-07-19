"""MCP server marketplace — enable/install external MCP servers.

The marketplace persists user-added servers in ``mcp_servers.json`` and merges
them with a built-in catalog (``mcp_marketplace_catalog.json``). Enabled servers
are connected at startup and their tools are registered into the shared
``ToolRegistry`` so that agents can use them alongside native tools.
"""

import asyncio
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from typing_extensions import Literal

from homomics_lab.mcp.client import BioMCPClient
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# MCP marketplace storage locations (formerly HOMOMICS_MCP_* config fields;
# defaults kept).
MCP_VENV_DIR = Path("./data/mcp_venvs")
MCP_SERVERS_STATE_PATH = Path("./data/mcp_servers.json")
MCP_MARKETPLACE_CATALOG_PATH = Path("./data/mcp_marketplace_catalog.json")

Transport = Literal["embedded", "stdio", "sse"]


class MCPServerEntry(BaseModel):
    """Persisted description of an MCP server available in the marketplace."""

    id: str
    name: str
    description: str = ""
    transport: Transport
    package: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    env: Dict[str, str] = Field(default_factory=dict)
    category: str = "general"
    enabled: bool = False
    installed: bool = False
    trusted: bool = False
    builtin: bool = False
    install_status: Optional[str] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("transport")
    @classmethod
    def _validate_transport(cls, v: str) -> str:
        if v not in {"embedded", "stdio", "sse"}:
            raise ValueError(f"transport must be one of embedded/stdio/sse, got {v}")
        return v

    def server_script(self) -> Optional[str]:
        """Return the stdio server script string, or None if not applicable."""
        if self.transport != "stdio":
            return None
        if not self.command:
            return None
        import shlex

        return self.command + " " + " ".join(shlex.quote(a) for a in self.args)


class MCPMarketplace:
    """Manage MCP server catalog, installation, and tool registration."""

    def __init__(
        self,
        state_path: Optional[Path] = None,
        catalog_path: Optional[Path] = None,
        venv_dir: Optional[Path] = None,
    ):
        self.state_path = Path(state_path or MCP_SERVERS_STATE_PATH)
        self.catalog_path = Path(catalog_path or MCP_MARKETPLACE_CATALOG_PATH)
        self.venv_dir = Path(venv_dir or MCP_VENV_DIR)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.venv_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_builtin_catalog()
        self._state: Dict[str, MCPServerEntry] = {}
        self._clients: Dict[str, BioMCPClient] = {}
        self._load_state()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _ensure_builtin_catalog(self) -> None:
        """Seed the catalog with the built-in Homomics bio server if missing."""
        if self.catalog_path.exists():
            return
        catalog = [
            {
                "id": "homomics-bio",
                "name": "Homomics Bio",
                "description": "Built-in bioinformatics MCP tools (PubMed, UniProt, GEO).",
                "transport": "embedded",
                "category": "bioinformatics",
                "enabled": True,
                "installed": True,
                "trusted": True,
                "builtin": True,
            }
        ]
        try:
            self.catalog_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        except Exception:
            logger.warning("Failed to write MCP catalog", exc_info=True)

    def _load_catalog(self) -> Dict[str, MCPServerEntry]:
        """Load built-in/user catalog entries from disk."""
        if not self.catalog_path.exists():
            return {}
        try:
            data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load MCP catalog", exc_info=True)
            return {}
        entries: Dict[str, MCPServerEntry] = {}
        for item in data:
            try:
                entry = MCPServerEntry(**item)
                entries[entry.id] = entry
            except Exception:
                logger.warning("Invalid catalog entry: %s", item, exc_info=True)
        return entries

    def _load_state(self) -> None:
        """Load user overrides (enabled/installed/tools) from disk."""
        if not self.state_path.exists():
            self._state = {}
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load MCP state", exc_info=True)
            self._state = {}
            return
        self._state = {}
        for item in data:
            try:
                entry = MCPServerEntry(**item)
                self._state[entry.id] = entry
            except Exception:
                logger.warning("Invalid state entry: %s", item, exc_info=True)

    def _save_state(self) -> None:
        """Persist user overrides to disk."""
        try:
            data = [entry.model_dump() for entry in self._state.values()]
            self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            logger.warning("Failed to save MCP state", exc_info=True)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def list_servers(self) -> List[MCPServerEntry]:
        """List all servers from the catalog merged with user state."""
        catalog = self._load_catalog()
        merged = dict(catalog)
        for id_, entry in self._state.items():
            merged[id_] = entry
        return sorted(merged.values(), key=lambda e: (not e.builtin, e.name.lower()))

    def get_server(self, id_: str) -> Optional[MCPServerEntry]:
        """Get a server by id, preferring user state over catalog."""
        if id_ in self._state:
            return self._state[id_]
        return self._load_catalog().get(id_)

    def add_server(self, entry: MCPServerEntry) -> MCPServerEntry:
        """Add a new user-defined server."""
        if entry.builtin:
            raise ValueError("Cannot add a built-in server")
        if entry.id in self._state or entry.id in self._load_catalog():
            raise ValueError(f"Server '{entry.id}' already exists")
        self._state[entry.id] = entry
        self._save_state()
        return entry

    def update_server(self, id_: str, entry: MCPServerEntry) -> MCPServerEntry:
        """Update an existing user-defined server (non-builtin only)."""
        if entry.builtin:
            raise ValueError("Cannot update a built-in server")
        existing = self.get_server(id_)
        if existing is None:
            raise ValueError(f"Server '{id_}' not found")
        if existing.builtin:
            raise ValueError("Cannot update a built-in server")
        self._state[id_] = entry
        self._save_state()
        return entry

    def remove_server(self, id_: str) -> bool:
        """Remove a user-defined server. Built-in servers cannot be removed."""
        entry = self.get_server(id_)
        if entry is None:
            raise ValueError(f"Server '{id_}' not found")
        if entry.builtin:
            raise ValueError("Cannot remove a built-in server")
        if id_ in self._state:
            if self._state[id_].enabled:
                self._state[id_].enabled = False
                self._unregister_server_tools(id_)
            del self._state[id_]
            self._save_state()
            return True
        return False

    # ------------------------------------------------------------------
    # Installation / enablement
    # ------------------------------------------------------------------

    async def install_server(self, id_: str) -> MCPServerEntry:
        """Install a stdio server package into an isolated venv.

        Uses ``uv pip install`` when ``uv`` is available, otherwise falls back to
        ``python -m pip install``.
        """
        entry = self.get_server(id_)
        if entry is None:
            raise ValueError(f"Server '{id_}' not found")
        if entry.transport != "stdio":
            raise ValueError("Installation is only supported for stdio transport")
        if not entry.package:
            raise ValueError("Package is required for stdio installation")

        entry.install_status = "installing"
        self._state[id_] = entry
        self._save_state()

        try:
            await asyncio.to_thread(self._create_and_install, id_, entry.package)
            entry.installed = True
            entry.install_status = "installed"
        except Exception as exc:
            entry.install_status = f"failed: {exc}"
            logger.exception("Failed to install MCP server %s", id_)

        self._state[id_] = entry
        self._save_state()
        return entry

    def _create_and_install(self, id_: str, package: str) -> None:
        """Synchronous venv creation + package installation."""
        venv_path = self.venv_dir / f"mcp-{id_}"
        if venv_path.exists():
            shutil.rmtree(venv_path)
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

        python = venv_path / "bin" / "python"
        if not python.exists():
            python = venv_path / "Scripts" / "python.exe"

        uv = shutil.which("uv")
        if uv:
            subprocess.run(
                [uv, "pip", "install", "--python", str(python), package],
                check=True,
            )
        else:
            subprocess.run([str(python), "-m", "pip", "install", package], check=True)

        entry = self._state.get(id_)
        if entry is not None:
            entry.command = str(python)
            entry.args = ["-m", package]

    async def enable_server(self, id_: str, tool_registry: ToolRegistry) -> MCPServerEntry:
        """Enable a server and register its tools."""
        entry = self.get_server(id_)
        if entry is None:
            raise ValueError(f"Server '{id_}' not found")
        if entry.transport == "stdio" and not entry.installed:
            raise ValueError("stdio server must be installed before enabling")

        client = self._connect_server(entry)
        try:
            await client.connect()
            tools = await client.list_tools()
        except Exception:
            await client.close()
            raise

        entry.tools = tools
        entry.enabled = True
        self._state[id_] = entry
        self._save_state()
        self._register_tools(id_, entry, client, tool_registry)
        return entry

    async def disable_server(self, id_: str, tool_registry: ToolRegistry) -> MCPServerEntry:
        """Disable a server and unregister its tools."""
        entry = self.get_server(id_)
        if entry is None:
            raise ValueError(f"Server '{id_}' not found")
        self._unregister_server_tools(id_, tool_registry)
        entry.enabled = False
        entry.tools = []
        self._state[id_] = entry
        self._save_state()
        return entry

    # ------------------------------------------------------------------
    # Health / startup registration
    # ------------------------------------------------------------------

    async def health_check(self, id_: str) -> Dict[str, Any]:
        """Connect to a server and return its tool list / error."""
        entry = self.get_server(id_)
        if entry is None:
            raise ValueError(f"Server '{id_}' not found")
        client = self._connect_server(entry)
        try:
            await client.connect()
            tools = await client.list_tools()
            return {
                "id": id_,
                "status": "ok",
                "tool_count": len(tools),
                "tools": tools,
            }
        except Exception as exc:
            return {
                "id": id_,
                "status": "error",
                "error": str(exc),
                "tool_count": 0,
                "tools": [],
            }
        finally:
            await client.close()

    async def register_enabled_servers(self, tool_registry: ToolRegistry) -> None:
        """Register all enabled servers at startup."""
        for entry in self.list_servers():
            if not entry.enabled:
                continue
            try:
                if entry.transport == "stdio" and not entry.installed:
                    logger.warning(
                        "Skipping enabled stdio server %s (not installed)", entry.id
                    )
                    continue
                client = self._connect_server(entry)
                await client.connect()
                tools = await client.list_tools()
                entry.tools = tools
                self._register_tools(entry.id, entry, client, tool_registry)
                self._state[entry.id] = entry
                logger.info(
                    "Registered MCP server %s with %d tools", entry.id, len(tools)
                )
            except Exception as exc:
                logger.warning(
                    "Failed to register MCP server %s: %s", entry.id, exc
                )
        self._save_state()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close any active MCP client connections."""
        for id_, client in list(self._clients.items()):
            try:
                await client.close()
            except Exception:
                logger.warning("Failed to close MCP client %s", id_, exc_info=True)
        self._clients.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect_server(self, entry: MCPServerEntry) -> BioMCPClient:
        """Create an unconnected BioMCPClient for the given server entry."""
        if entry.transport == "embedded":
            return BioMCPClient(mode="embedded")
        if entry.transport == "stdio":
            script = entry.server_script()
            if not script:
                raise ValueError("stdio server has no command configured")
            return BioMCPClient(mode="stdio", server_script=script)
        if entry.transport == "sse":
            if not entry.url:
                raise ValueError("sse server has no url configured")
            return BioMCPClient(mode="sse", server_url=entry.url)
        raise ValueError(f"Unknown transport: {entry.transport}")

    def _register_tools(
        self,
        id_: str,
        entry: MCPServerEntry,
        client: BioMCPClient,
        tool_registry: ToolRegistry,
    ) -> None:
        """Register tools from a connected MCP client into the tool registry."""
        from homomics_lab.mcp.integration import _infer_risk_level

        for tool_desc in entry.tools:
            name = tool_desc["name"]
            schema = tool_desc.get("parameters") or tool_desc.get(
                "inputSchema", {"type": "object"}
            )
            tool = ToolDefinition(
                name=name,
                description=tool_desc.get("description", ""),
                input_schema=schema,
                source="mcp",
                risk_level=_infer_risk_level(name),
                metadata={
                    "mcp_mode": entry.transport,
                    "mcp_server": id_,
                    "mcp_server_name": entry.name,
                },
                handler=_make_tool_handler(client, name),
            )
            tool_registry.register(tool)
            logger.info("Registered MCP tool %s from server %s", name, id_)
        self._clients[id_] = client

    def _unregister_server_tools(self, id_: str, tool_registry: ToolRegistry) -> None:
        """Remove tools belonging to a given server and close its client."""
        removed: List[str] = []
        for tool in list(tool_registry.list_all()):
            if tool.metadata.get("mcp_server") == id_:
                tool_registry.unregister(tool.name)
                removed.append(tool.name)
        client = self._clients.pop(id_, None)
        if client is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(client.close())
            except RuntimeError:
                try:
                    asyncio.run(client.close())
                except Exception:
                    logger.warning(
                        "Failed to close MCP client %s", id_, exc_info=True
                    )
        logger.info("Unregistered MCP tools for server %s: %s", id_, removed)


def _make_tool_handler(client: BioMCPClient, tool_name: str):
    """Return an async handler for a specific MCP tool."""

    async def handler(**inputs: Any) -> Dict[str, Any]:
        return await client.call_tool(tool_name, inputs)

    handler.__name__ = f"mcp_{tool_name}"
    return handler
