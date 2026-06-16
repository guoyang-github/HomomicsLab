"""Minimal async LLM client for runtime use.

Currently wraps OpenAI's async API and reads OPENAI_API_KEY from the
environment. If no key is available, the client degrades gracefully so that
tests and offline usage do not crash.
"""

import os
from typing import Any, Dict, List, Optional, Tuple, Union


class LLMClient:
    """Async LLM client for generating text completions.

    Usage:
        client = LLMClient(model="gpt-4o-mini")
        response = await client.chat_completion([
            {"role": "system", "content": "You are a bioinformatics assistant."},
            {"role": "user", "content": "Plan a single-cell analysis."},
        ])
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.model = model or os.environ.get("HOMOMICS_LLM_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.timeout = timeout
        self._client: Optional[Any] = None
        # Aggregated usage counters.
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.estimated_cost_usd = 0.0

    def _get_client(self) -> Any:
        """Lazy-load the OpenAI async client."""
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. Configure it to enable LLM fallback."
                )
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise RuntimeError(
                    "openai package is required for LLM fallback. "
                    "Install it with: pip install openai"
                ) from e

            kwargs: Dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        """Send a chat completion request and return the generated text.

        Raises:
            RuntimeError: if the LLM is not configured or the request fails.
        """
        client = self._get_client()
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        # Enforce monthly budget before incurring more cost.
        self._check_budget()

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content.strip()

        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0
            self._record_usage(prompt_tokens, completion_tokens, total_tokens)
            self._persist_cost(prompt_tokens, completion_tokens, total_tokens)

        return content

    def _record_usage(self, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        """Record token usage and update cost estimate."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.estimated_cost_usd += self._estimate_cost_usd(prompt_tokens, completion_tokens)

    def _persist_cost(self, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        """Persist the cost record to the shared cost controller and metrics."""
        cost = self._estimate_cost_usd(prompt_tokens, completion_tokens)
        try:
            from homomics_lab.cost_control import get_cost_controller

            get_cost_controller().record_llm_cost(
                model=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
            )
            # Per-request cap is enforced after the fact; future work can
            # estimate an upper bound before the call.
            get_cost_controller().check_request_budget(cost)
        except Exception:
            # Never fail a request because of cost-bookkeeping issues.
            pass

        try:
            from homomics_lab.metrics import record_llm_usage
            record_llm_usage(self.model, prompt_tokens, completion_tokens, cost)
        except Exception:
            pass

    def _check_budget(self) -> None:
        """Raise if the monthly budget is already exhausted before a new call."""
        try:
            from homomics_lab.cost_control import BudgetExceeded, get_cost_controller

            get_cost_controller().check_request_budget(0.0)
        except BudgetExceeded:
            raise
        except Exception:
            # Never fail a request because of cost-bookkeeping issues.
            pass

    @staticmethod
    def _estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
        """Return a rough cost estimate in USD based on known model prices.

        Prices are per 1M tokens. Unknown models fall back to gpt-4o-mini rates.
        """
        model_lower = (os.environ.get("HOMOMICS_LLM_MODEL", "gpt-4o-mini")).lower()
        # (input_rate, output_rate) per 1M tokens.
        rates = {
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-4": (30.00, 60.00),
            "gpt-3.5-turbo": (0.50, 1.50),
        }
        rate = next((r for k, r in rates.items() if k in model_lower), rates["gpt-4o-mini"])
        prompt_cost = prompt_tokens * rate[0] / 1_000_000
        completion_cost = completion_tokens * rate[1] / 1_000_000
        return prompt_cost + completion_cost

    def get_usage_summary(self) -> Dict[str, Any]:
        """Return aggregated usage and cost estimate."""
        return {
            "model": self.model,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }

    def is_configured(self) -> bool:
        """Return True if the client has an API key available."""
        return bool(self.api_key)


class FakeLLMClient(LLMClient):
    """Test double that returns a canned response instead of calling an API."""

    def __init__(self, response: str = "", model: str = "fake"):
        # Bypass real client initialization.
        self.model = model
        self.api_key = "fake"
        self.base_url = None
        self.timeout = 0.0
        self._client = None
        self._response = response

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 0,
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        return self._response
