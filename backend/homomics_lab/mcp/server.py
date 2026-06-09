"""MCP server for bioinformatics databases.

Run as a standalone process for MCP protocol compatibility:
    python -m homomics_lab.mcp.server

Or via stdio for MCP client integration:
    python -m homomics_lab.mcp.server --stdio
"""

from mcp.server.fastmcp import FastMCP
from homomics_lab.mcp.tools import BioDatabaseTools

mcp = FastMCP("homomics-bio")
tools = BioDatabaseTools()


@mcp.tool()
async def pubmed_search(query: str, retmax: int = 10) -> dict:
    """Search PubMed for scientific articles.

    Args:
        query: Search terms using PubMed syntax.
        retmax: Maximum number of results (default 10).

    Returns:
        Dict with count, ids, and articles list.
    """
    return await tools.pubmed_search(query=query, retmax=retmax)


@mcp.tool()
async def pubmed_fetch(pmid: str) -> dict:
    """Fetch article abstract by PubMed ID.

    Args:
        pmid: PubMed identifier (e.g., "12345678").

    Returns:
        Dict with title, abstract, authors, journal, pubdate.
    """
    return await tools.pubmed_fetch(pmid=pmid)


@mcp.tool()
async def uniprot_search(query: str, limit: int = 10) -> dict:
    """Search UniProt for protein information.

    Args:
        query: Protein name, gene symbol, or accession number.
        limit: Maximum results (default 10).

    Returns:
        Dict with count and results list.
    """
    return await tools.uniprot_search(query=query, limit=limit)


@mcp.tool()
async def geo_search(query: str, retmax: int = 10) -> dict:
    """Search GEO for gene expression datasets.

    Args:
        query: Search terms (e.g., "single cell", "tumor", "GSE12345").
        retmax: Maximum results (default 10).

    Returns:
        Dict with count and datasets list.
    """
    return await tools.geo_search(query=query, retmax=retmax)


if __name__ == "__main__":
    mcp.run()
