"""
In-workspace preparation for Authoring (issue #205, live-use slice).

workspace source -> Publication Compositor preparation -> verified prepared work -> S1 attach

The user prepares the workspace's already-ingested primary source; Hermeneia
never fabricates Compositor artifacts or bypasses Compositor verification. On
refusal the source and authoring state are unchanged and staging is removed.

Integration tests need the real Compositor environment plus a pinned Typst to
build a genuine synthetic PDF (HERMENEIA_COMPOSITOR_PYTHON/PATH, HERMENEIA_TYPST);
without them they skip with an explicit reason. No manuscript text is used.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from hermeneia.authoring import service, store
from hermeneia.authoring.service import AuthoringError, CompositorConfig
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

BUILDER = Path(__file__).parent.parent / "hermeneia" / "authoring" / "synthetic_work.py"
BASE = CompositorConfig.from_env()
needs_real = pytest.mark.skipif(
    not (BASE.configured and BASE.typst and Path(BASE.typst).is_file()),
    reason="Publication Compositor environment and pinned typst not configured",
)

SOURCE_TYP = """#set page(width: 432pt, height: 648pt, margin: 54pt)
#set text(font: "Synthetic Test Serif", size: 10pt)
#heading[Synthetic Heading]
The lamp glows.

The lamp glows.

A closing paragraph.
"""


def _compositor_env() -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if BASE.pythonpath:
        env["PYTHONPATH"] = f"{BASE.pythonpath}{os.pathsep}{BUILDER.parent}"
    return env


@pytest.fixture(scope="session")
def operator_config(tmp_path_factory) -> dict:
    """An operator-supplied saved profile and pinned font, built with Compositor's models."""
    if not (BASE.configured and BASE.typst):
        pytest.skip("Publication Compositor environment and pinned typst not configured")
    root = tmp_path_factory.mktemp("operator")
    (root / "fonts").mkdir()
    script = f"""
import synthetic_work as sw
from pathlib import Path
from publication_compositor.construction import PresentationStyleToken
from publication_compositor.profiles import StyleRule
sw._font(Path({str(root / 'fonts' / 'SyntheticTestSerif-Regular.ttf')!r}))
p = sw._profile()
Path({str(root / 'profile-body-only.json')!r}).write_text(p.model_dump_json())
extra = StyleRule(style_token=PresentationStyleToken.RHETORICAL_PARAGRAPH, font_families=(sw.FONT_FAMILY,),
                  font_size_pt=10.0, leading_em=0.2, weight="regular", italic=False, alignment="left")
Path({str(root / 'profile.json')!r}).write_text(p.model_copy(update={{"styles": (*p.styles, extra)}}).model_dump_json())
"""
    proc = subprocess.run([BASE.python, "-c", script], env=_compositor_env(), capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    (root / "source.typ").write_text(SOURCE_TYP)
    proc = subprocess.run([BASE.typst, "compile", "--font-path", str(root / "fonts"), "--ignore-system-fonts",
                           str(root / "source.typ"), str(root / "source.pdf")], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return {"root": root, "pdf": root / "source.pdf", "fonts": root / "fonts",
            "profile": root / "profile.json", "profile_body_only": root / "profile-body-only.json"}


def _config(operator: dict, *, profile: Path | None = None) -> CompositorConfig:
    return replace(BASE, profile=str(profile or operator["profile"]), fonts=str(operator["fonts"]))


def _workspace_with_primary_source(tmp_path: Path, pdf: Path, name: str = "source_upload.pdf") -> Path:
    """Ingest the PDF through Hermeneia's own compiler, as an upload would."""
    from hermeneia.compiler.compiler import Compiler

    ws = tmp_path / "ws"
    (ws / "uploads").mkdir(parents=True, exist_ok=True)
    upload = ws / "uploads" / name
    shutil.copyfile(pdf, upload)
    compiler = Compiler(db_path=ws / "hermeneia.db", build_dir=ws)
    compiler.compile(upload)
    compiler.close()
    return ws / "hermeneia.db"


def _authoring_rows(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        return sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in store.AUTHORING_TABLES)
    finally:
        conn.close()


def _evidence_digest(db: Path) -> str:
    conn = sqlite3.connect(db)
    h = hashlib.sha256()
    for table in ("source_documents", "source_extractions", "observations"):
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1"):
            h.update(repr(row).encode())
    conn.close()
    return h.hexdigest()


def _no_staging(db: Path) -> bool:
    return not any(name.startswith(".publication") for name in os.listdir(db.parent))


# ── Always-run contract tests ───────────────────────────────────────────────


def test_preparation_refuses_without_explicit_profile_and_fonts(tmp_path):
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    config = CompositorConfig(python="/usr/bin/python3", pythonpath=None, typst=None)
    with pytest.raises(AuthoringError) as exc:
        service.prepare_primary_source(db, document_id=None, actor="author", config=config)
    assert exc.value.code == "PREPARATION_NOT_CONFIGURED"
    assert "HERMENEIA_COMPOSITOR_PROFILE" in exc.value.message and "HERMENEIA_COMPOSITOR_FONTS" in exc.value.message


def test_unattached_projection_lists_primary_sources_read_only(tmp_path):
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    conn = sqlite3.connect(db)
    for doc_id, role in (("a" * 64, "primary"), ("b" * 64, "reference")):
        conn.execute(
            "INSERT INTO source_documents (id, original_filename, file_hash, total_pages, registered_at, "
            "compiler_version, source_role, excluded_from_analysis) VALUES (?,?,?,?,?,?,?,0)",
            (doc_id, f"{role}.pdf", doc_id, 3, "2026-09-14T00:00:00+00:00", "t", role),
        )
    conn.commit()
    conn.close()
    before = db.read_bytes()
    body = create_app(db_path=db).test_client().get("/api/authoring/work").get_json()
    assert body["attached"] is False
    assert [c["filename"] for c in body["preparation"]["candidates"]] == ["primary.pdf"]
    assert db.read_bytes() == before, "GET must not write"


def test_preparation_refuses_ambiguous_or_missing_source_bytes(tmp_path):
    db = tmp_path / "ws" / "hermeneia.db"
    SQLiteStore(db).close()
    profile = tmp_path / "profile.json"
    profile.write_text("{}")
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    config = CompositorConfig(python="/usr/bin/python3", pythonpath=None, typst=None, profile=str(profile), fonts=str(fonts))
    conn = sqlite3.connect(db)
    for doc_id in ("a" * 64, "b" * 64):
        conn.execute(
            "INSERT INTO source_documents (id, original_filename, file_hash, total_pages, registered_at, "
            "compiler_version, source_role, excluded_from_analysis) VALUES (?,?,?,?,?,?,?,0)",
            (doc_id, f"{doc_id[0]}.pdf", doc_id, 3, "2026-09-14T00:00:00+00:00", "t", "primary"),
        )
    conn.commit()
    conn.close()
    with pytest.raises(AuthoringError) as ambiguous:
        service.prepare_primary_source(db, document_id=None, actor="author", config=config)
    assert ambiguous.value.code == "AMBIGUOUS_PRIMARY_SOURCE" and len(ambiguous.value.findings) == 2
    with pytest.raises(AuthoringError) as missing:
        service.prepare_primary_source(db, document_id="a" * 64, actor="author", config=config)
    assert missing.value.code == "SOURCE_BYTES_NOT_FOUND", "bytes are located by hash, never guessed by filename"
    with pytest.raises(AuthoringError) as foreign:
        service.prepare_primary_source(db, document_id="c" * 64, actor="author", config=config)
    assert foreign.value.code == "NOT_A_PRIMARY_SOURCE"
    assert _no_staging(db)


# ── Real Compositor preparation of a genuine synthetic PDF ──────────────────


@needs_real
def test_prepare_primary_source_attaches_verified_work_and_enters_authoring(tmp_path, operator_config):
    db = _workspace_with_primary_source(tmp_path, operator_config["pdf"])
    upload = next((db.parent / "uploads").iterdir())
    source_sha = hashlib.sha256(upload.read_bytes()).hexdigest()
    evidence = _evidence_digest(db)
    config = _config(operator_config)

    result = service.prepare_primary_source(db, document_id=None, actor="author", config=config)
    assert result["prepared"] is True and result["source_document_id"] == source_sha
    stages = {s["stage"]: s for s in result["stages"]}
    assert stages["canonicalize"]["export_ready"] is True and stages["canonicalize"]["unresolved"] == 0

    projection = service.projection(db, config=config)
    assert projection["attached"] and projection["current_version_label"].startswith("C0")
    assert [u["text"] for u in projection["units"]] == [
        "Synthetic Heading", "The lamp glows.", "The lamp glows.", "A closing paragraph."]
    assert service.verify_history(db, config=config)["accepted_versions"] == 0

    conn = sqlite3.connect(db)
    work = conn.execute("SELECT inputs_json, synthetic, label FROM publication_works").fetchone()
    inputs = json.loads(work[0])
    provenance = json.loads(store.read_artifact(conn, db, inputs["preparation_provenance"]["sha256"]))
    conn.close()
    assert work[1] == 0 and work[2] == "source_upload.pdf"
    assert provenance["source_sha256"] == provenance["source_ir_source_pdf_sha256"] == source_sha
    assert provenance["workspace_source_document_id"] == source_sha
    assert provenance["prepared_by"] == "author"
    assert provenance["profile_sha256"] == hashlib.sha256(operator_config["profile"].read_bytes()).hexdigest()
    assert provenance["compositor_facade_sha256"] == json.loads(
        sqlite3.connect(db).execute("SELECT facade_pin_json FROM publication_works").fetchone()[0])["facade_sha256"]

    assert hashlib.sha256(upload.read_bytes()).hexdigest() == source_sha, "source bytes must be unchanged"
    assert _evidence_digest(db) == evidence, "Hermeneia source evidence must be unchanged"
    assert _no_staging(db)

    # The prepared work is a normal S1 work: revisable, with a verified proof.
    unit = projection["units"][2]
    proposal = service.propose(db, unit_id=unit["id"], parent_version_ref=projection["current_version_ref"],
                               new_text="The lamp glows brightly.", rationale="prepared edit", actor="author", config=config)
    decided = service.decide(db, proposal_id=proposal["id"], decision="approved", rationale="ok", actor="author", config=config)
    assert decided["outcome"]["status"] == "accepted"
    assert service.build_proof(db, config=config)["status"] == "verified"

    with pytest.raises(AuthoringError) as again:
        service.prepare_primary_source(db, document_id=None, actor="author", config=config)
    assert again.value.code == "WORK_ALREADY_ATTACHED"


@needs_real
def test_compositor_refusal_surfaces_findings_and_leaves_state_unchanged(tmp_path, operator_config):
    db = _workspace_with_primary_source(tmp_path, operator_config["pdf"])
    upload = next((db.parent / "uploads").iterdir())
    source_sha = hashlib.sha256(upload.read_bytes()).hexdigest()
    evidence = _evidence_digest(db)
    config = _config(operator_config, profile=operator_config["profile_body_only"])

    with pytest.raises(AuthoringError) as exc:
        service.prepare_primary_source(db, document_id=None, actor="author", config=config)
    assert exc.value.code == "PREPARATION_PROFILE_REFUSED" and exc.value.stage == "profile"
    assert "MISSING_PROFILE_STYLE_TOKEN" in {f["code"] for f in exc.value.findings}, "Compositor findings verbatim"
    assert _authoring_rows(db) == 0
    assert not (db.parent / "publication").exists()
    assert _no_staging(db)
    assert hashlib.sha256(upload.read_bytes()).hexdigest() == source_sha
    assert _evidence_digest(db) == evidence
    assert service.projection(db, config=config)["attached"] is False


@needs_real
def test_prepare_route_reports_refusal_with_stage_and_findings(tmp_path, operator_config):
    """The route starts a single-flight operation (202); its status carries Compositor's verdict."""
    from hermeneia.authoring import preparation_job

    db = _workspace_with_primary_source(tmp_path, operator_config["pdf"])
    app = create_app(db_path=db)
    client = app.test_client()
    app.config["HERMENEIA_COMPOSITOR_CONFIG"] = _config(operator_config, profile=operator_config["profile_body_only"])
    response = client.post("/api/authoring/prepare", json={})
    assert response.status_code == 202
    preparation_job.wait(db, timeout=300)
    refused = client.get("/api/authoring/prepare/status").get_json()
    assert refused["state"] == "refused"
    assert refused["code"] == "PREPARATION_PROFILE_REFUSED" and refused["stage"] == "profile"
    assert "MISSING_PROFILE_STYLE_TOKEN" in {f["code"] for f in refused["findings"]}

    app.config["HERMENEIA_COMPOSITOR_CONFIG"] = _config(operator_config)
    ok = client.post("/api/authoring/prepare", json={})
    assert ok.status_code == 202
    preparation_job.wait(db, timeout=300)
    done = client.get("/api/authoring/prepare/status").get_json()
    assert done["state"] == "succeeded" and done["work_id"]
    assert client.get("/api/authoring/work").get_json()["attached"] is True
