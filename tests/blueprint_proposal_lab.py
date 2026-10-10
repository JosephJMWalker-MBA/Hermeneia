"""P8 laboratory (#215): natural-language Blueprint proposals on the frozen synthetic corpus.

Each case in tests/fixtures/blueprint_proposal/v1/cases.json is materialized in
a disposable synthetic workspace through production write boundaries. The
"model" is the repository's in-process fake local adapter, returning a scripted
output written in case-local references and rendered against the real basis
labels. Production routes generate, refuse, accept, edit, discard and record.
This module only checks the frozen structural expectations. No network, no
real model. Evaluation data, not study history.

    python tests/blueprint_proposal_lab.py --write research/blueprint_proposal/v1
    python tests/blueprint_proposal_lab.py --check research/blueprint_proposal/v1
"""
from __future__ import annotations

import argparse
import io
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

import synthetic_study_lab as lab  # noqa: E402  (P5 isolation, PDF and fake-adapter primitives, unchanged)
from hermeneia.blueprint_proposals import TABLE, build_prompt, proposal_basis, verify_receipt  # noqa: E402
from hermeneia.storage.hashing import make_interpretation_id  # noqa: E402
from hermeneia.storage.sqlite import SQLiteStore  # noqa: E402
from hermeneia.study_lineage import project_study_lineage  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from hermeneia.workspace import export_workspace_bundle, read_bundle, restore_workspace  # noqa: E402
from test_e10_vertical_slice_api import _CapturingProvider, _FakeOllamaClient  # noqa: E402

CORPUS = TESTS / "fixtures" / "blueprint_proposal" / "v1" / "cases.json"
RESULT_SCHEMA = "hermeneia.blueprint-proposal-lab-results/v1"
EXPORT_TIME = "2026-10-08T00:00:00+00:00"


def load() -> dict:
    corpus = json.loads(CORPUS.read_text())
    if corpus.get("schema") != "hermeneia.blueprint-proposal-cases/v1" or corpus.get("policy_version") != "1.0.0":
        raise ValueError("P8 corpus schema or policy differs; re-freeze deliberately")
    return corpus


class Workspace:
    """One disposable study with case-local maps: A:n → Observation, I:key → Interpretation, BPk → Blueprint."""

    def __init__(self, corpus: dict, workdir: Path):
        self.corpus = corpus
        self.db = workdir / "ws" / "workspace.db"
        SQLiteStore(self.db).close()
        self.base = create_app(db_path=self.db, credential_store=lab._NoCredentials()).test_client()
        app = create_app(db_path=self.db, provider_registry=lab._ollama_registry(), credential_store=lab._NoCredentials())
        app.config["BLUEPRINT_PROPOSAL_GENERATION"] = "experimental"  # only the laboratory enables generation
        self.client = app.test_client()
        self.docs, self.obs, self.interps, self.perspectives, self.proposals, self.blueprints = {}, {}, {}, {}, {}, {}

    def ref(self, token: str) -> str:
        if token.startswith("I:"):
            return self.interps[token[2:]]
        doc, n = token.split(":")
        return self.obs[(doc, int(n))]

    def blueprint_payload(self, spec: dict) -> dict:
        return {"title": spec["title"], "thesis": spec["thesis"],
                "sections": [{"claim": s["claim"], "supporting_observations": [self.ref(t) for t in s["observations"]],
                              "supporting_interpretations": [self.ref(t) for t in s["interpretations"]]} for s in spec["sections"]]}

    def apply(self, op: dict) -> None:
        kind = op["op"]
        if kind == "upload":
            lines = self.corpus["documents"][op["doc"]]
            body = lab._ok(self.base.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(lines)), f"synthetic-{op['doc']}.pdf")},
                                          content_type="multipart/form-data"))
            self.docs[op["doc"]] = body["document_id"]
            conn = sqlite3.connect(self.db)
            rows = conn.execute("SELECT id FROM observations WHERE source_document_id = ? ORDER BY page, paragraph, sentence",
                                (body["document_id"],)).fetchall()
            conn.close()
            self.obs.update({(op["doc"], n): row[0] for n, row in enumerate(rows, 1)})
        elif kind == "save_perspective":
            self.perspectives[op["key"]] = lab._ok(self.base.post("/api/perspective/saved", json={"perspective_draft": {
                "label": op["label"], "purpose": op["purpose"], "questions": op["questions"]}, "declared_by": "Synthetic lab steward"}))
        elif kind == "steward_interpretation":
            saved = self.perspectives[op["perspective"]]
            conn = sqlite3.connect(self.db)
            name = conn.execute("SELECT name FROM perspectives WHERE id = ?", (saved["id"],)).fetchone()[0]
            conn.close()
            oid = self.obs[(op["doc"], op["sentence"])]
            identifier = make_interpretation_id(oid, name, op["text"])
            store = SQLiteStore(self.db)
            try:
                store.insert_interpretation({"id": identifier, "observation_id": oid, "perspective": name, "perspective_id": saved["id"],
                                             "text": op["text"], "evidential_status": "speculative",
                                             "evidence_observation_ids": json.dumps([oid]), "confidence": "human",
                                             "source": "steward-authored", "created_at": "2026-10-08T12:00:00+00:00"})
            finally:
                store.close()
            self.interps[op["key"]] = identifier
        elif kind == "model_proposal":
            e10 = create_app(db_path=self.db, provider_registry=lab._proposal_registry(), credential_store=lab._NoCredentials()).test_client()
            body = lab._ok(e10.post("/api/e10/interpretations/generate", json={"observation_id": self.obs[(op["doc"], op["sentence"])],
                                                                               "participants": ["gpt"]}))
            self.proposals[op["key"]] = body["proposals"][0]["id"]
        elif kind == "accept_proposal":
            body = lab._ok(self.base.post(f"/api/e10/proposals/{self.proposals[op['proposal']]}/accept", json={"comment": op["rationale"]}))
            self.interps[op["proposal"]] = body["interpretation"]["id"]
        elif kind == "exclude_document":
            lab._ok(self.base.patch(f"/api/documents/{self.docs[op['doc']]}/scope", json={"source_role": "reference"}))
            lab._ok(self.base.patch(f"/api/documents/{self.docs[op['doc']]}/scope", json={"excluded": True}))
        elif kind == "ratify_blueprint_exact":
            body = lab._ok(self.base.post("/api/pipeline/ratify-blueprint", json={"candidate": self.blueprint_payload(op["blueprint"])}))
            self.blueprints[op["key"]] = body["blueprint_id"]
        elif kind == "legacy_revise":
            body = lab._ok(self.base.post("/api/pipeline/revise-blueprint", json={
                "predecessor_id": self.blueprints[op["predecessor"]], "reason": op["reason"],
                "candidate": self.blueprint_payload(op["blueprint"])}))
            self.blueprints["legacy_successor"] = body["blueprint_id"]
        else:
            raise ValueError(f"unknown setup op {kind}")

    def basis(self, mode: str, predecessor: str | None):
        conn = lab._read_only(self.db)
        try:
            return proposal_basis(conn, mode, self.blueprints.get(predecessor) if predecessor else None)
        finally:
            conn.close()

    def wire(self, script: dict, basis: dict) -> str:
        if "raw" in script:
            return script["raw"]
        labels = {e["id"]: e["label"] for e in [*basis["binding"]["observations"], *basis["binding"]["interpretations"]]}

        def render(token):
            if token.startswith("raw:"):
                return self.ref(token[4:])
            if token == "O99":
                return token
            return labels[self.ref(token)]

        out = {"title": script["title"], "thesis": script["thesis"],
               "sections": [{"claim": s["claim"], "observations": [render(t) for t in s["observations"]],
                             "interpretations": [render(t) for t in s["interpretations"]]} for s in script["sections"]]}
        if "change_summary" in script:
            out["change_summary"] = script["change_summary"]
        return json.dumps(out)

    def count(self, table: str) -> int:
        conn = lab._read_only(self.db)
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def row(self, sql: str, args=()):
        conn = lab._read_only(self.db)
        try:
            cursor = conn.execute(sql, args)
            raw = cursor.fetchone()
            return dict(zip([c[0] for c in cursor.description], raw)) if raw else None
        finally:
            conn.close()

    def lineage(self, table: str, identifier: str):
        conn = lab._read_only(self.db)
        try:
            return next((i for i in project_study_lineage(conn)["items"]
                         if i["record"] == {"table": table, "key": {"id": identifier}} and i["event"] == "recorded"), None)
        finally:
            conn.close()

    def local(self, identifier: str) -> str:
        for (doc, n), oid in self.obs.items():
            if oid == identifier:
                return f"{doc}:{n}"
        for key, iid in self.interps.items():
            if iid == identifier:
                return f"I:{key}"
        return identifier


def propose(ws: Workspace, generate: dict, script: dict, model: str):
    basis = ws.basis(generate["mode"], generate.get("predecessor"))
    _CapturingProvider.render_responses = [ws.wire(script, basis)]
    body = {"mode": generate["mode"], "intent": generate["intent"], "model": generate.get("model", model)}
    if generate["mode"] == "revise":
        body["predecessor_id"] = ws.blueprints[generate["predecessor"]]
    return ws.client.post("/api/blueprint/proposals", json=body), basis


def decide(ws: Workspace, candidate: dict, step: dict):
    cid = candidate["candidate_id"]
    if step["decision"] == "discard":
        return ws.client.post(f"/api/blueprint/proposals/{cid}/discard", json={"decision": "discard", "candidate_id": cid})
    body = {"decision": step["decision"], "candidate_id": cid}
    if "reason" in step:
        body["reason"] = step["reason"]
    if step["decision"] == "edit_and_accept":
        edited = json.loads(json.dumps(candidate["proposal"]["blueprint"]))
        edited["title"] = step["edit"]["title"]
        if step["edit"].get("drop_last_section"):
            edited["sections"] = edited["sections"][:-1]
        body["blueprint"] = edited
    return ws.client.post(f"/api/blueprint/proposals/{cid}/accept", json=body)


def run_case(corpus: dict, case: dict, workdir: Path) -> dict:
    ws = Workspace(corpus, workdir)
    for op in case["setup"]:
        ws.apply(op)
    expected, observed, checks = case["expected"], {}, {}
    before = lab._logical_digest(ws.db)
    calls = len(_CapturingProvider.render_prompts)
    response, basis = propose(ws, case["generate"], case["generate"]["script"], corpus["extraction_model"])
    body = response.get_json() or {}
    gen = {"status": response.status_code, "code": body.get("code")}
    gen_expected = expected["generation"]
    checks["generation_outcome"] = response.status_code == gen_expected["status"] and (
        "code" not in gen_expected or body.get("code") == gen_expected["code"])
    checks["generation_writes_nothing"] = lab._logical_digest(ws.db) == before
    if gen_expected.get("no_provider_call"):
        checks["no_provider_call"] = len(_CapturingProvider.render_prompts) == calls
    for variant in case.get("variants", []):
        v_response, _ = propose(ws, case["generate"], variant["script"], corpus["extraction_model"])
        checks[f"variant_{variant['expect']['code']}"] = (v_response.status_code, v_response.get_json().get("code")) == (
            variant["expect"]["status"], variant["expect"]["code"])
    if "prompt_excludes_document" in gen_expected:
        prompt = build_prompt(basis, case["generate"]["intent"])
        checks["excluded_text_never_exposed"] = not any(line in prompt for line in corpus["documents"][gen_expected["prompt_excludes_document"]])
    candidate = body if response.status_code == 201 else None
    if candidate:
        proposal = candidate["proposal"]["blueprint"]
        refs = {"observations": sorted({ws.local(o) for s in proposal["sections"] for o in s["supporting_observations"]}),
                "interpretations": sorted({ws.local(i) for s in proposal["sections"] for i in s["supporting_interpretations"]})}
        gen["references"] = refs
        if "references" in gen_expected:
            checks["references_resolve_to_exposed_records"] = refs == {k: sorted(v) for k, v in gen_expected["references"].items()}
        if "exposed" in gen_expected:
            checks["exposed_basis"] = {"observations": len(candidate["binding"]["basis"]["observations"]),
                                       "interpretations": len(candidate["binding"]["basis"]["interpretations"])} == gen_expected["exposed"]
        if "interpretation_authorship_in_prompt" in gen_expected:
            label = {e["id"]: e["label"] for e in candidate["binding"]["basis"]["interpretations"]}
            prompt = candidate["extraction"]["prompt"]
            checks["prompt_labels_interpretation_authorship"] = all(
                f"{label[ws.interps[key]]} ({text};" in prompt for key, text in gen_expected["interpretation_authorship_in_prompt"].items())
        checks["candidate_binds_adapter_execution"] = (candidate["extraction"]["execution"].get("adapter") == "_CapturingProvider"
                                                       and candidate["extraction"]["execution"].get("model_id") == corpus["extraction_model"])
    observed["generation"] = gen
    for op in case["between"]:
        ws.apply(op)
    pre_decision = lab._logical_digest(ws.db)
    predecessor_row = ws.row("SELECT * FROM narrative_blueprints WHERE id = ?", (ws.blueprints["BP0"],)) if "BP0" in ws.blueprints else None
    receipt = None
    decisions = []
    for step in case["decisions"]:
        d_response = decide(ws, candidate, step)
        d_body = d_response.get_json() or {}
        entry = {"decision": step["decision"], "status": d_response.status_code, "code": d_body.get("code")}
        want = step["expect"]
        ok = d_response.status_code == want["status"] and ("code" not in want or d_body.get("code") == want["code"])
        if want.get("same_receipt"):
            ok = ok and receipt is not None and d_body.get("id") == receipt["id"]
        if d_response.status_code == 201:
            receipt = d_body
        decisions.append(entry)
        checks[f"decision_{len(decisions)}_{step['decision']}"] = ok
    observed["decisions"] = decisions
    result = expected.get("result", {})
    if "counts" in result:
        counts = {"receipts": ws.count(TABLE), "blueprints": ws.count("narrative_blueprints")}
        observed["counts"] = counts
        checks["counts"] = counts == result["counts"]
    if result.get("workspace_unchanged"):
        checks["workspace_unchanged"] = lab._logical_digest(ws.db) == pre_decision
    if "legacy_revision_source" in result:
        legacy = ws.row("SELECT source FROM narrative_blueprints WHERE id = ?", (ws.blueprints["legacy_successor"],))
        checks["legacy_revise_parity"] = legacy["source"] == result["legacy_revision_source"]
    if receipt is not None:
        bp_id = receipt["result"]["resulting_blueprint_id"]
        bp_row = ws.row("SELECT * FROM narrative_blueprints WHERE id = ?", (bp_id,))
        r = {"blueprint_source": bp_row["source"], "receipt_origin": receipt["origin"]["kind"], "edited": receipt["acceptance"]["edited"],
             "plan_compiled": ws.row("SELECT id FROM architect_plans WHERE id = ? AND blueprint_id = ?", (receipt["result"]["plan_id"], bp_id)) is not None,
             "accepted_equals_proposal": receipt["acceptance"]["accepted_blueprint"] == candidate["proposal"]["blueprint"],
             "proposal_preserved": receipt["candidate"]["proposal"] == candidate["proposal"],
             "accepted_title": receipt["acceptance"]["accepted_blueprint"]["title"],
             "accepted_sections": len(receipt["acceptance"]["accepted_blueprint"]["sections"]),
             "lineage": {"blueprint": (ws.lineage("narrative_blueprints", bp_id) or {}).get("authorship"),
                         "receipt": (ws.lineage(TABLE, receipt["id"]) or {}).get("authorship")}}
        conn = lab._read_only(ws.db)
        try:
            r["verify"] = verify_receipt(conn, receipt["id"])
        finally:
            conn.close()
        if receipt["mode"] == "revise":
            edge = receipt["result"]["supersession"]
            r["supersession_reason"] = ws.row("SELECT reason FROM supersession_relations WHERE old_id=? AND new_id=? AND ratified_at=?",
                                               (edge["old_id"], edge["new_id"], edge["ratified_at"]))["reason"]
            r["model_explanation"] = receipt["candidate"]["proposal"]["model_explanation"]
            r["rationale_is_not_model_explanation"] = receipt["acceptance"]["rationale"] != r["model_explanation"] and r["supersession_reason"] == receipt["acceptance"]["rationale"]
            r["predecessor_unchanged"] = ws.row("SELECT * FROM narrative_blueprints WHERE id = ?", (ws.blueprints["BP0"],)) == predecessor_row
        observed["result"] = {k: v for k, v in r.items()}
        for key, value in result.items():
            if key in r:
                checks[f"result_{key}"] = r[key] == value
        if "portability" in expected:
            bundle, target = workdir / "bundle", workdir / "restored" / "workspace.db"
            target.parent.mkdir()
            manifest = export_workspace_bundle(ws.db, bundle, generated_at=EXPORT_TIME, workspace_id="synthetic-p8")
            coverage = read_bundle(bundle)["coverage"][TABLE]
            restore_workspace(target, bundle)
            restored = sqlite3.connect(target).execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
            want = expected["portability"]
            observed["portability"] = {"component_exported": any("blueprint_proposal" in f["path"] for f in manifest["files"]),
                                       "coverage_status": coverage["status"], "restored_receipts": restored}
            checks["portability_declared"] = (observed["portability"] == {k: want[k] for k in ("component_exported", "coverage_status", "restored_receipts")}
                                              and all(word in coverage["reason"] for word in want["reason_mentions"]))
    return {"case_id": case["case_id"], "checks": checks, "observed": observed}


def further_checks(corpus: dict, workdir: Path) -> list[dict]:
    results = []
    script = next(c for c in corpus["cases"] if c["case_id"] == "P05_exact_accept")["generate"]
    # F1: a decision naming a different candidate is refused; no client substitution of the proposal is possible.
    ws = Workspace(corpus, workdir / "f1")
    ws.apply({"op": "upload", "doc": "A"})
    candidate = propose(ws, script, script["script"], corpus["extraction_model"])[0].get_json()
    other = "blueprint-proposal-candidate:sha256:" + "0" * 64
    r = ws.client.post(f"/api/blueprint/proposals/{candidate['candidate_id']}/accept", json={"decision": "accept", "candidate_id": other})
    smuggled = ws.client.post(f"/api/blueprint/proposals/{candidate['candidate_id']}/accept",
                              json={"decision": "accept", "candidate_id": candidate["candidate_id"], "blueprint": candidate["proposal"]["blueprint"]})
    results.append({"check_id": "F1_client_substitution", "checks": {
        "mismatch_refused": (r.status_code, r.get_json()["code"]) == (409, "CANDIDATE_MISMATCH"),
        "proposal_cannot_be_posted_with_accept": (smuggled.status_code, smuggled.get_json()["code"]) == (400, "INVALID_REQUEST"),
        "nothing_recorded": ws.count(TABLE) == 0 and ws.count("narrative_blueprints") == 0}})
    # F2: a steward edit citing excluded evidence the model never saw meets the existing scope refusal.
    # (Excluding an exposed source after generation is the stale case P08, refused earlier.)
    ws = Workspace(corpus, workdir / "f2")
    for op in ({"op": "upload", "doc": "A"}, {"op": "upload", "doc": "B"}, {"op": "exclude_document", "doc": "B"}):
        ws.apply(op)
    candidate = propose(ws, script, script["script"], corpus["extraction_model"])[0].get_json()
    edited = json.loads(json.dumps(candidate["proposal"]["blueprint"]))
    edited["sections"][0]["supporting_observations"].append(ws.obs[("B", 2)])
    r = ws.client.post(f"/api/blueprint/proposals/{candidate['candidate_id']}/accept",
                       json={"decision": "edit_and_accept", "candidate_id": candidate["candidate_id"], "blueprint": edited})
    results.append({"check_id": "F2_edit_cites_excluded", "checks": {
        "scope_refusal": r.status_code == 403, "nothing_recorded": ws.count(TABLE) == 0 and ws.count("narrative_blueprints") == 0}})
    # F3: generation is disabled on a default app.
    ws = Workspace(corpus, workdir / "f3")
    ws.apply({"op": "upload", "doc": "A"})
    default = create_app(db_path=ws.db, provider_registry=lab._ollama_registry(), credential_store=lab._NoCredentials()).test_client()
    calls = len(_CapturingProvider.render_prompts)
    r = default.post("/api/blueprint/proposals", json={"mode": "create", "intent": script["intent"], "model": corpus["extraction_model"]})
    results.append({"check_id": "F3_generation_disabled_by_default", "checks": {
        "refused": (r.status_code, r.get_json()["code"]) == (403, "BLUEPRINT_PROPOSAL_DISABLED"),
        "no_provider_call": len(_CapturingProvider.render_prompts) == calls}})
    # F4: the legacy revise route still writes steward-authored successors (refactor parity) — covered in P09.
    return results


def run() -> dict:
    corpus = load()
    records = []

    def isolated(fn, *args):
        with tempfile.TemporaryDirectory(prefix="p8-proposal-") as tmp:
            workdir = Path(tmp)
            with lab.isolated(workdir):
                _FakeOllamaClient.models = [corpus["extraction_model"]]
                return fn(*args, workdir)

    for case in corpus["cases"]:
        records.append(isolated(run_case, corpus, case))
    further = isolated(further_checks, corpus)
    p09 = next(r for r in records if r["case_id"] == "P09_predecessor_superseded")
    further.append({"check_id": "F4_legacy_revise_parity", "checks": {"legacy_successor_steward_authored": p09["checks"].get("legacy_revise_parity", False)}})
    aggregate = {"cases": {"items": len(records), "all_checks_passed": sum(all(r["checks"].values()) for r in records)},
                 "further_checks": {"items": len(further), "all_checks_passed": sum(all(r["checks"].values()) for r in further)}}
    return {"schema": RESULT_SCHEMA, "contract": "docs/design/blueprint-proposal-v1.md",
            "method": ("disposable synthetic workspaces through production write boundaries; scripted in-process fake adapter; "
                       "no network; no real model"),
            "aggregate": aggregate, "cases": records, "further_checks": further}


def summary_markdown(results: dict) -> str:
    lines = ["# P8 natural-language Blueprint proposals — synthetic evaluation summary", "",
             "Generated by `tests/blueprint_proposal_lab.py` (contract `docs/design/blueprint-proposal-v1.md`). Scripted "
             "in-process providers only; these results show governance, not model competence. Evaluation data, not study history.", "",
             "| Case | Generation | Decisions | Result | Checks |", "| --- | --- | --- | --- | --- |"]
    for r in results["cases"]:
        g = r["observed"]["generation"]
        gen = f"{g['status']}" + (f" `{g['code']}`" if g.get("code") else "")
        dec = "; ".join(f"{d['decision']} {d['status']}" + (f" `{d['code']}`" if d.get("code") else "") for d in r["observed"]["decisions"]) or "—"
        res = r["observed"].get("result")
        shown = (f"source `{res['blueprint_source']}`, origin `{res['receipt_origin']}`, Lineage {res['lineage']['blueprint']}/{res['lineage']['receipt']}"
                 + (f", reason = steward's" if res.get("rationale_is_not_model_explanation") else "")) if res else (
                 f"counts {r['observed'].get('counts')}" if r["observed"].get("counts") else "—")
        if r["observed"].get("portability"):
            shown += f"; WBS coverage `{r['observed']['portability']['coverage_status']}`"
        passed = f"{sum(1 for v in r['checks'].values() if v)}/{len(r['checks'])}"
        lines.append(f"| {r['case_id']} | {gen} | {dec} | {shown} | {passed} |")
    lines += ["", "| Further check | Checks |", "| --- | --- |"]
    lines += [f"| {f['check_id']} | {sum(1 for v in f['checks'].values() if v)}/{len(f['checks'])} |" for f in results["further_checks"]]
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
