"""EvolutionEngine — orchestrate the self-evolution closed loop."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from homomics_lab.agent.core.registry import RoleRegistry
from homomics_lab.agent.evolution import AgentEvolutionEngine
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.evolution.ingestion import CBKBIngestionService
from homomics_lab.evolution.skill_dag_miner import SkillDAGMiner
from homomics_lab.knowledge.cbkb import CBKB, LabSOP
from homomics_lab.knowledge.curator import CBKBCurator
from homomics_lab.skills.skill_dag import SkillDAG


@dataclass
class EvolutionReport:
    """Summary of a single evolution pass."""

    timestamp: str
    skill_dag_changes: Dict[str, Any] = field(default_factory=dict)
    parameter_preferences: int = 0
    sop_proposals: int = 0
    sops_applied: int = 0
    role_deltas: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "skill_dag_changes": self.skill_dag_changes,
            "parameter_preferences": self.parameter_preferences,
            "sop_proposals": self.sop_proposals,
            "sops_applied": self.sops_applied,
            "role_deltas": self.role_deltas,
            "errors": self.errors,
        }


class EvolutionEngine:
    """Run the self-evolution loop: mine history, learn preferences, update SOPs."""

    def __init__(
        self,
        cbkb: CBKB,
        skill_dag: SkillDAG,
        plan_engine: Optional[PlanEngine] = None,
        role_registry: Optional[RoleRegistry] = None,
    ):
        self.cbkb = cbkb
        self.skill_dag = skill_dag
        self.plan_engine = plan_engine
        self.role_registry = role_registry
        self.ingestion = CBKBIngestionService(cbkb)
        self.miner = SkillDAGMiner(cbkb, skill_dag)
        self.curator = CBKBCurator(cbkb, skill_dag=skill_dag)
        self.agent_evolution = None
        if role_registry is not None and plan_engine is not None:
            self.agent_evolution = AgentEvolutionEngine(cbkb, role_registry, plan_engine)

    def run_evolution_pass(
        self,
        since: Optional[str] = None,
        apply_sops: bool = True,
        sop_confidence_threshold: float = 0.9,
    ) -> EvolutionReport:
        """Execute one full evolution pass and return a report.

        Proposal-only convention (安全门禁，保持现状，勿在不加 HITL 的情况下放宽):

        - Role deltas from ``AgentEvolutionEngine.evolve_roles`` are
          *proposals only* — this pass never calls ``apply_evolution``.
          Applying role changes is a separate, explicitly invoked step.
        - SOP updates are persisted only when their confidence meets
          ``sop_confidence_threshold`` (default 0.9) and the existing SOP is
          not ``locked`` (see ``_apply_sop_update``).
        """
        report = EvolutionReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        try:
            report.skill_dag_changes = self.miner.mine_edges(since=since)
        except Exception as exc:
            report.errors.append(f"SkillDAG mining failed: {exc}")

        if self.agent_evolution is not None:
            try:
                preferences = self.agent_evolution.learn_parameter_preferences()
                report.parameter_preferences = len(preferences)
            except Exception as exc:
                report.errors.append(f"Parameter preference learning failed: {exc}")

            try:
                deltas = self.agent_evolution.evolve_roles()
                report.role_deltas = len(deltas)
            except Exception as exc:
                report.errors.append(f"Role evolution failed: {exc}")

        try:
            sop_updates = self.curator.propose_sop_updates()
            report.sop_proposals = len(sop_updates)
            if apply_sops:
                for update in sop_updates:
                    if update.confidence >= sop_confidence_threshold:
                        applied = self._apply_sop_update(update)
                        if applied:
                            report.sops_applied += 1
        except Exception as exc:
            report.errors.append(f"SOP evolution failed: {exc}")

        return report

    def _apply_sop_update(self, update) -> bool:
        """Persist a high-confidence SOP update to CBKB."""
        template = update.proposed_template
        existing = self.cbkb.get_sop(update.sop_id)
        if existing is not None and existing.locked:
            return False

        now = datetime.now(timezone.utc).isoformat()
        sop = LabSOP(
            id=update.sop_id,
            name=template.get("name", update.sop_id),
            category=template.get("category", "general"),
            template=template.get("template", {}),
            derived_from_bundle_ids=template.get("derived_from_bundle_ids", []),
            version=template.get("version", "1.0"),
            locked=False,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.cbkb.create_sop(sop)
        return True
