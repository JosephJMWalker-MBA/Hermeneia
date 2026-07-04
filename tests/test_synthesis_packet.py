"""Deterministic study synthesis packet tests (Issue #47)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study import PACKET_VERSION, compile_synthesis_packet
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


def test_packet_shape_organizes_ranked_records_and_preserves_references() -> None:
    annotations = [
        _annotation(
            id="mark-thesis",
            rank=5,
            selected_text="The green light recedes.",
            note_text="Desire depends on distance.",
            theme_bucket="aspiration",
            evidence_bucket="draft-1",
            source_locator="page:2:block:4",
            page=2,
            status="promoted_to_observation",
            observation_id="obs-1",
        ),
        _annotation(
            id="mark-question",
            rank=3,
            selected_text="Gatsby believed in the green light.",
            question_text="Does hope require self-deception?",
            theme_bucket="aspiration",
            source_locator="page:9:block:2",
            page=9,
            created_at="2026-07-02T00:00:00+00:00",
        ),
        _annotation(
            id="mark-unranked",
            selected_text="Context kept in the compiled record.",
            theme_bucket="class",
        ),
        _annotation(
            id="mark-dismissed",
            rank=5,
            selected_text="Do not include.",
            status="dismissed",
        ),
    ]
    documents = [
        {
            "id": "doc-a",
            "filename": "gatsby.pdf",
            "file_hash": "hash-a",
            "source_role": "primary",
            "total_pages": 10,
        }
    ]
    field_notes = [
        {
            "id": "field-old",
            "lane": "corpus",
            "understanding": "An earlier understanding.",
            "pressing_questions": None,
            "source_document_id": "doc-a",
            "original_filename": "gatsby.pdf",
            "page": 3,
            "governing_question": "What does Gatsby ask hope to do?",
            "created_at": "2026-07-01T12:00:00+00:00",
        },
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
        },
        {
            "id": "field-instrument",
            "lane": "instrument",
            "understanding": "The Reader needs better keyboard navigation.",
            "created_at": "2026-07-04T12:00:00+00:00",
        },
    ]

    packet = compile_synthesis_packet(
        annotations,
        documents=documents,
        field_notes=field_notes,
        reading_progress=[
            {
                "document_id": "doc-a",
                "pages_read": "[1, 2, 9, 99]",
                "last_page": 9,
                "completed_at": None,
                "updated_at": "2026-07-03T13:00:00+00:00",
            }
        ],
        compiled_at="2026-07-04T15:00:00+00:00",
        scope_document_id="doc-a",
        working_thesis="Desire survives by preserving distance.",
    )

    assert packet["packet_type"] == PACKET_VERSION
    assert packet["compiled_at"] == "2026-07-04T15:00:00+00:00"
    assert packet["identity"]["document_id"] == "doc-a"
    assert packet["identity"]["documents"][0]["file_hash"] == "hash-a"
    assert packet["governing_question"] == "How does desire depend on distance?"
    assert packet["working_thesis"] == "Desire survives by preserving distance."
    assert [item["id"] for item in packet["ranked_highlights"]] == [
        "mark-thesis",
        "mark-question",
    ]
    question_mark = packet["ranked_highlights"][1]
    assert question_mark["source"] == {
        "document_id": "doc-a",
        "filename": "gatsby.pdf",
        "source_role": "primary",
        "page": 9,
        "source_locator": "page:9:block:2",
        "observation_id": None,
    }
    assert packet["ranked_highlights"][0]["source"]["observation_id"] == "obs-1"
    assert packet["theme_buckets"] == [
        {
            "name": "aspiration",
            "count": 2,
            "ranked_count": 2,
            "highlight_ids": ["mark-question", "mark-thesis"],
        },
        {
            "name": "class",
            "count": 1,
            "ranked_count": 0,
            "highlight_ids": ["mark-unranked"],
        },
    ]
    assert (
        packet["field_notes"]["current_understanding"]["text"]
        == "Gatsby turns distance into a condition of desire."
    )
    assert packet["field_notes"]["current_understanding"]["field_note_id"] == "field-current"
    assert {
        (question["record_type"], question["record_id"])
        for question in packet["unresolved_questions"]
    } == {
        ("reader_highlight", "mark-question"),
        ("field_note", "field-current"),
    }
    assert packet["reading_trail"]["documents"][0]["pages_read"] == [1, 2, 9]
    assert packet["reading_trail"]["total_pages_read"] == 3
    assert packet["compiled_record"]["thesis_candidate_ids"] == ["mark-thesis"]
    assert packet["compiled_record"]["strongest_observation_ids"] == ["mark-thesis"]
    assert packet["adopted_companion_notes"]["identification_available"] is False
    assert packet["provenance"]["provider_free"] is True
    assert packet["provenance"]["canonical_evidence_modified"] is False
    assert "mark-dismissed" not in packet["provenance"]["source_records"]["reader_highlight_ids"]


def test_packet_is_deterministic_for_identical_records_and_timestamp() -> None:
    annotations = [
        _annotation(id="b", rank=2, created_at="2026-07-02"),
        _annotation(id="a", rank=4, created_at="2026-07-01"),
    ]
    documents = [
        {
            "id": "doc-a",
            "filename": "gatsby.pdf",
            "file_hash": "hash-a",
            "source_role": "primary",
            "total_pages": 10,
        }
    ]
    notes = [
        {
            "id": "note-a",
            "lane": "corpus",
            "understanding": "Current.",
            "created_at": "2026-07-01",
        }
    ]
    kwargs = {
        "documents": documents,
        "field_notes": notes,
        "reading_progress": [],
        "compiled_at": "2026-07-04T15:00:00+00:00",
    }

    first = compile_synthesis_packet(annotations, **kwargs)
    second = compile_synthesis_packet(
        list(reversed(annotations)),
        documents=list(reversed(documents)),
        field_notes=list(reversed(notes)),
        reading_progress=[],
        compiled_at="2026-07-04T15:00:00+00:00",
    )

    assert first == second


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_study_compile_api_includes_packet_from_saved_records(tmp_path: Path) -> None:
    db_path = tmp_path / "synthesis_packet.db"
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 10, _now(), "test", "primary", 0),
    )
    conn.commit()
    conn.close()

    client = create_app(db_path=db_path).test_client()
    assert client.post(
        "/api/reader/highlights",
        json={
            "source_document_id": doc_id,
            "selected_text": "the green light",
            "note_text": "Aspiration made visible.",
            "question_text": "Does hope require distance?",
            "source_locator": "page:2:block:4",
            "page": 2,
            "rank": 5,
            "theme_bucket": "aspiration",
        },
    ).status_code == 201
    assert client.post(
        "/api/investigation-log",
        json={
            "lane": "corpus",
            "understanding": "Distance sustains Gatsby's desire.",
            "pressing_questions": "Can desire survive attainment?",
            "source_document_id": doc_id,
            "page": 2,
            "governing_question": "How does desire depend on distance?",
        },
    ).status_code == 201
    assert client.post(
        "/api/reader/progress",
        json={"document_id": doc_id, "page": 2},
    ).status_code == 200

    response = client.get(f"/api/study/compile?document_id={doc_id}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["counts"]["ranked"] == 1
    packet = body["synthesis_packet"]
    assert packet["identity"]["documents"][0]["filename"] == "gatsby.pdf"
    assert packet["governing_question"] == "How does desire depend on distance?"
    assert packet["working_thesis"] is None
    assert packet["ranked_highlights"][0]["selected_text"] == "the green light"
    assert (
        packet["ranked_highlights"][0]["source"]["source_locator"]
        == "page:2:block:4"
    )
    assert (
        packet["field_notes"]["current_understanding"]["text"]
        == "Distance sustains Gatsby's desire."
    )
    assert {
        question["text"] for question in packet["unresolved_questions"]
    } == {
        "Does hope require distance?",
        "Can desire survive attainment?",
    }
    assert packet["reading_trail"]["documents"][0]["pages_read"] == [2]
    assert packet["provenance"]["provider_free"] is True

    verify = sqlite3.connect(db_path)
    assert verify.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    assert verify.execute("SELECT COUNT(*) FROM source_extractions").fetchone()[0] == 0
    verify.close()


def test_global_packet_excludes_records_from_excluded_documents(tmp_path: Path) -> None:
    db_path = tmp_path / "synthesis_scope.db"
    SQLiteStore(db_path).close()
    active_doc = "a" * 64
    excluded_doc = "b" * 64
    now = _now()
    conn = sqlite3.connect(db_path)
    for doc_id, filename, excluded in (
        (active_doc, "active.pdf", 0),
        (excluded_doc, "excluded.pdf", 1),
    ):
        conn.execute(
            """INSERT INTO source_documents
               (id, original_filename, file_hash, total_pages, registered_at,
                compiler_version, source_role, excluded_from_analysis)
               VALUES (?,?,?,?,?,?,?,?)""",
            (doc_id, filename, doc_id, 10, now, "test", "primary", excluded),
        )
    for note_id, doc_id, understanding, created_at in (
        ("active-note", active_doc, "Visible understanding.", "2026-07-01"),
        ("excluded-note", excluded_doc, "Hidden understanding.", "2026-07-02"),
    ):
        conn.execute(
            """INSERT INTO investigation_log
               (id, lane, understanding, source_document_id, created_at)
               VALUES (?,?,?,?,?)""",
            (note_id, "corpus", understanding, doc_id, created_at),
        )
    conn.execute(
        """INSERT INTO reader_highlights
           (id, source_document_id, source_role, selected_text, rank,
            tags, status, relevance, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            "excluded-mark",
            excluded_doc,
            "primary",
            "Hidden mark.",
            5,
            "[]",
            "saved_highlight",
            "unclear",
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()

    packet = create_app(db_path=db_path).test_client().get(
        "/api/study/compile"
    ).get_json()["synthesis_packet"]

    assert [document["id"] for document in packet["identity"]["documents"]] == [
        active_doc
    ]
    assert packet["field_notes"]["current_understanding"]["text"] == (
        "Visible understanding."
    )
    assert packet["ranked_highlights"] == []
    assert packet["provenance"]["source_records"]["field_note_ids"] == [
        "active-note"
    ]
