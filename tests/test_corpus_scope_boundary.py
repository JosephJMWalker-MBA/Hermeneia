"""
Corpus Scope Boundary Tests

Invariant: Supporting documents may inform inquiry, but they may not
silently become primary evidence.

Covers:
  - Muted documents are excluded from observation queries
  - Non-primary source_role does not suppress exclusion filter
  - source_role is preserved in the scope API
  - Proposals derived from non-primary observations carry source_role provenance
  - scope API boundary_clear flag is accurate
  - Observations from excluded documents cannot be fetched for interpretation
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.compiler.staging.interpretation import propose_interpretation
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_doc(conn: sqlite3.Connection, doc_id: str, filename: str,
                source_role: str = "primary", excluded: int = 0) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,1,?,?,?,?)""",
        (doc_id, filename, doc_id, _now(), "test", source_role, excluded),
    )


def _insert_obs(conn: sqlite3.Connection, obs_id: str, doc_id: str, text: str) -> None:
    locator = "p.1.s.1.§.1"
    extraction_id = obs_id + "_ext"
    conn.execute(
        """INSERT OR IGNORE INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            extraction_id,
            doc_id,
            1,
            "body",
            text,
            "test-parser",
            "1.0",
            "{}",
            locator,
            obs_id[:32],
            obs_id[:32],
            _now(),
        ),
    )
    conn.execute(
        """INSERT OR IGNORE INTO observations
           (id, epistemic_class, source_document_id, raw_text,
            source_locator, semantic_hash, page, paragraph, sentence,
            source_extraction_id, created_at)
           VALUES (?,?,?,?,?,?,1,1,1,?,?)""",
        (obs_id, "Evidence", doc_id, text, locator,
         obs_id[:32], extraction_id, _now()),
    )
    conn.commit()


def _insert_interpretation(
    conn: sqlite3.Connection,
    interp_id: str,
    obs_id: str,
    text: str,
    evidence_ids: list[str] | None = None,
) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO interpretations
           (id, observation_id, perspective, text, evidential_status,
            evidence_observation_ids, confidence, source, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            interp_id,
            obs_id,
            "Test Perspective",
            text,
            "speculative",
            json.dumps(evidence_ids or []),
            "human",
            "steward-authored",
            _now(),
        ),
    )
    conn.commit()


def _count_rows(db: Path, table: str) -> int:
    conn = sqlite3.connect(db)
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return int(count)


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "scope_test.db"
    store = SQLiteStore(db_path)
    store.close()
    return db_path


# ── Mute (excluded_from_analysis) ─────────────────────────────────────────────

def test_muted_primary_doc_excluded_from_observation_list(tmp_path):
    """Observations from a muted primary document must not appear in /api/e10/observations."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "muted.pdf",  source_role="primary", excluded=1)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Gatsby observation visible")
    _insert_obs(conn, "obs_b_1", "b" * 64, "Muted observation invisible")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get("/api/e10/observations")
    assert resp.status_code == 200
    obs = resp.get_json()["observations"]
    ids = [o["id"] for o in obs]
    assert "obs_a_1" in ids, "Primary document observation should be visible"
    assert "obs_b_1" not in ids, "Muted document observation must be excluded"


def test_muted_supporting_doc_excluded_from_observation_list(tmp_path):
    """A muted reference document's observations must also be excluded."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf",  source_role="primary",   excluded=0)
    _insert_doc(conn, "c" * 64, "essay.pdf",   source_role="reference", excluded=1)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Primary obs")
    _insert_obs(conn, "obs_c_1", "c" * 64, "Reference obs muted")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get("/api/e10/observations")
    obs_ids = [o["id"] for o in resp.get_json()["observations"]]
    assert "obs_c_1" not in obs_ids, "Muted reference observation must be excluded"


def test_active_supporting_doc_observations_are_included(tmp_path):
    """Active (non-muted) reference observations appear in the list but carry their role."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary",   excluded=0)
    _insert_doc(conn, "c" * 64, "essay.pdf",  source_role="reference", excluded=0)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Primary obs")
    _insert_obs(conn, "obs_c_1", "c" * 64, "Reference obs active")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get("/api/e10/observations")
    obs = resp.get_json()["observations"]
    ref_obs = next((o for o in obs if o["id"] == "obs_c_1"), None)
    assert ref_obs is not None, "Active reference obs should appear"
    assert ref_obs["source_role"] == "reference", "source_role must be 'reference', not 'primary'"


# ── scope API ─────────────────────────────────────────────────────────────────

def test_scope_api_separates_primary_from_supporting(tmp_path):
    """/api/e10/scope must categorise documents by role correctly."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf",   source_role="primary",     excluded=0)
    _insert_doc(conn, "b" * 64, "essay_en.pdf", source_role="commentary",  excluded=0)
    _insert_doc(conn, "c" * 64, "essay_es.pdf", source_role="reference",   excluded=0)
    _insert_doc(conn, "d" * 64, "muted.pdf",    source_role="exploratory", excluded=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get("/api/e10/scope")
    assert resp.status_code == 200
    d = resp.get_json()

    assert d["primary_count"] == 1
    assert d["supporting_count"] == 2
    assert d["muted_count"] == 1
    assert d["boundary_clear"] is True
    primary_names = [p["filename"] for p in d["primary"]]
    assert "gatsby.pdf" in primary_names


def test_scope_api_boundary_clear_false_when_no_primary(tmp_path):
    """boundary_clear must be False when no primary document is in scope."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "essay.pdf", source_role="commentary", excluded=0)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    d = client.get("/api/e10/scope").get_json()
    assert d["boundary_clear"] is False, "No primary doc → boundary_clear must be False"


def test_scope_api_muted_primary_does_not_count(tmp_path):
    """A muted primary document must not satisfy the primary boundary requirement."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    d = client.get("/api/e10/scope").get_json()
    assert d["primary_count"] == 0, "Muted primary must not count toward primary_count"
    assert d["boundary_clear"] is False


# ── source_role preserved in observations ─────────────────────────────────────

def test_observation_list_carries_source_role(tmp_path):
    """Every observation in /api/e10/observations must include its document's source_role."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary",  excluded=0)
    _insert_doc(conn, "b" * 64, "notes.pdf",  source_role="notes",    excluded=0)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Primary text")
    _insert_obs(conn, "obs_b_1", "b" * 64, "Notes text")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    obs = client.get("/api/e10/observations").get_json()["observations"]
    by_id = {o["id"]: o for o in obs}

    assert by_id["obs_a_1"]["source_role"] == "primary"
    assert by_id["obs_b_1"]["source_role"] == "notes", \
        "Notes observation must carry source_role='notes', not default to 'primary'"


# ── generation parameters carry provenance ────────────────────────────────────

def test_generate_stores_observation_source_role_in_generation_parameters(tmp_path):
    """Proposals generated from non-primary observations must record observation_source_role.

    Uses the 'meta' participant (mapped to ollama-meta / llama3.2:3b). When
    Ollama is unavailable the call raises a StagingError and the endpoint
    returns 400 with the provider error — in that case we inspect the
    generation_parameters directly via a stub inserted into the DB to verify
    the corpus context was constructed correctly.

    Strategy: verify the corpus_context dict built by the endpoint carries the
    right observation_role before the provider call, by patching generate_candidate_interpretation.
    """
    import unittest.mock as mock

    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf",   source_role="primary",    excluded=0)
    _insert_doc(conn, "b" * 64, "essay_en.pdf", source_role="commentary", excluded=0)
    _insert_obs(conn, "obs_b_1", "b" * 64, "The essay argues Gatsby symbolises capitalism.")
    conn.commit(); conn.close()

    captured = {}

    def fake_generate(*, observation_text, perspective_label, provider, corpus_context=None, response_mode="interpretive"):
        captured["corpus_context"] = corpus_context
        return "Stub interpretation text.", "stub-prompt"

    with mock.patch(
        "hermeneia.explorer.interpreter.generate_candidate_interpretation",
        side_effect=fake_generate,
    ), mock.patch(
        "hermeneia.web.app.generate_candidate_interpretation",
        side_effect=fake_generate,
    ):
        client = create_app(db_path=db).test_client()
        resp = client.post("/api/e10/interpretations/generate",
            json={"observation_id": "obs_b_1", "participants": ["meta"]},
            content_type="application/json")

    assert resp.status_code == 201, resp.data.decode()[:200]
    proposals = resp.get_json()["proposals"]
    assert proposals, "At least one proposal should be returned"

    # Corpus context passed to the generator must reflect the commentary source
    ctx = captured.get("corpus_context", {})
    assert ctx.get("observation_role") == "commentary", \
        f"corpus_context must set observation_role='commentary', got: {ctx}"
    assert ctx.get("primary_work") == "gatsby.pdf", \
        "corpus_context must identify the primary document"

    # generation_parameters stored in DB must record the source role
    raw_gp = proposals[0].get("generation_parameters") or {}
    gen_params = raw_gp if isinstance(raw_gp, dict) else json.loads(raw_gp)
    assert gen_params.get("observation_source_role") == "commentary", \
        "generation_parameters must record that this observation came from a commentary document"

    # The proposal payload returned by the API must surface obs_source_role
    assert proposals[0].get("obs_source_role") == "commentary", \
        "obs_source_role field on proposal payload must reflect commentary source"


# ── direct-ID and stale-ID enforcement ───────────────────────────────────────

def test_e10_generate_rejects_excluded_observation_direct_id(tmp_path):
    import unittest.mock as mock

    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="commentary", excluded=1)
    _insert_obs(conn, "obs_b_1", "b" * 64, "Muted observation must not generate.")
    conn.commit(); conn.close()

    with mock.patch("hermeneia.web.app.generate_candidate_interpretation") as gen:
        client = create_app(db_path=db).test_client()
        resp = client.post(
            "/api/e10/interpretations/generate",
            json={"observation_id": "obs_b_1", "participants": ["meta"]},
        )

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]
    assert not gen.called, "Excluded observation must be rejected before provider generation"
    assert _count_rows(db, "proposed_interpretations") == 0
    assert _count_rows(db, "interpretations") == 0
    assert _count_rows(db, "ai_provenance") == 0


def test_e10_observation_detail_rejects_excluded_observation_direct_id(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="reference", excluded=1)
    _insert_obs(conn, "obs_b_1", "b" * 64, "Muted detail must not load.")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get("/api/e10/observations/obs_b_1")

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]


def test_e10_discover_rejects_any_excluded_observation_direct_id(tmp_path):
    import unittest.mock as mock

    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="commentary", excluded=1)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Active observation.")
    _insert_obs(conn, "obs_b_1", "b" * 64, "Muted observation.")
    conn.commit(); conn.close()

    with mock.patch("hermeneia.web.app.generate_candidate_buckets") as buckets, \
         mock.patch("hermeneia.web.app.generate_interpretation_from_bucket") as gen:
        client = create_app(db_path=db).test_client()
        resp = client.post(
            "/api/e10/interpretations/discover",
            json={"observation_ids": ["obs_a_1", "obs_b_1"], "participants": ["meta"]},
        )

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]
    assert not buckets.called
    assert not gen.called
    assert _count_rows(db, "proposed_interpretations") == 0
    assert _count_rows(db, "ai_provenance") == 0


def test_architect_generate_prompt_excludes_excluded_observations_and_interpretations(tmp_path):
    import unittest.mock as mock

    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "commentary.pdf", source_role="commentary", excluded=0)
    _insert_doc(conn, "c" * 64, "muted.pdf", source_role="reference", excluded=1)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Visible primary evidence.")
    _insert_obs(conn, "obs_b_1", "b" * 64, "Visible commentary evidence.")
    _insert_obs(conn, "obs_c_1", "c" * 64, "Muted evidence must not enter prompt.")
    _insert_interpretation(conn, "interp_active_1", "obs_a_1", "Visible interpretation.")
    _insert_interpretation(conn, "interp_muted_1", "obs_c_1", "Muted interpretation.")
    _insert_interpretation(
        conn,
        "interp_mixed_1",
        "obs_a_1",
        "Mixed stale interpretation.",
        evidence_ids=["obs_c_1"],
    )
    conn.commit(); conn.close()

    captured = {}

    class FakeArchitectProvider:
        def render(self, prompt: str) -> str:
            captured["prompt"] = prompt
            return json.dumps({
                "title": "Scoped blueprint",
                "thesis": "Only active evidence is available.",
                "sections": [
                    {
                        "claim": "Active evidence remains available.",
                        "obs_refs": ["OBS-1"],
                        "interp_refs": ["INTERP-interp_a"],
                    }
                ],
            })

    with mock.patch(
        "hermeneia.narrative.artist_providers.get_provider",
        return_value=FakeArchitectProvider(),
    ):
        client = create_app(db_path=db).test_client()
        resp = client.post(
            "/api/architect/generate",
            json={"directive": "Build from active evidence only.", "provider": "fake"},
        )

    assert resp.status_code == 201, resp.data.decode()[:500]
    prompt = captured["prompt"]
    assert "Visible primary evidence." in prompt
    assert "Visible interpretation." in prompt
    assert "Visible commentary evidence." in prompt
    assert "Muted evidence must not enter prompt." not in prompt
    assert "Muted interpretation." not in prompt
    assert "Mixed stale interpretation." not in prompt


def test_trace_and_coverage_do_not_index_excluded_observations(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="reference", excluded=1)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Active observation.")
    _insert_obs(conn, "obs_b_1", "b" * 64, "Muted observation.")
    _insert_interpretation(conn, "interp_active_1", "obs_a_1", "Active interpretation.")
    _insert_interpretation(conn, "interp_muted_1", "obs_b_1", "Muted interpretation.")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    assert client.get("/api/trace/1").status_code == 200
    assert client.get("/api/trace/2").status_code == 404

    coverage = client.get("/api/coverage")
    assert coverage.status_code == 200
    ids = {row["id"] for row in coverage.get_json()["observations"]}
    assert ids == {"obs_a_1"}


def test_accept_proposal_rechecks_observation_scope_after_document_muted(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "commentary.pdf", source_role="commentary", excluded=0)
    _insert_obs(conn, "obs_b_1", "b" * 64, "Initially active commentary.")
    conn.commit(); conn.close()

    store = SQLiteStore(db)
    proposal = propose_interpretation(
        observation_id="obs_b_1",
        perspective="Test Perspective",
        text="Stale proposal text.",
        evidential_status="speculative",
        generating_model="test-model",
        prompt_reference="prompt",
        prompt_reference_type="full_text",
        conn=store,
        evidence_observation_ids=["obs_b_1"],
    )
    store.set_document_scope("b" * 64, excluded=True)
    store.close()

    client = create_app(db_path=db).test_client()
    resp = client.post(
        f"/api/e10/proposals/{proposal['id']}/accept",
        json={"steward_id": "tester", "rationale": "should fail"},
    )

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]
    conn2 = sqlite3.connect(db)
    status = conn2.execute(
        "SELECT status FROM proposed_interpretations WHERE id = ?",
        (proposal["id"],),
    ).fetchone()[0]
    accepted = conn2.execute(
        "SELECT accepting_steward FROM ai_provenance WHERE id = ?",
        (proposal["ai_provenance_id"],),
    ).fetchone()[0]
    interp_count = conn2.execute("SELECT COUNT(*) FROM interpretations").fetchone()[0]
    conn2.close()
    assert status == "pending"
    assert accepted is None
    assert interp_count == 0


def test_critic_run_rechecks_observation_scope_after_document_muted(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "commentary.pdf", source_role="commentary", excluded=0)
    _insert_obs(conn, "obs_b_1", "b" * 64, "Initially active commentary.")
    conn.commit(); conn.close()

    store = SQLiteStore(db)
    proposal = propose_interpretation(
        observation_id="obs_b_1",
        perspective="Test Perspective",
        text="Stale proposal text.",
        evidential_status="speculative",
        generating_model="test-model",
        prompt_reference="prompt",
        prompt_reference_type="full_text",
        conn=store,
        evidence_observation_ids=["obs_b_1"],
    )
    store.set_document_scope("b" * 64, excluded=True)
    store.close()

    client = create_app(db_path=db).test_client()
    resp = client.post(
        "/api/e10/critic/run",
        json={"proposal_id": proposal["id"], "policies": ["conservative"]},
    )

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]
    assert _count_rows(db, "critic_reports") == 0


def test_lineage_rejects_excluded_observation_direct_id(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="reference", excluded=1)
    _insert_obs(conn, "obs_b_1", "b" * 64, "Muted lineage must not load.")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get("/api/lineage/observation/obs_b_1")

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]


def test_reader_pages_rejects_excluded_document_direct_id(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="reference", excluded=1)
    _insert_obs(conn, "obs_b_1", "b" * 64, "Muted reader page.")
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get(f"/api/reader/documents/{'b'*64}/pages")

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]


def test_reader_summary_rejects_excluded_document_direct_id(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="reference", excluded=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.get(f"/api/reader/documents/{'b'*64}/summary")

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]


def test_reader_highlight_create_rejects_excluded_document_direct_id(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="reference", excluded=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/highlights", json={
        "source_document_id": "b" * 64,
        "page": 1,
        "selected_text": "Muted highlight.",
    })

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]
    assert _count_rows(db, "reader_highlights") == 0


def test_reader_progress_rejects_excluded_document_direct_id(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "b" * 64, "muted.pdf", source_role="reference", excluded=1)
    conn.commit(); conn.close()

    client = create_app(db_path=db).test_client()
    resp = client.post("/api/reader/progress", json={"document_id": "b" * 64, "page": 1})

    assert resp.status_code == 403
    assert "excluded_from_analysis" in resp.get_json()["error"]
    assert _count_rows(db, "reading_progress") == 0


def test_non_primary_generate_prompt_contains_source_role_warning(tmp_path):
    import unittest.mock as mock
    from hermeneia.explorer.interpreter import build_explorer_prompt

    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "commentary.pdf", source_role="commentary", excluded=0)
    _insert_obs(conn, "obs_b_1", "b" * 64, "Commentary observation.")
    conn.commit(); conn.close()

    captured = {}

    def fake_generate(*, observation_text, perspective_label, provider, corpus_context=None, response_mode="interpretive"):
        prompt = build_explorer_prompt(
            observation_text,
            perspective_label,
            corpus_context,
            response_mode,
        )
        captured["prompt"] = prompt
        return "Stub interpretation text.", prompt

    with mock.patch("hermeneia.web.app.generate_candidate_interpretation", side_effect=fake_generate):
        client = create_app(db_path=db).test_client()
        resp = client.post(
            "/api/e10/interpretations/generate",
            json={"observation_id": "obs_b_1", "participants": ["meta"]},
        )

    assert resp.status_code == 201, resp.data.decode()[:200]
    prompt = captured["prompt"]
    assert "Observation Source: commentary.pdf" in prompt
    assert "critical commentary" in prompt
    assert "Do not treat it as primary evidence" in prompt


def test_architect_prompt_labels_non_primary_evidence_when_used(tmp_path):
    import unittest.mock as mock

    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    _insert_doc(conn, "a" * 64, "gatsby.pdf", source_role="primary", excluded=0)
    _insert_doc(conn, "b" * 64, "commentary.pdf", source_role="commentary", excluded=0)
    _insert_obs(conn, "obs_a_1", "a" * 64, "Primary observation.")
    _insert_obs(conn, "obs_b_1", "b" * 64, "Commentary observation.")
    conn.commit(); conn.close()

    captured = {}

    class FakeArchitectProvider:
        def render(self, prompt: str) -> str:
            captured["prompt"] = prompt
            return json.dumps({
                "title": "Role-labelled blueprint",
                "thesis": "Role labels remain visible.",
                "sections": [
                    {
                        "claim": "Primary evidence remains primary.",
                        "obs_refs": ["OBS-1"],
                        "interp_refs": [],
                    }
                ],
            })

    with mock.patch(
        "hermeneia.narrative.artist_providers.get_provider",
        return_value=FakeArchitectProvider(),
    ):
        client = create_app(db_path=db).test_client()
        resp = client.post(
            "/api/architect/generate",
            json={"directive": "Use role labels.", "provider": "fake"},
        )

    assert resp.status_code == 201, resp.data.decode()[:500]
    prompt = captured["prompt"]
    assert "SOURCE ROLE RULE" in prompt
    assert "NON-PRIMARY commentary evidence from commentary.pdf" in prompt
    assert "do not treat as primary" in prompt.lower()
