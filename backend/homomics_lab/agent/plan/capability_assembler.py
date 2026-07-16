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
from homomics_lab.agent.intent.alias_registry import AliasRegistry
from homomics_lab.skills.capability_index import CapabilityIndex, CapabilityType
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry

logger = logging.getLogger(__name__)

# Generic file-format / biology terms that should not trigger explicit skill
# selection when a domain is already known.
_GENERIC_KEYWORDS = {
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
    OPEN_EXPLORATION_TEMPLATE_THRESHOLD = 0.45
    OPEN_EXPLORATION_CLEAR_STANDALONE_THRESHOLD = 0.75

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

    def __init__(
        self,
        capability_index: Optional[CapabilityIndex] = None,
        template_store: Optional[AnalysisTemplateStore] = None,
        skill_registry: Optional[SkillRegistry] = None,
        settings: Optional[Settings] = None,
        template_coverage_threshold: Optional[float] = None,
        standalone_score_threshold: Optional[float] = None,
        alias_registry: Optional[AliasRegistry] = None,
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
        self._alias_registry = alias_registry

    def _ensure_alias_registry(self) -> AliasRegistry:
        """Return the alias registry, building it from current registries if needed."""
        if self._alias_registry is None:
            from homomics_lab.domain.registry import get_domain_registry

            self._alias_registry = AliasRegistry.build(
                domains=get_domain_registry().list_all(),
                skills=self.skill_registry.list_all(),
            )
        return self._alias_registry

    async def assemble(
        self,
        intent: UserIntent,
        data_state: Optional[DataState] = None,
    ) -> CapabilityAssembly:
        """Return the best routing decision for ``intent``."""
        data_state = data_state or DataState()
        is_phase_level = self._ensure_alias_registry().is_phase_level(intent.analysis_type)

        # 0. Explicit skill target. When the user names a concrete skill (or the
        # classifier resolves the request to a registered skill_id), use it directly
        # instead of building a full domain pipeline or searching again.
        # Skip this shortcut when the intent is already narrowed to a domain phase
        # (e.g. descriptive_statistics): in that case the domain template or open
        # agent should decide how to fulfil the phase, not a keyword-matched skill.
        explicit_skill = None
        if not is_phase_level:
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
            result = CapabilityAssembly(
                route="cross_domain",
                domains=domains,
                reason=f"Multiple domains detected: {', '.join(domains)}",
            )
            logger.info("CapabilityAssembler route=%s reason=%s", result.route, result.reason)
            return result

        # 2. Domain template match.
        template, coverage = await self._match_template(intent, data_state)
        if template is not None:
            if coverage >= self.template_coverage_threshold:
                result = CapabilityAssembly(
                    route="domain_template",
                    domains=[template.domain] if template.domain else [],
                    template=template,
                    coverage=coverage,
                    reason=(
                        f"Template '{template.name}' covers {coverage:.0%} of intent signals"
                    ),
                )
                logger.info("CapabilityAssembler route=%s reason=%s", result.route, result.reason)
                return result
            # Open exploration mode weakens the domain gate so borderline
            # requests are handled by the open agent instead of forcing a
            # domain pipeline.
            if (
                self.settings.open_exploration_mode_enabled
                and coverage >= self.OPEN_EXPLORATION_TEMPLATE_THRESHOLD
            ):
                result = CapabilityAssembly(
                    route="open_agent",
                    domains=domains,
                    reason=(
                        f"Weak domain signal (coverage {coverage:.0%}); "
                        "routing to open agent"
                    ),
                )
                logger.info("CapabilityAssembler route=%s reason=%s", result.route, result.reason)
                return result

        # 3. Standalone / domain-agnostic skill match.
        # Only consider standalone skills when the intent lacks a concrete domain
        # signal.  Domain-specific requests should go through the domain strategy
        # (via open-agent fall-through) rather than being hijacked by generic
        # standalone capabilities.
        if not self._has_domain_signal(intent):
            skills, score = await self._match_standalone_skills(intent, data_state)
            if skills and score >= self.standalone_score_threshold:
                # In open exploration mode, only a clear standalone skill match
                # is allowed to bypass the open agent.
                if (
                    self.settings.open_exploration_mode_enabled
                    and score < self.OPEN_EXPLORATION_CLEAR_STANDALONE_THRESHOLD
                ):
                    result = CapabilityAssembly(
                        route="open_agent",
                        domains=domains,
                        reason=(
                            f"Uncertain standalone skill match ({score:.2f}); "
                            "routing to open agent"
                        ),
                    )
                    logger.info("CapabilityAssembler route=%s reason=%s", result.route, result.reason)
                    return result
                result = CapabilityAssembly(
                    route="standalone_skill",
                    prebuilt_skills=skills,
                    score=score,
                    reason=f"Standalone skill match score {score:.2f}",
                )
                logger.info("CapabilityAssembler route=%s reason=%s", result.route, result.reason)
                return result

        # 4. Open agent (with domain strategy as implicit fallback).
        result = CapabilityAssembly(
            route="open_agent",
            domains=domains,
            reason="No strong template or standalone skill match; delegating to open agent",
        )
        logger.info("CapabilityAssembler route=%s reason=%s", result.route, result.reason)
        return result

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

        registry = self._ensure_alias_registry()
        confirmed = 0
        for domain in domains:
            keywords = registry.get_domain_keywords(domain)
            keywords.add(domain.replace("-", " ").lower())
            keywords.add(domain.lower())
            if any(kw in message for kw in keywords):
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
        # 1. Strongest signal: a concrete skill_id or skill alias in intent.target.
        # If the classifier or caller explicitly names a registered skill, route
        # directly to it without requiring the id to appear in the user message.
        registry = self._ensure_alias_registry()
        target = intent.target
        if target:
            skill_id = registry.resolve_skill(target)
            if skill_id is None:
                # Allow raw skill ids that are not registered as aliases.
                skill_id = target
            skill = self.skill_registry.get(skill_id)
            if skill is not None:
                return skill

        message = (intent.original_message or "").lower()
        if not message:
            return None

        # 1b. Fast path: the message literally names the distinctive tail of a
        # skill id (e.g. "celltypist", "singler", "seurat"). This catches tool
        # names even when the alias registry's keyword scoring is too conservative.
        for skill in self.skill_registry.list_all():
            sid = skill.id.lower()
            # Use the most distinctive suffix of the skill id.
            distinctive = sid.split("-")[-1] if "-" in sid else sid
            if len(distinctive) >= 5 and distinctive in message:
                # Require the distinctive token to be a known tool/method name,
                # not a generic biology term.
                if distinctive not in _GENERIC_KEYWORDS:
                    return skill

        has_domain_signal = self._has_domain_signal(intent)

        # 2. Message-based matching via the canonical alias registry.
        # The registry already indexes skill ids, names, keywords, tags, and any
        # declared aliases, so we only need to disambiguate here.
        matched_keywords = registry.match_skills(message)
        matches: Dict[str, SkillDefinition] = {}
        for skill_id, aliases in matched_keywords.items():
            skill = self.skill_registry.get(skill_id)
            if skill is None:
                continue
            sid = skill.id.lower()
            sname = skill.name.lower()

            # Full id/name match is only treated as explicit when the classifier
            # did not already pin the request to a domain. This prevents a generic
            # phrase like "run single cell qc" from being hijacked by a skill
            # whose id happens to be "single_cell_qc".
            if not has_domain_signal and (sid in message or sname in message):
                matches[skill.id] = skill
                continue

            # Declared keywords/aliases (e.g. "celltypist") are distinctive tool
            # names and work even when a domain is present.  When a domain signal
            # is present we are much more conservative: ignore generic file-format
            # or biology terms and require the keyword to be part of the skill's
            # own identity (id/name) so we do not route a phase-level request
            # (e.g. descriptive_statistics) to an unrelated skill just because it
            # lists "h5ad" or "cell" as a keyword.
            hit_keywords: Set[str] = set()
            for kw in aliases:
                if has_domain_signal:
                    if kw in _GENERIC_KEYWORDS:
                        continue
                    if len(kw) < 5:
                        continue
                    # A domain-level request should not be hijacked by a skill
                    # whose id/name happens to appear literally in the message.
                    # Declared keywords/aliases (e.g. "celltypist") are still
                    # allowed because they are intentional tool references.
                    if kw == sid or kw == sname:
                        continue
                    if not (kw in sid or kw in sname):
                        continue
                hit_keywords.add(kw)

            if hit_keywords:
                matches[skill.id] = skill

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
            skill_id = skill.id.lower()
            skill_name = skill.name.lower()
            best = 0
            for kw in matched_keywords.get(skill.id, set()):
                # Bonus when the keyword is part of the skill's own id/name.
                in_identity = kw in skill_id or kw in skill_name
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
