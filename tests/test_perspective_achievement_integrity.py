"""Adversarial P4 integrity, coverage, ancestry, portability and read boundaries."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from hermeneia.capabilities import evaluate_capabilities
from hermeneia.guided_study_cycle import project_guided_study_cycle
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
from hermeneia.perspective_achievements import evaluate_perspective_achievements
from hermeneia.perspective_execution_receipts import TABLE, canonical_bytes
from hermeneia.study_lineage import project_study_lineage
from hermeneia.workspace import RestoreError, export_workspace_bundle, read_bundle, restore_workspace
from test_perspective_achievements import (
    EARNED, END, INVALID, NO, START, UNSUPPORTED, _assert_status, study,
)


def _drop_guard(conn, table, operation):
    names = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? "
                         "AND upper(sql) LIKE ?", (table, "%" + operation.upper() + "%")).fetchall()
    for row in names:
        conn.execute('DROP TRIGGER "' + row[0].replace('"', '""') + '"')


def _tamper(study, receipt, mutate, *, resign=True):
    """Test-only corruption bypass; production remains append-only."""
    changed = deepcopy(receipt)
    mutate(changed)
    if resign:
        changed["id"] = "perspective-execution-receipt:sha256:" + hashlib.sha256(
            canonical_bytes({key: value for key, value in changed.items() if key != "id"})).hexdigest()
    _drop_guard(study.conn, TABLE, "UPDATE")
    study.conn.execute(f"UPDATE {TABLE} SET id=?,run_id=?,receipt_json=? WHERE id=?",
                      (changed["id"], changed["run"]["run_id"], canonical_bytes(changed).decode(), receipt["id"]))
    study.conn.commit()
    return changed


@pytest.mark.parametrize("field", ["question", "response", "prompt"])
def test_resigned_receipt_with_tampered_text_digest_fails_closed(study, field):
    receipt = study.retained()
    _tamper(study, receipt, lambda r: r["run"].__setitem__(field, "Changed exact bytes"))
    _assert_status(study, INVALID, INVALID)


def test_resigned_tampered_scope_digest_fails_closed(study):
    receipt = study.retained()
    _tamper(study, receipt, lambda r: r["run"]["scope_receipt"]["primary"].__setitem__("text", "tampered"))
    _assert_status(study, INVALID, INVALID)


def test_receipt_identity_binding_itself_is_required(study):
    receipt = study.retained()
    _tamper(study, receipt, lambda r: r["run"]["execution"].__setitem__("model_id", "different"), resign=False)
    _assert_status(study, INVALID, INVALID)


@pytest.mark.parametrize("mutation", ["missing", "extra", "failed", "retention", "timestamp", "naive_time", "reversed_time"])
def test_malformed_supported_canonical_receipt_is_invalid_not_absent(study, mutation):
    receipt = study.retained()
    def corrupt(r):
        if mutation == "missing":
            del r["run"]["response_sha256"]
        elif mutation == "extra":
            r["invented"] = "history"
        elif mutation == "failed":
            r["run"]["status"] = "failed"
        elif mutation == "retention":
            r["retention"]["decision"] = "accepted"
        elif mutation == "timestamp":
            r["retention"]["retained_at"] = "2026-09-31T10:00:00+00:00"
        elif mutation == "naive_time":
            r["retention"]["retained_at"] = "2026-09-30T10:01:00"
        else:
            r["retention"]["retained_at"] = START
    _tamper(study, receipt, corrupt)
    _assert_status(study, INVALID, INVALID)


def test_noncanonical_json_storage_is_invalid_even_if_payload_is_unchanged(study):
    receipt = study.retained()
    _drop_guard(study.conn, TABLE, "UPDATE")
    study.conn.execute(f"UPDATE {TABLE} SET receipt_json=? WHERE id=?", (json.dumps(receipt, indent=2), receipt["id"]))
    study.conn.commit()
    _assert_status(study, INVALID, INVALID)


@pytest.mark.parametrize("field", ["id", "run_id", "receipt_json"])
def test_blob_receipt_columns_fail_closed_without_an_uncaught_projection_error(study, field):
    receipt = study.retained()
    _drop_guard(study.conn, TABLE, "UPDATE")
    value = canonical_bytes(receipt) if field == "receipt_json" else b"invalid-binary-binding"
    study.conn.execute(f"UPDATE {TABLE} SET {field}=? WHERE id=?", (sqlite3.Binary(value), receipt["id"]))
    study.conn.commit()
    _assert_status(study, INVALID, INVALID)


def test_blob_that_breaks_complete_lineage_source_refuses_positive_cherry_picking(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    receipt = study.retained("contextual-reader")
    _drop_guard(study.conn, TABLE, "UPDATE")
    study.conn.execute(f"UPDATE {TABLE} SET receipt_json=? WHERE id=?",
                      (sqlite3.Binary(canonical_bytes(receipt)), receipt["id"]))
    study.conn.commit()
    _assert_status(study, INVALID, INVALID)


def test_hash_consistent_prompt_must_match_captured_input_template(study):
    study.retained(prompt="A hash-consistent prompt with unrelated inputs.")
    _assert_status(study, INVALID, INVALID)


def test_prompt_implementation_drift_is_unsupported_and_not_reinterpreted(study, monkeypatch):
    import hermeneia.perspective_achievement_evidence as adapter
    study.retained()
    def drifted_template(*args, **kwargs):
        raise AssertionError("A changed prompt implementation must never reinterpret historical v1")
    monkeypatch.setattr(adapter, "build_perspective_prompt", drifted_template)
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)


def test_decorated_changed_template_cannot_hide_implementation_drift(study, monkeypatch):
    from functools import wraps
    import hermeneia.perspective_achievement_evidence as adapter
    study.retained()
    original = adapter.build_perspective_prompt
    @wraps(original)
    def changed_wrapper(*args, **kwargs):
        raise AssertionError("A decorated wrapper must not inherit original-template support")
    monkeypatch.setattr(adapter, "build_perspective_prompt", changed_wrapper)
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)


@pytest.mark.parametrize("version", ["receipt", "prompt", "builtin"])
def test_unknown_supported_revision_is_unsupported_not_fabricated(study, version):
    receipt = study.retained()
    def mutate(r):
        if version == "receipt":
            r["schema"] = "hermeneia.perspective-execution-receipt/v99"
        elif version == "prompt":
            r["run"]["prompt_version"] = "perspective-run/v99"
        else:
            r["run"]["perspective"]["version"] = "99"
    _tamper(study, receipt, mutate)
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)


def test_supported_builtin_plus_unknown_builtin_version_only_proves_explorer(study):
    study.retained("close-reader")
    receipt = study.retained("skeptical-reader")
    _tamper(study, receipt, lambda r: r["run"]["perspective"].__setitem__("version", "99"))
    _assert_status(study, EARNED, UNSUPPORTED)


def test_known_builtin_version_with_conflicting_definition_is_invalid(study):
    receipt = study.retained()
    def mutate(r):
        frame = r["run"]["perspective"]
        frame["definition"]["purpose"] = "Conflicting catalog definition"
        frame["definition_fingerprint"] = "sha256:" + hashlib.sha256(canonical_bytes(frame["definition"])).hexdigest()
    _tamper(study, receipt, mutate)
    _assert_status(study, INVALID, INVALID)


def test_positive_pair_survives_unrelated_local_corruption_but_diagnostic_remains(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    receipt = study.retained("contextual-reader")
    _tamper(study, receipt, lambda r: r["run"].__setitem__("question", "tampered"))
    rows = _assert_status(study, EARNED, EARNED)
    # Error remains explicit in the returned evidence package/coverage.
    assert "invalid" in json.dumps(rows).lower()


def test_known_invalidity_precedes_missing_coverage_without_witness(study):
    receipt = study.retained()
    _tamper(study, receipt, lambda r: r["run"].__setitem__("response", "tampered"))
    study.conn.execute("DROP TABLE source_extractions")
    study.conn.commit()
    _assert_status(study, INVALID, INVALID)


def test_valid_excluded_receipt_is_classified_without_leaking_child_text(study):
    study.retained(response="SECRET EXCLUDED RESPONSE")
    study.conn.execute("UPDATE source_documents SET excluded_from_analysis=1 WHERE id=?", (study.seed["doc_id"],))
    study.conn.commit()
    rows = _assert_status(study, NO, NO)
    assert "SECRET EXCLUDED RESPONSE" not in json.dumps(rows)
    assert all(row["evidence_refs"] == [] for row in rows.values())


def test_missing_exclusion_coverage_is_unsupported_not_classified_excluded(study):
    study.retained()
    study.conn.execute("ALTER TABLE source_documents DROP COLUMN excluded_from_analysis")
    study.conn.commit()
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)


def test_null_exclusion_coverage_remains_unknown_not_eligible(study):
    study.retained()
    study.conn.execute("UPDATE source_documents SET excluded_from_analysis=NULL WHERE id=?", (study.seed["doc_id"],))
    study.conn.commit()
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)


@pytest.mark.parametrize("timestamp", ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00"])
def test_retention_instant_outside_representable_utc_range_fails_closed(study, timestamp):
    receipt = study.retained()
    def mutate(r):
        r["run"]["created_at"] = timestamp
        r["run"]["completed_at"] = timestamp
        r["retention"]["retained_at"] = timestamp
    _tamper(study, receipt, mutate)
    _assert_status(study, INVALID, INVALID)


def test_unclassified_lineage_omission_cannot_become_negative_history(study, monkeypatch):
    import hermeneia.perspective_achievement_evidence as adapter
    study.retained()
    projection = project_study_lineage(study.conn)
    projection["items"] = [item for item in projection["items"] if item["record"]["table"] != TABLE]
    projection["coverage"]["omitted"][TABLE] = 1
    monkeypatch.setattr(adapter, "project_study_lineage", lambda conn: deepcopy(projection))
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)


@pytest.mark.parametrize("missing", ["source_extractions", "source_documents"])
def test_unknown_missing_reference_schema_refuses_negative_history(study, missing):
    study.retained()
    study.conn.execute("DROP TABLE " + missing)
    study.conn.commit()
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)


def test_missing_required_source_row_is_invalid_claimed_closure(study):
    study.retained()
    _drop_guard(study.conn, "source_extractions", "DELETE")
    study.conn.execute("DELETE FROM source_extractions WHERE id=?", (study.seed["extraction_ids"][0],))
    study.conn.commit()
    _assert_status(study, INVALID, INVALID)


def test_reversion_and_sibling_nodes_share_the_same_derived_family(study):
    root = study.saved("Root method")
    child = study.saved("Changed method", purpose="Challenge evidence.", predecessor=root)
    sibling = study.saved("Sibling method", purpose="Check context.", predecessor=root)
    reverted = study.saved("Root method", predecessor=child)
    for row in [root, child, sibling, reverted]:
        study.retained(row)
    _assert_status(study, EARNED, NO)


def test_saved_family_chain_not_current_leaf_drives_distinctness(study):
    a = study.saved("Root A")
    child = study.saved("Revision A", purpose="Challenge evidence.", predecessor=a)
    other = study.saved("Root B", purpose="Examine context.")
    study.retained(child)
    study.retained(other)
    _assert_status(study, EARNED, EARNED)


def test_legacy_upstream_family_preserves_explorer_but_refuses_second_opinion(study):
    root = study.saved("Legacy ancestor")
    child = study.saved("Executed child", purpose="Challenge evidence.", predecessor=root)
    study.retained(child)
    study.retained("close-reader")
    _drop_guard(study.conn, "perspectives", "UPDATE")
    study.conn.execute("UPDATE perspectives SET identity_scheme='perspective-label-v1' WHERE id=?", (root["id"],))
    study.conn.commit()
    _assert_status(study, EARNED, UNSUPPORTED)


@pytest.mark.parametrize("corruption", ["fingerprint", "cycle", "duplicate_relation"])
def test_invalid_upstream_family_keeps_node_evidence_but_refuses_only_possible_pair(study, corruption):
    root = study.saved("Ancestor root")
    intermediate = study.saved("Ancestor revision", purpose="Check evidence.", predecessor=root)
    leaf = study.saved("Executed leaf", purpose="Challenge evidence.", predecessor=intermediate)
    study.retained(leaf)
    study.retained("close-reader")
    if corruption == "fingerprint":
        _drop_guard(study.conn, "perspectives", "UPDATE")
        study.conn.execute("UPDATE perspectives SET definition_fingerprint='sha256:contradiction' WHERE id=?", (root["id"],))
    elif corruption == "cycle":
        study.conn.execute("INSERT INTO supersession_relations VALUES (?,?,?,?)", (leaf["id"], root["id"], "Injected cycle", START))
    else:
        study.conn.execute("INSERT INTO supersession_relations VALUES (?,?,?,?)", (root["id"], intermediate["id"], "Second relation same predecessor", END))
    study.conn.commit()
    _assert_status(study, EARNED, INVALID)


def test_revision_with_missing_edge_cannot_be_treated_as_new_root(study):
    root = study.saved()
    child = study.saved("Child", purpose="Challenge evidence.", predecessor=root)
    study.retained(child)
    _drop_guard(study.conn, "supersession_relations", "DELETE")
    study.conn.execute("DELETE FROM supersession_relations")
    study.conn.commit()
    _assert_status(study, INVALID, INVALID)


def test_multiple_incoming_relation_rows_are_ambiguous_even_same_parent(study):
    root = study.saved()
    child = study.saved("Child", purpose="Challenge evidence.", predecessor=root)
    study.retained(child)
    study.conn.execute("INSERT INTO supersession_relations VALUES (?,?,?,?)", (root["id"], child["id"], "Duplicate parent relation", END))
    study.conn.commit()
    _assert_status(study, INVALID, INVALID)


@pytest.mark.parametrize("parent", ["dangling", "cross_type"])
def test_incoming_non_perspective_parent_cannot_silently_create_fresh_family_root(study, parent):
    root = study.saved()
    study.retained(root)
    study.retained("close-reader")
    if parent == "dangling":
        _drop_guard(study.conn, "supersession_relations", "INSERT")
        parent_id = "missing-perspective-ancestor"
    else:
        parent_id = study.seed["doc_id"]
    study.conn.execute("INSERT INTO supersession_relations VALUES (?,?,?,?)", (parent_id, root["id"], "Unproven ancestry", START))
    study.conn.commit()
    _assert_status(study, EARNED, INVALID)


def test_readonly_adapter_and_evaluator_cannot_write_or_initialize_any_schema(study):
    study.retained()
    before_dump = tuple(study.conn.iterdump())
    before_bytes = study.path.read_bytes()
    changes = study.conn.total_changes
    denied = []
    writing = {getattr(sqlite3, name) for name in (
        "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE", "SQLITE_CREATE_TABLE",
        "SQLITE_CREATE_INDEX", "SQLITE_CREATE_TRIGGER", "SQLITE_CREATE_VIEW",
        "SQLITE_DROP_TABLE", "SQLITE_DROP_INDEX", "SQLITE_DROP_TRIGGER", "SQLITE_DROP_VIEW",
        "SQLITE_ALTER_TABLE", "SQLITE_ATTACH", "SQLITE_DETACH")}
    def authorize(action, arg1, arg2, database, source):
        if action in writing:
            denied.append((action, arg1, arg2))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    study.conn.execute("PRAGMA query_only=ON")
    study.conn.set_authorizer(authorize)
    try:
        _assert_status(study, EARNED, NO)
    finally:
        study.conn.set_authorizer(None)
    assert not denied
    assert study.conn.total_changes == changes
    assert tuple(study.conn.iterdump()) == before_dump
    assert study.path.read_bytes() == before_bytes


def test_readonly_evaluation_preserves_callers_pending_transaction(study):
    study.retained()
    study.conn.execute("CREATE TABLE test_pending_work(value TEXT)")
    study.conn.commit()
    study.conn.execute("BEGIN")
    study.conn.execute("INSERT INTO test_pending_work VALUES ('pending')")
    before = study.conn.total_changes
    _assert_status(study, EARNED, NO)
    assert study.conn.in_transaction
    assert study.conn.total_changes == before
    assert study.conn.execute("SELECT value FROM test_pending_work").fetchone()[0] == "pending"
    study.conn.rollback()
    assert study.conn.execute("SELECT COUNT(*) FROM test_pending_work").fetchone()[0] == 0


def test_evaluation_never_invokes_provider_or_key_lookup_even_if_modules_unavailable(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    script = r'''
import builtins, json, socket, sqlite3, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    prefixes = ('openai', 'anthropic', 'ollama', 'google.genai',
                'hermeneia.narrative.artist_providers', 'hermeneia.narrative.provider_registry')
    if any(name == prefix or name.startswith(prefix + '.') for prefix in prefixes):
        raise AssertionError('Provider import during evaluation: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
def forbidden(*args, **kwargs):
    raise AssertionError('Network during evaluation')
socket.create_connection = forbidden
socket.socket.connect = forbidden
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
from hermeneia.perspective_achievements import evaluate_perspective_achievements
conn = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
conn.execute('PRAGMA query_only=ON')
result = evaluate_perspective_achievements(read_perspective_achievement_evidence(conn))
assert [r['status'] for r in result['achievements']] == ['earned', 'earned']
conn.close()
print('provider-free')
'''
    env = {key: value for key, value in os.environ.items() if not key.endswith("_API_KEY")}
    result = subprocess.run([sys.executable, "-c", script, str(study.path)],
                            cwd=Path(__file__).parents[1], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "provider-free"


def test_achievement_evaluation_does_not_change_p1_p2_or_canonical_history(study):
    study.retained()
    projection = project_study_lineage(study.conn)
    current = {"governing_question": None, "perspective_available": False}
    capability_before = evaluate_capabilities(projection, current_state=current)
    guide_before = project_guided_study_cycle(projection, current_state=current)
    durable_before = tuple(study.conn.iterdump())
    _assert_status(study, EARNED, NO)
    after = project_study_lineage(study.conn)
    assert canonical_bytes(capability_before) == canonical_bytes(evaluate_capabilities(after, current_state=current))
    assert canonical_bytes(guide_before) == canonical_bytes(project_guided_study_cycle(after, current_state=current))
    assert tuple(study.conn.iterdump()) == durable_before


def test_mutable_highlight_change_updates_assessment_evidence_digest_without_rewriting_capture(study):
    from hermeneia.scope_resolution import resolve_scope_for_provider
    from test_scope_resolution import _selection_scope
    study.conn.execute(
        "INSERT INTO reader_highlights(id,source_document_id,page,source_locator,selected_text,note_text,created_at,updated_at) "
        "VALUES('captured-mark',?,2,'page:2:block:1','Alpha beta begins.','Original annotation',?,?)",
        (study.seed["doc_id"], START, START))
    study.conn.commit()
    scope_input = _selection_scope(study.seed, text="")
    scope_input["supporting"] = {"highlights": {"include": True, "ids": ["captured-mark"]}}
    scope = resolve_scope_for_provider(study.conn, scope_input)
    a = study.retained("close-reader", scope=scope)
    b = study.retained("skeptical-reader", scope=scope)
    before = evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))
    study.conn.execute("UPDATE reader_highlights SET note_text='Later annotation',updated_at=? WHERE id='captured-mark'", (END,))
    study.conn.commit()
    after = evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))
    assert before["evidence_sha256"] != after["evidence_sha256"]
    assert [row["status"] for row in before["achievements"]] == [EARNED, EARNED]
    assert [row["status"] for row in after["achievements"]] == [EARNED, EARNED]
    assert before["achievements"][1]["qualifying_receipt_ids"] == after["achievements"][1]["qualifying_receipt_ids"]
    from hermeneia.perspective_execution_receipts import load_retained_execution
    assert load_retained_execution(study.conn, a["id"]) == a
    assert load_retained_execution(study.conn, b["id"]) == b


def test_existing_wbs_export_restore_preserves_qualifying_evaluation(study, tmp_path):
    root = study.saved("Saved root")
    child = study.saved("Saved revision", purpose="Challenge evidence.", predecessor=root)
    study.retained(child)
    study.retained("contextual-reader")
    expected = _assert_status(study, EARNED, EARNED)
    before = study.path.read_bytes()
    bundle = tmp_path / "bundle"
    export_workspace_bundle(study.path, bundle, generated_at=START, workspace_id="synthetic")
    assert study.path.read_bytes() == before
    restored = tmp_path / "restored/workspace.db"
    restore_workspace(restored, bundle)
    conn = sqlite3.connect(restored)
    try:
        result = evaluate_perspective_achievements(read_perspective_achievement_evidence(conn))
    finally:
        conn.close()
    actual = {row["achievement_id"]: row for row in result["achievements"]}
    for identifier in expected:
        assert actual[identifier]["status"] == expected[identifier]["status"]
        assert actual[identifier]["qualifying_receipt_ids"] == expected[identifier]["qualifying_receipt_ids"]
        assert actual[identifier]["evidence_refs"] == expected[identifier]["evidence_refs"]


def test_existing_wbs_boundary_refuses_mismatched_hash_before_evaluation(study, tmp_path):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    bundle = tmp_path / "bundle"
    export_workspace_bundle(study.path, bundle, generated_at=START, workspace_id="synthetic")
    manifest = bundle / "manifest.json"
    value = json.loads(manifest.read_bytes())
    next(entry for entry in value["files"] if entry["path"] == "study/perspective_executions.json")["sha256"] = "0" * 64
    manifest.write_text(json.dumps(value))
    before = {path: path.read_bytes() for path in bundle.rglob("*") if path.is_file()}
    with pytest.raises(RestoreError):
        read_bundle(bundle)
    assert {path: path.read_bytes() for path in before} == before
