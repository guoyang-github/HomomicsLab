"""Literature connectors — thin wrappers over the existing literature adapters.

Reuses ``agent.literature_retriever`` (PubMed / Europe PMC / bioRxiv) so the
Connector interface adds a unified facade without duplicating network logic.
"""

from typing import Any, Dict, List

from homomics_lab.connectors.base import Connector, ConnectorHit, first_present


def _normalize(record: Dict[str, Any], source: str) -> ConnectorHit:
    authors_raw = record.get("authors")
    if isinstance(authors_raw, list):
        authors = [str(a) for a in authors_raw]
    elif isinstance(authors_raw, str) and authors_raw.strip():
        authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
    else:
        authors = []
    return ConnectorHit(
        title=first_present(record, "title", default="Untitled"),
        source=source,
        url=first_present(record, "url", "link", "href"),
        snippet=first_present(record, "abstract", "snippet", "summary", "description"),
        published=first_present(record, "pubdate", "published", "date", "year"),
        id=first_present(record, "pmid", "doi", "id"),
        authors=authors,
        metadata={k: v for k, v in record.items() if k not in {"abstract"}},
    )


class LiteratureConnector(Connector):
    """Connector backed by an existing ``LiteratureAdapter``."""

    def __init__(self, adapter: Any, description: str = "") -> None:
        self._adapter = adapter
        self.name = adapter.name
        self.description = description or f"Biomedical literature from {adapter.name}"

    def is_available(self) -> bool:
        try:
            import aiohttp  # noqa: F401
        except ImportError:
            return False
        return True

    async def search(self, query: str, limit: int = 5) -> List[ConnectorHit]:
        records = await self._adapter.search(query, limit)
        return [_normalize(r, self.name) for r in records]


def default_literature_connectors() -> List[Connector]:
    """Build the PubMed / Europe PMC / bioRxiv connectors."""
    from homomics_lab.agent.literature_retriever import (
        BioRxivAdapter,
        EuropePMCAdapter,
        PubMedAdapter,
    )

    return [
        LiteratureConnector(PubMedAdapter(), "PubMed biomedical literature (NCBI E-utilities)"),
        LiteratureConnector(EuropePMCAdapter(), "Europe PMC life-science literature"),
        LiteratureConnector(BioRxivAdapter(), "bioRxiv / medRxiv preprints"),
    ]
