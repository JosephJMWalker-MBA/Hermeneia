"""Exact award portability, strict archival closure, and bounded coverage."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import sqlite3

import pytest

from hermeneia.perspective_execution_receipts import canonical_bytes
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study_lineage import project_study_lineage
from hermeneia.workspace import (
    RestoreError, export_workspace_bundle, preview_restore, read_bundle, restore_workspace,
)
from hermeneia.workspace import export as export_module
from hermeneia.workspace import restore as restore_module
from test_perspective_achievements import Study

TIME = "2026-09-30T12:00:00+00:00"
TABLE = "achievement_awards"
FILE = "study/achievement_awards.json"
CAPABILITY = "perspective-achievement-awards-v1"
P3_TABLE = "perspective_execution_receipts"
P3_FILE = "study/perspective_executions.json"
ROW_KEYS = ("id", "achievement_id", "rule_id", "rule_version", "receipt_json")


@pytest.fixture
def study(tmp_path):
    value = Study(tmp_path / "source/workspace.db")
    try:
        yield value
    finally:
        value.conn.close()


def _export(path, bundle):
    return export_workspace_bundle(path, bundle, generated_at=TIME, workspace_id="synthetic")


def _connection(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _award_rows(path):
    conn = _connection(path)
    try:
        return [dict(row) for row in conn.execute(f"SELECT * FROM {TABLE} ORDER BY id")]
    finally:
        conn.close()


def _issue(study, achievement="second_opinion"):
    from hermeneia.achievement_awards import (
        evidence_package_digest, materialize_perspective_achievement_award,
        prepare_perspective_achievement_award,
    )

    package = prepare_perspective_achievement_award(study.conn, achievement)
    outcome = materialize_perspective_achievement_award(
        study.conn, achievement, "achievement." + achievement, "1.0.0",
        evidence_package_digest(package),
    )
    return outcome["receipt"]


def _rewrite_component(bundle, rows, *, file=FILE, table=TABLE):
    data = (json.dumps(rows, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    _rewrite_component_bytes(bundle, data, len(rows) if isinstance(rows, list) else 0,
                             file=file, table=table)


def _rewrite_component_bytes(bundle, data, count, *, file=FILE, table=TABLE):
    (bundle / file).write_bytes(data)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    for entry in manifest["files"]:
        if entry["path"] == file:
            entry["sha256"] = hashlib.sha256(data).hexdigest()
    manifest["counts"][table] = count
    manifest_path.write_text(json.dumps(manifest))


def _rebind(receipt):
    """Rebind a synthetic understood wire receipt, without claiming issuance."""
    package = receipt["evidence_package"]
    digest = "sha256:" + hashlib.sha256(
        b"hermeneia.perspective-achievement-evidence-package/v1\0" + canonical_bytes(package)
    ).hexdigest()
    receipt["evidence_package_sha256"] = digest
    receipt["issuance"]["approved_evidence_package_sha256"] = digest
    body = {key: value for key, value in receipt.items() if key != "award_id"}
    receipt["award_id"] = "achievement-award:sha256:" + hashlib.sha256(
        b"hermeneia.perspective-achievement-award/v1\0" + canonical_bytes(body)
    ).hexdigest()
    return receipt


def _row(receipt):
    return {"id": receipt["award_id"],
            **{key: receipt[key] for key in ("achievement_id", "rule_id", "rule_version")},
            "receipt_json": canonical_bytes(receipt).decode()}


def _assert_empty(path):
    conn = _connection(path)
    try:
        for table in (TABLE, P3_TABLE, "source_documents", "source_extractions", "perspectives"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    finally:
        conn.close()


def test_supported_empty_award_category_is_covered_without_historical_absence_claim(tmp_path):
    source = tmp_path / "source/workspace.db"
    SQLiteStore(source).close()
    bundle = tmp_path / "bundle"
    manifest = _export(source, bundle)
    assert CAPABILITY in manifest["required_capabilities"]
    assert manifest["counts"][TABLE] == 0
    assert manifest["wbs_version"] == "1.1"
    entry = next(entry for entry in manifest["files"] if entry["path"] == FILE)
    assert entry["role"] == "canonical"
    assert json.loads((bundle / FILE).read_bytes()) == []
    preview = preview_restore(tmp_path / "restored.db", bundle)
    assert preview["coverage"][TABLE]["status"] == "covered"
    assert preview["coverage"][TABLE]["extant_records"] == 0
    assert preview["would_create"][TABLE] == 0


def test_legacy_bundle_award_history_is_unsupported_after_schema_initialization(tmp_path):
    source = tmp_path / "source/workspace.db"
    SQLiteStore(source).close()
    conn = sqlite3.connect(source)
    conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
    conn.close()
    bundle = tmp_path / "bundle"
    manifest = _export(source, bundle)
    assert CAPABILITY not in manifest.get("required_capabilities", [])
    assert not (bundle / FILE).exists()
    preview = preview_restore(tmp_path / "restored.db", bundle)
    assert preview["coverage"][TABLE]["status"] == "unsupported"
    assert TABLE not in preview["would_create"]
    result = restore_workspace(tmp_path / "restored.db", bundle)
    assert result["coverage"][TABLE]["status"] == "unsupported"
    assert TABLE not in result["restored"]


def test_legacy_award_table_missing_required_columns_has_unsupported_coverage(tmp_path):
    source = tmp_path / "source/workspace.db"
    SQLiteStore(source).close()
    conn = _connection(source)
    conn.execute(f"DROP TABLE {TABLE}")
    conn.execute(f"CREATE TABLE {TABLE}(id TEXT, receipt_json TEXT)")
    conn.commit()
    conn.close()
    bundle = tmp_path / "bundle"
    manifest = _export(source, bundle)
    assert CAPABILITY not in manifest.get("required_capabilities", [])
    assert read_bundle(bundle)["coverage"][TABLE]["status"] == "unsupported"
    assert TABLE not in preview_restore(tmp_path / "target.db", bundle)["would_create"]


@pytest.mark.parametrize("damage", [
    "no_capability", "missing_file", "unlisted_file", "duplicate_manifest", "wrong_role",
    "hash", "count", "boolean_count", "missing_count",
])
def test_incomplete_or_ambiguous_award_component_refuses_before_target_write(tmp_path, damage):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    SQLiteStore(source).close()
    _export(source, bundle)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    entry = next(entry for entry in manifest["files"] if entry["path"] == FILE)
    if damage == "no_capability":
        manifest["required_capabilities"].remove(CAPABILITY)
    elif damage == "missing_file":
        (bundle / FILE).unlink()
    elif damage == "unlisted_file":
        manifest["files"].remove(entry)
    elif damage == "duplicate_manifest":
        manifest["files"].append(dict(entry))
    elif damage == "wrong_role":
        entry["role"] = "derived"
    elif damage == "hash":
        entry["sha256"] = "0" * 64
    elif damage == "missing_count":
        del manifest["counts"][TABLE]
    else:
        manifest["counts"][TABLE] = False if damage == "boolean_count" else 1
    manifest_path.write_text(json.dumps(manifest))
    target = tmp_path / "restored.db"
    with pytest.raises(RestoreError):
        restore_workspace(target, bundle)
    assert not target.exists()


def test_duplicate_manifest_json_keys_are_refused(tmp_path):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    SQLiteStore(source).close()
    _export(source, bundle)
    path = bundle / "manifest.json"
    manifest = path.read_text()
    path.write_text('{"counts":{},' + manifest[1:])
    with pytest.raises(RestoreError, match="duplicate JSON key"):
        read_bundle(bundle)


def test_duplicate_component_json_keys_are_refused(tmp_path):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    SQLiteStore(source).close()
    _export(source, bundle)
    _rewrite_component_bytes(bundle, b'[{"id":"one","id":"two"}]', 1)
    with pytest.raises(RestoreError, match="duplicate JSON key"):
        read_bundle(bundle)


def test_award_component_symlink_cannot_escape_bundle(tmp_path):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    SQLiteStore(source).close()
    _export(source, bundle)
    path = bundle / FILE
    outside = tmp_path / "outside.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(RestoreError, match="escapes"):
        read_bundle(bundle)


def test_unknown_required_award_capability_is_refused_before_target_write(tmp_path, monkeypatch):
    source, bundle = tmp_path / "source/workspace.db", tmp_path / "bundle"
    SQLiteStore(source).close()
    _export(source, bundle)
    monkeypatch.setattr(restore_module, "SUPPORTED_CAPABILITIES",
                        restore_module.SUPPORTED_CAPABILITIES - {CAPABILITY})
    target = tmp_path / "restored.db"
    with pytest.raises(RestoreError, match="requires capabilities"):
        restore_workspace(target, bundle)
    assert not target.exists()


@pytest.mark.parametrize("damage", [
    "not_list", "extra_field", "identity", "achievement", "rule", "version", "noncanonical",
    "receipt_json", "duplicate_award", "body", "schema", "profile",
])
def test_malformed_award_refuses_even_with_updated_bundle_hash(study, tmp_path, damage):
    study.retained()
    _issue(study, "perspective_explorer")
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    rows = json.loads((bundle / FILE).read_bytes())
    if damage == "not_list":
        rows = {}
    elif damage == "extra_field":
        rows[0]["unexpected"] = "must not be silently filtered"
    elif damage == "identity":
        rows[0]["id"] = "other"
    elif damage in {"achievement", "rule", "version"}:
        rows[0][{"achievement": "achievement_id", "rule": "rule_id", "version": "rule_version"}[damage]] = "other"
    elif damage == "receipt_json":
        rows[0]["receipt_json"] = "malformed"
    elif damage == "noncanonical":
        rows[0]["receipt_json"] += "\n"
    elif damage == "duplicate_award":
        rows.append(dict(rows[0]))
    else:
        receipt = json.loads(rows[0]["receipt_json"])
        if damage == "body":
            receipt["awarded_at"] = "2026-10-01T12:00:00+00:00"
        elif damage == "schema":
            receipt["schema"] = "hermeneia.perspective-achievement-award/v99"
        else:
            receipt["evidence_package"]["profile"] = "perspective-achievement-evidence-package/v99"
        rows[0]["receipt_json"] = canonical_bytes(receipt).decode()
    _rewrite_component(bundle, rows)
    with pytest.raises(RestoreError):
        read_bundle(bundle)


def test_conflicting_self_bound_same_slot_receipts_are_refused(study, tmp_path):
    study.retained()
    receipt = _issue(study, "perspective_explorer")
    other = deepcopy(receipt)
    other["awarded_at"] = "2026-10-01T12:00:00+00:00"
    _rebind(other)
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    _rewrite_component(bundle, sorted([_row(receipt), _row(other)], key=lambda row: row["id"]))
    with pytest.raises(RestoreError, match="slot"):
        read_bundle(bundle)


@pytest.mark.parametrize("missing", ["selected", "other_candidate"])
def test_restore_refuses_missing_award_assessment_receipt_atomically(study, tmp_path, missing):
    first, second = study.retained(), study.retained("skeptical-reader", kept="2026-09-30T10:02:00+00:00")
    extra = study.retained("contextual-reader", question="Another exact question.")
    receipt = _issue(study)
    assert receipt["evidence_package"]["assessment"]["finding"]["qualifying_receipt_ids"] == [first["id"], second["id"]]
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    rows = json.loads((bundle / P3_FILE).read_bytes())
    identifier = first["id"] if missing == "selected" else extra["id"]
    _rewrite_component(bundle, [row for row in rows if row["id"] != identifier],
                       file=P3_FILE, table=P3_TABLE)
    target = tmp_path / "target/workspace.db"
    with pytest.raises(RestoreError, match="award references"):
        restore_workspace(target, bundle)
    _assert_empty(target)


def test_export_refuses_missing_award_assessment_candidate_and_preserves_local_history(study, tmp_path):
    study.retained()
    extra = study.retained("skeptical-reader", question="Another exact question.")
    _issue(study, "perspective_explorer")
    study.conn.execute(f"DROP TRIGGER {P3_TABLE}_no_delete")
    study.conn.execute(f"DELETE FROM {P3_TABLE} WHERE id=?", (extra["id"],))
    study.conn.commit()
    before = tuple(study.conn.iterdump())
    with pytest.raises(export_module.AchievementAwardExportError):
        _export(study.path, tmp_path / "bundle")
    assert tuple(study.conn.iterdump()) == before
    assert len(_award_rows(study.path)) == 1


def test_award_restore_insertion_failure_rolls_back_all_dependency_history(study, tmp_path, monkeypatch):
    study.retained()
    _issue(study, "perspective_explorer")
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    insert = restore_module._insert_rows

    def fail(conn, table, rows, columns):
        if table == TABLE:
            raise sqlite3.OperationalError("synthetic award insertion failure")
        return insert(conn, table, rows, columns)

    monkeypatch.setattr(restore_module, "_insert_rows", fail)
    target = tmp_path / "target/workspace.db"
    with pytest.raises(RestoreError, match="award insertion failure"):
        restore_workspace(target, bundle)
    _assert_empty(target)


@pytest.mark.parametrize("overwrite", [False, True])
def test_award_only_target_is_occupied_and_restore_never_merges(study, tmp_path, overwrite):
    study.retained()
    receipt = _issue(study, "perspective_explorer")
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    target = tmp_path / "target/workspace.db"
    SQLiteStore(target).close()
    conn = _connection(target)
    row = _row(receipt)
    conn.execute(f"INSERT INTO {TABLE}({','.join(ROW_KEYS)}) VALUES (?,?,?,?,?)",
                 tuple(row[key] for key in ROW_KEYS))
    conn.commit()
    before = tuple(conn.iterdump())
    conn.close()
    assert preview_restore(target, bundle)["target_empty"] is False
    with pytest.raises(RestoreError, match="not empty"):
        restore_workspace(target, bundle, overwrite=overwrite)
    conn = _connection(target)
    try:
        assert tuple(conn.iterdump()) == before
    finally:
        conn.close()


def test_award_component_cannot_use_overwrite_to_enter_occupied_nonaward_workspace(study, tmp_path):
    study.retained()
    _issue(study, "perspective_explorer")
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    target_study = Study(tmp_path / "target/workspace.db")
    try:
        before = tuple(target_study.conn.iterdump())
        with pytest.raises(RestoreError, match="not empty"):
            restore_workspace(target_study.path, bundle, overwrite=True)
        assert tuple(target_study.conn.iterdump()) == before
    finally:
        target_study.conn.close()


def test_award_export_snapshot_cannot_include_a_concurrently_issued_award(study, tmp_path, monkeypatch):
    study.retained()
    first = _issue(study, "perspective_explorer")
    study.retained("skeptical-reader")
    writer = _connection(study.path)
    read_awards = export_module._achievement_awards
    fired = False

    def issue_concurrently(conn):
        nonlocal fired
        if not fired:
            fired = True
            original = study.conn
            try:
                study.conn = writer
                _issue(study)
            finally:
                study.conn = original
        return read_awards(conn)

    monkeypatch.setattr(export_module, "_achievement_awards", issue_concurrently)
    try:
        initial = tmp_path / "initial"
        manifest = _export(study.path, initial)
        assert fired
        assert manifest["counts"][TABLE] == 1
        assert json.loads((initial / FILE).read_bytes())[0]["id"] == first["award_id"]
        assert restore_workspace(tmp_path / "initial-target/workspace.db", initial)["restored"][TABLE] == 1
        assert _export(study.path, tmp_path / "next")["counts"][TABLE] == 2
    finally:
        writer.close()


@pytest.mark.parametrize("saved", [False, True])
def test_second_opinion_issue_export_restore_exact_bytes_verify_and_lineage(study, tmp_path, saved):
    from hermeneia.achievement_award_verification import verify_achievement_award

    left = study.saved("Inspect evidence") if saved else "close-reader"
    right = study.saved("Challenge evidence", purpose="Challenge exact evidence.") if saved else "skeptical-reader"
    first = study.retained(left, execution={"provider_id": "synthetic", "model_id": "fixture-v1", "temperature": 0.7})
    second = study.retained(right, kept="2026-09-30T10:02:00+00:00")
    receipt = _issue(study)
    _issue(study, "perspective_explorer")
    finding = receipt["evidence_package"]["assessment"]["finding"]
    assert finding["qualifying_receipt_ids"] == [first["id"], second["id"]]
    assert receipt["earned_at"] == "2026-09-30T10:02:00+00:00"
    assert [item["receipt_id"] for item in receipt["evidence_package"]["witness_bindings"]] == [first["id"], second["id"]]
    assert [item["run_id"] for item in receipt["evidence_package"]["witness_bindings"]] == [first["run"]["run_id"], second["run"]["run_id"]]
    before = tuple(study.conn.iterdump())
    bundle, repeated = tmp_path / "bundle", tmp_path / "repeated"
    manifest = _export(study.path, bundle)
    _export(study.path, repeated)
    assert tuple(study.conn.iterdump()) == before
    assert manifest["counts"][TABLE] == 2
    assert CAPABILITY in manifest["required_capabilities"]
    exported = json.loads((bundle / FILE).read_bytes())
    assert exported == _award_rows(study.path)
    assert [row["id"] for row in exported] == sorted(row["id"] for row in exported)
    assert (bundle / FILE).read_bytes() == (repeated / FILE).read_bytes()
    assert (bundle / "manifest.json").read_bytes() == (repeated / "manifest.json").read_bytes()
    target = tmp_path / "target/workspace.db"
    result = restore_workspace(target, bundle)
    assert result["restored"][TABLE] == 2
    assert result["coverage"][TABLE]["status"] == "covered"
    assert _award_rows(target) == _award_rows(study.path)
    restored = next(row for row in _award_rows(target) if row["id"] == receipt["award_id"])
    assert restored["receipt_json"].encode() == canonical_bytes(receipt)
    restored_receipt = json.loads(restored["receipt_json"])
    assert restored_receipt["award_id"] == receipt["award_id"]
    assert restored_receipt["earned_at"] == receipt["earned_at"]
    assert restored_receipt["awarded_at"] == receipt["awarded_at"]
    views = []
    for path in (study.path, target):
        conn = _connection(path)
        try:
            before_read = tuple(conn.iterdump())
            conn.execute("PRAGMA query_only=ON")
            report = verify_achievement_award(conn, receipt["award_id"])
            assert report["receipt_integrity"] == "valid"
            assert report["evidence_verification"] == "verified"
            assert report["historical_snapshot_replay"] == "verified"
            views.append([item for item in project_study_lineage(conn)["items"]
                          if item["record"]["table"] == TABLE])
            assert tuple(conn.iterdump()) == before_read
        finally:
            conn.close()
    assert views[0] == views[1]
    summary = next(item for item in views[1] if item["record"]["key"]["id"] == receipt["award_id"])
    assert summary["record_type"] == "perspective_achievement_award"
    assert summary["authorship"] == "derived"
    assert summary["timestamp"]["value"] == receipt["awarded_at"]
    reexported = tmp_path / "reexported"
    _export(target, reexported)
    assert (reexported / FILE).read_bytes() == (bundle / FILE).read_bytes()


def test_unknown_future_rule_preserves_understood_closed_historical_bytes(study, tmp_path):
    from hermeneia.achievement_award_verification import verify_achievement_award
    from hermeneia.achievement_awards import validate_award_receipt

    study.retained()
    future = deepcopy(_issue(study, "perspective_explorer"))
    future["rule_version"] = "9.0.0"
    assessment = future["evidence_package"]["assessment"]
    assessment["evaluator_version"] = "9.0.0"
    finding = assessment["finding"]
    finding["rule_version"] = "9.0.0"
    finding["rule_reference"] = finding["rule_id"] + ".v9.0.0"
    definitions = future["evidence_package"]["rule_definitions"]
    definition = next(item for item in definitions if item["rule_id"] == finding["rule_id"])
    definition["rule_version"] = "9.0.0"
    definition["synthetic_future_semantics"] = "Preserved payload; not an executable current rule."
    finding["rule_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(definition)).hexdigest()
    assessment["rules_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(definitions)).hexdigest()
    _rebind(future)
    validate_award_receipt(future)
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    _rewrite_component(bundle, [_row(future)])
    target = tmp_path / "target/workspace.db"
    restore_workspace(target, bundle)
    assert _award_rows(target) == [_row(future)]
    conn = _connection(target)
    try:
        report = verify_achievement_award(conn, future["award_id"])
        assert report["receipt_integrity"] == "valid"
        assert report["evidence_verification"] == "unverifiable_unsupported_rule"
    finally:
        conn.close()


def test_excluded_original_evidence_remains_archivable_and_safe_summary_survives(study, tmp_path):
    study.retained()
    receipt = _issue(study, "perspective_explorer")
    store = SQLiteStore(study.path)
    store.set_document_scope(study.seed["doc_id"], excluded=True)
    store.close()
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    target = tmp_path / "target/workspace.db"
    restore_workspace(target, bundle)
    assert _award_rows(study.path) == _award_rows(target)
    conn = _connection(target)
    try:
        items = project_study_lineage(conn)["items"]
    finally:
        conn.close()
    assert not any(item["record"]["table"] == P3_TABLE for item in items)
    summary = next(item for item in items if item["record"]["key"]["id"] == receipt["award_id"])
    serialized = json.dumps(summary)
    assert "Exact synthetic proposal" not in serialized
    assert "What does this exact evidence support" not in serialized
    assert "synthetic_future_semantics" not in serialized
    assert "temperature" not in serialized
    assert "purpose" not in serialized


def test_mutable_highlight_snapshot_drift_does_not_rewrite_receipt_or_refuse_archival_restore(study, tmp_path):
    from hermeneia.achievement_award_verification import verify_achievement_award
    from hermeneia.scope_resolution import resolve_scope_for_provider
    from test_scope_resolution import _selection_scope

    study.conn.execute(
        "INSERT INTO reader_highlights(id,source_document_id,page,source_locator,selected_text,created_at,updated_at) "
        "VALUES('mark',?,2,'page:2:block:1','Alpha beta begins.',?,?)",
        (study.seed["doc_id"], TIME, TIME),
    )
    study.conn.commit()
    selection = _selection_scope(study.seed, text="")
    selection["supporting"] = {"highlights": {"include": True, "ids": ["mark"]}}
    scope = resolve_scope_for_provider(study.conn, selection)
    study.retained(scope=scope)
    receipt = _issue(study, "perspective_explorer")
    study.conn.execute("UPDATE reader_highlights SET selected_text='Later authored mark' WHERE id='mark'")
    study.conn.commit()
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    target = tmp_path / "target/workspace.db"
    restore_workspace(target, bundle)
    assert _award_rows(study.path) == _award_rows(target)
    conn = _connection(target)
    try:
        report = verify_achievement_award(conn, receipt["award_id"])
        assert report["receipt_integrity"] == "valid"
        assert report["evidence_verification"] == "unverifiable_missing_coverage"
    finally:
        conn.close()


def test_explorer_unsupported_family_diagnostic_is_not_a_new_archival_parent_requirement(study, tmp_path):
    root = study.saved("Synthetic legacy ancestor")
    child = study.saved("Executed frame", purpose="Challenge evidence.", predecessor=root)
    study.retained(child)
    study.conn.execute("DROP TRIGGER perspectives_no_update")
    study.conn.execute("UPDATE perspectives SET identity_scheme='perspective-label-v1' WHERE id=?",
                       (root["id"],))
    study.conn.commit()
    receipt = _issue(study, "perspective_explorer")
    executions = receipt["evidence_package"]["adapter_basis"]["executions"]
    assert executions[0]["family_state"] == "unsupported"
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    target = tmp_path / "target/workspace.db"
    restore_workspace(target, bundle)
    assert _award_rows(target) == _award_rows(study.path)


def test_export_refuses_malformed_extant_award_without_silently_omitting_it(study, tmp_path):
    study.retained()
    _issue(study, "perspective_explorer")
    study.conn.execute(f"DROP TRIGGER {TABLE}_no_update")
    study.conn.execute(f"UPDATE {TABLE} SET receipt_json='malformed'")
    study.conn.commit()
    before = tuple(study.conn.iterdump())
    with pytest.raises(export_module.AchievementAwardExportError):
        _export(study.path, tmp_path / "bundle")
    assert tuple(study.conn.iterdump()) == before


def test_award_wire_id_order_is_not_inherited_from_receipt_insertion_order(study, tmp_path):
    study.retained()
    study.retained("skeptical-reader")
    _issue(study, "second_opinion")
    _issue(study, "perspective_explorer")
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    rows = json.loads((bundle / FILE).read_bytes())
    assert len(rows) == 2
    assert [row["id"] for row in rows] == sorted(row["id"] for row in rows)
    _rewrite_component(bundle, list(reversed(rows)))
    with pytest.raises(RestoreError, match="ASCII identity order"):
        read_bundle(bundle)


@pytest.mark.parametrize("mutation", [
    "question_digest", "scope_digest", "revision", "fingerprint", "methodology",
    "lineage_question_digest", "retained_at", "omitted_dependencies", "family_coverage",
    "lineage_extra_field",
])
def test_resigned_contradictory_parent_bindings_refuse_restore(study, tmp_path, mutation):
    study.retained()
    study.retained("skeptical-reader", kept="2026-09-30T10:02:00+00:00")
    altered = deepcopy(_issue(study))
    package = altered["evidence_package"]
    finding = package["assessment"]["finding"]
    if mutation == "question_digest":
        finding["question_comparison_basis"]["sha256"] = "sha256:" + "0" * 64
    elif mutation == "scope_digest":
        finding["scope_comparison_basis"]["sha256"] = "sha256:" + "0" * 64
    elif mutation in {"revision", "fingerprint", "methodology"}:
        key = {"revision": "revision_ids", "fingerprint": "definition_fingerprints",
               "methodology": "methodology_sha256"}[mutation]
        finding["perspective_distinctness_basis"][key][0] = "substitute-revision" if mutation == "revision" else "sha256:" + "0" * 64
    elif mutation == "family_coverage":
        coverage = deepcopy(package["assessment"]["coverage"])
        coverage["family_states"] = {"supported": 1, "unsupported": 1, "invalid": 0}
        package["assessment"]["coverage"] = deepcopy(coverage)
        finding["coverage"] = deepcopy(coverage)
        package["adapter_basis"]["coverage"] = deepcopy(coverage)
        package["assessment"]["evidence_sha256"] = "sha256:" + hashlib.sha256(
            canonical_bytes(package["adapter_basis"])).hexdigest()
    else:
        index = 1 if mutation == "retained_at" else 0
        identifier = finding["qualifying_receipt_ids"][index]
        execution = next(item for item in package["adapter_basis"]["executions"]
                         if item["lineage_ref"]["record"]["key"]["id"] == identifier)
        if mutation == "lineage_question_digest":
            execution["lineage_ref"]["provenance"]["question_sha256"] = "sha256:" + "0" * 64
        elif mutation == "lineage_extra_field":
            execution["lineage_ref"]["provenance"]["response"] = "Unexpected duplicated model output."
        elif mutation == "retained_at":
            changed = "2026-09-30T10:03:00+00:00"
            stamp = execution["lineage_ref"]["timestamp"]
            stamp["value"], stamp["sort_key"] = changed, "2026-09-30T10:03:00.000000+00:00"
            execution["lineage_ref"]["provenance"]["retention"]["retained_at"] = changed
            selected = finding["selection_basis"]["selected"][index]
            selected["retained_at"] = selected["retained_at_utc"] = changed
            altered["earned_at"] = changed
        else:
            execution["dependency_evidence"] = []
            finding["validated_evidence"][index]["dependency_evidence"] = []
        finding["evidence_refs"][index] = deepcopy(execution["lineage_ref"])
        package["assessment"]["evidence_sha256"] = "sha256:" + hashlib.sha256(
            canonical_bytes(package["adapter_basis"])).hexdigest()
    _rebind(altered)
    bundle = tmp_path / "bundle"
    _export(study.path, bundle)
    _rewrite_component(bundle, [_row(altered)])
    target = tmp_path / "target/workspace.db"
    with pytest.raises(RestoreError):
        restore_workspace(target, bundle)
    if target.exists():
        _assert_empty(target)
