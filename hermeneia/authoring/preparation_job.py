"""Single-flight, asynchronous in-workspace preparation (issue #205).

Preparing a real book legitimately takes minutes, far longer than the
supervised proxy's request window. A synchronous request there only
abandoned the response: the child kept preparing, could attach a work after
the caller saw 502, a retry started a second racing preparation, and a
workspace drain killed the child without cleanup or any recorded outcome.

This module makes preparation a workspace-owned operation instead:

* ``start`` begins one preparation (or identifies the one already running)
  and returns immediately; the unchanged S1 ``attach_work`` still performs
  the verified attach at the end.
* One atomic on-disk lease per workspace (``O_CREAT | O_EXCL``) guarantees a
  single owner across threads and processes; the raw Advanced attach takes
  the same lease.
* ``status`` is read-only and always reports a truthful outcome, including
  ``interrupted`` when the owning process has died.
* ``interrupt_all`` (installed as the child's SIGTERM handler) stops the
  running Compositor process and records ``interrupted``; the next ``start``
  cleans stale staging and unreferenced publication directories.

HISTORY IS IMMUTABLE; THE CURRENT WORK IS REVISABLE.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from .service import AuthoringError, CompositorConfig

# Distinct from the ".publication-prepare-*" staging prefix, so staging
# cleanup can never touch the lease or the recorded outcome.
LEASE_NAME = ".authoring-prepare.lease"
STATUS_NAME = ".authoring-prepare-status.json"
TERMINAL_STATES = ("succeeded", "refused", "failed", "interrupted")
OPERATION_KIND = "authoring_preparation"
INTERRUPTED_MESSAGE = (
    "Preparation was interrupted before it finished (the workspace runtime stopped). "
    "Nothing was attached; start it again."
)

_LOCK = threading.RLock()
_THREADS: dict[str, threading.Thread] = {}
_INTERRUPTING = threading.Event()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_dir(db_path: str | Path) -> Path:
    return Path(db_path).resolve().parent


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _pid_alive(pid: object) -> bool:
    try:
        pid = int(pid)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lease_is_live(workspace: Path, lease: dict | None) -> bool:
    if not lease:
        return False
    if int(lease.get("pid") or -1) == os.getpid():
        thread = _THREADS.get(str(workspace))
        if lease.get("kind") == OPERATION_KIND:
            return thread is not None and thread.is_alive()
        return True  # a synchronous exclusive section in this process
    return _pid_alive(lease.get("pid"))


def status(db_path: str | Path) -> dict:
    """Current preparation state for this workspace. Read-only."""
    workspace = _workspace_dir(db_path)
    current = _read_json(workspace / STATUS_NAME) or {"state": "idle"}
    current.pop("pid", None)
    if current.get("state") == "running" and not _lease_is_live(workspace, _read_json(workspace / LEASE_NAME)):
        current = {**current, "state": "interrupted", "code": "PREPARATION_INTERRUPTED",
                   "message": INTERRUPTED_MESSAGE}
    return current


def active_operations(db_path: str | Path) -> list[dict]:
    """Long-running operations that a workspace switch must not interrupt."""
    current = status(db_path)
    if current.get("state") != "running":
        return []
    return [{"kind": OPERATION_KIND, "operation_id": current.get("operation_id"),
             "started_at": current.get("started_at")}]


def _referenced_work_ids(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return {row[0] for row in conn.execute("SELECT id FROM publication_works")}
    except sqlite3.Error:
        return set()
    finally:
        conn.close()


def _clean_orphans(db_path: Path) -> list[str]:
    """Remove stale preparation staging and publication dirs no row references.

    Only called while this process holds the workspace lease, so no preparation
    or attach can be using them.
    """
    workspace = _workspace_dir(db_path)
    removed = []
    for path in workspace.glob(".publication-prepare-*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path.name)
    publication = workspace / "publication"
    if publication.is_dir():
        referenced = _referenced_work_ids(db_path)
        for path in publication.iterdir():
            if path.is_dir() and path.name.startswith("work-") and path.name not in referenced:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(f"publication/{path.name}")
        if not any(publication.iterdir()):
            publication.rmdir()
    return removed


def _acquire_lease(workspace: Path, lease: dict) -> bool:
    """Atomically take the workspace lease, recovering it first if its owner died."""
    path = workspace / LEASE_NAME
    existing = _read_json(path)
    if existing is not None:
        if _lease_is_live(workspace, existing):
            return False
        previous = _read_json(workspace / STATUS_NAME)
        if previous and previous.get("state") == "running" and previous.get("operation_id") == existing.get("operation_id"):
            _write_json_atomic(workspace / STATUS_NAME, {**previous, "state": "interrupted",
                                                         "code": "PREPARATION_INTERRUPTED",
                                                         "message": INTERRUPTED_MESSAGE, "finished_at": _now()})
        path.unlink(missing_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(lease, handle)
    return True


def _release_lease(workspace: Path, operation_id: str) -> None:
    path = workspace / LEASE_NAME
    lease = _read_json(path)
    if lease is not None and lease.get("operation_id") == operation_id:
        path.unlink(missing_ok=True)


class PreparationInProgress(AuthoringError):
    def __init__(self, current: dict):
        super().__init__("PREPARATION_IN_PROGRESS",
                         "A preparation is already running for this workspace.", 409)
        self.current = current


class AuthoringOperationInProgress(AuthoringError):
    def __init__(self, holder: dict):
        kind = str(holder.get("kind") or "unknown")
        super().__init__("AUTHORING_OPERATION_IN_PROGRESS",
                         f"Another authoring operation ({kind}) holds this workspace; "
                         "try again when it finishes.", 409)
        self.holder_kind = kind


def _conflict(db_path: str | Path) -> AuthoringError:
    """The truthful refusal for whichever operation currently holds the lease."""
    holder = _read_json(_workspace_dir(db_path) / LEASE_NAME) or {}
    if holder.get("kind") == OPERATION_KIND:
        return PreparationInProgress(status(db_path))
    return AuthoringOperationInProgress(holder)


def _joinable_preparation(db_path: str | Path) -> dict | None:
    """The running preparation that holds the lease, if that is who holds it."""
    holder = _read_json(_workspace_dir(db_path) / LEASE_NAME) or {}
    current = status(db_path)
    if (holder.get("kind") == OPERATION_KIND and current.get("state") == "running"
            and current.get("operation_id") == holder.get("operation_id")):
        return current
    return None


@contextmanager
def exclusive(db_path: str | Path, kind: str) -> Iterator[None]:
    """Hold the workspace lease for a short synchronous authoring write (raw attach)."""
    workspace = _workspace_dir(db_path)
    operation_id = f"{kind}-{uuid.uuid4().hex}"
    with _LOCK:
        if not _acquire_lease(workspace, {"operation_id": operation_id, "kind": kind, "pid": os.getpid(),
                                          "started_at": _now()}):
            raise _conflict(db_path)
    try:
        yield
    finally:
        _release_lease(workspace, operation_id)


def start(db_path: str | Path, *, document_id: str | None, actor: str,
          config: CompositorConfig) -> tuple[dict, int]:
    """Start one preparation, or identify the one already running. Returns (payload, HTTP status)."""
    from . import service

    db_path = Path(db_path)
    workspace = _workspace_dir(db_path)
    with _LOCK:
        joinable = _joinable_preparation(db_path)
        if joinable is not None:
            return {**joinable, "already_running": True}, 202
        operation_id = f"prep-{uuid.uuid4().hex}"
        lease = {"operation_id": operation_id, "kind": OPERATION_KIND, "pid": os.getpid(), "started_at": _now()}
        if not _acquire_lease(workspace, lease):
            # 202 only for the same running preparation; anything else is a truthful conflict.
            joinable = _joinable_preparation(db_path)
            if joinable is not None:
                return {**joinable, "already_running": True}, 202
            raise _conflict(db_path)
        try:
            _clean_orphans(db_path)
            chosen, source_path = service.resolve_preparation(db_path, document_id=document_id, config=config)
        except BaseException:
            _release_lease(workspace, operation_id)
            raise
        record = {
            "operation_id": operation_id,
            "state": "running",
            "document_id": chosen["id"],
            "source_filename": chosen["original_filename"],
            "actor": actor,
            "started_at": lease["started_at"],
        }
        _write_json_atomic(workspace / STATUS_NAME, {**record, "pid": os.getpid()})
        thread = threading.Thread(
            target=_run, args=(db_path, record, chosen, source_path, config),
            name=f"hermeneia-prepare-{operation_id}", daemon=True,
        )
        _THREADS[str(workspace)] = thread
        thread.start()
    return record, 202


def _run(db_path: Path, record: dict, chosen: dict, source_path: Path, config: CompositorConfig) -> None:
    from . import service

    workspace = _workspace_dir(db_path)
    final: dict
    try:
        result = service.run_preparation(db_path, chosen=chosen, source_path=source_path,
                                         actor=record["actor"], config=config)
        final = {"state": "succeeded", "work_id": result["work_id"], "stages": result.get("stages") or []}
    except AuthoringError as exc:
        final = {"state": "refused" if exc.status == 409 else "failed", "code": exc.code,
                 "message": exc.message, "stage": exc.stage, "findings": exc.findings}
    except Exception as exc:  # recorded, never swallowed silently
        final = {"state": "failed", "code": "PREPARATION_ERROR", "message": f"{type(exc).__name__}: {exc}"}
    if _INTERRUPTING.is_set() and final["state"] != "succeeded":
        final = {"state": "interrupted", "code": "PREPARATION_INTERRUPTED", "message": INTERRUPTED_MESSAGE}
    with _LOCK:
        _write_json_atomic(workspace / STATUS_NAME, {**record, **final, "finished_at": _now()})
        _release_lease(workspace, record["operation_id"])
        if _THREADS.get(str(workspace)) is threading.current_thread():
            _THREADS.pop(str(workspace), None)


def wait(db_path: str | Path, timeout: float | None = None) -> dict:
    """Test/diagnostic helper: wait for this process's preparation thread, then return status."""
    thread = _THREADS.get(str(_workspace_dir(db_path)))
    if thread is not None:
        thread.join(timeout)
    return status(db_path)


def interrupt_all(*, join_timeout: float = 1.5) -> None:
    """Stop running preparations in this process and record them as interrupted.

    Installed as the supervised child's SIGTERM handler so a drain or shutdown
    never silently orphans a preparation.
    """
    from . import service

    _INTERRUPTING.set()
    service.terminate_active_runners()
    with _LOCK:
        threads = dict(_THREADS)
    for workspace_key, thread in threads.items():
        thread.join(join_timeout)
        if thread.is_alive():
            workspace = Path(workspace_key)
            current = _read_json(workspace / STATUS_NAME) or {}
            if current.get("state") == "running":
                _write_json_atomic(workspace / STATUS_NAME, {**current, "state": "interrupted",
                                                             "code": "PREPARATION_INTERRUPTED",
                                                             "message": INTERRUPTED_MESSAGE, "finished_at": _now()})
                _release_lease(workspace, current.get("operation_id") or "")
            for path in workspace.glob(".publication-prepare-*"):
                shutil.rmtree(path, ignore_errors=True)


def install_signal_handler(on_exit: Callable[[], None] | None = None) -> None:
    """Install ``interrupt_all`` as SIGTERM handler (must be called from the main thread)."""
    import signal

    def _handle(signum, frame):  # noqa: ARG001
        interrupt_all()
        if on_exit is not None:
            on_exit()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle)
