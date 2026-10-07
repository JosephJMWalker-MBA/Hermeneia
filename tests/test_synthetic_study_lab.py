"""P5 Synthetic Study Laboratory v1 (#215): the results come from production rules.

The committed dataset must be reproduced by the production Lineage, Capability
Registry and Guided Study Cycle; those functions receive only the synthetic
workspace snapshot and the declared current state (never an expectation);
changing a production rule changes the results; and a disagreeing expectation
is reported, never rewritten. Synthetic workspaces only; no network.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import socket

import pytest

import hermeneia.capabilities as capabilities
import hermeneia.guided_study_cycle as guided
import synthetic_study_lab as lab

RESULTS = Path(__file__).resolve().parent.parent / "research" / "synthetic_study_lab" / "v1"
PLANNED_PROFILES = [
    "highlights heavily, weak synthesis",
    "forms interpretations too early, little contradiction testing",
    "asks many questions but never promotes/resolves",
    "overuses model Perspectives with little user-authored analysis",
    "organizes evidence but never reviews Blueprint",
    "careful evidence worker with several unresolved questions",
    "advanced self-directed investigator who should receive almost no nudges",
]


@pytest.fixture(scope="module")
def results():
    return json.loads(json.dumps(lab.run(), sort_keys=True, ensure_ascii=False))


def _one(trajectory_id):
    return next(t for t in lab.load_trajectories() if t["trajectory_id"].startswith(trajectory_id))


def test_frozen_contract_has_the_seven_planned_trajectories():
    schema = json.loads((lab.FIXTURES.parent / "trajectory.schema.json").read_text())
    trajectories = lab.load_trajectories()
    assert schema["$id"] == lab.TRAJECTORY_SCHEMA
    assert [t["trajectory_id"][:2] for t in trajectories] == [f"T{n}" for n in range(1, 8)]
    assert [t["planned_profile"] for t in trajectories] == PLANNED_PROFILES
    assert {t["fixture_class"] for t in trajectories} == {"lawful", "lawful_then_legacy_shape"}


def test_committed_dataset_and_matrix_are_reproduced_by_production(results):
    assert json.loads((RESULTS / "results.json").read_text()) == results
    assert (RESULTS / "summary.md").read_text() == lab.summary_markdown(results)


def test_all_seven_trajectories_meet_the_frozen_expectations(results):
    aggregate = results["aggregate"]
    assert aggregate["capability_state"]["correct"] == aggregate["capability_state"]["total"] == 7 * 33
    assert aggregate["unsupported_vs_not_yet"]["correct"] == aggregate["unsupported_vs_not_yet"]["total"]
    assert aggregate["forbidden_suggestions"]["count"] == 0
    for key in ("next_step_preferred", "next_step_permitted", "repeatable", "order_invariant",
                "no_manufactured_history", "label_invariant"):
        assert aggregate[key]["passed"] == aggregate[key]["total"] == 7, key
    assert all(not r["mismatches"] for r in results["trajectories"])


def test_production_receives_only_the_workspace_snapshot_and_declared_state(monkeypatch, tmp_path):
    calls = []
    for name in ("evaluate_capabilities", "project_guided_study_cycle"):
        real = getattr(lab, name)

        def spy(lineage, *args, _real=real, _name=name, **kwargs):
            calls.append((_name, deepcopy(lineage), args, deepcopy(kwargs)))
            return _real(lineage, *args, **kwargs)
        monkeypatch.setattr(lab, name, spy)
    for trajectory in lab.load_trajectories():
        lab.evaluate_trajectory(trajectory, tmp_path / trajectory["trajectory_id"])
        expected_tokens = {trajectory["trajectory_id"], trajectory["planned_profile"], trajectory["expected"]["reason"],
                           trajectory["expected"]["derivation"], *trajectory["edges"]}
        for _name, lineage, args, kwargs in calls:
            assert lineage["schema"] == "hermeneia.study-lineage/v1" and not args
            assert set(kwargs) == {"current_state"} and set(kwargs["current_state"]) <= {"governing_question", "perspective_available"}
            serialized = json.dumps([lineage, kwargs], sort_keys=True)
            assert not any(token in serialized for token in expected_tokens)
        calls.clear()


def test_results_follow_a_change_in_the_production_rules(monkeypatch, tmp_path):
    registry = capabilities.load_capability_registry()
    perturbed = deepcopy(registry)
    form = next(d for d in perturbed["capabilities"] if d["capability_id"] == "form_interpretation")
    form["positive_evidence"][0]["minimum"] = 1000
    monkeypatch.setattr(capabilities, "load_capability_registry", lambda path=None: capabilities._validate_registry(perturbed))
    monkeypatch.setattr(guided, "load_capability_registry", lambda path=None: capabilities._validate_registry(perturbed))
    result = lab.evaluate_trajectory(_one("T2"), tmp_path)
    # Without the attributable-Interpretation anchor, P2 walks from the start.
    assert result["production"]["recommended_step_id"] == "read_source"
    assert result["production"]["capabilities"]["form_interpretation"]["status"] == "available"
    assert {(m["capability_id"], m["field"]) for m in result["mismatches"]} == {
        ("form_interpretation", "status"), ("form_interpretation", "guide")}


def test_a_disagreeing_expectation_is_reported_never_rewritten(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    source = next(lab.FIXTURES.glob("T1_*.json"))
    altered = json.loads(source.read_text())
    altered["expected"]["preferred_next"] = "organize_evidence"
    altered["expected"]["permitted_next"] = ["organize_evidence"]
    altered["expected"]["capabilities"]["organize_evidence"]["guide"] = "currently_supported"
    path = fixtures / source.name
    path.write_text(json.dumps(altered))
    before = path.read_bytes()
    result = lab.run(fixtures)["trajectories"][0]
    assert result["production"]["recommended_step_id"] == "preserve_question"
    assert not result["metrics"]["next_step_preferred"]
    assert result["mismatches"] == [{"capability_id": "organize_evidence", "field": "guide",
                                     "expected": "currently_supported", "production": "ready"}]
    assert path.read_bytes() == before


def test_laboratory_isolation_blocks_network_and_restores_the_environment(tmp_path):
    previous = os.environ.get("HERMENEIA_CONNECTIONS_SETTINGS_PATH")
    with lab.isolated(tmp_path):
        with pytest.raises(RuntimeError, match="no network"):
            socket.create_connection(("127.0.0.1", 9))
        assert os.environ["HERMENEIA_CONNECTIONS_SETTINGS_PATH"].startswith(str(tmp_path))
    assert os.environ.get("HERMENEIA_CONNECTIONS_SETTINGS_PATH") == previous
    assert socket.create_connection.__name__ != "blocked"


def test_legacy_shape_is_the_only_direct_sql_and_is_labeled():
    for trajectory in lab.load_trajectories():
        legacy = [op for op in trajectory["operations"] if op["op"] == "legacy_drop_table"]
        assert (trajectory["fixture_class"] == "lawful_then_legacy_shape") == bool(legacy)
        assert all("not proof a user workflow" in op["label"] for op in legacy)
