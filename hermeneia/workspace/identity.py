"""Durable workspace identity (issue #83).

A workspace is a named interpretive project. Its identity — who the workspace
is — must be stable and independent of the corpus it currently contains. An
empty workspace, a changed corpus, or a future library-reference workspace must
not become identity-ambiguous, so the id is generated once and persisted, never
derived from a corpus fingerprint.

The corpus-hash id remains only as an exporter *fallback* when no persistent
identity exists (e.g. a read-only export of a legacy database).
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _table_exists(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspace_identity'"
        ).fetchone()
        is not None
    )


def _as_dict(row: sqlite3.Row | tuple) -> dict[str, Any]:
    return {
        "workspace_id": row[0],
        "workspace_name": row[1],
        "created_at": row[2],
        "updated_at": row[3],
    }


def read_workspace_identity(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Return the current identity, or None if none has been created yet."""
    if not _table_exists(conn):
        return None
    row = conn.execute(
        "SELECT workspace_id, workspace_name, created_at, updated_at "
        "FROM workspace_identity WHERE id = 'current'"
    ).fetchone()
    return _as_dict(row) if row else None


def read_workspace_id(conn: sqlite3.Connection) -> str | None:
    """Return just the durable workspace id, or None."""
    identity = read_workspace_identity(conn)
    return identity["workspace_id"] if identity else None


def ensure_workspace_identity(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return the identity, generating and persisting one on first access.

    The generated ``workspace_id`` is a random uuid — deliberately unrelated to
    the corpus, so it stays stable as the corpus changes.
    """
    existing = read_workspace_identity(conn)
    if existing:
        return existing
    now = _now()
    workspace_id = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO workspace_identity
             (id, workspace_id, workspace_name, created_at, updated_at)
           VALUES ('current', ?, ?, ?, ?)""",
        (workspace_id, None, now, now),
    )
    conn.commit()
    return {
        "workspace_id": workspace_id,
        "workspace_name": None,
        "created_at": now,
        "updated_at": now,
    }


def set_workspace_name(conn: sqlite3.Connection, name: str | None) -> dict[str, Any]:
    """Rename the workspace, preserving its id and created_at."""
    ensure_workspace_identity(conn)
    cleaned = (name or "").strip() or None
    conn.execute(
        "UPDATE workspace_identity SET workspace_name = ?, updated_at = ? "
        "WHERE id = 'current'",
        (cleaned, _now()),
    )
    conn.commit()
    return read_workspace_identity(conn)  # type: ignore[return-value]
