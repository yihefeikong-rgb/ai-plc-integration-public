"""存储安全回归：测试不得破坏知识库或泄露 API Key。"""

import json
import os

import pytest

from knowledge import engine as knowledge_engine_module
from knowledge.engine import KnowledgeEngine, KnowledgeMigrationRequiredError
from storage import app_settings


def test_dimension_mismatch_never_deletes_existing_collection(monkeypatch, tmp_path):
    """旧向量维度不兼容时，必须要求显式迁移而不是删除集合。"""

    class ExistingCollection:
        def count(self):
            return 1

        def query(self, **_kwargs):
            raise ValueError("embedding dimension mismatch")

    class FakeClient:
        def __init__(self):
            self.deleted = []

        def get_or_create_collection(self, **_kwargs):
            return ExistingCollection()

        def delete_collection(self, name):
            self.deleted.append(name)

    fake_client = FakeClient()
    monkeypatch.setattr(
        knowledge_engine_module.chromadb,
        "PersistentClient",
        lambda **_kwargs: fake_client,
    )
    monkeypatch.setattr(knowledge_engine_module, "_create_embedding_function", lambda _name: object())

    engine = KnowledgeEngine(str(tmp_path / "vector_db"), embedding_model="test")
    with pytest.raises(KnowledgeMigrationRequiredError):
        engine.initialize()

    assert fake_client.deleted == []
    assert engine._collection is None


def test_api_keys_stay_out_of_settings_json_and_save_atomically(
    monkeypatch, tmp_path, isolate_keyring
):
    """凭据只能进系统凭据库，JSON 仅保存非敏感配置。"""
    settings_file = tmp_path / "settings.json"
    replacements = []
    real_replace = app_settings.os.replace

    def record_replace(source, destination):
        replacements.append((source, destination))
        return real_replace(source, destination)

    monkeypatch.setattr(app_settings.os, "replace", record_replace)
    store = app_settings.AppSettings(str(settings_file)).initialize()
    store.update({"deepseek_api_key": "sk-sensitive-value", "default_language": "LAD"})

    persisted = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "sk-sensitive-value" not in settings_file.read_text(encoding="utf-8")
    assert persisted["deepseek_api_key"] == ""
    assert persisted["default_language"] == "LAD"
    assert store.get("deepseek_api_key") == "sk-sensitive-value"
    assert isolate_keyring[(app_settings.KEYRING_SERVICE, "settings/deepseek_api_key")] == "sk-sensitive-value"
    assert replacements
    assert all(os.path.basename(source).startswith(".settings-") for source, _ in replacements)
    assert not list(tmp_path.glob(".settings-*.tmp"))


def test_unavailable_credential_store_never_falls_back_to_plaintext(monkeypatch, tmp_path):
    """凭据库异常必须失败关闭，不能把 Key 写到 JSON。"""
    settings_file = tmp_path / "settings.json"
    store = app_settings.AppSettings(str(settings_file)).initialize()
    monkeypatch.setattr(
        app_settings.keyring,
        "set_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("keyring offline")),
    )

    with pytest.raises(app_settings.SettingsCredentialError):
        store.update({"openai_api_key": "secret-that-must-not-persist"})

    assert "secret-that-must-not-persist" not in settings_file.read_text(encoding="utf-8")
