"""SkillRetriever — retrieval-augmented planning context.

Combines multiple information sources into a single retrieval context that
feeds into PlanEngine and CodeAct:
  1. Semantic search over the skill registry
  2. SkillDAG graph neighbours and relationship warnings
  3. CBKB Lab SOPs for the target domain
  4. CBKB anomaly archive for known failure modes
  5. CBKB parameter lore for proven parameter choices
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.agent.literature_retriever import LiteratureRetriever
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG
from homomics_lab.tools.registry import ToolRegistry


@dataclass
class RetrievedSkill:
    """A skill retrieved together with graph-derived context."""

    skill: SkillDefinition
    semantic_score: float
    graph_boost: float = 0.0
    conflict_warning: Optional[str] = None
    followed_by: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)


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
    ):
        self.registry = skill_registry
        self.skill_dag = skill_dag
        self.cbkb = cbkb or CBKB(base_dir=Path("."))
        self.tool_registry = tool_registry
        self.data_sources = data_sources or []
        self.literature_retriever = literature_retriever

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
    ) -> RetrievalContext:
        """Retrieve skills, tools, data sources, literature, SOPs, and anomaly context."""
        skills = self._retrieve_skills(query, top_k=top_k, include_graph=include_graph)
        skill_ids = [s.skill.id for s in skills]

        tools: List[RetrievedTool] = []
        if include_tools and self.tool_registry is not None:
            tools = self._retrieve_tools(query)

        effective_data_sources = data_sources if data_sources is not None else self.data_sources
        retrieved_data_sources: List[RetrievedDataSource] = []
        if include_data_sources:
            retrieved_data_sources = self._retrieve_data_sources(query, effective_data_sources)

        literature: List[Dict[str, Any]] = []
        if include_literature and self.literature_retriever is not None:
            literature = await self.literature_retriever.retrieve(query)

        sops: List[Dict[str, Any]] = []
        if include_sops:
            sops = self._retrieve_sops(intent_type)

        anomalies: List[Dict[str, Any]] = []
        if include_anomalies:
            anomalies = self._retrieve_anomalies(intent_type)

        lore: List[Dict[str, Any]] = []
        if skill_ids:
            lore = self._retrieve_parameter_lore(skill_ids)

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
        """Retrieve skills via semantic search and optional SkillDAG boost."""
        if self.skill_dag is not None and include_graph:
            dag_results = self.skill_dag.search(
                query=query,
                top_k=top_k,
                include_neighbors=True,
                exclude_conflicts=True,
            )
            return [
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

        # Fallback to plain registry semantic search
        results: List[RetrievedSkill] = []
        for skill in self.registry.search(query):
            results.append(RetrievedSkill(skill=skill, semantic_score=1.0))
            if len(results) >= top_k:
                break
        return results

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


