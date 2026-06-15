from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from homomics_lab.bootstrap import bootstrap_worker_context
from homomics_lab.config import settings
from homomics_lab.jobs import JobService
from homomics_lab.logging_config import (
    configure_logging,
    new_correlation_id,
    set_correlation_id,
)
from homomics_lab.plan import PlanStore
from homomics_lab.scheduler import HomomicsScheduler
from homomics_lab.api.router import api_router


configure_logging(level="INFO" if not settings.debug else "DEBUG", json_format=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = await bootstrap_worker_context(enable_hot_reload=True)

    # Expose initialized registries for API endpoints
    app.state.tool_registry = ctx["tool_registry"]
    app.state.schema_validator = ctx["schema_validator"]
    app.state.skill_executor = ctx["skill_executor"]
    app.state.skill_store = ctx["skill_store"]
    app.state.domain_registry = ctx["domain_registry"]
    app.state.strategy_library = ctx["strategy_library"]
    app.state.domain_reloader = ctx["domain_reloader"]
    app.state.skill_reloader = ctx["skill_reloader"]
    app.state.mcp_client = ctx["mcp_client"]
    app.state.memory_manager = ctx["memory_manager"]

    print(f"Registered {len(app.state.tool_registry.list_all())} builtin tools")
    for external_skills in settings.external_skills_dirs:
        if external_skills.exists():
            print(f"Loaded external skills from {external_skills}")

    # Plan store for persisted, versioned execution plans
    app.state.plan_store = PlanStore()

    # Start background job worker only when worker_mode is enabled.
    # Queued jobs persisted before a restart are recovered into the queue.
    app.state.job_service = JobService()
    app.state.execution_pubsub = app.state.job_service.pubsub
    await app.state.job_service.start_worker()

    # Start scheduled task scheduler (curation, reports, evolution, etc.)
    app.state.scheduler = HomomicsScheduler()
    app.state.scheduler.set_context(ctx)
    await app.state.scheduler.start()

    yield

    # Shutdown: stop scheduler, background worker, and hot-reload watchers
    await app.state.scheduler.shutdown()
    await app.state.job_service.close()
    if app.state.mcp_client is not None:
        await app.state.mcp_client.close()
    if app.state.domain_reloader is not None:
        await app.state.domain_reloader.stop()
    if app.state.skill_reloader is not None:
        await app.state.skill_reloader.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Propagate or generate a correlation id for every request."""
    cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
    set_correlation_id(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
