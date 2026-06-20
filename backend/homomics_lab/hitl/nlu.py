"""Natural-language parsing for free-text HITL responses."""

import re
from typing import Any, Dict, List, Optional


class HITLNLUParser:
    """Map free-text user replies to HITL checkpoint options and parameters."""

    # Common affirmative / negative patterns (Chinese + English)
    AFFIRMATIVE_PATTERNS = [
        r"^(?:yes|yep|yeah|sure|ok|okay|go ahead|proceed|confirm|accept|continue|用默认值|默认|是的|确定|同意|继续|执行|好|行)",
    ]
    NEGATIVE_PATTERNS = [
        r"^(?:no|nope|skip|cancel|reject|stop|abort|否|不|跳过|取消|拒绝|停止)",
    ]
    MODIFY_PATTERNS = [
        r"^(?:modify|change|edit|adjust|update|调整|修改|更改|换|改)",
    ]

    @classmethod
    def parse(
        cls,
        text: str,
        options: List[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Parse a free-text HITL reply.

        Returns a dict with keys:
            - choice: matched option id (or best guess)
            - parameters: extracted/overridden parameters
            - confidence: "high" | "medium" | "low"
        """
        text_lower = text.strip().lower()
        if not text_lower:
            return {"choice": None, "parameters": {}, "confidence": "low"}

        parameters = parameters or {}
        extracted: Dict[str, Any] = {}

        # Try direct option label/id match.
        for opt in options:
            opt_id = str(opt.get("id", "")).lower()
            opt_label = str(opt.get("label", "")).lower()
            if opt_id and opt_id in text_lower:
                return {"choice": opt["id"], "parameters": extracted, "confidence": "high"}
            if opt_label and opt_label in text_lower:
                return {"choice": opt["id"], "parameters": extracted, "confidence": "high"}

        # Sentiment-based mapping to the first two common options.
        if any(re.search(p, text_lower) for p in cls.AFFIRMATIVE_PATTERNS):
            choice = cls._find_option(options, ["proceed", "accept", "continue", "yes"])
            if choice:
                return {"choice": choice, "parameters": extracted, "confidence": "medium"}
        if any(re.search(p, text_lower) for p in cls.NEGATIVE_PATTERNS):
            choice = cls._find_option(options, ["cancel", "skip", "reject", "no"])
            if choice:
                return {"choice": choice, "parameters": extracted, "confidence": "medium"}
        if any(re.search(p, text_lower) for p in cls.MODIFY_PATTERNS):
            choice = cls._find_option(options, ["modify", "change", "edit"])
            if choice:
                return {"choice": choice, "parameters": extracted, "confidence": "medium"}

        # Parameter extraction: "key=value" or "key: value"
        param_pattern = re.compile(r"(\w+)\s*[:=]\s*([^\s,;]+)")
        for match in param_pattern.finditer(text):
            key, value = match.groups()
            extracted[key] = cls._coerce_value(value)

        # If numeric parameters were extracted but no explicit choice, assume
        # the user wants to modify/confirm with new parameters.
        if extracted:
            choice = cls._find_option(options, ["modify", "change", "proceed", "accept"])
            if choice:
                return {"choice": choice, "parameters": extracted, "confidence": "low"}

        return {"choice": None, "parameters": extracted, "confidence": "low"}

    @staticmethod
    def _find_option(options: List[Dict[str, Any]], candidates: List[str]) -> Optional[str]:
        for opt in options:
            opt_id = str(opt.get("id", "")).lower()
            if opt_id in candidates:
                return opt["id"]
        return None

    @staticmethod
    def _coerce_value(value: str) -> Any:
        if value.lower() in {"true", "yes", "是"}:
            return True
        if value.lower() in {"false", "no", "否"}:
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value
