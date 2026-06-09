"""MCP (Model Context Protocol) integration for bioinformatics databases.

Provides tools for querying:
  - NCBI PubMed (literature search)
  - NCBI GEO (gene expression datasets)
  - UniProt (protein information)

Two usage modes:
  1. Direct (embedded): BioDatabaseTools class for in-process calls
  2. MCP protocol: Run `mcp_server.py` as standalone, connect via stdio_client

Example (direct):
    from homomics_lab.mcp import BioDatabaseTools
    tools = BioDatabaseTools()
    results = await tools.pubmed_search("single cell RNA-seq", retmax=5)
"""

from homomics_lab.mcp.client import BioMCPClient
from homomics_lab.mcp.tools import BioDatabaseTools

__all__ = ["BioDatabaseTools", "BioMCPClient"]
