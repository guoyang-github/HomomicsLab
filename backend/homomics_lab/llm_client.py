"""Minimal async LLM client for runtime use.

Currently wraps OpenAI's async API and reads OPENAI_API_KEY from the
environment. If no key is available, the client degrades gracefully so that
tests and offline usage do not crash.
"""

import os
from typing import Any, Dict, List, Optional


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

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()

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
