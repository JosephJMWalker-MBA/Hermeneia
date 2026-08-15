from __future__ import annotations

import sqlite3
import json
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

from hermeneia.narrative.provider_registry import (
    ProviderDefinition,
    ProviderRegistration,
    ProviderRegistry,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.credentials import CredentialStoreError, KeyringCredentialStore, default_credential_store

from test_constitutional_p0 import _seed_full_chain


class _FakeOllamaClient:
    models: list[str] = []
    error: Exception | None = None
    hosts: list[str | None] = []

    def __init__(self, host: str | None = None) -> None:
        self.__class__.hosts.append(host)

    def list(self):
        if self.__class__.error:
            raise self.__class__.error
        return {"models": [{"model": model} for model in self.__class__.models]}


class _CapturingProvider:
    calls: list[dict] = []

    def __init__(self, model: str | None = None, **kwargs) -> None:
        self.model = model
        self.kwargs = kwargs
        self.__class__.calls.append({"model": model, "kwargs": kwargs})

    @property
    def provider_name(self) -> str:
        return f"ollama/{self.model}"

    def render(self, prompt: str) -> str:
        if "ONLY valid JSON" in prompt:
            return '{"bucket":"symbol_and_imagery","confidence":"high","rationale":"test"}'
        return "Selected model response anchored in the observation."

    def test_connection(self) -> None:
        return None

    def execution_config(self) -> dict:
        return {
            "provider": "ollama",
            "model_id": self.model,
            "sdk_version": "test",
            "request_schema_version": "1",
        }


class _FakeCredentialStore:
    def __init__(self) -> None:
        self.passwords: dict[str, str] = {}
        self.fail_set = False
        self.fail_get = False
        self.fail_delete = False

    def available(self) -> bool:
        return True

    def status(self) -> dict[str, object]:
        return {
            "available": True,
            "backend": "tests.fake",
            "message": "fake secure credential store available",
        }

    def set_password(self, provider_id: str, secret: str) -> None:
        if self.fail_set:
            raise CredentialStoreError("write failed")
        self.passwords[provider_id] = secret

    def get_password(self, provider_id: str) -> str | None:
        if self.fail_get:
            raise CredentialStoreError("read failed")
        return self.passwords.get(provider_id)

    def has_password(self, provider_id: str) -> bool:
        return self.get_password(provider_id) is not None

    def delete_password(self, provider_id: str) -> None:
        if self.fail_delete:
            raise CredentialStoreError("delete failed")
        self.passwords.pop(provider_id, None)


class _UnavailableCredentialStore:
    def available(self) -> bool:
        return False

    def status(self) -> dict[str, object]:
        return {
            "available": False,
            "backend": None,
            "message": "fake secure credential store unavailable",
        }

    def set_password(self, provider_id: str, secret: str) -> None:
        raise CredentialStoreError("unavailable")

    def get_password(self, provider_id: str) -> str | None:
        raise CredentialStoreError("unavailable")

    def has_password(self, provider_id: str) -> bool:
        raise CredentialStoreError("unavailable")

    def delete_password(self, provider_id: str) -> None:
        raise CredentialStoreError("unavailable")


def _install_fake_ollama(
    monkeypatch: pytest.MonkeyPatch,
    models: list[str],
    *,
    error: Exception | None = None,
) -> None:
    if not os.environ.get("HERMENEIA_CONNECTIONS_SETTINGS_PATH"):
        settings_dir = Path(tempfile.mkdtemp(prefix="hermeneia-connections-settings-"))
        monkeypatch.setenv(
            "HERMENEIA_CONNECTIONS_SETTINGS_PATH",
            str(settings_dir / "connections.json"),
        )
    _FakeOllamaClient.models = models
    _FakeOllamaClient.error = error
    _FakeOllamaClient.hosts = []
    monkeypatch.setitem(
        sys.modules,
        "ollama",
        types.SimpleNamespace(Client=_FakeOllamaClient),
    )
    monkeypatch.setattr(
        "hermeneia.narrative.provider_registry.ProviderDefinition.adapter_available",
        lambda self: True if self.id.startswith("ollama-") else self.sdk_module is None,
    )


def _ollama_registry() -> ProviderRegistry:
    return ProviderRegistry(
        (
            ProviderRegistration(
                ProviderDefinition(
                    id="ollama-meta",
                    display_name="Meta Llama via Ollama",
                    provider_type="artist",
                    enabled=True,
                    capabilities=("text",),
                    local_or_remote="local",
                    default_model="llama3.2:3b",
                ),
                _CapturingProvider,
            ),
            ProviderRegistration(
                ProviderDefinition(
                    id="ollama-local",
                    display_name="Local Model via Ollama",
                    provider_type="artist",
                    enabled=True,
                    capabilities=("text",),
                    local_or_remote="local",
                    default_model="qwen3:4b",
                ),
                _CapturingProvider,
            ),
        ),
    )


def _cloud_registry() -> ProviderRegistry:
    return ProviderRegistry(
        (
            ProviderRegistration(
                ProviderDefinition(
                    id="openai",
                    display_name="OpenAI",
                    provider_type="artist",
                    enabled=True,
                    capabilities=("text",),
                    local_or_remote="remote",
                    required_environment="OPENAI_API_KEY",
                    default_model="gpt-4o",
                ),
                _CapturingProvider,
            ),
        ),
    )


def _table_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    conn.close()
    return counts


def test_e10_observation_reads_are_side_effect_free(tmp_path):
    db_path = tmp_path / "e10.db"
    store = SQLiteStore(db_path)
    _seed_full_chain(store)
    store.close()
    client = create_app(db_path=db_path).test_client()

    before = _table_counts(db_path)

    response = client.get("/api/e10/observations")

    assert response.status_code == 200
    assert response.get_json()["count"] >= 1
    assert _table_counts(db_path) == before


def test_e10_generate_review_promote_and_critic_flow(tmp_path):
    db_path = tmp_path / "e10.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    client = create_app(db_path=db_path).test_client()

    generated = client.post(
        "/api/e10/interpretations/generate",
        json={"observation_id": ids["obs_id"], "participants": ["gpt", "claude"]},
    )
    assert generated.status_code == 201
    proposals = generated.get_json()["proposals"]
    assert len(proposals) == 2
    assert {proposal["status"] for proposal in proposals} == {"pending"}

    proposal_id = proposals[0]["id"]
    critic = client.post(
        "/api/e10/critic/run",
        json={
            "proposal_id": proposal_id,
            "policies": [
                "aggregate_weighting",
                "decomposition",
                "contradiction_sensitive",
                "conservative",
            ],
        },
    )
    assert critic.status_code == 201
    reports = critic.get_json()["reports"]
    assert {report["policy"] for report in reports} == {
        "aggregate_weighting",
        "decomposition",
        "contradiction_sensitive",
        "conservative",
    }
    assert all(report["claims"] for report in reports)
    assert all(report["evidence_passages"] for report in reports)

    accepted = client.post(
        f"/api/e10/proposals/{proposal_id}/accept",
        json={"comment": "Accepted for E10 vertical slice."},
    )
    assert accepted.status_code == 200
    canonical = accepted.get_json()["interpretation"]
    assert canonical["observation_id"] == ids["obs_id"]
    assert canonical["source"] == "ai-accepted"

    lineage = client.get(f"/api/lineage/interpretation/{canonical['id']}")
    assert lineage.status_code == 200
    classes = {node["class"] for node in lineage.get_json()["nodes"]}
    assert {"Interpretation", "Observation", "SourceExtraction", "SourceDocument"} <= classes


def test_e10_provider_status_is_visible_without_secret_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-return")
    client = create_app(db_path=tmp_path / "missing.db").test_client()

    response = client.get("/api/e10/providers")

    assert response.status_code == 200
    body = response.get_json()
    assert body["credential_storage"] == "session_environment_or_system_store"
    assert body["stores_api_keys"] is True
    assert isinstance(body["persistent_api_keys"], bool)
    assert "system_credential_store" in body
    providers = {provider["participant"]: provider for provider in body["providers"]}
    assert providers["gpt"]["credential_source"] == "OPENAI_API_KEY"
    assert providers["gpt"]["configured"] is True
    assert providers["gpt"]["default_model"] == "gpt-4o"
    assert providers["meta"]["provider_id"] == "ollama-meta"
    assert providers["local"]["provider_id"] == "ollama-local"
    assert providers["meta"]["requires_credential"] is False
    assert providers["meta"]["credential_scope"] == "not_required"
    assert providers["local"]["requires_credential"] is False
    assert providers["local"]["credential_scope"] == "not_required"

    serialized = json.dumps(body)
    assert "do-not-return" not in serialized
    assert '"api_key"' not in serialized.lower()


def test_e10_ollama_status_discovers_installed_models(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://jetson.local:11434")
    _install_fake_ollama(monkeypatch, ["llama3.2:3b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    body = client.get("/api/e10/providers").get_json()
    providers = {provider["participant"]: provider for provider in body["providers"]}

    assert providers["meta"]["ollama_host"] == "http://jetson.local:11434"
    assert providers["meta"]["ollama_server_running"] is True
    assert providers["meta"]["installed_models"] == ["llama3.2:3b", "qwen3:4b"]
    assert providers["meta"]["selected_model"] == "llama3.2:3b"
    assert providers["meta"]["selected_model_installed"] is True
    assert providers["local"]["selected_model"] == "qwen3:4b"
    assert providers["local"]["selected_model_installed"] is True


def test_e10_ollama_status_reports_offline_runtime(tmp_path, monkeypatch):
    _install_fake_ollama(monkeypatch, [], error=ConnectionError("offline"))
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    providers = {
        provider["participant"]: provider
        for provider in client.get("/api/e10/providers").get_json()["providers"]
    }

    assert providers["local"]["ollama_server_running"] is False
    assert providers["local"]["installed_models"] == []
    assert providers["local"]["status"] == "not_connected"
    assert "ollama serve" in providers["local"]["ollama_setup_action"]


def test_e10_ollama_missing_selected_model_does_not_silently_switch(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["missing:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()
    assert client.put("/api/e10/providers/local/model", json={"model": "missing:1b"}).status_code == 200
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])

    local = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )

    assert local["installed_models"] == ["qwen3:4b"]
    assert local["selected_model"] == "missing:1b"
    assert local["selected_model_source"] == "user_config"
    assert local["selected_model_installed"] is False
    assert "qwen3:4b" not in local["message"], "Hermeneia must not imply an automatic switch"


def test_e10_ollama_model_selection_persists_in_user_settings_not_calibration(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    db_path = tmp_path / "missing.db"
    client = create_app(
        db_path=db_path,
        provider_registry=_ollama_registry(),
    ).test_client()

    response = client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["selected_model"] == "llama3.2:1b"
    assert body["selected_model_source"] == "user_config"
    assert not (tmp_path / "calibration.json").exists()
    settings = json.loads(settings_path.read_text())
    assert settings["schema"] == "hermeneia.connections_settings.v1"
    assert settings["version"] == 1
    assert settings["providers"]["ollama-local"]["selected_model"] == "llama3.2:1b"

    restarted = create_app(
        db_path=db_path,
        provider_registry=_ollama_registry(),
    ).test_client()
    local = next(
        provider for provider in restarted.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )
    assert local["selected_model"] == "llama3.2:1b"
    assert local["selected_model_source"] == "user_config"


def test_e10_ollama_user_settings_are_independent_of_workspace_db(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    first = create_app(
        db_path=tmp_path / "workspace-a" / "a.db",
        provider_registry=_ollama_registry(),
    ).test_client()
    assert first.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200

    second = create_app(
        db_path=tmp_path / "workspace-b" / "b.db",
        provider_registry=_ollama_registry(),
    ).test_client()
    local = next(
        provider for provider in second.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )

    assert local["selected_model"] == "llama3.2:1b"
    assert local["selected_model_source"] == "user_config"
    assert not (tmp_path / "workspace-a" / "calibration.json").exists()
    assert not (tmp_path / "workspace-b" / "calibration.json").exists()


def test_e10_ollama_settings_file_excludes_secrets_corpus_and_calibration(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-do-not-write")
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    db_path = tmp_path / "e10.db"
    store = SQLiteStore(db_path)
    _seed_full_chain(store)
    store.close()
    client = create_app(
        db_path=db_path,
        provider_registry=_ollama_registry(),
    ).test_client()

    assert client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200
    assert client.put("/api/e10/ollama/host", json={"host": "http://jetson.local:11434"}).status_code == 200

    text = settings_path.read_text()
    settings = json.loads(text)
    assert settings["providers"]["ollama-local"]["credential_source"] == {"kind": "not_required"}
    assert "sk-do-not-write" not in text
    assert "api_key" not in text.lower()
    assert "The green light burned at the end of the dock" not in text
    assert "calibration_tests" not in text


def test_e10_ollama_missing_persisted_model_remains_unavailable_after_restart(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _install_fake_ollama(monkeypatch, ["missing:1b", "qwen3:4b"])
    db_path = tmp_path / "missing.db"
    client = create_app(
        db_path=db_path,
        provider_registry=_ollama_registry(),
    ).test_client()
    assert client.put("/api/e10/providers/local/model", json={"model": "missing:1b"}).status_code == 200

    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    restarted = create_app(
        db_path=db_path,
        provider_registry=_ollama_registry(),
    ).test_client()
    local = next(
        provider for provider in restarted.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )

    assert local["selected_model"] == "missing:1b"
    assert local["selected_model_source"] == "user_config"
    assert local["selected_model_installed"] is False
    assert "qwen3:4b" not in local["message"], "Hermeneia must not imply an automatic switch"


def test_e10_ollama_malformed_or_missing_settings_fall_back_to_defaults(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{not-json")
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    local = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )
    assert local["selected_model"] == "qwen3:4b"
    assert local["selected_model_source"] == "default"

    assert client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200
    repaired = json.loads(settings_path.read_text())
    assert repaired["schema"] == "hermeneia.connections_settings.v1"
    assert repaired["providers"]["ollama-local"]["selected_model"] == "llama3.2:1b"


def test_e10_ollama_host_uses_environment_user_default_precedence(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    default_meta = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )
    assert default_meta["ollama_host"] == "http://localhost:11434"
    assert default_meta["ollama_host_source"] == "default"

    saved = client.put("/api/e10/ollama/host", json={"host": "http://jetson.local:11434"})
    assert saved.status_code == 200
    restarted = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()
    user_config = next(
        provider for provider in restarted.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )
    assert user_config["ollama_host"] == "http://jetson.local:11434"
    assert user_config["ollama_host_source"] == "user_config"

    monkeypatch.setenv("OLLAMA_HOST", "http://env.local:11434")
    env_override = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()
    env_status = next(
        provider for provider in env_override.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )
    assert env_status["ollama_host"] == "http://env.local:11434"
    assert env_status["ollama_host_source"] == "environment"


def test_e10_ollama_failed_settings_write_does_not_change_live_model_or_host(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    def fail_save(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("hermeneia.web.app.save_connections_settings", fail_save)

    model_response = client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"})
    host_response = client.put("/api/e10/ollama/host", json={"host": "http://jetson.local:11434"})
    local = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )

    assert model_response.status_code == 500
    assert host_response.status_code == 500
    assert local["selected_model"] == "qwen3:4b"
    assert local["selected_model_source"] == "default"
    assert local["ollama_host"] == "http://localhost:11434"
    assert local["ollama_host_source"] == "default"
    assert not settings_path.exists()


def test_e10_ollama_host_rejects_secret_bearing_or_non_origin_urls(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    bad_hosts = [
        "http://username:password@server:11434",
        "http://server:11434?token=secret",
        "http://server:11434/#secret",
        "http://server:11434/api",
        "http:///missing-host",
        "http://bad host:11434",
        "http://-bad-host:11434",
        "http://bad_host:11434",
        "http://server:99999",
        "ftp://server:11434",
    ]
    for host in bad_hosts:
        response = client.put("/api/e10/ollama/host", json={"host": host})
        assert response.status_code == 400, host

    assert not settings_path.exists()


def test_e10_ollama_host_accepts_and_normalizes_ipv6_origin(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    response = client.put("/api/e10/ollama/host", json={"host": "http://[0:0:0:0:0:0:0:1]:11434/"})

    assert response.status_code == 200
    assert response.get_json()["configured_ollama_host"] == "http://[::1]:11434"
    settings = json.loads(settings_path.read_text())
    assert settings["ollama"]["host"] == "http://[::1]:11434"


def test_e10_ollama_unsupported_future_settings_are_not_overwritten(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    settings_path.parent.mkdir(parents=True)
    future_settings = {
        "schema": "hermeneia.connections_settings.v1",
        "version": 2,
        "future_field": {"preserve": True},
    }
    settings_path.write_text(json.dumps(future_settings, indent=2))
    original_text = settings_path.read_text()
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    model_response = client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"})
    host_response = client.put("/api/e10/ollama/host", json={"host": "http://jetson.local:11434"})
    local = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )

    assert model_response.status_code == 409
    assert host_response.status_code == 409
    assert "Unsupported Hermeneia Connections settings version" in model_response.get_json()["error"]
    assert settings_path.read_text() == original_text
    assert local["selected_model"] == "qwen3:4b"
    assert local["selected_model_source"] == "default"
    assert local["ollama_host"] == "http://localhost:11434"
    assert local["ollama_host_source"] == "default"


def test_e10_ollama_unreadable_existing_settings_blocks_writes(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "schema": "hermeneia.connections_settings.v1",
        "version": 1,
        "providers": {"ollama-local": {"selected_model": "qwen3:4b"}},
    }))
    original_text = settings_path.read_text()

    def fail_read_text(self, *args, **kwargs):
        if self == settings_path:
            raise PermissionError("permission denied: /private/path/connections.json")
        return original_read_text(self, *args, **kwargs)

    original_read_text = Path.read_text
    monkeypatch.setattr(Path, "read_text", fail_read_text)
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    model_response = client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"})
    host_response = client.put("/api/e10/ollama/host", json={"host": "http://jetson.local:11434"})
    local = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )

    assert model_response.status_code == 409
    assert host_response.status_code == 409
    assert "could not be read" in model_response.get_json()["error"]
    assert "/private/path" not in model_response.get_json()["error"]
    monkeypatch.setattr(Path, "read_text", original_read_text)
    assert settings_path.read_text() == original_text
    assert local["selected_model"] == "qwen3:4b"
    assert local["selected_model_source"] == "default"
    assert local["ollama_host"] == "http://localhost:11434"
    assert local["ollama_host_source"] == "default"


def test_e10_ollama_refuses_uninstalled_or_unverified_model_selection(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    missing = client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"})
    assert missing.status_code == 400
    assert "not installed" in missing.get_json()["error"]

    _install_fake_ollama(monkeypatch, [], error=ConnectionError("offline"))
    offline = client.put("/api/e10/providers/local/model", json={"model": "qwen3:4b"})
    assert offline.status_code == 409
    assert "cannot verify installed models" in offline.get_json()["error"]


def test_e10_ollama_selected_model_reaches_test_and_calibration_calls(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    _CapturingProvider.calls = []
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()
    assert client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200

    tested = client.post("/api/e10/providers/local/test", json={})
    calibrated = client.post("/api/e10/providers/local/calibrate/Explorer", json={})

    assert tested.status_code == 200
    assert tested.get_json()["selected_model"] == "llama3.2:1b"
    assert calibrated.status_code in {200, 201}
    assert [call["model"] for call in _CapturingProvider.calls[-2:]] == [
        "llama3.2:1b",
        "llama3.2:1b",
    ]
    stored = json.loads((tmp_path / "calibration.json").read_text())
    tests = stored["records"]["local::ollama-local::llama3.2:1b"]["calibration_tests"]
    assert tests[-1]["provider_id"] == "ollama-local"
    assert tests[-1]["model_id"] == "llama3.2:1b"


def test_e10_ollama_calibration_does_not_transfer_between_selected_models(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    assert client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200
    calibrated = client.post("/api/e10/providers/local/calibrate/Explorer", json={})
    assert calibrated.status_code in {200, 201}
    first_cal = client.get("/api/e10/calibration").get_json()["calibration"]["local"]
    assert first_cal["model_id"] == "llama3.2:1b"
    assert first_cal["role_status"]["Explorer"]["status"] == "allowed"

    assert client.put("/api/e10/providers/local/model", json={"model": "qwen3:4b"}).status_code == 200
    second_cal = client.get("/api/e10/calibration").get_json()["calibration"]["local"]
    assert second_cal["model_id"] == "qwen3:4b"
    assert second_cal["role_status"]["Explorer"]["status"] == "untested"
    assert second_cal["calibration_tests"] == []

    assert client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200
    restored = client.get("/api/e10/calibration").get_json()["calibration"]["local"]
    assert restored["model_id"] == "llama3.2:1b"
    assert restored["role_status"]["Explorer"]["status"] == "allowed"
    assert len(restored["calibration_tests"]) == 1


def test_e10_ollama_alternate_model_does_not_inherit_default_static_suitability(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    providers = {
        provider["participant"]: provider
        for provider in client.get("/api/e10/providers").get_json()["providers"]
    }
    assert providers["local"]["selected_model"] == "qwen3:4b"
    assert providers["local"]["role_suitability"]["Explorer"] == "rejected"
    assert "qwen3:4b" in json.dumps(providers["local"]["setup"])

    selected = client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"})
    assert selected.status_code == 200
    providers = {
        provider["participant"]: provider
        for provider in client.get("/api/e10/providers").get_json()["providers"]
    }
    local = providers["local"]

    assert local["selected_model"] == "llama3.2:1b"
    assert local["role_suitability"]["Explorer"] == "untested"
    assert set(local["role_suitability"].values()) == {"untested"}
    setup_text = json.dumps(local["setup"])
    assert "qwen3:4b" not in setup_text
    assert "Explorer role rejected" not in setup_text
    assert "No static Hermeneia suitability judgment" in local["setup"]["about"]


def test_e10_ollama_participant_performance_is_not_shown_as_selected_model_metrics(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    assert client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200
    calibrated = client.post("/api/e10/providers/local/calibrate/Explorer", json={})
    assert calibrated.status_code in {200, 201}
    assert client.put("/api/e10/providers/local/model", json={"model": "qwen3:4b"}).status_code == 200

    performance = client.get("/api/e10/calibration").get_json()["calibration"]["local"]["performance"]

    assert performance["suppressed"] is True
    assert performance["calls"] == 0
    assert "multi-model Ollama" in performance["message"]


def test_e10_ollama_selected_model_reaches_explorer_and_companion_execution(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["llama3.2:1b", "qwen3:4b"])
    _CapturingProvider.calls = []
    db_path = tmp_path / "e10.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    client = create_app(
        db_path=db_path,
        provider_registry=_ollama_registry(),
    ).test_client()
    assert client.put("/api/e10/providers/local/model", json={"model": "llama3.2:1b"}).status_code == 200

    generated = client.post(
        "/api/e10/interpretations/generate",
        json={"observation_id": ids["obs_id"], "participants": ["local"]},
    )
    companion = client.post(
        "/api/companion/ask",
        json={"provider": "local", "message": "What should I notice?", "context_flags": {}},
    )

    assert generated.status_code == 201, generated.get_data(as_text=True)
    proposal = generated.get_json()["proposals"][0]
    conn = sqlite3.connect(db_path)
    try:
        model_row = conn.execute(
            "SELECT generating_model FROM ai_provenance WHERE staged_object_id = ?",
            (proposal["id"],),
        ).fetchone()
    finally:
        conn.close()
    assert model_row[0] == "llama3.2:1b"
    assert companion.status_code == 200, companion.get_data(as_text=True)
    assert companion.get_json()["model"] == "llama3.2:1b"
    assert _CapturingProvider.calls[-2]["model"] == "llama3.2:1b"
    assert _CapturingProvider.calls[-1]["model"] == "llama3.2:1b"


def test_e10_session_key_can_be_saved_and_removed_without_being_returned(tmp_path, monkeypatch):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    _CapturingProvider.calls = []
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
    ).test_client()
    secret = "session-secret-openai-key"

    saved = client.put(
        "/api/e10/providers/gpt/key",
        json={"api_key": secret},
    )
    assert saved.status_code == 200
    assert saved.get_json()["credential_scope"] == "session"

    status = client.get("/api/e10/providers").get_json()
    gpt = next(provider for provider in status["providers"] if provider["participant"] == "gpt")
    assert gpt["configured"] is True
    assert gpt["credential_scope"] == "session"
    assert secret not in json.dumps(status)
    assert secret not in settings_path.read_text()

    tested = client.post("/api/e10/providers/gpt/test", json={})
    assert tested.status_code == 200
    assert _CapturingProvider.calls[-1]["kwargs"]["api_key"] == secret

    restarted = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
    ).test_client()
    restarted_gpt = next(
        provider for provider in restarted.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "gpt"
    )
    assert restarted_gpt["credential_scope"] == "session"
    assert restarted_gpt["configured"] is False

    removed = client.delete("/api/e10/providers/gpt/key")
    assert removed.status_code == 200
    assert removed.get_json()["configured"] is False


def test_e10_environment_credential_source_resolves_only_selected_environment(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    _CapturingProvider.calls = []
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
    ).test_client()

    selected = client.put("/api/e10/providers/gpt/key", json={"credential_source": "environment"})
    tested = client.post("/api/e10/providers/gpt/test", json={})

    assert selected.status_code == 200
    assert selected.get_json()["credential_scope"] == "environment"
    assert tested.status_code == 200
    assert _CapturingProvider.calls[-1]["kwargs"]["api_key"] == "environment-openai-key"
    text = settings_path.read_text()
    assert "environment-openai-key" not in text
    assert "OPENAI_API_KEY" in text


def test_e10_system_store_save_load_delete_and_workspace_independence(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    store = _FakeCredentialStore()
    _CapturingProvider.calls = []
    first = create_app(
        db_path=tmp_path / "workspace-a" / "a.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()

    saved = first.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    )

    assert saved.status_code == 200
    assert saved.get_json()["credential_scope"] == "system_store"
    settings_text = settings_path.read_text()
    assert "system-openai-secret" not in settings_text
    assert json.loads(settings_text)["providers"]["openai"]["credential_source"]["configured"] is True

    second = create_app(
        db_path=tmp_path / "workspace-b" / "b.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()
    tested = second.post("/api/e10/providers/gpt/test", json={})
    second_gpt = next(
        provider for provider in second.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "gpt"
    )
    second_status = second.get("/api/e10/providers").get_json()

    assert tested.status_code == 200
    assert second_gpt["credential_scope"] == "system_store"
    assert second_gpt["system_credential_configured"] is True
    assert _CapturingProvider.calls[-1]["kwargs"]["api_key"] == "system-openai-secret"
    assert "system-openai-secret" not in json.dumps(second_status)
    assert not (tmp_path / "workspace-a" / "calibration.json").exists()
    assert not (tmp_path / "workspace-b" / "calibration.json").exists()

    removed = second.delete("/api/e10/providers/gpt/key", json={"credential_source": "system_store"})
    assert removed.status_code == 200
    assert "openai" not in store.passwords
    assert json.loads(settings_path.read_text())["providers"]["openai"]["credential_source"]["configured"] is False


def test_e10_system_store_unavailable_and_failed_writes_do_not_change_source(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    unavailable = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=_UnavailableCredentialStore(),
    ).test_client()

    unavailable_response = unavailable.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    )
    status = unavailable.get("/api/e10/providers").get_json()
    gpt = next(provider for provider in status["providers"] if provider["participant"] == "gpt")
    assert unavailable_response.status_code == 503
    assert gpt["credential_scope"] == "environment"
    assert not settings_path.exists()

    failing_store = _FakeCredentialStore()
    failing_store.fail_set = True
    failing = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=failing_store,
    ).test_client()
    failed = failing.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    )
    assert failed.status_code == 503
    assert "openai" not in failing_store.passwords
    assert not settings_path.exists()


def test_e10_system_store_failed_delete_preserves_secret_and_metadata(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    store = _FakeCredentialStore()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()
    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    ).status_code == 200
    before = settings_path.read_text()
    store.fail_delete = True

    removed = client.delete("/api/e10/providers/gpt/key", json={"credential_source": "system_store"})

    assert removed.status_code == 500
    assert store.passwords["openai"] == "system-openai-secret"
    assert settings_path.read_text() == before


def test_e10_system_store_replacement_metadata_failure_restores_prior_secret(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    store = _FakeCredentialStore()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()
    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "old-openai-secret"},
    ).status_code == 200
    before = settings_path.read_text()

    def _fail_save(settings, path=None):
        raise OSError("disk full")

    monkeypatch.setattr("hermeneia.web.app.save_connections_settings", _fail_save)
    replaced = client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "new-openai-secret"},
    )

    assert replaced.status_code == 500
    assert store.passwords["openai"] == "old-openai-secret"
    assert settings_path.read_text() == before


def test_e10_system_store_replacement_failed_rollback_is_reported(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    store = _FakeCredentialStore()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()
    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "old-openai-secret"},
    ).status_code == 200

    def _fail_save(settings, path=None):
        raise OSError("disk full")

    original_set_password = store.set_password

    def _fail_restore(provider_id: str, secret: str) -> None:
        if secret == "old-openai-secret":
            raise CredentialStoreError("restore failed")
        original_set_password(provider_id, secret)

    monkeypatch.setattr("hermeneia.web.app.save_connections_settings", _fail_save)
    monkeypatch.setattr(store, "set_password", _fail_restore)
    replaced = client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "new-openai-secret"},
    )

    assert replaced.status_code == 500
    assert "could not restore the prior credential" in replaced.get_json()["error"]
    assert store.passwords["openai"] == "new-openai-secret"


def test_e10_system_store_delete_metadata_failure_failed_restore_is_reported(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    store = _FakeCredentialStore()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()
    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    ).status_code == 200

    def _fail_save(settings, path=None):
        raise OSError("disk full")

    monkeypatch.setattr("hermeneia.web.app.save_connections_settings", _fail_save)
    store.fail_set = True
    removed = client.delete("/api/e10/providers/gpt/key", json={"credential_source": "system_store"})

    assert removed.status_code == 500
    assert "could not restore it" in removed.get_json()["error"]
    assert "openai" not in store.passwords


def test_e10_system_store_presence_is_independent_of_selected_source(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    store = _FakeCredentialStore()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()

    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    ).status_code == 200
    assert client.put("/api/e10/providers/gpt/key", json={"credential_source": "environment"}).status_code == 200
    status = client.get("/api/e10/providers").get_json()["providers"]
    gpt = next(provider for provider in status if provider["participant"] == "gpt")
    assert gpt["credential_scope"] == "environment"
    assert gpt["system_credential_configured"] is True

    deleted = client.delete("/api/e10/providers/gpt/key", json={"credential_source": "system_store"})
    status = client.get("/api/e10/providers").get_json()["providers"]
    gpt = next(provider for provider in status if provider["participant"] == "gpt")
    assert deleted.status_code == 200
    assert gpt["credential_scope"] == "environment"
    assert gpt["configured"] is True
    assert gpt["system_credential_configured"] is False
    assert json.loads(settings_path.read_text())["providers"]["openai"]["credential_source"]["kind"] == "environment"


def test_e10_system_store_selection_can_reuse_existing_secret_without_reentering(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    store = _FakeCredentialStore()
    _CapturingProvider.calls = []
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()

    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    ).status_code == 200
    assert client.put("/api/e10/providers/gpt/key", json={"credential_source": "environment"}).status_code == 200
    selected = client.put("/api/e10/providers/gpt/key", json={"credential_source": "system_store"})
    tested = client.post("/api/e10/providers/gpt/test", json={})

    assert selected.status_code == 200
    assert tested.status_code == 200
    assert _CapturingProvider.calls[-1]["kwargs"]["api_key"] == "system-openai-secret"


def test_e10_system_store_presence_does_not_trust_stale_configured_metadata(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    store = _FakeCredentialStore()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()
    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    ).status_code == 200
    store.passwords.pop("openai")

    status = client.get("/api/e10/providers").get_json()["providers"]
    gpt = next(provider for provider in status if provider["participant"] == "gpt")

    assert gpt["credential_scope"] == "system_store"
    assert gpt["configured"] is False
    assert gpt["system_credential_configured"] is False


def test_e10_keyring_backend_errors_are_sanitized(monkeypatch):
    _FakeBackend = type(
        "Keyring",
        (),
        {"priority": 1, "__module__": "keyring.backends.SecretService"},
    )

    fake_keyring = types.SimpleNamespace()
    fake_keyring.get_keyring = lambda: _FakeBackend()

    def _raise_backend_error(*args, **kwargs):
        raise RuntimeError("raw dbus secret backend failure")

    fake_keyring.set_password = _raise_backend_error
    fake_keyring.get_password = _raise_backend_error
    fake_keyring.delete_password = _raise_backend_error

    monkeypatch.setattr("hermeneia.credentials.importlib.util.find_spec", lambda name: object())
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    store = KeyringCredentialStore()

    for action in (
        lambda: store.set_password("openai", "secret"),
        lambda: store.get_password("openai"),
        lambda: store.delete_password("openai"),
    ):
        with pytest.raises(CredentialStoreError) as exc:
            action()
        assert "raw dbus" not in str(exc.value)
        assert "secret backend failure" not in str(exc.value)


def test_e10_keyring_rejects_positive_priority_non_system_backends(monkeypatch):
    for backend in (
        type(
            "PlaintextKeyring",
            (),
            {"priority": 1, "__module__": "custom.secureish"},
        )(),
        type(
            "FileKeyring",
            (),
            {"priority": 1, "__module__": "keyring.backends.SecretService"},
        )(),
        type(
            "EncryptedKeyring",
            (),
            {"priority": 1, "__module__": "keyrings.alt.file"},
        )(),
        type(
            "Keyring",
            (),
            {"priority": 1, "__module__": "thirdparty.backend"},
        )(),
    ):
        fake_keyring = types.SimpleNamespace()
        fake_keyring.get_keyring = lambda backend=backend: backend
        monkeypatch.setattr("hermeneia.credentials.importlib.util.find_spec", lambda name: object())
        monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

        store = default_credential_store()

        assert store.available() is False


def test_e10_keyring_delete_error_is_not_success_when_secret_is_present(monkeypatch):
    _FakeBackend = type(
        "Keyring",
        (),
        {"priority": 1, "__module__": "keyring.backends.SecretService"},
    )

    class PasswordDeleteError(Exception):
        pass

    fake_keyring = types.SimpleNamespace()
    fake_keyring.get_keyring = lambda: _FakeBackend()
    fake_keyring.get_password = lambda service, account: "still-present-secret"
    fake_keyring.set_password = lambda service, account, secret: None
    fake_keyring.delete_password = lambda service, account: (_ for _ in ()).throw(
        PasswordDeleteError("backend delete failed")
    )
    monkeypatch.setattr("hermeneia.credentials.importlib.util.find_spec", lambda name: object())
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    store = KeyringCredentialStore()

    with pytest.raises(CredentialStoreError) as exc:
        store.delete_password("openai")

    assert "backend delete failed" not in str(exc.value)
    assert "System credential store delete failed." == str(exc.value)


def test_e10_default_credential_store_sanitizes_backend_initialization_error(monkeypatch):
    fake_keyring = types.SimpleNamespace()
    fake_keyring.get_keyring = lambda: (_ for _ in ()).throw(
        RuntimeError("raw keychain initialization token")
    )
    monkeypatch.setattr("hermeneia.credentials.importlib.util.find_spec", lambda name: object())
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    store = default_credential_store()
    status = store.status()

    assert status["available"] is False
    assert "raw keychain" not in str(status["message"])
    assert "token" not in str(status["message"])


def test_e10_selected_credential_source_precedence_is_exact(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    store = _FakeCredentialStore()
    _CapturingProvider.calls = []
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_registry(),
        credential_store=store,
    ).test_client()

    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "system_store", "api_key": "system-openai-secret"},
    ).status_code == 200
    assert client.post("/api/e10/providers/gpt/test", json={}).status_code == 200
    assert _CapturingProvider.calls[-1]["kwargs"]["api_key"] == "system-openai-secret"

    assert client.put("/api/e10/providers/gpt/key", json={"credential_source": "environment"}).status_code == 200
    assert client.post("/api/e10/providers/gpt/test", json={}).status_code == 200
    assert _CapturingProvider.calls[-1]["kwargs"]["api_key"] == "environment-openai-key"

    assert client.put(
        "/api/e10/providers/gpt/key",
        json={"credential_source": "session", "api_key": "session-openai-key"},
    ).status_code == 200
    assert client.post("/api/e10/providers/gpt/test", json={}).status_code == 200
    assert _CapturingProvider.calls[-1]["kwargs"]["api_key"] == "session-openai-key"
    assert "session-openai-key" not in settings_path.read_text()


def test_e10_saved_key_reports_missing_adapter_without_implying_rejection(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(tmp_path / "connections.json"))
    client = create_app(db_path=tmp_path / "missing.db").test_client()
    monkeypatch.setattr(
        "hermeneia.narrative.provider_registry.ProviderDefinition.adapter_available",
        lambda self: False if self.id == "gemini" else self.sdk_module is None,
    )

    saved = client.put(
        "/api/e10/providers/gemini/key",
        json={"api_key": "session-secret-gemini-key"},
    )
    assert saved.status_code == 200

    providers = client.get("/api/e10/providers").get_json()["providers"]
    gemini = next(row for row in providers if row["participant"] == "gemini")
    assert gemini["configured"] is True
    assert gemini["adapter_available"] is False
    assert "Credential is saved" in gemini["message"]

    tested = client.post("/api/e10/providers/gemini/test", json={})
    assert tested.status_code == 200
    assert tested.get_json()["configuration_valid"] is False
    assert "credential is saved" in tested.get_json()["message"].lower()
    assert "not installed" in tested.get_json()["message"].lower()


def test_e10_ui_exposes_provider_configuration_surface():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "Connections — Providers" in index_html or "Providers" in index_html
    assert "/api/e10/providers" in index_html
    assert "Test Connection" in index_html
    assert "Add Key" in index_html
    assert "Manage Key" in index_html
    assert "Use Session Only" in index_html
    assert "Use Environment" in index_html
    assert "Save to System Store" in index_html
    assert "Remove Session Credential" in index_html
    assert "Remove System Credential" in index_html
    assert "Credential storage" in index_html
    assert "server memory" in index_html
    assert "credential_source: 'environment'" in index_html
    assert "credentialSource = 'session'" in index_html
    assert "system_credential_store_available" in index_html
    assert "key saved · adapter missing" in index_html
    assert "Connection to Hermeneia lost" in index_html
    assert "ollama_host" in index_html
    assert "installed_models" in index_html
    assert "selected_model" in index_html
    assert "e10SelectOllamaModel" in index_html
    assert "e10SaveOllamaHost" in index_html
    assert "/api/e10/ollama/host" in index_html
    assert "ollama_host_source" in index_html
    assert "user setting" in index_html
    assert "/api/e10/providers/${encodeURIComponent(participant)}/model" in index_html
    assert '(not installed)</option>' in index_html
    assert 'selected disabled>${x(selectedModel)} (not installed)' in index_html
    assert "await e10LoadProviders();" in index_html
    assert "perf && !perf.suppressed && perf.calls > 0" in index_html
