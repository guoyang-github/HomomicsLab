"""Tests for graph backends."""

import pytest

from homomics_lab.context.graph.factory import get_graph_backend, reset_graph_backend
from homomics_lab.context.graph.networkx import NetworkXBackend


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_graph_backend()
    yield
    reset_graph_backend()


@pytest.mark.asyncio
async def test_networkx_add_and_neighbors(tmp_path, monkeypatch):
    from homomics_lab.config import settings

    monkeypatch.setattr(settings, "graph_backend", "networkx")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    backend = get_graph_backend(settings)
    assert isinstance(backend, NetworkXBackend)

    await backend.add_node("skill_qc", ["Skill"], properties={"name": "QC"})
    await backend.add_node("skill_filter", ["Skill"], properties={"name": "Filter"})
    await backend.add_edge("skill_qc", "skill_filter", "FOLLOWED_BY", {"confidence": 0.9})

    neighbors = await backend.get_neighbors("skill_qc", edge_types=["FOLLOWED_BY"])
    assert len(neighbors) == 1
    assert neighbors[0].id == "skill_filter"

    edges = await backend.get_edges("skill_qc", edge_type="FOLLOWED_BY")
    assert len(edges) == 1
    assert edges[0].properties["confidence"] == 0.9
