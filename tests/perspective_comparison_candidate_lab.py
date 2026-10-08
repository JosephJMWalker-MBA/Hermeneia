"""P7 Layer 2 laboratory (#215): scripted extraction → governed candidate → steward decision.

Reuses the frozen Layer 1 corpus and its reference annotations unchanged.
Every workspace is a disposable synthetic study built through production
write boundaries. The "semantic model" is the repository's in-process fake
local adapter returning scripted text; no network or real model is used.
Scripted output measures the governed pipeline, never a model's extraction
quality. Extraction is scored against the frozen references separately from
steward acceptance. Evaluation data, not study history.

    python tests/perspective_comparison_candidate_lab.py --write research/perspective_comparison_candidate/v1
    python tests/perspective_comparison_candidate_lab.py --check research/perspective_comparison_candidate/v1
"""
from __future__ import annotations

import argparse
from collections import Counter
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

import perspective_comparison_lab as layer1_lab  # noqa: E402  (Layer 1 materialization, unchanged)
import synthetic_study_lab as lab  # noqa: E402
from hermeneia.accepted_perspective_comparisons import verify_accepted_comparison  # noqa: E402
from hermeneia.perspective_comparison_candidates import AUTHORITY_KEYS, layer1_digest, text_digest  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from hermeneia.workspace import export_workspace_bundle, restore_workspace  # noqa: E402
from test_e10_vertical_slice_api import _CapturingProvider, _FakeOllamaClient  # noqa: E402

CORPUS = TESTS / "fixtures" / "perspective_comparison" / "v1" / "candidate_cases.json"
CORPUS_SCHEMA = "hermeneia.perspective-comparison-candidate-cases/v1"
RESULT_SCHEMA = "hermeneia.perspective-comparison-candidate-lab-results/v1"
SPAN_STANCES = ("asserts", "denies", "unclassifiable")
EXPORT_TIME = "2026-10-07T00:00:00+00:00"


def load() -> tuple[dict, dict]:
    corpus = json.loads(CORPUS.read_text())
    if corpus.get("schema") != CORPUS_SCHEMA or corpus.get("policy_version") != "1.0.0":
        raise ValueError("candidate corpus schema or policy differs; re-freeze deliberately")
    layer1 = layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    return corpus, {case["case_id"]: case for case in layer1["cases"]}


# ── Workspace and scripted extraction ────────────────────────────────────────

class Study:
    """One disposable synthetic workspace for one Layer 1 case, with an app client."""

    def __init__(self, layer1_corpus: dict, case: dict, workdir: Path):
        self.case = case
        built = layer1_lab.materialize(layer1_corpus, case, workdir)
        self.db, self.ids, self.labels = built["db"], built["ids"], built["labels"]
        app = create_app(db_path=self.db, provider_registry=lab._ollama_registry(), credential_store=lab._NoCredentials())
        # The evaluation laboratory is the only place the experimental extraction route is enabled.
        app.config["PERSPECTIVE_SEMANTIC_EXTRACTION"] = "experimental"
        self.client = app.test_client()
        self.receipt_ids = [self.ids[key] for key in case["compare"]]
        self.responses = {step["key"]: step["response"] for step in case["steps"] if step["op"] == "run"}

    def layer1(self) -> dict:
        return layer1_lab.production_compare(self.db, self.receipt_ids)

    def wire(self, script: dict) -> str:
        """Translate a case-local script (R-keys, A:n/h labels) into the P/U wire labels of this workspace."""
        if "raw" in script:
            return script["raw"]
        layer1 = self.layer1()
        plabel = {self.labels[p["receipt_id"]]: f"P{index}" for index, p in enumerate(layer1["participants"], 1)}
        ulabel = {self.labels[u["ref"]["key"]["id"]]: f"U{index}" for index, u in enumerate(layer1["evidence"]["units"], 1)}

        def translate(value):
            if isinstance(value, dict):
                out = {}
                for key, item in value.items():
                    if key == "participant":
                        out[key] = plabel[item]
                    elif key == "relies_on":
                        out[key] = [ulabel[label] for label in item]
                    else:
                        out[key] = translate(item)
                return out
            if isinstance(value, list):
                return [translate(item) for item in value]
            return value

        return json.dumps(translate(script), ensure_ascii=False)

    def propose(self, output: str, model: str):
        _CapturingProvider.render_responses = [output]
        return self.client.post("/api/perspective/comparison/candidates", json={"receipt_ids": self.receipt_ids, "model": model})

    def case_local(self, value):
        if isinstance(value, dict):
            return {key: self.case_local(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.case_local(item) for item in value]
        return self.labels.get(value, value) if isinstance(value, str) else value


def faithful_script(reference: dict, order: list[str]) -> dict:
    """The frozen reference annotation rendered in the wire format (a scripted reference echo)."""
    return {"propositions": [{"id": p["id"], "statement": p["statement"], "positions": [
                {"participant": key, "stance": p["positions"][key]["stance"], "quote": p["positions"][key]["quote"],
                 "relies_on": list(p["positions"][key]["cited"])} for key in order]} for p in reference["propositions"]],
            "assumptions": [{"participant": a["participant"], "quote": a["quote"]} for a in reference["assumptions"]]}


# ── Extraction score (evaluation only; contract §9) ──────────────────────────

def _interval(response: str, quote: str) -> tuple[int, int]:
    start = response.index(quote)
    return start, start + len(quote)


def _overlap(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def score(structure: dict, reference: dict, responses: dict, order: list[str]) -> dict:
    """Candidate structure (case-local labels) against the frozen reference annotation."""
    def ref_span(p, key):
        position = p["positions"][key]
        return _interval(responses[key], position["quote"]) if position["stance"] in SPAN_STANCES and position["quote"] else None

    def cand_span(p, key):
        position = next(x for x in p["positions"] if x["participant"] == key)
        return (position["span"]["start"], position["span"]["end"]) if position["span"] else None

    matched, used = {}, set()
    for rp in reference["propositions"]:
        for cp in structure["propositions"]:
            if cp["id"] in used:
                continue
            if any(ref_span(rp, k) and cand_span(cp, k) and _overlap(ref_span(rp, k), cand_span(cp, k)) for k in order):
                matched[rp["id"]] = cp
                used.add(cp["id"])
                break
    cand_to_ref = {cp["id"]: rid for rid, cp in matched.items()}

    def tpfp(candidate: set, expected: set) -> dict:
        return {"tp": len(candidate & expected), "fp": len(candidate - expected), "fn": len(expected - candidate)}

    agree = total = 0
    reliance = {"tp": 0, "fp": 0, "fn": 0}
    for rp in reference["propositions"]:
        cp = matched.get(rp["id"])
        if cp is None:
            continue
        for key in order:
            position = next(x for x in cp["positions"] if x["participant"] == key)
            total += 1
            agree += position["stance"] == rp["positions"][key]["stance"]
            for name, value in tpfp({r["key"]["id"] for r in position["reliance"]}, set(rp["positions"][key]["cited"])).items():
                reliance[name] += value
    ref_assumptions = [(a["participant"], _interval(responses[a["participant"]], a["quote"])) for a in reference["assumptions"]]
    cand_assumptions = [(a["participant"], (a["span"]["start"], a["span"]["end"])) for a in structure["assumptions"]]
    hits, remaining = 0, list(ref_assumptions)
    for participant, span in cand_assumptions:
        hit = next((r for r in remaining if r[0] == participant and _overlap(r[1], span)), None)
        if hit is not None:
            remaining.remove(hit)
            hits += 1
    relations = structure["relations"]
    cand_agreement = {(cand_to_ref.get(a["proposition"], "cand:" + a["proposition"]), a["stance"], frozenset(a["participants"]))
                      for a in relations["agreement"]}
    ref_agreement = {(a["proposition"], a["stance"], frozenset(a["participants"])) for a in reference["agreement"]}
    cand_disagreement = {(cand_to_ref.get(d["proposition"], "cand:" + d["proposition"]),
                          frozenset(d["groups"][0]["participants"]), frozenset(d["groups"][1]["participants"]))
                         for d in relations["disagreement"]}
    ref_disagreement = {(d["proposition"], frozenset(d["groups"][0]["participants"]), frozenset(d["groups"][1]["participants"]))
                        for d in reference["disagreement"]}
    minority = True
    for d in reference["disagreement"]:
        if not d["smaller_groups"]:
            continue
        cp = matched.get(d["proposition"])
        found = next((x for x in relations["disagreement"] if cp is not None and x["proposition"] == cp["id"]), None)
        minority = minority and found is not None and set(d["smaller_groups"]) <= set(found["minority_participants"])
    unknown = True
    for u in reference["unclassifiable"]:
        cp = matched.get(u["proposition"])
        position = next((x for x in cp["positions"] if x["participant"] == u["participant"]), None) if cp else None
        unknown = unknown and position is not None and position["stance"] in ("unclassifiable", "unknown")
    return {"propositions": {"matched": len(matched), "reference": len(reference["propositions"]),
                             "candidate": len(structure["propositions"])},
            "stance": {"agree": agree, "total": total}, "reliance": reliance,
            "assumptions": {"tp": hits, "fp": len(cand_assumptions) - hits, "fn": len(remaining)},
            "agreement": tpfp(cand_agreement, ref_agreement), "disagreement": tpfp(cand_disagreement, ref_disagreement),
            "minority_preserved": minority, "unknown_preserved": unknown,
            "untraceable": dict(sorted(Counter(item["kind"] for item in structure["untraceable"]).items()))}


def perfect(score_: dict) -> bool:
    return (score_["propositions"]["matched"] == score_["propositions"]["reference"] == score_["propositions"]["candidate"]
            and score_["stance"]["agree"] == score_["stance"]["total"]
            and all(score_[k]["fp"] == score_[k]["fn"] == 0 for k in ("reliance", "assumptions", "agreement", "disagreement"))
            and score_["minority_preserved"] and score_["unknown_preserved"] and not score_["untraceable"])


def _relations_as_reference(structure: dict, reference: dict, matched_ids: dict) -> bool:
    """A faithful candidate's derived relations must equal the frozen reference relations."""
    relations = structure["relations"]
    agreement = [{"proposition": matched_ids[a["proposition"]], "stance": a["stance"], "participants": a["participants"],
                  "evidence_relation": a["reliance"]} for a in relations["agreement"] if not a["not_established_for"]]
    disagreement = [{"proposition": matched_ids[d["proposition"]], "groups": d["groups"], "smaller_groups": d["minority_participants"],
                     "evidence_relation": d["reliance"]} for d in relations["disagreement"] if not d["not_established_for"]]
    unclassifiable = [{"proposition": matched_ids[u["proposition"]], "participant": u["participant"]}
                      for u in relations["unknown_positions"] if u["stance"] == "unclassifiable"]
    return (agreement == reference["agreement"] and disagreement == reference["disagreement"]
            and [matched_ids[p] for p in relations["unresolved"]] == reference["unresolved"]
            and unclassifiable == reference["unclassifiable"]
            and len(agreement) == len(relations["agreement"]) and len(disagreement) == len(relations["disagreement"])
            and all(u["stance"] == "unclassifiable" for u in relations["unknown_positions"]))


def _no_authority(value) -> bool:
    if isinstance(value, dict):
        return all(key not in AUTHORITY_KEYS and _no_authority(item) for key, item in value.items())
    if isinstance(value, list):
        return all(_no_authority(item) for item in value)
    return True


def _governance_view(local: dict) -> dict:
    relations = local["relations"]
    return {"stances": {p["id"]: {x["participant"]: x["stance"] for x in p["positions"]} for p in local["propositions"]},
            "assumptions": [a["participant"] for a in local["assumptions"]],
            "untraceable": dict(Counter(item["kind"] for item in local["untraceable"])),
            "relations": {"agreement": [{k: a[k] for k in ("proposition", "stance", "participants", "not_established_for", "reliance")}
                                        for a in relations["agreement"]],
                          "disagreement": [{k: d[k] for k in ("proposition", "groups", "minority_participants",
                                                               "not_established_for", "reliance")}
                                           for d in relations["disagreement"]]}}


# ── Runs ─────────────────────────────────────────────────────────────────────

def _isolated(workdir: Path, corpus: dict, layer1_corpus: dict):
    context = lab.isolated(workdir)
    context.__enter__()
    _FakeOllamaClient.models = list(layer1_corpus["models"]) + [corpus["extraction_model"]]
    return context


def run_faithful(corpus, layer1_corpus, cases, case_id, workdir) -> dict:
    case = cases[case_id]
    study = Study(layer1_corpus, case, workdir / "a")
    before = lab._logical_digest(study.db)
    order = case["expected"]["order"]
    script = faithful_script(case["reference"], order)
    response = study.propose(study.wire(script), corpus["extraction_model"])
    candidate = response.get_json()
    local = study.case_local(candidate["structure"])
    scored = score(local, case["reference"], study.responses, order)
    matched_ids = {p["id"]: ref["id"] for p, ref in zip(local["propositions"], case["reference"]["propositions"])}
    again = study.propose(study.wire(script), corpus["extraction_model"]).get_json()
    layer1 = study.layer1()
    checks = {
        "candidate_created": response.status_code == 201 and candidate.get("canonical_status") == "not_persisted",
        "provenance_bound": ([b["receipt_id"] for b in candidate["binding"]["receipts"]] == [p["receipt_id"] for p in layer1["participants"]]
                             and candidate["binding"]["layer1"]["digest"] == layer1_digest(layer1)
                             and candidate["binding"]["question"]["text"] == layer1["question"]["text"]
                             and candidate["extraction"]["prompt_version"] == "perspective-comparison-extraction/v1"
                             and candidate["extraction"]["prompt_sha256"] == text_digest(candidate["extraction"]["prompt"])
                             and candidate["extraction"]["output_sha256"] == text_digest(candidate["extraction"]["output"])
                             and candidate["extraction"]["execution"]["model_id"] == corpus["extraction_model"]),
        "nothing_untraceable": candidate["structure"]["untraceable"] == [],
        "relations_reproduce_reference": _relations_as_reference(local, case["reference"], matched_ids),
        "extraction_score_perfect": perfect(scored),
        "no_authority_fields": _no_authority(candidate),
        "deterministic_given_output": (again["structure"] == candidate["structure"] and again["binding"] == candidate["binding"]
                                       and again["extraction"]["prompt"] == candidate["extraction"]["prompt"]),
        "generation_writes_nothing": lab._logical_digest(study.db) == before,
    }
    return {"case_id": case_id, "kind": "faithful", "checks": checks, "score": scored,
            "relations": {k: len(local["relations"][k]) for k in ("agreement", "disagreement", "unresolved", "unknown_positions")},
            "minorities": [d["minority_participants"] for d in local["relations"]["disagreement"] if d["minority_participants"]]}


def run_layer1_refusal(corpus, layer1_corpus, cases, spec, workdir) -> dict:
    study = Study(layer1_corpus, cases[spec["base_case"]], workdir / "a")
    calls = len(_CapturingProvider.render_prompts)
    response = study.propose('{"propositions": [], "assumptions": []}', corpus["extraction_model"])
    return {"case_id": spec["base_case"], "kind": "layer1_refusal",
            "checks": {"refused_as_layer1": response.status_code in (400, 409) and response.get_json()["code"] == spec["code"],
                       "no_model_call": len(_CapturingProvider.render_prompts) == calls},
            "code": response.get_json()["code"]}


def run_adversarial(corpus, layer1_corpus, cases, adv, workdir) -> dict:
    case = cases[adv["base_case"]]
    study = Study(layer1_corpus, case, workdir / "a")
    before = lab._logical_digest(study.db)
    response = study.propose(study.wire(adv["script"]), corpus["extraction_model"])
    body = response.get_json()
    expected = adv["governance"]
    record = {"case_id": adv["case_id"], "kind": "adversarial", "temptation": adv["temptation"], "base_case": adv["base_case"]}
    if expected["outcome"] == "refused":
        record["checks"] = {"refused_as_frozen": response.status_code == 422 and body["code"] == expected["code"]
                            and body["canonical_status"] == "not_persisted",
                            "generation_writes_nothing": lab._logical_digest(study.db) == before}
        record["outcome"] = {"refused": body.get("code")}
        return record
    local = study.case_local(body["structure"])
    view = _governance_view(local)
    scored = score(local, case["reference"], study.responses, case["expected"]["order"])
    record["checks"] = {
        "candidate_created": response.status_code == 201,
        "governance_as_frozen": view == {k: expected[k] for k in ("stances", "assumptions", "untraceable", "relations")},
        "score_as_frozen": scored == adv["score"],
        "no_authority_fields": _no_authority(body),
        "generation_writes_nothing": lab._logical_digest(study.db) == before,
    }
    record["outcome"] = {"untraceable": view["untraceable"], "score": scored}
    return record


def _edit(study: Study, reference: dict, kind: str) -> dict:
    keys = {label: identifier for identifier, label in study.labels.items()}
    order = study.case["expected"]["order"]

    def span(key, quote):
        start = study.responses[key].index(quote)
        return {"start": start, "end": start + len(quote), "text": quote}

    def ref(label):
        return {"table": "source_extractions" if ":" in label else "reader_highlights", "key": {"id": keys[label]}}

    propositions = []
    for index, p in enumerate(reference["propositions"], 1):
        positions = []
        for key in order:
            pos = p["positions"][key]
            positions.append({"participant": keys[key], "stance": pos["stance"],
                              "span": span(key, pos["quote"]) if pos["quote"] else None,
                              "reliance": [ref(label) for label in pos["cited"]]})
        propositions.append({"id": f"p{index}", "statement": p["statement"], "positions": positions})
    edit = {"participants": [keys[key] for key in order], "propositions": propositions,
            "assumptions": [{"id": f"a{index}", "participant": keys[a["participant"]], "span": span(a["participant"], a["quote"])}
                            for index, a in enumerate(reference["assumptions"], 1)]}
    if kind == "untraceable":
        edit["propositions"][0]["positions"][0]["span"]["text"] += " (paraphrased)"
    elif kind == "authority_field":
        edit["propositions"][0]["positions"][0]["truth"] = True
    return edit


def _records(db: Path) -> list[tuple]:
    conn = lab._read_only(db)
    try:
        return [tuple(row) for row in conn.execute("SELECT id, candidate_id, comparison_json FROM accepted_perspective_comparisons ORDER BY id")]
    finally:
        conn.close()


def _verify(db: Path, identifier: str) -> dict:
    conn = lab._read_only(db)
    try:
        return verify_accepted_comparison(conn, identifier)
    finally:
        conn.close()


def run_acceptance(corpus, layer1_corpus, cases, scenario, workdir) -> dict:
    case = cases[scenario["base_case"]]
    study = Study(layer1_corpus, case, workdir / "a")
    for op in scenario.get("before", []):
        lab._ok(study.client.put("/api/investigation", json={"thesis": op["text"]}))
    if scenario["script"] == "faithful":
        script = faithful_script(case["reference"], case["expected"]["order"])
    else:
        script = next(a for a in corpus["adversarial"] if a["case_id"] == scenario["script"])["script"]
    candidate = study.propose(study.wire(script), corpus["extraction_model"]).get_json()
    cid = candidate["candidate_id"]
    observed: dict = {"governing_question_status": candidate["binding"]["governing_question"]["status"]}
    accepted = None
    for step in scenario["steps"]:
        op = step["op"]
        if op in ("accept", "edit_and_accept"):
            body = {"decision": op, "candidate_id": step.get("body_candidate_id", cid)}
            if op == "edit_and_accept":
                body["structure"] = _edit(study, case["reference"], step["structure"])
            response = study.client.post(f"/api/perspective/comparison/candidates/{cid}/accept", json=body)
            entry = {"status": response.status_code}
            if response.status_code >= 400:
                entry["code"] = response.get_json()["code"]
            elif step.get("repeat"):
                entry["same_record"] = response.get_json()["id"] == accepted["id"]
            else:
                accepted = response.get_json()
            observed["repeat" if step.get("repeat") else "accept"] = entry
        elif op == "discard":
            response = study.client.post(f"/api/perspective/comparison/candidates/{cid}/discard", json={"decision": "discard", "candidate_id": cid})
            observed["discard"] = {"status": response.status_code}
        elif op == "set_governing_question":
            lab._ok(study.client.put("/api/investigation", json={"thesis": step["text"]}))
        elif op == "exclude_document":
            doc = next(identifier for identifier, label in study.labels.items() if label == step["doc"])
            lab._ok(study.client.patch(f"/api/documents/{doc}/scope", json={"source_role": "reference"}))
            lab._ok(study.client.patch(f"/api/documents/{doc}/scope", json={"excluded": True}))
        elif op == "verify":
            observed["verify"] = _verify(study.db, accepted["id"])
        elif op == "export_restore_verify":
            bundle, target = workdir / "bundle", workdir / "restored" / "workspace.db"
            target.parent.mkdir()
            export_workspace_bundle(study.db, bundle, generated_at=EXPORT_TIME, workspace_id="synthetic-p7")
            restore_workspace(target, bundle)
            observed["restored_bytes_identical"] = _records(target) == _records(study.db)
            observed["restored_verify"] = _verify(target, accepted["id"])
    observed["records"] = len(_records(study.db))
    if accepted is not None:
        conn = lab._read_only(study.db)
        try:
            items = [i for i in layer1_lab.project_study_lineage(conn)["items"]
                     if i["record"]["table"] == "accepted_perspective_comparisons"]
        finally:
            conn.close()
        observed["lineage_visible"] = bool(items)
        if items:
            observed["lineage_authorship"] = items[0]["authorship"]
        observed["get_status"] = study.client.get(f"/api/perspective/comparison/accepted/{accepted['id']}").status_code
        observed["accepted_equals_candidate"] = accepted["structure"] == candidate["structure"]
        observed["candidate_relations"] = {k: len(accepted["candidate"]["structure"]["relations"][k]) for k in ("agreement", "disagreement")}
        observed["accepted_relations"] = {k: len(accepted["structure"]["relations"][k]) for k in ("agreement", "disagreement")}
        observed["meaning"] = accepted["acceptance"]["meaning"]
        observed["no_authority_fields"] = _no_authority(accepted)
    expected = scenario["expected"]
    checks = {f"expected_{key}": observed.get(key) == value for key, value in expected.items()}
    if "restored_bytes_identical" in expected:
        checks["restored_verify_equals_source"] = observed.get("restored_verify") == observed.get("verify")
    if accepted is not None:
        checks["no_authority_fields"] = observed["no_authority_fields"]
    return {"scenario_id": scenario["scenario_id"], "kind": "acceptance", "checks": checks,
            "observed": {k: v for k, v in observed.items() if k != "meaning"}}


def run() -> dict:
    corpus, cases = load()
    layer1_corpus = layer1_lab.load_corpus(ROOT / corpus["layer1_corpus"])
    jobs = ([("faithful", case_id) for case_id in corpus["faithful"]["cases"]]
            + [("layer1_refusal", spec) for spec in corpus["layer1_refusals"]]
            + [("adversarial", adv) for adv in corpus["adversarial"]]
            + [("acceptance", scenario) for scenario in corpus["acceptance"]])
    runners = {"faithful": run_faithful, "layer1_refusal": run_layer1_refusal,
               "adversarial": run_adversarial, "acceptance": run_acceptance}
    records = []
    for kind, item in jobs:
        with tempfile.TemporaryDirectory(prefix="p7-layer2-") as tmp:
            workdir = Path(tmp)
            context = _isolated(workdir, corpus, layer1_corpus)
            try:
                records.append(runners[kind](corpus, layer1_corpus, cases, item, workdir))
            finally:
                context.__exit__(None, None, None)
    aggregate = {}
    for kind in runners:
        group = [r for r in records if r["kind"] == kind]
        aggregate[kind] = {"items": len(group), "all_checks_passed": sum(all(r["checks"].values()) for r in group)}
    outcomes = {}
    for r in (r for r in records if r["kind"] == "adversarial"):
        refused = "refused" in r["outcome"]
        outcomes[r["case_id"]] = {
            "governance": "refused" if refused else "downgraded_to_unknown" if r["outcome"]["untraceable"] else "admitted",
            "score_deviates_from_reference": not refused and not perfect(r["outcome"]["score"])}
    aggregate["adversarial_outcomes"] = outcomes
    # Traceable but wrong: governance cannot see it; only scoring and the steward can.
    aggregate["adversarial_visible_only_in_score"] = sorted(
        case_id for case_id, o in outcomes.items() if o["governance"] == "admitted" and o["score_deviates_from_reference"])
    return {"schema": RESULT_SCHEMA, "policy_version": "1.0.0", "corpus": CORPUS_SCHEMA,
            "method": ("disposable synthetic workspaces through production write boundaries; the semantic model is an "
                       "in-process fake returning scripted text (no network, no real model); scripted output measures the "
                       "governed pipeline, not extraction quality"),
            "aggregate": aggregate, "records": records}


def summary_markdown(results: dict) -> str:
    lines = ["# P7 Layer 2 governed comparison candidates — evaluation summary", "",
             "Generated by `tests/perspective_comparison_candidate_lab.py`. The semantic model is an in-process fake "
             "returning scripted text: these results measure the governed pipeline, **not** a model's extraction "
             "quality. Evaluation data, not study history.", "",
             "## Extraction (scored against the frozen references, separately from acceptance)", "",
             "| Item | Kind | Outcome | Checks |", "| --- | --- | --- | --- |"]
    for r in results["records"]:
        if r["kind"] == "acceptance":
            continue
        passed = f"{sum(1 for v in r['checks'].values() if v)}/{len(r['checks'])}"
        if r["kind"] == "faithful":
            rel = r["relations"]
            minority = f"; minority {', '.join(m for group in r['minorities'] for m in group)}" if r["minorities"] else ""
            outcome = (f"candidate reproduces the reference: {rel['agreement']} agreement, {rel['disagreement']} disagreement, "
                       f"{rel['unknown_positions']} unknown{minority}; score perfect")
        elif r["kind"] == "layer1_refusal":
            outcome = f"refused `{r['code']}` before any model call"
        elif "refused" in r["outcome"]:
            outcome = f"{r['temptation']}: output refused `{r['outcome']['refused']}`; no candidate"
        else:
            s = r["outcome"]["score"]
            caught = ", ".join(f"{k} ×{v}" for k, v in r["outcome"]["untraceable"].items()) or "nothing untraceable"
            outcome = (f"{r['temptation']}: governance caught {caught}; score agreement fp {s['agreement']['fp']}/fn "
                       f"{s['agreement']['fn']}, disagreement fp {s['disagreement']['fp']}/fn {s['disagreement']['fn']}, "
                       f"reliance fp {s['reliance']['fp']}, assumptions fp {s['assumptions']['fp']}, "
                       f"minority preserved {s['minority_preserved']}")
        lines.append(f"| {r['case_id']} | {r['kind']} | {outcome} | {passed} |")
    lines += ["", "## Steward acceptance", "", "| Scenario | Observed | Checks |", "| --- | --- | --- |"]
    for r in results["records"]:
        if r["kind"] != "acceptance":
            continue
        o = r["observed"]
        parts = [f"accept {o['accept']['status']}" + (f" `{o['accept']['code']}`" if "code" in o.get("accept", {}) else "")] if "accept" in o else []
        if "discard" in o:
            parts.insert(0, f"discard {o['discard']['status']}")
        if "repeat" in o:
            parts.append(f"repeat {o['repeat']['status']} (same record {o['repeat'].get('same_record')})")
        parts.append(f"records {o['records']}")
        if "lineage_authorship" in o:
            parts.append(f"Lineage `{o['lineage_authorship']}`")
        if o.get("lineage_visible") is False:
            parts.append("Lineage omits it; GET 404")
        if "verify" in o:
            parts.append("verify " + ", ".join(f"{k}={v}" for k, v in o["verify"].items() if k != "model_output"))
        if "restored_bytes_identical" in o:
            parts.append(f"export/restore bytes identical {o['restored_bytes_identical']}")
        passed = f"{sum(1 for v in r['checks'].values() if v)}/{len(r['checks'])}"
        lines.append(f"| {r['scenario_id']} | {'; '.join(parts)} | {passed} |")
    lines += ["", "## Aggregate", ""]
    for key, value in results["aggregate"].items():
        if key == "adversarial_outcomes":
            lines.append("- `adversarial_outcomes` (governance / score deviates from reference):")
            lines += [f"  - {case_id}: {o['governance']} / {o['score_deviates_from_reference']}" for case_id, o in value.items()]
        else:
            lines.append(f"- `{key}`: {value}")
    return "\n".join(lines) + "\n"


def write(results: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (out / "summary.md").write_text(summary_markdown(json.loads(json.dumps(results, sort_keys=True))))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    results = json.loads(json.dumps(run(), sort_keys=True, ensure_ascii=False))
    if args.write:
        write(results, args.write)
        print(f"wrote {args.write}")
        return 0
    if json.loads((args.check / "results.json").read_text()) != results or (args.check / "summary.md").read_text() != summary_markdown(results):
        print("results differ from committed dataset")
        return 1
    print("results match committed dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
