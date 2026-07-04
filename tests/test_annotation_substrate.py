"""
Ranked Semantic Annotation Substrate Tests (Issue #35)

The user marks meaning; the machine reasons over the marked meaning. This proves
the substrate: ranked, bucketed marks persist durably on reader_highlights, the two
senses of "bucket" stay distinct (theme = meaning category, evidence = working set),
and the deterministic compiler organizes ranked marks into a structured study
summary without any AI.

Two layers:
  - compiler unit tests (pure, no DB)
  - API + persistence tests (rank round-trip, validation, migration idempotence)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study import MARK_TYPES, classify_mark, compile_study
from hermeneia.web.app import create_app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- Compiler unit tests (pure) ------------------------------------------------

def _mark(**kw):
    base = {"status": "saved_highlight", "created_at": _now(), "tags": []}
    base.update(kw)
    return base


def test_classify_mark_derives_type_from_durable_fields():
    assert classify_mark(_mark(status="observation_candidate")) == "observation"
    assert classify_mark(_mark(status="promoted_to_observation")) == "observation"
    assert classify_mark(_mark(tags=["concept:aspiration"])) == "concept"
    assert classify_mark(_mark(question_text="Why?")) == "question"
    assert classify_mark(_mark(note_text="A thought.")) == "note"
    assert classify_mark(_mark()) == "highlight"
    # observation status wins over a concept tag (most-committed wins)
    assert classify_mark(_mark(status="promoted_to_observation",
                               tags=["concept:x"])) == "observation"
    # every derived type is one of the canonical MARK_TYPES
    assert classify_mark(_mark()) in MARK_TYPES


def test_compile_study_buckets_by_rank_and_type():
    marks = [
        _mark(rank=5, note_text="Thesis-level insight."),
        _mark(rank=4, status="observation_candidate", note_text="Strong obs."),
        _mark(rank=2, note_text="Minor note."),
        _mark(rank=1, note_text="Speculative."),
        _mark(rank=3, question_text="An open question?"),
        _mark(note_text="Unranked note."),
    ]
    study = compile_study(marks)

    assert len(study["thesis_candidates"]) == 1
    assert study["thesis_candidates"][0]["rank"] == 5
    assert len(study["strongest_observations"]) == 1
    assert study["strongest_observations"][0]["note_text"] == "Strong obs."
    assert len(study["open_questions"]) == 1
    assert {m["note_text"] for m in study["weak_areas"]} == {"Minor note.", "Speculative."}
    assert study["counts"]["total"] == 6
    assert study["counts"]["ranked"] == 5
    assert study["counts"]["unranked"] == 1
    assert study["suggested_next_steps"]  # non-empty guidance


def test_theme_bucket_summary_distinct_from_evidence_bucket():
    marks = [
        _mark(rank=5, theme_bucket="aspiration", evidence_bucket="draft-1", note_text="a"),
        _mark(rank=3, theme_bucket="aspiration", note_text="b"),
        _mark(rank=4, theme_bucket="class", evidence_bucket="draft-1", note_text="c"),
        _mark(rank=2, note_text="d"),  # neither bucket
    ]
    study = compile_study(marks)

    themes = {t["bucket"]: t for t in study["theme_bucket_summary"]}
    assert set(themes) == {"aspiration", "class"}
    assert themes["aspiration"]["count"] == 2
    assert themes["aspiration"]["avg_rank"] == 4.0
    # evidence bucket is membership (working set), independent of theme
    assert len(study["evidence_bucket"]) == 2
    assert study["counts"]["themes"] == 2
    assert study["counts"]["in_evidence_bucket"] == 2


def test_compile_is_deterministic_and_rank_sorted():
    marks = [
        _mark(rank=3, note_text="mid", created_at="2026-01-02"),
        _mark(rank=5, note_text="top", created_at="2026-01-03"),
        _mark(rank=5, note_text="also-top-earlier", created_at="2026-01-01"),
    ]
    a = compile_study(marks)
    b = compile_study(list(reversed(marks)))
    # rank desc, then created_at asc: stable regardless of input order
    order = [m["note_text"] for m in a["thesis_candidates"]]
    assert order == ["also-top-earlier", "top"]
    assert order == [m["note_text"] for m in b["thesis_candidates"]]


def test_compile_ignores_dismissed_and_invalid_ranks():
    marks = [
        _mark(rank=5, note_text="kept"),
        _mark(rank=5, note_text="gone", status="dismissed"),
        _mark(rank=99, note_text="bad-rank"),   # invalid -> treated as unranked
        _mark(rank=True, note_text="bool-rank"),  # bool guard -> unranked
    ]
    study = compile_study(marks)
    assert [m["note_text"] for m in study["thesis_candidates"]] == ["kept"]
    assert study["counts"]["total"] == 3  # dismissed excluded
    assert study["counts"]["ranked"] == 1  # only the valid rank-5


def test_compile_empty_gives_starting_guidance():
    study = compile_study([])
    assert study["counts"]["total"] == 0
    assert study["suggested_next_steps"]
    assert "Mark a passage" in study["suggested_next_steps"][0]


# -- API + persistence tests ---------------------------------------------------

def _make_db(tmp_path: Path) -> Path:
    db = tmp_path / "substrate.db"
    SQLiteStore(db).close()
    return db


def _insert_doc(db: Path, doc_id: str, *, excluded: int = 0) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT OR IGNORE INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 10, _now(), "test", "primary", excluded),
    )
    conn.commit()
    conn.close()


def test_fresh_db_has_substrate_columns(tmp_path):
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(reader_highlights)").fetchall()}
    conn.close()
    assert {"rank", "theme_bucket", "evidence_bucket"} <= cols


def test_migration_is_idempotent_on_a_pre_substrate_table(tmp_path):
    """A reader_highlights table without the new columns must migrate cleanly,
    and re-running must neither fail nor duplicate columns."""
    db = _make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.executescript(
        """DROP TABLE reader_highlights;
           CREATE TABLE reader_highlights (
             id TEXT PRIMARY KEY, source_document_id TEXT, source_role TEXT,
             page INTEGER, source_locator TEXT, selected_text TEXT,
             context_before TEXT, context_after TEXT, note_text TEXT,
             question_text TEXT, question_type TEXT, relevance TEXT, tags TEXT,
             status TEXT, observation_id TEXT, created_at TEXT, updated_at TEXT);"""
    )
    conn.commit()
    conn.close()

    from hermeneia.storage.sqlite import ensure_profile_tables
    for _ in range(2):  # idempotent
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        ensure_profile_tables(c)
        c.close()

    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(reader_highlights)").fetchall()]
    conn.close()
    assert cols.count("rank") == 1
    assert {"rank", "theme_bucket", "evidence_bucket"} <= set(cols)


def test_rank_and_buckets_round_trip_and_persist(tmp_path):
    db = _make_db(tmp_path)
    doc_id = "a" * 64
    _insert_doc(db, doc_id)

    client = create_app(db_path=db).test_client()
    r = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id,
        "selected_text": "the green light",
        "note_text": "Aspiration made visible.",
        "rank": 5,
        "theme_bucket": "aspiration",
        "evidence_bucket": "draft-1",
        "page": 2,
    })
    assert r.status_code == 201

    # Fresh app over the same DB (runs the migration path): must persist.
    second = create_app(db_path=db).test_client()
    rows = second.get(f"/api/reader/documents/{doc_id}/highlights").get_json()["highlights"]
    assert len(rows) == 1
    h = rows[0]
    assert h["rank"] == 5
    assert h["theme_bucket"] == "aspiration"
    assert h["evidence_bucket"] == "draft-1"


def test_rank_validation(tmp_path):
    db = _make_db(tmp_path)
    doc_id = "b" * 64
    _insert_doc(db, doc_id)
    client = create_app(db_path=db).test_client()

    def post(rank):
        return client.post("/api/reader/highlights", json={
            "source_document_id": doc_id, "selected_text": "x", "rank": rank})

    assert post(6).status_code == 400
    assert post(0).status_code == 400
    assert post("high").status_code == 400
    assert post(True).status_code == 400
    assert post(1.5).status_code == 400
    assert post(3).status_code == 201
    assert post("4").status_code == 201
    assert post(None).status_code == 201  # unranked is valid


def test_patch_updates_rank_and_buckets(tmp_path):
    db = _make_db(tmp_path)
    doc_id = "c" * 64
    _insert_doc(db, doc_id)
    client = create_app(db_path=db).test_client()

    hid = client.post("/api/reader/highlights", json={
        "source_document_id": doc_id, "selected_text": "y"}).get_json()["id"]

    assert client.patch(f"/api/reader/highlights/{hid}", json={
        "rank": 4, "theme_bucket": "class", "evidence_bucket": "draft-2"}).status_code == 200
    # invalid rank on PATCH is rejected
    assert client.patch(f"/api/reader/highlights/{hid}", json={"rank": 9}).status_code == 400

    h = client.get(f"/api/reader/documents/{doc_id}/highlights").get_json()["highlights"][0]
    assert h["rank"] == 4 and h["theme_bucket"] == "class" and h["evidence_bucket"] == "draft-2"

    assert client.patch(f"/api/reader/highlights/{hid}", json={
        "rank": None, "theme_bucket": " ", "evidence_bucket": ""}).status_code == 200
    h = client.get(f"/api/reader/documents/{doc_id}/highlights").get_json()["highlights"][0]
    assert h["rank"] is None and h["theme_bucket"] is None and h["evidence_bucket"] is None


def test_study_compile_endpoint(tmp_path):
    db = _make_db(tmp_path)
    doc_id = "d" * 64
    _insert_doc(db, doc_id)
    client = create_app(db_path=db).test_client()

    client.post("/api/reader/highlights", json={
        "source_document_id": doc_id, "selected_text": "thesis passage",
        "note_text": "The core claim.", "rank": 5, "theme_bucket": "aspiration"})
    client.post("/api/reader/highlights", json={
        "source_document_id": doc_id, "selected_text": "a question here",
        "question_text": "Does hope mean self-deception?", "rank": 3,
        "theme_bucket": "aspiration"})

    study = client.get(f"/api/study/compile?document_id={doc_id}").get_json()
    assert len(study["thesis_candidates"]) == 1
    assert len(study["open_questions"]) == 1
    assert study["theme_bucket_summary"][0]["bucket"] == "aspiration"
    assert study["theme_bucket_summary"][0]["count"] == 2
    assert study["counts"]["ranked"] == 2


def test_study_compile_endpoint_respects_active_document_scope(tmp_path):
    db = _make_db(tmp_path)
    active_doc = "e" * 64
    excluded_doc = "f" * 64
    _insert_doc(db, active_doc)
    _insert_doc(db, excluded_doc, excluded=1)
    client = create_app(db_path=db).test_client()

    client.post("/api/reader/highlights", json={
        "source_document_id": active_doc,
        "selected_text": "visible",
        "note_text": "Visible active mark.",
        "rank": 5,
    })
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT INTO reader_highlights
           (id, source_document_id, source_role, selected_text, note_text, rank,
            tags, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            "excluded-highlight",
            excluded_doc,
            "primary",
            "hidden",
            "Excluded mark.",
            5,
            "[]",
            "saved_highlight",
            _now(),
            _now(),
        ),
    )
    conn.commit()
    conn.close()

    study = client.get("/api/study/compile").get_json()
    assert [m["note_text"] for m in study["thesis_candidates"]] == ["Visible active mark."]
    assert client.get(f"/api/study/compile?document_id={excluded_doc}").status_code == 403
