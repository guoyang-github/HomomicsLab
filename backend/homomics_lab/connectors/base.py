"""Base types for scientific database connectors.

A ``Connector`` is a thin, stateless adapter over an external scientific
resource (PubMed, Europe PMC, bioRxiv, a generic web index, ...). Connectors
are the unit of extension: adding a new database means implementing this
interface in one file and registering it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConnectorHit:
    """A single normalized search result across any connector."""

    title: str
    source: str
    url: str = ""
    snippet: str = ""
    published: str = ""
    id: str = ""
    authors: List[str] = field(default_factory=list)
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def dedupe_key(self) -> str:
        """Identity used to merge hits across connectors."""
        if self.id:
            return f"id:{self.id.lower()}"
        if self.url:
            return f"url:{self.url.lower()}"
        return f"title:{self.title.strip().lower()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "snippet": self.snippet,
            "published": self.published,
            "id": self.id,
            "authors": self.authors,
            "score": self.score,
        }


class Connector(ABC):
    """Abstract base for a scientific database connector."""

    name: str = "abstract"
    description: str = ""

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[ConnectorHit]:
        """Return up to ``limit`` normalized hits for ``query``."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Whether this connector can run (deps / API keys present)."""
        return True


def first_present(record: Dict[str, Any], *keys: str, default: str = "") -> str:
    """Return the first non-empty string value among ``keys``."""
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default
