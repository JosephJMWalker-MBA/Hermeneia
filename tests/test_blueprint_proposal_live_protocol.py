"""P8 live diagnostic protocol (#215): frozen before any live call, scored independently of the parser.

Pins the protocol and harness bytes, checks that the protocol binds the frozen
corpus, and checks the independent census against the production parser. The
concealment rule is tested: one severe error or invented reference decides,
whatever the pooled numbers. Grading is validated strictly, and the scripted
ceiling reproduces through the same harness and reaches generation-ready. No
network.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import blueprint_proposal_lab as proposal_lab
import blueprint_proposal_live_eval as live_eval
from hermeneia import blueprint_proposals as bp

ROOT = Path(__file__).resolve().parent.parent
CEILING = ROOT / "research" / "blueprint_proposal_live" / "ceiling"
PROTOCOL = live_eval.load_protocol()
FROZEN = {"tests/fixtures/blueprint_proposal/v1/live_evaluation_protocol.json": "PROTOCOL_SHA256",
          "tests/blueprint_proposal_live_eval.py": "HARNESS_SHA256"}

BINDING = {"observations": [{"label": f"O{n}", "id": f"obs-a-{n}"} for n in (1, 2, 3)],
           "interpretations": [{"label": "I1", "id": "interp-1"}]}
INELIGIBLE = {"obs-b-1"}


def _out(sections, **extra):
    return json.dumps({"title": "T", "thesis": "Th", "sections": sections, **extra})


def _section(obs=(), interps=(), claim="C"):
    return {"claim": claim, "observations": list(obs), "interpretations": list(interps)}


def test_protocol_and_harness_are_frozen():
    for path, name in FROZEN.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == globals()[name], f"{path} changed after freezing"
    assert PROTOCOL["frozen_before_any_live_call"] is True and live_eval.frozen_prompt_check()


def test_protocol_binds_the_frozen_corpus():
    corpus = proposal_lab.load()
    ids = {c["case_id"] for c in corpus["cases"]}
    assert [c["case_id"].split("_")[0] for c in PROTOCOL["cases"]] == ["L1", "L2", "L3", "L4", "L5", "L6"]
    assert PROTOCOL["samples_per_case"] == 3 and PROTOCOL["model"] == "hermeneia-phi4-mini:latest"
    for case in PROTOCOL["cases"]:
        assert case["source_case"] is None or case["source_case"] in ids
        sets = {k: set(v) for k, v in case["sets"].items()}
        assert sets["required"] <= sets["expected"] <= sets["admissible"]
    assert PROTOCOL["thresholds"]["C1_invented_or_excluded_references"] == {
        "non_negotiable": True, "max_total": 0, "scope": PROTOCOL["thresholds"]["C1_invented_or_excluded_references"]["scope"]}


def test_census_classifies_every_reference_and_pointer():
    raw = _out([_section(["O1", "I1", " O1", "[O2]", "Observation 3", "O9", "obs-b-1"], ["I1", "I7"], claim="As O8 shows")])
    result = live_eval.census(raw, "create", BINDING, INELIGIBLE)
    assert [t["class"] for t in result["tokens"]] == ["valid", "misfiled", "malformed", "malformed", "malformed", "invented",
                                                      "excluded", "valid", "invented"]
    assert result["pointers"] == ["I7", "O8", "O9", "obs-b-1"] and not result["contract_valid"]
    assert result["offending"] == ["I7", "O8", "O9", "obs-b-1"]
    prose = live_eval.census("Use O1 and O5 for the lamp.", "create", BINDING, INELIGIBLE)
    assert prose["json"] is False and prose["offending"] == ["O5"] and not prose["contract_valid"]


@pytest.mark.parametrize("mode,raw", [
    ("create", _out([_section(["O1", "O2"], ["I1"])])),
    ("create", "```json\n" + _out([_section(["O1"])]) + "\n```"),
    ("create", _out([_section()])),
    ("create", _out([_section(["O1"])], extra="x")),
    ("create", json.dumps({"title": "T", "sections": [_section(["O1"])]})),
    ("create", json.dumps({"title": "T", "thesis": "  ", "sections": [_section(["O1"])]})),
    ("create", _out([])),
    ("create", _out([_section(["O1"])] * 13)),
    ("create", _out([{**_section(["O1"]), "note": "x"}])),
    ("create", _out([_section(["O1", "O1"])])),
    ("create", _out([{"claim": "C", "observations": [1], "interpretations": []}])),
    ("create", '{"title": "T", "title": "U", "thesis": "Th", "sections": []}'),
    ("create", _out([_section(["O9"])])),
    ("create", _out([_section(["obs-b-1"])])),
    ("create", _out([_section(["I1"])])),
    ("create", "The lamp is a vigil."),
    ("create", "[]"),
    ("revise", _out([_section(["O1"])])),
    ("revise", _out([_section(["O1"])], change_summary="Adds O1.")),
])
def test_independent_contract_agrees_with_the_production_parser(mode, raw):
    basis = {"mode": mode, "binding": BINDING, "ineligible_ids": INELIGIBLE}
    try:
        bp.parse_output(raw, basis)
        admitted = True
    except bp.ProposalRefused:
        admitted = False
    assert live_eval.census(raw, mode, BINDING, INELIGIBLE)["contract_valid"] is admitted


@pytest.fixture(scope="module")
def ceiling():
    return (json.loads((CEILING / "results.json").read_text()), json.loads((CEILING / "grading.json").read_text()))


def test_concealment_rule_one_individual_failure_decides(ceiling):
    results, grading = ceiling
    assert live_eval.aggregate(results, grading, PROTOCOL)["verdict"] == "P8_GOVERNANCE_READY_GENERATION_READY"

    severe = copy.deepcopy(grading)
    severe["grades"][4]["claims"][1]["class"] = "contradicted"
    agg = live_eval.aggregate(results, severe, PROTOCOL)
    assert agg["pooled"]["supported_rate"] >= 0.9 and agg["pooled"]["precision"] == 1.0
    assert agg["criteria"]["C4_semantic_fidelity"] is False and agg["verdict"] == "P8_GOVERNANCE_READY_GENERATION_NOT_READY"

    flattened = copy.deepcopy(grading)
    record = next(r for r in results["records"] if r["run_id"] == flattened["grades"][0]["run_id"])
    flattened["grades"][0]["uncertainty"] = {"class": "flattened", "rationale": "r", "quote": record["proposal_local"]["thesis"]}
    assert live_eval.aggregate(results, flattened, PROTOCOL)["criteria"]["C4_semantic_fidelity"] is False

    invented = copy.deepcopy(results)
    invented["records"][7]["census"]["offending"] = ["O7"]
    agg = live_eval.aggregate(invented, grading, PROTOCOL)
    assert agg["criteria"]["C1_invented_or_excluded_references"] is False and agg["pooled"]["precision"] == 1.0
    assert agg["verdict"] == "P8_GOVERNANCE_READY_GENERATION_NOT_READY"

    defect = copy.deepcopy(results)
    defect["records"][2]["governance"]["D2_no_write"] = False
    assert live_eval.aggregate(defect, grading, PROTOCOL)["verdict"] == "P8_DEFECT"


def test_grading_is_validated_strictly(ceiling):
    results, grading = ceiling
    broken = []
    g = copy.deepcopy(grading)
    g["grades"][0]["claims"].pop()
    broken.append(g)
    g = copy.deepcopy(grading)
    g["grades"][0]["authorship"] = {"class": "fail", "rationale": "r", "quote": None}
    broken.append(g)
    g = copy.deepcopy(grading)
    g["grades"][0]["uncertainty"] = {"class": "flattened", "rationale": "r", "quote": "text that is not in the output"}
    broken.append(g)
    g = copy.deepcopy(grading)
    g["results_binding"] = "0" * 64
    broken.append(g)
    g = copy.deepcopy(grading)
    g["grades"].append({**g["grades"][0], "run_id": "L9-s1"})
    broken.append(g)
    g = copy.deepcopy(grading)
    g["grades"][0]["claims"][0]["class"] = "mostly_supported"
    broken.append(g)
    for bad in broken:
        with pytest.raises(ValueError):
            live_eval.validate_grading(bad, results, PROTOCOL)


def _stable(record):
    keys = ("run_id", "case_id", "sample", "http_status", "code", "provider_failure", "prompt_sha256", "raw_output_sha256",
            "census", "exposed", "admitted", "governance", "proposal_local", "references", "grounding")
    return {k: record.get(k) for k in keys}


def test_scripted_ceiling_reproduces_and_reaches_generation_ready(ceiling, tmp_path):
    committed, grading = ceiling
    rerun = live_eval.execute(tmp_path / "ceiling", live=False)
    assert [_stable(r) for r in rerun["records"]] == [_stable(r) for r in committed["records"]]
    agg = live_eval.aggregate(committed, grading, PROTOCOL)
    assert json.loads((CEILING / "aggregate.json").read_text()) == json.loads(json.dumps(agg))
    assert (CEILING / "summary.md").read_text() == live_eval.summary_markdown(agg, committed)
    assert agg["verdict"] == "P8_GOVERNANCE_READY_GENERATION_READY" and not agg["governance_defects"]


PROTOCOL_SHA256 = "c8eae98205d03eecf5ec92eefa4ae3a6cab2644569082dcd6bda2a8b01b67771"
HARNESS_SHA256 = "833ff7abafe262e6e2bf7c2704cd6cb6c3306a7614ece872793f04e3987d5d70"


def test_committed_live_diagnostic_reproduces_from_preserved_outputs_and_grades():
    # Owner-authorized 2026-10-10 run, executed at the freezing commit; recomputed offline from what was preserved.
    live = ROOT / "research" / "blueprint_proposal_live" / "phi4-mini"
    results, grading = json.loads((live / "results.json").read_text()), json.loads((live / "grading.json").read_text())
    assert results["kind"] == "live" and results["protocol_sha256"] == PROTOCOL_SHA256 and results["harness_sha256"] == HARNESS_SHA256
    assert results["model_identity_before"]["digest"] == results["model_identity_after"]["digest"] == PROTOCOL["model_identity"]["digest"]
    assert len(results["records"]) == 18 and all(r["raw_output_sha256"] == bp.text_digest(r["raw_output"]) for r in results["records"])
    agg = live_eval.aggregate(results, grading, PROTOCOL)
    assert json.loads((live / "aggregate.json").read_text()) == json.loads(json.dumps(agg))
    assert (live / "summary.md").read_text() == live_eval.summary_markdown(agg, results)
    assert agg["verdict"] == "P8_GOVERNANCE_READY_GENERATION_NOT_READY" and agg["governance_defects"] == []
