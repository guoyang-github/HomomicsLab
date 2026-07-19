"""Retrieve and rank CBKB-derived context for a given user intent."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from homomics_lab.agent.intent.models import intent_strategy_key
from homomics_lab.context.reranker import BiEncoderReranker
from homomics_lab.knowledge.cbkb import CBKB

logger = logging.getLogger(__name__)


@dataclass
class CBKBContextItem:
    """A single retrieved CBKB context item."""

    source: str  # experiment, parameter_lore, sop, anomaly
    content: str
    priority: int
    metadata: Dict[str, Any]


class CBKBRetriever:
    """Retrieve relevant project context from CBKB."""

    def __init__(
        self,
        cbkb: CBKB,
        embedding_model_name: Optional[str] = None,
        reranker: Optional[Any] = None,
    ):
        self.cbkb = cbkb
        self.embedding_model_name = embedding_model_name
        self._embedding_model = None
        self._reranker = reranker or BiEncoderReranker(model_name=embedding_model_name)

    async def retrieve(
        self,
        project_id: str,
        query: str,
        intent: Optional[Any] = None,
        top_k: int = 10,
    ) -> List[CBKBContextItem]:
        """Retrieve a ranked list of CBKB context items for the current turn."""
        items: List[CBKBContextItem] = []

        # 1. Recent experiments
        try:
            experiments = self.cbkb.list_experiment_nodes_by_project(project_id, limit=5)
            for node in experiments:
                items.append(
                    CBKBContextItem(
                        source="experiment",
                        content=f"Experiment {node.bundle_id}: {node.summary}",
                        priority=8,
                        metadata={
                            "bundle_id": node.bundle_id,
                            "skills_used": node.skills_used,
                            "phases": node.phases,
                        },
                    )
                )
        except Exception as exc:
            logger.warning("CBKB experiment retrieval failed: %s", exc)

        # 2. Parameter lore for skills referenced by intent or recent experiments
        skill_ids = set()
        if intent and hasattr(intent, "target") and intent.target:
            skill_ids.add(intent.target)
        for sub in getattr(intent, "sub_intents", []) or []:
            if getattr(sub, "target", None):
                skill_ids.add(sub.target)
        for node in getattr(self.cbkb.list_experiment_nodes_by_project(project_id, limit=3), "__iter__", lambda: iter([]))():
            skill_ids.update(node.skills_used)

        for skill_id in list(skill_ids)[:5]:
            try:
                entries = self.cbkb.query_parameter_lore(
                    skill_id=skill_id,
                    project_id=project_id,
                    limit=3,
                )
                for entry in entries:
                    items.append(
                        CBKBContextItem(
                            source="parameter_lore",
                            content=(
                                f"Skill {entry.skill_id} parameter {entry.param_name}="
                                f"{entry.param_value} → {entry.outcome_metric}={entry.outcome_value}"
                            ),
                            priority=7,
                            metadata={
                                "skill_id": entry.skill_id,
                                "param_name": entry.param_name,
                                "param_value": entry.param_value,
                            },
                        )
                    )
            except Exception as exc:
                logger.warning("CBKB parameter lore retrieval failed: %s", exc)

        # 3. SOPs
        try:
            categories = set()
            if intent:
                for val in (intent.domain, intent_strategy_key(intent)):
                    if val:
                        categories.add(val)
            sops = []
            for category in categories:
                sops.extend(self.cbkb.list_sops(category=category)[:2])
            if not sops:
                sops = self.cbkb.list_sops()[:3]
            for sop in sops:
                template = sop.template
                if isinstance(template, dict):
                    steps = template.get("steps", [])
                    content = f"SOP '{sop.name}' ({sop.category}): steps: {'; '.join(steps[:5])}"
                else:
                    content = f"SOP '{sop.name}' ({sop.category})"
                items.append(
                    CBKBContextItem(
                        source="sop",
                        content=content,
                        priority=6,
                        metadata={"sop_id": sop.id, "category": sop.category},
                    )
                )
        except Exception as exc:
            logger.warning("CBKB SOP retrieval failed: %s", exc)

        # 4. Anomalies
        try:
            phase_type = intent_strategy_key(intent) if intent else None
            anomalies = self.cbkb.query_anomalies(
                project_id=project_id,
                phase_type=phase_type,
                limit=3,
            )
            for anomaly in anomalies:
                items.append(
                    CBKBContextItem(
                        source="anomaly",
                        content=f"Anomaly in {anomaly.phase_type}: {anomaly.summary}",
                        priority=9 if anomaly.severity == "critical" else 7,
                        metadata={
                            "severity": anomaly.severity,
                            "recommendations": anomaly.recommendations,
                        },
                    )
                )
        except Exception as exc:
            logger.warning("CBKB anomaly retrieval failed: %s", exc)

        return self._rerank(items, query, top_k)

    def _rerank(
        self,
        items: List[CBKBContextItem],
        query: str,
        top_k: int,
    ) -> List[CBKBContextItem]:
        """Rerank items by relevance to the query."""
        if not items:
            return []

        try:
            return self._reranker.rerank(
                query=query,
                candidates=items,
                text_fn=lambda item: item.content,
                top_k=top_k,
            )
        except Exception as exc:
            logger.warning("CBKB reranking failed: %s", exc)
            items.sort(key=lambda x: -x.priority)
            return items[:top_k]
