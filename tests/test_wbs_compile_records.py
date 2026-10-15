"""Provenance-loss repair: Observation compile records round-trip through WBS, or are declared and rebuilt honestly.

Restore must keep what the study's evidence relationships depend on, not
just recreate tables. A bundle carrying `observation-compile-records-v1`
restores provenance and indexes byte for byte. Unchanged before and after
the round trip:
- Critic provenance findings;
- narrative trust summaries;
- Reader related-observation anchors;
- search;
- Study Lineage Observation items.

A bundle without the component never gets manufactured provenance; only
the CI-016 derived indexes are rebuilt, exactly, and declared. Export and
restore negatives refuse or declare. Synthetic workspaces only; P5
isolation; no provider.
Contract: docs/design/wbs-observation-compile-records-v1.md.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

import synthetic_study_lab as lab
from hermeneia.compiler.evaluation_functions.provenance import evaluate_provenance
from hermeneia.storage.hashing import make_expression_profile_id, make_rendered_narrative_id
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study_lineage import project_study_lineage
from hermeneia.web.app import create_app
from hermeneia.workspace import export_workspace_bundle
from hermeneia.workspace.compile_records import CAPABILITY, COMPONENTS, FILES
from hermeneia.workspace.restore import RestoreError, read_bundle, restore_workspace

GENERATED_AT = "2026-10-15T12:00:00+00:00"
LINES = ["The ﬁrst  lamp burned all night.", "Nobody asked—why it burned.", "The keeper's ledger records only the oil."]
TABLES = [table for table, *_ in COMPONENTS]


def _rows(db: Path, table: str) -> list[dict]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}" ORDER BY 1, 2')]
    finally:
        conn.close()


class Study:
    """An uploaded document, a ratified Blueprint and plan citing its Observations, and a stored narrative."""

    def __init__(self, workdir: Path):
        self.db = workdir / "source" / "workspace.db"
        SQLiteStore(self.db).close()
        self.client = create_app(db_path=self.db, credential_store=lab._NoCredentials()).test_client()
        body = lab._ok(self.client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(LINES)), "a.pdf")},
                                        content_type="multipart/form-data"))
        self.document_id = body["document_id"]
        self.observations = [r["id"] for r in _rows(self.db, "observations")]
        ratified = lab._ok(self.client.post("/api/pipeline/ratify-blueprint", json={"candidate": {
            "title": "The lamp", "thesis": "The lamp burns unexplained.",
            "sections": [{"claim": "It burns.", "supporting_observations": self.observations[:2], "supporting_interpretations": []}]}}))
        self.plan_id = ratified["plan_id"]
        self.narrative_id = self.add_narrative(self.db)

    def add_narrative(self, db: Path) -> str:
        """Rendered narratives are not carried by WBS; tests store the identical row on each side to run the Critic."""
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


@pytest.fixture
def study(tmp_path):
    with lab.isolated(tmp_path):
        yield Study(tmp_path)


def _round_trip(study: Study, tmp_path: Path, mutate=None) -> Path:
    export_workspace_bundle(study.db, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w", blueprint_chain=True)
    if mutate:
        mutate(tmp_path / "bundle")
    target = tmp_path / "restored" / "workspace.db"
    restore_workspace(target, tmp_path / "bundle")
    return target


def _critic(db: Path, study: Study) -> list[tuple]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return sorted((f["obligation_id"], f["operation"], f["status"]) for f in evaluate_provenance(study.narrative_id, study.plan_id, conn))
    finally:
        conn.close()


def _observation_items(db: Path) -> list[dict]:
    conn = lab._read_only(db)
    try:
        return [i for i in project_study_lineage(conn)["items"] if i["record"]["table"] == "observations"]
    finally:
        conn.close()


def _strip_component(bundle: Path) -> None:
    """The bundle an exporter without the component would have written."""
    manifest = json.loads((bundle / "manifest.json").read_text())
    for path in FILES.values():
        (bundle / path).unlink()
    manifest["files"] = [e for e in manifest["files"] if e["path"] not in FILES.values()]
    manifest["required_capabilities"] = [c for c in manifest["required_capabilities"] if c != CAPABILITY]
    for table in [*TABLES, "observations_without_provenance"]:
        manifest["counts"].pop(table)
    (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def test_compile_records_round_trip_byte_for_byte(study, tmp_path):
    target = _round_trip(study, tmp_path)
    for table in TABLES:
        assert _rows(target, table) == _rows(study.db, table) and _rows(target, table), table
    assert len(_rows(target, "provenance")) == len(study.observations)


def test_evidence_behavior_is_unchanged_by_the_round_trip(study, tmp_path):
    target = _round_trip(study, tmp_path)
    study.add_narrative(target)
    before, after = _critic(study.db, study), _critic(target, study)
    assert before == after and {status for *_, status in after} == {"preserved"}
    assert _observation_items(target) == _observation_items(study.db)
    assert all(any(r["table"] == "provenance" for r in i["provenance"]["records"]) for i in _observation_items(target))
    restored = create_app(db_path=target, credential_store=lab._NoCredentials()).test_client()
    for url in (f"/api/reader/documents/{study.document_id}/related-observations?page=1", "/api/search?q=lamp",
                "/api/search?q=ledger", f"/api/trust/rendered_narrative/{study.narrative_id}"):
        a, b = study.client.get(url), restored.get(url)
        assert (a.status_code, a.get_json()) == (b.status_code, b.get_json()), url


def test_a_bundle_without_the_component_gets_no_manufactured_provenance_and_exact_rebuilt_indexes(study, tmp_path):
    target = _round_trip(study, tmp_path, mutate=_strip_component)
    assert _rows(target, "provenance") == []
    strip = lambda rows: [{k: v for k, v in r.items() if k != "derived_at"} for r in rows]  # noqa: E731
    assert strip(_rows(target, "observation_derived")) == strip(_rows(study.db, "observation_derived"))
    assert _rows(target, "terms") == _rows(study.db, "terms")
    assert _rows(target, "observation_terms") == _rows(study.db, "observation_terms")
    coverage = restore_workspace(tmp_path / "again" / "workspace.db", tmp_path / "bundle")["coverage"]
    assert coverage["observation_compile_records"]["status"] == "unsupported"
    assert coverage["observation_compile_records"]["derived_indexes"]["status"] == "rebuilt"
    assert coverage["not_carried"]["observation_provenance"]["status"] == "unsupported"
    assert coverage["not_carried"]["derived_indexes"]["status"] == "rebuilt_on_restore"
    study.add_narrative(target)  # ADR-0042: a missing provenance row is reported as transformation; unchanged here
    assert {status for *_, status in _critic(target, study)} == {"transformed"}


def _sql(db: Path, *statements: str, params: tuple = ()) -> None:
    conn = sqlite3.connect(db)
    try:
        for statement in statements:
            conn.execute(statement, params if "?" in statement else ())
        conn.commit()
    finally:
        conn.close()


EXPORT_NEGATIVES = {
    "missing_table": (("DROP TABLE observation_terms",), "COMPILE_RECORDS_SCHEMA_INCOMPLETE"),
    "changed_columns": (("ALTER TABLE terms ADD COLUMN weight REAL",), "COMPILE_RECORDS_SCHEMA_INCOMPLETE"),
    "identity_break": (("DROP TRIGGER provenance_no_update", "UPDATE provenance SET id = 'other' WHERE rowid = 1"),
                       "COMPILE_RECORDS_INTEGRITY_INVALID"),
    "dangling_observation": (("INSERT INTO observation_derived (observation_id, normalized_text, derivation_version, derived_at) "
                              "VALUES ('missing', 'x', '0.1.0', 'now')",), "COMPILE_RECORDS_CLOSURE_INCOMPLETE"),
    "dangling_term": (("INSERT INTO observation_terms (observation_id, term_id) SELECT id, 'missing-term' FROM observations LIMIT 1",),
                      "COMPILE_RECORDS_CLOSURE_INCOMPLETE"),
}


@pytest.mark.parametrize("case", sorted(EXPORT_NEGATIVES))
def test_export_declares_the_component_unsupported_rather_than_exporting_part_of_it(study, tmp_path, case):
    statements, code = EXPORT_NEGATIVES[case]
    _sql(study.db, *statements)
    manifest = export_workspace_bundle(study.db, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w")
    assert manifest["declared_unsupported"][CAPABILITY]["reason_code"] == code
    assert CAPABILITY not in manifest.get("required_capabilities", [])
    assert not any((tmp_path / "bundle" / path).exists() for path in FILES.values())
    assert manifest["counts"]["observations"] == len(study.observations)
    coverage = read_bundle(tmp_path / "bundle")["coverage"]["observation_compile_records"]
    assert coverage["status"] == "unsupported" and coverage["reason_code"] == code


def _rewrite(bundle: Path, table: str, rows: list, count: int | None = None) -> None:
    data = (json.dumps(rows, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (bundle / FILES[table]).write_bytes(data)
    manifest = json.loads((bundle / "manifest.json").read_text())
    next(e for e in manifest["files"] if e["path"] == FILES[table])["sha256"] = hashlib.sha256(data).hexdigest()
    if count is not None:
        manifest["counts"][table] = count
    (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def _manifest(bundle: Path, edit) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text())
    edit(manifest)
    (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def _dangling_provenance(bundle: Path) -> None:
    rows = json.loads((bundle / FILES["provenance"]).read_text())
    rows[0] = {**rows[0], "id": "zz-missing", "observation_id": "zz-missing"}
    _rewrite(bundle, "provenance", sorted(rows, key=lambda r: r["id"]))


def _unknown_column(bundle: Path) -> None:
    rows = json.loads((bundle / FILES["terms"]).read_text())
    rows[0]["weight"] = 1
    _rewrite(bundle, "terms", rows)


RESTORE_NEGATIVES = {
    "edited_without_rehash": lambda b: (b / FILES["provenance"]).write_bytes((b / FILES["provenance"]).read_bytes().replace(b"lamp", b"Lamp", 1)),
    "rehashed_dangling_provenance": _dangling_provenance,
    "capability_without_file": lambda b: (b / FILES["terms"]).unlink(),
    "file_without_capability": lambda b: _manifest(b, lambda m: m.__setitem__(
        "required_capabilities", [c for c in m["required_capabilities"] if c != CAPABILITY])),
    "count_mismatch": lambda b: _manifest(b, lambda m: m["counts"].__setitem__("provenance", 99)),
    "duplicate_key": lambda b: _rewrite(b, "terms", (lambda rows: rows + rows[:1])(json.loads((b / FILES["terms"]).read_text())),
                                        count=len(json.loads((b / FILES["terms"]).read_text())) + 1),
    "unknown_column": _unknown_column,
    "declaration_and_files": lambda b: _manifest(b, lambda m: m.setdefault("declared_unsupported", {}).__setitem__(
        CAPABILITY, {"reason_code": "COMPILE_RECORDS_CLOSURE_INCOMPLETE"})),
}


@pytest.mark.parametrize("case", sorted(RESTORE_NEGATIVES))
def test_restore_refuses_a_malformed_or_unclosed_component_and_writes_nothing(study, tmp_path, case):
    export_workspace_bundle(study.db, tmp_path / "bundle", generated_at=GENERATED_AT, workspace_id="w")
    RESTORE_NEGATIVES[case](tmp_path / "bundle")
    target = tmp_path / "restored" / "workspace.db"
    with pytest.raises(RestoreError):
        restore_workspace(target, tmp_path / "bundle")
    if target.exists():
        assert all(not _rows(target, table) for table in [*TABLES, "observations"])


def test_export_is_deterministic_and_read_only(study, tmp_path):
    before = lab._logical_digest(study.db)
    export_workspace_bundle(study.db, tmp_path / "a", generated_at=GENERATED_AT, workspace_id="w")
    export_workspace_bundle(study.db, tmp_path / "b", generated_at=GENERATED_AT, workspace_id="w")
    files = lambda root: {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}  # noqa: E731
    assert files(tmp_path / "a") == files(tmp_path / "b") and lab._logical_digest(study.db) == before
    manifest = json.loads((tmp_path / "a" / "manifest.json").read_text())
    assert CAPABILITY in manifest["required_capabilities"] and manifest["counts"]["observations_without_provenance"] == 0
    roles = {e["path"]: e["role"] for e in manifest["files"]}
    assert roles[FILES["provenance"]] == "canonical" and roles[FILES["terms"]] == "derived"
