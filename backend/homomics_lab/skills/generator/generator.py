"""Skill generator from natural language requirements."""

import re
from pathlib import Path
from typing import Dict, List, Optional

from .templates import SkillTemplateBuilder


class SkillGenerator:
    """Generate new skills from user requirements."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.builder = SkillTemplateBuilder()
        self.output_dir = output_dir or Path("./generated_skills")

    def generate(
        self,
        name: str,
        description: str,
        category: str = "custom",
        tool_type: str = "python",
        primary_tool: str = "",
        supported_tools: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        inputs: Optional[List[Dict[str, str]]] = None,
        outputs: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Generate a complete skill package.

        Returns dict with file paths as keys and content as values.
        """
        # Normalize name
        skill_id = self._normalize_name(name)

        supported_tools = supported_tools or []
        keywords = keywords or []
        inputs = inputs or []
        outputs = outputs or []
        dependencies = dependencies or []

        # Infer primary tool if not provided
        if not primary_tool and supported_tools:
            primary_tool = supported_tools[0]

        # Generate files
        files = {}

        files[f"{skill_id}/SKILL.md"] = self.builder.build_skill_md(
            name=skill_id,
            description=description,
            category=category,
            tool_type=tool_type,
            primary_tool=primary_tool,
            supported_tools=supported_tools,
            keywords=keywords,
            inputs=inputs,
            outputs=outputs,
            dependencies=dependencies,
        )

        if tool_type == "python":
            script_dir = f"{skill_id}/scripts/python"
            files[f"{script_dir}/run.py"] = self.builder.build_python_script(
                name=skill_id,
                description=description,
                inputs=inputs,
                outputs=outputs,
            )
        elif tool_type == "r":
            script_dir = f"{skill_id}/scripts/r"
            files[f"{script_dir}/run.R"] = self.builder.build_r_script(
                name=skill_id,
                description=description,
                inputs=inputs,
                outputs=outputs,
            )
        elif tool_type == "mixed":
            files[f"{skill_id}/scripts/python/run.py"] = self.builder.build_python_script(
                name=skill_id,
                description=description,
                inputs=inputs,
                outputs=outputs,
            )
            files[f"{skill_id}/scripts/r/run.R"] = self.builder.build_r_script(
                name=skill_id,
                description=description,
                inputs=inputs,
                outputs=outputs,
            )

        if tool_type in ("python", "mixed") and dependencies:
            files[f"{skill_id}/scripts/python/requirements.txt"] = self.builder.build_requirements_txt(dependencies)

        return files

    def save(self, files: Dict[str, str]) -> Path:
        """Save generated files to disk."""
        base_dir = self.output_dir
        base_dir.mkdir(parents=True, exist_ok=True)

        for relative_path, content in files.items():
            file_path = base_dir / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        return base_dir

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Convert name to skill ID format."""
        # Lowercase, replace spaces/special chars with hyphens
        normalized = re.sub(r"[^a-zA-Z0-9_\- ]", "", name.lower())
        normalized = normalized.replace(" ", "-").replace("_", "-")
        # Remove consecutive hyphens
        normalized = re.sub(r"-+", "-", normalized)
        return normalized.strip("-")

    def suggest_from_description(
        self,
        description: str,
    ) -> Dict[str, str]:
        """Suggest skill parameters from a natural language description.

        Simple heuristic-based suggestion. In production, this could use LLM.
        """
        desc_lower = description.lower()

        # Infer tool type
        if any(kw in desc_lower for kw in ["seurat", "deseq2", "ggplot", "monocle"]):
            tool_type = "r"
        elif any(kw in desc_lower for kw in ["python", "scanpy", "squidpy", "anndata"]):
            tool_type = "python"
        else:
            tool_type = "python"

        # Infer category
        if any(kw in desc_lower for kw in ["single cell", "scrna", "clustering cells", "cell type"]):
            category = "single-cell"
        elif "spatial" in desc_lower:
            category = "spatial-transcriptomics"
        elif "genomics" in desc_lower or "dna" in desc_lower:
            category = "genomics"
        elif "proteomics" in desc_lower or "protein" in desc_lower:
            category = "proteomics"
        else:
            category = "custom"

        # Extract keywords
        keywords = []
        keyword_map = {
            "cluster": ["clustering", "clusters", "louvain", "leiden"],
            "qc": ["quality control", "filter", "qc"],
            "visual": ["visualization", "plot", "umap", "tsne"],
            "de": ["differential expression", "de", "deg"],
            "annotation": ["annotate", "cell type", "marker"],
        }
        for kw, triggers in keyword_map.items():
            if any(t in desc_lower for t in triggers):
                keywords.append(kw)

        if not keywords:
            keywords = ["analysis"]

        return {
            "tool_type": tool_type,
            "category": category,
            "keywords": ", ".join(keywords),
        }
