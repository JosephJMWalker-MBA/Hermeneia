"""P5 Synthetic Study Laboratory v1 (#215): a deterministic evaluation runner.

Each frozen trajectory is materialized into a disposable synthetic workspace
through existing production write boundaries (the trajectory's one labeled
legacy-shape operation is the only direct SQL). The production Study Lineage
projection, Capability Registry evaluator and Guided Study Cycle then decide
every result from the workspace alone. The trajectory's ``expected`` block is
never passed to production; it is compared afterwards.

This is evaluation data, not study history: no real workspace, no private
text, no provider or model call (in-process fake adapters only, outbound
sockets blocked), no credential store, and nothing outside the disposable
workspaces is written except the explicit ``--write`` result files.

    python3 tests/synthetic_study_lab.py --write research/synthetic_study_lab/v1
    python3 tests/synthetic_study_lab.py --check research/synthetic_study_lab/v1
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import random
import socket
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent
for path in (str(ROOT), str(TESTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

import fitz  # noqa: E402

from hermeneia.capabilities import EVALUATOR_VERSION, evaluate_capabilities, load_capability_registry  # noqa: E402
from hermeneia.guided_study_cycle import GUIDE_VERSION, project_guided_study_cycle  # noqa: E402
from hermeneia.narrative.artist_providers import NullArtistProvider  # noqa: E402
from hermeneia.narrative.provider_registry import ProviderDefinition, ProviderRegistration, ProviderRegistry  # noqa: E402
from hermeneia.storage.hashing import make_interpretation_id  # noqa: E402
from hermeneia.storage.sqlite import SQLiteStore  # noqa: E402
from hermeneia.study_lineage import project_study_lineage  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from test_e10_vertical_slice_api import (  # noqa: E402  (the repository's own lawful P3 run fixtures)
    _CapturingProvider, _FakeOllamaClient, _ollama_registry, _scope_span_locator,
)

FIXTURES = TESTS / "fixtures" / "synthetic_study_lab" / "v1" / "trajectories"
TRAJECTORY_SCHEMA = "hermeneia.synthetic-study-trajectory/v1"
RESULT_SCHEMA = "hermeneia.synthetic-study-lab-results/v1"
POLICY_VERSION = "p5-lab-1.0.0"
CYCLE = ("governing_question", "read_source", "mark_evidence", "record_observation", "preserve_question",
         "organize_evidence", "explore_perspective", "form_interpretation", "challenge_interpretation",
         "review_blueprint", "review_lineage")
AVAILABILITY = {"available", "not_yet_available", "unsupported_due_to_missing_history"}
STATUS = AVAILABILITY | {"already_exercised_under_supported_evidence"}
GUIDE = {"ready", "currently_supported", "historically_exercised", "not_ready", "unknown"}
OPERATIONS = {"upload", "set_governing_question", "mark", "inquiry", "save_perspective", "retain_perspective_run",
              "steward_interpretation", "model_proposal", "accept_proposal", "ratify_blueprint", "exclude_document",
              "legacy_drop_table"}
RUN_MODEL = "qwen2.5:0.5b"
RUN_OUTPUT = "A synthetic Perspective reading produced by an in-process fake adapter.\n"
PROPOSAL_TEXT = "A synthetic model proposal produced by an in-process fake adapter."


class TrajectoryError(ValueError):
    """A fixture violates the trajectory contract or cannot be materialized lawfully."""


# ── Contract ─────────────────────────────────────────────────────────────────

def validate_trajectory(t: dict) -> dict:
    """Strict structural check mirroring trajectory.schema.json (no new dependency)."""
    def require(condition, message):
        if not condition:
            raise TrajectoryError(f"{t.get('trajectory_id', '?')}: {message}")

    fields = {"schema", "trajectory_id", "planned_profile", "fixture_class", "policy", "documents", "operations",
              "current_state", "declared_lineage", "coverage", "edges", "expected"}
    require(isinstance(t, dict) and set(t) == fields, "exact trajectory fields required")
    require(t["schema"] == TRAJECTORY_SCHEMA, "unsupported trajectory schema")
    require(t["fixture_class"] in ("lawful", "lawful_then_legacy_shape"), "unknown fixture class")
    require(t["policy"] == {"trajectory_policy_version": POLICY_VERSION, "registry_version": load_capability_registry()["registry_version"],
                            "evaluator_version": EVALUATOR_VERSION, "guide_version": GUIDE_VERSION},
            "policy versions differ from production; re-freeze deliberately")
    require(set(t["current_state"]) <= {"governing_question", "perspective_available"}, "unsupported current_state input")
    require(all(op.get("op") in OPERATIONS for op in t["operations"]), "unknown operation")
    legacy = [op for op in t["operations"] if op["op"] == "legacy_drop_table"]
    require(bool(legacy) == (t["fixture_class"] == "lawful_then_legacy_shape"), "legacy operations require the legacy fixture class")
    require(all(op.get("label") for op in legacy), "legacy operations must be labeled")
    require(set(t["coverage"]) == {"missing_tables", "missing_columns", "omitted_nonzero"}, "explicit coverage limits required")
    expected = t["expected"]
    require(set(expected) == {"capabilities", "preferred_next", "permitted_next", "must_not_suggest", "reason", "derivation"},
            "exact expected fields required")
    require(list(expected["capabilities"]) == list(CYCLE), "all 11 capabilities in cycle order required")
    for row in expected["capabilities"].values():
        require(set(row) == {"availability", "status", "guide"} and row["availability"] in AVAILABILITY
                and row["status"] in STATUS and row["guide"] in GUIDE, "invalid expected capability state")
    require(expected["preferred_next"] in expected["permitted_next"], "preferred step must be permitted")
    require(not set(expected["permitted_next"]) & set(expected["must_not_suggest"]), "a permitted step cannot be forbidden")
    require(set(expected["permitted_next"]) | set(expected["must_not_suggest"]) <= set(CYCLE), "unknown step")
    return t


def load_trajectories(directory: Path = FIXTURES) -> list[dict]:
    return [validate_trajectory(json.loads(path.read_text())) for path in sorted(directory.glob("*.json"))]


# ── Isolation ────────────────────────────────────────────────────────────────

class _NoCredentials:
    def available(self):
        return False

    def status(self):
        return {"available": False, "backend": "p5-lab.none", "message": "no credential store in the laboratory"}

    def get_password(self, provider_id):
        return None

    def has_password(self, provider_id):
        return False

    def set_password(self, provider_id, secret):
        raise RuntimeError("the laboratory never stores credentials")

    def delete_password(self, provider_id):
        raise RuntimeError("the laboratory never stores credentials")


@contextmanager
def isolated(workdir: Path):
    """No network, no keychain, throwaway connection settings, fake in-process Ollama."""
    saved_env = os.environ.get("HERMENEIA_CONNECTIONS_SETTINGS_PATH")
    saved_ollama = sys.modules.get("ollama")
    saved_connect = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection)

    def blocked(*_args, **_kwargs):
        raise RuntimeError("the synthetic laboratory makes no network connection")

    os.environ["HERMENEIA_CONNECTIONS_SETTINGS_PATH"] = str(workdir / "connections.json")
    socket.socket.connect = socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    _FakeOllamaClient.models = [RUN_MODEL]
    _FakeOllamaClient.error = None
    _FakeOllamaClient.hosts = []
    sys.modules["ollama"] = SimpleNamespace(Client=_FakeOllamaClient)
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = saved_connect
        if saved_env is None:
            os.environ.pop("HERMENEIA_CONNECTIONS_SETTINGS_PATH", None)
        else:
            os.environ["HERMENEIA_CONNECTIONS_SETTINGS_PATH"] = saved_env
        if saved_ollama is None:
            sys.modules.pop("ollama", None)
        else:
            sys.modules["ollama"] = saved_ollama


class _FakeProposalAdapter:
    """OpenAI-shaped in-process adapter for E10 proposals; no network, no model."""

    def __init__(self, model=None, **_kwargs):
        self._model = model or "synthetic-model"
        reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=PROPOSAL_TEXT))])
        self._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_k: reply)))

    def execution_config(self):
        return {"provider": "openai", "model_id": "synthetic-proposal-model"}


def _proposal_registry() -> ProviderRegistry:
    def definition(identifier):
        return ProviderDefinition(id=identifier, display_name=identifier, provider_type="artist", enabled=True,
                                  capabilities=("text",), local_or_remote="remote", default_model="gpt-4o")
    return ProviderRegistry((ProviderRegistration(definition("openai"), _FakeProposalAdapter),
                             ProviderRegistration(definition("null"), NullArtistProvider)))


# ── Materialization through production boundaries ───────────────────────────

def _pdf(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + 20 * index), line)
    doc.set_metadata({"creationDate": "D:20260101000000Z", "modDate": "D:20260101000000Z", "producer": "p5-lab"})
    return doc.tobytes(no_new_id=True)


def _ok(response, expected=(200, 201)):
    if response.status_code not in expected:
        raise TrajectoryError(f"production boundary refused a lawful operation: {response.status_code} {response.get_json(silent=True)}")
    return response.get_json()


def scramble(trajectory: dict) -> dict:
    """Same structure, neutral text and labels: decisions must not depend on wording or names."""
    t = deepcopy(trajectory)
    t["trajectory_id"], t["planned_profile"], t["edges"] = "T0_scrambled", "scrambled", []
    t["documents"] = {doc: [f"Neutral sentence {doc}{i}." for i in range(1, len(lines) + 1)] for doc, lines in t["documents"].items()}
    buckets: dict[str, str] = {}
    for index, op in enumerate(t["operations"], 1):
        for field in ("text", "question", "label", "purpose", "rationale", "title", "thesis"):
            if field in op:
                op[field] = f"Neutral {field} {index}?" if field == "question" else f"Neutral {field} {index}."
        if "questions" in op:
            op["questions"] = [f"Neutral prompt {index}.{n}?" for n in range(len(op["questions"]))]
        for field in ("theme_bucket", "evidence_bucket"):
            if op.get(field):
                op[field] = buckets.setdefault(op[field], f"group-{len(buckets) + 1}")
        for section in op.get("sections", []):
            section["claim"] = f"Neutral claim {index}."
    if t["current_state"].get("governing_question"):
        t["current_state"]["governing_question"] = "Neutral current question?"
    return t


def materialize(trajectory: dict, workdir: Path) -> Path:
    """Build the disposable synthetic workspace; returns its database path."""
    db = workdir / "ws" / "workspace.db"
    SQLiteStore(db).close()
    base = create_app(db_path=db, credential_store=_NoCredentials()).test_client()
    observations: dict[tuple[str, int], str] = {}
    extractions: dict[tuple[str, int], dict] = {}
    documents: dict[str, str] = {}
    perspectives: dict[str, dict] = {}
    interpretations: dict[str, str] = {}
    proposals: dict[str, str] = {}

    def obs(op):
        return observations[(op["doc"], op["sentence"])]

    for op in trajectory["operations"]:
        kind = op["op"]
        if kind == "upload":
            lines = trajectory["documents"][op["doc"]]
            body = _ok(base.post("/api/upload", data={"file": (io.BytesIO(_pdf(lines)), f"synthetic-{op['doc']}.pdf")},
                                 content_type="multipart/form-data"))
            documents[op["doc"]] = body["document_id"]
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, source_extraction_id FROM observations WHERE source_document_id = ? "
                                "ORDER BY page, paragraph, sentence", (body["document_id"],)).fetchall()
            if len(rows) != len(lines):
                raise TrajectoryError(f"expected one Observation per line for {op['doc']}, got {len(rows)}")
            for index, row in enumerate(rows, 1):
                observations[(op["doc"], index)] = row["id"]
                extraction = conn.execute("SELECT id, page, raw_text, source_locator FROM source_extractions WHERE id = ?",
                                          (row["source_extraction_id"],)).fetchone()
                extractions[(op["doc"], index)] = dict(extraction)
            conn.close()
        elif kind == "set_governing_question":
            _ok(base.put("/api/investigation", json={"thesis": op["text"]}))
        elif kind == "mark":
            text = trajectory["documents"][op["doc"]][op["sentence"] - 1]
            _ok(base.post("/api/reader/highlights", json={
                "source_document_id": documents[op["doc"]], "selected_text": text, "page": 1,
                "observation_id": obs(op), "theme_bucket": op.get("theme_bucket"), "evidence_bucket": op.get("evidence_bucket")}))
        elif kind == "inquiry":
            _ok(base.post(f"/api/observations/{obs(op)}/inquiry", json={"question_text": op["question"]}))
        elif kind == "save_perspective":
            saved = _ok(base.post("/api/perspective/saved", json={"perspective_draft": {
                "label": op["label"], "purpose": op["purpose"], "questions": op["questions"]}, "declared_by": "Synthetic lab steward"}))
            perspectives[op["key"]] = saved
        elif kind == "retain_perspective_run":
            extraction = extractions[(op["doc"], op["sentence"])]
            text = extraction["raw_text"].strip()
            block = int(extraction["source_locator"].rsplit(":", 1)[1])
            scope = {"primary": {"kind": "reader_selection", "text": text, "source_document_id": documents[op["doc"]],
                                 "page": extraction["page"],
                                 "locator": _scope_span_locator(page=extraction["page"], start_block=block, end_block=block,
                                                                end_offset=len(text), locators=[extraction["source_locator"]],
                                                                extraction_ids=[extraction["id"]]),
                                 "source_locators": [extraction["source_locator"]], "extraction_ids": [extraction["id"]]},
                     "included": {"governing_question": False, "current_page": False}}
            frame = op["perspective"]
            selection = ({"perspective_id": None, "saved_perspective_id": perspectives[frame["saved"]]["id"]}
                         if isinstance(frame, dict) else {"perspective_id": frame})
            _CapturingProvider.render_responses = [RUN_OUTPUT] * 8
            runner = create_app(db_path=db, provider_registry=_ollama_registry(), credential_store=_NoCredentials()).test_client()
            run = _ok(runner.post("/api/perspective/run", json={"question": op["question"], "model": RUN_MODEL,
                                                                 "scope": scope, **selection}))
            _ok(runner.post(f"/api/perspective/executions/{run['run_id']}/retain", json={"decision": "retain"}))
        elif kind == "steward_interpretation":
            saved = perspectives[op["perspective"]]
            conn = sqlite3.connect(db)
            name = conn.execute("SELECT name FROM perspectives WHERE id = ?", (saved["id"],)).fetchone()[0]
            conn.close()
            identifier = make_interpretation_id(obs(op), name, op["text"])
            store = SQLiteStore(db)
            try:
                store.insert_interpretation({
                    "id": identifier, "observation_id": obs(op), "perspective": name, "perspective_id": saved["id"],
                    "text": op["text"], "evidential_status": "speculative", "evidence_observation_ids": json.dumps([obs(op)]),
                    "confidence": "human", "source": "steward-authored", "created_at": "2026-10-07T12:00:00+00:00"})
            finally:
                store.close()
            interpretations[op["key"]] = identifier
        elif kind == "model_proposal":
            e10 = create_app(db_path=db, provider_registry=_proposal_registry(), credential_store=_NoCredentials()).test_client()
            body = _ok(e10.post("/api/e10/interpretations/generate", json={"observation_id": obs(op), "participants": ["gpt"]}))
            proposals[op["key"]] = body["proposals"][0]["id"]
        elif kind == "accept_proposal":
            body = _ok(base.post(f"/api/e10/proposals/{proposals[op['proposal']]}/accept", json={"comment": op["rationale"]}))
            interpretations[op["proposal"]] = body["interpretation"]["id"]
        elif kind == "ratify_blueprint":
            sections = [{"claim": section["claim"],
                         "supporting_observations": [observations[(ref["doc"], ref["sentence"])] for ref in section["observations"]],
                         "supporting_interpretations": [interpretations[key] for key in section.get("interpretations", [])]}
                        for section in op["sections"]]
            _ok(base.post("/api/pipeline/ratify-blueprint", json={"candidate": {
                "title": op["title"], "thesis": op["thesis"], "sections": sections}}))
        elif kind == "exclude_document":
            _ok(base.patch(f"/api/documents/{documents[op['doc']]}/scope", json={"source_role": "reference"}))
            _ok(base.patch(f"/api/documents/{documents[op['doc']]}/scope", json={"excluded": True}))
        elif kind == "legacy_drop_table":
            conn = sqlite3.connect(db)
            conn.execute(f'DROP TABLE "{op["table"]}"')
            conn.commit()
            conn.close()
    return db


# ── Production evaluation (the only decision-maker) ─────────────────────────

def _read_only(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def production_lineage(db: Path) -> dict:
    conn = _read_only(db)
    try:
        return project_study_lineage(conn)
    finally:
        conn.close()


def production_decide(lineage: dict, current_state: dict) -> tuple[dict, dict]:
    """Production P1 + P2 over the snapshot and declared current state only."""
    return (evaluate_capabilities(lineage, current_state=deepcopy(current_state)),
            project_guided_study_cycle(lineage, current_state=deepcopy(current_state)))


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def decisions(evaluation: dict, guide: dict) -> dict:
    steps = {step["capability_id"]: step["status"] for step in guide["steps"]}
    return {"capabilities": {row["capability_id"]: {
                "availability": row["availability"], "availability_reason_code": row["availability_reason_code"],
                "status": row["status"], "reason_code": row["reason_code"], "guide": steps[row["capability_id"]]}
                for row in sorted(evaluation["capabilities"], key=lambda r: CYCLE.index(r["capability_id"]))},
            "recommended_step_id": guide["recommended_step_id"], "recommendation_reason": guide["recommendation_reason"]}


def lineage_summary(lineage: dict) -> dict:
    counts: dict[str, int] = {}
    for item in lineage["items"]:
        key = f"{item['record']['table']}|{item['event']}|{item['authorship']}"
        counts[key] = counts.get(key, 0) + 1
    coverage = lineage["coverage"]
    return {"declared_lineage": dict(sorted(counts.items())),
            "coverage": {"missing_tables": sorted(coverage["missing_tables"]),
                         "missing_columns": {k: sorted(v) for k, v in sorted(coverage["missing_columns"].items())},
                         "omitted_nonzero": {k: v for k, v in sorted(coverage["omitted"].items()) if v}}}


def _logical_digest(db: Path) -> str:
    conn = _read_only(db)
    try:
        return hashlib.sha256("\n".join(conn.iterdump()).encode("utf-8")).hexdigest()
    finally:
        conn.close()


def _reverse_storage_copy(source: Path, target: Path) -> None:
    """Same rows and schema, every table's rows stored in reverse physical order."""
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    schema = src.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'").fetchall()
    for kind, _name, sql in schema:
        if kind == "table":
            dst.execute(sql)
    for kind, name, _sql in schema:
        if kind == "table":
            columns = [c[1] for c in src.execute(f'PRAGMA table_info("{name}")')]
            rows = src.execute(f'SELECT * FROM "{name}" ORDER BY rowid DESC').fetchall()
            if rows:
                dst.executemany(f'INSERT INTO "{name}" ({", ".join(chr(34) + c + chr(34) for c in columns)}) '
                                f'VALUES ({", ".join("?" for _ in columns)})', rows)
    for kind, _name, sql in schema:
        if kind in ("index", "trigger", "view"):
            dst.execute(sql)
    dst.commit()
    src.close()
    dst.close()


def _record_refs(value):
    if isinstance(value, dict):
        if isinstance(value.get("record"), dict) and "table" in value["record"]:
            yield value
        elif value.get("basis") == "current_state":
            yield value
        for item in value.values():
            yield from _record_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _record_refs(item)


def evaluate_trajectory(trajectory: dict, workdir: Path) -> dict:
    current_state = trajectory["current_state"]
    expected = trajectory["expected"]
    with isolated(workdir):
        db = materialize(trajectory, workdir / "primary")
        before = _logical_digest(db)
        lineage = production_lineage(db)
        evaluation, guide = production_decide(lineage, current_state)
        again_evaluation, again_guide = production_decide(production_lineage(db), current_state)
        after = _logical_digest(db)
        produced = decisions(evaluation, guide)

        independent = decisions(*production_decide(production_lineage(materialize(trajectory, workdir / "independent")), current_state))
        rng = random.Random(trajectory["trajectory_id"])
        permuted = deepcopy(lineage)
        permuted["items"].reverse()
        shuffled = deepcopy(lineage)
        rng.shuffle(shuffled["items"])
        permutation_equal = all(canonical(production_decide(variant, current_state)) == canonical((evaluation, guide))
                                for variant in (permuted, shuffled))
        reversed_db = workdir / "reversed.db"
        _reverse_storage_copy(db, reversed_db)
        reversed_lineage = production_lineage(reversed_db)
        storage_equal = (decisions(*production_decide(reversed_lineage, current_state)) == produced
                         and lineage_summary(reversed_lineage) == lineage_summary(lineage))
        scrambled = scramble(trajectory)
        label_free = decisions(*production_decide(production_lineage(materialize(scrambled, workdir / "scrambled")),
                                                  scrambled["current_state"])) == produced

    summary = lineage_summary(lineage)
    items = {(canonical(item["record"]), item["event"]) for item in lineage["items"]}
    refs = list(_record_refs(evaluation)) + list(_record_refs(guide))
    unresolved = [ref for ref in refs if "record" in ref and (canonical(ref["record"]), ref.get("event", ref.get("basis"))) not in items]
    undeclared_state = [ref for ref in refs if ref.get("basis") == "current_state" and ref.get("input") not in current_state]

    cells = [(capability, field) for capability in CYCLE for field in ("availability", "status", "guide")]
    mismatches = [{"capability_id": c, "field": f, "expected": expected["capabilities"][c][f], "production": produced["capabilities"][c][f]}
                  for c, f in cells if expected["capabilities"][c][f] != produced["capabilities"][c][f]]
    distinction_cells = [(c, f) for c in CYCLE for f in ("availability", "status")
                         if expected["capabilities"][c][f] in ("not_yet_available", "unsupported_due_to_missing_history")]
    recommended = produced["recommended_step_id"]
    metrics = {
        "capability_state": {"correct": len(cells) - len(mismatches), "total": len(cells)},
        "unsupported_vs_not_yet": {"correct": sum(expected["capabilities"][c][f] == produced["capabilities"][c][f] for c, f in distinction_cells),
                                   "total": len(distinction_cells)},
        "next_step_preferred": recommended == expected["preferred_next"],
        "next_step_permitted": recommended in expected["permitted_next"],
        "forbidden_suggestion": recommended in expected["must_not_suggest"],
        "repeatable_same_workspace": canonical((evaluation, guide)) == canonical((again_evaluation, again_guide)),
        "repeatable_independent_materialization": independent == produced,
        "invariant_to_item_order": permutation_equal,
        "invariant_to_storage_order": storage_equal,
        "no_manufactured_history": {
            "workspace_unchanged_by_evaluation": before == after,
            "lineage_matches_declared": summary["declared_lineage"] == trajectory["declared_lineage"],
            "coverage_matches_declared": summary["coverage"] == trajectory["coverage"],
            "all_references_resolve": not unresolved and not undeclared_state,
        },
        "invariant_to_labels_and_wording": label_free,
    }
    return {"trajectory_id": trajectory["trajectory_id"], "planned_profile": trajectory["planned_profile"],
            "fixture_class": trajectory["fixture_class"], "edges": trajectory["edges"],
            "materialized": summary, "production": produced,
            "expected": {"capabilities": expected["capabilities"], "preferred_next": expected["preferred_next"],
                         "permitted_next": expected["permitted_next"], "must_not_suggest": expected["must_not_suggest"]},
            "mismatches": mismatches, "metrics": metrics}


def run(directory: Path = FIXTURES) -> dict:
    trajectories = load_trajectories(directory)
    registry = load_capability_registry()
    results = []
    for trajectory in trajectories:
        with tempfile.TemporaryDirectory(prefix="p5-lab-") as tmp:
            results.append(evaluate_trajectory(trajectory, Path(tmp)))
    n = len(results)

    def share(predicate):
        return {"passed": sum(1 for r in results if predicate(r["metrics"])), "total": n}

    aggregate = {
        "capability_state": {"correct": sum(r["metrics"]["capability_state"]["correct"] for r in results),
                             "total": sum(r["metrics"]["capability_state"]["total"] for r in results)},
        "unsupported_vs_not_yet": {"correct": sum(r["metrics"]["unsupported_vs_not_yet"]["correct"] for r in results),
                                   "total": sum(r["metrics"]["unsupported_vs_not_yet"]["total"] for r in results)},
        "next_step_preferred": share(lambda m: m["next_step_preferred"]),
        "next_step_permitted": share(lambda m: m["next_step_permitted"]),
        "forbidden_suggestions": {"count": sum(1 for r in results if r["metrics"]["forbidden_suggestion"]), "total": n},
        "repeatable": share(lambda m: m["repeatable_same_workspace"] and m["repeatable_independent_materialization"]),
        "order_invariant": share(lambda m: m["invariant_to_item_order"] and m["invariant_to_storage_order"]),
        "no_manufactured_history": share(lambda m: all(m["no_manufactured_history"].values())),
        "label_invariant": share(lambda m: m["invariant_to_labels_and_wording"]),
    }
    return {"schema": RESULT_SCHEMA, "trajectory_schema": TRAJECTORY_SCHEMA, "policy_version": POLICY_VERSION,
            "production": {"registry_version": registry["registry_version"], "evaluator_version": EVALUATOR_VERSION,
                           # As reported by production itself, not recomputed here.
                           "registry_sha256": evaluate_capabilities(project_study_lineage(sqlite3.connect(":memory:")))["registry_sha256"],
                           "guide_version": GUIDE_VERSION},
            "boundaries": "Synthetic disposable workspaces; production write boundaries plus one labeled legacy-shape operation; "
                          "in-process fake adapters; no network, provider, credential store, real workspace or private text; "
                          "evaluation data, not study history.",
            "aggregate": aggregate, "trajectories": results}


def summary_markdown(results: dict) -> str:
    p = results["production"]
    lines = [
        "# P5 Synthetic Study Laboratory v1 — result matrix",
        "",
        f"Generated by `tests/synthetic_study_lab.py` from the frozen `{results['trajectory_schema']}` fixtures. "
        f"Production: registry `{p['registry_version']}` (`{p['registry_sha256'][:12]}…`), evaluator `{p['evaluator_version']}`, "
        f"guide `{p['guide_version']}`; policy `{results['policy_version']}`. Evaluation data, not study history.",
        "",
        "| Trajectory | Fixture | Expected next | Production next | Next OK | Forbidden | Capability states | Unsupported vs not-yet | Repeatable | Order-invariant | No manufactured history | Label-invariant |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    yes = lambda value: "yes" if value else "**NO**"
    for r in results["trajectories"]:
        m = r["metrics"]
        lines.append(" | ".join([
            f"| `{r['trajectory_id']}`", r["fixture_class"].replace("_", " "), f"`{r['expected']['preferred_next']}`",
            f"`{r['production']['recommended_step_id']}`", yes(m["next_step_preferred"] and m["next_step_permitted"]),
            "**yes**" if m["forbidden_suggestion"] else "no",
            f"{m['capability_state']['correct']}/{m['capability_state']['total']}",
            f"{m['unsupported_vs_not_yet']['correct']}/{m['unsupported_vs_not_yet']['total']}",
            yes(m["repeatable_same_workspace"] and m["repeatable_independent_materialization"]),
            yes(m["invariant_to_item_order"] and m["invariant_to_storage_order"]),
            yes(all(m["no_manufactured_history"].values())), yes(m["invariant_to_labels_and_wording"])]) + " |")
    a = results["aggregate"]
    lines += ["", "**Aggregate:** "
              f"capability states {a['capability_state']['correct']}/{a['capability_state']['total']}; "
              f"unsupported vs not-yet {a['unsupported_vs_not_yet']['correct']}/{a['unsupported_vs_not_yet']['total']}; "
              f"preferred next step {a['next_step_preferred']['passed']}/{a['next_step_preferred']['total']}; "
              f"forbidden suggestions {a['forbidden_suggestions']['count']}/{a['forbidden_suggestions']['total']}; "
              f"repeatable {a['repeatable']['passed']}/{a['repeatable']['total']}; "
              f"order-invariant {a['order_invariant']['passed']}/{a['order_invariant']['total']}; "
              f"no manufactured history {a['no_manufactured_history']['passed']}/{a['no_manufactured_history']['total']}; "
              f"label-invariant {a['label_invariant']['passed']}/{a['label_invariant']['total']}.", ""]
    mismatches = [(r["trajectory_id"], m) for r in results["trajectories"] for m in r["mismatches"]]
    lines.append("**Mismatches:** " + ("none." if not mismatches else ""))
    for trajectory_id, m in mismatches:
        lines.append(f"- `{trajectory_id}` `{m['capability_id']}` {m['field']}: expected `{m['expected']}`, production `{m['production']}`")
    return "\n".join(lines) + "\n"


def write(results: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (out / "summary.md").write_text(summary_markdown(results))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    results = run()
    if args.write:
        write(results, args.write)
        return 0
    committed = json.loads((args.check / "results.json").read_text())
    same = committed == json.loads(json.dumps(results, sort_keys=True, ensure_ascii=False))
    print("results match committed dataset" if same else "results differ from committed dataset")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
