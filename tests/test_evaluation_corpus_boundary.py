"""Corpus-boundary scorer (issue #63, second ruler).

Evidence preservation asks whether a surfaced item can walk back to evidence.
This scorer asks the prior question: was that evidence allowed to be used at
all? Primary and Supporting roles are permitted; Excluded documents (and
documents outside the declared corpus) are boundary violations.

Fixtures assert verdict + reason; the scorer is provider-free, reads only the
packet, and mutates nothing.
"""
from __future__ import annotations

import copy

from hermeneia.study import compile_synthesis_packet
from hermeneia.study.evaluation import (
    CORPUS_BOUNDARY,
    FAIL,
    NOT_APPLICABLE,
    PASS,
    score_corpus_boundary,
)


def _annotation(**overrides: object) -> dict[str, object]:
    annotation: dict[str, object] = {
        "id": "mark-default",
        "source_document_id": "doc-primary",
        "source_role": "primary",
        "page": 1,
        "source_locator": "page:1:block:1",
        "selected_text": "A selected passage.",
        "note_text": None,
        "question_text": None,
        "relevance": "unclear",
        "tags": [],
        "status": "saved_highlight",
        "rank": 5,
        "theme_bucket": None,
        "evidence_bucket": None,
        "observation_id": None,
        "created_at": "2026-07-01T00:00:00+00:00",
    }
    annotation.update(overrides)
    return annotation


_PRIMARY = {
    "id": "doc-primary", "filename": "gatsby.pdf", "file_hash": "h1",
    "source_role": "primary", "total_pages": 10, "excluded_from_analysis": 0,
}
_REFERENCE = {
    "id": "doc-ref", "filename": "essay.pdf", "file_hash": "h2",
    "source_role": "reference", "total_pages": 5, "excluded_from_analysis": 0,
}
_EXCLUDED = {
    "id": "doc-muted", "filename": "spoilers.pdf", "file_hash": "h3",
    "source_role": "primary", "total_pages": 3, "excluded_from_analysis": 1,
}


def _packet(annotations, documents):
    return compile_synthesis_packet(
        annotations,
        documents=documents,
        field_notes=[],
        reading_progress=[],
        compiled_at="2026-07-04T15:00:00+00:00",
    )


# ── Permitted corpus → pass ────────────────────────────────────────────────


def test_primary_source_is_permitted():
    packet = _packet([_annotation(id="m1")], [_PRIMARY])
    verdict = score_corpus_boundary(packet)
    assert verdict.dimension == CORPUS_BOUNDARY
    assert verdict.verdict == PASS
    assert "permitted corpus documents" in verdict.reason


def test_supporting_reference_role_is_permitted_not_a_violation():
    """Supporting/reference documents may inform interpretation; using one is
    not a boundary violation."""
    packet = _packet(
        [_annotation(id="m-ref", source_document_id="doc-ref", source_role="reference")],
        [_PRIMARY, _REFERENCE],
    )
    verdict = score_corpus_boundary(packet)
    assert verdict.verdict == PASS


# ── Impermissible corpus → fail with reason ────────────────────────────────


def test_excluded_document_is_a_boundary_violation():
    packet = _packet(
        [_annotation(id="m-muted", source_document_id="doc-muted")],
        [_PRIMARY, _EXCLUDED],
    )
    verdict = score_corpus_boundary(packet)
    assert verdict.verdict == FAIL
    assert "m-muted" in verdict.offending
    assert "excluded" in verdict.reason


def test_record_from_undeclared_document_is_a_violation():
    packet = _packet(
        [_annotation(id="m-ghost", source_document_id="doc-not-in-corpus")],
        [_PRIMARY],
    )
    verdict = score_corpus_boundary(packet)
    assert verdict.verdict == FAIL
    assert "m-ghost" in verdict.offending
    assert "not in the declared corpus" in verdict.reason


def test_mixed_permitted_and_excluded_flags_only_the_violation():
    packet = _packet(
        [
            _annotation(id="m-ok", source_document_id="doc-primary"),
            _annotation(id="m-bad", source_document_id="doc-muted"),
        ],
        [_PRIMARY, _EXCLUDED],
    )
    verdict = score_corpus_boundary(packet)
    assert verdict.verdict == FAIL
    assert verdict.offending == ["m-bad"]
    assert verdict.details["violations"] == 1
    assert verdict.details["assessable_records"] == 2


# ── Not applicable / boundaries ────────────────────────────────────────────


def test_no_document_backed_records_is_not_applicable():
    # An unranked, unbucketed highlight surfaces nothing, so there is no
    # document-backed record to assess.
    packet = _packet([_annotation(id="m-silent", rank=None)], [_PRIMARY])
    verdict = score_corpus_boundary(packet)
    assert verdict.verdict == NOT_APPLICABLE
    assert "no surfaced records" in verdict.reason


def test_scorer_does_not_mutate_the_packet():
    packet = _packet([_annotation(id="m1")], [_PRIMARY])
    before = copy.deepcopy(packet)
    score_corpus_boundary(packet)
    assert packet == before


def test_scorer_is_deterministic():
    packet = _packet(
        [_annotation(id="m-muted", source_document_id="doc-muted")],
        [_PRIMARY, _EXCLUDED],
    )
    assert (
        score_corpus_boundary(packet).to_dict()
        == score_corpus_boundary(packet).to_dict()
    )


def test_packet_identity_declares_excluded_flag():
    """The scorer relies on identity.documents carrying the excluded flag."""
    packet = _packet([_annotation(id="m1")], [_PRIMARY, _EXCLUDED])
    by_id = {d["id"]: d for d in packet["identity"]["documents"]}
    assert by_id["doc-primary"]["excluded"] is False
    assert by_id["doc-muted"]["excluded"] is True
