"""Object storage abstraction for HomomicsLab.

Supports:
  - local: filesystem storage (default, dev/single-user)
  - s3: Amazon S3 or S3-compatible stores (MinIO, OSS, Wasabi, etc.)

Objects are keyed by ``project_id/object_name``. Large results and uploaded
files can be offloaded to the configured backend instead of the local disk.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

from homomics_lab.config import settings


class StorageBackend(ABC):
    """Abstract object storage backend."""

    @abstractmethod
    def put(self, key: str, data: bytes) -> str:
        """Store an object and return its URI."""
        pass

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Retrieve an object by key."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object by key."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if the object exists."""
        pass

    @abstractmethod
    def get_uri(self, key: str) -> str:
        """Return a stable URI/URL for the object."""
        pass

    @staticmethod
    def make_key(project_id: str, *parts: str) -> str:
        """Build a safe object key from project_id and path parts."""
        from homomics_lab.security import validate_project_id

        validate_project_id(project_id)
        safe_parts = []
        for p in parts:
            p = str(p).replace("//", "/").lstrip("/")
            if ".." in p or p.startswith("."):
                raise ValueError(f"Invalid storage key part: {p}")
            safe_parts.append(p)
        return f"{project_id}/" + "/".join(safe_parts)


class LocalStorageBackend(StorageBackend):
    """Filesystem-backed storage."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(settings.data_dir) / "objects"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if ".." in key or key.startswith("/"):
            raise ValueError(f"Invalid storage key: {key}")
        return self.base_dir / key

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"file://{path.resolve()}"

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def get_uri(self, key: str) -> str:
        return f"file://{self._path(key).resolve()}"


class S3StorageBackend(StorageBackend):
    """S3-compatible object storage backend."""

    def __init__(
        self,
        bucket: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "boto3 is required for S3 storage. Install it with: pip install boto3"
            ) from exc

        self.bucket = bucket or settings.storage_s3_bucket
        if not self.bucket:
            raise ValueError("S3 bucket must be configured")

        endpoint = endpoint_url or settings.storage_s3_endpoint_url
        region_name = region or settings.storage_s3_region
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region_name,
            aws_access_key_id=access_key or settings.storage_s3_access_key,
            aws_secret_access_key=secret_key or settings.storage_s3_secret_key,
        )
        self._public_url_prefix = settings.storage_s3_public_url_prefix

    def put(self, key: str, data: bytes) -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return self.get_uri(key)

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def get_uri(self, key: str) -> str:
        if self._public_url_prefix:
            return f"{self._public_url_prefix.rstrip('/')}/{key}"
        return f"s3://{self.bucket}/{key}"


# Global backend instance cache.
_storage_backend: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """Return the configured storage backend (singleton)."""
    global _storage_backend
    if _storage_backend is None:
        _storage_backend = _create_storage_backend()
    return _storage_backend


def _create_storage_backend() -> StorageBackend:
    backend = getattr(settings, "storage_backend", "local")
    if backend == "s3":
        return S3StorageBackend()
    if backend == "local":
        return LocalStorageBackend()
    raise ValueError(f"Unknown storage backend: {backend}")


def reset_storage_backend() -> None:
    global _storage_backend
    _storage_backend = None
