"""Supervisor runtime handoff for isolated workspace child processes."""
from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from hermeneia.web.app import create_app
from hermeneia.web.supervisor import (
    ChildRuntime,
    RuntimeTarget,
    SupervisorRuntimeError,
    WorkspaceRuntimeSupervisor,
    create_supervisor_app,
    runtime_target_from_serve_args,
)
from hermeneia.workspace import WorkspaceRecord, create_workspace, inspect_workspace


class _FakeProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int | None:
        return self.returncode


class _FakeSupervisor(WorkspaceRuntimeSupervisor):
    def __init__(
        self,
        *,
        initial_record: WorkspaceRecord,
        fail_launch_for: set[str] | None = None,
        verify_errors: dict[str, str] | None = None,
        block_launch_for: str | None = None,
    ) -> None:
        super().__init__(
            initial_target=RuntimeTarget(initial_record.db_path, initial_record),
            startup_timeout=0.5,
            drain_timeout=0.2,
            child_grace_seconds=0.01,
        )
        self.fail_launch_for = fail_launch_for or set()
        self.verify_errors = verify_errors or {}
        self.block_launch_for = block_launch_for
        self.block_entered = threading.Event()
        self.unblock_launch = threading.Event()
        self.launched: list[str] = []
        self.children: list[ChildRuntime] = []

    def _launch_child(self, target: RuntimeTarget) -> ChildRuntime:
        key = target.workspace.slug if target.workspace else "custom"
        if key in self.fail_launch_for:
            raise SupervisorRuntimeError("candidate failed to start")
        if key == self.block_launch_for:
            self.block_entered.set()
            if not self.unblock_launch.wait(timeout=2):
                raise SupervisorRuntimeError("candidate launch timed out")
        self.launched.append(key)
        child = ChildRuntime(
            target=target,
            process=_FakeProcess(),  # type: ignore[arg-type]
            host="127.0.0.1",
            port=10000 + len(self.launched),
        )
        self.children.append(child)
        return child

    def _verify_child(self, child: ChildRuntime) -> None:
        key = child.target.workspace.slug if child.target.workspace else "custom"
        if key in self.verify_errors:
            raise SupervisorRuntimeError(self.verify_errors[key])


class _HandoffFailingSupervisor(_FakeSupervisor):
    def _handoff_to_candidate(self, candidate: ChildRuntime) -> None:
        raise SupervisorRuntimeError("candidate handoff failed")


class _ServerThread:
    def __init__(self, app) -> None:
        self.server = make_server("127.0.0.1", 0, app, threaded=True)
        self.port = int(self.server.socket.getsockname()[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "_ServerThread":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()


def _json_request(
    port: int,
    method: str,
    path: str,
    payload: dict | None = None,
) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        data = response.read()
    finally:
        conn.close()
    return response.status, json.loads(data.decode("utf-8"))


def _raw_request(port: int, method: str, path: str) -> tuple[int, bytes, dict[str, str]]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path)
        response = conn.getresponse()
        data = response.read()
        headers = {name.lower(): value for name, value in response.getheaders()}
    finally:
        conn.close()
    return response.status, data, headers


def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true")


def test_direct_runtime_reports_workspace_switch_capability_false(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record = create_workspace("The Second Sale")
    client = create_app(db_path=record.db_path).test_client()

    body = client.get("/api/runtime/workspace").get_json()

    assert body["capabilities"] == {"workspace_switch": False}


def test_supervisor_open_starts_candidate_hands_off_and_retires_old(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    second = create_workspace("Research Notes")
    supervisor = _FakeSupervisor(initial_record=first)
    supervisor.start()
    old_child = supervisor.active

    payload, status = supervisor.open_workspace(second.slug)

    assert status == 200
    assert payload["changed"] is True
    assert payload["workspace"]["slug"] == "research-notes"
    assert supervisor.active.target.workspace == second
    _wait_until(lambda: old_child.process.terminated)


def test_supervisor_start_clears_initial_candidate_bookkeeping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    supervisor = _FakeSupervisor(initial_record=first)

    supervisor.start()

    assert supervisor.active.target.workspace == first
    assert supervisor._candidate is None
    supervisor.shutdown()


def test_supervisor_default_drain_window_tracks_request_timeout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    supervisor = WorkspaceRuntimeSupervisor(
        initial_target=RuntimeTarget(first.db_path, first),
        request_timeout=17,
    )

    assert supervisor._request_timeout == 17
    assert supervisor._drain_timeout == 17


def test_supervisor_drains_in_flight_old_child_before_retiring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    second = create_workspace("Research Notes")
    supervisor = _FakeSupervisor(initial_record=first)
    supervisor.start()
    old_child = supervisor.active
    old_child.acquire()

    payload, status = supervisor.open_workspace(second.slug)

    assert status == 200
    assert payload["changed"] is True
    assert old_child.process.terminated is False
    old_child.release()
    _wait_until(lambda: old_child.process.terminated)


def test_supervisor_shutdown_reaps_active_and_draining_children(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    second = create_workspace("Research Notes")
    supervisor = _FakeSupervisor(initial_record=first)
    supervisor.start()
    old_child = supervisor.active
    old_child.acquire()
    supervisor.open_workspace(second.slug)
    active_child = supervisor.active

    supervisor.shutdown()

    assert old_child.process.terminated is True
    assert active_child.process.terminated is True
    old_child.release()


def test_supervisor_open_current_workspace_is_noop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    supervisor = _FakeSupervisor(initial_record=first)
    supervisor.start()

    payload, status = supervisor.open_workspace("The Second Sale")

    assert status == 200
    assert payload["changed"] is False
    assert payload["workspace"]["slug"] == "the-second-sale"
    assert supervisor.launched == ["the-second-sale"]


def test_supervisor_rejects_concurrent_workspace_switch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    second = create_workspace("Research Notes")
    supervisor = _FakeSupervisor(
        initial_record=first,
        block_launch_for=second.slug,
    )
    supervisor.start()
    result: list[tuple[dict, int]] = []
    thread = threading.Thread(
        target=lambda: result.append(supervisor.open_workspace(second.slug))
    )

    thread.start()
    assert supervisor.block_entered.wait(timeout=2)
    concurrent_payload, concurrent_status = supervisor.open_workspace(second.slug)
    supervisor.unblock_launch.set()
    thread.join(timeout=2)

    assert concurrent_status == 409
    assert "already in progress" in concurrent_payload["error"]
    assert result and result[0][1] == 200


@pytest.mark.parametrize(
    ("supervisor_factory", "expected_error"),
    [
        (
            lambda first, second: _FakeSupervisor(
                initial_record=first,
                fail_launch_for={second.slug},
            ),
            "candidate failed to start",
        ),
        (
            lambda first, second: _FakeSupervisor(
                initial_record=first,
                verify_errors={second.slug: "child runtime /api/health returned HTTP 504"},
            ),
            "child runtime /api/health returned HTTP 504",
        ),
        (
            lambda first, second: _FakeSupervisor(
                initial_record=first,
                verify_errors={
                    second.slug: "child runtime reported the wrong workspace identity"
                },
            ),
            "child runtime reported the wrong workspace identity",
        ),
        (
            lambda first, second: _HandoffFailingSupervisor(initial_record=first),
            "candidate handoff failed",
        ),
    ],
)
def test_supervisor_candidate_failures_keep_active_workspace(
    tmp_path,
    monkeypatch,
    supervisor_factory,
    expected_error,
):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    second = create_workspace("Research Notes")
    supervisor = supervisor_factory(first, second)
    supervisor.start()
    active_before = supervisor.active

    payload, status = supervisor.open_workspace(second.slug)

    assert status == 502
    assert expected_error in payload["error"]
    assert supervisor.active is active_before
    assert supervisor.active.target.workspace == first


@pytest.mark.parametrize("selector", ["../foo", "/tmp/foo", r"..\\foo"])
def test_supervisor_open_rejects_path_like_selectors(tmp_path, monkeypatch, selector):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    supervisor = _FakeSupervisor(initial_record=first)
    supervisor.start()

    payload, status = supervisor.open_workspace(selector)

    assert status == 400
    assert "catalog name" in payload["error"]
    assert supervisor.active.target.workspace == first


def test_supervisor_launch_target_leaves_custom_db_unselectable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_workspace("The Second Sale")
    custom_db = Path("custom/hermeneia.db")

    target = runtime_target_from_serve_args(
        db_path=custom_db,
        workspace_selector=None,
    )

    assert target.db_path == custom_db
    assert target.workspace is None


def test_supervised_runtime_switches_real_child_processes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = create_workspace("The Second Sale")
    second = create_workspace("Research Notes")
    supervisor = WorkspaceRuntimeSupervisor(
        initial_target=RuntimeTarget(first.db_path, first),
        startup_timeout=10,
        drain_timeout=1,
        child_grace_seconds=0.5,
    )
    supervisor.start()
    old_process = supervisor.active.process
    app = create_supervisor_app(supervisor)

    try:
        with _ServerThread(app) as public:
            status, body = _json_request(public.port, "GET", "/api/runtime/workspace")
            assert status == 200
            assert body["workspace"]["slug"] == "the-second-sale"
            assert body["capabilities"] == {"workspace_switch": True}
            assert supervisor.active.host == "127.0.0.1"

            status, created = _json_request(
                public.port,
                "POST",
                "/api/workspaces",
                {"name": "Created Through Proxy"},
            )
            assert status == 201
            assert created["workspace"]["is_active"] is False
            assert inspect_workspace("created-through-proxy").slug == "created-through-proxy"

            status, body = _json_request(
                public.port,
                "POST",
                f"/api/workspaces/{second.slug}/open",
            )
            assert status == 200
            assert body["changed"] is True
            assert body["workspace"]["slug"] == "research-notes"

            status, body = _json_request(public.port, "GET", "/api/runtime/workspace")
            assert status == 200
            assert body["workspace"]["slug"] == "research-notes"
            assert body["capabilities"] == {"workspace_switch": True}

            status, body = _json_request(public.port, "GET", "/api/workspaces")
            assert status == 200
            rows = {row["slug"]: row for row in body["workspaces"]}
            assert rows["research-notes"]["is_active"] is True
            assert rows["the-second-sale"]["is_active"] is False

            status, _, headers = _raw_request(public.port, "GET", "/")
            assert status == 200
            assert "text/html" in headers["content-type"]

            status, _, _ = _raw_request(public.port, "GET", "/does-not-exist")
            assert status == 404

            _wait_until(lambda: old_process.poll() is not None)
    finally:
        supervisor.shutdown()
