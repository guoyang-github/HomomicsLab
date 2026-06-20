"""Data lineage tracking for reproducible analysis workflows.

Tracks the provenance of every file in a workspace: which task created it,
from which upstream files, and what transformation was applied.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class LineageNode:
    """A file or data object in the lineage graph."""

    node_id: str
    path: str  # workspace-relative path
    type: str  # "raw" | "intermediate" | "output"
    checksum: str
    created_by_task: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageEdge:
    """A transformation relationship between two lineage nodes."""

    from_node: str  # source artifact_id
    to_node: str  # destination artifact_id
    transform_type: str  # "skill" | "gap_fill" | "manual" | "tool"
    transform_id: str  # task_id or tool_name
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageGraph:
    """A directed graph representing data provenance."""

    nodes: List[LineageNode]
    edges: List[LineageEdge]

    def get_upstream(self, node_id: str) -> List[LineageNode]:
        """Get all upstream nodes for a given node."""
        upstream_ids = {e.from_node for e in self.edges if e.to_node == node_id}
        return [n for n in self.nodes if n.node_id in upstream_ids]

    def get_downstream(self, node_id: str) -> List[LineageNode]:
        """Get all downstream nodes for a given node."""
        downstream_ids = {e.to_node for e in self.edges if e.from_node == node_id}
        return [n for n in self.nodes if n.node_id in downstream_ids]

    def get_roots(self) -> List[LineageNode]:
        """Get all root nodes (no upstream)."""
        has_upstream = {e.to_node for e in self.edges}
        return [n for n in self.nodes if n.node_id not in has_upstream]

    def get_leaves(self) -> List[LineageNode]:
        """Get all leaf nodes (no downstream)."""
        has_downstream = {e.from_node for e in self.edges}
        return [n for n in self.nodes if n.node_id not in has_downstream]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.__dict__ for n in self.nodes],
            "edges": [e.__dict__ for e in self.edges],
        }
