"""Bioinformatics database query tools.

Direct implementation of common bioinformatics API queries.
Can be used standalone or wrapped as MCP tools.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


class BioDatabaseTools:
    """Query tools for public bioinformatics databases."""

    NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"

    def __init__(self, email: Optional[str] = None):
        self.email = email or "homomics-lab@example.com"
        self._ncbi_delay = 0.34  # NCBI rate limit: 3 requests/second

    async def pubmed_search(
        self,
        query: str,
        retmax: int = 10,
        sort: str = "relevance",
    ) -> Dict[str, Any]:
        """Search PubMed for articles.

        Args:
            query: Search terms (PubMed syntax supported).
            retmax: Maximum results to return.
            sort: Sort order (relevance, date, etc.).

        Returns:
            Dict with keys: count, webenv, querykey, ids, articles.
        """
        try:
            # Search for IDs
            search_url = (
                f"{self.NCBI_BASE}/esearch.fcgi?db=pubmed&term="
                f"{urllib.parse.quote(query)}&retmax={retmax}&sort={sort}"
                f"&retmode=json&email={self.email}"
            )
            search_data = self._fetch_json(search_url)

            idlist = search_data.get("esearchresult", {}).get("idlist", [])
            count = search_data.get("esearchresult", {}).get("count", "0")

            if not idlist:
                return {
                    "count": count,
                    "ids": [],
                    "articles": [],
                }

            # Fetch summaries
            ids_str = ",".join(idlist)
            summary_url = (
                f"{self.NCBI_BASE}/esummary.fcgi?db=pubmed&id={ids_str}"
                f"&retmode=json&email={self.email}"
            )
            summary_data = self._fetch_json(summary_url)

            articles = []
            for uid in idlist:
                doc = summary_data.get("result", {}).get(uid, {})
                if isinstance(doc, dict):
                    articles.append({
                        "pmid": uid,
                        "title": doc.get("title", ""),
                        "authors": [
                            a.get("name", "") for a in doc.get("authors", [])
                        ],
                        "journal": doc.get("fulljournalname", ""),
                        "pubdate": doc.get("pubdate", ""),
                        "doi": doc.get("elocationid", ""),
                    })

            return {
                "count": count,
                "ids": idlist,
                "articles": articles,
            }

        except Exception as e:
            return {"error": str(e), "count": "0", "ids": [], "articles": []}

    async def pubmed_fetch(self, pmid: str) -> Dict[str, Any]:
        """Fetch full abstract for a PubMed article.

        Args:
            pmid: PubMed ID.

        Returns:
            Dict with title, abstract, authors, journal, etc.
        """
        try:
            url = (
                f"{self.NCBI_BASE}/efetch.fcgi?db=pubmed&id={pmid}"
                f"&rettype=abstract&retmode=text&email={self.email}"
            )
            abstract_text = self._fetch_text(url)

            # Also get structured data
            summary_url = (
                f"{self.NCBI_BASE}/esummary.fcgi?db=pubmed&id={pmid}"
                f"&retmode=json&email={self.email}"
            )
            summary_data = self._fetch_json(summary_url)
            doc = summary_data.get("result", {}).get(pmid, {})

            return {
                "pmid": pmid,
                "title": doc.get("title", ""),
                "abstract": abstract_text,
                "authors": [
                    a.get("name", "") for a in doc.get("authors", [])
                ],
                "journal": doc.get("fulljournalname", ""),
                "pubdate": doc.get("pubdate", ""),
            }

        except Exception as e:
            return {"error": str(e), "pmid": pmid}

    async def uniprot_search(
        self,
        query: str,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Search UniProt for proteins.

        Args:
            query: Protein name, gene, or accession.
            limit: Maximum results.

        Returns:
            Dict with results list.
        """
        try:
            url = (
                f"{self.UNIPROT_BASE}/search?query="
                f"{urllib.parse.quote(query)}&format=json&size={limit}"
            )
            data = self._fetch_json(url)

            results = []
            for entry in data.get("results", []):
                genes = []
                for g in entry.get("genes", []):
                    gene_name = g.get("geneName", {}).get("value", "")
                    if gene_name:
                        genes.append(gene_name)

                results.append({
                    "accession": entry.get("primaryAccession", ""),
                    "id": entry.get("uniProtkbId", ""),
                    "protein_name": entry.get(
                        "proteinDescription", {}
                    ).get("recommendedName", {}).get("fullName", {}).get("value", ""),
                    "genes": genes,
                    "organism": entry.get("organism", {}).get("scientificName", ""),
                    "length": entry.get("sequence", {}).get("length", 0),
                })

            return {
                "count": len(results),
                "results": results,
            }

        except Exception as e:
            return {"error": str(e), "count": 0, "results": []}

    async def geo_search(
        self,
        query: str,
        retmax: int = 10,
    ) -> Dict[str, Any]:
        """Search GEO (Gene Expression Omnibus) for datasets.

        Args:
            query: Search terms.
            retmax: Maximum results.

        Returns:
            Dict with dataset list.
        """
        try:
            search_url = (
                f"{self.NCBI_BASE}/esearch.fcgi?db=gds&term="
                f"{urllib.parse.quote(query)}&retmax={retmax}"
                f"&retmode=json&email={self.email}"
            )
            search_data = self._fetch_json(search_url)

            idlist = search_data.get("esearchresult", {}).get("idlist", [])

            if not idlist:
                return {"count": "0", "datasets": []}

            # Fetch summaries
            ids_str = ",".join(idlist)
            summary_url = (
                f"{self.NCBI_BASE}/esummary.fcgi?db=gds&id={ids_str}"
                f"&retmode=json&email={self.email}"
            )
            summary_data = self._fetch_json(summary_url)

            datasets = []
            for uid in idlist:
                doc = summary_data.get("result", {}).get(uid, {})
                if isinstance(doc, dict):
                    datasets.append({
                        "gds_id": uid,
                        "title": doc.get("title", ""),
                        "summary": doc.get("summary", ""),
                        "organism": doc.get("taxon", ""),
                        "platform": doc.get("gpl", ""),
                        "samples": doc.get("n_samples", ""),
                    })

            return {
                "count": search_data.get("esearchresult", {}).get("count", "0"),
                "datasets": datasets,
            }

        except Exception as e:
            return {"error": str(e), "count": "0", "datasets": []}

    def _fetch_json(self, url: str) -> Dict[str, Any]:
        """Fetch JSON from URL."""
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_text(self, url: str) -> str:
        """Fetch text from URL."""
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
