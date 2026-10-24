"""The ADR-0046 witness state, reached through the product's own routes (shared by the ADR-0046 tests).

An earlier-exporter WBS bundle (no Observation compile records) restores unchanged Observations without provenance.
Plans and narratives are content-addressed, so ratifying the same Blueprint on both sides yields the same plan,
narrative and Finding IDs.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3

import synthetic_study_lab as lab
from hermeneia.compiler.evaluation_functions.provenance import evaluate_provenance
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
ABSENT = {"observation_exists": True, "provenance_exists": False}


def connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def rows(db: Path, table: str) -> list[dict]:
    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}" ORDER BY 1')]
    finally:
        conn.close()


def render(finding: dict) -> dict:
    return json.loads(finding["evidence"])["observed_render"]


def by_obligation(findings: list[dict]) -> dict[str, dict]:
    return {json.loads(f["evidence"])["contract_obligation"]: f for f in findings}


def as_earlier_exporter_bundle(bundle: Path) -> None:
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
        self.observations = [r["id"] for r in rows(self.source, "observations")]
        self.candidate = {"title": "The lamp", "thesis": "The lamp burns unexplained.", "sections": [
            {"claim": "It burns.", "supporting_observations": self.observations, "supporting_interpretations": []}]}
        self.plan_id = self._ratify(client)
        self.narrative_id = self._add_narrative(self.source)
        export_workspace_bundle(self.source, workdir / "bundle", generated_at=GENERATED_AT, workspace_id="w")
        as_earlier_exporter_bundle(workdir / "bundle")
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
        conn = connect(db)
        try:
            return evaluate_provenance(self.narrative_id, self.plan_id, conn)
        finally:
            conn.close()

    def run_critic_route(self, db: Path) -> None:
        """The product Critic route: the legacy report and every registered Evaluation Function, persisted together."""
        client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
        lab._ok(client.post("/api/pipeline/run-critic", json={"narrative_id": self.narrative_id}))

    def persist(self, db: Path, findings: list[dict]):
        """The product's single Finding persistence boundary (the Critic route and the CLI both use it)."""
        store = SQLiteStore(db)
        try:
            result = store.insert_findings_batch(findings)
            store._conn.commit()
            return result
        finally:
            store.close()

    def four_states(self) -> dict[str, str]:
        """Add, to the restored study, one Observation in each observable state. Returns {obligation: state}.

        Restored without provenance, so the inserts state custody for the first time and nothing is overwritten.
        """
        absent, altered, preserved = self.observations[:3]
        phantom = "f" * 64
        source_rows = {row["observation_id"]: row for row in rows(self.source, "provenance")}
        conn = connect(self.restored)
        try:
            for observation, verbatim in ((preserved, source_rows[preserved]["verbatim_text"]),
                                          (altered, source_rows[altered]["verbatim_text"] + " Altered.")):
                row = dict(source_rows[observation], verbatim_text=verbatim)
                conn.execute(f"INSERT INTO provenance ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))
            conn.execute("INSERT INTO architect_plan_paragraphs (plan_id, order_idx, purpose, blueprint_section, required_observations, "
                         "required_interpretations, required_terms, forbidden_claims, notes) VALUES (?, 99, 'Phantom', 99, ?, '[]', '[]', '[]', NULL)",
                         (self.plan_id, json.dumps([phantom])))
            conn.commit()
            states = {}
            for observation in (absent, altered, preserved, phantom):
                record = conn.execute("SELECT o.raw_text, p.verbatim_text, p.id AS provenance_id FROM (SELECT ? AS id) q "
                                      "LEFT JOIN observations o ON o.id = q.id LEFT JOIN provenance p ON p.observation_id = q.id",
                                      (observation,)).fetchone()
                states[observation] = ("missing_observation" if record["raw_text"] is None else
                                       "missing_provenance" if record["provenance_id"] is None else
                                       "demonstrated_alteration" if record["verbatim_text"] != record["raw_text"] else
                                       "preserved_provenance")
            return states
        finally:
            conn.close()
