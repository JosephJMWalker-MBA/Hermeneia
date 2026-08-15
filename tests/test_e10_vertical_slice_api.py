from __future__ import annotations

import sqlite3
import json
import sys
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


def _install_fake_ollama(
    monkeypatch: pytest.MonkeyPatch,
    models: list[str],
    *,
    error: Exception | None = None,
) -> None:
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
    assert body["credential_storage"] == "server_session_or_environment"
    assert body["stores_api_keys"] is True
    assert body["persistent_api_keys"] is False
    providers = {provider["participant"]: provider for provider in body["providers"]}
    assert providers["gpt"]["credential_source"] == "OPENAI_API_KEY"
    assert providers["gpt"]["configured"] is True
    assert providers["gpt"]["default_model"] == "gpt-4o"
    assert providers["meta"]["provider_id"] == "ollama-meta"
    assert providers["local"]["provider_id"] == "ollama-local"
    assert providers["meta"]["requires_credential"] is False
    assert providers["meta"]["credential_scope"] is None
    assert providers["local"]["requires_credential"] is False
    assert providers["local"]["credential_scope"] is None

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
    _install_fake_ollama(monkeypatch, ["qwen3:4b"])
    (tmp_path / "calibration.json").write_text(json.dumps({
        "calibration_schema": "1.0",
        "records": {},
        "provider_configuration": {
            "ollama-local": {"selected_model": "missing:1b"},
        },
    }))
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    local = next(
        provider for provider in client.get("/api/e10/providers").get_json()["providers"]
        if provider["participant"] == "local"
    )

    assert local["installed_models"] == ["qwen3:4b"]
    assert local["selected_model"] == "missing:1b"
    assert local["selected_model_source"] == "user"
    assert local["selected_model_installed"] is False
    assert "qwen3:4b" not in local["message"], "Hermeneia must not imply an automatic switch"


def test_e10_ollama_model_selection_is_explicit_and_persisted(
    tmp_path,
    monkeypatch,
):
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
    assert body["selected_model_source"] == "user"
    persisted = json.loads((tmp_path / "calibration.json").read_text())
    assert persisted["provider_configuration"]["ollama-local"]["selected_model"] == "llama3.2:1b"
    assert "source_documents" not in json.dumps(persisted)


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


def test_e10_session_key_can_be_saved_and_removed_without_being_returned(tmp_path):
    client = create_app(db_path=tmp_path / "missing.db").test_client()
    secret = "session-secret-openai-key"

    saved = client.put(
        "/api/e10/providers/gpt/key",
        json={"api_key": secret},
    )
    assert saved.status_code == 200
    assert saved.get_json()["credential_scope"] == "server_session"

    status = client.get("/api/e10/providers").get_json()
    gpt = next(provider for provider in status["providers"] if provider["participant"] == "gpt")
    assert gpt["configured"] is True
    assert gpt["credential_scope"] == "server_session"
    assert secret not in json.dumps(status)

    removed = client.delete("/api/e10/providers/gpt/key")
    assert removed.status_code == 200
    assert removed.get_json()["configured"] is False


def test_e10_saved_key_reports_missing_adapter_without_implying_rejection(
    tmp_path,
    monkeypatch,
):
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
    assert "Save Key" in index_html
    assert "Remove Key" in index_html
    assert "Credential storage" in index_html
    assert "server memory" in index_html
    assert "key saved · adapter missing" in index_html
    assert "Connection to Hermeneia lost" in index_html
    assert "ollama_host" in index_html
    assert "installed_models" in index_html
    assert "selected_model" in index_html
    assert "e10SelectOllamaModel" in index_html
    assert "/api/e10/providers/${encodeURIComponent(participant)}/model" in index_html
