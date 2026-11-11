"""Versioned workspace manuscript drafts; not publication-canonical editions.

This is an author-owned *working draft* beside a workspace database. The
Publication Compositor remains the authority for accepted manuscript versions,
proofs, and publication editions. This file does not create SourceDocuments,
Observations, publication_works, or fake Compositor version identities.

Every explicit save creates an immutable revision snapshot and updates a
replaceable head only after the snapshot is durable. Optimistic revision checks
prevent silently overwriting another browser's edits. Markdown export is the
portable escape hatch until Workspace Bundle support is separately reviewed.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, request

MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_TITLE_CHARS = 200
SCHEMA = "hermeneia-working-manuscript/1"


class DraftError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _paths(db_path: Path) -> tuple[Path, Path, Path]:
    root = db_path.parent / "manuscript-draft"
    return root, root / "current.json", root / "revisions"


def _canonical_json(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _revision_id(number: int, previous: str | None, title: str, text: str) -> str:
    content = {"number": number, "previous": previous, "title": title, "text": text}
    return f"r{number:06d}-{hashlib.sha256(_canonical_json(content)).hexdigest()[:20]}"


def _read_head(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["schema"] != SCHEMA:
            raise ValueError("unsupported draft schema")
        expected = _revision_id(
            payload["number"], payload.get("previous"),
            payload["title"], payload["text"],
        )
        if payload["revision"] != expected:
            raise ValueError("draft revision integrity check failed")
        return payload
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise DraftError(
            "MANUSCRIPT_DRAFT_CORRUPT",
            "The manuscript draft cannot be verified. No changes were made. Recover from the saved revision files.",
            409,
        ) from exc


def _atomic_write(path: Path, data: bytes) -> None:
    fd, staging = tempfile.mkstemp(prefix=".draft-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(staging, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)


def _empty() -> dict:
    return {"schema": SCHEMA, "revision": None, "number": 0, "previous": None,
            "title": "", "text": "", "updated_at": None}


def _public(head: dict | None) -> dict:
    value = head or _empty()
    return {key: value[key] for key in ("revision", "number", "title", "text", "updated_at")}


def _save(db_path: Path, body: dict) -> tuple[dict, int]:
    title, text = body.get("title"), body.get("text")
    if not isinstance(title, str) or not isinstance(text, str):
        raise DraftError("INVALID_MANUSCRIPT_DRAFT", "Title and manuscript text must be strings.")
    title = title.strip()
    if not title or len(title) > MAX_TITLE_CHARS:
        raise DraftError("INVALID_MANUSCRIPT_TITLE", "Enter a manuscript title of at most 200 characters.")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise DraftError("MANUSCRIPT_TOO_LARGE", "The draft exceeds the 2 MiB pilot limit. Export Markdown before expanding it.", 413)
    expected = body.get("expected_revision")
    if expected is not None and (not isinstance(expected, str) or len(expected) > 100):
        raise DraftError("INVALID_EXPECTED_REVISION", "Invalid expected revision.")

    root, current_path, history_dir = _paths(db_path)
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise DraftError("UNSAFE_DRAFT_DIRECTORY", "The manuscript directory cannot be a symlink.", 409)
    lock_path = root / ".writer.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = _read_head(current_path)
        head = current or _empty()
        if expected != head["revision"]:
            raise DraftError("STALE_MANUSCRIPT_DRAFT", "This manuscript has changed in another session. Copy your edits, reload, and reconcile before saving.", 409)
        if current and title == current["title"] and text == current["text"]:
            return _public(current), 200
        history_dir.mkdir(exist_ok=True)
        if history_dir.is_symlink():
            raise DraftError("UNSAFE_DRAFT_HISTORY", "The revision directory cannot be a symlink.", 409)
        number = head["number"] + 1
        revision = _revision_id(number, head["revision"], title, text)
        payload = {"schema": SCHEMA, "revision": revision, "number": number,
                   "previous": head["revision"], "title": title, "text": text,
                   "updated_at": datetime.now(timezone.utc).isoformat()}
        data = _canonical_json(payload)
        path = history_dir / (revision + ".json")
        # A snapshot is immutable and cannot be silently replaced.
        try:
            with path.open("xb") as snapshot:
                snapshot.write(data)
                snapshot.flush()
                os.fsync(snapshot.fileno())
        except FileExistsError:
            recorded = _read_head(path)
            if recorded is None or recorded["revision"] != revision:
                raise DraftError("MANUSCRIPT_REVISION_COLLISION", "A conflicting revision already exists.", 409)
        _atomic_write(current_path, data)
        return _public(payload), 201


def register_manuscript_draft_routes(app: Flask, db_path: Path) -> None:
    @app.get("/api/manuscript-draft")
    def manuscript_draft_read():
        try:
            _, head, _ = _paths(db_path)
            return jsonify({**_public(_read_head(head)), "kind": "working_draft",
                            "publication_edition": False})
        except DraftError as exc:
            return jsonify({"error": str(exc), "code": exc.code}), exc.status

    @app.post("/api/manuscript-draft")
    def manuscript_draft_save():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "A JSON object is required.", "code": "INVALID_REQUEST"}), 400
        try:
            payload, status = _save(db_path, body)
            return jsonify({**payload, "kind": "working_draft", "publication_edition": False}), status
        except DraftError as exc:
            return jsonify({"error": str(exc), "code": exc.code}), exc.status

    @app.get("/api/manuscript-draft/history")
    def manuscript_draft_history():
        try:
            _, head_path, history = _paths(db_path)
            if _read_head(head_path) is None:
                return jsonify({"revisions": []})
            snapshots = []
            for file in sorted(history.glob("r*.json"), reverse=True)[:100]:
                entry = _read_head(file)
                if entry:
                    snapshots.append({key: entry[key] for key in
                                      ("revision", "number", "title", "updated_at", "previous")})
            return jsonify({"revisions": snapshots})
        except DraftError as exc:
            return jsonify({"error": str(exc), "code": exc.code}), exc.status

    @app.get("/api/manuscript-draft/export")
    def manuscript_draft_export():
        try:
            _, head_path, _ = _paths(db_path)
            head = _read_head(head_path)
            if head is None:
                raise DraftError("NO_MANUSCRIPT_DRAFT", "There is no saved manuscript draft to export.", 404)
            slug = re.sub(r"[^a-z0-9]+", "-", head["title"].lower()).strip("-")[:60] or "manuscript"
            return Response(head["text"], content_type="text/markdown; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{slug}.md"',
                                     "Cache-Control": "no-store"})
        except DraftError as exc:
            return jsonify({"error": str(exc), "code": exc.code}), exc.status
