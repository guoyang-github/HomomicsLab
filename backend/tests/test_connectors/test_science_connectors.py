"""Tests for the scientific database connector interface and flat tools."""

import asyncio

import pytest

from homomics_lab.connectors.base import Connector, ConnectorHit
from homomics_lab.connectors.registry import ConnectorRegistry
from homomics_lab.tools import science as science_tools


class FakeConnector(Connector):
    def __init__(self, name, hits, available=True, raises=None):
        self.name = name
        self.description = f"fake {name}"
        self._hits = hits
        self._available = available
        self._raises = raises
        self.calls = 0

    def is_available(self):
        return self._available

    async def search(self, query, limit=5):
        self.calls += 1
        if self._raises:
            raise self._raises
        return self._hits[:limit]


def _hit(title, id_="", url="", source="x"):
    return ConnectorHit(title=title, source=source, id=id_, url=url)


@pytest.fixture
def registry(monkeypatch):
    reg = ConnectorRegistry()
    monkeypatch.setattr(science_tools, "get_connector_registry", lambda: reg)
    return reg


def test_registry_register_get_list():
    reg = ConnectorRegistry()
    a = FakeConnector("alpha", [])
    reg.register(a)
    assert reg.get("alpha") is a
    assert reg.get("missing") is None
    assert reg.list_all() == [a]
    assert "alpha" in reg and len(reg) == 1


def test_available_filters_by_is_available():
    reg = ConnectorRegistry()
    on = FakeConnector("on", [], available=True)
    off = FakeConnector("off", [], available=False)
    reg.register(on)
    reg.register(off)
    assert reg.available() == [on]


def test_resolve_subset_and_unknown_names():
    reg = ConnectorRegistry()
    a = FakeConnector("alpha", [])
    b = FakeConnector("beta", [])
    reg.register(a)
    reg.register(b)
    assert reg.resolve(["beta"]) == [b]
    assert reg.resolve(["nope"]) == []
    assert reg.resolve(None) == [a, b]
    assert reg.resolve([]) == [a, b]


def test_science_list_dbs_reports_availability(registry):
    registry.register(FakeConnector("alpha", [], available=True))
    registry.register(FakeConnector("beta", [], available=False))
    out = science_tools.science_list_dbs()
    assert out["count"] == 2
    by_name = {d["name"]: d for d in out["databases"]}
    assert by_name["alpha"]["available"] is True
    assert by_name["beta"]["available"] is False


def test_science_search_merges_and_dedupes(registry):
    a = FakeConnector("alpha", [_hit("Same", id_="PMID:1"), _hit("Only A", id_="PMID:2")])
    b = FakeConnector("beta", [_hit("Same", id_="pmid:1"), _hit("Only B", url="http://b")])
    registry.register(a)
    registry.register(b)

    out = asyncio.run(science_tools.science_search("crispr", limit=10))
    assert out["count"] == 3  # PMID:1 deduped across sources (case-insensitive)
    titles = {r["title"] for r in out["results"]}
    assert titles == {"Same", "Only A", "Only B"}
    assert out["errors"] == {}
    assert a.calls == 1 and b.calls == 1


def test_science_search_respects_limit(registry):
    hits = [_hit(f"t{i}", id_=str(i)) for i in range(5)]
    registry.register(FakeConnector("alpha", hits))
    out = asyncio.run(science_tools.science_search("q", limit=2))
    assert out["count"] == 2


def test_science_search_filters_databases(registry):
    a = FakeConnector("alpha", [_hit("A", id_="1")])
    b = FakeConnector("beta", [_hit("B", id_="2")])
    registry.register(a)
    registry.register(b)
    out = asyncio.run(science_tools.science_search("q", databases=["beta"], limit=5))
    assert out["databases"] == ["beta"]
    assert [r["title"] for r in out["results"]] == ["B"]
    assert a.calls == 0 and b.calls == 1


def test_science_search_captures_per_connector_errors(registry):
    good = FakeConnector("good", [_hit("OK", id_="1")])
    bad = FakeConnector("bad", [], raises=RuntimeError("boom"))
    registry.register(good)
    registry.register(bad)
    out = asyncio.run(science_tools.science_search("q", limit=5))
    assert out["count"] == 1
    assert out["results"][0]["title"] == "OK"
    assert "bad" in out["errors"] and "boom" in out["errors"]["bad"]


def test_science_search_no_connectors_returns_error(registry):
    out = asyncio.run(science_tools.science_search("q", limit=5))
    assert out["count"] == 0
    assert "_" in out["errors"]
