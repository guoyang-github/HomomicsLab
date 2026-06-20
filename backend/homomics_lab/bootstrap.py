"""Shared worker/runtime bootstrap for API and standalone worker processes.

This module extracts the runtime initialization that both the FastAPI app
and the distributed worker need, so both can start with the same agents,
tools, skills, and domain registry.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List

from homomics_lab.agent.factory import create_default_agents
from homomics_lab.config import settings
from homomics_lab.context.context_engine.engine import ContextEngine
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.project_state import ProjectStateManager
from homomics_lab.context.semantic_memory import SemanticMemory
from homomics_lab.context.session_store import SQLiteSessionStore
from homomics_lab.provenance.recorder import ProvenanceRecorder
from homomics_lab.database import Base, async_engine
from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.registry import get_domain_registry
from homomics_lab.domain.hot_reload import DomainHotReloader, SkillHotReloader
from homomics_lab.agent.plan.strategies import StrategyLibrary
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.llm.cache import LLMResponseCache
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
      - ../paperwriting-Skills/skills
      - ../database-Skills/skills
      - ../mRNAseq-Skills/skills
      - ../riboseq-Skills/skills
    """
    # bootstrap.py is at backend/homomics_lab/bootstrap.py
    # project root is two levels up: backend/homomics_lab -> backend -> HomomicsLab
    project_root = Path(__file__).parent.parent.parent
    candidates: List[Path] = []
    for name in (
        "NanoResearch-Skills",
        "Genomics-Skills",
        "Utils-Skills",
        "paperwriting-Skills",
        "database-Skills",
        "mRNAseq-Skills",
        "riboseq-Skills",
    ):
        candidate = project_root.parent / name / "skills"
        if candidate.exists() and candidate.is_dir():
            candidates.append(candidate)
    return candidates


def _namespace_for_external_dir(external_skills_dir: Path) -> str:
    """Derive a clean namespace from an external skill collection path.

    Examples:
      - ../NanoResearch-Skills/skills -> nanoresearch
      - ../Genomics-Skills/skills -> genomics
      - ../paperwriting-Skills/skills -> paperwriting
    """
    raw = external_skills_dir.parent.name
    ns = raw.lower().removesuffix("-skills")
    return ns or "external"


async def _ensure_database_schema() -> None:
    """Create or migrate the database schema.

    In production (PostgreSQL) we rely on Alembic migrations. For SQLite local
    development and tests we use SQLAlchemy create_all for simplicity and to
    avoid event-loop conflicts inside test runners.
    """
    if settings.database_url.startswith("sqlite"):
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    import asyncio
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
        if alembic_cfg_path.exists():
            alembic_cfg = Config(str(alembic_cfg_path))
            alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
            # Alembic env.py uses asyncio.run; run it in a worker thread to avoid
            # event-loop conflicts inside the async bootstrap context.
            await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
            return
    except Exception as exc:
        print(f"Alembic migration failed: {exc}. Falling back to create_all.")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def bootstrap_worker_context(enable_hot_reload: bool = False) -> Dict[str, Any]:
    """Initialize the common runtime context used by workers and the API.

    Returns a dictionary with the initialized registries and executors.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    create_default_agents()

    # Ensure ORM tables exist. Prefer Alembic migrations; fall back to create_all
    # for SQLite/dev/test environments where Alembic may not have been run yet.
    await _ensure_database_schema()

    # CBKB is created early so domain loading and memory management can use it.
    cbkb = CBKB(base_dir=settings.data_dir)

    # Tools
    tool_registry = ToolRegistry()
    register_all_builtin_tools(tool_registry)
    mcp_client = await register_mcp_tools(tool_registry)

    # Schema validation
    schema_validator = SchemaValidator()

    # Provenance recorder for reproducibility
    provenance_recorder = ProvenanceRecorder()

    # Shared LLM response cache
    llm_cache = (
        LLMResponseCache(
            ttl_seconds=settings.llm_response_cache_ttl_seconds,
            max_entries=settings.llm_response_cache_max_entries,
            persist_dir=settings.llm_response_cache_dir,
        )
        if settings.llm_response_cache_enabled
        else None
    )

    # Skills runtime
    tracker = SkillPerformanceTracker()
    llm_client = LLMClient(cache=llm_cache)
    skill_executor = SkillRuntimeExecutor(
        tracker=tracker,
        tool_registry=tool_registry,
        llm_client=llm_client,
        provenance_recorder=provenance_recorder,
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

    # Import external skill directories into the canonical skill store path.
    # Each skill subdirectory is copied to data/skill_store/imported/<namespace>/
    # so the runtime no longer depends on the original external location.
    discovery_loader = SkillLoader(registry=skill_executor.registry)
    auto_trusted_dirs = _discover_external_skill_dirs()
    external_dirs = settings.external_skills_dirs or auto_trusted_dirs

    # Normalize collection folder names to clean namespaces and remove stale
    # imported directories (e.g. old "external" or renamed collections).
    expected_namespaces = {
        _namespace_for_external_dir(d)
        for d in external_dirs
        if d.exists()
    }
    if skill_store.imported_dir.exists():
        for subdir in skill_store.imported_dir.iterdir():
            if subdir.is_dir() and subdir.name not in expected_namespaces:
                shutil.rmtree(subdir)

    for external_skills_dir in external_dirs:
        if not external_skills_dir.exists():
            continue
        namespace = _namespace_for_external_dir(external_skills_dir)
        # Auto-trust skills discovered from the canonical sibling repos to reduce
        # friction in local development. Explicitly configured directories still
        # require manual trust unless they are also discovered siblings.
        auto_trust = external_skills_dir in auto_trusted_dirs
        for skill_path in external_skills_dir.iterdir():
            if not skill_path.is_dir():
                continue
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                # Peek at the skill to check for builtin collisions before copying.
                preview = discovery_loader.load_skill(skill_path)
                if skill_executor.registry.get(preview.id) is not None:
                    continue
                # Copy into the canonical skill store and register.
                skill = skill_store.import_skill(
                    source=str(skill_path),
                    namespace=namespace,
                    enable=True,
                )
                if auto_trust:
                    skill = skill_store.trust_skill(
                        skill.id, namespace=namespace, trusted=True
                    )
                skill.metadata["namespace"] = namespace
                skill.metadata.setdefault("trusted", False)
                skill_executor.register_skill(skill)
            except Exception as exc:
                print(f"Warning: Failed to import skill from {skill_path}: {exc}")

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
        cbkb=cbkb,
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
        cbkb=cbkb,
    )

    context_engine = ContextEngine(
        cbkb=cbkb,
        semantic_memory=semantic_memory,
        default_model=settings.context_engine_model or settings.llm_model or "default",
        embedding_model_name=settings.semantic_search_model,
        enable_llm_summary=settings.context_enable_episodic_summary,
    )
    project_state_manager = ProjectStateManager(cbkb=cbkb)

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
        "cbkb": cbkb,
        "context_engine": context_engine,
        "project_state_manager": project_state_manager,
        "provenance_recorder": provenance_recorder,
        "llm_cache": llm_cache,
    }
