"""ADR-0042 classifies a missing provenance record as a transformation: evidence for proposed ADR-0046 (v0.2).

Nothing here changes evaluation semantics; ADR-0046 is PROPOSED, not ratified.
- Passing tests pin what `provenance-v1.0`, the Critic route and the Finding store do today.
- Strict-xfail witnesses pin what the proposal says must stop. They must show XPASS(strict) only after the Primary
  Human Steward ratifies an amendment and it is implemented; only then are their markers removed.

The witness state is built in tests/adr0046_witness_state.py. The `unverifiable` schema rehearsal is in
tests/test_adr0046_unverifiable_rehearsal.py. Proposal: docs/adr/ADR-0046-provenance-absence-is-not-transformation.md.
"""
from __future__ import annotations

import json
import shutil
import sqlite3

import pytest

import synthetic_study_lab as lab
from adr0046_witness_state import ABSENT, Pair, by_obligation, connect, render, rows
from hermeneia.compiler.evaluation_functions.base import RATIFIED_DIMENSIONS
from hermeneia.compiler.projections.trust_card import trust_card

EVIDENCE_TABLES = ("source_documents", "source_extractions", "observations")


@pytest.fixture
def pair(tmp_path):
    with lab.isolated(tmp_path):
        yield Pair(tmp_path)


# ── The state: unchanged evidence, absent custody record ──────────────────────

def test_the_witness_state_is_unchanged_evidence_without_provenance(pair):
    for table in EVIDENCE_TABLES:
        assert rows(pair.restored, table) == rows(pair.source, table), table
    assert len(rows(pair.source, "provenance")) == len(pair.observations) >= 3
    assert rows(pair.restored, "provenance") == []


# ── D-1: what provenance-v1.0 does today (characterization, not endorsement) ─

def test_provenance_v1_reads_that_state_as_transformed_under_the_same_finding_ids(pair):
    source, restored = pair.critic(pair.source), pair.critic(pair.restored)
    assert len(source) == len(restored) == len(pair.observations)
    assert {f["status"] for f in source} == {"preserved"}
    assert {(f["operation"], f["status"]) for f in restored} == {("transformation", "transformed")}
    # Identity names the obligation evaluated, not its disposition or the method: the same IDs carry both answers.
    assert [f["id"] for f in source] == [f["id"] for f in restored]
    assert [f["obligation_id"] for f in source] == [f["obligation_id"] for f in restored]
    assert {f["evaluation_method"] for f in source + restored} == {"provenance-v1.0"}
    assert all(render(f) == ABSENT for f in restored)


def test_provenance_v1_truth_table_over_the_four_observable_states(pair):
    """Absence is the only path to "transformed"; a demonstrated alteration is classified "preserved"."""
    states = pair.four_states()
    assert sorted(states.values()) == ["demonstrated_alteration", "missing_observation", "missing_provenance",
                                       "preserved_provenance"]
    findings = by_obligation(pair.critic(pair.restored))
    assert {state: (findings[o]["operation"], findings[o]["status"]) for o, state in states.items()} == {
        "missing_provenance": ("transformation", "transformed"),
        "demonstrated_alteration": ("preservation", "preserved"),
        "preserved_provenance": ("preservation", "preserved"),
        "missing_observation": ("omission", "omitted"),
    }
    for finding in findings.values():
        assert (finding["status"] == "transformed") == (render(finding) == ABSENT)


def test_only_the_unratified_semantic_dimension_records_not_evaluated_today(pair):
    """Blast radius of amending `not_evaluated`: its only current producer is a dimension outside the registry."""
    pair.run_critic_route(pair.source)
    recorded = {(f["dimension"], f["status"]) for f in rows(pair.source, "findings")}
    assert {dimension for dimension, status in recorded if status == "not_evaluated"} == {"semantic"}
    assert "semantic" not in RATIFIED_DIMENSIONS


def test_existing_projections_give_the_same_verdict_for_transformed_and_not_evaluated(pair, tmp_path):
    current = tmp_path / "current.db"
    shutil.copyfile(pair.restored, current)
    pair.persist(current, pair.critic(pair.restored))
    amended = tmp_path / "amended.db"
    shutil.copyfile(pair.restored, amended)
    pair.persist(amended, [dict(f, operation="not_evaluated", status="not_evaluated") for f in pair.critic(pair.restored)])
    verdicts = []
    for db in (current, amended):
        conn = connect(db)
        try:
            verdicts.append(trust_card(pair.narrative_id, conn)["dimensions"]["provenance"])
        finally:
            conn.close()
    assert verdicts[0] == verdicts[1] == "partial"


# ── D-2: every historical v1.0 Finding has one exact reading from its own fields ─

# (evaluation_method, operation, status, observation_exists, provenance_exists) -> (established, not established).
# All four observed_render combinations are covered, so the reading is total over provenance-v1.0's code paths.
V1_READINGS = {
    ("provenance-v1.0", "preservation", "preserved", True, True): (
        ("the Observation existed", "a provenance record existed"),
        ("that the record agrees with the Observation", "that the Observation is linked to the plan's Blueprint")),
    ("provenance-v1.0", "transformation", "transformed", True, False): (
        ("the Observation existed", "no provenance record existed"),
        ("any alteration of the Observation", "the Observation's custody")),
    ("provenance-v1.0", "omission", "omitted", False, False): (
        ("no Observation with this ID existed",), ()),
    ("provenance-v1.0", "omission", "omitted", False, True): (
        ("no Observation with this ID existed", "a provenance record existed"), ()),
}


def _reading_key(finding: dict) -> tuple:
    observed = render(finding)
    return (finding["evaluation_method"], finding["operation"], finding["status"],
            observed["observation_exists"], observed["provenance_exists"])


def test_each_historical_v1_finding_has_exactly_one_reading_from_its_own_fields(pair):
    states = pair.four_states()
    findings = by_obligation(pair.critic(pair.restored))
    readings = {state: V1_READINGS[_reading_key(findings[o])] for o, state in states.items()}
    assert "any alteration of the Observation" in readings["missing_provenance"][1]
    # v1.0 "preserved" never compared the record with the Observation, so its reading must not claim agreement.
    assert readings["demonstrated_alteration"] == readings["preserved_provenance"]
    assert "that the record agrees with the Observation" in readings["preserved_provenance"][1]


# ── D-3: what the Finding store does today with each failure class ───────────

def _with(findings: list[dict], **fields) -> list[dict]:
    """Hypothetical computed Findings (test data only; no evaluator is changed)."""
    return [dict(f, **fields) for f in findings]


def test_a_historical_finding_cannot_be_reclassified_in_place_and_keeps_its_steward_decision(pair):
    historical = pair.critic(pair.restored)
    pair.persist(pair.restored, historical)
    conn = connect(pair.restored)
    try:
        conn.execute("INSERT INTO steward_decisions (id, finding_id, verdict, rationale, steward_id, decided_at, "
                     "constitution_version, created_at) VALUES ('sd', ?, 'deferred', 'Reviewed.', 'steward', 't', '{}', 't')",
                     (historical[0]["id"],))
        conn.commit()
        with pytest.raises(sqlite3.DatabaseError, match="Finding immutable"):
            conn.execute("UPDATE findings SET operation = 'not_evaluated', status = 'not_evaluated'")
        with pytest.raises(sqlite3.DatabaseError, match="Finding immutable"):
            conn.execute("DELETE FROM findings")
        joined = conn.execute("SELECT f.status FROM steward_decisions s JOIN findings f ON f.id = s.finding_id").fetchall()
        assert [tuple(r) for r in joined] == [("transformed",)]
    finally:
        conn.close()


def test_an_identical_reevaluation_is_idempotent(pair):
    """Any guard must keep this: the Critic route relies on it to complete a partial ledger on retry."""
    pair.persist(pair.restored, pair.critic(pair.restored))
    stored = rows(pair.restored, "findings")
    pair.persist(pair.restored, pair.critic(pair.restored))  # new created_at, same content
    assert rows(pair.restored, "findings") == stored


def test_today_a_divergent_reevaluation_is_discarded_silently(pair):
    historical = pair.critic(pair.restored)
    pair.persist(pair.restored, historical)
    assert pair.persist(pair.restored, _with(historical, operation="not_evaluated", status="not_evaluated")) is None
    assert {(f["status"], f["evaluation_method"]) for f in rows(pair.restored, "findings")} == {("transformed", "provenance-v1.0")}


def test_today_an_unsupported_status_is_discarded_silently(pair):
    """The CHECK vocabulary refuses it, but INSERT OR IGNORE also ignores CHECK violations."""
    finding = dict(pair.critic(pair.restored)[0], status="bogus")
    assert pair.persist(pair.restored, [finding]) is None
    assert rows(pair.restored, "findings") == []
    conn = connect(pair.restored)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            conn.execute(f"INSERT INTO findings ({', '.join(finding)}) VALUES ({', '.join('?' for _ in finding)})",
                         list(finding.values()))
    finally:
        conn.close()


def test_today_an_unratified_operation_status_pair_is_stored(pair):
    pair.persist(pair.restored, _with(pair.critic(pair.restored)[:1], operation="preservation", status="omitted"))
    assert [(f["operation"], f["status"]) for f in rows(pair.restored, "findings")] == [("preservation", "omitted")]


def test_today_a_failed_insertion_is_discarded_silently(pair):
    """NOT NULL is ignored by INSERT OR IGNORE too: the Finding is lost and the call succeeds."""
    assert pair.persist(pair.restored, _with(pair.critic(pair.restored)[:1], evidence=None)) is None
    assert rows(pair.restored, "findings") == []


def test_today_a_retained_older_evaluator_version_is_not_reported(pair):
    historical = pair.critic(pair.restored)
    pair.persist(pair.restored, historical)
    assert pair.persist(pair.restored, _with(historical, evaluation_method="provenance-v1.1")) is None
    assert {f["evaluation_method"] for f in rows(pair.restored, "findings")} == {"provenance-v1.0"}


# ── Witnesses: what the proposal says must stop ─────────────────────────────

class ProvenanceAbsenceReadAsAlteration(AssertionError):
    """An unchanged Observation whose provenance record is absent is classified as materially altered."""


class DivergentReevaluationDiscarded(AssertionError):
    """A result that disagrees with a stored Finding under the same ID is dropped without any signal."""


class UnsupportedValueAccepted(AssertionError):
    """A Finding with an unratified status or operation/status pair is accepted (dropped or stored) without a signal."""


class FailedInsertionUnreported(AssertionError):
    """A Finding the store did not record is reported as a successful write."""


class RetainedOlderVersionUnreported(AssertionError):
    """A stored Finding from an older evaluator version stands for a newer computation and nothing says so."""


@pytest.mark.xfail(strict=True, raises=ProvenanceAbsenceReadAsAlteration,
                   reason="ADR-0042 classifies missing provenance as transformation; ADR-0046 proposed, not ratified")
def test_an_unchanged_observation_without_provenance_is_not_classified_as_altered(pair):
    findings = pair.critic(pair.restored)
    assert len(findings) == len(pair.observations)  # the completeness invariant holds under any remedy
    for finding in findings:
        assert render(finding) == ABSENT  # the absence stays recorded
        if finding["operation"] == "transformation" or finding["status"] == "transformed":
            raise ProvenanceAbsenceReadAsAlteration(f"{finding['obligation_id'][:12]}: unchanged evidence, absent record, "
                                                    f"classified {finding['operation']}/{finding['status']}")


def _refused_without_writing(pair, batch: list[dict], expected_rows: list[dict]) -> bool:
    """True when the store refuses the whole batch and leaves the ledger exactly as it was."""
    try:
        pair.persist(pair.restored, batch)
    except (ValueError, sqlite3.DatabaseError):
        assert rows(pair.restored, "findings") == expected_rows, "a refused batch must write nothing"
        return True
    return False


@pytest.mark.xfail(strict=True, raises=DivergentReevaluationDiscarded,
                   reason="Findings are stored with INSERT OR IGNORE; ADR-0046 D-3 proposes failing closed")
def test_a_divergent_reevaluation_fails_closed_and_writes_nothing(pair):
    historical = pair.critic(pair.restored)
    half = len(historical) // 2
    pair.persist(pair.restored, historical[:half])
    stored = rows(pair.restored, "findings")
    batch = _with(historical[:half], operation="not_evaluated", status="not_evaluated") + historical[half:]
    if not _refused_without_writing(pair, batch, stored):
        raise DivergentReevaluationDiscarded(f"{half} divergent Findings dropped; {len(historical) - half} written beside them")


@pytest.mark.xfail(strict=True, raises=UnsupportedValueAccepted, reason="ADR-0046 D-3 proposes refusing unsupported values")
@pytest.mark.parametrize("fields", [{"status": "bogus"}, {"operation": "preservation", "status": "omitted"}],
                         ids=["unknown-status", "unratified-pair"])
def test_an_unsupported_value_is_refused(pair, fields):
    if not _refused_without_writing(pair, _with(pair.critic(pair.restored), **fields), []):
        raise UnsupportedValueAccepted(f"{fields} accepted; stored: {len(rows(pair.restored, 'findings'))}")


@pytest.mark.xfail(strict=True, raises=FailedInsertionUnreported, reason="ADR-0046 D-3 proposes read-back verification")
def test_a_failed_insertion_is_refused(pair):
    if not _refused_without_writing(pair, _with(pair.critic(pair.restored), evidence=None), []):
        raise FailedInsertionUnreported("Findings violating NOT NULL were dropped and the write reported success")


@pytest.mark.xfail(strict=True, raises=RetainedOlderVersionUnreported, reason="ADR-0046 D-3 proposes a ledger write report")
def test_a_retained_older_evaluator_version_is_reported(pair):
    historical = pair.critic(pair.restored)
    pair.persist(pair.restored, historical)
    report = pair.persist(pair.restored, _with(historical, evaluation_method="provenance-v1.1"))
    retained = {entry["id"] for entry in report["retained"]} if isinstance(report, dict) and "retained" in report else None
    if retained != {f["id"] for f in historical}:
        raise RetainedOlderVersionUnreported(f"report: {report!r}")
