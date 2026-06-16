"""Async LLM client with multi-provider support, fallback, and cost governance.

Supports OpenAI, Anthropic, Azure, and domestic OpenAI-compatible providers:
DeepSeek, Qwen (DashScope), Zhipu GLM, Moonshot (Kimi), and Ollama/local.
"""

import os
from typing import Any, Dict, List, Optional

from homomics_lab.llm.cost import estimate_cost_usd
from homomics_lab.llm.providers import get_provider_registry
from homomics_lab.llm.router import LLMRouter


class LLMClient:
    """Async LLM client with automatic provider selection and fallback.

    Usage:
        client = LLMClient()
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
        router: Optional[LLMRouter] = None,
    ):
        self.timeout = timeout
        self._router = router or LLMRouter()
        self._clients: Dict[str, Any] = {}
        self._init_usage()
        # Legacy overrides: if api_key/base_url are explicitly passed, build a
        # synthetic provider config for them. This keeps the old interface working.
        self._legacy_model = model or self._router.primary_model
        self._legacy_api_key = api_key
        self._legacy_base_url = base_url

    def _init_usage(self) -> None:
        """Initialize aggregated usage counters."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.estimated_cost_usd = 0.0

    def _get_client(self, provider) -> Any:
        """Lazy-load an OpenAI-compatible async client for the provider."""
        if provider.name in self._clients:
            return self._clients[provider.name]

        api_key = self._legacy_api_key or provider.resolve_api_key()
        if not api_key:
            raise RuntimeError(
                f"API key for provider '{provider.name}' is not set. "
                f"Configure {provider.api_key_env} or secrets manager."
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai package is required for LLM calls. Install it with: pip install openai"
            ) from e

        kwargs: Dict[str, Any] = {"api_key": api_key, "timeout": self.timeout}
        base_url = self._legacy_base_url or provider.base_url
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncOpenAI(**kwargs)
        self._clients[provider.name] = client
        return client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        prefer_cheap: bool = False,
    ) -> str:
        """Send a chat completion request with automatic provider routing.

        Args:
            messages: OpenAI-compatible message list.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.
            response_format: Optional response format dict.
            model: Explicit model override.
            prefer_cheap: If True, pick the cheapest configured model.
        """
        route = self._router.select(model=model or self._legacy_model, prefer_cheap=prefer_cheap)
        client = self._get_client(route.provider)

        kwargs: Dict[str, Any] = {
            "model": route.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content.strip()

        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0
            self._record_usage(route.model, prompt_tokens, completion_tokens, total_tokens)

        return content

    def _record_usage(self, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        """Record token usage and update cost estimate."""
        cost = estimate_cost_usd(model, prompt_tokens, completion_tokens)
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.estimated_cost_usd += cost

        try:
            from homomics_lab.cost_control import get_cost_controller

            get_cost_controller().record_llm_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost,
            )
            get_cost_controller().check_request_budget(cost)
        except Exception:
            pass

        try:
            from homomics_lab.metrics import record_llm_usage

            record_llm_usage(model, prompt_tokens, completion_tokens, cost)
        except Exception:
            pass

    def get_usage_summary(self) -> Dict[str, Any]:
        """Return aggregated usage and cost estimate."""
        return {
            "model": self._router.primary_model,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }

    def is_configured(self) -> bool:
        """Return True if any configured provider is available."""
        try:
            self._router.select()
            return True
        except Exception:
            return False

    def list_available_models(self) -> List[Dict[str, str]]:
        """Return all available models across configured providers."""
        return self._router.list_available_models()


class FakeLLMClient(LLMClient):
    """Test double that returns a canned response instead of calling an API."""

    def __init__(self, response: str = "", model: str = "fake"):
        # Bypass real client initialization.
        self._router = LLMRouter(registry=get_provider_registry())
        self._legacy_model = model
        self._legacy_api_key = "fake"
        self._legacy_base_url = None
        self.timeout = 0.0
        self._clients = {}
        self._response = response
        self._init_usage()

    def is_configured(self) -> bool:
        return True

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 0,
        response_format: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        prefer_cheap: bool = False,
    ) -> str:
        return self._response
