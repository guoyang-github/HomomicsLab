"""Prompt assembly for the LLM intent classifier.

The actual templates live in the prompt registry (``prompts/templates/base.yaml``
and domain-specific overrides in ``domain.yaml``). This module only provides the
variable formatting helpers and the public ``build_classification_prompt`` entry
point for backward compatibility.
"""

from typing import List, Optional

from homomics_lab.agent.intent.models import IntentDefinition
from homomics_lab.prompts import render_prompt


CLARIFICATION_TEMPLATE = (
    "我不太确定您的需求。您是想要：\n{options}\n\n请告诉我更具体一些。"
)

# Default number of candidate intents injected into the classification prompt
# after keyword pre-filtering. The full list is used as fallback when no
# keyword matches at all, so recall is preserved for paraphrased messages.
PREFILTER_TOP_K = 5


def prefilter_definitions(
    definitions: List[IntentDefinition],
    message: str,
    top_k: Optional[int] = PREFILTER_TOP_K,
) -> List[IntentDefinition]:
    """Select the top-K candidate intents for the message by keyword overlap.

    The injected intent list only guides the LLM's ``target``/``domain`` choice
    for analysis intents (the response categories themselves are fixed in the
    template), so ranking candidates by literal keyword/analysis-type overlap
    is a safe way to shrink the prompt. When nothing matches — e.g. fully
    paraphrased requests — the full list is returned unchanged so the LLM
    keeps full recall. With ``top_k=None`` pre-filtering is disabled.
    """
    if top_k is None or len(definitions) <= top_k:
        return list(definitions)
    text = message.lower()
    scored = []
    for idx, definition in enumerate(definitions):
        score = 0
        for kw in definition.keywords:
            if kw and kw.lower() in text:
                score += 1
        atype = definition.analysis_type.lower()
        if atype in text or atype.replace("_", " ") in text:
            score += 2
        if score > 0:
            scored.append((score, idx, definition))
    if not scored:
        return list(definitions)
    # Highest score first; stable by original order for ties.
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [definition for _score, _idx, definition in scored[:top_k]]


def format_intent_descriptions(definitions: List[IntentDefinition]) -> str:
    """Format intent definitions for the LLM prompt."""
    lines = []
    for d in definitions:
        lines.append(f"- {d.analysis_type} (domain: {d.domain or 'builtin'})")
        if d.keywords:
            lines.append(f"  keywords: {', '.join(d.keywords[:10])}")
        if d.examples:
            for ex in d.examples[:3]:
                lines.append(f"  example: {ex}")
        lines.append("")
    return "\n".join(lines)


def format_context(context: dict) -> str:
    """Format conversation context for the LLM prompt."""
    messages = context.get("recent_messages", [])
    if not messages:
        return "No prior context."
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, str):
            lines.append(f"{role}: {content}")
    return "\n".join(lines[-6:])


def build_classification_prompt(
    definitions: list,
    context: dict,
    message: str,
    top_k: Optional[int] = PREFILTER_TOP_K,
) -> str:
    """Build the final LLM prompt from the registry template.

    Intent descriptions are keyword-pre-filtered to the top-K candidates to
    keep the prompt small; the full list is injected when pre-filtering finds
    no match. Falls back to a minimal inline prompt if the registry template
    is missing.
    """
    candidates = prefilter_definitions(definitions, message, top_k=top_k)
    rendered = render_prompt(
        "intent.classification",
        intent_descriptions=format_intent_descriptions(candidates),
        formatted_context=format_context(context),
        message=message,
    )
    if rendered is not None:
        return rendered

    # Minimal fallback: should never happen in a normal boot, but keeps tests
    # runnable if the registry has not been initialized.
    return (
        "Classify the user's intent. Available intents:\n"
        + format_intent_descriptions(candidates)
        + "\nContext:\n"
        + format_context(context)
        + "\nMessage: "
        + message
    )
