"""Backward-compatible shim for intent analysis.

The real implementation now lives in ``homomics_lab.agent.intent``. This file
keeps the old ``IntentAnalyzer`` and ``UserIntent`` names importable so existing
code does not break.
"""

from pathlib import Path
from typing import Any, List, Optional

from homomics_lab.agent.intent import CascadeIntentAnalyzer, UserIntent


class IntentAnalyzer(CascadeIntentAnalyzer):
    """Backward-compatible intent analyzer.

    Supports the original constructor signature ``(intents_dir, use_domain_registry)``
    while delegating all behavior to the cascade analyzer.
    """

    def __init__(
        self,
        intents_dir: Optional[Path] = None,
        use_domain_registry: bool = True,
        **kwargs: Any,
    ):
        # Load legacy YAML intent definitions if intents_dir is provided.
        definitions: List[Any] = []
        if intents_dir is not None and intents_dir.exists():
            import yaml
            for yaml_file in intents_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        config = yaml.safe_load(f)
                    if isinstance(config, dict) and "analysis_type" in config:
                        definitions.append(config)
                except Exception:
                    continue

        super().__init__(
            definitions=definitions or None,
            use_domain_registry=use_domain_registry,
            **kwargs,
        )

        # Register any legacy YAML definitions at runtime.
        for config in definitions:
            analysis_type = config.get("analysis_type")
            if analysis_type:
                self.register_intent(analysis_type, config)


__all__ = ["IntentAnalyzer", "UserIntent"]
