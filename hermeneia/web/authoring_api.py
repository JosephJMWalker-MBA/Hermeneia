"""HTTP routes for the S1 Authoring surface (issue #205).

GET routes are read-only: they never initialize, migrate or write storage.
Every write is an explicit POST that appends history; nothing is updated in
place. The routes are thin: all behaviour lives in ``hermeneia.authoring``.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, jsonify, request

from ..authoring import service
from ..authoring.service import AuthoringError, CompositorConfig


def register_authoring_routes(app: Flask, db_path: Path) -> None:
    def _config() -> CompositorConfig:
        return app.config.get("HERMENEIA_COMPOSITOR_CONFIG") or CompositorConfig.from_env()

    def _error(exc: AuthoringError):
        return jsonify(exc.payload()), exc.status

    def _body() -> dict:
        return request.get_json(silent=True) or {}

    def _actor(body: dict) -> str:
        return str(body.get("actor") or "author").strip() or "author"

    @app.route("/api/authoring/work")
    def api_authoring_work():
        try:
            return jsonify(service.projection(db_path, config=_config()))
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/work/attach", methods=["POST"])
    def api_authoring_attach():
        body = _body()
        source_dir = str(body.get("source_dir") or "").strip()
        if not source_dir:
            return jsonify({"error": "source_dir is required", "code": "SOURCE_DIR_REQUIRED"}), 400
        try:
            return jsonify(service.attach_work(db_path, Path(source_dir), actor=_actor(body), config=_config())), 201
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/prepare", methods=["POST"])
    def api_authoring_prepare():
        body = _body()
        try:
            return jsonify(service.prepare_primary_source(
                db_path,
                document_id=(str(body.get("document_id") or "").strip() or None),
                actor=_actor(body),
                config=_config(),
            )), 201
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/drafts", methods=["POST"])
    def api_authoring_draft():
        body = _body()
        try:
            return jsonify(service.save_draft(
                db_path,
                unit_id=str(body.get("unit_id") or ""),
                parent_version_ref=str(body.get("parent_version_ref") or ""),
                text=str(body.get("text") or ""),
            )), 201
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/proposals", methods=["POST"])
    def api_authoring_propose():
        body = _body()
        try:
            return jsonify(service.propose(
                db_path,
                unit_id=str(body.get("unit_id") or ""),
                parent_version_ref=str(body.get("parent_version_ref") or ""),
                new_text=str(body.get("text") if body.get("text") is not None else ""),
                rationale=str(body.get("rationale") or ""),
                actor=_actor(body),
                config=_config(),
            )), 201
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/proposals/<proposal_id>/decision", methods=["POST"])
    def api_authoring_decide(proposal_id: str):
        body = _body()
        try:
            return jsonify(service.decide(
                db_path,
                proposal_id=proposal_id,
                decision=str(body.get("decision") or ""),
                rationale=str(body.get("rationale") or ""),
                actor=_actor(body),
                config=_config(),
            )), 201
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/decisions/<decision_id>/retry", methods=["POST"])
    def api_authoring_retry(decision_id: str):
        try:
            return jsonify(service.submit(db_path, decision_id=decision_id, config=_config())), 201
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/proofs", methods=["POST"])
    def api_authoring_proof():
        try:
            return jsonify(service.build_proof(db_path, config=_config())), 201
        except AuthoringError as exc:
            return _error(exc)

    @app.route("/api/authoring/proofs/<proof_id>/pdf")
    def api_authoring_proof_pdf(proof_id: str):
        try:
            data = service.proof_pdf(db_path, proof_id)
        except AuthoringError as exc:
            return _error(exc)
        return Response(data, mimetype="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{proof_id}.pdf"'})

    @app.route("/api/authoring/verify")
    def api_authoring_verify():
        try:
            return jsonify(service.verify_history(db_path, config=_config()))
        except AuthoringError as exc:
            return _error(exc)
