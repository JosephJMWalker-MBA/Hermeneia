"""Current exact packages and historical safe summaries have distinct boundaries.

All markers are synthetic. Current eligible P3 metadata is inspectable; awards
retain historical private packages while inspection keeps their summaries lean.
"""
from __future__ import annotations

import json
import socket

import pytest

import hermeneia.achievement_awards as awards
from hermeneia.narrative.provider_registry import ProviderRegistry
from hermeneia.perspective_execution_receipts import canonical_bytes
from hermeneia.study_lineage import project_study_lineage
from test_achievement_award_verification import _install
from test_perspective_achievements import study


PRIVATE_LABEL = "SYNTHETIC PRIVATE PERSPECTIVE LABEL"
PRIVATE_PURPOSE = "SYNTHETIC PRIVATE PERSPECTIVE PURPOSE"
PRIVATE_EXECUTION = "SYNTHETIC PRIVATE EXECUTION OBSERVATION"
RESPONSE = "SYNTHETIC OUTPUT NOT COPIED INTO THE AWARD PACKAGE"
ISSUED = "2026-10-01T11:00:00+00:00"
MARKERS = (PRIVATE_LABEL, PRIVATE_PURPOSE, PRIVATE_EXECUTION)


@pytest.fixture
def private_study(study):
    frame = study.saved(PRIVATE_LABEL, purpose=PRIVATE_PURPOSE)
    study.retained(frame, response=RESPONSE, execution={
        "provider_id": "synthetic", "model_id": "fixture-v1",
        "options": {"temperature": 0.7, "recorded_observation": PRIVATE_EXECUTION},
    })
    study.retained("close-reader", response=RESPONSE)
    return study


def _award_item(study, receipt):
    projection = project_study_lineage(study.conn)
    return next(item for item in projection["items"] if item["record"] == {
        "table": "achievement_awards", "key": {"id": receipt["award_id"]},
    })


@pytest.mark.parametrize("achievement", ["perspective_explorer", "second_opinion"])
def test_exact_earned_package_retains_private_definition_and_execution_metadata(private_study, achievement):
    before = tuple(private_study.conn.iterdump())
    package = awards.prepare_perspective_achievement_award(private_study.conn, achievement)
    assert package["assessment"]["finding"]["status"] == "earned"
    # This is the actual exact domain package, not a proposed public payload.
    encoded = canonical_bytes(package).decode("utf-8")
    assert all(marker in encoded for marker in MARKERS)
    assert RESPONSE not in encoded
    assert "What does this exact evidence support?" not in encoded
    private = next(value for value in package["adapter_basis"]["executions"]
                   if value["lineage_ref"]["provenance"]["perspective"]["definition"]["label"] == PRIVATE_LABEL)
    provenance = private["lineage_ref"]["provenance"]
    assert provenance["perspective"]["definition"]["label"] == PRIVATE_LABEL
    assert provenance["perspective"]["definition"]["purpose"] == PRIVATE_PURPOSE
    assert provenance["execution"]["options"]["recorded_observation"] == PRIVATE_EXECUTION
    assert tuple(private_study.conn.iterdump()) == before


@pytest.mark.parametrize("achievement", ["perspective_explorer", "second_opinion"])
def test_existing_award_summary_suppresses_private_package_even_with_eligible_evidence(private_study, achievement):
    receipt = _install(private_study, achievement, at=ISSUED)
    before = tuple(private_study.conn.iterdump())
    item = _award_item(private_study, receipt)
    assert item["record_data"]["award_id"] == receipt["award_id"]
    assert item["record_data"]["evaluation_status"] == "earned"
    assert item["record_data"]["issuer"] == {"kind": "hermeneia", "authorship": "derived"}
    assert item["contexts"]  # Eligible exact P3 links exist; previews stay lean.
    encoded = json.dumps(item)
    assert not any(marker in encoded for marker in MARKERS)
    assert "evidence_package" not in encoded and "receipt_json" not in encoded
    assert "purpose" not in encoded and "model_id" not in encoded
    assert item["provenance"]["references"] == [ref["record"] for ref in
        receipt["evidence_package"]["assessment"]["finding"]["evidence_refs"]]
    assert tuple(private_study.conn.iterdump()) == before


@pytest.mark.parametrize("achievement", ["perspective_explorer", "second_opinion"])
def test_exclusion_preserves_exact_private_history_while_award_summary_remains_safe(private_study, achievement):
    receipt = _install(private_study, achievement, at=ISSUED)
    original = private_study.conn.execute(
        "SELECT receipt_json FROM achievement_awards WHERE id=?", (receipt["award_id"],),
    ).fetchone()[0]
    assert all(marker in original for marker in MARKERS)
    private_study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    private_study.conn.commit()
    before = tuple(private_study.conn.iterdump())
    private_study.conn.execute("PRAGMA query_only=ON")
    item = _award_item(private_study, receipt)
    loaded = awards.load_achievement_award(private_study.conn, receipt["award_id"])
    assert canonical_bytes(loaded).decode() == original
    assert loaded["evidence_package_sha256"] == awards.evidence_package_digest(loaded["evidence_package"])
    assert item["record_data"]["award_id"] == receipt["award_id"]
    assert item["contexts"] == []
    assert not any(marker in json.dumps(item) for marker in MARKERS)
    assert tuple(private_study.conn.iterdump()) == before


def test_safe_summary_is_not_the_exact_approved_package_or_a_substitutable_receipt(private_study):
    receipt = _install(private_study, at=ISSUED)
    item = _award_item(private_study, receipt)
    summary = item["record_data"]
    package = receipt["evidence_package"]
    assert canonical_bytes(summary) != canonical_bytes(package)
    assert awards.evidence_package_digest(summary) != receipt["evidence_package_sha256"]
    with pytest.raises(awards.InvalidAward):
        awards.validate_evidence_package(summary)
    with pytest.raises(awards.InvalidAward):
        awards.validate_award_receipt(summary)
    assert summary["evidence_refs"] == [ref["record"] for ref in package["assessment"]["finding"]["evidence_refs"]]
    # The safe summary must not be represented as the exact approved package.
    assert set(summary) != set(package)


def test_current_package_metadata_is_already_visible_in_eligible_p3_lineage(private_study):
    package = awards.prepare_perspective_achievement_award(private_study.conn, "perspective_explorer")
    eligible = {item["record"]["key"]["id"]: item for item in project_study_lineage(private_study.conn)["items"]
                if item["record"]["table"] == "perspective_execution_receipts"}
    for execution in package["adapter_basis"]["executions"]:
        reference = execution["lineage_ref"]
        existing = eligible[reference["record"]["key"]["id"]]
        assert reference["provenance"]["perspective"] == existing["provenance"]["perspective"]
        assert reference["provenance"]["execution"] == existing["provenance"]["execution"]


def test_excluded_candidates_do_not_reenter_current_assessment_package(private_study):
    private_study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    private_study.conn.commit()
    from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
    from hermeneia.perspective_achievements import evaluate_perspective_achievements
    evidence = read_perspective_achievement_evidence(private_study.conn)
    result = evaluate_perspective_achievements(evidence)
    assert evidence.executions == ()
    assert all(item["status"] != "earned" and item["evidence_refs"] == [] for item in result["achievements"])
    assert not any(marker in json.dumps(result) for marker in MARKERS)


def test_boundary_reproduction_is_provider_free_read_only_and_does_not_issue(private_study, monkeypatch):
    receipt = _install(private_study, at=ISSUED)
    before = tuple(private_study.conn.iterdump())

    def forbidden(*args, **kwargs):
        pytest.fail("Disclosure witness reads must not issue, infer, or access providers/network")

    monkeypatch.setattr(awards, "materialize_perspective_achievement_award", forbidden)
    monkeypatch.setattr(ProviderRegistry, "create", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    private_study.conn.execute("PRAGMA query_only=ON")
    package = awards.prepare_perspective_achievement_award(private_study.conn, "perspective_explorer")
    loaded = awards.load_achievement_award(private_study.conn, receipt["award_id"])
    item = _award_item(private_study, receipt)
    assert package == loaded["evidence_package"]
    assert item["record_data"]["verification"]["receipt_integrity"] == "valid"
    assert private_study.conn.execute("SELECT COUNT(*) FROM achievement_awards").fetchone()[0] == 1
    assert tuple(private_study.conn.iterdump()) == before
