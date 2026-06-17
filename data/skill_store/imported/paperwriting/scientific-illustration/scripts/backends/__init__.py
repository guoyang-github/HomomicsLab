"""
Backend registry and auto-detection for scientific schematic generation.

Three backends are available, selected automatically in this priority:
1. APIBackend    - External image generation API (needs config + key)
2. GraphvizBackend - Local structured diagram generation (needs graphviz)
3. SpecBackend   - Fallback: generate a spec JSON for LLM/agent to process
"""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


def _load_ai_config(script_dir: Path) -> Dict[str, Any]:
    """Load AI model configuration from JSON file."""
    config_path = script_dir / "config" / "ai_models.json"
    defaults: Dict[str, Any] = {
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "image_generation_model": "google/gemini-2.0-flash-exp:free",
        "quality_thresholds": {
            "journal": 8.5, "conference": 8.0, "poster": 7.0,
            "presentation": 6.5, "report": 7.5, "grant": 8.0,
            "thesis": 8.0, "preprint": 7.5, "default": 7.5,
        },
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


def _get_env_key_name(script_dir: Path) -> str:
    """Read env_key_name from config, fallback to OPENROUTER_API_KEY."""
    config_path = script_dir / "config" / "ai_models.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("env_key_name", "OPENROUTER_API_KEY")
        except Exception:
            pass
    return "OPENROUTER_API_KEY"


def _has_api_config(script_dir: Path) -> bool:
    """Check if API config exists and the corresponding key is available."""
    config = _load_ai_config(script_dir)
    env_key = config.get("env_key_name", "OPENROUTER_API_KEY")
    return os.getenv(env_key) is not None


def _has_graphviz() -> bool:
    """Check if graphviz is available (both Python package and system binary)."""
    try:
        import graphviz
        import shutil
        return shutil.which("dot") is not None
    except ImportError:
        return False


class Backend(ABC):
    """Abstract base class for image generation backends."""

    @abstractmethod
    def generate(self, prompt: str, output_path: Path, doc_type: str = "default",
                 iterations: int = 2, verbose: bool = False) -> Dict[str, Any]:
        """Generate image and return result dict with success, path, mode, etc."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""


def detect_backend(script_dir: Path) -> Backend:
    """Auto-detect the best available backend."""
    from .api import APIBackend
    from .graphviz import GraphvizBackend
    from .spec import SpecBackend

    if _has_api_config(script_dir):
        return APIBackend(script_dir)
    if _has_graphviz():
        return GraphvizBackend(script_dir)
    return SpecBackend(script_dir)
