"""Async LLM client with multi-provider support, fallback, and cost governance.

Supports OpenAI, Anthropic, Azure, and domestic OpenAI-compatible providers:
DeepSeek, Qwen (DashScope), Zhipu GLM, Moonshot (Kimi), and Ollama/local.
"""

import asyncio
import logging
import random
import time
import uuid
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

from homomics_lab.llm.cache import BaseLLMResponseCache
from homomics_lab.llm.cost import estimate_cost_usd
from homomics_lab.llm.providers import get_provider_registry, reset_provider_registry
from homomics_lab.llm.router import LLM_COMPLEXITY_ROUTING_ENABLED, LLMRouter
from homomics_lab.llm.runtime_config import load_llm_runtime_config

logger = logging.getLogger(__name__)


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
        timeout: float = 240.0,
        router: Optional[LLMRouter] = None,
        cache: Optional[BaseLLMResponseCache] = None,
    ):
        self.timeout = timeout
        self._config_lock = asyncio.Lock()
        # By default, load the latest runtime config (UI/env) into the router.
        if router is None:
            runtime_config = load_llm_runtime_config()
            router = LLMRouter(runtime_config=runtime_config)
        self._router = router

        # Local/self-hosted models running on CPU are much slower than cloud APIs.
        # Give them a generous default timeout so the first load/prompt does not
        # immediately trip the fallback/retry logic.
        if self.timeout < 300 and self._is_local_provider():
            self.timeout = 300.0
        self._clients: Dict[str, Any] = {}
        self._init_usage()
        self._cache = cache
        # Legacy overrides: if api_key/base_url are explicitly passed, build a
        # synthetic provider config for them. This keeps the old interface working.
        self._legacy_model = model or self._router.primary_model
        self._legacy_api_key = api_key
        self._legacy_base_url = base_url

    async def reload_config(self) -> None:
        """Reload runtime LLM configuration and drop cached API clients."""
        async with self._config_lock:
            reset_provider_registry()
            runtime_config = load_llm_runtime_config()
            self._router = LLMRouter(runtime_config=runtime_config)
            self._clients = {}
            self._legacy_model = self._router.primary_model

    def _init_usage(self) -> None:
        """Initialize aggregated usage counters."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.estimated_cost_usd = 0.0

    def _is_local_provider(self) -> bool:
        runtime = getattr(self._router, "runtime_config", None)
        if runtime is None:
            return False
        provider = getattr(runtime, "provider", None)
        return provider in ("ollama", "local")

    @property
    def router(self) -> LLMRouter:
        """The router used for provider/model selection (read-only access).

        Exposed so executors can resolve skill-declared models/tiers through
        the same routing logic the client uses for regular calls.
        """
        return self._router

    @staticmethod
    def _supports_temperature(provider_name: str, model: str, base_url: Optional[str] = None) -> bool:
        """Return False for models with fixed server-side sampling parameters."""
        model_lower = model.lower()
        # Kimi K2.x and kimi-for-coding use fixed server-side sampling.
        if (
            model_lower.startswith("kimi-k2")
            or model_lower.startswith("kimi-k2.")
            or model_lower == "kimi-for-coding"
        ):
            return False
        # Kimi Code endpoint (api.kimi.com/coding) is also fixed-sampling.
        if base_url and "api.kimi.com/coding" in base_url.lower():
            return False
        # Other Moonshot models (moonshot-v1-*) do support temperature.
        return True

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

        kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": self.timeout,
            # Disable the OpenAI client's internal retry loop. The agent layer
            # already implements its own retry/backoff policy with explicit
            # timeouts, and internal retries can hang a job for many minutes
            # when the provider is slow or rate-limiting.
            "max_retries": 0,
        }
        base_url = self._legacy_base_url or provider.resolved_base_url
        if base_url:
            kwargs["base_url"] = base_url
            # Kimi Code (api.kimi.com/coding) restricts access to recognized
            # coding-agent User-Agents. Pretend to be Claude Code so the
            # OpenAI-compatible endpoint accepts the request.
            if "api.kimi.com/coding" in base_url.lower():
                kwargs["default_headers"] = {"User-Agent": "claude-code/0.1.0"}
        client = AsyncOpenAI(**kwargs)
        self._clients[provider.name] = client
        return client

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        prefer_cheap: bool = False,
        intent_type: Optional[str] = None,
        task_type: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
        return_usage: bool = False,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Union[str, Tuple[str, Dict[str, Any]]]:
        """Send a chat completion request with automatic provider routing.

        Args:
            messages: OpenAI-compatible message list.
            temperature: Sampling temperature.
            max_tokens: Max output tokens.
            response_format: Optional response format dict.
            model: Explicit model override.
            prefer_cheap: If True, pick the cheapest configured model.
            intent_type: Optional intent classification for complexity-based routing.
            task_type: Optional task classification for catalog-based routing.
            required_capabilities: Optional capability tags that the model must have.
            return_usage: If True, return a tuple (content, usage_metadata).
            session_id: Optional session identifier for cost attribution.
            project_id: Optional project identifier for cost attribution.
            request_id: Optional request identifier for cost attribution.
        """
        message, usage = await self.chat_completion_message(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            model=model,
            prefer_cheap=prefer_cheap,
            intent_type=intent_type,
            task_type=task_type,
            required_capabilities=required_capabilities,
            session_id=session_id,
            project_id=project_id,
            request_id=request_id,
        )
        content = (getattr(message, "content", None) or "").strip()
        if return_usage:
            return content, usage
        return content

    async def chat_completion_for_task(
        self,
        messages: List[Dict[str, Any]],
        task_type: str,
        required_capabilities: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Convenience wrapper that routes via the model catalog for ``task_type``."""
        return await self.chat_completion(
            messages=messages,
            task_type=task_type,
            required_capabilities=required_capabilities,
            **kwargs,
        )

    async def chat_completion_message(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        prefer_cheap: bool = False,
        intent_type: Optional[str] = None,
        task_type: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Send a chat completion and return the raw assistant message object.

        This is the low-level entry point used by the agent loop so it can
        inspect ``message.tool_calls``.
        """
        requested_model = model or self._legacy_model
        route = self._select_route(
            requested_model=requested_model,
            prefer_cheap=prefer_cheap,
            intent_type=intent_type,
            task_type=task_type,
            required_capabilities=required_capabilities,
            messages=messages,
        )

        # Check cache first (only for simple non-tool requests).
        if self._cache is not None and not tools:
            cached = await self._cache.get(
                route.model, messages, temperature, max_tokens, response_format
            )
            if cached is not None:
                self._record_cache_hit(route.model)
                # Reconstruct a minimal message object for callers.
                try:
                    from openai.types.chat import ChatCompletionMessage

                    msg = ChatCompletionMessage(role="assistant", content=cached)
                except Exception:
                    # Fallback object that exposes the same attributes as the
                    # OpenAI message so downstream code can use getattr().
                    msg = SimpleNamespace(role="assistant", content=cached)
                return msg, {"cache_hit": True, "model": route.model}

        tried_models = {route.model}
        last_error: Optional[Exception] = None
        while True:
            # Retry the same provider with exponential backoff before falling back.
            same_provider_attempts = 2
            for attempt in range(same_provider_attempts):
                try:
                    message, usage = await self._chat_completion_once(
                        route=route,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                        session_id=session_id,
                        project_id=project_id,
                        request_id=request_id,
                        tools=tools,
                    )
                    # Only cache simple text responses.
                    content = (getattr(message, "content", None) or "").strip()
                    if self._cache is not None and not tools and not getattr(message, "tool_calls", None):
                        await self._cache.put(
                            route.model,
                            messages,
                            temperature,
                            max_tokens,
                            response_format,
                            content,
                        )
                    return message, usage
                except Exception as exc:
                    if not self._is_retryable_error(exc):
                        raise
                    last_error = exc
                    if attempt < same_provider_attempts - 1:
                        backoff = (2 ** attempt) * 0.5 + random.uniform(0, 0.25)
                        logger.warning(
                            "Retryable LLM error on %s, retrying in %.2fs: %s",
                            route.model,
                            backoff,
                            exc,
                        )
                        await asyncio.sleep(backoff)
                    else:
                        break

            # Fall back to the next provider/model.
            try:
                route = self._router.select(
                    model=requested_model,
                    prefer_cheap=prefer_cheap,
                    skip=tried_models,
                    task_type=task_type,
                    required_capabilities=required_capabilities,
                )
                tried_models.add(route.model)
            except RuntimeError:
                break
            self._record_fallback(str(last_error), list(tried_models)[-2], route.model)

        if last_error is not None:
            raise last_error
        raise RuntimeError("All LLM fallback models failed")

    async def _chat_completion_once(
        self,
        route: Any,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, str]],
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        request_id: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Execute a single chat completion call and record usage.

        Returns the raw assistant message object together with a usage metadata
        dict so callers can aggregate per-turn costs and inspect ``tool_calls``.
        """
        client = self._get_client(route.provider)

        kwargs: Dict[str, Any] = {
            "model": route.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # Kimi K2.7 (and some newer Kimi models) use fixed server-side sampling
        # parameters and reject explicit temperature. Keep it for other models.
        base_url = self._legacy_base_url or route.provider.resolved_base_url
        if self._supports_temperature(route.provider.name, route.model, base_url):
            kwargs["temperature"] = temperature
        if response_format:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools

        start = time.time()
        span = self._start_llm_span(route.model, route.provider.name, kwargs)
        try:
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason == "length":
                logger.warning(
                    "LLM response truncated by max_tokens (max_tokens=%s, model=%s)",
                    max_tokens,
                    route.model,
                )

            usage = getattr(response, "usage", None)
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                total_tokens = getattr(usage, "total_tokens", 0) or 0

            latency_ms = (time.time() - start) * 1000
            cost_usd = estimate_cost_usd(route.model, prompt_tokens, completion_tokens)
            self._record_usage(
                route.model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cost_usd=cost_usd,
                session_id=session_id,
                project_id=project_id,
                request_id=request_id,
            )
            self._record_request_metrics(route.model, route.provider.name, latency_ms, exc=None)
            self._finish_llm_span(
                span,
                success=True,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )
            usage_meta = {
                "model": route.model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
                "finish_reason": finish_reason,
            }
            return message, usage_meta
        except Exception as exc:
            latency_ms = (time.time() - start) * 1000
            self._record_request_metrics(route.model, route.provider.name, latency_ms, exc=exc)
            self._finish_llm_span(
                span,
                success=False,
                latency_ms=latency_ms,
                error=str(exc),
            )
            raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        prefer_cheap: bool = False,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response token by token.

        Falls back synchronously if streaming fails.
        """
        route = self._router.select(model=model or self._legacy_model, prefer_cheap=prefer_cheap)
        client = self._get_client(route.provider)

        kwargs: Dict[str, Any] = {
            "model": route.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if response_format:
            kwargs["response_format"] = response_format

        start = time.time()
        span = self._start_llm_span(route.model, route.provider.name, kwargs)
        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            latency_ms = (time.time() - start) * 1000
            self._record_request_metrics(route.model, route.provider.name, latency_ms, exc=None)
            self._finish_llm_span(
                span,
                success=True,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.time() - start) * 1000
            self._record_request_metrics(route.model, route.provider.name, latency_ms, exc=exc)
            self._finish_llm_span(
                span,
                success=False,
                latency_ms=latency_ms,
                error=str(exc),
            )
            raise

    def _select_route(
        self,
        requested_model: str,
        prefer_cheap: bool,
        intent_type: Optional[str],
        task_type: Optional[str],
        required_capabilities: Optional[List[str]],
        messages: List[Dict[str, str]],
    ) -> Any:
        """Choose an initial route, optionally using complexity or catalog routing."""

        if task_type:
            return self._router.select(
                model=requested_model,
                prefer_cheap=prefer_cheap,
                task_type=task_type,
                required_capabilities=required_capabilities,
            )
        if intent_type and LLM_COMPLEXITY_ROUTING_ENABLED:
            input_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            return self._router.select_by_complexity(
                intent_type=intent_type,
                input_token_count=input_tokens,
            )
        return self._router.select(model=requested_model, prefer_cheap=prefer_cheap)

    def _record_request_metrics(
        self,
        model: str,
        provider: str,
        latency_ms: float,
        exc: Optional[Exception] = None,
    ) -> None:
        """Record duration/error metrics for an LLM request."""
        try:
            from homomics_lab.metrics import record_llm_error, record_llm_request_duration

            record_llm_request_duration(model, provider, latency_ms / 1000.0)
            if exc is not None:
                record_llm_error(model, provider, type(exc).__name__)
        except Exception:
            logger.debug("Failed to record LLM request metrics", exc_info=True)

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        """Return True if an exception warrants a fallback retry."""
        name = type(exc).__module__ + "." + type(exc).__name__
        retryable_names = {
            "openai.APIError",
            "openai.APIConnectionError",
            "openai.RateLimitError",
            "openai.Timeout",
            "openai.APITimeoutError",
            "openai.InternalServerError",
            "httpx.TimeoutException",
            "httpx.ConnectError",
        }
        if name in retryable_names:
            return True
        if isinstance(exc, asyncio.TimeoutError):
            return True
        return False

    def _record_cache_hit(self, model: str) -> None:
        """Record metrics for a cache hit."""
        try:
            from homomics_lab.metrics import record_llm_cache_hit

            record_llm_cache_hit(model)
        except Exception:
            logger.debug("Failed to record LLM cache hit metrics", exc_info=True)

    def _record_fallback(self, reason: str, from_model: str, to_model: str) -> None:
        """Record fallback metrics."""
        try:
            from homomics_lab.metrics import record_llm_fallback

            record_llm_fallback(reason, from_model, to_model)
        except Exception:
            logger.debug("Failed to record LLM fallback metrics", exc_info=True)

    def _start_llm_span(self, model: str, provider: str, kwargs: Dict[str, Any]) -> Any:
        """Start an OpenTelemetry span for an LLM call if tracing is available."""
        try:
            from homomics_lab.tracing import get_tracer
            from homomics_lab.logging_config import get_correlation_id

            tracer = get_tracer()
            if tracer is None:
                return None
            span = tracer.start_span("llm.chat_completion")
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.provider", provider)
            span.set_attribute("llm.request.temperature", kwargs.get("temperature", 0.3))
            span.set_attribute("llm.request.max_tokens", kwargs.get("max_tokens", 0))
            cid = get_correlation_id()
            if cid:
                span.set_attribute("correlation_id", cid)
            return span
        except Exception:
            logger.debug("Failed to start LLM span", exc_info=True)
            return None

    def _finish_llm_span(
        self,
        span: Any,
        success: bool,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Finish an OpenTelemetry span."""
        if span is None:
            return
        try:
            from opentelemetry.trace import Status, StatusCode

            span.set_attribute("llm.latency_ms", latency_ms)
            if prompt_tokens:
                span.set_attribute("llm.usage.prompt_tokens", prompt_tokens)
            if completion_tokens:
                span.set_attribute("llm.usage.completion_tokens", completion_tokens)
            if total_tokens:
                span.set_attribute("llm.usage.total_tokens", total_tokens)
            if error:
                span.set_status(Status(StatusCode.ERROR, error))
            else:
                span.set_attribute(
                    "llm.cost.usd",
                    estimate_cost_usd(span.attributes.get("llm.model", ""), prompt_tokens, completion_tokens),
                )
            span.end()
        except Exception:
            logger.debug("Failed to finish LLM span", exc_info=True)

    def _record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: Optional[float] = None,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Record token usage and update cost estimate."""
        cost = cost_usd if cost_usd is not None else estimate_cost_usd(model, prompt_tokens, completion_tokens)
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
                request_id=request_id or str(uuid.uuid4()),
                session_id=session_id,
                project_id=project_id,
            )
            get_cost_controller().check_request_budget(cost)
        except Exception:
            logger.debug("Failed to record LLM cost", exc_info=True)

        try:
            from homomics_lab.metrics import record_llm_usage

            record_llm_usage(model, prompt_tokens, completion_tokens, cost)
        except Exception:
            logger.debug("Failed to record LLM usage metrics", exc_info=True)

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
        intent_type: Optional[str] = None,
        task_type: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        return self._response
