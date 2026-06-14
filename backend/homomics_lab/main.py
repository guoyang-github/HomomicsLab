from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from homomics_lab.bootstrap import bootstrap_worker_context
from homomics_lab.config import settings
from homomics_lab.jobs import JobService
from homomics_lab.plan import PlanStore
from homomics_lab.scheduler import HomomicsScheduler
from homomics_lab.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = await bootstrap_worker_context(enable_hot_reload=True)

    # Expose initialized registries for API endpoints
    app.state.tool_registry = ctx["tool_registry"]
    app.state.schema_validator = ctx["schema_validator"]
    app.state.skill_executor = ctx["skill_executor"]
    app.state.domain_registry = ctx["domain_registry"]
    app.state.strategy_library = ctx["strategy_library"]
    app.state.domain_reloader = ctx["domain_reloader"]
    app.state.skill_reloader = ctx["skill_reloader"]
    app.state.mcp_client = ctx["mcp_client"]

    print(f"Registered {len(app.state.tool_registry.list_all())} builtin tools")
    external_skills = getattr(settings, "external_skills_dir", None)
    if external_skills and external_skills.exists():
        print(f"Loaded external skills from {external_skills}")

    # Plan store for persisted, versioned execution plans
    app.state.plan_store = PlanStore()

    # Start background job worker only when worker_mode is enabled
    app.state.job_service = JobService()
    app.state.execution_pubsub = app.state.job_service.pubsub
    app.state.job_service.start_worker()

    # Start scheduled task scheduler (curation, reports, etc.)
    app.state.scheduler = HomomicsScheduler()
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
