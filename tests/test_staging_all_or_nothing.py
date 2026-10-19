"""Each AI staging operation commits all of its writes or none (ADR-0009).

propose_interpretation writes an AIProvenance record and its
ProposedInterpretation. accept_proposed_interpretation marks the proposal
accepted, completes the provenance acceptance and inserts the canonical
Interpretation. A failure on a later write must leave none of the earlier ones
behind, so a failed acceptance can be retried, and a successful call still
commits everything at once.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import threading

import pytest

from hermeneia.compiler.staging.interpretation import (
    StagingError,
    accept_proposed_interpretation,
    propose_interpretation,
    reject_proposed_interpretation,
)
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.storage.hashing import make_interpretation_id
from test_constitutional_p0 import _seed_full_chain

GENERATED_AT = "2026-10-16T12:00:00+00:00"


class InjectedFailure(Exception):
    """Raised in place of a staging write."""


@pytest.fixture
def study(tmp_path):
    store = SQLiteStore(tmp_path / "workspace.db")
    ids = _seed_full_chain(store)
    try:
        yield store, ids
    finally:
        store.close()


def _state(db: Path) -> dict:
    """Committed staging state, read through a second connection."""
    conn = sqlite3.connect(db)
    try:
        def count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        return {
            "provenance": count("SELECT COUNT(*) FROM ai_provenance"),
            "provenance_accepted": count("SELECT COUNT(accepting_steward) FROM ai_provenance"),
            "pending": count("SELECT COUNT(*) FROM proposed_interpretations WHERE status = 'pending'"),
            "accepted": count("SELECT COUNT(*) FROM proposed_interpretations WHERE status = 'accepted'"),
            "interpretations": count("SELECT COUNT(*) FROM interpretations"),
        }
    finally:
        conn.close()


def _fail(*_args, **_kwargs):
    raise InjectedFailure


def _propose(store: SQLiteStore, ids: dict) -> dict:
    return propose_interpretation(
        observation_id=ids["obs_id"],
        perspective="literary",
        text="The green light symbolises deferred hope.",
        evidential_status="speculative",
        generating_model="fake-model",
        prompt_reference="sha256:abc123",
        prompt_reference_type="hash",
        conn=store,
        generation_timestamp=GENERATED_AT,
        parent_object_ids=[ids["obs_id"]],
    )


def test_a_failed_proposal_write_leaves_no_provenance_behind(study, monkeypatch):
    store, ids = study
    before = _state(store.db_path)
    monkeypatch.setattr(store, "insert_proposed_interpretation", _fail)
    with pytest.raises(InjectedFailure):
        _propose(store, ids)
    assert _state(store.db_path) == before

    monkeypatch.undo()
    _propose(store, ids)
    assert _state(store.db_path) == {**before, "provenance": before["provenance"] + 1, "pending": before["pending"] + 1}


@pytest.mark.parametrize("failing_write", ["complete_ai_provenance_acceptance", "insert_interpretation_with_provenance"])
def test_a_failed_acceptance_write_leaves_the_proposal_pending_and_retryable(study, monkeypatch, failing_write):
    store, ids = study
    proposal = _propose(store, ids)
    before = _state(store.db_path)
    monkeypatch.setattr(store, failing_write, _fail)
    with pytest.raises(InjectedFailure):
        accept_proposed_interpretation(proposal["id"], "steward-1", "Grounded.", store)
    assert _state(store.db_path) == before

    monkeypatch.undo()
    accept_proposed_interpretation(proposal["id"], "steward-1", "Grounded.", store)  # the steward's retry
    assert _state(store.db_path) == {
        **before,
        "provenance_accepted": 1,
        "pending": 0,
        "accepted": 1,
        "interpretations": before["interpretations"] + 1,
    }


def test_staging_inside_a_caller_block_belongs_to_that_block(study):
    store, ids = study
    before = _state(store.db_path)
    with pytest.raises(InjectedFailure):
        with store.atomic():
            proposal = _propose(store, ids)
            accept_proposed_interpretation(proposal["id"], "steward-1", "Grounded.", store)
            _fail()
    assert _state(store.db_path) == before


def test_a_concurrent_second_acceptance_is_refused_as_a_staging_error(study):
    """The pending check runs under the write lock, so the loser sees 'accepted', not a trigger failure."""
    store, ids = study
    proposal = _propose(store, ids)
    before = _state(store.db_path)
    first, second = SQLiteStore(store.db_path), SQLiteStore(store.db_path)
    read_done, release = threading.Event(), threading.Event()
    real_read = first.get_proposed_interpretation

    def read_then_hold(proposal_id):
        row = real_read(proposal_id)
        read_done.set()
        release.wait(5)
        return row

    first.get_proposed_interpretation = read_then_hold
    outcomes: dict[str, object] = {}

    def accept(label: str, store_: SQLiteStore) -> None:
        try:
            accept_proposed_interpretation(proposal["id"], f"steward-{label}", "Grounded.", store_)
            outcomes[label] = "accepted"
        except Exception as exc:  # recorded and asserted below
            outcomes[label] = exc

    one = threading.Thread(target=accept, args=("one", first))
    two = threading.Thread(target=accept, args=("two", second))
    try:
        one.start()
        assert read_done.wait(5)
        two.start()
        two.join(0.5)  # it waits for the lock, or (without one) runs to completion
        release.set()
        one.join(10)
        two.join(10)
    finally:
        release.set()
        first.close()
        second.close()

    assert sorted(outcomes) == ["one", "two"]
    winners = [label for label, outcome in outcomes.items() if outcome == "accepted"]
    (loser,) = [outcome for outcome in outcomes.values() if outcome != "accepted"]
    assert len(winners) == 1
    assert isinstance(loser, StagingError) and "already 'accepted'" in str(loser)
    assert _state(store.db_path) == {
        **before,
        "provenance_accepted": 1,
        "pending": 0,
        "accepted": 1,
        "interpretations": before["interpretations"] + 1,
    }


@pytest.mark.parametrize("status", ["speculative", "contested"])
def test_a_second_acceptance_with_the_same_canonical_id_is_refused_not_reattributed(study, status):
    """Content identity excludes method, evidence and steward. Never claim the second provenance was inserted."""
    store, ids = study
    first = _propose(store, ids)
    accepted = accept_proposed_interpretation(first["id"], "steward-first", "Original review.", store)
    before = _state(store.db_path)
    second = propose_interpretation(
        observation_id=ids["obs_id"], perspective="literary",
        text=first["text"], evidential_status=status,
        generating_model="second-model", prompt_reference="sha256:def456",
        prompt_reference_type="hash", conn=store,
        generation_timestamp="2026-10-16T12:01:00+00:00",
        evidence_observation_ids=[ids["obs_id"]],
    )
    assert second["id"] != first["id"]
    before_second_acceptance = _state(store.db_path)
    with pytest.raises(StagingError, match="already exists"):
        accept_proposed_interpretation(second["id"], "steward-second", "Second review.", store)
    assert _state(store.db_path) == before_second_acceptance
    assert store.get_proposed_interpretation(second["id"])["status"] == "pending"
    row = store._conn.execute("SELECT * FROM interpretations WHERE id = ?", (accepted["id"],)).fetchone()
    assert row["ai_provenance_id"] == first["ai_provenance_id"]
    assert row["evidential_status"] == first["evidential_status"]
    assert before["interpretations"] == before_second_acceptance["interpretations"]


def test_a_human_authored_canonical_interpretation_is_not_silently_reattributed(study):
    store, ids = study
    staged = _propose(store, ids)
    existing_id = make_interpretation_id(ids["obs_id"], staged["perspective"], staged["text"])
    store.insert_interpretation({
        "id": existing_id, "observation_id": ids["obs_id"], "perspective": staged["perspective"],
        "perspective_id": None, "text": staged["text"], "evidential_status": "contested",
        "evidence_observation_ids": "[]", "confidence": "human",
        "source": "steward-authored", "ai_provenance_id": None, "created_at": GENERATED_AT,
    })
    before = _state(store.db_path)
    with pytest.raises(StagingError, match="already exists"):
        accept_proposed_interpretation(staged["id"], "steward-1", "Reviewed.", store)
    assert _state(store.db_path) == before
    row = store._conn.execute("SELECT * FROM interpretations WHERE id = ?", (existing_id,)).fetchone()
    assert row["source"] == "steward-authored"
    assert row["ai_provenance_id"] is None


def test_silently_ignored_canonical_insert_rolls_back_acceptance(study):
    """A legacy INSERT OR IGNORE must not make an empty insert look like a steward promotion."""
    store, ids = study
    staged = _propose(store, ids)
    before = _state(store.db_path)
    store._conn.execute("""
        CREATE TEMP TRIGGER ignore_new_interpretation
        BEFORE INSERT ON main.interpretations
        BEGIN SELECT RAISE(IGNORE); END
    """)
    with pytest.raises(StagingError, match="not persisted exactly"):
        accept_proposed_interpretation(staged["id"], "steward-1", "Reviewed.", store)
    assert _state(store.db_path) == before
    assert store.get_proposed_interpretation(staged["id"])["status"] == "pending"


@pytest.mark.parametrize("winner", ["accept", "reject"])
def test_accept_and_reject_race_has_one_terminal_decision(study, winner):
    store, ids = study
    staged = _propose(store, ids)
    before = _state(store.db_path)
    first, second = SQLiteStore(store.db_path), SQLiteStore(store.db_path)
    read_done, release = threading.Event(), threading.Event()
    real_get = first.get_proposed_interpretation

    def read_then_hold(proposal_id):
        row = real_get(proposal_id)
        read_done.set()
        assert release.wait(5)
        return row

    first.get_proposed_interpretation = read_then_hold
    results = {}

    def decide(role, conn):
        try:
            if role == "accept":
                accept_proposed_interpretation(staged["id"], "steward-" + role, "Reviewed.", conn)
            else:
                reject_proposed_interpretation(staged["id"], "steward-" + role, "Rejected.", conn)
            results[role] = "success"
        except Exception as exc:
            results[role] = exc

    loser = "reject" if winner == "accept" else "accept"
    t1 = threading.Thread(target=decide, args=(winner, first))
    t2 = threading.Thread(target=decide, args=(loser, second))
    try:
        t1.start()
        assert read_done.wait(5)
        t2.start()
        t2.join(0.2)
        release.set()
        t1.join(10)
        t2.join(10)
    finally:
        release.set()
        first.close()
        second.close()

    assert set(results) == {"accept", "reject"}
    assert results[winner] == "success"
    assert isinstance(results[loser], StagingError)
    assert "already" in str(results[loser])
    assert store.get_proposed_interpretation(staged["id"])["status"] == (
        "accepted" if winner == "accept" else "rejected"
    )
    after = _state(store.db_path)
    expected = 1 if winner == "accept" else 0
    assert after["interpretations"] == before["interpretations"] + expected
    assert after["provenance_accepted"] == before["provenance_accepted"] + expected


@pytest.mark.parametrize("mode", ["triage", "interpretive", "skeptical"])
def test_response_mode_is_part_of_the_atomic_proposal_record(study, mode):
    store, ids = study
    p = propose_interpretation(
        observation_id=ids["obs_id"], perspective="literary", text="An alternative reading.",
        evidential_status="speculative", generating_model="fake-model",
        prompt_reference="sha256:abc123", prompt_reference_type="hash", conn=store,
        generation_timestamp=GENERATED_AT, response_mode=mode,
    )
    with sqlite3.connect(store.db_path) as other:
        row = other.execute(
            "SELECT status, response_mode, ai_provenance_id FROM proposed_interpretations WHERE id = ?",
            (p["id"],),
        ).fetchone()
    assert row == ("pending", mode, p["ai_provenance_id"])
    assert p["response_mode"] == mode


def test_generate_route_does_not_mutate_mode_in_a_second_transaction():
    app = (Path(__file__).resolve().parents[1] / "hermeneia/web/app.py").read_text()
    start = app.index("def api_e10_generate_interpretations():")
    end = app.index("def api_e10_discover", start)
    generate = app[start:end]
    assert "response_mode=response_mode" in generate
    assert "UPDATE proposed_interpretations SET response_mode" not in generate
