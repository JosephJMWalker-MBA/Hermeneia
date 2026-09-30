from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import sqlite3

import pytest

from hermeneia.perspective_execution_receipts import (
    SCHEMA, TABLE, canonical_bytes, capture_execution_run,
    ensure_perspective_execution_tables, execution_references,
    load_retained_execution, make_retained_receipt, receipt_from_row,
    store_retained_execution, validate_execution_references, validate_receipt,
)
from hermeneia.perspective_identity import frame_v2_row_from_draft, resolution_from_frame_v2_row
from hermeneia.perspective_runs import build_perspective_prompt, perspective_definition
from hermeneia.scope_resolution import resolve_scope_for_provider
from hermeneia.storage.sqlite import SQLiteStore
from test_scope_resolution import _seed_scope_db, _selection_scope

START = "2026-09-30T10:00:00+00:00"
END = "2026-09-30T10:00:01+00:00"
RETAINED = "2026-09-30T10:00:02+00:00"
RUN_ID = "4708aaad-0163-4501-a374-ac6e6b7c4e39"
OUTPUT = "  A proposed reading.\nUnicode ✓ remains exact.\n"


@pytest.fixture
def receipt_conn(tmp_path):
    path = tmp_path / "receipt.db"
    seed = _seed_scope_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    yield conn, seed
    conn.close()


def captured_run(conn, seed, *, definition=None, metadata=None, run_id=RUN_ID):
    definition = definition or perspective_definition("close-reader")
    scope = resolve_scope_for_provider(conn, _selection_scope(seed, text=""))
    question = "  What does the evidence support?\n"
    prompt = build_perspective_prompt(definition, question=question, scope_receipt=scope)
    return capture_execution_run(
        definition, question=question, scope_receipt=scope,
        execution={"provider_id": "stub", "model_id": "deterministic-stub", "deterministic": True},
        response=OUTPUT, prompt=prompt, perspective_metadata=metadata,
        created_at=START, completed_at=END, run_id=run_id,
    )


def _resign(receipt):
    receipt["id"] = "perspective-execution-receipt:sha256:" + hashlib.sha256(
        canonical_bytes({key: value for key, value in receipt.items() if key != "id"})
    ).hexdigest()
    return receipt


def test_transient_capture_does_not_write_or_retain(receipt_conn):
    conn, seed = receipt_conn
    before = conn.total_changes
    run = captured_run(conn, seed)
    assert conn.total_changes == before
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 0
    assert run["status"] == "succeeded"
    assert "retention" not in run


def test_capture_binds_exact_question_prompt_output_and_scope(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    assert run["question"] == "  What does the evidence support?\n"
    assert run["response"] == OUTPUT
    assert run["prompt_version"] == "perspective-run/v1"
    for text_field in ("question", "prompt", "response"):
        assert run[f"{text_field}_sha256"] == "sha256:" + hashlib.sha256(run[text_field].encode("utf-8")).hexdigest()
    assert run["scope_sha256"] == "sha256:" + hashlib.sha256(canonical_bytes(run["scope_receipt"])).hexdigest()
    assert run["created_at"] == START and run["completed_at"] == END
    assert run["execution"] == {"provider_id": "stub", "model_id": "deterministic-stub", "deterministic": True}
    refs = execution_references(run)
    assert {"table": "source_documents", "key": {"id": seed["doc_id"]}} in refs
    assert all({"table": "source_extractions", "key": {"id": identifier}} in refs for identifier in seed["extraction_ids"])


def test_capture_owns_deep_snapshot(receipt_conn):
    conn, seed = receipt_conn
    definition = perspective_definition("close-reader")
    scope = resolve_scope_for_provider(conn, _selection_scope(seed, text=""))
    execution = {"provider_id": "stub", "model_id": "stub", "options": {"temperature": 0}}
    run = capture_execution_run(definition, question="Q", scope_receipt=scope, execution=execution,
                                response=OUTPUT, prompt="P", created_at=START, completed_at=END)
    scope["primary"]["text"] = "changed"
    execution["options"]["temperature"] = 99
    assert run["scope_receipt"]["primary"]["text"] != "changed"
    assert run["execution"]["options"]["temperature"] == 0


def test_explicit_retention_installs_exactly_one_canonical_record(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    receipt = store_retained_execution(conn, run, retained_at=RETAINED)
    assert receipt["schema"] == SCHEMA
    assert receipt["retention"] == {"decision": "retain", "actor": "local_steward", "actor_identity": "unknown", "retained_at": RETAINED}
    assert receipt["run"] == run
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 1
    assert load_retained_execution(conn, receipt["id"]) == receipt
    assert "agreement" not in receipt["retention"]


def test_retention_is_idempotent_for_same_exact_run(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    first = store_retained_execution(conn, run, retained_at=RETAINED)
    second = store_retained_execution(conn, deepcopy(run), retained_at="2026-10-01T00:00:00+00:00")
    assert first == second
    assert second["retention"]["retained_at"] == RETAINED
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 1


def test_same_run_id_conflicting_result_refuses(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    original = store_retained_execution(conn, run, retained_at=RETAINED)
    changed = deepcopy(run)
    changed["response"] = "Different output"
    changed["response_sha256"] = "sha256:" + hashlib.sha256(changed["response"].encode()).hexdigest()
    with pytest.raises(ValueError, match="different|conflict"):
        store_retained_execution(conn, changed, retained_at=RETAINED)
    assert load_retained_execution(conn, original["id"]) == original


@pytest.mark.parametrize("field", ["question", "response", "prompt"])
def test_tampered_text_fails_digest_even_if_receipt_is_rebound(receipt_conn, field):
    conn, seed = receipt_conn
    receipt = make_retained_receipt(captured_run(conn, seed), retained_at=RETAINED)
    receipt["run"][field] += " tampered"
    with pytest.raises(ValueError, match="digest"):
        validate_receipt(_resign(receipt))


def test_tampered_scope_fails_digest(receipt_conn):
    conn, seed = receipt_conn
    receipt = make_retained_receipt(captured_run(conn, seed), retained_at=RETAINED)
    receipt["run"]["scope_receipt"]["primary"]["text"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        validate_receipt(_resign(receipt))


def test_detached_receipt_identity_refuses(receipt_conn):
    conn, seed = receipt_conn
    receipt = make_retained_receipt(captured_run(conn, seed), retained_at=RETAINED)
    receipt["run"]["execution"]["model_id"] = "other-model"
    with pytest.raises(ValueError, match="identity|digest"):
        validate_receipt(receipt)


@pytest.mark.parametrize("mutation", ["missing", "extra", "retention", "status", "timestamp"])
def test_malformed_canonical_records_fail_closed(receipt_conn, mutation):
    conn, seed = receipt_conn
    receipt = make_retained_receipt(captured_run(conn, seed), retained_at=RETAINED)
    if mutation == "missing": del receipt["run"]["response_sha256"]
    if mutation == "extra": receipt["activity"] = "fake"
    if mutation == "retention": receipt["retention"]["decision"] = "accepted"
    if mutation == "status": receipt["run"]["status"] = "failed"
    if mutation == "timestamp": receipt["run"]["completed_at"] = "unknown"
    with pytest.raises(ValueError): validate_receipt(_resign(receipt))


def test_raw_json_duplicate_keys_are_rejected(receipt_conn):
    conn, seed = receipt_conn
    receipt = make_retained_receipt(captured_run(conn, seed), retained_at=RETAINED)
    text = canonical_bytes(receipt).decode()
    text = text.replace('"schema":', '"schema":"shadow","schema":', 1)
    with pytest.raises(ValueError, match="duplicate"):
        receipt_from_row({"id": receipt["id"], "run_id": RUN_ID, "receipt_json": text})


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_json_is_rejected(value):
    with pytest.raises(ValueError): canonical_bytes({"value": value})


def test_row_identity_and_run_id_cannot_detach(receipt_conn):
    conn, seed = receipt_conn
    receipt = make_retained_receipt(captured_run(conn, seed), retained_at=RETAINED)
    for field in ("id", "run_id"):
        row = {"id": receipt["id"], "run_id": RUN_ID, "receipt_json": canonical_bytes(receipt).decode()}
        row[field] = "detached"
        with pytest.raises(ValueError, match="binding"):
            receipt_from_row(row)


def test_missing_reference_refuses_before_retention(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    run["scope_receipt"] = json.loads(json.dumps(run["scope_receipt"]).replace(seed["extraction_ids"][0], "missing"))
    run["scope_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(run["scope_receipt"])).hexdigest()
    with pytest.raises(ValueError, match="extraction|reference"):
        store_retained_execution(conn, run, retained_at=RETAINED)
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 0


def test_wrong_document_hash_refuses(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    run["scope_receipt"]["primary"]["source_document_hash"] = "different"
    run["scope_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(run["scope_receipt"])).hexdigest()
    with pytest.raises(ValueError, match="hash"):
        validate_execution_references(conn, run)


def test_exclusion_blocks_current_use_but_not_historical_archival_closure(receipt_conn):
    conn, seed = receipt_conn
    receipt = store_retained_execution(conn, captured_run(conn, seed), retained_at=RETAINED)
    conn.execute("UPDATE source_documents SET excluded_from_analysis=1 WHERE id=?", (seed["doc_id"],))
    conn.commit()
    validate_execution_references(conn, receipt)
    with pytest.raises(ValueError, match="excluded"):
        validate_execution_references(conn, receipt, require_eligible=True)
    assert load_retained_execution(conn, receipt["id"]) == receipt


def test_saved_frame_binds_exact_immutable_revision(receipt_conn):
    conn, seed = receipt_conn
    store = SQLiteStore(conn.execute("PRAGMA database_list").fetchone()[2])
    row, _ = frame_v2_row_from_draft({"label": "Exact frame", "purpose": "Inspect exact evidence", "questions": ["What supports this?"]}, declared_by="local_steward", declared_date=START)
    store.insert_frame_perspective(row)
    store.close()
    resolved = resolution_from_frame_v2_row(row)
    run = captured_run(conn, seed, definition=resolved.definition, metadata=resolved.receipt_metadata)
    assert run["perspective"]["id"] == row["id"]
    assert run["perspective"]["origin"] == "canonical_saved"
    assert {"table": "perspectives", "key": {"id": row["id"]}} in execution_references(run)
    receipt = store_retained_execution(conn, run, retained_at=RETAINED)
    assert load_retained_execution(conn, receipt["id"]) == receipt


def test_unowned_custom_draft_cannot_create_execution_claim(receipt_conn):
    conn, seed = receipt_conn
    definition = replace(perspective_definition("close-reader"), id="transient:draft", version="draft")
    with pytest.raises(ValueError, match="supported|built-in|Perspective"):
        captured_run(conn, seed, definition=definition)


def test_changed_mutable_question_does_not_rewrite_captured_input(receipt_conn):
    conn, seed = receipt_conn
    receipt = store_retained_execution(conn, captured_run(conn, seed), retained_at=RETAINED)
    conn.execute("INSERT INTO workspace_investigation(id,thesis,purpose,lenses,reconsider,created_at,updated_at) VALUES('current','New question','','[]','',?,?)", (END, END))
    conn.commit()
    validate_execution_references(conn, receipt)
    assert load_retained_execution(conn, receipt["id"])["run"]["question"] == "  What does the evidence support?\n"


def test_later_mutable_highlight_edit_does_not_rewrite_run_or_input(receipt_conn):
    conn, seed = receipt_conn
    conn.execute("INSERT INTO reader_highlights(id,source_document_id,page,source_locator,selected_text,note_text,created_at,updated_at) VALUES('mark',?,2,'page:2:block:1','Alpha beta begins.','Original note',?,?)", (seed["doc_id"], START, START))
    conn.commit()
    scope_input = _selection_scope(seed, text="")
    scope_input["supporting"] = {"highlights": {"include": True, "ids": ["mark"]}}
    scope = resolve_scope_for_provider(conn, scope_input)
    definition = perspective_definition("close-reader")
    prompt = build_perspective_prompt(definition, question="Q", scope_receipt=scope)
    run = capture_execution_run(definition, question="Q", scope_receipt=scope,
        execution={"provider_id": "stub", "model_id": "stub"}, response=OUTPUT,
        prompt=prompt, created_at=START, completed_at=END)
    receipt = store_retained_execution(conn, run, retained_at=RETAINED)
    conn.execute("UPDATE reader_highlights SET selected_text='Later authored text',note_text='Later note',question_text='Later question',status='dismissed' WHERE id='mark'")
    conn.commit()
    validate_execution_references(conn, receipt, require_eligible=True)
    loaded = load_retained_execution(conn, receipt["id"])
    assert loaded == receipt
    assert loaded["run"]["scope_receipt"]["supporting"][0]["text"] == "Alpha beta begins."
    assert {"table": "reader_highlights", "key": {"id": "mark"}} in execution_references(receipt)


def test_new_saved_revision_does_not_rebind_historical_execution(receipt_conn):
    conn, seed = receipt_conn
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    store = SQLiteStore(path)
    draft = {"label": "Exact frame", "purpose": "Inspect evidence", "questions": ["What supports this?"]}
    row, _ = frame_v2_row_from_draft(draft, declared_by="local_steward", declared_date=START)
    store.insert_frame_perspective(row)
    resolved = resolution_from_frame_v2_row(row)
    run = captured_run(conn, seed, definition=resolved.definition, metadata=resolved.receipt_metadata)
    receipt = store_retained_execution(conn, run, retained_at=RETAINED)
    revision, _ = frame_v2_row_from_draft({**draft, "purpose": "Challenge evidence"}, declared_by="local_steward", declared_date=RETAINED, predecessor_perspective_id=row["id"])
    store.insert_perspective_revision(row["id"], revision, "Intentional revision", RETAINED)
    store.close()
    validate_execution_references(conn, receipt)
    assert load_retained_execution(conn, receipt["id"]) == receipt
    assert receipt["run"]["perspective"]["id"] != revision["id"]


@pytest.mark.parametrize("statement", ["UPDATE perspective_execution_receipts SET receipt_json='{}'", "DELETE FROM perspective_execution_receipts", "INSERT OR REPLACE INTO perspective_execution_receipts SELECT * FROM perspective_execution_receipts"])
def test_receipts_are_database_enforced_append_only(receipt_conn, statement):
    conn, seed = receipt_conn
    receipt = store_retained_execution(conn, captured_run(conn, seed), retained_at=RETAINED)
    with pytest.raises(sqlite3.IntegrityError): conn.execute(statement)
    conn.rollback()
    assert load_retained_execution(conn, receipt["id"]) == receipt


def test_failed_insert_leaves_no_half_retained_record(receipt_conn):
    conn, seed = receipt_conn
    conn.execute(f"CREATE TRIGGER injected_failure AFTER INSERT ON {TABLE} BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        store_retained_execution(conn, captured_run(conn, seed), retained_at=RETAINED)
    assert not conn.in_transaction
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 0


def test_retention_respects_caller_transaction(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    conn.execute("CREATE TABLE marker(value TEXT)")
    conn.commit()
    conn.execute("BEGIN")
    conn.execute("INSERT INTO marker VALUES('before')")
    store_retained_execution(conn, run, retained_at=RETAINED)
    assert conn.in_transaction
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM marker").fetchone()[0] == 0
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 0


def test_failed_nested_retention_preserves_caller_pending_work(receipt_conn):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    conn.execute("CREATE TABLE marker(value TEXT)")
    conn.execute(f"CREATE TRIGGER injected_failure AFTER INSERT ON {TABLE} BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    conn.commit()
    conn.execute("BEGIN")
    conn.execute("INSERT INTO marker VALUES('before')")
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        store_retained_execution(conn, run, retained_at=RETAINED)
    assert conn.in_transaction
    assert conn.execute("SELECT value FROM marker").fetchone()[0] == "before"
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 0
    conn.rollback()


def test_schema_addition_preserves_old_workspace_rows(receipt_conn):
    conn, seed = receipt_conn
    rows = [tuple(row) for row in conn.execute("SELECT * FROM source_documents")]
    conn.execute(f"DROP TABLE {TABLE}")
    conn.execute("UPDATE schema_version SET version=17")
    conn.commit()
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    SQLiteStore(path).close()
    assert [tuple(row) for row in conn.execute("SELECT * FROM source_documents")] == rows
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 18
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 0


def test_readers_never_initialize_missing_schema():
    conn = sqlite3.connect(":memory:")
    assert load_retained_execution(conn, "absent") is None
    assert not conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()


def test_existing_schema17_app_startup_allows_first_explicit_keep(receipt_conn):
    from hermeneia.web.app import create_app

    conn, seed = receipt_conn
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    original = [tuple(row) for row in conn.execute("SELECT * FROM source_documents")]
    conn.execute(f"DROP TABLE {TABLE}")
    conn.execute("UPDATE schema_version SET version=17")
    conn.commit()
    create_app(path)
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone()
    assert [tuple(row) for row in conn.execute("SELECT * FROM source_documents")] == original
    receipt = store_retained_execution(conn, captured_run(conn, seed), retained_at=RETAINED)
    assert load_retained_execution(conn, receipt["id"]) == receipt


@pytest.mark.parametrize("mutation", ["corpus", "inclusion", "compiler", "materialized_primary", "packet"])
def test_resigned_unsupported_scope_contract_is_rejected(receipt_conn, mutation):
    conn, seed = receipt_conn
    run = captured_run(conn, seed)
    scope = run["scope_receipt"]
    if mutation == "corpus": scope["excluded"]["entire_corpus"] = False
    if mutation == "inclusion": scope["included"]["highlights"] = True
    if mutation == "compiler": scope["materialization"]["compiler"] = "guessed-from-current-state"
    if mutation == "materialized_primary": scope["materialization"]["primary"] = {}
    if mutation == "packet": scope["materialization"]["study_packet"] = {"invented": "outside evidence"}
    run["scope_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(scope)).hexdigest()
    with pytest.raises(ValueError): make_retained_receipt(run, retained_at=RETAINED)
