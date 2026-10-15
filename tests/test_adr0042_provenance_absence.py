"""ADR-0042 classifies a missing provenance record as a transformation: evidence for proposed ADR-0046.

Nothing here changes evaluation semantics; ADR-0046 is PROPOSED, not ratified.
- Passing tests pin what `provenance-v1.0` and the Finding store do today.
- Strict-xfail witnesses pin what the proposal says must stop. They must show XPASS(strict) only after the Primary
  Human Steward ratifies an amendment and it is implemented; only then are their markers removed.

The witness state is reached through the product's own routes: an earlier-exporter WBS bundle (no Observation
compile records) restores unchanged Observations without provenance. Plans and narratives are content-addressed,
so ratifying the same Blueprint on both sides yields the same plan, narrative and Finding IDs.
Proposal: docs/adr/ADR-0046-provenance-absence-is-not-transformation.md.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

import synthetic_study_lab as lab
from hermeneia.compiler.evaluation_functions.provenance import evaluate_provenance
from hermeneia.compiler.projections.trust_card import trust_card
from hermeneia.storage.hashing import make_expression_profile_id, make_rendered_narrative_id
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import export_workspace_bundle
from hermeneia.workspace.restore import restore_workspace

GENERATED_AT = "2026-10-15T12:00:00+00:00"
LINES = ["The lamp burned all night.", "Nobody asked why it burned.", "The keeper's ledger records only the oil.",
         "In the morning the wick was new."]
# Files an exporter with observation-compile-records-v1 writes; an earlier exporter writes none of them.
COMPILE_RECORD_FILES = {"corpus/provenance.json", "corpus/observation_derived.json", "corpus/terms.json",
                        "corpus/observation_terms.json"}
COMPILE_RECORD_COUNTS = ("provenance", "observation_derived", "terms", "observation_terms", "observations_without_provenance")
EVIDENCE_TABLES = ("source_documents", "source_extractions", "observations")


def _connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(db: Path, table: str) -> list[dict]:
    conn = _connect(db)
    try:
        return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}" ORDER BY id')]
    finally:
        conn.close()


def _as_earlier_exporter_bundle(bundle: Path) -> None:
    """The bundle an exporter without observation-compile-records-v1 writes (a no-op on such an exporter)."""
    manifest = json.loads((bundle / "manifest.json").read_text())
    listed = [entry["path"] for entry in manifest["files"] if entry["path"] in COMPILE_RECORD_FILES]
    if not listed:
        return
    for path in listed:
        (bundle / path).unlink()
    manifest["files"] = [entry for entry in manifest["files"] if entry["path"] not in COMPILE_RECORD_FILES]
    manifest["required_capabilities"] = [c for c in manifest.get("required_capabilities", [])
                                         if c != "observation-compile-records-v1"]
    for key in COMPILE_RECORD_COUNTS:
        manifest.get("counts", {}).pop(key, None)
    (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


class Pair:
    """A source study and its restoration from an earlier-exporter bundle, each with the same plan and narrative."""

    def __init__(self, workdir: Path):
        self.source = workdir / "source" / "workspace.db"
        SQLiteStore(self.source).close()
        client = create_app(db_path=self.source, credential_store=lab._NoCredentials()).test_client()
        lab._ok(client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(LINES)), "a.pdf")},
                            content_type="multipart/form-data"))
        self.observations = [r["id"] for r in _rows(self.source, "observations")]
        self.candidate = {"title": "The lamp", "thesis": "The lamp burns unexplained.", "sections": [
            {"claim": "It burns.", "supporting_observations": self.observations, "supporting_interpretations": []}]}
        self.plan_id = self._ratify(client)
        self.narrative_id = self._add_narrative(self.source)
        export_workspace_bundle(self.source, workdir / "bundle", generated_at=GENERATED_AT, workspace_id="w")
        _as_earlier_exporter_bundle(workdir / "bundle")
        self.restored = workdir / "restored" / "workspace.db"
        restore_workspace(self.restored, workdir / "bundle")
        restored_client = create_app(db_path=self.restored, credential_store=lab._NoCredentials()).test_client()
        assert self._ratify(restored_client) == self.plan_id
        assert self._add_narrative(self.restored) == self.narrative_id

    def _ratify(self, client) -> str:
        return lab._ok(client.post("/api/pipeline/ratify-blueprint", json={"candidate": self.candidate}))["plan_id"]

    def _add_narrative(self, db: Path) -> str:
        """Rendered narratives are not carried by WBS; the identical null-provider row is stored on each side."""
        narrative_id = make_rendered_narrative_id(self.plan_id, "null", make_expression_profile_id("literary-en"))
        store = SQLiteStore(db)
        try:
            store.insert_rendered_narrative({
                "id": narrative_id, "architect_plan_id": self.plan_id, "provider": "null",
                "expression_profile_id": make_expression_profile_id("literary-en"), "text": "It burns.",
                "prompt_used": "Test prompt.", "execution_config": json.dumps({"provider": "null", "model_id": None}),
                "created_at": GENERATED_AT})
        finally:
            store.close()
        return narrative_id

    def critic(self, db: Path) -> list[dict]:
        conn = _connect(db)
        try:
            return evaluate_provenance(self.narrative_id, self.plan_id, conn)
        finally:
            conn.close()

    def persist(self, db: Path, findings: list[dict]) -> None:
        store = SQLiteStore(db)
        try:
            store.insert_findings_batch(findings)
            store._conn.commit()
        finally:
            store.close()


@pytest.fixture
def pair(tmp_path):
    with lab.isolated(tmp_path):
        yield Pair(tmp_path)


def _render(finding: dict) -> dict:
    return json.loads(finding["evidence"])["observed_render"]


def _by_obligation(findings: list[dict]) -> dict[str, dict]:
    return {json.loads(f["evidence"])["contract_obligation"]: f for f in findings}


# ── The state: unchanged evidence, absent custody record ──────────────────────

def test_the_witness_state_is_unchanged_evidence_without_provenance(pair):
    for table in EVIDENCE_TABLES:
        assert _rows(pair.restored, table) == _rows(pair.source, table), table
    assert len(_rows(pair.source, "provenance")) == len(pair.observations) >= 3
    assert _rows(pair.restored, "provenance") == []


# ── What provenance-v1.0 does today (characterization, not endorsement) ──────

def test_provenance_v1_reads_that_state_as_transformed_under_the_same_finding_ids(pair):
    source, restored = pair.critic(pair.source), pair.critic(pair.restored)
    assert len(source) == len(restored) == len(pair.observations)
    assert {f["status"] for f in source} == {"preserved"}
    assert {(f["operation"], f["status"]) for f in restored} == {("transformation", "transformed")}
    # Identity names the obligation evaluated, not its disposition or the method: the same IDs carry both answers.
    assert [f["id"] for f in source] == [f["id"] for f in restored]
    assert [f["obligation_id"] for f in source] == [f["obligation_id"] for f in restored]
    assert {f["evaluation_method"] for f in source + restored} == {"provenance-v1.0"}
    assert {json.dumps(_render(f), sort_keys=True) for f in restored} == {
        json.dumps({"observation_exists": True, "provenance_exists": False}, sort_keys=True)}


def test_provenance_v1_truth_table_over_the_four_observable_states(pair):
    """Absence is the only path to "transformed"; a demonstrated alteration is classified "preserved"."""
    absent, altered, preserved = pair.observations[:3]
    phantom = "f" * 64
    source_rows = {row["observation_id"]: row for row in _rows(pair.source, "provenance")}
    conn = _connect(pair.restored)
    try:
        # Restored without provenance, so these inserts state custody for the first time; nothing is overwritten.
        for observation, verbatim in ((preserved, source_rows[preserved]["verbatim_text"]),
                                      (altered, source_rows[altered]["verbatim_text"] + " Altered.")):
            row = dict(source_rows[observation], verbatim_text=verbatim)
            conn.execute(f"INSERT INTO provenance ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))
        conn.execute("INSERT INTO architect_plan_paragraphs (plan_id, order_idx, purpose, blueprint_section, required_observations, "
                     "required_interpretations, required_terms, forbidden_claims, notes) VALUES (?, 99, 'Phantom', 99, ?, '[]', '[]', '[]', NULL)",
                     (pair.plan_id, json.dumps([phantom])))
        conn.commit()
        # The four states are distinguishable from stored records alone.
        observed = {}
        for observation in (absent, altered, preserved, phantom):
            record = conn.execute("SELECT o.raw_text, p.verbatim_text, p.id AS provenance_id FROM (SELECT ? AS id) q "
                                  "LEFT JOIN observations o ON o.id = q.id LEFT JOIN provenance p ON p.observation_id = q.id",
                                  (observation,)).fetchone()
            observed[observation] = ("missing_observation" if record["raw_text"] is None else
                                     "missing_provenance" if record["provenance_id"] is None else
                                     "demonstrated_alteration" if record["verbatim_text"] != record["raw_text"] else
                                     "preserved_provenance")
    finally:
        conn.close()
    assert observed == {absent: "missing_provenance", altered: "demonstrated_alteration",
                        preserved: "preserved_provenance", phantom: "missing_observation"}

    findings = _by_obligation(pair.critic(pair.restored))
    assert {state: (findings[o]["operation"], findings[o]["status"]) for o, state in observed.items()} == {
        "missing_provenance": ("transformation", "transformed"),
        "demonstrated_alteration": ("preservation", "preserved"),
        "preserved_provenance": ("preservation", "preserved"),
        "missing_observation": ("omission", "omitted"),
    }
    # A historical v1.0 "transformed" Finding is therefore exactly recognizable from its own evidence.
    for finding in findings.values():
        assert (finding["status"] == "transformed") == (_render(finding) == {"observation_exists": True, "provenance_exists": False})


# ── Storage and identity: why a reclassification cannot reuse an existing Finding ─

def _divergent(findings: list[dict]) -> list[dict]:
    """A hypothetical re-evaluation under a different method version (test data only; no evaluator is changed)."""
    return [dict(f, operation="not_evaluated", status="not_evaluated", evaluation_method="provenance-v1.1") for f in findings]


def test_a_historical_finding_cannot_be_reclassified_in_place(pair):
    pair.persist(pair.restored, pair.critic(pair.restored))
    conn = _connect(pair.restored)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="Finding immutable"):
            conn.execute("UPDATE findings SET operation = 'not_evaluated', status = 'not_evaluated'")
        with pytest.raises(sqlite3.DatabaseError, match="Finding immutable"):
            conn.execute("DELETE FROM findings")
    finally:
        conn.close()


def test_an_identical_reevaluation_is_idempotent(pair):
    """Any divergence guard must keep this: the Critic route relies on it to complete a partial ledger on retry."""
    pair.persist(pair.restored, pair.critic(pair.restored))
    stored = _rows(pair.restored, "findings")
    pair.persist(pair.restored, pair.critic(pair.restored))  # new created_at, same content
    assert _rows(pair.restored, "findings") == stored


def test_today_a_divergent_reevaluation_under_an_unchanged_id_is_discarded_silently(pair):
    historical = pair.critic(pair.restored)
    pair.persist(pair.restored, historical)
    pair.persist(pair.restored, _divergent(historical))  # no error is raised
    stored = _rows(pair.restored, "findings")
    assert {(f["status"], f["evaluation_method"]) for f in stored} == {("transformed", "provenance-v1.0")}
    assert len(stored) == len(historical)


def test_a_new_status_is_discarded_silently_by_the_existing_finding_store(pair):
    """The CHECK vocabulary refuses a new status, but INSERT OR IGNORE also ignores CHECK violations."""
    finding = dict(pair.critic(pair.restored)[0], status="unverifiable")
    pair.persist(pair.restored, [finding])  # no error is raised
    assert _rows(pair.restored, "findings") == []
    conn = _connect(pair.restored)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            conn.execute(f"INSERT INTO findings ({', '.join(finding)}) VALUES ({', '.join('?' for _ in finding)})",
                         list(finding.values()))
    finally:
        conn.close()


def test_existing_projections_give_the_same_verdict_for_transformed_and_not_evaluated(pair, tmp_path):
    current = tmp_path / "current.db"
    shutil.copyfile(pair.restored, current)
    pair.persist(current, pair.critic(pair.restored))
    proposed = tmp_path / "proposed.db"
    shutil.copyfile(pair.restored, proposed)
    pair.persist(proposed, _divergent(pair.critic(pair.restored)))
    verdicts = []
    for db in (current, proposed):
        conn = _connect(db)
        try:
            verdicts.append(trust_card(pair.narrative_id, conn)["dimensions"]["provenance"])
        finally:
            conn.close()
    assert verdicts[0] == verdicts[1] == "partial"


# ── Witnesses: what the proposal says must stop ─────────────────────────────

class ProvenanceAbsenceReadAsAlteration(AssertionError):
    """An unchanged Observation whose provenance record is absent is classified as materially altered."""


class DivergentReevaluationDiscarded(AssertionError):
    """A re-evaluation that disagrees with a stored Finding under the same ID succeeds without any signal."""


@pytest.mark.xfail(strict=True, raises=ProvenanceAbsenceReadAsAlteration,
                   reason="ADR-0042 classifies missing provenance as transformation; ADR-0046 proposed, not ratified")
def test_an_unchanged_observation_without_provenance_is_not_classified_as_altered(pair):
    findings = pair.critic(pair.restored)
    assert len(findings) == len(pair.observations)  # the completeness invariant holds under any remedy
    for finding in findings:
        assert _render(finding) == {"observation_exists": True, "provenance_exists": False}  # the absence stays recorded
        if finding["operation"] == "transformation" or finding["status"] == "transformed":
            raise ProvenanceAbsenceReadAsAlteration(f"{finding['obligation_id'][:12]}: unchanged evidence, absent record, "
                                                    f"classified {finding['operation']}/{finding['status']}")


@pytest.mark.xfail(strict=True, raises=DivergentReevaluationDiscarded,
                   reason="Findings are stored with INSERT OR IGNORE; ADR-0046 proposes failing closed on divergence")
def test_a_divergent_reevaluation_under_an_existing_id_fails_closed(pair):
    historical = pair.critic(pair.restored)
    pair.persist(pair.restored, historical)
    try:
        pair.persist(pair.restored, _divergent(historical))
    except sqlite3.DatabaseError:
        return
    if {f["status"] for f in _rows(pair.restored, "findings")} == {"transformed"}:
        raise DivergentReevaluationDiscarded(f"{len(historical)} divergent Findings were discarded without a signal")
