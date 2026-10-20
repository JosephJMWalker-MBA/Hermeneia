"""P10 Blueprint dependency chain portability laboratory (#252): export → fresh restore → equivalence.

Synthetic studies are built through production write boundaries:
- upload, saved Perspectives, steward Interpretations;
- E10 model proposals (accepted, pending, rejected);
- steward ratification and revision;
- P8 propose and accept (the P8 laboratory enables generation in its own
  disposable app only);
- legacy architect generation and legacy extract-and-save;
- document exclusion.

Each is exported with the gated chain component enabled, restored into a
fresh target, and compared:
- rows;
- Study Lineage;
- P1 capability decisions;
- P8 receipt verification;
- coverage declarations;
- determinism;
- an unchanged source.

Adversarial cases tamper with the source or the bundle and must be declared
unsupported or refused. P5 isolation (sockets blocked); in-process fakes; no
live model; no real workspace. Contract:
docs/design/blueprint-chain-portability-v1.md §7. This module records
evaluation data, not study history.

    python tests/blueprint_chain_lab.py --write research/blueprint_chain_portability/v1
    python tests/blueprint_chain_lab.py --check research/blueprint_chain_portability/v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest.mock as mock

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for entry in (str(ROOT), str(TESTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import blueprint_proposal_lab as proposal_lab  # noqa: E402  (P8's own production-route study builder, unchanged)
import synthetic_study_lab as lab  # noqa: E402
from hermeneia.blueprint_proposals import verify_receipt  # noqa: E402
from hermeneia.capabilities import evaluate_capabilities  # noqa: E402
from hermeneia.study_lineage import project_study_lineage  # noqa: E402
from hermeneia.workspace import export_workspace_bundle  # noqa: E402
from hermeneia.workspace.blueprint_chain import CAPABILITY, COMPONENTS, COVERAGE_KEY, FILES  # noqa: E402
from hermeneia.workspace.restore import RestoreError, preview_restore, read_bundle, restore_workspace  # noqa: E402
from test_e10_vertical_slice_api import _FakeOllamaClient  # noqa: E402

RESULT_SCHEMA = "hermeneia.blueprint-chain-portability-results/v1"
GENERATED_AT = "2026-10-13T12:00:00+00:00"
WORKSPACE_ID = "synthetic-blueprint-chain-lab"
CHAIN_TABLES = {table for _key, table, _path, _pk, _cols in COMPONENTS}


# ── Synthetic studies (production write boundaries) ──────────────────────────

def _corpus() -> dict:
    return proposal_lab.load()


def _p8_case(corpus: dict, case_id: str) -> dict:
    return next(case for case in corpus["cases"] if case["case_id"] == case_id)


def _steward_basis(ws) -> None:
    for op in ({"op": "upload", "doc": "A"},
               {"op": "save_perspective", "key": "P1", "label": "Light and vigilance", "purpose": "Read light as watchfulness.",
                "questions": ["Who is the lamp for?"]},
               {"op": "steward_interpretation", "key": "S1", "perspective": "P1", "doc": "A", "sentence": 1,
                "text": "The burning lamp marks a vigil no one admits to keeping."},
               {"op": "ratify_blueprint_exact", "key": "BP1", "blueprint": {
                   "title": "The unasked lamp", "thesis": "The lamp records a vigil the town declines to name.",
                   "sections": [{"claim": "The lamp burns without explanation.", "observations": ["A:1", "A:6"],
                                 "interpretations": ["I:S1"]}]}}):
        ws.apply(op)


def _accept_p8(ws, corpus, case_id: str, decision: dict) -> None:
    case = _p8_case(corpus, case_id)
    for op in case["setup"]:
        ws.apply(op)
    response, _basis = proposal_lab.propose(ws, case["generate"], case["generate"]["script"], corpus["extraction_model"])
    candidate = lab._ok(response)
    lab._ok(proposal_lab.decide(ws, candidate, decision))


def build_l1(ws, corpus):
    ws.apply({"op": "upload", "doc": "A"})


def build_l2(ws, corpus):
    _steward_basis(ws)


def build_l3(ws, corpus):
    ws.apply({"op": "upload", "doc": "A"})
    for key, sentence in (("M1", 1), ("M2", 2), ("M3", 3)):
        ws.apply({"op": "model_proposal", "key": key, "doc": "A", "sentence": sentence})
    ws.apply({"op": "accept_proposal", "proposal": "M1", "rationale": "Consistent with the passage."})
    lab._ok(ws.base.post(f"/api/e10/proposals/{ws.proposals['M3']}/reject", json={"comment": "Not supported by the passage."}))


def build_l4(ws, corpus):
    _steward_basis(ws)
    ws.apply({"op": "legacy_revise", "predecessor": "BP1", "reason": "Narrow the claim to the evidence.", "blueprint": {
        "title": "The unasked lamp", "thesis": "The lamp records a vigil.",
        "sections": [{"claim": "The lamp burns through the night.", "observations": ["A:1"], "interpretations": []}]}})


def build_l5(ws, corpus):
    _accept_p8(ws, corpus, "P05_exact_accept", {"decision": "accept"})


def build_l6(ws, corpus):
    case = _p8_case(corpus, "P10_revision_with_new_evidence")
    for op in case["setup"]:
        ws.apply(op)
    response, _basis = proposal_lab.propose(ws, case["generate"], case["generate"]["script"], corpus["extraction_model"])
    candidate = lab._ok(response)
    lab._ok(proposal_lab.decide(ws, candidate, {"decision": "edit_and_accept", "reason": "The steward narrows the revision.",
                                                "edit": {"title": "A steward-edited successor"}}))


def build_l7(ws, corpus):
    ws.apply({"op": "upload", "doc": "A"})
    architect = SimpleNamespace(render=lambda _prompt: json.dumps({
        "title": "Legacy generated", "thesis": "A legacy direct write.",
        "sections": [{"claim": "The lamp burns.", "obs_refs": ["OBS-1"], "interp_refs": []}]}))
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=architect):
        lab._ok(ws.base.post("/api/architect/generate", json={"directive": "Build from the evidence.", "provider": "fake"}))
    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
        "title": "Legacy extracted", "thesis": "A legacy extraction save.", "sections": [{"claim": "An extracted claim."}]})))])
    extractor = SimpleNamespace(_model="fake", _client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **_k: reply))))
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=extractor):
        lab._ok(ws.base.post("/api/pipeline/extract-blueprint", json={"text": "A source.", "provider": "fake", "save": True}))


def build_l8(ws, corpus):
    _steward_basis(ws)
    ws.apply({"op": "upload", "doc": "B"})
    ws.apply({"op": "exclude_document", "doc": "A"})


LAWFUL = (
    ("L1_empty_chain", build_l1),
    ("L2_steward_interpretation_and_ratified_blueprint", build_l2),
    ("L3_e10_proposals_accepted_pending_rejected", build_l3),
    ("L4_blueprint_revision", build_l4),
    ("L5_p8_exact_acceptance", build_l5),
    ("L6_p8_edit_and_accept_revision", build_l6),
    ("L7_legacy_ai_generated_and_extracted_rows", build_l7),
    ("L8_chain_citing_an_excluded_document", build_l8),
)


# ── Observation helpers ──────────────────────────────────────────────────────

def _ro(db: Path) -> sqlite3.Connection:
    return lab._read_only(db)


def chain_rows(db: Path) -> dict[str, list[dict]]:
    conn = _ro(db)
    try:
        out = {}
        for key, table, _path, pk, _cols in COMPONENTS:
            where = (" WHERE old_id IN (SELECT id FROM narrative_blueprints) AND new_id IN (SELECT id FROM narrative_blueprints)"
                     if table == "supersession_relations" else "")
            cursor = conn.execute(f'SELECT * FROM "{table}"{where} ORDER BY {", ".join(pk)}')
            names = [c[0] for c in cursor.description]
            out[key] = [dict(zip(names, row)) for row in cursor.fetchall()]
        return out
    finally:
        conn.close()


def lineage(db: Path) -> dict:
    conn = _ro(db)
    try:
        return project_study_lineage(conn)
    finally:
        conn.close()


def chain_items(projection: dict) -> list[dict]:
    return sorted((item for item in projection["items"] if item["record"]["table"] in CHAIN_TABLES),
                  key=lambda item: json.dumps(item, sort_keys=True, default=str))


def capability_decisions(projection: dict) -> list:
    return [(row["capability_id"], row["availability"], row["status"]) for row in evaluate_capabilities(projection)["capabilities"]]


def receipt_verdicts(db: Path) -> dict:
    conn = _ro(db)
    try:
        return {rid: verify_receipt(conn, rid) for (rid,) in conn.execute("SELECT id FROM blueprint_proposal_acceptances ORDER BY id")}
    finally:
        conn.close()


def export(db: Path, out: Path, *, blueprint_chain: bool = True) -> dict:
    return export_workspace_bundle(db, out, generated_at=GENERATED_AT, workspace_id=WORKSPACE_ID, blueprint_chain=blueprint_chain)


def _bundle_bytes(path: Path) -> dict[str, bytes]:
    return {str(p.relative_to(path)): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


def _summarize_lineage(projection: dict) -> dict:
    counts: dict[str, int] = {}
    for item in chain_items(projection):
        key = f"{item['record']['table']}|{item['event']}|{item['authorship']}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


# ── Cases ────────────────────────────────────────────────────────────────────

def run_lawful(case_id: str, builder, workdir: Path) -> dict:
    corpus = _corpus()
    ws = proposal_lab.Workspace(corpus, workdir / "source")
    builder(ws, corpus)
    source = ws.db
    before = lab._logical_digest(source)
    manifest = export(source, workdir / "bundle-a")
    export(source, workdir / "bundle-b")
    preview = preview_restore(workdir / "restored" / "workspace.db", workdir / "bundle-a")
    result = restore_workspace(workdir / "restored" / "workspace.db", workdir / "bundle-a")
    restored = workdir / "restored" / "workspace.db"
    source_lineage, restored_lineage = lineage(source), lineage(restored)
    source_rows = chain_rows(source)
    checks = {
        "export_deterministic": _bundle_bytes(workdir / "bundle-a") == _bundle_bytes(workdir / "bundle-b"),
        "source_unchanged_by_export": lab._logical_digest(source) == before,
        "capability_declared": CAPABILITY in manifest.get("required_capabilities", []) and "declared_unsupported" not in manifest,
        "coverage_covered": (preview["coverage"][COVERAGE_KEY]["status"] == result["coverage"][COVERAGE_KEY]["status"] == "covered"
                             and preview["coverage"]["blueprint_proposal_acceptances"]["status"] == "covered"),
        "counts_declared": all(manifest["counts"][key] == len(rows) for key, rows in source_rows.items()),
        "rows_identical": chain_rows(restored) == source_rows,
        "lineage_chain_items_identical": chain_items(restored_lineage) == chain_items(source_lineage),
        "capability_decisions_identical": capability_decisions(restored_lineage) == capability_decisions(source_lineage),
        "receipt_verdicts_identical": receipt_verdicts(restored) == receipt_verdicts(source),
    }
    return {"case_id": case_id, "kind": "lawful", "checks": checks,
            "rows": {key: len(rows) for key, rows in source_rows.items()},
            "blueprint_sources": sorted(row["source"] for row in source_rows["narrative_blueprints"]),
            "lineage_chain": _summarize_lineage(source_lineage),
            "receipt_verdicts": sorted(json.dumps(v, sort_keys=True) for v in receipt_verdicts(source).values())}


def run_legacy_shape(workdir: Path) -> dict:
    """L9: an export with the chain gate off is a WBS 1.x-shaped bundle; it restores with the chain unsupported."""
    corpus = _corpus()
    ws = proposal_lab.Workspace(corpus, workdir / "source")
    build_l5(ws, corpus)
    manifest = export(ws.db, workdir / "bundle", blueprint_chain=False)
    result = restore_workspace(workdir / "restored" / "workspace.db", workdir / "bundle")
    restored_rows = chain_rows(workdir / "restored" / "workspace.db")
    checks = {
        "no_chain_component": (CAPABILITY not in manifest.get("required_capabilities", []) and "declared_unsupported" not in manifest
                               and not any((workdir / "bundle" / path).exists() for path in FILES.values())),
        "coverage_unsupported": (result["coverage"][COVERAGE_KEY]["status"] == "unsupported"
                                 and result["coverage"]["blueprint_proposal_acceptances"]["status"] == "unsupported"),
        "nothing_reconstructed": all(not rows for rows in restored_rows.values()),
    }
    return {"case_id": "L9_gate_off_bundle_is_wbs_1x_shaped", "kind": "lawful", "checks": checks}


def _tamper_receipt(db: Path) -> None:
    conn = sqlite3.connect(db)
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='blueprint_proposal_acceptances'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    (stored,), = conn.execute("SELECT receipt_json FROM blueprint_proposal_acceptances").fetchall()
    conn.execute("UPDATE blueprint_proposal_acceptances SET receipt_json = ?", (stored.replace("vigil", "Vigil", 1),))
    conn.commit()
    conn.close()


def _dangling_link(db: Path) -> None:
    conn = sqlite3.connect(db)
    (blueprint_id,), = conn.execute("SELECT id FROM narrative_blueprints").fetchall()
    conn.execute("INSERT INTO blueprint_observation_links (blueprint_id, observation_id) VALUES (?, 'missing-observation')", (blueprint_id,))
    conn.commit()
    conn.close()


def _interpretation_edge(db: Path) -> None:
    conn = sqlite3.connect(db)
    (interpretation_id,), = conn.execute("SELECT id FROM interpretations").fetchall()
    (blueprint_id,), = conn.execute("SELECT id FROM narrative_blueprints").fetchall()
    conn.execute("INSERT INTO supersession_relations (old_id, new_id, reason, ratified_at) VALUES (?, ?, 'out of scope', ?)",
                 (interpretation_id, blueprint_id, GENERATED_AT))
    conn.commit()
    conn.close()


EXPORT_ADVERSARIAL = (
    ("A1_tampered_receipt", build_l5, _tamper_receipt, "CHAIN_INTEGRITY_INVALID"),
    ("A2_dangling_blueprint_link", build_l2, _dangling_link, "CHAIN_CLOSURE_INCOMPLETE"),
    ("A3_interpretation_to_blueprint_edge", build_l2, _interpretation_edge, "CHAIN_SUPERSESSION_OUT_OF_SCOPE"),
)


def run_export_adversarial(case_id, builder, tamper, code, workdir: Path) -> dict:
    corpus = _corpus()
    ws = proposal_lab.Workspace(corpus, workdir / "source")
    builder(ws, corpus)
    tamper(ws.db)
    manifest = export(ws.db, workdir / "bundle")
    result = restore_workspace(workdir / "restored" / "workspace.db", workdir / "bundle")
    declaration = manifest.get("declared_unsupported", {}).get(CAPABILITY, {})
    checks = {
        "declared_unsupported_with_code": declaration.get("reason_code") == code and CAPABILITY not in manifest.get("required_capabilities", []),
        "no_chain_file_written": not any((workdir / "bundle" / path).exists() for path in FILES.values()),
        "rest_of_workspace_exported": manifest["counts"]["observations"] > 0,
        "restore_reports_the_reason": (result["coverage"][COVERAGE_KEY]["status"] == "unsupported"
                                       and result["coverage"][COVERAGE_KEY].get("reason_code") == code),
        "nothing_reconstructed": all(not rows for rows in chain_rows(workdir / "restored" / "workspace.db").values()),
    }
    return {"case_id": case_id, "kind": "export_adversarial", "expected_code": code, "checks": checks}


def _rewrite(bundle: Path, path: str, rows) -> None:
    data = (json.dumps(rows, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (bundle / path).write_bytes(data)
    manifest = json.loads((bundle / "manifest.json").read_text())
    for entry in manifest["files"]:
        if entry["path"] == path:
            entry["sha256"] = hashlib.sha256(data).hexdigest()
    (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def _manifest(bundle: Path, edit) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text())
    edit(manifest)
    (bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")


def _load(bundle: Path, path: str):
    return json.loads((bundle / path).read_text())


def _drop_blueprint_keep_plan(bundle: Path) -> None:
    blueprints = _load(bundle, FILES["narrative_blueprints"])
    _rewrite(bundle, FILES["narrative_blueprints"], blueprints[1:])
    _manifest(bundle, lambda m: m["counts"].__setitem__("narrative_blueprints", len(blueprints) - 1))


def _drop_plan_keep_paragraphs(bundle: Path) -> None:
    plans = _load(bundle, FILES["architect_plans"])
    _rewrite(bundle, FILES["architect_plans"], plans[1:])
    _manifest(bundle, lambda m: m["counts"].__setitem__("architect_plans", len(plans) - 1))


def _duplicate_plan(bundle: Path) -> None:
    plans = _load(bundle, FILES["architect_plans"])
    _rewrite(bundle, FILES["architect_plans"], plans + plans[:1])
    _manifest(bundle, lambda m: m["counts"].__setitem__("architect_plans", len(plans) + 1))


def _unknown_column(bundle: Path) -> None:
    blueprints = _load(bundle, FILES["narrative_blueprints"])
    blueprints[0]["approved_by"] = "nobody"
    _rewrite(bundle, FILES["narrative_blueprints"], blueprints)


RESTORE_ADVERSARIAL = (
    ("A4_chain_file_edited_without_rehash",
     lambda b: (b / FILES["narrative_blueprints"]).write_bytes((b / FILES["narrative_blueprints"]).read_bytes().replace(b"lamp", b"Lamp", 1))),
    ("A5_rehashed_bundle_with_plan_whose_blueprint_was_removed", _drop_blueprint_keep_plan),
    ("A5b_rehashed_bundle_with_paragraphs_and_receipt_whose_plan_was_removed", _drop_plan_keep_paragraphs),
    ("A6_capability_declared_file_missing", lambda b: (b / FILES["architect_plans"]).unlink()),
    ("A7_file_present_without_capability",
     lambda b: _manifest(b, lambda m: m.__setitem__("required_capabilities", [c for c in m["required_capabilities"] if c != CAPABILITY]))),
    ("A8_count_mismatch", lambda b: _manifest(b, lambda m: m["counts"].__setitem__("interpretations", 99))),
    ("A9_duplicate_primary_key", _duplicate_plan),
    ("A10_unknown_column", _unknown_column),
    ("A11_declared_unsupported_and_chain_files",
     lambda b: _manifest(b, lambda m: m.__setitem__("declared_unsupported", {CAPABILITY: {"reason_code": "CHAIN_CLOSURE_INCOMPLETE"}}))),
)


def run_restore_adversarial(case_id: str, mutate, bundle_source: Path, workdir: Path) -> dict:
    bundle = workdir / "bundle"
    shutil.copytree(bundle_source, bundle)
    mutate(bundle)
    target = workdir / "restored" / "workspace.db"
    refused, message = False, ""
    try:
        restore_workspace(target, bundle)
    except RestoreError as exc:
        refused, message = True, str(exc)
    rows = chain_rows(target) if target.exists() else {}
    stage = "read_bundle" if refused and _read_refuses(bundle) else "restore_transaction" if refused else None
    return {"case_id": case_id, "kind": "restore_adversarial",
            "checks": {"refused": refused, "nothing_restored": all(not r for r in rows.values())},
            "refused_at": stage, "message_names_the_chain": "chain" in message.lower() or "blueprint" in message.lower()}


def _read_refuses(bundle: Path) -> bool:
    try:
        read_bundle(bundle)
    except RestoreError:
        return True
    return False


def run_occupied_target(bundle_source: Path, workdir: Path) -> dict:
    target = workdir / "occupied" / "workspace.db"
    restore_workspace(target, bundle_source)
    before = lab._logical_digest(target)
    refused, message = False, ""
    try:
        restore_workspace(target, bundle_source, overwrite=True)
    except RestoreError as exc:
        refused, message = True, str(exc)
    return {"case_id": "A12_covered_chain_into_occupied_target_with_overwrite", "kind": "restore_adversarial",
            "checks": {"refused": refused, "occupied_target_unchanged": lab._logical_digest(target) == before},
            "refused_at": "occupied_target", "message_names_the_chain": "blueprint-chain" in message.lower()}


def run() -> dict:
    records = []

    def isolated(fn, *args):
        with tempfile.TemporaryDirectory(prefix="p10-chain-") as tmp:
            workdir = Path(tmp)
            with lab.isolated(workdir):
                _FakeOllamaClient.models = [_corpus()["extraction_model"]]
                return fn(*args, workdir)

    for case_id, builder in LAWFUL:
        records.append(isolated(lambda cid, b, w: run_lawful(cid, b, w), case_id, builder))
    records.append(isolated(lambda w: run_legacy_shape(w)))
    for case_id, builder, tamper, code in EXPORT_ADVERSARIAL:
        records.append(isolated(lambda cid, b, t, c, w: run_export_adversarial(cid, b, t, c, w), case_id, builder, tamper, code))
    with tempfile.TemporaryDirectory(prefix="p10-chain-bundle-") as tmp:
        base = Path(tmp)
        with lab.isolated(base):
            corpus = _corpus()
            _FakeOllamaClient.models = [corpus["extraction_model"]]
            ws = proposal_lab.Workspace(corpus, base / "source")
            build_l6(ws, corpus)
            export(ws.db, base / "bundle")
        for case_id, mutate in RESTORE_ADVERSARIAL:
            records.append(isolated(lambda cid, m, w: run_restore_adversarial(cid, m, base / "bundle", w), case_id, mutate))
        records.append(isolated(lambda w: run_occupied_target(base / "bundle", w)))
    aggregate = {kind: {"cases": sum(1 for r in records if r["kind"] == kind),
                        "all_checks_passed": sum(1 for r in records if r["kind"] == kind and all(r["checks"].values()))}
                 for kind in ("lawful", "export_adversarial", "restore_adversarial")}
    return {"schema": RESULT_SCHEMA, "contract": "docs/design/blueprint-chain-portability-v1.md", "capability": CAPABILITY,
            "method": ("synthetic studies built through production write boundaries; exported with the gated chain "
                       "component; restored into fresh targets; in-process fakes; no network, live model or real workspace"),
            "aggregate": aggregate, "cases": records}


def summary_markdown(results: dict) -> str:
    lines = ["# P10 Blueprint dependency chain portability v1 — evaluation summary", "",
             f"Capability `{results['capability']}`. Generated by `tests/blueprint_chain_lab.py`; evaluation data, not study history.", "",
             "| Case | Kind | Outcome | Checks |", "| --- | --- | --- | --- |"]
    for r in results["cases"]:
        passed = f"{sum(1 for v in r['checks'].values() if v)}/{len(r['checks'])}"
        if r["kind"] == "lawful":
            carried = ", ".join(f"{k} {v}" for k, v in r["rows"].items() if v) if "rows" in r else None
            outcome = ("chain unsupported; nothing reconstructed" if carried is None
                       else f"round-trip: {carried}" if carried else "round-trip: empty chain (zero extant records, covered)")
        elif r["kind"] == "export_adversarial":
            outcome = f"declared unsupported `{r['expected_code']}`"
        else:
            outcome = f"refused at {r['refused_at']}"
        lines.append(f"| {r['case_id']} | {r['kind']} | {outcome} | {passed} |")
    lines += ["", "## Aggregate", ""]
    for kind, value in results["aggregate"].items():
        lines.append(f"- {kind}: {value['all_checks_passed']}/{value['cases']} cases pass every check")
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
