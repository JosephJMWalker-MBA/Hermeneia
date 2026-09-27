"""HTTP surface of the PM human-attention bridge (bridge-local, experimental).

Reads use read-only connections and have no side effects (CI-012). Writes append
events; nothing here updates or deletes a bridge record. The Reader creates the
anchoring highlight through the existing highlight path first, then attaches a
human judgment to it here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable

from flask import Flask, Response, jsonify, request

from ..integrations import pm_human_gold as G


def register_pm_bridge_routes(
    app: Flask,
    db_path: Path,
    *,
    require_active_document: Callable[[sqlite3.Connection, str], Any],
    scope_error_type: type[Exception],
    scope_error_response: Callable[[Exception], Any],
) -> None:
    def _ro() -> sqlite3.Connection | None:
        if not db_path.exists():
            return None
        conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _rw() -> sqlite3.Connection:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _body() -> dict:
        return request.get_json(silent=True) or {}

    def _actor(body: dict) -> str:
        return str(body.get("actor") or "owner").strip() or "owner"

    def _capture(body: dict) -> dict:
        return {"modality": str(body.get("modality") or "keyboard"),
                "device_class": str(body.get("device_class") or "unknown"),
                "actor": _actor(body)}

    def _run(fn: Callable[[sqlite3.Connection], Any], status: int = 200):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _rw()
        try:
            return jsonify(fn(conn)), status
        except G.BridgeError as exc:
            return jsonify({"error": str(exc)}), exc.status
        except scope_error_type as exc:
            return scope_error_response(exc)
        finally:
            conn.close()

    @app.route("/api/bridge/pm/gold-passes")
    def api_pm_gold_passes():
        conn = _ro()
        if conn is None:
            return jsonify({"passes": [], "open": None, "domain": G.DOMAIN, "annotation_schema": G.ANNOTATION_SCHEMA})
        try:
            passes = G.gold_passes(conn)
            return jsonify({"passes": passes, "open": next((p for p in passes if p["status"] == "GOLD_OPEN"), None),
                            "domain": G.DOMAIN, "annotation_schema": G.ANNOTATION_SCHEMA,
                            "vocabulary": {"target_form": G.TARGET_FORMS, "source_class": G.SOURCE_CLASSES}})
        finally:
            conn.close()

    @app.route("/api/bridge/pm/gold-passes", methods=["POST"])
    def api_pm_gold_pass_open():
        body = _body()
        doc_id = str(body.get("source_document_id") or "").strip()

        def go(conn):
            require_active_document(conn, doc_id)
            return G.open_gold_pass(conn, doc_id, actor=_actor(body), note=body.get("note"))
        return _run(go, 201)

    @app.route("/api/bridge/pm/gold-passes/<gold_pass_id>/seal", methods=["POST"])
    def api_pm_gold_pass_seal(gold_pass_id: str):
        body = _body()
        if body.get("confirm") != "seal":
            return jsonify({"error": 'sealing is explicit: send {"confirm": "seal"}'}), 400
        return _run(lambda conn: G.seal_gold_pass(conn, gold_pass_id, actor=_actor(body), note=body.get("note")))

    @app.route("/api/bridge/pm/annotations")
    def api_pm_annotations():
        conn = _ro()
        if conn is None:
            return jsonify({"annotations": []})
        try:
            doc_id = request.args.get("document_id") or None
            return jsonify({"annotations": G.annotations(conn, doc_id)})
        finally:
            conn.close()

    @app.route("/api/bridge/pm/annotations", methods=["POST"])
    def api_pm_annotate():
        body = _body()
        highlight_id = str(body.get("highlight_id") or "").strip()

        def go(conn):
            h = conn.execute("SELECT source_document_id FROM reader_highlights WHERE id = ?", (highlight_id,)).fetchone()
            if not h:
                raise G.BridgeError("unknown highlight", 404)
            require_active_document(conn, h["source_document_id"])
            return G.annotate(conn, highlight_id, body.get("judgment"), **_capture(body))
        return _run(go, 201)

    @app.route("/api/bridge/pm/annotations/<event_id>/revise", methods=["POST"])
    def api_pm_revise(event_id: str):
        body = _body()
        return _run(lambda conn: G.revise(conn, event_id, body.get("judgment"), **_capture(body)), 201)

    @app.route("/api/bridge/pm/annotations/<event_id>/withdraw", methods=["POST"])
    def api_pm_withdraw(event_id: str):
        body = _body()
        return _run(lambda conn: G.withdraw(conn, event_id, **_capture(body)), 201)

    @app.route("/api/bridge/pm/export")
    def api_pm_export():
        conn = _ro()
        data = G.export_human_gold(conn) if conn is not None else G.export_human_gold(sqlite3.connect(":memory:"))
        if conn is not None:
            conn.close()
        resp = jsonify(data)
        if request.args.get("download"):
            resp.headers["Content-Disposition"] = 'attachment; filename="pm-human-gold.json"'
        return resp

    @app.route("/api/bridge/pm/export.jsonl")
    def api_pm_export_jsonl():
        """Derived, private PM export. With span_text=1 it contains manuscript text: never Git material."""
        conn = _ro()
        if conn is None:
            return jsonify({"error": "database not found"}), 404
        try:
            span = request.args.get("span_text") in ("1", "true", "yes")
            text = G.export_pm_jsonl(conn, include_span_text=span)
        finally:
            conn.close()
        name = "pm-human-gold-PRIVATE-with-span-text.jsonl" if span else "pm-human-gold.jsonl"
        return Response(text, mimetype="application/x-ndjson",
                        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})
