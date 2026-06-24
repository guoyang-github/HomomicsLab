"""MCP client for bioinformatics databases.

Supports three modes:
  1. Embedded: Direct Python calls (no subprocess, no MCP protocol overhead)
  2. MCP stdio: Connects to an MCP server via stdio for protocol compatibility
  3. MCP SSE: Connects to an MCP server via Server-Sent Events over HTTP

Usage (embedded):
    client = BioMCPClient(mode="embedded")
    results = await client.call_tool("pubmed_search", {"query": "scRNA-seq", "retmax": 5})

Usage (MCP stdio):
    client = BioMCPClient(mode="stdio", server_script="mcp_server.py")
    await client.connect()
    results = await client.call_tool("pubmed_search", {"query": "scRNA-seq", "retmax": 5})

Usage (MCP SSE):
    client = BioMCPClient(mode="sse", server_url="http://localhost:8000/sse")
    await client.connect()
    results = await client.call_tool("pubmed_search", {"query": "scRNA-seq", "retmax": 5})
"""

import shlex
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from homomics_lab.mcp.tools import BioDatabaseTools


class BioMCPClient:
    """Client for bioinformatics MCP tools.

    Mode 'embedded' uses direct Python calls (fastest, no dependencies).
    Mode 'stdio' uses the MCP protocol over stdio (interoperable).
    Mode 'sse' uses the MCP protocol over Server-Sent Events (interoperable).
    """

    def __init__(
        self,
        mode: str = "embedded",
        server_script: Optional[str] = None,
        server_url: Optional[str] = None,
        email: Optional[str] = None,
    ):
        self.mode = mode
        self.server_script = server_script
        self.server_url = server_url
        self.email = email
        self._tools: Optional[BioDatabaseTools] = None
        self._session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None

    async def connect(self) -> None:
        """Initialize the client connection."""
        if self.mode == "embedded":
            self._tools = BioDatabaseTools(email=self.email)
        elif self.mode == "stdio":
            await self._connect_stdio()
        elif self.mode == "sse":
            await self._connect_sse()
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    async def _connect_stdio(self) -> None:
        """Connect to MCP server via stdio (MCP protocol)."""
        if not self.server_script:
            raise ValueError(
                "MCP stdio mode requires a server_script (e.g. 'python /path/to/server.py')."
            )

        parts = shlex.split(self.server_script)
        if not parts:
            raise ValueError("server_script must contain a command")

        server_params = StdioServerParameters(
            command=parts[0],
            args=parts[1:],
            env=None,  # inherit environment
        )

        self._exit_stack = AsyncExitStack()
        try:
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
        except Exception:
            await self._exit_stack.aclose()
            self._exit_stack = None
            raise

    async def _connect_sse(self) -> None:
        """Connect to MCP server via SSE (MCP protocol)."""
        if not self.server_url:
            raise ValueError("MCP sse mode requires a server_url.")

        self._exit_stack = AsyncExitStack()
        try:
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                sse_client(self.server_url)
            )
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()
        except Exception:
            await self._exit_stack.aclose()
            self._exit_stack = None
            raise

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools.

        Returns:
            List of tool descriptors with name, description, and parameters.
        """
        if self.mode == "embedded":
            # Keep the backward-compatible hard-coded descriptor list.
            return [
                {
                    "name": "pubmed_search",
                    "description": "Search PubMed for scientific articles",
                    "parameters": {
                        "query": {"type": "string", "description": "Search terms"},
                        "retmax": {"type": "integer", "description": "Max results", "default": 10},
                    },
                },
                {
                    "name": "pubmed_fetch",
                    "description": "Fetch article abstract by PubMed ID",
                    "parameters": {
                        "pmid": {"type": "string", "description": "PubMed ID"},
                    },
                },
                {
                    "name": "uniprot_search",
                    "description": "Search UniProt for protein information",
                    "parameters": {
                        "query": {"type": "string", "description": "Protein name or gene"},
                        "limit": {"type": "integer", "description": "Max results", "default": 10},
                    },
                },
                {
                    "name": "geo_search",
                    "description": "Search GEO for gene expression datasets",
                    "parameters": {
                        "query": {"type": "string", "description": "Search terms"},
                        "retmax": {"type": "integer", "description": "Max results", "default": 10},
                    },
                },
            ]

        if self._session is None:
            raise RuntimeError("Client not connected")

        response = await self._session.list_tools()
        tools: List[Dict[str, Any]] = []
        for tool in response.tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                }
            )
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call a bioinformatics tool.

        Args:
            tool_name: One of pubmed_search, pubmed_fetch, uniprot_search, geo_search.
            arguments: Tool-specific parameters.

        Returns:
            Tool result as a dict.
        """
        if self.mode == "embedded":
            if self._tools is None:
                await self.connect()

            if self._tools is None:
                raise RuntimeError("Client not connected")

            handler = getattr(self._tools, tool_name, None)
            if handler is None:
                raise ValueError(f"Unknown tool: {tool_name}")

            return await handler(**arguments)

        if self._session is None:
            raise RuntimeError("Client not connected")

        result = await self._session.call_tool(tool_name, arguments)
        content: List[Any] = []
        for item in result.content:
            if hasattr(item, "text"):
                content.append(item.text)
            else:
                content.append(str(item))
        return {
            "content": content,
            "is_error": result.isError or False,
        }

    async def search_pubmed(self, query: str, retmax: int = 10) -> Dict[str, Any]:
        """Convenience method: search PubMed."""
        return await self.call_tool("pubmed_search", {"query": query, "retmax": retmax})

    async def fetch_pubmed(self, pmid: str) -> Dict[str, Any]:
        """Convenience method: fetch PubMed article."""
        return await self.call_tool("pubmed_fetch", {"pmid": pmid})

    async def search_uniprot(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Convenience method: search UniProt."""
        return await self.call_tool("uniprot_search", {"query": query, "limit": limit})

    async def search_geo(self, query: str, retmax: int = 10) -> Dict[str, Any]:
        """Convenience method: search GEO."""
        return await self.call_tool("geo_search", {"query": query, "retmax": retmax})

    async def close(self) -> None:
        """Close any open MCP session."""
        if self._session is not None and hasattr(self._session, "close"):
            await self._session.close()
        self._session = None

        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
