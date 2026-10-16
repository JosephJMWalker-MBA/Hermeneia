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
)
from hermeneia.storage.sqlite import SQLiteStore
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
