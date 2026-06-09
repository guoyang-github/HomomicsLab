"""Templates for skill generation."""

from typing import Dict, List


class SkillTemplateBuilder:
    """Build SKILL.md and script templates from requirements."""

    def build_skill_md(
        self,
        name: str,
        description: str,
        category: str,
        tool_type: str,
        primary_tool: str,
        supported_tools: List[str],
        keywords: List[str],
        inputs: List[Dict[str, str]],
        outputs: List[str],
        dependencies: List[str],
    ) -> str:
        """Generate SKILL.md content."""
        supported = ", ".join(f'"{t}"' for t in supported_tools)
        kw = ", ".join(f'"{k}"' for k in keywords)

        lines = [
            "---",
            f"name: {name}",
            f"description: {description}",
            f"tool_type: {tool_type}",
            f"primary_tool: {primary_tool}",
            f"supported_tools: [{supported}]",
            f"keywords: [{kw}]",
            f"category: {category}",
            "multi_sample: false",
            "---",
            "",
            f"# {name.replace('-', ' ').title()}",
            "",
            description,
            "",
            "## When to Use This Skill",
            "",
            "Use when users:",
        ]

        for kw_item in keywords[:5]:
            lines.append(f"- Mention {kw_item} or related concepts")

        lines.extend([
            "",
            "## Parameters",
            "",
        ])

        for inp in inputs:
            req = " (required)" if inp.get("required") else ""
            lines.append(f"- `{inp['name']}`{req} - {inp.get('description', '')}")

        lines.extend([
            "",
            "## Outputs",
            "",
        ])

        for out in outputs:
            lines.append(f"- {out}")

        lines.extend([
            "",
            "## Dependencies",
            "",
        ])

        for dep in dependencies:
            lines.append(f"- {dep}")

        return "\n".join(lines)

    def build_python_script(
        self,
        name: str,
        description: str,
        inputs: List[Dict[str, str]],
        outputs: List[str],
    ) -> str:
        """Generate a Python script skeleton."""
        input_reads = []
        for inp in inputs:
            default = inp.get("default", "None")
            if default != "None":
                # Try to format default as Python literal
                try:
                    # If it's a number, use as-is
                    float(default)
                    default_str = default
                except ValueError:
                    default_str = repr(default)
                input_reads.append(f'    {inp["name"]} = skill_inputs.get("{inp["name"]}", {default_str})')
            else:
                input_reads.append(f'    {inp["name"]} = skill_inputs["{inp["name"]}"]')

        lines = [
            "\"\"\"",
            description,
            "\"\"\"",
            "",
            "import json",
            "import sys",
            "",
            "",
            "def main(skill_inputs: dict) -> dict:",
            '    """Execute the skill."""',
        ]

        for line in input_reads:
            lines.append(line)

        lines.extend([
            "",
            "    # TODO: Implement skill logic",
            "    result = {}",
            "",
        ])

        for out in outputs:
            lines.append(f'    result["{out}"] = None')

        lines.extend([
            "",
            "    return result",
            "",
            "",
            'if __name__ == "__main__":',
            "    skill_inputs = json.loads(sys.argv[1])",
            "    result = main(skill_inputs)",
            '    print(json.dumps(result))',
            "",
        ])

        return "\n".join(lines)

    def build_r_script(
        self,
        name: str,
        description: str,
        inputs: List[Dict[str, str]],
        outputs: List[str],
    ) -> str:
        """Generate an R script skeleton."""
        input_reads = []
        for inp in inputs:
            default = inp.get("default", "NULL")
            if default != "NULL":
                input_reads.append(f'  {inp["name"]} <- skill_inputs${inp["name"]} %||% {default}')
            else:
                input_reads.append(f'  {inp["name"]} <- skill_inputs${inp["name"]}')

        lines = [
            "#",
            f"# {description}",
            "#",
            "",
            'library(jsonlite)',
            "",
            'main <- function(skill_inputs) {',
        ]

        for line in input_reads:
            lines.append(line)

        lines.extend([
            "",
            "  # TODO: Implement skill logic",
            "  result <- list()",
            "",
        ])

        for out in outputs:
            lines.append(f'  result${out} <- NULL')

        lines.extend([
            "",
            "  return(result)",
            "}",
            "",
            'skill_inputs <- fromJSON(commandArgs(trailingOnly = TRUE)[1])',
            "result <- main(skill_inputs)",
            'cat(toJSON(result, auto_unbox = TRUE))',
            "",
        ])

        return "\n".join(lines)

    def build_requirements_txt(self, dependencies: List[str]) -> str:
        """Generate requirements.txt."""
        return "\n".join(dependencies) + "\n"
