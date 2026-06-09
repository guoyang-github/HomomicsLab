from fastapi import APIRouter
from . import chat, projects, files, skills, viz, reports, skill_generator

api_router = APIRouter(prefix="/api")
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(viz.router, prefix="/viz", tags=["visualization"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(skill_generator.router, prefix="/skill-generator", tags=["skill-generator"])
