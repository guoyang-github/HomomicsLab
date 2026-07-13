"""Tests for the LLM model catalog."""

import json

import pytest

from homomics_lab.llm.model_catalog import ModelCatalog


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
    return ModelCatalog()


def test_default_catalog_populated(catalog):
    """The built-in default list is loaded when no file exists."""
    assert catalog.get("gpt-4o") is not None
    assert catalog.get("gpt-4o-mini") is not None
    assert catalog.get("deepseek-chat") is not None
    assert catalog.get("qwen-turbo") is not None


def test_list_enabled_excludes_disabled(catalog, tmp_path, monkeypatch):
    """Disabled models are excluded from list_enabled."""
    data = [
        {
            "id": "visible-model",
            "provider": "openai",
            "name": "Visible",
            "capabilities": ["qa"],
            "enabled": True,
        },
        {
            "id": "hidden-model",
            "provider": "openai",
            "name": "Hidden",
            "capabilities": ["qa"],
            "enabled": False,
        },
    ]
    (tmp_path / "llm_model_catalog.json").write_text(json.dumps(data))
    catalog = ModelCatalog()
    ids = {m.id for m in catalog.list_enabled()}
    assert "visible-model" in ids
    assert "hidden-model" not in ids


def test_match_returns_best_model_for_task(catalog):
    """Planning tasks prefer a strong reasoning model."""
    model_id, reason = catalog.match("planning")
    assert model_id in {"gpt-4o", "claude-3-5-sonnet-latest", "kimi-k2.5", "qwen-max"}
    assert "planning" in reason


def test_match_prefer_cheap(catalog):
    """Cheap flag prefers the cheapest matching model."""
    model_id, reason = catalog.match("qa", prefer_cheap=True)
    assert model_id in {
        "gpt-4o-mini",
        "deepseek-chat",
        "qwen-turbo",
        "glm-4-flash",
        "llama3.1",
    }
    assert "cheapest" in reason


def test_match_required_capabilities(catalog):
    """Required capabilities filter the candidate pool."""
    model_id, _ = catalog.match("custom", required_capabilities=["vision"])
    assert model_id == "gpt-4o"


def test_match_no_match_returns_none(catalog):
    """An impossible capability set returns None."""
    model_id, reason = catalog.match("custom", required_capabilities=["vision", "cheap"])
    assert model_id is None
    assert reason == ""


def test_catalog_loads_from_file(tmp_path, monkeypatch):
    """A JSON file in data_dir overrides the built-in list."""
    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)
    custom = [
        {
            "id": "custom-model",
            "provider": "custom",
            "name": "Custom",
            "capabilities": ["qa"],
            "context_window": 8192,
            "cost_per_1k_input_usd": 0.01,
            "cost_per_1k_output_usd": 0.02,
        }
    ]
    (tmp_path / "llm_model_catalog.json").write_text(json.dumps(custom))
    catalog = ModelCatalog()
    assert catalog.get("custom-model") is not None
    assert catalog.get("gpt-4o") is None
