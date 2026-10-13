"""P10 (#252): the Blueprint dependency chain round-trips through WBS with closure, or is declared unsupported.

The committed laboratory dataset is reproduced:
- lawful round trips with equal rows, Lineage, P1 decisions and receipt
  verdicts;
- export-side declarations;
- restore-side refusals.

Chain export is gated, default off, so a default export is unchanged and P8's
unsupported declaration stands until the owner opens the P8 portability gate.
Synthetic workspaces only; P5 isolation; no network or live model.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3
import zipfile

import pytest

import blueprint_chain_lab as chain_lab
import synthetic_study_lab as lab
from hermeneia.blueprint_proposals import PORTABILITY_REASON
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import build_bundle_files
from hermeneia.workspace.blueprint_chain import CAPABILITY, COVERAGE_KEY, FILES, export_chain
from hermeneia.workspace.restore import SUPPORTED_CAPABILITIES, preview_restore

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "research" / "blueprint_chain_portability" / "v1"


@pytest.fixture(scope="module")
def results():
    return json.loads(json.dumps(chain_lab.run(), sort_keys=True, ensure_ascii=False))


def test_committed_dataset_and_summary_are_reproduced(results):
    assert json.loads((RESULTS / "results.json").read_text()) == results
    assert (RESULTS / "summary.md").read_text() == chain_lab.summary_markdown(results)


def test_every_case_meets_the_frozen_contract(results):
    assert results["aggregate"] == {"lawful": {"cases": 9, "all_checks_passed": 9},
                                    "export_adversarial": {"cases": 3, "all_checks_passed": 3},
                                    "restore_adversarial": {"cases": 10, "all_checks_passed": 10}}
    by_id = {case["case_id"]: case for case in results["cases"]}
    assert by_id["L5_p8_exact_acceptance"]["lineage_chain"]["narrative_blueprints|recorded|accepted_model"] == 1
    assert by_id["L6_p8_edit_and_accept_revision"]["lineage_chain"]["blueprint_proposal_acceptances|recorded|human"] == 1
    assert by_id["L3_e10_proposals_accepted_pending_rejected"]["lineage_chain"]["interpretations|recorded|accepted_model"] == 1
    assert by_id["L7_legacy_ai_generated_and_extracted_rows"]["blueprint_sources"] == ["ai-generated", "extracted"]


def _study(tmp_path: Path) -> Path:
    db = tmp_path / "ws" / "workspace.db"
    with lab.isolated(tmp_path):
        corpus = chain_lab._corpus()
        chain_lab._FakeOllamaClient.models = [corpus["extraction_model"]]
        ws = chain_lab.proposal_lab.Workspace(corpus, tmp_path)
        chain_lab.build_l5(ws, corpus)
    return db


def test_a_default_export_is_unchanged_and_keeps_p8_declared_unsupported(tmp_path):
    db = _study(tmp_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        default = build_bundle_files(conn, generated_at=chain_lab.GENERATED_AT, workspace_id="w")
    finally:
        conn.close()
    manifest = json.loads(default["manifest.json"])
    assert not set(FILES.values()) & set(default) and CAPABILITY not in manifest.get("required_capabilities", [])
    assert "declared_unsupported" not in manifest
    bundle = tmp_path / "bundle"
    for path, data in default.items():
        (bundle / path).parent.mkdir(parents=True, exist_ok=True)
        (bundle / path).write_bytes(data)
    coverage = preview_restore(tmp_path / "restored.db", bundle)["coverage"]
    assert coverage["blueprint_proposal_acceptances"] == {"status": "unsupported", "reason": PORTABILITY_REASON}
    assert coverage[COVERAGE_KEY]["status"] == "unsupported"


def test_the_web_export_gate_is_off_by_default_and_opens_only_by_configuration(tmp_path, monkeypatch):
    db = _study(tmp_path)
    monkeypatch.delenv("HERMENEIA_WBS_BLUEPRINT_CHAIN", raising=False)
    app = create_app(db_path=db, credential_store=lab._NoCredentials())
    assert app.config["WBS_BLUEPRINT_CHAIN"] == "disabled"
    names = zipfile.ZipFile(io.BytesIO(app.test_client().get("/api/workspace/export").data)).namelist()
    assert not any(name.endswith(FILES["blueprint_proposal_acceptances"]) for name in names)
    monkeypatch.setenv("HERMENEIA_WBS_BLUEPRINT_CHAIN", "enabled")
    enabled = create_app(db_path=db, credential_store=lab._NoCredentials())
    assert enabled.config["WBS_BLUEPRINT_CHAIN"] == "enabled"
    names = zipfile.ZipFile(io.BytesIO(enabled.test_client().get("/api/workspace/export").data)).namelist()
    assert {f"workspace/{path}" for path in FILES.values()} <= set(names)


def test_this_restorer_supports_the_capability():
    assert CAPABILITY in SUPPORTED_CAPABILITIES


def test_an_unmigrated_chain_schema_is_declared_not_narrowed(tmp_path):
    db = tmp_path / "workspace.db"
    SQLiteStore(db).close()
    conn = sqlite3.connect(db)
    try:
        conn.execute("ALTER TABLE interpretations DROP COLUMN steward_note")
        rows, declaration = export_chain(conn)
    finally:
        conn.close()
    assert rows is None and declaration["reason_code"] == "CHAIN_SCHEMA_INCOMPLETE"


def test_an_empty_current_store_exports_a_covered_empty_chain(tmp_path):
    db = tmp_path / "workspace.db"
    SQLiteStore(db).close()
    conn = sqlite3.connect(db)
    try:
        rows, declaration = export_chain(conn)
    finally:
        conn.close()
    assert declaration is None and set(rows) == set(FILES) and all(value == [] for value in rows.values())
