"""
Backend registry and auto-detection for slide image generation.

Three backends are available, selected automatically in this priority:
1. APIBackend    - External image generation API (needs config + key)
2. PPTXBackend   - Local PowerPoint generation (needs python-pptx)
3. SpecBackend   - Fallback: generate a spec JSON for LLM/agent to process
"""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


def _load_ai_config(script_dir: Path) -> Dict[str, Any]:
    """Load AI model configuration from JSON file."""
    config_path = script_dir / "config" / "ai_models.json"
    defaults: Dict[str, Any] = {
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "image_generation_model": "google/gemini-2.0-flash-exp:free",
        "quality_threshold": 6.5,
        "request_timeout": 120,
        "max_iterations": 2,
    }
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            merged = {**defaults, **config}
            return merged
        except (json.JSONDecodeError, OSError):
            return defaults
    return defaults


def _has_api_config(script_dir: Path) -> bool:
    """Check if API config exists and the corresponding key is available."""
    config = _load_ai_config(script_dir)
    env_key = config.get("env_key_name", "OPENROUTER_API_KEY")
    return os.getenv(env_key) is not None


def _has_pptx() -> bool:
    """Check if python-pptx is available."""
    try:
        import pptx
        return True
    except ImportError:
        return False


class Backend(ABC):
    """Abstract base class for slide generation backends."""

    @abstractmethod
    def generate(self, prompt: str, output_path: Path, visual_only: bool = False,
                 iterations: int = 2, verbose: bool = False) -> Dict[str, Any]:
        """Generate slide/visual and return result dict."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""


def detect_backend(script_dir: Path) -> Backend:
    """Auto-detect the best available backend."""
    from .api import APIBackend
    from .pptx import PPTXBackend
    from .spec import SpecBackend

    if _has_api_config(script_dir):
        return APIBackend(script_dir)
    if _has_pptx():
        return PPTXBackend(script_dir)
    return SpecBackend(script_dir)
