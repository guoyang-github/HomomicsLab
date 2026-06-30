"""Abstract graph backend for knowledge graph memory."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GraphNode:
    id: str
    labels: List[str]
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    from_id: str
    to_id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


class GraphBackend(ABC):
    """Pluggable backend for storing and querying typed knowledge graphs."""

    @abstractmethod
    async def add_node(
        self,
        node_id: str,
        labels: List[str],
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add or update a node."""

    @abstractmethod
    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add or update a typed edge."""

    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        edge_types: Optional[List[str]] = None,
        hops: int = 1,
        direction: str = "outgoing",
    ) -> List[GraphNode]:
        """Return neighbor nodes reachable within ``hops`` steps."""

    @abstractmethod
    async def get_edges(
        self,
        from_id: str,
        edge_type: Optional[str] = None,
    ) -> List[GraphEdge]:
        """Return edges originating from ``from_id``."""

    @abstractmethod
    async def search_nodes(
        self,
        query: str,
        labels: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[GraphNode]:
        """Full-text search over node properties."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying connections."""
