"""Tests for the encrypted secrets manager."""

import pytest

from homomics_lab.secrets import CryptoUnavailable, SecretNotFound, SecretsManager, reset_secrets_manager


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_secrets_manager()
    yield
    reset_secrets_manager()


class TestSecretsManagerPlaintext:
    def test_set_and_get(self, tmp_path):
        manager = SecretsManager(
            db_path=tmp_path / "secrets.db",
            plaintext_fallback=True,
        )
        manager.set("OPENAI_API_KEY", "sk-test", namespace="llm", description="test key")
        assert manager.get("OPENAI_API_KEY", namespace="llm") == "sk-test"

    def test_get_default(self, tmp_path):
        manager = SecretsManager(
            db_path=tmp_path / "secrets.db",
            plaintext_fallback=True,
        )
        assert manager.get("missing", namespace="llm", default="fallback") == "fallback"
        assert manager.get("missing", namespace="llm") is None

    def test_get_required_raises(self, tmp_path):
        manager = SecretsManager(
            db_path=tmp_path / "secrets.db",
            plaintext_fallback=True,
        )
        with pytest.raises(SecretNotFound):
            manager.get_required("missing", namespace="llm")

    def test_update_overwrites(self, tmp_path):
        manager = SecretsManager(
            db_path=tmp_path / "secrets.db",
            plaintext_fallback=True,
        )
        manager.set("key", "v1", namespace="ns")
        manager.set("key", "v2", namespace="ns")
        assert manager.get("key", namespace="ns") == "v2"

    def test_delete(self, tmp_path):
        manager = SecretsManager(
            db_path=tmp_path / "secrets.db",
            plaintext_fallback=True,
        )
        manager.set("key", "value", namespace="ns")
        assert manager.delete("key", namespace="ns") is True
        assert manager.get("key", namespace="ns") is None
        assert manager.delete("key", namespace="ns") is False

    def test_list(self, tmp_path):
        manager = SecretsManager(
            db_path=tmp_path / "secrets.db",
            plaintext_fallback=True,
        )
        manager.set("a", "1", namespace="ns1")
        manager.set("b", "2", namespace="ns1")
        manager.set("c", "3", namespace="ns2")

        ns1 = manager.list("ns1")
        assert len(ns1) == 2
        keys = {s.key for s in ns1}
        assert keys == {"a", "b"}

        all_secrets = manager.list()
        assert len(all_secrets) == 3

    def test_list_namespaces(self, tmp_path):
        manager = SecretsManager(
            db_path=tmp_path / "secrets.db",
            plaintext_fallback=True,
        )
        manager.set("x", "1", namespace="alpha")
        manager.set("y", "2", namespace="beta")
        assert set(manager.list_namespaces()) == {"alpha", "beta"}


class TestSecretsManagerEncrypted:
    def test_encrypted_storage(self, tmp_path):
        db_path = tmp_path / "secrets.db"
        manager = SecretsManager(
            db_path=db_path,
            master_key="super-secret-master-key",
        )
        manager.set("OPENAI_API_KEY", "sk-encrypted", namespace="llm")

        # Raw value in DB should not contain the secret.
        raw = db_path.read_bytes()
        assert b"sk-encrypted" not in raw

        # Decryption returns original value.
        assert manager.get("OPENAI_API_KEY", namespace="llm") == "sk-encrypted"

    def test_different_keys_cannot_decrypt(self, tmp_path):
        manager1 = SecretsManager(
            db_path=tmp_path / "secrets.db",
            master_key="key-one",
        )
        manager1.set("secret", "value", namespace="ns")

        manager2 = SecretsManager(
            db_path=tmp_path / "secrets.db",
            master_key="key-two",
        )
        with pytest.raises(Exception):
            manager2.get("secret", namespace="ns")

    def test_crypto_required_without_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "homomics_lab.secrets._CRYPTO_AVAILABLE",
            False,
            raising=False,
        )
        with pytest.raises(CryptoUnavailable):
            SecretsManager(
                db_path=tmp_path / "secrets.db",
                master_key="key",
            )
