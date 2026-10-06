"""Promoted regression for #221: a failed compile leaves no partial evidence chain.

If compilation fails at any persistence stage, no SourceDocument,
SourceExtraction, Observation, provenance, derived or term row from that
compile may remain (CI lineage invariant: creation fails when a required
provenance relation is absent), and the upload's source bytes are not
discarded. Commit 6e45298 preserves the negative versions; the repair
demonstrated strict unexpected passes before the expected failures were removed.
Synthetic PDFs; failures injected at real persistence seams.
"""
from __future__ import annotations

import hashlib
import io
import sqlite3

import fitz
import pytest

from hermeneia.compiler.compiler import Compiler
from hermeneia.storage.repository import Repository
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

TABLES = ("source_documents", "source_extractions", "observations", "provenance",
          "observation_derived", "terms", "observation_terms")


class PartialEvidenceChain(AssertionError):
    """Only the observed partial-persistence failure is expected here."""


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def _counts(db) -> dict[str, int]:
    conn = sqlite3.connect(db)
    try:
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    finally:
        conn.close()


def _fail(*_args, **_kwargs):
    raise OSError("injected interruption")


FAULTS = {
    "provenance_stage": (Repository, "persist_provenance"),
    "term_index_stage": (SQLiteStore, "insert_observation_terms_batch"),
}


@pytest.mark.parametrize("fault", sorted(FAULTS))
def test_failed_upload_compile_leaves_no_rows_and_keeps_source_bytes(tmp_path, monkeypatch, fault):
    ws = tmp_path / "ws"
    db = ws / "workspace.db"
    SQLiteStore(db).close()
    app = create_app(db_path=db)
    app.config["TESTING"] = False
    data = _pdf("The lamp burned all night. Nobody asked why it burned.")
    monkeypatch.setattr(*FAULTS[fault], _fail)
    response = app.test_client().post("/api/upload", data={"file": (io.BytesIO(data), "study.pdf")},
                                      content_type="multipart/form-data")
    assert response.status_code == 500
    counts = _counts(db)
    kept = any(hashlib.sha256(p.read_bytes()).hexdigest() == hashlib.sha256(data).hexdigest()
               for p in (ws / "uploads").iterdir() if p.is_file())
    if any(counts.values()) or not kept:
        raise PartialEvidenceChain(f"{fault}: counts={counts} source_bytes_kept={kept}")


def test_failed_cli_compile_leaves_no_rows(tmp_path, monkeypatch):
    pdf = tmp_path / "study.pdf"
    pdf.write_bytes(_pdf("A document compiled from the command line."))
    db = tmp_path / "workspace.db"
    compiler = Compiler(db_path=db, build_dir=tmp_path / "build")
    monkeypatch.setattr(Repository, "persist_provenance", _fail)
    with pytest.raises(OSError):
        compiler.compile(pdf)
    compiler.close()
    counts = _counts(db)
    if any(counts.values()):
        raise PartialEvidenceChain(f"counts={counts}")


def test_successful_compile_after_failure_creates_the_complete_chain(tmp_path, monkeypatch):
    pdf = tmp_path / "study.pdf"
    pdf.write_bytes(_pdf("Retry after an interruption completes the chain."))
    db = tmp_path / "workspace.db"
    compiler = Compiler(db_path=db, build_dir=tmp_path / "build")
    with monkeypatch.context() as patch:
        patch.setattr(Repository, "persist_provenance", _fail)
        with pytest.raises(OSError):
            compiler.compile(pdf)
    compiler.compile(pdf)
    compiler.close()
    counts = _counts(db)
    assert counts["source_documents"] == 1
    assert counts["observations"] > 0 and counts["provenance"] == counts["observations"]
    assert counts["observation_derived"] == counts["observations"] and counts["terms"] > 0
