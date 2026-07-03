"""Tests for the result loading API."""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from fastapi.testclient import TestClient

from homomics_lab.data import DataStore, ResultReference


@pytest.fixture
def data_store(tmp_path_factory):
    # The runtime DataStore is created with a project-specific directory.
    base = tmp_path_factory.mktemp("results_api")
    return DataStore(base_dir=base)


@pytest.fixture
def client_with_store(client, monkeypatch, data_store):
    """Patch the app's skill_executor.data_store to use the temp store."""
    skill_executor = client.app.state.skill_executor
    monkeypatch.setattr(skill_executor, "data_store", data_store)
    return client


def test_load_inline_result(client_with_store):
    response = client_with_store.post("/api/results/load", json={
        "inline": True,
        "data": {"answer": 42},
        "format": "json",
        "size": 13,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == {"answer": 42}


def test_load_json_file(client_with_store, data_store):
    ref = data_store.store("task_json", {"items": list(range(10))})

    response = client_with_store.post("/api/results/load", json=ref.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == {"items": list(range(10))}


def test_load_dataframe_returns_file(client_with_store, data_store):
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    ref = data_store.store("task_df", df)

    response = client_with_store.post("/api/results/load", json=ref.model_dump())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    loaded = pd.read_parquet(io.BytesIO(response.content))
    pd.testing.assert_frame_equal(loaded, df)


def test_load_anndata_returns_file(client_with_store, data_store):
    obs = pd.DataFrame(index=["c1", "c2"])
    var = pd.DataFrame(index=["g1", "g2"])
    X = np.array([[1.0, 2.0], [3.0, 4.0]])
    adata = AnnData(X=X, obs=obs, var=var)

    ref = data_store.store("task_adata", adata)
    response = client_with_store.post("/api/results/load", json=ref.model_dump())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].endswith('.h5ad"')


def test_load_missing_path_returns_404(client_with_store, data_store):
    missing_path = str(data_store.results_dir / "missing_result.json")
    response = client_with_store.post("/api/results/load", json={
        "inline": False,
        "path": missing_path,
        "format": "json",
        "size": 0,
    })
    assert response.status_code == 404


def test_load_path_escape_returns_400(client_with_store, tmp_path):
    ref = ResultReference(
        inline=False,
        path=str(tmp_path / "secret.json"),
        format="json",
        size=0,
    )
    response = client_with_store.post("/api/results/load", json=ref.model_dump())
    assert response.status_code == 400
