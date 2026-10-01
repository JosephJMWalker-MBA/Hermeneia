"""P3 projection boundaries over isolated, explicitly synthetic study evidence."""
from copy import deepcopy
from pathlib import Path
import json
import socket
import sqlite3

import pytest

from hermeneia.capabilities import evaluate_capabilities, load_capability_registry, CapabilityRegistryError
from hermeneia.guided_study_cycle import project_guided_study_cycle
from hermeneia.perspective_execution_receipts import (
    TABLE, canonical_bytes, capture_execution_run, store_retained_execution,
)
from hermeneia.perspective_runs import perspective_definition, build_perspective_prompt
from hermeneia.scope_resolution import resolve_scope_for_provider
from hermeneia.study_lineage import project_study_lineage, serialize_projection
from test_scope_resolution import _seed_scope_db, _selection_scope


START = "2026-09-30T10:00:00+00:00"
END = "2026-09-30T10:00:03+00:00"
KEPT = "2026-09-30T10:01:00+00:00"
OLD_REGISTRY = Path(__file__).parents[1] / "hermeneia/data/capability-registry-v1.json"


def _retained(tmp_path):
    db = tmp_path / "synthetic.db"
    seed = _seed_scope_db(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    scope = resolve_scope_for_provider(conn, _selection_scope(seed,
        text="beta begins.\nMiddle line with Unicode ✓ and punctuation.\nOmega"))
    definition = perspective_definition("close-reader")
    question = "What does this exact passage support? ✓"
    prompt = build_perspective_prompt(definition, question=question,
        scope_receipt=scope, scope_materialization=scope["materialization"])
    run = capture_execution_run(definition, question=question, scope_receipt=scope,
        execution={"provider_id": "synthetic-test", "model_id": "deterministic-fixture",
                   "stub": True, "temperature": None},
        response="Synthetic model output.\nExact trailing newline.\n", prompt=prompt,
        created_at=START, completed_at=END)
    receipt = store_retained_execution(conn, run, retained_at=KEPT)
    conn.commit()
    return db, conn, run, receipt


def _execution(projection):
    return [i for i in projection["items"] if i["record"]["table"] == TABLE]


def _explore(result):
    return next(r for r in result["capabilities"] if r["capability_id"] == "explore_perspective")


def test_lineage_preserves_typed_receipt_identity_exact_provenance_and_retention_time(tmp_path):
    _, conn, run, receipt = _retained(tmp_path)
    conn.execute("INSERT INTO perspectives (id,name,created_at) VALUES (?, 'Same ID different type', ?)", (receipt["id"], START))
    conn.commit()
    projection = project_study_lineage(conn)
    item, = _execution(projection)
    assert item["record"] == {"table": TABLE, "key": {"id": receipt["id"]}}
    assert item["record_type"] == "retained_perspective_execution"
    assert item["event"] == "recorded"
    assert item["authorship"] == "model"
    assert "not agreement" in item["provenance"]["basis"]
    assert item["timestamp"]["field"] == "retention.retained_at"
    assert item["timestamp"]["value"] == KEPT
    assert item["provenance"]["execution_created_at"] == START
    assert item["provenance"]["execution_completed_at"] == END
    assert item["provenance"]["execution"] == run["execution"]
    assert item["provenance"]["perspective"] == run["perspective"]
    assert item["provenance"]["retention"] == receipt["retention"]
    assert item["content"] == run["response"]
    assert json.loads(item["record_data"]["receipt_json"]) == receipt
    assert {r["table"] for r in item["provenance"]["references"]} == {"source_documents", "source_extractions"}
    assert item["contexts"] == [
        {"kind": "perspective_execution", "receipt_id": receipt["id"]},
        {"kind": "reader", "document_id": "scope-doc", "page": 2},
    ]
    same = [i for i in projection["items"] if i["record"]["key"] == {"id": receipt["id"]}]
    assert {i["record"]["table"] for i in same} == {TABLE, "perspectives"}


def test_receipt_projection_and_export_are_read_only_without_network_or_schema_init(tmp_path, monkeypatch):
    db, conn, _, _ = _retained(tmp_path)
    before = tuple(conn.iterdump())
    conn.close()
    original_bytes = db.read_bytes()
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    ro.execute("PRAGMA query_only=ON")
    ro.execute("BEGIN")

    def forbidden(*args, **kwargs):
        raise AssertionError("Receipt projection cannot open a connection or call a provider")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    a = project_study_lineage(ro)
    b = project_study_lineage(ro)
    assert serialize_projection(a) == serialize_projection(b)
    assert tuple(ro.iterdump()) == before
    ro.close()
    assert db.read_bytes() == original_bytes


def test_excluded_source_hides_all_captured_input_output_and_capability_support(tmp_path):
    _, conn, _, _ = _retained(tmp_path)
    conn.execute("UPDATE source_documents SET excluded_from_analysis=1 WHERE id='scope-doc'")
    conn.commit()
    projection = project_study_lineage(conn)
    assert not _execution(projection)
    assert projection["coverage"]["omitted"][TABLE] == 1
    assert b"Synthetic model output" not in serialize_projection(projection)
    assert _explore(evaluate_capabilities(projection))["status"] != "already_exercised_under_supported_evidence"


def test_corrupt_binding_is_omitted_instead_of_gaining_historical_support(tmp_path):
    _, conn, _, receipt = _retained(tmp_path)
    trigger = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND sql LIKE '%UPDATE%'", (TABLE,)).fetchone()[0]
    conn.execute(f'DROP TRIGGER "{trigger}"')
    corrupted = deepcopy(receipt)
    corrupted["run"]["response"] = "tampered"
    conn.execute(f"UPDATE {TABLE} SET receipt_json=?", (canonical_bytes(corrupted).decode(),))
    conn.commit()
    projection = project_study_lineage(conn)
    assert not _execution(projection)
    assert projection["coverage"]["omitted"][TABLE] == 1
    assert _explore(evaluate_capabilities(projection))["status"] != "already_exercised_under_supported_evidence"


def test_missing_evidence_ancestor_hides_receipt(tmp_path):
    _, conn, _, _ = _retained(tmp_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    triggers = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='source_extractions' AND sql LIKE '%DELETE%'").fetchall()
    for trigger in triggers:
        conn.execute(f'DROP TRIGGER "{trigger[0]}"')
    conn.execute("DELETE FROM source_extractions WHERE id='scope-ex-1'")
    conn.commit()
    projection = project_study_lineage(conn)
    assert not _execution(projection)
    assert projection["coverage"]["omitted"][TABLE] == 1


def test_legacy_workspace_projects_without_initializing_receipt_schema():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA query_only=ON")
    projection = project_study_lineage(conn)
    assert TABLE in projection["coverage"]["missing_tables"]
    assert not conn.execute("SELECT name FROM sqlite_master").fetchall()
    row = _explore(evaluate_capabilities(projection))
    assert row["status"] != "already_exercised_under_supported_evidence"


def test_new_rule_supports_only_narrow_retained_result_while_old_rule_stays_unsupported(tmp_path):
    _, conn, _, receipt = _retained(tmp_path)
    projection = project_study_lineage(conn)
    # Today's mutable inquiry readiness can be absent despite the captured run.
    current = {"governing_question": None, "perspective_available": False}
    new = _explore(evaluate_capabilities(projection, current_state=current))
    assert new["definition_version"] == "1.1.0"
    assert new["status"] == "already_exercised_under_supported_evidence"
    assert new["availability"] != "available"
    assert any(r.get("record") == {"table": TABLE, "key": {"id": receipt["id"]}} for r in new["evidence_refs"])
    old = _explore(evaluate_capabilities(projection, load_capability_registry(OLD_REGISTRY),
        current_state={"governing_question": "Ready?", "perspective_available": True}))
    assert old["definition_version"] == "1.0.0"
    assert old["status"] == "not_yet_available"  # Original evidence prerequisite is still absent.
    assert any("do not prove" in note for note in old["coverage_or_unknown_notes"])
    assert not any(r.get("record", {}).get("table") == TABLE for r in old["evidence_refs"])


def test_rule_versions_are_narrow_and_other_definitions_are_unchanged():
    old = load_capability_registry(OLD_REGISTRY)
    new = load_capability_registry()
    assert old["registry_version"] == "1.0.0"
    assert new["registry_version"] == "1.1.0"
    assert [r for r in old["capabilities"] if r["capability_id"] != "explore_perspective"] == [r for r in new["capabilities"] if r["capability_id"] != "explore_perspective"]
    old_explore = next(r for r in old["capabilities"] if r["capability_id"] == "explore_perspective")
    old_explore["positive_evidence"] = [{"fact": "retained_perspective_execution", "minimum": 1}]
    with pytest.raises(CapabilityRegistryError):
        evaluate_capabilities(project_study_lineage(sqlite3.connect(":memory:")), old)


def test_guided_cycle_consumes_supported_receipt_without_award_or_write(tmp_path):
    _, conn, _, _ = _retained(tmp_path)
    before = tuple(conn.iterdump())
    lineage = project_study_lineage(conn)
    guide = project_guided_study_cycle(lineage,
        current_state={"governing_question": "Ready?", "perspective_available": True})
    step = next(r for r in guide["steps"] if r["capability_id"] == "explore_perspective")
    assert step["status"] == "historically_exercised"
    assert step["history_support"]["status"] == "supported"
    assert guide["registry_version"] == "1.1.0"
    assert tuple(conn.iterdump()) == before
    assert conn.execute("SELECT count(*) FROM achievement_awards").fetchone()[0] == 0
    assert all(ref.get("record", {}).get("table") != "achievement_awards"
               for row in guide["steps"] for ref in row["evidence_or_state_basis"])
