"""Generic web connector — wraps the existing DuckDuckGo web search."""

from typing import List

from homomics_lab.connectors.base import Connector, ConnectorHit


class WebConnector(Connector):
    """Generic web search, exposed as a connector for unified querying."""

    name = "web"
    description = "General web search (DuckDuckGo); non-scientific fallback"

    def is_available(self) -> bool:
        try:
            import ddgs  # noqa: F401
        except ImportError:
            return False
        return True

    async def search(self, query: str, limit: int = 5) -> List[ConnectorHit]:
        # Lazy import keeps the connector layer independent of tool wiring.
        from homomics_lab.tools.builtin import web_search

        results = await web_search(query, num_results=limit)
        hits: List[ConnectorHit] = []
        for r in results:
            hits.append(
                ConnectorHit(
                    title=r.get("title", "") or "Untitled",
                    source=self.name,
                    url=r.get("href", "") or r.get("url", ""),
                    snippet=r.get("body", "") or r.get("snippet", ""),
                )
            )
        return hits
