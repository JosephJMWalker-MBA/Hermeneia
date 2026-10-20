"""HTTP regressions for ADR-0009 staging and steward decisions (#271).

Run against real Flask routes, SQLiteStore and isolated seeded workspaces.
Providers are local in-process fakes; no live model, network or user study.
Canonical collision policy: fail closed and leave the proposal pending.
"""
from __future__ import annotations

import sqlite3
import threading

import pytest

from hermeneia.compiler.staging.interpretation import propose_interpretation
from hermeneia.storage.hashing import make_interpretation_id
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain
from test_e10_vertical_slice_api import (
    _CapturingProvider,
    _cloud_catalog_registry,
    _reset_catalog_provider,
)

GENERATED_AT = "2026-10-19T12:00:00+00:00"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    db = tmp_path / "e10-staging-route.db"
    store = SQLiteStore(db)
    ids = _seed_full_chain(store)
    store.close()
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    _reset_catalog_provider()
    _CapturingProvider.render_prompts = []
    _CapturingProvider.render_responses = []
    _CapturingProvider.fail_on_render_calls = set()
    app = create_app(db_path=db, provider_registry=_cloud_catalog_registry())
    app.config["TESTING"] = True
    return db, ids, app


def _stage(db, ids, *, text="An additional candidate reading.", model="fake-one",
           generated_at=GENERATED_AT, evidential_status="speculative"):
    store = SQLiteStore(db)
    try:
        return propose_interpretation(
            observation_id=ids["obs_id"],
            perspective="literary",
            text=text,
            evidential_status=evidential_status,
            generating_model=model,
            prompt_reference="sha256:route-test",
            prompt_reference_type="hash",
            conn=store,
            generation_timestamp=generated_at,
            evidence_observation_ids=[ids["obs_id"]],
        )
    finally:
        store.close()


def _row(db, table, row_id):
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        record = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return dict(record) if record else None


def _count(db, table):
    with sqlite3.connect(db) as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def _decide(client, proposal_id, action):
    return client.post(
        f"/api/e10/proposals/{proposal_id}/{action}",
        json={"steward_id": "steward-route-test", "comment": "Review decision."},
    )


def test_http_accept_reports_only_the_canonical_row_actually_written(workspace):
    db, ids, app = workspace
    proposal = _stage(db, ids)
    response = _decide(app.test_client(), proposal["id"], "accept")
    assert response.status_code == 200, response.get_json()
    returned = response.get_json()["interpretation"]
    stored = _row(db, "interpretations", returned["id"])
    assert stored is not None
    for key, value in returned.items():
        assert stored[key] == value, key
    assert stored["ai_provenance_id"] == proposal["ai_provenance_id"]
    assert _row(db, "proposed_interpretations", proposal["id"])["status"] == "accepted"


def test_http_refuses_existing_human_canonical_without_reattribution(workspace):
    db, ids, app = workspace
    proposal = _stage(db, ids, text="A human reading already retained.")
    canonical_id = make_interpretation_id(ids["obs_id"], "literary", proposal["text"])
    store = SQLiteStore(db)
    try:
        store.insert_interpretation({
            "id": canonical_id, "observation_id": ids["obs_id"],
            "perspective": "literary", "perspective_id": None, "text": proposal["text"],
            "evidential_status": "contested", "evidence_observation_ids": "[]",
            "confidence": "human", "source": "steward-authored", "created_at": GENERATED_AT,
        })
    finally:
        store.close()
    before = _row(db, "interpretations", canonical_id)
    response = _decide(app.test_client(), proposal["id"], "accept")
    assert response.status_code == 400
    assert "already exists" in response.get_json()["error"]
    assert _row(db, "interpretations", canonical_id) == before
    assert _row(db, "proposed_interpretations", proposal["id"])["status"] == "pending"
    assert _row(db, "ai_provenance", proposal["ai_provenance_id"])["accepting_steward"] is None


def test_http_refuses_second_model_provenance_for_same_canonical_id(workspace):
    db, ids, app = workspace
    first = _stage(db, ids, text="Same words, different models.")
    second = _stage(db, ids, text=first["text"], model="fake-two",
                    generated_at="2026-10-19T12:01:00+00:00", evidential_status="contested")
    client = app.test_client()
    accepted = _decide(client, first["id"], "accept")
    assert accepted.status_code == 200, accepted.get_json()
    canonical_id = accepted.get_json()["interpretation"]["id"]
    before = _row(db, "interpretations", canonical_id)
    refused = _decide(client, second["id"], "accept")
    assert refused.status_code == 400
    assert "already exists" in refused.get_json()["error"]
    assert _row(db, "interpretations", canonical_id) == before
    assert _row(db, "proposed_interpretations", second["id"])["status"] == "pending"
    assert _row(db, "ai_provenance", second["ai_provenance_id"])["accepting_steward"] is None


def test_http_ignored_canonical_insert_rolls_back_decision(workspace):
    db, ids, app = workspace
    proposal = _stage(db, ids, text="Intentionally skipped by database trigger.")
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TRIGGER ignore_staging_canonical_insert
            BEFORE INSERT ON interpretations
            BEGIN SELECT RAISE(IGNORE); END
        """)
    before = _count(db, "interpretations")
    refused = _decide(app.test_client(), proposal["id"], "accept")
    assert refused.status_code == 400, refused.get_json()
    assert "not persisted exactly" in refused.get_json()["error"]
    assert _count(db, "interpretations") == before
    assert _row(db, "proposed_interpretations", proposal["id"])["status"] == "pending"
    assert _row(db, "ai_provenance", proposal["ai_provenance_id"])["accepting_steward"] is None


@pytest.mark.parametrize("first,second", [("accept", "reject"), ("reject", "accept")])
def test_http_terminal_decision_refuses_a_second_decision(workspace, first, second):
    db, ids, app = workspace
    proposal = _stage(db, ids)
    client = app.test_client()
    accepted = _decide(client, proposal["id"], first)
    assert accepted.status_code == 200, accepted.get_json()
    refused = _decide(client, proposal["id"], second)
    assert refused.status_code == 400, refused.get_json()
    assert "already" in refused.get_json()["error"]
    assert _row(db, "proposed_interpretations", proposal["id"])["status"] == (
        "accepted" if first == "accept" else "rejected"
    )


@pytest.mark.parametrize("winner", ["accept", "reject"])
def test_http_competing_decisions_return_one_200_and_one_governed_400(workspace, monkeypatch, winner):
    db, ids, app = workspace
    proposal = _stage(db, ids)
    entered = threading.Event()
    release = threading.Event()
    original_get = SQLiteStore.get_proposed_interpretation

    def hold_first_read(store, proposal_id):
        row = original_get(store, proposal_id)
        if threading.current_thread().name == "staging-winner":
            entered.set()
            assert release.wait(8), "winning request never released"
        return row

    monkeypatch.setattr(SQLiteStore, "get_proposed_interpretation", hold_first_read)
    loser = "reject" if winner == "accept" else "accept"
    results = {}

    def request(role):
        try:
            with app.test_client() as client:
                response = _decide(client, proposal["id"], role)
                results[role] = (response.status_code, response.get_json())
        except BaseException as exc:
            results[role] = exc

    t1 = threading.Thread(target=request, name="staging-winner", args=(winner,))
    t2 = threading.Thread(target=request, name="staging-loser", args=(loser,))
    try:
        t1.start()
        assert entered.wait(8), "first request did not reach the locked decision"
        t2.start()
    finally:
        release.set()
        t1.join(10)
        if t2.ident is not None:
            t2.join(10)
    assert not t1.is_alive() and not t2.is_alive()
    assert set(results) == {"accept", "reject"}, results
    assert results[winner][0] == 200, results
    assert results[loser][0] == 400, results
    assert "already" in results[loser][1]["error"]
    assert _row(db, "proposed_interpretations", proposal["id"])["status"] == (
        "accepted" if winner == "accept" else "rejected"
    )
    assert (_row(db, "ai_provenance", proposal["ai_provenance_id"])["accepting_steward"] is not None) == (
        winner == "accept"
    )


@pytest.mark.parametrize("mode", ["triage", "interpretive", "skeptical"])
def test_http_generate_response_mode_matches_committed_proposal(workspace, mode):
    db, ids, app = workspace
    response = app.test_client().post(
        "/api/e10/interpretations/generate",
        json={"observation_id": ids["obs_id"], "participants": ["gpt"], "response_mode": mode},
    )
    assert response.status_code == 201, response.get_json()
    proposals = response.get_json()["proposals"]
    assert len(proposals) == 1
    proposal = proposals[0]
    stored = _row(db, "proposed_interpretations", proposal["id"])
    assert stored is not None
    assert stored["status"] == "pending"
    assert stored["response_mode"] == mode == proposal["response_mode"]
    assert stored["ai_provenance_id"] == proposal["ai_provenance_id"]
