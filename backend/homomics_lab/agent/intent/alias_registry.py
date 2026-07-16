"""Canonical alias registry for phases, skills, and domains.

HomomicsLab receives many informal user terms: "celltypist", "Louvain",
"质控", "UMAP", "空间转录组", etc.  Rather than scattering ad-hoc maps
throughout the codebase, ``AliasRegistry`` centralises the mapping from
aliases to canonical IDs.  It is populated from:

* ``DomainDefinition`` declarations (phase IDs + intent keywords)
* ``SkillDefinition`` metadata (skill ID, name, keywords, tags, aliases)
* A small built-in table of cross-domain phase aliases (e.g. ``pca`` → ``dim_reduction``)

The registry is intentionally read-only after construction: callers query it,
planners consume it, and a global singleton is rebuilt when domains/skills are
hot-reloaded.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from homomics_lab.domain.models import DomainDefinition
from homomics_lab.skills.models import SkillDefinition

logger = logging.getLogger(__name__)

# Cross-domain canonical phase aliases.  These are independent of any single
# domain.yaml and serve as a safety net when a domain declaration does not
# explicitly list every common synonym.
COMMON_PHASE_ALIASES: Dict[str, str] = {
    # QC / preprocessing
    "qc": "qc",
    "quality control": "qc",
    "质控": "qc",
    # Data IO (keep explicit English; avoid overly broad Chinese verbs that
    # appear in almost any analysis request, e.g. "读取此文件并做统计" should
    # route to the analysis phase, not create a redundant data_io task).
    "data_io": "data_io",
    "load": "data_io",
    "import": "data_io",
    "加载": "data_io",
    "导入": "data_io",
    # Normalization
    "normalization": "normalization",
    "normalize": "normalization",
    "归一化": "normalization",
    "标准化": "normalization",
    # Dimensionality reduction
    "dim_reduction": "dim_reduction",
    "dimensionality reduction": "dim_reduction",
    "降维": "dim_reduction",
    "pca": "dim_reduction",
    # Clustering
    "clustering": "clustering",
    "louvain": "clustering",
    "leiden": "clustering",
    "聚类": "clustering",
    # Annotation
    "annotation": "annotation",
    "cell_annotation": "annotation",
    "cell type annotation": "annotation",
    "annotate": "annotation",
    "细胞注释": "annotation",
    "细胞类型注释": "annotation",
    "注释": "annotation",
    # Differential expression
    # NOTE: "de" was removed because it is too short and matches unrelated
    # substrings such as "resolved", "describe", "dendritic", etc.
    "differential_expression": "differential_expression",
    "deg": "differential_expression",
    "差异表达": "differential_expression",
    "差异分析": "differential_expression",
    # Visualization
    "visualization": "visualization",
    "umap": "visualization",
    "plot": "visualization",
    "可视化": "visualization",
    # Descriptive statistics
    "descriptive_statistics": "descriptive_statistics",
    "exploration": "descriptive_statistics",
    "descriptive statistics": "descriptive_statistics",
    "summary statistics": "descriptive_statistics",
    "describe the data": "descriptive_statistics",
    "描述性统计": "descriptive_statistics",
    "数据概览": "descriptive_statistics",
    "统计概要": "descriptive_statistics",
    "基本统计": "descriptive_statistics",
}

# Domain display-name / keyword aliases.  These are used when a domain.yaml does
# not declare its own keywords, or as additional synonyms.
COMMON_DOMAIN_ALIASES: Dict[str, List[str]] = {
    "single-cell-transcriptomics": [
        "single-cell",
        "single cell",
        "scRNA",
        "scrna",
        "单细胞",
        "免疫细胞",
        "单细胞转录组",
    ],
    "spatial-transcriptomics": [
        "spatial",
        "visium",
        "xenium",
        "空间",
        "空间转录组",
    ],
    "metagenomics": ["metagenomics", "宏基因组", "16s", "16S", "amplicon"],
    "genomics": ["genomics", "基因组", "wgs", "whole genome"],
    "transcriptomics": ["transcriptomics", "转录组", "bulk rna", "rnaseq"],
    "proteomics": ["proteomics", "蛋白质组", "蛋白组"],
    "epigenomics": ["epigenomics", "表观基因组", "chip-seq", "atac-seq"],
}

# Terms that are too generic to be treated as skill aliases on their own.
_GENERIC_TOKENS: Set[str] = {
    "h5ad",
    ".h5ad",
    "rds",
    ".rds",
    "csv",
    ".csv",
    "tsv",
    ".tsv",
    "mtx",
    ".mtx",
    "fastq",
    "bam",
    "cell",
    "cells",
    "gene",
    "genes",
    "rna",
    "seq",
    "data",
    "file",
    "read",
    "读取",
    "文件",
    "数据",
}


@dataclass
class AliasRegistry:
    """Central alias registry for phases, skills, and domains."""

    # phase alias -> canonical phase id (global)
    phase_aliases: Dict[str, str] = field(default_factory=dict)
    # phase alias -> {domain: canonical phase id} (domain-scoped overrides)
    domain_phase_aliases: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # skill alias -> canonical skill id
    skill_aliases: Dict[str, str] = field(default_factory=dict)
    # domain alias -> canonical domain id
    domain_aliases: Dict[str, str] = field(default_factory=dict)
    # domain id -> set of keywords used for cross-domain confirmation
    domain_keywords: Dict[str, Set[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_phase_alias(
        self,
        alias: str,
        phase_id: str,
        domain: Optional[str] = None,
    ) -> None:
        """Register an alias for a canonical phase id."""
        key = alias.lower()
        if domain:
            self.domain_phase_aliases.setdefault(key, {})[domain] = phase_id
        else:
            self.phase_aliases[key] = phase_id

    def register_skill_alias(self, alias: str, skill_id: str) -> None:
        """Register an alias for a canonical skill id."""
        key = alias.lower()
        # First registration wins; this prevents a generic tag from shadowing a
        # more specific alias registered earlier.
        if key not in self.skill_aliases:
            self.skill_aliases[key] = skill_id

    def register_domain_alias(self, alias: str, domain_id: str) -> None:
        """Register an alias that resolves to a canonical domain id."""
        self.domain_aliases[alias.lower()] = domain_id

    def register_domain_keywords(self, domain_id: str, keywords: List[str]) -> None:
        """Associate cross-domain confirmation keywords with a domain."""
        self.domain_keywords.setdefault(domain_id, set()).update(
            k.lower() for k in keywords
        )

    def register_domain(self, domain: DomainDefinition) -> None:
        """Index all aliases derivable from a domain declaration."""
        domain_id = domain.domain

        # Domain identity
        self.register_domain_alias(domain_id, domain_id)
        display_name = getattr(domain, "display_name", None)
        if display_name:
            self.register_domain_alias(display_name.lower(), domain_id)

        # Phase IDs are aliases for themselves, both globally and scoped.
        phase_ids = {p.id.lower() for p in domain.phases}
        for phase in domain.phases:
            self.register_phase_alias(phase.id, phase.id)
            self.register_phase_alias(phase.id, phase.id, domain=domain_id)
            # Phase description is also indexed, but only scoped to the domain
            # to avoid a generic description leaking across domains.
            if phase.description:
                self.register_phase_alias(
                    phase.description.lower(), phase.id, domain=domain_id
                )

        # Intent analysis types and their keywords.
        for intent in domain.intents:
            analysis_type = intent.analysis_type
            # If the analysis type is itself a phase, register it as a phase alias.
            if analysis_type.lower() in phase_ids:
                self.register_phase_alias(analysis_type, analysis_type)
                self.register_phase_alias(
                    analysis_type, analysis_type, domain=domain_id
                )

            for keyword in intent.keywords:
                key = keyword.lower()
                # Try to map the keyword to a phase first.
                phase_id = COMMON_PHASE_ALIASES.get(key)
                if phase_id is None and key in phase_ids:
                    phase_id = next(p.id for p in domain.phases if p.id.lower() == key)
                if phase_id is not None:
                    self.register_phase_alias(keyword, phase_id)
                    self.register_phase_alias(keyword, phase_id, domain=domain_id)

        # Domain-level confirmation keywords.
        domain_kw: Set[str] = set(COMMON_DOMAIN_ALIASES.get(domain_id, []))
        for intent in domain.intents:
            domain_kw.update(k.lower() for k in intent.keywords)
        self.register_domain_keywords(domain_id, sorted(domain_kw))

    def register_skill(self, skill: SkillDefinition) -> None:
        """Index all aliases derivable from a skill definition."""
        sid = skill.id
        # Identity aliases always win and are registered first.
        self.register_skill_alias(sid, sid)
        self.register_skill_alias(skill.name, sid)

        for alias in skill.metadata.get("aliases", []):
            if isinstance(alias, str):
                self.register_skill_alias(alias, sid)

        for kw in skill.metadata.get("keywords", []):
            if isinstance(kw, str):
                self.register_skill_alias(kw, sid)

        for tag in skill.metadata.get("tags", []):
            if isinstance(tag, str):
                self.register_skill_alias(tag, sid)

    def register_common_aliases(self) -> None:
        """Register the built-in cross-domain phase/domain alias tables."""
        for alias, phase_id in COMMON_PHASE_ALIASES.items():
            self.register_phase_alias(alias, phase_id)
        for domain_id, keywords in COMMON_DOMAIN_ALIASES.items():
            self.register_domain_alias(domain_id, domain_id)
            self.register_domain_alias(domain_id.replace("-", " "), domain_id)
            self.register_domain_keywords(domain_id, keywords)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def resolve_phase(
        self,
        alias: str,
        domain: Optional[str] = None,
    ) -> Optional[str]:
        """Return the canonical phase id for an alias, or None."""
        key = alias.lower()
        if domain:
            scoped = self.domain_phase_aliases.get(key, {}).get(domain)
            if scoped:
                return scoped
        return self.phase_aliases.get(key)

    def resolve_skill(self, alias: str) -> Optional[str]:
        """Return the canonical skill id for an alias, or None."""
        return self.skill_aliases.get(alias.lower())

    def resolve_domain(self, alias: str) -> Optional[str]:
        """Return the canonical domain id for an alias, or None."""
        return self.domain_aliases.get(alias.lower())

    def is_phase_level(self, analysis_type: str) -> bool:
        """Return True when ``analysis_type`` resolves to a known phase."""
        return self.resolve_phase(analysis_type) is not None

    def get_domain_keywords(self, domain_id: str) -> Set[str]:
        """Return the confirmation keywords associated with a domain."""
        return set(self.domain_keywords.get(domain_id, set()))

    # ------------------------------------------------------------------
    # Message matching
    # ------------------------------------------------------------------
    def _sorted_aliases(self, alias_map: Dict[str, str]) -> List[Tuple[str, str]]:
        """Return aliases sorted longest-first so specific phrases win."""
        return sorted(alias_map.items(), key=lambda x: len(x[0]), reverse=True)

    @staticmethod
    def _alias_matches(alias: str, lowered: str) -> bool:
        """Return True when ``alias`` occurs in ``lowered`` as a real token.

        Short ASCII aliases (length <= 3) must appear at a word boundary on
        both sides.  This prevents ``de``/``deg``/``qc`` from matching inside
        unrelated words such as ``resolved`` or ``degree``.  Non-ASCII and
        longer aliases continue to use substring matching for phrase support.
        """
        if alias not in lowered:
            return False
        if len(alias) > 3 or not alias.isascii():
            return True
        # Short ASCII alias: require word boundary before and after.
        import re

        pattern = re.compile(r"(?:^|\W)" + re.escape(alias) + r"(?:$|\W)")
        return bool(pattern.search(lowered))

    def match_phases(
        self,
        message: str,
        domain: Optional[str] = None,
    ) -> Dict[str, Set[str]]:
        """Return a map of canonical phase id -> matched aliases found in message."""
        lowered = message.lower()
        result: Dict[str, Set[str]] = {}

        def add(alias: str, phase_id: str) -> None:
            result.setdefault(phase_id, set()).add(alias)

        # Scoped aliases first so they take precedence when a domain is known.
        if domain:
            for alias, per_domain in sorted(
                self.domain_phase_aliases.items(), key=lambda x: len(x[0]), reverse=True
            ):
                if domain in per_domain and self._alias_matches(alias, lowered):
                    add(alias, per_domain[domain])

        # Global aliases.
        for alias, phase_id in self._sorted_aliases(self.phase_aliases):
            if self._alias_matches(alias, lowered):
                add(alias, phase_id)

        return result

    def match_skills(self, message: str) -> Dict[str, Set[str]]:
        """Return a map of canonical skill id -> matched aliases found in message.

        Generic file-format/biology tokens are excluded because they are not
        distinctive enough to select a skill on their own.
        """
        lowered = message.lower()
        result: Dict[str, Set[str]] = {}
        for alias, skill_id in self._sorted_aliases(self.skill_aliases):
            if alias in _GENERIC_TOKENS:
                continue
            if self._alias_matches(alias, lowered):
                result.setdefault(skill_id, set()).add(alias)
        return result

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def build(
        cls,
        domains: Optional[List[DomainDefinition]] = None,
        skills: Optional[List[SkillDefinition]] = None,
    ) -> "AliasRegistry":
        """Build a registry from the supplied domains and skills."""
        registry = cls()
        registry.register_common_aliases()
        for domain in domains or []:
            registry.register_domain(domain)
        for skill in skills or []:
            registry.register_skill(skill)
        return registry


# Global singleton, rebuilt on domain/skill hot-reload.
_global_alias_registry: Optional[AliasRegistry] = None


def get_alias_registry(
    domains: Optional[List[DomainDefinition]] = None,
    skills: Optional[List[SkillDefinition]] = None,
    force_refresh: bool = False,
) -> AliasRegistry:
    """Return the global alias registry, building it lazily if needed.

    Callers may pass explicit ``domains``/``skills`` to force a rebuild; this is
    useful during tests and after hot-reload.
    """
    global _global_alias_registry
    if _global_alias_registry is None or force_refresh or domains is not None or skills is not None:
        # If no explicit lists are provided, pull from the global registries.
        if domains is None:
            from homomics_lab.domain.registry import get_domain_registry

            domains = get_domain_registry().list_all()
        if skills is None:
            from homomics_lab.skills.registry import get_default_registry

            skills = get_default_registry().list_all()
        _global_alias_registry = AliasRegistry.build(domains, skills)
    return _global_alias_registry


def reset_alias_registry() -> None:
    """Reset the global singleton.  Useful in tests."""
    global _global_alias_registry
    _global_alias_registry = None
