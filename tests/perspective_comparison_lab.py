"""P7 Structured Perspective Comparison laboratory (#215): frozen corpus → production comparator.

Each case in tests/fixtures/perspective_comparison/v1/cases.json is
materialized in a disposable synthetic workspace through production write
boundaries: upload, Reader highlight, saved Perspective, Perspective run with
explicit retain or discard, highlight edit, and document exclusion. In-process
fake adapters control each response and model ID; outbound network is blocked.
The production P4 evidence adapter decides eligibility and the production
comparator compares. This module only checks the outcome against the frozen
expectations, validates each reference claim annotation against the populated
semantic form, and records evaluation data. It is not study history.

    python tests/perspective_comparison_lab.py --write research/perspective_comparison/v1
    python tests/perspective_comparison_lab.py --check research/perspective_comparison/v1
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import io
from itertools import combinations, permutations
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
from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence  # noqa: E402
from hermeneia.perspective_comparison import (  # noqa: E402
    POLICY_VERSION, SCHEMA, SEMANTIC_NOT_ESTABLISHED, UNCERTAINTY, ComparisonRefused, compare_retained_perspectives,
)
from hermeneia.storage.sqlite import SQLiteStore  # noqa: E402
from hermeneia.study_lineage import project_study_lineage  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from test_e10_vertical_slice_api import _CapturingProvider, _FakeOllamaClient  # noqa: E402

FIXTURES = TESTS / "fixtures" / "perspective_comparison" / "v1"
CASES_SCHEMA = "hermeneia.perspective-comparison-cases/v1"
RESULT_SCHEMA = "hermeneia.perspective-comparison-lab-results/v1"
STANCES = ("asserts", "denies", "does_not_address", "unclassifiable")
FORBIDDEN_KEYS = {"truth", "true", "correct", "correctness", "best", "winner", "majority", "consensus", "synthesis",
                  "answer", "adjudication", "verdict", "agreement", "disagreement", "claims", "propositions",
                  "assumptions", "unresolved", "score", "similarity"}
REFUSALS = {"DUPLICATE_PARTICIPANT", "TOO_FEW_PARTICIPANTS", "TOO_MANY_PARTICIPANTS", "COVERAGE_UNSUPPORTED",
            "INELIGIBLE_RECEIPT", "QUESTION_MISMATCH"}


class CaseError(ValueError):
    """A fixture violates the corpus contract or cannot be materialized lawfully."""


# ── Corpus ───────────────────────────────────────────────────────────────────

def load_corpus(path: Path = FIXTURES / "cases.json") -> dict:
    corpus = json.loads(path.read_text())
    if corpus.get("schema") != CASES_SCHEMA or corpus.get("policy_version") != POLICY_VERSION:
        raise CaseError("corpus schema or policy version differs from production; re-freeze deliberately")
    for case in corpus["cases"]:
        fields = {"case_id", "controls", "setup", "steps", "compare", "expected", "reference", "probes", "variants"}
        if set(case) != fields:
            raise CaseError(f"{case.get('case_id')}: exact case fields required")
        keys = [s["key"] for s in case["steps"] if s["op"] == "run"]
        if len(set(keys)) != len(keys) or not set(case["compare"]) <= set(keys):
            raise CaseError(f"{case['case_id']}: run keys must be unique and compared keys must exist")
        if "refusal" in case["expected"]:
            if case["expected"]["refusal"] not in REFUSALS or case["reference"] is not None:
                raise CaseError(f"{case['case_id']}: refusal cases carry a known code and no reference")
        if any(probe["refusal"] not in REFUSALS for probe in case["probes"]):
            raise CaseError(f"{case['case_id']}: unknown probe refusal")
    return corpus


# ── Materialization (production write boundaries only) ───────────────────────

def _scope(extractions: list[dict], doc_id: str, focus: list[int], *, page: bool, highlight_ids: list[str]) -> dict:
    first, last = extractions[focus[0] - 1], extractions[focus[1] - 1]
    span = extractions[focus[0] - 1:focus[1]]
    locators, ids = [e["source_locator"] for e in span], [e["id"] for e in span]
    block = lambda e: int(e["source_locator"].rsplit(":", 1)[1])  # noqa: E731
    scope = {"primary": {"kind": "reader_selection", "text": "\n\n".join(e["raw_text"].strip() for e in span),
                         "source_document_id": doc_id, "page": first["page"],
                         "locator": lab._scope_span_locator(page=first["page"], start_block=block(first), end_block=block(last),
                                                            end_offset=len(last["raw_text"].strip()), locators=locators,
                                                            extraction_ids=ids),
                         "source_locators": locators, "extraction_ids": ids},
             "supporting": {}}
    if page:
        scope["supporting"]["current_page"] = {"include": True}
    if highlight_ids:
        scope["supporting"]["highlights"] = {"include": True, "ids": highlight_ids}
    return scope


def materialize(corpus: dict, case: dict, workdir: Path, modify: dict | None = None) -> dict:
    """Build one disposable workspace. Returns its path and the case-local label maps."""
    modify = modify or {}
    db = workdir / "ws" / "workspace.db"
    SQLiteStore(db).close()
    base = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
    runner = create_app(db_path=db, provider_registry=lab._ollama_registry(), credential_store=lab._NoCredentials()).test_client()
    docs, extractions, highlights, saved = {}, {}, {}, {}
    labels: dict[str, str] = {}
    for key in case["setup"]["documents"]:
        lines = corpus["documents"][key]
        body = lab._ok(base.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(lines)), f"synthetic-{key}.pdf")},
                                 content_type="multipart/form-data"))
        docs[key] = body["document_id"]
        labels[body["document_id"]] = key
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT e.id, e.page, e.raw_text, e.source_locator, o.id AS observation_id FROM observations o "
            "JOIN source_extractions e ON e.id = o.source_extraction_id WHERE o.source_document_id = ? "
            "ORDER BY o.page, o.paragraph, o.sentence", (body["document_id"],))]
        conn.close()
        if len(rows) != len(lines):
            raise CaseError(f"expected one extraction per line for {key}, got {len(rows)}")
        extractions[key] = rows
        labels.update({row["id"]: f"{key}:{index}" for index, row in enumerate(rows, 1)})
    for key, spec in case["setup"]["highlights"].items():
        row = extractions[spec["doc"]][spec["sentence"] - 1]
        body = lab._ok(base.post("/api/reader/highlights", json={
            "source_document_id": docs[spec["doc"]], "selected_text": row["raw_text"].strip(), "page": row["page"],
            "observation_id": row["observation_id"]}))
        highlights[key] = body["id"]
        labels[body["id"]] = key
    for key, spec in case["setup"]["saved_perspectives"].items():
        body = lab._ok(base.post("/api/perspective/saved", json={"perspective_draft": spec, "declared_by": "Synthetic lab steward"}))
        saved[key] = body["id"]
        labels[body["id"]] = key
    receipts, runs = {}, {}
    for step in case["steps"]:
        if step["op"] == "run":
            step = {**step, **modify.get(step["key"], {})}
            frame = step["perspective"]
            selection = ({"perspective_id": None, "saved_perspective_id": saved[frame["saved"]]}
                         if isinstance(frame, dict) else {"perspective_id": frame})
            scope = _scope(extractions[step["doc"]], docs[step["doc"]], step["focus"], page=step["current_page"],
                           highlight_ids=[highlights[h] for h in step["highlights"]])
            _CapturingProvider.render_responses = [step["response"]]
            run = lab._ok(runner.post("/api/perspective/run", json={
                "question": step.get("question", corpus["question"]), "model": step["model"], "scope": scope, **selection}))
            runs[step["key"]] = run["run_id"]
            if step["decision"] == "retain":
                receipt = lab._ok(runner.post(f"/api/perspective/executions/{run['run_id']}/retain", json={"decision": "retain"}))
                receipts[step["key"]] = receipt["id"]
                labels[receipt["id"]] = step["key"]
            else:
                lab._ok(runner.post(f"/api/perspective/executions/{run['run_id']}/discard", json={"decision": "discard"}))
        elif step["op"] == "patch_highlight":
            lab._ok(base.patch(f"/api/reader/highlights/{highlights[step['highlight']]}", json={"relevance": step["relevance"]}))
        elif step["op"] == "exclude_document":
            lab._ok(base.patch(f"/api/documents/{docs[step['doc']]}/scope", json={"source_role": "reference"}))
            lab._ok(base.patch(f"/api/documents/{docs[step['doc']]}/scope", json={"excluded": True}))
        elif step["op"] == "drop_receipts_table":
            conn = sqlite3.connect(db)
            conn.execute('DROP TABLE "perspective_execution_receipts"')
            conn.commit()
            conn.close()
        else:
            raise CaseError(f"unknown step {step['op']}")
    # A discarded run has no receipt; a probe naming it can only supply its transient run ID.
    ids = {**{key: run_id for key, run_id in runs.items() if key not in receipts}, **receipts}
    return {"db": db, "ids": ids, "labels": labels}


def production_compare(db: Path, receipt_ids: list[str]):
    """The only decision-maker: P4's read-only adapter and the production comparator."""
    conn = lab._read_only(db)
    try:
        evidence = read_perspective_achievement_evidence(conn)
    finally:
        conn.close()
    try:
        return compare_retained_perspectives(evidence, receipt_ids)
    except ComparisonRefused as refusal:
        return {"refusal": refusal.code}


# ── Contract checks ──────────────────────────────────────────────────────────

def _is_digest(value) -> bool:
    return isinstance(value, str) and value.startswith("sha256:") and len(value) == 71


def validate_result(result: dict) -> list[str]:
    """Structural check of hermeneia.perspective-comparison/v1 (mirrors comparison.schema.json)."""
    problems = []
    fields = {"schema", "policy_version", "comparison_id", "inputs", "coverage", "question", "participants", "evidence",
              "relations", "semantic", "uncertainty", "not_synthesis"}
    if set(result) != fields:
        return [f"fields {sorted(set(result) ^ fields)}"]
    if result["schema"] != SCHEMA or result["policy_version"] != POLICY_VERSION:
        problems.append("schema/policy")
    if not result["comparison_id"].startswith("perspective-comparison:sha256:"):
        problems.append("comparison_id")
    if result["question"]["binding"] != "exact_execution_question" or result["question"]["governing_question"] != "not_bound":
        problems.append("question binding")
    participant_fields = {"receipt_id", "run_id", "lineage_record", "authorship", "retention", "executed", "perspective",
                          "execution", "digests", "response", "evidence_supplied"}
    for p in result["participants"]:
        if set(p) != participant_fields or p["authorship"] != "model" or p["retention"]["decision"] != "retain":
            problems.append("participant fields")
        if not all(_is_digest(v) for v in p["digests"].values()) or not _is_digest(p["perspective"]["methodology_sha256"]):
            problems.append("participant digests")
        if p["perspective"]["family"]["state"] not in ("supported", "unsupported", "invalid"):
            problems.append("family state")
    n = len(result["participants"])
    if not 2 <= n <= 8 or len(result["relations"]) != n * (n - 1) // 2:
        problems.append("participant/relation count")
    vocab = {"perspective": {"same_family", "distinct_family_distinct_methodology", "distinct_family_same_methodology",
                             "family_unsupported"},
             "execution": {"same_provider_model", "different_provider_model"}, "response_text": {"identical", "different"},
             "evidence_units": {"identical", "overlapping", "disjoint"}, "evidence_focus": {"identical", "overlapping", "disjoint"}}
    for r in result["relations"]:
        if any(r[k] not in v for k, v in vocab.items()) or not isinstance(r["same_source_document"], bool):
            problems.append("relation vocabulary")
    ev = result["evidence"]
    if set(ev) != {"basis", "statement", "units", "shared_by_all", "supplied_only_to", "overall"} or ev["basis"] != "supplied_scope":
        problems.append("evidence fields")
    for unit in ev["units"]:
        if unit["ref"]["table"] not in ("source_extractions", "reader_highlights") or not unit["supplied_to"]:
            problems.append("unit")
    if result["semantic"] != SEMANTIC_NOT_ESTABLISHED and result["semantic"].get("status") != "proposed_unaccepted":
        problems.append("semantic")
    codes = [u["code"] for u in result["uncertainty"]]
    if any(c not in UNCERTAINTY for c in codes) or codes != [c for c in UNCERTAINTY if c in codes]:
        problems.append("uncertainty codes/order")
    return problems


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def _relation(sets: list[set]) -> str:
    if any(not s for s in sets):
        return "some_uncited"
    if all(s == sets[0] for s in sets):
        return "identical"
    if all(not (a & b) for a, b in combinations(sets, 2)):
        return "disjoint"
    return "overlapping"


def derive(reference: dict, order: list[str]) -> dict:
    """The contract's populated-form rules, applied to case-local positions."""
    agreement, disagreement, unclassifiable = [], [], []
    for p in reference["propositions"]:
        positions = p["positions"]
        by = {s: [k for k in order if positions[k]["stance"] == s] for s in STANCES}
        cited = lambda keys: [set(positions[k]["cited"]) for k in keys]  # noqa: E731
        if by["asserts"] and by["denies"]:
            groups = [{"stance": s, "participants": by[s]} for s in ("asserts", "denies")]
            largest = max(len(g["participants"]) for g in groups)
            disagreement.append({"proposition": p["id"], "groups": groups,
                                 "smaller_groups": [k for g in groups if len(g["participants"]) < largest for k in g["participants"]],
                                 "evidence_relation": _relation(cited(by["asserts"] + by["denies"]))})
        else:
            for stance in ("asserts", "denies"):
                if len(by[stance]) >= 2:
                    agreement.append({"proposition": p["id"], "stance": stance, "participants": by[stance],
                                      "evidence_relation": _relation(cited(by[stance]))})
        unclassifiable += [{"proposition": p["id"], "participant": k} for k in by["unclassifiable"]]
    return {"agreement": agreement, "disagreement": disagreement,
            "unresolved": [d["proposition"] for d in disagreement], "unclassifiable": unclassifiable}


def populate_reference(reference: dict, result: dict, labels: dict) -> tuple[dict, list[str]]:
    """Build the populated semantic form with real IDs and exact offsets; report every closure problem."""
    problems = []
    keys = {v: k for k, v in labels.items()}
    order = [labels[p["receipt_id"]] for p in result["participants"]]
    responses = {labels[p["receipt_id"]]: p["response"] for p in result["participants"]}
    supplied = {k: set() for k in order}
    for unit in result["evidence"]["units"]:
        for holder in unit["supplied_to"]:
            supplied[labels[holder["receipt_id"]]].add(labels[unit["ref"]["key"]["id"]])

    def quote(participant, text):
        if text is None:
            return None
        if responses[participant].count(text) != 1:
            problems.append(f"quote does not resolve exactly once in {participant}: {text!r}")
            return None
        start = responses[participant].index(text)
        return {"start": start, "end": start + len(text), "text": text}

    def ref(label):
        identifier = keys[label]
        return {"table": "reader_highlights" if ":" not in label else "source_extractions", "key": {"id": identifier}}

    propositions = []
    for p in reference["propositions"]:
        if set(p["positions"]) != set(order):
            problems.append(f"{p['id']}: one position per participant required")
        positions = []
        for k in order:
            position = p["positions"][k]
            if position["stance"] in ("asserts", "denies") and position["quote"] is None:
                problems.append(f"{p['id']}/{k}: asserts/denies require a quote")
            if position["stance"] == "does_not_address" and position["quote"] is not None:
                problems.append(f"{p['id']}/{k}: does_not_address has no quote")
            if not set(position["cited"]) <= supplied[k]:
                problems.append(f"{p['id']}/{k}: cited evidence outside supplied Scope")
            positions.append({"participant": keys[k], "stance": position["stance"], "quote": quote(k, position["quote"]),
                              "cited_evidence": [ref(label) for label in position["cited"]]})
        propositions.append({"id": p["id"], "statement": p["statement"], "positions": positions})
    derived = derive(reference, order)
    for name in ("agreement", "disagreement", "unresolved", "unclassifiable"):
        if derived[name] != reference[name]:
            problems.append(f"{name} listed differs from the contract derivation")
    ids = lambda group: [keys[k] for k in group]  # noqa: E731
    populated = {
        "status": "proposed_unaccepted",
        "origin": {"kind": "evaluation_reference", "author": reference["author"]},
        "acceptance": "none",
        "propositions": propositions,
        "agreement": [{**a, "participants": ids(a["participants"])} for a in reference["agreement"]],
        "disagreement": [{**d, "groups": [{**g, "participants": ids(g["participants"])} for g in d["groups"]],
                          "smaller_groups": ids(d["smaller_groups"]), "resolution": "none_recorded"}
                         for d in reference["disagreement"]],
        "assumptions": [{"id": a["id"], "participant": keys[a["participant"]], "quote": quote(a["participant"], a["quote"])}
                        for a in reference["assumptions"]],
        "unresolved": list(reference["unresolved"]),
        "unclassifiable": [{**u, "participant": keys[u["participant"]]} for u in reference["unclassifiable"]],
    }
    return populated, problems + validate_populated(populated, [p["receipt_id"] for p in result["participants"]])


def validate_populated(semantic: dict, receipt_ids: list[str]) -> list[str]:
    """Structural check of the schema's semantic_populated form."""
    problems = []
    if set(semantic) != {"status", "origin", "acceptance", "propositions", "agreement", "disagreement", "assumptions",
                         "unresolved", "unclassifiable"}:
        return ["populated fields"]
    if semantic["status"] != "proposed_unaccepted" or semantic["acceptance"] != "none" \
            or semantic["origin"]["kind"] != "evaluation_reference":
        problems.append("populated status/origin/acceptance")
    members = set(receipt_ids)
    for p in semantic["propositions"]:
        if [x["participant"] for x in p["positions"]] != receipt_ids or any(x["stance"] not in STANCES for x in p["positions"]):
            problems.append(f"{p['id']}: positions")
        for x in p["positions"]:
            if x["quote"] is not None and not (0 <= x["quote"]["start"] < x["quote"]["end"]):
                problems.append(f"{p['id']}: quote offsets")
    for d in semantic["disagreement"]:
        if d["resolution"] != "none_recorded" or len(d["groups"]) < 2 or not set(d["smaller_groups"]) <= members:
            problems.append(f"{d['proposition']}: disagreement form")
    if any(not set(a["participants"]) <= members or len(a["participants"]) < 2 for a in semantic["agreement"]):
        problems.append("agreement form")
    return problems


# ── Normalization to case-local labels ───────────────────────────────────────

def normalized(result: dict, labels: dict) -> dict:
    lab_ = lambda identifier: labels.get(identifier, identifier)  # noqa: E731
    participants = {}
    for p in result["participants"]:
        perspective = p["perspective"]
        participants[lab_(p["receipt_id"])] = {
            "origin": perspective["origin"], "perspective": lab_(perspective["id"]),
            "family": [perspective["family"]["key"][0], lab_(perspective["family"]["key"][1])] if perspective["family"]["key"] else None,
            "family_state": perspective["family"]["state"], "model_id": p["execution"]["model_id"],
            "focus": [lab_(i) for i in p["evidence_supplied"]["focus"]],
            "context": [lab_(i) for i in p["evidence_supplied"]["context"]],
            "highlights": [lab_(h["id"]) for h in p["evidence_supplied"]["highlights"]]}
    ev = result["evidence"]
    evidence = {"units": {lab_(u["ref"]["key"]["id"]): {lab_(h["receipt_id"]): h["roles"] for h in u["supplied_to"]} for u in ev["units"]},
                "snapshot_varies": sorted(lab_(u["ref"]["key"]["id"]) for u in ev["units"] if u["captured_snapshot_varies"]),
                "shared_by_all": sorted(lab_(r["key"]["id"]) for r in ev["shared_by_all"]),
                "only": {lab_(o["receipt_id"]): sorted(lab_(r["key"]["id"]) for r in o["refs"]) for o in ev["supplied_only_to"]},
                "overall": ev["overall"]}
    relations = [{"pair": [lab_(x) for x in r["participants"]], **{k: v for k, v in r.items() if k != "participants"}}
                 for r in result["relations"]]
    coverage = result["coverage"]
    return {"order": [lab_(p["receipt_id"]) for p in result["participants"]], "participants": participants,
            "evidence": evidence, "relations": relations, "uncertainty": [u["code"] for u in result["uncertainty"]],
            "coverage": {"extant_records": coverage.get("extant_records"), "eligible_records": coverage.get("eligible_records"),
                         "classified_records": coverage.get("classified_records")},
            "question": result["question"]["text"], "semantic": result["semantic"]}


def substantive(norm: dict) -> dict:
    """What model identity must not change: everything except execution provenance."""
    return {"order": norm["order"], "question": norm["question"], "evidence": norm["evidence"],
            "perspectives": {k: {f: v[f] for f in ("origin", "perspective", "family", "family_state")} for k, v in norm["participants"].items()},
            "relations": [{k: v for k, v in r.items() if k != "execution"} for r in norm["relations"]],
            "semantic": norm["semantic"], "uncertainty": norm["uncertainty"]}


def _expected_view(norm: dict) -> dict:
    return {k: norm[k] for k in ("order", "participants", "evidence", "relations", "uncertainty", "coverage")}


def _sorted_expected(expected: dict) -> dict:
    view = deepcopy(expected)
    view["evidence"]["shared_by_all"] = sorted(view["evidence"]["shared_by_all"])
    view["evidence"]["only"] = {k: sorted(v) for k, v in view["evidence"]["only"].items()}
    view["evidence"]["snapshot_varies"] = sorted(view["evidence"]["snapshot_varies"])
    return view


# ── Evaluation ───────────────────────────────────────────────────────────────

def _provenance_closed(db: Path, result: dict) -> bool:
    conn = lab._read_only(db)
    try:
        lineage = project_study_lineage(conn)
        typed = {(i["record"]["table"], i["record"]["key"]["id"]): i for i in lineage["items"]}
        for p in result["participants"]:
            item = typed.get(("perspective_execution_receipts", p["receipt_id"]))
            if item is None or item["record"] != p["lineage_record"] or item["authorship"] != "model":
                return False
            if p["digests"]["response_sha256"] != "sha256:" + hashlib.sha256(p["response"].encode("utf-8")).hexdigest():
                return False
            if p["digests"]["question_sha256"] != "sha256:" + hashlib.sha256(result["question"]["text"].encode("utf-8")).hexdigest():
                return False
        for unit in result["evidence"]["units"]:
            table, identifier = unit["ref"]["table"], unit["ref"]["key"]["id"]
            if conn.execute(f'SELECT 1 FROM "{table}" WHERE id = ?', (identifier,)).fetchone() is None:
                return False
        return True
    finally:
        conn.close()


def evaluate_case(corpus: dict, case: dict, workdir: Path) -> dict:
    built = materialize(corpus, case, workdir / "base")
    db, ids, labels = built["db"], built["ids"], built["labels"]
    before = lab._logical_digest(db)
    requested = [ids[k] for k in case["compare"]]
    result = production_compare(db, requested)
    record = {"case_id": case["case_id"], "controls": case["controls"], "checks": {}}
    checks = record["checks"]
    checks["probes_refused_as_frozen"] = all(
        production_compare(db, [ids[k] for k in probe["compare"]]) == {"refusal": probe["refusal"]} for probe in case["probes"])
    if "refusal" in case["expected"]:
        checks["refused_as_frozen"] = result == case["expected"]
        checks["workspace_unchanged"] = lab._logical_digest(db) == before
        record["comparison"] = result
        return record
    norm = normalized(result, labels)
    expected = _sorted_expected(case["expected"])
    view = _expected_view(norm)
    checks["schema_valid"] = not validate_result(result)
    checks["participant_attribution"] = (
        view["order"] == expected["order"] and view["participants"] == expected["participants"]
        and all(p["receipt_id"] == ids[labels[p["receipt_id"]]] for p in result["participants"])
        and all(p["response"] == next(s["response"] for s in case["steps"] if s.get("key") == labels[p["receipt_id"]])
                for p in result["participants"]))
    checks["evidence_overlap"] = view["evidence"] == expected["evidence"]
    checks["relations"] = view["relations"] == expected["relations"]
    checks["uncertainty"] = view["uncertainty"] == expected["uncertainty"]
    checks["coverage_preserved"] = view["coverage"] == expected["coverage"]
    checks["semantic_abstention"] = result["semantic"] == SEMANTIC_NOT_ESTABLISHED
    checks["no_consensus_truth_or_claim_fields"] = not (set(_keys(result)) & FORBIDDEN_KEYS)
    checks["minority_preserved"] = sorted(p["receipt_id"] for p in result["participants"]) == sorted(requested)
    checks["provenance_closed"] = _provenance_closed(db, result)
    checks["repeatable"] = production_compare(db, requested) == result
    checks["order_invariant"] = all(production_compare(db, list(order)) == result for order in permutations(requested))
    reversed_db = workdir / "reversed.db"
    lab._reverse_storage_copy(db, reversed_db)
    checks["storage_order_invariant"] = production_compare(reversed_db, requested) == result
    rebuilt = materialize(corpus, case, workdir / "rebuild")
    rebuilt_result = production_compare(rebuilt["db"], [rebuilt["ids"][k] for k in case["compare"]])
    checks["independent_rebuild_identical"] = normalized(rebuilt_result, rebuilt["labels"]) == norm
    populated, problems = populate_reference(case["reference"], result, labels)
    checks["reference_adequate_and_closed"] = not problems
    record["reference_problems"] = problems
    variants = []
    for variant in case["variants"]:
        vbuilt = materialize(corpus, case, workdir / variant["variant_id"], modify=variant["modify"])
        vresult = production_compare(vbuilt["db"], [vbuilt["ids"][k] for k in case["compare"]])
        vnorm = normalized(vresult, vbuilt["labels"])
        entry = {"variant_id": variant["variant_id"], "expect": variant["expect"]}
        if variant["expect"] == "substantive_unchanged":
            entry["passed"] = (substantive(vnorm) == substantive(norm)
                               and [r["execution"] for r in vnorm["relations"]] == variant["execution_relations"])
        elif variant["expect"] == "evidence_changed":
            entry["passed"] = (vnorm["evidence"] == _sorted_expected({"evidence": variant["evidence"]})["evidence"]
                               and [{k: r[k] for k in ("evidence_units", "evidence_focus")} for r in vnorm["relations"]]
                               == variant["evidence_relations"]
                               and substantive(vnorm) != substantive(norm))
        else:
            vpopulated, vproblems = populate_reference(variant["reference"], vresult, vbuilt["labels"])
            responses_changed = [p["response"] for p in vresult["participants"]] != [p["response"] for p in result["participants"]]
            entry["passed"] = (substantive(vnorm) == substantive(norm) and responses_changed and not vproblems
                               and derive(variant["reference"], vnorm["order"]) != derive(case["reference"], norm["order"]))
            entry["boundary"] = ("The conclusion flip changed the reference claim structure but not the "
                                 "deterministic comparison beyond response text.")
        entry["passed"] = entry["passed"] and not validate_result(vresult)
        variants.append(entry)
    record["variants"] = variants
    checks["variants_as_frozen"] = all(v["passed"] for v in variants)
    checks["workspace_unchanged"] = lab._logical_digest(db) == before
    record["comparison"] = norm
    record["reference"] = {k: v for k, v in populated.items() if k not in ("propositions",)} | {
        "propositions": [{"id": p["id"], "statement": p["statement"],
                          "stances": [labels.get(x["participant"]) + ":" + x["stance"] for x in p["positions"]],
                          "uncited": [labels.get(x["participant"]) for x in p["positions"]
                                      if x["stance"] in ("asserts", "denies") and not x["cited_evidence"]]}
                         for p in populated["propositions"]]}
    record["reference"] = _relabel(record["reference"], labels)
    return record


def _relabel(value, labels):
    if isinstance(value, dict):
        return {k: _relabel(v, labels) for k, v in value.items()}
    if isinstance(value, list):
        return [_relabel(v, labels) for v in value]
    return labels.get(value, value) if isinstance(value, str) else value


def run(path: Path = FIXTURES / "cases.json") -> dict:
    corpus = load_corpus(path)
    records = []
    for case in corpus["cases"]:
        with tempfile.TemporaryDirectory(prefix="p7-comparison-") as tmp:
            workdir = Path(tmp)
            with lab.isolated(workdir):
                _FakeOllamaClient.models = list(corpus["models"])
                records.append(evaluate_case(corpus, case, workdir))
    compared = [r for r in records if "schema_valid" in r["checks"]]
    names = sorted({name for r in records for name in r["checks"]})
    aggregate = {name: {"passed": sum(1 for r in records if r["checks"].get(name) is True),
                        "total": sum(1 for r in records if name in r["checks"])} for name in names}
    aggregate["manufactured_semantic_fields"] = {
        "count": sum(1 for r in compared if r["comparison"]["semantic"] != SEMANTIC_NOT_ESTABLISHED), "total": len(compared)}
    return {"schema": RESULT_SCHEMA, "policy_version": POLICY_VERSION, "corpus": CASES_SCHEMA,
            "method": ("each case materialized in a disposable synthetic workspace through production write boundaries; "
                       "in-process fake adapters; no network, provider, credential store, real workspace or private text; "
                       "production P4 adapter decides eligibility and the production comparator compares"),
            "aggregate": aggregate, "cases": records}


def _reference_digest(reference: dict) -> str:
    parts = [f"agree {a['proposition']} ({', '.join(a['participants'])})" for a in reference["agreement"]]
    parts += [f"disagree {d['proposition']}" + (f" (minority {', '.join(d['smaller_groups'])})" if d["smaller_groups"] else "")
              for d in reference["disagreement"]]
    parts += [f"{len(reference['assumptions'])} quoted assumption(s)"] if reference["assumptions"] else []
    parts += [f"unclassifiable {u['proposition']}/{u['participant']}" for u in reference["unclassifiable"]]
    parts += [f"{p['id']} stated without cited evidence by {', '.join(p['uncited'])}" for p in reference["propositions"] if p["uncited"]]
    return "; ".join(parts) or "no shared proposition"


def summary_markdown(results: dict) -> str:
    lines = ["# P7 Structured Perspective Comparison v1 — evaluation summary", "",
             f"Policy `{results['policy_version']}`. Generated by `tests/perspective_comparison_lab.py`; evaluation data, not study history.", "",
             "| Case | Deterministic outcome | Evidence | Relations (perspective / execution / text) | Uncertainty beyond the base four "
             "| Reference annotation (not produced by the comparator) | Checks |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    base = {"GOVERNING_QUESTION_NOT_BOUND", "SUPPLIED_NOT_RELIED_ON", "EXECUTION_SETTINGS_UNDISCLOSED", "NO_ADJUDICATION"}
    for r in results["cases"]:
        checks = r["checks"]
        passed = f"{sum(1 for v in checks.values() if v is True)}/{len(checks)}"
        c = r["comparison"]
        if "refusal" in c:
            lines.append(f"| {r['case_id']} | refused `{c['refusal']}` | — | — | — | — | {passed} |")
            continue
        relations = "; ".join(f"{'–'.join(x['pair'])}: {x['perspective']} / {x['execution']} / {x['response_text']}" for x in c["relations"])
        extra = ", ".join(f"`{u}`" for u in c["uncertainty"] if u not in base) or "—"
        lines.append(f"| {r['case_id']} | compared; semantic not established | {c['evidence']['overall']} | {relations} | {extra} "
                     f"| {_reference_digest(r['reference'])} | {passed} |")
    lines += ["", "The reference column is the frozen evaluation annotation of each case's designed claim structure. The "
              "deterministic comparator establishes none of it: every compared case reports `semantic` as "
              "`not_established` (`SEMANTIC_EXTRACTION_REQUIRED`).", "", "## Aggregate", ""]
    for name in sorted(results["aggregate"]):
        value = results["aggregate"][name]
        lines.append(f"- `{name}`: " + (f"{value['count']}/{value['total']}" if "count" in value else f"{value['passed']}/{value['total']}"))
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
    committed = json.loads((args.check / "results.json").read_text())
    if committed != results or (args.check / "summary.md").read_text() != summary_markdown(results):
        print("results differ from committed dataset")
        return 1
    print("results match committed dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
