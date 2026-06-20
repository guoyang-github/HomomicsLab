"""Resolve HITL checkpoints using previously learned user preferences."""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from homomics_lab.preferences.store import UserPreferenceStore

logger = logging.getLogger(__name__)


class HITLPreferenceResolver:
    """Auto-resolve checkpoints that closely match historical preferences."""

    def __init__(self, preference_store: UserPreferenceStore) -> None:
        self.preference_store = preference_store

    @staticmethod
    def _context_hash(checkpoint: Dict[str, Any]) -> str:
        """Stable hash of checkpoint content used for similarity lookup."""
        content = checkpoint.get("context_summary", "")
        options = checkpoint.get("options", [])
        payload = json.dumps({"context": content, "options": options}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def try_resolve(
        self,
        project_id: str,
        checkpoint: Dict[str, Any],
        similarity_threshold: float = 0.85,
    ) -> Optional[Dict[str, Any]]:
        """Return a resolution if a stored preference applies.

        Resolution includes:
            - choice: selected option id
            - parameters: stored parameter overrides
            - source: "exact" | "scope_default"
            - importance: preference importance score
        """
        scope_type = checkpoint.get("metadata", {}).get("scope_type", "checkpoint")
        scope_id = checkpoint.get("metadata", {}).get("scope_id")
        context_hash = self._context_hash(checkpoint)

        # Exact hash match.
        exact = self.preference_store.get(
            project_id=project_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        for pref in exact:
            if pref.get("context_hash") == context_hash:
                value = json.loads(pref["value"]) if isinstance(pref["value"], str) else pref["value"]
                return {
                    "choice": value.get("choice"),
                    "parameters": value.get("parameters", {}),
                    "source": "exact",
                    "importance": pref.get("importance", 0.5),
                }

        # Scope-level default (e.g. default for a skill/phase).
        scope_default = self.preference_store.get_default(
            project_id=project_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        if isinstance(scope_default, dict) and scope_default.get("choice"):
            return {
                "choice": scope_default["choice"],
                "parameters": scope_default.get("parameters", {}),
                "source": "scope_default",
                "importance": scope_default.get("importance", 0.5),
            }

        return None

    def record_resolution(
        self,
        project_id: str,
        checkpoint: Dict[str, Any],
        choice: str,
        parameters: Optional[Dict[str, Any]] = None,
        importance: float = 0.7,
        remember: bool = True,
    ) -> None:
        """Store a resolved HITL choice as a learned preference."""
        if not remember:
            return

        scope_type = checkpoint.get("metadata", {}).get("scope_type", "checkpoint")
        scope_id = checkpoint.get("metadata", {}).get("scope_id")
        context_hash = self._context_hash(checkpoint)
        value = {"choice": choice, "parameters": parameters or {}}

        try:
            self.preference_store.record(
                project_id=project_id,
                scope_type=scope_type,
                scope_id=scope_id,
                key=None,
                value=value,
                preference_type="default",
                importance=importance,
                context_hash=context_hash,
            )
        except Exception as exc:
            logger.warning("Failed to record HITL preference: %s", exc)

    def record_parameter_default(
        self,
        project_id: str,
        scope_type: str,
        scope_id: str,
        key: str,
        value: Any,
        importance: float = 0.6,
    ) -> None:
        """Store a parameter default learned from user behavior or CBKB lore."""
        try:
            self.preference_store.record(
                project_id=project_id,
                scope_type=scope_type,
                scope_id=scope_id,
                key=key,
                value=value,
                preference_type="default",
                importance=importance,
            )
        except Exception as exc:
            logger.warning("Failed to record parameter preference: %s", exc)
