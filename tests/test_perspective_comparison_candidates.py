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


# ── Experimental extraction policy v1.1 (docs/design/perspective-comparison-extraction-v1.1.md) ──

V1_1_POLICY = json.loads((ROOT / "tests" / "fixtures" / "perspective_comparison" / "v1" / "extraction_policy_v1.1.json").read_text())


def test_v1_1_prompt_constants_equal_the_frozen_policy():
    from hermeneia.perspective_comparison_candidates import (
        V1_1_CLASSIFICATIONS, V1_1_EXAMPLE, V1_1_EXAMPLE_INTRO, V1_1_HEADER, V1_1_OUTPUT_RULES, V1_1_WORK_ORDER,
    )
    prompt = V1_1_POLICY["prompt"]
    assert (list(V1_1_HEADER), list(V1_1_WORK_ORDER), list(V1_1_OUTPUT_RULES)) == (
        prompt["header"], prompt["work_order"], prompt["output_rules"])
    assert (V1_1_EXAMPLE_INTRO, V1_1_EXAMPLE) == (prompt["example_intro"], prompt["example"])
    assert V1_1_CLASSIFICATIONS == V1_1_POLICY["mapping_to_canonical_stance"]


def test_v1_1_wire_normalizes_to_the_same_canonical_structure_and_v1_is_unchanged(study):
    import perspective_comparison_live_eval_v1_1 as v11
    from hermeneia.perspective_comparison_candidates import build_prompt, parse_output_v1_1, prompt_for
    s = study("C08_two_to_one_minority")
    inputs = _inputs(s.db, s.receipt_ids)
    view = inputs["view"]
    wire = s.wire(candidate_lab.faithful_script(s.case["reference"], ["R1", "R2", "R3"]))
    assert normalize(parse_output_v1_1(v11.to_v1_1_wire(wire), view), view) == normalize(parse_output(wire, view), view)
    assert prompt_for("1.0.0", view, inputs["texts"]) == build_prompt(view, inputs["texts"])
    assert prompt_for("1.1.0", view, inputs["texts"]) != build_prompt(view, inputs["texts"])


def test_v1_1_enforces_its_bound_and_keeps_explicit_unknowns_honest(study):
    from hermeneia.perspective_comparison_candidates import parse_output_v1_1
    s = study("C01_same_conclusion_same_evidence")
    view = _inputs(s.db, s.receipt_ids)["view"]
    quote = s.case["steps"][0]["response"]

    def proposition(index, second):
        return {"id": f"p{index}", "statement": "The lamp signals a watch.", "classifications": [
            {"participant": "P1", "classification": "supports", "quote": quote, "relies_on": []}, second]}

    unknown = {"participant": "P2", "classification": "unknown", "quote": None, "relies_on": []}
    structure = normalize(parse_output_v1_1(json.dumps({"propositions": [proposition(1, unknown)], "assumptions": []}), view), view)
    assert [p["stance"] for p in structure["propositions"][0]["positions"]] == ["asserts", "unknown"]
    assert structure["untraceable"] == []
    silent_quoted = {"participant": "P2", "classification": "silent", "quote": "Read narrowly", "relies_on": []}
    structure = normalize(parse_output_v1_1(json.dumps({"propositions": [proposition(1, silent_quoted)], "assumptions": []}), view), view)
    assert [u["kind"] for u in structure["untraceable"]] == ["contradictory_position"]
    with pytest.raises(ExtractionRefused) as refused:
        parse_output_v1_1(json.dumps({"propositions": [proposition(i, unknown) for i in range(1, 6)], "assumptions": []}), view)
    assert refused.value.code == "EXTRACTION_OUTPUT_CONTRACT_VIOLATION"


def test_v1_1_candidates_can_be_discarded_but_never_accepted(study):
    import perspective_comparison_live_eval_v1_1 as v11
    s = study("C03_different_conclusions_same_evidence")
    before = lab._logical_digest(s.db)
    wire = v11.to_v1_1_wire(s.wire(candidate_lab.faithful_script(s.case["reference"], ["R1", "R2"])))
    _CapturingProvider.render_responses = [wire]
    candidate = v11._post(s.client, s.receipt_ids, CORPUS["extraction_model"]).get_json()
    assert candidate["extraction"]["policy_version"] == "1.1.0"
    assert candidate["extraction"]["prompt_version"] == "perspective-comparison-extraction/v1.1"
    url = f"/api/perspective/comparison/candidates/{candidate['candidate_id']}"
    for body in ({"decision": "accept", "candidate_id": candidate["candidate_id"]},
                 {"decision": "edit_and_accept", "candidate_id": candidate["candidate_id"],
                  "structure": candidate_lab._edit(s, s.case["reference"], "reference")}):
        refused = s.client.post(url + "/accept", json=body)
        assert (refused.status_code, refused.get_json()["code"]) == (409, "POLICY_NOT_ACCEPTABLE")
    assert s.client.post(url + "/discard", json={"decision": "discard", "candidate_id": candidate["candidate_id"]}).status_code == 200
    unsupported = s.client.post("/api/perspective/comparison/candidates",
                                json={"receipt_ids": s.receipt_ids, "model": CORPUS["extraction_model"], "policy_version": "9.9.9"})
    assert (unsupported.status_code, unsupported.get_json()["code"]) == (400, "INVALID_REQUEST")
    assert lab._logical_digest(s.db) == before
