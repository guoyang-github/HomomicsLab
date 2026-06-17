"""Computational Biology Knowledge Base (CBKB).

A domain-specific knowledge system that accumulates structured insights
from reproducible bioinformatics analyses. Unlike general-purpose personal
knowledge bases, CBKB is organized around experiment provenance, parameter
lore, anomaly patterns, lab SOPs, and skill evolution.

Layers:
  1. Experiment Graph — ReproducibilityBundle as atomic nodes with typed edges
  2. Parameter Lore — "key parameter → outcome quality" mappings per skill
  3. Anomaly Archive — Structured record of every phase-level anomaly detected
  4. Lab SOP — Best-practice templates automatically distilled from repeated successes
  5. Skill Evolution Log — History of SkillDAG edge state transitions
"""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────
# Data models
# ─────────────────────────────────────────

@dataclass
class ExperimentNode:
    bundle_id: str
    project_id: str
    created_at: str
    skills_used: List[str]
    phases: List[str]
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentEdge:
    from_bundle: str
    to_bundle: str
    edge_type: str  # "shares_data" | "shares_skill" | "shares_parameter" | "derived_from"
    strength: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParameterLoreEntry:
    id: str
    skill_id: str
    param_name: str
    param_value: str
    outcome_metric: str
    outcome_value: float
    project_id: str
    context: str
    created_at: str


@dataclass
class AnomalyRecord:
    id: str
    project_id: str
    phase_type: str
    summary: str
    flags: List[str]
    recommendations: List[str]
    severity: str  # "info" | "warning" | "critical"
    created_at: str


@dataclass
class LabSOP:
    id: str
    name: str
    category: str
    template: Dict[str, Any]
    derived_from_bundle_ids: List[str]
    version: str = "1.0"
    locked: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass
class SkillEvolutionRecord:
    id: str
    from_skill: str
    to_skill: str
    edge_type: str
    old_state: str
    new_state: str
    trigger: str
    confidence: float
    timestamp: str


# ─────────────────────────────────────────
# CBKB Core
# ─────────────────────────────────────────

class CBKB:
    """Computational Biology Knowledge Base."""

    DB_NAME = "cbkb.db"

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / ".metadata" / self.DB_NAME
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS experiment_nodes (
                    bundle_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    skills_used TEXT NOT NULL,
                    phases TEXT NOT NULL,
                    summary TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_en_project ON experiment_nodes(project_id);
                CREATE INDEX IF NOT EXISTS idx_en_created ON experiment_nodes(created_at);

                CREATE TABLE IF NOT EXISTS experiment_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_bundle TEXT NOT NULL,
                    to_bundle TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    strength REAL DEFAULT 1.0,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(from_bundle, to_bundle, edge_type)
                );
                CREATE INDEX IF NOT EXISTS idx_ee_from ON experiment_edges(from_bundle);
                CREATE INDEX IF NOT EXISTS idx_ee_type ON experiment_edges(edge_type);

                CREATE TABLE IF NOT EXISTS parameter_lore (
                    id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    param_name TEXT NOT NULL,
                    param_value TEXT NOT NULL,
                    outcome_metric TEXT NOT NULL,
                    outcome_value REAL NOT NULL,
                    project_id TEXT NOT NULL,
                    context TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pl_skill ON parameter_lore(skill_id);
                CREATE INDEX IF NOT EXISTS idx_pl_param ON parameter_lore(param_name);

                CREATE TABLE IF NOT EXISTS anomaly_archive (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    phase_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    flags TEXT NOT NULL,
                    recommendations TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_aa_project ON anomaly_archive(project_id);
                CREATE INDEX IF NOT EXISTS idx_aa_phase ON anomaly_archive(phase_type);
                CREATE INDEX IF NOT EXISTS idx_aa_severity ON anomaly_archive(severity);

                CREATE TABLE IF NOT EXISTS lab_sop (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    template TEXT NOT NULL,
                    derived_from_bundle_ids TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '1.0',
                    locked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sop_category ON lab_sop(category);

                CREATE TABLE IF NOT EXISTS skill_evolution_log (
                    id TEXT PRIMARY KEY,
                    from_skill TEXT NOT NULL,
                    to_skill TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    old_state TEXT NOT NULL,
                    new_state TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sel_from ON skill_evolution_log(from_skill);
                CREATE INDEX IF NOT EXISTS idx_sel_to ON skill_evolution_log(to_skill);
            """)

    # ── Layer 1: Experiment Graph ───────────────────

    def add_experiment_node(self, node: ExperimentNode) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO experiment_nodes
                (bundle_id, project_id, created_at, skills_used, phases, summary, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.bundle_id,
                    node.project_id,
                    node.created_at,
                    json.dumps(node.skills_used),
                    json.dumps(node.phases),
                    node.summary,
                    json.dumps(node.metadata),
                ),
            )

    def add_experiment_edge(self, edge: ExperimentEdge) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO experiment_edges
                (from_bundle, to_bundle, edge_type, strength, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    edge.from_bundle,
                    edge.to_bundle,
                    edge.edge_type,
                    edge.strength,
                    json.dumps(edge.metadata),
                ),
            )

    def find_related_experiments(
        self, bundle_id: str, edge_type: Optional[str] = None
    ) -> List[Tuple[str, str, float]]:
        """Return (related_bundle_id, edge_type, strength) tuples."""
        with sqlite3.connect(str(self.db_path)) as conn:
            if edge_type:
                rows = conn.execute(
                    """
                    SELECT to_bundle, edge_type, strength FROM experiment_edges
                    WHERE from_bundle = ? AND edge_type = ?
                    UNION
                    SELECT from_bundle, edge_type, strength FROM experiment_edges
                    WHERE to_bundle = ? AND edge_type = ?
                    """,
                    (bundle_id, edge_type, bundle_id, edge_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT to_bundle, edge_type, strength FROM experiment_edges
                    WHERE from_bundle = ?
                    UNION
                    SELECT from_bundle, edge_type, strength FROM experiment_edges
                    WHERE to_bundle = ?
                    """,
                    (bundle_id, bundle_id),
                ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def get_experiment_node(self, bundle_id: str) -> Optional[ExperimentNode]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT * FROM experiment_nodes WHERE bundle_id = ?", (bundle_id,)
            ).fetchone()
        if row is None:
            return None
        return ExperimentNode(
            bundle_id=row[0],
            project_id=row[1],
            created_at=row[2],
            skills_used=json.loads(row[3]),
            phases=json.loads(row[4]),
            summary=row[5],
            metadata=json.loads(row[6]),
        )

    def list_experiment_nodes_by_project(
        self, project_id: str, limit: int = 10
    ) -> List[ExperimentNode]:
        """Return recent experiment nodes for a given project."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """
                SELECT * FROM experiment_nodes
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [
            ExperimentNode(
                bundle_id=r[0],
                project_id=r[1],
                created_at=r[2],
                skills_used=json.loads(r[3]),
                phases=json.loads(r[4]),
                summary=r[5],
                metadata=json.loads(r[6]),
            )
            for r in rows
        ]

    # ── Layer 2: Parameter Lore ─────────────────────

    def add_parameter_lore(self, entry: ParameterLoreEntry) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO parameter_lore
                (id, skill_id, param_name, param_value, outcome_metric, outcome_value,
                 project_id, context, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.skill_id,
                    entry.param_name,
                    entry.param_value,
                    entry.outcome_metric,
                    entry.outcome_value,
                    entry.project_id,
                    entry.context,
                    entry.created_at,
                ),
            )

    def query_parameter_lore(
        self,
        skill_id: Optional[str] = None,
        param_name: Optional[str] = None,
        min_outcome: Optional[float] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ParameterLoreEntry]:
        conditions = []
        params = []
        if skill_id:
            conditions.append("skill_id = ?")
            params.append(skill_id)
        if param_name:
            conditions.append("param_name = ?")
            params.append(param_name)
        if min_outcome is not None:
            conditions.append("outcome_value >= ?")
            params.append(min_outcome)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM parameter_lore {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            ParameterLoreEntry(
                id=r[0], skill_id=r[1], param_name=r[2], param_value=r[3],
                outcome_metric=r[4], outcome_value=r[5], project_id=r[6],
                context=r[7], created_at=r[8],
            )
            for r in rows
        ]

    # ── Layer 3: Anomaly Archive ────────────────────

    def archive_anomaly(self, record: AnomalyRecord) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO anomaly_archive
                (id, project_id, phase_type, summary, flags, recommendations, severity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.project_id,
                    record.phase_type,
                    record.summary,
                    json.dumps(record.flags),
                    json.dumps(record.recommendations),
                    record.severity,
                    record.created_at,
                ),
            )

    def query_anomalies(
        self,
        phase_type: Optional[str] = None,
        severity: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[AnomalyRecord]:
        conditions = []
        params = []
        if phase_type:
            conditions.append("phase_type = ?")
            params.append(phase_type)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM anomaly_archive {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            AnomalyRecord(
                id=r[0], project_id=r[1], phase_type=r[2], summary=r[3],
                flags=json.loads(r[4]), recommendations=json.loads(r[5]),
                severity=r[6], created_at=r[7],
            )
            for r in rows
        ]

    def get_anomaly_stats(self) -> Dict[str, Any]:
        """Return aggregate anomaly statistics."""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM anomaly_archive").fetchone()[0]
            by_phase = conn.execute(
                "SELECT phase_type, COUNT(*) FROM anomaly_archive GROUP BY phase_type"
            ).fetchall()
            by_severity = conn.execute(
                "SELECT severity, COUNT(*) FROM anomaly_archive GROUP BY severity"
            ).fetchall()
        return {
            "total": total,
            "by_phase": dict(by_phase),
            "by_severity": dict(by_severity),
        }

    # ── Layer 4: Lab SOP ────────────────────────────

    def create_sop(self, sop: LabSOP) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sop.created_at = sop.created_at or now
        sop.updated_at = sop.updated_at or now
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO lab_sop
                (id, name, category, template, derived_from_bundle_ids, version, locked, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sop.id,
                    sop.name,
                    sop.category,
                    json.dumps(sop.template),
                    json.dumps(sop.derived_from_bundle_ids),
                    sop.version,
                    int(sop.locked),
                    sop.created_at,
                    sop.updated_at,
                ),
            )

    def get_sop(self, sop_id: str) -> Optional[LabSOP]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT * FROM lab_sop WHERE id = ?", (sop_id,)
            ).fetchone()
        if row is None:
            return None
        return LabSOP(
            id=row[0],
            name=row[1],
            category=row[2],
            template=json.loads(row[3]),
            derived_from_bundle_ids=json.loads(row[4]),
            version=row[5],
            locked=bool(row[6]),
            created_at=row[7],
            updated_at=row[8],
        )

    def list_sops(self, category: Optional[str] = None) -> List[LabSOP]:
        with sqlite3.connect(str(self.db_path)) as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM lab_sop WHERE category = ? ORDER BY updated_at DESC",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM lab_sop ORDER BY updated_at DESC"
                ).fetchall()
        return [
            LabSOP(
                id=r[0], name=r[1], category=r[2], template=json.loads(r[3]),
                derived_from_bundle_ids=json.loads(r[4]), version=r[5],
                locked=bool(r[6]), created_at=r[7], updated_at=r[8],
            )
            for r in rows
        ]

    # ── Layer 5: Skill Evolution Log ────────────────

    def log_skill_evolution(self, record: SkillEvolutionRecord) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO skill_evolution_log
                (id, from_skill, to_skill, edge_type, old_state, new_state, trigger, confidence, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.from_skill,
                    record.to_skill,
                    record.edge_type,
                    record.old_state,
                    record.new_state,
                    record.trigger,
                    record.confidence,
                    record.timestamp,
                ),
            )

    def get_skill_evolution(
        self, skill_id: Optional[str] = None, limit: int = 100
    ) -> List[SkillEvolutionRecord]:
        with sqlite3.connect(str(self.db_path)) as conn:
            if skill_id:
                rows = conn.execute(
                    """
                    SELECT * FROM skill_evolution_log
                    WHERE from_skill = ? OR to_skill = ?
                    ORDER BY timestamp DESC LIMIT ?
                    """,
                    (skill_id, skill_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skill_evolution_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [
            SkillEvolutionRecord(
                id=r[0], from_skill=r[1], to_skill=r[2], edge_type=r[3],
                old_state=r[4], new_state=r[5], trigger=r[6],
                confidence=r[7], timestamp=r[8],
            )
            for r in rows
        ]

    # ── Cross-layer insights ────────────────────────

    def get_project_summary(self, project_id: str) -> Dict[str, Any]:
        """Aggregate view of everything known about a project."""
        with sqlite3.connect(str(self.db_path)) as conn:
            exp_count = conn.execute(
                "SELECT COUNT(*) FROM experiment_nodes WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            anomaly_count = conn.execute(
                "SELECT COUNT(*) FROM anomaly_archive WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            param_count = conn.execute(
                "SELECT COUNT(*) FROM parameter_lore WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

        return {
            "project_id": project_id,
            "experiments_recorded": exp_count,
            "anomalies_recorded": anomaly_count,
            "parameter_lore_entries": param_count,
        }

    def suggest_parameters(self, skill_id: str) -> List[Dict[str, Any]]:
        """Suggest parameters for a skill based on historical best outcomes."""
        lore = self.query_parameter_lore(skill_id=skill_id, limit=200)
        if not lore:
            return []
        # Simple aggregation: group by (param_name, param_value), compute mean outcome
        from collections import defaultdict
        groups = defaultdict(list)
        for e in lore:
            groups[(e.param_name, e.param_value)].append(e.outcome_value)
        return [
            {"param_name": k[0], "param_value": k[1], "mean_outcome": sum(vs) / len(vs), "samples": len(vs)}
            for k, vs in sorted(groups.items(), key=lambda x: -sum(x[1]) / len(x[1]))
        ]
