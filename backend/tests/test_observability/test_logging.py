"""Tests for structured logging and correlation ids."""

import json
import logging

import pytest

from homomics_lab.logging_config import (
    CorrelationIdFilter,
    JsonFormatter,
    correlation_id_context,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
)


@pytest.fixture(autouse=True)
def _reset_correlation_id():
    set_correlation_id(None)
    yield
    set_correlation_id(None)


def test_new_correlation_id_is_uuid():
    cid = new_correlation_id()
    assert isinstance(cid, str)
    assert len(cid) == 36


def test_set_and_get_correlation_id():
    set_correlation_id("test-cid-123")
    assert get_correlation_id() == "test-cid-123"


def test_correlation_id_context():
    with correlation_id_context("ctx-123"):
        assert get_correlation_id() == "ctx-123"
    assert get_correlation_id() is None


def test_json_formatter_includes_correlation_id():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    set_correlation_id("fmt-123")
    CorrelationIdFilter().filter(record)

    formatted = formatter.format(record)
    payload = json.loads(formatted)
    assert payload["message"] == "hello world"
    assert payload["correlation_id"] == "fmt-123"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test_logger"
