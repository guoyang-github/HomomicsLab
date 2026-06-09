import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserIntent:
    analysis_type: str
    complexity: str  # direct_response, single_step, complex
    data_scale: Optional[str] = None
    urgency: str = "normal"
    domain_knowledge: list[str] = field(default_factory=list)


class IntentAnalyzer:
    """Rule-based intent analyzer (LLM-enhanced in Phase 2)."""

    SINGLE_CELL_KEYWORDS = [
        "单细胞", "single cell", "scRNA", "10x", "scanpy", "seurat",
        "PBMC", "细胞", "cell"
    ]

    SPATIAL_KEYWORDS = [
        "空间", "spatial", "visium", "xenium", "merfish"
    ]

    CONVERSION_KEYWORDS = [
        "转换", "convert", "格式", "format", "变成", "转成"
    ]

    QA_KEYWORDS = [
        "什么是", "how to", "怎么", "如何", "explain"
    ]

    COMPLEX_KEYWORDS = [
        "分析", "analysis", "流程", "pipeline", "全流程", "完整"
    ]

    async def analyze(self, message: str) -> UserIntent:
        text = message.lower()

        # Determine analysis type — QA keywords have highest priority
        if any(kw in text for kw in self.QA_KEYWORDS):
            analysis_type = "qa"
        elif any(kw in text for kw in self.SINGLE_CELL_KEYWORDS):
            analysis_type = "single_cell_analysis"
        elif any(kw in text for kw in self.SPATIAL_KEYWORDS):
            analysis_type = "spatial_analysis"
        elif any(kw in text for kw in self.CONVERSION_KEYWORDS):
            analysis_type = "file_conversion"
        else:
            analysis_type = "general"

        # Determine complexity
        if analysis_type == "qa":
            complexity = "direct_response"
        elif analysis_type == "file_conversion":
            complexity = "single_step"
        elif any(kw in text for kw in self.COMPLEX_KEYWORDS):
            complexity = "complex"
        else:
            complexity = "single_step"

        # Extract data scale hint
        data_scale = self._extract_data_scale(text)

        return UserIntent(
            analysis_type=analysis_type,
            complexity=complexity,
            data_scale=data_scale,
        )

    def _extract_data_scale(self, text: str) -> Optional[str]:
        patterns = [
            r'(\d+)\s*个细胞',
            r'(\d+)\s*cells',
            r'(\d+)k\s*cells',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
