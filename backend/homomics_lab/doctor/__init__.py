"""Doctor — health check and diagnostics for HomomicsLab.

Provides comprehensive system diagnostics:
  - Dependency availability (sqlite-vec, sentence-transformers, scanpy, etc.)
  - Skill system status (builtin/external counts)
  - Database connectivity
  - HPC scheduler availability
  - Disk space
  - Environment configuration

Usage:
    from homomics_lab.doctor import HealthChecker
    checker = HealthChecker()
    report = checker.run_all_checks()
"""

import asyncio
import inspect
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: str  # "ok", "warning", "error"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health diagnostic report."""

    overall: str  # "healthy", "degraded", "unhealthy"
    checks: List[CheckResult]
    timestamp: str
    version: str = "0.5.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "version": self.version,
            "timestamp": self.timestamp,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class HealthChecker:
    """Runs diagnostic checks across the system."""

    def __init__(self, skill_executor=None):
        self.skill_executor = skill_executor

    async def _run_with_timeout(
        self, name: str, coro_or_result, timeout: float
    ) -> CheckResult:
        """Run a single check, enforcing a timeout for async checks."""
        if inspect.iscoroutine(coro_or_result):
            try:
                return await asyncio.wait_for(coro_or_result, timeout=timeout)
            except asyncio.TimeoutError:
                return CheckResult(
                    name=name,
                    status="error",
                    message=f"Health check '{name}' timed out after {timeout}s",
                    details={"timeout_seconds": timeout},
                )
        return coro_or_result

    async def run_all_checks(self, timeout_seconds: float = 5.0) -> HealthReport:
        """Execute all health checks and compile report."""
        checks = await asyncio.gather(
            self._run_with_timeout(
                "python_version", self._check_python_version(), timeout_seconds
            ),
            self._run_with_timeout(
                "core_dependencies", self._check_core_dependencies(), timeout_seconds
            ),
            self._run_with_timeout(
                "optional_dependencies",
                self._check_optional_dependencies(),
                timeout_seconds,
            ),
            self._run_with_timeout("database", self._check_database(), timeout_seconds),
            self._run_with_timeout("redis", self._check_redis(), timeout_seconds),
            self._run_with_timeout("storage", self._check_storage(), timeout_seconds),
            self._run_with_timeout(
                "skill_system", self._check_skill_system(), timeout_seconds
            ),
            self._run_with_timeout(
                "disk_space", self._check_disk_space(), timeout_seconds
            ),
            self._run_with_timeout(
                "hpc_schedulers", self._check_hpc_schedulers(), timeout_seconds
            ),
        )

        # Determine overall status
        statuses = [c.status for c in checks]
        if any(s == "error" for s in statuses):
            overall = "unhealthy"
        elif any(s == "warning" for s in statuses):
            overall = "degraded"
        else:
            overall = "healthy"

        return HealthReport(
            overall=overall,
            checks=checks,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _check_python_version(self) -> CheckResult:
        """Check Python version meets requirements."""
        version_info = sys.version_info
        version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

        if version_info.major < 3 or (
            version_info.major == 3 and version_info.minor < 10
        ):
            return CheckResult(
                name="python_version",
                status="error",
                message=f"Python {version_str} is too old. Requires >= 3.10.",
                details={"current": version_str, "required": ">=3.10"},
            )

        return CheckResult(
            name="python_version",
            status="ok",
            message=f"Python {version_str}",
            details={"current": version_str},
        )

    def _check_core_dependencies(self) -> CheckResult:
        """Check core runtime dependencies."""
        core_deps = [
            "fastapi",
            "pydantic",
            "sqlalchemy",
            "numpy",
        ]

        missing = []
        versions = {}

        for dep in core_deps:
            try:
                mod = __import__(dep)
                versions[dep] = getattr(mod, "__version__", "unknown")
            except ImportError:
                missing.append(dep)

        if missing:
            return CheckResult(
                name="core_dependencies",
                status="error",
                message=f"Missing core dependencies: {', '.join(missing)}",
                details={"missing": missing, "versions": versions},
            )

        return CheckResult(
            name="core_dependencies",
            status="ok",
            message="All core dependencies available",
            details={"versions": versions},
        )

    def _check_optional_dependencies(self) -> CheckResult:
        """Check optional but important dependencies."""
        optional_deps = {
            "sqlite_vec": "sqlite-vec (semantic memory)",
            "sentence_transformers": "sentence-transformers (embeddings)",
            "sklearn": "scikit-learn (TF-IDF search)",
            "scanpy": "scanpy (single-cell analysis)",
            "anndata": "anndata (data structures)",
        }

        missing = []
        versions = {}

        for mod_name, description in optional_deps.items():
            try:
                mod = __import__(mod_name)
                versions[description] = getattr(mod, "__version__", "unknown")
            except ImportError:
                missing.append(description)

        if missing:
            return CheckResult(
                name="optional_dependencies",
                status="warning",
                message=f"Optional dependencies missing: {', '.join(missing)}",
                details={"missing": missing, "available": versions},
            )

        return CheckResult(
            name="optional_dependencies",
            status="ok",
            message="All optional dependencies available",
            details={"versions": versions},
        )

    def _check_skill_system(self) -> CheckResult:
        """Check skill registry status."""
        if self.skill_executor is None:
            return CheckResult(
                name="skill_system",
                status="warning",
                message="Skill executor not initialized",
                details={"registered_skills": 0},
            )

        registry = self.skill_executor.registry
        skills = registry.list_all()
        builtin_count = sum(1 for s in skills if s.metadata.get("source") == "builtin")
        external_count = sum(
            1 for s in skills if s.metadata.get("source") == "external"
        )

        details = {
            "total_skills": len(skills),
            "builtin_skills": builtin_count,
            "external_skills": external_count,
        }

        if len(skills) == 0:
            return CheckResult(
                name="skill_system",
                status="warning",
                message="No skills registered",
                details=details,
            )

        return CheckResult(
            name="skill_system",
            status="ok",
            message=f"{len(skills)} skills registered ({builtin_count} builtin, {external_count} external)",
            details=details,
        )

    def _check_disk_space(self) -> CheckResult:
        """Check available disk space."""
        try:
            stat = shutil.disk_usage("/tmp")
            total_gb = stat.total / (1024**3)
            free_gb = stat.free / (1024**3)
            used_pct = (stat.used / stat.total) * 100

            details = {
                "total_gb": round(total_gb, 2),
                "free_gb": round(free_gb, 2),
                "used_percent": round(used_pct, 1),
            }

            if free_gb < 1:
                return CheckResult(
                    name="disk_space",
                    status="error",
                    message=f"Critical: only {free_gb:.1f} GB free",
                    details=details,
                )
            elif free_gb < 5:
                return CheckResult(
                    name="disk_space",
                    status="warning",
                    message=f"Low disk space: {free_gb:.1f} GB free",
                    details=details,
                )

            return CheckResult(
                name="disk_space",
                status="ok",
                message=f"{free_gb:.1f} GB free ({used_pct:.1f}% used)",
                details=details,
            )
        except Exception as e:
            return CheckResult(
                name="disk_space",
                status="warning",
                message=f"Could not check disk space: {e}",
                details={},
            )

    def _check_hpc_schedulers(self) -> CheckResult:
        """Check which HPC schedulers are available."""
        available = []

        # Check SLURM
        if shutil.which("sbatch"):
            available.append("slurm")

        # Check Nextflow
        if shutil.which("nextflow"):
            available.append("nextflow")

        # Local is always available
        available.append("local")

        return CheckResult(
            name="hpc_schedulers",
            status="ok",
            message=f"Available: {', '.join(available)}",
            details={"available": available},
        )

    async def _check_database(self) -> CheckResult:
        """Ping the configured SQL database."""
        from homomics_lab.config import settings
        from homomics_lab.database.connection import get_engine

        start = time.perf_counter()
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                result = await conn.exec_driver_sql("SELECT 1")
                ok = result.scalar() == 1
            latency = (time.perf_counter() - start) * 1000
            if ok:
                return CheckResult(
                    name="database",
                    status="ok",
                    message="Database connection succeeded",
                    details={
                        "url": self._mask_url(settings.database_url),
                        "latency_ms": round(latency, 2),
                    },
                )
            return CheckResult(
                name="database",
                status="error",
                message="Database ping returned unexpected result",
                details={"latency_ms": round(latency, 2)},
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return CheckResult(
                name="database",
                status="error",
                message=f"Database connection failed: {exc}",
                details={"latency_ms": round(latency, 2)},
            )

    async def _check_redis(self) -> CheckResult:
        """Ping Redis when the Redis queue backend is configured."""
        from homomics_lab.config import settings

        start = time.perf_counter()
        if settings.queue_backend != "redis":
            return CheckResult(
                name="redis",
                status="ok",
                message="Redis backend is not enabled",
                details={},
            )
        try:
            from redis.asyncio import Redis

            client = Redis.from_url(settings.redis_url)
            try:
                ok = await client.ping()
            finally:
                await client.close()
            latency = (time.perf_counter() - start) * 1000
            if ok:
                return CheckResult(
                    name="redis",
                    status="ok",
                    message="Redis ping succeeded",
                    details={
                        "url": self._mask_url(settings.redis_url),
                        "latency_ms": round(latency, 2),
                    },
                )
            return CheckResult(
                name="redis",
                status="error",
                message="Redis ping returned unexpected result",
                details={"latency_ms": round(latency, 2)},
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return CheckResult(
                name="redis",
                status="error",
                message=f"Redis connection failed: {exc}",
                details={"latency_ms": round(latency, 2)},
            )

    async def _check_storage(self) -> CheckResult:
        """Verify that the configured object storage backend is usable."""
        from homomics_lab.config import settings

        start = time.perf_counter()
        try:
            from homomics_lab.storage import get_storage_backend

            backend = get_storage_backend()
            ok = await backend.health_check()
            latency = (time.perf_counter() - start) * 1000
            if ok:
                return CheckResult(
                    name="storage",
                    status="ok",
                    message="Object storage backend is reachable",
                    details={
                        "backend": settings.storage_backend,
                        "latency_ms": round(latency, 2),
                    },
                )
            return CheckResult(
                name="storage",
                status="error",
                message="Object storage backend health check failed",
                details={
                    "backend": settings.storage_backend,
                    "latency_ms": round(latency, 2),
                },
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return CheckResult(
                name="storage",
                status="error",
                message=f"Storage backend check failed: {exc}",
                details={
                    "backend": settings.storage_backend,
                    "latency_ms": round(latency, 2),
                },
            )

    @staticmethod
    def _mask_url(url: Optional[str]) -> Optional[str]:
        """Strip credentials from URLs before returning them in responses."""
        if not url:
            return url
        try:
            parsed = urlparse(url)
            if parsed.username or parsed.password:
                netloc = parsed.hostname or ""
                if parsed.port:
                    netloc += f":{parsed.port}"
                parsed = parsed._replace(netloc=netloc)
            return urlunparse(parsed)
        except Exception:
            return "<masked>"
