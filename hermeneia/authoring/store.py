"""Append-only persistence for S1 Publication Compositor authoring references.

Hermeneia stores *references and authored decisions*, never an editable copy of
the publication model. Compositor-produced artifacts (source IR, C0, ledgers,
versions, receipts, proofs) are kept byte for byte under the workspace's
``publication/<work_id>/`` area and addressed by SHA-256; the rows below point
at those exact bytes.

HISTORY IS IMMUTABLE; THE CURRENT WORK IS REVISABLE. Every table is
append-only (update/delete triggers abort). The current manuscript is the head
of the accepted-outcome chain, derived from history rather than stored as a
mutable pointer.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

AUTHORING_TABLES = (
    "publication_works",
    "publication_artifacts",
    "authoring_drafts",
    "authoring_proposals",
    "authoring_decisions",
    "authoring_requests",
    "authoring_outcomes",
    "authoring_proofs",
)

AUTHORING_DDL = """
CREATE TABLE IF NOT EXISTS publication_works (
    id                          TEXT PRIMARY KEY,
    workspace_id                TEXT NOT NULL,
    label                       TEXT,
    work_root_json              TEXT NOT NULL,
    inputs_json                 TEXT NOT NULL,
    renderer_environment_sha256 TEXT,
    facade_pin_json             TEXT NOT NULL,
    root_version_ref            TEXT NOT NULL,
    synthetic                   INTEGER NOT NULL DEFAULT 0,
    attached_by                 TEXT NOT NULL,
    attached_at                 TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_works_workspace
    ON publication_works(workspace_id);

CREATE TABLE IF NOT EXISTS publication_artifacts (
    sha256      TEXT PRIMARY KEY,
    work_id     TEXT NOT NULL REFERENCES publication_works(id),
    kind        TEXT NOT NULL,
    relpath     TEXT NOT NULL,
    byte_length INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS authoring_drafts (
    id                TEXT PRIMARY KEY,
    work_id           TEXT NOT NULL REFERENCES publication_works(id),
    parent_version_ref TEXT NOT NULL,
    unit_id           TEXT NOT NULL,
    draft_text        TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS authoring_proposals (
    id                   TEXT PRIMARY KEY,
    work_id              TEXT NOT NULL REFERENCES publication_works(id),
    parent_version_ref   TEXT NOT NULL,
    unit_id              TEXT NOT NULL,
    unit_text_sha256     TEXT NOT NULL,
    unit_semantic_sha256 TEXT NOT NULL,
    operation            TEXT NOT NULL,
    start_offset         INTEGER NOT NULL,
    end_offset           INTEGER NOT NULL,
    before_value         TEXT NOT NULL,
    after_value          TEXT NOT NULL,
    rationale            TEXT NOT NULL,
    proposed_by          TEXT NOT NULL,
    record_json          TEXT NOT NULL,
    proposal_sha256      TEXT NOT NULL,
    validation_status    TEXT NOT NULL,
    validation_json      TEXT NOT NULL,
    created_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS authoring_decisions (
    id                 TEXT PRIMARY KEY,
    proposal_id        TEXT NOT NULL UNIQUE REFERENCES authoring_proposals(id),
    proposal_sha256    TEXT NOT NULL,
    decision           TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
    actor              TEXT NOT NULL,
    rationale          TEXT NOT NULL,
    workspace_id       TEXT NOT NULL,
    target_version_ref TEXT NOT NULL,
    decision_sha256    TEXT NOT NULL,
    decided_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS authoring_requests (
    id                     TEXT PRIMARY KEY,
    decision_id            TEXT NOT NULL REFERENCES authoring_decisions(id),
    work_id                TEXT NOT NULL REFERENCES publication_works(id),
    expected_parent_ref    TEXT NOT NULL,
    idempotency_key        TEXT NOT NULL,
    record_artifact_sha256 TEXT NOT NULL,
    attempt                INTEGER NOT NULL,
    created_at             TEXT NOT NULL,
    UNIQUE(decision_id, attempt)
);

CREATE TABLE IF NOT EXISTS authoring_outcomes (
    id                       TEXT PRIMARY KEY,
    request_id               TEXT NOT NULL UNIQUE REFERENCES authoring_requests(id),
    work_id                  TEXT NOT NULL REFERENCES publication_works(id),
    status                   TEXT NOT NULL CHECK(status IN ('accepted','refused','error')),
    chain_index              INTEGER,
    receipt_artifact_sha256  TEXT,
    version_artifact_sha256  TEXT,
    ledger_artifact_sha256   TEXT,
    overlay_artifact_sha256  TEXT,
    result_version_ref       TEXT,
    result_version_sha256    TEXT,
    findings_json            TEXT NOT NULL,
    created_at               TEXT NOT NULL,
    UNIQUE(work_id, chain_index)
);

CREATE TABLE IF NOT EXISTS authoring_proofs (
    id                    TEXT PRIMARY KEY,
    work_id               TEXT NOT NULL REFERENCES publication_works(id),
    version_ref           TEXT NOT NULL,
    status                TEXT NOT NULL CHECK(status IN ('verified','failed','refused','error')),
    result_artifact_sha256 TEXT,
    pdf_artifact_sha256   TEXT,
    references_json       TEXT NOT NULL,
    findings_json         TEXT NOT NULL,
    created_at            TEXT NOT NULL
);
""" + "".join(
    f"""
CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table}
BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;
CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table}
BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;
"""
    for table in AUTHORING_TABLES
)


def ensure_authoring_schema(conn: sqlite3.Connection) -> None:
    """Create the S1 authoring tables. Called only from the SQLiteStore write path."""
    conn.executescript(AUTHORING_DDL)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def authoring_tables_exist(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='publication_works'"
    ).fetchone()
    return row is not None


def work_dir(db_path: str | Path, work_id: str) -> Path:
    return Path(db_path).parent / "publication" / work_id


def store_artifact(
    conn: sqlite3.Connection,
    db_path: str | Path,
    work_id: str,
    kind: str,
    data: bytes,
    *,
    suffix: str = ".json",
    now: str,
) -> str:
    """Write exact bytes content-addressed under the work area; idempotent by hash."""
    digest = sha256_bytes(data)
    relpath = f"artifacts/{digest}{suffix}"
    target = work_dir(db_path, work_id) / relpath
    if target.exists():
        if sha256_bytes(target.read_bytes()) != digest:
            raise ValueError(f"stored artifact {relpath} does not match its content address")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    existing = conn.execute(
        "SELECT kind FROM publication_artifacts WHERE sha256 = ?", (digest,)
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO publication_artifacts (sha256, work_id, kind, relpath, byte_length, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (digest, work_id, kind, relpath, len(data), now),
        )
    return digest


def read_artifact(conn: sqlite3.Connection, db_path: str | Path, digest: str) -> bytes:
    row = conn.execute(
        "SELECT work_id, relpath FROM publication_artifacts WHERE sha256 = ?", (digest,)
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown artifact {digest}")
    data = (work_dir(db_path, row[0]) / row[1]).read_bytes()
    if sha256_bytes(data) != digest:
        raise ValueError(f"artifact {digest} failed its content-address check")
    return data


def artifact_relpath(conn: sqlite3.Connection, digest: str) -> str:
    row = conn.execute("SELECT relpath FROM publication_artifacts WHERE sha256 = ?", (digest,)).fetchone()
    if row is None:
        raise KeyError(f"unknown artifact {digest}")
    return row[0]


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.execute(sql, params)
    names = [c[0] for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def get_work(conn: sqlite3.Connection) -> dict | None:
    if not authoring_tables_exist(conn):
        return None
    found = rows(conn, "SELECT * FROM publication_works ORDER BY attached_at, id")
    return found[0] if found else None


def accepted_chain(conn: sqlite3.Connection, work_id: str) -> list[dict]:
    """Accepted outcomes in chain order, joined to their request and decision."""
    return rows(
        conn,
        """SELECT o.*, r.idempotency_key, r.expected_parent_ref, r.record_artifact_sha256,
                  r.decision_id, d.proposal_id
           FROM authoring_outcomes o
           JOIN authoring_requests r ON r.id = o.request_id
           JOIN authoring_decisions d ON d.id = r.decision_id
           WHERE o.work_id = ? AND o.status = 'accepted'
           ORDER BY o.chain_index""",
        (work_id,),
    )


def export_tables(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    if not authoring_tables_exist(conn):
        return {}
    order = {
        "publication_works": "attached_at, id",
        "publication_artifacts": "created_at, sha256",
        "authoring_drafts": "created_at, id",
        "authoring_proposals": "created_at, id",
        "authoring_decisions": "decided_at, id",
        "authoring_requests": "created_at, id",
        "authoring_outcomes": "created_at, id",
        "authoring_proofs": "created_at, id",
    }
    return {table: rows(conn, f"SELECT * FROM {table} ORDER BY {order[table]}") for table in AUTHORING_TABLES}
