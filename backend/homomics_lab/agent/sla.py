"""Agent introspection / SLA estimator.

Given a user intent and the available skill registry, estimates whether the
agent can auto-execute the task, what skills/resources are needed, and how
much it might cost. This helps individual users understand the agent's
confidence before committing to a long-running workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from homomics_lab.agent.intent.models import UserIntent
from homomics_lab.config import settings
from homomics_lab.cost_control import CostController, get_cost_controller
from homomics_lab.skills.registry import SkillRegistry


@dataclass
class AgentSLA:
    """Self-assessment of the agent's ability to handle a request."""

    execution_mode: str  # "auto" | "confirm" | "human_required" | "direct_response"
    confidence: float  # 0.0 - 1.0
    estimated_steps: int
    required_skills: List[str]
    missing_skills: List[str]
    estimated_llm_cost_usd: Optional[float]
    estimated_compute_cost_usd: Optional[float]
    risks: List[str]
    explanation: str
    nfcore_pipeline: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "confidence": round(self.confidence, 2),
            "estimated_steps": self.estimated_steps,
            "required_skills": self.required_skills,
            "missing_skills": self.missing_skills,
            "estimated_llm_cost_usd": self.estimated_llm_cost_usd,
            "estimated_compute_cost_usd": self.estimated_compute_cost_usd,
            "risks": self.risks,
            "explanation": self.explanation,
            "nfcore_pipeline": self.nfcore_pipeline,
        }


class SLAEngine:
    """Estimate agent SLA for a user intent."""

    def __init__(
        self,
        skill_registry: Optional[SkillRegistry] = None,
        cost_controller: Optional[CostController] = None,
    ):
        self.skill_registry = skill_registry
        self.cost_controller = cost_controller or get_cost_controller()

    def assess(self, intent: UserIntent) -> AgentSLA:
        """Return an SLA estimate for the intent."""
        analysis_type = intent.analysis_type or "unknown"
        complexity = intent.complexity or "direct_response"

        # Direct response / QA / pubmed search can be answered directly.
        if complexity == "direct_response" or analysis_type in (
            "qa", "pubmed_search", "uniprot_search", "geo_search", "general_help"
        ):
            return AgentSLA(
                execution_mode="direct_response",
                confidence=0.95,
                estimated_steps=0,
                required_skills=[],
                missing_skills=[],
                estimated_llm_cost_usd=0.01,
                estimated_compute_cost_usd=0.0,
                risks=[],
                explanation="这是一个直接回答类问题，我可以立即回复。",
            )

        # Known curated templates or nf-core pipelines give highest auto-execute confidence.
        from homomics_lab.hpc.template_registry import get_template_registry
        from homomics_lab.config import settings
        from homomics_lab.nfcore_integration import get_nfcore_manager

        template = get_template_registry().resolve_for_intent(analysis_type)
        has_template = template is not None
        nfcore_suggestion = None
        if getattr(settings, "nfcore_enabled", True):
            nfcore_suggestion = get_nfcore_manager().suggest_pipeline(analysis_type)
            if nfcore_suggestion is not None and not has_template:
                has_template = True

        # Required skill set heuristic.
        required_skills = self._required_skills_for(analysis_type)
        available = set()
        missing = []
        if self.skill_registry is not None:
            available = {s.id for s in self.skill_registry.list_all()}
            missing = [s for s in required_skills if s not in available]

        # Decide execution mode.
        if missing:
            execution_mode = "human_required"
            confidence = 0.3
            explanation = (
                f"当前缺少执行该任务所需的关键 skill：{', '.join(missing)}。"
                "需要您补充 skill 或人工介入。"
            )
        elif has_template:
            execution_mode = "auto"
            confidence = 0.9
            if nfcore_suggestion is not None:
                explanation = (
                    f"nf-core 流程 '{nfcore_suggestion}' 匹配该分析类型，"
                    "我可以自动下载/缓存并运行该流程。"
                )
            else:
                explanation = (
                    "已有经过验证的 Nextflow 模板匹配该分析类型，我可以自动编排并运行。"
                )
        elif complexity == "single_step":
            execution_mode = "auto"
            confidence = 0.85
            explanation = "这是单步任务，我可以直接调用 skill 执行。"
        else:
            execution_mode = "confirm"
            confidence = 0.7
            explanation = (
                "这是一个多步骤工作流。我可以生成计划并执行，但建议您先审阅计划。"
            )

        # Cost estimate (rough upper bound).
        snapshot = self.cost_controller.get_snapshot()
        llm_cost = self._estimate_llm_cost(complexity, has_template)
        compute_cost = self._estimate_compute_cost(analysis_type)
        risks = self._risks_for(analysis_type, missing)

        return AgentSLA(
            execution_mode=execution_mode,
            confidence=confidence,
            estimated_steps=self._estimate_steps(complexity, has_template),
            required_skills=required_skills,
            missing_skills=missing,
            estimated_llm_cost_usd=llm_cost,
            estimated_compute_cost_usd=compute_cost,
            risks=risks,
            explanation=explanation,
            nfcore_pipeline=nfcore_suggestion,
        )

    def _required_skills_for(self, analysis_type: str) -> List[str]:
        mapping = {
            "single_cell_analysis": ["scanpy_qc", "scanpy_normalize", "scanpy_cluster"],
            "spatial_analysis": ["spatial_qc", "spatial_cluster", "spatial_deconvolve"],
            "metagenomics_analysis": ["metagenomics_qc", "metagenomics_taxonomy"],
            "rnaseq_analysis": ["fastp", "salmon_quant", "multiqc"],
        }
        return mapping.get(analysis_type, [])

    def _estimate_steps(self, complexity: str, has_template: bool) -> int:
        if has_template:
            return 3
        if complexity == "single_step":
            return 1
        if complexity == "workflow":
            return 5
        return 2

    def _estimate_llm_cost(self, complexity: str, has_template: bool) -> float:
        if has_template:
            return 0.02
        if complexity == "single_step":
            return 0.05
        if complexity == "workflow":
            return 0.2
        return 0.05

    def _estimate_compute_cost(self, analysis_type: str) -> float:
        # Rough cost for a typical run (USD).
        mapping = {
            "single_cell_analysis": 0.5,
            "spatial_analysis": 1.0,
            "metagenomics_analysis": 2.0,
            "rnaseq_analysis": 1.5,
        }
        return mapping.get(analysis_type, 0.1)

    def _risks_for(self, analysis_type: str, missing_skills: List[str]) -> List[str]:
        risks = []
        if missing_skills:
            risks.append("缺少关键 skill，执行可能失败或结果不完整")
        if analysis_type in ("rnaseq_analysis", "metagenomics_analysis"):
            risks.append("大型 NGS 任务可能消耗较多计算资源和存储")
        if analysis_type == "single_cell_analysis":
            risks.append("细胞数量、批次效应可能影响聚类质量")
        if not settings.force_sandbox:
            risks.append("当前未强制沙箱，代码执行存在安全风险")
        return risks
