"""Unsupported-claims scorer (issue #63, third ruler).

A surfaced claim is unsupported when it has no acceptable support path:
lineage exists, lineage is traceable, and the supporting document is inside the
declared corpus boundary. This composes traceability and permissibility at the
claim level.

Guardrail: *unsupported* does not mean "bad interpretation" — it means
Hermeneia cannot walk the claim to permissible evidence. Fixtures assert
verdict + reason; the scorer is provider-free, reads only the packet, and
mutates nothing.
"""
from __future__ import annotations

import copy

from hermeneia.study import compile_synthesis_packet
from hermeneia.study.evaluation import (
    FAIL,
    NOT_APPLICABLE,
    PASS,
    UNSUPPORTED_CLAIMS,
    score_unsupported_claims,
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
_EXCLUDED = {
    "id": "doc-muted", "filename": "spoilers.pdf", "file_hash": "h3",
    "source_role": "primary", "total_pages": 3, "excluded_from_analysis": 1,
}


def _packet(annotations, documents=None):
    return compile_synthesis_packet(
        annotations,
        documents=documents or [_PRIMARY],
        field_notes=[],
        reading_progress=[],
        compiled_at="2026-07-04T15:00:00+00:00",
    )


# ── Supported ──────────────────────────────────────────────────────────────


def test_supported_claim_passes():
    verdict = score_unsupported_claims(_packet([_annotation(id="m1")]))
    assert verdict.dimension == UNSUPPORTED_CLAIMS
    assert verdict.verdict == PASS
    assert "acceptable support path" in verdict.reason


# ── Each failure mode of the support path ──────────────────────────────────


def test_no_lineage_fails():
    packet = _packet([_annotation(id="m-nolineage", source_document_id=None)])
    verdict = score_unsupported_claims(packet)
    assert verdict.verdict == FAIL
    assert "m-nolineage" in verdict.offending
    assert "no lineage path" in verdict.reason


def test_untraceable_lineage_fails():
    packet = _packet([
        _annotation(id="m-untraceable", page=None, source_locator=None),
    ])
    verdict = score_unsupported_claims(packet)
    assert verdict.verdict == FAIL
    assert "m-untraceable" in verdict.offending
    assert "not traceable" in verdict.reason


def test_excluded_corpus_support_fails():
    packet = _packet(
        [_annotation(id="m-excluded", source_document_id="doc-muted")],
        documents=[_PRIMARY, _EXCLUDED],
    )
    verdict = score_unsupported_claims(packet)
    assert verdict.verdict == FAIL
    assert "m-excluded" in verdict.offending
    assert "excluded from analysis" in verdict.reason


def test_undeclared_document_support_fails():
    packet = _packet([_annotation(id="m-ghost", source_document_id="doc-ghost")])
    verdict = score_unsupported_claims(packet)
    assert verdict.verdict == FAIL
    assert "m-ghost" in verdict.offending
    assert "not in the declared corpus" in verdict.reason


def test_mixed_supported_and_unsupported_names_only_the_gap():
    packet = _packet(
        [
            _annotation(id="m-ok", source_document_id="doc-primary"),
            _annotation(id="m-excluded", source_document_id="doc-muted"),
        ],
        documents=[_PRIMARY, _EXCLUDED],
    )
    verdict = score_unsupported_claims(packet)
    assert verdict.verdict == FAIL
    assert verdict.offending == ["m-excluded"]
    assert verdict.details["unsupported"] == 1
    assert verdict.details["claim_count"] == 2


# ── Not applicable / boundaries ────────────────────────────────────────────


def test_no_claims_returns_not_applicable():
    # An unranked, unbucketed, unquestioned highlight surfaces no claim.
    verdict = score_unsupported_claims(_packet([_annotation(id="m-silent", rank=None)]))
    assert verdict.verdict == NOT_APPLICABLE
    assert "no surfaced claims" in verdict.reason


def test_scorer_is_deterministic():
    packet = _packet(
        [_annotation(id="m-excluded", source_document_id="doc-muted")],
        documents=[_PRIMARY, _EXCLUDED],
    )
    assert (
        score_unsupported_claims(packet).to_dict()
        == score_unsupported_claims(packet).to_dict()
    )


def test_scorer_does_not_mutate_the_packet():
    packet = _packet([_annotation(id="m1")])
    before = copy.deepcopy(packet)
    score_unsupported_claims(packet)
    assert packet == before
