"""ADR-0048 post-open write races, guarded by ADR-0050: the witnesses of
docs/verification/2026-10-24-adr0048-post-open-write-races.md, now acceptance tests under ADR-0050's stipulations.

A newer build may commit its migration at any moment this build holds no transaction on the workspace. Each witness
runs one operation and finds every point where a workspace connection is about to start a transaction. It then
replays the operation once per point, with a newer migration committed exactly there.

At every point (V2: every point, no sampling) it asserts all of the following (V1):
- the newer migration really committed at that seam;
- this build wrote nothing after it, whether DML, DDL or a canonical record;
- the operation ended in the governed ADR-0048 refusal for that newer schema: NewerSchemaError raised by the library,
  the CLI's DatabaseTargetError carrying it, or the HTTP 503 refusal body.

An unrelated error, a generic 500, a lock error or a suppressed refusal fails the witness. So does an operation that
never reaches a workspace transaction.

The store's own initialization is left out here; test_newer_schema_refusal_boundaries.py pins its every point.
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
from hermeneia.cli.target import DatabaseTargetError
from hermeneia.storage.schema_guard import NewerSchemaError, SchemaMarkerError, _keyword
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
from hermeneia.web.app import create_app

_connect = sqlite3.connect
_TRANSACTION_STARTS = {"BEGIN", "SAVEPOINT", "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"}
NEWER = SCHEMA_VERSION + 1
REFUSAL = f"workspace schema {NEWER} is newer than this build supports"


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
        conn.execute("UPDATE schema_version SET version = ?", (NEWER,))
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


def _outcome(operate, root, db):
    try:
        return "returned", operate(root, db)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - every outcome is inspected, none is suppressed
        return "raised", exc


def _governed_refusal(outcome) -> bool:
    """The operation ended in ADR-0048's refusal of exactly this newer schema, at its own boundary."""
    kind, value = outcome
    if kind == "raised":
        return isinstance(value, (SchemaMarkerError, DatabaseTargetError)) and REFUSAL in str(value)
    status, body = getattr(value, "status_code", None), (value.get_json(silent=True) if hasattr(value, "get_json") else None)
    return (status == 503 and isinstance(body, dict) and body.get("refusal") == "workspace_schema"
            and body.get("error_type") == "NewerSchemaError" and REFUSAL in body.get("error", ""))


def _replay(tmp_path: Path, template: Path, database: str, operate, *, shape: str = "append",
            skip=_in_store_initialization) -> int:
    """Replay ``operate`` on fresh copies of ``template`` with a newer migration before each transaction start.

    Returns how many points were checked. Raises SeamNotReached when there were none.
    """
    def run(point):
        root = tmp_path / f"replay-{point}"
        shutil.copytree(template, root)
        db, observed = root / database, []
        with _newer_migration_at(db, point, shape, skip, observed) as seen:
            outcome = _outcome(operate, root, db)
        return seen[0], observed, db, outcome

    points, _, _, dry = run(None)
    if dry[0] == "raised" or getattr(dry[1], "status_code", 200) >= 400:
        raise SeamNotReached(f"the operation fails even without a newer migration: {dry}")
    checked = 0
    for point in range(points):
        _, observed, db, outcome = run(point)
        if observed == [None]:
            continue
        if len(observed) != 1 or isinstance(observed[0], tuple) and observed[0][0] == "error":
            raise SeamNotReached(f"the newer migration was not committed at point {point}: {observed}")
        checked += 1
        assert observed[0][1] == [NEWER], f"point {point}: the newer migration did not commit"
        assert _state(db) == observed[0], f"point {point}: written after a newer migration committed"
        assert _governed_refusal(outcome), f"point {point}: not the governed refusal: {outcome}"
    if not checked:
        raise SeamNotReached("the operation started no transaction on the workspace after its initialization")
    return checked


def _app(db: Path, **kwargs):
    return create_app(db_path=db, credential_store=lab._NoCredentials(), **kwargs).test_client()


@pytest.fixture
def study(tmp_path):
    """A closed real workspace (one uploaded PDF, two Observations), its Architect plan and a null-provider narrative,
    and a WBS bundle of it before the plan, under ``template``."""
    with lab.isolated(tmp_path):
        template = tmp_path / "template"
        db = template / "ws" / "hermeneia.db"
        SQLiteStore(db).close()
        client = _app(db)
        lab._ok(client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(["The lamp burned all night.",
                                                                                "Nobody asked why."])), "a.pdf")},
                            content_type="multipart/form-data"))
        from hermeneia.workspace import export_workspace_bundle
        export_workspace_bundle(db, template / "bundle", generated_at="2026-10-24T00:00:00+00:00")
        conn = _connect(db)
        observations = [r[0] for r in conn.execute("SELECT id FROM observations")]
        conn.close()
        candidate = {"title": "T", "thesis": "T.", "sections": [{"claim": "C.", "supporting_observations": observations,
                                                                 "supporting_interpretations": []}]}
        plan = lab._ok(client.post("/api/pipeline/ratify-blueprint", json={"candidate": candidate}))["plan_id"]
        profile, other_profile = [p["slug"] for p in client.get("/api/profiles").get_json()["profiles"][:2]]
        narrative = lab._ok(client.post("/api/pipeline/run-artist",
                                        json={"plan_id": plan, "provider": "null", "profile": profile}))["id"]
        yield template, {"candidate": {**candidate, "title": "T2"}, "plan": plan, "other_profile": other_profile,
                         "narrative": narrative}


# ── The harness itself ──────────────────────────────────────────────────────

def test_the_harness_passes_where_the_build_already_refuses(study, tmp_path):
    """Every transaction start of a store open, guarded initialization included: each replay is refused unwritten."""
    template, _ = study
    def open_store(_root, db):
        SQLiteStore(db).close()
    assert _replay(tmp_path, template, "ws/hermeneia.db", open_store, skip=lambda: False) > 0


def test_the_harness_rejects_an_operation_that_is_not_refused(study, tmp_path):
    """A write on a raw connection is not guarded; the harness must catch it rather than pass it."""
    template, _ = study
    def raw_write(_root, db):
        conn = sqlite3.connect(db)  # the module's connect, so the harness sees it; deliberately not guarded
        conn.execute("INSERT INTO terms (id, term) VALUES ('unguarded', 'unguarded')")
        conn.commit()
        conn.close()
    with pytest.raises(AssertionError, match="written after a newer migration"):
        _replay(tmp_path, template, "ws/hermeneia.db", raw_write)


# ── Witnesses: every writer category, every transaction start ───────────────

def test_w1_a_request_write_connection_refuses_a_newer_migration(study, tmp_path):
    template, made = study
    _replay(tmp_path, template, "ws/hermeneia.db",
            lambda _root, db: _app(db).post("/api/pipeline/ratify-blueprint", json={"candidate": made["candidate"]}))


def test_w2_a_request_store_refuses_a_newer_migration(study, tmp_path):
    template, _ = study
    pdf = lab._pdf(["A second page of evidence."])
    _replay(tmp_path, template, "ws/hermeneia.db", lambda _root, db: _app(db).post(
        "/api/upload", data={"file": (io.BytesIO(pdf), "b.pdf")}, content_type="multipart/form-data"))


def test_w3_a_cli_raw_connection_refuses_a_newer_migration(study, tmp_path):
    template, _ = study
    from hermeneia.cli import main as cli_main, profile_cmd

    def create_profile(_root, db):
        answers = iter(["witness-en", "Witness", "", "", "", "", "", "", "Write plainly.", ""])
        with mock.patch.object(sys, "argv", ["herm", "--db", str(db), "profile", "create"]), \
                mock.patch.object(profile_cmd.console, "input", lambda *_a, **_k: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()):
            cli_main.main()

    _replay(tmp_path, template, "ws/hermeneia.db", create_profile)


def test_w4_restore_refuses_a_newer_migration(study, tmp_path):
    template, _ = study
    from hermeneia.workspace.restore import restore_workspace
    _replay(tmp_path, template, "target/hermeneia.db", lambda root, db: restore_workspace(db, root / "bundle"))


@pytest.mark.parametrize("shape", ["append", "rename"])
def test_w5_setup_init_refuses_a_newer_migration(study, tmp_path, shape):
    template, _ = study
    _replay(tmp_path, template, "fresh/hermeneia.db", lambda _root, db: _app(db).post("/api/setup/init"), shape=shape)


def test_w6_workspace_creation_refuses_a_newer_migration(study, tmp_path):
    template, _ = study
    from hermeneia.workspace.lifecycle import create_workspace
    _replay(tmp_path, template, "managed/witness/hermeneia.db",
            lambda root, _db: create_workspace("Witness", workspace_root=root / "managed"))


def test_w7_the_artist_refuses_a_newer_migration_after_its_provider_call(study, tmp_path):
    """The route catches every exception into its own 500. The refusal it caught is still the response (ADR-0050)."""
    template, made = study
    _replay(tmp_path, template, "ws/hermeneia.db", lambda _root, db: _app(db).post(
        "/api/pipeline/run-artist", json={"plan_id": made["plan"], "provider": "null",
                                          "profile": made["other_profile"]}))


def test_w8_the_critic_refuses_a_newer_migration_before_writing_findings(study, tmp_path):
    template, made = study
    _replay(tmp_path, template, "ws/hermeneia.db", lambda _root, db: _app(db).post(
        "/api/pipeline/run-critic", json={"narrative_id": made["narrative"]}))


def test_w9_e10_generation_refuses_rather_than_reporting_a_partial_result(tmp_path, monkeypatch):
    """The E10 route reports a participant's staging failure as a partial result (#272). A refusal is no such
    failure: it ends the request as the governed 503, and no earlier proposal is reported as a success."""
    import hermeneia.web.app as webapp
    from test_constitutional_p0 import _seed_full_chain
    from test_e10_vertical_slice_api import _cloud_catalog_registry, _reset_catalog_provider
    monkeypatch.setenv("HERMENEIA_CONNECTIONS_SETTINGS_PATH", str(tmp_path / "connections.json"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-anthropic")
    monkeypatch.setattr(webapp, "generate_candidate_interpretation",
                        lambda *_a, **_k: ("An independent candidate.", "frozen synthetic prompt"))
    _reset_catalog_provider()
    template = tmp_path / "template"
    store = SQLiteStore(template / "workspace.db")
    ids = _seed_full_chain(store)
    store.close()
    body = {"observation_id": ids["obs_id"], "participants": ["gpt", "claude"]}
    _replay(tmp_path, template, "workspace.db", lambda _root, db: create_app(
        db_path=db, provider_registry=_cloud_catalog_registry()).test_client().post(
            "/api/e10/interpretations/generate", json=body))


def test_w10_an_authoring_write_connection_refuses_a_newer_migration(study, tmp_path):
    template, _ = study
    from hermeneia.authoring import service

    def write(_root, db):
        conn = service._conn_rw(db)
        try:
            conn.execute("INSERT INTO terms (id, term) VALUES ('authoring-witness', 'authoring witness')")
            conn.commit()
        finally:
            conn.close()

    _replay(tmp_path, template, "ws/hermeneia.db", write)
