"""Cold-start baseline seeding for CBKB and SkillDAG (P2-2).

Fresh deployments have no execution history, so CBKB experiment nodes and
SkillDAG CONFIRMED edges — the substrate of the self-evolution loop — start
completely empty. This module broadcasts a set of pre-computed benchmark
records (``benchmarks/seed_baselines.yaml``) into both stores so that a new
deployment has a non-empty self-evolution baseline out of the box.

Isolation guarantees:
  - experiment nodes use ``project_id="system"`` and ``seed_``-prefixed
    bundle ids, with ``metadata["source"] == "seed"`` — they never touch
    real user projects;
  - skill edges are seeded through the public
    ``propose_edge`` + ``record_observation(success=True)`` path with
    ``proposed_by="seed"`` and are skipped once CONFIRMED, so re-seeding is
    idempotent (``force=True`` re-broadcasts on demand).
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from homomics_lab.knowledge.cbkb import CBKB, ExperimentEdge, ExperimentNode
from homomics_lab.skills.skill_dag import EdgeStatus, EdgeType, SkillDAG

logger = logging.getLogger(__name__)

#: Project id used for all seeded experiment nodes — never a real user project.
SEED_PROJECT_ID = "system"

#: proposed_by marker on seeded SkillDAG edges.
SEED_PROPOSED_BY = "seed"

#: Path to the bundled declarative seed data.
DEFAULT_SEED_PATH = Path(__file__).parent.parent / "benchmarks" / "seed_baselines.yaml"

#: Successful observations recorded per seed edge. FOLLOWED_BY edges are
#: promoted to CONFIRMED at execution_count >= 5 with success rate >= 0.8 and
#: confidence >= 0.7 (see SkillDAG._transition_status); a proposed edge starts
#: at confidence 0.3 and gains +0.1 per success, so exactly 5 successes reach
#: confidence 0.8 and promote the edge.
SEED_EDGE_SUCCESSES = 5


def load_seed_data(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load declarative seed data from YAML (defaults to the bundled file)."""
    seed_path = Path(path) if path is not None else DEFAULT_SEED_PATH
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Seed data must be a YAML mapping: {seed_path}")
    data.setdefault("experiments", [])
    data.setdefault("experiment_edges", [])
    data.setdefault("skill_edges", [])
    return data


def seed_baselines(
    cbkb: CBKB,
    skill_dag: SkillDAG,
    data: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> Dict[str, int]:
    """Broadcast seed records into CBKB and SkillDAG.

    Idempotent by default: existing experiment nodes (same bundle_id) and
    already-CONFIRMED seed edges are skipped. ``force=True`` re-broadcasts
    everything.

    Returns a report dict with keys ``experiments_added``,
    ``experiment_edges_added``, ``skill_edges_confirmed`` and ``skipped``.
    """
    if data is None:
        data = load_seed_data()

    report = {
        "experiments_added": 0,
        "experiment_edges_added": 0,
        "skill_edges_confirmed": 0,
        "skipped": 0,
    }

    # ── Experiment nodes ──────────────────────────────
    for record in data.get("experiments", []):
        bundle_id = record["bundle_id"]
        if not force and cbkb.get_experiment_node(bundle_id) is not None:
            report["skipped"] += 1
            continue
        metadata = dict(record.get("metadata") or {})
        metadata.setdefault("source", "seed")
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id=bundle_id,
                project_id=record.get("project_id", SEED_PROJECT_ID),
                created_at=record.get("created_at", ""),
                skills_used=list(record.get("skills_used", [])),
                phases=list(record.get("phases", [])),
                summary=record.get("summary", ""),
                metadata=metadata,
            )
        )
        report["experiments_added"] += 1

    # ── Experiment edges ──────────────────────────────
    for record in data.get("experiment_edges", []):
        from_bundle = record["from_bundle"]
        to_bundle = record["to_bundle"]
        edge_type = record.get("edge_type", "shares_skill")
        already_linked = any(
            related == to_bundle
            for related, _, _ in cbkb.find_related_experiments(from_bundle, edge_type)
        )
        if not force and already_linked:
            report["skipped"] += 1
            continue
        metadata = dict(record.get("metadata") or {})
        metadata.setdefault("source", "seed")
        cbkb.add_experiment_edge(
            ExperimentEdge(
                from_bundle=from_bundle,
                to_bundle=to_bundle,
                edge_type=edge_type,
                strength=float(record.get("strength", 1.0)),
                metadata=metadata,
            )
        )
        report["experiment_edges_added"] += 1

    # ── SkillDAG edges ────────────────────────────────
    for record in data.get("skill_edges", []):
        from_skill = record["from"]
        to_skill = record["to"]
        edge_type = EdgeType(record.get("edge_type", EdgeType.FOLLOWED_BY.value))
        context = record.get("context", "")
        edge_id = f"{from_skill}_{edge_type.value}_{to_skill}"

        existing = skill_dag.edges.get(edge_id)
        if (
            not force
            and existing is not None
            and existing.status == EdgeStatus.CONFIRMED
            and existing.proposed_by == SEED_PROPOSED_BY
        ):
            report["skipped"] += 1
            continue

        skill_dag.propose_edge(
            from_skill=from_skill,
            to_skill=to_skill,
            edge_type=edge_type,
            context=context,
            proposed_by=SEED_PROPOSED_BY,
        )
        for _ in range(SEED_EDGE_SUCCESSES):
            edge = skill_dag.record_observation(
                from_skill, to_skill, edge_type, success=True, context=context
            )
        if edge.status == EdgeStatus.CONFIRMED:
            report["skill_edges_confirmed"] += 1

    logger.info("Seed baselines broadcast complete: %s", report)
    return report


def is_store_empty(cbkb: CBKB, skill_dag: SkillDAG) -> bool:
    """Return True when neither store has any self-evolution substrate yet.

    "Empty" means: CBKB has zero experiment nodes (any project) and SkillDAG
    has zero CONFIRMED edges. CBKB exposes no count API, so the experiment
    node count is read directly from its SQLite store.
    """
    with sqlite3.connect(str(cbkb.db_path)) as conn:
        node_count = conn.execute("SELECT COUNT(*) FROM experiment_nodes").fetchone()[0]
    if node_count > 0:
        return False
    return not any(e.status == EdgeStatus.CONFIRMED for e in skill_dag.edges.values())
