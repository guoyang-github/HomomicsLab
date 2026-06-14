from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOMOMICS_")

    app_name: str = "HomomicsLab"
    port: int = 8080
    host: str = "0.0.0.0"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./homomics_lab.db"
    data_dir: Path = Path("./data")
    skills_dir: Path = Path("./skills")
    external_skills_dir: Optional[Path] = None
    semantic_search_model: Optional[str] = None  # e.g., "all-MiniLM-L6-v2" for dense embeddings

    # Job queue / distributed worker settings (P3)
    queue_backend: str = "memory"  # "memory" | "redis"
    redis_url: str = "redis://localhost:6379/0"
    worker_mode: bool = True  # start a local worker inside the API process
    worker_concurrency: int = 1
    worker_heartbeat_ttl: int = 30  # seconds
    worker_lock_ttl: int = 600  # seconds

    # Scheduled task settings (APScheduler)
    curation_enabled: bool = True
    curation_schedule: str = "0 2 * * *"
    narrative_report_enabled: bool = True
    narrative_report_schedule: str = "0 6 * * *"
    sop_proposal_enabled: bool = True
    sop_proposal_schedule: str = "0 3 * * 0"
    scheduler_timezone: str = "UTC"
    scheduler_run_at_startup: bool = False

    # MCP integration settings
    mcp_enabled: bool = True
    mcp_mode: str = "embedded"  # "embedded" | "stdio" | "sse"
    mcp_server_script: Optional[str] = None


settings = Settings()
