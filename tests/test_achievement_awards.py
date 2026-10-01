"""Adversarial award-domain boundaries over synthetic canonical P3 evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from threading import Barrier

import pytest

import hermeneia.achievement_awards as awards
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
from hermeneia.perspective_achievements import evaluate_perspective_achievements
from hermeneia.perspective_execution_receipts import TABLE as P3_TABLE, canonical_bytes
from test_perspective_achievements import END, KEPT, START, study


TABLE = "achievement_awards"
EXPLORER = "perspective_explorer"
SECOND = "second_opinion"
VERSION = "1.0.0"
AWARDED = "2026-09-30T11:00:00+00:00"
LATER = "2026-09-30T12:00:00+00:00"
PACKAGE_DOMAIN = b"hermeneia.perspective-achievement-evidence-package/v1\0"
AWARD_DOMAIN = b"hermeneia.perspective-achievement-award/v1\0"


def _digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _package_digest(package):
    return "sha256:" + hashlib.sha256(PACKAGE_DOMAIN + canonical_bytes(package)).hexdigest()


def _award_id(receipt):
    body = {key: value for key, value in receipt.items() if key != "award_id"}
    return "achievement-award:sha256:" + hashlib.sha256(AWARD_DOMAIN + canonical_bytes(body)).hexdigest()


def _resign(receipt):
    """Test-only rehash: integrity cannot rescue contradictory contract facts."""
    changed = deepcopy(receipt)
    changed["evidence_package_sha256"] = _package_digest(changed["evidence_package"])
    changed["issuance"]["approved_evidence_package_sha256"] = changed["evidence_package_sha256"]
    changed["award_id"] = _award_id(changed)
    return changed


def _row(receipt, raw=None):
    return {"id": receipt["award_id"], "achievement_id": receipt["achievement_id"],
            "rule_id": receipt["rule_id"], "rule_version": receipt["rule_version"],
            "receipt_json": canonical_bytes(receipt).decode() if raw is None else raw}


def _initialize(conn):
    awards.ensure_achievement_award_tables(conn)
    conn.commit()


def _prepare(study, achievement=EXPLORER):
    return awards.prepare_perspective_achievement_award(study.conn, achievement)


def _materialize(conn, package):
    finding = package["assessment"]["finding"]
    return awards.materialize_perspective_achievement_award(
        conn, finding["achievement_id"], finding["rule_id"], finding["rule_version"],
        awards.evidence_package_digest(package))["receipt"]


def _issued(study, monkeypatch, achievement=EXPLORER):
    _initialize(study.conn)
    monkeypatch.setattr(awards, "_now", lambda: AWARDED)
    package = _prepare(study, achievement)
    return _materialize(study.conn, package)


def _basis(evidence):
    def order(execution):
        receipt = json.loads(execution.receipt_json)
        instant = datetime.fromisoformat(receipt["retention"]["retained_at"].replace("Z", "+00:00"))
        return instant.astimezone(timezone.utc), receipt["id"]
    return {"source_state": evidence.source_state, "coverage": json.loads(evidence.coverage_json),
            "diagnostics": json.loads(evidence.diagnostics_json), "executions": [{
                "receipt_sha256": "sha256:" + hashlib.sha256(execution.receipt_json.encode()).hexdigest(),
                "lineage_ref": json.loads(execution.lineage_ref_json),
                "family_key": list(execution.family_key) if execution.family_key is not None else None,
                "family_state": execution.family_state,
                "family_evidence": json.loads(execution.family_evidence_json),
                "family_reason_code": execution.family_reason_code,
                "dependency_evidence": json.loads(execution.dependency_evidence_json),
                "eligibility_observations": json.loads(execution.eligibility_json),
            } for execution in sorted(evidence.executions, key=order)]}


@pytest.mark.parametrize("achievement,count", [(EXPLORER, 1), (SECOND, 2)])
def test_package_binds_exact_unchanged_assessment_and_whole_adapter_basis(study, achievement, count):
    parents = [study.retained("close-reader", execution={
        "provider_id": "synthetic", "model_id": "fixture-v1", "options": {"temperature": 0.7}}),
        study.retained("skeptical-reader", kept="2026-09-30T10:02:00+00:00")]
    evidence = read_perspective_achievement_evidence(study.conn)
    result = evaluate_perspective_achievements(evidence)
    before = tuple(study.conn.iterdump())
    package = _prepare(study, achievement)
    assert tuple(study.conn.iterdump()) == before
    assert set(package) == {"profile", "assessment", "adapter_basis", "rule_definitions", "witness_bindings"}
    assert package["profile"] == "perspective-achievement-evidence-package/v1"
    assessment = package["assessment"]
    assert set(assessment) == {"result_schema", "evaluator_version", "rules_sha256", "evidence_sha256",
                               "finding", "coverage", "diagnostics", "limitations"}
    assert assessment == {"result_schema": result["schema"], "finding": next(
        finding for finding in result["achievements"] if finding["achievement_id"] == achievement),
        **{key: result[key] for key in ("evaluator_version", "rules_sha256", "evidence_sha256",
                                      "coverage", "diagnostics", "limitations")}}
    assert package["adapter_basis"] == _basis(evidence)
    assert assessment["evidence_sha256"] == _digest(package["adapter_basis"])
    assert assessment["rules_sha256"] == _digest(package["rule_definitions"])
    selected = assessment["finding"]["qualifying_receipt_ids"]
    expected = {parent["id"]: parent for parent in parents}
    assert package["witness_bindings"] == [{"receipt_id": identifier,
        "run_id": expected[identifier]["run"]["run_id"],
        "receipt_sha256": _digest(expected[identifier])} for identifier in selected]
    assert len(package["witness_bindings"]) == count
    assert "Exact synthetic proposal" not in json.dumps(package)
    assert awards.evidence_package_digest(package) == _package_digest(package)
    assert awards.evidence_package_digest(package) != assessment["evidence_sha256"]
    metadata = assessment["finding"]["evidence_refs"][0]["provenance"]["execution"]
    assert metadata["options"]["temperature"] == 0.7


def test_receipt_body_and_package_have_separate_domain_separated_digest_boundaries(study):
    study.retained()
    package = _prepare(study)
    receipt = awards.make_award_receipt(package, awarded_at=AWARDED)
    assert set(receipt) == {"schema", "award_id", "achievement_id", "rule_id", "rule_version",
        "evaluation_status", "earned_at", "awarded_at", "issuer", "issuance",
        "evidence_package", "evidence_package_sha256"}
    assert receipt["schema"] == "hermeneia.perspective-achievement-award/v1"
    assert receipt["award_id"] == _award_id(receipt)
    assert receipt["evidence_package_sha256"] == _package_digest(package)
    assert receipt["earned_at"] == KEPT
    assert receipt["awarded_at"] == AWARDED
    assert receipt["issuer"] == {"kind": "hermeneia", "authorship": "derived"}
    assert receipt["issuance"] == {"policy": "explicit-steward-materialization/v1",
        "actor": "local_steward", "actor_identity": "unknown",
        "approved_evidence_package_sha256": _package_digest(package)}
    assert awards.award_from_row(_row(receipt)) == receipt
    assert not canonical_bytes(receipt).endswith(b"\n")
    assert awards.make_award_receipt(package, awarded_at=LATER)["award_id"] != receipt["award_id"]
    package["assessment"]["limitations"].append("Caller-mutated copy")
    assert "Caller-mutated copy" not in json.dumps(receipt)


def test_retention_and_repeated_read_only_preparation_do_not_issue_awards(study):
    _initialize(study.conn)
    study.retained()
    before = tuple(study.conn.iterdump())
    first = _prepare(study)
    second = _prepare(study)
    assert first == second
    assert tuple(study.conn.iterdump()) == before
    assert study.conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
    readonly = sqlite3.connect(f"file:{study.path}?mode=ro", uri=True)
    try:
        assert awards.prepare_perspective_achievement_award(readonly, EXPLORER) == first
    finally:
        readonly.close()


def test_preparation_does_not_initialize_a_legacy_award_ledger(study):
    study.retained()
    if study.conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone():
        study.conn.execute(f"DROP TABLE {TABLE}")
        study.conn.commit()
    before = tuple(study.conn.iterdump())
    assert _prepare(study)["assessment"]["finding"]["status"] == "earned"
    assert tuple(study.conn.iterdump()) == before
    assert not study.conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone()


def test_explicit_materialization_stores_exact_bytes_and_retries_original_history(study, monkeypatch):
    study.retained()
    receipt = _issued(study, monkeypatch)
    stored = study.conn.execute(f"SELECT * FROM {TABLE}").fetchone()
    assert dict(stored) == _row(receipt)
    assert awards.load_achievement_award(study.conn, receipt["award_id"]) == receipt
    monkeypatch.setattr(awards, "_now", lambda: (_ for _ in ()).throw(AssertionError("Retry must not clock a new award")))
    study.retained("skeptical-reader", kept=LATER)
    # A stale approval is harmless only when the exact slot is already occupied.
    returned = _materialize(study.conn, receipt["evidence_package"])
    assert canonical_bytes(returned) == canonical_bytes(receipt)
    assert study.conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1


def test_retry_reads_original_receipt_after_selected_evidence_disappears(study, monkeypatch):
    parent = study.retained()
    receipt = _issued(study, monkeypatch)
    for name, in study.conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (P3_TABLE,)):
        study.conn.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
    study.conn.execute(f"DELETE FROM {P3_TABLE} WHERE id=?", (parent["id"],))
    study.conn.commit()
    assert _materialize(study.conn, receipt["evidence_package"]) == receipt
    assert awards.load_achievement_award(study.conn, receipt["award_id"]) == receipt


@pytest.mark.parametrize("change", ["new_candidate", "source_metadata", "exclusion", "unrelated_invalid"])
def test_approval_is_stale_on_any_assessed_snapshot_drift(study, change):
    _initialize(study.conn)
    study.retained()
    package = _prepare(study)
    if change == "new_candidate":
        study.retained("skeptical-reader", kept=LATER)
    elif change == "source_metadata":
        study.conn.execute("UPDATE source_documents SET source_role='context' WHERE id=?", (study.seed["doc_id"],))
        study.conn.commit()
    elif change == "exclusion":
        study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1 WHERE id=?", (study.seed["doc_id"],))
        study.conn.commit()
    else:
        study.retained("contextual-reader", prompt="Hash-consistent unrelated prompt")
    before = tuple(study.conn.iterdump())
    with pytest.raises(ValueError):
        _materialize(study.conn, package)
    assert tuple(study.conn.iterdump()) == before
    assert study.conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0


def test_pending_caller_transaction_is_refused_without_commit_or_rollback(study):
    _initialize(study.conn)
    study.retained()
    package = _prepare(study)
    study.conn.execute("CREATE TABLE caller_pending(value TEXT)")
    study.conn.commit()
    study.conn.execute("INSERT INTO caller_pending VALUES('Pending human work')")
    assert study.conn.in_transaction
    with pytest.raises(ValueError):
        _materialize(study.conn, package)
    assert study.conn.in_transaction
    assert study.conn.execute("SELECT value FROM caller_pending").fetchone()[0] == "Pending human work"
    assert study.conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
    study.conn.rollback()


def test_failed_award_write_preserves_committed_p3_and_retry_uses_actual_later_time(study, monkeypatch):
    _initialize(study.conn)
    parent = study.retained()
    package = _prepare(study)
    times = iter([AWARDED, LATER])
    monkeypatch.setattr(awards, "_now", lambda: next(times))
    study.conn.execute(f"CREATE TRIGGER injected_award_failure AFTER INSERT ON {TABLE} BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    study.conn.commit()
    p3_before = study.conn.execute(f"SELECT receipt_json FROM {P3_TABLE} WHERE id=?", (parent["id"],)).fetchone()[0]
    with pytest.raises((sqlite3.DatabaseError, ValueError)):
        _materialize(study.conn, package)
    assert not study.conn.in_transaction
    assert study.conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
    assert study.conn.execute(f"SELECT receipt_json FROM {P3_TABLE} WHERE id=?", (parent["id"],)).fetchone()[0] == p3_before
    study.conn.execute("DROP TRIGGER injected_award_failure")
    study.conn.commit()
    receipt = _materialize(study.conn, package)
    assert receipt["awarded_at"] == LATER
    assert receipt["earned_at"] == KEPT


def test_two_concurrent_materializers_return_one_original_canonical_receipt(study, monkeypatch):
    _initialize(study.conn)
    study.retained()
    package = _prepare(study)
    clock_reads = []
    def issuance_time():
        clock_reads.append(AWARDED)
        return AWARDED
    monkeypatch.setattr(awards, "_now", issuance_time)
    barrier = Barrier(2)
    def issue():
        conn = sqlite3.connect(study.path, timeout=10)
        try:
            barrier.wait(timeout=10)
            return _materialize(conn, package)
        finally:
            conn.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(issue) for _ in range(2)]
        receipts = [future.result(timeout=20) for future in futures]
    assert canonical_bytes(receipts[0]) == canonical_bytes(receipts[1])
    rows = study.conn.execute(f"SELECT * FROM {TABLE}").fetchall()
    assert len(rows) == 1
    assert dict(rows[0]) == _row(receipts[0])
    assert clock_reads == [AWARDED]


@pytest.mark.parametrize("operation", ["update", "delete", "replace_id", "replace_slot"])
def test_database_guards_refuse_award_mutation_and_replacement_by_id_or_slot(study, monkeypatch, operation):
    study.retained()
    receipt = _issued(study, monkeypatch)
    original = dict(study.conn.execute(f"SELECT * FROM {TABLE}").fetchone())
    with pytest.raises(sqlite3.DatabaseError):
        if operation == "update":
            study.conn.execute(f"UPDATE {TABLE} SET receipt_json=receipt_json WHERE id=?", (receipt["award_id"],))
        elif operation == "delete":
            study.conn.execute(f"DELETE FROM {TABLE} WHERE id=?", (receipt["award_id"],))
        else:
            changed = receipt if operation == "replace_id" else awards.make_award_receipt(
                receipt["evidence_package"], awarded_at=LATER)
            row = _row(changed)
            study.conn.execute(f"INSERT OR REPLACE INTO {TABLE} VALUES (?,?,?,?,?)", tuple(row.values()))
    study.conn.rollback()
    assert dict(study.conn.execute(f"SELECT * FROM {TABLE}").fetchone()) == original


def test_same_rule_definition_conflict_refuses_retry_without_rewriting_history(study, monkeypatch):
    study.retained()
    receipt = _issued(study, monkeypatch)
    released = awards.perspective_achievement_rules()
    changed = deepcopy(released)
    changed[0]["predicate"] = "Conflicting same-version predicate"
    monkeypatch.setattr(awards, "perspective_achievement_rules", lambda: deepcopy(changed))
    with pytest.raises(awards.UnsupportedAward):
        _materialize(study.conn, receipt["evidence_package"])
    assert awards.load_achievement_award(study.conn, receipt["award_id"]) == receipt


def test_malformed_existing_slot_blocks_replacement_and_preserves_purported_bytes(study):
    _initialize(study.conn)
    study.retained()
    package = _prepare(study)
    receipt = awards.make_award_receipt(package, awarded_at=AWARDED)
    broken = deepcopy(receipt)
    broken["evidence_package_sha256"] = "sha256:" + "0" * 64
    row = _row(broken)
    study.conn.execute(f"INSERT INTO {TABLE} VALUES (?,?,?,?,?)", tuple(row.values()))
    study.conn.commit()
    before = tuple(study.conn.iterdump())
    with pytest.raises(awards.InvalidAward):
        _materialize(study.conn, package)
    assert tuple(study.conn.iterdump()) == before


@pytest.mark.parametrize("state", ["not_earned", "unsupported", "invalid"])
def test_non_earned_assessment_cannot_be_materialized(study, state):
    _initialize(study.conn)
    if state == "unsupported":
        study.conn.execute(f"DROP TABLE {P3_TABLE}")
        study.conn.commit()
    elif state == "invalid":
        study.retained(prompt="Hash-consistent prompt unrelated to captured inputs")
    before = tuple(study.conn.iterdump())
    with pytest.raises(ValueError):
        awards.materialize_perspective_achievement_award(study.conn, EXPLORER,
            "achievement.perspective_explorer", VERSION, "sha256:" + "0" * 64)
    assert tuple(study.conn.iterdump()) == before


@pytest.mark.parametrize("achievement,rule,version,digest", [
    ("invented", "achievement.invented", VERSION, "sha256:" + "0" * 64),
    (EXPLORER, "achievement.second_opinion", VERSION, "sha256:" + "0" * 64),
    (EXPLORER, "achievement.perspective_explorer", "2.0.0", "sha256:" + "0" * 64),
    (EXPLORER, "achievement.perspective_explorer", "01.0.0", "sha256:" + "0" * 64),
    (EXPLORER, "achievement.perspective_explorer", VERSION, None),
    (EXPLORER, "achievement.perspective_explorer", VERSION, "sha256:" + "A" * 64),
    (EXPLORER, "achievement.perspective_explorer", VERSION, {"status": "earned"}),
])
def test_request_identity_and_approval_are_exact_not_client_authored_facts(study, achievement, rule, version, digest):
    _initialize(study.conn)
    study.retained()
    before = tuple(study.conn.iterdump())
    with pytest.raises(ValueError):
        awards.materialize_perspective_achievement_award(study.conn, achievement, rule, version, digest)
    assert tuple(study.conn.iterdump()) == before


def test_known_earned_witness_can_issue_with_unrelated_invalid_diagnostic_preserved(study, monkeypatch):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    study.retained("contextual-reader", prompt="Hash-consistent unrelated synthetic prompt")
    receipt = _issued(study, monkeypatch, SECOND)
    diagnostics = receipt["evidence_package"]["assessment"]["diagnostics"]
    assert any(item["state"] == "invalid" for item in diagnostics)
    assert receipt["evaluation_status"] == "earned"
    assert len(receipt["evidence_package"]["witness_bindings"]) == 2


def test_explorer_family_only_unsupported_diagnostic_is_not_an_added_qualification_gate(study, monkeypatch):
    root = study.saved("Legacy ancestor")
    child = study.saved("Supported executed revision", purpose="Challenge exact evidence.", predecessor=root)
    study.retained(child)
    for name, in study.conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='perspectives'"):
        study.conn.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
    study.conn.execute("UPDATE perspectives SET identity_scheme='perspective-label-v1' WHERE id=?", (root["id"],))
    study.conn.commit()
    receipt = _issued(study, monkeypatch)
    diagnostics = receipt["evidence_package"]["assessment"]["diagnostics"]
    assert any(item["state"] == "unsupported" and item["stage"] == "family" for item in diagnostics)
    assert receipt["evaluation_status"] == "earned"


def test_second_opinion_earned_time_is_selected_pair_threshold_not_earliest_possible_pair(study):
    first = study.retained("close-reader", question="Inquiry one", kept="2026-09-30T10:01:00+00:00")
    study.retained("skeptical-reader", question="Inquiry two", kept="2026-09-30T10:02:00+00:00")
    study.retained("contextual-reader", question="Inquiry two", kept="2026-09-30T10:03:00+00:00")
    last = study.retained("skeptical-reader", question="Inquiry one", kept="2026-09-30T10:09:00+00:00")
    receipt = awards.make_award_receipt(_prepare(study, SECOND), awarded_at=AWARDED)
    assert receipt["evidence_package"]["assessment"]["finding"]["qualifying_receipt_ids"] == [first["id"], last["id"]]
    assert receipt["earned_at"] == "2026-09-30T10:09:00+00:00"


def test_equal_retention_instants_use_ascii_receipt_order_and_preserve_original_strings(study):
    parents = [study.retained("close-reader", kept="2026-09-30T06:01:00-04:00"),
               study.retained("skeptical-reader", kept="2026-09-30T10:01:00Z")]
    receipt = awards.make_award_receipt(_prepare(study, SECOND), awarded_at=AWARDED)
    selected = receipt["evidence_package"]["assessment"]["finding"]["selection_basis"]["selected"]
    assert [item["receipt_id"] for item in selected] == sorted(parent["id"] for parent in parents)
    assert {item["retained_at"] for item in selected} == {"2026-09-30T06:01:00-04:00", "2026-09-30T10:01:00Z"}
    assert receipt["earned_at"] == KEPT


def test_truthful_clock_skew_does_not_backdate_or_clamp_either_time(study, monkeypatch):
    _initialize(study.conn)
    study.retained()
    monkeypatch.setattr(awards, "_now", lambda: START)
    receipt = _materialize(study.conn, _prepare(study))
    assert receipt["awarded_at"] == START
    assert receipt["earned_at"] == KEPT
    awards.validate_award_receipt(receipt)


@pytest.mark.parametrize("encoding", ["pretty", "newline", "duplicate_outer", "duplicate_nested", "bom", "invalid_utf8", "nan"])
def test_stored_award_json_requires_strict_exact_p3_canonical_codec(study, encoding):
    study.retained()
    receipt = awards.make_award_receipt(_prepare(study), awarded_at=AWARDED)
    raw = canonical_bytes(receipt).decode()
    if encoding == "pretty":
        raw = json.dumps(receipt, indent=2)
    elif encoding == "newline":
        raw += "\n"
    elif encoding == "duplicate_outer":
        raw = '{"schema":' + json.dumps(receipt["schema"]) + "," + raw[1:]
    elif encoding == "duplicate_nested":
        raw = raw.replace('"authorship":"derived"', '"authorship":"derived","authorship":"derived"', 1)
    elif encoding == "bom":
        raw = "\ufeff" + raw
    elif encoding == "invalid_utf8":
        raw = b"\xff" + raw.encode()
    else:
        raw = raw.replace('"actor_identity":"unknown"', '"actor_identity":NaN', 1)
    with pytest.raises(ValueError):
        awards.award_from_row(_row(receipt, raw))


@pytest.mark.parametrize("column", ["id", "achievement_id", "rule_id", "rule_version"])
def test_indexed_row_mirrors_cannot_disagree_with_receipt_body(study, column):
    study.retained()
    receipt = awards.make_award_receipt(_prepare(study), awarded_at=AWARDED)
    row = _row(receipt)
    row[column] = "contradictory-mirror"
    with pytest.raises(awards.InvalidAward):
        awards.award_from_row(row)


@pytest.mark.parametrize("field", ["award_id", "evidence_package_sha256", "earned_at", "awarded_at"])
def test_receipt_integrity_detects_unresigned_body_changes(study, field):
    study.retained()
    receipt = awards.make_award_receipt(_prepare(study), awarded_at=AWARDED)
    receipt[field] = "changed-unbound-value"
    with pytest.raises(awards.InvalidAward):
        awards.validate_award_receipt(receipt)


@pytest.mark.parametrize("path", [
    (), ("issuer",), ("issuance",), ("evidence_package",),
    ("evidence_package", "assessment"), ("evidence_package", "adapter_basis"),
    ("evidence_package", "witness_bindings", 0),
    ("evidence_package", "assessment", "finding"),
    ("evidence_package", "assessment", "finding", "selection_basis"),
    ("evidence_package", "assessment", "finding", "selection_basis", "selected", 0),
])
def test_unknown_closed_contract_fields_are_rejected_even_when_rehashed(study, path):
    study.retained()
    receipt = awards.make_award_receipt(_prepare(study), awarded_at=AWARDED)
    target = receipt
    for part in path:
        target = target[part]
    target["uncontracted_field"] = "Must not be silently stripped"
    with pytest.raises(awards.InvalidAward):
        awards.validate_award_receipt(_resign(receipt))


@pytest.mark.parametrize("contradiction", [
    "finding_status", "coverage", "evidence_digest", "rule_digest", "registry_digest", "earned_time",
    "request_digest", "witness_count", "selected_order", "duplicate_run", "wrong_typed_table", "selected_time",
])
def test_internal_bindings_refuse_hash_consistent_contradictions(study, contradiction):
    study.retained("close-reader")
    study.retained("skeptical-reader", kept="2026-09-30T10:02:00+00:00")
    receipt = awards.make_award_receipt(_prepare(study, SECOND), awarded_at=AWARDED)
    package = receipt["evidence_package"]
    finding = package["assessment"]["finding"]
    if contradiction == "finding_status":
        finding["status"] = "not_earned"
    elif contradiction == "coverage":
        package["assessment"]["coverage"]["uncontracted_coverage"] = True
    elif contradiction == "evidence_digest":
        package["assessment"]["evidence_sha256"] = "sha256:" + "0" * 64
    elif contradiction == "rule_digest":
        finding["rule_sha256"] = "sha256:" + "0" * 64
    elif contradiction == "registry_digest":
        package["assessment"]["rules_sha256"] = "sha256:" + "0" * 64
    elif contradiction == "earned_time":
        receipt["earned_at"] = KEPT
    elif contradiction == "request_digest":
        receipt = _resign(receipt)
        receipt["issuance"]["approved_evidence_package_sha256"] = "sha256:" + "0" * 64
        receipt["award_id"] = _award_id(receipt)
    elif contradiction == "witness_count":
        package["witness_bindings"].pop()
    elif contradiction == "selected_order":
        package["witness_bindings"].reverse()
    elif contradiction == "duplicate_run":
        package["witness_bindings"][1]["run_id"] = package["witness_bindings"][0]["run_id"]
    elif contradiction == "wrong_typed_table":
        finding["evidence_refs"][0]["record"]["table"] = TABLE
    else:
        finding["selection_basis"]["selected"][0]["retained_at_utc"] = "2026-09-30T10:03:00+00:00"
    if contradiction != "request_digest":
        receipt = _resign(receipt)
    with pytest.raises(awards.InvalidAward):
        awards.validate_award_receipt(receipt)


@pytest.mark.parametrize("field,value", [
    ("schema", "hermeneia.perspective-achievement-award/v99"),
    ("profile", "perspective-achievement-evidence-package/v99"),
])
def test_unknown_wire_formats_are_unsupported_and_never_converted(study, field, value):
    study.retained()
    receipt = awards.make_award_receipt(_prepare(study), awarded_at=AWARDED)
    if field == "schema":
        receipt[field] = value
    else:
        receipt["evidence_package"][field] = value
    with pytest.raises(awards.UnsupportedAward):
        awards.validate_award_receipt(_resign(receipt))


@pytest.mark.parametrize("value", ["2026-09-30T11:00:00", "2026-09-31T11:00:00+00:00", "not-a-time", None])
def test_award_time_requires_a_real_aware_clock_reading(study, value):
    study.retained()
    with pytest.raises(ValueError):
        awards.make_award_receipt(_prepare(study), awarded_at=value)


def test_materialization_outcome_separates_fresh_recording_from_idempotent_history_return(study, monkeypatch):
    _initialize(study.conn)
    study.retained()
    package = _prepare(study)
    monkeypatch.setattr(awards, "_now", lambda: AWARDED)
    finding = package["assessment"]["finding"]
    arguments = (study.conn, finding["achievement_id"], finding["rule_id"], finding["rule_version"],
                 awards.evidence_package_digest(package))
    fresh = awards.materialize_perspective_achievement_award(*arguments)
    repeated = awards.materialize_perspective_achievement_award(*arguments)
    assert set(fresh) == {"status", "receipt"}
    assert fresh["status"] == "recorded"
    assert repeated == {"status": "already_recorded", "receipt": fresh["receipt"]}
    assert "status" not in fresh["receipt"]


def _install_synthetic_v2(monkeypatch):
    """Exercise independent slots without declaring a production v2 release."""
    import hermeneia.perspective_achievements as evaluator
    rules = awards.perspective_achievement_rules()
    for rule in rules:
        rule["rule_version"] = "2.0.0"
    monkeypatch.setattr(evaluator, "_RULES", tuple(deepcopy(rules)))
    monkeypatch.setattr(evaluator, "EVALUATOR_VERSION", "2.0.0")
    monkeypatch.setattr(awards, "_SUPPORTED_RULES_SHA256", {
        **awards._SUPPORTED_RULES_SHA256, "2.0.0": _digest(rules)})
    return rules


def test_synthetic_new_rule_version_can_occupy_its_own_slot_without_replacing_v1(study, monkeypatch):
    study.retained()
    original = _issued(study, monkeypatch)
    _install_synthetic_v2(monkeypatch)
    package = awards.prepare_perspective_achievement_award(study.conn, EXPLORER, rule_version="2.0.0")
    monkeypatch.setattr(awards, "_now", lambda: LATER)
    second = _materialize(study.conn, package)
    assert second["rule_version"] == "2.0.0"
    assert second["awarded_at"] == LATER
    assert second["award_id"] != original["award_id"]
    rows = study.conn.execute(f"SELECT * FROM {TABLE} ORDER BY rule_version").fetchall()
    assert len(rows) == 2
    assert [dict(row) for row in rows] == [_row(original), _row(second)]
    assert awards.load_achievement_award(study.conn, original["award_id"]) == original


def test_synthetic_v2_current_negative_never_revokes_or_recalculates_v1_history(study, monkeypatch):
    study.retained()
    original = _issued(study, monkeypatch)
    _install_synthetic_v2(monkeypatch)
    study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1 WHERE id=?", (study.seed["doc_id"],))
    study.conn.commit()
    current = evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))
    finding = next(item for item in current["achievements"] if item["achievement_id"] == EXPLORER)
    assert finding["rule_version"] == "2.0.0"
    assert finding["status"] == "not_earned"
    before = tuple(study.conn.iterdump())
    with pytest.raises(ValueError):
        awards.materialize_perspective_achievement_award(study.conn, EXPLORER,
            "achievement.perspective_explorer", "2.0.0", "sha256:" + "0" * 64)
    assert tuple(study.conn.iterdump()) == before
    assert awards.load_achievement_award(study.conn, original["award_id"]) == original


def test_materialization_requires_explicit_ledger_initialization(study):
    study.retained()
    package = _prepare(study)
    if study.conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone():
        study.conn.execute(f"DROP TABLE {TABLE}")
        study.conn.commit()
    before = tuple(study.conn.iterdump())
    with pytest.raises(awards.UnsupportedAward):
        _materialize(study.conn, package)
    assert tuple(study.conn.iterdump()) == before


def test_failed_canonical_readback_rolls_back_only_award_and_preserves_parent(study, monkeypatch):
    _initialize(study.conn)
    parent = study.retained()
    package = _prepare(study)
    monkeypatch.setattr(awards, "_now", lambda: AWARDED)
    original_loader = awards.load_achievement_award
    def failed_readback(conn, identifier):
        raise awards.InvalidAward("Injected canonical readback failure")
    monkeypatch.setattr(awards, "load_achievement_award", failed_readback)
    with pytest.raises(awards.InvalidAward):
        _materialize(study.conn, package)
    assert not study.conn.in_transaction
    assert study.conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
    assert study.conn.execute(f"SELECT receipt_json FROM {P3_TABLE} WHERE id=?", (parent["id"],)).fetchone()[0] == canonical_bytes(parent).decode()
    monkeypatch.setattr(awards, "load_achievement_award", original_loader)
    monkeypatch.setattr(awards, "_now", lambda: LATER)
    assert _materialize(study.conn, package)["awarded_at"] == LATER


def test_open_execution_metadata_preserves_finite_numbers_and_exact_unicode_without_coercion(study):
    execution = {"provider_id": "synthetic", "model_id": "fixture-v1", "options": {
        "numeric_forms": [1, 1.0, -0.0, 0.7], "label": "Cafe\u0301 ✓", "nested": {"unknown_option": True}}}
    study.retained(execution=execution)
    receipt = awards.make_award_receipt(_prepare(study), awarded_at=AWARDED)
    metadata = receipt["evidence_package"]["assessment"]["finding"]["evidence_refs"][0]["provenance"]["execution"]
    assert canonical_bytes(metadata) == canonical_bytes(execution)
    stored = canonical_bytes(receipt)
    assert b"[1,1.0,-0.0,0.7]" in stored
    assert b"Cafe\\u0301 \\u2713" in stored
    assert awards.award_from_row(_row(receipt)) == receipt


@pytest.mark.parametrize("identifier", ["not-a-uuid", "", "00000000-0000-0000-0000-00000000000G"])
def test_selected_run_identity_must_retain_the_p3_uuid_shape(study, identifier):
    study.retained()
    receipt = awards.make_award_receipt(_prepare(study), awarded_at=AWARDED)
    receipt["evidence_package"]["witness_bindings"][0]["run_id"] = identifier
    with pytest.raises(awards.InvalidAward):
        awards.validate_award_receipt(_resign(receipt))


def test_changed_selected_pair_returns_original_slot_and_reports_already_recorded(study, monkeypatch):
    study.retained("close-reader", kept="2026-09-30T10:02:00+00:00")
    study.retained("skeptical-reader", kept="2026-09-30T10:03:00+00:00")
    original = _issued(study, monkeypatch, SECOND)
    original_ids = original["evidence_package"]["assessment"]["finding"]["qualifying_receipt_ids"]
    study.retained("contextual-reader", kept="2026-09-30T10:01:00+00:00")
    package = _prepare(study, SECOND)
    finding = package["assessment"]["finding"]
    assert finding["qualifying_receipt_ids"] != original_ids
    assert awards.evidence_package_digest(package) != original["evidence_package_sha256"]
    monkeypatch.setattr(awards, "_now", lambda: (_ for _ in ()).throw(AssertionError("Occupied slot must not acquire a new time")))
    outcome = awards.materialize_perspective_achievement_award(study.conn, SECOND,
        finding["rule_id"], VERSION, awards.evidence_package_digest(package))
    assert outcome == {"status": "already_recorded", "receipt": original}
    assert study.conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1


def test_terminal_award_rows_do_not_change_current_achievement_evaluation(study, monkeypatch):
    _initialize(study.conn)
    study.retained("close-reader")
    study.retained("skeptical-reader")
    before = evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))
    _issued(study, monkeypatch, EXPLORER)
    _issued(study, monkeypatch, SECOND)
    after = evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))
    assert after == before
