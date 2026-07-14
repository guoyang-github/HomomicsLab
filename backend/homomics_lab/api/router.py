from fastapi import APIRouter, Depends
from . import chat, collab, cost, domains, nfcore, projects, files, skills, viz, reports, results, skill_generator, health, execution, plan, scheduler, secrets, checkpoints, llm, settings, reproducibility, knowledge, templates, mcp, lineage, waiting
from .auth import admin_router, auth_router, require_admin, require_analyst_or_admin, require_auth
from .rate_limit import rate_limit_dependency

api_router = APIRouter(prefix="/api")

# WebSocket-friendly routers are included without the HTTP-only auth/rate-limit
# dependencies. Their own handlers perform any needed validation.
_PROTECTED_DEPS = [Depends(rate_limit_dependency), Depends(require_auth)]

# Role-protected dependency bundles.
_ADMIN_DEPS = [Depends(rate_limit_dependency), Depends(require_admin)]
_ANALYST_ADMIN_DEPS = [Depends(rate_limit_dependency), Depends(require_analyst_or_admin)]

# Health endpoints must be publicly reachable for load balancers / orchestrators.
api_router.include_router(health.router, tags=["health"])

# Authentication endpoints are public by design.
api_router.include_router(auth_router)

# Admin-only placeholder router (admin_router already declares /admin prefix).
api_router.include_router(admin_router, tags=["admin"])

api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(collab.router, prefix="/collab", tags=["collaboration"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"], dependencies=_PROTECTED_DEPS)
api_router.include_router(lineage.router, prefix="/lineage", tags=["lineage"], dependencies=_PROTECTED_DEPS)
api_router.include_router(files.router, prefix="/files", tags=["files"], dependencies=_PROTECTED_DEPS)
api_router.include_router(skills.router, prefix="/skills", tags=["skills"], dependencies=_ANALYST_ADMIN_DEPS)
api_router.include_router(viz.router, prefix="/viz", tags=["visualization"], dependencies=_PROTECTED_DEPS)
api_router.include_router(reports.router, prefix="/reports", tags=["reports"], dependencies=_PROTECTED_DEPS)
api_router.include_router(skill_generator.router, prefix="/skill-generator", tags=["skill-generator"], dependencies=_PROTECTED_DEPS)
api_router.include_router(cost.router, prefix="/costs", tags=["costs"], dependencies=_PROTECTED_DEPS)
api_router.include_router(nfcore.router, prefix="/nfcore", tags=["nfcore"], dependencies=_PROTECTED_DEPS)
api_router.include_router(execution.router, prefix="/execution", tags=["execution"])
api_router.include_router(plan.router, prefix="/plan", tags=["plan"], dependencies=_PROTECTED_DEPS)
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"], dependencies=_ADMIN_DEPS)
api_router.include_router(domains.router, prefix="/domains", tags=["domains"], dependencies=_PROTECTED_DEPS)
api_router.include_router(secrets.router, prefix="/secrets", tags=["secrets"], dependencies=_ADMIN_DEPS)
api_router.include_router(checkpoints.router, prefix="/jobs", tags=["checkpoints"], dependencies=_PROTECTED_DEPS)
api_router.include_router(llm.router, prefix="/llm", tags=["llm"], dependencies=_ADMIN_DEPS)
api_router.include_router(settings.router, prefix="/settings", tags=["settings"], dependencies=_ADMIN_DEPS)
api_router.include_router(reproducibility.router, prefix="/reproducibility", tags=["reproducibility"], dependencies=_PROTECTED_DEPS)
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"], dependencies=_PROTECTED_DEPS)
api_router.include_router(templates.router, prefix="/templates", tags=["templates"], dependencies=_PROTECTED_DEPS)
api_router.include_router(results.router, prefix="/results", tags=["results"], dependencies=_PROTECTED_DEPS)
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"], dependencies=_ADMIN_DEPS)
api_router.include_router(waiting.router, prefix="/waiting", tags=["waiting"], dependencies=_PROTECTED_DEPS)
