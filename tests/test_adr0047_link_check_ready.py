"""ADR-0047 L2-b, implementation-ready and NOT active: provenance-v1.1 checks each obligation's Blueprint link.

The default evaluator stays provenance-v1.0, so the L2-b witnesses in tests/test_ef_ratification_divergences.py stay
strict-xfail until ADR-0046 U and ADR-0047 L2-b are ratified and activated together. These tests ask for v1.1
explicitly. Its evidence keeps three facts distinct:
- whether the Observation exists;
- whether its custody (provenance) record exists;
- whether the plan's Blueprint links it: true, false (a demonstrated missing link), or null (the Blueprint could not
  be resolved, so the link is unknown).
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import synthetic_study_lab as lab
from adr0046_witness_state import Pair, by_obligation, connect, render
from hermeneia.compiler.evaluation_functions import provenance
from hermeneia.compiler.projections.finding_readings import finding_reading
from hermeneia.storage.hashing import make_blueprint_id
from test_ef_ratification_divergences import Study

V11 = provenance.UNVERIFIABLE_METHOD


@pytest.fixture
def study(tmp_path):
    with lab.isolated(tmp_path):
        yield Study(tmp_path / "source")


@pytest.fixture
def pair(tmp_path):
    with lab.isolated(tmp_path):
        yield Pair(tmp_path)


def _v11(db, narrative_id, plan_id) -> dict[str, dict]:
    conn = connect(db)
    try:
        return by_obligation(provenance.evaluate_provenance(narrative_id, plan_id, conn, method=V11))
    finally:
        conn.close()


def _historical_plan(db, observation: str, *, blueprint_exists: bool) -> tuple[str, str]:
    """A historical record, written directly (foreign keys off, as an old or imported database might hold it): a plan
    citing `observation`, whose Blueprint either links nothing or does not exist at all. Returns (narrative, plan)."""
    sections = [{"claim": "Historical.", "supporting_observations": [observation], "supporting_interpretations": []}]
    blueprint_id = make_blueprint_id("Historical", "Unlinked.", sections) if blueprint_exists else "f" * 64
    plan_id, narrative_id = "a" * 64, "b" * 64
    conn = sqlite3.connect(db)
    try:
        if blueprint_exists:
            conn.execute("INSERT INTO narrative_blueprints (id, title, thesis, sections, source, created_at) "
                         "VALUES (?, 'Historical', 'Unlinked.', ?, 'steward-authored', 't')", (blueprint_id, json.dumps(sections)))
        conn.execute("INSERT INTO architect_plans (id, blueprint_id, blueprint_hash, title, source, created_at) "
                     "VALUES (?, ?, 'h', 'Historical', 'deterministic', 't')", (plan_id, blueprint_id))
        conn.execute("INSERT INTO architect_plan_paragraphs (plan_id, order_idx, purpose, blueprint_section, required_observations, "
                     "required_interpretations, required_terms, forbidden_claims, notes) VALUES (?, 1, 'H', 1, ?, '[]', '[]', '[]', NULL)",
                     (plan_id, json.dumps([observation])))
        conn.execute("INSERT INTO rendered_narratives (id, architect_plan_id, provider, expression_profile_id, text, prompt_used, "
                     "execution_config, created_at) VALUES (?, ?, 'null', NULL, 'H.', 'H.', '{}', 't')", (narrative_id, plan_id))
        conn.commit()
    finally:
        conn.close()
    return narrative_id, plan_id


def test_a_linked_observation_with_custody_is_preserved_and_the_link_is_recorded(study):
    finding = _v11(study.db, study.narrative_id, study.plan_id)[study.observations[0]]
    assert (finding["status"], render(finding)) == ("preserved", {"observation_exists": True, "provenance_exists": True,
                                                                 "blueprint_link_exists": True})
    assert finding_reading(finding)["not_established"] == ["that the record agrees with the Observation"]


def test_a_demonstrated_missing_link_is_unverifiable_and_kept_distinct_from_custody(study):
    unlinked = study.cite_unlinked_observation()
    finding = _v11(study.db, study.narrative_id, study.plan_id)[unlinked]
    assert (finding["operation"], finding["status"]) == ("unverifiable", "unverifiable")
    assert render(finding) == {"observation_exists": True, "provenance_exists": True, "blueprint_link_exists": False}
    reading = finding_reading(finding)
    assert "a provenance record existed" in reading["established"]
    assert "the plan's Blueprint does not link this Observation" in reading["established"]  # demonstrated, not inferred
    assert reading["not_established"] == ["the obligation's provenance relationship to the Blueprint"]


def test_an_undeterminable_link_is_recorded_as_unknown_not_as_missing(study):
    narrative_id, plan_id = _historical_plan(study.db, study.observations[0], blueprint_exists=False)
    finding = _v11(study.db, narrative_id, plan_id)[study.observations[0]]
    assert finding["status"] == "unverifiable"
    assert render(finding)["blueprint_link_exists"] is None
    reading = finding_reading(finding)
    assert not any("links this Observation" in fact and "whether" not in fact for fact in reading["established"])
    assert any("could not be resolved" in item for item in reading["not_established"])


def test_a_missing_custody_record_and_a_missing_link_are_both_recorded(pair):
    observation = pair.observations[0]
    narrative_id, plan_id = _historical_plan(pair.restored, observation, blueprint_exists=True)
    finding = _v11(pair.restored, narrative_id, plan_id)[observation]
    assert finding["status"] == "unverifiable"
    assert render(finding) == {"observation_exists": True, "provenance_exists": False, "blueprint_link_exists": False}
    assert finding_reading(finding)["not_established"] == [
        "whether the Observation was preserved or altered", "the obligation's provenance relationship to the Blueprint"]


def test_the_active_evaluator_is_unchanged(study):
    unlinked = study.cite_unlinked_observation()
    conn = connect(study.db)
    try:
        finding = by_obligation(provenance.evaluate_provenance(study.narrative_id, study.plan_id, conn))[unlinked]
    finally:
        conn.close()
    assert finding["evaluation_method"] == "provenance-v1.0" and finding["status"] == "preserved"
    assert "blueprint_link_exists" not in render(finding)


def test_a_reading_refuses_evidence_that_does_not_match_its_disposition(study):
    finding = _v11(study.db, study.narrative_id, study.plan_id)[study.observations[0]]
    forged = dict(finding, operation="unverifiable", status="unverifiable")  # facts say preserved
    assert finding_reading(forged)["established"] is None
