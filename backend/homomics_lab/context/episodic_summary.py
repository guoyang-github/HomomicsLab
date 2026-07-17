"""Rolling session summary for long-running conversations.

Keeps a concise summary of what has happened in the current session so that
even when old raw messages are evicted from WorkingMemory, the agent still
knows the user's overall goal and key decisions.
"""

import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.config import settings
from homomics_lab.llm_client import LLMClient
from homomics_lab.models.common import ChatMessage

logger = logging.getLogger(__name__)

_MAX_CACHED_SESSIONS = 256


@dataclass
class EpisodicSummary:
    """Structured session summary."""

    user_goal: str = ""
    completed_steps: List[str] = None  # type: ignore
    pending_steps: List[str] = None  # type: ignore
    key_decisions: Dict[str, Any] = None  # type: ignore
    open_questions: List[str] = None  # type: ignore
    errors: List[str] = None  # type: ignore

    def __post_init__(self):
        if self.completed_steps is None:
            self.completed_steps = []
        if self.pending_steps is None:
            self.pending_steps = []
        if self.key_decisions is None:
            self.key_decisions = {}
        if self.open_questions is None:
            self.open_questions = []
        if self.errors is None:
            self.errors = []

    def to_text(self) -> str:
        lines = ["Session summary:"]
        if self.user_goal:
            lines.append(f"- User goal: {self.user_goal}")
        if self.completed_steps:
            lines.append(f"- Completed: {'; '.join(self.completed_steps[-5:])}")
        if self.pending_steps:
            lines.append(f"- Pending: {'; '.join(self.pending_steps[-5:])}")
        if self.key_decisions:
            decisions = ", ".join(f"{k}={v}" for k, v in list(self.key_decisions.items())[:5])
            lines.append(f"- Key decisions: {decisions}")
        if self.open_questions:
            lines.append(f"- Open questions: {'; '.join(self.open_questions[-3:])}")
        if self.errors:
            lines.append(f"- Recent errors: {'; '.join(self.errors[-3:])}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_goal": self.user_goal,
            "completed_steps": self.completed_steps,
            "pending_steps": self.pending_steps,
            "key_decisions": self.key_decisions,
            "open_questions": self.open_questions,
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodicSummary":
        return cls(
            user_goal=data.get("user_goal", ""),
            completed_steps=list(data.get("completed_steps", [])),
            pending_steps=list(data.get("pending_steps", [])),
            key_decisions=dict(data.get("key_decisions", {})),
            open_questions=list(data.get("open_questions", [])),
            errors=list(data.get("errors", [])),
        )


class EpisodicSummarizer:
    """Generate and update a rolling session summary.

    The summarizer is throttled to keep it off the chat critical path:

    - Sessions with fewer than ``settings.episodic_summary_min_messages``
      messages are not summarized at all (the last cached/previous summary,
      if any, is returned instead).
    - Summaries are cached per ``session_id`` and only recomputed when the
      session's message count has moved by at least
      ``settings.episodic_summary_min_interval`` since the cached entry.

    The LLM client is injected by the caller (shared instance). When it is
    ``None`` the LLM path is skipped and the rule-based fallback is used.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client
        # session_id -> (message_count, summary)
        self._cache: "OrderedDict[str, Tuple[int, EpisodicSummary]]" = OrderedDict()

    async def summarize(
        self,
        messages: List[ChatMessage],
        previous_summary: Optional[EpisodicSummary] = None,
        session_id: Optional[str] = None,
        message_count: Optional[int] = None,
    ) -> EpisodicSummary:
        """Update session summary from recent messages.

        ``messages`` may be a truncated window (e.g. the most recent 10);
        ``message_count`` should carry the full session message count so the
        throttling cache does not saturate on the window size. It defaults to
        ``len(messages)``.
        """
        count = message_count if message_count is not None else len(messages)
        cached_count: Optional[int] = None
        cached_summary: Optional[EpisodicSummary] = None
        if session_id is not None:
            entry = self._cache.get(session_id)
            if entry is not None:
                cached_count, cached_summary = entry
                self._cache.move_to_end(session_id)

        if not messages:
            return previous_summary or cached_summary or EpisodicSummary()

        # Too early in the session to be worth a summary.
        if count < settings.episodic_summary_min_messages:
            return cached_summary or previous_summary or EpisodicSummary()

        # Reuse the cached summary until the session has grown enough.
        if (
            cached_summary is not None
            and cached_count is not None
            and abs(count - cached_count) < settings.episodic_summary_min_interval
        ):
            return cached_summary

        summary = await self._compute(messages, previous_summary or cached_summary)
        if session_id is not None:
            self._cache[session_id] = (count, summary)
            while len(self._cache) > _MAX_CACHED_SESSIONS:
                self._cache.popitem(last=False)
        return summary

    async def _compute(
        self,
        messages: List[ChatMessage],
        previous_summary: Optional[EpisodicSummary],
    ) -> EpisodicSummary:
        client = self.llm_client
        if client is not None and client.is_configured():
            try:
                return await self._llm_summarize(messages, previous_summary)
            except Exception as exc:
                logger.warning("LLM episodic summary failed: %s", exc)

        return self._rule_summarize(messages, previous_summary)

    async def _llm_summarize(
        self,
        messages: List[ChatMessage],
        previous_summary: Optional[EpisodicSummary],
    ) -> EpisodicSummary:
        """Use an LLM to merge previous summary with recent messages."""
        client = self.llm_client
        if client is None:
            raise RuntimeError("LLM client not configured")
        history_text = "\n".join(
            f"{msg.sender}: {_message_to_text(msg)}" for msg in messages[-10:]
        )
        previous = (previous_summary or EpisodicSummary()).to_text()

        prompt = f"""You are a session summarizer for a bioinformatics assistant.
Update the session summary by incorporating the recent conversation.

Previous summary:
{previous}

Recent messages:
{history_text}

Return a JSON object with these fields:
{{
  "user_goal": "one-sentence description of what the user is trying to do",
  "completed_steps": ["step 1", "step 2"],
  "pending_steps": ["step 3"],
  "key_decisions": {{"parameter_name": "value"}},
  "open_questions": ["question 1"],
  "errors": ["error 1"]
}}
"""
        raw = await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw)
        return EpisodicSummary(
            user_goal=parsed.get("user_goal", ""),
            completed_steps=list(parsed.get("completed_steps", [])),
            pending_steps=list(parsed.get("pending_steps", [])),
            key_decisions=dict(parsed.get("key_decisions", {})),
            open_questions=list(parsed.get("open_questions", [])),
            errors=list(parsed.get("errors", [])),
        )

    def _rule_summarize(
        self,
        messages: List[ChatMessage],
        previous_summary: Optional[EpisodicSummary],
    ) -> EpisodicSummary:
        """Fallback rule-based summarizer when LLM is unavailable."""
        summary = previous_summary or EpisodicSummary()

        for msg in messages:
            text = _message_to_text(msg)
            if not text:
                continue
            if msg.sender == "user":
                # Keep the latest user goal heuristically
                if len(text) > 10:
                    summary.user_goal = text[:200]
            elif msg.sender == "agent":
                if "error" in text.lower() or "失败" in text:
                    summary.errors.append(text[:200])
                    summary.errors = summary.errors[-5:]
                elif "completed" in text.lower() or "已完成" in text:
                    summary.completed_steps.append(text[:200])
                    summary.completed_steps = summary.completed_steps[-10:]
                elif "pending" in text.lower() or "待处理" in text:
                    summary.pending_steps.append(text[:200])
                    summary.pending_steps = summary.pending_steps[-10:]

        return summary


def _message_to_text(msg: ChatMessage) -> str:
    """Convert a ChatMessage content to plain text."""
    content = msg.content
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)
