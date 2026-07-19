import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Prevent Hugging Face libraries from blocking startup with network HEAD/etag
# checks when models are already cached locally.  This affects sentence-transformers
# and transformers code paths throughout the backend.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from homomics_lab.api.audit import audit_middleware
from homomics_lab.api.rate_limit import update_limiter_config
from homomics_lab.metrics import metrics_endpoint, prometheus_middleware
from homomics_lab.bootstrap import bootstrap_worker_context, close_worker_context
from homomics_lab.config import settings
from homomics_lab.domain.marketplace import DomainMarketplace
from homomics_lab.jobs import JobService
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.reports.store import ReportStore
from homomics_lab.settings_store import apply_runtime_settings
from homomics_lab.logging_config import (
    configure_logging,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)
from homomics_lab.plan import PlanStore
from homomics_lab.scheduler import HomomicsScheduler
from homomics_lab.version import app_version
from homomics_lab.api.router import api_router
from homomics_lab.tracing import instrument_fastapi, setup_tracing


APP_NAME = "HomomicsLab"
# JSON-lines logging and OpenAPI docs are fixed on; hot reload of skill/domain
# files is fixed on (formerly HOMOMICS_LOG_JSON_FORMAT /
# HOMOMICS_OPENAPI_DOCS_ENABLED / HOMOMICS_SKILL_HOT_RELOAD_ENABLED).
LOG_JSON_FORMAT = True
OPENAPI_DOCS_ENABLED = True
SKILL_HOT_RELOAD_ENABLED = True

configure_logging(level=settings.log_level, json_format=LOG_JSON_FORMAT)
setup_tracing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load any runtime setting overrides before bootstrapping dependent services.
    apply_runtime_settings(settings)

    ctx = await bootstrap_worker_context(
        enable_hot_reload=SKILL_HOT_RELOAD_ENABLED
    )

    # Expose initialized registries for API endpoints
    app.state.tool_registry = ctx["tool_registry"]
    app.state.schema_validator = ctx["schema_validator"]
    app.state.skill_executor = ctx["skill_executor"]
    app.state.skill_store = ctx["skill_store"]
    app.state.domain_registry = ctx["domain_registry"]
    app.state.strategy_library = ctx["strategy_library"]
    app.state.domain_reloader = ctx["domain_reloader"]
    app.state.skill_reloader = ctx["skill_reloader"]
    app.state.mcp_marketplace = ctx["mcp_marketplace"]
    app.state.memory_manager = ctx["memory_manager"]
    app.state.capability_index = ctx["capability_index"]
    app.state.context_engine = ctx["context_engine"]
    app.state.project_state_manager = ctx["project_state_manager"]
    app.state.llm_client = ctx["llm_client"]
    app.state.provenance_recorder = ctx["provenance_recorder"]
    app.state.llm_cache = ctx["llm_cache"]
    app.state.knowledge_index = ctx["knowledge_index"]

    # Analysis templates: scenario presets for plan generation.
    analysis_template_store = ctx["analysis_template_store"]
    app.state.analysis_template_store = analysis_template_store

    # Workflow execution service: routes Plans to local orchestrator or Nextflow.
    app.state.workflow_execution_service = ctx["workflow_execution_service"]

    # Waiting orchestrator: event-driven job suspend/resume.
    app.state.waiting_service = ctx["waiting_service"]

    # CBKB: shared knowledge base for reproducibility, evolution, and intent enrichment.
    cbkb = ctx["cbkb"]
    app.state.cbkb = cbkb

    # Domain template marketplace for importing and listing domain.yaml templates.
    app.state.domain_marketplace = DomainMarketplace(
        builtin_domains_dir=Path(__file__).parent / "domains",
        marketplace_dir=settings.data_dir / "marketplace" / "domains",
        skill_registry=app.state.skill_executor.registry,
    )

    print(f"Registered {len(app.state.tool_registry.list_all())} builtin tools")
    for external_skills in settings.external_skills_dirs:
        if external_skills.exists():
            print(f"Loaded external skills from {external_skills}")

    # Plan store for persisted, versioned execution plans
    app.state.plan_store = PlanStore()

    # Execution trace store for plan/job-level observability
    app.state.trace_store = TraceStore()

    # Persistent analysis report store
    app.state.report_store = ReportStore()

    # Start background job worker only when worker_mode is enabled.
    # Queued jobs persisted before a restart are recovered into the queue.
    app.state.job_service = JobService(
        skill_executor=app.state.skill_executor,
        memory_manager=app.state.memory_manager,
        waiting_service=app.state.waiting_service,
    )
    app.state.execution_pubsub = app.state.job_service.pubsub
    await app.state.job_service.start_worker()

    # Start scheduled task scheduler (curation, reports, evolution, etc.)
    app.state.scheduler = HomomicsScheduler()
    app.state.scheduler.set_context(ctx)
    await app.state.scheduler.start()

    # Wire persisted timer wait conditions into the live scheduler so they
    # survive process restarts; a periodic tick() sweep is the fallback for
    # any one-shot job that gets missed.
    app.state.waiting_service.attach_scheduler(app.state.scheduler.scheduler)
    app.state.waiting_service.rebuild_timer_jobs()
    app.state.scheduler.scheduler.add_job(
        app.state.waiting_service.tick,
        "interval",
        minutes=1,
        id="waiting_tick",
        name="waiting_tick",
        replace_existing=True,
        max_instances=1,
    )

    yield

    # Shutdown: stop scheduler, background worker, and hot-reload watchers
    await app.state.scheduler.shutdown()
    await app.state.job_service.close()
    if getattr(app.state, "trace_store", None) is not None:
        app.state.trace_store = None
    await close_worker_context(ctx)


app = FastAPI(
    title=APP_NAME,
    version=app_version(),
    docs_url="/docs" if OPENAPI_DOCS_ENABLED else None,
    redoc_url="/redoc" if OPENAPI_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if OPENAPI_DOCS_ENABLED else None,
    lifespan=lifespan,
)

instrument_fastapi(app)

logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return a structured error with correlation_id for any unhandled exception."""
    cid = get_correlation_id() or new_correlation_id()
    logger.exception("Unhandled exception correlation_id=%s", cid)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "correlation_id": cid,
        },
        headers={"X-Correlation-ID": cid},
    )


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
    logger.warning(
        "HOMOMICS_CORS_ORIGINS is not set and debug mode is disabled. "
        "Cross-origin frontend requests will be blocked. "
        "Set HOMOMICS_CORS_ORIGINS to your frontend URL for separated deployments."
    )
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
    return {"name": APP_NAME, "version": app_version()}


@app.get("/health")
async def health():
    from homomics_lab.llm.runtime_config import load_llm_runtime_config

    try:
        config = load_llm_runtime_config()
        llm_status = {
            "llm_configured": config.is_configured,
            "llm_provider": config.provider,
            "llm_model": config.model,
        }
    except Exception:
        provider = settings.llm_provider
        model = settings.llm_model
        llm_status = {
            "llm_configured": bool(provider and model),
            "llm_provider": provider,
            "llm_model": model,
        }
    return {
        "status": "ok",
        "version": app_version(),
        **llm_status,
    }


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
