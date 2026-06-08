import re
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ContextSummary:
    key_conclusions: List[str] = field(default_factory=list)
    key_parameters: Dict[str, str] = field(default_factory=dict)
    key_results: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    full_text_hash: str = ""
    storage_location: str = ""


class ContextSummarizer:
    """Extract structured summaries from long context items."""

    def __init__(self, max_length: int = 1000):
        self.max_length = max_length

    def summarize(self, text: str, summary_type: str = "result") -> ContextSummary:
        summary = ContextSummary()

        # Extract key conclusions (first sentence + result sentences)
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if sentences:
            summary.key_conclusions.append(sentences[0][:200])

        for sentence in sentences:
            if any(kw in sentence.lower() for kw in ["final", "result", "output", "contains", "identified"]):
                if sentence not in summary.key_conclusions:
                    summary.key_conclusions.append(sentence[:200])

        summary.key_conclusions = summary.key_conclusions[:5]

        # Extract parameters
        summary.key_parameters = self._extract_parameters(text)

        # Extract warnings
        summary.warnings = self._extract_warnings(text)

        return summary

    def _extract_parameters(self, text: str) -> Dict[str, str]:
        params = {}
        # Match patterns like "key=value" or "key: value"
        patterns = [
            r'(\w+)[=:](\d+(?:\.\d+)?)',
            r'(\w+)[=:](\w+)',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                key, value = match.groups()
                params[key] = value
        return params

    def _extract_warnings(self, text: str) -> List[str]:
        warnings = []
        for sentence in text.split("."):
            if any(kw in sentence.lower() for kw in ["warning", "caution", "note", "attention", "error"]):
                warnings.append(sentence.strip())
        return warnings[:3]
