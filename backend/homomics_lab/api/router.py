from fastapi import APIRouter
from . import chat, cost, domains, nfcore, projects, files, skills, viz, reports, skill_generator, health, execution, plan, scheduler

api_router = APIRouter(prefix="/api")
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(viz.router, prefix="/viz", tags=["visualization"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(skill_generator.router, prefix="/skill-generator", tags=["skill-generator"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(cost.router, prefix="/costs", tags=["costs"])
api_router.include_router(nfcore.router, prefix="/nfcore", tags=["nfcore"])
api_router.include_router(execution.router, prefix="/execution", tags=["execution"])
api_router.include_router(plan.router, prefix="/plan", tags=["plan"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
api_router.include_router(domains.router, prefix="/domains", tags=["domains"])
