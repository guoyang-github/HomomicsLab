"""SkillDAG edge mining — learn skill relationships from execution history."""

import json
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homomics_lab.knowledge.cbkb import CBKB, SkillEvolutionRecord
from homomics_lab.skills.skill_dag import EdgeStatus, EdgeType, SkillDAG


class SkillDAGMiner:
    """Mine skill transitions from CBKB and evolve the SkillDAG."""

    def __init__(self, cbkb: CBKB, skill_dag: SkillDAG):
        self.cbkb = cbkb
        self.skill_dag = skill_dag

    def mine_edges(
        self,
        since: Optional[str] = None,
        min_cooccurrence: int = 3,
    ) -> Dict[str, Any]:
        """Evolve SkillDAG edges from recent experiment history.

        Returns a summary of changes: proposed, confirmed, deprecated edges.
        """
        nodes = self._recent_experiment_nodes(since)

        # Record every observed adjacent transition.
        transitions = 0
        for node in nodes:
            skills = node.skills_used
            for i in range(len(skills) - 1):
                success = bool(node.metadata.get("success", True))
                self.skill_dag.record_execution(skills[i], skills[i + 1], success)
                transitions += 1

        # Batch infer high-frequency co-occurrence edges.
        records = [
            {"skill_sequence": n.skills_used, "success": n.metadata.get("success", True)}
            for n in nodes
        ]
        inferred = self.skill_dag.infer_from_history(records, min_cooccurrence=min_cooccurrence)

        # Audit log for status transitions.
        changed_edges = []
        for edge in list(self.skill_dag.edges.values()):
            if edge.source in ("runtime_proposal", "history_mining"):
                old_state = self._edge_state_before(edge)
                if edge.status != old_state:
                    self._log_transition(edge, old_state)
                    changed_edges.append(
                        {
                            "edge_id": edge.id,
                            "from_skill": edge.from_skill,
                            "to_skill": edge.to_skill,
                            "edge_type": edge.edge_type.value,
                            "old_state": old_state.value,
                            "new_state": edge.status.value,
                            "confidence": edge.confidence,
                            "execution_count": edge.execution_count,
                        }
                    )

        confirmed = [e for e in changed_edges if e["new_state"] == EdgeStatus.CONFIRMED.value]
        deprecated = [e for e in changed_edges if e["new_state"] == EdgeStatus.DEPRECATED.value]

        return {
            "experiment_nodes_processed": len(nodes),
            "transitions_recorded": transitions,
            "inferred_edges": len(inferred),
            "confirmed_edges": len(confirmed),
            "deprecated_edges": len(deprecated),
            "changed_edges": changed_edges,
        }

    def _recent_experiment_nodes(self, since: Optional[str] = None) -> List[Any]:
        """Pull experiment nodes from CBKB, optionally filtered by date."""
        sql = "SELECT * FROM experiment_nodes"
        params: tuple = ()
        if since:
            sql += " WHERE created_at >= ?"
            params = (since,)
        sql += " ORDER BY created_at DESC"

        with sqlite3.connect(str(self.cbkb.db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()

        from homomics_lab.knowledge.cbkb import ExperimentNode

        return [
            ExperimentNode(
                bundle_id=r[0],
                project_id=r[1],
                created_at=r[2],
                skills_used=json.loads(r[3]),
                phases=json.loads(r[4]),
                summary=r[5] or "",
                metadata=json.loads(r[6]),
            )
            for r in rows
        ]

    @staticmethod
    def _edge_state_before(edge) -> EdgeStatus:
        """Return the state the edge had before this mining pass.

        Since ``record_execution`` already mutated the edge in memory, we
        approximate the previous state from current state:
          - CONFIRMED previously must have been CANDIDATE if source is proposal/mining
          - DEPRECATED previously was CONFIRMED
          - CANDIDATE did not change
        """
        if edge.status == EdgeStatus.CONFIRMED:
            return EdgeStatus.CANDIDATE
        if edge.status == EdgeStatus.DEPRECATED:
            return EdgeStatus.CONFIRMED
        return edge.status

    def _log_transition(self, edge, old_state: EdgeStatus) -> None:
        """Write a SkillEvolutionRecord to CBKB."""
        record = SkillEvolutionRecord(
            id=str(uuid.uuid4().hex),
            from_skill=edge.from_skill,
            to_skill=edge.to_skill,
            edge_type=edge.edge_type.value,
            old_state=old_state.value,
            new_state=edge.status.value,
            trigger=edge.source,
            confidence=edge.confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.cbkb.log_skill_evolution(record)
