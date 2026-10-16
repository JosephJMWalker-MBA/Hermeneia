"""ADR-0046 packet 4: D-2 readings and an implementation-ready U (the schema-22 migration and provenance-v1.1).

Nothing here activates U. The product migration runs only on test databases; `provenance-v1.1` runs only when asked
for explicitly; the write guard still refuses `unverifiable`. Activation is gated separately
(tests/test_adr0046_activation_gate.py). This file supersedes the earlier rehearsal: the same checks, against the
product migration.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

import synthetic_study_lab as lab
from adr0046_witness_state import ABSENT, Pair, by_obligation, connect, render, rows
from hermeneia.compiler.evaluation_functions import provenance
from hermeneia.compiler.projections.audit_dashboard import audit_dashboard
from hermeneia.compiler.projections.finding_readings import finding_reading
from hermeneia.compiler.projections.trust_card import trust_card
from hermeneia.storage import findings_vocabulary
from hermeneia.storage import sqlite as storage
from hermeneia.storage.findings_vocabulary import FindingsMigrationError, admits_unverifiable, migrate_findings_vocabulary
from hermeneia.storage.schema_guard import NewerSchemaError
from hermeneia.storage.sqlite import SCHEMA_VERSION, FindingLedgerRefusal, SQLiteStore
from hermeneia.web.app import create_app

INDEX = Path(__file__).resolve().parents[1] / "hermeneia" / "web" / "static" / "index.html"


@pytest.fixture
def pair(tmp_path):
    with lab.isolated(tmp_path):
        yield Pair(tmp_path)


@pytest.fixture
def ledger(pair):
    """A full Critic ledger, a steward decision on one Finding and a supersession relation between two."""
    pair.run_critic_route(pair.source)
    conn = connect(pair.source)
    first, second = [r["id"] for r in conn.execute("SELECT id FROM findings ORDER BY id LIMIT 2")]
    conn.execute("INSERT INTO steward_decisions (id, finding_id, verdict, rationale, steward_id, decided_at, "
                 "constitution_version, created_at) VALUES ('sd', ?, 'deferred', 'Reviewed.', 'steward', 't', '{}', 't')", (first,))
    conn.execute("INSERT INTO supersession_relations (old_id, new_id, reason, ratified_at) VALUES (?, ?, 'Rehearsal.', 't')",
                 (first, second))
    conn.commit()
    conn.close()
    return pair


def _schema(db, *, findings: bool) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        clause = "=" if findings else "!="
        return [tuple(r) for r in conn.execute(f"SELECT type, name, sql FROM sqlite_master WHERE tbl_name {clause} 'findings' "
                                               "ORDER BY type, name")]
    finally:
        conn.close()


def _insert(db, finding: dict) -> None:
    conn = sqlite3.connect(db)
    try:
        conn.execute(f"INSERT INTO findings ({', '.join(finding)}) VALUES ({', '.join('?' for _ in finding)})", list(finding.values()))
        conn.commit()
    finally:
        conn.close()


# ── The schema-22 migration (product code, test databases only) ─────────────

def test_the_migration_preserves_every_finding_and_every_guard(ledger):
    db = ledger.source
    before, other_schema = rows(db, "findings"), _schema(db, findings=False)
    assert migrate_findings_vocabulary(db) == {"status": "migrated", "findings": len(before)}
    conn = connect(db)
    try:
        assert admits_unverifiable(conn)
        assert rows(db, "findings") == before and len(before) > 10
        assert _schema(db, findings=False) == other_schema
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
                         (before[0]["id"],))
    finally:
        conn.close()


def test_the_migration_is_idempotent(ledger):
    migrate_findings_vocabulary(ledger.source)
    after = (rows(ledger.source, "findings"), _schema(ledger.source, findings=True))
    assert migrate_findings_vocabulary(ledger.source) == {"status": "already_migrated"}
    assert (rows(ledger.source, "findings"), _schema(ledger.source, findings=True)) == after


def test_a_failure_after_the_destructive_steps_rolls_everything_back(ledger, monkeypatch):
    db = ledger.source
    before, findings_schema = rows(db, "findings"), _schema(db, findings=True)
    real, calls = findings_vocabulary._ledger, []

    def drifting(conn):  # the second reading (after the rebuild) disagrees
        calls.append(1)
        count, digest = real(conn)
        return (count, digest) if len(calls) == 1 else (count, "0" * 64)

    monkeypatch.setattr(findings_vocabulary, "_ledger", drifting)
    with pytest.raises(FindingsMigrationError, match="rolled back"):
        migrate_findings_vocabulary(db)
    assert rows(db, "findings") == before and _schema(db, findings=True) == findings_schema


def test_a_conflicting_object_stops_the_migration_before_any_change(ledger):
    db = ledger.source
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE findings__v22 (id TEXT)")
    conn.commit()
    conn.close()
    before = rows(db, "findings")
    with pytest.raises(sqlite3.OperationalError, match="already exists"):
        migrate_findings_vocabulary(db)
    assert rows(db, "findings") == before and not admits_unverifiable(sqlite3.connect(db))


def test_an_unknown_findings_schema_is_refused(tmp_path):
    db = tmp_path / "other.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE findings (id TEXT PRIMARY KEY, status TEXT)")
    conn.close()
    with pytest.raises(FindingsMigrationError, match="nothing was changed"):
        migrate_findings_vocabulary(db)


def test_sqlite_refuses_the_rename_without_legacy_mode(ledger):
    """Why the migration renames in legacy mode: the supersession guards name `findings`."""
    conn = sqlite3.connect(ledger.source, isolation_level=None)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")
        conn.execute("CREATE TABLE findings__probe AS SELECT * FROM findings")
        conn.execute("DROP TABLE findings")
        with pytest.raises(sqlite3.OperationalError, match="supersession_relations_.*no such table: main.findings"):
            conn.execute("ALTER TABLE findings__probe RENAME TO findings")
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    assert rows(ledger.source, "findings")


def test_a_workspace_marked_22_is_refused_by_this_build_and_a_lowered_marker_is_recognised(ledger):
    db = ledger.source
    migrate_findings_vocabulary(db)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE schema_version SET version = 22")
    conn.commit()
    conn.close()
    with pytest.raises(NewerSchemaError):
        SQLiteStore(db)  # ADR-0048: this (schema-21) build never opens it
    conn = sqlite3.connect(db)
    conn.execute("UPDATE schema_version SET version = 21")  # what a build older than ADR-0048 would do
    conn.commit()
    conn.close()
    assert migrate_findings_vocabulary(db) == {"status": "already_migrated"}


def test_the_r2_procedure_takes_a_verified_backup_before_migrating(ledger, tmp_path):
    db, backup = ledger.source, tmp_path / "backups" / "pre-schema-22.db"
    before = rows(db, "findings")
    result = findings_vocabulary.migrate_with_verified_backup(db, backup)
    assert result["status"] == "migrated" and rows(db, "findings") == before
    assert rows(backup, "findings") == before and not admits_unverifiable(sqlite3.connect(backup))  # the pre-migration ledger
    with pytest.raises(FindingsMigrationError, match="refusing to overwrite"):
        findings_vocabulary.migrate_with_verified_backup(db, backup)


def test_a_failed_r2_migration_keeps_the_verified_backup_and_rolls_back(ledger, tmp_path, monkeypatch):
    db, backup = ledger.source, tmp_path / "pre-schema-22.db"
    before = rows(db, "findings")
    real, calls = findings_vocabulary._ledger, []
    monkeypatch.setattr(findings_vocabulary, "_ledger",
                        lambda conn: (calls.append(1), real(conn) if len(calls) == 1 else (0, ""))[1])
    with pytest.raises(FindingsMigrationError):
        findings_vocabulary.migrate_with_verified_backup(db, backup)
    assert rows(db, "findings") == before and not admits_unverifiable(sqlite3.connect(db))
    assert rows(backup, "findings") == before


# ── Write guard and projections around `unverifiable` ───────────────────────

def test_before_activation_the_write_guard_refuses_unverifiable_even_on_a_migrated_ledger(pair):
    migrate_findings_vocabulary(pair.restored)
    findings = provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, connect(pair.restored),
                                              method=provenance.UNVERIFIABLE_METHOD)
    with pytest.raises(FindingLedgerRefusal) as refused:
        pair.persist(pair.restored, findings)
    assert refused.value.refusal_class == "unsupported_value"
    assert rows(pair.restored, "findings") == []


def test_at_activation_the_write_guard_admits_unverifiable_for_provenance_only(pair, monkeypatch):
    monkeypatch.setattr(storage, "ACTIVE_DIMENSION_DISPOSITIONS", dict(storage.PENDING_DIMENSION_DISPOSITIONS))
    migrate_findings_vocabulary(pair.restored)
    findings = provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, connect(pair.restored),
                                              method=provenance.UNVERIFIABLE_METHOD)
    assert len(pair.persist(pair.restored, findings)["inserted"]) == len(findings)
    with pytest.raises(FindingLedgerRefusal):
        pair.persist(pair.restored, [dict(findings[0], id="s" * 64, dimension="structural")])


def test_projections_count_unverifiable_without_failing(pair):
    migrate_findings_vocabulary(pair.restored)
    for finding in provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, connect(pair.restored),
                                                  method=provenance.UNVERIFIABLE_METHOD):
        _insert(pair.restored, finding)
    conn = connect(pair.restored)
    try:
        assert trust_card(pair.narrative_id, conn)["dimensions"]["provenance"] == "partial"  # not success
        counts = audit_dashboard(pair.narrative_id, conn)["dimensions"]["provenance"]
        assert counts["unverifiable"] == len(pair.observations) and counts["transformed"] == 0
    finally:
        conn.close()


# ── provenance-v1.1, explicitly requested (the default stays v1.0) ──────────

def test_provenance_v1_1_records_unverifiable_for_an_absent_record_and_nothing_else_changes(pair):
    states = pair.four_states()
    v10 = by_obligation(pair.critic(pair.restored))
    v11 = by_obligation(provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, connect(pair.restored),
                                                       method=provenance.UNVERIFIABLE_METHOD))
    assert {state: (v11[o]["operation"], v11[o]["status"]) for o, state in states.items()} == {
        "missing_provenance": ("unverifiable", "unverifiable"),
        "demonstrated_alteration": ("preservation", "preserved"),
        "preserved_provenance": ("preservation", "preserved"),
        "missing_observation": ("omission", "omitted"),
    }
    assert len(v11) == len(v10)  # completeness
    # Same Finding IDs; v1.1 records the v1.0 facts unchanged plus the Blueprint link (ADR-0047 L2-b).
    assert {o: f["id"] for o, f in v11.items()} == {o: f["id"] for o, f in v10.items()}
    assert {o: {k: v for k, v in render(f).items() if k != "blueprint_link_exists"} for o, f in v11.items()} == \
        {o: render(f) for o, f in v10.items()}
    # Every cited Observation is linked to the Blueprint; the phantom obligation's citation is not.
    assert {o: render(f)["blueprint_link_exists"] for o, f in v11.items()} == {o: o in pair.observations for o in v11}
    assert {f["evaluation_method"] for f in v11.values()} == {"provenance-v1.1"}
    with pytest.raises(ValueError, match="unknown provenance evaluation method"):
        provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, connect(pair.restored), method="provenance-v9")


# ── D-2: readings from a Finding's own fields ───────────────────────────────

def test_every_provenance_finding_has_an_exact_reading_naming_its_method(pair):
    states = pair.four_states()
    for method in ("provenance-v1.0", "provenance-v1.1"):
        findings = by_obligation(provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, connect(pair.restored),
                                                                method=method))
        readings = {state: finding_reading(findings[o]) for o, state in states.items()}
        for state, reading in readings.items():
            assert reading["evaluation_method"] == method and reading["established"] is not None, (method, state)
            assert reading["attribution"] == f"recorded as {findings[next(o for o, s in states.items() if s == state)]['status']} by {method}"
        assert readings["demonstrated_alteration"]["not_established"] == readings["preserved_provenance"]["not_established"]
        assert "that the record agrees with the Observation" in readings["preserved_provenance"]["not_established"]
    v10 = finding_reading(by_obligation(pair.critic(pair.restored))[next(o for o, s in states.items() if s == "missing_provenance")])
    assert v10["attribution"] == "recorded as transformed by provenance-v1.0"
    assert "any alteration of the Observation" in v10["not_established"]


def test_a_reading_never_claims_more_than_its_table_knows(pair):
    finding = dict(pair.critic(pair.restored)[0], evaluation_method="structural-v1.0", dimension="semantic")
    reading = finding_reading(finding)
    assert reading["established"] is None and reading["not_established"] is None
    assert reading["ratified_dimension"] is False


def test_the_finding_endpoints_carry_the_reading(pair):
    pair.run_critic_route(pair.source)
    client = create_app(db_path=pair.source, credential_store=lab._NoCredentials()).test_client()
    listed = client.get("/api/e10/findings").get_json()["findings"]
    assert listed and all(f["reading"]["evaluation_method"] == f["evaluation_method"] for f in listed)
    one = next(f for f in listed if f["dimension"] == "provenance")
    lineage = client.get(f"/api/e10/findings/{one['id']}/lineage").get_json()
    assert lineage["finding"]["reading"]["attribution"] == "recorded as preserved by provenance-v1.0"


def _extract_function(source: str, signature: str) -> str:
    start = source.index(signature)
    depth, i = 0, source.index("{", start)
    while i < len(source):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[start:i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces extracting {signature!r}")


def test_the_reader_shows_the_attribution_and_what_was_established():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    source = INDEX.read_text(encoding="utf-8")
    assert "${x(f.reading ? f.reading.attribution : f.status)}" in source
    function = _extract_function(source, "function e10FindingReadingHtml(reading)")
    reading = {"attribution": "recorded as transformed by provenance-v1.0", "established": ["the Observation existed"],
               "not_established": ["any alteration of the Observation"], "ratified_dimension": False}
    script = ("const x = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;');\n" + function +
              f"\nprocess.stdout.write(e10FindingReadingHtml({json.dumps(reading)}) + '|' + e10FindingReadingHtml(null));")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout
    html, empty = out.rsplit("|", 1)
    assert "recorded as transformed by provenance-v1.0" in html
    assert "Its evidence established:</strong> the Observation existed" in html
    assert "It did not establish:</strong> any alteration of the Observation" in html
    assert "Unratified dimension (historical)" in html and empty == ""
