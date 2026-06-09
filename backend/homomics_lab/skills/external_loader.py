"""Load external skills from NanoResearch-Skills compatible directories."""

import re
from pathlib import Path
from typing import Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillOutputSchema, SkillRuntime
from homomics_lab.skills.registry import SkillRegistry


def _parse_frontmatter(content: str) -> tuple[Dict, str]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, remaining_markdown).
    """
    if not content.startswith("---"):
        return {}, content

    # Find the end of frontmatter
    match = re.search(r"^---\s*\n(.*?)^---\s*\n", content, re.DOTALL | re.MULTILINE)
    if not match:
        return {}, content

    yaml_text = match.group(1)
    remaining = content[match.end():]

    # Simple YAML parsing for the subset we need
    frontmatter = _simple_yaml_parse(yaml_text)
    return frontmatter, remaining


def _simple_yaml_parse(text: str) -> Dict:
    """Parse a simple subset of YAML (no nested objects beyond one level).

    Handles:
    - key: value
    - key: [list, items]
    - key:
        nested_key: value
        nested_key2: value
    """
    result: Dict = {}
    lines = text.split("\n")
    i = 0
    current_nested_key = None
    current_nested: Dict = {}

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Check if it's a nested block start
        if stripped.endswith(":") and not _is_inline_value(stripped):
            # Check next lines for indentation
            key = stripped[:-1].strip()
            nested = {}
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if not next_line.strip():
                    j += 1
                    continue
                if next_line.startswith(" ") or next_line.startswith("\t"):
                    # It's part of the nested block
                    nested_match = re.match(r"^\s+(\w+):\s*(.*)$", next_line)
                    if nested_match:
                        n_key, n_value = nested_match.groups()
                        nested[n_key] = _parse_yaml_value(n_value.strip())
                    j += 1
                else:
                    break
            result[key] = nested
            i = j
            continue

        # Simple key-value
        match = re.match(r"^(\w+):\s*(.*)$", stripped)
        if match:
            key, value = match.groups()
            result[key] = _parse_yaml_value(value.strip())

        i += 1

    return result


def _is_inline_value(line: str) -> bool:
    """Check if a line has an inline value after the colon."""
    parts = line.split(":", 1)
    return len(parts) > 1 and parts[1].strip()


def _parse_yaml_value(value: str):
    """Parse a YAML value string."""
    value = value.strip()

    # Empty string
    if not value:
        return None

    # Boolean
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # List
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        if not inner.strip():
            return []
        items = []
        for item in _split_list_items(inner):
            parsed = _parse_yaml_value(item.strip())
            items.append(parsed)
        return items

    # Quoted string
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]

    # Number
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # Plain string
    return value


def _split_list_items(text: str) -> List[str]:
    """Split comma-separated list items, respecting quotes."""
    items = []
    current = []
    in_quotes = None
    for char in text:
        if char in ('"', "'"):
            if in_quotes == char:
                in_quotes = None
            elif in_quotes is None:
                in_quotes = char
            current.append(char)
        elif char == "," and in_quotes is None:
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        items.append("".join(current))
    return items


def _extract_category_from_keywords(keywords: List[str], skill_name: str) -> str:
    """Extract category from skill keywords or name."""
    category_keywords = {
        "single-cell": "single-cell",
        "spatial-transcriptomics": "spatial-transcriptomics",
        "spatial": "spatial-transcriptomics",
        "workflows": "workflows",
        "workflow": "workflows",
    }

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in category_keywords:
            return category_keywords[kw_lower]

    # Infer from name prefix
    name_lower = skill_name.lower()
    if name_lower.startswith("bio-single-cell-"):
        return "single-cell"
    elif name_lower.startswith("bio-spatial-"):
        return "spatial-transcriptomics"
    elif name_lower.startswith("bio-workflows-"):
        return "workflows"

    return "general"


class ExternalSkillLoader:
    """Load skills from external NanoResearch-Skills compatible directories."""

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry

    def load_skill(self, skill_dir: Path) -> SkillDefinition:
        """Load a single skill from its directory.

        Args:
            skill_dir: Path to the skill directory containing SKILL.md.

        Returns:
            SkillDefinition parsed from the skill directory.
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"No SKILL.md found in {skill_dir}")

        content = skill_md.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(content)

        name = frontmatter.get("name", skill_dir.name)
        description = frontmatter.get("description", "")
        tool_type = frontmatter.get("tool_type", "python")
        primary_tool = frontmatter.get("primary_tool", "")
        supported_tools = frontmatter.get("supported_tools", [])
        keywords = frontmatter.get("keywords", [])

        # Determine scripts directory
        scripts_dir = self._find_scripts_dir(skill_dir, tool_type, primary_tool)

        # Read requirements
        requirements = self._read_requirements(skill_dir)

        # Build metadata
        metadata = {
            "primary_tool": primary_tool,
            "supported_tools": supported_tools if isinstance(supported_tools, list) else [],
            "keywords": keywords if isinstance(keywords, list) else [],
            "scripts_dir": str(scripts_dir) if scripts_dir else None,
            "source": "external",
            "source_dir": str(skill_dir.absolute()),
        }

        # Add multi_sample config if present
        if "multi_sample" in frontmatter:
            metadata["multi_sample"] = frontmatter["multi_sample"]

        # Determine runtime type
        runtime_type = self._resolve_runtime_type(tool_type)

        # Determine python version from requirements or default
        python_version = "3.10"

        category = _extract_category_from_keywords(
            metadata["keywords"], name
        )

        skill = SkillDefinition(
            id=name,
            name=name,
            version="1.0.0",
            category=category,
            description=description,
            input_schema=SkillInputSchema(),
            output_schema=SkillOutputSchema(),
            runtime=SkillRuntime(
                type=runtime_type,
                python_version=python_version,
                dependencies=requirements,
            ),
            metadata=metadata,
        )

        return skill

    def _find_scripts_dir(self, skill_dir: Path, tool_type: str, primary_tool: str) -> Optional[Path]:
        """Find the appropriate scripts directory for a skill."""
        scripts_base = skill_dir / "scripts"

        if not scripts_base.exists():
            return None

        if tool_type == "python":
            py_dir = scripts_base / "python"
            if py_dir.exists():
                return py_dir
        elif tool_type == "r":
            r_dir = scripts_base / "r"
            if r_dir.exists():
                return r_dir
        elif tool_type == "mixed":
            # Prefer Python for mixed unless primary_tool is R-based
            r_tools = {"seurat", "monocle3", "archr", "signac", "harmony", "cellchat", "nichenet"}
            primary_lower = primary_tool.lower()

            if primary_lower in r_tools:
                r_dir = scripts_base / "r"
                if r_dir.exists():
                    return r_dir
                py_dir = scripts_base / "python"
                if py_dir.exists():
                    return py_dir
            else:
                py_dir = scripts_base / "python"
                if py_dir.exists():
                    return py_dir
                r_dir = scripts_base / "r"
                if r_dir.exists():
                    return r_dir

        return None

    def _read_requirements(self, skill_dir: Path) -> List[str]:
        """Read requirements.txt if present."""
        req_file = skill_dir / "requirements.txt"
        if not req_file.exists():
            return []

        content = req_file.read_text(encoding="utf-8")
        requirements = []
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                requirements.append(line)
        return requirements

    def _resolve_runtime_type(self, tool_type: str) -> str:
        """Resolve tool_type to runtime type.

        Preserves 'mixed' type for skills that support both Python and R.
        The sandbox and executor will handle mixed by selecting the
        appropriate runtime based on primary_tool or availability.
        """
        tool_type_lower = tool_type.lower()
        if tool_type_lower in ("python", "r", "mixed"):
            return tool_type_lower
        return "python"

    def load_all(self, skills_root: Path) -> List[SkillDefinition]:
        """Load all skills from a skills root directory.

        Args:
            skills_root: Path to the directory containing skill subdirectories.

        Returns:
            List of loaded SkillDefinitions.
        """
        skills = []

        for item in skills_root.iterdir():
            if not item.is_dir():
                continue

            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                skill = self.load_skill(item)
                skills.append(skill)

                if self.registry is not None:
                    self.registry.register(skill)

            except Exception as e:
                # Log and continue with other skills
                print(f"Warning: Failed to load skill from {item}: {e}")
                continue

        return skills
