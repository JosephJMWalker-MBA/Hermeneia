"""ADR-0047 L2-a: every Observation an ArchitectPlan requires is linked to its Blueprint, at every write and restore.

The witnesses in tests/test_ef_ratification_divergences.py were converted by this change. These tests add:
- atomicity of a refused write;
- restore refusal of a bundle that carries an inconsistent chain;
- historical compatibility: an inconsistent plan already stored is never rewritten, stays readable and evaluable,
  and its chain is declared rather than carried;
- a tripwire over every plan-paragraph write site.
L2-b (the Critic's read-time link check) is separate and not active.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import pytest

import synthetic_study_lab as lab
from hermeneia.compiler.architect import PlanLinkIntegrityError, compile_architect_plan
from hermeneia.storage.hashing import make_blueprint_id
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.workspace import export_workspace_bundle
from hermeneia.workspace.restore import RestoreError, restore_workspace
from test_ef_ratification_divergences import Study, _connect

ROOT = Path(__file__).resolve().parents[1]
GENERATED_AT = "2026-10-16T12:00:00+00:00"


@pytest.fixture
def study(tmp_path):
    with lab.isolated(tmp_path):
        yield Study(tmp_path / "source")


def _store_blueprint(store: SQLiteStore, observations: list[str], linked: list[str]) -> dict:
    sections = [{"claim": "Store-written.", "supporting_observations": observations, "supporting_interpretations": []}]
    blueprint_id = make_blueprint_id("Store", "Written.", sections)
    store.insert_blueprint({"id": blueprint_id, "title": "Store", "thesis": "Written.", "sections": json.dumps(sections),
                            "source": "steward-authored", "created_at": GENERATED_AT}, linked, [])
    return compile_architect_plan(blueprint_id, store._conn)


def _count(db: Path, table: str) -> int:
    conn = _connect(db)
    try:
        return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    finally:
        conn.close()


def test_a_refused_store_write_rolls_back_with_its_caller_transaction(study):
    blueprints, plans = _count(study.db, "narrative_blueprints"), _count(study.db, "architect_plans")
    store = SQLiteStore(study.db)
    try:
        with pytest.raises(PlanLinkIntegrityError, match="does not link; nothing was written"):
            with store.atomic():
                plan = _store_blueprint(store, study.observations[:2], study.observations[:1])
                store.insert_architect_plan(plan["plan_row"], plan["paragraph_rows"])
    finally:
        store.close()
    assert (_count(study.db, "narrative_blueprints"), _count(study.db, "architect_plans")) == (blueprints, plans)


def test_a_consistent_store_write_is_accepted(study):
    store = SQLiteStore(study.db)
    try:
        with store.atomic():
            plan = _store_blueprint(store, study.observations[:2], study.observations[:2])
            store.insert_architect_plan(plan["plan_row"], plan["paragraph_rows"])
    finally:
        store.close()
    assert study.unlinked_plans() == {}
    assert _count(study.db, "architect_plans") == 2


def test_a_bundle_carrying_an_inconsistent_chain_is_refused_at_restore(study, tmp_path):
    """Written by an exporter without L2-a, or edited: the paragraph file cites an Observation the Blueprint does not link."""
    bundle = tmp_path / "bundle"
    export_workspace_bundle(study.db, bundle, generated_at=GENERATED_AT, workspace_id="w", blueprint_chain=True)
    path = "study/architect_plan_paragraphs.json"
    rows = json.loads((bundle / path).read_text())
    rows[0]["required_observations"] = json.dumps(json.loads(rows[0]["required_observations"]) + [study.observations[3]])
    data = json.dumps(rows).encode("utf-8")
    (bundle / path).write_bytes(data)
    manifest = json.loads((bundle / "manifest.json").read_text())
    (entry,) = [e for e in manifest["files"] if e["path"] == path]
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    target = tmp_path / "restored" / "workspace.db"
    with pytest.raises(RestoreError, match="CHAIN_INTEGRITY_INVALID|blueprint_observation_links"):
        restore_workspace(target, bundle)
    assert not target.exists() or _count(target, "architect_plans") == 0


def test_a_historical_inconsistent_plan_stays_readable_and_its_chain_is_declared_not_carried(study, tmp_path):
    unlinked = study.cite_unlinked_observation()  # stored before this boundary existed; never rewritten
    before = study.unlinked_plans()
    assert before == {study.plan_id: {unlinked}}
    SQLiteStore(study.db).close()  # the workspace still opens
    assert study.run_critic_route()  # and is still evaluated (L2-b, read-time detection, is separate)
    manifest = export_workspace_bundle(study.db, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w",
                                       blueprint_chain=True)
    declared = manifest["declared_unsupported"]["blueprint-dependency-chain-v1"]
    assert declared["reason_code"] == "CHAIN_INTEGRITY_INVALID"
    assert manifest["counts"]["observations"] == len(study.observations)  # the rest of the workspace is carried
    assert study.unlinked_plans() == before


def test_every_plan_paragraph_write_site_checks_the_links():
    """Tripwire: a literal plan-paragraph insert must be preceded by require_plan_obligations_linked in its file."""
    sites = {}
    for path in sorted((ROOT / "hermeneia").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        writes = len(re.findall(r"INTO architect_plan_paragraphs", text))
        if writes:
            sites[str(path.relative_to(ROOT))] = (writes, text.count("require_plan_obligations_linked("))
    assert sites == {
        "hermeneia/cli/architect_cmd.py": (1, 1),
        "hermeneia/storage/sqlite.py": (1, 1),
        "hermeneia/web/app.py": (4, 4),
    }
