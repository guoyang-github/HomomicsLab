"""CBKBCurator — automatic nightly curation for the Computational Biology Knowledge Base.

Orchestrates:
  1. Distillation of new experiment bundles into structured insights
  2. Topic clustering over experiment nodes (Jaccard on skills + parameters)
  3. Narrative report generation (periodic aggregates)
  4. SOP evolution proposals (new SOPs + divergence detection)
  5. Auto-linking of similar experiments via typed edges
"""

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from homomics_lab.knowledge.cbkb import (
    AnomalyRecord,
    CBKB,
    ExperimentEdge,
    ExperimentNode,
    LabSOP,
    ParameterLoreEntry,
)


# ─────────────────────────────────────────
# Curation data models
# ─────────────────────────────────────────


@dataclass
class DistilledInsight:
    insight_type: str  # e.g. "skill_sequence", "parameter_combo", "project_similarity"
    title: str
    content: str
    source_ids: List[str]
    confidence: float
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TopicCluster:
    cluster_id: str
    topic_name: str
    bundle_ids: List[str]
    common_skills: List[str]
    common_parameters: List[str]
    centroid_summary: str


@dataclass
class NarrativeReport:
    period: str  # ISO date range, e.g. "2024-01-01 to 2024-01-31"
    total_experiments: int
    total_anomalies: int
    top_skills: List[Tuple[str, int]]
    top_anomalies: List[Tuple[str, int]]
    insights: List[DistilledInsight]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SOPProposal:
    sop_id: str
    proposed_template: Dict[str, Any]
    confidence: float
    derived_from_bundles: List[str]
    reason: str


# ─────────────────────────────────────────
# Curator
# ─────────────────────────────────────────


class CBKBCurator:
    """Automatic curator for CBKB layers."""

    def __init__(self, cbkb: CBKB, skill_dag: Optional[Any] = None):
        self.cbkb = cbkb
        self.skill_dag = skill_dag

    # ── Internal helpers ────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.cbkb.db_path))

    def _all_experiment_nodes(self, since: Optional[str] = None) -> List[ExperimentNode]:
        sql = "SELECT * FROM experiment_nodes"
        params: Tuple = ()
        if since:
            sql += " WHERE created_at >= ?"
            params = (since,)
        sql += " ORDER BY created_at DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
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

    def _all_parameter_lore(self, since: Optional[str] = None) -> List[ParameterLoreEntry]:
        sql = "SELECT * FROM parameter_lore"
        params: Tuple = ()
        if since:
            sql += " WHERE created_at >= ?"
            params = (since,)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            ParameterLoreEntry(
                id=r[0], skill_id=r[1], param_name=r[2], param_value=r[3],
                outcome_metric=r[4], outcome_value=r[5], project_id=r[6],
                context=r[7] or "", created_at=r[8],
            )
            for r in rows
        ]

    def _all_anomalies(self, since: Optional[str] = None) -> List[AnomalyRecord]:
        sql = "SELECT * FROM anomaly_archive"
        params: Tuple = ()
        if since:
            sql += " WHERE created_at >= ?"
            params = (since,)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            AnomalyRecord(
                id=r[0], project_id=r[1], phase_type=r[2], summary=r[3],
                flags=json.loads(r[4]), recommendations=json.loads(r[5]),
                severity=r[6], created_at=r[7],
            )
            for r in rows
        ]

    def _all_edges(self) -> List[ExperimentEdge]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM experiment_edges").fetchall()
        return [
            ExperimentEdge(
                from_bundle=r[1], to_bundle=r[2], edge_type=r[3],
                strength=r[4], metadata=json.loads(r[5]),
            )
            for r in rows
        ]

    def _edge_exists(self, a: str, b: str, edge_type: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM experiment_edges
                WHERE from_bundle = ? AND to_bundle = ? AND edge_type = ?
                UNION
                SELECT 1 FROM experiment_edges
                WHERE from_bundle = ? AND to_bundle = ? AND edge_type = ?
                """,
                (a, b, edge_type, b, a, edge_type),
            ).fetchone()
        return row is not None

    # ── Public API ──────────────────────────────────

    def run_full_curation(self, since: Optional[str] = None) -> Dict[str, Any]:
        """Orchestrate all curation steps and return a summary dict."""
        insights = self.distill_new_bundles(since)
        clusters = self.cluster_topics()
        narrative = self.generate_narrative()
        proposals = self.propose_sop_updates()
        linked = self.auto_link_experiments()
        return {
            "distilled_insights": len(insights),
            "topic_clusters": len(clusters),
            "narrative_generated": narrative.period,
            "sop_proposals": len(proposals),
            "auto_linked_edges": linked,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def distill_new_bundles(self, since: Optional[str] = None) -> List[DistilledInsight]:
        """Scan ExperimentGraph for bundles and extract insights."""
        nodes = self._all_experiment_nodes(since)
        insights: List[DistilledInsight] = []

        # 1. Most common skill sequence
        sequences: List[Tuple[str, ...]] = [tuple(n.skills_used) for n in nodes if n.skills_used]
        if sequences:
            seq_counts = Counter(sequences)
            most_common_seq, seq_freq = seq_counts.most_common(1)[0]
            insights.append(
                DistilledInsight(
                    insight_type="skill_sequence",
                    title="Most common skill sequence",
                    content=f"Sequence {list(most_common_seq)} observed {seq_freq} times",
                    source_ids=[n.bundle_id for n in nodes if tuple(n.skills_used) == most_common_seq],
                    confidence=min(1.0, seq_freq / len(nodes) + 0.5),
                )
            )

        # 2. Parameter combinations that succeeded
        lore = self._all_parameter_lore(since)
        if lore:
            # Group by (skill_id, param_name, param_value) and mean outcome
            combo_groups: Dict[Tuple[str, str, str], List[float]] = defaultdict(list)
            for entry in lore:
                combo_groups[(entry.skill_id, entry.param_name, entry.param_value)].append(entry.outcome_value)
            best_combos = sorted(
                combo_groups.items(),
                key=lambda x: sum(x[1]) / len(x[1]),
                reverse=True,
            )[:3]
            for (skill, param, val), outcomes in best_combos:
                mean_outcome = sum(outcomes) / len(outcomes)
                insights.append(
                    DistilledInsight(
                        insight_type="parameter_combo",
                        title=f"Reliable parameter: {param}={val} for {skill}",
                        content=f"Mean outcome {mean_outcome:.2f} across {len(outcomes)} samples",
                        source_ids=[e.id for e in lore if (e.skill_id, e.param_name, e.param_value) == (skill, param, val)],
                        confidence=min(1.0, len(outcomes) * 0.1 + 0.5),
                    )
                )

        # 3. Projects with similar characteristics
        project_skills: Dict[str, Set[str]] = defaultdict(set)
        for n in nodes:
            project_skills[n.project_id].update(n.skills_used)
        project_list = list(project_skills.items())
        similar_projects: List[str] = []
        for i in range(len(project_list)):
            for j in range(i + 1, len(project_list)):
                pid_a, skills_a = project_list[i]
                pid_b, skills_b = project_list[j]
                if skills_a and skills_b:
                    sim = len(skills_a & skills_b) / len(skills_a | skills_b)
                    if sim >= 0.5:
                        similar_projects.append(f"{pid_a} ~ {pid_b} (Jaccard={sim:.2f})")
        if similar_projects:
            insights.append(
                DistilledInsight(
                    insight_type="project_similarity",
                    title="Projects with similar characteristics",
                    content="; ".join(similar_projects),
                    source_ids=list(project_skills.keys()),
                    confidence=0.7,
                )
            )

        return insights

    def cluster_topics(self) -> List[TopicCluster]:
        """Group experiment nodes by Jaccard similarity on skills + parameters."""
        nodes = self._all_experiment_nodes()
        lore = self._all_parameter_lore()
        if not nodes:
            return []

        # Build per-bundle parameter set
        bundle_params: Dict[str, Set[str]] = defaultdict(set)
        for entry in lore:
            bundle_params[entry.project_id].add(entry.param_name)

        # Compute pairwise Jaccard similarity matrix
        def jaccard(a: Set[str], b: Set[str]) -> float:
            if not a and not b:
                return 0.0
            return len(a & b) / len(a | b)

        def node_similarity(n1: ExperimentNode, n2: ExperimentNode) -> float:
            skill_sim = jaccard(set(n1.skills_used), set(n2.skills_used))
            param_sim = jaccard(bundle_params.get(n1.project_id, set()), bundle_params.get(n2.project_id, set()))
            return (skill_sim + param_sim) / 2.0

        # Simple greedy clustering
        visited: Set[str] = set()
        clusters: List[TopicCluster] = []
        cluster_counter = 0

        for node in nodes:
            if node.bundle_id in visited:
                continue
            members = [node]
            visited.add(node.bundle_id)
            for other in nodes:
                if other.bundle_id in visited:
                    continue
                if node_similarity(node, other) >= 0.5:
                    members.append(other)
                    visited.add(other.bundle_id)

            if len(members) >= 2:
                cluster_counter += 1
                all_skills = Counter([s for m in members for s in m.skills_used])
                all_params = Counter([p for m in members for p in bundle_params.get(m.project_id, [])])
                common_skills = [s for s, c in all_skills.most_common(3) if c >= len(members) // 2 + 1]
                common_parameters = [p for p, c in all_params.most_common(3) if c >= len(members) // 2 + 1]
                topic_name = f"Topic: {' + '.join(common_skills[:2]) or 'mixed'}"
                clusters.append(
                    TopicCluster(
                        cluster_id=f"tc_{cluster_counter:03d}",
                        topic_name=topic_name,
                        bundle_ids=[m.bundle_id for m in members],
                        common_skills=common_skills,
                        common_parameters=common_parameters,
                        centroid_summary=f"Cluster of {len(members)} experiments sharing skills and parameters",
                    )
                )

        return clusters

    def generate_narrative(self, period_days: int = 30) -> NarrativeReport:
        """Aggregate stats and surface top insights."""
        since_dt = datetime.now(timezone.utc) - timedelta(days=period_days)
        since = since_dt.isoformat()

        nodes = self._all_experiment_nodes(since)
        anomalies = self._all_anomalies(since)
        all_lore = self._all_parameter_lore(since)

        # Top skills
        skill_counter = Counter([s for n in nodes for s in n.skills_used])
        top_skills = skill_counter.most_common(5)

        # Top anomalies by phase type
        anomaly_counter = Counter([a.phase_type for a in anomalies])
        top_anomalies = anomaly_counter.most_common(3)

        # Top 3 ParameterLore insights
        param_insights: List[DistilledInsight] = []
        if all_lore:
            groups: Dict[Tuple[str, str], List[float]] = defaultdict(list)
            for e in all_lore:
                groups[(e.param_name, e.param_value)].append(e.outcome_value)
            top_params = sorted(groups.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)[:3]
            for (pname, pval), outcomes in top_params:
                param_insights.append(
                    DistilledInsight(
                        insight_type="parameter_lore",
                        title=f"Most reliable parameter: {pname}={pval}",
                        content=f"Mean outcome {sum(outcomes)/len(outcomes):.2f} over {len(outcomes)} runs",
                        source_ids=[e.id for e in all_lore if (e.param_name, e.param_value) == (pname, pval)],
                        confidence=min(1.0, len(outcomes) * 0.1 + 0.5),
                    )
                )

        # Top 3 AnomalyArchive insights
        anomaly_insights: List[DistilledInsight] = []
        if anomalies:
            by_summary = Counter([a.summary for a in anomalies])
            for summary, count in by_summary.most_common(3):
                anomaly_insights.append(
                    DistilledInsight(
                        insight_type="anomaly_pattern",
                        title=f"Frequent anomaly: {summary}",
                        content=f"Observed {count} times in last {period_days} days",
                        source_ids=[a.id for a in anomalies if a.summary == summary],
                        confidence=min(1.0, count * 0.1 + 0.5),
                    )
                )

        period_end = datetime.now(timezone.utc).isoformat()
        period_str = f"{since} to {period_end}"

        return NarrativeReport(
            period=period_str,
            total_experiments=len(nodes),
            total_anomalies=len(anomalies),
            top_skills=top_skills,
            top_anomalies=top_anomalies,
            insights=param_insights + anomaly_insights,
        )

    def propose_sop_updates(self) -> List[SOPProposal]:
        """Propose new SOPs from topic clusters and detect divergence."""
        proposals: List[SOPProposal] = []
        clusters = self.cluster_topics()
        existing_sops = self.cbkb.list_sops()

        # 1. Find topic clusters with >3 members that don't have a matching SOP
        for cluster in clusters:
            if len(cluster.bundle_ids) <= 3:
                continue
            matched = False
            for sop in existing_sops:
                # Check if SOP already covers enough of this cluster
                overlap = len(set(sop.derived_from_bundle_ids) & set(cluster.bundle_ids))
                if overlap >= len(cluster.bundle_ids) // 2:
                    matched = True
                    break
            if not matched:
                template = {
                    "recommended_skills": cluster.common_skills,
                    "recommended_parameters": cluster.common_parameters,
                    "description": cluster.centroid_summary,
                }
                proposals.append(
                    SOPProposal(
                        sop_id=f"sop_proposal_{cluster.cluster_id}",
                        proposed_template=template,
                        confidence=min(1.0, len(cluster.bundle_ids) * 0.1),
                        derived_from_bundles=cluster.bundle_ids,
                        reason=f"Cluster {cluster.cluster_id} has {len(cluster.bundle_ids)} experiments but no matching SOP",
                    )
                )

        # 2. Find existing SOPs whose derived bundles have diverged significantly
        for sop in existing_sops:
            derived_nodes = [
                self.cbkb.get_experiment_node(bid)
                for bid in sop.derived_from_bundle_ids
            ]
            derived_nodes = [n for n in derived_nodes if n is not None]
            if len(derived_nodes) < 2:
                continue
            # Compute mean pairwise skill Jaccard among derived bundles
            similarities: List[float] = []
            for i in range(len(derived_nodes)):
                for j in range(i + 1, len(derived_nodes)):
                    s1 = set(derived_nodes[i].skills_used)
                    s2 = set(derived_nodes[j].skills_used)
                    if s1 or s2:
                        similarities.append(len(s1 & s2) / len(s1 | s2))
            if similarities:
                mean_sim = sum(similarities) / len(similarities)
                if mean_sim < 0.5:
                    proposals.append(
                        SOPProposal(
                            sop_id=f"sop_divergence_{sop.id}",
                            proposed_template={
                                "current_template": sop.template,
                                "note": "Derived bundles have diverged; consider splitting or updating",
                                "mean_similarity": round(mean_sim, 2),
                            },
                            confidence=round(1.0 - mean_sim, 2),
                            derived_from_bundles=sop.derived_from_bundle_ids,
                            reason=f"SOP '{sop.name}' derived bundles diverged (mean similarity {mean_sim:.2f})",
                        )
                    )

        return proposals

    def auto_link_experiments(self) -> int:
        """Auto-create edges between similar experiments. Returns edge count created."""
        nodes = self._all_experiment_nodes()
        if not nodes:
            return 0

        created = 0
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                n1, n2 = nodes[i], nodes[j]
                s1 = set(n1.skills_used)
                s2 = set(n2.skills_used)
                skill_sim = len(s1 & s2) / len(s1 | s2) if (s1 or s2) else 0.0

                # Parameter similarity from metadata if available
                p1 = set(n1.metadata.get("parameters", {}).keys()) if isinstance(n1.metadata.get("parameters"), dict) else set()
                p2 = set(n2.metadata.get("parameters", {}).keys()) if isinstance(n2.metadata.get("parameters"), dict) else set()
                param_sim = len(p1 & p2) / len(p1 | p2) if (p1 or p2) else 0.0

                overall_sim = (skill_sim + param_sim) / 2.0 if (skill_sim and param_sim) else max(skill_sim, param_sim)

                if overall_sim > 0.7:
                    edge_type = "shares_skill" if skill_sim >= param_sim else "shares_parameter"
                    if not self._edge_exists(n1.bundle_id, n2.bundle_id, edge_type):
                        self.cbkb.add_experiment_edge(
                            ExperimentEdge(
                                from_bundle=n1.bundle_id,
                                to_bundle=n2.bundle_id,
                                edge_type=edge_type,
                                strength=round(overall_sim, 3),
                            )
                        )
                        created += 1
        return created
