"""#252 coverage audit: Blueprint-chain portability is not complete study portability.

Every runtime table is exported, carried by a capability component, or
declared not carried. Export counts what each not-carried surface left
behind. Restore reports each surface unsupported and reconstructs none of
it. Compile-time derived indexes are declared not rebuilt; a restored
workspace has them empty. Older bundles report unknown counts. Synthetic
workspaces only.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3

import pytest

import synthetic_study_lab as lab
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace import export_workspace_bundle
from hermeneia.workspace.coverage import CHAIN_SURFACE, COMPILE_RECORD_SURFACES, NOT_CARRIED
from hermeneia.workspace.restore import preview_restore, restore_workspace
from test_constitutional_p0 import _seed_full_chain

GENERATED_AT = "2026-10-13T12:00:00+00:00"


def _count(db: Path, table: str, where: str = "") -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def study(tmp_path):
    db = tmp_path / "source" / "workspace.db"
    SQLiteStore(db).close()
    with lab.isolated(tmp_path):
        client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
        body = lab._ok(client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(["The lamp burned.", "Nobody asked."])), "a.pdf")},
                                   content_type="multipart/form-data"))
        (observation,), = sqlite3.connect(db).execute("SELECT id FROM observations ORDER BY id LIMIT 1").fetchall()
        lab._ok(client.post(f"/api/observations/{observation}/inquiry", json={"question_text": "Who lit it?"}))
        lab._ok(client.post(f"/api/observations/{observation}/review", json={"review_status": "unsure"}))
        lab._ok(client.post("/api/reader/progress", json={"document_id": body["document_id"], "page": 1}))
        lab._ok(client.post("/api/profiles", json={"name": "Steward voice", "artist_prompt": "Write plainly."}))
    store = SQLiteStore(db)
    try:
        ids = _seed_full_chain(store)
        store.insert_witness_session({
            "id": "witness-1", "rendered_narrative_id": ids["narrative_id"], "witness_profile": "general",
            "task_description": "Read it.", "task_completed": 1, "notes": "", "facilitated_by": "steward",
            "session_date": GENERATED_AT, "constitution_version": "1.0.0", "created_at": GENERATED_AT})
    finally:
        store.close()
    return db


def test_a_default_export_counts_everything_it_leaves_behind(study, tmp_path):
    manifest = export_workspace_bundle(study, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w")
    left = manifest["not_exported"]
    # Provenance and the derived indexes are carried by the compile-records component since the repair.
    assert set(left) == {surface for surface, *_ in NOT_CARRIED} - set(COMPILE_RECORD_SURFACES) | {CHAIN_SURFACE}
    assert manifest["counts"]["provenance"] == _count(study, "provenance") > 0
    assert manifest["counts"]["observations_without_provenance"] == 0
    assert left["study_reviews"]["tables"] == {"observation_reviews": 1, "inquiry_notes": 1}
    assert left["reports"]["tables"]["rendered_narratives"] == 1 and left["reports"]["tables"]["validation_reports"] == 1
    assert left["governance"]["tables"]["witness_sessions"] == 1
    assert left["custom_expression_profiles"]["tables"] == {"expression_profiles": 1}
    assert left["reading_progress"]["tables"] == {"reading_progress": 1}
    chain = left[CHAIN_SURFACE]
    assert chain["tables"]["interpretations"] == 1 and chain["tables"]["narrative_blueprints"] == 1 and "gated off" in chain["reason"]


def test_restore_declares_every_surface_unsupported_and_reconstructs_none(study, tmp_path):
    manifest = export_workspace_bundle(study, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w")
    target = tmp_path / "restored" / "workspace.db"
    preview = preview_restore(target, tmp_path / "bundle")
    result = restore_workspace(target, tmp_path / "bundle")
    for coverage in (preview["coverage"], result["coverage"]):
        assert coverage["study_portability"] == {"status": "partial", "reason": coverage["study_portability"]["reason"],
                                                 "source_counts": "recorded"}
        assert coverage["observation_compile_records"]["status"] == "covered"
        for surface, *_ in NOT_CARRIED:
            if surface in COMPILE_RECORD_SURFACES:
                assert surface not in coverage["not_carried"]
                continue
            assert coverage["not_carried"][surface]["status"] == "unsupported"
            assert coverage["not_carried"][surface]["source_records"] == manifest["not_exported"][surface]["tables"]
        assert coverage["not_carried"][CHAIN_SURFACE]["source_records"]["interpretations"] == 1
    for surface, tables, _kind, _reason in NOT_CARRIED:
        if surface in COMPILE_RECORD_SURFACES:
            continue
        for table in tables:
            where = "WHERE source IS NOT 'built-in'" if table == "expression_profiles" else ""
            assert _count(target, table, where) == 0, table
    assert _count(target, "interpretations") == _count(target, "narrative_blueprints") == 0
    assert _count(target, "observations") == _count(study, "observations")


def test_with_the_chain_gate_open_the_chain_is_carried_not_declared(study, tmp_path):
    manifest = export_workspace_bundle(study, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w", blueprint_chain=True)
    assert CHAIN_SURFACE not in manifest["not_exported"]
    result = restore_workspace(tmp_path / "restored" / "workspace.db", tmp_path / "bundle")
    assert result["coverage"]["blueprint_dependency_chain"]["status"] == "covered"
    assert CHAIN_SURFACE not in result["coverage"]["not_carried"]
    assert result["coverage"]["study_portability"]["status"] == "partial"


def test_an_older_bundle_reports_unknown_counts(study, tmp_path):
    export_workspace_bundle(study, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w")
    manifest_path = tmp_path / "bundle" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    del manifest["not_exported"]
    manifest_path.write_text(json.dumps(manifest))
    coverage = preview_restore(tmp_path / "restored.db", tmp_path / "bundle")["coverage"]
    assert coverage["study_portability"]["source_counts"] == "unknown"
    assert all(entry["source_records"] == "unknown" for entry in coverage["not_carried"].values())


def test_every_runtime_table_is_classified(tmp_path):
    from hermeneia.workspace.blueprint_chain import COMPONENTS
    db = tmp_path / "workspace.db"
    SQLiteStore(db).close()
    tables = {r[0] for r in sqlite3.connect(db).execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    exported = {"source_documents", "source_extractions", "observations", "reader_highlights", "perspectives",
                "supersession_relations", "investigation_log", "workspace_investigation", "perspective_execution_receipts",
                "achievement_awards", "accepted_perspective_comparisons", "publication_works", "publication_artifacts",
                "authoring_drafts", "authoring_proposals", "authoring_decisions", "authoring_requests", "authoring_outcomes",
                "authoring_proofs"}
    system = {"schema_version", "workspace_identity"}
    chain = {table for _key, table, _path, _pk, _cols in COMPONENTS}
    declared = {table for _surface, names, _kind, _reason in NOT_CARRIED for table in names}
    assert tables == exported | system | chain | declared, sorted(tables ^ (exported | system | chain | declared))


# Regression witnesses (found by the 2026-10-13 real-study validation). Restore lost compile-time provenance,
# so evidence-integrity checks changed meaning after a round trip. The observation-compile-records repair
# (docs/design/wbs-observation-compile-records-v1.md) showed strict unexpected passes on 2026-10-15 before
# these xfail markers were removed; the assertions are unchanged.

class RestoredProvenanceLost(AssertionError):
    """A restored workspace holds Observations without their compile-time provenance rows."""


class RestoredObservationLooksTransformed(AssertionError):
    """The Critic provenance check would classify a restored, untouched Observation as transformed."""


def test_restore_keeps_compile_time_observation_provenance(study, tmp_path):
    export_workspace_bundle(study, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w")
    target = tmp_path / "restored" / "workspace.db"
    restore_workspace(target, tmp_path / "bundle")
    if _count(study, "provenance") > 0 and _count(target, "provenance") == 0 and _count(target, "observations") > 0:
        raise RestoredProvenanceLost(f"{_count(study, 'provenance')} provenance rows in the source, 0 after restore")


def test_an_untouched_observation_is_still_preserved_after_restore(study, tmp_path):
    export_workspace_bundle(study, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w")
    target = tmp_path / "restored" / "workspace.db"
    restore_workspace(target, tmp_path / "bundle")
    conn = sqlite3.connect(target)
    try:
        (observation,), = conn.execute("SELECT id FROM observations ORDER BY id LIMIT 1").fetchall()
        has_provenance = conn.execute("SELECT 1 FROM provenance WHERE observation_id = ?", (observation,)).fetchone() is not None
    finally:
        conn.close()
    # The Critic provenance evaluation (compiler/evaluation_functions/provenance.py) treats an Observation
    # without a provenance row as "transformation"/"transformed" rather than "preservation"/"preserved".
    if not has_provenance:
        raise RestoredObservationLooksTransformed(f"restored Observation {observation[:12]} has no provenance row")
