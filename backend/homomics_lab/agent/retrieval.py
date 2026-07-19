"""SkillRetriever — retrieval-augmented planning context.

Combines multiple information sources into a single retrieval context that
feeds into PlanEngine and CodeAct:
  1. Semantic search over the skill registry
  2. SkillDAG graph neighbours and relationship warnings
  3. CBKB Lab SOPs for the target domain
  4. CBKB anomaly archive for known failure modes
  5. CBKB parameter lore for proven parameter choices
  6. CapabilityIndex unified dense + graph search

Also hosts ``SkillReranker``, the BM25-style reranker applied to retrieved
skill candidates before they reach the planner.
"""

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from homomics_lab.agent.literature_retriever import LiteratureRetriever
from homomics_lab.config import settings
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.skills.capability_index import CapabilityIndex, CapabilityType
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class RetrievedSkill:
    """A skill retrieved together with graph-derived context.

    After reranking, ``semantic_score`` holds the composite rerank score while
    ``raw_semantic_score`` preserves the original upstream score.
    """

    skill: SkillDefinition
    semantic_score: float
    graph_boost: float = 0.0
    conflict_warning: Optional[str] = None
    followed_by: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    raw_semantic_score: Optional[float] = None


@dataclass
class RetrievedTool:
    """A tool retrieved together with its metadata."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    risk_level: str
    source: str


@dataclass
class RetrievedDataSource:
    """A data source available for code generation."""

    id: str
    path: str
    format: str
    description: str


@dataclass
class RetrievalContext:
    """Combined retrieval result for planning."""

    query: str
    intent_type: str
    skills: List[RetrievedSkill]
    tools: List[RetrievedTool]
    data_sources: List[RetrievedDataSource]
    literature: List[Dict[str, Any]]
    sops: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    parameter_lore: List[Dict[str, Any]]

    def to_prompt_context(self, max_skills: int = 10) -> Dict[str, Any]:
        """Serialize into a dict suitable for LLM prompt or plan generation."""
        return {
            "query": self.query,
            "intent_type": self.intent_type,
            "skills": [
                {
                    "id": s.skill.id,
                    "name": s.skill.name,
                    "description": s.skill.description,
                    "category": s.skill.category,
                    "runtime": s.skill.runtime.type,
                    "inputs": s.skill.input_schema.properties,
                    "outputs": s.skill.output_schema.properties,
                    "score": round(s.semantic_score + s.graph_boost, 3),
                    "conflict_warning": s.conflict_warning,
                    "followed_by": s.followed_by,
                    "depends_on": s.depends_on,
                }
                for s in self.skills[:max_skills]
            ],
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputs": t.input_schema,
                    "risk_level": t.risk_level,
                    "source": t.source,
                }
                for t in self.tools[:10]
            ],
            "data_sources": [
                {
                    "id": d.id,
                    "path": d.path,
                    "format": d.format,
                    "description": d.description,
                }
                for d in self.data_sources[:10]
            ],
            "literature": self.literature[:5],
            "sops": self.sops[:5],
            "anomalies": self.anomalies[:5],
            "parameter_lore": self.parameter_lore[:5],
        }


_TOKEN_RE = re.compile(r"[a-z0-9]+")

# BM25 saturation constant for normalizing raw BM25 into [0, 1):
#   bm25_norm = bm25 / (bm25 + BM25_NORM_K)
BM25_NORM_K = 1.5


def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokenizer; splits snake_case and kebab-case."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]


def _skill_tokens(skill: Any) -> List[str]:
    """Build the token document for a skill (name weighted twice)."""
    metadata = getattr(skill, "metadata", None) or {}
    parts = [
        skill.name,
        skill.name,
        skill.description or "",
        (skill.category or "").replace("_", " ").replace("-", " "),
    ]
    for key in ("tags", "keywords", "supported_tools"):
        values = metadata.get(key) or []
        parts.extend(str(v) for v in values)
    primary_tool = metadata.get("primary_tool")
    if primary_tool:
        parts.append(str(primary_tool))
    return _tokenize(" ".join(p for p in parts if p))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class SkillReranker:
    """Rerank retrieved skill candidates with semantic + BM25 + graph signals.

    The retriever's upstream signals are heterogeneous and uncalibrated:
    the hybrid index fuses dense/sparse rankings with reciprocal rank fusion,
    whose scores carry no relevance magnitude.  Without re-scoring, any query —
    including meaningless tokens like ``"x_alpha"`` — would be force-matched
    to some skill.

    Candidates are reranked with a transparent composite score in [0, 1]:

        composite = w_semantic * clamp(semantic_score)
                  + w_bm25     * normalized_bm25(query, skill)
                  + w_graph    * clamp(graph_boost)

    The BM25 component is computed in pure Python over the skill's
    name / description / category / keywords (name counted twice).  Candidates
    below ``min_score`` are dropped, so unrelated queries retrieve nothing
    instead of an arbitrary best-effort match.

    ``RetrievedSkill.semantic_score`` is overwritten with the composite score
    so downstream consumers keep working unchanged; the original upstream
    score is preserved on ``RetrievedSkill.raw_semantic_score`` for auditing.

    Args:
        semantic_weight: Weight of the upstream semantic score.
        bm25_weight: Weight of the normalized BM25 lexical overlap.
        graph_weight: Weight of the SkillDAG graph boost.
        min_score: Composite score floor; candidates below it are dropped.
        k1: BM25 term-frequency saturation parameter.
        b: BM25 document-length normalization parameter.
    """

    def __init__(
        self,
        semantic_weight: float = 0.4,
        bm25_weight: float = 0.5,
        graph_weight: float = 0.1,
        min_score: float = 0.1,
        k1: float = 1.2,
        b: float = 0.75,
    ):
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.graph_weight = graph_weight
        self.min_score = min_score
        self.k1 = k1
        self.b = b

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievedSkill],
        top_k: Optional[int] = None,
        corpus: Optional[Sequence[Any]] = None,
    ) -> List[RetrievedSkill]:
        """Rerank candidates, drop those below ``min_score``, then truncate.

        The composite score is written back to ``semantic_score``; the
        previous value is kept on ``raw_semantic_score``.

        Args:
            query: The retrieval query.
            candidates: Retrieved skills to rerank.
            top_k: Optional truncation applied AFTER threshold filtering.
            corpus: Optional background skill collection used for BM25
                document-frequency / average-length statistics.  Without it
                the candidate set itself is the corpus, which makes idf
                vanish when only one candidate survives upstream filtering.
        """
        if not candidates:
            return []

        query_terms = _tokenize(query)
        corpus_tokens = [_skill_tokens(skill) for skill in corpus] if corpus else None
        bm25_scores = self._bm25(query_terms, candidates, corpus_tokens)

        scored: List[RetrievedSkill] = []
        for idx, candidate in enumerate(candidates):
            bm25_norm = 0.0
            if bm25_scores[idx] > 0.0:
                bm25_norm = bm25_scores[idx] / (bm25_scores[idx] + BM25_NORM_K)
            composite = (
                self.semantic_weight * _clamp01(candidate.semantic_score)
                + self.bm25_weight * bm25_norm
                + self.graph_weight * _clamp01(candidate.graph_boost)
            )
            if composite < self.min_score:
                continue
            candidate.raw_semantic_score = candidate.semantic_score
            candidate.semantic_score = composite
            scored.append(candidate)

        # Stable sort: ties keep the upstream (semantic rank) order.
        scored.sort(key=lambda rs: rs.semantic_score, reverse=True)
        if top_k is not None:
            scored = scored[:top_k]
        return scored

    def _bm25(
        self,
        query_terms: Sequence[str],
        candidates: Sequence[RetrievedSkill],
        corpus_tokens: Optional[List[List[str]]] = None,
    ) -> List[float]:
        """Compute BM25 scores of the query against the candidate corpus.

        Document-frequency and average-length statistics come from
        ``corpus_tokens`` when provided, otherwise from the candidates.
        """
        docs = [_skill_tokens(rs.skill) for rs in candidates]
        stats_docs = corpus_tokens if corpus_tokens else docs
        n_docs = len(stats_docs)
        avg_dl = sum(len(d) for d in stats_docs) / n_docs if n_docs else 0.0

        doc_freq: Dict[str, int] = {}
        for doc in stats_docs:
            for term in set(doc):
                doc_freq[term] = doc_freq.get(term, 0) + 1

        scores: List[float] = []
        for doc in docs:
            tf: Dict[str, int] = {}
            for term in doc:
                tf[term] = tf.get(term, 0) + 1
            dl = len(doc)
            score = 0.0
            for term in set(query_terms):
                freq = tf.get(term, 0)
                if freq == 0:
                    continue
                df = doc_freq.get(term, 0)
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
                denom = freq + self.k1 * (1.0 - self.b + self.b * dl / avg_dl) if avg_dl else freq + self.k1
                score += idf * (freq * (self.k1 + 1.0)) / denom
            scores.append(score)
        return scores


class SkillRetriever:
    """Retrieve and fuse context for retrieval-augmented planning."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        skill_dag: Optional[SkillDAG] = None,
        cbkb: Optional[CBKB] = None,
        tool_registry: Optional[ToolRegistry] = None,
        data_sources: Optional[List[Dict[str, Any]]] = None,
        literature_retriever: Optional[LiteratureRetriever] = None,
        capability_index: Optional[CapabilityIndex] = None,
        rerank_min_score: float = 0.1,
        reranker: Optional[SkillReranker] = None,
    ):
        self.registry = skill_registry
        self.skill_dag = skill_dag
        # Anchor CBKB to the configured data dir (absolute). ``Path(".")`` breaks
        # as soon as the worker chdir's into a project workspace: the lazy
        # SkillRetriever/PlanEngine build then tried to create cbkb.db inside the
        # workspace and failed with "unable to open database file".
        self.cbkb = cbkb or CBKB(base_dir=Path(settings.data_dir))
        self.tool_registry = tool_registry
        self.data_sources = data_sources or []
        self.literature_retriever = literature_retriever
        self.capability_index = capability_index
        self.reranker = reranker or SkillReranker(min_score=rerank_min_score)

    async def retrieve(
        self,
        query: str,
        intent_type: str,
        top_k: int = 10,
        include_graph: bool = True,
        include_sops: bool = True,
        include_anomalies: bool = True,
        include_tools: bool = True,
        include_data_sources: bool = True,
        include_literature: bool = False,
        data_sources: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[str] = None,
    ) -> RetrievalContext:
        """Retrieve skills, tools, data sources, literature, SOPs, and anomaly context."""
        skills = self._retrieve_skills(query, top_k=top_k, include_graph=include_graph)
        skill_ids = {s.skill.id for s in skills}

        tools: List[RetrievedTool] = []
        if include_tools and self.tool_registry is not None:
            tools = self._retrieve_tools(query)
        tool_names = {t.name for t in tools}

        effective_data_sources = data_sources if data_sources is not None else self.data_sources
        retrieved_data_sources: List[RetrievedDataSource] = []
        if include_data_sources:
            retrieved_data_sources = self._retrieve_data_sources(query, effective_data_sources)
        data_source_ids = {d.id for d in retrieved_data_sources}

        literature: List[Dict[str, Any]] = []
        if include_literature and self.literature_retriever is not None:
            literature = await self.literature_retriever.retrieve(query)

        sops: List[Dict[str, Any]] = []
        if include_sops:
            sops = self._retrieve_sops(intent_type)
        sop_ids = {s.get("id") for s in sops}

        anomalies: List[Dict[str, Any]] = []
        if include_anomalies:
            anomalies = self._retrieve_anomalies(intent_type)

        lore: List[Dict[str, Any]] = []
        if skill_ids:
            lore = self._retrieve_parameter_lore(list(skill_ids))

        # Augment with the unified capability index (best-effort, additive).
        cap_results = await self._retrieve_capabilities(
            query=query,
            intent_type=intent_type,
            project_id=project_id,
            top_k=top_k,
        )
        for rs in cap_results.get("skills", []):
            if rs.skill.id not in skill_ids:
                skills.append(rs)
                skill_ids.add(rs.skill.id)
        for t in cap_results.get("tools", []):
            if t.name not in tool_names:
                tools.append(t)
                tool_names.add(t.name)
        for s in cap_results.get("sops", []):
            if s.get("id") not in sop_ids:
                sops.append(s)
                sop_ids.add(s.get("id"))
        for d in cap_results.get("data_sources", []):
            if d.id not in data_source_ids:
                retrieved_data_sources.append(d)
                data_source_ids.add(d.id)

        return RetrievalContext(
            query=query,
            intent_type=intent_type,
            skills=skills,
            tools=tools,
            data_sources=retrieved_data_sources,
            literature=literature,
            sops=sops,
            anomalies=anomalies,
            parameter_lore=lore,
        )

    def _retrieve_skills(
        self,
        query: str,
        top_k: int,
        include_graph: bool,
    ) -> List[RetrievedSkill]:
        """Retrieve skills via semantic search and optional SkillDAG boost.

        Both paths are reranked by the BM25 reranker: candidates below the
        reranker's ``min_score`` are dropped, and ``top_k`` is applied only
        after threshold filtering.
        """
        if self.skill_dag is not None and include_graph:
            dag_results = self.skill_dag.search(
                query=query,
                top_k=top_k,
                include_neighbors=True,
                exclude_conflicts=True,
            )
            candidates = [
                RetrievedSkill(
                    skill=r.skill,
                    semantic_score=r.semantic_score,
                    graph_boost=r.graph_boost,
                    conflict_warning=r.conflict_warning,
                    followed_by=[s for s, _ in self.skill_dag.get_followed_by(r.skill.id)] if self.skill_dag else [],
                    depends_on=self.skill_dag.get_dependencies(r.skill.id) if self.skill_dag else [],
                )
                for r in dag_results
            ]
            return self.reranker.rerank(
                query, candidates, top_k=top_k, corpus=self.registry.list_all()
            )

        # Fallback to plain registry search.  Keep the registry's recall
        # (semantic + legacy keyword substring) but attach the real semantic
        # scores instead of a hard-coded 1.0; the reranker re-scores anyway.
        scored = {
            skill.id: score
            for skill, score in self.registry.semantic_search(query, top_k=top_k * 2)
        }
        candidates = [
            RetrievedSkill(skill=skill, semantic_score=scored.get(skill.id, 0.0))
            for skill in self.registry.search(query)
        ]
        return self.reranker.rerank(
            query, candidates, top_k=top_k, corpus=self.registry.list_all()
        )

    async def _retrieve_capabilities(
        self,
        query: str,
        intent_type: str,
        project_id: Optional[str],
        top_k: int,
    ) -> Dict[str, List[Any]]:
        """Search the unified CapabilityIndex and map candidates to retrieval structs."""
        if self.capability_index is None:
            return {}

        try:
            candidates = await self.capability_index.search(
                query=query,
                top_k=top_k,
                item_types=[
                    CapabilityType.SKILL,
                    CapabilityType.TOOL,
                    CapabilityType.SOP,
                    CapabilityType.DATA_SOURCE,
                ],
                project_id=project_id,
            )
        except Exception:
            logger.warning("CapabilityIndex retrieval failed for query %r", query, exc_info=True)
            return {}

        skills: List[RetrievedSkill] = []
        tools: List[RetrievedTool] = []
        sops: List[Dict[str, Any]] = []
        data_sources: List[RetrievedDataSource] = []

        for candidate in candidates:
            payload = candidate.payload or {}
            if candidate.type == CapabilityType.SKILL:
                skill = next(
                    (s for s in self.registry.list_all() if s.id == candidate.id),
                    None,
                )
                if skill is None:
                    skill = SkillDefinition(
                        id=candidate.id,
                        name=candidate.name,
                        version=payload.get("version", "1.0.0"),
                        category=candidate.category or payload.get("category", "general"),
                        description=candidate.description,
                        metadata=payload.get("metadata", {}),
                    )
                skills.append(RetrievedSkill(skill=skill, semantic_score=candidate.score))

            elif candidate.type == CapabilityType.TOOL:
                tool_def: Optional[ToolDefinition] = None
                if self.tool_registry is not None:
                    tool_def = self.tool_registry.get(candidate.id)
                if tool_def is None:
                    tool_def = ToolDefinition(
                        name=candidate.id,
                        description=candidate.description,
                        input_schema=payload.get("input_schema", {"type": "object"}),
                        source=payload.get("source", "capability_index"),
                        risk_level=payload.get("risk_level", "low"),
                        metadata=payload.get("metadata", {}),
                    )
                tools.append(RetrievedTool(
                    name=tool_def.name,
                    description=tool_def.description,
                    input_schema=tool_def.input_schema,
                    risk_level=tool_def.risk_level,
                    source=tool_def.source,
                ))

            elif candidate.type == CapabilityType.SOP:
                sops.append({
                    "id": candidate.id,
                    "name": candidate.name,
                    "category": candidate.category,
                    "template": payload.get("template"),
                    "version": payload.get("version"),
                    "locked": payload.get("locked"),
                })

            elif candidate.type == CapabilityType.DATA_SOURCE:
                data_sources.append(RetrievedDataSource(
                    id=candidate.id,
                    path=payload.get("path", ""),
                    format=payload.get("format", ""),
                    description=candidate.description,
                ))

        return {
            "skills": skills,
            "tools": tools,
            "sops": sops,
            "data_sources": data_sources,
        }

    def _retrieve_sops(self, intent_type: str) -> List[Dict[str, Any]]:
        """Retrieve SOPs whose category matches the intent type."""
        try:
            sops = self.cbkb.list_sops(category=intent_type)
        except Exception:
            return []
        return [
            {
                "id": sop.id,
                "name": sop.name,
                "category": sop.category,
                "template": sop.template,
                "version": sop.version,
                "locked": sop.locked,
            }
            for sop in sops
        ]

    def _retrieve_anomalies(self, intent_type: str) -> List[Dict[str, Any]]:
        """Retrieve recent anomalies for the target domain."""
        try:
            records = self.cbkb.query_anomalies(phase_type=intent_type, limit=5)
        except Exception:
            return []
        return [
            {
                "id": r.id,
                "phase_type": r.phase_type,
                "summary": r.summary,
                "flags": r.flags,
                "recommendations": r.recommendations,
                "severity": r.severity,
            }
            for r in records
        ]

    def _retrieve_parameter_lore(self, skill_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieve parameter lore for the top retrieved skills."""
        lore: List[Dict[str, Any]] = []
        for skill_id in skill_ids[:5]:
            try:
                entries = self.cbkb.query_parameter_lore(skill_id=skill_id, limit=3)
            except Exception:
                continue
            for e in entries:
                lore.append({
                    "skill_id": e.skill_id,
                    "param_name": e.param_name,
                    "param_value": e.param_value,
                    "outcome_metric": e.outcome_metric,
                    "outcome_value": e.outcome_value,
                    "context": e.context,
                })
        return lore

    def _retrieve_tools(self, query: str) -> List[RetrievedTool]:
        """Retrieve tools whose description matches the query.

        Uses a simple substring heuristic plus a few cross-cutting category
        hints; can be replaced with embedding search once the tool registry
        stores embeddings.
        """
        if self.tool_registry is None:
            return []

        query_lower = query.lower()
        keywords = set(query_lower.split())

        # Cross-cutting hints: if the query smells like a lookup, include the
        # corresponding tool even if the literal keyword does not match its name.
        category_hints: Dict[str, List[str]] = {
            "pubmed_search": ["paper", "literature", "pubmed", "article", "reference"],
            "web_search": ["search", "web", "internet", "online", "find"],
            "file_read": ["read", "load", "open", "inspect"],
            "shell_exec": ["run", "execute", "command", "shell", "bash"],
        }

        scored: List[tuple[float, RetrievedTool]] = []
        for tool in self.tool_registry.list_all():
            text = f"{tool.name} {tool.description}".lower()
            score = float(sum(1 for kw in keywords if kw in text))
            for hint_tool, hint_terms in category_hints.items():
                if tool.name == hint_tool and any(term in query_lower for term in hint_terms):
                    score += 1.0

            if score > 0:
                scored.append((score, RetrievedTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    risk_level=tool.risk_level,
                    source=tool.source,
                )))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:10]]

    def _retrieve_data_sources(
        self,
        query: str,
        data_sources: Optional[List[Dict[str, Any]]] = None,
    ) -> List[RetrievedDataSource]:
        """Retrieve data sources relevant to the query."""
        sources = data_sources if data_sources is not None else self.data_sources
        keywords = set(query.lower().split())
        results: List[RetrievedDataSource] = []
        for ds in sources:
            text = f"{ds.get('id', '')} {ds.get('description', '')} {ds.get('format', '')}".lower()
            if any(kw in text for kw in keywords):
                results.append(RetrievedDataSource(
                    id=ds.get("id", ""),
                    path=ds.get("path", ""),
                    format=ds.get("format", ""),
                    description=ds.get("description", ""),
                ))
        return results


