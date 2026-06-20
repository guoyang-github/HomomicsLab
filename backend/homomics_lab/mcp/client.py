"""MCP client for bioinformatics databases.

Supports two modes:
  1. Embedded: Direct Python calls (no subprocess, no MCP protocol overhead)
  2. MCP stdio: Connects to an MCP server via stdio for protocol compatibility

Usage (embedded):
    client = BioMCPClient(mode="embedded")
    results = await client.call_tool("pubmed_search", {"query": "scRNA-seq", "retmax": 5})

Usage (MCP protocol):
    client = BioMCPClient(mode="stdio", server_script="mcp_server.py")
    await client.connect()
    results = await client.call_tool("pubmed_search", {"query": "scRNA-seq", "retmax": 5})
"""

from typing import Any, Dict, List, Optional

from homomics_lab.mcp.tools import BioDatabaseTools


class BioMCPClient:
    """Client for bioinformatics MCP tools.

    Mode 'embedded' uses direct Python calls (fastest, no dependencies).
    Mode 'stdio' uses the MCP protocol over stdio (interoperable).
    """

    def __init__(
        self,
        mode: str = "embedded",
        server_script: Optional[str] = None,
        email: Optional[str] = None,
    ):
        self.mode = mode
        self.server_script = server_script
        self.email = email
        self._tools: Optional[BioDatabaseTools] = None
        self._session = None

    async def connect(self) -> None:
        """Initialize the client connection."""
        if self.mode == "embedded":
            self._tools = BioDatabaseTools(email=self.email)
        elif self.mode == "stdio":
            await self._connect_stdio()
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    async def _connect_stdio(self) -> None:
        """Connect to MCP server via stdio (MCP protocol)."""
        # For full MCP stdio support, use mcp.stdio_client
        # This is a placeholder for protocol-mode integration
        raise NotImplementedError(
            "MCP stdio mode requires running the server as a subprocess. "
            "Use 'embedded' mode for direct calls."
        )

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools.

        Returns:
            List of tool descriptors with name, description, and parameters.
        """
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
        if self._tools is None and self.mode == "embedded":
            await self.connect()

        if self._tools is None:
            raise RuntimeError("Client not connected")

        handler = getattr(self._tools, tool_name, None)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        return await handler(**arguments)

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
