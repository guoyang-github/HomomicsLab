"""Tests for the big-result DataStore."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData

from homomics_lab.data import DataStore, ResultReference


class Unstringifiable:
    """An object whose string representation always fails."""

    def __str__(self):
        raise RuntimeError("cannot stringify")


@pytest.fixture
def store(tmp_path):
    return DataStore(base_dir=tmp_path, inline_size_limit=100)


class TestDataStore:
    def test_small_json_inline(self, store):
        ref = store.store("task_1", {"answer": 42})
        assert isinstance(ref, ResultReference)
        assert ref.inline is True
        assert ref.format == "json"
        assert ref.data == {"answer": 42}
        assert ref.size > 0

    def test_large_json_offloaded(self, store, tmp_path):
        big = {"items": list(range(50))}
        ref = store.store("task_2", big)
        assert ref.inline is False
        assert ref.format == "json"
        assert ref.path is not None
        assert Path(ref.path).exists()
        assert ref.size > store.inline_size_limit

        loaded = store.load(ref)
        assert loaded == big

    def test_dataframe_offloaded_to_parquet(self, store):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        ref = store.store("task_3", df)
        assert ref.inline is False
        assert ref.format == "parquet"
        assert Path(ref.path).exists()

        loaded = store.load(ref)
        pd.testing.assert_frame_equal(loaded, df)

    def test_anndata_offloaded_to_h5ad(self, store):
        obs = pd.DataFrame(index=["c1", "c2"])
        var = pd.DataFrame(index=["g1", "g2"])
        X = np.array([[1.0, 2.0], [3.0, 4.0]])
        adata = AnnData(X=X, obs=obs, var=var)

        ref = store.store("task_4", adata)
        assert ref.inline is False
        assert ref.format == "h5ad"
        assert Path(ref.path).exists()

        loaded = store.load(ref)
        assert isinstance(loaded, AnnData)
        np.testing.assert_array_equal(loaded.X, X)

    def test_non_json_serializable_rejected_by_default(self, store):
        obj = {"unstable": Unstringifiable(), "value": 42}
        with pytest.raises(ValueError, match="pickle serialization is disabled"):
            store.store("task_5", obj)

    def test_large_non_json_serializable_rejected_by_default(self, store):
        obj = {"chunks": [Unstringifiable() for _ in range(1000)]}
        with pytest.raises(ValueError, match="pickle serialization is disabled"):
            store.store("task_6", obj)

    def test_non_json_serializable_uses_pickle_when_enabled(self, store, monkeypatch):
        from homomics_lab.config import settings

        monkeypatch.setattr(settings, "allow_pickle_serialization", True)
        obj = {"unstable": Unstringifiable(), "value": 42}
        ref = store.store("task_5", obj)
        assert ref.format == "pickle"
        assert ref.metadata is not None
        assert "cannot stringify" in ref.metadata.get("reason", "")

        loaded = store.load(ref)
        assert loaded["value"] == 42
        assert isinstance(loaded["unstable"], Unstringifiable)

    def test_large_non_json_serializable_offloaded_when_enabled(self, store, monkeypatch):
        from homomics_lab.config import settings

        monkeypatch.setattr(settings, "allow_pickle_serialization", True)
        obj = {"chunks": [Unstringifiable() for _ in range(1000)]}
        ref = store.store("task_6", obj)
        assert ref.inline is False
        assert ref.format == "pickle"
        assert Path(ref.path).exists()

        loaded = store.load(ref)
        assert len(loaded["chunks"]) == 1000

    def test_load_missing_path_raises(self, store):
        ref = ResultReference(inline=False, path="/nonexistent/file.json", format="json")
        with pytest.raises(FileNotFoundError):
            store.load(ref)

    def test_load_inline_returns_data(self, store):
        ref = ResultReference(inline=True, data=[1, 2, 3], format="json", size=9)
        assert store.load(ref) == [1, 2, 3]

    def test_list_artifacts(self, store):
        store.store("a", {"x": 1})
        store.store("b", pd.DataFrame({"y": [2]}))
        artifacts = store.list_artifacts()
        assert len(artifacts) == 1  # only the DataFrame is offloaded
        assert all(str(p).endswith(".parquet") for p in artifacts)

    def test_zarr_array_offloaded(self, store):
        zarr = pytest.importorskip("zarr")
        arr = zarr.zeros(shape=(10, 20), chunks=(5, 5), dtype="float32")
        arr[:] = 1.0

        ref = store.store("task_zarr", arr)
        assert ref.inline is False
        assert ref.format == "zarr"
        assert ref.path is not None
        assert Path(ref.path).exists()
        assert Path(ref.path).is_dir()

        loaded = store.load(ref)
        assert isinstance(loaded, zarr.Array)
        assert loaded.shape == (10, 20)
        np.testing.assert_array_equal(loaded[:], arr[:])
