"""P6 Deterministic Companion Coach v1 (#215): governed, read-only, never past P1/P2.

The committed evaluation is reproduced by the production coach over the
frozen P5 trajectories and P6 negatives; the coach cannot suggest a
capability P1 marks unavailable even when handed a tampered guide; it refuses
inputs from different snapshots; it has no provider, storage or network
dependency; and its API is a read-only projection. Synthetic workspaces only.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

import companion_coach_lab as coach_lab
import synthetic_study_lab as lab
from hermeneia.companion_coach import coach
from hermeneia.web.app import create_app

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "research" / "companion_coach" / "v1"


@pytest.fixture(scope="module")
def results():
    return json.loads(json.dumps(coach_lab.run(), sort_keys=True, ensure_ascii=False))


def _workspace(prefix: str, tmp_path: Path) -> Path:
    trajectory = next(t for t in lab.load_trajectories() if t["trajectory_id"].startswith(prefix))
    with lab.isolated(tmp_path):
        return lab.materialize(trajectory, tmp_path / prefix)


def _production(prefix: str, tmp_path: Path):
    db = _workspace(prefix, tmp_path)
    return lab.production_decide(lab.production_lineage(db), {})


def test_committed_dataset_and_matrix_are_reproduced_by_production(results):
    assert json.loads((RESULTS / "results.json").read_text()) == results
    assert (RESULTS / "summary.md").read_text() == coach_lab.summary_markdown(results)


def test_every_scenario_meets_the_frozen_contract(results):
    aggregate = results["aggregate"]
    assert aggregate.pop("forbidden_suggestions") == {"count": 0, "total": 9}
    assert all(value == {"passed": 9, "total": 9} for value in aggregate.values()), aggregate


def test_mature_trajectories_are_quiet_and_negatives_never_suggest(results):
    by_id = {r["scenario_id"]: r["coach"] for r in results["scenarios"]}
    assert by_id["T7_advanced_self_directed"]["decision"] == "remain_quiet"
    assert by_id["T5_organizer_never_reviews_blueprint"]["quiet_reason"] == "OPTIONAL_REVIEW_ONLY"
    assert by_id["N1_question_without_source"]["quiet_reason"] == "NEXT_STEP_BLOCKED"
    assert by_id["N2_legacy_missing_extractions"]["quiet_reason"] == "NEXT_STEP_UNKNOWN"
    assert by_id["N1_question_without_source"]["suggestion"] is None
    assert by_id["N2_legacy_missing_extractions"]["suggestion"] is None


def test_coach_cannot_recommend_a_capability_whose_prerequisites_are_unavailable(tmp_path):
    evaluation, guide = _production("T1", tmp_path)
    unavailable = [row["capability_id"] for row in evaluation["capabilities"] if row["availability"] != "available"]
    assert {"form_interpretation", "challenge_interpretation", "review_blueprint"} <= set(unavailable)
    for capability in unavailable:
        tampered = deepcopy(guide)
        tampered["recommended_step_id"] = capability
        result = coach(evaluation, tampered)
        assert result["decision"] == "remain_quiet" and result["suggestion"] is None and result["next_action"] is None
        assert result["quiet_reason"] in ("NEXT_STEP_BLOCKED", "NEXT_STEP_UNKNOWN")
        assert result["blocked"]["capability_id"] == capability and result["blocked"]["prerequisites_missing"]


def test_coach_refuses_inputs_that_are_not_one_snapshot(tmp_path):
    evaluation_t1, guide_t1 = _production("T1", tmp_path / "a")
    evaluation_t2, guide_t2 = _production("T2", tmp_path / "b")
    with pytest.raises(ValueError):
        coach(evaluation_t1, guide_t2)
    loosened = deepcopy(evaluation_t1)
    next(r for r in loosened["capabilities"] if r["capability_id"] == "form_interpretation")["availability"] = "available"
    with pytest.raises(ValueError):
        coach(loosened, guide_t1)
    with pytest.raises(ValueError):
        coach(evaluation_t1, {**guide_t1, "guide_version": "9.9.9"})


def test_coach_module_has_no_provider_storage_or_network_dependency():
    tree = ast.parse((ROOT / "hermeneia" / "companion_coach.py").read_text())
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported <= {"__future__", "copy", "json"}


def test_api_is_a_read_only_projection_of_the_production_coach(tmp_path):
    db = _workspace("T2", tmp_path)
    client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
    before = lab._logical_digest(db)
    response = client.get("/api/companion/coach")
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    body = response.get_json()
    assert body.pop("current_frame_selection") is None
    assert body == json.loads(json.dumps(coach(*lab.production_decide(lab.production_lineage(db), {}))))
    assert body["decision"] == "suggest" and body["suggestion"]["capability_id"] == "challenge_interpretation"
    assert lab._logical_digest(db) == before
    assert client.get("/api/companion/coach?debug=1").status_code == 400
    assert client.get("/api/companion/coach?perspective_kind=saved&perspective_id=missing").status_code == 400


def test_api_without_a_workspace_creates_nothing(tmp_path):
    db = tmp_path / "missing" / "workspace.db"
    response = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client().get("/api/companion/coach")
    assert response.status_code == 200
    assert response.get_json()["suggestion"]["capability_id"] == "governing_question"
    assert not db.exists() and not db.parent.exists()
