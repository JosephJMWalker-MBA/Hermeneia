from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

from hermeneia.narrative.artist_providers import (
    ArtistProvider,
    DEFAULT_PROVIDER_REGISTRY,
    get_provider,
)
from hermeneia.narrative.provider_registry import (
    ProviderDefinition,
    ProviderRegistry,
)
from hermeneia.storage.hashing import (
    make_architect_plan_id,
    make_observation_id,
    make_rendered_narrative_id,
    sha256_file,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_constitutional_p0 import _seed_full_chain


_KEY_ENVIRONMENT = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "XAI_API_KEY",
)


class _MetaTestArtist:
    """Test-only BYOP adapter; no network or provider assertions."""

    @property
    def provider_name(self) -> str:
        return "meta/test-model"

    def render(self, prompt: str) -> str:
        return prompt

    def test_connection(self) -> None:
        return None

    def execution_config(self) -> dict:
        return {
            "provider": "meta",
            "model_id": "test-model",
            "sdk_version": "test",
            "request_schema_version": "1",
            "constitutional_profile": {},
        }


def _clean_provider_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _KEY_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)


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


def _meta_registry() -> ProviderRegistry:
    return DEFAULT_PROVIDER_REGISTRY.with_provider(
        ProviderDefinition(
            id="meta",
            display_name="Meta",
            provider_type="artist",
            enabled=True,
            capabilities=("text",),
            local_or_remote="remote",
            required_environment=None,
            sdk_module=None,
        ),
        _MetaTestArtist,
    )


def test_provider_registry_is_immutable_and_extensible_by_composition():
    extended = _meta_registry()

    assert "meta" not in DEFAULT_PROVIDER_REGISTRY.ids()
    assert "meta" in extended.ids()
    assert extended is not DEFAULT_PROVIDER_REGISTRY
    assert isinstance(get_provider("meta", registry=extended), ArtistProvider)

    with pytest.raises(ValueError, match="already registered"):
        extended.with_provider(extended.definition("meta"), _MetaTestArtist)


def test_default_registry_exposes_local_ollama_artists_without_provider_authority():
    meta = DEFAULT_PROVIDER_REGISTRY.definition("ollama-meta")
    local = DEFAULT_PROVIDER_REGISTRY.definition("ollama-local")

    assert meta.provider_type == "artist"
    assert meta.local_or_remote == "local"
    assert meta.default_model == "llama3.2:3b"
    assert local.provider_type == "artist"
    assert local.local_or_remote == "local"
    assert local.default_model == "qwen3:4b"


def test_ecology_api_returns_descriptive_metadata_without_rank_or_secrets(
    tmp_path,
    monkeypatch,
):
    _clean_provider_environment(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "never-return-this-secret")
    client = create_app(
        db_path=tmp_path / "missing.db",
        provider_registry=_meta_registry(),
    ).test_client()

    response = client.get("/api/ecology")

    assert response.status_code == 200
    ecology = response.get_json()
    providers = {provider["id"]: provider for provider in ecology["providers"]}
    assert providers["meta"]["capabilities"] == ["text"]
    assert providers["meta"]["provider_type"] == "artist"
    assert providers["openai"]["configured"] is True
    assert "meta" in ecology["available_artists"]

    serialized = json.dumps(ecology)
    assert "never-return-this-secret" not in serialized
    assert '"api_key"' not in serialized.lower()
    assert "rank" not in serialized.lower()
    assert "quality" not in serialized.lower()
    assert "phenotype" not in serialized.lower()
    assert "lineage" not in serialized.lower()
    assert "provenance" not in serialized.lower()
    assert "authority" not in serialized.lower()


def test_ecology_endpoint_is_read_only(tmp_path, monkeypatch):
    _clean_provider_environment(monkeypatch)
    db_path = tmp_path / "ecology.db"
    store = SQLiteStore(db_path)
    _seed_full_chain(store)
    store.close()
    client = create_app(
        db_path=db_path,
        provider_registry=_meta_registry(),
    ).test_client()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    response = client.get("/api/ecology")

    assert response.status_code == 200
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_removing_provider_leaves_canonical_ontology_and_history_unchanged(tmp_path):
    db_path = tmp_path / "history.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    reduced = DEFAULT_PROVIDER_REGISTRY.without("null")
    assert "null" not in reduced.ids()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    narrative = conn.execute(
        "SELECT provider, execution_config FROM rendered_narratives WHERE id = ?",
        (ids["narrative_id"],),
    ).fetchone()
    plan = conn.execute(
        "SELECT id, blueprint_id FROM architect_plans WHERE id = ?",
        (ids["plan_id"],),
    ).fetchone()
    conn.close()

    assert narrative["provider"] == "null"
    assert json.loads(narrative["execution_config"])["provider"] == "null"
    assert plan["id"] == make_architect_plan_id(plan["blueprint_id"])
    assert sha256_file(db_path) == before_hash
    assert _table_counts(db_path) == before_counts


def test_provider_identity_is_excluded_from_evidence_and_architect_identity():
    observation_parameters = inspect.signature(make_observation_id).parameters
    architect_parameters = inspect.signature(make_architect_plan_id).parameters

    assert "provider" not in observation_parameters
    assert "model" not in observation_parameters
    assert "provider" not in architect_parameters
    assert "model" not in architect_parameters

    source_hash = "a" * 64
    locator = "page:1:block:1:sentence:1"
    raw_text = "Evidence remains fixed."
    assert (
        make_observation_id(source_hash, locator, raw_text)
        == make_observation_id(source_hash, locator, raw_text)
    )
    assert make_architect_plan_id("b" * 64) == make_architect_plan_id("b" * 64)


def test_provider_and_model_identity_remain_in_rendered_narrative_identity():
    plan_id = "p" * 64
    profile_id = "e" * 64

    first = make_rendered_narrative_id(
        plan_id,
        "meta/model-a",
        profile_id,
    )
    second = make_rendered_narrative_id(
        plan_id,
        "meta/model-b",
        profile_id,
    )

    assert first != second


def test_registry_projection_is_reconstructible(monkeypatch):
    _clean_provider_environment(monkeypatch)
    first = _meta_registry().ecology()
    second = _meta_registry().ecology()

    assert first == second
