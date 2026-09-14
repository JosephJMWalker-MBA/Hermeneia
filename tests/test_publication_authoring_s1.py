"""
S1 authoring integration with Publication Compositor (issue #205).

HISTORY IS IMMUTABLE; THE CURRENT WORK IS REVISABLE.

The pure tests below always run. The integration tests exercise the real
Publication Compositor ``EditorialLocalJob`` through Hermeneia's runner and
require a configured Compositor environment:

    HERMENEIA_COMPOSITOR_PYTHON   Python with Publication Compositor's dependencies
    HERMENEIA_COMPOSITOR_PATH     PYTHONPATH exposing ``publication_compositor``
    HERMENEIA_TYPST               pinned typst 0.15.1 executable (proof tests only)

Without them those tests skip with an explicit reason; they are never
simulated. All fixtures are synthetic — no manuscript text is involved.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from hermeneia.authoring import service, store
from hermeneia.authoring.service import AuthoringError, CompositorConfig, plain_text_delta
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace.export import build_workspace_zip, export_workspace_bundle
from hermeneia.workspace.restore import RestoreError, read_bundle, restore_workspace

NOW = "2026-09-14T00:00:00+00:00"
SYNTHETIC_BUILDER = Path(__file__).parent.parent / "hermeneia" / "authoring" / "synthetic_work.py"

COMPOSITOR = CompositorConfig.from_env()
needs_compositor = pytest.mark.skipif(
    not COMPOSITOR.configured,
    reason="Publication Compositor environment not configured (HERMENEIA_COMPOSITOR_PYTHON)",
)
needs_typst = pytest.mark.skipif(
    not (COMPOSITOR.configured and COMPOSITOR.typst and Path(COMPOSITOR.typst).is_file()),
    reason="pinned typst executable not configured (HERMENEIA_TYPST)",
)


# ── Pure contract tests ─────────────────────────────────────────────────────


def test_authoring_tables_are_append_only(tmp_path):
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO publication_works (id, workspace_id, work_root_json, inputs_json, facade_pin_json, "
        "root_version_ref, attached_by, attached_at) VALUES ('w','ws','{}','{}','{}','c0:x','t',?)",
        (NOW,),
    )
    conn.commit()
    for table in store.AUTHORING_TABLES:
        for statement in (f"UPDATE {table} SET rowid = rowid", f"DELETE FROM {table}"):
            if table == "publication_works" or conn.execute(f"SELECT 1 FROM {table}").fetchone():
                with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                    conn.execute(statement)
    conn.close()


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        # "glows." and "shines." share the suffix "s.", so the minimal range is "glow".
        ("The lamp glows.", "The lamp shines.", ("replace_text", 9, 13, "glow", "shine")),
        ("The lamp glows.", "The lamp.", ("delete_text", 8, 14, " glows", "")),
        ("The lamp glows.", "The lamp glows brightly.", ("replace_text", 13, 14, "s", "s brightly")),
        ("glows", "Aglows", ("replace_text", 0, 1, "g", "Ag")),
        ("a \U0001F600 b", "a \U0001F600 c", ("replace_text", 4, 5, "b", "c")),
    ],
)
def test_plain_text_delta_is_exact_scalar_range(before, after, expected):
    delta = plain_text_delta(before, after)
    assert (delta["operation"], delta["start_offset"], delta["end_offset"],
            delta["before_value"], delta["after_value"]) == expected
    assert before[delta["start_offset"]:delta["end_offset"]] == delta["before_value"]
    rebuilt = before[:delta["start_offset"]] + delta["after_value"] + before[delta["end_offset"]:]
    assert rebuilt == after


def test_plain_text_delta_refuses_no_change():
    with pytest.raises(AuthoringError) as exc:
        plain_text_delta("same", "same")
    assert exc.value.code == "NO_CHANGE"


def test_authoring_get_is_read_only_and_reports_no_work(tmp_path):
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    before = db.read_bytes()
    client = create_app(db_path=db).test_client()
    response = client.get("/api/authoring/work")
    assert response.status_code == 200
    assert response.get_json()["attached"] is False
    assert db.read_bytes() == before


def test_workspace_without_work_still_exports_wbs_1_1(tmp_path):
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    manifest = export_workspace_bundle(db, tmp_path / "bundle", generated_at=NOW, workspace_id="w")
    assert manifest["wbs_version"] == "1.1"
    assert "required_capabilities" not in manifest
    assert not (tmp_path / "bundle" / "publication").exists()


def test_restore_refuses_unknown_required_capability(tmp_path):
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    bundle = tmp_path / "bundle"
    export_workspace_bundle(db, bundle, generated_at=NOW, workspace_id="w")
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["required_capabilities"] = ["future-capability-v9"]
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RestoreError, match="future-capability-v9"):
        read_bundle(bundle)


# ── Integration with the real Compositor facade (synthetic work) ────────────


@pytest.fixture(scope="session")
def synthetic_work(tmp_path_factory) -> Path:
    if not COMPOSITOR.configured:
        pytest.skip("Publication Compositor environment not configured")
    out = tmp_path_factory.mktemp("compositor") / "synthetic-work"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if COMPOSITOR.pythonpath:
        env["PYTHONPATH"] = COMPOSITOR.pythonpath
    proc = subprocess.run([COMPOSITOR.python, str(SYNTHETIC_BUILDER), str(out)],
                          env=env, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return out


def _seed_reader_evidence(db: Path) -> None:
    """A forensic source document, extraction, observation and human highlight."""
    SQLiteStore(db).close()
    conn = sqlite3.connect(db)
    doc = "d" * 64
    conn.execute(
        "INSERT INTO source_documents (id, original_filename, file_hash, total_pages, registered_at, "
        "compiler_version, source_role, excluded_from_analysis) VALUES (?,?,?,?,?,?,?,0)",
        (doc, "source.pdf", doc, 1, NOW, "t", "primary"),
    )
    conn.execute(
        "INSERT INTO source_extractions (id, document_id, page, region, raw_text, parser, parser_version, "
        "coordinates, source_locator, source_hash, hash, extracted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("ext-1", doc, 1, "block:2", "The lamp glows.", "t", "1", "{}", "page:1:block:2", doc, "h", NOW),
    )
    conn.execute(
        "INSERT INTO observations (id, epistemic_class, source_document_id, source_extraction_id, raw_text, "
        "source_locator, semantic_hash, page, paragraph, sentence, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("obs-1", "Evidence", doc, "ext-1", "The lamp glows.", "p1s1", "s", 1, 1, 1, NOW),
    )
    conn.execute(
        "INSERT INTO reader_highlights (id, source_document_id, page, selected_text, note_text, created_at, "
        "updated_at) VALUES (?,?,?,?,?,?,?)",
        ("hl-1", doc, 1, "The lamp glows.", "A historical note on the original wording.", NOW, NOW),
    )
    conn.commit()
    conn.close()


def _forensic_rows(db: Path) -> list:
    conn = sqlite3.connect(db)
    out = [conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
           for table in ("source_documents", "source_extractions", "observations", "reader_highlights")]
    conn.close()
    return out


def _current_unit(projection: dict, origin: str) -> dict:
    return next(u for u in projection["units"] if u["origin_ref"] == origin)


def _edit(db, unit, parent, text, label, config=COMPOSITOR):
    proposal = service.propose(db, unit_id=unit["id"], parent_version_ref=parent, new_text=text,
                               rationale=f"{label} rationale", actor="author", config=config)
    assert proposal["validation_status"] == "valid", proposal["findings"]
    result = service.decide(db, proposal_id=proposal["id"], decision="approved",
                            rationale=f"approve {label}", actor="author", config=config)
    assert result["outcome"]["status"] == "accepted", result["outcome"]["findings_json"]
    return proposal, result


@pytest.fixture()
def attached(tmp_path, synthetic_work) -> Path:
    db = tmp_path / "ws" / "hermeneia.db"
    _seed_reader_evidence(db)
    service.attach_work(db, synthetic_work, actor="author", config=COMPOSITOR)
    return db


@needs_compositor
def test_attach_projects_exact_current_version_without_copying_authority(attached):
    p = service.projection(attached, config=COMPOSITOR)
    assert p["attached"] and p["current_version_label"].startswith("C0")
    assert p["current_version_ref"] == p["work"]["root_version_ref"]
    texts = [u["text"] for u in p["units"]]
    assert texts == ["Synthetic Heading", "The lamp glows.", "The lamp glows.", "A closing paragraph."]
    assert p["units"][1]["id"] != p["units"][2]["id"], "equal text must keep distinct unit identity"
    assert set(p["supported_operations"]) == {"replace_text", "delete_text"}
    assert all(u["reader_correspondence"]["status"] == "unresolved" for u in p["units"])
    conn = sqlite3.connect(attached)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert not any("unit_text" in t or t == "manuscript_units" for t in tables)


@needs_compositor
def test_second_attach_is_refused(attached, synthetic_work):
    with pytest.raises(AuthoringError) as exc:
        service.attach_work(attached, synthetic_work, actor="author", config=COMPOSITOR)
    assert exc.value.code == "WORK_ALREADY_ATTACHED"


@needs_compositor
def test_attach_refuses_tampered_work(tmp_path, synthetic_work):
    tampered = tmp_path / "tampered"
    shutil.copytree(synthetic_work, tampered)
    (tampered / "canonical_c0.json").write_text((tampered / "canonical_c0.json").read_text().replace("lamp", "lamb"))
    db = tmp_path / "ws" / "hermeneia.db"
    with pytest.raises(AuthoringError) as exc:
        service.attach_work(db, tampered, actor="author", config=COMPOSITOR)
    assert exc.value.code == "WORK_ARTIFACT_HASH_MISMATCH"


@needs_compositor
def test_two_sequential_edits_to_one_unit_preserve_lineage_and_history(attached):
    before_forensics = _forensic_rows(attached)
    p0 = service.projection(attached, config=COMPOSITOR)
    target, twin = p0["units"][2], p0["units"][1]
    origin = target["origin_ref"]

    _edit(attached, target, p0["current_version_ref"], "The lamp glows brightly.", "first")
    p1 = service.projection(attached, config=COMPOSITOR)
    u1 = _current_unit(p1, origin)
    assert p1["current_version_label"] == "N+1" and u1["text"] == "The lamp glows brightly."
    assert u1["id"] != target["id"], "a changed unit is a new immutable unit version"
    assert _current_unit(p1, twin["origin_ref"])["text"] == "The lamp glows.", "twin must be untouched"

    _edit(attached, u1, p1["current_version_ref"], "The lamp glows brightly again.", "second")
    p2 = service.projection(attached, config=COMPOSITOR)
    u2 = _current_unit(p2, origin)
    assert p2["current_version_label"] == "N+2"
    assert [(item["label"], item["text"]) for item in u2["lineage"]] == [
        ("C0 (source-derived root)", "The lamp glows."),
        ("N+1", "The lamp glows brightly."),
        ("N+2", "The lamp glows brightly again."),
    ]
    assert service.verify_history(attached, config=COMPOSITOR)["accepted_versions"] == 2

    conn = sqlite3.connect(attached)
    chain = store.accepted_chain(conn, p2["work"]["id"])
    assert [row["expected_parent_ref"] for row in chain] == [p0["current_version_ref"], p1["current_version_ref"]]
    assert chain[1]["result_version_ref"] == p2["current_version_ref"]
    decisions = conn.execute("SELECT decision, rationale FROM authoring_decisions ORDER BY decided_at").fetchall()
    receipt = json.loads(store.read_artifact(conn, attached, chain[1]["receipt_artifact_sha256"]))
    conn.close()
    assert decisions == [("approved", "approve first"), ("approved", "approve second")]
    assert receipt["parent_version_ref"] == p1["current_version_ref"]
    assert _forensic_rows(attached) == before_forensics, "Reader evidence and annotations must not migrate"


@needs_compositor
def test_stale_parent_and_unsupported_edits_are_refused_visibly(attached):
    p0 = service.projection(attached, config=COMPOSITOR)
    target = p0["units"][2]
    _edit(attached, target, p0["current_version_ref"], "The lamp glows brightly.", "first")

    stale = service.propose(attached, unit_id=target["id"], parent_version_ref=p0["current_version_ref"],
                            new_text="The lamp glows dimly.", rationale="stale", actor="author", config=COMPOSITOR)
    assert stale["validation_status"] == "refused"
    assert "EDITORIAL_JOB_STALE_PARENT" in {f["code"] for f in stale["findings"]}
    with pytest.raises(AuthoringError) as exc:
        service.decide(attached, proposal_id=stale["id"], decision="approved", rationale="try",
                       actor="author", config=COMPOSITOR)
    assert exc.value.code == "PROPOSAL_NOT_VALID"

    p1 = service.projection(attached, config=COMPOSITOR)
    current = _current_unit(p1, target["origin_ref"])
    erase = service.propose(attached, unit_id=current["id"], parent_version_ref=p1["current_version_ref"],
                            new_text="", rationale="erase", actor="author", config=COMPOSITOR)
    assert erase["validation_status"] == "refused", "whole-unit erasure is outside the supported envelope"
    assert service.projection(attached, config=COMPOSITOR)["current_version_ref"] == p1["current_version_ref"]


@needs_compositor
def test_rejection_and_duplicate_submission_never_change_the_manuscript(attached):
    p0 = service.projection(attached, config=COMPOSITOR)
    target = p0["units"][1]
    proposal = service.propose(attached, unit_id=target["id"], parent_version_ref=p0["current_version_ref"],
                               new_text="The lamp flickers.", rationale="maybe", actor="author", config=COMPOSITOR)
    rejected = service.decide(attached, proposal_id=proposal["id"], decision="rejected", rationale="no",
                              actor="author", config=COMPOSITOR)
    assert rejected["outcome"] is None
    assert service.projection(attached, config=COMPOSITOR)["current_version_ref"] == p0["current_version_ref"]

    _proposal, accepted = _edit(attached, target, p0["current_version_ref"], "The lamp shines.", "real")
    again = service.submit(attached, decision_id=accepted["decision"]["id"], config=COMPOSITOR)
    assert again.get("duplicate") is True and again["id"] == accepted["outcome"]["id"]
    conn = sqlite3.connect(attached)
    assert conn.execute("SELECT COUNT(*) FROM authoring_outcomes WHERE status='accepted'").fetchone()[0] == 1
    conn.close()


@needs_typst
def test_proof_renders_only_final_wording_and_links_exact_unit(attached):
    p0 = service.projection(attached, config=COMPOSITOR)
    target = p0["units"][2]
    _edit(attached, target, p0["current_version_ref"], "The lamp glows brightly.", "first")
    p1 = service.projection(attached, config=COMPOSITOR)
    _edit(attached, _current_unit(p1, target["origin_ref"]), p1["current_version_ref"], "The lamp glows brightly again.", "second")
    p2 = service.projection(attached, config=COMPOSITOR)
    final_unit = _current_unit(p2, target["origin_ref"])

    proof = service.build_proof(attached, config=COMPOSITOR)
    assert proof["status"] == "verified", proof["findings"]
    assert proof["version_ref"] == p2["current_version_ref"]
    refs = proof["references"]
    assert any(r["editorial_content_id"] == final_unit["id"] and len(r["revision_record_ids"]) == 2 for r in refs)
    assert all(r["proof_sha256"] == hashlib.sha256(service.proof_pdf(attached, proof["id"])).hexdigest() for r in refs)
    lines = _pdf_lines(service.proof_pdf(attached, proof["id"]))
    assert "The lamp glows brightly again." in lines
    assert "The lamp glows brightly." not in lines
    assert lines.count("The lamp glows.") == 1, "only the untouched twin keeps the C0 wording"
    assert service.projection(attached, config=COMPOSITOR)["proof_state"]["status"] == "current"

    rebuilt = service.build_proof(attached, config=COMPOSITOR)
    assert rebuilt["status"] == "verified"
    assert _pdf_lines(service.proof_pdf(attached, rebuilt["id"])) == lines, "rebuild must not re-enter the edit"


@needs_typst
def test_renderer_failure_keeps_accepted_version_and_retry_succeeds(attached):
    p0 = service.projection(attached, config=COMPOSITOR)
    _edit(attached, p0["units"][2], p0["current_version_ref"], "The lamp glows brightly.", "first")
    head = service.projection(attached, config=COMPOSITOR)["current_version_ref"]
    broken = CompositorConfig(python=COMPOSITOR.python, pythonpath=COMPOSITOR.pythonpath,
                              typst=str(Path(COMPOSITOR.typst).parent / "missing-typst"))
    failed = service.build_proof(attached, config=broken)
    assert failed["status"] == "failed"
    assert failed["message"] == service.PROOF_NOT_UPDATED
    assert "EDITORIAL_PROOF_TYPST_UNAVAILABLE" in {f["code"] for f in failed["findings"]}
    state = service.projection(attached, config=COMPOSITOR)
    assert state["current_version_ref"] == head, "manuscript stays saved after a renderer failure"
    assert state["proof_state"]["last_attempt"]["message"] == service.PROOF_NOT_UPDATED
    retried = service.build_proof(attached, config=COMPOSITOR)
    assert retried["status"] == "verified" and retried["version_ref"] == head


@needs_typst
def test_new_edit_marks_previous_proof_stale(attached):
    p0 = service.projection(attached, config=COMPOSITOR)
    target = p0["units"][2]
    _edit(attached, target, p0["current_version_ref"], "The lamp glows brightly.", "first")
    assert service.build_proof(attached, config=COMPOSITOR)["status"] == "verified"
    p1 = service.projection(attached, config=COMPOSITOR)
    _edit(attached, _current_unit(p1, target["origin_ref"]), p1["current_version_ref"], "The lamp glows softly.", "second")
    state = service.projection(attached, config=COMPOSITOR)["proof_state"]
    assert state["status"] == "stale" and state["proof_version_ref"] == p1["current_version_ref"]


@needs_typst
def test_integrated_history_survives_export_and_restore(attached, tmp_path):
    p0 = service.projection(attached, config=COMPOSITOR)
    target = p0["units"][2]
    _edit(attached, target, p0["current_version_ref"], "The lamp glows brightly.", "first")
    p1 = service.projection(attached, config=COMPOSITOR)
    _edit(attached, _current_unit(p1, target["origin_ref"]), p1["current_version_ref"], "The lamp glows brightly again.", "second")
    proof = service.build_proof(attached, config=COMPOSITOR)
    assert proof["status"] == "verified"
    source_state = service.projection(attached, config=COMPOSITOR)

    bundle = tmp_path / "bundle"
    manifest = export_workspace_bundle(attached, bundle, generated_at=NOW, workspace_id="w")
    assert manifest["wbs_version"] == "1.2"
    assert manifest["required_capabilities"] == ["publication-authoring-v0"]
    assert manifest["counts"]["authoring_accepted_versions"] == 2
    zip_a = build_workspace_zip(attached, generated_at=NOW, workspace_id="w")
    assert zip_a == build_workspace_zip(attached, generated_at=NOW, workspace_id="w")

    restored = tmp_path / "restored" / "hermeneia.db"
    restore_workspace(restored, bundle)
    assert service.verify_history(restored, config=COMPOSITOR)["current_version_ref"] == source_state["current_version_ref"]
    after = service.projection(restored, config=COMPOSITOR)
    for key in ("current_version_ref", "current_version_label", "versions"):
        assert after[key] == source_state[key]
    assert [u["lineage"] for u in after["units"]] == [u["lineage"] for u in source_state["units"]]
    assert service.proof_pdf(restored, proof["id"]) == service.proof_pdf(attached, proof["id"])
    assert _forensic_rows(restored) == _forensic_rows(attached)

    # The restored work keeps being revisable from the restored head.
    current = _current_unit(after, target["origin_ref"])
    _edit(restored, current, after["current_version_ref"], "The lamp glows at last.", "third")
    assert service.projection(restored, config=COMPOSITOR)["current_version_label"] == "N+3"


@needs_compositor
def test_restore_refuses_missing_or_tampered_authoring_artifacts(attached, tmp_path):
    p0 = service.projection(attached, config=COMPOSITOR)
    _edit(attached, p0["units"][2], p0["current_version_ref"], "The lamp glows brightly.", "first")
    bundle = tmp_path / "bundle"
    export_workspace_bundle(attached, bundle, generated_at=NOW, workspace_id="w")
    receipt = next(p for p in (bundle / "publication" / "files").rglob("*.json")
                   if '"idempotency_key"' in p.read_text())

    tampered = tmp_path / "tampered"
    shutil.copytree(bundle, tampered)
    target = tampered / receipt.relative_to(bundle)
    target.write_text(target.read_text().replace("hermeneia", "hermeneiA", 1))
    with pytest.raises(RestoreError, match="hash check"):
        restore_workspace(tmp_path / "t" / "hermeneia.db", tampered)

    missing = tmp_path / "missing"
    shutil.copytree(bundle, missing)
    (missing / receipt.relative_to(bundle)).unlink()
    with pytest.raises(RestoreError, match="missing"):
        restore_workspace(tmp_path / "m" / "hermeneia.db", missing)

    unlisted = tmp_path / "unlisted"
    shutil.copytree(bundle, unlisted)
    (unlisted / "publication" / "files" / "stray.json").write_text("{}")
    with pytest.raises(RestoreError, match="unlisted"):
        restore_workspace(tmp_path / "u" / "hermeneia.db", unlisted)


@needs_compositor
def test_restore_publication_write_failure_leaves_no_active_state_and_retry_succeeds(attached, tmp_path, monkeypatch):
    """A destination write failure mid-install must not orphan accepted authoring rows."""
    import hermeneia.workspace.restore as restore_module

    p0 = service.projection(attached, config=COMPOSITOR)
    _edit(attached, p0["units"][2], p0["current_version_ref"], "The lamp glows brightly.", "first")
    head = service.projection(attached, config=COMPOSITOR)["current_version_ref"]
    bundle = tmp_path / "bundle"
    export_workspace_bundle(attached, bundle, generated_at=NOW, workspace_id="w")

    real_copy = restore_module._copy_publication_file
    calls = {"n": 0}

    def failing_copy(src, dest):
        calls["n"] += 1
        if calls["n"] == 3:  # fail after some files were already written
            raise OSError(28, "No space left on device (injected)")
        return real_copy(src, dest)

    monkeypatch.setattr(restore_module, "_copy_publication_file", failing_copy)
    target = tmp_path / "restored" / "hermeneia.db"
    with pytest.raises(RestoreError, match="publication"):
        restore_workspace(target, bundle)
    assert calls["n"] == 3

    conn = sqlite3.connect(target)
    assert conn.execute("SELECT COUNT(*) FROM publication_works").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM authoring_outcomes").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 0
    conn.close()
    leftovers = sorted(p.name for p in target.parent.iterdir())
    assert not any("publication" in name for name in leftovers), leftovers

    monkeypatch.setattr(restore_module, "_copy_publication_file", real_copy)
    restore_workspace(target, bundle)
    assert service.verify_history(target, config=COMPOSITOR)["current_version_ref"] == head
    assert service.projection(target, config=COMPOSITOR)["current_version_ref"] == head


@needs_compositor
def test_export_refuses_incomplete_integrated_backup(attached, tmp_path):
    p0 = service.projection(attached, config=COMPOSITOR)
    _edit(attached, p0["units"][2], p0["current_version_ref"], "The lamp glows brightly.", "first")
    conn = sqlite3.connect(attached)
    relpath = conn.execute("SELECT relpath FROM publication_artifacts WHERE kind='version'").fetchone()[0]
    work_id = conn.execute("SELECT id FROM publication_works").fetchone()[0]
    conn.close()
    artifact = store.work_dir(attached, work_id) / relpath
    artifact.write_bytes(artifact.read_bytes() + b" ")
    from hermeneia.workspace.export import PublicationExportError
    with pytest.raises(PublicationExportError):
        export_workspace_bundle(attached, tmp_path / "bundle", generated_at=NOW, workspace_id="w")


@needs_compositor
def test_http_routes_drive_the_bounded_flow(attached):
    app = create_app(db_path=attached)
    app.config["HERMENEIA_COMPOSITOR_CONFIG"] = COMPOSITOR
    client = app.test_client()
    state = client.get("/api/authoring/work").get_json()
    unit = state["units"][2]
    draft = client.post("/api/authoring/drafts", json={"unit_id": unit["id"], "parent_version_ref": state["current_version_ref"], "text": "The lamp glo"})
    assert draft.status_code == 201
    assert client.get("/api/authoring/work").get_json()["units"][2]["draft"] == "The lamp glo"
    proposal = client.post("/api/authoring/proposals", json={
        "unit_id": unit["id"], "parent_version_ref": state["current_version_ref"],
        "text": "The lamp glows warmly.", "rationale": "warmth"}).get_json()
    assert proposal["validation_status"] == "valid"
    missing_rationale = client.post(f"/api/authoring/proposals/{proposal['id']}/decision", json={"decision": "approved", "rationale": ""})
    assert missing_rationale.status_code == 400
    decided = client.post(f"/api/authoring/proposals/{proposal['id']}/decision", json={"decision": "approved", "rationale": "yes"})
    assert decided.status_code == 201 and decided.get_json()["outcome"]["status"] == "accepted"
    assert client.get("/api/authoring/work").get_json()["current_version_label"] == "N+1"


def _pdf_lines(pdf: bytes) -> list[str]:
    """Extract proof text with the Compositor environment's own PDF reader."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if COMPOSITOR.pythonpath:
        env["PYTHONPATH"] = COMPOSITOR.pythonpath
    script = (
        "import sys, pypdfium2 as p\n"
        "d = p.PdfDocument(sys.stdin.buffer.read())\n"
        "print('\\n'.join(d[i].get_textpage().get_text_range() for i in range(len(d))))\n"
    )
    proc = subprocess.run([COMPOSITOR.python, "-c", script], input=pdf, env=env, capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-1000:]
    return [line.strip() for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]
