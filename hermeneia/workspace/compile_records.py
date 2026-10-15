"""Observation compile records in WBS (provenance-loss repair): one all-or-nothing component.

Compile-time Observation provenance cannot be reconstructed: it holds a
random compilation run ID, compile-time stamps and parser layout boxes. So it
travels verbatim, and so do the derived normalization and term indexes,
because carrying them is exact. A bundle without the component keeps its
Observations without provenance; provenance is never manufactured. Only the
CI-016 derived indexes are rebuilt from the restored Observations, and
coverage says so.
Contract: docs/design/wbs-observation-compile-records-v1.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

CAPABILITY = "observation-compile-records-v1"
COVERAGE_KEY = "observation_compile_records"

# (table, bundle file, manifest role, primary key, exact columns), in restore dependency order.
COMPONENTS: tuple[tuple[str, str, str, tuple[str, ...], frozenset[str]], ...] = (
    ("provenance", "corpus/provenance.json", "canonical", ("id",), frozenset({
        "id", "observation_id", "source_document_id", "source_extraction_id", "source_document_hash", "page", "paragraph",
        "sentence", "verbatim_text", "location_precision", "char_offset_start", "char_offset_end", "bbox_x", "bbox_y",
        "bbox_width", "bbox_height", "bbox_dpi", "created_at", "compiler_version", "compilation_run_id"})),
    ("observation_derived", "corpus/observation_derived.json", "derived", ("observation_id",), frozenset({
        "observation_id", "normalized_text", "sentence_tokens", "whitespace_map", "derivation_version", "derived_at"})),
    ("terms", "corpus/terms.json", "derived", ("id",), frozenset({"id", "term"})),
    ("observation_terms", "corpus/observation_terms.json", "derived", ("observation_id", "term_id"),
     frozenset({"observation_id", "term_id"})),
)
FILES = {table: path for table, path, _role, _pk, _cols in COMPONENTS}
ROLES = {table: role for table, _path, role, _pk, _cols in COMPONENTS}
_PRECEDENCE = ("COMPILE_RECORDS_SCHEMA_INCOMPLETE", "COMPILE_RECORDS_INTEGRITY_INVALID", "COMPILE_RECORDS_CLOSURE_INCOMPLETE")
REASONS = {
    "COMPILE_RECORDS_SCHEMA_INCOMPLETE": ("An Observation compile-record table is missing or has columns other than the "
                                          "supported schema; provenance and indexes are not exported."),
    "COMPILE_RECORDS_INTEGRITY_INVALID": ("A provenance row's identity differs from its Observation (ADR-0012); provenance "
                                          "and indexes are not exported rather than exported in part."),
    "COMPILE_RECORDS_CLOSURE_INCOMPLETE": ("An Observation compile record references a record that does not exist; provenance "
                                           "and indexes are not exported rather than left dangling."),
}
COVERED_REASON = "Observation provenance and derived indexes carried verbatim with closure."
UNSUPPORTED_REASON = ("This bundle does not carry Observation provenance; it is not reconstructed, so restored Observations "
                      "have no provenance rows.")


class CompileRecordsError(ValueError):
    """A bundle's compile-records component is malformed, contradictory or not closed; nothing is restored."""


def _dicts(conn: sqlite3.Connection, sql: str) -> list[dict]:
    cursor = conn.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def problems(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Integrity and closure problems of the compile records in this snapshot, most severe first; IDs only."""
    found: list[tuple[str, str]] = []

    def ids(table: str) -> set[str]:
        return {row[0] for row in conn.execute(f'SELECT id FROM "{table}"')}

    observations, documents, extractions, terms = (ids("observations"), ids("source_documents"),
                                                   ids("source_extractions"), ids("terms"))
    for identifier, observation, document, extraction in conn.execute(
            "SELECT id, observation_id, source_document_id, source_extraction_id FROM provenance ORDER BY id"):
        if identifier != observation:
            found.append(("COMPILE_RECORDS_INTEGRITY_INVALID", f"provenance {identifier}"))
        if observation not in observations or document not in documents or extraction not in extractions:
            found.append(("COMPILE_RECORDS_CLOSURE_INCOMPLETE", f"provenance {identifier}"))
    for (observation,) in conn.execute("SELECT observation_id FROM observation_derived ORDER BY observation_id"):
        if observation not in observations:
            found.append(("COMPILE_RECORDS_CLOSURE_INCOMPLETE", f"observation_derived {observation}"))
    for observation, term in conn.execute("SELECT observation_id, term_id FROM observation_terms ORDER BY observation_id, term_id"):
        if observation not in observations or term not in terms:
            found.append(("COMPILE_RECORDS_CLOSURE_INCOMPLETE", f"observation_terms {observation} {term}"))
    return sorted(found, key=lambda item: (_PRECEDENCE.index(item[0]), item[1]))


def observations_without_provenance(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM observations WHERE id NOT IN (SELECT observation_id FROM provenance)").fetchone()[0]


# ── Export ───────────────────────────────────────────────────────────────────

def export_component(conn: sqlite3.Connection) -> tuple[dict[str, list[dict]] | None, dict | None]:
    """From the caller's read snapshot: (exact rows by table, None), or (None, the unsupported declaration)."""
    present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    needed = {table for table, *_ in COMPONENTS} | {"observations", "source_documents", "source_extractions"}
    if not needed <= present or any(_columns(conn, table) != set(columns) for table, _p, _r, _pk, columns in COMPONENTS):
        code = "COMPILE_RECORDS_SCHEMA_INCOMPLETE"
        return None, {"reason_code": code, "reason": REASONS[code]}
    found = problems(conn)
    if found:
        code = found[0][0]
        return None, {"reason_code": code, "reason": REASONS[code], "problem_count": len(found)}
    return {table: _dicts(conn, f'SELECT * FROM "{table}" ORDER BY {", ".join(pk)}')
            for table, _path, _role, pk, _cols in COMPONENTS}, None


# ── Restore ──────────────────────────────────────────────────────────────────

def _unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def read_component(root: Path, manifest: dict) -> tuple[dict[str, list[dict]] | None, dict]:
    """Validate the component before any write: (rows by table, coverage), or CompileRecordsError."""
    declared = CAPABILITY in (manifest.get("required_capabilities") or [])
    unsupported = (manifest.get("declared_unsupported") or {}).get(CAPABILITY)
    listed = [entry for entry in manifest.get("files") or [] if entry.get("path") in FILES.values()]
    present = [path for path in FILES.values() if (root / path).exists()]
    if unsupported is not None:
        if declared or listed or present:
            raise CompileRecordsError("compile records are declared unsupported but their files or capability are present")
        if not isinstance(unsupported, dict) or unsupported.get("reason_code") not in REASONS:
            raise CompileRecordsError("compile-records unsupported declaration is malformed")
        return None, {"status": "unsupported", "reason_code": unsupported["reason_code"], "reason": REASONS[unsupported["reason_code"]]}
    if not declared:
        if listed or present:
            raise CompileRecordsError("compile-record files are present without their required capability declaration")
        return None, {"status": "unsupported", "reason": UNSUPPORTED_REASON}
    entries = {entry.get("path"): entry for entry in listed}
    if len(listed) != len(FILES) or len(entries) != len(FILES):
        raise CompileRecordsError("compile-records component must list every file exactly once")
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise CompileRecordsError("compile-records component requires explicit record counts")
    rows: dict[str, list[dict]] = {}
    resolved_root = root.resolve()
    for table, path, role, pk, columns in COMPONENTS:
        entry, file = entries[path], root / path
        if entry.get("role") != role or not file.is_file() or resolved_root not in file.resolve().parents:
            raise CompileRecordsError(f"compile-record file {path} must be a {role} file inside the bundle")
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise CompileRecordsError(f"compile-record file {path} failed its hash check")
        try:
            table_rows = json.loads(data, object_pairs_hook=_unique_keys)
        except (ValueError, UnicodeError) as exc:
            raise CompileRecordsError(f"compile-record file {path} is not valid JSON") from exc
        if not isinstance(table_rows, list) or not all(isinstance(row, dict) and set(row) == columns for row in table_rows):
            raise CompileRecordsError(f"compile-record file {path} must hold rows with exactly the supported columns")
        keys = [tuple(row[column] for column in pk) for row in table_rows]
        if len(set(keys)) != len(keys) or keys != sorted(keys):
            raise CompileRecordsError(f"compile-record file {path} must use unique keys in primary-key order")
        if type(counts.get(table)) is not int or counts[table] != len(table_rows):
            raise CompileRecordsError(f"compile-record count for {table} disagrees with its file")
        rows[table] = table_rows
    return rows, {"status": "covered", "extant_records": {table: len(value) for table, value in rows.items()},
                  "reason": COVERED_REASON}


def insert_component(conn: sqlite3.Connection, rows: dict[str, list[dict]]) -> dict[str, int]:
    """Insert exact rows inside the caller's restore transaction, after Observations; then prove closure."""
    restored = {}
    for table, _path, _role, _pk, columns in COMPONENTS:
        if not set(columns) <= _columns(conn, table):
            raise CompileRecordsError(f"target cannot store the complete {table} row")
        ordered = sorted(columns)
        for row in rows[table]:
            conn.execute(f'INSERT INTO "{table}" ({", ".join(ordered)}) VALUES ({", ".join("?" for _ in ordered)})',
                         [row[column] for column in ordered])
        restored[table] = len(rows[table])
    found = problems(conn)
    if found:
        raise CompileRecordsError(f"restored compile records are not closed: {found[0][0]} ({found[0][1]})")
    return restored


def rebuild_derived_indexes(conn: sqlite3.Connection) -> dict:
    """CI-016: regenerate the derived indexes from restored Observations for a bundle that lacks them.

    Never touches Observations, extractions, documents or provenance. The derivation version and time are recorded.
    """
    from ..compiler.normalization import normalize_sentence
    from ..compiler.observation_compiler import COMPILER_VERSION
    from ..field.index import extract_terms, term_id

    derived_at = datetime.now(timezone.utc).isoformat()
    observations = conn.execute("SELECT id, raw_text FROM observations ORDER BY id").fetchall()
    terms: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []
    for identifier, raw_text in observations:
        normalized = normalize_sentence(raw_text)
        conn.execute("INSERT INTO observation_derived (observation_id, normalized_text, sentence_tokens, whitespace_map, "
                     "derivation_version, derived_at) VALUES (?, ?, '[]', '[]', ?, ?)",
                     (identifier, normalized, COMPILER_VERSION, derived_at))
        # The same text choice and tokenizer as field.index.build_term_index.
        for term in extract_terms(normalized or raw_text or ""):
            pairs.append((identifier, terms.setdefault(term, term_id(term))))
    conn.executemany("INSERT OR IGNORE INTO terms (id, term) VALUES (?, ?)", [(tid, term) for term, tid in terms.items()])
    conn.executemany("INSERT OR IGNORE INTO observation_terms (observation_id, term_id) VALUES (?, ?)", pairs)
    return {"status": "rebuilt", "derivation_version": COMPILER_VERSION, "derived_at": derived_at,
            "rebuilt_records": {"observation_derived": len(observations), "terms": len(terms), "observation_terms": len(pairs)}}
