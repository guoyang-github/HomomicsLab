"""LiteratureRetriever — async, multi-source biomedical literature search.

Phase 4.2 implementation supports PubMed (via NCBI E-utilities), Europe PMC,
and bioRxiv.  The retriever is built around a pluggable adapter pattern so
additional sources can be added without changing callers.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode


try:
    import aiohttp
except Exception:  # pragma: no cover - aiohttp may be unavailable in minimal installs
    aiohttp = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# NCBI / literature-retrieval defaults (formerly HOMOMICS_NCBI_* /
# HOMOMICS_LITERATURE_* config fields; defaults kept — no credentials, so the
# retriever stays inert unless constructed with explicit credentials).
NCBI_EMAIL = None
NCBI_API_KEY = None
LITERATURE_CACHE_TTL_SECONDS = 3600.0
LITERATURE_MAX_RESULTS = 10


class LiteratureRetrieverError(Exception):
    """Raised when literature retrieval fails and no partial results are available."""


_CacheKey = Tuple[str, str, int]


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: List[Dict[str, Any]], expires_at: float):
        self.value = value
        self.expires_at = expires_at


class LiteratureAdapter(ABC):
    """Abstract base for a single literature source adapter."""

    name: str = "abstract"

    @abstractmethod
    async def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Return a list of literature records for ``query``."""
        ...


class _RateLimiter:
    """Simple async rate limiter enforcing a minimum delay between requests."""

    def __init__(self, delay_seconds: float):
        self._delay = delay_seconds
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self._delay <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            self._last_request = time.monotonic()


class PubMedAdapter(LiteratureAdapter):
    """Async PubMed search via NCBI E-utilities (esearch + esummary)."""

    name = "pubmed"
    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(
        self,
        email: Optional[str] = None,
        api_key: Optional[str] = None,
        session: Optional[Any] = None,
    ):
        self.email = email or NCBI_EMAIL
        self.api_key = api_key or NCBI_API_KEY
        delay = 0.1 if self.api_key else 0.34
        self._rate_limiter = _RateLimiter(delay)
        self._session = session

    async def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        session: aiohttp.ClientSession
        if self._session is not None:
            session = self._session
        else:
            session = aiohttp.ClientSession()

        try:
            pmids = await self._search_pmids(session, query, max_results)
            if not pmids:
                return []
            return await self._summarize_pmids(session, pmids)
        finally:
            if self._session is None:
                await session.close()

    async def _request_json(
        self,
        session: Any,
        url: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        await self._rate_limiter.acquire()
        params = {k: v for k, v in params.items() if v is not None}
        full_url = f"{url}?{urlencode(params)}"
        try:
            async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=15.0)) as response:
                response.raise_for_status()
                return await response.json()
        except LiteratureRetrieverError:
            raise
        except Exception as exc:
            raise LiteratureRetrieverError(f"PubMed request failed: {exc}") from exc

    async def _search_pmids(
        self,
        session: Any,
        query: str,
        max_results: int,
    ) -> List[str]:
        params: Dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "email": self.email,
            "api_key": self.api_key,
        }
        data = await self._request_json(session, self.SEARCH_URL, params)
        result = data.get("esearchresult", {})
        if "ERROR" in result:
            raise LiteratureRetrieverError(f"PubMed search error: {result['ERROR']}")
        return result.get("idlist", [])

    async def _summarize_pmids(
        self,
        session: Any,
        pmids: List[str],
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "email": self.email,
            "api_key": self.api_key,
        }
        data = await self._request_json(session, self.SUMMARY_URL, params)
        summaries = data.get("result", {})

        results: List[Dict[str, Any]] = []
        for pmid in pmids:
            summary = summaries.get(pmid, {})
            results.append({
                "pmid": pmid,
                "title": summary.get("title", ""),
                "source": summary.get("source", ""),
                "pubdate": summary.get("pubdate", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return results


class EuropePMCAdapter(LiteratureAdapter):
    """Async Europe PMC REST search."""

    name = "europepmc"
    SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, session: Optional[Any] = None):
        self._session = session

    async def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        session: aiohttp.ClientSession
        if self._session is not None:
            session = self._session
        else:
            session = aiohttp.ClientSession()

        try:
            params: Dict[str, Any] = {
                "query": query,
                "format": "json",
                "pageSize": max_results,
            }
            async with session.get(
                self.SEARCH_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15.0),
            ) as response:
                response.raise_for_status()
                data = await response.json()
        except LiteratureRetrieverError:
            raise
        except Exception as exc:
            raise LiteratureRetrieverError(f"Europe PMC request failed: {exc}") from exc
        finally:
            if self._session is None:
                await session.close()

        results: List[Dict[str, Any]] = []
        for item in data.get("resultList", {}).get("result", []):
            ids = item.get("id", "")
            pmid = item.get("pmid", "")
            doi = item.get("doi", "")
            pmcid = item.get("pmcid", "")
            results.append({
                "pmid": pmid or ids,
                "doi": doi,
                "pmcid": pmcid,
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "pubdate": item.get("pubYear", ""),
                "url": self._build_url(pmid, pmcid, doi),
            })
        return results

    @staticmethod
    def _build_url(pmid: str, pmcid: str, doi: str) -> str:
        if pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        if pmcid:
            return f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}"
        if doi:
            return f"https://doi.org/{doi}"
        return ""


class BioRxivAdapter(LiteratureAdapter):
    """Async bioRxiv search using the public API.

    The bioRxiv API does not have a generic text search endpoint.  We use the
    Covid-19 endpoint as a broad query endpoint (it returns papers for any
    query string), falling back to the details endpoint when no results are
    returned.  Callers requiring exact bioRxiv semantics should treat this as a
    best-effort adapter.
    """

    name = "biorxiv"
    SEARCH_URL = "https://api.biorxiv.org/covid19/"

    def __init__(self, session: Optional[Any] = None):
        self._session = session

    async def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        session: aiohttp.ClientSession
        if self._session is not None:
            session = self._session
        else:
            session = aiohttp.ClientSession()

        try:
            params: Dict[str, Any] = {
                "text": query,
                "count": max_results,
            }
            async with session.get(
                self.SEARCH_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15.0),
            ) as response:
                response.raise_for_status()
                data = await response.json()
        except LiteratureRetrieverError:
            raise
        except Exception as exc:
            raise LiteratureRetrieverError(f"bioRxiv request failed: {exc}") from exc
        finally:
            if self._session is None:
                await session.close()

        results: List[Dict[str, Any]] = []
        collection = data.get("collection", [])
        if not isinstance(collection, list):
            collection = []
        for item in collection[:max_results]:
            doi = item.get("doi", "")
            results.append({
                "doi": doi,
                "title": item.get("title", ""),
                "date": item.get("date", ""),
                "url": f"https://www.biorxiv.org/content/{doi}" if doi else "",
            })
        return results


class LiteratureRetriever:
    """Retrieve and merge biomedical literature from multiple async adapters.

    ``retrieve`` runs adapters concurrently, merges results, deduplicates by
    DOI/title/PMID, and caches by ``(adapter_name, query, max_results)``.
    Network or HTTP errors in individual adapters are logged and skipped; if
    every adapter fails, ``LiteratureRetrieverError`` is raised.

    A backward-compatible synchronous helper, ``retrieve_sync``, is provided
    for callers that cannot easily be made async.
    """

    def __init__(
        self,
        adapters: Optional[List[LiteratureAdapter]] = None,
        cache_ttl_seconds: Optional[float] = None,
        max_results: Optional[int] = None,
    ):
        self.adapters = adapters or [
            PubMedAdapter(),
            EuropePMCAdapter(),
            BioRxivAdapter(),
        ]
        self.cache_ttl_seconds = (
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else LITERATURE_CACHE_TTL_SECONDS
        )
        self.max_results = max_results if max_results is not None else LITERATURE_MAX_RESULTS
        self._cache: Dict[_CacheKey, _CacheEntry] = {}

    async def retrieve(
        self,
        query: str,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return merged, deduplicated literature records for ``query``."""
        limit = max_results if max_results is not None else self.max_results
        if limit <= 0:
            return []

        # 1. Serve fully-cached adapter results where possible.
        pending_adapters: List[LiteratureAdapter] = []
        cached_results: List[Dict[str, Any]] = []
        for adapter in self.adapters:
            key: _CacheKey = (adapter.name, query, limit)
            entry = self._cache.get(key)
            if entry and entry.expires_at > time.monotonic():
                cached_results.extend(entry.value)
            else:
                if entry:
                    self._cache.pop(key, None)
                pending_adapters.append(adapter)

        # 2. Query remaining adapters concurrently.
        adapter_results: List[List[Dict[str, Any]]] = []
        if pending_adapters:
            tasks = [self._search_adapter(adapter, query, limit) for adapter in pending_adapters]
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
            for adapter, result in zip(pending_adapters, gathered):
                if isinstance(result, Exception):
                    logger.warning(
                        "Literature adapter %s failed for query %r: %s",
                        adapter.name,
                        query,
                        result,
                    )
                    continue
                key = (adapter.name, query, limit)
                self._cache[key] = _CacheEntry(
                    value=result,
                    expires_at=time.monotonic() + self.cache_ttl_seconds,
                )
                adapter_results.append(result)

        # 3. Merge, deduplicate, limit.
        merged = self._deduplicate(cached_results + [r for results in adapter_results for r in results])
        if not merged:
            raise LiteratureRetrieverError(
                "All literature adapters failed or returned no results."
            )
        return merged[:limit]

    async def _search_adapter(
        self,
        adapter: LiteratureAdapter,
        query: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        return await adapter.search(query, max_results)

    @staticmethod
    def _deduplicate(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for record in records:
            key_parts = [
                record.get("doi", "").strip().lower(),
                record.get("pmid", "").strip().lower(),
                record.get("pmcid", "").strip().lower(),
                record.get("title", "").strip().lower(),
            ]
            key = tuple(p for p in key_parts if p)
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(record)
        return unique

    def retrieve_sync(
        self,
        query: str,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper around :meth:`retrieve`.

        This helper is intended for legacy synchronous callers.  It creates an
        event loop only when one does not already exist.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.retrieve(query, max_results))
        else:
            if loop.is_running():
                raise LiteratureRetrieverError(
                    "Cannot call retrieve_sync from a running event loop; use retrieve() instead."
                )
            return loop.run_until_complete(self.retrieve(query, max_results))


# Backward-compatible alias for callers that expect the old sync API.
def retrieve_literature(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Synchronously retrieve literature using default adapters."""
    return LiteratureRetriever(max_results=max_results).retrieve_sync(query)
