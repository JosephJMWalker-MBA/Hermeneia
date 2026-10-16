"""SQLiteStore record writers defer their commit inside store.atomic().

atomic() promises all or nothing: a writer called inside the block must not
commit on its own, so an exception later in the block rolls its write back.
Outside atomic() every writer still commits at once, so a caller that closes
the store and reads through another connection (the upload route's
source-role write) still sees the row.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Callable

import pytest

from hermeneia.perspective_identity import frame_v2_row_from_draft
from hermeneia.storage.hashing import (
    make_critic_report_id,
    make_expression_profile_id,
    make_finding_id,
    make_interpretation_id,
    make_perspective_id,
    make_ratification_record_id,
    make_rendered_narrative_id,
    make_steward_decision_id,
    make_validation_report_id,
    make_witness_session_id,
)
from hermeneia.storage.sqlite import SQLiteStore
from test_constitutional_p0 import _seed_full_chain

NOW = "2026-10-16T12:00:00+00:00"


class LaterFailure(Exception):
    """Raised inside the block after the write under test."""


@dataclass(frozen=True)
class Writer:
    write: Callable[[SQLiteStore, dict], object]
    probe: str  # SQL for one value the write changes
    prepare: Callable[[SQLiteStore, dict], object] = lambda store, ids: None  # committed first, outside atomic()


@pytest.fixture
def chain(tmp_path):
    store = SQLiteStore(tmp_path / "workspace.db")
    ids = _seed_full_chain(store, include_report=False)
    try:
        yield store, ids
    finally:
        store.close()


def _committed(db: Path, sql: str):
    """Read through a second connection, which sees only committed state."""
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def _interpretation(ids: dict, text: str) -> dict:
    return {
        "id": make_interpretation_id(ids["obs_id"], "literary", text),
        "observation_id": ids["obs_id"],
        "perspective": "literary",
        "perspective_id": None,
        "text": text,
        "evidential_status": "contested",
        "evidence_observation_ids": json.dumps([ids["obs_id"]]),
        "confidence": 0.5,
        "source": "test",
        "created_at": NOW,
    }


WRITERS: dict[str, Writer] = {}

# --- source scope, interpretations, supersession ---

WRITERS["set_document_scope"] = Writer(
    write=lambda store, ids: store.set_document_scope(ids["doc_id"], source_role="reference"),
    probe="SELECT source_role FROM source_documents",
)
WRITERS["insert_interpretation"] = Writer(
    write=lambda store, ids: store.insert_interpretation(_interpretation(ids, "A second reading.")),
    probe="SELECT COUNT(*) FROM interpretations",
)
WRITERS["insert_supersession_relation"] = Writer(
    prepare=lambda store, ids: store.insert_interpretation(_interpretation(ids, "A revised reading.")),
    write=lambda store, ids: store.insert_supersession_relation({
        "old_id": ids["interp_id"],
        "new_id": _interpretation(ids, "A revised reading.")["id"],
        "reason": "Revised.",
        "ratified_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM supersession_relations",
)

# --- perspectives ---


def _frame(purpose: str = "Examine how institutions gain, lose, or borrow legitimacy.", predecessor: str | None = None) -> dict:
    draft = {
        "label": "Institutional Trust Reader",
        "purpose": purpose,
        "questions": ["Who is expected to trust whom?"],
        "challenges": ["Challenge unsupported legitimacy claims."],
        "limitations": ["May overemphasize institutions."],
    }
    return frame_v2_row_from_draft(draft, declared_by="Primary Human Steward", declared_date=NOW,
                                   predecessor_perspective_id=predecessor)[0]


def _revise(store: SQLiteStore, ids: dict | None = None) -> dict:
    root = _frame()["id"]
    return store.insert_perspective_revision(root, _frame("Trace how institutions ask to be believed.", root),
                                             "Sharper trust language.", NOW)


PERSPECTIVES_AND_EDGES = "SELECT (SELECT COUNT(*) FROM perspectives) || '/' || (SELECT COUNT(*) FROM supersession_relations)"

WRITERS["register_perspective"] = Writer(
    write=lambda store, ids: store.register_perspective({
        "id": make_perspective_id("historical"), "name": "historical", "description": "", "created_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM perspectives",
)
WRITERS["insert_frame_perspective"] = Writer(
    write=lambda store, ids: store.insert_frame_perspective(_frame()),
    probe="SELECT COUNT(*) FROM perspectives",
)
WRITERS["insert_perspective_revision"] = Writer(
    prepare=lambda store, ids: store.insert_frame_perspective(_frame()),
    write=_revise,
    probe=PERSPECTIVES_AND_EDGES,
)


# --- expression chain ---

WRITERS["insert_expression_profile"] = Writer(
    write=lambda store, ids: store.insert_expression_profile({
        "id": make_expression_profile_id("plain-en"), "slug": "plain-en", "name": "Plain English",
        "description": "Test profile", "language": "en", "audience": "general", "reading_level": "general",
        "tone": "plain", "voice": "active", "artist_prompt": "Write plainly.", "critic_expectations": "[]",
        "source": "test", "created_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM expression_profiles",
)
WRITERS["insert_rendered_narrative"] = Writer(
    write=lambda store, ids: store.insert_rendered_narrative({
        "id": make_rendered_narrative_id(ids["plan_id"], "other", ids["profile_id"]),
        "architect_plan_id": ids["plan_id"], "provider": "other", "expression_profile_id": ids["profile_id"],
        "text": "Evidence remains fixed.", "prompt_used": "Test prompt.", "created_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM rendered_narratives",
)
WRITERS["insert_validation_report"] = Writer(
    write=lambda store, ids: store.insert_validation_report({
        "id": make_validation_report_id(ids["narrative_id"]), "rendered_narrative_id": ids["narrative_id"],
        "architect_plan_id": ids["plan_id"], "expression_profile_id": ids["profile_id"],
        "semantic_fidelity": 1.0, "required_terms_present": "[]", "required_terms_missing": "[]",
        "unsupported_claims": "[]", "omitted_observations": "[]", "omitted_interpretations": "[]",
        "semantic_drift": 0.0, "warnings": "[]", "approved": 1, "created_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM validation_reports",
)

# --- Critic and governance records ---


def _critic_report(ids: dict) -> dict:
    return {
        "id": make_critic_report_id("proposal-1", "conservative", NOW), "proposal_id": "proposal-1",
        "observation_id": ids["obs_id"], "policy": "conservative", "claims": "[]", "evidence_passages": "[]",
        "overall_verdict": "supported", "normalized": 0, "normalization_notes": None,
        "generated_at": NOW, "created_at": NOW,
    }


def _finding_id(ids: dict) -> str:
    return make_finding_id(ids["narrative_id"], "structural", "o" * 64)


def _insert_finding(store: SQLiteStore, ids: dict) -> None:
    store.insert_findings_batch([{
        "id": _finding_id(ids), "rendered_narrative_id": ids["narrative_id"], "architect_plan_id": ids["plan_id"],
        "dimension": "structural", "obligation_id": "o" * 64, "operation": "preservation", "status": "preserved",
        "evidence": "{}", "evaluation_method": "structural-v1.0", "constitution_version": "{}", "created_at": NOW,
    }])


WRITERS["insert_critic_report"] = Writer(
    write=lambda store, ids: store.insert_critic_report(_critic_report(ids)),
    probe="SELECT COUNT(*) FROM critic_reports",
)
WRITERS["mark_critic_report_normalized"] = Writer(
    prepare=lambda store, ids: store.insert_critic_report(_critic_report(ids)),
    write=lambda store, ids: store.mark_critic_report_normalized(_critic_report(ids)["id"], "Claims reviewed."),
    probe="SELECT normalized FROM critic_reports",
)
WRITERS["insert_ratification_record"] = Writer(
    write=lambda store, ids: store.insert_ratification_record({
        "id": make_ratification_record_id(ids["narrative_id"], "steward", NOW),
        "rendered_narrative_id": ids["narrative_id"], "ratified_by": "steward", "ratified_at": NOW,
        "steward_declaration": "Ratified.", "finding_count": 0, "steward_decision_count": 0,
        "witness_session_count": 0, "constitution_version": "{}", "audit_snapshot": "{}", "created_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM ratification_records",
)
WRITERS["insert_witness_session"] = Writer(
    write=lambda store, ids: store.insert_witness_session({
        "id": make_witness_session_id(ids["narrative_id"], "general-reader", NOW),
        "rendered_narrative_id": ids["narrative_id"], "witness_profile": "general-reader",
        "task_description": "Summarize the claim.", "task_completed": 1, "notes": None,
        "facilitated_by": "steward", "session_date": NOW, "constitution_version": "{}", "created_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM witness_sessions",
)
WRITERS["insert_steward_decision"] = Writer(
    prepare=_insert_finding,
    write=lambda store, ids: store.insert_steward_decision({
        "id": make_steward_decision_id(_finding_id(ids), "accepted", NOW), "finding_id": _finding_id(ids),
        "verdict": "accepted", "rationale": "Preserved.", "steward_id": "steward", "decided_at": NOW,
        "constitution_version": "{}", "created_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM steward_decisions",
)


def test_a_repeated_revision_inside_atomic_does_not_commit_the_block_early(chain):
    store, _ids = chain
    store.insert_frame_perspective(_frame())
    _revise(store)  # committed; the repeat below takes the idempotent path
    before = _committed(store.db_path, "SELECT COUNT(*) FROM perspectives")
    with pytest.raises(LaterFailure):
        with store.atomic():
            store.register_perspective({
                "id": make_perspective_id("historical"), "name": "historical", "description": "", "created_at": NOW,
            })
            _revise(store)
            raise LaterFailure
    assert _committed(store.db_path, "SELECT COUNT(*) FROM perspectives") == before


def test_a_refused_revision_inside_atomic_undoes_only_its_own_writes(chain):
    """The refusal comes after the successor row is written; the caller catches it and the block goes on."""
    store, _ids = chain
    store.insert_frame_perspective(_frame())
    store._conn.execute("""
        CREATE TEMP TRIGGER refuse_supersession BEFORE INSERT ON supersession_relations
        BEGIN SELECT RAISE(ABORT, 'refused for this test'); END
    """)
    with store.atomic():
        store.register_perspective({
            "id": make_perspective_id("historical"), "name": "historical", "description": "", "created_at": NOW,
        })
        with pytest.raises(sqlite3.IntegrityError, match="refused for this test"):
            _revise(store)
    assert _committed(store.db_path, "SELECT COUNT(*) FROM perspectives WHERE name = 'historical'") == 1  # the block's own write
    assert _committed(store.db_path, PERSPECTIVES_AND_EDGES) == "3/0"  # literary, historical, root; no successor


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_a_later_failure_inside_atomic_rolls_the_write_back(chain, name):
    store, ids = chain
    writer = WRITERS[name]
    writer.prepare(store, ids)
    before = _committed(store.db_path, writer.probe)
    with pytest.raises(LaterFailure):
        with store.atomic():
            writer.write(store, ids)
            assert store._conn.execute(writer.probe).fetchone()[0] != before  # written inside the block
            assert _committed(store.db_path, writer.probe) == before  # but not committed
            raise LaterFailure
    assert _committed(store.db_path, writer.probe) == before


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_outside_atomic_the_write_commits_at_once(chain, name):
    store, ids = chain
    writer = WRITERS[name]
    writer.prepare(store, ids)
    before = _committed(store.db_path, writer.probe)
    writer.write(store, ids)
    assert _committed(store.db_path, writer.probe) != before
