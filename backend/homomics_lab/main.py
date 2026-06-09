from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from homomics_lab.config import settings
from homomics_lab.agent.factory import create_default_agents
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.skills.external_loader import ExternalSkillLoader
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    create_default_agents()

    # Initialize skills runtime with metrics tracking
    tracker = SkillPerformanceTracker()
    app.state.skill_executor = SkillRuntimeExecutor(tracker=tracker)
    register_builtin_skills(app.state.skill_executor)

    # Load external skills if configured
    if settings.external_skills_dir and settings.external_skills_dir.exists():
        loader = ExternalSkillLoader(registry=app.state.skill_executor.registry)
        loaded = loader.load_all(settings.external_skills_dir)
        for skill in loaded:
            app.state.skill_executor.register_skill(skill)
        print(f"Loaded {len(loaded)} external skills from {settings.external_skills_dir}")

    yield


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
