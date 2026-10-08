"""P7 Structured Perspective Comparison v1 (#215): deterministic, read-only, never past the semantic boundary.

The committed evaluation is reproduced by the production comparator over the
frozen synthetic corpus. Refusals come before eligibility and never reveal why
a receipt is ineligible. A tampered receipt is never compared. The lab's own
closure checks catch bad references. The comparator has no provider, storage
or network dependency, and its API is a read-only projection. Synthetic
workspaces only; in-process fakes; no network.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

import perspective_comparison_lab as comparison_lab
import synthetic_study_lab as lab
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
from hermeneia.perspective_comparison import (
    SEMANTIC_NOT_ESTABLISHED, UNCERTAINTY, ComparisonRefused, compare_retained_perspectives,
)
from hermeneia.web.app import create_app
from test_e10_vertical_slice_api import _FakeOllamaClient

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "research" / "perspective_comparison" / "v1"
SCHEMA_FILE = ROOT / "tests" / "fixtures" / "perspective_comparison" / "v1" / "comparison.schema.json"
CORPUS = comparison_lab.load_corpus()


@pytest.fixture(scope="module")
def results():
    return json.loads(json.dumps(comparison_lab.run(), sort_keys=True, ensure_ascii=False))


def _case(prefix: str) -> dict:
    return next(case for case in CORPUS["cases"] if case["case_id"].startswith(prefix))


def _built(prefix: str, tmp_path: Path) -> dict:
    with lab.isolated(tmp_path):
        _FakeOllamaClient.models = list(CORPUS["models"])
        return comparison_lab.materialize(CORPUS, _case(prefix), tmp_path / prefix)


def _evidence(db: Path):
    conn = lab._read_only(db)
    try:
        return read_perspective_achievement_evidence(conn)
    finally:
        conn.close()


def test_committed_dataset_and_summary_are_reproduced_by_production(results):
    assert json.loads((RESULTS / "results.json").read_text()) == results
    assert (RESULTS / "summary.md").read_text() == comparison_lab.summary_markdown(results)


def test_every_case_meets_the_frozen_contract(results):
    aggregate = dict(results["aggregate"])
    assert aggregate.pop("manufactured_semantic_fields") == {"count": 0, "total": 13}
    assert all(value["passed"] == value["total"] for value in aggregate.values()), aggregate
    assert aggregate["variants_as_frozen"] == {"passed": 13, "total": 13}
    flip = next(v for v in results["cases"][0]["variants"] if v["variant_id"] == "conclusion_flip")
    assert flip["passed"] and "not the deterministic comparison" in flip["boundary"]


def test_schema_file_pins_the_production_vocabulary():
    schema = json.loads(SCHEMA_FILE.read_text())
    assert schema["properties"]["uncertainty"]["items"]["properties"]["code"]["enum"] == list(UNCERTAINTY)
    assert schema["$defs"]["semantic_not_established"]["properties"]["fields"]["const"] == SEMANTIC_NOT_ESTABLISHED["fields"]
    assert schema["$defs"]["semantic_populated"]["properties"]["origin"]["properties"]["kind"] == {"const": "evaluation_reference"}
    forbidden = comparison_lab.FORBIDDEN_KEYS & set(schema["properties"])
    assert forbidden == set(), forbidden


def test_refusals_precede_eligibility_and_do_not_reveal_why(tmp_path):
    built = _built("C10", tmp_path)
    evidence, ids = _evidence(built["db"]), built["ids"]

    def code(receipt_ids):
        with pytest.raises(ComparisonRefused) as refused:
            compare_retained_perspectives(evidence, receipt_ids)
        return refused.value.code

    fabricated = [f"perspective-execution-receipt:sha256:{index:064x}" for index in range(9)]
    assert code([ids["R1"], ids["R1"]]) == "DUPLICATE_PARTICIPANT"
    assert code([ids["R1"]]) == "TOO_FEW_PARTICIPANTS"
    assert code(fabricated) == "TOO_MANY_PARTICIPANTS"
    # Excluded and never-existing receipts are refused identically.
    assert code([ids["R1"], ids["R3"]]) == code([ids["R1"], fabricated[0]]) == "INELIGIBLE_RECEIPT"
    result = compare_retained_perspectives(evidence, [ids["R2"], ids["R1"]])
    assert "The bell" not in json.dumps(result) and result["coverage"]["classified_records"]["excluded"] == 1


def test_a_tampered_receipt_is_never_compared(tmp_path):
    built = _built("C01", tmp_path)
    tampered = tmp_path / "tampered.db"
    shutil.copy(built["db"], tampered)
    conn = sqlite3.connect(tampered)
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='perspective_execution_receipts'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    row = conn.execute("SELECT receipt_json FROM perspective_execution_receipts WHERE id = ?", (built["ids"]["R2"],)).fetchone()
    altered = row[0].replace("Read narrowly", "Read broadly")
    assert altered != row[0]
    conn.execute("UPDATE perspective_execution_receipts SET receipt_json = ? WHERE id = ?", (altered, built["ids"]["R2"]))
    conn.commit()
    conn.close()
    evidence = _evidence(tampered)
    assert evidence.coverage["classified_records"]["invalid"] == 1
    with pytest.raises(ComparisonRefused) as refused:
        compare_retained_perspectives(evidence, [built["ids"]["R1"], built["ids"]["R2"]])
    assert refused.value.code == "INELIGIBLE_RECEIPT"


def test_lab_closure_checks_catch_unfaithful_references(tmp_path):
    built = _built("C01", tmp_path)
    result = comparison_lab.production_compare(built["db"], [built["ids"]["R1"], built["ids"]["R2"]])
    reference = _case("C01")["reference"]
    assert comparison_lab.populate_reference(reference, result, built["labels"])[1] == []
    misquoted = deepcopy(reference)
    misquoted["propositions"][0]["positions"]["R2"]["quote"] = "the lamp shows a watch"
    outside = deepcopy(reference)
    outside["propositions"][0]["positions"]["R1"]["cited"] = ["A:5"]
    undeclared = deepcopy(reference)
    undeclared["agreement"] = []
    for bad in (misquoted, outside, undeclared):
        assert comparison_lab.populate_reference(bad, result, built["labels"])[1]
    assert comparison_lab.validate_result({**result, "consensus": "R1"})
    assert set(comparison_lab._keys({**result, "semantic": {"agreement": []}})) & comparison_lab.FORBIDDEN_KEYS


def test_comparator_module_has_no_provider_storage_or_network_dependency():
    tree = ast.parse((ROOT / "hermeneia" / "perspective_comparison.py").read_text())
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported <= {"__future__", "datetime", "hashlib", "itertools", "json",
                        "perspective_achievement_evidence", "perspective_execution_receipts"}, imported


def test_api_is_a_read_only_projection_of_the_production_comparator(tmp_path):
    built = _built("C08", tmp_path)
    db, ids = built["db"], built["ids"]
    client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
    before = lab._logical_digest(db)
    query = "&".join(f"receipt_id={ids[key]}" for key in ("R3", "R1", "R2"))
    response = client.get(f"/api/perspective/comparison?{query}")
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    expected = compare_retained_perspectives(_evidence(db), [ids["R1"], ids["R2"], ids["R3"]])
    assert response.get_json() == json.loads(json.dumps(expected))
    assert [p["receipt_id"] for p in response.get_json()["participants"]] == [ids["R1"], ids["R2"], ids["R3"]]
    refusals = {
        f"/api/perspective/comparison?{query}&debug=1": (400, "UNSUPPORTED_PARAMETER"),
        f"/api/perspective/comparison?receipt_id={ids['R1']}&receipt_id={ids['R1']}": (400, "DUPLICATE_PARTICIPANT"),
        f"/api/perspective/comparison?receipt_id={ids['R1']}": (400, "TOO_FEW_PARTICIPANTS"),
        f"/api/perspective/comparison?receipt_id={ids['R1']}&receipt_id=unknown": (409, "INELIGIBLE_RECEIPT"),
    }
    for url, (status, code) in refusals.items():
        refused = client.get(url)
        assert (refused.status_code, refused.get_json()["code"]) == (status, code), url
    assert lab._logical_digest(db) == before


def test_api_refuses_an_excluded_receipt_exactly_as_an_unknown_one(tmp_path):
    built = _built("C10", tmp_path)
    client = create_app(db_path=built["db"], credential_store=lab._NoCredentials()).test_client()
    excluded = client.get(f"/api/perspective/comparison?receipt_id={built['ids']['R1']}&receipt_id={built['ids']['R3']}")
    unknown = client.get(f"/api/perspective/comparison?receipt_id={built['ids']['R1']}&receipt_id=unknown")
    assert excluded.status_code == unknown.status_code == 409
    assert excluded.get_json() == unknown.get_json()


def test_api_without_a_workspace_creates_nothing(tmp_path):
    db = tmp_path / "missing" / "workspace.db"
    client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
    response = client.get("/api/perspective/comparison?receipt_id=a&receipt_id=b")
    assert (response.status_code, response.get_json()["code"]) == (409, "COVERAGE_UNSUPPORTED")
    assert not db.exists() and not db.parent.exists()
