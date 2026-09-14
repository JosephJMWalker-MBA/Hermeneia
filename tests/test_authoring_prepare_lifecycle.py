"""
Lifecycle of long-running Authoring preparation under the supervised runtime.

Regression for the live failure after #207: the supervisor proxies every
request with a 60-second window, while preparing a real book takes minutes.
On the old synchronous route the proxy timeout only abandoned the response:
the child kept preparing and could attach a work after the caller saw 502, a
retry started a second racing preparation (IntegrityError, orphaned
publication directory), and a drain SIGTERMed the child without cleanup or any
recorded outcome.

Preparation is now a single-flight, workspace-owned operation: POST returns
202 immediately, status is polled, a switch is refused while it runs, and an
interrupted child records ``interrupted`` and leaves no staging behind.

A stand-in "Compositor" executable that simply sleeps makes preparation last
longer than the proxy window without needing the real Compositor; the real
success path runs when a Compositor environment is configured.

HISTORY IS IMMUTABLE; THE CURRENT WORK IS REVISABLE.
"""
from __future__ import annotations

import http.client
import json
import os
import shutil
import sqlite3
import subprocess
import textwrap
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from hermeneia.authoring import preparation_job, service, store
from hermeneia.authoring.service import CompositorConfig
from hermeneia.web.app import create_app
from hermeneia.web.supervisor import RuntimeTarget, WorkspaceRuntimeSupervisor, create_supervisor_app
from hermeneia.workspace import create_workspace

REAL = CompositorConfig.from_env()


def _make_pdf(path: Path, text: str) -> None:
    import fitz  # PyMuPDF, already a Hermeneia dependency

    doc = fitz.open()
    page = doc.new_page(width=432, height=648)
    page.insert_text((60, 100), text, fontsize=11)
    doc.save(path)
    doc.close()


def _ingest(ws_dir: Path, pdf: Path, name: str = "primary_upload.pdf") -> Path:
    from hermeneia.compiler.compiler import Compiler

    (ws_dir / "uploads").mkdir(parents=True, exist_ok=True)
    upload = ws_dir / "uploads" / name
    shutil.copyfile(pdf, upload)
    compiler = Compiler(db_path=ws_dir / "hermeneia.db", build_dir=ws_dir)
    compiler.compile(upload)
    compiler.close()
    return ws_dir / "hermeneia.db"


def _slow_compositor(tmp_path: Path, seconds: float) -> dict[str, str]:
    """An executable standing in for the Compositor Python: it only sleeps.

    It records its pid so tests can prove it was terminated.
    """
    script = tmp_path / "slow-compositor"
    script.write_text(textwrap.dedent(f"""\
        #!/bin/sh
        echo $$ >> "{tmp_path / 'runner-pids'}"
        sleep {seconds}
        exit 3
    """))
    script.chmod(0o755)
    profile = tmp_path / "profile.json"
    profile.write_text("{}")
    fonts = tmp_path / "fonts"
    fonts.mkdir(exist_ok=True)
    return {
        "HERMENEIA_COMPOSITOR_PYTHON": str(script),
        "HERMENEIA_COMPOSITOR_PROFILE": str(profile),
        "HERMENEIA_COMPOSITOR_FONTS": str(fonts),
    }


def _config_from(env: dict[str, str]) -> CompositorConfig:
    return CompositorConfig(python=env["HERMENEIA_COMPOSITOR_PYTHON"], pythonpath=None, typst=None,
                            profile=env["HERMENEIA_COMPOSITOR_PROFILE"], fonts=env["HERMENEIA_COMPOSITOR_FONTS"])


def _runner_pids(tmp_path: Path) -> list[int]:
    path = tmp_path / "runner-pids"
    return [int(line) for line in path.read_text().split()] if path.exists() else []


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _leftovers(ws_dir: Path) -> list[str]:
    names = [n for n in os.listdir(ws_dir) if n.startswith(".publication-prepare-")]
    publication = ws_dir / "publication"
    if publication.is_dir():
        names += [f"publication/{n}" for n in os.listdir(publication)]
    return sorted(names)


def _work_rows(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM publication_works").fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _wait_until(predicate, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition did not become true")


def _json(port: int, method: str, path: str, payload: dict | None = None, timeout: float = 10) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers={"Content-Type": "application/json"} if body else {})
        response = conn.getresponse()
        return response.status, json.loads(response.read() or b"{}")
    finally:
        conn.close()


class _Public:
    def __init__(self, app) -> None:
        self.server = make_server("127.0.0.1", 0, app, threaded=True)
        self.port = int(self.server.socket.getsockname()[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()


# ── In-process lifecycle (no supervisor) ────────────────────────────────────


@pytest.fixture()
def prepared_workspace(tmp_path) -> tuple[Path, CompositorConfig]:
    ws = tmp_path / "ws"
    pdf = tmp_path / "source.pdf"
    _make_pdf(pdf, "The lamp glows.")
    db = _ingest(ws, pdf)
    return db, _config_from(_slow_compositor(tmp_path, 2.0))


def test_start_returns_immediately_and_retry_identifies_the_same_operation(prepared_workspace, tmp_path):
    db, config = prepared_workspace
    started = time.monotonic()
    first, code = preparation_job.start(db, document_id=None, actor="author", config=config)
    assert code == 202 and first["state"] == "running"
    assert time.monotonic() - started < 1.0, "start must not wait for Compositor"

    again, code = preparation_job.start(db, document_id=None, actor="author", config=config)
    assert code == 202 and again["already_running"] is True
    assert again["operation_id"] == first["operation_id"], "a retry identifies, never duplicates"
    _wait_until(lambda: len(_runner_pids(tmp_path)) >= 1)
    time.sleep(0.3)
    assert len(_runner_pids(tmp_path)) == 1, "exactly one preparation owns the workspace"
    assert preparation_job.active_operations(db)[0]["operation_id"] == first["operation_id"]

    final = preparation_job.wait(db, timeout=15)
    assert final["state"] == "failed" and final["code"] == "COMPOSITOR_PROCESS_FAILED"
    assert final["operation_id"] == first["operation_id"]
    assert _work_rows(db) == 0 and _leftovers(db.parent) == []
    assert not (db.parent / preparation_job.LEASE_NAME).exists()
    assert preparation_job.active_operations(db) == []


def test_status_route_is_read_only_and_prepare_route_returns_202(prepared_workspace):
    db, config = prepared_workspace
    app = create_app(db_path=db)
    app.config["HERMENEIA_COMPOSITOR_CONFIG"] = config
    client = app.test_client()
    assert client.get("/api/authoring/prepare/status").get_json() == {"state": "idle"}
    before = db.read_bytes()
    response = client.post("/api/authoring/prepare", json={})
    assert response.status_code == 202 and response.get_json()["state"] == "running"
    assert client.get("/api/runtime/operations").get_json()["long_running"][0]["kind"] == "authoring_preparation"
    assert client.get("/api/authoring/prepare/status").get_json()["state"] == "running"
    blocked = client.post("/api/authoring/work/attach", json={"source_dir": str(db.parent)})
    assert blocked.status_code == 409 and blocked.get_json()["code"] == "PREPARATION_IN_PROGRESS"
    preparation_job.wait(db, timeout=15)
    assert db.read_bytes() == before, "a failed preparation writes no authoring state"
    unattached = client.get("/api/authoring/work").get_json()
    assert unattached["preparation"]["operation"]["state"] == "failed"


def test_quick_refusals_stay_synchronous_and_take_no_lease(prepared_workspace):
    db, config = prepared_workspace
    unconfigured = replace(config, profile=None)
    app = create_app(db_path=db)
    app.config["HERMENEIA_COMPOSITOR_CONFIG"] = unconfigured
    response = app.test_client().post("/api/authoring/prepare", json={})
    assert response.status_code == 503 and response.get_json()["code"] == "PREPARATION_NOT_CONFIGURED"
    assert not (db.parent / preparation_job.LEASE_NAME).exists()
    assert preparation_job.status(db) == {"state": "idle"}


def test_dead_owner_reads_as_interrupted_and_next_start_recovers_cleanly(prepared_workspace):
    db, config = prepared_workspace
    ws = db.parent
    # The state an old child leaves behind when SIGTERMed mid-preparation.
    (ws / preparation_job.LEASE_NAME).write_text(json.dumps(
        {"operation_id": "prep-dead", "kind": "authoring_preparation", "pid": 2 ** 22 + 12345}))
    (ws / preparation_job.STATUS_NAME).write_text(json.dumps(
        {"operation_id": "prep-dead", "state": "running", "started_at": "2026-09-14T00:00:00+00:00"}))
    (ws / ".publication-prepare-deadbeef").mkdir()
    (ws / "publication" / "work-orphan").mkdir(parents=True)
    snapshot = (ws / preparation_job.STATUS_NAME).read_bytes()

    reported = preparation_job.status(db)
    assert reported["state"] == "interrupted" and reported["code"] == "PREPARATION_INTERRUPTED"
    assert (ws / preparation_job.STATUS_NAME).read_bytes() == snapshot, "status must stay read-only"

    started, code = preparation_job.start(db, document_id=None, actor="author", config=config)
    assert code == 202 and started["operation_id"] != "prep-dead"
    assert not (ws / ".publication-prepare-deadbeef").exists()
    assert not (ws / "publication" / "work-orphan").exists()
    preparation_job.wait(db, timeout=15)


def test_interrupt_terminates_runner_records_interrupted_and_cleans(prepared_workspace, tmp_path):
    db, _ = prepared_workspace
    config = _config_from(_slow_compositor(tmp_path, 30.0))
    preparation_job.start(db, document_id=None, actor="author", config=config)
    _wait_until(lambda: len(_runner_pids(tmp_path)) == 1)
    runner = _runner_pids(tmp_path)[0]
    preparation_job.interrupt_all(join_timeout=5)
    try:
        _wait_until(lambda: not _alive(runner), timeout=5)
        final = preparation_job.status(db)
        assert final["state"] == "interrupted" and final["code"] == "PREPARATION_INTERRUPTED"
        assert _leftovers(db.parent) == [] and _work_rows(db) == 0
        assert not (db.parent / preparation_job.LEASE_NAME).exists()
    finally:
        preparation_job._INTERRUPTING.clear()


# ── Through the real supervisor and a real child process ────────────────────


def _supervised(tmp_path: Path, monkeypatch, *, slow_seconds: float, request_timeout: float):
    monkeypatch.chdir(tmp_path)
    for key, value in _slow_compositor(tmp_path, slow_seconds).items():
        monkeypatch.setenv(key, value)
    first = create_workspace("Prepare Lifecycle")
    second = create_workspace("Other Workspace")
    pdf = tmp_path / "source.pdf"
    _make_pdf(pdf, "The lamp glows.")
    _ingest(first.db_path.parent, pdf)
    supervisor = WorkspaceRuntimeSupervisor(
        initial_target=RuntimeTarget(first.db_path, first),
        startup_timeout=10,
        request_timeout=request_timeout,
        child_grace_seconds=3,
    )
    supervisor.start()
    return supervisor, first, second


def test_supervised_prepare_outlives_request_window_without_502_or_race(tmp_path, monkeypatch):
    supervisor, first, second = _supervised(tmp_path, monkeypatch, slow_seconds=3.0, request_timeout=0.5)
    try:
        with _Public(create_supervisor_app(supervisor)) as public:
            started = time.monotonic()
            code, body = _json(public.port, "POST", "/api/authoring/prepare", {})
            assert code == 202, body
            assert time.monotonic() - started < 0.5, "must answer inside the proxy window"
            operation = body["operation_id"]

            code, again = _json(public.port, "POST", "/api/authoring/prepare", {})
            assert code == 202 and again["operation_id"] == operation

            code, busy = _json(public.port, "POST", f"/api/workspaces/{second.slug}/open")
            assert code == 409 and busy["operations"][0]["operation_id"] == operation
            code, runtime = _json(public.port, "GET", "/api/runtime/workspace")
            assert runtime["workspace"]["slug"] == first.slug, "switch refused; active workspace kept"

            # Normal proxying still applies the ordinary request window.
            code, status = _json(public.port, "GET", "/api/authoring/prepare/status")
            assert code == 200 and status["state"] == "running"

            _wait_until(lambda: _json(public.port, "GET", "/api/authoring/prepare/status")[1]["state"] != "running",
                        timeout=15)
            code, final = _json(public.port, "GET", "/api/authoring/prepare/status")
            assert final["operation_id"] == operation and final["state"] == "failed"
            assert len(_runner_pids(tmp_path)) == 1, "one preparation, despite the retry"
            assert _work_rows(first.db_path) == 0 and _leftovers(first.db_path.parent) == []

            code, switched = _json(public.port, "POST", f"/api/workspaces/{second.slug}/open")
            assert code == 200 and switched["changed"] is True, "switch allowed once idle"
    finally:
        supervisor.shutdown()


def test_supervisor_shutdown_mid_preparation_is_recorded_not_orphaned(tmp_path, monkeypatch):
    supervisor, first, _second = _supervised(tmp_path, monkeypatch, slow_seconds=30.0, request_timeout=0.5)
    child = supervisor.active.process
    try:
        with _Public(create_supervisor_app(supervisor)) as public:
            code, body = _json(public.port, "POST", "/api/authoring/prepare", {})
            assert code == 202
            _wait_until(lambda: len(_runner_pids(tmp_path)) == 1)
            runner = _runner_pids(tmp_path)[0]
    finally:
        supervisor.shutdown()
    assert child.poll() is not None
    _wait_until(lambda: not _alive(runner), timeout=5)
    status = preparation_job.status(first.db_path)
    assert status["state"] == "interrupted" and status["operation_id"] == body["operation_id"]
    assert _leftovers(first.db_path.parent) == [] and _work_rows(first.db_path) == 0
    assert not (first.db_path.parent / preparation_job.LEASE_NAME).exists()


# ── Real Compositor: success still ends in the verified S1 attach ───────────


@pytest.mark.skipif(not (REAL.configured and REAL.typst and REAL.profile and REAL.fonts),
                    reason="real Compositor preparation environment not configured")
def test_real_preparation_completes_asynchronously_and_attaches_once(tmp_path):
    ws = tmp_path / "ws"
    pdf = tmp_path / "source.pdf"
    typ = tmp_path / "source.typ"
    typ.write_text('#set page(width: 432pt, height: 648pt, margin: 54pt)\n'
                   f'#set text(font: "Synthetic Test Serif", size: 10pt)\n'
                   '#heading[Synthetic Heading]\nThe lamp glows.\n\nA closing paragraph.\n')
    proc = subprocess.run([REAL.typst, "compile", "--font-path", REAL.fonts, "--ignore-system-fonts", str(typ), str(pdf)],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    db = _ingest(ws, pdf)
    started, code = preparation_job.start(db, document_id=None, actor="author", config=REAL)
    assert code == 202
    final = preparation_job.wait(db, timeout=600)
    assert final["state"] == "succeeded", final
    assert _work_rows(db) == 1 and final["work_id"]
    assert service.projection(db, config=REAL)["attached"] is True
    with pytest.raises(service.AuthoringError) as again:
        preparation_job.start(db, document_id=None, actor="author", config=REAL)
    assert again.value.code == "WORK_ALREADY_ATTACHED"
    assert not (db.parent / preparation_job.LEASE_NAME).exists()
