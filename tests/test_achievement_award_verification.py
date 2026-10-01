"""Historical checks distinguish immutable contradictions from snapshot loss."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import sqlite3

import pytest

from hermeneia.achievement_awards import (
    make_award_receipt, prepare_perspective_achievement_award,
)
from hermeneia.achievement_award_verification import verify_achievement_award
from hermeneia.perspective_execution_receipts import TABLE, canonical_bytes
from test_perspective_achievement_integrity import _drop_guard
from test_perspective_achievements import study


AWARD_TABLE = "achievement_awards"
ISSUED = "2026-09-30T11:00:00+00:00"


def _install(study, achievement="perspective_explorer", *, mutate=None, at=ISSUED):
    package = prepare_perspective_achievement_award(study.conn, achievement)
    if mutate:
        mutate(package)
    receipt = make_award_receipt(package, awarded_at=at)
    study.conn.execute(
        "INSERT INTO achievement_awards (id,achievement_id,rule_id,rule_version,receipt_json) VALUES (?,?,?,?,?)",
        (receipt["award_id"], receipt["achievement_id"], receipt["rule_id"],
         receipt["rule_version"], canonical_bytes(receipt).decode()),
    )
    study.conn.commit()
    return receipt


def _verify(study, award):
    before = tuple(study.conn.iterdump())
    result = verify_achievement_award(study.conn, award["award_id"])
    assert result["award_id"] == award["award_id"]
    assert tuple(study.conn.iterdump()) == before
    return result


@pytest.mark.parametrize("achievement", ["perspective_explorer", "second_opinion"])
def test_original_supported_snapshot_verifies_receipt_witness_and_full_replay(study, achievement):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    result = _verify(study, _install(study, achievement))
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "verified"
    assert result["historical_snapshot_replay"] == "verified"


def test_new_candidates_do_not_rewrite_original_pair_or_count_as_historical_replay(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    award = _install(study, "second_opinion")
    study.retained("contextual-reader", kept="2026-09-30T10:00:30+00:00")
    result = _verify(study, award)
    assert result["evidence_verification"] == "verified"
    assert result["historical_snapshot_replay"] == "unsupported"


@pytest.mark.parametrize("mutation", ["excluded", "metadata", "null_exclusion"])
def test_source_mutable_snapshot_drift_is_missing_coverage_and_preserves_award(study, mutation):
    study.retained()
    award = _install(study)
    if mutation == "excluded":
        study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    elif mutation == "null_exclusion":
        study.conn.execute("UPDATE source_documents SET excluded_from_analysis=NULL")
    else:
        study.conn.execute("UPDATE source_documents SET source_role='supporting'")
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "unverifiable_missing_coverage"
    assert result["historical_snapshot_replay"] == "unsupported"


@pytest.mark.parametrize("table", [TABLE, "source_extractions"])
def test_missing_selected_immutable_row_is_missing_evidence(study, table):
    study.retained()
    award = _install(study)
    _drop_guard(study.conn, table, "DELETE")
    study.conn.execute(f"DELETE FROM {table}")
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "unverifiable_missing_evidence"
    assert result["historical_snapshot_replay"] == "unsupported"


@pytest.mark.parametrize("table", [TABLE, "source_documents", "source_extractions"])
def test_missing_required_schema_is_missing_coverage(study, table):
    study.retained()
    award = _install(study)
    study.conn.execute(f"DROP TABLE {table}")
    study.conn.commit()
    assert _verify(study, award)["evidence_verification"] == "unverifiable_missing_coverage"


def test_missing_required_column_is_missing_coverage(study):
    study.retained()
    award = _install(study)
    study.conn.execute("ALTER TABLE source_documents DROP COLUMN excluded_from_analysis")
    study.conn.commit()
    assert _verify(study, award)["evidence_verification"] == "unverifiable_missing_coverage"


def test_immutable_dependency_byte_contradiction_is_invalid_evidence(study):
    study.retained()
    award = _install(study)
    _drop_guard(study.conn, "source_extractions", "UPDATE")
    study.conn.execute("UPDATE source_extractions SET raw_text='Altered forensic bytes'")
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "invalid_evidence"
    assert any(check["state"] == "invalid_evidence" for check in result["checks"])


def test_known_invalidity_precedes_other_missing_evidence_and_coverage(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    award = _install(study, "second_opinion")
    _drop_guard(study.conn, TABLE, "UPDATE")
    selected = award["evidence_package"]["witness_bindings"]
    study.conn.execute(f"UPDATE {TABLE} SET receipt_json='{{}}' WHERE id=?", (selected[0]["receipt_id"],))
    _drop_guard(study.conn, TABLE, "DELETE")
    study.conn.execute(f"DELETE FROM {TABLE} WHERE id=?", (selected[1]["receipt_id"],))
    study.conn.execute("DROP TABLE source_extractions")
    study.conn.commit()
    result = _verify(study, award)
    assert result["evidence_verification"] == "invalid_evidence"
    states = {check["state"] for check in result["checks"]}
    assert {"invalid_evidence", "unverifiable_missing_evidence", "unverifiable_missing_coverage"} <= states


def test_p3_exact_stored_bytes_remain_required_even_when_noncanonical_json_means_same_object(study):
    p3 = study.retained()
    award = _install(study)
    _drop_guard(study.conn, TABLE, "UPDATE")
    study.conn.execute(f"UPDATE {TABLE} SET receipt_json=?", (json.dumps(p3, indent=2),))
    study.conn.commit()
    assert _verify(study, award)["evidence_verification"] == "invalid_evidence"


def test_family_failure_recorded_before_explorer_award_is_diagnostic_without_new_gate(study):
    root = study.saved("Original frame")
    child = study.saved("Executed revision", purpose="Challenge source claims.", predecessor=root)
    study.retained(child)
    _drop_guard(study.conn, "perspectives", "UPDATE")
    study.conn.execute("UPDATE perspectives SET identity_scheme='perspective-label-v1' WHERE id=?", (root["id"],))
    study.conn.commit()
    award = _install(study)
    assert award["evidence_package"]["assessment"]["diagnostics"]
    result = _verify(study, award)
    assert result["evidence_verification"] == "verified"
    assert result["historical_snapshot_replay"] == "verified"


def test_second_opinion_requires_unchanged_saved_family_evidence(study):
    root = study.saved("Original method")
    child = study.saved("Executed revision", purpose="Challenge source claims.", predecessor=root)
    study.retained(child)
    study.retained("close-reader")
    award = _install(study, "second_opinion")
    _drop_guard(study.conn, "perspectives", "UPDATE")
    study.conn.execute("UPDATE perspectives SET definition_fingerprint='sha256:contradiction' WHERE id=?", (root["id"],))
    study.conn.commit()
    assert _verify(study, award)["evidence_verification"] == "invalid_evidence"


def test_unknown_historical_evaluator_is_preserved_without_fabricated_replay(study):
    study.retained()
    award = _install(study, mutate=lambda p: p["assessment"].__setitem__("evaluator_version", "99.0.0"))
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "unverifiable_unsupported_rule"
    assert result["historical_snapshot_replay"] == "unsupported"


def test_unavailable_historical_prompt_implementation_is_unsupported(study, monkeypatch):
    study.retained()
    award = _install(study)
    import hermeneia.perspective_achievement_evidence as adapter
    def unsupported(*args, **kwargs):
        raise AssertionError("Unsupported template must not execute")
    monkeypatch.setattr(adapter, "build_perspective_prompt", unsupported)
    assert _verify(study, award)["evidence_verification"] == "unverifiable_unsupported_rule"


def test_invalid_award_bytes_do_not_become_trusted_history(study):
    study.retained()
    award = _install(study)
    _drop_guard(study.conn, AWARD_TABLE, "UPDATE")
    changed = deepcopy(award)
    changed["awarded_at"] = "2026-09-30T12:00:00+00:00"
    study.conn.execute("UPDATE achievement_awards SET receipt_json=?", (canonical_bytes(changed).decode(),))
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "invalid"
    assert result["evidence_verification"] != "verified"


def test_ordering_anomaly_is_reported_without_clamping_truthful_award_time(study):
    study.retained()
    award = _install(study, at="2026-09-29T00:00:00+00:00")
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert any(check["reason_code"] == "AWARD_TIME_PRECEDES_EARNED_TIME" for check in result["checks"])


def test_verifier_preserves_pending_caller_transaction_and_never_initializes(study):
    study.retained()
    award = _install(study)
    study.conn.execute("CREATE TABLE caller_work(value TEXT)")
    study.conn.commit()
    study.conn.execute("INSERT INTO caller_work VALUES ('pending')")
    before = tuple(study.conn.iterdump())
    study.conn.execute("PRAGMA query_only=ON")
    result = verify_achievement_award(study.conn, award["award_id"])
    assert result["receipt_integrity"] == "valid"
    assert study.conn.in_transaction
    assert tuple(study.conn.iterdump()) == before
    study.conn.rollback()
    empty = sqlite3.connect(":memory:")
    empty.execute("PRAGMA query_only=ON")
    result = verify_achievement_award(empty, award["award_id"])
    assert result["receipt_integrity"] == "unsupported"
    assert result["evidence_verification"] == "unverifiable_missing_coverage"
    assert not empty.execute("SELECT name FROM sqlite_master").fetchall()
    empty.close()


@pytest.mark.parametrize("field", ["dependency_evidence", "eligibility_observations"])
def test_rehashed_incomplete_capture_cannot_claim_verified_evidence(study, field):
    study.retained()
    def strip(package):
        execution = package["adapter_basis"]["executions"][0]
        execution[field] = []
        validated = package["assessment"]["finding"]["validated_evidence"][0]
        validated["dependency_evidence" if field == "dependency_evidence" else "eligibility_observations"] = []
        package["assessment"]["evidence_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(package["adapter_basis"])).hexdigest()
    award = _install(study, mutate=strip)
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "unverifiable_missing_coverage"
    assert result["historical_snapshot_replay"] == "unsupported"


def test_rehashed_selected_lineage_metadata_must_match_exact_p3_run(study):
    study.retained()
    def alter(package):
        reference = package["adapter_basis"]["executions"][0]["lineage_ref"]
        reference["provenance"]["execution"]["model_id"] = "Unrelated recorded model"
        package["assessment"]["finding"]["evidence_refs"][0] = deepcopy(reference)
        package["assessment"]["evidence_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(package["adapter_basis"])).hexdigest()
    award = _install(study, mutate=alter)
    assert _verify(study, award)["evidence_verification"] == "invalid_evidence"


def test_exact_basis_with_contradictory_assessment_is_invalid_replay(study):
    study.retained()
    award = _install(study, mutate=lambda p: p["assessment"]["finding"].__setitem__("reason", "Contradictory captured evaluator output"))
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "verified"
    assert result["historical_snapshot_replay"] == "invalid"


def test_source_immutable_hash_contradiction_survives_other_missing_ancestor(study):
    study.retained()
    award = _install(study)
    _drop_guard(study.conn, "source_documents", "UPDATE")
    study.conn.execute("UPDATE source_documents SET file_hash='immutable-hash-contradiction'")
    _drop_guard(study.conn, "source_extractions", "DELETE")
    study.conn.execute("DELETE FROM source_extractions")
    study.conn.commit()
    result = _verify(study, award)
    assert result["evidence_verification"] == "invalid_evidence"
    states = {check["state"] for check in result["checks"]}
    assert "unverifiable_missing_evidence" in states
    assert "unverifiable_missing_coverage" in states


def test_mutable_highlight_edit_is_snapshot_loss_and_does_not_reinterpret_p3(study):
    from hermeneia.scope_resolution import resolve_scope_for_provider
    from test_scope_resolution import _selection_scope
    study.conn.execute(
        "INSERT INTO reader_highlights (id,source_document_id,page,source_locator,selected_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("historical-mark", study.seed["doc_id"], study.seed["page"], study.seed["locators"][0],
         "Original mutable mark", ISSUED, ISSUED),
    )
    study.conn.commit()
    selection = _selection_scope(study.seed, text="")
    selection["supporting"] = {"highlights": {"include": True, "ids": ["historical-mark"]}}
    scope = resolve_scope_for_provider(study.conn, selection)
    p3 = study.retained(scope=scope)
    award = _install(study)
    study.conn.execute("UPDATE reader_highlights SET selected_text='Later edited mark', status='dismissed'")
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "unverifiable_missing_coverage"
    assert result["historical_snapshot_replay"] == "unsupported"
    assert study.conn.execute(f"SELECT receipt_json FROM {TABLE} WHERE id=?", (p3["id"],)).fetchone()[0] == canonical_bytes(p3).decode()


def test_verification_is_stable_under_database_row_order(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    award = _install(study, "second_opinion")
    before = verify_achievement_award(study.conn, award["award_id"])
    study.conn.execute("PRAGMA reverse_unordered_selects=ON")
    assert verify_achievement_award(study.conn, award["award_id"]) == before


def test_unknown_receipt_wire_format_is_unsupported_without_earned_provenance(study):
    study.retained()
    award = _install(study)
    changed = deepcopy(award)
    changed["schema"] = "hermeneia.perspective-achievement-award/v99"
    _drop_guard(study.conn, AWARD_TABLE, "UPDATE")
    study.conn.execute("UPDATE achievement_awards SET receipt_json=?", (canonical_bytes(changed).decode(),))
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "unsupported"
    assert result["evidence_verification"] == "unverifiable_unsupported_rule"
    assert result["historical_snapshot_replay"] == "unsupported"


def test_replay_implementation_error_retains_known_immutable_invalidity(study, monkeypatch):
    study.retained()
    award = _install(study)
    _drop_guard(study.conn, "source_extractions", "UPDATE")
    study.conn.execute("UPDATE source_extractions SET raw_text='Known immutable contradiction'")
    study.conn.commit()
    import hermeneia.achievement_award_verification as verification
    def failed_replay(*args, **kwargs):
        raise RuntimeError("Unavailable replay implementation")
    monkeypatch.setattr(verification, "evaluate_perspective_achievements", failed_replay)
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "invalid_evidence"
    assert result["historical_snapshot_replay"] == "unsupported"
    assert any(check["reason_code"] == "IMMUTABLE_ROW_DIGEST_MISMATCH" for check in result["checks"])


def test_available_immutable_contradiction_is_retained_when_other_required_column_is_missing(study):
    study.retained()
    award = _install(study)
    _drop_guard(study.conn, "source_documents", "UPDATE")
    study.conn.execute("UPDATE source_documents SET file_hash='Known immutable contradiction'")
    study.conn.execute("ALTER TABLE source_documents DROP COLUMN excluded_from_analysis")
    study.conn.commit()
    result = _verify(study, award)
    assert result["evidence_verification"] == "invalid_evidence"
    assert any(check["state"] == "unverifiable_missing_coverage" for check in result["checks"])


def test_missing_award_wire_column_is_unsupported_coverage_without_repair(study):
    study.retained()
    award = _install(study)
    study.conn.execute("ALTER TABLE achievement_awards DROP COLUMN receipt_json")
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "unsupported"
    assert result["evidence_verification"] == "unverifiable_missing_coverage"


def test_malformed_ancestor_reference_keeps_negative_findings_json_safe(study):
    study.retained()
    award = _install(study)
    _drop_guard(study.conn, "source_extractions", "UPDATE")
    study.conn.execute("UPDATE source_extractions SET document_id=?", (sqlite3.Binary(b"PRIVATE INVALID ID"),))
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "invalid_evidence"
    assert "PRIVATE INVALID ID" not in json.dumps(result)


def test_unsupported_rule_does_not_hide_known_immutable_family_contradiction(study):
    root = study.saved("Original root")
    left = study.saved("Executed child", purpose="Inspect exact evidence.", predecessor=root)
    right = study.saved("Different root", purpose="Challenge exact evidence.")
    study.retained(left)
    study.retained(right)
    award = _install(study, "second_opinion", mutate=lambda p:
                     p["assessment"].__setitem__("evaluator_version", "99.0.0"))
    _drop_guard(study.conn, "perspectives", "UPDATE")
    study.conn.execute("UPDATE perspectives SET name='Altered immutable ancestor' WHERE id=?", (root["id"],))
    study.conn.commit()
    result = _verify(study, award)
    assert result["receipt_integrity"] == "valid"
    assert result["evidence_verification"] == "invalid_evidence"
    assert any(check["reason_code"] == "IMMUTABLE_ROW_DIGEST_MISMATCH" for check in result["checks"])
    assert any(check["state"] == "unverifiable_unsupported_rule" for check in result["checks"])
