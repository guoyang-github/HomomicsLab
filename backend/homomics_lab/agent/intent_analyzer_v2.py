"""Configuration-driven IntentAnalyzer (v2).

Replaces hardcoded keyword lists with domain-configurable intent definitions.
Intent configurations are loaded from:
1. DomainRegistry (from loaded domain.yaml files)
2. Legacy YAML intent files (backward compatibility)
3. Runtime registration (for dynamic domains)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from homomics_lab.domain.registry import get_domain_registry


@dataclass
class UserIntent:
    analysis_type: str
    complexity: str  # direct_response, single_step, complex
    data_scale: Optional[str] = None
    urgency: str = "normal"
    domain_knowledge: List[str] = field(default_factory=list)
    confidence: float = 1.0  # Intent matching confidence


class IntentAnalyzer:
    """Configuration-driven intent analyzer.

    Loads intent definitions from DomainRegistry and/or YAML files.
    Falls back to keyword matching with confidence scoring.
    """

    # Built-in QA keywords (domain-agnostic)
    QA_KEYWORDS = [
        "什么是", "how to", "怎么", "如何", "explain",
        "what is", "how do", "什么是", "解释",
    ]

    def __init__(
        self,
        intents_dir: Optional[Path] = None,
        use_domain_registry: bool = True,
    ):
        self.intents_dir = intents_dir
        self.use_domain_registry = use_domain_registry
        self._intent_configs: Dict[str, Dict] = {}
        self._load_all_intents()

    def _load_all_intents(self) -> None:
        """Load intent configurations from all sources."""
        # 1. Load from DomainRegistry
        if self.use_domain_registry:
            registry = get_domain_registry()
            for domain in registry.list_all():
                for intent in domain.intents:
                    self._intent_configs[intent.analysis_type] = {
                        "domain": domain.domain,
                        "keywords": intent.keywords,
                        "complexity_indicators": intent.complexity_indicators,
                        "data_scale_patterns": intent.data_scale_patterns,
                    }

        # 2. Load from legacy YAML files
        if self.intents_dir and self.intents_dir.exists():
            for yaml_file in self.intents_dir.glob("*.yaml"):
                with open(yaml_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if "analysis_type" in config:
                        self._intent_configs[config["analysis_type"]] = config

    def reload(self) -> None:
        """Reload intent configurations from all sources."""
        self._intent_configs.clear()
        self._load_all_intents()

    def register_intent(self, analysis_type: str, config: Dict) -> None:
        """Register an intent configuration at runtime."""
        self._intent_configs[analysis_type] = config

    async def analyze(self, message: str) -> UserIntent:
        """Analyze user message and return structured intent."""
        text = message.lower()

        # 1. QA check (highest priority, domain-agnostic)
        if any(kw in text for kw in self.QA_KEYWORDS):
            return UserIntent(
                analysis_type="qa",
                complexity="direct_response",
                confidence=1.0,
            )

        # 2. Domain-specific intent matching with confidence scoring
        best_match = None
        best_score = 0.0

        for analysis_type, config in self._intent_configs.items():
            score = self._calculate_match_score(text, config)
            if score > best_score:
                best_score = score
                best_match = (analysis_type, config)

        # Threshold: require at least one keyword match
        if best_match and best_score > 0:
            analysis_type, config = best_match
            complexity = self._determine_complexity(text, config)
            data_scale = self._extract_data_scale(text, config)
            domain = config.get("domain", "")

            return UserIntent(
                analysis_type=analysis_type,
                complexity=complexity,
                data_scale=data_scale,
                domain_knowledge=[domain] if domain else [],
                confidence=best_score,
            )

        # 3. Fallback: generic analysis
        return UserIntent(
            analysis_type="general",
            complexity="single_step",
            confidence=0.0,
        )

    def _calculate_match_score(self, text: str, config: Dict) -> float:
        """Calculate intent matching confidence score (0.0 - 1.0+)."""
        keywords = config.get("keywords", [])
        if not keywords:
            return 0.0

        matches = sum(1 for kw in keywords if kw.lower() in text)
        if matches == 0:
            return 0.0

        # Score = match ratio * match count (more matches = higher confidence)
        ratio = matches / len(keywords)
        return ratio + (matches * 0.1)

    def _determine_complexity(self, text: str, config: Dict) -> str:
        """Determine analysis complexity from message and config."""
        indicators = config.get("complexity_indicators", [])
        if any(kw.lower() in text for kw in indicators):
            return "complex"
        # Heuristic: multiple keywords or long message = complex
        if len(text.split()) > 15:
            return "complex"
        return "single_step"

    def _extract_data_scale(self, text: str, config: Dict) -> Optional[str]:
        """Extract data scale hints using configured patterns."""
        patterns = config.get("data_scale_patterns", [])
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        # Universal patterns
        universal_patterns = [
            r'(\d+)\s*个细胞',
            r'(\d+)\s*cells',
            r'(\d+)k\s*cells',
            r'(\d+)\s*个样本',
            r'(\d+)\s*samples',
            r'(\d+)\s*个基因',
            r'(\d+)\s*genes',
        ]
        for pattern in universal_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

    def list_registered_intents(self) -> Dict[str, Dict]:
        """Return all registered intent configurations."""
        return dict(self._intent_configs)
