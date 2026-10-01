"""Awards expose a terminal safe summary, never their private assessment data."""
from __future__ import annotations

from copy import deepcopy
import json
import sqlite3

import pytest

from hermeneia.capabilities import evaluate_capabilities
from hermeneia.guided_study_cycle import project_guided_study_cycle
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
from hermeneia.perspective_achievements import evaluate_perspective_achievements
from hermeneia.perspective_execution_receipts import TABLE
from hermeneia.study_lineage import project_study_lineage, serialize_projection
from test_achievement_award_verification import _install
from test_perspective_achievement_integrity import _drop_guard
from test_perspective_achievements import study


def _awards(projection):
    return [item for item in projection["items"] if item["record"]["table"] == "achievement_awards"]


def test_award_is_derived_record_with_original_issuance_time_and_lean_evidence(study):
    study.retained()
    receipt = _install(study)
    projection = project_study_lineage(study.conn)
    item, = _awards(projection)
    assert item["record"] == {"table": "achievement_awards", "key": {"id": receipt["award_id"]}}
    assert (item["record_type"], item["event"], item["authorship"]) == ("perspective_achievement_award", "recorded", "derived")
    assert item["timestamp"]["value"] == receipt["awarded_at"]
    assert item["record_data"]["earned_at"] == receipt["earned_at"]
    assert item["record_data"]["issuer"] == {"kind": "hermeneia", "authorship": "derived"}
    assert item["record_data"]["evidence_refs"] == [ref["record"] for ref in receipt["evidence_package"]["assessment"]["finding"]["evidence_refs"]]
    assert all(set(ref) == {"table", "key"} for ref in item["provenance"]["references"])
    assert item["record_data"]["verification"]["receipt_integrity"] == "valid"
    assert item["record_data"]["verification"]["evidence_verification"] == "not_performed"
    assert "agreement" in item["provenance"]["basis"].lower()
    encoded = json.dumps(item)
    assert "evidence_package" not in encoded
    assert "Exact synthetic proposal" not in encoded
    assert "What does this exact evidence support" not in encoded
    assert "purpose" not in encoded and "model_id" not in encoded


def test_excluded_descendants_cannot_leak_from_private_award_but_summary_survives(study):
    secret = "PRIVATE FRAME LABEL IN RECEIPT"
    saved = study.saved(secret, purpose="PRIVATE PURPOSE IN RECEIPT")
    study.retained(saved, execution={"provider_id": "PRIVATE PROVIDER", "model_id": "PRIVATE MODEL"}, response="PRIVATE RESPONSE")
    receipt = _install(study)
    study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    study.conn.commit()
    projection = project_study_lineage(study.conn)
    item, = _awards(projection)
    assert item["record"]["key"]["id"] == receipt["award_id"]
    assert item["contexts"] == []
    assert not [i for i in projection["items"] if i["record"]["table"] == TABLE]
    serialized = json.dumps(item)
    assert all(value not in serialized for value in [secret, "PRIVATE PURPOSE", "PRIVATE PROVIDER", "PRIVATE MODEL", "PRIVATE RESPONSE"])


def test_missing_ancestor_preserves_safe_summary_with_no_receipt_link(study):
    study.retained()
    _install(study)
    _drop_guard(study.conn, "source_extractions", "DELETE")
    study.conn.execute("DELETE FROM source_extractions")
    study.conn.commit()
    item, = _awards(project_study_lineage(study.conn))
    assert item["contexts"] == []
    assert item["record_data"]["verification"]["historical_snapshot_replay"] == "unsupported"


def test_malformed_award_is_omitted_with_bounded_diagnostic(study):
    study.retained()
    _install(study)
    _drop_guard(study.conn, "achievement_awards", "UPDATE")
    study.conn.execute("UPDATE achievement_awards SET receipt_json='PRIVATE MALFORMED CONTENT'")
    study.conn.commit()
    projection = project_study_lineage(study.conn)
    assert _awards(projection) == []
    assert projection["coverage"]["omitted"]["achievement_awards"] == 1
    assert any(d["record"]["table"] == "achievement_awards" and d["state"] == "invalid" for d in projection["coverage"]["diagnostics"])
    assert "PRIVATE MALFORMED CONTENT" not in json.dumps(projection)


def test_projection_does_not_invoke_recursive_historical_verifier(study, monkeypatch):
    study.retained()
    _install(study)
    import hermeneia.achievement_award_verification as verification
    def recursive(*args, **kwargs):
        raise AssertionError("Lineage must not call verifier which calls adapter which projects Lineage")
    monkeypatch.setattr(verification, "verify_achievement_award", recursive)
    assert _awards(project_study_lineage(study.conn))
    assert evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))["achievements"][0]["status"] == "earned"


def test_award_rows_do_not_change_p1_p2_or_perspective_evaluation(study):
    study.retained()
    before_lineage = project_study_lineage(study.conn)
    before = evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))
    _install(study)
    after_lineage = project_study_lineage(study.conn)
    assert evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn)) == before
    assert evaluate_capabilities(after_lineage) == evaluate_capabilities(before_lineage)
    assert project_guided_study_cycle(after_lineage) == project_guided_study_cycle(before_lineage)
    only_awards = deepcopy(after_lineage)
    only_awards["items"] = _awards(after_lineage)
    empty = deepcopy(only_awards)
    empty["items"] = []
    assert evaluate_capabilities(only_awards) == evaluate_capabilities(empty)
    assert project_guided_study_cycle(only_awards) == project_guided_study_cycle(empty)


def test_lineage_is_read_only_and_stable_under_database_row_order(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    _install(study, "perspective_explorer")
    _install(study, "second_opinion")
    before = tuple(study.conn.iterdump())
    study.conn.execute("PRAGMA query_only=ON")
    normal = serialize_projection(project_study_lineage(study.conn))
    study.conn.execute("PRAGMA reverse_unordered_selects=ON")
    assert serialize_projection(project_study_lineage(study.conn)) == normal
    study.conn.execute("PRAGMA reverse_unordered_selects=OFF")
    assert tuple(study.conn.iterdump()) == before


def test_award_coverage_limits_do_not_change_legacy_capability_or_guided_steps(study):
    empty = project_study_lineage(study.conn)
    empty["items"] = []
    empty["coverage"].update(missing_tables=[], missing_columns={}, omitted={})
    original = evaluate_capabilities(empty)
    original_steps = project_guided_study_cycle(empty)["steps"]
    for state in ("missing", "malformed", "missing_columns"):
        altered = deepcopy(empty)
        if state == "missing":
            altered["coverage"]["missing_tables"] = ["achievement_awards"]
        elif state == "missing_columns":
            altered["coverage"]["missing_columns"] = {"achievement_awards": ["receipt_json"]}
        else:
            altered["coverage"]["omitted"] = {"achievement_awards": 1}
        result = evaluate_capabilities(altered)
        assert result["capabilities"] == original["capabilities"]
        assert result["lineage_coverage"] == altered["coverage"]
        assert project_guided_study_cycle(altered)["steps"] == original_steps


@pytest.mark.parametrize("field", ["id", "achievement_id", "rule_id", "rule_version", "receipt_json"])
def test_blob_award_columns_are_safe_invalid_diagnostics_without_json_disclosure(study, field):
    study.retained()
    _install(study)
    _drop_guard(study.conn, "achievement_awards", "UPDATE")
    study.conn.execute(f"UPDATE achievement_awards SET {field}=?", (sqlite3.Binary(b"PRIVATE BINARY DATA"),))
    study.conn.commit()
    projection = project_study_lineage(study.conn)
    assert _awards(projection) == []
    assert projection["coverage"]["omitted"]["achievement_awards"] == 1
    assert projection["coverage"]["diagnostics"]
    assert b"PRIVATE BINARY DATA" not in serialize_projection(projection)
