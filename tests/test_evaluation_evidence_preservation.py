"""Evidence-preservation scorer + harness (issue #63, design §9/§11).

The first deterministic ruler: did every surfaced packet item preserve a
walkable path back to evidence, or did the system explicitly say why not?

These tests build small synthesis packets from study records, run the scorer,
and assert both the verdict and its reason against recorded expectations. They
also confirm the scorer is provider-free and performs no writes, and that the
report is deterministic.
"""
from __future__ import annotations

import copy

from hermeneia.study import compile_synthesis_packet
from hermeneia.study.evaluation import (
    EVIDENCE_PRESERVATION,
    FAIL,
    NOT_APPLICABLE,
    PASS,
    ScorerVerdict,
    build_evaluation_report,
    score_evidence_preservation,
)


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


def _packet(annotations, field_notes=None):
    return compile_synthesis_packet(
        annotations,
        documents=_DOCUMENTS,
        field_notes=field_notes or [],
        reading_progress=[],
        compiled_at="2026-07-04T15:00:00+00:00",
        scope_document_id="doc-a",
    )


# ── Fixtures: (name, packet, expected verdict, reason fragment) ─────────────


def _fixture_gatsby_clean():
    packet = _packet([
        _annotation(id="mark-thesis", rank=5, theme_bucket="aspiration",
                    page=2, source_locator="page:2:block:4"),
    ])
    return ("gatsby-clean", packet, PASS, "trace to a walkable source")


def _fixture_dropped_evidence():
    packet = _packet([
        _annotation(id="mark-nolocator", rank=5, page=None, source_locator=None),
    ])
    return ("dropped-evidence", packet, FAIL, "mark-nolocator")


def _fixture_not_applicable():
    # No ranked/bucketed/questioned highlights and no field notes → nothing
    # surfaces in the packet, so there is no evidence obligation to evaluate.
    packet = _packet([_annotation(id="mark-silent")])
    return ("no-surfaced-items", packet, NOT_APPLICABLE, "no surfaced study records")


_FIXTURES = [
    _fixture_gatsby_clean,
    _fixture_dropped_evidence,
    _fixture_not_applicable,
]


# ── Expected-vs-actual regression (verdict + reason) ───────────────────────


def test_scorer_matches_expected_verdict_and_reason():
    for build in _FIXTURES:
        name, packet, expected_verdict, reason_fragment = build()
        verdict = score_evidence_preservation(packet)
        assert verdict.dimension == EVIDENCE_PRESERVATION, name
        assert verdict.verdict == expected_verdict, f"{name}: {verdict.reason}"
        assert reason_fragment in verdict.reason, name


def test_fail_names_the_offending_record():
    _, packet, _, _ = _fixture_dropped_evidence()
    verdict = score_evidence_preservation(packet)
    assert verdict.verdict == FAIL
    assert "mark-nolocator" in verdict.offending
    assert "missing" in verdict.reason


def test_pass_counts_are_reported():
    _, packet, _, _ = _fixture_gatsby_clean()
    verdict = score_evidence_preservation(packet)
    assert verdict.verdict == PASS
    assert verdict.details["untraceable"] == 0
    assert verdict.details["traceable"] == verdict.details["record_count"]


def test_field_note_with_page_is_treated_as_traceable():
    """Page-level field notes carry an explicit source-locator gap but still
    preserve a walkable path (document + page), so they do not fail."""
    field_notes = [{
        "id": "field-1",
        "lane": "corpus",
        "understanding": "Distance sustains desire.",
        "pressing_questions": None,
        "source_document_id": "doc-a",
        "original_filename": "gatsby.pdf",
        "page": 3,
        "governing_question": "How does desire depend on distance?",
        "created_at": "2026-07-03T12:00:00+00:00",
    }]
    packet = _packet([_annotation(id="mark-silent")], field_notes=field_notes)
    verdict = score_evidence_preservation(packet)
    assert verdict.verdict == PASS


# ── Boundaries: provider-free, no mutation, deterministic ──────────────────


def test_scorer_does_not_mutate_the_packet():
    _, packet, _, _ = _fixture_gatsby_clean()
    before = copy.deepcopy(packet)
    score_evidence_preservation(packet)
    assert packet == before


def test_scorer_is_deterministic():
    _, packet, _, _ = _fixture_dropped_evidence()
    first = score_evidence_preservation(packet)
    second = score_evidence_preservation(packet)
    assert first.to_dict() == second.to_dict()


# ── Report ─────────────────────────────────────────────────────────────────


def test_report_aggregates_and_is_deterministic():
    cases = []
    for build in _FIXTURES:
        name, packet, _, _ = build()
        cases.append((name, [score_evidence_preservation(packet)]))
    report_a = build_evaluation_report(cases, generated_at="2026-07-04T00:00:00+00:00")
    report_b = build_evaluation_report(
        list(reversed(cases)), generated_at="2026-07-04T00:00:00+00:00"
    )
    # Order-independent and byte-stable.
    assert report_a == report_b
    assert report_a["provider_free"] is True
    assert report_a["canonical_evidence_modified"] is False
    assert report_a["summary"] == {PASS: 1, FAIL: 1, NOT_APPLICABLE: 1}
    assert [case["case"] for case in report_a["cases"]] == sorted(
        case["case"] for case in report_a["cases"]
    )


# ── Verdict invariants ─────────────────────────────────────────────────────


def test_fail_verdict_requires_offending_or_explicit_reason():
    import pytest

    with pytest.raises(ValueError):
        ScorerVerdict(dimension="x", verdict=FAIL, reason="no offending given")


def test_verdict_requires_nonempty_reason():
    import pytest

    with pytest.raises(ValueError):
        ScorerVerdict(dimension="x", verdict=PASS, reason="   ")
