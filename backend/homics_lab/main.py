from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from homics_lab.config import settings
from homics_lab.agent.factory import create_default_agents
from homics_lab.skills.runtime import SkillRuntimeExecutor
from homics_lab.skills.builtin import register_builtin_skills


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.skills_dir.mkdir(parents=True, exist_ok=True)
    create_default_agents()

    # Initialize skills runtime
    app.state.skill_executor = SkillRuntimeExecutor()
    register_builtin_skills(app.state.skill_executor)

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

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
