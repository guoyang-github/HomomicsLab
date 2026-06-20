"""Request audit logging middleware for HomomicsLab.

Records every HTTP request with method, path, user, project, status code,
and duration. Logs are written to a rotating file when
``HOMOMICS_AUDIT_LOG_ENABLED`` is true.
"""

from __future__ import annotations

import json
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Request

from homomics_lab.config import settings
from homomics_lab.logging_config import get_correlation_id


class AuditLogger:
    """Singleton audit logger with rotating file output."""

    _instance: Optional["AuditLogger"] = None
    _logger: logging.Logger
    _configured: bool

    def __new__(cls) -> "AuditLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logger = logging.getLogger("homomics_lab.audit")
            cls._instance._logger.setLevel(logging.INFO)
            cls._instance._configured = False
        return cls._instance

    def _ensure_handler(self) -> None:
        if self._configured or not settings.audit_log_enabled:
            return

        log_path = settings.audit_log_path or Path(settings.data_dir) / "logs" / "audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handler = RotatingFileHandler(
            str(log_path),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)
        self._configured = True

    def log(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: str = "anonymous",
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> None:
        if not settings.audit_log_enabled:
            return
        self._ensure_handler()

        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
            "project_id": project_id,
            "correlation_id": correlation_id,
            "client_ip": client_ip,
        }
        self._logger.info(json.dumps(record, default=str))

    def list_for_project(
        self,
        project_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Read audit log entries filtered by project_id.

        Returns the most recent ``limit`` entries for the project. If audit
        logging is disabled or the log file does not exist, an empty list is
        returned.
        """
        if not settings.audit_log_enabled:
            return []

        log_path = settings.audit_log_path or Path(settings.data_dir) / "logs" / "audit.log"
        if not log_path.exists():
            return []

        records: List[Dict[str, Any]] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("project_id") == project_id:
                records.append(record)

        return records[-limit:]


async def audit_middleware(request: Request, call_next):
    """FastAPI middleware that records request audit logs."""
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000

    user_id = getattr(request.state, "user_id", "anonymous")
    project_id = request.query_params.get("project_id") or request.path_params.get("project_id")
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )

    AuditLogger().log(
        method=request.method,
        path=str(request.url),
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        project_id=project_id,
        correlation_id=get_correlation_id(),
        client_ip=client_ip,
    )
    return response
