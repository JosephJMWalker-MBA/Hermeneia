"""Exact single-Perspective executions retained by explicit local human action.

Capture is transient and read-only. Only ``store_retained_execution`` installs
study history; no successful model response implicitly acquires that authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any
import uuid

from .perspective_identity import (
    FRAME_V2_SCHEME, SAVED_PERSPECTIVE_ORIGIN, definition_from_frame_v2_row,
    validate_frame_v2_row_identity,
)
from .perspective_runs import (
    PerspectiveDefinition, perspective_definition, transient_perspective_fingerprint,
    transient_perspective_semantics,
)
from .reader_span import decode_reader_span_locator

TABLE = "perspective_execution_receipts"
SCHEMA = "hermeneia.perspective-execution-receipt/v1"
CAPABILITY = "perspective-retained-execution-v1"
PROMPT_VERSION = "perspective-run/v1"
_ID_PREFIX = "perspective-execution-receipt:sha256:"
_RUN_FIELDS = {
    "run_id", "operation", "perspective", "question", "question_sha256",
    "scope_receipt", "scope_sha256", "execution", "response", "response_sha256",
    "prompt", "prompt_sha256", "prompt_version", "status", "created_at", "completed_at",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _json_value(value: Any) -> None:
    if isinstance(value, dict):
        _require(all(isinstance(key, str) for key in value), "JSON keys must be strings")
        for item in value.values():
            _json_value(item)
    elif isinstance(value, list):
        for item in value:
            _json_value(item)
    else:
        _require(value is None or isinstance(value, (str, bool, int, float)), "Unsupported JSON value")


def canonical_bytes(value: Any) -> bytes:
    """The v1 codec: strict JSON, sorted keys, ASCII escaping, compact UTF-8."""
    _json_value(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _copy(value: Any) -> Any:
    return json.loads(canonical_bytes(value))


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_text(value: str) -> str:
    return _digest_bytes(value.encode("utf-8"))


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _keys(value: Any, keys: set[str], name: str) -> None:
    _require(isinstance(value, dict) and set(value) == keys, f"Invalid {name} fields")


def _time(value: Any, name: str) -> datetime:
    _require(isinstance(value, str), f"Invalid {name} timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid {name} timestamp") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, f"Unknown {name} timestamp zone")
    return parsed


def _string_list(value: Any, name: str, *, required: bool = True) -> list[str]:
    _require(isinstance(value, list) and all(_nonblank(item) for item in value), f"Invalid {name}")
    _require(len(set(value)) == len(value), f"Duplicate {name}")
    _require(not required or bool(value), f"Missing {name}")
    return value


def _scope_parts(scope: Any) -> list[dict]:
    _keys(scope, {"receipt_version", "primary", "supporting", "included", "excluded", "materialization"}, "Scope receipt")
    _require(scope["receipt_version"] == "resolved-scope:v1", "Unsupported Scope receipt")
    primary, supporting = scope.get("primary"), scope.get("supporting")
    _require(isinstance(primary, dict) and primary.get("kind") == "reader_selection", "Invalid primary Scope")
    _require(isinstance(supporting, list) and all(isinstance(part, dict) for part in supporting), "Invalid supporting Scope")
    _keys(scope["included"], {"current_page", "highlights", "governing_question"}, "Scope inclusions")
    _keys(scope["excluded"], {"current_page", "highlights", "governing_question", "entire_corpus", "all_notes", "accepted_interpretations", "other_documents"}, "Scope exclusions")
    _require(all(type(flag) is bool for flag in [*scope["included"].values(), *scope["excluded"].values()]), "Invalid Scope inclusion flags")
    _require(scope["included"]["governing_question"] is False
             and all(scope["excluded"][key] is True for key in ("governing_question", "entire_corpus", "all_notes", "accepted_interpretations", "other_documents")), "Unsupported Scope inclusions")
    for key, kind in (("current_page", "current_page"), ("highlights", "reader_highlight")):
        _require(scope["included"][key] == any(part.get("kind") == kind for part in supporting)
                 and scope["excluded"][key] == (not scope["included"][key]), "Scope inclusion flags disagree with evidence")
    _require(_nonblank(primary.get("source_document_hash")), "Missing source document hash")
    for part in [primary, *supporting]:
        _require(_nonblank(part.get("text")) and _nonblank(part.get("source_document_id")), "Missing Scope evidence")
        _require(type(part.get("page")) is int and part["page"] > 0, "Invalid Scope page")
        _require(part["source_document_id"] == primary["source_document_id"], "Cross-document Scope is unsupported")
        if part.get("kind") == "reader_highlight":
            _require(_nonblank(part.get("id")) and part.get("included") is True, "Invalid highlight Scope reference")
            _require(part.get("role") == "supporting" and part.get("evidence_status") == "durable_reader_highlight", "Invalid highlight Scope role")
        else:
            _require(part.get("kind") in {"reader_selection", "current_page"}, "Unsupported Scope evidence kind")
            _require(part.get("role") == ("primary" if part is primary else "supporting"), "Invalid Scope evidence role")
            _require(part is primary or (part.get("kind") == "current_page" and part.get("included") is True and part["page"] == primary["page"]), "Invalid current-page Scope")
            _require(part.get("source_metadata_origin") == "server_resolved_reader_projection", "Scope was not server resolved")
            _require(part.get("source_document_hash") == primary["source_document_hash"], "Inconsistent source document hash")
            _string_list(part.get("extraction_ids"), "Scope extraction references")
            _string_list(part.get("source_locators"), "Scope source locators")
    resolution = primary.get("resolution")
    _keys(resolution, {"reader_span", "block_ranges"}, "Reader selection resolution")
    _require(_nonblank(primary.get("locator")) and decode_reader_span_locator(primary["locator"]) == resolution["reader_span"], "Reader selection locator binding mismatch")
    ranges = resolution["block_ranges"]
    _require(isinstance(ranges, list) and bool(ranges), "Missing Reader selection block ranges")
    range_ids, range_locators = [], []
    for part in ranges:
        _keys(part, {"block_index", "start", "end", "source_locators", "extraction_ids"}, "Reader block range")
        _require(all(type(part[key]) is int for key in ("block_index", "start", "end"))
                 and part["block_index"] >= 0 and part["end"] >= part["start"] >= 0, "Invalid Reader block range")
        range_ids.extend(_string_list(part["extraction_ids"], "Reader range extraction references"))
        range_locators.extend(_string_list(part["source_locators"], "Reader range source locators"))
    _require(list(dict.fromkeys(range_ids)) == primary["extraction_ids"]
             and list(dict.fromkeys(range_locators)) == primary["source_locators"], "Reader range evidence binding mismatch")
    material = scope.get("materialization")
    _keys(material, {"kind", "status", "compiler", "canonical_evidence_modified", "primary", "supporting", "study_packet"}, "Scope materialization")
    _require(isinstance(material, dict) and material.get("kind") == "transient_scope_materialization"
             and material.get("status") == "server_resolved"
             and material.get("compiler") == "hermeneia.scope_resolution.resolve_scope_for_provider"
             and material.get("canonical_evidence_modified") is False, "Invalid Scope materialization")
    captured_primary = material.get("primary")
    _keys(captured_primary, {"kind", "role", "text", "source_document_id", "page", "locator", "source_locators", "extraction_ids"}, "Materialized primary Scope")
    _require(isinstance(captured_primary, dict) and all(primary.get(key) == value for key, value in captured_primary.items()), "Scope materialization disagrees with primary evidence")
    _require(material.get("supporting") == supporting, "Scope materialization disagrees with supporting evidence")
    packet = material["study_packet"]
    if scope["included"]["highlights"]:
        _require(isinstance(packet, dict) and packet.get("packet_type") == "study-synthesis-packet-v1", "Invalid Scope study packet")
        identity, provenance = packet.get("identity"), packet.get("provenance")
        _require(isinstance(identity, dict) and identity.get("scope") == "document"
                 and identity.get("document_id") == primary["source_document_id"], "Scope study packet document mismatch")
        documents = identity.get("documents")
        _require(isinstance(documents, list) and len(documents) == 1 and isinstance(documents[0], dict)
                 and documents[0].get("id") == primary["source_document_id"]
                 and documents[0].get("file_hash") == primary["source_document_hash"], "Scope study packet document hash mismatch")
        _require(isinstance(provenance, dict) and provenance.get("compiler") == "hermeneia.study.compile_synthesis_packet"
                 and provenance.get("version") == "study-synthesis-packet-v1"
                 and provenance.get("provider_free") is True
                 and provenance.get("canonical_evidence_modified") is False, "Invalid Scope study packet provenance")
        records = provenance.get("source_records")
        _keys(records, {"source_document_ids", "reader_highlight_ids", "field_note_ids", "reading_progress_document_ids"}, "Scope study packet references")
        highlight_ids = [part["id"] for part in supporting if part.get("kind") == "reader_highlight"]
        packet_highlight_ids = _string_list(records["reader_highlight_ids"], "Scope study packet highlight references")
        _require(records["source_document_ids"] == [primary["source_document_id"]]
                 and set(packet_highlight_ids) == set(highlight_ids) and records["field_note_ids"] == []
                 and records["reading_progress_document_ids"] in ([], [primary["source_document_id"]]), "Scope study packet references disagree with selected evidence")
    else:
        _require(packet is None, "Unexpected Scope study packet")
    return [primary, *supporting]


def _validate_run(run: Any) -> dict:
    _keys(run, _RUN_FIELDS, "execution run")
    _require(_nonblank(run["run_id"]), "Missing run identity")
    try:
        uuid.UUID(run["run_id"])
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid opaque run identity") from exc
    _require(run["operation"] == "perspective_run" and run["status"] == "succeeded", "Unsupported execution status")
    _require(run["prompt_version"] == PROMPT_VERSION, "Unsupported prompt version")
    _require(_time(run["completed_at"], "completed_at") >= _time(run["created_at"], "created_at"), "Execution timestamps are reversed")
    perspective = run["perspective"]
    _keys(perspective, {"id", "version", "origin", "definition_fingerprint", "definition", "metadata"}, "Perspective")
    _require(_nonblank(perspective["id"]) and isinstance(perspective["version"], str), "Invalid Perspective identity")
    _require(perspective["origin"] in {"built_in", SAVED_PERSPECTIVE_ORIGIN}, "Unsupported Perspective origin")
    semantic = perspective["definition"]
    _keys(semantic, {"label", "purpose", "questions", "challenges", "limitations"}, "Perspective definition")
    _require(_nonblank(semantic["label"]) and _nonblank(semantic["purpose"]), "Missing Perspective semantics")
    for key in ("questions", "challenges", "limitations"):
        _require(isinstance(semantic[key], list) and all(_nonblank(item) for item in semantic[key]), f"Invalid Perspective {key}")
    _require(bool(semantic["questions"]), "Missing Perspective questions")
    _require(perspective["definition_fingerprint"] == _digest_bytes(canonical_bytes(semantic)), "Perspective definition digest mismatch")
    metadata = perspective["metadata"]
    _require(isinstance(metadata, dict), "Invalid Perspective metadata")
    if perspective["origin"] == SAVED_PERSPECTIVE_ORIGIN:
        _require(perspective["version"] == "", "Saved Perspective revision uses its immutable ID, not a display version")
        _require(metadata.get("origin") == SAVED_PERSPECTIVE_ORIGIN
                 and metadata.get("identity_scheme") == FRAME_V2_SCHEME
                 and metadata.get("perspective_id") == perspective["id"]
                 and metadata.get("definition_fingerprint") == perspective["definition_fingerprint"]
                 and metadata.get("definition") == semantic, "Invalid saved Perspective binding")
    else:
        _require(_nonblank(perspective["version"]), "Missing built-in Perspective version")
        _require(metadata in ({}, {"origin": "built_in"}), "Invalid built-in Perspective metadata")
    for field in ("question", "response", "prompt"):
        _require(_nonblank(run[field]), f"Missing execution {field}")
        _require(run[f"{field}_sha256"] == _digest_text(run[field]), f"Execution {field} digest mismatch")
    _require(run["scope_sha256"] == _digest_bytes(canonical_bytes(run["scope_receipt"])), "Execution Scope digest mismatch")
    _scope_parts(run["scope_receipt"])
    _require(isinstance(run["execution"], dict) and _nonblank(run["execution"].get("provider_id"))
             and _nonblank(run["execution"].get("model_id")), "Missing provider/model execution provenance")
    canonical_bytes(run)
    return _copy(run)


def capture_execution_run(
    definition: PerspectiveDefinition, *, question: str, scope_receipt: dict,
    execution: dict, response: str, prompt: str, perspective_metadata: dict | None = None,
    created_at: str, completed_at: str, run_id: str | None = None,
) -> dict:
    """Capture exact effective inputs/output without retaining or writing them."""
    metadata = _copy(perspective_metadata or {})
    origin = metadata.get("origin", "built_in")
    if origin == "built_in":
        _require(perspective_definition(definition.id) == definition, "Unsupported built-in Perspective definition")
    else:
        _require(origin == SAVED_PERSPECTIVE_ORIGIN, "Unsupported transient Perspective retention")
    _require(all(isinstance(value, str) for value in (question, response, prompt)), "Execution text must be exact strings")
    run = {
        "run_id": run_id or str(uuid.uuid4()), "operation": "perspective_run",
        "perspective": {"id": definition.id, "version": definition.version, "origin": origin,
                        "definition_fingerprint": transient_perspective_fingerprint(definition),
                        "definition": transient_perspective_semantics(definition), "metadata": metadata},
        "question": question, "question_sha256": _digest_text(question),
        "scope_receipt": _copy(scope_receipt), "scope_sha256": _digest_bytes(canonical_bytes(scope_receipt)),
        "execution": _copy(execution), "response": response, "response_sha256": _digest_text(response),
        "prompt": prompt, "prompt_sha256": _digest_text(prompt), "prompt_version": PROMPT_VERSION,
        "status": "succeeded", "created_at": created_at, "completed_at": completed_at,
    }
    return _validate_run(run)


def make_retained_receipt(run: dict, *, retained_at: str) -> dict:
    captured = _validate_run(run)
    body = {"schema": SCHEMA, "run": captured, "retention": {
        "decision": "retain", "actor": "local_steward", "actor_identity": "unknown", "retained_at": retained_at,
    }}
    receipt = {**body, "id": _ID_PREFIX + hashlib.sha256(canonical_bytes(body)).hexdigest()}
    return validate_receipt(receipt)


def validate_receipt(receipt: dict) -> dict:
    _keys(receipt, {"schema", "id", "run", "retention"}, "receipt")
    _require(receipt["schema"] == SCHEMA, "Unsupported receipt schema")
    run = _validate_run(receipt["run"])
    retention = receipt["retention"]
    _keys(retention, {"decision", "actor", "actor_identity", "retained_at"}, "retention")
    _require(retention["decision"] == "retain" and retention["actor"] == "local_steward"
             and retention["actor_identity"] == "unknown", "Invalid human retention decision")
    _require(_time(retention["retained_at"], "retained_at") >= _time(run["completed_at"], "completed_at"), "Retention predates execution")
    body = {key: value for key, value in receipt.items() if key != "id"}
    expected = _ID_PREFIX + hashlib.sha256(canonical_bytes(body)).hexdigest()
    _require(receipt["id"] == expected, "Receipt identity digest mismatch")
    return _copy(receipt)


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def receipt_from_row(row: dict | sqlite3.Row) -> dict:
    try:
        receipt = json.loads(row["receipt_json"], object_pairs_hook=_strict_pairs,
                             parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("Nonfinite JSON value")))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed stored Perspective receipt") from exc
    receipt = validate_receipt(receipt)
    try:
        _require(row["id"] == receipt["id"] and row["run_id"] == receipt["run"]["run_id"], "Stored receipt binding mismatch")
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Malformed stored Perspective receipt binding") from exc
    _require(row["receipt_json"].encode("utf-8") == canonical_bytes(receipt), "Stored receipt bytes are not canonical")
    return receipt


def _run_of(value: dict) -> dict:
    return validate_receipt(value)["run"] if "schema" in value else _validate_run(value)


def execution_references(value: dict) -> list[dict]:
    """Exact typed durable references, without inferring mutable current inputs."""
    run = _run_of(value)
    pairs = set()
    for part in _scope_parts(run["scope_receipt"]):
        pairs.add(("source_documents", part["source_document_id"]))
        pairs.update(("source_extractions", identifier) for identifier in part.get("extraction_ids", []))
        if part["kind"] == "reader_highlight":
            pairs.add(("reader_highlights", part["id"]))
    if run["perspective"]["origin"] == SAVED_PERSPECTIVE_ORIGIN:
        pairs.add(("perspectives", run["perspective"]["id"]))
    return [{"table": table, "key": {"id": identifier}} for table, identifier in sorted(pairs)]


def _row(conn: sqlite3.Connection, table: str, identifier: str) -> dict:
    cursor = conn.execute(f'SELECT * FROM "{table}" WHERE id=?', (identifier,))
    row = cursor.fetchone()
    _require(row is not None, f"Missing {table} reference: {identifier}")
    return dict(zip((column[0] for column in cursor.description), row))


def validate_execution_references(conn: sqlite3.Connection, value: dict, *, require_eligible: bool = False) -> None:
    """Validate immutable closure; archival preservation may include excluded rows."""
    run = _run_of(value)
    scope = run["scope_receipt"]
    for part in _scope_parts(scope):
        doc = _row(conn, "source_documents", part["source_document_id"])
        _require(doc.get("file_hash") == scope["primary"]["source_document_hash"], "Source document hash mismatch")
        if require_eligible:
            _require("excluded_from_analysis" in doc and doc["excluded_from_analysis"] in (0, False), "Source document is excluded or exclusion coverage is unknown")
        if part["kind"] == "reader_highlight":
            highlight = _row(conn, "reader_highlights", part["id"])
            _require(highlight.get("source_document_id") == part["source_document_id"], "Reader highlight source association mismatch")
            # Marks and their authored questions are mutable. The captured text
            # belongs to the execution; later edits/dismissal do not rewrite it.
        else:
            locators = set(part["source_locators"])
            for identifier in part["extraction_ids"]:
                extraction = _row(conn, "source_extractions", identifier)
                _require(extraction.get("document_id") == part["source_document_id"]
                         and extraction.get("page") == part["page"]
                         and extraction.get("source_locator") in locators, "Source extraction association mismatch")
    perspective = run["perspective"]
    if perspective["origin"] == SAVED_PERSPECTIVE_ORIGIN:
        row = _row(conn, "perspectives", perspective["id"])
        incoming = conn.execute("SELECT old_id FROM supersession_relations WHERE new_id=? AND old_id IN (SELECT id FROM perspectives)", (perspective["id"],)).fetchall()
        _require(len(incoming) <= 1, "Ambiguous saved Perspective revision")
        validate_frame_v2_row_identity(row, predecessor_perspective_id=incoming[0][0] if incoming else None)
        _require(transient_perspective_semantics(definition_from_frame_v2_row(row)) == perspective["definition"]
                 and row.get("declared_by") == perspective["metadata"].get("declared_by")
                 and row.get("declared_date") == perspective["metadata"].get("declared_date"), "Saved Perspective snapshot binding mismatch")


def ensure_perspective_execution_tables(conn: sqlite3.Connection) -> None:
    """Additive schema only; callers own transaction/commit and migration policy."""
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, receipt_json TEXT NOT NULL)")
    for operation in ("UPDATE", "DELETE"):
        conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_{operation.lower()} BEFORE {operation} ON {TABLE} BEGIN SELECT RAISE(ABORT, 'Perspective execution receipt immutable'); END")
    # REPLACE deletes may bypass delete triggers with recursive_triggers off.
    conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_replace BEFORE INSERT ON {TABLE} WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE id=NEW.id OR run_id=NEW.run_id) BEGIN SELECT RAISE(ABORT, 'Perspective execution receipt already exists'); END")


def store_retained_execution(conn: sqlite3.Connection, run: dict, *, retained_at: str | None = None, require_eligible: bool = False) -> dict:
    """Atomic retention; exact run retries return the original immutable decision."""
    captured = _validate_run(run)
    own_transaction = not conn.in_transaction
    savepoint = "perspective_retention_" + uuid.uuid4().hex
    conn.execute("BEGIN IMMEDIATE" if own_transaction else f"SAVEPOINT {savepoint}")
    try:
        validate_execution_references(conn, captured, require_eligible=require_eligible)
        cursor = conn.execute(f"SELECT id,run_id,receipt_json FROM {TABLE} WHERE run_id=?", (captured["run_id"],))
        existing = cursor.fetchone()
        if existing is not None:
            row = dict(zip((column[0] for column in cursor.description), existing))
            receipt = receipt_from_row(row)
            _require(receipt["run"] == captured, "Run identity conflicts with different immutable execution")
        else:
            receipt = make_retained_receipt(captured, retained_at=retained_at or datetime.now(timezone.utc).isoformat())
            conn.execute(f"INSERT INTO {TABLE}(id,run_id,receipt_json) VALUES(?,?,?)", (receipt["id"], captured["run_id"], canonical_bytes(receipt).decode("utf-8")))
            _require(load_retained_execution(conn, receipt["id"]) == receipt, "Installed receipt binding mismatch")
        if own_transaction:
            conn.commit()
        else:
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return receipt
    except Exception:
        if own_transaction:
            conn.rollback()
        else:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def load_retained_execution(conn: sqlite3.Connection, receipt_id: str) -> dict | None:
    """Read existing storage only; missing historical schema is unsupported."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone() is None:
        return None
    cursor = conn.execute(f"SELECT id,run_id,receipt_json FROM {TABLE} WHERE id=?", (receipt_id,))
    row = cursor.fetchone()
    return receipt_from_row(dict(zip((column[0] for column in cursor.description), row))) if row is not None else None
