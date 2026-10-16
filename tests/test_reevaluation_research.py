"""Research (not product behavior): how could a ratified, revised evaluator record a new determination for an existing
obligation while preserving the original Finding, its ID and its steward decisions?

Evidence for docs/design/historical-reevaluation-research-2026-10-16.md and proposed ADR-0049. Every option is
prototyped here, on test databases only. Product code, Finding identity and the schema are not changed. The scenario
is real product data:
- a restored study with provenance-v1.0 Findings (two `transformed` for absent records, two `preserved`, one
  `omitted`);
- a steward decision on one of the `transformed` Findings;
- the ADR-0046 vocabulary migration (test DB only), with `unverifiable` admitted for the run.
provenance-v1.1 then re-evaluates the same five obligations.
"""
from __future__ import annotations

import hashlib
import sqlite3

import pytest

import synthetic_study_lab as lab
from adr0046_witness_state import Pair, connect, rows
from hermeneia.compiler.evaluation_functions import provenance
from hermeneia.storage import sqlite as storage
from hermeneia.storage.findings_vocabulary import migrate_findings_vocabulary
from hermeneia.storage.sqlite import FindingLedgerRefusal

V10, V11 = provenance.EVALUATION_METHOD, provenance.UNVERIFIABLE_METHOD


class Scenario:
    def __init__(self, pair: Pair):
        self.pair, self.db = pair, pair.restored
        pair.four_states()
        conn = connect(self.db)
        try:
            self.v10 = provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, conn, method=V10)
            self.v11 = provenance.evaluate_provenance(pair.narrative_id, pair.plan_id, conn, method=V11)
        finally:
            conn.close()
        pair.persist(self.db, self.v10)
        self.decided = next(f for f in self.v10 if f["status"] == "transformed")
        conn = connect(self.db)
        conn.execute("INSERT INTO steward_decisions (id, finding_id, verdict, rationale, steward_id, decided_at, "
                     "constitution_version, created_at) VALUES ('sd', ?, 'accepted', 'Reviewed as recorded.', 'steward', 't', '{}', 't')",
                     (self.decided["id"],))
        conn.commit()
        conn.close()
        migrate_findings_vocabulary(self.db)
        self.original = rows(self.db, "findings")
        self.changed = [n for o, n in zip(self.v10, self.v11) if (o["operation"], o["status"]) != (n["operation"], n["status"])]

    def decision(self) -> dict:
        conn = connect(self.db)
        try:
            return dict(conn.execute("SELECT s.finding_id, f.status FROM steward_decisions s JOIN findings f ON f.id = s.finding_id").fetchone())
        finally:
            conn.close()

    def schema(self) -> list[tuple]:
        conn = sqlite3.connect(self.db)
        try:
            return [tuple(r) for r in conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name")]
        finally:
            conn.close()


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ACTIVE_DIMENSION_DISPOSITIONS", dict(storage.PENDING_DIMENSION_DISPOSITIONS))
    with lab.isolated(tmp_path):
        yield Scenario(Pair(tmp_path))


def test_the_scenario_has_changed_and_unchanged_obligations(scenario):
    assert sorted(f["status"] for f in scenario.v10) == ["omitted", "preserved", "preserved", "transformed", "transformed"]
    assert sorted(f["status"] for f in scenario.v11) == ["omitted", "preserved", "preserved", "unverifiable", "unverifiable"]
    assert [f["id"] for f in scenario.v10] == [f["id"] for f in scenario.v11]  # identity names the obligation only
    assert len(scenario.changed) == 2


def test_baseline_d3_refuses_the_revision_and_preserves_the_original(scenario):
    with pytest.raises(FindingLedgerRefusal) as refused:
        scenario.pair.persist(scenario.db, scenario.v11)
    assert refused.value.refusal_class == "divergent_result"
    assert sorted(refused.value.finding_ids) == sorted(f["id"] for f in scenario.changed)
    assert rows(scenario.db, "findings") == scenario.original
    assert scenario.decision() == {"finding_id": scenario.decided["id"], "status": "transformed"}


# ── Option A: method-versioned identity ─────────────────────────────────────

def _method_versioned_id(finding: dict) -> str:
    key = f"finding:{finding['rendered_narrative_id']}:{finding['dimension']}:{finding['obligation_id']}:{finding['evaluation_method']}"
    return hashlib.sha256(key.encode()).hexdigest()


def test_option_a_method_versioned_identity(scenario):
    schema_before = scenario.schema()
    revised = [dict(f, id=_method_versioned_id(f)) for f in scenario.v11]
    report = scenario.pair.persist(scenario.db, revised)
    stored = rows(scenario.db, "findings")
    # Every obligation gains a second Finding, including the three whose result did not change.
    assert len(report["inserted"]) == 5 and len(stored) == 10
    per_obligation = {}
    for finding in stored:
        per_obligation.setdefault(finding["obligation_id"], []).append(finding["status"])
    assert all(len(statuses) == 2 for statuses in per_obligation.values())  # "exactly one" needs a new "current" rule
    # The stored v1.0 identities do not follow the new formula: two identity rules would coexist permanently.
    assert all(_method_versioned_id(f) != f["id"] for f in scenario.v10)
    assert scenario.decision() == {"finding_id": scenario.decided["id"], "status": "transformed"}  # preserved
    assert scenario.schema() == schema_before  # no schema change; the cost is identity semantics for every dimension


# ── Option B: append-only evaluation occurrences ────────────────────────────

def test_option_b_append_only_occurrences(scenario):
    conn = sqlite3.connect(scenario.db)
    try:
        # A new canonical object would be needed; prototyped as a side table on the test database only.
        conn.execute("CREATE TABLE evaluation_occurrences (finding_id TEXT NOT NULL REFERENCES findings(id), "
                     "evaluation_method TEXT NOT NULL, operation TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL, "
                     "seq INTEGER NOT NULL, PRIMARY KEY (finding_id, evaluation_method))")
        for seq, method_findings in enumerate((scenario.v10, scenario.v11)):
            conn.executemany("INSERT INTO evaluation_occurrences VALUES (?, ?, ?, ?, ?, ?)",
                             [(f["id"], f["evaluation_method"], f["operation"], f["status"], f["evidence"], seq) for f in method_findings])
        conn.commit()
        current = dict(conn.execute("SELECT finding_id, status FROM evaluation_occurrences o WHERE seq = "
                                    "(SELECT MAX(seq) FROM evaluation_occurrences WHERE finding_id = o.finding_id)").fetchall())
    finally:
        conn.close()
    assert rows(scenario.db, "findings") == scenario.original  # Findings untouched
    # The steward decision binds to the Finding ID, so it now sits on a thread whose current determination it never
    # reviewed: it accepted "transformed", and the thread now says "unverifiable".
    assert current[scenario.decided["id"]] == "unverifiable"
    assert scenario.decision()["status"] == "transformed"
    # The Finding stops being "one bounded delta" (ADR-0041 §1): ontology change, schema change, and decisions would
    # have to rebind to occurrences.


# ── Option C: explicit revision with supersession ───────────────────────────

def _revision_id(predecessor_id: str, method: str) -> str:
    return hashlib.sha256(f"finding-revision:{predecessor_id}:{method}".encode()).hexdigest()


def _revise(scenario: Scenario, computed: list[dict], stored_by_id: dict, method: str, ratified_at: str) -> list[dict]:
    """Write a revision Finding only where the ratified method's result differs, and record the supersession."""
    revisions = [dict(f, id=_revision_id(stored_by_id[f["obligation_id"]], method)) for f in computed
                 if _status(scenario, stored_by_id[f["obligation_id"]]) != f["status"]]
    scenario.pair.persist(scenario.db, revisions)
    conn = sqlite3.connect(scenario.db)
    try:
        for revision in revisions:
            conn.execute("INSERT OR IGNORE INTO supersession_relations (old_id, new_id, reason, ratified_at) VALUES (?, ?, ?, ?)",
                         (stored_by_id[revision["obligation_id"]], revision["id"],
                          f"re-evaluated under {method} (ratified method change)", ratified_at))
        conn.commit()
    finally:
        conn.close()
    return revisions


def _status(scenario: Scenario, finding_id: str) -> str:
    conn = connect(scenario.db)
    try:
        return conn.execute("SELECT status FROM findings WHERE id = ?", (finding_id,)).fetchone()[0]
    finally:
        conn.close()


def _heads(scenario: Scenario) -> dict[str, str]:
    """The current Finding per obligation: the one no supersession relation replaces."""
    conn = connect(scenario.db)
    try:
        return {r["obligation_id"]: r["status"] for r in conn.execute(
            "SELECT obligation_id, status FROM findings f WHERE NOT EXISTS (SELECT 1 FROM supersession_relations s WHERE s.old_id = f.id)")}
    finally:
        conn.close()


def test_option_c_explicit_revision_with_supersession(scenario):
    schema_before = scenario.schema()
    first = {f["obligation_id"]: f["id"] for f in scenario.v10}
    revisions = _revise(scenario, scenario.v11, first, V11, "2026-10-16T00:00:00+00:00")
    stored = rows(scenario.db, "findings")
    assert len(revisions) == 2 and len(stored) == 7  # only the two changed obligations gain a Finding
    assert [f for f in stored if f["id"] in first.values()] == scenario.original  # originals byte-identical
    assert scenario.decision() == {"finding_id": scenario.decided["id"], "status": "transformed"}  # stays with what it reviewed
    assert _heads(scenario) == {f["obligation_id"]: f["status"] for f in scenario.v11}  # exactly one current per obligation
    assert scenario.schema() == schema_before  # existing tables and supersession guards accept it as they are
    # Idempotent: re-running the same ratified revision computes the same IDs and writes nothing new.
    again = [dict(f, id=_revision_id(first[f["obligation_id"]], V11)) for f in scenario.changed]
    assert scenario.pair.persist(scenario.db, again)["identical"] == [f["id"] for f in again]
    assert len(rows(scenario.db, "findings")) == 7


def test_option_c_chains_through_later_revisions_and_keeps_one_head(scenario):
    first = {f["obligation_id"]: f["id"] for f in scenario.v10}
    _revise(scenario, scenario.v11, first, V11, "2026-10-16T00:00:00+00:00")
    heads_v11 = {f["obligation_id"]: _revision_id(first[f["obligation_id"]], V11) for f in scenario.changed}
    # A hypothetical later ratified method revises one obligation again.
    later = dict(scenario.changed[0], id=_revision_id(heads_v11[scenario.changed[0]["obligation_id"]], "provenance-v1.2"),
                 evaluation_method="provenance-v1.2", operation="omission", status="omitted")
    scenario.pair.persist(scenario.db, [later])
    conn = sqlite3.connect(scenario.db)
    conn.execute("INSERT INTO supersession_relations VALUES (?, ?, 're-evaluated under provenance-v1.2', 't')",
                 (heads_v11[later["obligation_id"]], later["id"]))
    conn.commit()
    conn.close()
    heads = _heads(scenario)
    assert len(heads) == 5 and heads[later["obligation_id"]] == "omitted"
    assert len(rows(scenario.db, "findings")) == 8


def test_option_c_does_not_weaken_d3(scenario):
    """A revision is an explicit act; the ordinary write path still refuses a divergent result under the old ID."""
    first = {f["obligation_id"]: f["id"] for f in scenario.v10}
    _revise(scenario, scenario.v11, first, V11, "2026-10-16T00:00:00+00:00")
    with pytest.raises(FindingLedgerRefusal):
        scenario.pair.persist(scenario.db, scenario.v11)
