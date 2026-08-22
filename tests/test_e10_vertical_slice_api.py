from __future__ import annotations

import sqlite3
import json
import os
import sys
import tempfile
import threading
import time
import types
from queue import Queue
from pathlib import Path

import pytest

from hermeneia.narrative.provider_registry import (
    ModelCatalog,
    ModelCatalogEntry,
    ProviderDefinition,
    ProviderRegistration,
    ProviderRegistry,
)
from hermeneia.narrative.artist_providers import (
    AnthropicArtistProvider,
    GeminiArtistProvider,
    OpenAIArtistProvider,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.credentials import CredentialStoreError, KeyringCredentialStore, default_credential_store

from test_constitutional_p0 import _seed_full_chain


class _FakeOllamaClient:
    models: list[str] = []
    error: Exception | None = None
    pull_error: Exception | None = None
    pull_calls: list[dict] = []
    pull_events: list[dict] = []
    pull_block_event: threading.Event | None = None
    pull_fail_after_block: Exception | None = None
    hosts: list[str | None] = []

    def __init__(self, host: str | None = None) -> None:
        self.host = host
        self.__class__.hosts.append(host)

    def list(self):
        if self.__class__.error:
            raise self.__class__.error
        return {"models": [{"model": model} for model in self.__class__.models]}

    def pull(self, model: str, stream: bool = True):
        self.__class__.pull_calls.append({"model": model, "stream": stream, "host": self.host})
        if self.__class__.pull_error:
            raise self.__class__.pull_error
        for event in self.__class__.pull_events or [
            {"status": "pulling manifest"},
            {"status": "pulling layers", "completed": 1, "total": 2},
            {"status": "success"},
        ]:
            yield event
            if self.__class__.pull_block_event is not None:
                self.__class__.pull_block_event.wait(timeout=2)
                if self.__class__.pull_fail_after_block is not None:
                    raise self.__class__.pull_fail_after_block
                self.__class__.pull_block_event = None
        if model not in self.__class__.models:
            self.__class__.models.append(model)


class _CapturingProvider:
    calls: list[dict] = []
    render_prompts: list[str] = []
    render_responses: list[str] = []
    fail_on_render_calls: set[int] = set()

    def __init__(self, model: str | None = None, **kwargs) -> None:
        self.model = model
        self.kwargs = kwargs
        self.__class__.calls.append({"model": model, "kwargs": kwargs})

    @property
    def provider_name(self) -> str:
        return f"ollama/{self.model}"

    def render(self, prompt: str) -> str:
        self.__class__.render_prompts.append(prompt)
        call_number = len(self.__class__.render_prompts)
        if call_number in self.__class__.fail_on_render_calls:
            raise RuntimeError("simulated local model failure")
        if "ONLY valid JSON" in prompt:
            return '{"bucket":"symbol_and_imagery","confidence":"high","rationale":"test"}'
        if self.__class__.render_responses:
            return self.__class__.render_responses.pop(0)
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


class _CatalogProvider(_CapturingProvider):
    catalogs: dict[str, list[str]] = {}
    catalog_availability: dict[str, dict[str, str]] = {}
    catalog_errors: dict[str, Exception] = {}
    catalog_calls: list[dict] = []
    reject_constructor_models: set[str] = set()

    def __init__(self, provider_id: str = "openai", model: str | None = None, **kwargs) -> None:
        if model in self.__class__.reject_constructor_models:
            raise ValueError(f"model rejected during construction: {model}")
        self.provider_id = provider_id
        super().__init__(model=model, **kwargs)

    @property
    def provider_name(self) -> str:
        return f"{self.provider_id}/{self.model}"

    def execution_config(self) -> dict:
        return {
            "provider": self.provider_id,
            "model_id": self.model,
            "sdk_version": "test",
            "request_schema_version": "1",
        }

    def model_catalog(self) -> ModelCatalog:
        self.__class__.catalog_calls.append({
            "provider_id": self.provider_id,
            "model": self.model,
            "kwargs": self.kwargs,
        })
        error = self.__class__.catalog_errors.get(self.provider_id)
        if error:
            raise error
        return ModelCatalog(
            provider_id=self.provider_id,
            catalog_source="provider_api",
            status="available",
            models=tuple(
                ModelCatalogEntry(
                    model_id=model,
                    provider_id=self.provider_id,
                    display_label=model,
                    family="claude" if model.startswith("claude-") else "gpt" if model.startswith("gpt-") else None,
                    availability=self.__class__.catalog_availability.get(
                        self.provider_id,
                        {},
                    ).get(model, "known_unverified"),
                    catalog_source="provider_api",
                    capabilities=("text",),
                )
                for model in self.__class__.catalogs.get(self.provider_id, [])
            ),
        )


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
    _FakeOllamaClient.pull_error = None
    _FakeOllamaClient.pull_calls = []
    _FakeOllamaClient.pull_events = []
    _FakeOllamaClient.pull_block_event = None
    _FakeOllamaClient.pull_fail_after_block = None
    _FakeOllamaClient.hosts = []
    _CapturingProvider.calls = []
    _CapturingProvider.render_prompts = []
    _CapturingProvider.render_responses = []
    _CapturingProvider.fail_on_render_calls = set()
    monkeypatch.setitem(
        sys.modules,
        "ollama",
        types.SimpleNamespace(Client=_FakeOllamaClient),
    )
    monkeypatch.setattr(
        "hermeneia.narrative.provider_registry.ProviderDefinition.adapter_available",
        lambda self: True if self.id.startswith("ollama-") else self.sdk_module is None,
    )


def _wait_for_ollama_install(client, job_id: str, *, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/e10/ollama/install/{job_id}")
        assert response.status_code == 200
        last = response.get_json()
        if last["status"] in {"succeeded", "failed"}:
            return last
        time.sleep(0.02)
    raise AssertionError(f"Ollama install job did not finish: {last}")


def _wait_for_ollama_event(client, job_id: str, status: str, *, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/e10/ollama/install/{job_id}")
        assert response.status_code == 200
        last = response.get_json()
        if any(event.get("status") == status for event in last.get("events", [])):
            return last
        time.sleep(0.02)
    raise AssertionError(f"Ollama install job did not report {status!r}: {last}")


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


def _cloud_catalog_registry() -> ProviderRegistry:
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
                lambda **kwargs: _CatalogProvider(provider_id="openai", **kwargs),
            ),
            ProviderRegistration(
                ProviderDefinition(
                    id="anthropic",
                    display_name="Anthropic",
                    provider_type="artist",
                    enabled=True,
                    capabilities=("text",),
                    local_or_remote="remote",
                    required_environment="ANTHROPIC_API_KEY",
                    default_model="claude-sonnet-4-6",
                ),
                lambda **kwargs: _CatalogProvider(provider_id="anthropic", **kwargs),
            ),
        ),
    )


def _reset_catalog_provider() -> None:
    _CatalogProvider.catalogs = {
        "openai": ["gpt-4o", "gpt-4.1"],
        "anthropic": ["claude-sonnet-4-6", "claude-opus-4-1"],
    }
    _CatalogProvider.catalog_availability = {
        "openai": {"gpt-4o": "available", "gpt-4.1": "available"},
        "anthropic": {
            "claude-sonnet-4-6": "available",
            "claude-opus-4-1": "available",
        },
    }
    _CatalogProvider.catalog_errors = {}
    _CatalogProvider.catalog_calls = []
    _CatalogProvider.reject_constructor_models = set()
    _CatalogProvider.calls = []


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


def test_e10_ollama_install_missing_selected_model_refreshes_catalog_without_investigation_mutation(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "schema": "hermeneia.connections_settings.v1",
        "version": 1,
        "providers": {"ollama-local": {"selected_model": "llama3.2:3b"}},
    }))
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    db_path = tmp_path / "e10.db"
    store = SQLiteStore(db_path)
    _seed_full_chain(store)
    store.close()
    conn = sqlite3.connect(db_path)
    before = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("source_documents", "source_extractions", "observations")
    }
    conn.close()
    client = create_app(db_path=db_path, provider_registry=_ollama_registry()).test_client()

    missing = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )
    assert missing["selected_model"] == "llama3.2:3b"
    assert missing["selected_model_installed"] is False

    started = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    assert started.status_code == 202
    completed = _wait_for_ollama_install(client, started.get_json()["job_id"])

    assert completed["status"] == "succeeded"
    assert _FakeOllamaClient.pull_calls == [
        {"model": "llama3.2:3b", "stream": True, "host": "http://localhost:11434"}
    ]
    local = completed["provider"]
    assert local["selected_model"] == "llama3.2:3b"
    assert local["selected_model_source"] == "user_config"
    assert local["selected_model_installed"] is True
    assert "llama3.2:3b" in local["installed_models"]
    assert any(event["status"] == "pulling manifest" for event in completed["events"])

    conn = sqlite3.connect(db_path)
    after = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("source_documents", "source_extractions", "observations")
    }
    conn.close()
    assert after == before


def test_e10_ollama_install_one_model_does_not_silently_select_it(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    started = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    assert started.status_code == 202
    completed = _wait_for_ollama_install(client, started.get_json()["job_id"])

    assert completed["status"] == "succeeded"
    local = completed["provider"]
    assert local["selected_model"] == "qwen3:4b"
    assert local["selected_model_installed"] is True
    assert "llama3.2:3b" in local["installed_models"]


def test_e10_ollama_install_progress_is_visible_before_completion(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    block = threading.Event()
    _FakeOllamaClient.pull_events = [
        {"status": "pulling manifest"},
        {"status": "success"},
    ]
    _FakeOllamaClient.pull_block_event = block
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    started = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    assert started.status_code == 202
    job_id = started.get_json()["job_id"]

    running = _wait_for_ollama_event(client, job_id, "pulling manifest")

    assert running["status"] == "running"
    assert any(event["status"] == "pulling manifest" for event in running["events"])
    assert _FakeOllamaClient.pull_calls == [
        {"model": "llama3.2:3b", "stream": True, "host": "http://localhost:11434"}
    ]

    block.set()
    completed = _wait_for_ollama_install(client, job_id)

    assert completed["status"] == "succeeded"
    assert "llama3.2:3b" in completed["provider"]["installed_models"]


def test_e10_ollama_install_preserves_partial_progress_on_later_failure(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    block = threading.Event()
    _FakeOllamaClient.pull_events = [{"status": "pulling manifest"}]
    _FakeOllamaClient.pull_block_event = block
    _FakeOllamaClient.pull_fail_after_block = RuntimeError("network lost token=sk-hidden")
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    started = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    job_id = started.get_json()["job_id"]
    running = _wait_for_ollama_event(client, job_id, "pulling manifest")
    assert running["status"] == "running"

    block.set()
    failed = _wait_for_ollama_install(client, job_id)
    body = json.dumps(failed)

    assert failed["status"] == "failed"
    assert any(event["status"] == "pulling manifest" for event in failed["events"])
    assert any(event["status"] == "failed" for event in failed["events"])
    assert "sk-hidden" not in body
    assert "token=" not in body
    assert "llama3.2:3b" not in failed["provider"]["installed_models"]


def test_e10_ollama_install_suppresses_duplicate_active_host_model_pull(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    block = threading.Event()
    _FakeOllamaClient.pull_events = [
        {"status": "pulling manifest"},
        {"status": "success"},
    ]
    _FakeOllamaClient.pull_block_event = block
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    first = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    job_id = first.get_json()["job_id"]
    _wait_for_ollama_event(client, job_id, "pulling manifest")
    duplicate = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )

    assert duplicate.status_code == 202
    assert duplicate.get_json()["job_id"] == job_id
    assert duplicate.get_json()["duplicate_suppressed"] is True
    assert len(_FakeOllamaClient.pull_calls) == 1

    block.set()
    completed = _wait_for_ollama_install(client, job_id)
    assert completed["status"] == "succeeded"
    already = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    assert already.status_code == 200
    assert already.get_json()["status"] == "already_installed"


def test_e10_ollama_install_reservation_is_atomic_for_concurrent_same_model_requests(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    block = threading.Event()
    _FakeOllamaClient.pull_events = [
        {"status": "pulling manifest"},
        {"status": "success"},
    ]
    _FakeOllamaClient.pull_block_event = block
    app = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    )
    barrier = threading.Barrier(3)
    results: Queue[tuple[int, dict]] = Queue()

    def post_install() -> None:
        with app.test_client() as client:
            barrier.wait(timeout=2)
            response = client.post(
                "/api/e10/ollama/install",
                json={"participant": "local", "model": "llama3.2:3b"},
            )
            results.put((response.status_code, response.get_json()))

    threads = [threading.Thread(target=post_install) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=2)
    for thread in threads:
        thread.join(timeout=2)

    responses = [results.get(timeout=1) for _ in range(2)]
    assert [status for status, _ in responses] == [202, 202]
    job_ids = {body["job_id"] for _, body in responses}
    assert len(job_ids) == 1
    assert len(_FakeOllamaClient.pull_calls) == 1
    assert any(body.get("duplicate_suppressed") is True for _, body in responses)

    job_id = next(iter(job_ids))
    running = _wait_for_ollama_event(app.test_client(), job_id, "pulling manifest")
    assert running["status"] == "running"
    block.set()
    completed = _wait_for_ollama_install(app.test_client(), job_id)
    assert completed["status"] == "succeeded"


def test_e10_ollama_install_same_host_different_models_create_separate_jobs(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    _FakeOllamaClient.pull_events = [{"status": "success"}]
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    first = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    second = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "mistral:7b"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.get_json()["job_id"] != second.get_json()["job_id"]
    assert _wait_for_ollama_install(client, first.get_json()["job_id"])["status"] == "succeeded"
    assert _wait_for_ollama_install(client, second.get_json()["job_id"])["status"] == "succeeded"
    assert sorted(call["model"] for call in _FakeOllamaClient.pull_calls) == [
        "llama3.2:3b",
        "mistral:7b",
    ]


def test_e10_ollama_install_releases_duplicate_guard_after_failure(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    block = threading.Event()
    _FakeOllamaClient.pull_events = [{"status": "pulling manifest"}]
    _FakeOllamaClient.pull_block_event = block
    _FakeOllamaClient.pull_fail_after_block = RuntimeError("interrupted")
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    first = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    job_id = first.get_json()["job_id"]
    _wait_for_ollama_event(client, job_id, "pulling manifest")
    duplicate = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    assert duplicate.get_json()["job_id"] == job_id
    block.set()
    assert _wait_for_ollama_install(client, job_id)["status"] == "failed"

    _FakeOllamaClient.pull_fail_after_block = None
    _FakeOllamaClient.pull_block_event = None
    retried = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    assert retried.status_code == 202
    assert retried.get_json()["job_id"] != job_id
    assert len(_FakeOllamaClient.pull_calls) == 2


def test_e10_ollama_install_job_and_event_retention_are_bounded(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    _FakeOllamaClient.pull_events = [
        {"status": f"layer-{idx}", "completed": idx, "total": 120}
        for idx in range(120)
    ]
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    first = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "retention0:1b"},
    )
    first_job_id = first.get_json()["job_id"]
    first_done = _wait_for_ollama_install(client, first_job_id)
    assert first_done["status"] == "succeeded"
    assert len(first_done["events"]) == 80
    assert first_done["events"][-1]["status"] == "success"
    assert first_done["events"][0]["status"] != "queued"

    _FakeOllamaClient.pull_events = [{"status": "success"}]
    for idx in range(1, 23):
        response = client.post(
            "/api/e10/ollama/install",
            json={"participant": "local", "model": f"retention{idx}:1b"},
        )
        assert response.status_code == 202
        assert _wait_for_ollama_install(client, response.get_json()["job_id"])["status"] == "succeeded"

    assert client.get(f"/api/e10/ollama/install/{first_job_id}").status_code == 404


def test_e10_ollama_install_rejects_unsafe_model_identities_without_pull(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    for model in ["bad model", "llama;rm -rf", "../secret", "http://host/model", "model:bad:tag"]:
        rejected = client.post("/api/e10/ollama/install", json={"participant": "local", "model": model})
        assert rejected.status_code == 400, model
        assert rejected.get_json()["configuration_valid"] is False

    assert _FakeOllamaClient.pull_calls == []


def test_e10_ollama_install_failure_is_clean_and_preserves_selection(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-should-not-leak")
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    _FakeOllamaClient.pull_error = RuntimeError("disk full token=sk-secret-should-not-leak")
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    started = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "llama3.2:3b"},
    )
    assert started.status_code == 202
    failed = _wait_for_ollama_install(client, started.get_json()["job_id"])
    body = json.dumps(failed)

    assert failed["status"] == "failed"
    assert "sk-secret-should-not-leak" not in body
    assert "token=" not in body
    local = failed["provider"]
    assert local["selected_model"] == "qwen3:4b"
    assert "llama3.2:3b" not in local["installed_models"]


def test_e10_ollama_install_offline_runtime_is_actionable_and_no_pull_occurs(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, [], error=ConnectionError("offline token=sk-hidden"))
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    response = client.post(
        "/api/e10/ollama/install",
        json={"participant": "local", "model": "qwen3:4b"},
    )

    assert response.status_code == 409
    body = json.dumps(response.get_json())
    assert "runtime is not reachable" in response.get_json()["error"]
    assert response.get_json()["ollama_host"] == "http://localhost:11434"
    assert response.get_json()["runtime_status"] == "offline"
    assert "sk-hidden" not in body
    assert "token=" not in body
    assert _FakeOllamaClient.pull_calls == []


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


def test_e10_cloud_catalog_discovery_uses_credentials_and_reports_provenance(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "catalog-openai-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "catalog-anthropic-secret")
    _reset_catalog_provider()
    client = create_app(
        db_path=tmp_path / "workspace-a" / "a.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    payload = client.get("/api/e10/providers").get_json()
    providers = {row["participant"]: row for row in payload["providers"]}
    gpt = providers["gpt"]
    claude = providers["claude"]

    assert gpt["model_catalog_source"] == "provider_api"
    assert gpt["model_catalog_status"] == "available"
    assert gpt["available_models"] == ["gpt-4.1", "gpt-4o"]
    assert gpt["selected_model"] == "gpt-4o"
    assert gpt["selected_model_available"] is True
    assert claude["available_models"] == ["claude-opus-4-1", "claude-sonnet-4-6"]
    assert any(
        call["provider_id"] == "openai"
        and call["kwargs"]["api_key"] == "catalog-openai-secret"
        for call in _CatalogProvider.catalog_calls
    )
    assert "catalog-openai-secret" not in json.dumps(payload)
    assert "catalog-anthropic-secret" not in json.dumps(payload)
    assert not settings_path.exists()


def test_e10_cloud_catalog_failure_preserves_selection_without_secret_disclosure(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "catalog-openai-secret")
    _reset_catalog_provider()
    _CatalogProvider.catalog_errors = {
        "openai": RuntimeError("provider returned catalog-openai-secret in metadata"),
    }
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    payload = client.get("/api/e10/providers").get_json()
    gpt = next(row for row in payload["providers"] if row["participant"] == "gpt")

    assert gpt["configured"] is True
    assert gpt["selected_model"] == "gpt-4o"
    assert gpt["model_catalog_status"] == "unavailable"
    assert gpt["model_catalog_source"] == "unavailable"
    assert "Check provider credentials and connectivity" in gpt["model_catalog_error"]
    assert "catalog-openai-secret" not in json.dumps(payload)


def test_e10_openai_adapter_normalizes_provider_api_model_catalog(monkeypatch):
    class _FakeModels:
        def list(self):
            return types.SimpleNamespace(data=[
                types.SimpleNamespace(id="gpt-4o"),
                types.SimpleNamespace(id="o3-mini"),
                types.SimpleNamespace(id="text-embedding-3-large"),
            ])

    class _FakeOpenAI:
        def __init__(self, api_key):
            self.models = _FakeModels()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_FakeOpenAI))

    catalog = OpenAIArtistProvider(api_key="secret-openai-key").model_catalog()

    assert catalog.catalog_source == "provider_api"
    assert [entry.model_id for entry in catalog.models] == ["gpt-4o", "o3-mini"]
    assert {entry.catalog_source for entry in catalog.models} == {"provider_api"}
    assert {entry.availability for entry in catalog.models} == {"known_unverified"}
    assert {entry.capabilities for entry in catalog.models} == {()}


def test_e10_anthropic_adapter_normalizes_provider_api_model_catalog(monkeypatch):
    class _FakeModels:
        def list(self, limit=100):
            assert limit == 100
            return [
                types.SimpleNamespace(id="claude-sonnet-4-6", display_name="Claude Sonnet 4.6", created_at="2026-01-01"),
                types.SimpleNamespace(id="embedding-model", display_name="Embedding", created_at=None),
            ]

    class _FakeAnthropic:
        def __init__(self, api_key):
            self.models = _FakeModels()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_FakeAnthropic))

    catalog = AnthropicArtistProvider(api_key="secret-anthropic-key").model_catalog()

    assert catalog.catalog_source == "provider_api"
    assert [entry.model_id for entry in catalog.models] == ["claude-sonnet-4-6"]
    assert catalog.models[0].display_label == "Claude Sonnet 4.6"
    assert catalog.models[0].snapshot is None
    assert catalog.models[0].availability == "known_unverified"
    assert catalog.models[0].capabilities == ()


def test_e10_gemini_adapter_preserves_unknown_capability_metadata(monkeypatch):
    class _FakeModels:
        def list(self):
            return [
                types.SimpleNamespace(
                    name="models/gemini-2.0-flash",
                    display_name="Gemini 2 Flash",
                    supported_actions=["generateContent"],
                ),
                types.SimpleNamespace(
                    name="models/gemini-unknown",
                    display_name="Gemini Unknown",
                    supported_actions=[],
                ),
            ]

        def generate_content(self, model, contents):
            return types.SimpleNamespace(text="ok")

    class _FakeClient:
        def __init__(self, api_key):
            self.models = _FakeModels()

    fake_google = types.SimpleNamespace(genai=types.SimpleNamespace(Client=_FakeClient))
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_google.genai)

    catalog = GeminiArtistProvider(api_key="secret-gemini-key").model_catalog()

    entries = {entry.model_id: entry for entry in catalog.models}
    assert entries["gemini-2.0-flash"].availability == "available"
    assert entries["gemini-2.0-flash"].capabilities == ("generateContent",)
    assert entries["gemini-unknown"].availability == "known_unverified"
    assert entries["gemini-unknown"].capabilities == ()


def test_e10_cloud_model_selection_persists_across_restart_and_workspaces(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "environment-anthropic-key")
    _reset_catalog_provider()
    first = create_app(
        db_path=tmp_path / "workspace-a" / "a.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    selected = first.put("/api/e10/providers/gpt/model", json={"model": "gpt-4.1"})
    tested = first.post("/api/e10/providers/gpt/test", json={})

    assert selected.status_code == 200
    assert selected.get_json()["selected_model"] == "gpt-4.1"
    assert selected.get_json()["selected_model_source"] == "user_config"
    assert tested.status_code == 200
    assert _CatalogProvider.calls[-1]["model"] == "gpt-4.1"
    settings = json.loads(settings_path.read_text())
    assert settings["providers"]["openai"]["selected_model"] == "gpt-4.1"
    assert "environment-openai-key" not in settings_path.read_text()

    second = create_app(
        db_path=tmp_path / "workspace-b" / "b.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()
    providers = {row["participant"]: row for row in second.get("/api/e10/providers").get_json()["providers"]}

    assert providers["gpt"]["selected_model"] == "gpt-4.1"
    assert providers["gpt"]["selected_model_source"] == "user_config"
    assert providers["claude"]["selected_model"] == "claude-sonnet-4-6"
    assert providers["claude"]["selected_model_source"] == "default"
    assert not (tmp_path / "workspace-a" / "calibration.json").exists()
    assert not (tmp_path / "workspace-b" / "calibration.json").exists()


def test_e10_cloud_model_missing_from_catalog_does_not_silently_fallback(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    _reset_catalog_provider()
    first = create_app(
        db_path=tmp_path / "missing-a.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()
    assert first.put("/api/e10/providers/gpt/model", json={"model": "gpt-4.1"}).status_code == 200
    _CatalogProvider.catalogs["openai"] = ["gpt-4o"]
    _CatalogProvider.calls = []
    second = create_app(
        db_path=tmp_path / "missing-b.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    status = second.get("/api/e10/providers").get_json()["providers"]
    gpt = next(row for row in status if row["participant"] == "gpt")
    tested = second.post("/api/e10/providers/gpt/test", json={})

    assert gpt["selected_model"] == "gpt-4.1"
    assert gpt["selected_model_source"] == "user_config"
    assert gpt["selected_model_available"] is False
    assert gpt["available_models"] == ["gpt-4o"]
    assert gpt["status"] == "not_connected"
    assert tested.status_code == 200
    assert _CatalogProvider.calls[-1]["model"] == "gpt-4.1"


def test_e10_cloud_catalog_discovery_ignores_stale_selected_constructor_model(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "schema": "hermeneia.connections_settings.v1",
        "version": 1,
        "providers": {"openai": {"selected_model": "retired-model"}},
    }))
    _reset_catalog_provider()
    _CatalogProvider.catalogs["openai"] = ["gpt-4o", "gpt-4.1"]
    _CatalogProvider.reject_constructor_models = {"retired-model"}
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    payload = client.get("/api/e10/providers").get_json()
    gpt = next(row for row in payload["providers"] if row["participant"] == "gpt")

    assert gpt["selected_model"] == "retired-model"
    assert gpt["selected_model_available"] is False
    assert gpt["available_models"] == ["gpt-4.1", "gpt-4o"]
    assert gpt["model_catalog_status"] == "available"
    assert any(
        call["provider_id"] == "openai" and call["model"] is None
        for call in _CatalogProvider.catalog_calls
    )


def test_e10_cloud_model_explicit_switch_a_b_a_and_provider_isolation(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "environment-anthropic-key")
    _reset_catalog_provider()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    assert client.put("/api/e10/providers/gpt/model", json={"model": "gpt-4.1"}).status_code == 200
    assert client.put("/api/e10/providers/gpt/model", json={"model": "gpt-4o"}).status_code == 200
    assert client.put("/api/e10/providers/gpt/model", json={"model": "gpt-4.1"}).status_code == 200

    providers = {row["participant"]: row for row in client.get("/api/e10/providers").get_json()["providers"]}
    settings = json.loads(settings_path.read_text())

    assert providers["gpt"]["selected_model"] == "gpt-4.1"
    assert providers["gpt"]["role_suitability"]["Explorer"] == "untested"
    assert "No static Hermeneia suitability" in providers["gpt"]["setup"]["about"]
    assert providers["claude"]["selected_model"] == "claude-sonnet-4-6"
    assert settings["providers"]["openai"]["selected_model"] == "gpt-4.1"
    assert "anthropic" not in settings["providers"] or "selected_model" not in settings["providers"]["anthropic"]


def test_e10_cloud_catalog_preserves_known_unverified_availability(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    _reset_catalog_provider()
    _CatalogProvider.catalogs["openai"] = ["gpt-verified", "gpt-unverified"]
    _CatalogProvider.catalog_availability = {
        "openai": {
            "gpt-verified": "available",
            "gpt-unverified": "known_unverified",
        }
    }
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    first = client.put("/api/e10/providers/gpt/model", json={"model": "gpt-unverified"})
    unverified = next(
        row for row in client.get("/api/e10/providers").get_json()["providers"]
        if row["participant"] == "gpt"
    )

    assert first.status_code == 200
    assert unverified["known_models"] == ["gpt-unverified", "gpt-verified"]
    assert unverified["available_models"] == ["gpt-verified"]
    assert unverified["selected_model"] == "gpt-unverified"
    assert unverified["selected_model_availability"] == "known_unverified"
    assert unverified["selected_model_available"] is False
    assert unverified["status"] == "configured"
    assert "known from provider discovery" in unverified["message"]
    assert "not present" not in unverified["message"]
    option = next(
        model for model in unverified["model_catalog"]["models"]
        if model["model_id"] == "gpt-unverified"
    )
    assert option["availability"] == "known_unverified"

    second = client.put("/api/e10/providers/gpt/model", json={"model": "gpt-verified"})
    verified = next(
        row for row in client.get("/api/e10/providers").get_json()["providers"]
        if row["participant"] == "gpt"
    )

    assert second.status_code == 200
    assert verified["selected_model"] == "gpt-verified"
    assert verified["selected_model_availability"] == "available"
    assert verified["selected_model_available"] is True


def test_e10_cloud_calibration_isolated_by_selected_model(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    _reset_catalog_provider()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()

    assert client.put("/api/e10/providers/gpt/model", json={"model": "gpt-4o"}).status_code == 200
    first = client.post("/api/e10/providers/gpt/calibrate/Explorer", json={})
    first_cal = client.get("/api/e10/calibration").get_json()["calibration"]["gpt"]
    assert first.status_code == 201
    assert first.get_json()["model_id"] == "gpt-4o"
    assert first_cal["calibration_identity"] == "gpt::openai::gpt-4o"
    assert len(first_cal["calibration_tests"]) == 1

    assert client.put("/api/e10/providers/gpt/model", json={"model": "gpt-4.1"}).status_code == 200
    second_cal = client.get("/api/e10/calibration").get_json()["calibration"]["gpt"]
    assert second_cal["calibration_identity"] == "gpt::openai::gpt-4.1"
    assert second_cal["calibration_tests"] == []

    assert client.put("/api/e10/providers/gpt/model", json={"model": "gpt-4o"}).status_code == 200
    restored = client.get("/api/e10/calibration").get_json()["calibration"]["gpt"]
    assert restored["calibration_identity"] == "gpt::openai::gpt-4o"
    assert len(restored["calibration_tests"]) == 1


def test_e10_blueprint_extraction_ignores_legacy_request_model_override(
    tmp_path,
    monkeypatch,
):
    settings_path = tmp_path / "user-config" / "connections.json"
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    _reset_catalog_provider()
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_cloud_catalog_registry(),
    ).test_client()
    assert client.put("/api/e10/providers/gpt/model", json={"model": "gpt-4.1"}).status_code == 200
    calls: list[dict] = []

    def _fake_get_provider(name, **kwargs):
        calls.append({"name": name, "kwargs": kwargs})
        return object()

    monkeypatch.setattr(
        "hermeneia.narrative.artist_providers.get_provider",
        _fake_get_provider,
    )

    response = client.post("/api/pipeline/extract-blueprint", json={
        "text": "A detailed analysis of the topic at hand.",
        "provider": "openai",
        "model": "legacy-payload-model",
    })

    assert response.status_code == 200
    assert calls[-1]["kwargs"]["model"] == "gpt-4.1"
    assert calls[-1]["kwargs"]["api_key"] == "environment-openai-key"
    assert calls[-1]["kwargs"]["model"] != "legacy-payload-model"


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
    assert "model_catalog" in index_html
    assert "e10SelectProviderModel" in index_html
    assert "e10SelectOllamaModel" in index_html
    assert "e10SaveOllamaHost" in index_html
    assert "/api/e10/ollama/host" in index_html
    assert "/api/e10/ollama/install" in index_html
    assert "e10InstallOllamaModel" in index_html
    assert "e10PollOllamaInstall" in index_html
    assert "_e10OllamaInstallJobs" in index_html
    assert "Install ${x(selectedModel)}" in index_html
    assert "Use Install model" in index_html
    assert "activeInstallForSelected" in index_html
    assert "!activeInstallForSelected" in index_html
    assert "ollama_host_source" in index_html
    assert "user setting" in index_html
    assert "/api/e10/providers/${encodeURIComponent(participant)}/model" in index_html
    assert '(unavailable)</option>' in index_html
    assert 'selected disabled>${x(selectedModel)} (unavailable)' in index_html
    assert "compatibility unverified" in index_html
    assert "await e10LoadProviders();" in index_html
    assert "perf && !perf.suppressed && perf.calls > 0" in index_html


def _canonical_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "source_documents",
                "source_extractions",
                "observations",
                "interpretations",
                "narrative_blueprints",
                "architect_plans",
                "rendered_narratives",
            )
        }
    finally:
        conn.close()


def _reader_selection_scope(text: str = "Only this selected passage participates.") -> dict:
    return {
        "primary": {
            "kind": "reader_selection",
            "text": text,
            "source_document_id": "doc-selected",
            "page": 3,
            "locator": "reader-span:v1:%7B%22page%22%3A3%7D",
            "source_locators": ["page:3:block:1"],
            "extraction_ids": ["ex-selected"],
        },
        "included": {"governing_question": False},
    }


def test_perspective_run_requires_explicit_scope_question_and_local_model(tmp_path, monkeypatch):
    _install_fake_ollama(monkeypatch, ["qwen2.5:0.5b"])
    client = create_app(
        db_path=tmp_path / "perspective.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    missing_scope = client.post(
        "/api/perspective/run",
        json={
            "perspective_id": "close-reader",
            "question": "What matters?",
            "model": "qwen2.5:0.5b",
        },
    )
    missing_question = client.post(
        "/api/perspective/run",
        json={
            "perspective_id": "close-reader",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )
    missing_model = client.post(
        "/api/perspective/run",
        json={
            "perspective_id": "close-reader",
            "question": "What matters?",
            "scope": _reader_selection_scope(),
        },
    )

    assert missing_scope.status_code == 400
    assert "selected Reader text" in missing_scope.get_json()["error"]
    assert missing_question.status_code == 400
    assert "question is required" in missing_question.get_json()["error"]
    assert missing_model.status_code == 400
    assert "model is required" in missing_model.get_json()["error"]


def test_perspective_run_uses_selected_reader_text_and_exact_local_execution_identity(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-key-that-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-anthropic-key-that-must-not-be-used")
    _install_fake_ollama(monkeypatch, ["qwen3:4b", "qwen2.5:0.5b"])
    _CapturingProvider.calls = []
    _CapturingProvider.render_prompts = []
    db_path = tmp_path / "perspective.db"
    store = SQLiteStore(db_path)
    _seed_full_chain(store)
    store.close()
    before = _canonical_counts(db_path)

    client = create_app(db_path=db_path, provider_registry=_ollama_registry()).test_client()
    response = client.post(
        "/api/perspective/run",
        json={
            "perspective_id": "close-reader",
            "question": "What tension in this passage deserves more attention?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope("Selected passage text with punctuation — and Unicode."),
            "governing_question": "Ambient thesis must not enter this selected-passage Scope.",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["operation"] == "perspective_run"
    assert body["canonical_status"] == "not_persisted"
    assert body["perspective"]["id"] == "close-reader"
    assert body["perspective"]["version"] == "1"
    assert body["execution"]["provider_id"] == "ollama-local"
    assert body["execution"]["provider"] == "ollama"
    assert body["execution"]["model_id"] == "qwen2.5:0.5b"
    assert body["execution"]["selection_source"] == "per_run"
    assert body["scope_receipt"]["primary"]["text"] == "Selected passage text with punctuation — and Unicode."
    assert body["scope_receipt"]["primary"]["source_metadata_origin"] == "reader_client"
    assert body["scope_receipt"]["included"]["governing_question"] is False
    assert "governing_question_text" not in body["scope_receipt"]
    assert body["scope_receipt"]["excluded"]["entire_corpus"] is True
    assert body["response"] == "Selected model response anchored in the observation."
    assert _CapturingProvider.calls[-1]["model"] == "qwen2.5:0.5b"
    prompt = _CapturingProvider.render_prompts[-1]
    assert "Selected passage text with punctuation — and Unicode." in prompt
    assert "Ambient thesis must not enter this selected-passage Scope." not in prompt
    assert "entire corpus" not in prompt.lower()
    assert _canonical_counts(db_path) == before


def test_perspective_run_per_run_model_does_not_change_connection_selected_model(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b", "qwen2.5:0.5b"])
    client = create_app(
        db_path=tmp_path / "perspective.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    selected = client.put("/api/e10/providers/local/model", json={"model": "qwen3:4b"})
    assert selected.status_code == 200

    run = client.post(
        "/api/perspective/run",
        json={
            "perspective_id": "close-reader",
            "question": "What changes if another local model reads this?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )
    assert run.status_code == 201
    assert run.get_json()["perspective"]["id"] == "close-reader"
    assert run.get_json()["execution"]["model_id"] == "qwen2.5:0.5b"

    providers = client.get("/api/e10/providers").get_json()["providers"]
    local = next(row for row in providers if row["participant"] == "local")
    assert local["selected_model"] == "qwen3:4b"
    assert local["selected_model_source"] == "user_config"


def test_perspective_run_missing_or_offline_local_model_fails_without_fallback(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    _CapturingProvider.calls = []
    client = create_app(
        db_path=tmp_path / "perspective.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    missing = client.post(
        "/api/perspective/run",
        json={
            "perspective_id": "close-reader",
            "question": "What matters?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )
    assert missing.status_code == 409
    assert "not installed" in missing.get_json()["error"]
    assert "Connections" in missing.get_json()["error"]
    assert missing.get_json()["provider_id"] == "ollama-local"
    assert _CapturingProvider.calls == []

    _install_fake_ollama(monkeypatch, [], error=ConnectionError("offline"))
    offline = client.post(
        "/api/perspective/run",
        json={
            "perspective_id": "close-reader",
            "question": "What matters?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )
    assert offline.status_code == 409
    assert offline.get_json()["runtime_status"] == "offline"
    assert offline.get_json()["provider_id"] == "ollama-local"


def test_perspective_room_requires_explicit_scope_question_and_local_model(tmp_path, monkeypatch):
    _install_fake_ollama(monkeypatch, ["qwen2.5:0.5b"])
    client = create_app(
        db_path=tmp_path / "perspective.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    missing_scope = client.post(
        "/api/perspective/room",
        json={
            "question": "What matters?",
            "model": "qwen2.5:0.5b",
        },
    )
    missing_question = client.post(
        "/api/perspective/room",
        json={
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )
    missing_model = client.post(
        "/api/perspective/room",
        json={
            "question": "What matters?",
            "scope": _reader_selection_scope(),
        },
    )

    assert missing_scope.status_code == 400
    assert "selected Reader text" in missing_scope.get_json()["error"]
    assert missing_question.status_code == 400
    assert "question is required" in missing_question.get_json()["error"]
    assert missing_model.status_code == 400
    assert "model is required" in missing_model.get_json()["error"]


def test_perspective_room_sequences_three_perspectives_with_one_scope_question_and_model(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-key-that-must-not-be-used")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-anthropic-key-that-must-not-be-used")
    _install_fake_ollama(monkeypatch, ["qwen3:4b", "qwen2.5:0.5b"])
    _CapturingProvider.render_responses = [
        "Close reading A.",
        "Contextual reading B.",
        "Skeptical reading C.",
    ]
    db_path = tmp_path / "perspective-room.db"
    store = SQLiteStore(db_path)
    _seed_full_chain(store)
    store.close()
    before = _canonical_counts(db_path)
    client = create_app(db_path=db_path, provider_registry=_ollama_registry()).test_client()
    selected = client.put("/api/e10/providers/local/model", json={"model": "qwen3:4b"})
    assert selected.status_code == 200

    response = client.post(
        "/api/perspective/room",
        json={
            "question": "What is this passage asking us to notice?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope("Room source text only."),
            "governing_question": "Ambient thesis must not enter the Room.",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["operation"] == "perspective_room"
    assert body["canonical_status"] == "not_persisted"
    assert body["status"] == "succeeded"
    assert body["question"] == "What is this passage asking us to notice?"
    assert body["model"]["provider_id"] == "ollama-local"
    assert body["model"]["model_id"] == "qwen2.5:0.5b"
    assert body["model"]["selection_source"] == "per_run"
    assert body["scope_receipt"]["primary"]["text"] == "Room source text only."
    assert body["scope_receipt"]["included"]["governing_question"] is False
    assert "governing_question_text" not in body["scope_receipt"]
    assert [row["perspective"]["id"] for row in body["participants"]] == [
        "close-reader",
        "contextual-reader",
        "skeptical-reader",
    ]
    assert [row["prior_participant_ids"] for row in body["participants"]] == [
        [],
        ["close-reader"],
        ["close-reader", "contextual-reader"],
    ]
    assert [row["response"] for row in body["participants"]] == [
        "Close reading A.",
        "Contextual reading B.",
        "Skeptical reading C.",
    ]
    assert all(row["execution"]["model_id"] == "qwen2.5:0.5b" for row in body["participants"])
    assert all(row["execution"]["provider_id"] == "ollama-local" for row in body["participants"])
    assert all(row["canonical_status"] == "not_persisted" for row in body["participants"])
    assert len(_CapturingProvider.calls) == 3
    assert {call["model"] for call in _CapturingProvider.calls} == {"qwen2.5:0.5b"}
    first_prompt, second_prompt, third_prompt = _CapturingProvider.render_prompts
    assert "Prior Proposed Readings" not in first_prompt
    assert "Close reading A." in second_prompt
    assert "Close reading A." in third_prompt
    assert "Contextual reading B." in third_prompt
    assert "non-canonical model-generated deliberation material" in second_prompt
    assert "not source evidence" in second_prompt
    assert "Ambient thesis must not enter the Room." not in "\n".join(_CapturingProvider.render_prompts)
    assert "Room source text only." in first_prompt
    assert "Room source text only." in second_prompt
    assert "Room source text only." in third_prompt
    assert "Close reading A." not in str(body["scope_receipt"])
    assert _canonical_counts(db_path) == before

    providers = client.get("/api/e10/providers").get_json()["providers"]
    local = next(row for row in providers if row["participant"] == "local")
    assert local["selected_model"] == "qwen3:4b"


def test_perspective_room_missing_or_offline_local_model_fails_before_execution(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    client = create_app(
        db_path=tmp_path / "perspective-room.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    missing = client.post(
        "/api/perspective/room",
        json={
            "question": "What matters?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )
    assert missing.status_code == 409
    assert "not installed" in missing.get_json()["error"]
    assert _CapturingProvider.calls == []

    _install_fake_ollama(monkeypatch, [], error=ConnectionError("offline"))
    offline = client.post(
        "/api/perspective/room",
        json={
            "question": "What matters?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )
    assert offline.status_code == 409
    assert offline.get_json()["runtime_status"] == "offline"
    assert _CapturingProvider.calls == []


def test_perspective_room_mid_failure_preserves_prior_and_marks_later_not_run(
    tmp_path,
    monkeypatch,
):
    _install_fake_ollama(monkeypatch, ["qwen2.5:0.5b"])
    _CapturingProvider.render_responses = ["Close reading A."]
    _CapturingProvider.fail_on_render_calls = {2}
    client = create_app(
        db_path=tmp_path / "perspective-room.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    response = client.post(
        "/api/perspective/room",
        json={
            "question": "What stops the sequence?",
            "model": "qwen2.5:0.5b",
            "scope": _reader_selection_scope(),
        },
    )

    assert response.status_code == 502
    body = response.get_json()
    assert body["operation"] == "perspective_room"
    assert body["status"] == "failed"
    participants = body["participants"]
    assert [row["status"] for row in participants] == ["succeeded", "failed", "not_run"]
    assert participants[0]["response"] == "Close reading A."
    assert participants[1]["prior_participant_ids"] == ["close-reader"]
    assert participants[1]["perspective"]["id"] == "contextual-reader"
    assert "failed" in participants[1]["error"]
    assert participants[2]["prior_participant_ids"] == ["close-reader"]
    assert "response" not in participants[2]
    assert len(_CapturingProvider.render_prompts) == 2
    assert _CapturingProvider.render_prompts[1].count("Close reading A.") == 1


def test_perspective_run_ui_separates_scope_perspective_question_and_model():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()
    perspective_js = index_html.split("// ── Perspective Run", 1)[1].split("// ── Thesis", 1)[0]

    assert "cr-bottom-tab-perspective" not in index_html
    assert "cr-perspective-run" in index_html
    assert "Perspective Run" in index_html
    assert "Scope" in index_html
    assert "Perspective" in index_html
    assert "Question" in index_html
    assert "Model" in index_html
    assert "/api/perspective/definitions" in index_html
    assert "/api/perspective/run" in index_html
    assert "_crPerspectiveFromSelection" in index_html
    assert "_crGetReaderSelection({ refresh: false, fallback: true })" in index_html
    assert "_crOpenBottomWorkstation('perspective')" in index_html
    assert "onclick=\"_crPerspectiveFromSelection()\"" in index_html
    assert 'placeholder="What tension in this passage deserves more attention?"' in index_html
    assert "q.value = 'What tension in this passage is easiest to overlook?'" not in perspective_js
    assert "governing_question: invLoad()?.thesis" not in perspective_js
    assert "governing_question: false" in perspective_js
    assert "Local Ollama only · no cloud fallback" in index_html
    assert "Not in interpretation record" in index_html


def test_perspective_room_ui_is_contextual_without_permanent_tab():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()
    perspective_js = index_html.split("// ── Perspective Run", 1)[1].split("// ── Thesis", 1)[0]

    assert "cr-bottom-tab-perspective" not in index_html
    assert "Ask the Room" in index_html
    assert "cr-perspective-mode-room" in index_html
    assert '<div id="cr-perspective-room-plan" hidden' in index_html
    assert "1 Close Reader" not in index_html
    assert "2 Contextual Reader" not in index_html
    assert "3 Skeptical Reader" not in index_html
    assert "_crPerspectiveRoomDefinitions = defs.default_room || []" in perspective_js
    assert "function _crRenderPerspectiveRoomPlan()" in perspective_js
    assert "_crPerspectiveRoomDefinitions.map((p, idx)" in perspective_js
    assert "/api/perspective/room" in perspective_js
    assert "Final answer" not in perspective_js
    assert "Consensus" not in perspective_js
    assert "q.value = 'What tension" not in perspective_js


def test_perspective_room_ui_renders_participant_status_truthfully():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()
    perspective_js = index_html.split("function _crRenderPerspectiveRoom(", 1)[1].split("async function _crRunPerspective", 1)[0]

    assert "status === 'succeeded'" in perspective_js
    assert "Proposed reading · not in interpretation record" in perspective_js
    assert "status === 'failed'" in perspective_js
    assert "Execution failed · no proposed reading" in perspective_js
    assert "status === 'not_run'" in perspective_js
    assert "Not run because an earlier Perspective failed." in perspective_js
    assert "Not executed · no proposed reading" in perspective_js
    assert "Planned model:" in perspective_js
    assert "row.execution?.provider_id || receipt.model?.provider_id" not in perspective_js
    assert "row.execution?.model_id || receipt.model?.model_id" not in perspective_js
