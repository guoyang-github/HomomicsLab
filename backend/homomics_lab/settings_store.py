"""Runtime settings store for non-sensitive configuration overrides.

Allows the frontend Settings panel to update operational parameters (sandbox
backend, memory toggles, budgets, retention) without restarting the server.
Values are persisted to a JSON file under ``settings.data_dir`` and applied to
the in-memory ``Settings`` object immediately.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from homomics_lab.config import Settings, settings

logger = logging.getLogger(__name__)

RUNTIME_SETTINGS_FILE = "runtime_settings.json"


class RuntimeSettings(BaseModel):
    """Whitelist of settings that can be changed at runtime via the API."""

    skill_sandbox_backend: Optional[str] = Field(
        default=None,
        description="Sandbox backend: auto | local | bubblewrap | container",
    )
    enable_semantic_memory: Optional[bool] = Field(
        default=None,
        description="Whether semantic memory (sqlite-vec) is enabled.",
    )
    semantic_search_model: Optional[str] = Field(
        default=None,
        description="Sentence-transformers model name; empty disables semantic memory.",
    )
    session_ttl_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Session retention period in days.",
    )
    default_job_timeout_seconds: Optional[float] = Field(
        default=None,
        ge=1,
        description="Default timeout for background jobs.",
    )
    max_skill_timeout_seconds: Optional[float] = Field(
        default=None,
        ge=1,
        description="Maximum allowed per-skill timeout.",
    )
    result_inline_size_limit_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Results larger than this are stored as file references.",
    )
    max_llm_cost_per_request_usd: Optional[float] = Field(
        default=None,
        ge=0,
        description="Per-request LLM cost cap.",
    )
    monthly_budget_usd: Optional[float] = Field(
        default=None,
        ge=0,
        description="Monthly spend cap (enforced when auth is enabled).",
    )
    skill_hot_reload_enabled: Optional[bool] = Field(
        default=None,
        description="Watch sibling skill repos and domain files at startup.",
    )

    @field_validator("skill_sandbox_backend")
    @classmethod
    def _validate_sandbox_backend(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"auto", "local", "bubblewrap", "container"}
        if v not in allowed:
            raise ValueError(f"skill_sandbox_backend must be one of {allowed}, got {v}")
        return v

    def to_filtered_dict(self) -> Dict[str, Any]:
        """Return only explicitly set (non-None) values."""
        return self.model_dump(exclude_none=True)


def _runtime_settings_path() -> Path:
    """Return the path to the runtime settings JSON file."""
    path = settings.data_dir / ".metadata" / RUNTIME_SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_runtime_settings() -> Dict[str, Any]:
    """Load persisted runtime overrides.

    Returns an empty dict if the file does not exist or is corrupt.
    """
    path = _runtime_settings_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Runtime settings file is not a dict; ignoring")
            return {}
        return data
    except Exception as exc:
        logger.warning("Failed to load runtime settings: %s", exc)
        return {}


def save_runtime_settings(updates: Dict[str, Any]) -> RuntimeSettings:
    """Validate, merge and persist runtime setting overrides.

    Args:
        updates: Dict of setting keys to new values.

    Returns:
        The validated RuntimeSettings object.
    """
    current = load_runtime_settings()
    merged = {**current, **updates}
    validated = RuntimeSettings(**merged)
    filtered = validated.to_filtered_dict()

    path = _runtime_settings_path()
    path.write_text(
        json.dumps(filtered, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return validated


def apply_runtime_settings(target: Optional[Settings] = None) -> Settings:
    """Load persisted runtime settings and apply them to a Settings object.

    This should be called once at startup, before components that depend on
    these values are initialized.
    """
    target = target or settings
    data = load_runtime_settings()
    if not data:
        return target

    try:
        validated = RuntimeSettings(**data)
    except Exception as exc:
        logger.warning("Invalid runtime settings on disk: %s", exc)
        return target

    for key, value in validated.to_filtered_dict().items():
        if hasattr(target, key):
            setattr(target, key, value)
            logger.debug("Applied runtime setting: %s = %s", key, value)
        else:
            logger.warning("Runtime setting '%s' does not exist on Settings", key)

    # If semantic memory is enabled but no model is configured, disable it to
    # avoid startup failures when sentence-transformers is unavailable.
    if target.enable_semantic_memory and not target.semantic_search_model:
        logger.warning(
            "enable_semantic_memory is true but semantic_search_model is unset; "
            "disabling semantic memory"
        )
        target.enable_semantic_memory = False

    return target
