"""ADR-0048 post-open write races: the witnesses of docs/verification/2026-10-24-adr0048-post-open-write-races.md.

A newer build may commit its migration at any moment this build holds no transaction on the workspace. The rule these
witnesses pin (Option B of that record, drafted as ADR-0050): wherever that happens, this build writes nothing to the
workspace afterwards.

Each witness runs one operation, finds every point where a workspace connection is about to start a transaction, and
replays the operation with a newer migration committed exactly there. It replays every point, or eight evenly spaced
points including the first and the last when there are more. The store's own guarded initialization is left out,
because test_newer_schema_refusal_boundaries.py pins it.

Current main lets these writes land, so each witness is a strict xfail that may fail only by assertion. When the
protection lands, it XPASSes, fails strictly, and must be unmarked. A witness whose operation never reaches a workspace
transaction raises instead, so a moved seam cannot hide behind its xfail.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
from pathlib import Path
import shutil
import sqlite3
import sys
from unittest import mock

import pytest

import synthetic_study_lab as lab
from hermeneia.storage.schema_guard import _keyword
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
from hermeneia.web.app import create_app

_connect = sqlite3.connect
_TRANSACTION_STARTS = {"BEGIN", "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"}
_SAMPLED_POINTS = 8

RACE = pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "ADR-0048 post-open write race (docs/verification/2026-10-24-adr0048-post-open-write-races.md); "
    "unmark when every write transaction re-checks the marker (draft ADR-0050)"))


class SeamNotReached(RuntimeError):
    """The operation never started a transaction on the workspace, so the witness proved nothing."""


def _migrate_as_newer_build(db: Path, shape: str) -> None:
    """Another process running a newer build commits its migration. It never waits for a lock."""
    conn = _connect(db, timeout=0)
    try:
        if shape == "append":
            conn.execute("CREATE TABLE future_records (id TEXT PRIMARY KEY)")
        else:  # a newer schema that moved a table an older migration would recreate
            conn.execute("ALTER TABLE expression_profiles RENAME TO expression_profiles_v22")
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 1,))
        conn.commit()
    finally:
        conn.close()


def _state(db: Path) -> tuple:
    """The schema cookie (moved by any DDL), the marker and the logical content."""
    conn = _connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return (conn.execute("PRAGMA schema_version").fetchone()[0],
                [r[0] for r in conn.execute("SELECT version FROM schema_version")],
                hashlib.sha256("\n".join(conn.iterdump()).encode()).hexdigest())
    finally:
        conn.close()


def _in_store_initialization() -> bool:
    frame = sys._getframe(2)
    while frame is not None:
        if frame.f_code.co_name == "create_app" or (
                frame.f_code.co_name == "__init__" and isinstance(frame.f_locals.get("self"), SQLiteStore)):
            return True
        frame = frame.f_back
    return False


@contextlib.contextmanager
def _newer_migration_at(db: Path, point: int | None, shape: str, skip, observed: list):
    """Count the transaction starts on ``db``; just before the ``point``-th, commit a newer migration.

    ``observed`` receives the state right after the newer migration, or None when another connection held the write
    lock there, so that no newer build could have committed at that point.
    """
    seen, target = [0], db.resolve()

    def connect(database, *args, **kwargs):
        conn = _connect(database, *args, **kwargs)
        if isinstance(database, (str, Path)) and not str(database).startswith("file:") \
                and Path(database).resolve() == target:
            def trace(sql):
                if conn.in_transaction or _keyword(sql) not in _TRANSACTION_STARTS or skip():
                    return
                if seen[0] == point:
                    try:
                        _migrate_as_newer_build(db, shape)
                        observed.append(_state(db))
                    except sqlite3.OperationalError as exc:
                        observed.append(None if "locked" in str(exc) else ("error", repr(exc)))
                seen[0] += 1

            conn.set_trace_callback(trace)
        return conn

    with mock.patch.object(sqlite3, "connect", connect):
        yield seen


def _replay(tmp_path: Path, template: Path, database: str, operate, *, shape: str = "append",
            skip=_in_store_initialization) -> int:
    """Replay ``operate`` on fresh copies of ``template`` with a newer migration at each transaction start.

    Returns how many points were checked. Asserts that nothing was written after the newer migration at any of them.
    """
    def run(point):
        root = tmp_path / f"replay-{point}"
        shutil.copytree(template, root)
        db, observed = root / database, []
        with _newer_migration_at(db, point, shape, skip, observed) as seen:
            with contextlib.suppress(Exception, SystemExit):
                operate(root, db)
        return seen[0], observed, db

    points, _, _ = run(None)
    if not points:
        raise SeamNotReached("the operation started no transaction on the workspace")
    step = max(1, (points - 1) // (_SAMPLED_POINTS - 1))
    chosen = sorted(set(range(0, points, step)) | {points - 1}) if points > _SAMPLED_POINTS else range(points)
    checked = 0
    for point in chosen:
        _, observed, db = run(point)
        if observed and isinstance(observed[0], tuple) and observed[0][0] == "error":
            raise SeamNotReached(f"the newer migration could not be committed at point {point}: {observed[0][1]}")
        if observed == [None]:
            continue
        checked += 1
        assert _state(db) == observed[0], f"written after a newer migration committed before transaction {point}"
    return checked


@pytest.fixture
def study(tmp_path):
    """A closed real workspace (one uploaded PDF, two Observations) and a WBS bundle of it, under ``template``."""
    with lab.isolated(tmp_path):
        template = tmp_path / "template"
        db = template / "ws" / "hermeneia.db"
        SQLiteStore(db).close()
        client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
        lab._ok(client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(["The lamp burned all night.",
                                                                                "Nobody asked why."])), "a.pdf")},
                            content_type="multipart/form-data"))
        from hermeneia.workspace import export_workspace_bundle
        export_workspace_bundle(db, template / "bundle", generated_at="2026-10-24T00:00:00+00:00")
        yield template


def _app(db: Path):
    return create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()


# ── The harness itself ──────────────────────────────────────────────────────

def test_the_harness_passes_where_the_build_already_refuses(study, tmp_path):
    """Every transaction start of a store open, guarded initialization included: each replay is refused unwritten."""
    assert _replay(tmp_path, study, "ws/hermeneia.db", lambda _root, db: SQLiteStore(db).close(),
                   skip=lambda: False) > 0


# ── W1-W5 ───────────────────────────────────────────────────────────────────

@RACE
def test_w1_a_request_write_connection_writes_nothing_after_a_newer_migration(study, tmp_path):
    conn = _connect(study / "ws" / "hermeneia.db")
    observations = [r[0] for r in conn.execute("SELECT id FROM observations")]
    conn.close()
    candidate = {"title": "T", "thesis": "T.", "sections": [{"claim": "C.", "supporting_observations": observations,
                                                             "supporting_interpretations": []}]}
    _replay(tmp_path, study, "ws/hermeneia.db",
            lambda _root, db: _app(db).post("/api/pipeline/ratify-blueprint", json={"candidate": candidate}))


@RACE
def test_w2_a_request_store_writes_nothing_after_a_newer_migration(study, tmp_path):
    pdf = lab._pdf(["A second page of evidence."])
    _replay(tmp_path, study, "ws/hermeneia.db", lambda _root, db: _app(db).post(
        "/api/upload", data={"file": (io.BytesIO(pdf), "b.pdf")}, content_type="multipart/form-data"))


@RACE
def test_w3_a_cli_raw_connection_writes_nothing_after_a_newer_migration(study, tmp_path):
    from hermeneia.cli import main as cli_main, profile_cmd

    def create_profile(_root, db):
        answers = iter(["witness-en", "Witness", "", "", "", "", "", "", "Write plainly.", ""])
        with mock.patch.object(sys, "argv", ["herm", "--db", str(db), "profile", "create"]), \
                mock.patch.object(profile_cmd.console, "input", lambda *_a, **_k: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()):
            cli_main.main()

    _replay(tmp_path, study, "ws/hermeneia.db", create_profile)


@RACE
def test_w4_restore_writes_nothing_after_a_newer_migration(study, tmp_path):
    from hermeneia.workspace.restore import restore_workspace
    _replay(tmp_path, study, "target/hermeneia.db", lambda root, db: restore_workspace(db, root / "bundle"))


def _setup_init(_root, db):
    _app(db).post("/api/setup/init")


def test_w5a_setup_init_changes_nothing_under_an_append_only_newer_schema(study, tmp_path):
    """Monotonic evolution: the older profile migration finds every table it creates and writes nothing."""
    _replay(tmp_path, study, "fresh/hermeneia.db", _setup_init)


@RACE
def test_w5b_setup_init_migrates_nothing_after_a_newer_migration(study, tmp_path):
    _replay(tmp_path, study, "fresh/hermeneia.db", _setup_init, shape="rename")
