"""Encrypted secrets manager for HomomicsLab.

Stores sensitive credentials (LLM API keys, cloud credentials, container registry
tokens) in a SQLite database with Fernet encryption at rest. The master key can
be supplied via ``HOMOMICS_SECRETS_MASTER_KEY`` or derived from a passphrase.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from homomics_lab.config import settings

logger = logging.getLogger(__name__)


try:
    from cryptography.fernet import Fernet
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover
    _CRYPTO_AVAILABLE = False


class SecretsError(Exception):
    """Base exception for secrets manager errors."""


class SecretNotFound(SecretsError):
    """Raised when a requested secret does not exist."""


class CryptoUnavailable(SecretsError):
    """Raised when encryption is requested but cryptography is not installed."""


def _derive_key(master_key: str) -> bytes:
    """Derive a Fernet-compatible key from a user-supplied master key."""
    digest = hashlib.sha256(master_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@dataclass
class Secret:
    """A stored secret with metadata."""

    key: str
    value: str
    namespace: str
    description: Optional[str]
    created_at: str
    updated_at: str


class SecretsManager:
    """Encrypted secrets manager backed by SQLite.

    Args:
        db_path: Path to the SQLite secrets database. Defaults to
            ``<data_dir>/secrets.db``.
        master_key: Encryption key. If not provided, reads
            ``HOMOMICS_SECRETS_MASTER_KEY`` from the environment/settings.
        plaintext_fallback: If True and cryptography is unavailable, store
            secrets as plaintext and log a warning. This is dangerous and should
            only be used for local development.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        master_key: Optional[str] = None,
        plaintext_fallback: bool = False,
    ):
        self.db_path = db_path or (settings.data_dir / "secrets.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._plaintext = plaintext_fallback

        key = master_key or settings.secrets_master_key
        if key:
            if not _CRYPTO_AVAILABLE:
                raise CryptoUnavailable(
                    "cryptography is required for encrypted secrets storage"
                )
            self._fernet = Fernet(_derive_key(key))
        else:
            self._fernet = None
            if not self._plaintext:
                logger.warning(
                    "No secrets master key configured. Secrets will be stored as "
                    "plaintext. Set HOMOMICS_SECRETS_MASTER_KEY to enable encryption."
                )
                self._plaintext = True

        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS secrets (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
                """
            )
            conn.commit()

    def _encrypt(self, value: str) -> str:
        if self._fernet is not None:
            return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        return value

    def _decrypt(self, value: str) -> str:
        if self._fernet is not None:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        return value

    def set(
        self,
        key: str,
        value: str,
        namespace: str = "default",
        description: Optional[str] = None,
    ) -> None:
        """Store or update a secret."""
        now = datetime.now(timezone.utc).isoformat()
        encrypted = self._encrypt(value)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO secrets (namespace, key, value, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value=excluded.value,
                    description=excluded.description,
                    updated_at=excluded.updated_at
                """,
                (namespace, key, encrypted, description, now, now),
            )
            conn.commit()

    def get(self, key: str, namespace: str = "default", default: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret by key and namespace."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM secrets WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
        if row is None:
            return default
        return self._decrypt(row[0])

    def get_required(self, key: str, namespace: str = "default") -> str:
        """Retrieve a secret or raise SecretNotFound."""
        value = self.get(key, namespace)
        if value is None:
            raise SecretNotFound(f"Secret '{key}' not found in namespace '{namespace}'")
        return value

    def delete(self, key: str, namespace: str = "default") -> bool:
        """Delete a secret. Returns True if it existed."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "DELETE FROM secrets WHERE namespace = ? AND key = ?",
                (namespace, key),
            )
            conn.commit()
            return cur.rowcount > 0

    def list(self, namespace: Optional[str] = None) -> List[Secret]:
        """List secrets, optionally filtered by namespace."""
        query = "SELECT namespace, key, value, description, created_at, updated_at FROM secrets"
        params: tuple = ()
        if namespace:
            query += " WHERE namespace = ?"
            params = (namespace,)

        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            Secret(
                key=row[1],
                value=self._decrypt(row[2]),
                namespace=row[0],
                description=row[3],
                created_at=row[4],
                updated_at=row[5],
            )
            for row in rows
        ]

    def list_namespaces(self) -> List[str]:
        """Return all distinct namespaces."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT DISTINCT namespace FROM secrets").fetchall()
        return [row[0] for row in rows]


# Singleton accessor.
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Return the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def reset_secrets_manager() -> None:
    """Reset the singleton (mostly for tests)."""
    global _secrets_manager
    _secrets_manager = None
