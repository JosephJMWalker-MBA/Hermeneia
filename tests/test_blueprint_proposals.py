"""P8 (#215): natural-language Blueprint proposals are governed candidates; only a steward decision commits.

The committed synthetic evaluation is reproduced. The production prompt is the
frozen policy. Acceptance receipts are append-only, tamper-evident and
Lineage-gated. A proposal source without a receipt proves no authorship.
Receipts never become P1/P2 evidence, and generation is enabled only
explicitly. Synthetic workspaces only; in-process fakes; no network.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3

import pytest

import blueprint_proposal_lab as proposal_lab
import synthetic_study_lab as lab
from hermeneia import blueprint_proposals as bp
from hermeneia.capabilities import evaluate_capabilities
from hermeneia.study_lineage import project_study_lineage
from hermeneia.web.app import create_app
from test_e10_vertical_slice_api import _FakeOllamaClient

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "research" / "blueprint_proposal" / "v1"
POLICY = json.loads((ROOT / "tests" / "fixtures" / "blueprint_proposal" / "v1" / "proposal_policy_v1.json").read_text())
CORPUS = proposal_lab.load()


@pytest.fixture(scope="module")
def results():
    return json.loads(json.dumps(proposal_lab.run(), sort_keys=True, ensure_ascii=False))


@pytest.fixture
def accepted(tmp_path):
    """A workspace with one exact-accepted proposal (case P05), inside the laboratory isolation."""
    context = lab.isolated(tmp_path)
    context.__enter__()
    _FakeOllamaClient.models = [CORPUS["extraction_model"]]
    case = next(c for c in CORPUS["cases"] if c["case_id"] == "P05_exact_accept")
    ws = proposal_lab.Workspace(CORPUS, tmp_path)
    for op in case["setup"]:
        ws.apply(op)
    candidate = proposal_lab.propose(ws, case["generate"], case["generate"]["script"], CORPUS["extraction_model"])[0].get_json()
    receipt = proposal_lab.decide(ws, candidate, {"decision": "accept"}).get_json()
    yield ws, receipt
    context.__exit__(None, None, None)


def test_committed_dataset_and_summary_are_reproduced(results):
    assert json.loads((RESULTS / "results.json").read_text()) == results
    assert (RESULTS / "summary.md").read_text() == proposal_lab.summary_markdown(results)
    assert results["aggregate"] == {"cases": {"items": 15, "all_checks_passed": 15},
                                    "further_checks": {"items": 4, "all_checks_passed": 4}}


def test_production_prompt_is_the_frozen_policy():
    assert list(bp.HEADER) == POLICY["header"] and list(bp.RULES) == POLICY["rules"]
    assert (bp.INTENT_INTRO, bp.GOVERNING_INTRO, bp.OBSERVATIONS_INTRO, bp.INTERPRETATIONS_INTRO, bp.NONE_LINE) == (
        POLICY["intent_intro"], POLICY["governing_intro"], POLICY["observations_intro"], POLICY["interpretations_intro"], POLICY["none_line"])
    assert (bp.OBSERVATION_LINE, bp.INTERPRETATION_LINE, bp.AUTHORSHIP_LABELS) == (
        POLICY["observation_line"], POLICY["interpretation_line"], POLICY["authorship_labels"])
    assert (bp.PREDECESSOR_INTRO, list(bp.PREDECESSOR_LINES), bp.RETURN_INTRO, bp.CREATE_SHAPE, bp.REVISE_SHAPE, bp.RULES_INTRO, bp.REVISE_RULE) == (
        POLICY["predecessor_intro"], POLICY["predecessor_lines"], POLICY["return_intro"], POLICY["create_shape"],
        POLICY["revise_shape"], POLICY["rules_intro"], POLICY["revise_rule"])
    assert (bp.POLICY_VERSION, bp.PROMPT_VERSION, bp.BASIS_POLICY, bp.MAX_OBSERVATIONS, bp.MAX_INTERPRETATIONS, bp.MAX_SECTIONS) == (
        POLICY["policy_version"], POLICY["prompt_version"], POLICY["basis_policy"], POLICY["basis_limits"]["observations"],
        POLICY["basis_limits"]["interpretations"], POLICY["section_limits"]["max"])


def test_receipts_are_append_only_and_tamper_evident(accepted, tmp_path):
    ws, receipt = accepted
    conn = sqlite3.connect(ws.db)
    for statement in (f"UPDATE {bp.TABLE} SET receipt_json = receipt_json", f"DELETE FROM {bp.TABLE}",
                      f"INSERT OR REPLACE INTO {bp.TABLE} SELECT * FROM {bp.TABLE}"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(statement)
    conn.close()
    tampered = tmp_path / "tampered.db"
    shutil.copy(ws.db, tampered)
    conn = sqlite3.connect(tampered)
    conn.execute(f"DROP TRIGGER {bp.TABLE}_no_update")
    conn.execute(f"UPDATE {bp.TABLE} SET receipt_json = replace(receipt_json, '\"edited\":false', '\"edited\":true')")
    conn.commit()
    lineage = project_study_lineage(conn)
    assert not any(i["record"]["table"] == bp.TABLE for i in lineage["items"])
    assert {"record": {"table": bp.TABLE, "key": {"id": receipt["id"]}}, "state": "invalid",
            "reason_code": "BLUEPRINT_PROPOSAL_ACCEPTANCE_INVALID"} in lineage["coverage"]["diagnostics"]
    assert bp.verify_receipt(conn, receipt["id"])["record_integrity"] == "invalid"
    conn.close()


def test_receipt_leaves_lineage_when_an_exposed_source_is_excluded(accepted):
    ws, receipt = accepted
    assert ws.lineage(bp.TABLE, receipt["id"])["authorship"] == "accepted_model"
    ws.apply({"op": "exclude_document", "doc": "A"})
    assert ws.lineage(bp.TABLE, receipt["id"]) is None
    assert ws.client.get(f"/api/blueprint/proposals/acceptances/{receipt['id']}").status_code == 404
    assert ws.count(bp.TABLE) == 1  # append-only history is preserved, only its projection is withheld


def test_a_proposal_source_without_a_receipt_proves_no_authorship(accepted):
    ws, receipt = accepted
    conn = sqlite3.connect(ws.db)
    conn.execute("INSERT INTO narrative_blueprints (id, title, thesis, sections, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                 ("forged-blueprint", "Forged", "No receipt.", "[]", "proposal-accepted", "2026-10-08T00:00:00+00:00"))
    conn.commit()
    conn.close()
    assert ws.lineage("narrative_blueprints", "forged-blueprint")["authorship"] == "unknown"
    assert ws.lineage("narrative_blueprints", receipt["result"]["resulting_blueprint_id"])["authorship"] == "accepted_model"


def test_receipts_are_never_p1_evidence_and_never_change_p1_decisions(accepted, tmp_path):
    # A receipt legitimately proves its Blueprint's authorship label (accepted_model vs unknown); it is
    # never itself P1/P2 evidence, and no availability, status, reason or prerequisite depends on it.
    ws, _receipt = accepted

    def capabilities(db):
        conn = lab._read_only(db)
        try:
            rows = evaluate_capabilities(project_study_lineage(conn), current_state={})["capabilities"]
        finally:
            conn.close()
        assert not any(ref["record"]["table"] == bp.TABLE for row in rows for ref in row["evidence_refs"])
        return [{k: v for k, v in row.items() if k != "evidence_refs"} for row in rows]

    without = tmp_path / "without-receipts.db"
    shutil.copy(ws.db, without)
    conn = sqlite3.connect(without)
    conn.execute(f"DROP TABLE {bp.TABLE}")
    conn.commit()
    conn.close()
    assert capabilities(ws.db) == capabilities(without)


def test_generation_is_disabled_unless_explicitly_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMENEIA_BLUEPRINT_PROPOSALS", raising=False)
    assert create_app(db_path=tmp_path / "a" / "w.db").config["BLUEPRINT_PROPOSAL_GENERATION"] == "disabled"
    monkeypatch.setenv("HERMENEIA_BLUEPRINT_PROPOSALS", "experimental")
    assert create_app(db_path=tmp_path / "b" / "w.db").config["BLUEPRINT_PROPOSAL_GENERATION"] == "experimental"
