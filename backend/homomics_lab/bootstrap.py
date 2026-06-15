"""Shared worker/runtime bootstrap for API and standalone worker processes.

This module extracts the runtime initialization that both the FastAPI app
and the distributed worker need, so both can start with the same agents,
tools, skills, and domain registry.
"""

from pathlib import Path
from typing import Any, Dict, List

from homomics_lab.agent.factory import create_default_agents
from homomics_lab.config import settings
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.semantic_memory import SemanticMemory
from homomics_lab.context.session_store import SQLiteSessionStore
from homomics_lab.database import Base, async_engine
from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.registry import get_domain_registry
from homomics_lab.domain.hot_reload import DomainHotReloader, SkillHotReloader
from homomics_lab.agent.plan.strategies import StrategyLibrary
from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.skill_dag import SkillDAG
from homomics_lab.skills.skill_store import SkillStore
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.stability.schema_validator import SchemaValidator
from homomics_lab.mcp.integration import register_mcp_skills, register_mcp_tools
from homomics_lab.tools.builtin import register_all_builtin_tools
from homomics_lab.tools.registry import ToolRegistry


def _discover_external_skill_dirs() -> List[Path]:
    """Discover sibling skill repositories for local development.

    If the user has not configured ``external_skills_dirs`` we look for the
    canonical community skill repositories next to the project root:
      - ../NanoResearch-Skills/skills
      - ../Genomics-Skills/skills
    """
    # bootstrap.py is at backend/homomics_lab/bootstrap.py
    # project root is two levels up: backend/homomics_lab -> backend -> HomomicsLab
    project_root = Path(__file__).parent.parent.parent
    candidates: List[Path] = []
    for name in ("NanoResearch-Skills", "Genomics-Skills", "Utils-Skills"):
        candidate = project_root.parent / name / "skills"
        if candidate.exists() and candidate.is_dir():
            candidates.append(candidate)
    return candidates


async def bootstrap_worker_context(enable_hot_reload: bool = False) -> Dict[str, Any]:
    """Initialize the common runtime context used by workers and the API.

    Returns a dictionary with the initialized registries and executors.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    create_default_agents()

    # Ensure ORM tables exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Tools
    tool_registry = ToolRegistry()
    register_all_builtin_tools(tool_registry)
    mcp_client = await register_mcp_tools(tool_registry)

    # Schema validation
    schema_validator = SchemaValidator()

    # Skills runtime
    tracker = SkillPerformanceTracker()
    llm_client = LLMClient()
    skill_executor = SkillRuntimeExecutor(
        tracker=tracker,
        tool_registry=tool_registry,
        llm_client=llm_client,
    )

    # SkillStore manages skill lifecycle (import / enable / disable / lock)
    skill_store = SkillStore(
        registry=skill_executor.registry,
        store_dir=settings.data_dir / "skill_store",
    )

    # Register builtin and legacy skills through SkillStore
    register_builtin_skills(skill_executor)
    for skill in list(skill_executor.registry.list_all()):
        skill_store._record_meta(
            skill=skill,
            namespace="builtin",
            source=skill.metadata.get("source", "builtin"),
            source_dir=Path(skill.metadata.get("source_dir", ".")),
            enabled=True,
        )

    # Load external skill directories at DISCOVERY level: only frontmatter is
    # loaded into the runtime registry at startup. Full SKILL.md bodies are
    # activated lazily on first execution (OpenClaw-style progressive disclosure).
    loader = SkillLoader(registry=skill_executor.registry)
    external_dirs = settings.external_skills_dirs or _discover_external_skill_dirs()
    for external_skills_dir in external_dirs:
        if external_skills_dir.exists():
            loaded = loader.load_all(external_skills_dir, disclosure="discovery")
            for skill in loaded:
                # Builtin/legacy skills take precedence over external discovery.
                if skill_executor.registry.get(skill.id) is not None:
                    continue
                skill.metadata["namespace"] = "external"
                skill.metadata["trusted"] = False
                skill_executor.register_skill(skill)
                skill_store._record_meta(
                    skill=skill,
                    namespace="external",
                    source=skill.metadata.get("source", "external"),
                    source_dir=Path(skill.metadata.get("source_dir", ".")),
                    enabled=True,
                    trusted=False,
                )

    # Wrap MCP tools as skills so the planner can orchestrate them
    if mcp_client is not None:
        register_mcp_skills(skill_executor, tool_registry)

    # SkillDAG — self-evolving skill relationship graph
    skill_dag = SkillDAG(
        registry=skill_executor.registry,
        db_path=settings.data_dir / "skill_dag.db",
    )

    # Domains and strategies
    domain_registry = get_domain_registry()
    strategy_library = StrategyLibrary()
    domain_loader = DomainLoader(
        skill_registry=skill_executor.registry,
        strategy_lib=strategy_library,
        skill_dag=skill_dag,
    )
    domains_dir = Path(__file__).parent / "domains"
    loaded_domains = []
    if domains_dir.exists():
        for domain_yaml in domains_dir.rglob("domain.yaml"):
            try:
                domain = domain_loader.load(domain_yaml)
                domain_registry.register(domain, domain_loader, domain_yaml)
                loaded_domains.append(domain.domain)
            except Exception as e:
                print(f"Warning: Failed to load domain from {domain_yaml}: {e}")
    print(f"Loaded {len(loaded_domains)} domains: {loaded_domains}")

    # Hot reload watchers (only for the API process)
    domain_reloader = None
    skill_reloader = None
    if enable_hot_reload:
        domain_reloader = DomainHotReloader(
            domain_registry=domain_registry,
            domain_loader=domain_loader,
        )
        for domain_yaml in domains_dir.rglob("domain.yaml"):
            domain_reloader.watch_domain(domain_yaml)
        await domain_reloader.start()

        for external_skills_dir in external_dirs:
            if external_skills_dir.exists():
                if skill_reloader is None:
                    skill_reloader = SkillHotReloader(
                        skill_registry=skill_executor.registry,
                    )
                skill_reloader.watch_skills_directory(external_skills_dir)
        if skill_reloader is not None:
            await skill_reloader.start()

    # Session / memory management
    if settings.session_store_url.startswith("sqlite+aiosqlite:///"):
        db_path = settings.session_store_url.replace("sqlite+aiosqlite:///", "")
    else:
        db_path = str(settings.data_dir / "sessions.db")
    session_store = SQLiteSessionStore(db_path=db_path)
    await session_store.init()

    semantic_memory = None
    if settings.enable_semantic_memory and settings.semantic_search_model:
        semantic_memory = SemanticMemory(
            db_path=str(settings.data_dir / ".metadata" / "semantic_memory.db"),
            model_name=settings.semantic_search_model,
        )

    memory_manager = MemoryManager(
        session_store=session_store,
        semantic_memory=semantic_memory,
        cbkb=None,  # wired later if available
    )

    return {
        "tool_registry": tool_registry,
        "schema_validator": schema_validator,
        "skill_executor": skill_executor,
        "skill_store": skill_store,
        "skill_dag": skill_dag,
        "domain_registry": domain_registry,
        "strategy_library": strategy_library,
        "domain_reloader": domain_reloader,
        "skill_reloader": skill_reloader,
        "mcp_client": mcp_client,
        "llm_client": llm_client,
        "memory_manager": memory_manager,
    }
