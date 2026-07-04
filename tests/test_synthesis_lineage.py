"""Reader-to-synthesis lineage (deterministic, provider-free).

Every packet item a steward can act on should be walkable backward to the
study record and source location that produced it. These tests exercise the
``lineage`` block of the synthesis packet: highlights, field notes, questions,
theme-bucket members, and compiled claims each resolve to a source reference,
missing lineage is represented explicitly rather than dropped, canonical input
records are not mutated, and identical inputs produce identical output.
"""
from __future__ import annotations

import copy
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study import compile_synthesis_packet
from hermeneia.web.app import create_app


def _annotation(**overrides: object) -> dict[str, object]:
    annotation: dict[str, object] = {
        "id": "mark-default",
        "source_document_id": "doc-a",
        "source_role": "primary",
        "page": 1,
        "source_locator": "page:1:block:1",
        "selected_text": "A selected passage.",
        "note_text": None,
        "question_text": None,
        "relevance": "unclear",
        "tags": [],
        "status": "saved_highlight",
        "rank": None,
        "theme_bucket": None,
        "evidence_bucket": None,
        "observation_id": None,
        "created_at": "2026-07-01T00:00:00+00:00",
    }
    annotation.update(overrides)
    return annotation


_DOCUMENTS = [
    {
        "id": "doc-a",
        "filename": "gatsby.pdf",
        "file_hash": "hash-a",
        "source_role": "primary",
        "total_pages": 10,
    }
]

_FIELD_NOTES = [
    {
        "id": "field-current",
        "lane": "corpus",
        "understanding": "Gatsby turns distance into a condition of desire.",
        "pressing_questions": "What happens when the distance collapses?",
        "source_document_id": "doc-a",
        "original_filename": "gatsby.pdf",
        "page": 9,
        "governing_question": "How does desire depend on distance?",
        "created_at": "2026-07-03T12:00:00+00:00",
    }
]


def _compile(annotations, **overrides):
    kwargs = dict(
        documents=_DOCUMENTS,
        field_notes=_FIELD_NOTES,
        reading_progress=[],
        compiled_at="2026-07-04T15:00:00+00:00",
        scope_document_id="doc-a",
    )
    kwargs.update(overrides)
    return compile_synthesis_packet(annotations, **kwargs)


def _record(lineage, record_id):
    return next(r for r in lineage["records"] if r["record_id"] == record_id)


# ── Packet item → record, record → source ──────────────────────────────────


def test_highlight_item_traces_to_page_locator_and_roles():
    annotations = [
        _annotation(
            id="mark-thesis",
            rank=5,
            theme_bucket="aspiration",
            evidence_bucket="draft-1",
            page=2,
            source_locator="page:2:block:4",
            observation_id="obs-1",
        )
    ]
    lineage = _compile(annotations)["lineage"]
    rec = _record(lineage, "mark-thesis")
    assert rec["record_type"] == "reader_highlight"
    # The highlight surfaces in several packet roles, all enumerated.
    assert "ranked_highlight" in rec["roles"]
    assert "theme_bucket:aspiration" in rec["roles"]
    assert "thesis_candidate" in rec["roles"]
    assert "evidence_bucket" in rec["roles"]
    # And it traces back to an exact source location.
    assert rec["source"]["document_id"] == "doc-a"
    assert rec["source"]["filename"] == "gatsby.pdf"
    assert rec["source"]["page"] == 2
    assert rec["source"]["source_locator"] == "page:2:block:4"
    assert rec["source"]["observation_id"] == "obs-1"
    assert rec["traceable"] is True
    assert rec["missing"] == []


def test_question_item_traces_to_source():
    annotations = [
        _annotation(
            id="mark-question",
            rank=3,
            question_text="Does hope require self-deception?",
            page=9,
            source_locator="page:9:block:2",
        )
    ]
    lineage = _compile(annotations)["lineage"]
    rec = _record(lineage, "mark-question")
    assert "unresolved_question" in rec["roles"]
    assert rec["source"]["source_locator"] == "page:9:block:2"
    assert rec["traceable"] is True


def test_field_note_traces_to_page_reference():
    annotations = [_annotation(id="mark-1", rank=4)]
    lineage = _compile(annotations)["lineage"]
    rec = _record(lineage, "field-current")
    assert rec["record_type"] == "field_note"
    assert set(rec["roles"]) == {"field_note_understanding", "field_note_question"}
    assert rec["source"]["document_id"] == "doc-a"
    assert rec["source"]["page"] == 9
    assert rec["traceable"] is True


def test_theme_bucket_members_are_traceable_not_bare_ids():
    """The bare theme_bucket highlight_ids gain a resolved source path."""
    annotations = [
        _annotation(id="mark-a", rank=5, theme_bucket="aspiration", page=2,
                    source_locator="page:2:block:1"),
        _annotation(id="mark-b", rank=3, theme_bucket="aspiration", page=4,
                    source_locator="page:4:block:7"),
    ]
    lineage = _compile(annotations)["lineage"]
    members = [
        r for r in lineage["records"]
        if "theme_bucket:aspiration" in r["roles"]
    ]
    assert {r["record_id"] for r in members} == {"mark-a", "mark-b"}
    assert all(r["source"]["source_locator"] for r in members)


# ── Missing lineage is explicit, not silently dropped ──────────────────────


def test_highlight_missing_locator_is_marked_untraceable_explicitly():
    annotations = [
        _annotation(
            id="mark-nolocator",
            rank=5,
            page=None,
            source_locator=None,
        )
    ]
    lineage = _compile(annotations)["lineage"]
    rec = _record(lineage, "mark-nolocator")
    # Still present (not dropped), but explicitly flagged.
    assert rec["traceable"] is False
    assert "page" in rec["missing"]
    assert "source_locator" in rec["missing"]
    assert lineage["counts"]["untraceable"] >= 1


def test_field_note_locator_gap_is_explicit_with_reason():
    annotations = [_annotation(id="mark-1", rank=4)]
    lineage = _compile(annotations)["lineage"]
    rec = _record(lineage, "field-current")
    assert rec["missing"] == ["source_locator"]
    assert "page granularity" in rec["missing_reason"]


def test_counts_partition_records_by_traceability():
    annotations = [
        _annotation(id="ok", rank=5, page=1, source_locator="page:1:block:1"),
        _annotation(id="bad", rank=5, page=None, source_locator=None),
    ]
    lineage = _compile(annotations)["lineage"]
    counts = lineage["counts"]
    assert counts["records"] == counts["traceable"] + counts["untraceable"]
    assert counts["traceable"] >= 1
    assert counts["untraceable"] >= 1


# ── Canonical input is not mutated; output is deterministic ────────────────


def test_compilation_does_not_mutate_input_records():
    annotations = [
        _annotation(id="mark-thesis", rank=5, theme_bucket="aspiration",
                    source_locator="page:2:block:4", page=2),
    ]
    before = copy.deepcopy(annotations)
    before_notes = copy.deepcopy(_FIELD_NOTES)
    _compile(annotations)
    assert annotations == before
    assert _FIELD_NOTES == before_notes


def test_lineage_is_deterministic_for_identical_inputs():
    annotations = [
        _annotation(id="b", rank=2, theme_bucket="x", created_at="2026-07-02"),
        _annotation(id="a", rank=4, theme_bucket="y", created_at="2026-07-01"),
    ]
    first = _compile(annotations)["lineage"]
    second = _compile(annotations)["lineage"]
    assert first == second


def test_highlight_not_surfaced_anywhere_is_omitted_from_lineage():
    """An unranked, unbucketed, unquestioned highlight feeds no packet item,
    so it has no claim to trace and is not listed."""
    annotations = [_annotation(id="mark-silent")]
    lineage = _compile(annotations)["lineage"]
    assert all(r["record_id"] != "mark-silent" for r in lineage["records"])


# ── Exposed through the deterministic study API, canonical evidence intact ─


def test_study_compile_api_exposes_lineage_without_touching_canonical(tmp_path: Path):
    db_path = tmp_path / "synthesis_lineage.db"
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            doc_id,
            "gatsby.pdf",
            doc_id,
            10,
            datetime.now(timezone.utc).isoformat(),
            "test",
            "primary",
            0,
        ),
    )
    conn.commit()
    conn.close()

    client = create_app(db_path=db_path).test_client()
    assert client.post(
        "/api/reader/highlights",
        json={
            "source_document_id": doc_id,
            "selected_text": "the green light",
            "question_text": "Does hope require distance?",
            "source_locator": "page:2:block:4",
            "page": 2,
            "rank": 5,
            "theme_bucket": "aspiration",
        },
    ).status_code == 201

    body = client.get(f"/api/study/compile?document_id={doc_id}").get_json()
    lineage = body["synthesis_packet"]["lineage"]

    rec = next(r for r in lineage["records"] if r["record_type"] == "reader_highlight")
    assert rec["source"]["source_locator"] == "page:2:block:4"
    assert "thesis_candidate" in rec["roles"]
    assert rec["traceable"] is True
    assert lineage["counts"]["records"] >= 1

    # The lineage projection reads canonical tables but writes nothing.
    verify = sqlite3.connect(db_path)
    assert verify.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    assert verify.execute("SELECT COUNT(*) FROM source_extractions").fetchone()[0] == 0
    verify.close()
