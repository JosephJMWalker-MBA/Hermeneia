"""Promoted regressions for #232: excluded evidence cannot enter a Blueprint or an Artist prompt.

Committing a Blueprint (ratify or revise) refuses supporting Observations, and
supporting Interpretations whose evidence touches Observations, from documents
excluded from analysis (403 `excluded_from_analysis`, as the other
evidence-consuming routes do). As defense in depth, a plan committed before
its evidence was excluded is refused before any Artist prompt is constructed.
Commit 4d520a9 preserves the negative versions; the repair demonstrated
strict unexpected passes before the expected failures were removed.
Synthetic PDFs; offline `null` Artist provider.
"""
from __future__ import annotations

import io
import json
import sqlite3
from datetime import datetime, timezone

import fitz
import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

MUTED = "Muted evidence must not enter prompt."


class ExcludedEvidenceCrossed(AssertionError):
    """Only the observed exclusion-boundary failures are expected here."""


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


@pytest.fixture
def study(tmp_path):
    db = tmp_path / "ws" / "workspace.db"
    SQLiteStore(db).close()
    client = create_app(db_path=db).test_client()

    def upload(text: str, name: str) -> str:
        return client.post("/api/upload", data={"file": (io.BytesIO(_pdf(text)), name)},
                           content_type="multipart/form-data").get_json()["document_id"]

    primary, muted = upload("Visible primary evidence about the lamp.", "primary.pdf"), upload(MUTED, "muted.pdf")
    conn = sqlite3.connect(db)
    obs = {doc: [r[0] for r in conn.execute("SELECT id FROM observations WHERE source_document_id = ?", (doc,))]
           for doc in (primary, muted)}
    conn.close()
    return db, client, muted, obs[primary], obs[muted]


def _exclude(client, doc_id: str) -> None:
    assert client.patch(f"/api/documents/{doc_id}/scope", json={"source_role": "reference"}).status_code == 200
    assert client.patch(f"/api/documents/{doc_id}/scope", json={"excluded": True}).status_code == 200


def _candidate(primary_obs, muted_obs=(), interpretations=()) -> dict:
    sections = [{"claim": "Primary claim.", "supporting_observations": list(primary_obs)}]
    if muted_obs or interpretations:
        sections.append({"claim": "Claim resting on muted evidence.", "supporting_observations": list(muted_obs),
                         "supporting_interpretations": list(interpretations)})
    return {"title": "Lamp", "thesis": "The lamp signals unrest.", "sections": sections}


def _count(db, table: str) -> int:
    return sqlite3.connect(db).execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _prompts_with_muted_text(db) -> int:
    return sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM rendered_narratives WHERE instr(prompt_used, ?) > 0", (MUTED,)).fetchone()[0]


def _refused(response) -> bool:
    body = response.get_json() or {}
    return response.status_code == 403 and body.get("scope") == "excluded_from_analysis"


def test_ratify_refuses_observations_from_excluded_documents(study):
    db, client, muted, primary_obs, muted_obs = study
    _exclude(client, muted)
    response = client.post("/api/pipeline/ratify-blueprint", json={"candidate": _candidate(primary_obs, muted_obs)})
    if not _refused(response) or _count(db, "narrative_blueprints") or _count(db, "architect_plans"):
        raise ExcludedEvidenceCrossed(f"{response.status_code} {response.get_json()}")


def test_revise_refuses_observations_from_excluded_documents(study):
    db, client, muted, primary_obs, muted_obs = study
    predecessor = client.post("/api/pipeline/ratify-blueprint", json={"candidate": _candidate(primary_obs)}).get_json()
    _exclude(client, muted)
    response = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor["blueprint_id"], "reason": "Add the muted claim.",
        "candidate": _candidate(primary_obs, muted_obs)})
    if not _refused(response) or _count(db, "narrative_blueprints") != 1:
        raise ExcludedEvidenceCrossed(f"{response.status_code} {response.get_json()}")


def test_ratify_refuses_interpretations_resting_on_excluded_evidence(study):
    db, client, muted, primary_obs, muted_obs = study
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO interpretations (id, observation_id, perspective, text, evidential_status, "
        "evidence_observation_ids, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("interp_mixed", primary_obs[0], "Test Perspective", "Mixed interpretation.", "speculative",
         json.dumps(muted_obs), datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    _exclude(client, muted)
    response = client.post("/api/pipeline/ratify-blueprint",
                           json={"candidate": _candidate(primary_obs, interpretations=["interp_mixed"])})
    if not _refused(response) or _count(db, "narrative_blueprints"):
        raise ExcludedEvidenceCrossed(f"{response.status_code} {response.get_json()}")


def test_artist_refuses_plan_whose_evidence_was_excluded_after_commit(study):
    db, client, muted, primary_obs, muted_obs = study
    plan = client.post("/api/pipeline/ratify-blueprint",
                       json={"candidate": _candidate(primary_obs, muted_obs)}).get_json()["plan_id"]
    _exclude(client, muted)
    run = client.post("/api/pipeline/run-artist", json={"plan_id": plan, "provider": "null"})
    preview = client.post("/api/pipeline/preview-artist", json={"plan_id": plan, "provider": "null"})
    ratify = client.post("/api/pipeline/ratify-draft", json={"plan_id": plan, "provider": "steward", "text": "Draft."})
    statuses = [run.status_code, preview.status_code, ratify.status_code]
    if any(status < 400 for status in statuses) or _prompts_with_muted_text(db):
        raise ExcludedEvidenceCrossed(f"statuses={statuses} prompts_with_muted_text={_prompts_with_muted_text(db)}")


def test_active_evidence_still_commits_and_renders(study):
    db, client, muted, primary_obs, _muted_obs = study
    _exclude(client, muted)
    response = client.post("/api/pipeline/ratify-blueprint", json={"candidate": _candidate(primary_obs)})
    assert response.status_code == 201, response.get_json()
    run = client.post("/api/pipeline/run-artist", json={"plan_id": response.get_json()["plan_id"], "provider": "null"})
    assert run.status_code in (200, 201), run.get_json()
    assert _prompts_with_muted_text(db) == 0
