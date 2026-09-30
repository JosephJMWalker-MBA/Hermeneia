"""Exact retained execution portability and fail-closed bundle coverage."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

import pytest

from hermeneia.perspective_execution_receipts import (
    capture_execution_run,
    load_retained_execution,
    store_retained_execution,
)
from hermeneia.perspective_identity import frame_v2_row_from_draft, resolution_from_frame_v2_row
from hermeneia.perspective_runs import build_perspective_prompt, perspective_definition
from hermeneia.scope_resolution import resolve_scope_for_provider
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study_lineage import project_study_lineage
from hermeneia.workspace import RestoreError, export_workspace_bundle, preview_restore, read_bundle, restore_workspace
from hermeneia.workspace import restore as restore_module
from hermeneia.workspace import export as export_module
from hermeneia.workspace.export import (
    PERSPECTIVE_EXECUTION_CAPABILITY,
    PERSPECTIVE_EXECUTION_FILE,
    PerspectiveExecutionExportError,
)

TIME = "2026-09-30T10:00:00+00:00"
TEXT = "Exact source evidence."
TABLE = "perspective_execution_receipts"


def _connection(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _seed(path: Path, *, saved=False):
    store = SQLiteStore(path)
    conn = store._conn
    conn.execute(
        """INSERT INTO source_documents
        (id, original_filename, file_hash, total_pages, registered_at, compiler_version)
        VALUES ('document', 'synthetic.txt', 'source-hash', 1, ?, 'test')""", (TIME,),
    )
    conn.execute(
        """INSERT INTO source_extractions
        (id, document_id, page, region, raw_text, parser, parser_version, coordinates,
         source_locator, source_hash, hash, extracted_at)
        VALUES ('extraction', 'document', 1, 'block:0', ?, 'test', '1', '{}',
                'page:1:block:0', 'source-hash', 'extraction-hash', ?)""", (TEXT, TIME),
    )
    conn.execute(
        """INSERT INTO reader_highlights
        (id, source_document_id, page, source_locator, selected_text, created_at, updated_at)
        VALUES ('highlight', 'document', 1, 'page:1:block:0', ?, ?, ?)""", (TEXT, TIME, TIME),
    )
    conn.commit()
    metadata = None
    definition = perspective_definition("close-reader")
    if saved:
        row, _ = frame_v2_row_from_draft(
            {"label": "Saved synthetic frame", "purpose": "Inspect exact evidence.",
             "questions": ["What is supported?"], "challenges": [], "limitations": []},
            declared_by="local-steward", declared_date=TIME,
        )
        store.insert_frame_perspective(row)
        resolution = resolution_from_frame_v2_row(row)
        definition, metadata = resolution.definition, resolution.receipt_metadata
    point = {"block_index": 0, "source_locator": "page:1:block:0",
             "source_locators": ["page:1:block:0"], "extraction_ids": ["extraction"]}
    span = {"coordinate_space": "reader_projection", "page": 1,
            "source_locators": ["page:1:block:0"], "extraction_ids": ["extraction"],
            "start": {**point, "offset": 0}, "end": {**point, "offset": len(TEXT)}}
    scope = resolve_scope_for_provider(conn, {
        "primary": {"source_document_id": "document", "page": 1, "text": TEXT,
                    "locator": "reader-span:v1:" + quote(json.dumps(span))},
        "supporting": {"highlights": {"include": True, "ids": ["highlight"]}},
    })
    question = "What does this exact evidence support?"
    run = capture_execution_run(
        definition, question=question, scope_receipt=scope,
        execution={"provider_id": "deterministic-stub", "model_id": "stub-v1",
                   "temperature": 0, "runtime_host": "none"},
        response="Exact machine output.\nΩ", prompt=build_perspective_prompt(
            definition, question=question, scope_receipt=scope),
        perspective_metadata=metadata, created_at=TIME,
        completed_at="2026-09-30T10:01:00+00:00",
    )
    receipt = store_retained_execution(conn, run)
    store.close()
    return receipt


def _export(path, destination):
    return export_workspace_bundle(path, destination, generated_at=TIME, workspace_id="synthetic")


def _receipt_rows(path):
    conn = _connection(path)
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {TABLE} ORDER BY id")]
    finally:
        conn.close()


def _rewrite_component(bundle, rows):
    data = (json.dumps(rows, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    (bundle / PERSPECTIVE_EXECUTION_FILE).write_bytes(data)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    for entry in manifest["files"]:
        if entry["path"] == PERSPECTIVE_EXECUTION_FILE:
            entry["sha256"] = hashlib.sha256(data).hexdigest()
    manifest["counts"][TABLE] = len(rows) if isinstance(rows, list) else 0
    manifest_path.write_text(json.dumps(manifest))


@pytest.mark.parametrize("saved", [False, True])
def test_export_restore_preserves_exact_receipt_and_typed_lineage(tmp_path, saved):
    source, restored = tmp_path / "source/workspace.db", tmp_path / "restored/workspace.db"
    receipt = _seed(source, saved=saved)
    before = source.read_bytes()
    bundle = tmp_path / "bundle"
    manifest = _export(source, bundle)
    assert source.read_bytes() == before
    assert PERSPECTIVE_EXECUTION_CAPABILITY in manifest["required_capabilities"]
    assert manifest["counts"][TABLE] == 1
    entry = next(entry for entry in manifest["files"] if entry["path"] == PERSPECTIVE_EXECUTION_FILE)
    assert entry["role"] == "canonical"
    assert json.loads((bundle / PERSPECTIVE_EXECUTION_FILE).read_bytes()) == _receipt_rows(source)
    result = restore_workspace(restored, bundle)
    assert result["restored"][TABLE] == 1
    assert result["coverage"][TABLE]["status"] == "covered"
    assert _receipt_rows(source) == _receipt_rows(restored)
    conn = _connection(restored)
    try:
        assert load_retained_execution(conn, receipt["id"]) == receipt
    finally:
        conn.close()
    views = []
    for path in (source, restored):
        conn = _connection(path)
        try:
            views.append([item for item in project_study_lineage(conn)["items"]
                          if item["record"]["table"] == TABLE])
        finally:
            conn.close()
    assert len(views[0]) == 1
    assert views[0] == views[1]


def test_bundle_content_is_deterministic_and_reexports_exactly(tmp_path):
    source = tmp_path / "source/workspace.db"
    _seed(source, saved=True)
    first, second, third = (tmp_path / label for label in ("first", "second", "third"))
    _export(source, first)
    _export(source, second)
    assert (first / PERSPECTIVE_EXECUTION_FILE).read_bytes() == (second / PERSPECTIVE_EXECUTION_FILE).read_bytes()
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    restored = tmp_path / "restored/workspace.db"
    restore_workspace(restored, first)
    _export(restored, third)
    assert (first / PERSPECTIVE_EXECUTION_FILE).read_bytes() == (third / PERSPECTIVE_EXECUTION_FILE).read_bytes()


def test_empty_category_is_covered_without_claiming_absent_history(tmp_path):
    source = tmp_path / "source/workspace.db"
    SQLiteStore(source).close()
    bundle = tmp_path / "bundle"
    _export(source, bundle)
    preview = preview_restore(tmp_path / "restored.db", bundle)
    assert preview["would_create"][TABLE] == 0
    assert preview["coverage"][TABLE] == {
        "status": "covered", "extant_records": 0,
        "reason": "Extant retained-receipt category covered; no complete historical activity claim.",
    }


def test_legacy_bundle_missing_category_returns_unsupported_not_zero_activity(tmp_path):
    source = tmp_path / "source/workspace.db"
    SQLiteStore(source).close()
    conn = _connection(source)
    conn.execute(f"DROP TABLE {TABLE}")
    conn.close()
    bundle = tmp_path / "bundle"
    manifest = _export(source, bundle)
    assert PERSPECTIVE_EXECUTION_CAPABILITY not in manifest.get("required_capabilities", [])
    assert not (bundle / PERSPECTIVE_EXECUTION_FILE).exists()
    preview = preview_restore(tmp_path / "restored.db", bundle)
    assert preview["coverage"][TABLE]["status"] == "unsupported"
    assert TABLE not in preview["would_create"]
    result = restore_workspace(tmp_path / "restored.db", bundle)
    assert result["coverage"][TABLE]["status"] == "unsupported"
    assert TABLE not in result["restored"]
    assert _receipt_rows(tmp_path / "restored.db") == []


@pytest.mark.parametrize("damage", ["no_capability", "missing_file", "unlisted_file", "duplicate_manifest", "wrong_role", "hash", "count"])
def test_incomplete_or_ambiguous_receipt_component_refuses(tmp_path, damage):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source)
    _export(source, bundle)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    entry = next(entry for entry in manifest["files"] if entry["path"] == PERSPECTIVE_EXECUTION_FILE)
    if damage == "no_capability":
        manifest["required_capabilities"].remove(PERSPECTIVE_EXECUTION_CAPABILITY)
    elif damage == "missing_file":
        (bundle / PERSPECTIVE_EXECUTION_FILE).unlink()
    elif damage == "unlisted_file":
        manifest["files"].remove(entry)
    elif damage == "duplicate_manifest":
        manifest["files"].append(dict(entry))
    elif damage == "wrong_role":
        entry["role"] = "derived"
    elif damage == "hash":
        entry["sha256"] = "0" * 64
    else:
        manifest["counts"][TABLE] = 0
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RestoreError):
        preview_restore(tmp_path / "restored.db", bundle)
    assert not (tmp_path / "restored.db").exists()


@pytest.mark.parametrize("damage", ["not_list", "extra_field", "identity", "run_identity", "receipt_json", "duplicate_receipt", "output"])
def test_malformed_payload_refuses_even_when_component_hash_is_updated(tmp_path, damage):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source)
    _export(source, bundle)
    rows = json.loads((bundle / PERSPECTIVE_EXECUTION_FILE).read_bytes())
    if damage == "not_list":
        rows = {}
    elif damage == "extra_field":
        rows[0]["unexpected"] = "not part of immutable row"
    elif damage == "identity":
        rows[0]["id"] = "other"
    elif damage == "run_identity":
        rows[0]["run_id"] = "other"
    elif damage == "receipt_json":
        rows[0]["receipt_json"] = "malformed"
    elif damage == "duplicate_receipt":
        rows.append(dict(rows[0]))
    else:
        receipt = json.loads(rows[0]["receipt_json"])
        receipt["run"]["response"] = "changed exact output"
        rows[0]["receipt_json"] = json.dumps(receipt)
    _rewrite_component(bundle, rows)
    with pytest.raises(RestoreError):
        read_bundle(bundle)


@pytest.mark.parametrize("missing", ["source_documents", "source_extractions", "reader_highlights", "perspectives"])
def test_restore_rejects_missing_typed_reference_atomically(tmp_path, missing):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source, saved=True)
    _export(source, bundle)
    paths = {"source_documents": "corpus/documents.json", "source_extractions": "corpus/extractions.json",
             "reader_highlights": "study/highlights.json", "perspectives": "study/perspectives.json"}
    (bundle / paths[missing]).write_text("[]")
    restored = tmp_path / "restored/workspace.db"
    with pytest.raises(RestoreError):
        restore_workspace(restored, bundle)
    conn = _connection(restored)
    try:
        for table in (TABLE, "source_documents", "source_extractions", "reader_highlights", "perspectives"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        conn.close()


def test_receipt_write_failure_rolls_back_all_bundle_rows(tmp_path, monkeypatch):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source, saved=True)
    _export(source, bundle)
    insert = restore_module._insert_rows

    def fail(conn, table, rows, columns):
        if table == TABLE:
            raise sqlite3.OperationalError("deterministic retained-receipt insertion failure")
        return insert(conn, table, rows, columns)

    monkeypatch.setattr(restore_module, "_insert_rows", fail)
    restored = tmp_path / "restored/workspace.db"
    with pytest.raises(RestoreError, match="insertion failure"):
        restore_workspace(restored, bundle)
    conn = _connection(restored)
    try:
        assert conn.execute("SELECT count(*) FROM source_documents").fetchone()[0] == 0
        assert conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_receipt_only_target_is_not_treated_as_empty(tmp_path):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source)
    _export(source, bundle)
    target = tmp_path / "target/workspace.db"
    SQLiteStore(target).close()
    row = _receipt_rows(source)[0]
    conn = _connection(target)
    conn.execute(f"INSERT INTO {TABLE} (id,run_id,receipt_json) VALUES (?,?,?)", tuple(row[key] for key in ("id", "run_id", "receipt_json")))
    conn.commit()
    conn.close()
    assert preview_restore(target, bundle)["target_empty"] is False
    with pytest.raises(RestoreError, match="not empty"):
        restore_workspace(target, bundle)


def test_excluded_source_history_remains_archivable_without_lineage_disclosure(tmp_path):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source)
    store = SQLiteStore(source)
    store.set_document_scope("document", excluded=True)
    store.close()
    _export(source, bundle)
    restored = tmp_path / "restored/workspace.db"
    restore_workspace(restored, bundle)
    assert _receipt_rows(source) == _receipt_rows(restored)
    conn = _connection(restored)
    try:
        result = project_study_lineage(conn)
    finally:
        conn.close()
    assert not any(item["record"]["table"] == TABLE for item in result["items"])
    assert result["coverage"]["omitted"][TABLE] == 1


def test_export_refuses_receipt_with_missing_source_reference(tmp_path):
    source = tmp_path / "source/workspace.db"
    _seed(source)
    conn = _connection(source)
    conn.execute("DROP TRIGGER source_extractions_no_delete")
    conn.execute("DELETE FROM source_extractions")
    conn.commit()
    conn.close()
    with pytest.raises(PerspectiveExecutionExportError):
        _export(source, tmp_path / "bundle")


def test_unknown_restorer_capability_refuses_before_target_mutation(tmp_path, monkeypatch):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source)
    _export(source, bundle)
    monkeypatch.setattr(restore_module, "SUPPORTED_CAPABILITIES", frozenset())
    target = tmp_path / "restored.db"
    with pytest.raises(RestoreError, match="requires capabilities"):
        restore_workspace(target, bundle)
    assert not target.exists()


def test_receipt_component_cannot_escape_bundle_through_symlink(tmp_path):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source)
    _export(source, bundle)
    component = bundle / PERSPECTIVE_EXECUTION_FILE
    outside = tmp_path / "outside.json"
    outside.write_bytes(component.read_bytes())
    component.unlink()
    component.symlink_to(outside)
    with pytest.raises(RestoreError, match="escapes"):
        preview_restore(tmp_path / "restored.db", bundle)
    assert not (tmp_path / "restored.db").exists()


def test_concurrent_retention_cannot_detach_exported_receipt_from_its_saved_frame(tmp_path, monkeypatch):
    source = tmp_path / "source/workspace.db"
    original = _seed(source)
    writer = SQLiteStore(source)
    row, _ = frame_v2_row_from_draft(
        {"label": "Concurrent synthetic frame", "purpose": "Inspect evidence.",
         "questions": ["What differs?"], "challenges": [], "limitations": []},
        declared_by="local-steward", declared_date=TIME,
    )
    resolution = resolution_from_frame_v2_row(row)
    read_receipts = export_module._perspective_executions
    fired = False

    def commit_concurrent_retention(conn):
        nonlocal fired
        if not fired:
            fired = True
            writer.insert_frame_perspective(row)
            captured = original["run"]
            concurrent = capture_execution_run(
                resolution.definition, question=captured["question"],
                scope_receipt=captured["scope_receipt"], execution=captured["execution"],
                response="Concurrent exact output.",
                prompt=build_perspective_prompt(resolution.definition,
                    question=captured["question"], scope_receipt=captured["scope_receipt"]),
                perspective_metadata=resolution.receipt_metadata,
                created_at=TIME, completed_at="2026-09-30T10:01:00+00:00",
                run_id="8dcb3eaf-3304-475e-a759-41a13d8d44e4",
            )
            store_retained_execution(writer._conn, concurrent)
        return read_receipts(conn)

    monkeypatch.setattr(export_module, "_perspective_executions", commit_concurrent_retention)
    try:
        first = tmp_path / "first"
        manifest = _export(source, first)
        assert fired
        assert manifest["counts"][TABLE] == 1
        assert json.loads((first / "study/perspectives.json").read_bytes()) == []
        assert restore_workspace(tmp_path / "first-restore/workspace.db", first)["restored"][TABLE] == 1
        second = tmp_path / "second"
        manifest = _export(source, second)
        assert manifest["counts"][TABLE] == 2
        assert manifest["counts"]["perspectives"] == 1
        assert restore_workspace(tmp_path / "second-restore/workspace.db", second)["restored"][TABLE] == 2
    finally:
        writer.close()


def test_export_preserves_caller_owned_transaction(tmp_path):
    source = tmp_path / "source/workspace.db"
    _seed(source)
    conn = _connection(source)
    try:
        conn.execute("BEGIN")
        files = export_module.build_bundle_files(conn, generated_at=TIME, workspace_id="synthetic")
        assert PERSPECTIVE_EXECUTION_FILE in files
        assert conn.in_transaction
        conn.rollback()
        files = export_module.build_bundle_files(conn, generated_at=TIME, workspace_id="synthetic")
        assert PERSPECTIVE_EXECUTION_FILE in files
        assert not conn.in_transaction
    finally:
        conn.close()


def test_duplicate_json_row_keys_refuse_even_with_matching_manifest_hash(tmp_path):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    _seed(source)
    _export(source, bundle)
    component = bundle / PERSPECTIVE_EXECUTION_FILE
    data = component.read_bytes().replace(b'"id":', b'"id": "shadow", "id":', 1)
    component.write_bytes(data)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    for entry in manifest["files"]:
        if entry["path"] == PERSPECTIVE_EXECUTION_FILE:
            entry["sha256"] = hashlib.sha256(data).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(RestoreError, match="duplicate key"):
        read_bundle(bundle)
