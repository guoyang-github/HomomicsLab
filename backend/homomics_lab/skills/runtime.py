"""Skill runtime executor with unified execution path for all skills.

All skills (builtin and external) now use the same directory-based layout.
The executor no longer distinguishes between builtin (code strings) and
external (file-based) skills.
"""

import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from homomics_lab.config import settings
from homomics_lab.data import DataStore, ResultReference
from homomics_lab.skills.agent_executor import AgentSkillExecutor
from homomics_lab.skills.cache import SkillCache
from homomics_lab.skills.code_act import run_code_act
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.hpc.scheduler import get_scheduler, BaseScheduler
from homomics_lab.hpc.router import select_execution_backend
from homomics_lab.llm_client import LLMClient
from homomics_lab.stability.schema_validator import SchemaValidator
from homomics_lab.tools.approval import ToolApprovalRequired
from homomics_lab.tools.registry import ToolRegistry, get_default_tool_registry


class UntrustedSkillError(ValueError):
    """Raised when an external/community skill is executed before being trusted."""

    pass


class SkillRuntimeExecutor:
    """Executes skills in a sandboxed environment with optional HPC backend.

    Unified execution: all skills are treated equally, whether builtin or external.
    The skill's metadata["scripts_dir"] determines where code is loaded from.
    """

    def __init__(
        self,
        registry: SkillRegistry = None,
        working_dir: Path = None,
        executor_type: str = "local",
        tracker: SkillPerformanceTracker = None,
        schema_validator: SchemaValidator = None,
        tool_registry: Optional[ToolRegistry] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        self.registry = registry or get_default_registry()
        self.working_dir = working_dir
        self._executor_type = executor_type
        self._scheduler: Optional[BaseScheduler] = None
        self.tracker = tracker
        self.schema_validator = schema_validator
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.llm_client = llm_client
        self._agent_executor: Optional[AgentSkillExecutor] = None
        self.data_store = DataStore(
            working_dir or Path.cwd(),
            inline_size_limit=settings.result_inline_size_limit_bytes,
        )
        self.cache = (
            SkillCache(settings.skill_cache_dir)
            if settings.skill_cache_enabled
            else None
        )

    def _get_agent_executor(self) -> AgentSkillExecutor:
        """Lazy initialization of the declarative skill agent executor."""
        if self._agent_executor is None:
            self._agent_executor = AgentSkillExecutor(
                tool_registry=self.tool_registry,
                llm_client=self.llm_client,
            )
        return self._agent_executor

    def _get_scheduler(self) -> BaseScheduler:
        """Lazy initialization of the scheduler."""
        if self._scheduler is None:
            self._scheduler = get_scheduler(
                self._executor_type,
                working_dir=self.working_dir,
            )
        return self._scheduler

    def select_backend_for(self, plan, data_state) -> str:
        """Automatically choose and cache the best backend for a plan."""
        backend = select_execution_backend(plan, data_state)
        if backend != self._executor_type:
            self._executor_type = backend
            self._scheduler = None
        return backend

    async def run_nextflow_plan(
        self,
        plan,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        """Run a full PlanResult as a Nextflow workflow project.

        Resolution order:
        1. Use a curated production template if one matches the plan intent.
        2. Fall back to the LLM-driven Nextflow architect skill.
        3. Fall back to the simple translator (stubs for unsupported domains).
        """
        from homomics_lab.hpc.scheduler import NextflowRunner
        from homomics_lab.hpc.template_registry import get_template_registry

        scheduler = self._get_scheduler()
        if not isinstance(scheduler, NextflowRunner):
            raise RuntimeError(
                f"Expected NextflowRunner, got {type(scheduler).__name__}. "
                "Call select_backend_for(plan, data_state) first."
            )

        # 1. Curated template path (local or nf-core cached pipeline).
        intent_type = getattr(plan, "intent_analysis_type", None) or ""
        template_path = get_template_registry().resolve_for_intent(intent_type)
        if template_path is not None:
            # nf-core pipelines are full directories with relative imports;
            # run them in-place instead of copying main.nf.
            nfcore_cache = getattr(settings, "nfcore_cache_dir", None) or (
                settings.data_dir / "nfcore_pipelines"
            )
            try:
                is_nfcore = str(template_path.resolve()).startswith(str(Path(nfcore_cache).resolve()))
            except Exception:
                is_nfcore = False

            if is_nfcore:
                profiles = getattr(settings, "nfcore_default_profiles", ["docker"])
                return await scheduler.run_pipeline_dir(
                    template_path,
                    inputs,
                    timeout_seconds=timeout_seconds,
                    profiles=profiles,
                )
            return await scheduler.run_template(
                template_path, inputs, timeout_seconds=timeout_seconds
            )

        # 2. LLM architect skill.
        architect_skill = self.registry.get("utils_workflow_management_nextflow")
        if architect_skill is None:
            architect_skill = self.registry.get("utils-workflow-management-nextflow")
        if architect_skill is not None:
            self.registry.activate(architect_skill.id)
        if (
            architect_skill is not None
            and self.llm_client is not None
            and self.llm_client.is_configured()
        ):
            result = await self._run_agent_nextflow_plan(
                architect_skill, plan, inputs, scheduler, timeout_seconds
            )
            if result.get("success"):
                return result

        # 3. Simple translator fallback.
        return await scheduler.run_plan(plan, inputs, timeout_seconds=timeout_seconds)

    async def _run_agent_nextflow_plan(
        self,
        skill,
        plan,
        inputs: Dict[str, Any],
        scheduler,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        """Use a declarative Nextflow architect skill to generate and run a project."""
        project_dir = self.working_dir / "nf_project"
        project_dir.mkdir(parents=True, exist_ok=True)

        agent_inputs = {
            "task": "Generate a production-grade Nextflow DSL2 pipeline from the given analysis plan.",
            "plan_summary": self._summarize_plan(plan),
            "user_inputs": inputs,
            "output_dir": str(project_dir),
        }

        agent = self._get_agent_executor()
        agent_result = await agent.execute(skill, agent_inputs, working_dir=project_dir)
        if not agent_result.get("success"):
            return agent_result

        # Find the generated main.nf; default to the project root.
        nf_candidates = list(project_dir.rglob("main.nf"))
        nf_file = nf_candidates[0] if nf_candidates else project_dir / "main.nf"

        run_result = await scheduler.run_project(
            nf_file,
            inputs,
            timeout_seconds=timeout_seconds,
        )
        run_result["agent_result"] = agent_result
        run_result["nf_file"] = str(nf_file)
        return run_result

    @staticmethod
    def _summarize_plan(plan) -> Dict[str, Any]:
        """Create a JSON-serializable summary of a PlanResult."""
        phases = []
        for phase in getattr(plan, "phases", []):
            phases.append(
                {
                    "phase_type": phase.phase_type,
                    "required": phase.required,
                    "skill_id": (
                        phase.selected_skill.id
                        if getattr(phase, "selected_skill", None) is not None
                        else None
                    ),
                    "parameters": getattr(phase, "parameters", {}),
                }
            )
        return {
            "strategy_name": getattr(plan, "strategy_name", "unknown"),
            "phases": phases,
        }

    def register_skill(self, skill: SkillDefinition) -> None:
        """Register a skill (builtin or external) into the registry.

        All skills are treated uniformly. The skill's scripts_dir in metadata
        determines where code is loaded from at execution time.
        """
        self.registry.register(skill)

    async def _execute_code_act(
        self,
        skill: SkillDefinition,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a CodeAct skill by delegating to the CodeAct engine."""
        # Build a minimal retrieval context from available registries so CodeAct
        # can see tools and relevant skills even when invoked directly.
        from homomics_lab.agent.retrieval import SkillRetriever

        retriever = SkillRetriever(
            skill_registry=self.registry,
            tool_registry=self.tool_registry,
        )
        retrieval_context = retriever.retrieve(
            query=inputs.get("task", ""),
            intent_type=skill.category or "general",
            include_sops=False,
            include_anomalies=False,
        )

        result = await run_code_act(
            task=inputs.get("task", ""),
            language=inputs.get("language", "python"),
            context=inputs.get("context", {}),
            working_dir=self.working_dir,
            llm_client=self.llm_client,
            skill_registry=self.registry,
            retrieval_context=retrieval_context,
            tool_registry=self.tool_registry,
        )
        return {
            "skill_id": skill.id,
            "code": result["code"],
            "success": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "result": result["result"],
        }

    async def execute(self, skill_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a skill by ID.

        Dispatches to the appropriate handler based on skill type:
          - python/r/mixed with scripts_dir  -> sandbox/scheduler
          - mcp                              -> ToolRegistry
          - code_act                         -> CodeAct engine
          - cli/workflow/container/agent or  -> LLM agent / knowledge fallback
            skills without executable scripts
        """
        skill = self.registry.get(skill_id)
        if skill is None:
            raise ValueError(f"Skill '{skill_id}' not found")

        # Progressive disclosure: activate the full SKILL.md body (and
        # scripts/requirements) the first time the skill is executed. Pass the
        # user inputs as context so Claude Code-style argument substitution and
        # dynamic context injection can run.
        execution_context = {"arguments": inputs.get("arguments", ""), "inputs": inputs}
        skill = self.registry.activate(skill_id, context=execution_context)
        if skill is None:
            raise ValueError(f"Skill '{skill_id}' disappeared during activation")

        # Trust model: external/community skills must be explicitly trusted.
        # Programmatic skills without a source are treated as builtin for
        # backward compatibility with tests and internal components.
        source = skill.metadata.get("source") or "builtin"
        if source in {"external", "community", "imported"} and not skill.metadata.get("trusted"):
            raise UntrustedSkillError(
                f"Skill '{skill_id}' from source '{source}' is not trusted. "
                f"Run 'homomics trust {skill_id}' or POST /skills/{skill_id}/trust first."
            )

        # Schema validation (if validator configured)
        if self.schema_validator is not None:
            validation = self.schema_validator.validate_input(skill, inputs)
            if not validation.passed:
                raise ValueError(
                    f"Input validation failed for skill '{skill_id}': "
                    f"{'; '.join(validation.errors)}"
                )

        # Validate inputs (schema-based defaults)
        validated = skill.validate_input(inputs)

        start_time = time.time()
        fingerprint = skill.metadata.get("sha256") or skill.metadata.get("version") or ""
        if self._is_cacheable(skill) and self.cache is not None:
            cached = self.cache.get(skill_id, validated, fingerprint=fingerprint)
            if cached is not None:
                result = self._unwrap_cached(cached, skill_id=skill_id)
                if self.tracker is not None:
                    duration_ms = (time.time() - start_time) * 1000
                    self.tracker.record(
                        skill_id=skill_id,
                        duration_ms=duration_ms,
                        success=True,
                        output_size=len(str(result)),
                        executor_type=self._executor_type,
                        cache_hit=True,
                    )
                return result

        result = None
        success = False
        error_msg = ""
        try:
            result = await self._dispatch_execute(skill, validated)
            success = True
            stored = self.data_store.store(
                task_id=f"{skill_id}_{uuid.uuid4().hex[:8]}",
                data=result,
            )
            if self._is_cacheable(skill) and self.cache is not None:
                self.cache.put(skill_id, validated, stored, fingerprint=fingerprint)
            return self._unwrap_reference(stored, skill_id=skill_id)

        except ToolApprovalRequired as exc:
            error_msg = str(exc)
            return {
                "skill_id": skill_id,
                "success": False,
                "mode": "awaiting_tool_approval",
                "approval_request": {
                    "call_id": exc.call_id,
                    "tool_name": exc.tool_name,
                    "arguments": exc.arguments,
                    "risk_level": exc.risk_level,
                },
            }

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # Record metrics
            if self.tracker is not None:
                duration_ms = (time.time() - start_time) * 1000
                output_size = len(str(result)) if result else 0
                self.tracker.record(
                    skill_id=skill_id,
                    duration_ms=duration_ms,
                    success=success,
                    output_size=output_size,
                    executor_type=self._executor_type,
                    error_message=error_msg,
                )

    async def _dispatch_execute(
        self,
        skill: SkillDefinition,
        validated: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Route a validated skill to the correct execution backend."""
        exec_type = self._resolve_execution_type(skill)

        # MCP-backed skills delegate to the ToolRegistry
        if exec_type == "mcp":
            return await self._execute_mcp_skill(skill, validated)

        # CodeAct skills run outside the restrictive sandbox so they can
        # generate and execute arbitrary code safely in their own subprocess.
        if skill.metadata.get("code_act") is True:
            return await self._execute_code_act(skill, validated)

        # Declarative / agentic / workflow skills do not require scripts.
        if self._is_declarative(skill):
            agent = self._get_agent_executor()
            return await agent.execute(skill, validated, working_dir=self.working_dir)

        # Script-based skills require a scripts directory.
        scripts_dir = self._resolve_scripts_dir(skill)
        if scripts_dir is None:
            raise RuntimeError(
                f"Script-based skill '{skill.id}' has no scripts directory. "
                f"If this skill is declarative, set runtime.type to one of "
                f"cli/workflow/container/agent/knowledge."
            )

        return await self._execute_from_dir(skill, scripts_dir, exec_type, validated)

    @staticmethod
    def _is_declarative(skill: SkillDefinition) -> bool:
        """Return True when a skill should be executed by the agent/knowledge path."""
        runtime_type = skill.runtime.type.lower()
        if runtime_type in {"cli", "workflow", "container", "agent", "knowledge"}:
            return True
        if skill.metadata.get("agent") is True:
            return True
        # A script-type skill without scripts is treated as knowledge/agentic
        # rather than failing immediately.
        if runtime_type in {"python", "r", "mixed"} and not skill.metadata.get("scripts_dir"):
            return True
        return False

    def _resolve_execution_type(self, skill: SkillDefinition) -> str:
        """Determine the execution type (python, r, or mcp) for a skill."""
        runtime_type = skill.runtime.type.lower()

        if runtime_type in ("python", "r", "mcp"):
            return runtime_type

        if runtime_type == "mixed":
            # Choose based on primary_tool
            primary = skill.metadata.get("primary_tool", "").lower()
            r_tools = {
                "seurat", "monocle3", "archr", "signac", "harmony",
                "cellchat", "nichenet", "singleR", "scvi", "scran",
            }
            if primary in r_tools:
                return "r"
            return "python"

        return "python"

    @staticmethod
    def _is_cacheable(skill: SkillDefinition) -> bool:
        """Return True for deterministic script-based skills that may be memoized."""
        if skill.metadata.get("code_act") is True or skill.metadata.get("agent") is True:
            return False
        return skill.runtime.type.lower() in {"python", "r", "mixed"}

    @staticmethod
    def _unwrap_reference(ref: ResultReference, skill_id: str) -> Any:
        """Return a payload from a result reference.

        Small results are stored inline and returned directly to preserve the
        existing API contract. Large results are returned as a serializable
        reference that callers can load with ``DataStore.load``.
        """
        if ref.inline:
            return ref.data
        return {
            "skill_id": skill_id,
            "success": True,
            "result": ref.model_dump() if hasattr(ref, "model_dump") else ref.dict(),
        }

    def _unwrap_cached(self, cached: Any, skill_id: str) -> Any:
        """Load a cached value, resolving any stored result reference."""
        if isinstance(cached, ResultReference):
            return self._unwrap_reference(cached, skill_id)
        return cached

    async def _execute_mcp_skill(
        self,
        skill: SkillDefinition,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an MCP-backed skill by delegating to the ToolRegistry."""
        tool_name = skill.metadata.get("tool_name")
        if not tool_name:
            raise RuntimeError(f"MCP skill '{skill.id}' is missing metadata.tool_name")
        result = await self.tool_registry.invoke_async(tool_name, inputs)
        return {
            "success": result.success,
            "output": result.output,
            "error_message": result.error_message,
        }

    async def execute_route(
        self,
        route,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an ExecutionRoute produced by the ExecutionRouter.

        This is the foundation-first dispatch point: curated skills are used
        when available, otherwise CodeAct generates and executes code.
        """
        from homomics_lab.agent.execution_router import ExecutionMode

        inputs = inputs or {}

        if route.mode == ExecutionMode.CURATED_SKILL:
            if route.skill is None:
                raise ValueError("CURATED_SKILL route missing skill")
            return await self.execute(route.skill.id, route.context.get("parameters", inputs))

        if route.mode in {
            ExecutionMode.GENERATED_FROM_TEMPLATE,
            ExecutionMode.CODE_FROM_RETRIEVAL,
            ExecutionMode.CODE_FROM_SCRATCH,
        }:
            return await run_code_act(
                task=route.task,
                language=route.language,
                context={**route.context, **inputs},
                working_dir=self.working_dir,
                llm_client=self.llm_client,
                skill_registry=self.registry,
                tool_registry=self.tool_registry,
            )

        if route.mode == ExecutionMode.TOOL_ONLY:
            outputs = {}
            for tool_name in route.tools:
                try:
                    result = await self.tool_registry.invoke_async(tool_name, inputs)
                    outputs[tool_name] = {
                        "success": result.success,
                        "output": result.output,
                        "error": result.error_message,
                    }
                except Exception as exc:
                    outputs[tool_name] = {"success": False, "error": str(exc)}
            return {"success": True, "tool_outputs": outputs}

        raise ValueError(f"Unsupported execution mode: {route.mode}")

    def _resolve_scripts_dir(self, skill: SkillDefinition) -> Optional[Path]:
        """Resolve the scripts directory for a skill.

        Checks metadata['scripts_dir'] first, then falls back to
        finding scripts relative to the skill definition.
        """
        if skill.metadata.get("scripts_dir"):
            scripts_dir = Path(skill.metadata["scripts_dir"])
            if scripts_dir.exists():
                return scripts_dir

        return None

    async def _execute_from_dir(
        self,
        skill: SkillDefinition,
        scripts_dir: Path,
        exec_type: str,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a skill by reading scripts from its directory."""
        timeout = self._parse_timeout(skill.runtime.resources.time)

        # Collect all script files
        if exec_type == "r":
            script_files = sorted(scripts_dir.glob("*.R"))
            if not script_files:
                script_files = sorted(scripts_dir.glob("*.r"))
            if not script_files:
                raise RuntimeError(f"No .R files found in {scripts_dir}")
        else:
            script_files = sorted(scripts_dir.glob("*.py"))
            if not script_files:
                raise RuntimeError(f"No .py files found in {scripts_dir}")

        # Concatenate scripts
        code_parts = []
        for f in script_files:
            code_parts.append(f"# --- {f.name} ---")
            code_parts.append(f.read_text(encoding="utf-8"))
        code = "\n".join(code_parts)

        scheduler = self._get_scheduler()
        return await scheduler.execute(skill, code, inputs, timeout_seconds=timeout)

    def _parse_timeout(self, time_str: str) -> float:
        """Parse time string like '30m' or '1h' into seconds."""
        time_str = str(time_str).strip()
        if time_str.endswith("m"):
            seconds = float(time_str[:-1]) * 60
        elif time_str.endswith("h"):
            seconds = float(time_str[:-1]) * 3600
        elif time_str.endswith("s"):
            seconds = float(time_str[:-1])
        else:
            seconds = float(time_str)

        # Cap at 1 hour for MVP
        return min(seconds, 3600.0)
