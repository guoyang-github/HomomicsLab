import pytest

from homomics_lab.config import settings
from homomics_lab.storage import LocalStorageBackend, StorageBackend, get_storage_backend


@pytest.fixture
def backend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "storage_backend", "local")
    return LocalStorageBackend()


def test_make_key():
    key = StorageBackend.make_key("proj_123", "uploads", "data.h5ad")
    assert key == "proj_123/uploads/data.h5ad"


def test_make_key_rejects_traversal():
    with pytest.raises(ValueError):
        StorageBackend.make_key("proj_123", "../etc", "passwd")


def test_local_put_get_delete(backend):
    key = StorageBackend.make_key("proj_abc", "results", "out.txt")
    uri = backend.put(key, b"hello world")
    assert uri.startswith("file://")
    assert backend.get(key) == b"hello world"
    assert backend.exists(key)
    backend.delete(key)
    assert not backend.exists(key)


def test_get_storage_backend_local(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "storage_backend", "local")
    b = get_storage_backend()
    assert isinstance(b, LocalStorageBackend)
