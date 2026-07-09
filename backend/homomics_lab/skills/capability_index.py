"""Unified Capability Index for skills, tools, SOPs, experiments and data sources.

The index is the retrieval backbone of the agent's "skill discovery" capability:
instead of searching each repository independently, everything is embedded into a
single vector space and linked in a knowledge graph.  This lets the planner:

1. Find semantically relevant skills/tools/SOPs for a user request.
2. Walk graph edges (skill → tool, experiment → skill, SOP → skill, ...) to
   enrich the retrieval context.
3. Fall back to structured filters (type, category, project) when embeddings are
   unavailable.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncio

from homomics_lab.config import Settings, settings as default_settings
from homomics_lab.context.feedback_store import (
    ExecutionFeedback,
    FeedbackOutcome,
    FeedbackStore,
    SQLiteFeedbackStore,
)
from homomics_lab.context.graph.base import GraphBackend
from homomics_lab.context.graph.factory import get_graph_backend, reset_graph_backend
from homomics_lab.context.vector_store.base import VectorStoreBackend
from homomics_lab.context.vector_store.factory import get_vector_store, reset_vector_store
from homomics_lab.embeddings.base import EmbeddingProvider
from homomics_lab.agent.intent import UserIntent
from homomics_lab.embeddings.factory import get_embedding_provider, reset_embedding_provider

logger = logging.getLogger(__name__)

_COLLECTION = "capabilities"


class CapabilityType(str, Enum):
    SKILL = "skill"
    TOOL = "tool"
    SOP = "sop"
    EXPERIMENT = "experiment"
    DATA_SOURCE = "data_source"
    TEMPLATE = "template"
    PARAMETER_LORE = "parameter_lore"


@dataclass
class CapabilityCandidate:
    """A single retrieved capability."""

    id: str
    type: CapabilityType
    name: str
    description: str
    category: str
    score: float
    payload: Dict[str, Any]


class CapabilityIndex:
    """Unified dense + graph index of agent capabilities."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStoreBackend] = None,
        graph_backend: Optional[GraphBackend] = None,
        feedback_store: Optional[FeedbackStore] = None,
    ) -> None:
        self.settings = settings or default_settings
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._graph_backend = graph_backend
        self._feedback_store = feedback_store

        self._owns_embedding = embedding_provider is None
        self._owns_vector_store = vector_store is None
        self._owns_graph_backend = graph_backend is None
        self._owns_feedback_store = feedback_store is None

        # Lightweight in-memory cache of indexed items for keyword fallback
        # and structured filtering when embeddings are unavailable.
        self._source_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lazy accessors
    # ------------------------------------------------------------------
    def _get_embedding_provider(self) -> Optional[EmbeddingProvider]:
        if self._embedding_provider is None:
            self._embedding_provider = get_embedding_provider(self.settings)
        return self._embedding_provider

    def _get_vector_store(self) -> VectorStoreBackend:
        if self._vector_store is None:
            self._vector_store = get_vector_store(self.settings)
        return self._vector_store

    def _get_graph_backend(self) -> Optional[GraphBackend]:
        if self._graph_backend is None:
            self._graph_backend = get_graph_backend(self.settings)
        return self._graph_backend

    def _get_feedback_store(self) -> FeedbackStore:
        if self._feedback_store is None:
            self._feedback_store = SQLiteFeedbackStore(
                db_path=self.settings.data_dir / "feedback.db"
            )
        return self._feedback_store

    # ------------------------------------------------------------------
    # Embedding helper
    # ------------------------------------------------------------------
    async def _embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not texts:
            return []
        provider = self._get_embedding_provider()
        if provider is None or not provider.is_available():
            return None
        try:
            return await asyncio.to_thread(provider.encode, texts)
        except Exception as exc:
            logger.warning("Capability index embedding failed: %s", exc)
            return None

    async def _dimension(self) -> int:
        provider = self._get_embedding_provider()
        if provider is None:
            return 0
        try:
            return await asyncio.to_thread(lambda: provider.dimension)
        except Exception as exc:
            logger.warning("Failed to determine embedding dimension: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Indexing helpers
    # ------------------------------------------------------------------
    def _doc_id(self, item_type: CapabilityType, item_id: str) -> str:
        return f"{item_type.value}:{item_id}"

    async def _index(
        self,
        item_type: CapabilityType,
        item_id: str,
        name: str,
        description: str,
        category: str,
        payload: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> None:
        doc_id = self._doc_id(item_type, item_id)
        text = f"{name}\n{description}\n{category}"
        metadata = {
            "type": item_type.value,
            "id": item_id,
            "name": name,
            "description": description,
            "category": category,
            "project_id": project_id,
        }

        # Keep a lightweight cache for structured/keyword fallback.
        self._source_cache[doc_id] = {
            "type": item_type.value,
            "id": item_id,
            "name": name,
            "description": description,
            "category": category,
            "text": text,
            "metadata": metadata,
            "payload": payload,
            "project_id": project_id,
        }

        embeddings = await self._embed([text])
        if embeddings:
            try:
                await self._get_vector_store().upsert(
                    collection=_COLLECTION,
                    ids=[doc_id],
                    texts=[text],
                    embeddings=embeddings,
                    metadata=[metadata],
                )
            except Exception as exc:
                logger.warning("Failed to index capability %s: %s", doc_id, exc)

        graph = self._get_graph_backend()
        if graph is not None:
            try:
                await graph.add_node(
                    node_id=doc_id,
                    labels=["Capability", item_type.value.capitalize()],
                    properties={
                        "name": name,
                        "description": description[:500],
                        "category": category,
                        "project_id": project_id,
                    },
                )
                # Link to category hub for graph traversal.
                await graph.add_edge(
                    from_id=f"category:{category}",
                    to_id=doc_id,
                    edge_type="HAS_CAPABILITY",
                )
                if project_id:
                    await graph.add_edge(
                        from_id=f"project:{project_id}",
                        to_id=doc_id,
                        edge_type="HAS_CAPABILITY",
                    )
            except Exception as exc:
                logger.warning("Failed to index capability graph node %s: %s", doc_id, exc)

    async def _link(self, from_id: str, to_id: str, edge_type: str) -> None:
        graph = self._get_graph_backend()
        if graph is None:
            return
        try:
            await graph.add_edge(from_id=from_id, to_id=to_id, edge_type=edge_type)
        except Exception as exc:
            logger.warning("Graph edge creation failed: %s", exc)

    # ------------------------------------------------------------------
    # Public indexing API
    # ------------------------------------------------------------------
    async def index_skill(self, skill) -> None:
        """Index a ``SkillDefinition``."""
        from homomics_lab.skills.models import SkillDefinition

        if not isinstance(skill, SkillDefinition):
            raise TypeError("Expected SkillDefinition")
        payload = skill.model_dump(mode="json")
        tags = skill.metadata.get("tags", []) or []
        await self._index(
            CapabilityType.SKILL,
            skill.id,
            skill.name,
            skill.description,
            skill.category,
            payload,
        )
        for tag in tags:
            await self._link(from_id=f"tag:{tag}", to_id=self._doc_id(CapabilityType.SKILL, skill.id), edge_type="TAGGED")

    async def index_tool(self, tool) -> None:
        """Index a ``ToolDefinition``."""
        from homomics_lab.tools.models import ToolDefinition

        if not isinstance(tool, ToolDefinition):
            raise TypeError("Expected ToolDefinition")
        payload = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "source": tool.source,
            "risk_level": tool.risk_level,
            "metadata": tool.metadata,
        }
        await self._index(
            CapabilityType.TOOL,
            tool.name,
            tool.name,
            tool.description,
            tool.source,
            payload,
        )

    async def index_sop(self, sop) -> None:
        """Index a ``LabSOP``."""
        from homomics_lab.knowledge.cbkb import LabSOP

        if not isinstance(sop, LabSOP):
            raise TypeError("Expected LabSOP")
        summary = sop.template.get("description", "") if isinstance(sop.template, dict) else ""
        description = f"{sop.name} {summary}".strip()
        payload = {
            "id": sop.id,
            "name": sop.name,
            "category": sop.category,
            "template": sop.template,
            "version": sop.version,
            "locked": sop.locked,
        }
        await self._index(
            CapabilityType.SOP,
            sop.id,
            sop.name,
            description,
            sop.category,
            payload,
        )

    async def index_experiment(self, node) -> None:
        """Index a ``CBKB ExperimentNode``."""
        from homomics_lab.knowledge.cbkb import ExperimentNode

        if not isinstance(node, ExperimentNode):
            raise TypeError("Expected ExperimentNode")
        description = f"Summary: {node.summary}. Skills: {', '.join(node.skills_used)}. Phases: {', '.join(node.phases)}"
        payload = {
            "bundle_id": node.bundle_id,
            "project_id": node.project_id,
            "summary": node.summary,
            "skills_used": node.skills_used,
            "phases": node.phases,
            "metadata": node.metadata,
        }
        doc_id = self._doc_id(CapabilityType.EXPERIMENT, node.bundle_id)
        await self._index(
            CapabilityType.EXPERIMENT,
            node.bundle_id,
            node.bundle_id,
            description,
            "experiment",
            payload,
            project_id=node.project_id,
        )
        for skill_id in node.skills_used:
            await self._link(
                from_id=doc_id,
                to_id=self._doc_id(CapabilityType.SKILL, skill_id),
                edge_type="USES_SKILL",
            )

    async def index_data_source(
        self,
        source_id: str,
        name: str,
        description: str,
        category: str = "data",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Index an external data source (database, API, file repository, ...)."""
        payload = {
            "source_id": source_id,
            "name": name,
            "description": description,
            "category": category,
            "metadata": metadata or {},
        }
        await self._index(
            CapabilityType.DATA_SOURCE,
            source_id,
            name,
            description,
            category,
            payload,
        )

    async def index_analysis_template(self, template) -> None:
        """Index an ``AnalysisTemplate`` scenario preset."""
        from homomics_lab.agent.plan.template import AnalysisTemplate

        if not isinstance(template, AnalysisTemplate):
            raise TypeError("Expected AnalysisTemplate")

        description = (
            f"{template.description} Domain: {template.domain}. "
            f"Intents: {', '.join(template.applicable_intents)}. "
            f"Tags: {', '.join(template.tags)}."
        )
        payload = template.to_dict()
        await self._index(
            CapabilityType.TEMPLATE,
            template.template_id,
            template.name,
            description,
            template.domain or "template",
            payload,
        )

    async def index_parameter_lore(
        self,
        skill_id: str,
        param_name: str,
        lore: Dict[str, Any],
    ) -> None:
        """Index parameter best-practice lore for a skill.

        ``lore`` should include keys like ``range``, ``source``, ``rationale``,
        and optionally ``default`` / ``example``.
        """
        lore_id = f"{skill_id}:{param_name}"
        description = (
            f"Parameter '{param_name}' for skill '{skill_id}'. "
            f"Range: {lore.get('range', 'unspecified')}. "
            f"Rationale: {lore.get('rationale', '')}"
        )
        payload = {
            "skill_id": skill_id,
            "param_name": param_name,
            "lore": lore,
        }
        await self._index(
            CapabilityType.PARAMETER_LORE,
            lore_id,
            param_name,
            description,
            lore.get("source", "parameter_lore"),
            payload,
        )
        # Link the lore to its skill in the graph.
        await self._link(
            from_id=self._doc_id(CapabilityType.SKILL, skill_id),
            to_id=self._doc_id(CapabilityType.PARAMETER_LORE, lore_id),
            edge_type="HAS_PARAMETER_LORE",
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    async def search(
        self,
        query: str,
        top_k: int = 10,
        item_types: Optional[List[CapabilityType]] = None,
        project_id: Optional[str] = None,
        min_score: float = 0.0,
        *,
        intent: Optional[UserIntent] = None,
        data_type: Optional[str] = None,
        domains: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> List[CapabilityCandidate]:
        """Search capabilities using dense embeddings, with keyword fallback.

        Structured filters (``item_types``, ``data_type``, ``domains``,
        ``categories``) are applied to metadata whenever the underlying store
        supports it; otherwise they are applied after retrieval.
        """
        if not query.strip():
            return []

        filters = self._build_filters(
            item_types=item_types,
            project_id=project_id,
            data_type=data_type,
            domains=domains,
            categories=categories,
        )

        results: List[Any] = []
        query_embedding = await self._embed([query])

        if query_embedding is not None:
            try:
                results = await self._get_vector_store().search(
                    collection=_COLLECTION,
                    query_embedding=query_embedding[0],
                    top_k=top_k * 4,
                    filters=filters or None,
                )
            except Exception as exc:
                logger.warning("Capability vector search failed: %s", exc)
                results = []

        # Fallback to keyword search if dense search failed or returned nothing.
        if not results:
            try:
                results = await self._get_vector_store().keyword_search(
                    collection=_COLLECTION,
                    query=query,
                    top_k=top_k * 4,
                    filters=filters or None,
                )
            except Exception as exc:
                logger.warning("Capability keyword search failed: %s", exc)
                results = []

        # Final fallback: scan the lightweight source cache.
        if not results:
            results = self._cache_keyword_fallback(query, filters, top_k=top_k * 4)

        candidates = self._results_to_candidates(results, item_types=item_types)
        candidates = await self._apply_feedback(candidates)
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]

    @staticmethod
    def _build_filters(
        item_types: Optional[List[CapabilityType]] = None,
        project_id: Optional[str] = None,
        data_type: Optional[str] = None,
        domains: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        if item_types:
            filters["type"] = [t.value for t in item_types]
        if project_id is not None:
            filters["project_id"] = project_id
        if data_type:
            filters["data_type"] = data_type
        if domains:
            filters["domain"] = domains
        if categories:
            filters["category"] = categories
        return filters

    def _cache_keyword_fallback(
        self,
        query: str,
        filters: Dict[str, Any],
        top_k: int,
    ) -> List[Any]:
        """Match indexed items by keyword when vector/keyword store is empty."""
        from dataclasses import dataclass

        @dataclass
        class _CachedResult:
            id: str
            score: float
            metadata: Dict[str, Any]

        query_tokens = set(query.lower().split())
        results: List[_CachedResult] = []
        for doc_id, cached in self._source_cache.items():
            meta = cached.get("metadata", {})
            if not self._matches_filters(meta, filters):
                continue
            text = cached.get("text", "").lower()
            hits = sum(1 for token in query_tokens if len(token) > 2 and token in text)
            if hits == 0:
                continue
            score = min(0.3 + hits * 0.05, 0.9)
            results.append(_CachedResult(id=doc_id, score=score, metadata=meta))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def _matches_filters(metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Apply structured filters to cached metadata."""
        for key, value in filters.items():
            if key == "type" and isinstance(value, list):
                if metadata.get("type") not in value:
                    return False
            elif key == "category" and isinstance(value, list):
                if metadata.get("category") not in value:
                    return False
            elif key == "domain" and isinstance(value, list):
                # Templates store domain in metadata if indexed that way.
                if metadata.get("domain") not in value:
                    return False
            elif key == "data_type":
                if metadata.get("data_type") != value:
                    return False
            elif key == "project_id":
                if metadata.get("project_id") != value:
                    return False
        return True

    def _results_to_candidates(
        self,
        results: List[Any],
        item_types: Optional[List[CapabilityType]] = None,
    ) -> List[CapabilityCandidate]:
        """Convert vector/keyword search results to CapabilityCandidates."""
        candidates: List[CapabilityCandidate] = []
        seen: set = set()
        for r in results:
            meta = getattr(r, "metadata", None) or {}
            item_type = CapabilityType(meta.get("type", "skill"))
            if item_types and item_type not in item_types:
                continue
            item_id = meta.get("id", getattr(r, "id", ""))
            key = (item_type.value, item_id)
            if key in seen:
                continue
            seen.add(key)
            cached = self._source_cache.get(f"{item_type.value}:{item_id}", {})
            candidates.append(
                CapabilityCandidate(
                    id=item_id,
                    type=item_type,
                    name=meta.get("name", ""),
                    description=meta.get("description", ""),
                    category=meta.get("category", ""),
                    score=getattr(r, "score", 0.0),
                    payload=cached.get("payload", meta),
                )
            )
        return candidates

    async def search_by_intent(
        self,
        intent: UserIntent,
        data_state: Optional[Any] = None,
        item_types: Optional[List[CapabilityType]] = None,
        top_k: int = 10,
    ) -> List[CapabilityCandidate]:
        """Search capabilities by combining intent fields and data state.

        The query is assembled from the user's original message, analysis type,
        target, domain and any extracted keywords.  ``data_state`` supplies
        ``data_type`` and ``domain_state`` for structured filtering.
        """
        parts: List[str] = [
            intent.original_message or "",
            intent.analysis_type or "",
        ]
        if intent.target:
            parts.append(intent.target)
        if intent.domain:
            parts.append(intent.domain)

        keywords: List[str] = []
        if intent.domain_knowledge:
            keywords.extend(intent.domain_knowledge)
        if intent.metadata and isinstance(intent.metadata, dict):
            meta_keywords = intent.metadata.get("keywords")
            if isinstance(meta_keywords, list):
                keywords.extend(str(k) for k in meta_keywords)
            elif isinstance(meta_keywords, str):
                keywords.append(meta_keywords)
        if keywords:
            parts.append(" ".join(keywords))

        query = " ".join(p for p in parts if p).strip()
        if not query:
            return []

        data_type: Optional[str] = None
        domains: Optional[List[str]] = None
        if data_state is not None:
            data_type = getattr(data_state, "data_type", None)
            domain_state = getattr(data_state, "domain_state", None)
            if isinstance(domain_state, dict) and domain_state:
                domains = [d for d in domain_state.keys() if not d.startswith("_")]
            if intent.domain and (not domains or intent.domain not in domains):
                domains = (domains or []) + [intent.domain]

        return await self.search(
            query=query,
            top_k=top_k,
            item_types=item_types,
            data_type=data_type,
            domains=domains,
            intent=intent,
        )

    async def _apply_feedback(
        self, candidates: List[CapabilityCandidate]
    ) -> List[CapabilityCandidate]:
        """Adjust candidate scores using historical execution feedback."""
        if not candidates:
            return candidates
        store = self._get_feedback_store()

        def _stats(c: CapabilityCandidate):
            return store.get_stats(c.type.value, c.id)

        for c in candidates:
            stats = await asyncio.to_thread(_stats, c)
            # Neutral success_rate (0.5) yields multiplier 1.0.
            multiplier = 1.0 + 0.5 * (stats.success_rate - 0.5)
            c.score = round(c.score * multiplier, 6)
        return candidates

    async def search_similar(
        self,
        embedding: List[float],
        top_k: int = 10,
        item_types: Optional[List[CapabilityType]] = None,
        project_id: Optional[str] = None,
    ) -> List[CapabilityCandidate]:
        """Search with an externally provided embedding vector."""
        filters: Dict[str, Any] = {}
        if project_id is not None:
            filters["project_id"] = project_id

        try:
            results = await self._get_vector_store().search(
                collection=_COLLECTION,
                query_embedding=embedding,
                top_k=top_k * 2,
                filters=filters or None,
            )
        except Exception as exc:
            logger.warning("Capability vector search failed: %s", exc)
            return []

        candidates: List[CapabilityCandidate] = []
        for r in results:
            meta = r.metadata or {}
            item_type = CapabilityType(meta.get("type", "skill"))
            if item_types and item_type not in item_types:
                continue
            candidates.append(
                CapabilityCandidate(
                    id=meta.get("id", r.id),
                    type=item_type,
                    name=meta.get("name", ""),
                    description=meta.get("description", ""),
                    category=meta.get("category", ""),
                    score=r.score,
                    payload=meta,
                )
            )
        candidates = await self._apply_feedback(candidates)
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]

    async def add_feedback(
        self,
        capability_id: str,
        capability_type: CapabilityType,
        outcome: FeedbackOutcome,
        project_id: Optional[str] = None,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record execution feedback for a capability."""
        feedback = ExecutionFeedback(
            target_type=capability_type.value,
            target_id=capability_id,
            outcome=outcome,
            project_id=project_id,
            rating=rating,
            comment=comment,
            context=context or {},
        )
        await asyncio.to_thread(self._get_feedback_store().record, feedback)

    async def get_neighbors(
        self,
        item_id: str,
        item_type: CapabilityType,
        edge_types: Optional[List[str]] = None,
        hops: int = 1,
    ) -> List[CapabilityCandidate]:
        """Graph traversal: return capabilities linked to the given item."""
        graph = self._get_graph_backend()
        if graph is None:
            return []

        doc_id = self._doc_id(item_type, item_id)
        try:
            nodes = await graph.get_neighbors(doc_id, edge_types=edge_types, hops=hops)
        except Exception as exc:
            logger.warning("Graph neighbor search failed: %s", exc)
            return []

        candidates: List[CapabilityCandidate] = []
        for node in nodes:
            if not node.id.startswith("skill:") and not node.id.startswith("tool:"):
                continue
            parts = node.id.split(":", 1)
            if len(parts) != 2:
                continue
            cap_type = CapabilityType(parts[0])
            props = node.properties or {}
            candidates.append(
                CapabilityCandidate(
                    id=parts[1],
                    type=cap_type,
                    name=props.get("name", ""),
                    description=props.get("description", ""),
                    category=props.get("category", ""),
                    score=0.0,
                    payload=props,
                )
            )
        return candidates

    async def close(self) -> None:
        if self._owns_vector_store:
            try:
                await self._get_vector_store().close()
                reset_vector_store()
            except Exception as exc:
                logger.warning("Vector store close failed: %s", exc)
        if self._owns_graph_backend:
            try:
                await self._get_graph_backend().close()
                reset_graph_backend()
            except Exception as exc:
                logger.warning("Graph backend close failed: %s", exc)
        if self._owns_feedback_store:
            try:
                self._get_feedback_store().close()
            except Exception as exc:
                logger.warning("Feedback store close failed: %s", exc)
        if self._owns_embedding:
            reset_embedding_provider()
