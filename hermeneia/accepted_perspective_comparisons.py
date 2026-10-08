"""Accepted Perspective comparisons (#215 P7 Layer 2): an append-only record of a steward's acceptance.

A record means only: "the steward accepted this comparison structure". It
does not establish that any claim is true, that the steward agrees with any
Perspective, or that any disagreement is resolved. It binds the exact
participant receipts, the Layer 1 digest, the governing-question snapshot,
the preserved model candidate (prompt, execution, raw output, normalized
structure) and the accepted structure. Reads never initialize storage; the
model is never called again. Contract: docs/design/perspective-comparison-layer2-v1.md.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

from .perspective_comparison import ComparisonRefused, compare_retained_perspectives
from .perspective_comparison_candidates import (
    CANDIDATE_SCHEMA, EXTRACTION_POLICY_VERSION, PROMPT_VERSION, STRUCTURE_SCHEMA, ExtractionRefused,
    StructureRefused, build_prompt, candidate_id, layer1_digest, normalize, parse_output, text_digest,
    unit_texts, validate_structure, view_from_receipts,
)
from .perspective_execution_receipts import TABLE as RECEIPT_TABLE, canonical_bytes, receipt_from_row

TABLE = "accepted_perspective_comparisons"
SCHEMA = "hermeneia.accepted-perspective-comparison/v1"
CAPABILITY = "accepted-perspective-comparison-v1"
COLUMNS = frozenset({"id", "candidate_id", "comparison_json"})
MEANING = ("The steward accepted this comparison structure. It does not establish that any claim is true, that the "
           "steward agrees with any Perspective, or that any disagreement is resolved.")
_DOMAIN = b"hermeneia.accepted-perspective-comparison/v1\0"
_ID_PREFIX = "accepted-perspective-comparison:sha256:"
_FIELDS = {"schema", "id", "origin", "binding", "candidate", "structure", "acceptance"}
_ACCEPTANCE_FIELDS = {"decision", "actor", "actor_identity", "accepted_at", "reviewed_candidate_id", "structure_sha256", "meaning"}
# One origin field, three kinds, one schema (docs/design/perspective-comparison-p7-disposition.md §3).
MODEL_ORIGINS = {"accept": "model_proposed_steward_accepted", "edit_and_accept": "model_proposed_steward_edited"}
STEWARD_AUTHORED = "steward_authored"


class InvalidAcceptedComparison(ValueError):
    """A stored or proposed record violates the accepted-comparison contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidAcceptedComparison(message)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def record_id(record: dict) -> str:
    body = {key: value for key, value in record.items() if key != "id"}
    return _ID_PREFIX + hashlib.sha256(_DOMAIN + canonical_bytes(body)).hexdigest()


def _finish(record: dict) -> dict:
    record["id"] = record_id(record)
    return validate_record(json.loads(canonical_bytes(record)))


def make_accepted_record(candidate: dict, *, decision: str, structure: dict, accepted_at: str) -> dict:
    """The record of a steward decision on one exact model candidate (accept or edit_and_accept)."""
    return _finish({
        "schema": SCHEMA, "origin": {"kind": MODEL_ORIGINS[decision]}, "binding": candidate["binding"],
        "candidate": {"candidate_id": candidate["candidate_id"], "extraction": candidate["extraction"],
                      "structure": candidate["structure"]},
        "structure": structure,
        "acceptance": {"decision": decision, "actor": "local_steward", "actor_identity": "unknown",
                       "accepted_at": accepted_at, "reviewed_candidate_id": candidate["candidate_id"],
                       "structure_sha256": _digest(canonical_bytes(structure)), "meaning": MEANING},
    })


def make_steward_authored_record(binding: dict, structure: dict, *, accepted_at: str) -> dict:
    """Option (b): the same canonical type, authored directly by a steward (no route in P7)."""
    return _finish({
        "schema": SCHEMA, "origin": {"kind": STEWARD_AUTHORED}, "binding": binding, "candidate": None,
        "structure": structure,
        "acceptance": {"decision": "author", "actor": "local_steward", "actor_identity": "unknown",
                       "accepted_at": accepted_at, "reviewed_candidate_id": None,
                       "structure_sha256": _digest(canonical_bytes(structure)), "meaning": MEANING},
    })


def validate_record(record) -> dict:
    """Self-contained integrity: shape, versions, identities and internal bindings (no database)."""
    _require(isinstance(record, dict) and set(record) == _FIELDS and record["schema"] == SCHEMA, "record fields")
    _require(record["id"] == record_id(record), "record identity digest mismatch")
    binding, origin, acceptance = record["binding"], record["origin"], record["acceptance"]
    _require(isinstance(binding, dict) and set(binding) == {"receipts", "question", "governing_question", "layer1"}, "binding fields")
    receipts = binding["receipts"]
    _require(isinstance(receipts, list) and 2 <= len(receipts) <= 8
             and all(isinstance(r, dict) and set(r) == {"receipt_id", "receipt_sha256", "response_sha256", "scope_sha256"} for r in receipts)
             and len({r["receipt_id"] for r in receipts}) == len(receipts), "binding receipts")
    _require(binding["layer1"].get("schema") == "hermeneia.perspective-comparison/v1"
             and binding["layer1"].get("policy_version") == "1.0.0", "unsupported Layer 1 binding")
    governing = binding["governing_question"]
    _require(set(governing) == {"status", "text", "sha256", "basis"} and governing["basis"] == "current_snapshot_at_generation"
             and ((governing["status"] == "captured" and isinstance(governing["text"], str)
                   and governing["sha256"] == text_digest(governing["text"]))
                  or (governing["status"] == "absent" and governing["text"] is None and governing["sha256"] is None)),
             "governing-question snapshot")
    _require(binding["question"]["sha256"] == text_digest(binding["question"]["text"]), "question digest")
    _require(isinstance(acceptance, dict) and set(acceptance) == _ACCEPTANCE_FIELDS and acceptance["actor"] == "local_steward"
             and acceptance["actor_identity"] == "unknown" and acceptance["meaning"] == MEANING
             and isinstance(acceptance["accepted_at"], str), "acceptance fields")
    structure = record["structure"]
    _require(isinstance(structure, dict) and structure.get("schema") == STRUCTURE_SCHEMA
             and structure.get("participants") == [r["receipt_id"] for r in receipts], "structure participants")
    _require(acceptance["structure_sha256"] == _digest(canonical_bytes(structure)), "accepted structure digest")
    if isinstance(origin, dict) and set(origin) == {"kind"} and origin["kind"] in MODEL_ORIGINS.values():
        candidate = record["candidate"]
        _require(isinstance(candidate, dict) and set(candidate) == {"candidate_id", "extraction", "structure"}, "candidate fields")
        extraction = candidate["extraction"]
        _require(extraction.get("policy_version") == EXTRACTION_POLICY_VERSION and extraction.get("prompt_version") == PROMPT_VERSION,
                 "unsupported extraction policy or prompt version")
        _require(extraction["prompt_sha256"] == text_digest(extraction["prompt"])
                 and extraction["output_sha256"] == text_digest(extraction["output"]), "extraction digests")
        recomputed = candidate_id({"schema": CANDIDATE_SCHEMA, "binding": binding, "extraction": extraction,
                                   "structure": candidate["structure"]})
        _require(candidate["candidate_id"] == recomputed == acceptance["reviewed_candidate_id"], "candidate binding")
        _require(MODEL_ORIGINS.get(acceptance["decision"]) == origin["kind"], "origin kind must match the decision")
        if acceptance["decision"] == "accept":
            _require(structure == candidate["structure"], "exact acceptance must keep the candidate structure")
        else:
            _require(structure["untraceable"] == [], "an edited structure is never downgraded")
    else:
        _require(origin == {"kind": STEWARD_AUTHORED} and record["candidate"] is None
                 and acceptance["decision"] == "author" and acceptance["reviewed_candidate_id"] is None
                 and structure["untraceable"] == [], "steward-authored record")
    return record


def _strict(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "duplicate key")
        value[key] = item
    return value


def record_from_row(row) -> dict:
    row = dict(row)
    _require(set(row) == COLUMNS and isinstance(row["comparison_json"], str), "row columns")
    record = json.loads(row["comparison_json"], object_pairs_hook=_strict)
    _require(canonical_bytes(record).decode("utf-8") == row["comparison_json"], "stored bytes are not canonical")
    validate_record(record)
    _require(row["id"] == record["id"], "row identity mismatch")
    expected = record["candidate"]["candidate_id"] if record["candidate"] else None
    _require(row["candidate_id"] == expected, "row candidate mismatch")
    return record


def ensure_accepted_comparison_tables(conn: sqlite3.Connection) -> None:
    """Explicit additive initialization; never called by reads."""
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY, candidate_id TEXT UNIQUE, comparison_json TEXT NOT NULL)")
    for operation in ("UPDATE", "DELETE"):
        conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_{operation.lower()} BEFORE {operation} ON {TABLE} "
                     "BEGIN SELECT RAISE(ABORT, 'Accepted Perspective comparison immutable'); END")
    conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_replace BEFORE INSERT ON {TABLE} "
                 f"WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE id=NEW.id OR candidate_id=NEW.candidate_id) "
                 "BEGIN SELECT RAISE(ABORT, 'Accepted Perspective comparison already exists'); END")


def _row(conn, table, identifier):
    cursor = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?', (identifier,))
    raw = cursor.fetchone()
    return dict(zip((column[0] for column in cursor.description), raw)) if raw is not None else None


def store_accepted_comparison(conn: sqlite3.Connection, record: dict) -> dict:
    """Insert one record inside the caller's write transaction, then reread and validate it."""
    validate_record(record)
    candidate = record["candidate"]["candidate_id"] if record["candidate"] else None
    conn.execute(f"INSERT INTO {TABLE} (id, candidate_id, comparison_json) VALUES (?, ?, ?)",
                 (record["id"], candidate, canonical_bytes(record).decode("utf-8")))
    stored = record_from_row(_row(conn, TABLE, record["id"]))
    validate_record_references(conn, stored)
    return stored


def load_accepted_comparison(conn: sqlite3.Connection, identifier: str) -> dict | None:
    row = _row(conn, TABLE, identifier)
    return record_from_row(row) if row is not None else None


def _bound_receipts(conn: sqlite3.Connection, record: dict) -> list[dict]:
    receipts = []
    for binding in record["binding"]["receipts"]:
        row = _row(conn, RECEIPT_TABLE, binding["receipt_id"])
        _require(row is not None, "missing_receipt")
        _require(_digest(row["receipt_json"].encode("utf-8")) == binding["receipt_sha256"], "receipt_mismatch")
        receipt = receipt_from_row(row)
        _require(receipt["run"]["response_sha256"] == binding["response_sha256"]
                 and receipt["run"]["scope_sha256"] == binding["scope_sha256"], "receipt_mismatch")
        receipts.append(receipt)
    _require(all(r["run"]["question"] == record["binding"]["question"]["text"] for r in receipts), "receipt_mismatch")
    return receipts


def validate_record_references(conn: sqlite3.Connection, record: dict) -> None:
    """Receipt closure: exact bound receipts exist and every span and reliance resolves against them."""
    view = view_from_receipts(_bound_receipts(conn, record))
    try:
        validate_structure(record["structure"], view, allow_untraceable=record["acceptance"]["decision"] == "accept")
        if record["candidate"] is not None:
            validate_structure(record["candidate"]["structure"], view, allow_untraceable=True)
    except StructureRefused as exc:
        raise InvalidAcceptedComparison("span_mismatch") from exc


def verify_accepted_comparison(conn: sqlite3.Connection, identifier: str) -> dict:
    """Read-only verification over one snapshot; the model output is preserved, never replayed."""
    own = not conn.in_transaction
    try:
        if own:
            conn.execute("BEGIN")
        result = {"record_integrity": "invalid", "receipt_closure": "unverified", "layer1_replay": "unverified",
                  "candidate_replay": "unverified", "model_output": "preserved_not_replayed"}
        try:
            record = load_accepted_comparison(conn, identifier)
        except (InvalidAcceptedComparison, ValueError, KeyError, TypeError):
            return result
        if record is None:
            raise KeyError(identifier)
        result["record_integrity"] = "valid"
        try:
            receipts = _bound_receipts(conn, record)
            validate_record_references(conn, record)
            result["receipt_closure"] = "verified"
        except (ValueError, KeyError, TypeError) as exc:
            result["receipt_closure"] = str(exc) if str(exc) in ("missing_receipt", "receipt_mismatch", "span_mismatch") else "receipt_mismatch"
            return result
        from .perspective_achievement_evidence import read_perspective_achievement_evidence
        try:
            layer1 = compare_retained_perspectives(read_perspective_achievement_evidence(conn),
                                                   [r["receipt_id"] for r in record["binding"]["receipts"]])
            result["layer1_replay"] = ("verified" if layer1_digest(layer1) == record["binding"]["layer1"]["digest"]
                                       else "mismatch")
        except ComparisonRefused:
            result["layer1_replay"] = "participants_not_eligible"
        if record["candidate"] is None:
            result["candidate_replay"] = "not_applicable"
        else:
            view = view_from_receipts(receipts)
            extraction = record["candidate"]["extraction"]
            try:
                replayed = normalize(parse_output(extraction["output"], view), view)
                same = (build_prompt(view, unit_texts(conn, view, receipts)) == extraction["prompt"]
                        and canonical_bytes(replayed) == canonical_bytes(record["candidate"]["structure"]))
            except (ExtractionRefused, ValueError):
                same = False
            result["candidate_replay"] = "verified" if same else "mismatch"
        return result
    finally:
        if own and conn.in_transaction:
            conn.rollback()
