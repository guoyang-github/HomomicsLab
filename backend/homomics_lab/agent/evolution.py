"""AgentEvolutionEngine — learns from CBKB history to evolve roles, plans, and SOPs."""

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.agent.core.registry import RoleRegistry
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.knowledge.cbkb import CBKB, ExperimentNode, LabSOP, ParameterLoreEntry


@dataclass
class RoleDelta:
    """Proposed change to a role definition."""

    role_id: str
    field_changed: str
    old_value: Any
    new_value: Any
    confidence: float
    reason: str


@dataclass
class PlanPattern:
    """A recurring successful plan pattern mined from ExperimentGraph."""

    pattern_name: str
    strategy_type: str
    typical_phases: List[str]
    success_rate: float
    avg_duration_min: float
    extracted_from_n_bundles: int


@dataclass
class ParameterPreference:
    """A statistically preferred parameter value learned from ParameterLore."""

    skill_id: str
    param_name: str
    preferred_value: str
    preference_strength: float
    sample_count: int
    project_ids: List[str]


@dataclass
class SOPUpdate:
    """Proposed change to a LabSOP."""

    sop_id: str
    proposed_changes: Dict[str, Any]
    confidence: float
    derived_from_bundles: List[str]


class AgentEvolutionEngine:
    """Analyzes CBKB execution history and proposes evolutionary updates.

    The engine is intentionally simple — it uses mean comparisons and
    frequency thresholds rather than complex ML so that every proposal
    is auditable and explainable.
    """

    def __init__(self, cbkb: CBKB, role_registry: RoleRegistry, plan_engine: PlanEngine):
        self.cbkb = cbkb
        self.role_registry = role_registry
        self.plan_engine = plan_engine

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _list_experiment_nodes(self) -> List[ExperimentNode]:
        """Return all experiment nodes from CBKB."""
        with sqlite3.connect(str(self.cbkb.db_path)) as conn:
            rows = conn.execute(
                "SELECT bundle_id, project_id, created_at, skills_used, phases, summary, metadata "
                "FROM experiment_nodes"
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

    def _list_parameter_lore(self, skill_id: Optional[str] = None) -> List[ParameterLoreEntry]:
        """Return all parameter lore entries (bypassing the default query limit)."""
        with sqlite3.connect(str(self.cbkb.db_path)) as conn:
            if skill_id:
                rows = conn.execute(
                    "SELECT * FROM parameter_lore WHERE skill_id = ? ORDER BY created_at DESC",
                    (skill_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM parameter_lore ORDER BY created_at DESC").fetchall()
        return [
            ParameterLoreEntry(
                id=r[0],
                skill_id=r[1],
                param_name=r[2],
                param_value=r[3],
                outcome_metric=r[4],
                outcome_value=r[5],
                project_id=r[6],
                context=r[7],
                created_at=r[8],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # evolve_roles
    # ------------------------------------------------------------------

    def evolve_roles(self) -> List[RoleDelta]:
        """Analyze CBKB per role and propose role updates.

        Two heuristics are applied:
        1. Parameter dominance — if one parameter value consistently produces
           the best mean outcome and represents >70 % of samples, propose
           embedding it in the role metadata.
        2. Skill failure — if a skill's average outcome is very low,
           propose lowering the role's priority or adding the skill to
           ``blocked_skills``.
        """
        deltas: List[RoleDelta] = []

        for role in self.role_registry.list_all():
            skills_to_check = (
                role.allowed_skills
                if role.allowed_skills
                else list({entry.skill_id for entry in self._list_parameter_lore()})
            )

            for skill_id in skills_to_check:
                lore = self._list_parameter_lore(skill_id=skill_id)
                if len(lore) < 3:
                    continue

                # ---- heuristic 1: parameter dominance ----
                by_param: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
                for entry in lore:
                    by_param[entry.param_name][entry.param_value].append(entry.outcome_value)

                for param_name, value_groups in by_param.items():
                    if len(value_groups) < 2:
                        continue

                    total_samples = sum(len(vs) for vs in value_groups.values())
                    if total_samples < 3:
                        continue

                    means = {val: sum(vs) / len(vs) for val, vs in value_groups.items()}
                    best_value = max(means, key=lambda k: means[k])
                    best_samples = len(value_groups[best_value])
                    best_ratio = best_samples / total_samples

                    # Best value must dominate (>70 %) *and* beat every alternative
                    second_best = max(
                        (means[v] for v in means if v != best_value),
                        default=0.0,
                    )
                    if best_ratio > 0.70 and means[best_value] > second_best:
                        old_meta = dict(role.metadata)
                        new_meta = dict(old_meta)
                        pref_key = f"preferred_param_{skill_id}_{param_name}"
                        if old_meta.get(pref_key) != best_value:
                            new_meta[pref_key] = best_value
                            deltas.append(
                                RoleDelta(
                                    role_id=role.role_id,
                                    field_changed="metadata",
                                    old_value=old_meta,
                                    new_value=new_meta,
                                    confidence=round(best_ratio, 2),
                                    reason=(
                                        f"Parameter '{param_name}={best_value}' for skill "
                                        f"'{skill_id}' has best mean outcome "
                                        f"({means[best_value]:.2f}) in {best_ratio:.0%} of "
                                        f"{total_samples} samples."
                                    ),
                                )
                            )

                # ---- heuristic 2: skill failure ----
                all_outcomes = [e.outcome_value for e in lore]
                avg_outcome = sum(all_outcomes) / len(all_outcomes)
                if avg_outcome < 0.3 and len(all_outcomes) >= 3:
                    new_priority = min(role.priority + 20, 500)
                    if new_priority != role.priority:
                        deltas.append(
                            RoleDelta(
                                role_id=role.role_id,
                                field_changed="priority",
                                old_value=role.priority,
                                new_value=new_priority,
                                confidence=0.75,
                                reason=(
                                    f"Skill '{skill_id}' shows low average outcome "
                                    f"({avg_outcome:.2f}) over {len(all_outcomes)} runs; "
                                    f"lower role priority."
                                ),
                            )
                        )
                    if avg_outcome < 0.15 and skill_id not in role.blocked_skills:
                        new_blocked = list(role.blocked_skills) + [skill_id]
                        deltas.append(
                            RoleDelta(
                                role_id=role.role_id,
                                field_changed="blocked_skills",
                                old_value=list(role.blocked_skills),
                                new_value=new_blocked,
                                confidence=0.80,
                                reason=(
                                    f"Skill '{skill_id}' consistently fails "
                                    f"(avg outcome {avg_outcome:.2f}); propose blocking."
                                ),
                            )
                        )

        return deltas

    # ------------------------------------------------------------------
    # mine_plan_patterns
    # ------------------------------------------------------------------

    def mine_plan_patterns(self) -> List[PlanPattern]:
        """Mine successful plan patterns from the ExperimentGraph.

        Groups experiment nodes by ``metadata.strategy_type``, counts
        phase-sequence frequencies, and returns patterns that appear at
        least twice with associated success-rate and duration statistics.
        """
        nodes = self._list_experiment_nodes()
        if not nodes:
            return []

        by_strategy: Dict[str, List[ExperimentNode]] = defaultdict(list)
        for node in nodes:
            strategy = node.metadata.get("strategy_type", "unknown")
            by_strategy[strategy].append(node)

        patterns: List[PlanPattern] = []

        for strategy, strategy_nodes in by_strategy.items():
            if len(strategy_nodes) < 2:
                continue

            seq_counts: Dict[Tuple[str, ...], List[ExperimentNode]] = defaultdict(list)
            for node in strategy_nodes:
                seq = tuple(node.phases)
                if seq:
                    seq_counts[seq].append(node)

            for seq, seq_nodes in seq_counts.items():
                if len(seq_nodes) < 2:
                    continue

                successful = [n for n in seq_nodes if n.metadata.get("success", True)]
                success_rate = len(successful) / len(seq_nodes) if seq_nodes else 0.0

                durations = [
                    n.metadata.get("duration_min", 0.0)
                    for n in seq_nodes
                    if isinstance(n.metadata.get("duration_min"), (int, float))
                ]
                avg_duration = sum(durations) / len(durations) if durations else 0.0

                patterns.append(
                    PlanPattern(
                        pattern_name=f"{strategy}_pattern_{'_'.join(seq)}",
                        strategy_type=strategy,
                        typical_phases=list(seq),
                        success_rate=round(success_rate, 2),
                        avg_duration_min=round(avg_duration, 1),
                        extracted_from_n_bundles=len(seq_nodes),
                    )
                )

        patterns.sort(key=lambda p: (-p.success_rate, -p.extracted_from_n_bundles))
        return patterns

    # ------------------------------------------------------------------
    # learn_parameter_preferences
    # ------------------------------------------------------------------

    def learn_parameter_preferences(self, project_id: Optional[str] = None) -> List[ParameterPreference]:
        """Aggregate ParameterLore and return statistically preferred values.

        Preference strength is expressed as the number of standard
        deviations the best mean outcome sits above the mean of *all*
        candidate-value means for that parameter.
        """
        lore = self._list_parameter_lore()
        if project_id:
            lore = [e for e in lore if e.project_id == project_id]

        # Group by (skill_id, param_name) -> {param_value: [outcomes]}
        by_skill_param: Dict[Tuple[str, str], Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for entry in lore:
            by_skill_param[(entry.skill_id, entry.param_name)][entry.param_value].append(
                entry.outcome_value
            )

        preferences: List[ParameterPreference] = []

        for (skill_id, param_name), value_outcomes in by_skill_param.items():
            if len(value_outcomes) < 2:
                continue

            means = {val: sum(vs) / len(vs) for val, vs in value_outcomes.items()}
            best_value = max(means, key=lambda k: means[k])
            best_mean = means[best_value]
            best_samples = len(value_outcomes[best_value])

            all_means = list(means.values())
            mean_of_means = sum(all_means) / len(all_means)
            if len(all_means) > 1:
                variance = sum((m - mean_of_means) ** 2 for m in all_means) / len(all_means)
                std = variance ** 0.5
            else:
                std = 0.0

            preference_strength = (best_mean - mean_of_means) / (std + 1e-6)
            if preference_strength <= 0.1:
                continue

            project_ids = sorted(
                {
                    e.project_id
                    for e in lore
                    if e.skill_id == skill_id
                    and e.param_name == param_name
                    and e.param_value == best_value
                }
            )

            preferences.append(
                ParameterPreference(
                    skill_id=skill_id,
                    param_name=param_name,
                    preferred_value=best_value,
                    preference_strength=round(preference_strength, 2),
                    sample_count=best_samples,
                    project_ids=project_ids,
                )
            )

        preferences.sort(key=lambda p: -p.preference_strength)
        return preferences

    # ------------------------------------------------------------------
    # auto_update_sops
    # ------------------------------------------------------------------

    def auto_update_sops(self) -> List[SOPUpdate]:
        """Find repeated successful analysis patterns and propose SOP changes.

        A pattern must repeat at least 3 times with ``metadata.success``
        to be considered. Existing SOPs are updated with a version bump;
        novel patterns trigger a proposal for a new auto-SOP.
        """
        nodes = self._list_experiment_nodes()
        if not nodes:
            return []

        pattern_groups: Dict[Tuple[str, str], List[ExperimentNode]] = defaultdict(list)
        for node in nodes:
            if not node.phases:
                continue
            phases_key = ",".join(node.phases)
            skills_key = ",".join(node.skills_used)
            pattern_groups[(phases_key, skills_key)].append(node)

        updates: List[SOPUpdate] = []

        for (phases_key, skills_key), group in pattern_groups.items():
            successful = [n for n in group if n.metadata.get("success", True)]
            if len(successful) < 3:
                continue

            confidence = len(successful) / len(group) if group else 0.0
            bundle_ids = [n.bundle_id for n in successful]

            # Look for an existing SOP with matching phase template
            existing_sops = self.cbkb.list_sops()
            matching_sop: Optional[LabSOP] = None
            for sop in existing_sops:
                sop_phases = ",".join(sop.template.get("phases", []))
                if sop_phases == phases_key:
                    matching_sop = sop
                    break

            if matching_sop is not None:
                version_parts = matching_sop.version.split(".")
                try:
                    major = int(version_parts[0])
                    new_version = f"{major + 1}.0"
                except ValueError:
                    new_version = matching_sop.version

                updates.append(
                    SOPUpdate(
                        sop_id=matching_sop.id,
                        proposed_changes={
                            "version": new_version,
                            "template": {
                                **matching_sop.template,
                                "phases": phases_key.split(","),
                                "skills_used": skills_key.split(",") if skills_key else [],
                                "success_rate": round(confidence, 2),
                            },
                            "derived_from_bundle_ids": list(
                                set(matching_sop.derived_from_bundle_ids + bundle_ids)
                            ),
                        },
                        confidence=round(confidence, 2),
                        derived_from_bundles=bundle_ids,
                    )
                )
            else:
                sop_id = f"sop_auto_{phases_key.replace(',', '_')}"
                updates.append(
                    SOPUpdate(
                        sop_id=sop_id,
                        proposed_changes={
                            "name": f"Auto SOP: {phases_key}",
                            "category": successful[0].metadata.get("strategy_type", "general"),
                            "template": {
                                "phases": phases_key.split(","),
                                "skills_used": skills_key.split(",") if skills_key else [],
                                "success_rate": round(confidence, 2),
                            },
                            "derived_from_bundle_ids": bundle_ids,
                            "version": "1.0",
                        },
                        confidence=round(confidence, 2),
                        derived_from_bundles=bundle_ids,
                    )
                )

        return updates

    # ------------------------------------------------------------------
    # apply_evolution
    # ------------------------------------------------------------------

    def apply_evolution(self, deltas: List[RoleDelta]) -> int:
        """Apply proposed ``RoleDelta`` objects to the ``RoleRegistry``.

        Only roles that are not marked ``locked`` are modified.
        Returns the number of deltas actually applied.
        """
        applied = 0
        for delta in deltas:
            role = self.role_registry.get(delta.role_id)
            if role is None:
                continue
            if getattr(role, "locked", False):
                continue

            if delta.field_changed == "metadata":
                role.metadata = delta.new_value
                applied += 1
            elif delta.field_changed == "priority":
                role.priority = delta.new_value
                applied += 1
            elif delta.field_changed == "blocked_skills":
                role.blocked_skills = delta.new_value
                applied += 1
            elif delta.field_changed == "system_prompt":
                role.system_prompt = delta.new_value
                applied += 1
            elif delta.field_changed == "allowed_skills":
                role.allowed_skills = delta.new_value
                applied += 1

        return applied
