"""LLM pricing table and cost estimation.

Prices are in USD per 1M tokens (input, output). Domestic providers are
converted to USD where possible; Ollama/local is treated as zero.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# (input_rate_usd_per_1m, output_rate_usd_per_1m)
PRICING: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Anthropic
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (1.00, 5.00),
    # DeepSeek (USD-ish rates; verify with official pricing)
    "deepseek-chat": (0.14, 0.28),
    "deepseek-coder": (0.14, 0.28),
    "deepseek-reasoner": (0.55, 2.19),
    # Qwen (DashScope; approximate USD)
    "qwen-turbo": (0.50, 1.00),
    "qwen-plus": (3.00, 6.00),
    "qwen-max": (5.00, 10.00),
    # Zhipu GLM (approximate USD)
    "glm-4": (5.00, 5.00),
    "glm-4-flash": (0.10, 0.10),
    "glm-4-air": (1.00, 1.00),
    # Moonshot (approximate USD)
    "moonshot-v1-8k": (1.00, 1.00),
    "moonshot-v1-32k": (2.00, 2.00),
    "moonshot-v1-128k": (4.00, 4.00),
    # Azure mirrors OpenAI rates for same models
    "azure-gpt-4o": (2.50, 10.00),
    "azure-gpt-4o-mini": (0.15, 0.60),
    # Local / Ollama
    "llama3.1": (0.0, 0.0),
    "qwen2.5": (0.0, 0.0),
    "deepseek-coder-v2": (0.0, 0.0),
}


def get_model_pricing(model: str) -> Optional[Tuple[float, float]]:
    """Return (input_rate, output_rate) for a model, or None if unknown."""
    model_lower = model.lower()
    # Exact match first.
    if model_lower in PRICING:
        return PRICING[model_lower]
    # Prefix match.
    for key, rates in PRICING.items():
        if model_lower.startswith(key) or key.startswith(model_lower):
            return rates
    return None


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD for a given model and token counts."""
    rates = get_model_pricing(model)
    if rates is None:
        # Default to gpt-4o-mini rates for unknown models.
        rates = PRICING["gpt-4o-mini"]
    prompt_cost = prompt_tokens * rates[0] / 1_000_000
    completion_cost = completion_tokens * rates[1] / 1_000_000
    return prompt_cost + completion_cost


def list_priced_models() -> Dict[str, Tuple[float, float]]:
    """Return the full pricing table."""
    return dict(PRICING)
