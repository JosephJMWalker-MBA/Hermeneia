"""P8 live Blueprint proposal diagnostic (#215), owner-authorized 2026-10-10, bounded.

Executes tests/fixtures/blueprint_proposal/v1/live_evaluation_protocol.json,
which is frozen with this module before any live call. The run is six cases,
three samples each, against the installed local Ollama model through the
production proposal route, on disposable synthetic workspaces. Nothing is
accepted.

The automatic scorer here is independent of the production parser, and the
rubric-grade aggregation is frozen with the protocol. Semantic grades are
recorded separately (grading.json) after the run and before any aggregate is
computed. The scripted ceiling runs the same harness through the in-process
fake adapter, with no network. Evaluation data, not study history.

    python tests/blueprint_proposal_live_eval.py ceiling research/blueprint_proposal_live/ceiling
    python tests/blueprint_proposal_live_eval.py run     research/blueprint_proposal_live/phi4-mini
    python tests/blueprint_proposal_live_eval.py score   <dir>    # results.json + grading.json -> aggregate
    python tests/blueprint_proposal_live_eval.py check   <dir>    # recompute and compare
"""
from __future__ import annotations

import argparse
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for entry in (str(ROOT), str(TESTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import blueprint_proposal_lab as proposal_lab  # noqa: E402  (frozen P8 corpus and workspace materialization, unchanged)
import synthetic_study_lab as lab  # noqa: E402
from hermeneia import blueprint_proposals as bp  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from test_e10_vertical_slice_api import _FakeOllamaClient  # noqa: E402

PROTOCOL_PATH = TESTS / "fixtures" / "blueprint_proposal" / "v1" / "live_evaluation_protocol.json"
POLICY_PATH = TESTS / "fixtures" / "blueprint_proposal" / "v1" / "proposal_policy_v1.json"
PROTOCOL_SCHEMA = "hermeneia.blueprint-proposal-live-evaluation-protocol/v1"
RESULTS_SCHEMA = "hermeneia.blueprint-proposal-live-evaluation/v1"
GRADING_SCHEMA = "hermeneia.blueprint-proposal-live-grading/v1"
AGGREGATE_SCHEMA = "hermeneia.blueprint-proposal-live-aggregate/v1"
CANONICAL_TABLES = ("narrative_blueprints", "architect_plans", "supersession_relations", bp.TABLE)
SUPPORT = ("supported", "limit_statement", "plausible_unsupported", "contradicted", "misrepresents_record")
SEVERE_SUPPORT = {"contradicted": "S1", "misrepresents_record": "S4"}
PROPOSAL_CODES = {"PROPOSAL_OUTPUT_UNPARSEABLE", "PROPOSAL_OUTPUT_INVALID", "PROPOSAL_REFERENCE_EXCLUDED",
                  "PROPOSAL_REFERENCE_UNKNOWN"}
_FENCE = re.compile(r"\A\s*```(?:json)?[ \t]*\n(.*)\n[ \t]*```\s*\Z", re.S)
_POINTER = re.compile(r"\b[OI]\d+\b")
_ANY_LABEL = re.compile(r"(?<![A-Za-z0-9])([OoIi])(\d+)(?![0-9])")
_WORD_LABEL = re.compile(r"\b(observation|interpretation)\s*#?\s*(\d+)\b", re.I)


def load_protocol() -> dict:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    if protocol.get("schema") != PROTOCOL_SCHEMA or protocol.get("frozen_before_any_live_call") is not True:
        raise ValueError("P8 live protocol schema differs; re-freeze deliberately")
    return protocol


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def frozen_prompt_check() -> bool:
    """D7: the production prompt constants are the frozen policy."""
    policy = json.loads(POLICY_PATH.read_text())
    return (list(bp.HEADER) == policy["header"] and list(bp.RULES) == policy["rules"]
            and (bp.INTENT_INTRO, bp.GOVERNING_INTRO, bp.OBSERVATIONS_INTRO, bp.INTERPRETATIONS_INTRO, bp.NONE_LINE)
            == (policy["intent_intro"], policy["governing_intro"], policy["observations_intro"],
                policy["interpretations_intro"], policy["none_line"])
            and (bp.OBSERVATION_LINE, bp.INTERPRETATION_LINE, bp.AUTHORSHIP_LABELS)
            == (policy["observation_line"], policy["interpretation_line"], policy["authorship_labels"])
            and (bp.PREDECESSOR_INTRO, list(bp.PREDECESSOR_LINES), bp.RETURN_INTRO, bp.CREATE_SHAPE, bp.REVISE_SHAPE,
                 bp.RULES_INTRO, bp.REVISE_RULE)
            == (policy["predecessor_intro"], policy["predecessor_lines"], policy["return_intro"], policy["create_shape"],
                policy["revise_shape"], policy["rules_intro"], policy["revise_rule"])
            and bp.POLICY_VERSION == policy["policy_version"] and bp.PROMPT_VERSION == policy["prompt_version"])


# ── Independent reference census and contract check (protocol "scoring") ─────

def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def census(raw, mode: str, binding: dict, ineligible) -> dict:
    """Classify every reference and pointer in a raw output without the production parser."""
    raw = raw if isinstance(raw, str) else ""
    own = {"observations": {o["label"]: o["id"] for o in binding["observations"]},
           "interpretations": {i["label"]: i["id"] for i in binding["interpretations"]}}
    labels = set(own["observations"]) | set(own["interpretations"])
    exposed_ids = set(own["observations"].values()) | set(own["interpretations"].values())
    ineligible = set(ineligible)

    def classify(token: str, field: str) -> str:
        other = "interpretations" if field == "observations" else "observations"
        if token in own[field]:
            return "valid"
        if token in own[other]:
            return "misfiled"
        stripped = token.strip()
        if stripped in ineligible:
            return "excluded"
        found = {f"{m.group(1).upper()}{int(m.group(2))}" for m in _ANY_LABEL.finditer(token)}
        found |= {f"{'O' if m.group(1).lower() == 'observation' else 'I'}{int(m.group(2))}" for m in _WORD_LABEL.finditer(token)}
        if stripped in exposed_ids or (len(found) == 1 and found <= labels):
            return "malformed"
        return "invented"

    pointers = sorted({t for t in _POINTER.findall(raw) if t not in labels} | {i for i in ineligible if i and i in raw})
    match = _FENCE.match(raw)
    try:
        value = json.loads(match.group(1) if match else raw, object_pairs_hook=_unique)
    except (ValueError, TypeError):
        value = None
    if not isinstance(value, dict):
        return {"json": False, "violations": ["not one JSON object"], "tokens": [], "pointers": pointers,
                "offending": pointers, "contract_valid": False}
    violations, tokens = [], []
    fields = {"title", "thesis", "sections"} | ({"change_summary"} if mode == "revise" else set())
    if set(value) != fields:
        violations.append(f"fields {sorted(value)} != {sorted(fields)}")
    for name in sorted(fields - {"sections"}):
        if name in value and not _nonblank(value[name]):
            violations.append(f"{name} is not a non-blank string")
    sections = value.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= bp.MAX_SECTIONS:
        violations.append("sections must be a list of 1 to 12 sections")
    for n, section in enumerate(sections if isinstance(sections, list) else [], 1):
        if not isinstance(section, dict):
            violations.append(f"section {n} is not an object")
            continue
        if set(section) != {"claim", "observations", "interpretations"}:
            violations.append(f"section {n} fields {sorted(section)}")
        if "claim" in section and not _nonblank(section["claim"]):
            violations.append(f"section {n} claim is not a non-blank string")
        for field in ("observations", "interpretations"):
            if field not in section:
                continue
            refs = section[field]
            if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
                violations.append(f"section {n} {field} is not a list of strings")
                refs = [r for r in refs if isinstance(r, str)] if isinstance(refs, list) else []
            elif len(set(refs)) != len(refs):
                violations.append(f"section {n} {field} has duplicates")
            tokens += [{"section": n, "field": field, "token": r, "class": classify(r, field)} for r in refs]
    offending = sorted(set(pointers) | {t["token"] for t in tokens if t["class"] in ("invented", "excluded")})
    return {"json": True, "violations": violations, "tokens": tokens, "pointers": pointers, "offending": offending,
            "contract_valid": not violations and all(t["class"] == "valid" for t in tokens)}


def reference_scores(cited: set, sets: dict) -> dict:
    admissible, expected, required = (set(sets[k]) for k in ("admissible", "expected", "required"))
    return {"cited": sorted(cited), "precision_num": len(cited & admissible), "precision_den": len(cited),
            "precision": round(len(cited & admissible) / len(cited), 4) if cited else 0.0,
            "expected_num": len(cited & expected), "expected_den": len(expected),
            "expected_recall": round(len(cited & expected) / len(expected), 4),
            "required_missing": sorted(required - cited), "required_recall": round(len(cited & required) / len(required), 4),
            "outside_admissible": sorted(cited - admissible)}


# ── Materialization and one sample ───────────────────────────────────────────

def case_spec(pcase: dict, corpus: dict) -> tuple[list, dict, dict]:
    if pcase["source_case"]:
        source = next(c for c in corpus["cases"] if c["case_id"] == pcase["source_case"])
        generate = {k: source["generate"][k] for k in ("mode", "intent", "predecessor") if k in source["generate"]}
        script = source["generate"]["script"] if pcase["ceiling_script"] == "source" else pcase["ceiling_script"]
        return source["setup"], generate, script
    return pcase["setup"], pcase["generate"], pcase["ceiling_script"]


def _counts(ws) -> dict:
    return {table: ws.count(table) for table in CANONICAL_TABLES}


def _proposal_local(ws, proposal: dict) -> dict:
    blueprint = proposal["blueprint"]
    return {"title": blueprint["title"], "thesis": blueprint["thesis"], "model_explanation": proposal["model_explanation"],
            "sections": [{"claim": s["claim"], "observations": [ws.local(o) for o in s["supporting_observations"]],
                          "interpretations": [ws.local(i) for i in s["supporting_interpretations"]]} for s in blueprint["sections"]]}


def run_sample(corpus: dict, protocol: dict, pcase: dict, sample: int, workdir: Path, *, live: bool) -> dict:
    setup, generate, script = case_spec(pcase, corpus)
    with lab.isolated(workdir):
        _FakeOllamaClient.models = [corpus["extraction_model"]]
        ws = proposal_lab.Workspace(corpus, workdir)
        for op in setup:
            ws.apply(op)
        basis = ws.basis(generate["mode"], generate.get("predecessor"))
        prompt = bp.build_prompt(basis, generate["intent"])
        before, counts_before = lab._logical_digest(ws.db), _counts(ws)
        if not live:
            started = time.monotonic()
            response, _ = proposal_lab.propose(ws, generate, script, corpus["extraction_model"])
            elapsed = time.monotonic() - started
    if live:
        import perspective_comparison_live_eval as p7_live  # loopback guard and fresh settings, unchanged

        body = {"mode": generate["mode"], "intent": generate["intent"], "model": protocol["model"]}
        if generate["mode"] == "revise":
            body["predecessor_id"] = ws.blueprints[generate["predecessor"]]
        with p7_live.fresh_settings(workdir), p7_live.loopback_only():
            app = create_app(db_path=ws.db, credential_store=lab._NoCredentials())
            app.config["BLUEPRINT_PROPOSAL_GENERATION"] = "experimental"  # evaluation app only
            started = time.monotonic()
            response = app.test_client().post("/api/blueprint/proposals", json=body)
            elapsed = time.monotonic() - started
    payload = response.get_json(silent=True) or {}
    status, code = response.status_code, payload.get("code")
    raw = payload.get("output") if status == 422 else (payload.get("extraction") or {}).get("output")
    expected_execution = ({"provider_id": "ollama-local", "model_id": protocol["model"], "adapter": "OllamaArtistProvider"} if live
                          else {"provider_id": "ollama-local", "model_id": corpus["extraction_model"], "adapter": "_CapturingProvider"})
    sense = census(raw, generate["mode"], basis["binding"], basis["ineligible_ids"]) if raw is not None else None
    # A runtime or model failure: 502 PROVIDER_FAILED, or the uncoded 409 of the local execution context.
    provider_failure = ((status == 502 and code == "PROVIDER_FAILED")
                        or (status == 409 and code is None and payload.get("canonical_status") == "not_persisted"))
    governance = {"D1_status": status in (201, 422) or provider_failure,
                  "D2_no_write": lab._logical_digest(ws.db) == before and _counts(ws) == counts_before}
    record = {"run_id": f"{pcase['case_id'].split('_')[0]}-s{sample}", "case_id": pcase["case_id"], "sample": sample,
              "mode": generate["mode"], "intent": generate["intent"], "http_status": status, "code": code,
              "provider_failure": provider_failure, "elapsed_s": round(elapsed, 3), "prompt": prompt,
              "prompt_sha256": bp.text_digest(prompt), "raw_output": raw,
              "raw_output_sha256": bp.text_digest(raw) if raw is not None else None, "census": sense,
              "exposed": {"observations": [ws.local(o["id"]) for o in basis["binding"]["observations"]],
                          "interpretations": {ws.local(i["id"]): i["label"] for i in basis["binding"]["interpretations"]}},
              "response_body": payload, "admitted": status == 201}
    if status == 422 and code in PROPOSAL_CODES:
        try:
            bp.parse_output(raw, basis)
            governance["D3_refusal_reproduced"] = False
        except bp.ProposalRefused as refusal:
            governance["D3_refusal_reproduced"] = refusal.code == code
        governance["D6_no_valid_refusal"] = sense is not None and not sense["contract_valid"]
    elif status == 201:
        candidate = payload
        exposed_obs = {o["id"] for o in basis["binding"]["observations"]}
        exposed_int = {i["id"] for i in basis["binding"]["interpretations"]}
        blueprint = candidate["proposal"]["blueprint"]
        try:
            reparsed = json.loads(json.dumps(bp.parse_output(raw, basis)))
        except bp.ProposalRefused:
            reparsed = None
        execution = candidate["extraction"]["execution"]
        governance["D4_candidate_integrity"] = (
            bp.candidate_id(candidate) == candidate["candidate_id"] and reparsed == candidate["proposal"]
            and all(set(s["supporting_observations"]) <= exposed_obs and set(s["supporting_interpretations"]) <= exposed_int
                    for s in blueprint["sections"])
            and candidate["extraction"]["prompt"] == prompt
            and candidate["binding"]["basis"] == json.loads(json.dumps(basis["binding"]))
            and all(execution.get(k) == v for k, v in expected_execution.items()))
        governance["D5_no_bad_admission"] = sense is not None and sense["contract_valid"]
        record["proposal_local"] = _proposal_local(ws, candidate["proposal"])
        cited = {t for s in record["proposal_local"]["sections"] for t in [*s["observations"], *s["interpretations"]]}
        record["references"] = reference_scores(cited, pcase["sets"])
        sections = record["proposal_local"]["sections"]
        record["grounding"] = {"sections": len(sections), "cited_sections": sum(1 for s in sections if s["observations"] or s["interpretations"])}
    elif not provider_failure:
        governance["D1_status"] = False
    record["governance"] = governance
    return record


def results_binding(results: dict) -> str:
    """Binds a grading file to the exact admitted outputs it grades."""
    return _sha(_canonical(sorted([r["run_id"], r["raw_output_sha256"]] for r in results["records"] if r["admitted"])))


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def execute(out: Path, *, live: bool) -> dict:
    protocol, corpus = load_protocol(), proposal_lab.load()
    frozen_files = [PROTOCOL_PATH, Path(__file__).resolve()]
    if live:
        dirty = _git("status", "--porcelain", "--", *[str(p.relative_to(ROOT)) for p in frozen_files])
        if dirty:
            raise RuntimeError("the protocol and harness must be committed before any live call")
        import perspective_comparison_live_eval_substitution as identity_reader  # loopback identity read, unchanged

        identity_before = identity_reader.installed_identity(protocol["model"])
        if identity_before["digest"] != protocol["model_identity"]["digest"]:
            raise RuntimeError("installed model digest differs from the frozen protocol; refusing to run")
    if not frozen_prompt_check():
        raise RuntimeError("D7: the production prompt differs from the frozen policy; refusing to run")
    out.mkdir(parents=True, exist_ok=True)
    partial = out / "records.partial.jsonl"
    partial.unlink(missing_ok=True)
    records = []
    for sample in range(1, protocol["samples_per_case"] + 1):
        for pcase in protocol["cases"]:
            with tempfile.TemporaryDirectory(prefix="p8-live-") as tmp:
                record = run_sample(corpus, protocol, pcase, sample, Path(tmp), live=live)
            records.append(record)
            with partial.open("a") as handle:  # no live output is lost if post-processing fails
                handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            print(f"{record['run_id']}: http {record['http_status']} {record['code'] or ''}", flush=True)
    result = {"schema": RESULTS_SCHEMA, "kind": "live" if live else "scripted_ceiling",
              "protocol_sha256": _sha(PROTOCOL_PATH.read_bytes()), "harness_sha256": _sha(Path(__file__).read_bytes()),
              "frozen_prompt": True, "records": records}
    if live:
        result["protocol_commit"] = _git("rev-parse", "HEAD")
        result["model_identity_before"] = identity_before
        result["model_identity_after"] = identity_reader.installed_identity(protocol["model"])
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    partial.unlink()
    return result


# ── Grades and aggregate ─────────────────────────────────────────────────────

def _proposal_text(record: dict) -> str:
    p = record["proposal_local"]
    return "\n".join([p["title"], p["thesis"], *[s["claim"] for s in p["sections"]], p["model_explanation"] or ""])


def validate_grading(grading: dict, results: dict, protocol: dict) -> dict:
    """Strictly checks that grading covers exactly the admitted outputs with the frozen rubric's classes."""
    if grading.get("schema") != GRADING_SCHEMA or grading.get("rubric_version") != protocol["rubric"]["version"]:
        raise ValueError("grading schema or rubric version differs")
    if grading.get("results_binding") != results_binding(results):
        raise ValueError("grading is not bound to these exact outputs")
    admitted = {r["run_id"]: r for r in results["records"] if r["admitted"]}
    grades = {}
    for grade in grading["grades"]:
        if grade["run_id"] in grades:
            raise ValueError(f"duplicate grade {grade['run_id']}")
        grades[grade["run_id"]] = grade
    if set(grades) != set(admitted):
        raise ValueError("grades must cover exactly the admitted samples")
    for run_id, grade in grades.items():
        record = admitted[run_id]
        units = ["thesis", *[f"section {n}" for n in range(1, len(record["proposal_local"]["sections"]) + 1)]]
        if [c["unit"] for c in grade["claims"]] != units:
            raise ValueError(f"{run_id}: claim units must be {units}")
        text = _proposal_text(record)
        checks = [grade["intent"]["score"] in (0, 1, 2), _nonblank(grade["intent"]["rationale"]),
                  all(c["class"] in SUPPORT and _nonblank(c["rationale"]) for c in grade["claims"]),
                  grade["uncertainty"]["class"] in ("preserved", "flattened") and _nonblank(grade["uncertainty"]["rationale"]),
                  grade["authorship"]["class"] in ("pass", "fail") and _nonblank(grade["authorship"]["rationale"])]
        for key, failing in (("uncertainty", "flattened"), ("authorship", "fail")):
            if grade[key]["class"] == failing:
                quote = grade[key].get("quote")
                checks.append(_nonblank(quote) and quote in text)
        if not all(checks):
            raise ValueError(f"{run_id}: grade does not follow the frozen rubric")
    return grades


def _ratio(num, den):
    return round(num / den, 4) if den else None


def aggregate(results: dict, grading: dict | None, protocol: dict) -> dict:
    t = protocol["thresholds"]
    per3, per4 = t["C3_references"]["per_sample"], t["C4_semantic_fidelity"]["per_sample"]
    grades = validate_grading(grading, results, protocol) if grading is not None else {}
    records, cases = results["records"], [c["case_id"] for c in protocol["cases"]]
    defects = [{"run_id": r["run_id"], "check": k} for r in records for k, ok in sorted(r["governance"].items()) if not ok]
    samples = []
    for r in records:
        s = {"run_id": r["run_id"], "case_id": r["case_id"], "admitted": r["admitted"], "http_status": r["http_status"],
             "code": r["code"], "provider_failure": r["provider_failure"],
             "offending": (r["census"] or {}).get("offending", []), "passes": False}
        if r["admitted"]:
            ref = r["references"]
            s["references"] = {k: ref[k] for k in ("precision", "expected_recall", "required_recall", "required_missing",
                                                   "outside_admissible")}
            s["references_pass"] = (ref["required_recall"] >= per3["required_recall"] and ref["precision"] >= per3["min_precision"]
                                    and ref["expected_recall"] >= per3["min_expected_recall"])
            g = grades.get(r["run_id"])
            if g is not None:
                classes = [c["class"] for c in g["claims"]]
                severe = sorted({SEVERE_SUPPORT[c] for c in classes if c in SEVERE_SUPPORT}
                                | ({"S2"} if g["intent"]["score"] == 0 else set())
                                | ({"S3"} if g["authorship"]["class"] == "fail" else set()))
                supported = sum(1 for c in classes if c in ("supported", "limit_statement"))
                s["semantic"] = {"intent": g["intent"]["score"], "supported": supported, "claims": len(classes),
                                 "supported_rate": _ratio(supported, len(classes)), "uncertainty": g["uncertainty"]["class"],
                                 "authorship": g["authorship"]["class"], "severe": severe,
                                 "classes": {k: classes.count(k) for k in SUPPORT if k in classes}}
                s["semantic_pass"] = (not severe and g["intent"]["score"] >= per4["min_intent"]
                                      and s["semantic"]["supported_rate"] >= per4["min_supported_rate"]
                                      and g["uncertainty"]["class"] == per4["uncertainty"])
                s["passes"] = s["references_pass"] and s["semantic_pass"]
        samples.append(s)
    admitted = [s for s in samples if s["admitted"]]
    graded = [s for s in admitted if "semantic" in s]
    by_case = {c: [s for s in samples if s["case_id"] == c] for c in cases}
    adm_records = [r for r in records if r["admitted"]]
    pooled = {"precision": _ratio(sum(r["references"]["precision_num"] for r in adm_records),
                                  sum(r["references"]["precision_den"] for r in adm_records)),
              "expected_recall": _ratio(sum(r["references"]["expected_num"] for r in adm_records),
                                        sum(r["references"]["expected_den"] for r in adm_records)),
              "mean_intent": _ratio(sum(s["semantic"]["intent"] for s in graded), len(graded)),
              "supported_rate": _ratio(sum(s["semantic"]["supported"] for s in graded), sum(s["semantic"]["claims"] for s in graded))}
    cited = {r["run_id"]: set(r["references"]["cited"]) for r in adm_records}

    def jaccard(run_ids):
        pairs = list(combinations(run_ids, 2))
        if not pairs:
            return None
        return round(sum(len(cited[a] & cited[b]) / len(cited[a] | cited[b]) if cited[a] | cited[b] else 1.0
                         for a, b in pairs) / len(pairs), 4)

    consistency = {c: {"admitted": sum(1 for s in group if s["admitted"]),
                       "all_admitted_pass": all(s["passes"] for s in group if s["admitted"]),
                       "mean_pairwise_jaccard": jaccard([s["run_id"] for s in group if s["admitted"]])}
                   for c, group in by_case.items()}
    offending_total = sum(len(s["offending"]) for s in samples)
    severe_total = sum(len(s["semantic"]["severe"]) for s in graded)
    p3, p4, c5 = t["C3_references"]["pooled"], t["C4_semantic_fidelity"]["pooled"], t["C5_consistency"]["per_case"]
    ungraded = len(graded) != len(admitted)
    criteria = {
        "C1_invented_or_excluded_references": offending_total <= t["C1_invented_or_excluded_references"]["max_total"],
        "C2_admission": (len(admitted) >= t["C2_admission"]["min_admitted_total"]
                         and all(v["admitted"] >= t["C2_admission"]["min_admitted_per_case"] for v in consistency.values())),
        "C3_references": (bool(admitted) and all(s["references_pass"] for s in admitted)
                          and (pooled["precision"] or 0) >= p3["min_precision"] and (pooled["expected_recall"] or 0) >= p3["min_expected_recall"]),
        "C4_semantic_fidelity": (bool(graded) and not ungraded and severe_total <= t["C4_semantic_fidelity"]["severe_errors_max"]
                                 and all(s["semantic_pass"] for s in graded)
                                 and (pooled["mean_intent"] or 0) >= p4["min_mean_intent"] and (pooled["supported_rate"] or 0) >= p4["min_supported_rate"]),
        "C5_consistency": all(v["admitted"] >= 2 and v["all_admitted_pass"] and (v["mean_pairwise_jaccard"] or 0) >= c5["min_mean_pairwise_jaccard"]
                              for v in consistency.values()),
    }
    if defects:
        verdict = "P8_DEFECT"
    elif ungraded:
        verdict = "UNGRADED"
    else:
        verdict = "P8_GOVERNANCE_READY_GENERATION_READY" if all(criteria.values()) else "P8_GOVERNANCE_READY_GENERATION_NOT_READY"
    codes = {}
    for s in samples:
        if not s["admitted"]:
            key = "PROVIDER_FAILURE" if s["provider_failure"] else (s["code"] or str(s["http_status"]))
            codes[key] = codes.get(key, 0) + 1
    l13 = [s["run_id"] for s in admitted if s["case_id"] in ("L1_vigil_or_absence", "L3_vigil_or_absence_repeat")]
    return {"schema": AGGREGATE_SCHEMA, "kind": results["kind"], "thresholds_version": t["version"],
            "rubric_version": protocol["rubric"]["version"], "verdict": verdict, "criteria": criteria,
            "governance_defects": defects,
            "counts": {"runs": len(samples), "admitted": len(admitted), "refusals_by_code": dict(sorted(codes.items())),
                       "runs_with_invented_or_excluded": sum(1 for s in samples if s["offending"]),
                       "invented_or_excluded_tokens": offending_total, "severe_errors": severe_total,
                       "admitted_samples_passing": sum(1 for s in admitted if s["passes"]),
                       "misfiled_or_malformed_tokens": sum(1 for r in records for tok in ((r["census"] or {}).get("tokens") or [])
                                                           if tok["class"] in ("misfiled", "malformed")),
                       "uncited_sections": sum(r["grounding"]["sections"] - r["grounding"]["cited_sections"] for r in adm_records),
                       "sections": sum(r["grounding"]["sections"] for r in adm_records)},
            "pooled": pooled, "consistency": consistency,
            "l1_l3_six_sample_jaccard": jaccard(l13), "samples": samples}


def summary_markdown(agg: dict, results: dict) -> str:
    lines = [f"# P8 live Blueprint proposal diagnostic — {agg['kind']}", "",
             "Generated by `tests/blueprint_proposal_live_eval.py`; frozen protocol "
             "`tests/fixtures/blueprint_proposal/v1/live_evaluation_protocol.json`. Evaluation data, not study history.", ""]
    if "model_identity_before" in results:
        m = results["model_identity_before"]
        lines += [f"Model `{m['model']}` · digest `{m['digest']}` · {m['parameter_size']} · {m['quantization_level']} · "
                  f"protocol commit `{results['protocol_commit'][:7]}`.", ""]
    lines += [f"**Verdict: {agg['verdict']}** ({agg['thresholds_version']}, {agg['rubric_version']})", "",
              "| Criterion | Holds |", "| --- | --- |"]
    lines += [f"| {k} | {'yes' if v else 'no'} |" for k, v in agg["criteria"].items()]
    c, p = agg["counts"], agg["pooled"]
    lines += ["", f"Runs {c['runs']}, admitted {c['admitted']}, admitted samples passing every per-sample criterion "
              f"{c['admitted_samples_passing']}. Refusals: {c['refusals_by_code'] or 'none'}. Runs with invented or excluded "
              f"references {c['runs_with_invented_or_excluded']} ({c['invented_or_excluded_tokens']} tokens). Severe semantic "
              f"errors {c['severe_errors']}. Governance defects {len(agg['governance_defects'])}.", "",
              f"Pooled: precision {p['precision']}, expected recall {p['expected_recall']}, mean intent {p['mean_intent']}, "
              f"supported-claim rate {p['supported_rate']}. Uncited sections {c['uncited_sections']}/{c['sections']}.", "",
              "| Run | HTTP | Code | Invented/excluded | Precision | Exp. recall | Req. recall | Intent | Supported | Uncertainty | Authorship | Severe | Passes |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in agg["samples"]:
        ref, sem = s.get("references") or {}, s.get("semantic") or {}
        supported = f"{sem['supported']}/{sem['claims']}" if sem else "—"
        lines.append(f"| {s['run_id']} | {s['http_status']} | {s['code'] or '—'} | {', '.join(s['offending']) or '—'} | "
                     f"{ref.get('precision', '—')} | {ref.get('expected_recall', '—')} | {ref.get('required_recall', '—')} | "
                     f"{sem.get('intent', '—')} | {supported} | {sem.get('uncertainty', '—')} | {sem.get('authorship', '—')} | "
                     f"{', '.join(sem.get('severe', [])) or '—'} | {'yes' if s['passes'] else 'no'} |")
    lines += ["", "| Case | Admitted | All admitted pass | Mean pairwise Jaccard |", "| --- | --- | --- | --- |"]
    lines += [f"| {k} | {v['admitted']} | {'yes' if v['all_admitted_pass'] else 'no'} | {v['mean_pairwise_jaccard']} |"
              for k, v in agg["consistency"].items()]
    lines += ["", f"L1 and L3 pooled (six identical requests): mean pairwise Jaccard {agg['l1_l3_six_sample_jaccard']}.", ""]
    return "\n".join(lines)


def score(out: Path) -> dict:
    protocol = load_protocol()
    results = json.loads((out / "results.json").read_text())
    grading = json.loads((out / "grading.json").read_text())
    return aggregate(results, grading, protocol)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("ceiling", "run", "score", "check"))
    parser.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command in ("ceiling", "run"):
        execute(args.out, live=args.command == "run")
        print(f"wrote {args.out / 'results.json'}; grade into grading.json, then run score")
        return 0
    agg = score(args.out)
    results = json.loads((args.out / "results.json").read_text())
    text, md = json.dumps(agg, indent=2, sort_keys=True, ensure_ascii=False) + "\n", summary_markdown(agg, results)
    if args.command == "score":
        (args.out / "aggregate.json").write_text(text)
        (args.out / "summary.md").write_text(md)
        print(agg["verdict"])
        return 0
    same = (args.out / "aggregate.json").read_text() == text and (args.out / "summary.md").read_text() == md
    print("aggregate matches committed results and grading" if same else "aggregate DIFFERS")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
