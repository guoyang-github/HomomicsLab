from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from homomics_lab.api.audit import audit_middleware
from homomics_lab.api.rate_limit import update_limiter_config
from homomics_lab.metrics import metrics_endpoint, prometheus_middleware
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
from homomics_lab.tracing import instrument_fastapi, setup_tracing


configure_logging(level="INFO" if not settings.debug else "DEBUG", json_format=True)
setup_tracing(service_name=settings.otel_service_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = await bootstrap_worker_context(enable_hot_reload=settings.skill_hot_reload_enabled)

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
    app.state.context_engine = ctx["context_engine"]
    app.state.project_state_manager = ctx["project_state_manager"]
    app.state.llm_client = ctx["llm_client"]
    app.state.provenance_recorder = ctx["provenance_recorder"]
    app.state.llm_cache = ctx["llm_cache"]

    # CBKB: shared knowledge base for reproducibility, evolution, and intent enrichment.
    cbkb = ctx["cbkb"]
    app.state.cbkb = cbkb

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

instrument_fastapi(app)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Propagate or generate a correlation id for every request."""
    cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
    set_correlation_id(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add baseline security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# Request audit logging (rotating file). Enabled via HOMOMICS_AUDIT_LOG_ENABLED.
app.middleware("http")(audit_middleware)

# Prometheus metrics middleware.
app.middleware("http")(prometheus_middleware)


# Rate limiting and auth are applied at the API-router level so that
# long-lived WebSocket routes are not forced through HTTP-only dependencies.
update_limiter_config()
app.include_router(api_router)

# CORS: production defaults to no cross-origin access. In debug mode with no
# explicit origins, allow common local frontend dev servers for convenience.
# Override via ``HOMOMICS_CORS_ORIGINS`` in production.
if settings.cors_origins:
    _allow_origins = settings.cors_origins
elif settings.debug:
    _allow_origins = ["http://localhost:5173", "http://localhost:3000"]
else:
    _allow_origins = []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Optional trusted-host enforcement in production.
if getattr(settings, "trusted_hosts", None):
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.5.0"}


@app.get("/health/memory")
async def health_memory(request: Request):
    mm = getattr(request.app.state, "memory_manager", None)
    if mm is None:
        return {
            "session_store": "not_configured",
            "semantic_memory": "not_configured",
        }

    session_ok = True
    try:
        await mm.session_store.get("__health_check__")
    except Exception:
        session_ok = False

    semantic_ok = mm.semantic_memory is not None

    return {
        "session_store": "ok" if session_ok else "error",
        "semantic_memory": "ok" if semantic_ok else "disabled",
    }


@app.get("/health/usage")
async def health_usage(request: Request):
    """Return LLM usage summary for the running process."""
    llm_client = getattr(request.app.state, "llm_client", None)
    if llm_client is None:
        return {"llm_usage": "not_configured"}
    return llm_client.get_usage_summary()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return metrics_endpoint()
