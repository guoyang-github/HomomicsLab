from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root: backend/homomics_lab/config.py -> backend -> HomomicsLab
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_BACKEND_ROOT = Path(__file__).parent.parent


def _abs_backend_path(path: Path) -> Path:
    """Resolve a config path relative to the backend package unless absolute."""
    p = Path(path)
    return p if p.is_absolute() else (_BACKEND_ROOT / p).resolve()


def _abs_sqlite_url(url: str) -> str:
    """Anchor relative SQLite URLs to the backend directory.

    Relative sqlite URLs otherwise depend on the process CWD, which is fragile
    once background jobs execute inside per-project workspaces.
    """
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix):
        return url
    raw = url[len(prefix):]
    if raw.startswith("/") or raw in {":memory:", ""}:
        return url
    return prefix + str(_abs_backend_path(Path(raw)))


class Settings(BaseSettings):
    """User-visible and deployment-necessary configuration.

    Everything tunable that no user class ever needs to change lives as a
    module-level constant at its call site instead of here (see
    ``docs/improvement-plan-v2.0.md`` section 2). New fields must justify
    which user, in which scenario, must change them.
    """

    model_config = SettingsConfigDict(env_prefix="HOMOMICS_")

    # ------------------------------------------------------------------
    # Service
    # ------------------------------------------------------------------
    port: int = 8080
    debug: bool = False
    log_level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR | CRITICAL

    # ------------------------------------------------------------------
    # Data / storage
    # ------------------------------------------------------------------
    data_dir: Path = Path("./data")
    database_url: str = "sqlite+aiosqlite:///./homomics_lab.db"
    session_store_url: str = "sqlite+aiosqlite:///./data/sessions.db"
    storage_backend: str = "local"  # "local" | "s3"
    storage_s3_bucket: Optional[str] = None
    storage_s3_endpoint_url: Optional[str] = None
    storage_s3_region: Optional[str] = None
    storage_s3_access_key: Optional[str] = None
    storage_s3_secret_key: Optional[str] = None
    storage_s3_public_url_prefix: Optional[str] = None

    # ------------------------------------------------------------------
    # Job queue / worker
    # ------------------------------------------------------------------
    queue_backend: str = "memory"  # "memory" | "redis"
    redis_url: str = "redis://localhost:6379/0"
    worker_mode: bool = True  # start a local worker inside the API process

    # ------------------------------------------------------------------
    # LLM routing (API keys/base URLs come from the secrets store or the
    # provider-specific env vars, see llm/runtime_config.py)
    # ------------------------------------------------------------------
    llm_provider: Optional[str] = (
        None  # e.g. openai, deepseek, qwen, zhipu, moonshot, ollama
    )
    llm_model: Optional[str] = None

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------
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

    @field_validator("data_dir", mode="before")
    @classmethod
    def _validate_data_dir(cls, v: Any) -> Path:
        return _abs_backend_path(Path(v))

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
        return _abs_sqlite_url(v)

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
        return _abs_sqlite_url(v)

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

    # ------------------------------------------------------------------
    # Skill sandbox / security
    # ------------------------------------------------------------------
    skill_sandbox_backend: str = "auto"  # "auto" | "local" | "bubblewrap" | "container"
    # Optional explicit Python interpreter for skill/sandbox execution. When set,
    # sandboxes prepend this interpreter's bin directory to PATH so skills can use
    # a pre-installed environment (e.g. a conda env or project venv). If unset,
    # the backend process's own interpreter is used.
    skill_python_path: Optional[str] = None
    # Comma-separated list of allowed git URL prefixes for skill/domain import.
    # Empty list allows all git URLs (development default). Set this in production
    # to restrict imports to trusted hosts, e.g. "https://github.com/your-org/".
    allowed_skill_git_urls: List[str] = Field(default_factory=list)
    interactive_mode: bool = False  # require approval for high-risk tool calls
    force_sandbox: bool = (
        True  # if True, shell_exec and CodeAct must run through a sandbox
    )
    allow_pickle_serialization: bool = (
        False  # if False, DataStore refuses pickle fallback
    )
    # Shared secret used to authenticate Nextflow weblog callbacks.
    nextflow_webhook_secret: Optional[str] = None

    # ------------------------------------------------------------------
    # Auth (opt-in for local development)
    # ------------------------------------------------------------------
    auth_enabled: bool = False
    api_key: Optional[str] = None  # production single-shared-key or bootstrap key
    admin_initial_password: Optional[str] = None  # password for the first-boot admin user

    # JWT settings (required when auth_enabled=True and no OIDC is configured)
    jwt_secret_key: Optional[str] = None

    # OIDC settings (optional; if set, JWT access tokens are verified via JWKS)
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None

    # Rate limiting (opt-in)
    rate_limit_enabled: bool = False

    # Audit logging (opt-in)
    audit_log_enabled: bool = False

    # Secrets manager
    secrets_master_key: Optional[str] = None

    # ------------------------------------------------------------------
    # CORS / host security
    # ------------------------------------------------------------------
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

    def masked_dump(self) -> Dict[str, Any]:
        """Return a copy of the settings with sensitive values redacted.

        Use this for logs, health checks, or any user-facing output.
        """
        data = self.model_dump()
        sensitive_keys = {
            "api_key",
            "admin_initial_password",
            "jwt_secret_key",
            "secrets_master_key",
            "storage_s3_secret_key",
            "embedding_api_key",
        }

        def _mask(value: Any) -> Any:
            if isinstance(value, str) and value:
                return "*" * min(len(value), 8)
            return value

        return {k: _mask(v) if k in sensitive_keys else v for k, v in data.items()}


settings = Settings()
