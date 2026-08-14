"""Stable public runtime supervisor for workspace child processes."""
from __future__ import annotations

import http.client
import json
import os
import selectors
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from flask import Flask, Response, jsonify, request

from hermeneia.workspace import (
    WorkspaceLifecycleError,
    WorkspaceRecord,
    inspect_workspace,
)

from .child_server import READY_EVENT


_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class SupervisorRuntimeError(RuntimeError):
    """Raised when a candidate workspace runtime cannot become active."""


@dataclass(frozen=True)
class RuntimeTarget:
    """A launch target for one child runtime."""

    db_path: Path
    workspace: WorkspaceRecord | None

    @property
    def label(self) -> str:
        if self.workspace is not None:
            return f"{self.workspace.kind}:{self.workspace.slug}"
        return "custom"


@dataclass
class ChildRuntime:
    """A running child process plus drain accounting."""

    target: RuntimeTarget
    process: subprocess.Popen[str]
    host: str
    port: int
    _lock: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.RLock())
    )
    _requests: int = 0
    _draining: bool = False

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    def acquire(self) -> None:
        with self._lock:
            self._requests += 1

    def release(self) -> None:
        with self._lock:
            self._requests = max(0, self._requests - 1)
            if self._requests == 0:
                self._lock.notify_all()

    def mark_draining(self) -> None:
        with self._lock:
            self._draining = True

    def wait_for_drain(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._lock:
            while self._requests > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._lock.wait(timeout=remaining)
            return True

    def terminate(self, *, grace_seconds: float) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=grace_seconds)


class WorkspaceRuntimeSupervisor:
    """Own the stable public endpoint and the active one-workspace child."""

    def __init__(
        self,
        *,
        initial_target: RuntimeTarget,
        startup_timeout: float = 10.0,
        request_timeout: float = 60.0,
        drain_timeout: float | None = None,
        child_grace_seconds: float = 2.0,
    ) -> None:
        self._initial_target = initial_target
        self._startup_timeout = startup_timeout
        self._request_timeout = request_timeout
        self._drain_timeout = request_timeout if drain_timeout is None else drain_timeout
        self._child_grace_seconds = child_grace_seconds
        self._state_lock = threading.RLock()
        self._switch_lock = threading.Lock()
        self._active: ChildRuntime | None = None
        self._draining: list[ChildRuntime] = []
        self._candidate: ChildRuntime | None = None

    @property
    def active(self) -> ChildRuntime:
        with self._state_lock:
            if self._active is None:
                raise SupervisorRuntimeError("workspace runtime has not started")
            return self._active

    def start(self) -> None:
        with self._state_lock:
            if self._active is not None:
                return
        child = self._launch_verified_child(self._initial_target)
        with self._state_lock:
            self._active = child
            if self._candidate is child:
                self._candidate = None

    def shutdown(self) -> None:
        with self._state_lock:
            children = [
                c
                for c in [self._candidate, self._active, *self._draining]
                if c is not None
            ]
            self._candidate = None
            self._active = None
            self._draining = []
        for child in children:
            child.terminate(grace_seconds=self._child_grace_seconds)

    def acquire_active(self) -> ChildRuntime:
        with self._state_lock:
            if self._active is None:
                raise SupervisorRuntimeError("workspace runtime has not started")
            child = self._active
            child.acquire()
            return child

    def release(self, child: ChildRuntime) -> None:
        child.release()

    def open_workspace(self, selector: str) -> tuple[dict, int]:
        if _selector_is_path_like(selector):
            return {"error": "workspace selector must be a catalog name, slug, id, or legacy alias"}, 400
        try:
            record = inspect_workspace(selector)
        except WorkspaceLifecycleError as exc:
            return {"error": str(exc)}, 404

        target = RuntimeTarget(db_path=record.db_path, workspace=record)
        with self._state_lock:
            active = self._active
            if active is None:
                return {"error": "workspace runtime has not started"}, 503
            if _same_workspace(active.target.workspace, record):
                return {"changed": False, "workspace": _workspace_payload(record, is_active=True)}, 200

        if not self._switch_lock.acquire(blocking=False):
            return {"error": "workspace switch already in progress"}, 409

        candidate: ChildRuntime | None = None
        try:
            candidate = self._launch_verified_child(target)
            self._handoff_to_candidate(candidate)
            candidate = None
            return {"changed": True, "workspace": _workspace_payload(record, is_active=True)}, 200
        except SupervisorRuntimeError as exc:
            if candidate is not None:
                candidate.terminate(grace_seconds=self._child_grace_seconds)
            return {"error": str(exc)}, 502
        finally:
            if candidate is not None:
                candidate.terminate(grace_seconds=self._child_grace_seconds)
            with self._state_lock:
                if self._candidate is candidate:
                    self._candidate = None
            self._switch_lock.release()

    def forward_current_request(self, *, workspace_switch_capability: bool = False) -> Response:
        child = self.acquire_active()
        try:
            status, headers, body = _forward_request_to_child(
                child=child,
                timeout=self._request_timeout,
            )
        finally:
            self.release(child)

        if workspace_switch_capability and status == 200:
            body, headers = _with_workspace_switch_capability(body, headers)
        return Response(body, status=status, headers=headers)

    def _launch_verified_child(self, target: RuntimeTarget) -> ChildRuntime:
        child = self._launch_child(target)
        with self._state_lock:
            self._candidate = child
        try:
            self._verify_child(child)
        except Exception as exc:
            child.terminate(grace_seconds=self._child_grace_seconds)
            with self._state_lock:
                if self._candidate is child:
                    self._candidate = None
            raise SupervisorRuntimeError(str(exc)) from exc
        return child

    def _launch_child(self, target: RuntimeTarget) -> ChildRuntime:
        env = os.environ.copy()
        repo_root = Path(__file__).resolve().parents[2]
        pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(repo_root) if not pythonpath else f"{repo_root}{os.pathsep}{pythonpath}"
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "hermeneia.web.child_server",
                "--db",
                str(target.db_path),
                "--host",
                "127.0.0.1",
                "--port",
                "0",
            ],
            cwd=str(Path.cwd()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
        )
        try:
            host, port = _read_child_ready(process, timeout=self._startup_timeout)
        except Exception:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=self._child_grace_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self._child_grace_seconds)
            raise
        _drain_child_stdout(process)
        if host != "127.0.0.1":
            process.terminate()
            process.wait(timeout=self._child_grace_seconds)
            raise SupervisorRuntimeError("child runtime did not bind to localhost")
        return ChildRuntime(target=target, process=process, host=host, port=port)

    def _verify_child(self, child: ChildRuntime) -> None:
        _get_json(child, "/api/health", timeout=self._startup_timeout)
        runtime = _get_json(child, "/api/runtime/workspace", timeout=self._startup_timeout)
        workspace = runtime.get("workspace") if isinstance(runtime, dict) else None
        if not isinstance(workspace, dict):
            raise SupervisorRuntimeError("child runtime did not report workspace identity")
        if child.target.workspace is not None and not _workspace_identity_matches(
            child.target.workspace,
            workspace,
        ):
            raise SupervisorRuntimeError("child runtime reported the wrong workspace identity")

    def _handoff_to_candidate(self, candidate: ChildRuntime) -> None:
        old: ChildRuntime | None = None
        with self._state_lock:
            old = self._active
            self._active = candidate
            self._candidate = None
            if old is not None:
                old.mark_draining()
                self._draining.append(old)
        if old is not None:
            try:
                self._retire_child_when_drained(old)
            except Exception:
                old.terminate(grace_seconds=self._child_grace_seconds)
                with self._state_lock:
                    self._draining = [item for item in self._draining if item is not old]

    def _retire_child_when_drained(self, child: ChildRuntime) -> None:
        def retire() -> None:
            child.wait_for_drain(self._drain_timeout)
            child.terminate(grace_seconds=self._child_grace_seconds)
            with self._state_lock:
                self._draining = [item for item in self._draining if item is not child]

        thread = threading.Thread(
            target=retire,
            name="hermeneia-runtime-retire",
            daemon=True,
        )
        thread.start()


def create_supervisor_app(supervisor: WorkspaceRuntimeSupervisor) -> Flask:
    """Create the public Flask proxy that fronts the active child runtime."""
    app = Flask(__name__)

    @app.route("/api/workspaces/<path:selector>/open", methods=["POST"])
    def open_workspace(selector: str):
        payload, status = supervisor.open_workspace(selector)
        return jsonify(payload), status

    @app.route(
        "/",
        defaults={"path": ""},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    )
    @app.route(
        "/<path:path>",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    )
    def proxy(path: str):
        try:
            return supervisor.forward_current_request(
                workspace_switch_capability=path == "api/runtime/workspace",
            )
        except (OSError, http.client.HTTPException) as exc:
            return jsonify({"error": f"active workspace runtime unavailable: {exc}"}), 502
        except SupervisorRuntimeError as exc:
            return jsonify({"error": str(exc)}), 503

    return app


def runtime_target_from_serve_args(
    *,
    db_path: Path,
    workspace_selector: str | None,
) -> RuntimeTarget:
    """Build a supervisor launch target without making custom DBs selectable."""
    if workspace_selector:
        return RuntimeTarget(db_path=db_path, workspace=inspect_workspace(workspace_selector))
    try:
        record = inspect_workspace("gatsby")
    except WorkspaceLifecycleError:
        record = None
    if record is not None and _canonical(record.db_path) == _canonical(db_path):
        return RuntimeTarget(db_path=db_path, workspace=record)
    return RuntimeTarget(db_path=db_path, workspace=None)


def _forward_request_to_child(
    *,
    child: ChildRuntime,
    timeout: float,
) -> tuple[int, list[tuple[str, str]], bytes]:
    path = request.full_path if request.query_string else request.path
    body = request.get_data()
    headers = _forward_request_headers(request.headers.items())
    conn = http.client.HTTPConnection(child.host, child.port, timeout=timeout)
    try:
        conn.request(request.method, path, body=body, headers=dict(headers))
        response = conn.getresponse()
        response_body = response.read()
        response_headers = _forward_response_headers(response.getheaders())
        return response.status, response_headers, response_body
    finally:
        conn.close()


def _forward_request_headers(headers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    forwarded = []
    for name, value in headers:
        lower = name.lower()
        if lower in _HOP_BY_HOP_HEADERS or lower in {"host", "content-length"}:
            continue
        forwarded.append((name, value))
    return forwarded


def _forward_response_headers(headers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    forwarded = []
    for name, value in headers:
        lower = name.lower()
        if lower in _HOP_BY_HOP_HEADERS or lower == "content-length":
            continue
        forwarded.append((name, value))
    return forwarded


def _with_workspace_switch_capability(
    body: bytes,
    headers: list[tuple[str, str]],
) -> tuple[bytes, list[tuple[str, str]]]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body, headers
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        capabilities = {}
    capabilities["workspace_switch"] = True
    payload["capabilities"] = capabilities
    updated = json.dumps(payload).encode("utf-8")
    response_headers = [
        (name, value)
        for name, value in headers
        if name.lower() not in {"content-length", "content-type"}
    ]
    response_headers.append(("Content-Type", "application/json"))
    return updated, response_headers


def _read_child_ready(process: subprocess.Popen[str], *, timeout: float) -> tuple[str, int]:
    if process.stdout is None:
        raise SupervisorRuntimeError("child runtime stdout was not captured")
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SupervisorRuntimeError("child runtime exited during startup")
        events = selector.select(timeout=max(0.01, min(0.1, deadline - time.monotonic())))
        if not events:
            continue
        line = process.stdout.readline()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == READY_EVENT:
            return str(payload.get("host")), int(payload.get("port"))
        if payload.get("event") == "hermeneia_child_failed":
            raise SupervisorRuntimeError(str(payload.get("error") or "child runtime failed"))
    raise SupervisorRuntimeError("child runtime did not become ready before timeout")


def _drain_child_stdout(process: subprocess.Popen[str]) -> None:
    if process.stdout is None:
        return

    def drain() -> None:
        for line in process.stdout or []:
            sys.stderr.write(line)

    thread = threading.Thread(target=drain, name="hermeneia-child-stdout", daemon=True)
    thread.start()


def _get_json(child: ChildRuntime, path: str, *, timeout: float) -> dict:
    conn = http.client.HTTPConnection(child.host, child.port, timeout=timeout)
    try:
        conn.request("GET", path, headers={"Accept": "application/json"})
        response = conn.getresponse()
        body = response.read()
    finally:
        conn.close()
    if response.status < 200 or response.status >= 300:
        raise SupervisorRuntimeError(f"child runtime {path} returned HTTP {response.status}")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupervisorRuntimeError(f"child runtime {path} did not return JSON") from exc
    if not isinstance(payload, dict):
        raise SupervisorRuntimeError(f"child runtime {path} did not return an object")
    return payload


def _workspace_identity_matches(expected: WorkspaceRecord, reported: dict) -> bool:
    if reported.get("kind") != expected.kind:
        return False
    if reported.get("slug") != expected.slug:
        return False
    if expected.workspace_id and reported.get("id") != expected.workspace_id:
        return False
    return True


def _same_workspace(left: WorkspaceRecord | None, right: WorkspaceRecord | None) -> bool:
    if left is None or right is None:
        return False
    if left.workspace_id and right.workspace_id:
        return left.workspace_id == right.workspace_id
    return left.kind == right.kind and left.slug == right.slug


def _workspace_payload(record: WorkspaceRecord, *, is_active: bool) -> dict:
    payload = {
        "id": record.workspace_id,
        "name": record.name,
        "slug": record.slug,
        "kind": record.kind,
        "managed": record.kind == "managed",
        "is_active": is_active,
    }
    if record.created_at:
        payload["created_at"] = record.created_at
    if record.updated_at:
        payload["updated_at"] = record.updated_at
    return payload


def _selector_is_path_like(selector: str) -> bool:
    return "/" in selector or "\\" in selector or selector.strip() in {".", ".."}


def _canonical(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()
