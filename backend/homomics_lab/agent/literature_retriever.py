"""LiteratureRetriever — fetch relevant biomedical literature for planning.

Phase 2 MVP uses NCBI E-utilities for PubMed search. Future versions can add
bioRxiv, Europe PMC, and semantic search over local paper collections.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen


class LiteratureRetriever:
    """Retrieve biomedical literature abstracts/titles for a query."""

    PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self, max_results: int = 5, email: Optional[str] = None):
        self.max_results = max_results
        self.email = email or "homomics@example.com"

    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """Return a list of literature records for the query.

        Falls back to an empty list if the network is unavailable or the
        request fails, so planning never breaks because of PubMed.
        """
        try:
            pmids = self._search_pmids(query)
            if not pmids:
                return []
            return self._summarize_pmids(pmids)
        except Exception:
            return []

    def _search_pmids(self, query: str) -> List[str]:
        """Search PubMed and return a list of PMIDs."""
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": self.max_results,
            "retmode": "json",
            "email": self.email,
        }
        url = f"{self.PUBMED_SEARCH_URL}?{urlencode(params)}"
        with urlopen(url, timeout=15.0) as response:
            data = self._parse_json(response.read())
        return data.get("esearchresult", {}).get("idlist", [])

    def _summarize_pmids(self, pmids: List[str]) -> List[Dict[str, Any]]:
        """Fetch title/source/year for a list of PMIDs."""
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "email": self.email,
        }
        url = f"{self.PUBMED_SUMMARY_URL}?{urlencode(params)}"
        with urlopen(url, timeout=15.0) as response:
            data = self._parse_json(response.read())

        results: List[Dict[str, Any]] = []
        for pmid in pmids:
            summary = data.get("result", {}).get(pmid, {})
            results.append({
                "pmid": pmid,
                "title": summary.get("title", ""),
                "source": summary.get("source", ""),
                "pubdate": summary.get("pubdate", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return results

    @staticmethod
    def _parse_json(raw: bytes) -> Dict[str, Any]:
        import json
        return json.loads(raw.decode("utf-8"))
