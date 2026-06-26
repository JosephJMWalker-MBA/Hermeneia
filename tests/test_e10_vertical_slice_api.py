from __future__ import annotations

import sqlite3
import json
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_constitutional_p0 import _seed_full_chain


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

    assert "Expert — Providers" in index_html
    assert "/api/e10/providers" in index_html
    assert "Test Connection" in index_html
    assert "Add Key" in index_html
    assert "Manage Key" in index_html
    assert "Save Key" in index_html
    assert "Remove Key" in index_html
    assert "Credential storage" in index_html
    assert "server memory" in index_html
    assert "key saved · adapter missing" in index_html
    assert "Hermeneia server is unavailable" in index_html
