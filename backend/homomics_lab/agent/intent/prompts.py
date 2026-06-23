"""Prompt templates for the LLM intent classifier."""


INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for a bioinformatics analysis assistant.

Your job is to classify the user's latest message into one of the intent types below.

Available intent types and examples:
__INTENT_DESCRIPTIONS__

Recent conversation context:
__CONTEXT__

User message:
__MESSAGE__

Respond with a single JSON object in this exact format (no markdown fences):
{
  "primary_intent": {
    "analysis_type": "intent_id",
    "confidence": 0.0,
    "reason": "short reason"
  },
  "alternative_intents": [
    {"analysis_type": "intent_id", "confidence": 0.0}
  ],
  "sub_intents": [
    {"analysis_type": "intent_id", "confidence": 0.0}
  ],
  "data_scale_hint": "optional string, e.g. '5000 cells'",
  "needs_clarification": false,
  "clarification_question": "optional question if ambiguous"
}

Rules:
1. Distinguish "qa" (asking for explanation/knowledge) from "general_help" (asking for code/script).
2. "single_cell_analysis" includes scRNA-seq, clustering, UMAP, PCA, QC, differential expression.
3. "spatial_analysis" includes Visium, Xenium, MERFISH, spatial transcriptomics.
4. "file_conversion" is for format conversion requests only.
5. If the user asks for multiple analysis steps (e.g., "QC then cluster"), include them in sub_intents.
6. If the message refers to "it", "this", "that", or "上一个文件", use the conversation context to resolve the referent.
7. Set needs_clarification=true if the top confidence is below 0.7 and alternatives are close.
8. If nothing matches, use analysis_type "general" with low confidence.
9. CRITICAL: If the user asks "what are", "有哪些", "includes", "介绍", or similar information-seeking phrases about an analysis type, classify as "qa" (direct_response), NOT as an execution workflow.
"""


CLARIFICATION_TEMPLATE = (
    "我不太确定您的需求。您是想要：\n{options}\n\n请告诉我更具体一些。"
)


def format_intent_descriptions(definitions: list) -> str:
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
    """Build the final LLM prompt by substituting placeholders safely."""
    return (
        INTENT_CLASSIFICATION_PROMPT
        .replace("__INTENT_DESCRIPTIONS__", format_intent_descriptions(definitions))
        .replace("__CONTEXT__", format_context(context))
        .replace("__MESSAGE__", message)
    )
