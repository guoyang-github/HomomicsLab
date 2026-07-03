"""Prompt assembly for the LLM intent classifier.

The actual templates live in the prompt registry (``prompts/templates/base.yaml``
and domain-specific overrides in ``domain.yaml``). This module only provides the
variable formatting helpers and the public ``build_classification_prompt`` entry
point for backward compatibility.
"""

from typing import Any, Dict, List

from homomics_lab.agent.intent.models import IntentDefinition
from homomics_lab.prompts import render_prompt


CLARIFICATION_TEMPLATE = (
    "我不太确定您的需求。您是想要：\n{options}\n\n请告诉我更具体一些。"
)


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
) -> str:
    """Build the final LLM prompt from the registry template.

    Falls back to a minimal inline prompt if the registry template is missing.
    """
    rendered = render_prompt(
        "intent.classification",
        intent_descriptions=format_intent_descriptions(definitions),
        context=format_context(context),
        message=message,
    )
    if rendered is not None:
        return rendered

    # Minimal fallback: should never happen in a normal boot, but keeps tests
    # runnable if the registry has not been initialized.
    return (
        "Classify the user's intent. Available intents:\n"
        + format_intent_descriptions(definitions)
        + "\nContext:\n"
        + format_context(context)
        + "\nMessage: "
        + message
    )
