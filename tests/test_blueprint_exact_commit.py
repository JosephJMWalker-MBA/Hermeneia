from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest
from hermeneia.storage.hashing import (
    make_interpretation_id,
    make_observation_id,
    make_semantic_hash,
    make_source_extraction_id,
    make_source_locator,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


def _seed_evidence(db_path):
    store = SQLiteStore(db_path)
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "a" * 64
    store.insert_source_document({
        "id": doc_id,
        "original_filename": "source.pdf",
        "file_hash": doc_id,
        "total_pages": 1,
        "registered_at": now,
        "compiler_version": "test",
    })
    extraction_locator = make_source_locator(1, 1)
    extraction_text = "The green light glowed across the bay."
    extraction_id = make_source_extraction_id(
        doc_id,
        extraction_locator,
        extraction_text,
        "test-parser",
        "test",
    )
    store.insert_source_extractions_batch([{
        "id": extraction_id,
        "epistemic_class": "Evidence",
        "document_id": doc_id,
        "page": 1,
        "region": "block:1",
        "raw_text": extraction_text,
        "parser": "test-parser",
        "parser_version": "test",
        "coordinates": "{}",
        "source_locator": extraction_locator,
        "source_hash": doc_id,
        "hash": extraction_id,
        "extracted_at": now,
    }])
    obs_locator = make_source_locator(1, 1, 1)
    obs_id = make_observation_id(doc_id, obs_locator, extraction_text)
    store.insert_observations_batch([{
        "id": obs_id,
        "epistemic_class": "Evidence",
        "source_document_id": doc_id,
        "source_extraction_id": extraction_id,
        "raw_text": extraction_text,
        "normalized_text": extraction_text,
        "source_locator": obs_locator,
        "semantic_hash": make_semantic_hash(extraction_text),
        "page": 1,
        "paragraph": 1,
        "sentence": 1,
        "preceding_observation_id": None,
        "following_observation_id": None,
        "created_at": now,
    }])
    interp_id = make_interpretation_id(obs_id, "Literary", "The light marks longing.")
    store.insert_interpretation({
        "id": interp_id,
        "observation_id": obs_id,
        "perspective": "Literary",
        "perspective_id": None,
        "text": "The light marks longing.",
        "evidential_status": "speculative",
        "evidence_observation_ids": "[]",
        "confidence": "human",
        "source": "steward-authored",
        "created_at": now,
    })
    store.close()
    return {"doc_id": doc_id, "extraction_id": extraction_id, "obs_id": obs_id, "interp_id": interp_id}


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [
        "source_documents",
        "source_extractions",
        "observations",
        "interpretations",
        "reader_highlights",
        "investigation_log",
        "narrative_blueprints",
        "blueprint_observation_links",
        "blueprint_interpretation_links",
        "architect_plans",
        "architect_plan_paragraphs",
        "supersession_relations",
    ]
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }


def _candidate(obs_id: str, interp_id: str) -> dict:
    return {
        "title": "Reviewed title",
        "thesis": "Reviewed thesis.",
        "sections": [
            {
                "claim": "Reviewed claim.",
                "supporting_observations": [obs_id],
                "supporting_interpretations": [interp_id],
            }
        ],
    }


def test_reader_style_generation_then_commit_persists_reviewed_candidate_without_second_provider_call(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "exact.db"
    ids = _seed_evidence(db_path)
    calls: list[dict] = []
    candidate_a = _candidate(ids["obs_id"], ids["interp_id"])
    candidate_b = {
        "title": "Unreviewed title",
        "thesis": "Unreviewed thesis.",
        "sections": [{"claim": "Unreviewed claim.", "supporting_observations": [], "supporting_interpretations": []}],
    }

    def fake_get_provider(provider, **kwargs):
        calls.append({"provider": provider, "kwargs": kwargs})
        return object()

    def fake_extract(text, provider):
        if len(calls) == 1:
            return candidate_a
        return candidate_b

    monkeypatch.setattr("hermeneia.narrative.artist_providers.get_provider", fake_get_provider)
    monkeypatch.setattr("hermeneia.compiler.blueprint_extractor.extract_blueprint_from_text", fake_extract)

    client = create_app(db_path=db_path).test_client()
    generated = client.post("/api/pipeline/extract-blueprint", json={
        "text": "Question and captured material.",
        "provider": "null",
        "save": False,
    })
    assert generated.status_code == 200
    assert generated.get_json()["proposed_blueprint"] == candidate_a
    assert len(calls) == 1

    def fail_if_called(*args, **kwargs):
        raise AssertionError("commit must not call the Blueprint extractor")

    monkeypatch.setattr("hermeneia.compiler.blueprint_extractor.extract_blueprint_from_text", fail_if_called)
    committed = client.post("/api/pipeline/ratify-blueprint", json={
        "proposed_blueprint": generated.get_json()["proposed_blueprint"],
    })

    assert committed.status_code == 201
    data = committed.get_json()
    assert data["committed_blueprint"] == candidate_a
    assert data["committed_blueprint"] != candidate_b
    assert len(calls) == 1

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT title, thesis, sections, source FROM narrative_blueprints").fetchone()
    conn.close()
    assert row[0] == candidate_a["title"]
    assert row[1] == candidate_a["thesis"]
    assert json.loads(row[2]) == candidate_a["sections"]
    assert row[3] == "extracted"


def test_ratify_blueprint_exact_round_trip_and_architect_ancestry(tmp_path, monkeypatch):
    db_path = tmp_path / "roundtrip.db"
    ids = _seed_evidence(db_path)
    candidate = _candidate(ids["obs_id"], ids["interp_id"])
    client = create_app(db_path=db_path).test_client()
    monkeypatch.setattr(
        "hermeneia.narrative.artist_providers.get_provider",
        lambda *args, **kwargs: pytest.fail("ratify-blueprint must not instantiate a provider"),
    )

    committed = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": candidate})
    assert committed.status_code == 201
    body = committed.get_json()
    assert body["committed_blueprint"] == candidate

    detail = client.get(f"/api/architect/blueprints/{body['blueprint_id']}")
    assert detail.status_code == 200
    saved = detail.get_json()
    assert saved["title"] == candidate["title"]
    assert saved["thesis"] == candidate["thesis"]
    assert [
        {
            "claim": section["claim"],
            "supporting_observations": section["supporting_observations"],
            "supporting_interpretations": section["supporting_interpretations"],
        }
        for section in saved["sections"]
    ] == candidate["sections"]
    assert saved["architect_plan"]["id"] == body["plan_id"]
    assert saved["architect_plan"]["paragraphs"][0]["required_observations"] == [ids["obs_id"]]
    assert saved["architect_plan"]["paragraphs"][0]["required_interpretations"] == [ids["interp_id"]]

    conn = sqlite3.connect(db_path)
    plan_blueprint_id = conn.execute(
        "SELECT blueprint_id FROM architect_plans WHERE id = ?",
        (body["plan_id"],),
    ).fetchone()[0]
    conn.close()
    assert plan_blueprint_id == body["blueprint_id"]


def test_ratify_blueprint_persists_exact_human_edited_candidate_and_ancestry(tmp_path, monkeypatch):
    db_path = tmp_path / "edited.db"
    ids = _seed_evidence(db_path)
    candidate = {
        "title": "Edited working title",
        "thesis": "Edited working thesis.",
        "sections": [
            {
                "claim": "Claim C moved first.",
                "supporting_observations": [ids["obs_id"]],
                "supporting_interpretations": [],
            },
            {
                "claim": "Edited claim B.",
                "supporting_observations": [],
                "supporting_interpretations": [ids["interp_id"]],
            },
            {
                "claim": "New human claim.",
                "supporting_observations": [],
                "supporting_interpretations": [],
            },
        ],
    }
    monkeypatch.setattr(
        "hermeneia.narrative.artist_providers.get_provider",
        lambda *args, **kwargs: pytest.fail("ratify-blueprint must not instantiate a provider"),
    )
    client = create_app(db_path=db_path).test_client()

    committed = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": candidate})

    assert committed.status_code == 201
    body = committed.get_json()
    assert body["committed_blueprint"] == candidate
    detail = client.get(f"/api/architect/blueprints/{body['blueprint_id']}")
    saved = detail.get_json()
    assert saved["title"] == candidate["title"]
    assert saved["thesis"] == candidate["thesis"]
    assert [
        {
            "claim": section["claim"],
            "supporting_observations": section["supporting_observations"],
            "supporting_interpretations": section["supporting_interpretations"],
        }
        for section in saved["sections"]
    ] == candidate["sections"]
    assert saved["architect_plan"]["id"] == body["plan_id"]
    assert saved["architect_plan"]["paragraphs"][0]["blueprint_section"] == 1
    assert saved["architect_plan"]["paragraphs"][0]["required_observations"] == [ids["obs_id"]]
    assert saved["architect_plan"]["paragraphs"][1]["blueprint_section"] == 2
    assert saved["architect_plan"]["paragraphs"][1]["required_interpretations"] == [ids["interp_id"]]


@pytest.mark.parametrize(
    "bad_candidate,error",
    [
        ({"thesis": "T.", "sections": [{"claim": "C."}]}, "title is required"),
        ({"title": "T", "sections": [{"claim": "C."}]}, "thesis is required"),
        ({"title": "T", "thesis": "Th.", "sections": []}, "at least one section is required"),
        ({"title": "T", "thesis": "Th.", "sections": [{"claim": "  "}]}, "claim is required"),
        ({"title": "T", "thesis": "Th.", "sections": ["bad"]}, "must be an object"),
        (
            {"title": "T", "thesis": "Th.", "sections": [{"claim": "C.", "supporting_observations": "obs"}]},
            "supporting_observations must be a list",
        ),
    ],
)
def test_ratify_blueprint_rejects_malformed_candidate_without_writing(tmp_path, bad_candidate, error):
    db_path = tmp_path / "bad.db"
    _seed_evidence(db_path)
    client = create_app(db_path=db_path).test_client()
    conn = sqlite3.connect(db_path)
    before = _counts(conn)
    conn.close()

    response = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": bad_candidate})

    assert response.status_code == 400
    assert error in response.get_json()["error"]
    conn = sqlite3.connect(db_path)
    after = _counts(conn)
    conn.close()
    assert after == before


def test_ratify_blueprint_rejects_unknown_evidence_ids_without_writing(tmp_path):
    db_path = tmp_path / "unknown.db"
    ids = _seed_evidence(db_path)
    candidate = _candidate("missing-observation", ids["interp_id"])
    client = create_app(db_path=db_path).test_client()
    conn = sqlite3.connect(db_path)
    before = _counts(conn)
    conn.close()

    response = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": candidate})

    assert response.status_code == 400
    assert "unknown supporting_observations" in response.get_json()["error"]
    conn = sqlite3.connect(db_path)
    after = _counts(conn)
    conn.close()
    assert after == before


def test_ratify_blueprint_is_idempotent_and_does_not_mutate_evidence_tables(tmp_path):
    db_path = tmp_path / "idempotent.db"
    ids = _seed_evidence(db_path)
    candidate = _candidate(ids["obs_id"], ids["interp_id"])
    client = create_app(db_path=db_path).test_client()
    conn = sqlite3.connect(db_path)
    before = _counts(conn)
    conn.close()

    first = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": candidate})
    second = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": candidate})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["blueprint_id"] == second.get_json()["blueprint_id"]
    assert first.get_json()["plan_id"] == second.get_json()["plan_id"]

    conn = sqlite3.connect(db_path)
    after = _counts(conn)
    conn.close()
    for table in [
        "source_documents",
        "source_extractions",
        "observations",
        "interpretations",
        "reader_highlights",
        "investigation_log",
    ]:
        assert after[table] == before[table]
    assert after["narrative_blueprints"] == before["narrative_blueprints"] + 1
    assert after["blueprint_observation_links"] == before["blueprint_observation_links"] + 1
    assert after["blueprint_interpretation_links"] == before["blueprint_interpretation_links"] + 1
    assert after["architect_plans"] == before["architect_plans"] + 1
    assert after["architect_plan_paragraphs"] == before["architect_plan_paragraphs"] + 1


def test_revise_blueprint_appends_successor_plan_and_supersession_without_mutating_predecessor(tmp_path, monkeypatch):
    db_path = tmp_path / "revision.db"
    ids = _seed_evidence(db_path)
    predecessor = _candidate(ids["obs_id"], ids["interp_id"])
    successor = {
        "title": "Revised title",
        "thesis": "Revised thesis.",
        "sections": [
            {
                "claim": "Revised claim.",
                "supporting_observations": [ids["obs_id"]],
                "supporting_interpretations": [ids["interp_id"]],
            },
            {
                "claim": "Added human claim.",
                "supporting_observations": [],
                "supporting_interpretations": [],
            },
        ],
    }
    client = create_app(db_path=db_path).test_client()
    monkeypatch.setattr(
        "hermeneia.narrative.artist_providers.get_provider",
        lambda *args, **kwargs: pytest.fail("revise-blueprint must not instantiate a provider"),
    )

    committed = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": predecessor})
    predecessor_id = committed.get_json()["blueprint_id"]
    before_detail = client.get(f"/api/architect/blueprints/{predecessor_id}").get_json()

    revised = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor_id,
        "reason": "The new reading needs a second claim.",
        "proposed_blueprint": successor,
    })

    assert revised.status_code == 201
    body = revised.get_json()
    assert body["status"] == "revised"
    assert body["predecessor_id"] == predecessor_id
    assert body["blueprint_id"] != predecessor_id
    assert body["committed_blueprint"] == successor
    assert body["supersession"]["old_id"] == predecessor_id
    assert body["supersession"]["new_id"] == body["blueprint_id"]
    assert body["supersession"]["reason"] == "The new reading needs a second claim."
    assert body["plan_id"]

    after_predecessor = client.get(f"/api/architect/blueprints/{predecessor_id}").get_json()
    assert after_predecessor["title"] == before_detail["title"]
    assert after_predecessor["thesis"] == before_detail["thesis"]
    assert after_predecessor["sections"] == before_detail["sections"]
    assert after_predecessor["superseded_by"][0]["new_id"] == body["blueprint_id"]

    successor_detail = client.get(f"/api/architect/blueprints/{body['blueprint_id']}").get_json()
    assert successor_detail["supersedes"][0]["old_id"] == predecessor_id
    assert successor_detail["architect_plan"]["id"] == body["plan_id"]
    assert successor_detail["architect_plan"]["paragraph_count"] == 2


def test_revise_blueprint_exact_retry_reuses_existing_relation_without_duplicate_event(tmp_path):
    db_path = tmp_path / "revision-retry.db"
    ids = _seed_evidence(db_path)
    predecessor = _candidate(ids["obs_id"], ids["interp_id"])
    successor = {
        "title": "Retry successor",
        "thesis": "Retry thesis.",
        "sections": [{"claim": "Retry claim.", "supporting_observations": [ids["obs_id"]], "supporting_interpretations": []}],
    }
    client = create_app(db_path=db_path).test_client()
    predecessor_id = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": predecessor}).get_json()["blueprint_id"]
    payload = {
        "predecessor_id": predecessor_id,
        "reason": "same human reason",
        "proposed_blueprint": successor,
    }

    first = client.post("/api/pipeline/revise-blueprint", json=payload)
    second = client.post("/api/pipeline/revise-blueprint", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["blueprint_id"] == second.get_json()["blueprint_id"]
    assert second.get_json()["status"] == "already_revised"
    assert first.get_json()["supersession"] == second.get_json()["supersession"]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM supersession_relations").fetchone()[0] == 1
    conn.close()


def test_revise_blueprint_allows_competing_successors_without_current_leaf_pointer(tmp_path):
    db_path = tmp_path / "revision-branches.db"
    ids = _seed_evidence(db_path)
    predecessor = _candidate(ids["obs_id"], ids["interp_id"])
    successor_a = {
        "title": "Branch A",
        "thesis": "Branch A thesis.",
        "sections": [{"claim": "Branch A claim.", "supporting_observations": [], "supporting_interpretations": []}],
    }
    successor_b = {
        "title": "Branch B",
        "thesis": "Branch B thesis.",
        "sections": [{"claim": "Branch B claim.", "supporting_observations": [ids["obs_id"]], "supporting_interpretations": []}],
    }
    client = create_app(db_path=db_path).test_client()
    predecessor_id = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": predecessor}).get_json()["blueprint_id"]

    a = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor_id,
        "reason": "alternate structure A",
        "proposed_blueprint": successor_a,
    })
    b = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor_id,
        "reason": "alternate structure B",
        "proposed_blueprint": successor_b,
    })

    assert a.status_code == 201
    assert b.status_code == 201
    assert a.get_json()["blueprint_id"] != b.get_json()["blueprint_id"]
    detail = client.get(f"/api/architect/blueprints/{predecessor_id}").get_json()
    assert sorted(edge["new_id"] for edge in detail["superseded_by"]) == sorted([
        a.get_json()["blueprint_id"],
        b.get_json()["blueprint_id"],
    ])


def test_revise_blueprint_reuses_convergent_existing_successor_with_new_edge(tmp_path):
    db_path = tmp_path / "revision-convergent.db"
    ids = _seed_evidence(db_path)
    predecessor_a = _candidate(ids["obs_id"], ids["interp_id"])
    predecessor_b = {
        "title": "Another predecessor",
        "thesis": "Another thesis.",
        "sections": [{"claim": "Another claim.", "supporting_observations": [], "supporting_interpretations": []}],
    }
    successor = {
        "title": "Convergent successor",
        "thesis": "Convergent thesis.",
        "sections": [{"claim": "Convergent claim.", "supporting_observations": [ids["obs_id"]], "supporting_interpretations": []}],
    }
    client = create_app(db_path=db_path).test_client()
    pred_a_id = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": predecessor_a}).get_json()["blueprint_id"]
    pred_b_id = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": predecessor_b}).get_json()["blueprint_id"]

    first = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": pred_a_id,
        "reason": "first route",
        "proposed_blueprint": successor,
    })
    second = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": pred_b_id,
        "reason": "second route",
        "proposed_blueprint": successor,
    })

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["blueprint_id"] == second.get_json()["blueprint_id"]
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM narrative_blueprints").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM supersession_relations").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM architect_plans WHERE blueprint_id = ?", (first.get_json()["blueprint_id"],)).fetchone()[0] == 1
    conn.close()


@pytest.mark.parametrize(
    ("payload_update", "error"),
    [
        ({"reason": "   "}, "revision reason is required"),
        ({"proposed_blueprint": None}, "proposed_blueprint must be an object"),
    ],
)
def test_revise_blueprint_rejects_invalid_request_without_writing(tmp_path, payload_update, error):
    db_path = tmp_path / "revision-invalid.db"
    ids = _seed_evidence(db_path)
    predecessor = _candidate(ids["obs_id"], ids["interp_id"])
    successor = {
        "title": "Invalid successor",
        "thesis": "Invalid thesis.",
        "sections": [{"claim": "Invalid claim.", "supporting_observations": [], "supporting_interpretations": []}],
    }
    client = create_app(db_path=db_path).test_client()
    predecessor_id = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": predecessor}).get_json()["blueprint_id"]
    conn = sqlite3.connect(db_path)
    before = _counts(conn)
    conn.close()
    payload = {
        "predecessor_id": predecessor_id,
        "reason": "valid reason",
        "proposed_blueprint": successor,
    }
    payload.update(payload_update)

    response = client.post("/api/pipeline/revise-blueprint", json=payload)

    assert response.status_code == 400
    assert error in response.get_json()["error"]
    conn = sqlite3.connect(db_path)
    after = _counts(conn)
    conn.close()
    assert after == before


def test_revise_blueprint_rejects_noop_and_cycle_without_writing(tmp_path):
    db_path = tmp_path / "revision-cycle.db"
    ids = _seed_evidence(db_path)
    predecessor = _candidate(ids["obs_id"], ids["interp_id"])
    successor = {
        "title": "Cycle successor",
        "thesis": "Cycle thesis.",
        "sections": [{"claim": "Cycle claim.", "supporting_observations": [], "supporting_interpretations": []}],
    }
    client = create_app(db_path=db_path).test_client()
    predecessor_id = client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": predecessor}).get_json()["blueprint_id"]
    successor_id = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor_id,
        "reason": "forward edge",
        "proposed_blueprint": successor,
    }).get_json()["blueprint_id"]
    conn = sqlite3.connect(db_path)
    before_cycle = _counts(conn)
    conn.close()

    noop = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": predecessor_id,
        "reason": "no-op",
        "proposed_blueprint": predecessor,
    })
    cycle = client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": successor_id,
        "reason": "back edge",
        "proposed_blueprint": predecessor,
    })

    assert noop.status_code == 400
    assert "cannot supersede itself" in noop.get_json()["error"]
    assert cycle.status_code == 400
    assert "cycle rejected" in cycle.get_json()["error"]
    conn = sqlite3.connect(db_path)
    after = _counts(conn)
    conn.close()
    assert after == before_cycle
