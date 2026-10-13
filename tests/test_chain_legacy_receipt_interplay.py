"""#252 x #251: a legacy-origin acceptance receipt round-trips through the Blueprint chain component.

This test is inert until #254 (the `proposal` mode of
LEGACY_BLUEPRINT_WRITES) is merged; it skips while that module is absent.
After the merge it checks the following:
1. a proposal-mode legacy candidate, accepted through the P8 route, is
   exported by the chain component with closure;
2. it restores into a fresh target;
3. it verifies there exactly as in the source;
4. its Blueprint keeps Lineage authorship `accepted_model`.

Synthetic workspace; P5 isolation; in-process fake provider.
"""
from __future__ import annotations

import pytest

pytest.importorskip("hermeneia.legacy_blueprint_candidates")

import synthetic_study_lab as lab  # noqa: E402
from hermeneia.blueprint_proposals import verify_receipt  # noqa: E402
from hermeneia.study_lineage import project_study_lineage  # noqa: E402
from hermeneia.workspace import export_workspace_bundle  # noqa: E402
from hermeneia.workspace.blueprint_chain import CAPABILITY  # noqa: E402
from hermeneia.workspace.restore import restore_workspace  # noqa: E402

proposal_mode = pytest.importorskip("test_r251_proposal_mode")


def _authorship(db, blueprint_id):
    conn = lab._read_only(db)
    try:
        return next(i["authorship"] for i in project_study_lineage(conn)["items"]
                    if i["record"] == {"table": "narrative_blueprints", "key": {"id": blueprint_id}} and i["event"] == "recorded")
    finally:
        conn.close()


def _verify(db, receipt_id):
    conn = lab._read_only(db)
    try:
        return verify_receipt(conn, receipt_id)
    finally:
        conn.close()


def test_a_legacy_origin_receipt_round_trips_with_closure(tmp_path):
    with lab.isolated(tmp_path):
        study = proposal_mode.Study(tmp_path)
        candidate = study.generate(proposal_mode.FakeArchitect(proposal_mode.REPLY)).get_json()
        receipt = study.decide(candidate["candidate_id"], {"decision": "accept"}).get_json()
    manifest = export_workspace_bundle(study.db, tmp_path / "bundle", generated_at="2026-10-13T12:00:00+00:00",
                                       workspace_id="w", blueprint_chain=True)
    assert CAPABILITY in manifest["required_capabilities"] and "declared_unsupported" not in manifest
    target = tmp_path / "restored" / "workspace.db"
    result = restore_workspace(target, tmp_path / "bundle")
    assert result["coverage"]["blueprint_dependency_chain"]["status"] == "covered"
    assert _verify(target, receipt["id"]) == _verify(study.db, receipt["id"]) == {
        "record_integrity": "valid", "candidate_replay": "verified", "result_closure": "verified",
        "model_output": "preserved_not_replayed"}
    blueprint_id = receipt["result"]["resulting_blueprint_id"]
    assert _authorship(target, blueprint_id) == _authorship(study.db, blueprint_id) == "accepted_model"
