from pathlib import Path
from typing import Any, List, Optional

from pydantic import Field, field_validator
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
    external_skills_dirs: List[Path] = Field(default_factory=list)
    semantic_search_model: Optional[str] = None  # e.g., "all-MiniLM-L6-v2" for dense embeddings

    @field_validator("external_skills_dirs", mode="before")
    @classmethod
    def _parse_external_skills_dirs(cls, v: Any) -> List[Path]:
        if v is None:
            return []
        if isinstance(v, (str, Path)):
            v = [v]
        paths: List[Path] = []
        for item in v:
            if isinstance(item, str):
                for part in item.split(","):
                    part = part.strip()
                    if part:
                        paths.append(Path(part))
            elif isinstance(item, Path):
                paths.append(item)
        return paths

    @property
    def external_skills_dir(self) -> Optional[Path]:
        """Backward-compatible alias returning the first external skills directory."""
        return self.external_skills_dirs[0] if self.external_skills_dirs else None

    # Job queue / distributed worker settings (P3)
    queue_backend: str = "memory"  # "memory" | "redis"
    redis_url: str = "redis://localhost:6379/0"
    worker_mode: bool = True  # start a local worker inside the API process
    worker_concurrency: int = 1
    worker_heartbeat_ttl: int = 30  # seconds
    worker_lock_ttl: int = 600  # seconds

    # Scheduled task settings (APScheduler) — disabled by default for individual users
    # to avoid surprise token/CPU/GPU usage. Enable explicitly in production if needed.
    curation_enabled: bool = False
    curation_schedule: str = "0 2 * * *"
    narrative_report_enabled: bool = False
    narrative_report_schedule: str = "0 6 * * *"
    sop_proposal_enabled: bool = False
    sop_proposal_schedule: str = "0 3 * * 0"
    evolution_enabled: bool = False
    evolution_schedule: str = "0 2 * * *"
    scheduler_timezone: str = "UTC"
    scheduler_run_at_startup: bool = False

    # Skill sandbox / security settings
    skill_sandbox_backend: str = "auto"  # "auto" | "local" | "bubblewrap" | "container"
    skill_container_image: str = "python:3.10-slim"
    skills_shell_execution_enabled: bool = False  # Claude Code-style !`cmd` injection
    interactive_mode: bool = False  # require approval for high-risk tool calls
    force_sandbox: bool = True  # if True, shell_exec and CodeAct must run through a sandbox
    allow_pickle_serialization: bool = False  # if False, DataStore refuses pickle fallback

    # Auth / rate limiting (opt-in for local development)
    auth_enabled: bool = False
    api_key: Optional[str] = None  # production single-shared-key or bootstrap key
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 60
    rate_limit_upload_max_bytes: int = 1024 * 1024 * 1024  # 1 GB
    max_upload_file_bytes: int = 1024 * 1024 * 1024  # 1 GB per file

    # Audit logging
    audit_log_enabled: bool = False
    audit_log_path: Optional[Path] = None

    # Cost control
    monthly_budget_usd: Optional[float] = None  # per-user/tenant budget (enforced when auth enabled)
    max_llm_cost_per_request_usd: Optional[float] = None

    # CORS / host security
    cors_origins: Optional[List[str]] = None  # e.g. ["https://app.homomics.lab"]
    trusted_hosts: Optional[List[str]] = None  # e.g. ["app.homomics.lab"]

    # Object storage abstraction
    storage_backend: str = "local"  # "local" | "s3"
    storage_s3_bucket: Optional[str] = None
    storage_s3_endpoint_url: Optional[str] = None
    storage_s3_region: Optional[str] = None
    storage_s3_access_key: Optional[str] = None
    storage_s3_secret_key: Optional[str] = None
    storage_s3_public_url_prefix: Optional[str] = None

    # nf-core integration
    nfcore_enabled: bool = True
    nfcore_cache_dir: Optional[Path] = None
    nfcore_default_profiles: List[str] = Field(default_factory=lambda: ["docker"])

    @field_validator("nfcore_default_profiles", mode="before")
    @classmethod
    def _parse_nfcore_profiles(cls, v: Any) -> List[str]:
        if v is None:
            return ["docker"]
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return list(v)

    # Job / worker settings
    default_job_timeout_seconds: float = 3600.0

    # Result / cache settings
    result_inline_size_limit_bytes: int = 10 * 1024 * 1024
    skill_cache_enabled: bool = True
    skill_cache_dir: Path = Field(default_factory=lambda: Path("./data/skill_cache"))

    # Literature / RAP settings
    literature_retrieval_enabled: bool = False  # requires network; disabled by default

    # CodeAct safety settings
    codeact_hitl_level: str = "high"  # "low" | "medium" | "high" | "critical" | "never"

    # CodeAct cache settings
    codeact_cache_enabled: bool = True
    codeact_cache_dir: Path = Field(default_factory=lambda: Path("./data/codeact_cache"))

    # MCP integration settings
    mcp_enabled: bool = True
    mcp_mode: str = "embedded"  # "embedded" | "stdio" | "sse"
    mcp_server_script: Optional[str] = None

    # Session / memory settings
    session_store_url: str = "sqlite+aiosqlite:///./data/sessions.db"
    session_ttl_days: int = 90
    enable_semantic_memory: bool = True


settings = Settings()
