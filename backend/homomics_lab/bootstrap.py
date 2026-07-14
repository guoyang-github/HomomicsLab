"""Shared worker/runtime bootstrap for API and standalone worker processes.

This module extracts the runtime initialization that both the FastAPI app
and the distributed worker need, so both can start with the same agents,
tools, skills, and domain registry.
"""

import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List

from homomics_lab.agent.factory import create_default_agents
from homomics_lab.agent.plan.strategies import StrategyLibrary
from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
from homomics_lab.config import settings
from homomics_lab.context.context_engine.engine import ContextEngine
from homomics_lab.prompts import initialize_prompt_registry
from homomics_lab.context.graph.factory import get_graph_backend
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.vector_store.factory import get_vector_store
from homomics_lab.embeddings.factory import get_embedding_provider
from homomics_lab.context.project_state import ProjectStateManager
from homomics_lab.context.semantic_memory import create_semantic_memory
from homomics_lab.context.session_store import create_session_store_from_settings
from homomics_lab.database import Base, get_engine
from homomics_lab.domain.hot_reload import DomainHotReloader, SkillHotReloader
from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.registry import get_domain_registry
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.llm.cache import get_llm_response_cache
from homomics_lab.llm.runtime_config import (
    is_local_llm_provider,
    load_llm_runtime_config,
)
from homomics_lab.llm_client import LLMClient
from homomics_lab.mcp.integration import register_mcp_skills
from homomics_lab.mcp.marketplace import MCPMarketplace
from homomics_lab.provenance.recorder import ProvenanceRecorder
from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.knowledge.ingestion import KnowledgeIndex
from homomics_lab.skills.capability_index import CapabilityIndex
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.skill_dag import SkillDAG
from homomics_lab.skills.skill_store import SkillStore
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.stability.schema_validator import SchemaValidator
from homomics_lab.tools.builtin import register_all_builtin_tools
from homomics_lab.tools.registry import ToolRegistry
from homomics_lab.workflow.execution_service import WorkflowExecutionService

logger = logging.getLogger(__name__)


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
    if not settings.skill_sibling_discovery_enabled:
        return []
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
        async with get_engine().begin() as conn:
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

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def bootstrap_worker_context(enable_hot_reload: bool = False) -> Dict[str, Any]:
    """Initialize the common runtime context used by workers and the API.

    Returns a dictionary with the initialized registries and executors.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)

    # Load global prompt templates before agents/domains render system prompts.
    initialize_prompt_registry()

    # Analysis templates: seed built-in scenario presets on first boot.
    analysis_template_store = AnalysisTemplateStore(data_dir=settings.data_dir)
    imported_count = analysis_template_store.import_builtin_templates()
    if imported_count:
        print(f"[bootstrap] imported {imported_count} built-in analysis templates")

    # Ensure ORM tables exist. Prefer Alembic migrations; fall back to create_all
    # for SQLite/dev/test environments where Alembic may not have been run yet.
    await _ensure_database_schema()

    # Seed a default admin user/tenant when auth is enabled and the user table is
    # empty. This is only a convenience for first-boot local deployments.
    if settings.auth_enabled:
        from homomics_lab.database.connection import get_session_factory
        from homomics_lab.api.auth import create_default_admin_if_missing

        async with get_session_factory()() as session:
            await create_default_admin_if_missing(session)

    # CBKB is created early so domain loading and memory management can use it.
    cbkb = CBKB(base_dir=settings.data_dir)

    # Tools
    tool_registry = ToolRegistry()
    register_all_builtin_tools(tool_registry)

    # MCP server marketplace: load catalog, install/enable user servers.
    mcp_marketplace = MCPMarketplace()
    if settings.mcp_marketplace_enabled:
        try:
            await mcp_marketplace.register_enabled_servers(tool_registry)
        except Exception as exc:
            logger.warning("Failed to register enabled MCP servers: %s", exc)
    if settings.science_connectors_enabled:
        try:
            from homomics_lab.tools.science import register_science_tools

            register_science_tools(tool_registry)
        except Exception as exc:
            logger.warning("Failed to register science connectors: %s", exc)

    # Schema validation
    schema_validator = SchemaValidator()

    # Provenance recorder for reproducibility
    provenance_recorder = ProvenanceRecorder()

    # Shared LLM response cache
    llm_cache = get_llm_response_cache(settings)

    print("[bootstrap] creating skill runtime...")
    # Skills runtime
    tracker = SkillPerformanceTracker(
        db_path=Path(settings.data_dir) / ".metadata" / "homomics_lab_metrics.db"
    )
    llm_client = LLMClient(cache=llm_cache)
    await llm_client.reload_config()
    skill_executor = SkillRuntimeExecutor(
        tracker=tracker,
        tool_registry=tool_registry,
        llm_client=llm_client,
        provenance_recorder=provenance_recorder,
    )

    # Workflow execution service: routes Plans to local orchestrator or Nextflow.
    workflow_execution_service = WorkflowExecutionService(
        skill_registry=skill_executor.registry,
        tool_registry=tool_registry,
        llm_client=llm_client,
        cbkb=cbkb,
    )

    print("[bootstrap] creating skill store...")
    # SkillStore manages skill lifecycle (import / enable / disable / lock).
    # skills_dir is the canonical runtime source directory: imported skills are
    # copied here, and drop-in skills are registered in place.
    skill_store = SkillStore(
        registry=skill_executor.registry,
        store_dir=settings.data_dir / "skill_store",
        skills_dir=settings.skills_dir,
    )

    print("[bootstrap] registering builtin skills...")
    register_builtin_skills(skill_executor)
    for skill in list(skill_executor.registry.list_all()):
        skill_store._record_meta(
            skill=skill,
            namespace="builtin",
            source=skill.metadata.get("source", "builtin"),
            source_dir=Path(skill.metadata.get("source_dir", ".")),
            enabled=True,
        )

    discovery_loader = SkillLoader(registry=skill_executor.registry)
    auto_trusted_dirs = _discover_external_skill_dirs()
    external_dirs = settings.external_skills_dirs or auto_trusted_dirs

    # Ensure the user drop-in directory exists.
    settings.skills_dir.mkdir(parents=True, exist_ok=True)

    print("[bootstrap] importing user drop-in skills...")
    # Register skills placed directly under ./skills/ in place (no copy).
    for skill_path in settings.skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
        if not (skill_path / "SKILL.md").exists():
            continue
        try:
            preview = discovery_loader.load_discovery(skill_path)
            if skill_executor.registry.get(preview.id) is not None:
                continue
            skill = skill_store.register_dropin(
                source_dir=skill_path,
                namespace="user",
                enable=True,
            )
            # User drop-in skills live in the project's canonical skills_dir and are
            # treated as locally administered, so we trust them by default.
            skill = skill_store.trust_skill(
                skill.id, namespace="user", trusted=True
            )
            skill_executor.register_skill(skill)
            print(f"Registered user skill: {skill.id}")
        except Exception as exc:
            print(f"Warning: Failed to register user skill from {skill_path}: {exc}")

    print("[bootstrap] importing external skills...")
    # Copy external skill collections into the canonical skills_dir.
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
            if not (skill_path / "SKILL.md").exists():
                continue
            try:
                preview = discovery_loader.load_discovery(skill_path)
                # Do not override user drop-in or builtin skills.
                if skill_executor.registry.get(preview.id) is not None:
                    continue
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
    if settings.mcp_marketplace_enabled:
        register_mcp_skills(skill_executor, tool_registry)

    # Register default agents now that the skill runtime and tool registry are ready.
    # This ensures analysts/supervisors can actually invoke skills at runtime.
    create_default_agents(
        skill_executor=skill_executor,
        tool_registry=tool_registry,
    )

    # SkillDAG — self-evolving skill relationship graph
    skill_dag = SkillDAG(
        registry=skill_executor.registry,
        db_path=settings.data_dir / "skill_dag.db",
    )

    # Cold-start self-evolution baseline (P2-2): on a fresh deployment both
    # CBKB and SkillDAG are empty, so broadcast the bundled benchmark seed
    # records to give the self-evolution loop a starting point. Best-effort:
    # any failure is logged and must never block startup.
    try:
        from homomics_lab.knowledge.seed import is_store_empty, seed_baselines

        if is_store_empty(cbkb, skill_dag):
            report = seed_baselines(cbkb, skill_dag)
            logger.info("Auto-seeded cold-start baselines: %s", report)
    except Exception:
        logger.warning("Auto-seed of baseline records failed; continuing", exc_info=True)

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

    # Shared embedding/vector/graph backends so that CapabilityIndex and
    # KnowledgeIndex do not duplicate or double-close resources.
    # Synchronous warmup of local embedding models is intentionally skipped here;
    # it can add 30-60s to startup and block the API from serving requests.
    # Local providers lazy-load on first encode; a background warmup can be added
    # later if first-request latency becomes a problem.
    try:
        shared_embedding_provider = get_embedding_provider(settings)
    except Exception:
        shared_embedding_provider = None
    try:
        shared_vector_store = get_vector_store(settings)
    except Exception:
        shared_vector_store = None
    try:
        shared_graph_backend = get_graph_backend(settings)
    except Exception:
        shared_graph_backend = None

    # Unified capability index: embed and graph-link all skills, tools and SOPs
    # so the planner and TurnRunner can retrieve them semantically.
    capability_index = CapabilityIndex(
        settings=settings,
        embedding_provider=shared_embedding_provider,
        vector_store=shared_vector_store,
        graph_backend=shared_graph_backend,
    )

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
                        skill_store=skill_store,
                        capability_index=capability_index,
                    )
                skill_reloader.watch_skills_directory(external_skills_dir)
        if settings.skills_dir.exists():
            if skill_reloader is None:
                skill_reloader = SkillHotReloader(
                    skill_registry=skill_executor.registry,
                    skill_store=skill_store,
                    capability_index=capability_index,
                )
            skill_reloader.watch_skills_directory(settings.skills_dir)
        if skill_reloader is not None:
            await skill_reloader.start()

    # Session / memory management
    session_store = create_session_store_from_settings()
    await session_store.init()

    semantic_memory = create_semantic_memory(settings)

    # Populate the capability index with all current skills, tools, and SOPs.
    try:
        for skill in skill_executor.registry.list_all():
            try:
                await capability_index.index_skill(skill)
            except Exception:
                logger.warning(
                    "Failed to index skill %s", getattr(skill, "id", "?"), exc_info=True
                )
        for tool in tool_registry.list_all():
            try:
                await capability_index.index_tool(tool)
            except Exception:
                logger.warning(
                    "Failed to index tool %s", getattr(tool, "name", "?"), exc_info=True
                )
        for sop in cbkb.list_sops():
            try:
                await capability_index.index_sop(sop)
            except Exception:
                logger.warning(
                    "Failed to index SOP %s", getattr(sop, "id", "?"), exc_info=True
                )
    except Exception:
        logger.warning(
            "Capability index population failed; continuing without it", exc_info=True
        )

    memory_manager = MemoryManager(
        session_store=session_store,
        semantic_memory=semantic_memory,
        cbkb=cbkb,
    )

    # Knowledge ingestion index: parses documents, extracts entities/relations,
    # and loads them into the graph/vector/memory stores (cognee-style ECL).
    knowledge_index = KnowledgeIndex(
        settings=settings,
        llm_client=llm_client,
        graph_backend=shared_graph_backend,
        vector_store=shared_vector_store,
        memory_backend=semantic_memory,
        capability_index=capability_index,
        embedding_provider=shared_embedding_provider,
    )

    # Local/self-hosted LLMs are usually CPU-bound and much slower. Disable
    # optional LLM-powered context summarization by default so the chat pipeline
    # does not block on multiple LLM calls for every turn.
    enable_llm_summary = (
        settings.context_enable_episodic_summary and not is_local_llm_provider()
    )
    logger.info(
        "ContextEngine LLM summary enabled: %s (provider=%s)",
        enable_llm_summary,
        getattr(load_llm_runtime_config(), "provider", None),
    )

    context_engine = ContextEngine(
        cbkb=cbkb,
        semantic_memory=semantic_memory,
        default_model=settings.context_engine_model or settings.llm_model or "default",
        embedding_model_name=settings.semantic_search_model,
        enable_llm_summary=enable_llm_summary,
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
        "mcp_marketplace": mcp_marketplace,
        "llm_client": llm_client,
        "memory_manager": memory_manager,
        "capability_index": capability_index,
        "cbkb": cbkb,
        "context_engine": context_engine,
        "project_state_manager": project_state_manager,
        "provenance_recorder": provenance_recorder,
        "llm_cache": llm_cache,
        "knowledge_index": knowledge_index,
        "analysis_template_store": analysis_template_store,
        "workflow_execution_service": workflow_execution_service,
    }


async def _try_close(obj: Any, name: str) -> None:
    """Call ``close()``/``shutdown()``/``stop()`` on a context object if it exists."""
    if obj is None:
        return
    for method_name in ("close", "shutdown", "stop"):
        method = getattr(obj, method_name, None)
        if method is None:
            continue
        try:
            if inspect.iscoroutinefunction(method):
                await method()
            elif callable(method):
                method()
            return
        except Exception:
            logger.warning(
                "Failed to %s %s during shutdown", method_name, name, exc_info=True
            )


async def close_worker_context(ctx: Dict[str, Any]) -> None:
    """Release resources held by a bootstrap context.

    Called from both the API lifespan shutdown and the worker shutdown path.
    """
    # Close indices and managers first; they may hold open DB/graph/vector handles.
    for key in (
        "capability_index",
        "knowledge_index",
        "memory_manager",
        "context_engine",
        "session_store",
        "llm_client",
        "llm_cache",
        "provenance_recorder",
        "workflow_execution_service",
        "skill_store",
        "mcp_marketplace",
        "domain_reloader",
        "skill_reloader",
    ):
        await _try_close(ctx.get(key), key)
