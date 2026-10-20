"""Truthful responses when an E10 multi-participant request partly succeeds.

Both E10 routes use independent ADR-0009 staging transactions. If a later
participant fails, earlier committed proposals must be returned to the caller,
not hidden behind an error. The source workspace is synthetic; providers are
in-process fakes and never contact a live service.
"""
from __future__ import annotations

import sqlite3

import pytest

import hermeneia.web.app as webapp
from hermeneia.compiler.staging.interpretation import StagingError
from hermeneia.explorer.interpreter import ExplorerError
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain
from test_e10_vertical_slice_api import _cloud_catalog_registry, _reset_catalog_provider
from test_explorer_discovery import _seed_discover_db


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """Prepare the same fake cloud adapters as the E10 vertical slice tests."""
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(tmp_path / "connections.json"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-anthropic")
    _reset_catalog_provider()

    db = tmp_path / "workspace.db"
    store = SQLiteStore(db)
    ids = _seed_full_chain(store)
    store.close()
    return db, ids, monkeypatch


def _request(case, db, ids):
    if case == "generate":
        observation_ids = [ids["obs_id"]]
        url = "/api/e10/interpretations/generate"
        body = {"observation_id": ids["obs_id"], "participants": ["gpt", "claude"]}
    else:
        observation_ids = [ids["obs_id"], ids["obs2_id"]]
        url = "/api/e10/interpretations/discover"
        body = {"observation_ids": observation_ids, "participants": ["gpt", "claude"]}
    client = create_app(db_path=db, provider_registry=_cloud_catalog_registry()).test_client()
    return client, client.post(url, json=body), observation_ids


def _seed_discovery(db, ids, tmp_path):
    """Use the existing real two-Observation discovery fixture."""
    # The fixture builds an independent workspace at the supplied path.
    tmp_path.mkdir(parents=True, exist_ok=True)
    path, seeded = _seed_discover_db(tmp_path)
    return path, seeded


def _rows(db, table):
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]


def _use_fake_generation(monkeypatch, case, *, fail_on):
    calls = []
    def generate(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == fail_on:
            raise ExplorerError("deliberate participant failure")
        return f"Independent candidate {len(calls)}.", "frozen synthetic prompt"
    if case == "generate":
        monkeypatch.setattr(webapp, "generate_candidate_interpretation", generate)
    else:
        monkeypatch.setattr(webapp, "generate_candidate_buckets",
                            lambda observations, provider: [[o["id"] for o in observations]])
        monkeypatch.setattr(webapp, "generate_interpretation_from_bucket", generate)
    return calls


@pytest.mark.parametrize("case", ["generate", "discover"])
def test_partial_response_returns_every_committed_proposal_id(case, setup, tmp_path):
    db, ids, monkeypatch = setup
    if case == "discover":
        db, ids = _seed_discovery(db, ids, tmp_path / "discover")
    _use_fake_generation(monkeypatch, case, fail_on=2)
    client, response, _ = _request(case, db, ids)

    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    assert data["partial"] is True
    assert data["created_count"] == 1
    assert len(data["proposals"]) == 1
    assert len(data["failures"]) == 1
    assert data["failures"][0]["participant"] == "claude"
    assert data["failures"][0]["stage"] == "generation"
    assert "deliberate participant failure" in data["failures"][0]["error"]

    stored = _rows(db, "proposed_interpretations")
    assert len(stored) == 1
    assert stored[0]["id"] == data["proposals"][0]["id"]
    assert stored[0]["status"] == "pending"
    assert len(_rows(db, "ai_provenance")) == 1
    detail = client.get(f"/api/e10/observations/{stored[0]['observation_id']}")
    assert detail.status_code == 200
    assert any(p["id"] == stored[0]["id"] for p in detail.get_json()["proposals"])


@pytest.mark.parametrize("case", ["generate", "discover"])
def test_all_failed_preserves_4xx_with_no_created_proposals(case, setup, tmp_path):
    db, ids, monkeypatch = setup
    if case == "discover":
        db, ids = _seed_discovery(db, ids, tmp_path / "discover")
    _use_fake_generation(monkeypatch, case, fail_on=1)
    # Fail on every participant, not just the first.
    if case == "generate":
        monkeypatch.setattr(webapp, "generate_candidate_interpretation",
                            lambda *args, **kwargs: (_ for _ in ()).throw(ExplorerError("all failed")))
    else:
        monkeypatch.setattr(webapp, "generate_interpretation_from_bucket",
                            lambda *args, **kwargs: (_ for _ in ()).throw(ExplorerError("all failed")))
    _, response, _ = _request(case, db, ids)

    assert response.status_code == 400, response.get_json()
    data = response.get_json()
    assert data["created_count"] == 0
    assert data["partial"] is False
    assert len(data["failures"]) == 2
    assert {f["participant"] for f in data["failures"]} == {"gpt", "claude"}
    assert not _rows(db, "proposed_interpretations")
    assert not _rows(db, "ai_provenance")


@pytest.mark.parametrize("case", ["generate", "discover"])
def test_fully_successful_response_remains_created_and_not_partial(case, setup, tmp_path):
    db, ids, monkeypatch = setup
    if case == "discover":
        db, ids = _seed_discovery(db, ids, tmp_path / "discover")
    _use_fake_generation(monkeypatch, case, fail_on=None)
    _, response, _ = _request(case, db, ids)

    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    assert data["partial"] is False
    assert data["failures"] == []
    assert data["created_count"] == 2
    assert len(_rows(db, "proposed_interpretations")) == 2


@pytest.mark.parametrize("case", ["generate", "discover"])
def test_staging_refusal_also_discloses_prior_commits(case, setup, tmp_path):
    db, ids, monkeypatch = setup
    if case == "discover":
        db, ids = _seed_discovery(db, ids, tmp_path / "discover")
    _use_fake_generation(monkeypatch, case, fail_on=None)
    original = webapp.propose_interpretation
    calls = []
    def staged(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise StagingError("deliberate staging refusal")
        return original(**kwargs)
    monkeypatch.setattr(webapp, "propose_interpretation", staged)
    _, response, _ = _request(case, db, ids)
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    assert data["partial"] is True
    assert data["created_count"] == 1
    assert data["failures"][0]["stage"] == "staging"
    assert "deliberate staging refusal" in data["failures"][0]["error"]
    assert len(_rows(db, "proposed_interpretations")) == 1
    assert len(_rows(db, "ai_provenance")) == 1


def test_reader_discloses_partial_generation_without_hiding_pending_proposals():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "hermeneia/web/static/index.html").read_text()
    start = source.index("async function e10GenerateInterpretations()")
    end = source.index("function e10RenderReview()", start)
    code = source[start:end]
    assert "data.partial" in code
    assert "data.failures" in code
    assert "were saved for review" in code
    assert "e10ProposalCard" in code
