"""Shared synthetic fixtures for the #251 proposal-mode tests (contract v1.1).

`golden_workspace` builds a deterministic study whose legacy architect prompt
exercises sampling (55 Observations, 40 shown), a non-primary document, and
Interpretations whose Observations are shown and unshown. The golden prompt in
tests/fixtures/r251/legacy_architect_prompt_golden.txt was captured from the
unmodified route at d38fdbc. P5 isolation; no network.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3

import synthetic_study_lab as lab
from hermeneia.storage.hashing import make_interpretation_id
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

GOLDEN_PROMPT = Path(__file__).resolve().parent / "fixtures" / "r251" / "legacy_architect_prompt_golden.txt"
GOLDEN_DIRECTIVE = "  Trace the lines.  "


def golden_workspace(workdir: Path, mode: str = "legacy"):
    """Returns (db, app) for the deterministic golden study."""
    db = workdir / "ws" / "workspace.db"
    SQLiteStore(db).close()
    app = create_app(db_path=db, credential_store=lab._NoCredentials())
    app.config["LEGACY_BLUEPRINT_WRITES"] = mode
    client = app.test_client()
    docs = []
    for name, count in (("one", 30), ("two", 25)):
        lines = [f"Document {name}, line {k}." for k in range(1, count + 1)]
        body = lab._ok(client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(lines)), f"synthetic-{name}.pdf")},
                                   content_type="multipart/form-data"))
        docs.append(body["document_id"])
    lab._ok(client.patch(f"/api/documents/{docs[1]}/scope", json={"source_role": "reference"}))
    conn = sqlite3.connect(db)
    observations = [r[0] for r in conn.execute("SELECT id FROM observations ORDER BY page, paragraph, sentence, id")]
    conn.close()
    store = SQLiteStore(db)
    try:
        for k, (index, status) in enumerate(((0, "speculative"), (7, "established"), (50, "established"))):
            observation, text = observations[index], f"Steward reading {k}."
            store.insert_interpretation({
                "id": make_interpretation_id(observation, "Close", text), "observation_id": observation, "perspective": "Close",
                "text": text, "evidential_status": status, "evidence_observation_ids": json.dumps([observation]),
                "confidence": "human", "source": "steward-authored", "created_at": f"2026-10-13T12:00:0{k}+00:00"})
    finally:
        store.close()
    return db, app
