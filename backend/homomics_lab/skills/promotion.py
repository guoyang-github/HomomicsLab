"""Transient skill promotion — turn a successful CodeAct run into a curated skill.

This closes the loop between ad-hoc code generation and reusable, version-locked
skills. A promoted skill starts as untrusted and becomes curated after human review.
"""

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.knowledge.cbkb import ParameterLoreEntry
from homomics_lab.skills.models import (
    SkillDefinition,
    SkillInputSchema,
    SkillOutputSchema,
    SkillRuntime,
)
from homomics_lab.skills.registry import SkillRegistry


class SkillPromotionError(Exception):
    """Raised when promotion of a transient skill fails."""

    pass


class TransientSkillPromoter:
    """Promote a CodeAct artifact into a curated skill package."""

    def __init__(
        self,
        skill_registry: SkillRegistry,
        cbkb: Optional[CBKB] = None,
    ):
        self.skill_registry = skill_registry
        self.cbkb = cbkb

    def create_package(
        self,
        source_dir: Path,
        skill_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "generated",
        author: str = "homomics-codeact",
    ) -> Path:
        """Create a skill package from a CodeAct work directory.

        Returns the path to the generated skill package directory. The caller
        (usually SkillStore.import_skill) can then persist and register it.
        """
        source_dir = Path(source_dir)
        code_file = source_dir / "__code_act_source__.py"
        result_file = source_dir / "__skill_result__.json"

        if not code_file.exists():
            raise SkillPromotionError(f"No generated code found in {source_dir}")

        code = code_file.read_text(encoding="utf-8")
        result: Dict[str, Any] = {}
        if result_file.exists():
            try:
                result = json.loads(result_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        generated_name = name or self._infer_name(code) or "generated_skill"
        skill_id = skill_id or self._sanitize_id(generated_name)

        package_dir = source_dir / f"promoted_{skill_id}"
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True)
        scripts_dir = package_dir / "scripts" / "python"
        scripts_dir.mkdir(parents=True)

        # New-spec skill: SKILL.md + scripts/python/core_analysis.py. There is
        # no fixed entrypoint; the runtime concatenates scripts as reference.
        main_script = scripts_dir / "core_analysis.py"
        main_script.write_text(self._wrap_as_skill(code), encoding="utf-8")

        skill_md = package_dir / "SKILL.md"
        skill_md.write_text(
            self._build_skill_md(
                skill_id=skill_id,
                name=generated_name,
                description=description or f"Auto-generated skill promoted from CodeAct run in {source_dir.name}",
                category=category,
                author=author,
                code=code,
                result=result,
            ),
            encoding="utf-8",
        )

        return package_dir

    def promote(
        self,
        source_dir: Path,
        skill_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "generated",
        author: str = "homomics-codeact",
        trusted: bool = False,
    ) -> SkillDefinition:
        """Promote a CodeAct work directory into a registered skill.

        This creates the package and registers it directly in the runtime
        SkillRegistry. For persistence, prefer using ``create_package`` +
        ``SkillStore.import_skill``.
        """
        package_dir = self.create_package(
            source_dir=source_dir,
            skill_id=skill_id,
            name=name,
            description=description,
            category=category,
            author=author,
        )

        code_file = source_dir / "__code_act_source__.py"
        code = code_file.read_text(encoding="utf-8")
        result: Dict[str, Any] = {}
        result_file = source_dir / "__skill_result__.json"
        if result_file.exists():
            try:
                result = json.loads(result_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        main_script = package_dir / "scripts" / "python" / "core_analysis.py"
        sha256 = self._hash_file(main_script)

        skill = SkillDefinition(
            id=skill_id or self._sanitize_id(name or self._infer_name(code) or "generated_skill"),
            name=name or self._infer_name(code) or "generated_skill",
            description=description or "Auto-generated skill promoted from CodeAct run",
            category=category,
            version="1.0.0",
            runtime=SkillRuntime(type="python"),
            input_schema=SkillInputSchema(
                properties={
                    "input_path": {"type": "string", "description": "Input file path"},
                    "output_path": {"type": "string", "description": "Output file path"},
                },
            ),
            output_schema=SkillOutputSchema(
                properties={
                    "result": {"type": "object", "description": "Result produced by the skill"},
                },
            ),
            metadata={
                "source": "generated",
                "scripts_dir": str(package_dir / "scripts" / "python"),
                "sha256": sha256,
                "promoted_from": str(source_dir),
                "promoted_at": datetime.now(timezone.utc).isoformat(),
                "trusted": trusted,
                "author": author,
                "generated_result": result,
            },
        )

        self.skill_registry.register(skill)

        if self.cbkb is not None:
            self._record_parameter_lore(skill, result)

        return skill

    @staticmethod
    def _infer_name(code: str) -> Optional[str]:
        """Infer a short skill name from the first scanpy/seurat operation."""
        lowered = code.lower()
        if "qc" in lowered or "filter" in lowered or "calculate_qc_metrics" in lowered:
            return "generated_qc"
        if "normalize" in lowered:
            return "generated_normalize"
        if "cluster" in lowered or "leiden" in lowered:
            return "generated_cluster"
        if "umap" in lowered or "plot" in lowered or "savefig" in lowered:
            return "generated_visualize"
        if "differential" in lowered or "wilcoxon" in lowered:
            return "generated_de"
        return None

    @staticmethod
    def _sanitize_id(name: str) -> str:
        """Convert a human name into a valid skill ID."""
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
        if not cleaned:
            cleaned = "generated_skill"
        return cleaned

    @staticmethod
    def _wrap_as_skill(code: str) -> str:
        """Wrap generated code into a skill script with standard result capture."""
        return f"""# Auto-generated skill script promoted from CodeAct
import json
import sys

# Inputs are expected to be provided by the skill runtime via stdin or globals.
# For promoted skills we keep the original code mostly intact.

{code}

if __name__ == "__main__":
    if 'result' not in locals():
        result = {{}}
    with open('__skill_result__.json', 'w') as f:
        json.dump(result, f)
"""

    @staticmethod
    def _build_skill_md(
        skill_id: str,
        name: str,
        description: str,
        category: str,
        author: str,
        code: str,
        result: Dict[str, Any],
    ) -> str:
        """Generate a SKILL.md front matter for the promoted skill."""
        return f"""---
name: {skill_id}
description: {description}
category: {category}
version: 1.0.0
author: {author}
runtime:
  type: python
tool_type: python
keywords: ["generated", "codeact", "{category}"]
inputs:
  input_path:
    type: string
    description: Path to input data file
    required: true
  output_path:
    type: string
    description: Path to write output
    default: ./output/result.h5ad
outputs:
  result:
    type: object
    description: Execution result
---

# {name}

{description}

## Generated Code

```python
{code}
```

## Example Result

```json
{json.dumps(result, indent=2, ensure_ascii=False)}
```
"""

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA-256 of a file."""
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def _record_parameter_lore(
        self,
        skill: SkillDefinition,
        result: Dict[str, Any],
    ) -> None:
        """Record a parameter lore entry so future plans can learn from this run."""
        if self.cbkb is None:
            return
        try:
            entry = ParameterLoreEntry(
                id=hashlib.sha256(f"{skill.id}:generated".encode()).hexdigest()[:16],
                skill_id=skill.id,
                param_name="generated",
                param_value="true",
                outcome_metric="promotion_success",
                outcome_value=1.0,
                project_id="codeact_promotion",
                context=f"Promoted from {skill.metadata.get('promoted_from', 'unknown')}",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self.cbkb.add_parameter_lore(entry)
        except Exception:
            pass
