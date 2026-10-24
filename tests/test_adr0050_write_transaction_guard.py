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
- Review of #273: a refusal partway through an E10 request still discloses the proposals it committed (#272);
  read-only recursive CTEs take no write lock while writable ones stay guarded; no PRAGMA can change a newer
  workspace, with the one recorded journal-mode exception pinned.
"""
from __future__ import annotations

import ast
import contextlib
import importlib
import inspect
import io
from pathlib import Path
import re
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
from hermeneia.web.app import create_app
from test_adr0048_post_open_write_races import study  # noqa: F401  (a fixture)
from test_e10_partial_proposal_disclosure import _rows, _seed_discovery, setup  # noqa: F401  (setup is a fixture)

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
    "writable CTE": lambda c: c.execute("WITH t(id, term) AS (VALUES ('j', 'j')) INSERT INTO terms SELECT id, term FROM t"),
    "stored PRAGMA": lambda c: c.execute("PRAGMA user_version = 7"),
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


# ── Review: partial-commit truthfulness under a refusal (#272) ──────────────

@contextlib.contextmanager
def _holding_write_lock(db: Path):
    holder = _connect(db)
    holder.execute("BEGIN IMMEDIATE")
    try:
        yield
    finally:
        holder.rollback()
        holder.close()


@pytest.mark.parametrize("case", ["generate", "discover"])
def test_an_e10_refusal_between_participants_discloses_what_it_committed(case, setup, tmp_path):
    """P1's proposal commits, a newer build migrates while P2 generates, and P2's staging is refused.

    The governed 503 names P1's proposal, as #272 requires of any partial result. Nothing after the migration is
    written, and no later participant is generated.
    """
    import hermeneia.web.app as webapp
    from test_e10_vertical_slice_api import _cloud_catalog_registry
    db, ids, monkeypatch = setup
    if case == "discover":
        db, ids = _seed_discovery(db, ids, tmp_path / "discover")
    calls, after_newer = [], []

    def generate(*_args, **_kwargs):
        calls.append(1)
        if len(calls) == 2:
            witnesses._migrate_as_newer_build(db, "append")
            after_newer.append(witnesses._state(db))
        return f"Independent candidate {len(calls)}.", "frozen synthetic prompt"

    if case == "generate":
        url, body = "/api/e10/interpretations/generate", {"observation_id": ids["obs_id"], "participants": ["gpt", "claude"]}
        monkeypatch.setattr(webapp, "generate_candidate_interpretation", generate)
    else:
        url, body = "/api/e10/interpretations/discover", {"observation_ids": [ids["obs_id"], ids["obs2_id"]],
                                                          "participants": ["gpt", "claude"]}
        monkeypatch.setattr(webapp, "generate_candidate_buckets", lambda observations, provider: [[o["id"] for o in observations]])
        monkeypatch.setattr(webapp, "generate_interpretation_from_bucket", generate)
    client = create_app(db_path=db, provider_registry=_cloud_catalog_registry()).test_client()
    response = client.post(url, json=body)
    refusal = response.get_json()

    assert response.status_code == 503, refusal
    assert refusal["refusal"] == "workspace_schema" and refusal["error_type"] == "NewerSchemaError"
    assert witnesses.REFUSAL in refusal["error"]
    committed = [row["id"] for row in _rows(db, "proposed_interpretations")]
    assert len(committed) == 1 and refusal["proposal_ids"] == committed
    assert refusal["created_count"] == 1 and refusal["partial"] is True and refusal["failures"] == []
    assert len(calls) == 2  # no participant after the refusal was generated
    assert witnesses._state(db) == after_newer[0]  # nothing written after the newer migration

    again = client.post(url, json=body)
    assert again.status_code == 503 and witnesses._state(db) == after_newer[0]


def test_a_refusal_a_route_caught_keeps_the_route_report(tmp_path):
    """The HTTP hook replaces a route's response with the refusal, keeping what the route reported."""
    from flask import jsonify
    db = _workspace(tmp_path)
    app = create_app(db_path=db, credential_store=lab._NoCredentials())

    def swallowing():
        conn = connect_workspace(db)
        _mark(db, SCHEMA_VERSION + 1)
        try:
            conn.execute("INSERT INTO terms (id, term) VALUES ('k', 'k')")
        except Exception:  # noqa: BLE001 - the swallowing route under test
            pass
        finally:
            conn.close()
        return jsonify({"created_count": 1, "proposals": ["committed-before"]}), 201

    app.add_url_rule("/_test/swallowing", view_func=swallowing, methods=["POST"])
    response = app.test_client().post("/_test/swallowing")
    body = response.get_json()
    assert response.status_code == 503 and body["refusal"] == "workspace_schema"
    assert body["route_response"] == {"status": 201, "body": {"created_count": 1, "proposals": ["committed-before"]}}
    assert _terms(db) == 0


# ── Review: read-only recursive queries take no write lock ─────────────────

def _with_statements():
    """Every SQL string literal in hermeneia/ that is a WITH statement."""
    for path in sorted((ROOT / "hermeneia").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and node.value.lstrip().upper().startswith("WITH "):
                yield f"{path.relative_to(ROOT)}:{node.lineno}", node.value


def test_every_recursive_query_in_hermeneia_reads_without_the_write_lock(tmp_path):
    """Run on a guarded connection while another holds the write lock: one that tried to take it would fail."""
    statements = dict(_with_statements())
    assert sorted(path.split(":")[0] for path in statements) == [
        "hermeneia/storage/sqlite.py", "hermeneia/storage/sqlite.py",  # _perspective_path_exists, supersession_descendants
        "hermeneia/web/app.py",                                        # _blueprint_path_exists
        "hermeneia/workspace/restore.py"]                              # _perspective_path_exists
    db = _workspace(tmp_path)
    conn = connect_workspace(db, timeout=0)
    with _holding_write_lock(db):
        for where, sql in statements.items():
            conn.execute(sql, ("x",) * sql.count("?")).fetchall()
            assert not conn.in_transaction, where
    conn.close()


def test_the_recursive_store_and_restore_methods_take_no_write_lock(tmp_path):
    from hermeneia.workspace.restore import _perspective_path_exists
    db = _workspace(tmp_path)
    store = SQLiteStore(db)
    store._conn.execute("PRAGMA busy_timeout = 0")
    conn = connect_workspace(db, timeout=0)
    with _holding_write_lock(db):
        assert store._perspective_path_exists("a", "b") is False
        assert store.supersession_descendants("a") == []
        assert _perspective_path_exists(conn, "a", "b") is False
    assert not store._conn.in_transaction and not conn.in_transaction
    store.close()
    conn.close()


def test_a_writable_cte_is_still_a_guarded_write(tmp_path):
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    conn.execute("WITH t(id, term) AS (VALUES ('w', 'w')) INSERT INTO terms SELECT id, term FROM t")
    assert not conn.in_transaction and _terms(db) == 1  # committed at once, as before
    with _holding_write_lock(db):
        locked = connect_workspace(db, timeout=0)
        with pytest.raises(sqlite3.OperationalError, match="locked"):  # it needs the write lock, so it waits for it
            locked.execute("WITH t(id, term) AS (VALUES ('x', 'x')) INSERT INTO terms SELECT id, term FROM t")
        locked.close()
    conn.close()


# ── Review: no PRAGMA can change a newer workspace ──────────────────────────

def _stored_values(db: Path) -> tuple:
    conn = _connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return tuple(conn.execute(f"PRAGMA {name}").fetchone()[0] for name in (
            "user_version", "application_id", "schema_version", "journal_mode", "page_size", "auto_vacuum"))
    finally:
        conn.close()


MUTATING_PRAGMAS = ["user_version = 7", "user_version(7)", "main.application_id = 7", "schema_version = 999",
                    "page_size = 8192", "auto_vacuum = FULL", "incremental_vacuum", "optimize", "wal_checkpoint(TRUNCATE)",
                    "journal_mode = DELETE", "journal_mode = WAL", "writable_schema = ON"]


@pytest.mark.parametrize("pragma", MUTATING_PRAGMAS)
def test_no_pragma_can_change_a_newer_workspace(tmp_path, pragma):
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    _mark(db, SCHEMA_VERSION + 1)
    before = _stored_values(db)
    with pytest.raises(NewerSchemaError):
        conn.execute(f"PRAGMA {pragma}")
    assert not conn.in_transaction
    conn.close()
    assert _stored_values(db) == before


@pytest.mark.parametrize("pragma", ["user_version", "application_id", "schema_version", "journal_mode", "page_size",
                                    "table_info(terms)", "foreign_key_check", "database_list", "foreign_keys = ON",
                                    "query_only = OFF", "busy_timeout = 0"])
def test_reading_and_setting_pragmas_take_no_write_lock(tmp_path, pragma):
    db = _workspace(tmp_path)
    conn = connect_workspace(db, timeout=0)
    with _holding_write_lock(db):
        conn.execute(f"PRAGMA {pragma}").fetchall()
        assert not conn.in_transaction
    conn.close()


def test_a_stored_pragma_still_sets_a_supported_workspace(tmp_path):
    db = _workspace(tmp_path)
    conn = connect_workspace(db)
    conn.execute("PRAGMA user_version = 7")
    assert not conn.in_transaction  # committed at once, as before
    conn.close()
    assert _stored_values(db)[0] == 7


def test_the_journal_mode_exception_writes_nothing_to_a_newer_wal_workspace(tmp_path):
    """The recorded exception: the journal-mode check runs without the write lock, because SQLite cannot change the
    mode inside a transaction. A newer build that migrated in that gap finds a WAL workspace, and setting WAL on it
    writes nothing, as an unguarded connection shows here."""
    db = _workspace(tmp_path)
    _mark(db, SCHEMA_VERSION + 1)
    before = (db.read_bytes(), sorted(p.name for p in db.parent.iterdir()))
    raw = _connect(db)
    assert raw.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    raw.close()
    assert (db.read_bytes(), sorted(p.name for p in db.parent.iterdir())) == before


def _pragma_statements():
    """Every PRAGMA statement in hermeneia/'s SQL: execute() arguments and *DDL script constants."""
    pragma = re.compile(r"PRAGMA\s+[\w.]+\s*(?:=\s*\w+|\([^)]*\))?", re.I)
    for path in sorted((ROOT / "hermeneia").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            texts = []
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in ("execute", "executemany", "executescript") \
                    and node.args:
                texts.append(ast.get_source_segment(source, node.args[0]) or "")
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.endswith("DDL") for t in node.targets):
                texts.append(ast.get_source_segment(source, node.value) or "")
            for text in texts:
                for match in pragma.finditer(text):
                    yield str(path.relative_to(ROOT)), re.sub(r"\s+", "", match.group(0)).replace("PRAGMA", "PRAGMA ")


def test_every_pragma_hermeneia_issues_reads_or_is_the_recorded_exception():
    from hermeneia.storage.schema_guard import _pragma_kind
    found = set(_pragma_statements())
    assert found, "the scan found no PRAGMA statements"
    unguarded = {(path, sql) for path, sql in found if _pragma_kind(sql) != "read"}
    assert unguarded == {("hermeneia/storage/sqlite.py", "PRAGMA journal_mode=WAL")}, unguarded
