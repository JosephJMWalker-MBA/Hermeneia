"""P7 Layer 2 (#215): governed comparison candidates and append-only accepted comparisons.

The committed Layer 2 evaluation is reproduced. Layer 1 is byte-identical to
its verified commit. Replay views converge. Steward authoring (option (b))
uses the same canonical type. Normalization never admits untraced text.
Accepted records are immutable and tamper-evident, never P1/P2 evidence, and
restore all-or-nothing. Synthetic workspaces; in-process fakes; no network.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

import perspective_comparison_candidate_lab as candidate_lab
import synthetic_study_lab as lab
from hermeneia.accepted_perspective_comparisons import (
    TABLE, make_steward_authored_record, store_accepted_comparison, verify_accepted_comparison,
)
from hermeneia.capabilities import evaluate_capabilities
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
from hermeneia.perspective_comparison_candidates import (
    ExtractionRefused, candidate_inputs, normalize, parse_output, structure_from_edit, view_from_receipts,
)
from hermeneia.study_lineage import project_study_lineage
from hermeneia.workspace import RestoreError, export_workspace_bundle, read_bundle, restore_workspace
from test_e10_vertical_slice_api import _CapturingProvider

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "research" / "perspective_comparison_candidate" / "v1"
LAYER1_SHA256 = "81f76b1a7491b72bb6f486ee0f41280965eb5e1a68c6bb966d1a6ff35d9cedb8"  # 43f7327
CORPUS, CASES = candidate_lab.load()
LAYER1 = candidate_lab.layer1_lab.load_corpus(ROOT / CORPUS["layer1_corpus"])


@pytest.fixture(scope="module")
def results():
    return json.loads(json.dumps(candidate_lab.run(), sort_keys=True, ensure_ascii=False))


@pytest.fixture
def study(tmp_path):
    def build(case_id: str):
        context = candidate_lab._isolated(tmp_path, CORPUS, LAYER1)
        request_cleanup.append(context)
        return candidate_lab.Study(LAYER1, CASES[case_id], tmp_path / case_id)
    request_cleanup: list = []
    yield build
    for context in request_cleanup:
        context.__exit__(None, None, None)


def _accept_faithful(s):
    order = s.case["expected"]["order"]
    candidate = s.propose(s.wire(candidate_lab.faithful_script(s.case["reference"], order)), CORPUS["extraction_model"]).get_json()
    response = s.client.post(f"/api/perspective/comparison/candidates/{candidate['candidate_id']}/accept",
                             json={"decision": "accept", "candidate_id": candidate["candidate_id"]})
    assert response.status_code == 201, response.get_json()
    return candidate, response.get_json()


def _inputs(db, receipt_ids):
    conn = lab._read_only(db)
    try:
        return candidate_inputs(conn, read_perspective_achievement_evidence(conn), receipt_ids)
    finally:
        conn.close()


def test_committed_dataset_and_summary_are_reproduced(results):
    assert json.loads((RESULTS / "results.json").read_text()) == results
    assert (RESULTS / "summary.md").read_text() == candidate_lab.summary_markdown(results)


def test_every_item_meets_its_frozen_expectation(results):
    aggregate = results["aggregate"]
    for kind, total in (("faithful", 13), ("layer1_refusal", 2), ("adversarial", 10), ("acceptance", 9)):
        assert aggregate[kind] == {"items": total, "all_checks_passed": total}, kind
    # Paraphrase-as-disagreement and silent-minority erasure are traceable; only scoring and the steward catch them.
    assert aggregate["adversarial_visible_only_in_score"] == ["ADV3_paraphrase_called_disagreement",
                                                              "ADV4a_minority_erased_by_absence"]


def test_layer1_is_byte_identical_to_its_verified_commit():
    assert hashlib.sha256((ROOT / "hermeneia" / "perspective_comparison.py").read_bytes()).hexdigest() == LAYER1_SHA256


def test_replay_view_from_receipts_equals_the_layer1_view(study):
    s = study("C13_overlapping_evidence_changed_highlight")
    inputs = _inputs(s.db, s.receipt_ids)
    assert view_from_receipts(inputs["receipts"]) == inputs["view"]


def test_normalization_never_admits_untraced_text(study):
    s = study("C08_two_to_one_minority")
    view = _inputs(s.db, s.receipt_ids)["view"]
    wire = json.loads(s.wire(candidate_lab.faithful_script(s.case["reference"], ["R1", "R2", "R3"])))
    wire["propositions"][0]["positions"][2]["quote"] = "a"  # occurs more than once: ambiguous, so unknown
    wire["propositions"][0]["positions"][0].update(stance="does_not_address")  # quote kept: contradictory
    structure = normalize(parse_output("```json\n" + json.dumps(wire) + "\n```", view), view)
    kinds = sorted(item["kind"] for item in structure["untraceable"])
    assert kinds == ["contradictory_position", "untraceable_position"]
    assert [p["stance"] for p in structure["propositions"][0]["positions"]] == ["unknown", "asserts", "unknown"]
    assert structure["relations"]["disagreement"] == []  # no traced dissent, so no manufactured disagreement
    with pytest.raises(ExtractionRefused) as refused:
        parse_output('{"propositions": [], "propositions": [], "assumptions": []}', view)
    assert refused.value.code == "EXTRACTION_OUTPUT_UNPARSEABLE"


def test_steward_authored_comparison_converges_on_the_same_type(study):
    s = study("C06_wording_only_difference")
    inputs = _inputs(s.db, s.receipt_ids)
    structure = structure_from_edit(candidate_lab._edit(s, s.case["reference"], "reference"), inputs["view"])
    record = make_steward_authored_record(inputs["binding"], structure, accepted_at="2026-10-08T00:00:00+00:00")
    conn = sqlite3.connect(s.db)
    conn.execute("BEGIN IMMEDIATE")
    store_accepted_comparison(conn, record)
    conn.commit()
    item = next(i for i in project_study_lineage(conn)["items"] if i["record"]["table"] == TABLE)
    assert (item["authorship"], item["record_data"]["origin"], item["record_data"]["decision"]) == ("human", "steward_authored", "author")
    assert verify_accepted_comparison(conn, record["id"]) == {
        "record_integrity": "valid", "receipt_closure": "verified", "layer1_replay": "verified",
        "candidate_replay": "not_applicable", "model_output": "preserved_not_replayed"}
    conn.close()


def test_accepted_records_are_immutable_and_tamper_evident(study, tmp_path):
    s = study("C01_same_conclusion_same_evidence")
    _candidate, record = _accept_faithful(s)
    conn = sqlite3.connect(s.db)
    for statement in (f"UPDATE {TABLE} SET comparison_json = comparison_json",
                      f"DELETE FROM {TABLE}",
                      f"INSERT OR REPLACE INTO {TABLE} SELECT * FROM {TABLE}"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(statement)
    conn.close()
    tampered = tmp_path / "tampered.db"
    shutil.copy(s.db, tampered)
    conn = sqlite3.connect(tampered)
    conn.execute(f"DROP TRIGGER {TABLE}_no_update")
    conn.execute(f"UPDATE {TABLE} SET comparison_json = replace(comparison_json, 'none_recorded', 'resolved')")
    conn.execute(f"UPDATE {TABLE} SET comparison_json = replace(comparison_json, '\"actor\":\"local_steward\"', '\"actor\":\"steward\"')")
    conn.commit()
    lineage = project_study_lineage(conn)
    assert not any(i["record"]["table"] == TABLE for i in lineage["items"])
    assert {"record": {"table": TABLE, "key": {"id": record["id"]}}, "state": "invalid",
            "reason_code": "ACCEPTED_COMPARISON_INVALID"} in lineage["coverage"]["diagnostics"]
    assert verify_accepted_comparison(conn, record["id"])["record_integrity"] == "invalid"
    conn.close()


def test_accepted_comparisons_are_never_p1_or_p2_evidence(study):
    s = study("C08_two_to_one_minority")

    def evaluation():
        conn = lab._read_only(s.db)
        try:
            return evaluate_capabilities(project_study_lineage(conn), current_state={})
        finally:
            conn.close()

    before = evaluation()
    _accept_faithful(s)
    assert evaluation()["capabilities"] == before["capabilities"]


def test_restore_is_all_or_nothing_and_old_bundles_are_unsupported(study, tmp_path):
    s = study("C03_different_conclusions_same_evidence")
    _accept_faithful(s)
    bundle = tmp_path / "bundle"
    manifest = export_workspace_bundle(s.db, bundle, generated_at=candidate_lab.EXPORT_TIME, workspace_id="synthetic-p7")
    assert "accepted-perspective-comparison-v1" in manifest["required_capabilities"]
    assert read_bundle(bundle)["coverage"][TABLE] == {
        "status": "covered", "extant_records": 1,
        "reason": "Extant accepted-comparison category covered; no complete historical claim."}
    tampered = tmp_path / "tampered"
    shutil.copytree(bundle, tampered)
    path = tampered / "study" / "accepted_perspective_comparisons.json"
    path.write_bytes(path.read_bytes().replace(b"none_recorded", b"resolved"))
    with pytest.raises(RestoreError):
        restore_workspace(tmp_path / "t1" / "workspace.db", tampered)
    orphan = tmp_path / "orphan"
    shutil.copytree(bundle, orphan)
    receipts = orphan / "study" / "perspective_executions.json"
    rows = json.loads(receipts.read_text())
    receipts.write_text(json.dumps(rows[:1]))
    data = json.loads((orphan / "manifest.json").read_text())
    for entry in data["files"]:
        if entry["path"] == "study/perspective_executions.json":
            entry["sha256"] = hashlib.sha256(receipts.read_bytes()).hexdigest()
    data["counts"]["perspective_execution_receipts"] = 1
    (orphan / "manifest.json").write_text(json.dumps(data))
    target = tmp_path / "t2" / "workspace.db"
    with pytest.raises(RestoreError):
        restore_workspace(target, orphan)
    conn = sqlite3.connect(target)
    assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM perspective_execution_receipts").fetchone()[0] == 0
    conn.close()
    legacy = tmp_path / "legacy"
    shutil.copytree(bundle, legacy)
    (legacy / "study" / "accepted_perspective_comparisons.json").unlink()
    data = json.loads((legacy / "manifest.json").read_text())
    data["files"] = [e for e in data["files"] if e["path"] != "study/accepted_perspective_comparisons.json"]
    data["required_capabilities"].remove("accepted-perspective-comparison-v1")
    del data["counts"][TABLE]
    (legacy / "manifest.json").write_text(json.dumps(data))
    assert read_bundle(legacy)["coverage"][TABLE]["status"] == "unsupported"


def test_provider_failure_and_refused_output_create_no_candidate(study):
    s = study("C01_same_conclusion_same_evidence")
    before = lab._logical_digest(s.db)
    _CapturingProvider.fail_on_render_calls = {len(_CapturingProvider.render_prompts) + 1}
    try:
        failed = s.propose("{}", CORPUS["extraction_model"])
    finally:
        _CapturingProvider.fail_on_render_calls = set()
    assert (failed.status_code, failed.get_json()["code"]) == (502, "PROVIDER_FAILED")
    refused = s.propose('{"propositions": [], "assumptions": [], "consensus": true}', CORPUS["extraction_model"])
    assert (refused.status_code, refused.get_json()["code"]) == (422, "EXTRACTION_OUTPUT_AUTHORITY_FIELD")
    bogus = "perspective-comparison-candidate:sha256:" + "f" * 64
    unknown = s.client.post(f"/api/perspective/comparison/candidates/{bogus}/accept", json={"decision": "accept", "candidate_id": bogus})
    assert (unknown.status_code, unknown.get_json()["code"]) == (404, "UNKNOWN_CANDIDATE")
    assert lab._logical_digest(s.db) == before
