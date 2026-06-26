"""
Era II Sprint E6 — Witness Layer tests.

Verifies:
- WitnessSession as a canonical, immutable, append-only verification object
- Orthogonality with StewardDecision (different axis: reception, not governance)
- Directionality: WitnessSession.rendered_narrative_id → rendered_narratives.id
- rendered_narratives table has no witness_session_id column (sealed)
- Immutability triggers: UPDATE and DELETE rejected
- Supersession: a corrected session supersedes the old via supersession_relations
- witness_summary projection: aggregate completion rates by profile
- understanding_ledger projection: detailed session view
- Cross-projection invariants: session counts agree
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermeneia.compiler.projections.understanding_ledger import understanding_ledger
from hermeneia.compiler.projections.witness_summary import witness_summary
from hermeneia.compiler.witness.session import record_witness_session
from hermeneia.storage.hashing import make_witness_session_id
from hermeneia.storage.sqlite import SQLiteStore

import sys
sys.path.insert(0, str(Path(__file__).parent))
from test_constitutional_p0 import _seed_full_chain


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def store_ids(tmp_path):
    store = SQLiteStore(tmp_path / "test.db")
    ids = _seed_full_chain(store, architect_terms=["evidence", "fixed"])
    yield store, ids
    store.close()


# ── WitnessSession canonical object ──────────────────────────────────────────

def test_record_session_returns_dict(store_ids):
    store, ids = store_ids
    session = record_witness_session(
        ids["narrative_id"], "8-year-old",
        "Explain the main idea back in your own words.",
        True, "facilitator-1", store._conn,
    )
    assert isinstance(session, dict)
    assert session["rendered_narrative_id"] == ids["narrative_id"]
    assert session["witness_profile"] == "8-year-old"
    assert session["task_completed"] == 1


def test_record_session_id_content_addressable(store_ids):
    """Same narrative + profile + date → same session ID."""
    store, ids = store_ids
    date = "2026-06-20"
    s = record_witness_session(
        ids["narrative_id"], "80-year-old",
        "Answer: what does this document ask you to do?",
        False, "facilitator-1", store._conn, session_date=date,
    )
    expected = make_witness_session_id(ids["narrative_id"], "80-year-old", date)
    assert s["id"] == expected


def test_record_session_persisted(store_ids):
    store, ids = store_ids
    record_witness_session(
        ids["narrative_id"], "8-year-old",
        "Explain the main idea.",
        True, "facilitator-1", store._conn,
    )
    rows = store.sessions_for_narrative(ids["narrative_id"])
    assert len(rows) == 1
    assert rows[0]["witness_profile"] == "8-year-old"


def test_record_session_notes_optional(store_ids):
    store, ids = store_ids
    s = record_witness_session(
        ids["narrative_id"], "general",
        "Summarize in one sentence.",
        True, "facilitator-1", store._conn,
    )
    assert s["notes"] is None


def test_record_session_notes_stored_when_provided(store_ids):
    store, ids = store_ids
    s = record_witness_session(
        ids["narrative_id"], "general",
        "Summarize in one sentence.",
        True, "facilitator-1", store._conn,
        notes="Witness paused twice but completed unaided.",
    )
    assert s["notes"] == "Witness paused twice but completed unaided."


def test_record_session_task_not_completed(store_ids):
    store, ids = store_ids
    s = record_witness_session(
        ids["narrative_id"], "8-year-old",
        "What is the main argument?",
        False, "facilitator-1", store._conn,
    )
    assert s["task_completed"] == 0


# ── Input validation ─────────────────────────────────────────────────────────

def test_empty_witness_profile_rejected(store_ids):
    store, ids = store_ids
    with pytest.raises(ValueError, match="witness_profile"):
        record_witness_session(ids["narrative_id"], "  ", "Task.", True, "facilitator-1", store._conn)


def test_empty_task_description_rejected(store_ids):
    store, ids = store_ids
    with pytest.raises(ValueError, match="task_description"):
        record_witness_session(ids["narrative_id"], "8-year-old", "", True, "facilitator-1", store._conn)


def test_empty_facilitated_by_rejected(store_ids):
    store, ids = store_ids
    with pytest.raises(ValueError, match="facilitated_by"):
        record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True, "", store._conn)


def test_nonexistent_narrative_rejected(store_ids):
    store, ids = store_ids
    with pytest.raises(ValueError, match="RenderedNarrative"):
        record_witness_session("nonexistent-id", "8-year-old", "Task.", True, "facilitator-1", store._conn)


# ── Immutability ─────────────────────────────────────────────────────────────

def test_witness_session_update_rejected(store_ids):
    store, ids = store_ids
    s = record_witness_session(
        ids["narrative_id"], "8-year-old", "Task.", True, "facilitator-1", store._conn
    )
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute(
            "UPDATE witness_sessions SET task_completed = 0 WHERE id = ?", (s["id"],)
        )


def test_witness_session_delete_rejected(store_ids):
    store, ids = store_ids
    s = record_witness_session(
        ids["narrative_id"], "8-year-old", "Task.", True, "facilitator-1", store._conn
    )
    with pytest.raises(Exception, match="immutable"):
        store._conn.execute("DELETE FROM witness_sessions WHERE id = ?", (s["id"],))


# ── Directionality constraint ────────────────────────────────────────────────

def test_rendered_narratives_has_no_witness_session_column(store_ids):
    """rendered_narratives must not reference WitnessSession — sealed table."""
    store, ids = store_ids
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(rendered_narratives)").fetchall()}
    assert "witness_session_id" not in cols


def test_witness_session_references_narrative(store_ids):
    """witness_sessions.rendered_narrative_id FK enforced — wrong ID must fail."""
    store, ids = store_ids
    with pytest.raises(Exception):
        store._conn.execute(
            """
            INSERT INTO witness_sessions
                (id, rendered_narrative_id, witness_profile, task_description,
                 task_completed, notes, facilitated_by, session_date,
                 constitution_version, created_at)
            VALUES
                ('test-id', 'nonexistent-narrative', '8-year-old', 'Task.',
                 1, NULL, 'facilitator-1', '2026-06-20', '1.0',
                 '2026-06-20T00:00:00+00:00')
            """
        )
        store._conn.commit()


# ── Orthogonality with StewardDecision ───────────────────────────────────────

def test_witness_and_steward_coexist_independently(store_ids):
    """WitnessSession and StewardDecision can both exist for the same narrative
    without referencing each other."""
    from hermeneia.compiler.evaluation_functions.structural import evaluate_structural
    from hermeneia.compiler.stewardship.decision import record_steward_decision

    store, ids = store_ids
    findings = evaluate_structural(ids["narrative_id"], ids["plan_id"], store._conn)
    store.insert_findings_batch(findings)
    fid = findings[0]["id"]

    # Record a StewardDecision (governs a Finding)
    record_steward_decision(fid, "accepted", "Approved.", "steward-1", store._conn)

    # Record a WitnessSession (tests the RenderedNarrative)
    record_witness_session(
        ids["narrative_id"], "8-year-old", "Explain the idea.", True, "facilitator-1", store._conn
    )

    # Both exist; neither references the other
    decisions = store.decisions_for_finding(fid)
    sessions = store.sessions_for_narrative(ids["narrative_id"])
    assert len(decisions) == 1
    assert len(sessions) == 1
    assert "witness_session_id" not in dict(decisions[0])
    assert "steward_decision_id" not in dict(sessions[0])


# ── Supersession ─────────────────────────────────────────────────────────────

def test_session_supersession_via_relation(store_ids):
    """A corrected session supersedes the old; both remain accessible."""
    store, ids = store_ids
    date1, date2 = "2026-06-20", "2026-06-21"
    s1 = record_witness_session(
        ids["narrative_id"], "8-year-old", "Explain the main idea.", False,
        "facilitator-1", store._conn, session_date=date1,
        notes="Witness was unfamiliar with the topic domain.",
    )
    s2 = record_witness_session(
        ids["narrative_id"], "8-year-old", "Explain the main idea.", True,
        "facilitator-1", store._conn, session_date=date2,
        notes="Repeated session with simplified preamble — completed unaided.",
    )

    store.insert_supersession_relation({
        "old_id": s1["id"],
        "new_id": s2["id"],
        "reason": "Initial session had confounding domain unfamiliarity; repeated with corrected setup.",
        "ratified_at": date2,
    })

    sessions = store.sessions_for_narrative(ids["narrative_id"])
    assert len(sessions) == 2

    supersessions = store.supersessions_from(s1["id"])
    assert len(supersessions) == 1
    assert supersessions[0]["new_id"] == s2["id"]


def test_witness_session_in_supersession_existence_check(store_ids):
    """Supersession existence trigger recognizes witness_sessions IDs."""
    store, ids = store_ids
    s1 = record_witness_session(
        ids["narrative_id"], "general", "Task.", True,
        "facilitator-1", store._conn, session_date="2026-06-20",
    )
    s2 = record_witness_session(
        ids["narrative_id"], "general", "Task.", True,
        "facilitator-1", store._conn, session_date="2026-06-21",
    )
    store.insert_supersession_relation({
        "old_id": s1["id"],
        "new_id": s2["id"],
        "reason": "Corrected session setup.",
        "ratified_at": "2026-06-21",
    })
    old = store._conn.execute(
        "SELECT id FROM witness_sessions WHERE id = ?", (s1["id"],)
    ).fetchone()
    assert old is not None


# ── witness_summary projection ───────────────────────────────────────────────

def test_witness_summary_empty_before_sessions(store_ids):
    store, ids = store_ids
    result = witness_summary(ids["narrative_id"], store._conn)
    assert result["total_sessions"] == 0
    assert result["completed"] == 0
    assert result["by_profile"] == {}


def test_witness_summary_tracks_completion(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    record_witness_session(ids["narrative_id"], "80-year-old", "Task.", False,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    result = witness_summary(ids["narrative_id"], store._conn)
    assert result["total_sessions"] == 2
    assert result["completed"] == 1
    assert result["not_completed"] == 1


def test_witness_summary_by_profile(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-21")
    record_witness_session(ids["narrative_id"], "80-year-old", "Task.", False,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    result = witness_summary(ids["narrative_id"], store._conn)
    assert result["by_profile"]["8-year-old"]["completed"] == 2
    assert result["by_profile"]["80-year-old"]["not_completed"] == 1


def test_witness_summary_is_read_only(store_ids):
    store, ids = store_ids
    count_before = store.witness_session_count()
    witness_summary(ids["narrative_id"], store._conn)
    assert store.witness_session_count() == count_before


def test_witness_summary_regeneratable(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    r1 = witness_summary(ids["narrative_id"], store._conn)
    r2 = witness_summary(ids["narrative_id"], store._conn)
    r1.pop("generated_at"); r2.pop("generated_at")
    assert r1 == r2


def test_witness_summary_unknown_narrative(store_ids):
    store, ids = store_ids
    result = witness_summary("nonexistent-id", store._conn)
    assert "error" in result
    assert result["total_sessions"] == 0


# ── understanding_ledger projection ──────────────────────────────────────────

def test_understanding_ledger_empty_before_sessions(store_ids):
    store, ids = store_ids
    result = understanding_ledger(ids["narrative_id"], store._conn)
    assert result["session_count"] == 0
    assert result["sessions"] == []
    assert result["profiles_tested"] == []


def test_understanding_ledger_records_sessions(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Explain the main idea.",
                           True, "facilitator-1", store._conn, session_date="2026-06-20")
    result = understanding_ledger(ids["narrative_id"], store._conn)
    assert result["session_count"] == 1
    s = result["sessions"][0]
    assert s["witness_profile"] == "8-year-old"
    assert s["task_completed"] is True
    assert "task_description" in s
    assert "facilitated_by" in s
    assert "session_date" in s


def test_understanding_ledger_profiles_tested(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    record_witness_session(ids["narrative_id"], "80-year-old", "Task.", False,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    result = understanding_ledger(ids["narrative_id"], store._conn)
    assert set(result["profiles_tested"]) == {"8-year-old", "80-year-old"}


def test_understanding_ledger_is_read_only(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "general", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    count_before = store.witness_session_count()
    understanding_ledger(ids["narrative_id"], store._conn)
    assert store.witness_session_count() == count_before


def test_understanding_ledger_regeneratable(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    r1 = understanding_ledger(ids["narrative_id"], store._conn)
    r2 = understanding_ledger(ids["narrative_id"], store._conn)
    r1.pop("generated_at"); r2.pop("generated_at")
    assert r1 == r2


def test_understanding_ledger_unknown_narrative(store_ids):
    store, ids = store_ids
    result = understanding_ledger("nonexistent-id", store._conn)
    assert "error" in result
    assert result["session_count"] == 0


# ── Cross-projection consistency ─────────────────────────────────────────────

def test_summary_and_ledger_agree_on_total(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    record_witness_session(ids["narrative_id"], "80-year-old", "Task.", False,
                           "facilitator-2", store._conn, session_date="2026-06-20")
    summary = witness_summary(ids["narrative_id"], store._conn)
    ledger = understanding_ledger(ids["narrative_id"], store._conn)
    assert summary["total_sessions"] == ledger["session_count"]


def test_summary_and_ledger_agree_on_profiles(store_ids):
    store, ids = store_ids
    record_witness_session(ids["narrative_id"], "8-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    record_witness_session(ids["narrative_id"], "80-year-old", "Task.", True,
                           "facilitator-1", store._conn, session_date="2026-06-20")
    summary = witness_summary(ids["narrative_id"], store._conn)
    ledger = understanding_ledger(ids["narrative_id"], store._conn)
    assert set(summary["by_profile"].keys()) == set(ledger["profiles_tested"])
