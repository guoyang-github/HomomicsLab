"""LightweightDebate — short multi-agent debate for ambiguous decisions."""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from homomics_lab.agent.core.dynamic_agent import DynamicAgent
from homomics_lab.llm_client import LLMClient


@dataclass
class DebateOption:
    """A candidate option produced by the debate."""

    id: str
    label: str
    description: str = ""
    proposer: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "proposer": self.proposer,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class DebateResult:
    """Result of a lightweight debate."""

    topic: str
    options: List[DebateOption]
    recommendation: Optional[DebateOption] = None
    round_summaries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "options": [o.to_dict() for o in self.options],
            "recommendation": self.recommendation.to_dict() if self.recommendation else None,
            "round_summaries": self.round_summaries,
            "metadata": self.metadata,
        }


class DebateJudge(ABC):
    """Abstract judge that scores a debate option from an expert's perspective."""

    @abstractmethod
    async def score(
        self,
        expert: DynamicAgent,
        option: DebateOption,
        context: Dict[str, Any],
    ) -> float:
        """Return a score in [0.0, 1.0] for ``option`` from ``expert``'s view."""
        ...


class RuleBasedDebateJudge(DebateJudge):
    """Deterministic, rule-based debate judge.

    Fast and fully reproducible; used as the default and as a fallback for the
    LLM-based judge.
    """

    async def score(
        self,
        expert: DynamicAgent,
        option: DebateOption,
        context: Dict[str, Any],
    ) -> float:
        return self._score_sync(expert, option, context)

    @staticmethod
    def _score_sync(
        expert: DynamicAgent,
        option: DebateOption,
        context: Dict[str, Any],
    ) -> float:
        """Score an option from a single expert's perspective."""
        role = expert.role
        skill_hint = option.metadata.get("skill") or option.id

        # Direct skill match (including wildcards) gives high score.
        if skill_hint and (
            skill_hint in role.allowed_skills
            or any(
                s.endswith("*") and skill_hint.startswith(s[:-1])
                for s in role.allowed_skills
            )
        ):
            return 0.9

        # Category match gives medium score.
        category = option.metadata.get("category")
        if category and category in role.allowed_skill_categories:
            return 0.7

        # Generalists give a neutral score.
        if not role.allowed_skills and not role.allowed_skill_categories:
            return 0.6

        # Otherwise low score.
        return 0.3


class LLMDebateJudge(DebateJudge):
    """LLM-based debate judge with rule-based fallback.

    Asks an LLM to score how well an option fits an expert's role, parses the
    structured JSON response, and falls back to :class:`RuleBasedDebateJudge` on
    any parsing or validation failure.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        fallback_judge: Optional[DebateJudge] = None,
    ):
        self._llm_client = llm_client
        self._fallback_judge = fallback_judge or RuleBasedDebateJudge()

    async def score(
        self,
        expert: DynamicAgent,
        option: DebateOption,
        context: Dict[str, Any],
    ) -> float:
        try:
            prompt = self._build_prompt(expert, option, context)
            response = await self._llm_client.chat_completion(
                [
                    {"role": "system", "content": "You are an impartial debate judge."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            data = json.loads(response)
            score = float(data["score"])
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Score {score} out of [0.0, 1.0] range")
            return score
        except Exception:
            return await self._fallback_judge.score(expert, option, context)

    @staticmethod
    def _build_prompt(
        expert: DynamicAgent,
        option: DebateOption,
        context: Dict[str, Any],
    ) -> str:
        role = expert.role
        topic = context.get("topic", "")
        user_message = context.get("user_message", "")
        allowed_skills = ", ".join(role.allowed_skills) or "generalist"
        allowed_categories = ", ".join(role.allowed_skill_categories) or "any"
        return (
            "You are a debate judge evaluating how well an option matches an expert's role.\n\n"
            f"Debate topic: {topic}\n"
            f"User message: {user_message}\n\n"
            f"Expert role ID: {role.role_id}\n"
            f"Expert name: {role.name}\n"
            f"Expert description: {role.description}\n"
            f"Expert allowed skills: {allowed_skills}\n"
            f"Expert allowed skill categories: {allowed_categories}\n\n"
            f"Option ID: {option.id}\n"
            f"Option label: {option.label}\n"
            f"Option description: {option.description}\n"
            f"Option metadata: {option.metadata}\n\n"
            'Return a JSON object with exactly two keys: '
            '{"score": <float between 0.0 and 1.0>, "reason": "<brief explanation>"}.'
        )


class LightweightDebate:
    """Run a 1-2 round debate among experts and let the Supervisor recommend.

    The debate is deterministic and rule-based by default so that it is fast and
    testable. In production the scoring can be replaced with an LLM-based judge.
    """

    def __init__(
        self,
        supervisor: Optional[Any] = None,
        experts: Optional[List[DynamicAgent]] = None,
        max_rounds: int = 2,
        auto_decide_threshold: float = 0.8,
        auto_decide_gap: float = 0.2,
        judge: Optional[DebateJudge] = None,
    ):
        self.supervisor = supervisor
        self.experts = experts or []
        self.max_rounds = max(1, max_rounds)
        self.auto_decide_threshold = auto_decide_threshold
        self.auto_decide_gap = auto_decide_gap
        self.judge = judge or RuleBasedDebateJudge()

    async def run(
        self,
        topic: str,
        candidates: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> DebateResult:
        """Run the debate and return options + optional recommendation."""
        context = context or {}
        score_context = {**context, "topic": topic}
        options = [
            DebateOption(
                id=c.get("id") or str(i),
                label=c.get("label", ""),
                description=c.get("description", ""),
                proposer=c.get("proposer", ""),
                metadata=c.get("metadata", {}),
            )
            for i, c in enumerate(candidates)
        ]

        round_summaries: List[str] = []

        for round_idx in range(self.max_rounds):
            round_scores: Dict[str, List[float]] = {opt.id: [] for opt in options}
            for expert in self.experts:
                for opt in options:
                    score = await self.judge.score(expert, opt, score_context)
                    round_scores[opt.id].append(score)

            # Update running average score per option.
            for opt in options:
                scores = round_scores[opt.id]
                avg = sum(scores) / len(scores) if scores else 0.0
                # Simple running average across rounds.
                opt.score = (opt.score * round_idx + avg) / (round_idx + 1)

            summary = f"Round {round_idx + 1}: " + ", ".join(
                f"{opt.label}={opt.score:.2f}" for opt in options
            )
            round_summaries.append(summary)

            # Supervisor can boost the best-fitting option.
            if self.supervisor is not None:
                options = self._supervisor_adjust(options, context)

            top = sorted(options, key=lambda o: o.score, reverse=True)
            if len(top) >= 2 and top[0].score >= self.auto_decide_threshold:
                if top[0].score - top[1].score >= self.auto_decide_gap:
                    break

        sorted_options = sorted(options, key=lambda o: o.score, reverse=True)
        recommendation = sorted_options[0] if sorted_options else None
        if recommendation and len(sorted_options) >= 2:
            if recommendation.score < self.auto_decide_threshold:
                recommendation = None
            elif sorted_options[1].score > recommendation.score - self.auto_decide_gap:
                recommendation = None
        elif recommendation and recommendation.score < self.auto_decide_threshold:
            recommendation = None

        return DebateResult(
            topic=topic,
            options=sorted_options,
            recommendation=recommendation,
            round_summaries=round_summaries,
            metadata={"rounds": len(round_summaries)},
        )

    @staticmethod
    def _score_option(expert: DynamicAgent, option: DebateOption, context: Dict[str, Any]) -> float:
        """Backward-compatible synchronous scoring helper.

        Delegates to :class:`RuleBasedDebateJudge`.
        """
        return RuleBasedDebateJudge._score_sync(expert, option, context)

    def _supervisor_adjust(self, options: List[DebateOption], context: Dict[str, Any]) -> List[DebateOption]:
        """Supervisor applies a small bonus to the option best aligned with context."""
        if not options:
            return options

        # Prefer options whose id matches the user's explicit mention, if any.
        user_keywords = set(str(context.get("user_message", "")).lower().split())
        for opt in options:
            if any(kw in opt.label.lower() or opt.id.lower() for kw in user_keywords):
                opt.score = min(1.0, opt.score + 0.05)

        return options

    @staticmethod
    def candidates_from_intents(intents: List[Any]) -> List[Dict[str, Any]]:
        """Helper to build debate candidates from IntentMatch objects."""
        candidates = []
        for intent in intents:
            analysis_type = getattr(intent, "analysis_type", str(intent))
            candidates.append({
                "id": analysis_type,
                "label": analysis_type.replace("_", " ").title(),
                "description": getattr(intent, "description", "") or analysis_type,
                "metadata": {"skill": analysis_type},
            })
        return candidates
