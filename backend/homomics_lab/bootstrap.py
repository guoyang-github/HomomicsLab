"""Shared worker/runtime bootstrap for API and standalone worker processes.

This module extracts the runtime initialization that both the FastAPI app
and the distributed worker need, so both can start with the same agents,
tools, skills, and domain registry.
"""

from pathlib import Path
from typing import Any, Dict

from homomics_lab.agent.factory import create_default_agents
from homomics_lab.config import settings
from homomics_lab.database import Base, async_engine
from homomics_lab.domain.loader import DomainLoader
from homomics_lab.domain.registry import get_domain_registry
from homomics_lab.domain.hot_reload import DomainHotReloader, SkillHotReloader
from homomics_lab.agent.plan.strategies import StrategyLibrary
from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.stability.schema_validator import SchemaValidator
from homomics_lab.mcp.integration import register_mcp_skills, register_mcp_tools
from homomics_lab.tools.builtin import register_all_builtin_tools
from homomics_lab.tools.registry import ToolRegistry


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
    skill_executor = SkillRuntimeExecutor(tracker=tracker, tool_registry=tool_registry)
    register_builtin_skills(skill_executor)
    if settings.external_skills_dir and settings.external_skills_dir.exists():
        loader = SkillLoader(registry=skill_executor.registry)
        loaded = loader.load_all(settings.external_skills_dir)
        for skill in loaded:
            skill_executor.register_skill(skill)

    # Wrap MCP tools as skills so the planner can orchestrate them
    if mcp_client is not None:
        register_mcp_skills(skill_executor, tool_registry)

    # Domains and strategies
    domain_registry = get_domain_registry()
    strategy_library = StrategyLibrary()
    domain_loader = DomainLoader(
        skill_registry=skill_executor.registry,
        strategy_lib=strategy_library,
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

        if settings.external_skills_dir and settings.external_skills_dir.exists():
            skill_reloader = SkillHotReloader(
                skill_registry=skill_executor.registry,
            )
            skill_reloader.watch_skills_directory(settings.external_skills_dir)
            await skill_reloader.start()

    return {
        "tool_registry": tool_registry,
        "schema_validator": schema_validator,
        "skill_executor": skill_executor,
        "domain_registry": domain_registry,
        "strategy_library": strategy_library,
        "domain_reloader": domain_reloader,
        "skill_reloader": skill_reloader,
        "mcp_client": mcp_client,
    }
