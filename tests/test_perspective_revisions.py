from __future__ import annotations

import json
import sqlite3

import pytest

from hermeneia.perspective_identity import (
    FRAME_V2_SCHEME,
    frame_v2_row_from_draft,
    perspective_frame_v2_id,
)
from hermeneia.perspective_runs import (
    normalize_transient_perspective_draft,
    transient_perspective_fingerprint,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_e10_vertical_slice_api import (
    _CapturingProvider,
    _install_fake_ollama,
    _ollama_registry,
    _reader_selection_scope,
)


def _draft(**overrides) -> dict:
    base = {
        "label": "Institutional Trust Reader",
        "purpose": "Examine how institutions gain, lose, or borrow legitimacy.",
        "questions": ["Who is expected to trust whom?"],
        "challenges": ["Challenge unsupported legitimacy claims."],
        "limitations": ["May overemphasize institutions."],
    }
    base.update(overrides)
    return base


def _saved_row(draft: dict | None = None, *, declared_by: str = "Primary Human Steward", predecessor: str | None = None):
    return frame_v2_row_from_draft(
        draft or _draft(),
        declared_by=declared_by,
        declared_date="2026-08-22T12:00:00+00:00",
        predecessor_perspective_id=predecessor,
    )[0]


def test_frame_v2_identity_distinguishes_semantics_declaration_context_and_time() -> None:
    transient = normalize_transient_perspective_draft(_draft()).definition
    row = _saved_row()

    assert row["definition_fingerprint"] == transient_perspective_fingerprint(transient)
    assert row["id"] == perspective_frame_v2_id(
        definition_fingerprint=row["definition_fingerprint"],
        declared_by="Primary Human Steward",
    )
    assert _saved_row(declared_by="Another Steward")["id"] != row["id"]
    assert _saved_row(_draft(purpose="Examine institutional trust differently."))["id"] != row["id"]
    assert frame_v2_row_from_draft(
        _draft(),
        declared_by="Primary Human Steward",
        declared_date="2030-01-01T00:00:00+00:00",
    )[0]["id"] == row["id"]


def test_frame_v2_perspectives_are_immutable_and_same_label_can_coexist(tmp_path):
    store = SQLiteStore(tmp_path / "perspectives.db")
    first = store.insert_frame_perspective(_saved_row())
    second = store.insert_frame_perspective(
        _saved_row(_draft(purpose="A refined institutional standpoint."), predecessor=first["id"])
    )

    assert first["name"] == second["name"] == "Institutional Trust Reader"
    assert first["id"] != second["id"]
    with pytest.raises(sqlite3.IntegrityError, match="Perspective immutable"):
        store._conn.execute("UPDATE perspectives SET purpose = 'mutated' WHERE id = ?", (first["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="Perspective immutable"):
        store._conn.execute("DELETE FROM perspectives WHERE id = ?", (first["id"],))
    store.close()


def test_revision_appends_successor_supersession_and_retry_is_idempotent(tmp_path):
    store = SQLiteStore(tmp_path / "revisions.db")
    predecessor = store.insert_frame_perspective(_saved_row())
    successor_row = _saved_row(
        _draft(purpose="Trace how institutions ask to be believed."),
        predecessor=predecessor["id"],
    )

    successor = store.insert_perspective_revision(
        predecessor["id"],
        successor_row,
        "Sharper trust language.",
        "2026-08-22T12:30:00+00:00",
    )
    retry = store.insert_perspective_revision(
        predecessor["id"],
        {**successor_row, "declared_date": "2030-01-01T00:00:00+00:00", "created_at": "2030-01-01T00:00:00+00:00"},
        "Sharper trust language.",
        "2030-01-01T00:00:00+00:00",
    )

    assert retry["id"] == successor["id"]
    assert store.get_perspective_by_id(predecessor["id"])["purpose"] == predecessor["purpose"]
    edges = store.supersessions_from(predecessor["id"])
    assert len(edges) == 1
    assert edges[0]["new_id"] == successor["id"]
    assert store.perspective_is_current_leaf(predecessor["id"]) is False
    assert store.perspective_is_current_leaf(successor["id"]) is True
    with pytest.raises(ValueError, match="current Perspective leaf"):
        store.insert_perspective_revision(
            predecessor["id"],
            _saved_row(_draft(purpose="Hidden branch."), predecessor=predecessor["id"]),
            "Branch attempt.",
            "2026-08-22T13:00:00+00:00",
        )
    store.close()


def test_saved_perspective_api_and_run_use_canonical_identity(tmp_path, monkeypatch):
    _install_fake_ollama(monkeypatch, ["qwen2.5:0.5b"])
    _CapturingProvider.calls = []
    _CapturingProvider.render_prompts = []
    client = create_app(
        db_path=tmp_path / "saved-run.db",
        provider_registry=_ollama_registry(),
    ).test_client()

    saved = client.post(
        "/api/perspective/saved",
        json={"perspective_draft": _draft(), "declared_by": "Primary Human Steward"},
    )
    assert saved.status_code == 201
    perspective = saved.get_json()
    assert perspective["identity_scheme"] == FRAME_V2_SCHEME
    assert perspective["declared_by"] == "Primary Human Steward"

    listing = client.get("/api/perspective/saved").get_json()
    assert listing["perspectives"][0]["id"] == perspective["id"]

    neither = client.post("/api/perspective/run", json={
        "question": "What matters?",
        "model": "qwen2.5:0.5b",
        "scope": _reader_selection_scope(),
    })
    both = client.post("/api/perspective/run", json={
        "perspective_id": "close-reader",
        "saved_perspective_id": perspective["id"],
        "question": "What matters?",
        "model": "qwen2.5:0.5b",
        "scope": _reader_selection_scope(),
    })
    assert neither.status_code == 400
    assert both.status_code == 400

    run = client.post("/api/perspective/run", json={
        "saved_perspective_id": perspective["id"],
        "question": "Who is asked to trust?",
        "model": "qwen2.5:0.5b",
        "scope": _reader_selection_scope("Only this source passage."),
    })

    assert run.status_code == 201
    receipt = run.get_json()
    assert receipt["canonical_status"] == "not_persisted"
    assert receipt["perspective"]["origin"] == "canonical_saved"
    assert receipt["perspective"]["perspective_id"] == perspective["id"]
    assert receipt["perspective"]["definition_fingerprint"] == perspective["definition_fingerprint"]
    assert receipt["perspective"]["declared_by"] == "Primary Human Steward"
    assert receipt["execution"]["provider_id"] == "ollama-local"
    assert receipt["execution"]["model_id"] == "qwen2.5:0.5b"
    assert "Perspective ID: " + perspective["id"] in _CapturingProvider.render_prompts[-1]


def test_saved_perspective_get_routes_are_read_only_for_missing_database(tmp_path):
    db_path = tmp_path / "missing.db"
    client = create_app(db_path=db_path).test_client()

    listing = client.get("/api/perspective/saved")
    missing = client.get("/api/perspective/saved/perspective-frame-v2:missing")

    assert listing.status_code == 200
    assert listing.get_json()["perspectives"] == []
    assert missing.status_code == 404
    assert not db_path.exists()


def test_saved_perspective_revision_api_rejects_legacy_and_non_leaf(tmp_path):
    store = SQLiteStore(tmp_path / "api-revisions.db")
    store.register_perspective({
        "id": "legacy-id",
        "name": "Legacy",
        "description": "",
        "created_at": "2026-08-22T12:00:00+00:00",
    })
    root = store.insert_frame_perspective(_saved_row())
    store.close()
    client = create_app(db_path=tmp_path / "api-revisions.db").test_client()

    legacy = client.post(
        "/api/perspective/saved/legacy-id/revisions",
        json={"perspective_draft": _draft(), "declared_by": "Primary Human Steward", "reason": "No."},
    )
    assert legacy.status_code == 409
    assert "frame-v2" in legacy.get_json()["error"]

    first = client.post(
        f"/api/perspective/saved/{root['id']}/revisions",
        json={
            "perspective_draft": _draft(purpose="Trace legitimation."),
            "declared_by": "Primary Human Steward",
            "reason": "Refine purpose.",
        },
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/perspective/saved/{root['id']}/revisions",
        json={
            "perspective_draft": _draft(purpose="Hidden branch."),
            "declared_by": "Primary Human Steward",
            "reason": "Branch.",
        },
    )
    assert second.status_code == 409
    assert "current Perspective leaf" in second.get_json()["error"]
