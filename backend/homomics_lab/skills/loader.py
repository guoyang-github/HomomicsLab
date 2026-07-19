"""Unified skill loader for all skills (builtin, external, community, user).

Skills are loaded from directory structures containing:
  <skill-name>/
    SKILL.md
    [optional] scripts/
    [optional] references/
    [optional] assets/

Progressive disclosure (OpenClaw / Claude Code-style):
  - Discovery: only SKILL.md frontmatter (name, description, runtime type, etc.).
  - Activation: full SKILL.md body + requirements + scripts location.
  - Execution: references/assets/scripts are loaded on demand.

Claude Code extensions implemented here:
  - ``!`command``` and ````` ```! ```` dynamic context injection.
  - ``$ARGUMENTS``, ``$N``, and named ``$arg`` substitution.
  - ``${CLAUDE_SKILL_DIR}`` and other variable substitution.
  - ``allowed-tools`` / ``disallowed-tools`` metadata parsing.
  - ``disable-model-invocation`` / ``user-invocable`` flags.

No distinction is made between builtin and external skills at the loading level.
The source (builtin/external/community/user) is recorded in skill.metadata["source"].
"""

import asyncio
import logging
import re
import shlex
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from homomics_lab.config import settings
from homomics_lab.skills.models import (
    SkillDefinition,
    SkillInputSchema,
    SkillOutputSchema,
    SkillResources,
    SkillRuntime,
)
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.sandbox import SKILL_CONTAINER_IMAGE, Sandbox

logger = logging.getLogger(__name__)

# Claude Code-style !`cmd` injection in skill docs (formerly
# HOMOMICS_SKILLS_SHELL_EXECUTION_ENABLED; default kept: off).
SKILLS_SHELL_EXECUTION_ENABLED = False


class DisclosureLevel(str, Enum):
    """Progressive disclosure levels for a skill."""

    DISCOVERY = "discovery"  # name + description only
    ACTIVATED = "activated"  # full SKILL.md body + metadata loaded
    EXECUTING = "executing"  # references / scripts loaded on demand


def _parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
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

    try:
        frontmatter = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc

    return frontmatter, remaining


def _normalize_property_spec(spec: Any) -> Dict[str, Any]:
    """Normalize a single input/output property declaration to JSON-schema-like dict."""
    if isinstance(spec, dict):
        return dict(spec)
    if isinstance(spec, list):
        return {"type": "array", "items": spec}
    if isinstance(spec, bool):
        return {"type": "boolean", "default": spec}
    if isinstance(spec, (int, float)):
        return {"type": "number", "default": spec}
    if isinstance(spec, str):
        return {"type": "string", "description": spec}
    return {}


def _build_input_schema(inputs_raw: Any, top_level_required: Optional[List[str]]) -> SkillInputSchema:
    """Build SkillInputSchema from frontmatter ``inputs`` block."""
    if not isinstance(inputs_raw, dict) or not inputs_raw:
        return SkillInputSchema()

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for key, value in inputs_raw.items():
        if not isinstance(key, str):
            continue
        prop = _normalize_property_spec(value)
        if prop.pop("required", False):
            required.append(key)
        properties[key] = prop

    # A top-level `required: [a, b]` list overrides per-property flags.
    if isinstance(top_level_required, list):
        required = [r for r in top_level_required if isinstance(r, str)]

    return SkillInputSchema(type="object", properties=properties, required=required)


def _build_output_schema(outputs_raw: Any) -> SkillOutputSchema:
    """Build SkillOutputSchema from frontmatter ``outputs`` block."""
    if not isinstance(outputs_raw, dict) or not outputs_raw:
        return SkillOutputSchema()

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for key, value in outputs_raw.items():
        if not isinstance(key, str):
            continue
        prop = _normalize_property_spec(value)
        if prop.pop("required", False):
            required.append(key)
        properties[key] = prop

    return SkillOutputSchema(type="object", properties=properties, required=required)


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


def _parse_string_list(value: Any) -> List[str]:
    """Normalize a frontmatter value to a list of non-empty strings.

    Handles: None, single string, list of strings, comma-separated string.
    """
    if value is None:
        return []
    if isinstance(value, str):
        if not value.strip():
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        result: List[str] = []
        for item in value:
            if isinstance(item, str):
                for part in item.split(","):
                    part = part.strip()
                    if part:
                        result.append(part)
        return result
    return []


class SkillLoader:
    """Load skills from external NanoResearch-Skills compatible directories.

    Supports progressive disclosure:
      - ``load_discovery`` only reads frontmatter.
      - ``activate`` lazily loads the full body, scripts, and requirements.
      - ``load_skill`` is a convenience for discovery + activation.

    Also implements Claude Code-style SKILL.md rendering:
      - shell command injection (``!`cmd` `` and ````` ```! ```` blocks)
      - argument / variable substitution
    """

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry

    def load_discovery(self, skill_dir: Path) -> SkillDefinition:
        """Load only the discovery-level metadata from a skill directory.

        The full SKILL.md body, scripts, and requirements are NOT loaded.
        This keeps the runtime registry lightweight at startup.
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"No SKILL.md found in {skill_dir}")

        content = skill_md.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(content)

        return self._build_definition(
            skill_dir=skill_dir,
            frontmatter=frontmatter,
            instructions="",
            scripts_dir=None,
            requirements=[],
            disclosure_level=DisclosureLevel.DISCOVERY,
        )

    def activate(
        self,
        skill: SkillDefinition,
        context: Optional[Dict[str, Any]] = None,
    ) -> SkillDefinition:
        """Load the full skill body into a discovery-level skill object.

        Mutates the existing SkillDefinition in place so registry references
        remain valid. Idempotent.

        Args:
            skill: The skill to activate.
            context: Optional execution context used for rendering the skill
                body (``arguments``, ``inputs``, etc.).
        """
        if skill.metadata.get("disclosure_level") == DisclosureLevel.ACTIVATED:
            return skill

        source_path = skill.metadata.get("source_path") or skill.metadata.get("source_dir")
        if not source_path:
            # Programmatic skills without a source directory are treated as fully materialized.
            skill.metadata["disclosure_level"] = DisclosureLevel.ACTIVATED
            return skill

        skill_dir = Path(source_path)
        if not skill_dir.exists():
            raise ValueError(
                f"Cannot activate skill '{skill.id}': source path not found: {source_path}"
            )

        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        frontmatter, raw_instructions = _parse_frontmatter(content)

        # Claude Code-style rendering: argument substitution + dynamic context injection.
        rendered_instructions = self._render_content(
            raw_instructions,
            skill_dir,
            frontmatter,
            context,
            skill,
        )

        scripts_dir = self._find_scripts_dir(
            skill_dir,
            frontmatter.get("tool_type") or frontmatter.get("type", "python"),
            frontmatter.get("primary_tool", ""),
        )
        requirements = self._read_requirements(skill_dir)

        activated = self._build_definition(
            skill_dir=skill_dir,
            frontmatter=frontmatter,
            instructions=rendered_instructions,
            scripts_dir=scripts_dir,
            requirements=requirements,
            disclosure_level=DisclosureLevel.ACTIVATED,
        )

        # Preserve registry identity and any trust/source/namespace overrides
        # applied after discovery.
        preserved_meta = {
            k: skill.metadata[k]
            for k in (
                "source",
                "source_dir",
                "source_path",
                "namespace",
                "trusted",
                "trust_level",
                "sha256",
            )
            if k in skill.metadata
        }
        original_id = skill.id

        skill.name = activated.name
        skill.description = activated.description
        skill.version = activated.version
        skill.author = activated.author
        skill.category = activated.category
        skill.input_schema = activated.input_schema
        skill.output_schema = activated.output_schema
        skill.runtime = activated.runtime
        skill.quality = activated.quality
        skill.metadata = activated.metadata
        skill.domains = activated.domains
        skill.categories = activated.categories
        skill.id = original_id
        skill.metadata.update(preserved_meta)
        return skill

    def load_skill(self, skill_dir: Path) -> SkillDefinition:
        """Load a single skill from its directory (discovery + activation).

        Args:
            skill_dir: Path to the skill directory containing SKILL.md.

        Returns:
            SkillDefinition parsed from the skill directory.
        """
        skill = self.load_discovery(skill_dir)
        self.activate(skill)
        return skill

    def _build_definition(
        self,
        skill_dir: Path,
        frontmatter: Dict[str, Any],
        instructions: str,
        scripts_dir: Optional[Path],
        requirements: List[str],
        disclosure_level: DisclosureLevel,
    ) -> SkillDefinition:
        """Build a SkillDefinition from parsed frontmatter."""
        name = frontmatter.get("name", skill_dir.name)
        description = frontmatter.get("description", "")
        version = str(frontmatter.get("version", "1.0.0"))
        author = str(frontmatter.get("author", "community"))
        license_ = str(frontmatter.get("license", "unknown"))
        tool_type = frontmatter.get("tool_type") or frontmatter.get("type", "python")
        primary_tool = frontmatter.get("primary_tool", "")
        supported_tools = frontmatter.get("supported_tools", [])
        keywords = frontmatter.get("keywords", [])
        depends_on = frontmatter.get("depends_on", [])
        prerequisites = frontmatter.get("prerequisites", [])
        workflow = frontmatter.get("workflow")
        allowed_tools = frontmatter.get("allowed-tools", [])
        disallowed_tools = frontmatter.get("disallowed-tools", [])
        resources = frontmatter.get("resources", {})
        executor = str(frontmatter.get("executor", "auto"))

        input_schema = _build_input_schema(
            frontmatter.get("inputs"), frontmatter.get("required")
        )
        output_schema = _build_output_schema(frontmatter.get("outputs"))

        metadata: Dict[str, Any] = {
            "primary_tool": primary_tool,
            "supported_tools": supported_tools if isinstance(supported_tools, list) else [],
            "keywords": keywords if isinstance(keywords, list) else [],
            "scripts_dir": str(scripts_dir) if scripts_dir else None,
            "source": "external",
            "source_dir": str(skill_dir.absolute()),
            "source_path": str(skill_dir.absolute()),
            "license": license_,
            "instructions": instructions.strip(),
            "allowed_tools": self._normalize_tool_list(allowed_tools),
            "disallowed_tools": self._normalize_tool_list(disallowed_tools),
            "disclosure_level": disclosure_level,
        }

        # Claude Code / Agent Skills frontmatter extensions
        if "disable-model-invocation" in frontmatter:
            metadata["disable_model_invocation"] = bool(frontmatter["disable-model-invocation"])
        if "user-invocable" in frontmatter:
            metadata["user_invocable"] = self._parse_bool(frontmatter["user-invocable"], True)
        if "when_to_use" in frontmatter:
            metadata["when_to_use"] = str(frontmatter["when_to_use"])
        if "context" in frontmatter:
            metadata["context"] = str(frontmatter["context"])
        if "agent" in frontmatter:
            metadata["agent"] = str(frontmatter["agent"])
        if "model" in frontmatter:
            metadata["model"] = str(frontmatter["model"])
        # Capability tier for per-skill model selection ("cheap" | "reasoning"
        # | "coding"); both YAML spellings are accepted.
        if "model_tier" in frontmatter or "model-tier" in frontmatter:
            metadata["model_tier"] = str(
                frontmatter.get("model_tier") or frontmatter.get("model-tier")
            )
        if "argument-hint" in frontmatter:
            metadata["argument_hint"] = str(frontmatter["argument-hint"])
        if "arguments" in frontmatter:
            metadata["arguments"] = self._normalize_tool_list(frontmatter["arguments"])

        if "multi_sample" in frontmatter:
            metadata["multi_sample"] = frontmatter["multi_sample"]
        if depends_on:
            metadata["depends_on"] = depends_on if isinstance(depends_on, list) else [depends_on]
        if prerequisites:
            metadata["prerequisites"] = prerequisites if isinstance(prerequisites, list) else [prerequisites]
        if workflow:
            metadata["workflow"] = workflow
        if "code_act" in frontmatter:
            metadata["code_act"] = bool(frontmatter["code_act"])
        # Respect explicit trust declarations in SKILL.md frontmatter.
        if "trusted" in frontmatter:
            metadata["trusted"] = bool(frontmatter["trusted"])
        # Optional explicit trust level (official/verified/community/experimental).
        # Invalid values are ignored so resolution falls back to source/trusted.
        if "trust_level" in frontmatter:
            from homomics_lab.skills.trust import TrustLevel

            raw_level = str(frontmatter["trust_level"]).strip().lower()
            if raw_level in {level.value for level in TrustLevel}:
                metadata["trust_level"] = raw_level
            else:
                logger.warning(
                    "Skill '%s' declares invalid trust_level %r; ignoring it",
                    name,
                    frontmatter["trust_level"],
                )

        # Lightweight progressive-disclosure hint so the runtime can decide
        # agentic vs script execution without activating the full skill body.
        metadata["has_scripts"] = (skill_dir / "scripts").is_dir()

        runtime_type = self._resolve_runtime_type(tool_type)
        runtime = SkillRuntime(
            type=runtime_type,
            python_version="3.10",
            dependencies=requirements,
            executor=executor,
        )
        if isinstance(resources, dict):
            runtime.resources = SkillResources(**resources)

        # Honor an explicit category from frontmatter; fall back to inference.
        category = frontmatter.get("category")
        if not category:
            category = _extract_category_from_keywords(metadata["keywords"], name)

        # Parse optional domain/category affiliations. Skills can belong to zero
        # or more domains; empty domains means the skill is standalone.
        domains = _parse_string_list(frontmatter.get("domains", []))
        categories = _parse_string_list(frontmatter.get("categories", []))
        # For backward compatibility, if ``domain`` (singular) is present and
        # ``domains`` is not, migrate it.
        legacy_domain = frontmatter.get("domain")
        if legacy_domain and not domains:
            domains = _parse_string_list(legacy_domain)

        return SkillDefinition(
            id=name,
            name=name,
            version=version,
            author=author,
            category=category,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            runtime=runtime,
            metadata=metadata,
            domains=domains,
            categories=categories,
        )

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

        Supports:
        - python / r / mixed: language-based local execution
        - cli: command-line tool wrappers (e.g. samtools, salmon)
        - workflow: workflow/pipeline definitions (Nextflow/Snakemake/WDL)
        - container: containerized tool execution
        - prompt / agent / knowledge: agentic skills
        """
        tool_type_lower = tool_type.lower().strip()
        valid_types = {"python", "r", "mixed", "cli", "workflow", "container", "agent", "knowledge"}
        if tool_type_lower in valid_types:
            return tool_type_lower
        # Claude Code ``type: prompt`` skills are agentic prompt templates.
        if tool_type_lower == "prompt":
            return "agent"
        # Treat shell/bash variants as CLI wrappers.
        if tool_type_lower in {"shell", "bash", "sh"}:
            return "cli"
        return "python"

    def load_all(
        self,
        skills_root: Path,
        disclosure: str = "activated",
    ) -> List[SkillDefinition]:
        """Load all skills from a skills root directory.

        Args:
            skills_root: Path to the directory containing skill subdirectories.
            disclosure: ``activated`` (default) loads full skill bodies;
                ``discovery`` loads only frontmatter for progressive disclosure.

        Returns:
            List of loaded SkillDefinitions.
        """
        if disclosure not in {"activated", "discovery"}:
            raise ValueError(f"Invalid disclosure level: {disclosure}")

        skills = []

        for item in skills_root.iterdir():
            if not item.is_dir():
                continue

            skill_md = item / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                if disclosure == "discovery":
                    skill = self.load_discovery(item)
                else:
                    skill = self.load_skill(item)

                skills.append(skill)

                if self.registry is not None:
                    self.registry.register(skill)

            except Exception as e:
                # Log and continue with other skills
                print(f"Warning: Failed to load skill from {item}: {e}")
                continue

        return skills

    # ------------------------------------------------------------------
    # Claude Code-style SKILL.md rendering helpers
    # ------------------------------------------------------------------

    def _render_content(
        self,
        content: str,
        skill_dir: Path,
        frontmatter: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        skill: SkillDefinition,
    ) -> str:
        """Render SKILL.md body with variable/argument substitution and shell injection."""
        context = context or {}

        # Built-in variable substitution
        content = content.replace("${CLAUDE_SKILL_DIR}", str(skill_dir))

        # Argument substitution
        arguments = context.get("arguments", "")
        arg_parts = self._split_arguments(arguments)
        content = content.replace("$ARGUMENTS", arguments)
        for i, part in enumerate(arg_parts):
            content = content.replace(f"$ARGUMENTS[{i}]", part)
            content = content.replace(f"${i}", part)

        # Named arguments declared in frontmatter
        declared_args = frontmatter.get("arguments", [])
        if isinstance(declared_args, str):
            declared_args = self._normalize_tool_list(declared_args)
        for i, name in enumerate(declared_args):
            value = arg_parts[i] if i < len(arg_parts) else ""
            content = content.replace(f"${name}", value)

        # Dynamic context injection: !`cmd` and ```! blocks
        content = self._inject_shell_commands(content, skill_dir, skill)
        return content

    def _inject_shell_commands(
        self,
        content: str,
        skill_dir: Path,
        skill: SkillDefinition,
    ) -> str:
        """Replace Claude Code-style shell placeholders with command output.

        Shell commands are only executed when:
          1. ``SKILLS_SHELL_EXECUTION_ENABLED`` is True, and
          2. the skill is builtin or explicitly trusted.

        Otherwise the placeholder is replaced with a clear marker.
        """
        shell_enabled = SKILLS_SHELL_EXECUTION_ENABLED
        source = skill.metadata.get("source", "external")
        trusted = skill.metadata.get("trusted", source == "builtin")
        can_run_shell = shell_enabled and trusted

        disabled_marker = "[shell execution disabled]"
        if shell_enabled and not trusted:
            disabled_marker = "[shell execution disabled for untrusted skill]"

        def run_block(match: re.Match) -> str:
            cmd = match.group(1).strip()
            if not can_run_shell:
                return disabled_marker
            return self._run_shell_command(cmd, skill_dir)

        # Multi-line ```! blocks
        content = re.sub(
            r"^```!\s*\n(.*?)```\s*$",
            run_block,
            content,
            flags=re.MULTILINE | re.DOTALL,
        )

        # Inline !`cmd`
        def run_inline(match: re.Match) -> str:
            cmd = match.group(2).strip()
            if not can_run_shell:
                return match.group(1) + disabled_marker
            output = self._run_shell_command(cmd, skill_dir)
            return match.group(1) + output

        content = re.sub(
            r"(^|\s)!`([^`]+)`",
            run_inline,
            content,
            flags=re.MULTILINE,
        )
        return content

    def _run_shell_command(self, command: str, cwd: Path) -> str:
        """Run a shell command inside the configured sandbox and return output."""
        try:
            sandbox = Sandbox.create(
                settings.skill_sandbox_backend,
                cwd,
                container_image=SKILL_CONTAINER_IMAGE,
            )
            # run_command is async, but activation runs in a synchronous context.
            # Use a small helper that tolerates an already-running event loop.
            return self._run_command_sync(sandbox, command, cwd)
        except Exception as exc:
            return f"[shell command failed: {exc}]"

    @staticmethod
    def _run_command_sync(sandbox: Sandbox, command: str, cwd: Path) -> str:
        """Synchronously invoke sandbox.run_command, avoiding nested loop issues."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(sandbox.run_command(command, cwd=cwd))
        # Already inside an event loop: schedule on a new thread to avoid blocking.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, sandbox.run_command(command, cwd=cwd))
            return future.result(timeout=35)

    @staticmethod
    def _split_arguments(arguments: str) -> List[str]:
        """Split an argument string shell-style."""
        if not arguments:
            return []
        try:
            return shlex.split(arguments)
        except ValueError:
            return arguments.split()

    @staticmethod
    def _normalize_tool_list(value: Any) -> List[str]:
        """Normalize a space/comma-separated tool list or YAML list."""
        if not value:
            return []
        if isinstance(value, list):
            return [
                str(item).strip().split("(")[0].split()[0]
                for item in value
                if str(item).strip()
            ]
        if isinstance(value, str):
            return [s.strip() for s in re.split(r"[,\s]+", value) if s.strip()]
        return []

    @staticmethod
    def _parse_bool(value: Any, default: bool) -> bool:
        """Parse a frontmatter boolean value."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() not in {"false", "no", "0", "off"}
        return default
