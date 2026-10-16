"""Two divergences between ratified Evaluation Function authority and the code (investigation, 2026-10-16).

1. ADR-0042's Provenance EF method requires a `blueprint_observation_links` check; `provenance-v1.0` never queries it.
2. The `semantic` dimension is executed by the runner and its Findings are persisted, although it is absent from
   `RATIFIED_DIMENSIONS` and ADR-0042 ratified that function's successor under another name.

Nothing here changes behavior. Passing tests pin what the code does; strict-xfail witnesses pin what the ratified
text requires and must show XPASS(strict) before their markers are removed, after the Steward decides a remedy.
Record: docs/design/ef-ratification-divergences-2026-10-16.md.
"""
from __future__ import annotations

import inspect
import io
import json
from pathlib import Path
import sqlite3

import pytest

import synthetic_study_lab as lab
from hermeneia.compiler.architect import compile_architect_plan
from hermeneia.compiler.evaluation_functions import semantic as semantic_ef
from hermeneia.compiler.evaluation_functions.base import RATIFIED_DIMENSIONS, validate_ef_contract
from hermeneia.compiler.evaluation_functions.provenance import evaluate_provenance
from hermeneia.compiler.evaluation_functions.runner import _load_efs
from hermeneia.compiler.projections.trust_card import trust_card
from hermeneia.storage.hashing import make_blueprint_id, make_expression_profile_id, make_rendered_narrative_id
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import export_workspace_bundle
from hermeneia.workspace.restore import restore_workspace

LINES = ["The lamp burned all night.", "Nobody asked why it burned.", "The keeper's ledger records only the oil.",
         "In the morning the wick was new."]


def _connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


class Study:
    """An uploaded document, a Blueprint ratified through the product route citing two of its four Observations,
    and a stored null-provider narrative."""

    def __init__(self, workdir: Path):
        self.db = workdir / "workspace.db"
        SQLiteStore(self.db).close()
        self.client = create_app(db_path=self.db, credential_store=lab._NoCredentials()).test_client()
        lab._ok(self.client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(LINES)), "a.pdf")},
                                 content_type="multipart/form-data"))
        conn = _connect(self.db)
        self.observations = [r["id"] for r in conn.execute("SELECT id FROM observations ORDER BY id")]
        conn.close()
        self.ratified = lab._ok(self.client.post("/api/pipeline/ratify-blueprint", json={"candidate": {
            "title": "The lamp", "thesis": "The lamp burns unexplained.",
            "sections": [{"claim": "It burns.", "supporting_observations": self.observations[:2],
                          "supporting_interpretations": []}]}}))
        self.plan_id = self.ratified["plan_id"]
        self.narrative_id = make_rendered_narrative_id(self.plan_id, "null", make_expression_profile_id("literary-en"))
        store = SQLiteStore(self.db)
        try:
            store.insert_rendered_narrative({
                "id": self.narrative_id, "architect_plan_id": self.plan_id, "provider": "null",
                "expression_profile_id": make_expression_profile_id("literary-en"), "text": "It burns.",
                "prompt_used": "Test prompt.", "execution_config": json.dumps({"provider": "null", "model_id": None}),
                "created_at": "2026-10-16T12:00:00+00:00"})
        finally:
            store.close()

    def cite_unlinked_observation(self) -> str:
        """Append a plan obligation citing an existing, provenance-bearing Observation the Blueprint does not link.

        No product route writes this state (see the invariant test); it is constructed directly, as the existing
        test_era2_sprint_e3 phantom-obligation test does, to exercise the EF on imported or malformed state.
        """
        unlinked = self.observations[3]
        conn = _connect(self.db)
        try:
            conn.execute("INSERT INTO architect_plan_paragraphs (plan_id, order_idx, purpose, blueprint_section, required_observations, "
                         "required_interpretations, required_terms, forbidden_claims, notes) VALUES (?, 99, 'Unlinked', 99, ?, '[]', '[]', '[]', NULL)",
                         (self.plan_id, json.dumps([unlinked])))
            conn.commit()
        finally:
            conn.close()
        return unlinked

    def facts(self, observation: str) -> dict:
        conn = _connect(self.db)
        try:
            blueprint = conn.execute("SELECT blueprint_id FROM architect_plans WHERE id = ?", (self.plan_id,)).fetchone()[0]
            return {
                "observation": conn.execute("SELECT 1 FROM observations WHERE id = ?", (observation,)).fetchone() is not None,
                "provenance": conn.execute("SELECT 1 FROM provenance WHERE observation_id = ?", (observation,)).fetchone() is not None,
                "linked": conn.execute("SELECT 1 FROM blueprint_observation_links WHERE blueprint_id = ? AND observation_id = ?",
                                       (blueprint, observation)).fetchone() is not None,
            }
        finally:
            conn.close()

    def provenance_findings(self) -> dict[str, dict]:
        conn = _connect(self.db)
        try:
            return {json.loads(f["evidence"])["contract_obligation"]: f
                    for f in evaluate_provenance(self.narrative_id, self.plan_id, conn)}
        finally:
            conn.close()

    def unlinked_plans(self, db: Path | None = None) -> dict[str, set[str]]:
        """Plans whose cited Observations are not all linked to their Blueprint: {plan_id: unlinked}."""
        conn = _connect(db or self.db)
        try:
            found = {}
            for plan_id, blueprint_id in conn.execute("SELECT id, blueprint_id FROM architect_plans"):
                cited = {o for (raw,) in conn.execute("SELECT required_observations FROM architect_plan_paragraphs WHERE plan_id = ?",
                                                      (plan_id,)) for o in json.loads(raw)}
                linked = {o for (o,) in conn.execute("SELECT observation_id FROM blueprint_observation_links WHERE blueprint_id = ?",
                                                     (blueprint_id,))}
                if cited - linked:
                    found[plan_id] = cited - linked
            return found
        finally:
            conn.close()

    def write_plan_through_the_store_api(self) -> None:
        """The one writer that takes links separately from the sections: SQLiteStore.insert_blueprint."""
        sections = [{"claim": "Store-written.", "supporting_observations": self.observations[:2], "supporting_interpretations": []}]
        blueprint_id = make_blueprint_id("Store", "Written.", sections)
        store = SQLiteStore(self.db)
        try:
            store.insert_blueprint({"id": blueprint_id, "title": "Store", "thesis": "Written.", "sections": json.dumps(sections),
                                    "source": "steward-authored", "created_at": "2026-10-16T12:00:00+00:00"},
                                   self.observations[:1], [])
            plan = compile_architect_plan(blueprint_id, store._conn)
            store.insert_architect_plan(plan["plan_row"], plan["paragraph_rows"])
            store._conn.commit()
        finally:
            store.close()

    def run_critic_route(self) -> list[dict]:
        lab._ok(self.client.post("/api/pipeline/run-critic", json={"narrative_id": self.narrative_id}))
        conn = _connect(self.db)
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM findings WHERE rendered_narrative_id = ?", (self.narrative_id,))]
        finally:
            conn.close()


@pytest.fixture
def study(tmp_path):
    with lab.isolated(tmp_path):
        yield Study(tmp_path)


# ── 1. ADR-0042's Blueprint-link check ──────────────────────────────────────

def test_provenance_v1_classifies_a_cited_but_unlinked_observation_as_preserved(study):
    unlinked = study.cite_unlinked_observation()
    assert study.facts(unlinked) == {"observation": True, "provenance": True, "linked": False}
    finding = study.provenance_findings()[unlinked]
    assert (finding["operation"], finding["status"]) == ("preservation", "preserved")
    # The evidence records only what was checked: no link fact exists to explain the disposition.
    assert json.loads(finding["evidence"])["observed_render"] == {"observation_exists": True, "provenance_exists": True}


def test_product_blueprint_writers_keep_every_plan_obligation_linked(study):
    """Why the missing check is latent: ratify and revise derive links and plan obligations from the same sections."""
    revised = lab._ok(study.client.post("/api/pipeline/revise-blueprint", json={
        "predecessor_id": study.ratified["blueprint_id"], "reason": "Cite the ledger.", "candidate": {
            "title": "The lamp", "thesis": "The lamp burns unexplained.",
            "sections": [{"claim": "It burns.", "supporting_observations": study.observations[1:3], "supporting_interpretations": []},
                         {"claim": "The wick was new.", "supporting_observations": study.observations[3:], "supporting_interpretations": []}]}}))
    imported = lab._ok(study.client.post("/api/architect/import", json={
        "title": "Imported", "thesis": "The ledger is silent.", "sections": [{"claim": "It records oil.", "obs_refs": ["OBS-1", "OBS-3"]}]}))
    conn = _connect(study.db)
    try:
        plans = conn.execute("SELECT id, blueprint_id FROM architect_plans").fetchall()
        assert {p["id"] for p in plans} == {study.plan_id, revised["plan_id"], imported["plan_id"]}
        for plan in plans:
            cited = {o for (raw,) in conn.execute("SELECT required_observations FROM architect_plan_paragraphs WHERE plan_id = ?",
                                                  (plan["id"],)) for o in json.loads(raw)}
            linked = {o for (o,) in conn.execute("SELECT observation_id FROM blueprint_observation_links WHERE blueprint_id = ?",
                                                 (plan["blueprint_id"],))}
            assert cited and cited <= linked, plan["id"]
    finally:
        conn.close()


class BlueprintLinkNotChecked(AssertionError):
    """A required Observation the plan's Blueprint does not link is classified preserved (ADR-0042 requires both)."""


@pytest.mark.xfail(strict=True, raises=BlueprintLinkNotChecked,
                   reason="ADR-0042 Provenance EF method requires blueprint_observation_links; provenance-v1.0 does not query it")
def test_a_cited_observation_the_blueprint_does_not_link_is_not_classified_preserved(study):
    unlinked = study.cite_unlinked_observation()
    finding = study.provenance_findings()[unlinked]
    if finding["status"] == "preserved":
        raise BlueprintLinkNotChecked(f"{unlinked[:12]}: linked={study.facts(unlinked)['linked']}, status=preserved")


# L2 (ADR-0047): write-time and restore-time integrity, and read-time recording of the link fact.

class UnlinkedObligationWritten(AssertionError):
    """A plan whose obligations are not all linked to its Blueprint is written (ADR-0047 L2-a)."""


class UnlinkedChainRestored(AssertionError):
    """A chain with an unlinked plan obligation is carried as covered and restored (ADR-0047 L2-a)."""


class LinkAbsenceNotRecorded(AssertionError):
    """The Finding's evidence does not record that the Blueprint link was absent (ADR-0047 L2-b)."""


@pytest.mark.xfail(strict=True, raises=UnlinkedObligationWritten, reason="ADR-0047 L2-a proposed: the store API accepts it")
def test_the_store_api_refuses_a_plan_with_unlinked_obligations(study):
    try:
        study.write_plan_through_the_store_api()
    except (ValueError, sqlite3.DatabaseError):
        assert study.unlinked_plans() == {}, "a refused write must store nothing"
        return
    if study.unlinked_plans():
        raise UnlinkedObligationWritten(f"plans with unlinked obligations: {len(study.unlinked_plans())}")


_CHAIN_EXPORT = "blueprint_chain" in inspect.signature(export_workspace_bundle).parameters


@pytest.mark.skipif(not _CHAIN_EXPORT, reason="needs the WBS Blueprint chain component (#255)")
@pytest.mark.xfail(strict=True, raises=UnlinkedChainRestored, reason="ADR-0047 L2-a proposed: chain closure does not check links")
def test_an_inconsistent_historical_chain_is_neither_exported_as_covered_nor_restored(study, tmp_path):
    study.cite_unlinked_observation()  # a historical or corrupted record; no product route writes it
    assert study.unlinked_plans()
    export_workspace_bundle(study.db, tmp_path / "bundle", generated_at="2026-10-16T12:00:00+00:00", workspace_id="w",
                            blueprint_chain=True)
    target = tmp_path / "restored" / "workspace.db"
    try:
        restore_workspace(target, tmp_path / "bundle")
    except Exception:  # noqa: BLE001 - any refusal satisfies the boundary; the target must then hold nothing
        assert not target.exists() or study.unlinked_plans(target) == {}
        return
    if study.unlinked_plans(target):
        raise UnlinkedChainRestored(f"restored plans with unlinked obligations: {len(study.unlinked_plans(target))}")


@pytest.mark.xfail(strict=True, raises=LinkAbsenceNotRecorded, reason="ADR-0047 L2-b proposed: provenance-v1.0 records no link fact")
def test_the_evidence_records_that_the_blueprint_link_was_absent(study):
    unlinked = study.cite_unlinked_observation()
    observed = json.loads(study.provenance_findings()[unlinked]["evidence"])["observed_render"]
    if observed.get("blueprint_link_exists") is not False:
        raise LinkAbsenceNotRecorded(f"observed_render: {observed}")


# ── 2. The unratified `semantic` dimension ──────────────────────────────────

def test_the_runner_executes_a_dimension_outside_the_ratified_registry(study):
    registered = [dimension for dimension, _function in _load_efs()]
    assert "semantic" in registered and "semantic" not in RATIFIED_DIMENSIONS
    assert sorted(set(registered) - RATIFIED_DIMENSIONS) == ["semantic"]
    # The module contract does not consult the registry, so it raises no violation.
    assert semantic_ef.dimension == "semantic" and validate_ef_contract(semantic_ef) == []


def test_the_critic_route_persists_unratified_semantic_findings_into_the_canonical_ledger(study):
    findings = study.run_critic_route()
    assert {f["dimension"] for f in findings} - RATIFIED_DIMENSIONS == {"semantic"}
    semantic = [f for f in findings if f["dimension"] == "semantic"]
    assert semantic and {f["evaluation_method"] for f in semantic} == {semantic_ef.EVALUATION_METHOD}
    conn = _connect(study.db)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="Finding immutable"):
            conn.execute("DELETE FROM findings WHERE dimension = 'semantic'")
        assert "semantic" in trust_card(study.narrative_id, conn)["dimensions"]
    finally:
        conn.close()


def test_the_semantic_function_uses_ratified_dispositions_outside_their_adr_0041_meanings():
    """ADR-0041 §5: `transformed` = materially altered; `not_evaluated` = not evaluated in this invocation."""
    assert semantic_ef._verdict(True, True) == ("supported", "preservation", "preserved")
    assert semantic_ef._verdict(True, False) == ("partially_supported", "transformation", "transformed")  # thin trace
    assert semantic_ef._verdict(False, False) == ("weak", "not_evaluated", "not_evaluated")  # function ran


class UnratifiedDimensionPersisted(AssertionError):
    """A Finding whose dimension is absent from RATIFIED_DIMENSIONS is written to the canonical ledger."""


@pytest.mark.xfail(strict=True, raises=UnratifiedDimensionPersisted,
                   reason="runner registers `semantic`, absent from RATIFIED_DIMENSIONS (ADR-0042 ratified it as observation_coverage)")
def test_the_critic_route_persists_only_ratified_dimensions(study):
    unratified = sorted({f["dimension"] for f in study.run_critic_route()} - RATIFIED_DIMENSIONS)
    if unratified:
        raise UnratifiedDimensionPersisted(f"persisted dimensions outside the registry: {unratified}")
