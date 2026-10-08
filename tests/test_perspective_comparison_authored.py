"""P7 closeout (#215): steward-authored structured comparison on the same canonical type and record machinery.

The committed closeout evidence is reproduced, with no model call. One origin
field carries three provenance kinds, which must agree with the decision and
the candidate. Model-assisted records carry the new kinds. Provider-backed
extraction is disabled unless explicitly enabled for evaluation. Synthetic
workspaces only.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

import perspective_comparison_authored_lab as authored_lab
import perspective_comparison_candidate_lab as candidate_lab
from hermeneia.accepted_perspective_comparisons import (
    MODEL_ORIGINS, STEWARD_AUTHORED, InvalidAcceptedComparison, record_id, validate_record,
)
from hermeneia.web.app import create_app

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "research" / "perspective_comparison_authored" / "v1"
SCHEMA = ROOT / "tests" / "fixtures" / "perspective_comparison" / "v1" / "accepted-comparison.schema.json"
CORPUS, CASES = candidate_lab.load()
LAYER1 = candidate_lab.layer1_lab.load_corpus(ROOT / CORPUS["layer1_corpus"])


@pytest.fixture(scope="module")
def results():
    return json.loads(json.dumps(authored_lab.run(), sort_keys=True, ensure_ascii=False))


@pytest.fixture
def context(tmp_path):
    entered = []

    def enter():
        entered.append(candidate_lab._isolated(tmp_path, CORPUS, LAYER1))
    yield enter
    for item in entered:
        item.__exit__(None, None, None)


def test_committed_closeout_evidence_is_reproduced(results):
    assert json.loads((RESULTS / "results.json").read_text()) == results
    assert (RESULTS / "summary.md").read_text() == authored_lab.summary_markdown(results)
    assert results["aggregate"] == {"authored_reference": {"items": 13, "all_checks_passed": 13},
                                    "demonstration": {"items": 2, "all_checks_passed": 2},
                                    "refusal": {"items": 6, "all_checks_passed": 6},
                                    "exclusion": {"items": 1, "all_checks_passed": 1},
                                    "gate": {"items": 1, "all_checks_passed": 1}}


def test_one_origin_field_three_kinds_one_schema():
    schema = json.loads(SCHEMA.read_text())
    assert schema["properties"]["origin"]["properties"]["kind"]["enum"] == [*MODEL_ORIGINS.values(), STEWARD_AUTHORED]


def test_origin_must_agree_with_decision_and_candidate(context, tmp_path):
    context()
    study = authored_lab.AuthoredStudy(LAYER1, CASES["C01_same_conclusion_same_evidence"], tmp_path / "ws")
    record = study.submit(study.basis().get_json()["binding"],
                          candidate_lab._edit(study, CASES["C01_same_conclusion_same_evidence"]["reference"], "reference")).get_json()
    assert validate_record(record) == record
    for mutate in (lambda r: r["origin"].update(kind="model_proposed_steward_accepted"),
                   lambda r: r["acceptance"].update(decision="accept"),
                   lambda r: r["origin"].update(kind="model_candidate")):
        forged = deepcopy(record)
        mutate(forged)
        forged["id"] = record_id(forged)  # even a self-consistent digest cannot launder a contradictory origin
        with pytest.raises(InvalidAcceptedComparison):
            validate_record(forged)


def test_model_assisted_records_carry_the_new_provenance_kinds(context, tmp_path):
    context()
    case = CASES["C06_wording_only_difference"]
    kinds = []
    for decision, script in (("accept", candidate_lab.faithful_script(case["reference"], ["R1", "R2"])),
                             ("edit_and_accept", next(a for a in CORPUS["adversarial"] if a["base_case"] == case["case_id"])["script"])):
        study = candidate_lab.Study(LAYER1, case, tmp_path / decision)
        candidate = study.propose(study.wire(script), CORPUS["extraction_model"]).get_json()
        body = {"decision": decision, "candidate_id": candidate["candidate_id"]}
        if decision == "edit_and_accept":
            body["structure"] = candidate_lab._edit(study, case["reference"], "reference")
        record = study.client.post(f"/api/perspective/comparison/candidates/{candidate['candidate_id']}/accept", json=body).get_json()
        kinds.append(record["origin"]["kind"])
    assert kinds == ["model_proposed_steward_accepted", "model_proposed_steward_edited"]


def test_semantic_extraction_is_disabled_unless_explicitly_enabled(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMENEIA_SEMANTIC_EXTRACTION", raising=False)
    assert create_app(db_path=tmp_path / "a" / "w.db").config["PERSPECTIVE_SEMANTIC_EXTRACTION"] == "disabled"
    monkeypatch.setenv("HERMENEIA_SEMANTIC_EXTRACTION", "experimental")
    assert create_app(db_path=tmp_path / "b" / "w.db").config["PERSPECTIVE_SEMANTIC_EXTRACTION"] == "experimental"
    monkeypatch.setenv("HERMENEIA_SEMANTIC_EXTRACTION", "yes")
    assert create_app(db_path=tmp_path / "c" / "w.db").config["PERSPECTIVE_SEMANTIC_EXTRACTION"] == "disabled"
