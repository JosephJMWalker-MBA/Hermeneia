"""Thin explicit Perspective award API over synthetic committed P3 evidence."""
from __future__ import annotations

from copy import deepcopy
import json
import socket
import sqlite3

import pytest

import hermeneia.achievement_awards as awards
from hermeneia.capabilities import evaluate_capabilities
from hermeneia.achievement_award_verification import verify_achievement_award
from hermeneia.narrative.provider_registry import ProviderRegistry
from hermeneia.perspective_execution_receipts import TABLE as P3_TABLE, canonical_bytes
from hermeneia.web.app import create_app
from test_achievement_award_verification import _install
from test_achievement_awards import _digest, _install_synthetic_v2
from test_perspective_achievement_integrity import _drop_guard, _tamper
from test_perspective_achievements import study
from test_study_lineage_api import _rollback_journal, _snapshot


BASE = "/api/achievements/perspective"
EXPLORER = "perspective_explorer"
SECOND = "second_opinion"
VERSION = "1.0.0"
ISSUED = "2026-10-01T11:00:00+00:00"


@pytest.fixture
def client(study):
    app = create_app(db_path=study.path)
    app.testing = True
    return app.test_client()


def _assessment(client, achievement=EXPLORER):
    return client.get(f"{BASE}/{achievement}/assessment")


def _approval(package):
    finding = package["assessment"]["finding"]
    return {"rule_id": finding["rule_id"], "rule_version": finding["rule_version"],
            "assessment_package_sha256": awards.evidence_package_digest(package)}


def _issue(client, study, achievement=EXPLORER):
    package = awards.prepare_perspective_achievement_award(study.conn, achievement)
    return client.post(f"{BASE}/{achievement}/award", json=_approval(package))


def _stored(study):
    return [tuple(row) for row in study.conn.execute("SELECT * FROM achievement_awards ORDER BY id")]


def _dump(study):
    return tuple(study.conn.iterdump())


def _stable_durable_files(study):
    # Close the fixture's live WAL connection before changing test journal mode.
    # The read boundary starts after this setup and checks every file unchanged.
    study.conn.close()
    _rollback_journal(study.path)
    study.conn = sqlite3.connect(study.path)
    study.conn.row_factory = sqlite3.Row


def _no_calls(*args, **kwargs):
    pytest.fail("A read must not issue, invoke a provider, or use network access")


def _assert_summary(summary, receipt):
    for key in ("award_id", "achievement_id", "rule_id", "rule_version", "evaluation_status",
                "earned_at", "awarded_at", "issuer"):
        assert summary[key] == receipt[key]
    assert "evidence_package" not in summary and "receipt_json" not in summary
    assert summary["evidence_refs"] == [ref["record"] for ref in
        receipt["evidence_package"]["assessment"]["finding"]["evidence_refs"]]


@pytest.mark.parametrize("achievement,count", [(EXPLORER, 1), (SECOND, 2)])
def test_earned_assessment_returns_exact_domain_package_and_approval_digest(study, client, achievement, count):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    expected = awards.prepare_perspective_achievement_award(study.conn, achievement)
    before = _dump(study)
    response = _assessment(client, achievement)
    assert response.status_code == 200
    body = response.get_json()
    for key in ("achievement_id", "rule_id", "rule_version", "status", "reason_code", "reason"):
        assert body[key] == expected["assessment"]["finding"][key]
    assert body["assessment_package"] == expected
    assert body["assessment_package_sha256"] == awards.evidence_package_digest(expected)
    assert len(expected["witness_bindings"]) == count
    assert body["coverage"] == expected["assessment"]["coverage"]
    assert body["limitations"] == expected["assessment"]["limitations"]
    assert _dump(study) == before and _stored(study) == []


@pytest.mark.parametrize("state", ["not_earned", "unsupported_due_to_missing_coverage", "invalid_evidence"])
def test_non_earned_assessment_preserves_structured_state_without_award(study, client, state):
    if state == "unsupported_due_to_missing_coverage":
        study.conn.execute(f"DROP TABLE {P3_TABLE}")
        study.conn.commit()
    elif state == "invalid_evidence":
        retained = study.retained()
        _tamper(study, retained, lambda r: r["run"].__setitem__("response", "Tampered bytes"))
    before = _dump(study)
    response = _assessment(client)
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == state
    assert body["reason_code"] and body["reason"]
    assert body["assessment_package"] is None
    assert body["assessment_package_sha256"] is None
    assert isinstance(body["coverage"], dict) and isinstance(body["limitations"], list)
    assert _dump(study) == before and _stored(study) == []


@pytest.mark.parametrize("achievement", [EXPLORER, SECOND])
def test_explicit_approved_post_records_award_and_preserves_p3(study, client, monkeypatch, achievement):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    monkeypatch.setattr(awards, "_now", lambda: ISSUED)
    p3 = [tuple(row) for row in study.conn.execute(f"SELECT * FROM {P3_TABLE} ORDER BY id")]
    response = _issue(client, study, achievement)
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "recorded"
    assert body["receipt_representation"] == "safe_summary" and "receipt" not in body
    receipt = awards.load_achievement_award(study.conn, body["award_id"])
    _assert_summary(body["receipt_projection"], receipt)
    assert receipt["achievement_id"] == achievement and receipt["awarded_at"] == ISSUED
    assert len(_stored(study)) == 1
    assert [tuple(row) for row in study.conn.execute(f"SELECT * FROM {P3_TABLE} ORDER BY id")] == p3


def test_prepare_stale_post_and_fresh_prepare_explicit_flow(study, client):
    study.retained()
    first = _assessment(client).get_json()
    request_a = {"rule_id": first["rule_id"], "rule_version": first["rule_version"],
                 "assessment_package_sha256": first["assessment_package_sha256"]}
    study.retained("skeptical-reader")
    prior = _dump(study)
    stale = client.post(f"{BASE}/{EXPLORER}/award", json=request_a)
    assert stale.status_code == 409 and stale.get_json()["error"]
    assert _dump(study) == prior and _stored(study) == []
    second = _assessment(client).get_json()
    assert second["assessment_package_sha256"] != first["assessment_package_sha256"]
    recorded = client.post(f"{BASE}/{EXPLORER}/award", json={"rule_id": second["rule_id"],
        "rule_version": second["rule_version"], "assessment_package_sha256": second["assessment_package_sha256"]})
    assert recorded.status_code == 201 and recorded.get_json()["status"] == "recorded"


@pytest.mark.parametrize("digest", [None, "", "sha256:" + "A" * 64, "sha256:bad", "0" * 64, [], {}])
def test_malformed_digest_refused_without_writes(study, client, digest):
    study.retained()
    prior = _dump(study)
    response = client.post(f"{BASE}/{EXPLORER}/award", json={"rule_id": "achievement." + EXPLORER,
        "rule_version": VERSION, "assessment_package_sha256": digest})
    assert response.status_code == 400 and response.get_json()["error"]
    assert _dump(study) == prior


@pytest.mark.parametrize("body", [None, [], {}, {"rule_id": "achievement.perspective_explorer"},
    {"rule_id": "achievement.perspective_explorer", "rule_version": VERSION},
    {"rule_id": "achievement.perspective_explorer", "rule_version": VERSION,
     "assessment_package_sha256": "sha256:" + "0" * 64, "receipt": {"status": "earned"}},
    {"rule_id": "achievement.perspective_explorer", "rule_version": VERSION,
     "assessment_package_sha256": "sha256:" + "0" * 64, "actor": "Invented steward"}])
def test_request_requires_only_exact_explicit_intent_fields(study, client, body):
    study.retained()
    before = _dump(study)
    response = client.post(f"{BASE}/{EXPLORER}/award", json=body)
    assert response.status_code == 400 and response.get_json()["error"]
    assert _dump(study) == before


@pytest.mark.parametrize("achievement,rule,version,status", [
    ("invented", "achievement.invented", VERSION, 404),
    (EXPLORER, "achievement.second_opinion", VERSION, 409),
    (EXPLORER, "achievement.perspective_explorer", "99.0.0", 409),
])
def test_unknown_or_wrong_rule_intent_refused(study, client, achievement, rule, version, status):
    study.retained()
    before = _dump(study)
    response = client.post(f"{BASE}/{achievement}/award", json={"rule_id": rule,
        "rule_version": version, "assessment_package_sha256": "sha256:" + "0" * 64})
    assert response.status_code == status and response.get_json()["error"]
    assert _dump(study) == before


@pytest.mark.parametrize("state", ["not_earned", "unsupported_due_to_missing_coverage", "invalid_evidence"])
def test_non_earned_post_refuses_and_preserves_committed_evidence(study, client, state):
    if state == "unsupported_due_to_missing_coverage":
        study.conn.execute(f"DROP TABLE {P3_TABLE}")
        study.conn.commit()
    elif state == "invalid_evidence":
        retained = study.retained()
        _tamper(study, retained, lambda r: r["run"].__setitem__("response", "Invalid digest"))
    before = _dump(study)
    response = client.post(f"{BASE}/{EXPLORER}/award", json={"rule_id": "achievement." + EXPLORER,
        "rule_version": VERSION, "assessment_package_sha256": "sha256:" + "0" * 64})
    assert response.status_code == 409 and response.get_json()["error"]
    assert _dump(study) == before


def test_idempotent_retry_preserves_id_times_bytes_and_original_witness(study, client, monkeypatch):
    original = study.retained()
    request = _approval(awards.prepare_perspective_achievement_award(study.conn, EXPLORER))
    monkeypatch.setattr(awards, "_now", lambda: ISSUED)
    first = client.post(f"{BASE}/{EXPLORER}/award", json=request)
    assert first.status_code == 201
    identifier = first.get_json()["award_id"]
    issued = awards.load_achievement_award(study.conn, identifier)
    initial_rows = _stored(study)
    monkeypatch.setattr(awards, "_now", _no_calls)
    retry = client.post(f"{BASE}/{EXPLORER}/award", json=request)
    assert retry.status_code == 200 and retry.get_json()["status"] == "already_recorded"
    assert retry.get_json()["award_id"] == identifier
    assert retry.get_json()["receipt_projection"] == first.get_json()["receipt_projection"]
    assert _stored(study) == initial_rows
    study.retained("skeptical-reader", kept="2026-09-30T10:00:30+00:00")
    changed = awards.prepare_perspective_achievement_award(study.conn, EXPLORER)
    assert changed["assessment"]["finding"]["qualifying_receipt_ids"] != [original["id"]]
    later = client.post(f"{BASE}/{EXPLORER}/award", json=_approval(changed))
    assert later.status_code == 200 and later.get_json()["status"] == "already_recorded"
    assert later.get_json()["award_id"] == identifier
    assert _stored(study) == initial_rows
    assert canonical_bytes(awards.load_achievement_award(study.conn, identifier)) == canonical_bytes(issued)


def test_list_deterministic_with_same_timestamp_and_safe_summary(study, client):
    study.retained("close-reader", response="PRIVATE MODEL OUTPUT NEVER IN AWARD API")
    study.retained("skeptical-reader", response="PRIVATE MODEL OUTPUT NEVER IN AWARD API")
    records = [_install(study, SECOND), _install(study, EXPLORER)]
    expected = sorted(records, key=lambda receipt: (receipt["awarded_at"], receipt["award_id"]))
    before = _dump(study)
    first, repeat = client.get(f"{BASE}/awards"), client.get(f"{BASE}/awards")
    assert first.status_code == repeat.status_code == 200 and first.data == repeat.data
    summaries = first.get_json()["awards"]
    assert [row["award_id"] for row in summaries] == [row["award_id"] for row in expected]
    for summary, receipt in zip(summaries, expected):
        _assert_summary(summary, receipt)
    for hidden in (b"PRIVATE MODEL OUTPUT", b"Alpha beta begins.", b"Middle line with Unicode", b"prompt"):
        assert hidden not in first.data
    assert _dump(study) == before


def test_detail_preserves_historical_semantics_without_current_eligibility(study, client, monkeypatch):
    study.retained()
    receipt = _install(study)
    import hermeneia.perspective_achievement_evidence as adapter
    import hermeneia.perspective_achievements as evaluator
    monkeypatch.setattr(adapter, "read_perspective_achievement_evidence", _no_calls)
    monkeypatch.setattr(evaluator, "evaluate_perspective_achievements", _no_calls)
    before = _dump(study)
    response = client.get(f"{BASE}/awards/{receipt['award_id']}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["award_id"] == receipt["award_id"] and body["receipt_representation"] == "safe_summary"
    assert "receipt" not in body
    _assert_summary(body["receipt_projection"], receipt)
    assert _dump(study) == before


@pytest.mark.parametrize("suffix", ["", "/verification"])
def test_unknown_award_returns_bounded_not_found(study, client, suffix):
    before = _dump(study)
    response = client.get(f"{BASE}/awards/achievement-award:sha256:{'0' * 64}{suffix}")
    assert response.status_code == 404 and response.get_json()["error"]
    assert _dump(study) == before


def test_malformed_award_detail_fails_closed_without_rewrite(study, client):
    study.retained()
    receipt = _install(study)
    _drop_guard(study.conn, "achievement_awards", "UPDATE")
    study.conn.execute("UPDATE achievement_awards SET receipt_json='{}'")
    study.conn.commit()
    before = _dump(study)
    response = client.get(f"{BASE}/awards/{receipt['award_id']}")
    assert response.status_code == 409 and response.get_json()["error"]
    assert _dump(study) == before


@pytest.mark.parametrize("state", ["verified", "unverifiable_missing_evidence",
    "unverifiable_missing_coverage", "invalid_evidence", "unverifiable_unsupported_rule"])
def test_verification_preserves_exact_three_domain_dimensions(study, client, state):
    study.retained()
    mutation = (lambda p: p["assessment"].__setitem__("evaluator_version", "99.0.0")) if state == "unverifiable_unsupported_rule" else None
    receipt = _install(study, mutate=mutation)
    if state == "unverifiable_missing_evidence":
        _drop_guard(study.conn, P3_TABLE, "DELETE")
        study.conn.execute(f"DELETE FROM {P3_TABLE}")
    elif state == "unverifiable_missing_coverage":
        study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    elif state == "invalid_evidence":
        _drop_guard(study.conn, "source_extractions", "UPDATE")
        study.conn.execute("UPDATE source_extractions SET raw_text='Changed bytes'")
    study.conn.commit()
    expected = verify_achievement_award(study.conn, receipt["award_id"])
    before = _dump(study)
    response = client.get(f"{BASE}/awards/{receipt['award_id']}/verification")
    assert response.status_code == 200
    body = response.get_json()
    assert body == expected and body["receipt_integrity"] == "valid"
    assert body["evidence_verification"] == state
    assert body["historical_snapshot_replay"] in {"verified", "unsupported", "invalid"}
    assert "valid" not in body and _dump(study) == before


def test_unknown_historical_evaluator_detail_stays_readable(study, client):
    study.retained()
    receipt = _install(study, mutate=lambda p: p["assessment"].__setitem__("evaluator_version", "99.0.0"))
    response = client.get(f"{BASE}/awards/{receipt['award_id']}")
    assert response.status_code == 200
    _assert_summary(response.get_json()["receipt_projection"], receipt)


@pytest.mark.parametrize("route", ["assessment", "list", "detail", "verification", "lineage", "guide"])
def test_get_never_materializes_and_preserves_rows_dump_and_files(study, client, monkeypatch, route):
    study.retained()
    receipt = _install(study)
    paths = {"assessment": f"{BASE}/{EXPLORER}/assessment", "list": f"{BASE}/awards",
        "detail": f"{BASE}/awards/{receipt['award_id']}",
        "verification": f"{BASE}/awards/{receipt['award_id']}/verification",
        "lineage": "/api/study-lineage", "guide": "/api/guided-study-cycle"}
    _stable_durable_files(study)
    before, files = _dump(study), _snapshot(study.path.parent)
    monkeypatch.setattr(awards, "materialize_perspective_achievement_award", _no_calls)
    monkeypatch.setattr(ProviderRegistry, "create", _no_calls)
    monkeypatch.setattr(socket, "create_connection", _no_calls)
    monkeypatch.setattr(socket.socket, "connect", _no_calls)
    response = client.get(paths[route])
    assert response.status_code == 200
    assert _dump(study) == before and len(_stored(study)) == 1
    assert _snapshot(study.path.parent) == files


@pytest.mark.parametrize("achievement", [EXPLORER, SECOND])
def test_synthetic_assess_issue_list_detail_verify_flow_provider_free(study, client, monkeypatch, achievement):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    monkeypatch.setattr(ProviderRegistry, "create", _no_calls)
    monkeypatch.setattr(socket, "create_connection", _no_calls)
    monkeypatch.setattr(socket.socket, "connect", _no_calls)
    assessment = _assessment(client, achievement)
    assert assessment.status_code == 200 and len(_stored(study)) == 0
    package = assessment.get_json()["assessment_package"]
    assert assessment.get_json()["assessment_package_sha256"] == awards.evidence_package_digest(package)
    issued = client.post(f"{BASE}/{achievement}/award", json=_approval(package))
    assert issued.status_code == 201
    identifier = issued.get_json()["award_id"]
    receipt = awards.load_achievement_award(study.conn, identifier)
    listed = client.get(f"{BASE}/awards")
    assert listed.status_code == 200 and listed.get_json()["awards"][0]["award_id"] == identifier
    detail = client.get(f"{BASE}/awards/{identifier}")
    assert detail.status_code == 200
    _assert_summary(detail.get_json()["receipt_projection"], receipt)
    verified = client.get(f"{BASE}/awards/{identifier}/verification")
    assert verified.status_code == 200
    assert {key: verified.get_json()[key] for key in ("receipt_integrity", "evidence_verification", "historical_snapshot_replay")} == {
        "receipt_integrity": "valid", "evidence_verification": "verified", "historical_snapshot_replay": "verified"}
    assert len(_stored(study)) == 1


@pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
def test_issuance_does_not_offer_generic_crud(study, client, method):
    before = _dump(study)
    response = getattr(client, method)(f"{BASE}/{EXPLORER}/award")
    assert response.status_code == 405 and _dump(study) == before


def test_current_negative_assessment_does_not_overwrite_historical_award(study, client):
    study.retained()
    receipt = _install(study)
    study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    study.conn.commit()
    original = _stored(study)
    response = _assessment(client)
    assert response.status_code == 200 and response.get_json()["status"] != "earned"
    history = client.get(f"{BASE}/awards")
    assert history.status_code == 200 and history.get_json()["awards"][0]["award_id"] == receipt["award_id"]
    assert _stored(study) == original


def test_post_delegates_exact_request_with_no_route_owned_transaction(study, client, monkeypatch):
    study.retained()
    package = awards.prepare_perspective_achievement_award(study.conn, EXPLORER)
    expected = _approval(package)
    original = awards.materialize_perspective_achievement_award
    calls = []

    def captured(conn, achievement_id, rule_id, rule_version, digest):
        assert not conn.in_transaction
        calls.append((achievement_id, rule_id, rule_version, digest))
        return original(conn, achievement_id, rule_id, rule_version, digest)

    monkeypatch.setattr(awards, "materialize_perspective_achievement_award", captured)
    response = client.post(f"{BASE}/{EXPLORER}/award", json=expected)
    assert response.status_code == 201
    assert calls == [(EXPLORER, expected["rule_id"], expected["rule_version"], expected["assessment_package_sha256"])]


def test_current_assessment_delegates_exact_domain_preparation(study, client, monkeypatch):
    study.retained()
    original = awards.prepare_perspective_achievement_award
    calls = []

    def captured(conn, achievement_id, *args, **kwargs):
        package = original(conn, achievement_id, *args, **kwargs)
        calls.append((achievement_id, package))
        return package

    monkeypatch.setattr(awards, "prepare_perspective_achievement_award", captured)
    response = _assessment(client)
    assert response.status_code == 200 and len(calls) == 1
    assert calls[0][0] == EXPLORER and calls[0][1] == response.get_json()["assessment_package"]


def test_current_assessment_keeps_captured_output_and_source_text_out_of_package(study, client):
    study.retained(response="SYNTHETIC PRIVATE RESPONSE SENTINEL", question="SYNTHETIC QUESTION SENTINEL")
    response = _assessment(client)
    assert response.status_code == 200 and response.get_json()["status"] == "earned"
    for text in (b"SYNTHETIC PRIVATE RESPONSE SENTINEL", b"SYNTHETIC QUESTION SENTINEL",
                 b"Alpha beta begins.", b"Middle line with Unicode", b"Omega closes"):
        assert text not in response.data


def test_historical_reads_suppress_excluded_private_metadata_and_never_reevaluate(study, client, monkeypatch):
    frame = study.saved("SYNTHETIC PRIVATE LABEL", purpose="SYNTHETIC PRIVATE PURPOSE")
    study.retained(frame, execution={"provider_id": "synthetic", "model_id": "PRIVATE MODEL SENTINEL"})
    receipt = _install(study)
    study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    study.conn.commit()
    before = _stored(study)
    import hermeneia.perspective_achievement_evidence as adapter
    import hermeneia.perspective_achievements as evaluator
    monkeypatch.setattr(adapter, "read_perspective_achievement_evidence", _no_calls)
    monkeypatch.setattr(evaluator, "evaluate_perspective_achievements", _no_calls)
    for route in (f"{BASE}/awards", f"{BASE}/awards/{receipt['award_id']}"):
        response = client.get(route)
        assert response.status_code == 200
        for marker in (b"SYNTHETIC PRIVATE LABEL", b"SYNTHETIC PRIVATE PURPOSE", b"PRIVATE MODEL SENTINEL"):
            assert marker not in response.data
        assert b"evidence_package" not in response.data and b"receipt_json" not in response.data
    assert _stored(study) == before


def test_capability_read_cannot_materialize_awards(study, client, monkeypatch):
    from hermeneia.study_lineage import project_study_lineage
    study.retained()
    before = _dump(study)
    monkeypatch.setattr(awards, "materialize_perspective_achievement_award", _no_calls)
    monkeypatch.setattr(awards, "ensure_achievement_award_tables", _no_calls)
    result = evaluate_capabilities(project_study_lineage(study.conn))
    assert result["capabilities"]
    assert _dump(study) == before and _stored(study) == []


@pytest.mark.parametrize("route", ["assessment", "list", "detail", "verification"])
def test_new_gets_open_read_only_connections_and_never_initialize(study, client, monkeypatch, route):
    study.retained()
    receipt = _install(study)
    paths = {"assessment": f"{BASE}/{EXPLORER}/assessment", "list": f"{BASE}/awards",
        "detail": f"{BASE}/awards/{receipt['award_id']}",
        "verification": f"{BASE}/awards/{receipt['award_id']}/verification"}
    connect = sqlite3.connect
    calls = []

    def checked(database, *args, **kwargs):
        assert "mode=ro" in str(database) and kwargs.get("uri") is True
        conn = connect(database, *args, **kwargs)
        trace = []
        calls.append(trace)
        conn.set_trace_callback(trace.append)
        return conn

    monkeypatch.setattr(sqlite3, "connect", checked)
    monkeypatch.setattr(awards, "ensure_achievement_award_tables", _no_calls)
    import hermeneia.web.app as web
    monkeypatch.setattr(web, "SQLiteStore", _no_calls)
    response = client.get(paths[route])
    assert response.status_code == 200 and len(calls) == 1
    assert calls[0][:2] == ["PRAGMA query_only=ON", "BEGIN"]
    assert all(sql.lstrip().upper().startswith(("SELECT", "PRAGMA", "BEGIN", "ROLLBACK")) for sql in calls[0])


def test_synthetic_supported_new_rule_version_uses_separate_slot(study, client, monkeypatch):
    study.retained()
    old = _issue(client, study).get_json()
    _install_synthetic_v2(monkeypatch)
    package = awards.prepare_perspective_achievement_award(study.conn, EXPLORER, rule_version="2.0.0")
    response = client.post(f"{BASE}/{EXPLORER}/award", json=_approval(package))
    assert response.status_code == 201
    new = response.get_json()
    assert new["award_id"] != old["award_id"]
    assert new["receipt_projection"]["rule_version"] == "2.0.0"
    assert len(_stored(study)) == 2


@pytest.mark.parametrize("route", ["list", "detail", "verification"])
def test_unavailable_award_schema_remains_bounded_unsupported_without_initialization(study, client, route):
    study.conn.execute("DROP TABLE achievement_awards")
    study.conn.commit()
    paths = {"list": f"{BASE}/awards", "detail": f"{BASE}/awards/achievement-award:sha256:{'0' * 64}",
        "verification": f"{BASE}/awards/achievement-award:sha256:{'0' * 64}/verification"}
    before = _dump(study)
    response = client.get(paths[route])
    assert response.status_code == 409 and response.get_json()["error"]
    assert _dump(study) == before
    assert not study.conn.execute("SELECT 1 FROM sqlite_master WHERE name='achievement_awards'").fetchone()


def test_fail_closed_write_failure_preserves_prior_p3_records(study, client):
    study.retained()
    package = awards.prepare_perspective_achievement_award(study.conn, EXPLORER)
    study.conn.execute("CREATE TRIGGER synthetic_award_write_failure BEFORE INSERT ON achievement_awards "
                       "BEGIN SELECT RAISE(ABORT, 'SYNTHETIC SQL PRIVATE SENTINEL'); END")
    study.conn.commit()
    before = _dump(study)
    response = client.post(f"{BASE}/{EXPLORER}/award", json=_approval(package))
    assert response.status_code == 409 and response.get_json()["error"]
    assert b"SYNTHETIC SQL PRIVATE SENTINEL" not in response.data
    assert _dump(study) == before and _stored(study) == []


def test_unknown_achievement_current_assessment_refuses_without_fabricated_state(study, client):
    before = _dump(study)
    response = _assessment(client, "invented")
    assert response.status_code == 404 and response.get_json()["error"]
    assert _dump(study) == before


def test_api_history_summary_matches_existing_safe_lineage_whitelist_without_projecting_history(study, client, monkeypatch):
    import hermeneia.study_lineage as lineage
    import hermeneia.perspective_achievement_evidence as adapter
    import hermeneia.perspective_achievements as evaluator
    study.retained()
    receipt = _install(study)
    expected = next(item["record_data"] for item in lineage.project_study_lineage(study.conn)["items"]
                    if item["record"] == {"table": "achievement_awards", "key": {"id": receipt["award_id"]}})
    monkeypatch.setattr(lineage, "project_study_lineage", _no_calls)
    monkeypatch.setattr(adapter, "read_perspective_achievement_evidence", _no_calls)
    monkeypatch.setattr(evaluator, "evaluate_perspective_achievements", _no_calls)
    monkeypatch.setattr(awards, "prepare_perspective_achievement_award", _no_calls)
    listed = client.get(f"{BASE}/awards")
    detail = client.get(f"{BASE}/awards/{receipt['award_id']}")
    assert listed.status_code == detail.status_code == 200
    assert listed.get_json()["awards"] == [expected]
    assert detail.get_json()["receipt_projection"] == expected


def test_retry_after_exclusion_returns_existing_safe_award_without_private_package(study, client):
    frame = study.saved("SYNTHETIC EXCLUDED LABEL", purpose="SYNTHETIC EXCLUDED PURPOSE")
    study.retained(frame, execution={"provider_id": "synthetic", "model_id": "SYNTHETIC EXCLUDED MODEL"})
    request = _approval(awards.prepare_perspective_achievement_award(study.conn, EXPLORER))
    issued = client.post(f"{BASE}/{EXPLORER}/award", json=request)
    assert issued.status_code == 201
    identifier = issued.get_json()["award_id"]
    original = _stored(study)
    study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1")
    study.conn.commit()
    retry = client.post(f"{BASE}/{EXPLORER}/award", json=request)
    assert retry.status_code == 200 and retry.get_json()["status"] == "already_recorded"
    assert retry.get_json()["award_id"] == identifier
    assert retry.get_json()["receipt_representation"] == "safe_summary"
    for hidden in (b"SYNTHETIC EXCLUDED LABEL", b"SYNTHETIC EXCLUDED PURPOSE", b"SYNTHETIC EXCLUDED MODEL",
                   b"evidence_package", b"receipt_json"):
        assert hidden not in retry.data
    assert _stored(study) == original


def test_structurally_supported_unknown_historical_rule_version_is_readable_but_not_replayed(study, client):
    study.retained()

    def historical_version(package):
        for rule in package["rule_definitions"]:
            rule["rule_version"] = "99.0.0"
        finding = package["assessment"]["finding"]
        finding["rule_version"] = "99.0.0"
        finding["rule_reference"] = finding["rule_id"] + ".v99.0.0"
        definition = next(rule for rule in package["rule_definitions"] if rule["achievement_id"] == finding["achievement_id"])
        finding["rule_sha256"] = _digest(definition)
        package["assessment"]["rules_sha256"] = _digest(package["rule_definitions"])

    receipt = _install(study, mutate=historical_version)
    detail = client.get(f"{BASE}/awards/{receipt['award_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["receipt_projection"]["rule_version"] == "99.0.0"
    verified = client.get(f"{BASE}/awards/{receipt['award_id']}/verification")
    assert verified.status_code == 200
    assert verified.get_json()["receipt_integrity"] == "valid"
    assert verified.get_json()["evidence_verification"] == "unverifiable_unsupported_rule"
    assert verified.get_json()["historical_snapshot_replay"] == "unsupported"


def test_history_order_uses_awarded_instants_before_identity_and_not_insertion(study, client):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    late = _install(study, EXPLORER, at="2026-10-01T11:00:00.100000+00:00")
    early = _install(study, SECOND, at="2026-10-01T11:00:00+00:00")
    response = client.get(f"{BASE}/awards")
    assert response.status_code == 200
    assert [row["award_id"] for row in response.get_json()["awards"]] == [early["award_id"], late["award_id"]]


def test_list_does_not_silently_skip_malformed_historical_award(study, client):
    study.retained()
    _install(study)
    _drop_guard(study.conn, "achievement_awards", "UPDATE")
    study.conn.execute("UPDATE achievement_awards SET receipt_json='PRIVATE MALFORMED BYTES'")
    study.conn.commit()
    before = _dump(study)
    response = client.get(f"{BASE}/awards")
    assert response.status_code == 409 and response.get_json()["error"]
    assert b"PRIVATE MALFORMED BYTES" not in response.data
    assert "awards" not in response.get_json() and _dump(study) == before


def test_invalid_historical_receipt_verification_remains_structured_negative(study, client):
    study.retained()
    receipt = _install(study)
    _drop_guard(study.conn, "achievement_awards", "UPDATE")
    study.conn.execute("UPDATE achievement_awards SET receipt_json='{}'")
    study.conn.commit()
    expected = verify_achievement_award(study.conn, receipt["award_id"])
    before = _dump(study)
    response = client.get(f"{BASE}/awards/{receipt['award_id']}/verification")
    assert response.status_code == 200 and response.get_json() == expected
    assert response.get_json()["receipt_integrity"] == "invalid"
    assert response.get_json()["evidence_verification"] == "invalid_evidence"
    assert _dump(study) == before


@pytest.mark.parametrize("field", ["rule_id", "rule_version", "assessment_package_sha256"])
def test_duplicate_approval_fields_are_not_silently_collapsed_into_valid_intent(study, client, field):
    study.retained()
    approved = _approval(awards.prepare_perspective_achievement_award(study.conn, EXPLORER))
    conflicting = deepcopy(approved)
    conflicting[field] = {"rule_id": "achievement.unapproved", "rule_version": "99.0.0",
                          "assessment_package_sha256": "sha256:" + "0" * 64}[field]
    # Last-key-wins JSON parsing would discard the contradictory first intent.
    raw = json.dumps(conflicting)[:-1] + "," + json.dumps(field) + ":" + json.dumps(approved[field]) + "}"
    before = _dump(study)
    response = client.post(f"{BASE}/{EXPLORER}/award", data=raw, content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["error"]
    assert _dump(study) == before and _stored(study) == []


def test_detail_delegates_canonical_receipt_validation_to_existing_loader(study, client, monkeypatch):
    study.retained()
    receipt = _install(study)
    original = awards.load_achievement_award
    calls = []

    def captured(conn, identifier):
        calls.append(identifier)
        return original(conn, identifier)

    monkeypatch.setattr(awards, "load_achievement_award", captured)
    response = client.get(f"{BASE}/awards/{receipt['award_id']}")
    assert response.status_code == 200 and calls == [receipt["award_id"]]
    _assert_summary(response.get_json()["receipt_projection"], receipt)


def test_list_delegates_each_canonical_row_to_existing_codec(study, client, monkeypatch):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    expected = [_install(study, EXPLORER), _install(study, SECOND)]
    original = awards.award_from_row
    calls = []

    def captured(row):
        calls.append(row["id"])
        return original(row)

    monkeypatch.setattr(awards, "award_from_row", captured)
    response = client.get(f"{BASE}/awards")
    assert response.status_code == 200
    assert set(calls) == {receipt["award_id"] for receipt in expected}
    assert len(calls) == 2


@pytest.mark.parametrize("raw,content_type", [
    (b"{broken", "application/json"),
    (b'{"rule_id":"\xff"}', "application/json"),
    (b"null", "application/json"),
    (b"", "application/json"),
    (b'{"rule_id":NaN}', "application/json"),
])
def test_malformed_raw_request_is_bounded_bad_request_without_mutation(study, client, raw, content_type):
    study.retained()
    before = _dump(study)
    response = client.post(f"{BASE}/{EXPLORER}/award", data=raw, content_type=content_type)
    assert response.status_code == 400 and response.get_json()["error"]
    assert _dump(study) == before and _stored(study) == []


def test_valid_json_with_non_json_media_type_cannot_issue(study, client):
    study.retained()
    payload = _approval(awards.prepare_perspective_achievement_award(study.conn, EXPLORER))
    before = _dump(study)
    response = client.post(f"{BASE}/{EXPLORER}/award", data=json.dumps(payload), content_type="text/plain")
    assert response.status_code == 400 and response.get_json()["error"]
    assert _dump(study) == before and _stored(study) == []
