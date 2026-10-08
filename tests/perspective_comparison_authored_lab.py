"""P7 closeout laboratory (#215): steward-authored structured comparisons on the frozen corpus.

The completion evidence of docs/design/perspective-comparison-p7-disposition.md
§6. Each frozen Layer 1 case is materialized in a disposable synthetic
workspace through production write boundaries. The steward then authors the
case's frozen reference annotation directly, through the authoring-basis and
authored routes, on an app with semantic extraction in its default disabled
state. No model is called. Evaluation data, not study history.

    python tests/perspective_comparison_authored_lab.py --write research/perspective_comparison_authored/v1
    python tests/perspective_comparison_authored_lab.py --check research/perspective_comparison_authored/v1
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for entry in (str(ROOT), str(TESTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import perspective_comparison_candidate_lab as candidate_lab  # noqa: E402
import perspective_comparison_lab as layer1_lab  # noqa: E402
import synthetic_study_lab as lab  # noqa: E402
from hermeneia.accepted_perspective_comparisons import TABLE, verify_accepted_comparison  # noqa: E402
from hermeneia.capabilities import evaluate_capabilities  # noqa: E402
from hermeneia.companion_coach import coach  # noqa: E402
from hermeneia.guided_study_cycle import project_guided_study_cycle  # noqa: E402
from hermeneia.perspective_execution_receipts import canonical_bytes  # noqa: E402
from hermeneia.study_lineage import project_study_lineage  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from hermeneia.workspace import export_workspace_bundle, restore_workspace  # noqa: E402
from test_e10_vertical_slice_api import _CapturingProvider, _FakeOllamaClient  # noqa: E402

RESULT_SCHEMA = "hermeneia.perspective-comparison-authored-lab-results/v1"
EXPORT_TIME = "2026-10-08T00:00:00+00:00"
VERIFIED = {"record_integrity": "valid", "receipt_closure": "verified", "layer1_replay": "verified",
            "candidate_replay": "not_applicable", "model_output": "preserved_not_replayed"}


class AuthoredStudy:
    """A disposable workspace and a default-configuration app (semantic extraction disabled)."""

    case_local = candidate_lab.Study.case_local

    def __init__(self, layer1_corpus: dict, case: dict, workdir: Path):
        self.case = case
        built = layer1_lab.materialize(layer1_corpus, case, workdir)
        self.db, self.ids, self.labels = built["db"], built["ids"], built["labels"]
        self.app = create_app(db_path=self.db, credential_store=lab._NoCredentials())
        self.client = self.app.test_client()
        self.receipt_ids = [self.ids[key] for key in case["compare"]]
        self.responses = {step["key"]: step["response"] for step in case["steps"] if step["op"] == "run"}

    def basis(self):
        query = "&".join(f"receipt_id={rid}" for rid in self.receipt_ids)
        return self.client.get(f"/api/perspective/comparison/authoring-basis?{query}")

    def submit(self, binding, structure):
        return self.client.post("/api/perspective/comparison/authored", json={"binding": binding, "structure": structure})

    def records(self) -> list[tuple]:
        conn = lab._read_only(self.db)
        try:
            return [tuple(row) for row in conn.execute(f"SELECT id, candidate_id, comparison_json FROM {TABLE} ORDER BY id")]
        finally:
            conn.close()

    def verify(self, identifier: str, db: Path | None = None) -> dict:
        conn = lab._read_only(db or self.db)
        try:
            return verify_accepted_comparison(conn, identifier)
        finally:
            conn.close()

    def lineage_item(self, identifier: str):
        conn = lab._read_only(self.db)
        try:
            return next((i for i in project_study_lineage(conn)["items"] if i["record"] == {"table": TABLE, "key": {"id": identifier}}), None)
        finally:
            conn.close()

    def governed_views(self) -> dict:
        """P1, P2 and P6 over the current snapshot: must be unchanged by an authored comparison."""
        conn = lab._read_only(self.db)
        try:
            lineage = project_study_lineage(conn)
        finally:
            conn.close()
        evaluation = evaluate_capabilities(lineage, current_state={})
        guide = project_guided_study_cycle(lineage, current_state={})
        return json.loads(canonical_bytes({"p1": evaluation["capabilities"], "p2": guide["steps"],
                                           "p2_recommended": guide["recommended_step_id"], "p6": coach(evaluation, guide)}))

    def exclude(self, doc: str) -> None:
        identifier = next(i for i, label in self.labels.items() if label == doc)
        lab._ok(self.client.patch(f"/api/documents/{identifier}/scope", json={"source_role": "reference"}))
        lab._ok(self.client.patch(f"/api/documents/{identifier}/scope", json={"excluded": True}))


def _export_restore(study: AuthoredStudy, workdir: Path, identifier: str) -> dict:
    bundle, target = workdir / "bundle", workdir / "restored" / "workspace.db"
    target.parent.mkdir()
    export_workspace_bundle(study.db, bundle, generated_at=EXPORT_TIME, workspace_id="synthetic-p7-authored")
    restore_workspace(target, bundle)
    conn = lab._read_only(target)
    try:
        restored = [tuple(row) for row in conn.execute(f"SELECT id, candidate_id, comparison_json FROM {TABLE} ORDER BY id")]
    finally:
        conn.close()
    return {"bytes_identical": restored == study.records(), "restored_verify": study.verify(identifier, target)}


def author_case(layer1_corpus, case, workdir) -> dict:
    study = AuthoredStudy(layer1_corpus, case, workdir / "ws")
    before = study.governed_views()
    basis = study.basis()
    structure = candidate_lab._edit(study, case["reference"], "reference")
    response = study.submit(basis.get_json()["binding"], structure)
    record = response.get_json()
    local = study.case_local(record["structure"])
    matched = {p["id"]: ref["id"] for p, ref in zip(local["propositions"], case["reference"]["propositions"])}
    row = next(r for r in study.records() if r[0] == record["id"])
    conn = sqlite3.connect(study.db)
    immutable = True
    for statement in (f"UPDATE {TABLE} SET comparison_json = comparison_json", f"DELETE FROM {TABLE}",
                      f"INSERT OR REPLACE INTO {TABLE} SELECT * FROM {TABLE}"):
        try:
            conn.execute(statement)
            immutable = False
        except sqlite3.IntegrityError:
            pass
    conn.rollback()
    conn.close()
    again = study.submit(basis.get_json()["binding"], structure)
    item = study.lineage_item(record["id"])
    round_trip = _export_restore(study, workdir, record["id"])
    relations = local["relations"]
    checks = {
        "basis_read_only_no_store": basis.status_code == 200 and basis.headers.get("Cache-Control") == "no-store",
        "recorded_as_steward_authored": (response.status_code == 201 and record["origin"] == {"kind": "steward_authored"}
                                         and record["acceptance"]["decision"] == "author" and record["candidate"] is None
                                         and record["structure"]["untraceable"] == []),
        "relations_reproduce_frozen_reference": candidate_lab._relations_as_reference(local, case["reference"], matched),
        "stored_bytes_canonical": row[2] == canonical_bytes(record).decode("utf-8") and row[1] is None,
        "append_only": immutable,
        "resubmission_returns_same_record": again.status_code == 200 and again.get_json()["id"] == record["id"] and len(study.records()) == 1,
        "lineage_human_steward_authored": item is not None and item["authorship"] == "human" and item["record_data"]["origin"] == "steward_authored",
        "independent_verification": study.verify(record["id"]) == VERIFIED,
        "export_restore_exact": round_trip["bytes_identical"] and round_trip["restored_verify"] == VERIFIED,
        "p1_p2_p6_unchanged": study.governed_views() == before,
        "no_authority_fields": candidate_lab._no_authority(record),
    }
    return {"item": case["case_id"], "kind": "authored_reference", "checks": checks,
            "relations": {"agreement": [(matched[a["proposition"]], a["stance"], a["participants"], a["reliance"]) for a in relations["agreement"]],
                          "disagreement": [(matched[d["proposition"]], d["groups"], d["minority_participants"], d["reliance"]) for d in relations["disagreement"]],
                          "unknown_positions": [(matched[u["proposition"]], u["participant"], u["stance"]) for u in relations["unknown_positions"]],
                          "assumptions": [a["participant"] for a in local["assumptions"]],
                          "evidence_use": {e["participant"]: {"relied_on": sorted(r["key"]["id"] for r in e["relied_on"]),
                                                              "supplied_not_relied_on": sorted(r["key"]["id"] for r in e["supplied_not_relied_on"])}
                                           for e in relations["evidence_use"]}}}


def explicit_unknown(layer1_corpus, cases, workdir) -> dict:
    case = cases["C11_legitimately_unclassifiable"]
    study = AuthoredStudy(layer1_corpus, case, workdir / "ws")
    structure = candidate_lab._edit(study, case["reference"], "reference")
    r2 = structure["participants"][1]
    position = next(p for p in structure["propositions"][0]["positions"] if p["participant"] == r2)
    position.update(stance="unknown", span=None, reliance=[])
    response = study.submit(study.basis().get_json()["binding"], structure)
    record = response.get_json()
    unknown = [(u["participant"], u["stance"]) for u in record["structure"]["relations"]["unknown_positions"]]
    return {"item": "E1_explicit_unknown", "kind": "demonstration",
            "checks": {"recorded": response.status_code == 201,
                       "explicit_unknown_kept_without_support": (r2, "unknown") in unknown and record["structure"]["untraceable"] == [],
                       "no_relation_manufactured": record["structure"]["relations"]["agreement"] == record["structure"]["relations"]["disagreement"] == []},
            "unknown_positions": [(study.labels[p], s) for p, s in unknown]}


def no_reliance(results_by_case: dict) -> dict:
    use = results_by_case["C09_unsupported_assertion"]["relations"]["evidence_use"]["R2"]
    return {"item": "E2_no_reliance_established", "kind": "demonstration",
            "checks": {"asserted_with_reliance_empty": use["relied_on"] == [] and use["supplied_not_relied_on"] == ["A:1"]},
            "evidence_use_R2": use}


def refusals(layer1_corpus, cases, workdir) -> list[dict]:
    case = cases["C01_same_conclusion_same_evidence"]
    results = []

    def scenario(name, mutate, expected_status, expected_code):
        study = AuthoredStudy(layer1_corpus, case, workdir / name)
        before = lab._logical_digest(study.db)
        binding = study.basis().get_json()["binding"]
        structure = candidate_lab._edit(study, case["reference"], "reference")
        binding, structure, changed_workspace = mutate(study, binding, structure)
        response = study.submit(binding, structure)
        body = response.get_json()
        checks = {"refused_as_frozen": (response.status_code, body.get("code")) == (expected_status, expected_code),
                  "nothing_recorded": study.records() == []}
        if not changed_workspace:
            checks["workspace_unchanged"] = lab._logical_digest(study.db) == before
        results.append({"item": name, "kind": "refusal", "checks": checks, "observed": [response.status_code, body.get("code")]})

    def governing_changed(study, binding, structure):
        lab._ok(study.client.put("/api/investigation", json={"thesis": "Who keeps the harbor watch?"}))
        return binding, structure, True

    def participant_excluded(study, binding, structure):
        study.exclude("A")
        return binding, structure, True

    def layer1_altered(study, binding, structure):
        altered = deepcopy(binding)
        altered["layer1"]["digest"] = "sha256:" + "0" * 64
        return altered, structure, False

    def untraceable(study, binding, structure):
        return binding, candidate_lab._edit(study, case["reference"], "untraceable"), False

    def authority(study, binding, structure):
        return binding, candidate_lab._edit(study, case["reference"], "authority_field"), False

    def missing_position(study, binding, structure):
        structure["propositions"][0]["positions"].pop()
        return binding, structure, False

    scenario("R1_governing_question_changed", governing_changed, 409, "STALE_INPUT")
    scenario("R2_participant_excluded", participant_excluded, 409, "STALE_INPUT")
    scenario("R3_layer1_digest_altered", layer1_altered, 409, "STALE_INPUT")
    scenario("R4_untraceable_span", untraceable, 422, "STRUCTURE_UNTRACEABLE")
    scenario("R5_authority_key", authority, 422, "STRUCTURE_INVALID")
    scenario("R6_missing_position", missing_position, 422, "STRUCTURE_INVALID")
    return results


def exclusion_after_authoring(layer1_corpus, cases, workdir) -> dict:
    case = cases["C08_two_to_one_minority"]
    study = AuthoredStudy(layer1_corpus, case, workdir / "ws")
    record = study.submit(study.basis().get_json()["binding"], candidate_lab._edit(study, case["reference"], "reference")).get_json()
    study.exclude("A")
    verified = study.verify(record["id"])
    round_trip = _export_restore(study, workdir, record["id"])
    return {"item": "X1_exclusion_after_authoring", "kind": "exclusion",
            "checks": {"lineage_omits": study.lineage_item(record["id"]) is None,
                       "get_unavailable": study.client.get(f"/api/perspective/comparison/accepted/{record['id']}").status_code == 404,
                       "record_preserved": len(study.records()) == 1,
                       "verification": verified == {**VERIFIED, "layer1_replay": "participants_not_eligible"},
                       "export_restore_exact": round_trip["bytes_identical"] and round_trip["restored_verify"] == verified},
            "verification": verified}


def model_gate(layer1_corpus, cases, workdir) -> dict:
    study = AuthoredStudy(layer1_corpus, cases["C01_same_conclusion_same_evidence"], workdir / "ws")
    before, calls = lab._logical_digest(study.db), len(_CapturingProvider.render_prompts)
    response = study.client.post("/api/perspective/comparison/candidates",
                                 json={"receipt_ids": study.receipt_ids, "model": "model-extract:1b"})
    return {"item": "G1_model_generation_disabled_by_default", "kind": "gate",
            "checks": {"refused": (response.status_code, response.get_json()["code"]) == (403, "SEMANTIC_EXTRACTION_DISABLED"),
                       "no_model_call": len(_CapturingProvider.render_prompts) == calls,
                       "workspace_unchanged": lab._logical_digest(study.db) == before}}


def run() -> dict:
    corpus, cases = candidate_lab.load()
    layer1_corpus = layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    records, by_case = [], {}

    def isolated(fn, *args):
        with tempfile.TemporaryDirectory(prefix="p7-authored-") as tmp:
            workdir = Path(tmp)
            with lab.isolated(workdir):
                _FakeOllamaClient.models = list(layer1_corpus["models"])
                return fn(*args, workdir)

    for case_id in corpus["faithful"]["cases"]:
        result = isolated(author_case, layer1_corpus, cases[case_id])
        by_case[case_id] = result
        records.append(result)
    records.append(isolated(explicit_unknown, layer1_corpus, cases))
    records.append(no_reliance(by_case))
    records.extend(isolated(refusals, layer1_corpus, cases))
    records.append(isolated(exclusion_after_authoring, layer1_corpus, cases))
    records.append(isolated(model_gate, layer1_corpus, cases))
    aggregate = {kind: {"items": sum(1 for r in records if r["kind"] == kind),
                        "all_checks_passed": sum(1 for r in records if r["kind"] == kind and all(r["checks"].values()))}
                 for kind in ("authored_reference", "demonstration", "refusal", "exclusion", "gate")}
    return {"schema": RESULT_SCHEMA, "contract": "docs/design/perspective-comparison-p7-disposition.md §6",
            "method": "disposable synthetic workspaces through production write boundaries; default app configuration "
                      "(semantic extraction disabled); no model call; frozen references authored directly",
            "aggregate": aggregate, "records": json.loads(json.dumps(records))}


def summary_markdown(results: dict) -> str:
    lines = ["# P7 closeout — steward-authored structured comparison — evaluation summary", "",
             "Generated by `tests/perspective_comparison_authored_lab.py` (contract: "
             "`docs/design/perspective-comparison-p7-disposition.md` §6). No model is called. Evaluation data, not study history.", "",
             "| Item | Kind | Shown | Checks |", "| --- | --- | --- | --- |"]
    for r in results["records"]:
        passed = f"{sum(1 for v in r['checks'].values() if v)}/{len(r['checks'])}"
        if r["kind"] == "authored_reference":
            rel = r["relations"]
            parts = [f"agree {a[0]} {'+'.join(a[2])} (reliance {a[3]})" for a in rel["agreement"]]
            parts += [f"disagree {d[0]} {'+'.join(d[1][0]['participants'])} vs {'+'.join(d[1][1]['participants'])} (reliance {d[3]})"
                      + (f", minority {'+'.join(d[2])}" if d[2] else "") for d in rel["disagreement"]]
            parts += [f"{len(rel['assumptions'])} assumption(s)"] if rel["assumptions"] else []
            parts += [f"unknown {u[0]}/{u[1]} {u[2]}" for u in rel["unknown_positions"]]
            shown = "; ".join(parts) or "no cross-Perspective relation (as in the reference)"
        elif r["kind"] == "refusal":
            shown = f"{r['observed'][0]} `{r['observed'][1]}`"
        elif r["item"] == "E1_explicit_unknown":
            shown = ", ".join(f"{p} {s}" for p, s in r["unknown_positions"])
        elif r["item"] == "E2_no_reliance_established":
            shown = f"R2 relied_on {r['evidence_use_R2']['relied_on']}, supplied_not_relied_on {r['evidence_use_R2']['supplied_not_relied_on']}"
        elif r["kind"] == "exclusion":
            shown = "Lineage omits; GET 404; " + ", ".join(f"{k}={v}" for k, v in r["verification"].items() if k != "model_output")
        else:
            shown = "403 `SEMANTIC_EXTRACTION_DISABLED`; no model call; no write"
        lines.append(f"| {r['item']} | {r['kind']} | {shown} | {passed} |")
    lines += ["", "## Aggregate", ""] + [f"- `{k}`: {v['all_checks_passed']}/{v['items']}" for k, v in results["aggregate"].items()]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    results = json.loads(json.dumps(run(), sort_keys=True, ensure_ascii=False))
    if args.write:
        args.write.mkdir(parents=True, exist_ok=True)
        (args.write / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        (args.write / "summary.md").write_text(summary_markdown(results))
        print(f"wrote {args.write}")
        return 0
    committed = json.loads((args.check / "results.json").read_text())
    if committed != results or (args.check / "summary.md").read_text() != summary_markdown(results):
        print("results differ from committed dataset")
        return 1
    print("results match committed dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
