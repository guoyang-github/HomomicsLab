"""Tests for the job queue / pub/sub backend factory."""

import pytest

from homomics_lab.jobs.backends import (
    MemoryPubSubBackend,
    MemoryQueueBackend,
    create_backends,
    get_pubsub_backend,
    get_queue_backend,
    reset_backends,
)
from homomics_lab.jobs.backends.redis import RedisPubSubBackend, RedisQueueBackend


@pytest.fixture(autouse=True)
def _reset_backends():
    reset_backends()
    yield
    reset_backends()


def test_factory_returns_memory_by_default():
    queue, pubsub = create_backends()
    assert isinstance(queue, MemoryQueueBackend)
    assert isinstance(pubsub, MemoryPubSubBackend)


def test_get_queue_backend_is_cached():
    q1 = get_queue_backend()
    q2 = get_queue_backend()
    assert q1 is q2


def test_get_pubsub_backend_is_cached():
    p1 = get_pubsub_backend()
    p2 = get_pubsub_backend()
    assert p1 is p2


def test_factory_returns_redis_when_configured(monkeypatch):
    monkeypatch.setattr("homomics_lab.jobs.backends.factory.settings.queue_backend", "redis")
    monkeypatch.setattr("homomics_lab.jobs.backends.factory.settings.redis_url", "redis://localhost:6379/0")
    reset_backends()

    queue, pubsub = create_backends()
    assert isinstance(queue, RedisQueueBackend)
    assert isinstance(pubsub, RedisPubSubBackend)


def test_factory_raises_on_unknown_backend(monkeypatch):
    monkeypatch.setattr("homomics_lab.jobs.backends.factory.settings.queue_backend", "unknown")
    reset_backends()

    with pytest.raises(ValueError, match="Unknown queue backend"):
        create_backends()
