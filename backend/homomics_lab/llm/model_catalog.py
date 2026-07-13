"""Model catalog for task-aware LLM routing.

The catalog stores static metadata about known models (capabilities, context
window, pricing) and can be overridden from a JSON file in ``data_dir``.
``LLMRouter`` consults it when a ``task_type`` is supplied, so the best model
for a given cognitive task can be chosen without hard-coding per-call logic.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from homomics_lab.config import settings

logger = logging.getLogger(__name__)

ModelCapability = Literal[
    "qa",
    "code",
    "planning",
    "tool_use",
    "long_context",
    "vision",
    "cheap",
]

_TASK_CAPABILITY_MAP: Dict[str, List[ModelCapability]] = {
    "qa": ["qa"],
    "code": ["code"],
    "code_generation": ["code"],
    "planning": ["planning"],
    "tool_use": ["tool_use"],
    "tool_call": ["tool_use"],
    "long_context": ["long_context"],
    "vision": ["vision"],
    "cheap": ["cheap"],
}


def _risk_level_for_task(task_type: str) -> str:
    """Map well-known tasks to a default risk level for auto-approval checks."""
    # This is intentionally simple; callers that care should pass explicit caps.
    return "low"


class ModelInfo(BaseModel):
    """Static metadata describing a single LLM offering."""

    id: str
    provider: str
    name: str
    capabilities: List[ModelCapability] = Field(default_factory=list)
    context_window: int = 128_000
    cost_per_1k_input_usd: float = 0.0
    cost_per_1k_output_usd: float = 0.0
    supports_temperature: bool = True
    enabled: bool = True


class ModelCatalog:
    """Catalog of known LLMs with capability-aware matching."""

    _DEFAULT_MODELS: List[ModelInfo] = [
        ModelInfo(
            id="gpt-4o",
            provider="openai",
            name="GPT-4o",
            capabilities=["qa", "code", "planning", "tool_use", "long_context", "vision"],
            context_window=128_000,
            cost_per_1k_input_usd=2.5,
            cost_per_1k_output_usd=10.0,
        ),
        ModelInfo(
            id="gpt-4o-mini",
            provider="openai",
            name="GPT-4o mini",
            capabilities=["qa", "code", "tool_use", "long_context", "cheap"],
            context_window=128_000,
            cost_per_1k_input_usd=0.15,
            cost_per_1k_output_usd=0.6,
        ),
        ModelInfo(
            id="claude-3-5-sonnet-latest",
            provider="anthropic",
            name="Claude 3.5 Sonnet",
            capabilities=["qa", "code", "planning", "tool_use", "long_context"],
            context_window=200_000,
            cost_per_1k_input_usd=3.0,
            cost_per_1k_output_usd=12.0,
        ),
        ModelInfo(
            id="kimi-k2.5",
            provider="moonshot",
            name="Kimi K2.5",
            capabilities=["qa", "code", "planning", "tool_use", "long_context"],
            context_window=256_000,
            cost_per_1k_input_usd=1.2,
            cost_per_1k_output_usd=3.6,
        ),
        ModelInfo(
            id="deepseek-chat",
            provider="deepseek",
            name="DeepSeek Chat",
            capabilities=["qa", "code", "tool_use", "cheap"],
            context_window=64_000,
            cost_per_1k_input_usd=0.14,
            cost_per_1k_output_usd=0.28,
        ),
        ModelInfo(
            id="deepseek-coder",
            provider="deepseek",
            name="DeepSeek Coder",
            capabilities=["code", "planning", "tool_use"],
            context_window=64_000,
            cost_per_1k_input_usd=0.14,
            cost_per_1k_output_usd=0.28,
        ),
        ModelInfo(
            id="qwen-turbo",
            provider="qwen",
            name="Qwen Turbo",
            capabilities=["qa", "tool_use", "cheap"],
            context_window=128_000,
            cost_per_1k_input_usd=0.3,
            cost_per_1k_output_usd=0.6,
        ),
        ModelInfo(
            id="qwen-max",
            provider="qwen",
            name="Qwen Max",
            capabilities=["qa", "code", "planning", "tool_use", "long_context"],
            context_window=32_000,
            cost_per_1k_input_usd=2.4,
            cost_per_1k_output_usd=4.8,
        ),
        ModelInfo(
            id="llama3.1",
            provider="ollama",
            name="Llama 3.1",
            capabilities=["qa", "code", "tool_use"],
            context_window=128_000,
            cost_per_1k_input_usd=0.0,
            cost_per_1k_output_usd=0.0,
        ),
        ModelInfo(
            id="glm-4-flash",
            provider="zhipu",
            name="GLM-4 Flash",
            capabilities=["qa", "tool_use", "cheap"],
            context_window=128_000,
            cost_per_1k_input_usd=0.0,
            cost_per_1k_output_usd=0.0,
        ),
    ]

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = data_dir or settings.data_dir
        self._models: Dict[str, ModelInfo] = {}
        self._load()

    def _catalog_path(self) -> Path:
        return self._data_dir / "llm_model_catalog.json"

    def _load(self) -> None:
        """Load catalog from disk or fall back to the built-in list."""
        path = self._catalog_path()
        loaded: List[ModelInfo] = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    loaded = [ModelInfo(**item) for item in data]
                else:
                    logger.warning("Model catalog file is not a list; using defaults")
            except Exception as exc:
                logger.warning("Failed to load model catalog: %s", exc)

        if not loaded:
            loaded = list(self._DEFAULT_MODELS)

        self._models = {m.id: m for m in loaded}

    def get(self, model_id: str) -> Optional[ModelInfo]:
        """Return metadata for a single model."""
        return self._models.get(model_id)

    def list_all(self) -> List[ModelInfo]:
        """Return all known models."""
        return list(self._models.values())

    def list_enabled(self) -> List[ModelInfo]:
        """Return models that are not disabled in the catalog."""
        return [m for m in self._models.values() if m.enabled]

    def match(
        self,
        task_type: str,
        prefer_cheap: bool = False,
        required_capabilities: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], str]:
        """Pick the best model for ``task_type``.

        Returns:
            A tuple of ``(model_id, reason)``.  If no model matches the requested
            capabilities, returns ``(None, "")``.
        """
        if required_capabilities:
            needed = [c for c in required_capabilities if c]
        else:
            needed = list(_TASK_CAPABILITY_MAP.get(task_type, []))

        candidates = [
            m for m in self.list_enabled()
            if all(cap in m.capabilities for cap in needed)
        ]
        if not candidates:
            return None, ""

        if prefer_cheap:
            candidates.sort(
                key=lambda m: (
                    m.cost_per_1k_input_usd + m.cost_per_1k_output_usd,
                    -m.context_window,
                )
            )
            best = candidates[0]
            return best.id, f"cheapest model for {task_type}"

        # Prefer capability breadth and context window, then cost.
        candidates.sort(
            key=lambda m: (
                -(len(m.capabilities)),
                -m.context_window,
                m.cost_per_1k_input_usd + m.cost_per_1k_output_usd,
            )
        )
        best = candidates[0]
        return best.id, f"best capability match for {task_type}"

    def reload(self) -> None:
        """Reload the catalog from disk."""
        self._load()


def get_model_catalog() -> ModelCatalog:
    """Return the global model catalog singleton."""
    return ModelCatalog()
