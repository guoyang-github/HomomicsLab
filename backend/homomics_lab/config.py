from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root: backend/homomics_lab/config.py -> backend -> HomomicsLab
_PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOMOMICS_")

    app_name: str = "HomomicsLab"
    api_version: str = "v1"
    port: int = 8080
    host: str = "0.0.0.0"
    debug: bool = False
    openapi_docs_enabled: bool = True
    database_url: str = "sqlite+aiosqlite:///./homomics_lab.db"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    data_dir: Path = Path("./data")
    # Canonical user skill drop-in directory. Defaults to the project-root
    # ``skills/`` folder so it is stable regardless of the backend's CWD.
    # Override via HOMOMICS_SKILLS_DIR.
    skills_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT / "skills")
    external_skills_dirs: List[Path] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Embedding provider configuration
    # ------------------------------------------------------------------
    embedding_provider: str = (
        "sentence_transformers"  # sentence_transformers | openai | ollama
    )
    embedding_model: Optional[str] = None  # e.g., "BAAI/bge-small-en-v1.5"
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None

    @field_validator("embedding_provider")
    @classmethod
    def _validate_embedding_provider(cls, v: str) -> str:
        allowed = {"sentence_transformers", "openai", "ollama"}
        if v not in allowed:
            raise ValueError(f"embedding_provider must be one of {allowed}, got {v}")
        return v

    # ------------------------------------------------------------------
    # Memory backends (vector + graph)
    # ------------------------------------------------------------------
    vector_store_backend: str = "qdrant"  # qdrant | pgvector | sqlite-vec
    vector_store_url: Optional[str] = (
        None  # e.g., "http://localhost:6333" or postgres URL
    )
    graph_backend: str = "networkx"  # networkx | neo4j
    graph_store_url: Optional[str] = None  # e.g., "bolt://localhost:7687"
    memory_reranker_model: Optional[str] = None
    llm_memory_extraction_enabled: bool = False

    @field_validator("vector_store_backend")
    @classmethod
    def _validate_vector_store_backend(cls, v: str) -> str:
        allowed = {"qdrant", "pgvector", "sqlite-vec"}
        if v not in allowed:
            raise ValueError(f"vector_store_backend must be one of {allowed}, got {v}")
        return v

    @field_validator("graph_backend")
    @classmethod
    def _validate_graph_backend(cls, v: str) -> str:
        allowed = {"networkx", "neo4j"}
        if v not in allowed:
            raise ValueError(f"graph_backend must be one of {allowed}, got {v}")
        return v

    # Deprecated: kept briefly for settings migration; will be removed in a follow-up.
    semantic_search_model: Optional[str] = None
    semantic_memory_backend: str = "sqlite"
    semantic_memory_postgres_url: Optional[str] = None

    @field_validator("semantic_memory_backend")
    @classmethod
    def _validate_semantic_memory_backend(cls, v: str) -> str:
        allowed = {"sqlite", "postgres"}
        if v not in allowed:
            raise ValueError(
                f"semantic_memory_backend must be one of {allowed}, got {v}"
            )
        return v

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        """Normalize and validate the database URL.

        - SQLite URLs must use the async ``aiosqlite`` driver.
        - PostgreSQL URLs must use the async ``asyncpg`` driver.
        """
        v = v.strip()
        if v.startswith("sqlite://") and not v.startswith("sqlite+aiosqlite://"):
            raise ValueError(
                "SQLite database_url must use the aiosqlite driver "
                "(e.g. sqlite+aiosqlite:///path/to/db.db)"
            )
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            # Normalize legacy prefixes to asyncpg.
            if not v.startswith("postgresql+asyncpg://"):
                v = "postgresql+asyncpg://" + v.split("://", 1)[1]
        return v

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

    @field_validator("allowed_skill_git_urls", mode="before")
    @classmethod
    def _parse_allowed_skill_git_urls(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [part.strip() for part in v.split(",") if part.strip()]
        return [str(item).strip() for item in v if str(item).strip()]

    @field_validator("session_store_url")
    @classmethod
    def _validate_session_store_url(cls, v: str) -> str:
        """Normalize and validate the session store database URL."""
        v = v.strip()
        if v.startswith("sqlite://") and not v.startswith("sqlite+aiosqlite://"):
            raise ValueError(
                "session_store_url must use the aiosqlite driver "
                "(e.g. sqlite+aiosqlite:///path/to/db.db)"
            )
        if v.startswith("postgresql://") or v.startswith("postgres://"):
            if not v.startswith("postgresql+asyncpg://"):
                v = "postgresql+asyncpg://" + v.split("://", 1)[1]
        return v

    @field_validator("storage_backend")
    @classmethod
    def _validate_storage_backend(cls, v: str) -> str:
        allowed = {"local", "s3"}
        if v not in allowed:
            raise ValueError(f"storage_backend must be one of {allowed}, got {v}")
        return v

    @field_validator("queue_backend")
    @classmethod
    def _validate_queue_backend(cls, v: str) -> str:
        allowed = {"memory", "redis"}
        if v not in allowed:
            raise ValueError(f"queue_backend must be one of {allowed}, got {v}")
        return v

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
    auto_load_domain_strategies: bool = True
    skill_sandbox_backend: str = "auto"  # "auto" | "local" | "bubblewrap" | "container"
    # Comma-separated list of allowed git URL prefixes for skill/domain import.
    # Empty list allows all git URLs (development default). Set this in production
    # to restrict imports to trusted hosts, e.g. "https://github.com/your-org/".
    allowed_skill_git_urls: List[str] = Field(default_factory=list)
    skill_container_image: str = "python:3.10-slim"
    r_container_image: str = "r-base:4.3.0"
    skill_container_memory_mb: int = 1024
    skill_container_cpus: float = 1.0
    skill_container_pids_limit: int = 64
    skill_container_readonly_root: bool = True
    skill_container_venv_mount: bool = True
    auto_install_dependencies: bool = (
        False  # create venvs and install skill deps automatically
    )
    skill_hot_reload_enabled: bool = (
        True  # watch sibling skill repos and domain files at startup
    )
    skill_sibling_discovery_enabled: bool = (
        False  # auto-discover ../<domain>-Skills/skills
    )
    skills_shell_execution_enabled: bool = False  # Claude Code-style !`cmd` injection
    domain_strict_validation: bool = False  # if False, missing skills become warnings instead of failing the whole domain
    interactive_mode: bool = False  # require approval for high-risk tool calls
    force_sandbox: bool = (
        True  # if True, shell_exec and CodeAct must run through a sandbox
    )
    allow_pickle_serialization: bool = (
        False  # if False, DataStore refuses pickle fallback
    )

    # Auth / rate limiting (opt-in for local development)
    auth_enabled: bool = False
    api_key: Optional[str] = None  # production single-shared-key or bootstrap key
    admin_initial_password: Optional[str] = None  # password for the first-boot admin user

    # JWT settings (required when auth_enabled=True and no OIDC is configured)
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 1 day

    # OIDC settings (optional; if set, JWT access tokens are verified via JWKS)
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None

    rate_limit_enabled: bool = False
    rate_limit_backend: str = "memory"  # "memory" | "redis"
    rate_limit_redis_url: Optional[str] = None
    rate_limit_trust_proxy: bool = False
    rate_limit_requests_per_minute: int = 60
    rate_limit_upload_max_bytes: int = 1024 * 1024 * 1024  # 1 GB
    max_upload_file_bytes: int = 1024 * 1024 * 1024  # 1 GB per file

    @field_validator("rate_limit_backend")
    @classmethod
    def _validate_rate_limit_backend(cls, v: str) -> str:
        allowed = {"memory", "redis"}
        if v not in allowed:
            raise ValueError(f"rate_limit_backend must be one of {allowed}, got {v}")
        return v

    @model_validator(mode="after")
    def _default_rate_limit_redis_url(self):
        if self.rate_limit_redis_url is None:
            self.rate_limit_redis_url = self.redis_url
        return self

    # Audit logging
    audit_log_enabled: bool = False
    audit_log_path: Optional[Path] = None

    # Secrets manager
    secrets_db_path: Optional[Path] = None
    secrets_master_key: Optional[str] = None
    secrets_plaintext_fallback: bool = (
        False  # dangerous; only for local dev without cryptography
    )

    # Cost control
    monthly_budget_usd: Optional[float] = (
        None  # per-user/tenant budget (enforced when auth enabled)
    )
    max_llm_cost_per_request_usd: Optional[float] = None

    # LLM routing
    llm_provider: Optional[str] = (
        None  # e.g. openai, deepseek, qwen, zhipu, moonshot, ollama
    )
    llm_model: Optional[str] = None
    llm_fallback_models: Optional[str] = None  # comma-separated list

    # LLM infrastructure (P5)
    llm_response_cache_enabled: bool = True
    llm_response_cache_backend: str = "local"  # "local" | "redis"
    llm_response_cache_redis_url: Optional[str] = None
    llm_response_cache_dir: Path = Field(
        default_factory=lambda: Path("./data/llm_cache")
    )
    llm_response_cache_ttl_seconds: float = 3600.0
    llm_response_cache_max_entries: int = 1000
    llm_complexity_routing_enabled: bool = True

    @field_validator("llm_response_cache_backend")
    @classmethod
    def _validate_llm_response_cache_backend(cls, v: str) -> str:
        allowed = {"local", "redis"}
        if v not in allowed:
            raise ValueError(
                f"llm_response_cache_backend must be one of {allowed}, got {v}"
            )
        return v

    @model_validator(mode="after")
    def _default_llm_response_cache_redis_url(self):
        if self.llm_response_cache_redis_url is None:
            self.llm_response_cache_redis_url = self.redis_url
        return self

    # OpenTelemetry tracing
    otel_enabled: bool = False
    otel_exporter: str = "console"  # console | otlp
    otel_otlp_endpoint: Optional[str] = "http://localhost:4317"
    otel_service_name: str = "homomicslab"

    # Logging
    log_level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR | CRITICAL
    log_json_format: bool = True  # JSON lines vs. plain text

    # Health checks
    health_check_timeout_seconds: float = 5.0

    # CORS / host security
    cors_origins: Optional[List[str]] = None  # e.g. ["https://app.homomics.lab"]
    trusted_hosts: Optional[List[str]] = None  # e.g. ["app.homomics.lab"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, str):
            parts = [part.strip() for part in v.split(",") if part.strip()]
            return parts if parts else None
        if isinstance(v, list):
            origins = [str(item).strip() for item in v if str(item).strip()]
            return origins if origins else None
        return None

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
    max_skill_timeout_seconds: float = 86400.0

    # Workflow execution settings
    workflow_nextflow_enabled: bool = True
    workflow_nextflow_min_phases: int = 3
    workflow_cache_enabled: bool = True
    workflow_cache_dir: Optional[Path] = None
    workflow_cache_content_hash_limit: int = 10 * 1024 * 1024  # 10 MB
    nextflow_webhook_secret: Optional[str] = None  # shared secret for Nextflow weblog callbacks

    @model_validator(mode="after")
    def _validate_timeout_bounds(self):
        if self.default_job_timeout_seconds > self.max_skill_timeout_seconds:
            raise ValueError(
                "default_job_timeout_seconds must be <= max_skill_timeout_seconds"
            )
        if self.max_skill_timeout_seconds < 1:
            raise ValueError("max_skill_timeout_seconds must be at least 1")
        return self

    # Result / cache settings
    result_inline_size_limit_bytes: int = 10 * 1024 * 1024
    skill_cache_enabled: bool = True
    skill_cache_dir: Path = Field(default_factory=lambda: Path("./data/skill_cache"))
    skill_fallback_concatenation: bool = (
        True  # deprecated: concat all .py/.R when no entrypoint
    )

    # Literature / RAP settings
    literature_retrieval_enabled: bool = False  # requires network; disabled by default
    ncbi_email: Optional[str] = None
    ncbi_api_key: Optional[str] = None
    literature_cache_ttl_seconds: float = 3600.0
    literature_max_results: int = 10

    # HITL thresholds
    hitl_confidence_threshold: float = 0.7
    hitl_risk_threshold: float = 0.6

    # Debate judge backend ("rule" | "llm")
    debate_judge_backend: str = "rule"

    @field_validator("debate_judge_backend")
    @classmethod
    def _validate_debate_judge_backend(cls, v: str) -> str:
        allowed = {"rule", "llm"}
        if v not in allowed:
            raise ValueError(f"debate_judge_backend must be one of {allowed}, got {v}")
        return v

    # CodeAct safety settings
    codeact_hitl_level: str = "high"  # "low" | "medium" | "high" | "critical" | "never"

    # CodeAct cache settings
    codeact_cache_enabled: bool = True
    codeact_cache_dir: Path = Field(
        default_factory=lambda: Path("./data/codeact_cache")
    )

    # MCP integration settings
    mcp_enabled: bool = True
    mcp_mode: str = "embedded"  # "embedded" | "stdio" | "sse"
    mcp_server_script: Optional[str] = None
    mcp_server_url: Optional[str] = None

    @field_validator("mcp_mode")
    @classmethod
    def _validate_mcp_mode(cls, v: str) -> str:
        allowed = {"embedded", "stdio", "sse"}
        if v not in allowed:
            raise ValueError(f"mcp_mode must be one of {allowed}, got {v}")
        return v

    # Session / memory settings
    session_store_url: str = "sqlite+aiosqlite:///./data/sessions.db"
    session_ttl_days: int = 90
    enable_semantic_memory: bool = True

    # ContextEngine settings
    context_engine_model: Optional[str] = None  # default model for context budget
    context_token_budget_mode: str = "normal"  # concise | normal | verbatim
    context_enable_project_state: bool = True
    context_enable_episodic_summary: bool = True
    context_output_reserve_tokens: int = 2000

    def masked_dump(self) -> Dict[str, Any]:
        """Return a copy of the settings with sensitive values redacted.

        Use this for logs, health checks, or any user-facing output.
        """
        data = self.model_dump()
        sensitive_keys = {
            "api_key",
            "secrets_master_key",
            "storage_s3_secret_key",
            "llm_api_key",
            "openai_api_key",
            "anthropic_api_key",
        }

        def _mask(value: Any) -> Any:
            if isinstance(value, str) and value:
                return "*" * min(len(value), 8)
            return value

        return {k: _mask(v) if k in sensitive_keys else v for k, v in data.items()}


settings = Settings()
