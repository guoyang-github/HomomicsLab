"""Capability-first routing assembler.

Decides which planner should handle a user intent by progressively matching
against structured capabilities:

1. Multi-domain composition — when the intent names two or more domains.
2. Domain template — when an indexed analysis template covers the intent
   (coverage >= 0.7 by default).
3. Standalone skill — when a domain-agnostic skill matches strongly
   (score >= 0.65 by default).
4. Open agent — everything else; domain strategy remains the implicit fallback
   when the open agent declines the request.

The assembler is intentionally stateless and cheap to construct.  It prefers
the ``CapabilityIndex`` for retrieval but degrades gracefully to the
``AnalysisTemplateStore`` and ``SkillRegistry`` when the index is unavailable.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.models import DataState
from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
from homomics_lab.config import Settings, settings as default_settings
from homomics_lab.skills.capability_index import CapabilityIndex, CapabilityType
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry

logger = logging.getLogger(__name__)


@dataclass
class CapabilityAssembly:
    """Decision produced by ``CapabilityAssembler``.

    The route tells ``TaskDecomposer`` which planner to invoke.  Optional
    fields (``template``, ``prebuilt_skills``) are hints that avoid redundant
    retrieval by the downstream planner.
    """

    route: str  # cross_domain | domain_template | standalone_skill | open_agent
    domains: List[str] = field(default_factory=list)
    template: Optional[AnalysisTemplate] = None
    prebuilt_skills: List[SkillDefinition] = field(default_factory=list)
    coverage: float = 0.0
    score: float = 0.0
    reason: str = ""


class CapabilityAssembler:
    """Assemble a capability-first routing decision for an intent."""

    DEFAULT_TEMPLATE_COVERAGE_THRESHOLD = 0.7
    DEFAULT_STANDALONE_SCORE_THRESHOLD = 0.5

    # Analysis types that are too broad to be treated as domain signals.
    _BROAD_ANALYSIS_TYPES = {
        "general",
        "builtin_analysis",
        "analysis",
        "unknown",
        "unknown_type",
    }

    # Well-known cross-domain ordering used when multiple domains are detected.
    _DOMAIN_ORDER = [
        "single-cell-transcriptomics",
        "spatial-transcriptomics",
        "metagenomics",
        "genomics",
        "transcriptomics",
        "proteomics",
        "epigenomics",
    ]

    # Keywords that must appear in the original message for a domain to count
    # toward cross-domain composition.  This prevents an LLM-decomposed sub-intent
    # from silently promoting a request to cross-domain when the user only talked
    # about one domain.
    _DOMAIN_KEYWORDS: Dict[str, List[str]] = {
        "single-cell-transcriptomics": [
            "single-cell",
            "single cell",
            "scRNA",
            "scrna",
            "单细胞",
            "免疫细胞",
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

    def __init__(
        self,
        capability_index: Optional[CapabilityIndex] = None,
        template_store: Optional[AnalysisTemplateStore] = None,
        skill_registry: Optional[SkillRegistry] = None,
        settings: Optional[Settings] = None,
        template_coverage_threshold: Optional[float] = None,
        standalone_score_threshold: Optional[float] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.capability_index = capability_index
        self.template_store = template_store or AnalysisTemplateStore(settings=self.settings)
        self.skill_registry = skill_registry or get_default_registry()
        self.template_coverage_threshold = (
            template_coverage_threshold
            if template_coverage_threshold is not None
            else self.DEFAULT_TEMPLATE_COVERAGE_THRESHOLD
        )
        self.standalone_score_threshold = (
            standalone_score_threshold
            if standalone_score_threshold is not None
            else self.DEFAULT_STANDALONE_SCORE_THRESHOLD
        )

    async def assemble(
        self,
        intent: UserIntent,
        data_state: Optional[DataState] = None,
    ) -> CapabilityAssembly:
        """Return the best routing decision for ``intent``."""
        data_state = data_state or DataState()

        # 0. Explicit skill target. When the user names a concrete skill (or the
        # classifier resolves the request to a registered skill_id), use it directly
        # instead of building a full domain pipeline or searching again.
        explicit_skill = self._resolve_explicit_target_skill(intent)
        if explicit_skill is not None:
            return CapabilityAssembly(
                route="standalone_skill",
                prebuilt_skills=[explicit_skill],
                score=1.0,
                reason=f"Explicit skill target '{explicit_skill.id}'",
            )

        # 1. Multi-domain composition.
        domains = self._detect_domains(intent)
        if len(domains) >= 2 and self._message_confirms_cross_domain(intent, domains):
            return CapabilityAssembly(
                route="cross_domain",
                domains=domains,
                reason=f"Multiple domains detected: {', '.join(domains)}",
            )

        # 2. Domain template match.
        template, coverage = await self._match_template(intent, data_state)
        if template is not None and coverage >= self.template_coverage_threshold:
            return CapabilityAssembly(
                route="domain_template",
                domains=[template.domain] if template.domain else [],
                template=template,
                coverage=coverage,
                reason=(
                    f"Template '{template.name}' covers {coverage:.0%} of intent signals"
                ),
            )

        # 3. Standalone / domain-agnostic skill match.
        # Only consider standalone skills when the intent lacks a concrete domain
        # signal.  Domain-specific requests should go through the domain strategy
        # (via open-agent fall-through) rather than being hijacked by generic
        # standalone capabilities.
        if not self._has_domain_signal(intent):
            skills, score = await self._match_standalone_skills(intent, data_state)
            if skills and score >= self.standalone_score_threshold:
                return CapabilityAssembly(
                    route="standalone_skill",
                    prebuilt_skills=skills,
                    score=score,
                    reason=f"Standalone skill match score {score:.2f}",
                )

        # 4. Open agent (with domain strategy as implicit fallback).
        return CapabilityAssembly(
            route="open_agent",
            domains=domains,
            reason="No strong template or standalone skill match; delegating to open agent",
        )

    @classmethod
    def _detect_domains(cls, intent: UserIntent) -> List[str]:
        """Return ordered distinct domains referenced by ``intent``."""
        domains: List[str] = []
        seen: Set[str] = set()

        def add(domain: Optional[str]) -> None:
            if not domain:
                return
            if domain not in seen:
                seen.add(domain)
                domains.append(domain)

        add(intent.domain)
        for sub in intent.sub_intents:
            add(sub.domain)

        structured = getattr(intent, "structured_intent", None)
        if structured is not None:
            add(getattr(structured, "domain", None))
            for sub in getattr(structured, "sub_intents", []) or []:
                add(getattr(sub, "domain", None))

        order_index = {d: i for i, d in enumerate(cls._DOMAIN_ORDER)}

        def sort_key(domain: str) -> int:
            return order_index.get(domain, len(cls._DOMAIN_ORDER))

        return sorted(domains, key=sort_key)

    def _has_domain_signal(self, intent: UserIntent) -> bool:
        """Return True when the intent names a concrete analysis domain."""
        if intent.domain is not None:
            return True
        if intent.analysis_type not in self._BROAD_ANALYSIS_TYPES:
            return True
        for sub in intent.sub_intents:
            if sub.domain is not None:
                return True
            if sub.analysis_type not in self._BROAD_ANALYSIS_TYPES:
                return True
        structured = getattr(intent, "structured_intent", None)
        if structured is not None:
            if getattr(structured, "domain", None) is not None:
                return True
            if getattr(structured, "analysis_type", None) not in self._BROAD_ANALYSIS_TYPES:
                return True
        return False

    def _message_confirms_cross_domain(
        self,
        intent: UserIntent,
        domains: List[str],
    ) -> bool:
        """Return True when the user's message explicitly supports all domains.

        This guards against LLM sub-intent decomposition inventing a second
        domain (e.g. treating the word "比较" as spatial-transcriptomics) and
        triggering an unwanted cross-domain workflow.
        """
        message = (intent.original_message or "").lower()
        if not message:
            # No original message to verify against; be conservative.
            return False

        confirmed = 0
        for domain in domains:
            keywords = self._DOMAIN_KEYWORDS.get(domain, [domain])
            if any(kw.lower() in message for kw in keywords):
                confirmed += 1
            elif domain.replace("-", " ").lower() in message:
                confirmed += 1

        # Require every detected domain to be confirmed by the message.
        return confirmed >= len(domains)

    def _resolve_explicit_target_skill(
        self,
        intent: UserIntent,
    ) -> Optional[SkillDefinition]:
        """Return the skill directly referenced by ``intent.target`` or message.

        A concrete skill_id in ``intent.target`` is the strongest routing signal:
        it lets the user say "use CellTypist" and get a one-step plan instead of
        the full single-cell pipeline. If ``target`` is not a skill_id, we also
        check whether the original message explicitly names a skill (full id/name
        for requests without a domain signal, or declared keywords/aliases for
        tool names like CellTypist even within a domain).
        """
        # 1. Strongest signal: the classifier resolved the request to a skill_id.
        target = intent.target
        if target:
            skill = self.skill_registry.get(target)
            if skill is not None:
                return skill

        message = (intent.original_message or "").lower()
        if not message:
            return None

        has_domain_signal = self._has_domain_signal(intent)

        # 2. Message-based matching. Track each skill and the keywords that matched
        # so we can disambiguate when several skills share generic tokens.
        matches: Dict[str, SkillDefinition] = {}
        matched_keywords: Dict[str, Set[str]] = {}

        for skill in self.skill_registry.list_all():
            sid = skill.id.lower()
            sname = skill.name.lower()

            # Full id/name match is only treated as explicit when the classifier
            # did not already pin the request to a domain. This prevents a generic
            # phrase like "run single cell qc" from being hijacked by a skill
            # whose id happens to be "single_cell_qc".
            if not has_domain_signal and (sid in message or sname in message):
                matches[skill.id] = skill
                matched_keywords.setdefault(skill.id, set()).add(sid if sid in message else sname)
                continue

            # Declared keywords/aliases (e.g. "celltypist") are distinctive tool
            # names and work even when a domain is present.
            keywords: Set[str] = set()
            for tag in skill.metadata.get("tags", []):
                if isinstance(tag, str) and len(tag) > 2:
                    keywords.add(tag.lower())
            for kw in skill.metadata.get("keywords", []):
                if isinstance(kw, str) and len(kw) > 2:
                    keywords.add(kw.lower())

            hit_keywords = {kw for kw in keywords if kw in message}
            if hit_keywords:
                matches[skill.id] = skill
                matched_keywords.setdefault(skill.id, set()).update(hit_keywords)

        if not matches:
            return None

        unique = list(matches.values())

        # Unique, unambiguous match -> use it.
        if len(unique) == 1:
            return unique[0]

        # Disambiguate multiple keyword matches by keyword specificity.
        # Longer, distinctive keywords (e.g. "celltypist") beat short or generic
        # tokens (e.g. "h5ad", "data"). A clear winner is returned only when its
        # best keyword is substantially more specific than the runner-up.
        def _skill_score(skill: SkillDefinition) -> int:
            sid = skill.id.lower()
            sname = skill.name.lower()
            best = 0
            for kw in matched_keywords.get(skill.id, set()):
                # Bonus when the keyword is part of the skill's own id/name.
                in_identity = kw in sid or kw in sname
                score = len(kw) + (3 if in_identity else 0)
                best = max(best, score)
            return best

        scored = sorted(
            ((s, _skill_score(s)) for s in unique),
            key=lambda x: x[1],
            reverse=True,
        )
        if scored[0][1] > 0:
            top_score = scored[0][1]
            second_score = scored[1][1] if len(scored) > 1 else 0
            # Clear winner: at least 4 points ahead or 1.5x the runner-up.
            if top_score - second_score >= 4 or (
                second_score > 0 and top_score / second_score >= 1.5
            ):
                return scored[0][0]

        # Ambiguous: let semantic/standalone routing handle it instead.
        return None

    async def _match_template(
        self,
        intent: UserIntent,
        data_state: DataState,
    ) -> Tuple[Optional[AnalysisTemplate], float]:
        """Find the best matching analysis template and its coverage score."""
        candidates: List[Tuple[AnalysisTemplate, float]] = []

        if self.capability_index is not None:
            try:
                cap_results = await self.capability_index.search_by_intent(
                    intent,
                    data_state=data_state,
                    item_types=[CapabilityType.TEMPLATE],
                    top_k=10,
                )
                for cand in cap_results:
                    try:
                        template = AnalysisTemplate.from_dict(cand.payload)
                    except Exception:
                        continue
                    coverage = self._template_coverage(intent, template)
                    candidates.append((template, coverage))
            except Exception as exc:
                logger.warning("Template search via capability index failed: %s", exc)

        # Fallback: scan the file-backed template store directly.
        if not candidates:
            try:
                for template in self.template_store.list_templates():
                    coverage = self._template_coverage(intent, template)
                    candidates.append((template, coverage))
            except Exception as exc:
                logger.warning("Template store scan failed: %s", exc)

        if not candidates:
            return None, 0.0

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

    @staticmethod
    def _template_coverage(intent: UserIntent, template: AnalysisTemplate) -> float:
        """Compute token-level coverage of template intents by intent signals."""
        applicable = template.applicable_intents or []
        if not applicable:
            return 0.0

        signals = set()
        for text in [
            intent.analysis_type,
            intent.target or "",
            intent.domain or "",
            intent.original_message or "",
            *(
                intent.metadata.get("keywords", [])
                if isinstance(intent.metadata, dict)
                else []
            ),
            *(intent.domain_knowledge or []),
        ]:
            if isinstance(text, str):
                signals.update(text.lower().split())

        for sub in intent.sub_intents:
            for text in [
                sub.analysis_type,
                sub.target or "",
                sub.domain or "",
                sub.original_message or "",
            ]:
                if isinstance(text, str):
                    signals.update(text.lower().split())

        applicable_tokens: Set[str] = set()
        for intent_text in applicable:
            applicable_tokens.update(intent_text.lower().split())

        if not applicable_tokens:
            return 0.0

        matches = sum(1 for token in applicable_tokens if token in signals)
        return matches / len(applicable_tokens)

    async def _match_standalone_skills(
        self,
        intent: UserIntent,
        data_state: DataState,
    ) -> Tuple[List[SkillDefinition], float]:
        """Find the best matching standalone skills and the top score.

        Candidates are gathered from the capability index, semantic search and
        keyword search.  The highest score across all sources is kept for each
        skill so that a strong keyword match can compensate for a weak dense
        embedding score on small registries.
        """
        scores: Dict[str, float] = {}

        if self.capability_index is not None:
            try:
                cap_results = await self.capability_index.search_by_intent(
                    intent,
                    data_state=data_state,
                    item_types=[CapabilityType.SKILL],
                    top_k=10,
                )
                for cand in cap_results:
                    skill = self.skill_registry.get(cand.id)
                    if skill is None or not skill.is_standalone:
                        continue
                    scores[skill.id] = max(scores.get(skill.id, 0.0), cand.score)
            except Exception as exc:
                logger.warning("Standalone skill search via capability index failed: %s", exc)

        query = intent.original_message or intent.analysis_type
        if query:
            # Semantic search.
            try:
                matches = self.skill_registry.semantic_search(query, top_k=10)
            except Exception:
                matches = []
            for skill, score in matches:
                if not skill.is_standalone:
                    continue
                scores[skill.id] = max(scores.get(skill.id, 0.0), score)

            # Keyword search as a backstop for exact-name/description matches.
            keyword_hits = self.skill_registry.search(query)
            for skill in keyword_hits:
                if not skill.is_standalone:
                    continue
                scores[skill.id] = max(scores.get(skill.id, 0.0), 0.55)

        if not scores:
            return [], 0.0

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = [self.skill_registry.get(sid) for sid, _ in ranked[:3]]
        selected = [s for s in selected if s is not None]
        top_score = ranked[0][1] if ranked else 0.0
        return selected, top_score
