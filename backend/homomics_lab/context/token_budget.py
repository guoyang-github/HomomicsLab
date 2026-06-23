"""Token budget management for context assembly.

Provides model-aware context windows and token counting with graceful fallbacks:
  1. tiktoken (OpenAI models)
  2. transformers.AutoTokenizer (if available)
  3. rough word-count heuristic
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from homomics_lab.context.context_engine.models import ContextPart

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelContextConfig:
    """Context window configuration for a specific model."""

    max_context_tokens: int
    output_reserve_tokens: int = 2000
    cost_prompt_per_1k: float = 0.0
    cost_completion_per_1k: float = 0.0


# Sensible defaults for common HomomicsLab-supported models.
# These can be overridden via config or env variables.
DEFAULT_MODEL_CONFIGS: Dict[str, ModelContextConfig] = {
    "gpt-4o": ModelContextConfig(max_context_tokens=128_000, output_reserve_tokens=4_000),
    "gpt-4o-mini": ModelContextConfig(max_context_tokens=128_000, output_reserve_tokens=4_000),
    "gpt-4-turbo": ModelContextConfig(max_context_tokens=128_000, output_reserve_tokens=4_000),
    "claude-3-5-sonnet": ModelContextConfig(max_context_tokens=200_000, output_reserve_tokens=4_000),
    "claude-3-opus": ModelContextConfig(max_context_tokens=200_000, output_reserve_tokens=4_000),
    "kimi-k1.5": ModelContextConfig(max_context_tokens=128_000, output_reserve_tokens=4_000),
    "moonshot-v1-128k": ModelContextConfig(max_context_tokens=128_000, output_reserve_tokens=4_000),
    "deepseek-chat": ModelContextConfig(max_context_tokens=64_000, output_reserve_tokens=4_000),
    "qwen2.5-72b": ModelContextConfig(max_context_tokens=128_000, output_reserve_tokens=4_000),
    "default": ModelContextConfig(max_context_tokens=8_000, output_reserve_tokens=2_000),
}


def _normalize_model_name(model: str) -> str:
    """Map a full model identifier to a known base model name."""
    model_lower = model.lower()
    for key in DEFAULT_MODEL_CONFIGS:
        if key in model_lower:
            return key
    # Handle common prefixes like "openai/gpt-4o"
    if "/" in model_lower:
        return _normalize_model_name(model_lower.split("/")[-1])
    return "default"


class TokenBudgetManager:
    """Count tokens and enforce a model-specific context budget."""

    def __init__(
        self,
        model: str = "default",
        configs: Optional[Dict[str, ModelContextConfig]] = None,
        output_reserve_tokens: Optional[int] = None,
    ):
        self.model = model
        self.normalized_model = _normalize_model_name(model)
        self.configs = configs or DEFAULT_MODEL_CONFIGS
        self.config = self.configs.get(self.normalized_model, self.configs["default"])
        if output_reserve_tokens is not None:
            self.config = ModelContextConfig(
                max_context_tokens=self.config.max_context_tokens,
                output_reserve_tokens=output_reserve_tokens,
            )
        self._encoder = None
        self._encoder_kind = "heuristic"

    @property
    def max_context_tokens(self) -> int:
        return self.config.max_context_tokens

    @property
    def output_reserve_tokens(self) -> int:
        return self.config.output_reserve_tokens

    def available_input_tokens(self) -> int:
        """Tokens still available for the input context after reserving output."""
        return max(0, self.config.max_context_tokens - self.config.output_reserve_tokens)

    def _load_encoder(self):
        """Lazy-load the best available tokenizer."""
        if self._encoder is not None:
            return self._encoder

        # Try tiktoken first (OpenAI models)
        try:
            import tiktoken

            # tiktoken encoding names differ from model names; map known ones.
            encoding_name = "cl100k_base"
            if "gpt-4o" in self.normalized_model:
                encoding_name = "o200k_base"
            elif self.normalized_model.startswith("gpt-4") or self.normalized_model.startswith("gpt-3.5"):
                encoding_name = "cl100k_base"
            self._encoder = tiktoken.get_encoding(encoding_name)
            self._encoder_kind = "tiktoken"
            return self._encoder
        except Exception:
            pass

        # Fall back to transformers AutoTokenizer for known local models.
        # Use a tiny, commonly-cached model and require local files so the
        # fallback never blocks on a network download.
        if self.normalized_model not in ("default",):
            try:
                from transformers import AutoTokenizer

                tokenizer_name = "gpt2"
                self._encoder = AutoTokenizer.from_pretrained(
                    tokenizer_name, local_files_only=True
                )
                self._encoder_kind = "transformers"
                return self._encoder
            except Exception:
                pass

        self._encoder = None
        self._encoder_kind = "heuristic"
        return None

    def count(self, text: str) -> int:
        """Return token count for a plain text string."""
        encoder = self._load_encoder()
        if encoder is None:
            # Rough heuristic: ~0.75 words per token for English/Chinese mix.
            return max(1, int(len(text.split()) / 0.75))

        try:
            if self._encoder_kind == "tiktoken":
                return len(encoder.encode(text))
            if self._encoder_kind == "transformers":
                return len(encoder.encode(text, add_special_tokens=False))
        except Exception as exc:
            logger.warning("Tokenizer failed: %s. Falling back to heuristic.", exc)

        return max(1, int(len(text.split()) / 0.75))

    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """Estimate token count for an OpenAI-style message list.

        Includes per-message overhead observed in OpenAI token counting.
        """
        total = 0
        for msg in messages:
            total += 3  # role/content overhead
            total += self.count(msg.get("content", ""))
            if msg.get("name"):
                total += 1
        total += 3  # reply priming
        return total

    def fits(self, text: str, budget: Optional[int] = None) -> bool:
        """Check whether text fits within a token budget."""
        budget = budget if budget is not None else self.available_input_tokens()
        return self.count(text) <= budget

    def truncate(self, text: str, max_tokens: int, suffix: str = "...") -> str:
        """Truncate text to fit within max_tokens."""
        if self.count(text) <= max_tokens:
            return text
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            candidate = text[:mid]
            if self.count(candidate + suffix) <= max_tokens:
                low = mid
            else:
                high = mid - 1
        return text[:low] + suffix


class TokenBudgetFitter:
    """Greedy fit a prioritized list of context parts into a token budget."""

    def __init__(self, budget_manager: TokenBudgetManager):
        self.budget_manager = budget_manager

    def fit(
        self,
        parts: List["ContextPart"],  # type: ignore
        reserved_parts: List["ContextPart"],  # type: ignore
        budget: int,
    ) -> List["ContextPart"]:  # type: ignore
        """Return parts that fit within budget, keeping reserved_parts first."""
        result = list(reserved_parts)
        used = sum(p.tokens for p in result)

        for part in sorted(parts, key=lambda p: (-p.priority, p.tokens)):
            if used + part.tokens <= budget:
                result.append(part)
                used += part.tokens

        return result
