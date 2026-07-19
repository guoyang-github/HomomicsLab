"""Shared fixtures for API integration tests.

These fixtures mock expensive/external dependencies (LLM calls, heavy
bootstrap) so that ``tests/test_api`` can run quickly and deterministically
without external API keys or network access.
"""

import atexit
import os
import shutil
import tempfile

# Use an isolated data directory so tests don't import the production skill store.
_test_data_dir = tempfile.mkdtemp(prefix="homomics_api_test_")
os.environ["HOMOMICS_DATA_DIR"] = _test_data_dir
os.environ["HOMOMICS_DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_data_dir}/homomics_lab.db"
os.environ["HOMOMICS_SESSION_STORE_URL"] = f"sqlite+aiosqlite:///{_test_data_dir}/sessions.db"

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# The global settings singleton and cached DB engine may already have been
# initialised by tests that ran earlier in this pytest process (pydantic
# BaseSettings does not re-read env vars once constructed). Force both to
# point at the isolated test data directory before importing the app.
from homomics_lab.config import settings as _settings  # noqa: E402
from homomics_lab.database.connection import reset_engine as _reset_engine  # noqa: E402

_settings.data_dir = __import__("pathlib").Path(_test_data_dir)
_settings.database_url = os.environ["HOMOMICS_DATABASE_URL"]
_settings.session_store_url = os.environ["HOMOMICS_SESSION_STORE_URL"]
_reset_engine()

from homomics_lab.main import app  # noqa: E402


# Clean up the isolated test data directory after the test run.
atexit.register(lambda: shutil.rmtree(_test_data_dir, ignore_errors=True))


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient to avoid full app bootstrap per test."""
    # Force the global settings singleton and cached DB engine to point at the
    # isolated test data directory. This must happen at fixture time, not only
    # at conftest import time: earlier tests in the same pytest process may
    # have polluted settings/engine after collection, and pydantic BaseSettings
    # does not re-read env vars once constructed.
    from homomics_lab.scheduler import HomomicsScheduler
    from homomics_lab.jobs import JobService

    _settings.data_dir = __import__("pathlib").Path(_test_data_dir)
    _settings.database_url = os.environ["HOMOMICS_DATABASE_URL"]
    _settings.session_store_url = os.environ["HOMOMICS_SESSION_STORE_URL"]
    _reset_engine()

    # Ensure schema exists in the isolated database — do not rely on the app
    # lifespan having run migrations against this particular engine.
    import asyncio as _asyncio

    from homomics_lab.database import Base as _Base
    from homomics_lab.database.connection import get_engine as _get_engine

    async def _create_schema() -> None:
        async with _get_engine().begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)

    _asyncio.run(_create_schema())

    async def _noop(_self) -> None:
        return None

    with (
        patch.object(HomomicsScheduler, "start", _noop),
        patch.object(HomomicsScheduler, "shutdown", _noop),
        patch.object(JobService, "start_worker", _noop),
        patch.object(JobService, "close", _noop),
    ):
        with TestClient(app) as c:
            yield c


@pytest.fixture(autouse=True)
def mock_llm_and_intent_for_api(monkeypatch):
    """Patch LLM and intent analyzer so API tests don't hit the network."""
    from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
    from homomics_lab.agent.intent.models import UserIntent
    from homomics_lab.llm_client import LLMClient

    async def fake_analyze(self, message, **kwargs):
        msg = str(message or "").lower()
        if "单细胞" in msg or "single cell" in msg or "scrna" in msg:
            return UserIntent(
                intent_type="analysis", interaction_mode="execute", domain="single-cell-transcriptomics", scope="full", original_message=message,
            )
        if "csv" in msg or "转换" in msg or "convert" in msg:
            return UserIntent(
                intent_type="file_conversion", interaction_mode="execute", target="convert_file", scope="single_step", original_message=message,
            )
        if "选择" in msg or "debate" in msg:
            return UserIntent(
                intent_type="general_help", interaction_mode="answer", target="generate_code", scope="single_step", original_message=message,
            )
        return UserIntent(
            intent_type="qa", interaction_mode="answer", target="answer_question", scope="single_step", original_message=message,
        )

    monkeypatch.setattr(CascadeIntentAnalyzer, "analyze", fake_analyze)

    def fake_is_configured(self):
        return True

    async def fake_chat_completion(*args, **kwargs):
        return "This is a mock response for API testing."

    class _FakeMessage:
        def __init__(self, content=None, tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    async def fake_chat_completion_message(*args, **kwargs):
        return _FakeMessage(content="Mock LLM message"), {
            "cost_usd": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    async def fake_chat_completion_stream(*args, **kwargs):
        yield "Mock"

    monkeypatch.setattr(LLMClient, "is_configured", fake_is_configured)
    monkeypatch.setattr(LLMClient, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(LLMClient, "chat_completion_message", fake_chat_completion_message)
    monkeypatch.setattr(LLMClient, "chat_completion_stream", fake_chat_completion_stream)
