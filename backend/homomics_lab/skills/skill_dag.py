"""SkillDAG — self-evolving typed skill graph for skill discovery and relationship querying.

This is NOT the core driver of plan generation. Its role is:
  1. Skill discovery: filter noise from large skill libraries via structured relationships
  2. Conflict detection: warn about redundant or incompatible skill combinations
  3. Alternative recommendation: suggest replacements when a skill fails

The graph evolves at runtime through:
  - manual seed edges (bootstrap)
  - execution-backed edge proposals (followed_by from observed sequences)
  - historical pattern mining (co-occurrence statistics)
  - schema compatibility inference

Edge lifecycle: CANDIDATE → CONFIRMED → DEPRECATED
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import yaml

from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry


class EdgeType(str, Enum):
    """Types of directed edges in the skill graph."""

    DEPENDS_ON = "depends_on"  # hard prerequisite
    CONFLICTS_WITH = "conflicts_with"  # mutually exclusive
    SPECIALIZES = "specializes"  # more specific version
    FOLLOWED_BY = "followed_by"  # soft recommendation (common next step)
    ALTERNATIVE_TO = "alternative_to"  # interchangeable alternative
    PRODUCES = "produces"  # data output relationship for schema inference


class EdgeStatus(str, Enum):
    """Lifecycle status of an edge."""

    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


@dataclass
class SkillDAGEdge:
    """A typed directed edge between two skills."""

    id: str
    from_skill: str
    to_skill: str
    edge_type: EdgeType

    confidence: float = 0.5  # 0.0 ~ 1.0
    status: EdgeStatus = EdgeStatus.CANDIDATE

    source: str = "unknown"  # manual_seed / runtime_proposal / schema_inference / history_mining / community
    proposed_by: Optional[str] = None

    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_validated: Optional[str] = None

    context: str = ""  # human-readable explanation
    schema_compatibility_score: Optional[float] = None

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SkillDAGSearchResult:
    """Result of a structured skill search."""

    skill: SkillDefinition
    semantic_score: float
    graph_boost: float  # bonus from graph relationships
    conflict_warning: Optional[str] = None


class SkillDAG:
    """Self-evolving typed skill graph.

    Core operations:
      - search(): semantic + graph-neighbor retrieval
      - get_conflicts(), get_alternatives(): relationship queries
      - propose_edge(), record_execution(): runtime evolution
      - validate_sequence(): check a skill sequence for conflicts
    """

    def __init__(
        self,
        registry: SkillRegistry,
        db_path: Optional[Path] = None,
        manual_seed_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.db_path = db_path or Path("./skill_dag.db")
        self.edges: Dict[str, SkillDAGEdge] = {}
        self._init_db()
        if manual_seed_path and manual_seed_path.exists():
            self._load_manual_seeds(manual_seed_path)
        self._load_from_db()

    # ─────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────

    def _init_db(self) -> None:
        import sqlite3

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_dag_edges (
                    id TEXT PRIMARY KEY,
                    from_skill TEXT NOT NULL,
                    to_skill TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    status TEXT NOT NULL DEFAULT 'candidate',
                    source TEXT NOT NULL,
                    proposed_by TEXT,
                    execution_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_validated TEXT,
                    context TEXT,
                    schema_compatibility_score REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_from_skill ON skill_dag_edges(from_skill)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_to_skill ON skill_dag_edges(to_skill)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edge_type ON skill_dag_edges(edge_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON skill_dag_edges(status)")
            conn.commit()

    def _load_from_db(self) -> None:
        import sqlite3

        if not self.db_path.exists():
            return
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM skill_dag_edges").fetchall()
            for row in rows:
                edge = SkillDAGEdge(
                    id=row["id"],
                    from_skill=row["from_skill"],
                    to_skill=row["to_skill"],
                    edge_type=EdgeType(row["edge_type"]),
                    confidence=row["confidence"],
                    status=EdgeStatus(row["status"]),
                    source=row["source"],
                    proposed_by=row["proposed_by"],
                    execution_count=row["execution_count"],
                    success_count=row["success_count"],
                    failure_count=row["failure_count"],
                    last_validated=row["last_validated"],
                    context=row["context"] or "",
                    schema_compatibility_score=row["schema_compatibility_score"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                self.edges[edge.id] = edge

    def _persist_edge(self, edge: SkillDAGEdge) -> None:
        import sqlite3

        edge.updated_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO skill_dag_edges
                (id, from_skill, to_skill, edge_type, confidence, status, source,
                 proposed_by, execution_count, success_count, failure_count,
                 last_validated, context, schema_compatibility_score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.from_skill,
                    edge.to_skill,
                    edge.edge_type.value,
                    edge.confidence,
                    edge.status.value,
                    edge.source,
                    edge.proposed_by,
                    edge.execution_count,
                    edge.success_count,
                    edge.failure_count,
                    edge.last_validated,
                    edge.context,
                    edge.schema_compatibility_score,
                    edge.created_at,
                    edge.updated_at,
                ),
            )
            conn.commit()

    def _load_manual_seeds(self, path: Path) -> None:
        """Load CONFIRMED seed edges from YAML."""
        data = yaml.safe_load(path.read_text())
        for seed in data.get("seeds", []):
            self.add_edge(
                from_skill=seed["from"],
                to_skill=seed["to"],
                edge_type=seed["type"],
                context=seed.get("context", ""),
            )

    def add_edge(
        self,
        from_skill: str,
        to_skill: str,
        edge_type: str,
        context: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillDAGEdge:
        """Add or confirm a manual/domain seed edge (idempotent).

        Unlike ``propose_edge`` which creates CANDIDATE runtime proposals,
        ``add_edge`` immediately marks the edge CONFIRMED with full confidence.
        This is the API used by bootstrapping, domain loaders, and manual seeds.
        """
        edge_type_enum = EdgeType(edge_type)
        edge_id = f"{from_skill}_{edge_type_enum.value}_{to_skill}"
        now = datetime.now(timezone.utc).isoformat()

        edge = self.edges.get(edge_id)
        if edge is not None:
            edge.status = EdgeStatus.CONFIRMED
            edge.confidence = max(edge.confidence, 1.0)
            edge.source = "manual_seed"
            if context:
                edge.context = context
            if metadata:
                edge.context = metadata.get("context", edge.context)
            edge.updated_at = now
            self._persist_edge(edge)
            return edge

        edge = SkillDAGEdge(
            id=edge_id,
            from_skill=from_skill,
            to_skill=to_skill,
            edge_type=edge_type_enum,
            confidence=1.0,
            status=EdgeStatus.CONFIRMED,
            source="manual_seed",
            context=context,
            created_at=now,
            updated_at=now,
        )
        if metadata:
            edge.context = metadata.get("context", edge.context)

        self.edges[edge_id] = edge
        self._persist_edge(edge)
        return edge

    # ─────────────────────────────────────────
    # Query interface (for PlanEngine / Agent)
    # ─────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        include_neighbors: bool = True,
        exclude_conflicts: bool = True,
        min_confidence: float = 0.5,
    ) -> List[SkillDAGSearchResult]:
        """Structured skill search: semantic + graph neighbor retrieval.

        Returns skills ranked by semantic relevance boosted by graph relationships.
        """
        # 1. Semantic search through registry
        semantic_results = self.registry.semantic_search(query, top_k=top_k * 2)

        results: List[SkillDAGSearchResult] = []
        seen_skills: set = set()

        for skill, sem_score in semantic_results:
            if skill.id in seen_skills:
                continue
            seen_skills.add(skill.id)

            # Graph boost: confirmed followed_by edges increase score
            graph_boost = 0.0
            conflict_warning = None

            confirmed_edges = self._get_confirmed_edges_from(skill.id, min_confidence)
            for edge in confirmed_edges:
                if edge.edge_type == EdgeType.FOLLOWED_BY:
                    graph_boost += edge.confidence * 0.1

            # Conflict detection
            if exclude_conflicts:
                conflicts = self.get_conflicts(skill.id)
                if conflicts:
                    conflict_warning = f"Conflicts with: {', '.join(conflicts)}"

            results.append(
                SkillDAGSearchResult(
                    skill=skill,
                    semantic_score=sem_score,
                    graph_boost=graph_boost,
                    conflict_warning=conflict_warning,
                )
            )

        # 2. Neighbor expansion (if enabled)
        if include_neighbors:
            neighbors = self._expand_neighbors(semantic_results, hops=1)
            for skill in neighbors:
                if skill.id in seen_skills:
                    continue
                seen_skills.add(skill.id)
                results.append(
                    SkillDAGSearchResult(
                        skill=skill,
                        semantic_score=0.0,
                        graph_boost=0.2,
                    )
                )

        # Sort by combined score
        results.sort(key=lambda r: r.semantic_score + r.graph_boost, reverse=True)
        return results[:top_k]

    def get_conflicts(self, skill_id: str) -> List[str]:
        """Get all skills that conflict with the given skill."""
        return [
            e.to_skill
            for e in self.edges.values()
            if e.from_skill == skill_id
            and e.edge_type == EdgeType.CONFLICTS_WITH
            and e.status == EdgeStatus.CONFIRMED
        ]

    def get_alternatives(self, skill_id: str) -> List[Tuple[str, float]]:
        """Get alternative skills with confidence scores."""
        return [
            (e.to_skill, e.confidence)
            for e in self.edges.values()
            if e.from_skill == skill_id
            and e.edge_type == EdgeType.ALTERNATIVE_TO
            and e.status == EdgeStatus.CONFIRMED
        ]

    def get_followed_by(
        self,
        skill_id: str,
        min_confidence: float = 0.6,
    ) -> List[Tuple[str, float]]:
        """Get recommended next skills (followed_by edges)."""
        return [
            (e.to_skill, e.confidence)
            for e in self.edges.values()
            if e.from_skill == skill_id
            and e.edge_type == EdgeType.FOLLOWED_BY
            and e.status == EdgeStatus.CONFIRMED
            and e.confidence >= min_confidence
        ]

    def get_dependencies(self, skill_id: str) -> List[str]:
        """Get hard prerequisite skills."""
        return [
            e.to_skill
            for e in self.edges.values()
            if e.from_skill == skill_id
            and e.edge_type == EdgeType.DEPENDS_ON
            and e.status == EdgeStatus.CONFIRMED
        ]

    def validate_sequence(self, skill_sequence: List[str]) -> "SequenceValidationResult":
        """Check a skill sequence for conflicts and missing dependencies."""
        errors = []
        warnings = []
        seen = set()

        for i, skill_id in enumerate(skill_sequence):
            # Conflict check
            for seen_skill in seen:
                edge_id = f"{seen_skill}_conflicts_with_{skill_id}"
                if edge_id in self.edges and self.edges[edge_id].status == EdgeStatus.CONFIRMED:
                    errors.append(
                        f"Conflict: '{seen_skill}' and '{skill_id}' should not be used together"
                    )

            # Dependency check
            deps = self.get_dependencies(skill_id)
            for dep in deps:
                if dep not in seen:
                    warnings.append(
                        f"Dependency warning: '{skill_id}' depends on '{dep}' "
                        f"which appears earlier in the sequence"
                    )

            seen.add(skill_id)

        return SequenceValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _get_confirmed_edges_from(
        self,
        skill_id: str,
        min_confidence: float,
    ) -> List[SkillDAGEdge]:
        """Get all confirmed edges originating from a skill."""
        return [
            e
            for e in self.edges.values()
            if e.from_skill == skill_id
            and e.status == EdgeStatus.CONFIRMED
            and e.confidence >= min_confidence
        ]

    def _expand_neighbors(
        self,
        seed_results: List[Tuple[SkillDefinition, float]],
        hops: int = 1,
    ) -> List[SkillDefinition]:
        """Expand search to graph neighbors of top semantic matches."""
        neighbors = []
        for skill, _score in seed_results[:5]:  # top-5 seeds
            for edge in self.edges.values():
                if edge.from_skill == skill.id and edge.status == EdgeStatus.CONFIRMED:
                    neighbor = self.registry.get(edge.to_skill)
                    if neighbor:
                        neighbors.append(neighbor)
        return neighbors

    # ─────────────────────────────────────────
    # Self-evolution interface
    # ─────────────────────────────────────────

    def propose_edge(
        self,
        from_skill: str,
        to_skill: str,
        edge_type: EdgeType,
        context: str = "",
        proposed_by: str = "system",
    ) -> SkillDAGEdge:
        """Propose a new edge. If it already exists, return the existing edge."""
        edge_id = f"{from_skill}_{edge_type.value}_{to_skill}"

        if edge_id in self.edges:
            return self.edges[edge_id]

        edge = SkillDAGEdge(
            id=edge_id,
            from_skill=from_skill,
            to_skill=to_skill,
            edge_type=edge_type,
            confidence=0.3,
            status=EdgeStatus.CANDIDATE,
            source="runtime_proposal",
            proposed_by=proposed_by,
            context=context,
        )
        self.edges[edge_id] = edge
        self._persist_edge(edge)
        return edge

    def record_execution(
        self,
        from_skill: Optional[str],
        to_skill: str,
        success: bool,
    ) -> None:
        """Record an execution observation to evolve edge confidence.

        If from_skill → to_skill was observed, propose or reinforce a followed_by edge.
        """
        if from_skill is None:
            return

        edge_id = f"{from_skill}_{EdgeType.FOLLOWED_BY.value}_{to_skill}"
        edge = self.edges.get(edge_id)

        if edge is None:
            edge = self.propose_edge(
                from_skill=from_skill,
                to_skill=to_skill,
                edge_type=EdgeType.FOLLOWED_BY,
                context=f"Observed in execution flow: success={success}",
            )

        edge.execution_count += 1
        if success:
            edge.success_count += 1
            edge.confidence = min(1.0, edge.confidence + 0.1)
        else:
            edge.failure_count += 1
            edge.confidence = max(0.0, edge.confidence - 0.2)

        edge.last_validated = datetime.now(timezone.utc).isoformat()
        self._transition_status(edge)
        self._persist_edge(edge)

    def _transition_status(self, edge: SkillDAGEdge) -> None:
        """Transition edge status based on confidence and execution stats."""
        if edge.status == EdgeStatus.CANDIDATE:
            min_executions = 5 if edge.edge_type == EdgeType.FOLLOWED_BY else 10
            if (
                edge.execution_count >= min_executions
                and edge.success_count / max(edge.execution_count, 1) >= 0.8
                and edge.confidence >= 0.7
            ):
                edge.status = EdgeStatus.CONFIRMED

        elif edge.status == EdgeStatus.CONFIRMED:
            if edge.execution_count >= 10:
                failure_rate = edge.failure_count / edge.execution_count
                if failure_rate > 0.5 or edge.confidence < 0.3:
                    edge.status = EdgeStatus.DEPRECATED

    # ─────────────────────────────────────────
    # Batch inference from history
    # ─────────────────────────────────────────

    def infer_from_history(
        self,
        execution_records: List[Dict[str, Any]],
        min_cooccurrence: int = 3,
    ) -> List[SkillDAGEdge]:
        """Infer followed_by edges from execution history co-occurrence."""
        from collections import Counter

        sequences = []
        for record in execution_records:
            seq = record.get("skill_sequence", [])
            if len(seq) >= 2:
                sequences.append(seq)

        cooccurrence = Counter()
        for seq in sequences:
            for i in range(len(seq) - 1):
                cooccurrence[(seq[i], seq[i + 1])] += 1

        inferred = []
        for (skill_a, skill_b), count in cooccurrence.most_common(20):
            if count >= min_cooccurrence:
                edge_id = f"{skill_a}_{EdgeType.FOLLOWED_BY.value}_{skill_b}"
                if edge_id not in self.edges:
                    edge = self.propose_edge(
                        from_skill=skill_a,
                        to_skill=skill_b,
                        edge_type=EdgeType.FOLLOWED_BY,
                        context=f"Inferred from {count} historical co-occurrences",
                        proposed_by="history_mining",
                    )
                    edge.confidence = min(0.5 + count * 0.05, 0.9)
                    inferred.append(edge)

        return inferred

    def get_confirmed_edges(
        self,
        min_confidence: float = 0.7,
        limit: int = 200,
    ) -> List[SkillDAGEdge]:
        """Get all confirmed edges above a confidence threshold."""
        edges = [
            e
            for e in self.edges.values()
            if e.status == EdgeStatus.CONFIRMED and e.confidence >= min_confidence
        ]
        edges.sort(key=lambda e: e.confidence, reverse=True)
        return edges[:limit]


@dataclass
class SequenceValidationResult:
    """Result of validating a skill sequence against the DAG."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
