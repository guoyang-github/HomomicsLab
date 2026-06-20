"""DataStore for skill results.

Small results are kept inline (JSON-serializable dicts/lists). Large results,
pandas DataFrames, and AnnData objects are written to files under the workspace
or a configured base directory and returned as references.

Pickle serialization is disabled by default because it can execute arbitrary
code during deserialization. Enable ``HOMOMICS_ALLOW_PICKLE_SERIALIZATION``
only in fully trusted, single-user environments.
"""

import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel

from homomics_lab.config import settings


class ResultReference(BaseModel):
    """Reference to a skill result."""

    inline: bool
    data: Optional[Any] = None
    path: Optional[str] = None
    format: str = "json"
    size: int = 0
    metadata: Optional[Dict[str, Any]] = None


class DataStore:
    """Store skill results, offloading large objects to files."""

    def __init__(
        self,
        base_dir: Union[str, Path],
        inline_size_limit: int = 10 * 1024 * 1024,
    ):
        self.base_dir = Path(base_dir)
        self.results_dir = self.base_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.inline_size_limit = inline_size_limit

    def store(self, task_id: str, data: Any) -> ResultReference:
        """Persist a result. Returns an inline reference or a file reference."""
        # Detect known large object types.
        df = self._as_dataframe(data)
        adata = self._as_anndata(data)

        if df is not None:
            return self._store_dataframe(task_id, df)
        if adata is not None:
            return self._store_anndata(task_id, adata)

        # Fallback: JSON-serializable object.
        return self._store_json(task_id, data)

    def load(self, ref: ResultReference) -> Any:
        """Load a result from a reference."""
        if ref.inline:
            return ref.data
        if ref.path is None:
            raise ValueError("Reference has no path")
        path = Path(ref.path)
        if not path.exists():
            raise FileNotFoundError(f"Result artifact not found: {path}")
        if ref.format == "parquet":
            return self._read_dataframe(path)
        if ref.format == "h5ad":
            return self._read_anndata(path)
        if ref.format == "pickle":
            if not settings.allow_pickle_serialization:
                raise ValueError(
                    "Refusing to load pickle artifact: pickle deserialization is disabled. "
                    "Enable HOMOMICS_ALLOW_PICKLE_SERIALIZATION only in trusted environments."
                )
            import pickle
            with open(path, "rb") as f:
                return pickle.load(f)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _store_json(self, task_id: str, data: Any) -> ResultReference:
        try:
            raw = json.dumps(data, default=str).encode("utf-8")
        except Exception as exc:
            if settings.allow_pickle_serialization:
                return self._store_pickle(task_id, data, reason=str(exc))
            raise ValueError(
                "Result is not JSON-serializable and pickle serialization is disabled. "
                "Enable HOMOMICS_ALLOW_PICKLE_SERIALIZATION only in trusted environments."
            ) from exc

        if len(raw) <= self.inline_size_limit:
            return ResultReference(inline=True, data=data, format="json", size=len(raw))

        path = self._artifact_path(task_id, "json")
        path.write_bytes(raw)
        return ResultReference(inline=False, path=str(path), format="json", size=len(raw))

    def _store_pickle(self, task_id: str, data: Any, reason: str = "") -> ResultReference:
        import pickle
        raw = pickle.dumps(data)
        if len(raw) <= self.inline_size_limit:
            return ResultReference(
                inline=True, data=data, format="pickle", size=len(raw), metadata={"reason": reason}
            )
        path = self._artifact_path(task_id, "pkl")
        path.write_bytes(raw)
        return ResultReference(
            inline=False, path=str(path), format="pickle", size=len(raw), metadata={"reason": reason}
        )

    def _store_dataframe(self, task_id: str, df) -> ResultReference:

        path = self._artifact_path(task_id, "parquet")
        df.to_parquet(path, index=False)
        size = path.stat().st_size
        return ResultReference(inline=False, path=str(path), format="parquet", size=size)

    def _store_anndata(self, task_id: str, adata) -> ResultReference:
        path = self._artifact_path(task_id, "h5ad")
        adata.write(path)
        size = path.stat().st_size
        return ResultReference(inline=False, path=str(path), format="h5ad", size=size)

    def _artifact_path(self, task_id: str, ext: str) -> Path:
        filename = f"{task_id}_{uuid.uuid4().hex[:8]}.{ext}"
        return self.results_dir / filename

    @staticmethod
    def _as_dataframe(data: Any):
        """Return the data if it is a pandas DataFrame, else None."""
        try:
            import pandas as pd
        except ImportError:
            return None
        if isinstance(data, pd.DataFrame):
            return data
        return None

    @staticmethod
    def _as_anndata(data: Any):
        """Return the data if it is an AnnData object, else None."""
        try:
            import anndata
        except ImportError:
            return None
        if isinstance(data, anndata.AnnData):
            return data
        return None

    @staticmethod
    def _read_dataframe(path: Path):
        import pandas as pd

        return pd.read_parquet(path)

    @staticmethod
    def _read_anndata(path: Path):
        import anndata

        return anndata.read_h5ad(path)

    def list_artifacts(self) -> Dict[str, int]:
        """List stored artifact files with sizes."""
        return {
            str(p): p.stat().st_size
            for p in self.results_dir.iterdir()
            if p.is_file()
        }
