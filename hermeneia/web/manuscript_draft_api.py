"""A versioned *working* manuscript for Hermeneia's first real writing pilot.

Not a Publication Compositor edition, canonical version, proof or Reader source.
Semantic HTML plus document-local CSS stay in this workspace's working-draft
area. A commit is an immutable snapshot and the current pointer is updated
atomically. A separate Compositor acceptance/export bridge is later work.
"""
from __future__ import annotations

import fcntl
import hashlib
import html
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask, Response, jsonify, request

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_CSS_BYTES = 64 * 1024
MAX_TITLE_CHARS = 200
SCHEMA = "hermeneia-working-manuscript/2"
ALLOWED_TAGS = {
    "p", "div", "br", "h1", "h2", "h3", "ul", "ol", "li",
    "blockquote", "b", "strong", "i", "em", "u", "s", "del",
    "code", "pre", "hr", "a", "span", "sup", "sub",
}
VOID_TAGS = {"br", "hr"}
SUPPRESSED_TAGS = {"script", "style", "svg", "math", "iframe", "object",
                   "embed", "form", "input", "button", "video", "audio",
                   "link", "meta", "base", "textarea"}


class DraftError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class _MarkupSanitizer(HTMLParser):
    """Allow text and a small semantic markup language, no active attributes."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.opened: list[str] = []
        self.suppress: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SUPPRESSED_TAGS:
            self.suppress.append(tag)
            return
        if self.suppress or tag not in ALLOWED_TAGS:
            return
        attributes = ""
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if (href.startswith("https://") or href.startswith("http://")
                    or href.startswith("mailto:")):
                attributes = f' href="{html.escape(href, quote=True)}" rel="noopener noreferrer"'
        self.parts.append(f"<{tag}{attributes}>")
        if tag not in VOID_TAGS:
            self.opened.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag in VOID_TAGS and not self.suppress:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if self.suppress:
            if tag == self.suppress[-1]:
                self.suppress.pop()
            return
        if tag in self.opened:
            while self.opened:
                top = self.opened.pop()
                self.parts.append(f"</{top}>")
                if top == tag:
                    break

    def handle_data(self, data):
        if not self.suppress:
            self.parts.append(html.escape(data, quote=False))

    def finish(self):
        while self.opened:
            self.parts.append(f"</{self.opened.pop()}>")
        return "".join(self.parts)


def _sanitize_markup(value: str) -> str:
    cleaner = _MarkupSanitizer()
    cleaner.feed(value)
    return cleaner.finish()


def _paths(db_path: Path) -> tuple[Path, Path, Path]:
    root = db_path.parent / "manuscript-draft"
    return root, root / "current.json", root / "revisions"


def _serialized(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _revision_id(number: int, previous: str | None, title: str,
                 markup: str, style_css: str) -> str:
    body = {"number": number, "previous": previous,
            "title": title, "html": markup, "style_css": style_css}
    return f"r{number:06d}-{hashlib.sha256(_serialized(body)).hexdigest()[:20]}"


def _read_revision(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["schema"] != SCHEMA:
            raise ValueError("unsupported working draft schema")
        expected = _revision_id(
            payload["number"], payload.get("previous"), payload["title"],
            payload["html"], payload["style_css"]
        )
        if payload["revision"] != expected:
            raise ValueError("working draft integrity mismatch")
        return payload
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise DraftError(
            "MANUSCRIPT_DRAFT_CORRUPT",
            "The working draft failed integrity verification; no data was changed. Inspect its saved revisions.",
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
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)


def _empty() -> dict:
    return {"schema": SCHEMA, "revision": None, "number": 0, "previous": None,
            "title": "", "html": "", "style_css": "", "updated_at": None}


def _public(record: dict | None) -> dict:
    value = record or _empty()
    return {key: value[key] for key in
            ("revision", "number", "previous", "title", "html", "style_css", "updated_at")}


def _save(db_path: Path, body: dict) -> tuple[dict, int]:
    title, markup, style_css = body.get("title"), body.get("html"), body.get("style_css", "")
    if not all(isinstance(v, str) for v in (title, markup, style_css)):
        raise DraftError("INVALID_MANUSCRIPT_DRAFT", "Title, text, and CSS must be strings.")
    title = title.strip()
    if not title or len(title) > MAX_TITLE_CHARS:
        raise DraftError("INVALID_MANUSCRIPT_TITLE", "Enter a title of at most 200 characters.")
    if len(markup.encode("utf-8")) > MAX_HTML_BYTES:
        raise DraftError("MANUSCRIPT_TOO_LARGE", "The draft exceeds the 2 MiB pilot limit.", 413)
    if len(style_css.encode("utf-8")) > MAX_CSS_BYTES:
        raise DraftError("MANUSCRIPT_CSS_TOO_LARGE", "Document CSS exceeds the 64 KiB pilot limit.", 413)
    # CSS is only ever rendered in the script-disabled document iframe.
    markup = _sanitize_markup(markup)
    expected = body.get("expected_revision")
    if expected is not None and (not isinstance(expected, str) or len(expected) > 100):
        raise DraftError("INVALID_EXPECTED_REVISION", "Invalid expected revision.")

    root, current_path, history_dir = _paths(db_path)
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise DraftError("UNSAFE_DRAFT_DIRECTORY", "The draft directory cannot be a symlink.", 409)
    with (root / ".writer.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = _read_revision(current_path)
        head = current or _empty()
        if expected != head["revision"]:
            raise DraftError("STALE_MANUSCRIPT_DRAFT", "This draft changed in another session. Save your local text elsewhere, reload, and reconcile before resaving.", 409)
        if current and all(current[k] == v for k, v in (
            ("title", title), ("html", markup), ("style_css", style_css)
        )):
            return _public(current), 200
        history_dir.mkdir(exist_ok=True)
        if history_dir.is_symlink():
            raise DraftError("UNSAFE_DRAFT_HISTORY", "The revision directory cannot be a symlink.", 409)
        number = head["number"] + 1
        revision = _revision_id(number, head["revision"], title, markup, style_css)
        payload = {"schema": SCHEMA, "revision": revision, "number": number,
                   "previous": head["revision"], "title": title, "html": markup,
                   "style_css": style_css, "updated_at": datetime.now(timezone.utc).isoformat()}
        data = _serialized(payload)
        snapshot_path = history_dir / (revision + ".json")
        try:
            with snapshot_path.open("xb") as snapshot:
                snapshot.write(data)
                snapshot.flush()
                os.fsync(snapshot.fileno())
        except FileExistsError:
            existing = _read_revision(snapshot_path)
            if existing is None or existing != payload:
                raise DraftError("MANUSCRIPT_REVISION_COLLISION", "A different revision already exists at this identifier.", 409)
        _atomic_write(current_path, data)
        return _public(payload), 201


def _html_export(title: str, markup: str, css: str) -> str:
    # style payload is data, not an executable script. Escape closing tag.
    safe_css = re.sub(r"</style", r"<\\/style", css, flags=re.I)
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>{safe_css}</style></head>"
        f"<body><article>{markup}</article></body></html>"
    )


def register_manuscript_draft_routes(app: Flask, db_path: Path) -> None:
    def error(exc: DraftError):
        return jsonify({"error": str(exc), "code": exc.code}), exc.status

    @app.get("/api/manuscript-draft")
    def manuscript_draft_read():
        try:
            _, path, _ = _paths(db_path)
            return jsonify({**_public(_read_revision(path)), "kind": "working_draft",
                            "publication_edition": False})
        except DraftError as exc:
            return error(exc)

    @app.post("/api/manuscript-draft")
    def manuscript_draft_save():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "A JSON object is required."}), 400
        try:
            result, status = _save(db_path, body)
            return jsonify({**result, "kind": "working_draft", "publication_edition": False}), status
        except DraftError as exc:
            return error(exc)

    @app.get("/api/manuscript-draft/history")
    def manuscript_draft_history():
        try:
            _, head, folder = _paths(db_path)
            if _read_revision(head) is None:
                return jsonify({"revisions": []})
            snapshots = []
            for file in sorted(folder.glob("r*.json"), reverse=True)[:100]:
                entry = _read_revision(file)
                if entry:
                    snapshots.append({key: entry[key] for key in
                                      ("revision", "number", "previous", "title", "updated_at")})
            return jsonify({"revisions": snapshots})
        except DraftError as exc:
            return error(exc)

    @app.get("/api/manuscript-draft/history/<revision>")
    def manuscript_draft_revision(revision: str):
        if not re.fullmatch(r"r[0-9]{6}-[a-f0-9]{20}", revision):
            return jsonify({"error": "Invalid revision identifier."}), 400
        try:
            _, _, folder = _paths(db_path)
            snapshot = _read_revision(folder / (revision + ".json"))
            if snapshot is None:
                raise DraftError("REVISION_NOT_FOUND", "That revision does not exist.", 404)
            return jsonify({**_public(snapshot), "kind": "working_draft"})
        except DraftError as exc:
            return error(exc)

    @app.get("/api/manuscript-draft/export")
    def manuscript_draft_export():
        try:
            _, head, _ = _paths(db_path)
            saved = _read_revision(head)
            if saved is None:
                raise DraftError("NO_MANUSCRIPT_DRAFT", "Save a draft before exporting.", 404)
            slug = re.sub(r"[^a-z0-9]+", "-", saved["title"].lower()).strip("-")[:60] or "manuscript"
            return Response(_html_export(saved["title"], saved["html"], saved["style_css"]),
                            content_type="text/html; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{slug}.html"',
                                     "Cache-Control": "no-store"})
        except DraftError as exc:
            return error(exc)
