"""ADR-0046 option U (an explicit `unverifiable` disposition): a rehearsal of its schema migration on test databases.

The product schema, SQLiteStore and the evaluator are not changed. These tests measure what option U would require:
the `findings` CHECK vocabulary can only change by rebuilding the table (SQLite cannot alter a CHECK constraint).
The rehearsal proves the rebuild can preserve every Finding and every guard, and records what it breaks.
"""
from __future__ import annotations

import sqlite3

import pytest

import synthetic_study_lab as lab
from adr0046_witness_state import Pair, connect, rows
from hermeneia.compiler.projections.audit_dashboard import audit_dashboard
from hermeneia.compiler.projections.trust_card import trust_card
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore

OPERATIONS = "'preservation','omission','transformation','injection','not_evaluated'"
STATUSES = "'preserved','omitted','transformed','injected','not_evaluated'"


@pytest.fixture
def ledger(tmp_path):
    """A full Critic ledger (every registered dimension, via the product route), one steward decision on it, and
    one supersession relation between two of its Findings."""
    with lab.isolated(tmp_path):
        pair = Pair(tmp_path)
        pair.run_critic_route(pair.source)
        conn = connect(pair.source)
        first, second = [r["id"] for r in conn.execute("SELECT id FROM findings ORDER BY id LIMIT 2")]
        conn.execute("INSERT INTO steward_decisions (id, finding_id, verdict, rationale, steward_id, decided_at, "
                     "constitution_version, created_at) VALUES ('sd', ?, 'deferred', 'Reviewed.', 'steward', 't', '{}', 't')",
                     (first,))
        conn.execute("INSERT INTO supersession_relations (old_id, new_id, reason, ratified_at) VALUES (?, ?, 'Rehearsal.', 't')",
                     (first, second))
        conn.commit()
        conn.close()
        yield pair


def _schema(conn: sqlite3.Connection, *, findings: bool) -> list[tuple]:
    clause = "=" if findings else "!="
    return [tuple(r) for r in conn.execute(f"SELECT type, name, sql FROM sqlite_master WHERE tbl_name {clause} 'findings' ORDER BY type, name")]


def rehearse_rebuild(db, *, legacy_rename: bool = True) -> None:
    """The documented SQLite table rebuild, admitting `unverifiable` in both vocabularies. Test code only."""
    conn = sqlite3.connect(db, isolation_level=None)
    try:
        objects = _schema(conn, findings=True)
        (table_sql,) = [sql for kind, _name, sql in objects if kind == "table"]
        rebuilt = (table_sql.replace("CREATE TABLE findings", "CREATE TABLE findings__rebuild", 1)
                   .replace(f"({OPERATIONS})", f"({OPERATIONS},'unverifiable')", 1)
                   .replace(f"({STATUSES})", f"({STATUSES},'unverifiable')", 1))
        assert rebuilt.count("'unverifiable'") == 2
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(f"PRAGMA legacy_alter_table={'ON' if legacy_rename else 'OFF'}")
        conn.execute("BEGIN")
        try:
            conn.execute(rebuilt)
            conn.execute("INSERT INTO findings__rebuild SELECT * FROM findings")
            conn.execute("DROP TABLE findings")
            conn.execute("ALTER TABLE findings__rebuild RENAME TO findings")
            for kind, _name, sql in objects:
                if kind in ("index", "trigger") and sql:
                    conn.execute(sql)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA legacy_alter_table=OFF")
            conn.execute("PRAGMA foreign_keys=ON")
    finally:
        conn.close()


def _insert(conn, finding: dict, verb: str = "INSERT") -> None:
    conn.execute(f"{verb} INTO findings ({', '.join(finding)}) VALUES ({', '.join('?' for _ in finding)})", list(finding.values()))


def test_the_rebuild_preserves_every_finding_and_every_guard(ledger):
    db = ledger.source
    before_rows = rows(db, "findings")
    conn = connect(db)
    other_schema = _schema(conn, findings=False)
    conn.close()

    rehearse_rebuild(db)

    conn = connect(db)
    try:
        assert rows(db, "findings") == before_rows and len(before_rows) > 10
        assert _schema(conn, findings=False) == other_schema
        assert tuple(conn.execute("PRAGMA integrity_check").fetchone()) == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.DatabaseError, match="Finding immutable"):
            conn.execute("UPDATE findings SET status = 'omitted'")
        with pytest.raises(sqlite3.DatabaseError, match="Finding immutable"):
            conn.execute("DELETE FROM findings")
        assert conn.execute("SELECT COUNT(*) FROM steward_decisions s JOIN findings f ON f.id = s.finding_id").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM supersession_relations s JOIN findings f ON f.id = s.old_id").fetchone()[0] == 1
        with pytest.raises(sqlite3.DatabaseError, match="Supersession old object missing"):
            conn.execute("INSERT INTO supersession_relations (old_id, new_id, reason, ratified_at) VALUES ('missing', ?, 'r', 't')",
                         (before_rows[0]["id"],))
    finally:
        conn.close()


def test_the_rebuild_needs_legacy_rename_because_supersession_guards_name_findings(ledger):
    db = ledger.source
    before = rows(db, "findings")
    with pytest.raises(sqlite3.OperationalError, match="error in trigger supersession_relations_.*no such table: main.findings"):
        rehearse_rebuild(db, legacy_rename=False)
    assert rows(db, "findings") == before  # rolled back whole: the failure is safe


def test_the_rebuilt_vocabulary_admits_unverifiable_and_still_needs_the_write_guard(ledger):
    db = ledger.source
    rehearse_rebuild(db)
    finding = next(f for f in rows(db, "findings") if f["dimension"] == "provenance")
    conn = connect(db)
    try:
        _insert(conn, dict(finding, id="u" * 64, operation="unverifiable", status="unverifiable"))
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            _insert(conn, dict(finding, id="b" * 64, status="bogus"))
        _insert(conn, dict(finding, id="b" * 64, status="bogus"), "INSERT OR IGNORE")  # still dropped silently
        assert conn.execute("SELECT COUNT(*) FROM findings WHERE id = ?", ("b" * 64,)).fetchone()[0] == 0
        # The schema admits the value for every dimension; scoping it to provenance is the write guard's job.
        _insert(conn, dict(finding, id="s" * 64, dimension="structural", operation="unverifiable", status="unverifiable"))
    finally:
        conn.close()


def test_current_projections_fail_on_an_unverifiable_finding(ledger):
    """Option U needs projection changes; a build without them (any older build) fails on a migrated ledger."""
    db = ledger.source
    rehearse_rebuild(db)
    finding = next(f for f in rows(db, "findings") if f["dimension"] == "provenance")
    conn = connect(db)
    try:
        _insert(conn, dict(finding, id="u" * 64, operation="unverifiable", status="unverifiable"))
        conn.commit()
        for projection in (trust_card, audit_dashboard):
            with pytest.raises(KeyError, match="unverifiable"):
                projection(ledger.narrative_id, conn)
    finally:
        conn.close()


def test_the_current_build_downgrades_a_newer_schema_marker_instead_of_refusing(ledger):
    """No build refuses a newer workspace today, so an older build would open a migrated ledger without warning."""
    db = ledger.source
    rehearse_rebuild(db)
    conn = connect(db)
    conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 1,))
    conn.commit()
    conn.close()
    SQLiteStore(db).close()
    conn = connect(db)
    try:
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == SCHEMA_VERSION
        assert "'unverifiable'" in conn.execute("SELECT sql FROM sqlite_master WHERE name = 'findings'").fetchone()[0]
    finally:
        conn.close()
