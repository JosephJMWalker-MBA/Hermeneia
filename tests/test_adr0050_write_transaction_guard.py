"""ADR-0050: every write transaction re-checks the workspace schema. The guard, the writer inventory, slow work.

- The guard: every statement form that can write a workspace is refused, with ADR-0048's error, inside its own
  transaction and before its first write, once a newer build has migrated the workspace. Reads take no write lock,
  and a write around the guard is caught.
- The store's three transaction styles (`_commit()` writers, `atomic()`, `_own_transaction()`) are refused the same
  way. A guarded transaction's lock keeps the marker fixed until it commits.
- The inventory (V2): every connection in hermeneia/ that may write a workspace is connect_workspace(), and each one
  is pinned here with the test that exercises its category. A new writer, guarded or not, fails until it is
  reviewed and added.
- Slow work (decision 2): no write lock is held while a provider generates or a person answers a prompt.
"""
from __future__ import annotations

import ast
import contextlib
import importlib
import inspect
import io
from pathlib import Path
import shutil
import sqlite3
import sys
from unittest import mock

import pytest

import synthetic_study_lab as lab
import test_adr0048_post_open_write_races as witnesses
from hermeneia.storage.schema_guard import (GuardedConnection, NewerSchemaError, SchemaMarkerError,
                                            UnguardedWriteError, connect_workspace)
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
from test_adr0048_post_open_write_races import study  # noqa: F401  (a fixture)

ROOT = Path(__file__).resolve().parents[1]
_connect = sqlite3.connect


def _workspace(tmp_path: Path) -> Path:
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    return db


def _mark(db: Path, version: int) -> None:
    conn = _connect(db, timeout=0)
    conn.execute("UPDATE schema_version SET version = ?", (version,))
    conn.commit()
    conn.close()


def _terms(db: Path) -> int:
    conn = _connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
    finally:
        conn.close()


def _write_lock_free(db: Path) -> bool:
    probe = _connect(db, timeout=0)
    try:
        probe.execute("BEGIN IMMEDIATE")
        probe.rollback()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        probe.close()


def _row(n):
    return {"id": f"t{n}", "term": f"term {n}"}


# ── The guard: every statement form ─────────────────────────────────────────

WRITES = {
    "DML": lambda c: c.execute("INSERT INTO terms (id, term) VALUES ('a', 'a')"),
    "DDL": lambda c: c.execute("CREATE TABLE later_table (id TEXT)"),
    "executemany": lambda c: c.executemany("INSERT INTO terms (id, term) VALUES (?, ?)", [("b", "b")]),
    "cursor().execute": lambda c: c.cursor().execute("INSERT INTO terms (id, term) VALUES ('c', 'c')"),
    "executescript": lambda c: c.executescript("INSERT INTO terms (id, term) VALUES ('d', 'd'); CREATE TABLE s (x);"),
    "BEGIN IMMEDIATE": lambda c: c.execute("BEGIN IMMEDIATE"),
    "SAVEPOINT": lambda c: c.execute("SAVEPOINT outermost"),
}


@pytest.mark.parametrize("form", WRITES)
def test_every_write_form_is_refused_inside_its_transaction_with_nothing_written(tmp_path, form):
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    conn.execute("SELECT COUNT(*) FROM terms").fetchone()  # opened and read before the newer build migrates
    _mark(db, SCHEMA_VERSION + 1)
    cookie = _connect(db).execute("PRAGMA schema_version").fetchone()[0]
    with pytest.raises(NewerSchemaError, match=f"schema {SCHEMA_VERSION + 1} is newer"):
        WRITES[form](conn)
    assert not conn.in_transaction and _write_lock_free(db)  # rolled back: no lock is left held
    assert _terms(db) == 0 and _connect(db).execute("PRAGMA schema_version").fetchone()[0] == cookie
    conn.close()


def test_a_deferred_transaction_that_read_before_the_migration_is_refused_not_locked(tmp_path):
    """WAL mode refuses a stale snapshot's write as `database is locked`; the guard reports the refusal behind it."""
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    conn.execute("BEGIN")
    conn.execute("SELECT COUNT(*) FROM terms").fetchone()
    _mark(db, SCHEMA_VERSION + 1)
    with pytest.raises(NewerSchemaError) as refused:
        conn.execute("INSERT INTO terms (id, term) VALUES ('e', 'e')")
    assert isinstance(refused.value.__cause__, sqlite3.OperationalError)
    assert not conn.in_transaction and _terms(db) == 0
    conn.close()


@pytest.mark.parametrize("marker", ["ambiguous", "malformed"])
def test_a_marker_tampered_after_the_open_is_refused_at_the_next_write(tmp_path, marker):
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    raw = _connect(db, timeout=0)
    if marker == "ambiguous":
        raw.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, 't')", (SCHEMA_VERSION - 1,))
    else:
        raw.executescript("DROP TABLE schema_version; CREATE TABLE schema_version (version TEXT, applied_at TEXT);"
                          "INSERT INTO schema_version VALUES ('twenty-two', 't');")
    raw.commit()
    raw.close()
    with pytest.raises(SchemaMarkerError, match=marker):
        conn.execute("INSERT INTO terms (id, term) VALUES ('f', 'f')")
    assert _terms(db) == 0
    conn.close()


def test_reads_take_no_write_lock_and_writes_keep_their_commit_semantics(tmp_path):
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    conn.execute("SELECT COUNT(*) FROM terms").fetchall()
    assert not conn.in_transaction and _write_lock_free(db)
    conn.execute("CREATE TABLE IF NOT EXISTS extra (id TEXT)")
    assert not conn.in_transaction  # DDL commits at once, as before
    conn.execute("INSERT INTO terms (id, term) VALUES ('g', 'g')")
    assert conn.in_transaction and not _write_lock_free(db)  # DML leaves its transaction to the caller, as before
    conn.commit()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO no_such_table VALUES (1)")
    assert not conn.in_transaction and _write_lock_free(db)  # a failed statement leaves no transaction behind
    conn.close()
    assert _terms(db) == 1


@pytest.mark.parametrize("opener", ["BEGIN", "BEGIN IMMEDIATE", "SAVEPOINT s"])
def test_a_transaction_opened_around_the_guard_cannot_write(tmp_path, opener):
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    with conn:
        conn.execute("INSERT INTO terms (id, term) VALUES ('h', 'h')")  # a guarded transaction, then ended
    sqlite3.Cursor(conn).execute(opener)
    with pytest.raises(UnguardedWriteError):
        conn.execute("INSERT INTO terms (id, term) VALUES ('i', 'i')")
    conn.rollback()
    conn.close()
    assert _terms(db) == 1


# ── The store's transaction styles ──────────────────────────────────────────

STORE_WRITES = {
    "_commit() writer": lambda s: s.insert_terms_batch([_row(1)]),
    "atomic()": lambda s: s.atomic().__enter__(),
    "_own_transaction()": lambda s: s._own_transaction().__enter__(),
}


@pytest.mark.parametrize("style", STORE_WRITES)
def test_each_store_transaction_style_refuses_a_newer_migration_after_the_open(tmp_path, style):
    db = _workspace(tmp_path)
    store = SQLiteStore(db)
    assert isinstance(store._conn, GuardedConnection)
    _mark(db, SCHEMA_VERSION + 1)
    with pytest.raises(NewerSchemaError):
        STORE_WRITES[style](store)
    assert not store._conn.in_transaction and _terms(db) == 0
    store.close()


def test_a_guarded_transaction_holds_the_marker_until_it_commits(tmp_path):
    """Inside atomic() the lock is held, so a newer build cannot migrate between the check and the writes."""
    db = _workspace(tmp_path)
    store = SQLiteStore(db)
    with store.atomic():
        store.insert_terms_batch([_row(2)])
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            _mark(db, SCHEMA_VERSION + 1)
        store.insert_terms_batch([_row(3)])
    store.close()
    assert _terms(db) == 2


# ── The writer inventory (V2) ───────────────────────────────────────────────

# Every connection in hermeneia/ that may write a workspace, with the tests that exercise its category.
_CLI = ("test_w3_a_cli_raw_connection_refuses_a_newer_migration", "test_every_cli_connection_is_guarded")
WRITER_INVENTORY = {
    ("hermeneia/storage/sqlite.py", "SQLiteStore.__init__"): (
        "test_each_store_transaction_style_refuses_a_newer_migration_after_the_open",
        "test_w2_a_request_store_refuses_a_newer_migration",
        "test_w9_e10_generation_refuses_rather_than_reporting_a_partial_result"),
    ("hermeneia/web/app.py", "create_app"): (
        "test_a_newer_migration_after_the_startup_probe_is_refused_before_the_startup_migration",),
    ("hermeneia/web/app.py", "create_app._conn_rw"): (
        "test_w1_a_request_write_connection_refuses_a_newer_migration",
        "test_w7_the_artist_refuses_a_newer_migration_after_its_provider_call",
        "test_w8_the_critic_refuses_a_newer_migration_before_writing_findings"),
    ("hermeneia/web/app.py", "create_app.api_setup_init"): ("test_w5_setup_init_refuses_a_newer_migration",),
    ("hermeneia/workspace/lifecycle.py", "create_workspace"): ("test_w6_workspace_creation_refuses_a_newer_migration",),
    ("hermeneia/workspace/restore.py", "restore_workspace"): ("test_w4_restore_refuses_a_newer_migration",),
    ("hermeneia/workspace/restore.py", "preview_restore"): (  # it only reads; guarded regardless
        "test_every_write_form_is_refused_inside_its_transaction_with_nothing_written",),
    ("hermeneia/authoring/service.py", "_conn_rw"): ("test_w10_an_authoring_write_connection_refuses_a_newer_migration",),
    ("hermeneia/cli/explorer_cmd.py", "cmd_explorer_discover"): _CLI,
    **{(f"hermeneia/cli/{module}.py", "_open_db"): _CLI
       for module in ("architect_cmd", "artist_cmd", "blueprinter", "bootstrap_cmd", "comparer", "critic_cmd",
                      "extract_cmd", "health", "inspector", "interpreter", "profile_cmd", "theme_cmd")},
}
# The only raw sqlite3.connect() calls that are neither read-only nor in memory.
RAW_CONNECTIONS = {
    ("hermeneia/storage/schema_guard.py", "connect_workspace"): "the guarded factory itself",
    ("hermeneia/storage/schema_guard.py", "require_supported_schema"): "ADR-0048's probe, which only reads",
    ("hermeneia/storage/sqlite.py", "SQLiteStore.backup_to"):
        "the backup API copies pages into a fresh destination file; no SQL writes a workspace",
}


class _Calls(ast.NodeVisitor):
    def __init__(self):
        self.scopes, self.calls = [], []

    def _scope(self, node):
        self.scopes.append(node)
        self.generic_visit(node)
        self.scopes.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def visit_Call(self, node):
        self.calls.append((list(self.scopes), node))
        self.generic_visit(node)


def _sites():
    for path in sorted((ROOT / "hermeneia").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        visitor = _Calls()
        visitor.visit(ast.parse(source))
        for scopes, call in visitor.calls:
            yield str(path.relative_to(ROOT)), scopes, call, source


def _read_only(scopes, call, source) -> bool:
    """An in-memory database, or a ``mode=ro`` URI opened with uri=True (the URI may be built just before)."""
    if not call.args:
        return False
    target = call.args[0]
    if isinstance(target, ast.Constant) and target.value == ":memory:":
        return True
    text = ast.get_source_segment(source, target) or ""
    if isinstance(target, ast.Name) and scopes:
        text += "".join(ast.get_source_segment(source, node.value) or "" for node in ast.walk(scopes[-1])
                        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == target.id
                                                                for t in node.targets))
    uri = any(k.arg == "uri" and isinstance(k.value, ast.Constant) and k.value.value is True for k in call.keywords)
    return "mode=ro" in text and uri


def _named(call, *names) -> bool:
    func = call.func
    return (isinstance(func, ast.Attribute) and func.attr in names) or (isinstance(func, ast.Name) and func.id in names)


def test_every_workspace_writer_is_guarded_and_inventoried():
    writers, raw, bypasses = set(), set(), []
    for path, scopes, call, source in _sites():
        where = (path, ".".join(scope.name for scope in scopes))
        func = call.func
        sqlite3_attr = isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "sqlite3"
        if _named(call, "connect_workspace"):
            writers.add(where)
        elif sqlite3_attr and func.attr == "connect" and not _read_only(scopes, call, source):
            raw.add(where)
        elif sqlite3_attr and func.attr in ("Connection", "Cursor") and path != "hermeneia/storage/schema_guard.py":
            bypasses.append((where, func.attr))
        elif _named(call, "cursor") and (call.args or call.keywords) and path != "hermeneia/storage/schema_guard.py":
            bypasses.append((where, "cursor(factory)"))
    assert writers == set(WRITER_INVENTORY), "a workspace writer was added or removed; review and inventory it"
    assert raw == set(RAW_CONNECTIONS), "a raw connection that may write a workspace must use connect_workspace()"
    assert not bypasses, f"connections or cursors built around the guard: {bypasses}"
    for source in sorted((ROOT / "hermeneia").rglob("*.py")):
        assert "from sqlite3 import connect" not in source.read_text(encoding="utf-8"), source


def test_every_inventoried_category_names_tests_that_exist():
    import test_newer_schema_refusal_boundaries as boundaries
    names = {name for module in (witnesses, boundaries, sys.modules[__name__]) for name in dir(module)}
    missing = {(where, test) for where, tests in WRITER_INVENTORY.items() for test in tests if test not in names}
    assert not missing


@pytest.mark.parametrize("module", ["architect_cmd", "artist_cmd", "blueprinter", "bootstrap_cmd", "comparer",
                                    "critic_cmd", "extract_cmd", "health", "inspector", "interpreter",
                                    "profile_cmd", "theme_cmd"])
def test_every_cli_connection_is_guarded(tmp_path, module):
    db = _workspace(tmp_path)
    open_db = importlib.import_module(f"hermeneia.cli.{module}")._open_db
    opened = open_db(str(db)) if "bundle_or_db" in inspect.signature(open_db).parameters else open_db(db)
    conn = opened[1] if isinstance(opened, tuple) else opened
    assert isinstance(conn, GuardedConnection)
    _mark(db, SCHEMA_VERSION + 1)
    with pytest.raises(NewerSchemaError):
        conn.execute("INSERT INTO terms (id, term) VALUES ('cli', 'cli')")
    conn.close()
    assert _terms(db) == 0


@pytest.mark.parametrize("ending", ["returns", "exits"])
def test_the_cli_reports_a_refusal_a_command_caught_as_its_governed_exit(tmp_path, monkeypatch, ending):
    """A command that swallows the refusal still ends as DatabaseTargetError carrying it (V1)."""
    from hermeneia.cli import main as cli_main
    from hermeneia.cli.target import DatabaseTargetError
    db = _workspace(tmp_path)

    def command():
        conn = connect_workspace(db)
        _mark(db, SCHEMA_VERSION + 1)
        try:
            conn.execute("INSERT INTO terms (id, term) VALUES ('swallowed', 'swallowed')")
        except Exception:  # noqa: BLE001 - the swallowing command under test
            pass
        finally:
            conn.close()
        if ending == "exits":
            sys.exit(1)

    monkeypatch.setattr(cli_main, "_main", command)
    with pytest.raises(DatabaseTargetError, match=f"schema {SCHEMA_VERSION + 1} is newer"):
        cli_main.main()
    assert _terms(db) == 0


# ── Decision 2: slow work holds no write lock ──────────────────────────────

def test_no_write_lock_is_held_while_a_provider_generates_or_a_person_answers(study, tmp_path, monkeypatch):
    template, made = study
    root = tmp_path / "work"
    shutil.copytree(template, root)
    db = root / "ws" / "hermeneia.db"
    seen = []

    def watched(name, run=None):
        def call(*args, **kwargs):
            seen.append((name, _write_lock_free(db)))
            return run(*args, **kwargs) if run else None
        return call

    from hermeneia.narrative.artist_providers import NullArtistProvider
    import hermeneia.web.app as webapp
    from test_e10_vertical_slice_api import _cloud_catalog_registry, _reset_catalog_provider
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-openai")
    _reset_catalog_provider()
    monkeypatch.setattr(NullArtistProvider, "render", watched("Artist provider", NullArtistProvider.render))
    monkeypatch.setattr(webapp, "generate_candidate_interpretation",
                        watched("Explorer provider", lambda *_a, **_k: ("A candidate.", "prompt")))
    client = witnesses._app(db)
    lab._ok(client.post("/api/pipeline/run-artist", json={"plan_id": made["plan"], "provider": "null",
                                                           "profile": made["other_profile"]}))
    observation = _connect(db).execute("SELECT id FROM observations").fetchone()[0]
    e10 = webapp.create_app(db_path=db, provider_registry=_cloud_catalog_registry()).test_client()
    lab._ok(e10.post("/api/e10/interpretations/generate", json={"observation_id": observation, "participants": ["gpt"]}))

    from hermeneia.cli import main as cli_main, profile_cmd
    answers = iter(["slow-work-en", "Slow work", "", "", "", "", "", "", "Write plainly.", ""])
    with mock.patch.object(sys, "argv", ["herm", "--db", str(db), "profile", "create"]), \
            mock.patch.object(profile_cmd.console, "input", watched("CLI prompt", lambda *_a, **_k: next(answers))), \
            contextlib.redirect_stdout(io.StringIO()):
        cli_main.main()

    assert {name for name, _ in seen} == {"Artist provider", "Explorer provider", "CLI prompt"}, seen
    assert all(free for _, free in seen), seen
