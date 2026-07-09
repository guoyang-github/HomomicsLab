"""Capability-aware retrieval for the Open Agent Planner.

Retrieves skills, tools, SOPs, experiments, and data sources from the
CapabilityIndex and registries, then ranks them by applicability to the
user's intent.
"""

from typing import Any, Dict, List, Optional

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.open_agent.models import CapabilityCandidate
from homomics_lab.agent.plan.models import DataState
from homomics_lab.skills.capability_index import (
    CapabilityCandidate as IndexCapabilityCandidate,
)
from homomics_lab.skills.capability_index import CapabilityIndex, CapabilityType
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.tools.registry import ToolRegistry, get_default_tool_registry


class CapabilityRetriever:
    """Retrieve and rank capabilities for an open agent request."""

    def __init__(
        self,
        skill_registry: Optional[SkillRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        capability_index: Optional[CapabilityIndex] = None,
        top_k: int = 10,
    ):
        self.skill_registry = skill_registry or get_default_registry()
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.capability_index = capability_index
        self.top_k = top_k

    async def retrieve(
        self,
        intent: UserIntent,
        data_state: Optional[DataState] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[CapabilityCandidate]:
        """Retrieve ranked capabilities for ``intent``.

        Tries CapabilityIndex first; falls back to keyword search over
        registries if the index is unavailable.
        """
        query = self._build_query(intent)
        candidates: List[CapabilityCandidate] = []

        if self.capability_index is not None:
            try:
                candidates = await self._retrieve_from_index(query, intent, data_state)
            except Exception:
                candidates = []

        if not candidates:
            candidates = self._retrieve_from_registries(query, intent)

        # Last-resort fallback: for open-ended/exploratory requests, or when
        # no capability matched the query at all, return all registered tools
        # and skills with a low baseline score. This prevents the open agent
        # from giving up on broad questions, while the reasoning engine still
        # selects only relevant items.
        if not candidates:
            candidates = self._broad_fallback(intent)

        # Deduplicate by id, keeping highest score.
        seen: Dict[str, CapabilityCandidate] = {}
        for c in candidates:
            if c.id not in seen or seen[c.id].score < c.score:
                seen[c.id] = c

        ranked = sorted(seen.values(), key=lambda x: x.score, reverse=True)
        return ranked[: self.top_k]

    async def _retrieve_from_index(
        self,
        query: str,
        intent: UserIntent,
        data_state: Optional[DataState],
    ) -> List[CapabilityCandidate]:
        """Retrieve from CapabilityIndex."""
        results = await self.capability_index.search(
            query=query,
            item_types=None,  # search all types
            top_k=self.top_k * 2,
        )
        candidates: List[CapabilityCandidate] = []
        for r in results:
            candidates.append(self._index_candidate_to_open_agent(r))
        return candidates

    @staticmethod
    def _index_candidate_to_open_agent(
        r: IndexCapabilityCandidate,
    ) -> CapabilityCandidate:
        return CapabilityCandidate(
            id=r.id,
            type=r.type,
            name=r.name,
            description=r.description,
            category=r.category,
            score=r.score,
            payload=r.payload,
        )

    def _retrieve_from_registries(
        self,
        query: str,
        intent: UserIntent,
    ) -> List[CapabilityCandidate]:
        """Fallback retrieval via keyword/semantic search over registries."""
        candidates: List[CapabilityCandidate] = []

        # Skills
        try:
            skill_results = self.skill_registry.semantic_search(query, top_k=self.top_k)
        except Exception:
            skill_results = [(s, 0.0) for s in self.skill_registry.search(query)]
        for skill, score in skill_results:
            candidates.append(
                CapabilityCandidate(
                    id=skill.id,
                    type=CapabilityType.SKILL,
                    name=skill.name,
                    description=skill.description,
                    category=skill.category,
                    score=score,
                    payload={"skill": skill},
                )
            )

        # Tools
        for tool in self.tool_registry.list_all():
            text = f"{tool.name} {tool.description}".lower()
            query_tokens = set(query.lower().split())
            hits = sum(1 for t in query_tokens if len(t) > 2 and t in text)
            if hits == 0:
                continue
            score = min(0.3 + hits * 0.1, 0.9)
            candidates.append(
                CapabilityCandidate(
                    id=tool.name,
                    type=CapabilityType.TOOL,
                    name=tool.name,
                    description=tool.description,
                    category=tool.source or "tool",
                    score=score,
                    payload={"tool": tool},
                )
            )

        return candidates

    def _broad_fallback(self, intent: UserIntent) -> List[CapabilityCandidate]:
        """Return all registered tools and skills as a last-resort fallback."""
        candidates: List[CapabilityCandidate] = []
        for skill in self.skill_registry.list_all():
            candidates.append(
                CapabilityCandidate(
                    id=skill.id,
                    type=CapabilityType.SKILL,
                    name=skill.name,
                    description=skill.description,
                    category=skill.category,
                    score=0.1,
                    payload={"skill": skill},
                )
            )
        for tool in self.tool_registry.list_all():
            candidates.append(
                CapabilityCandidate(
                    id=tool.name,
                    type=CapabilityType.TOOL,
                    name=tool.name,
                    description=tool.description,
                    category=tool.source or "tool",
                    score=0.1,
                    payload={"tool": tool},
                )
            )
        return candidates

    @staticmethod
    def _build_query(intent: UserIntent) -> str:
        """Build a rich query string from the intent."""
        parts = []
        if intent.original_message:
            parts.append(intent.original_message)
        parts.append(intent.analysis_type)
        if intent.target:
            parts.append(intent.target)
        if intent.domain:
            parts.append(intent.domain)
        keywords = getattr(intent, "keywords", None) or []
        parts.extend(keywords)
        return " ".join(str(p) for p in parts if p)
