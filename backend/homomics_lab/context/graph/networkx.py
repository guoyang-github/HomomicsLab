"""NetworkX-backed graph store for local development and tests."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from homomics_lab.context.graph.base import GraphBackend, GraphEdge, GraphNode

logger = logging.getLogger(__name__)


class NetworkXBackend(GraphBackend):
    """In-memory graph backend that persists to a JSON file."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path
        self._graph = nx.DiGraph()
        self._load()

    async def add_node(
        self,
        node_id: str,
        labels: List[str],
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._graph.add_node(
            node_id,
            labels=labels,
            properties=properties or {},
        )
        self._save()

    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._graph.add_edge(
            from_id,
            to_id,
            type=edge_type,
            properties=properties or {},
        )
        self._save()

    async def get_neighbors(
        self,
        node_id: str,
        edge_types: Optional[List[str]] = None,
        hops: int = 1,
        direction: str = "outgoing",
    ) -> List[GraphNode]:
        if node_id not in self._graph:
            return []

        if direction == "outgoing":
            subgraph = nx.bfs_tree(self._graph, node_id, depth_limit=hops)
        elif direction == "incoming":
            subgraph = nx.bfs_tree(self._graph.reverse(), node_id, depth_limit=hops)
        else:
            undirected = self._graph.to_undirected()
            subgraph = nx.bfs_tree(undirected, node_id, depth_limit=hops)

        neighbor_ids = [n for n in subgraph.nodes() if n != node_id]
        if edge_types:
            neighbor_ids = [
                n
                for n in neighbor_ids
                if any(
                    self._graph.edges[u, v].get("type") in edge_types
                    for u, v in subgraph.in_edges(n)
                )
                or any(
                    self._graph.edges[u, v].get("type") in edge_types
                    for u, v in subgraph.out_edges(n)
                )
            ]
        return [self._node_to_model(n) for n in neighbor_ids]

    async def get_edges(
        self,
        from_id: str,
        edge_type: Optional[str] = None,
    ) -> List[GraphEdge]:
        if from_id not in self._graph:
            return []
        edges = []
        for _, to_id, data in self._graph.out_edges(from_id, data=True):
            if edge_type is None or data.get("type") == edge_type:
                edges.append(
                    GraphEdge(
                        from_id=from_id,
                        to_id=to_id,
                        type=data.get("type", "unknown"),
                        properties=data.get("properties", {}),
                    )
                )
        return edges

    async def search_nodes(
        self,
        query: str,
        labels: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[GraphNode]:
        query_lower = query.lower()
        results = []
        for node_id, data in self._graph.nodes(data=True):
            node_labels = data.get("labels", [])
            if labels and not any(label in node_labels for label in labels):
                continue
            props = data.get("properties", {})
            text = " ".join(str(v) for v in [node_id, *node_labels, *props.values()])
            if query_lower in text.lower():
                results.append(self._node_to_model(node_id))
        return results[:top_k]

    async def close(self) -> None:
        self._save()

    def _node_to_model(self, node_id: str) -> GraphNode:
        data = self._graph.nodes[node_id]
        return GraphNode(
            id=node_id,
            labels=data.get("labels", []),
            properties=data.get("properties", {}),
        )

    def _load(self) -> None:
        if self.storage_path is None or not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self._graph = nx.node_link_graph(data)
        except Exception as exc:
            logger.warning("Failed to load NetworkX graph: %s", exc)
            self._graph = nx.DiGraph()

    def _save(self) -> None:
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self._graph)
        self.storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
