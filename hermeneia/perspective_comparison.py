"""Structured Perspective Comparison v1 (#215 P7): a deterministic, read-only projection.

Compares retained Perspective receipts that the P4 evidence adapter already
found eligible (E(r)). It reports participants, the exact question binding,
the evidence each Perspective was supplied and how those sets relate, and
pair relations. Claims, agreement, disagreement, evidence reliance,
assumptions and unresolved disagreement are not established: retained
responses are free prose, and this policy performs no semantic extraction.
It decides nothing, synthesizes nothing, persists nothing and calls no
provider. Contract: docs/design/perspective-comparison-v1.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json

from .perspective_achievement_evidence import PerspectiveAchievementEvidence
from .perspective_execution_receipts import SCHEMA as RECEIPT_SCHEMA, canonical_bytes, receipt_from_row

SCHEMA = "hermeneia.perspective-comparison/v1"
POLICY_VERSION = "1.0.0"
MIN_PARTICIPANTS, MAX_PARTICIPANTS = 2, 8
ELIGIBILITY = "perspective-achievement-rules-v1 E(r) via read_perspective_achievement_evidence"
_METHODOLOGY_FIELDS = ("purpose", "questions", "challenges", "limitations")  # P4 M(r)
_HIGHLIGHT_SNAPSHOT = ("text", "page", "locator", "relevance", "status")

SEMANTIC_NOT_ESTABLISHED = {
    "status": "not_established",
    "reason_code": "SEMANTIC_EXTRACTION_REQUIRED",
    "fields": ["claims", "agreement", "disagreement", "evidence_reliance", "assumptions", "unresolved"],
    "statement": ("Retained Perspective responses are free prose under perspective-run/v1. Claims, agreement, "
                  "disagreement, the evidence a response relied on, assumptions and unresolved disagreement cannot be "
                  "established from receipt structure without semantic extraction, which this deterministic policy "
                  "does not perform."),
}
EVIDENCE_STATEMENT = ("Evidence below is what each retained Perspective was supplied in its recorded Scope. "
                      "Which supplied evidence a response relied on is not established.")
NOT_SYNTHESIS = ("This comparison is a read-only projection over retained Perspective receipts. It is not a synthesis "
                 "and not study history. It does not decide which Perspective is correct, and no agreement, majority "
                 "or model consensus becomes truth or user agreement.")
UNCERTAINTY = {
    "GOVERNING_QUESTION_NOT_BOUND": ("Perspective Scope excludes the workspace governing question; this comparison "
                                     "binds only the exact execution question."),
    "SUPPLIED_NOT_RELIED_ON": ("Supplied evidence is what each Perspective was given, not proof that its response "
                               "relied on it."),
    "EXECUTION_SETTINGS_UNDISCLOSED": "Undisclosed model revision, seed, temperature and runtime defaults remain unknown.",
    "NO_ADJUDICATION": ("No user adjudication is recorded. Retention is not agreement, and this comparison does not "
                        "decide which Perspective is correct."),
    "MODEL_DIFFERENCE_NOT_PERSPECTIVE": ("Participants that share a Perspective family differ only in execution; a "
                                         "model difference does not make a distinct Perspective."),
    "IDENTICAL_TEXT_NOT_AGREEMENT": "Identical response text is a textual fact, not recorded agreement.",
    "FAMILY_UNSUPPORTED": "Perspective family ancestry for some participants cannot be established.",
    "HIGHLIGHT_SNAPSHOT_VARIES": ("A Reader highlight was captured with different metadata in different runs; each "
                                  "participant keeps its own captured snapshot."),
    "RECEIPTS_NOT_ELIGIBLE": ("Some retained receipts in this workspace are not eligible (for example, excluded from "
                              "analysis) and do not inform this comparison."),
}


class ComparisonRefused(ValueError):
    """The requested participants are not an admissible comparison; nothing was compared."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _order(receipt: dict) -> tuple[datetime, str]:
    # P4 K(r): the original retention instant in UTC, then the receipt ID.
    instant = datetime.fromisoformat(receipt["retention"]["retained_at"].replace("Z", "+00:00"))
    return instant.astimezone(timezone.utc), receipt["id"]


def _same_question(left: dict, right: dict) -> bool:
    # P4 same_question: validated digest and exact UTF-8 bytes; no normalization.
    a, b = left["run"], right["run"]
    return a["question_sha256"] == b["question_sha256"] and a["question"].encode("utf-8") == b["question"].encode("utf-8")


def _methodology(receipt: dict) -> bytes:
    definition = receipt["run"]["perspective"]["definition"]
    return canonical_bytes({key: definition[key] for key in _METHODOLOGY_FIELDS})


def _supplied(receipt: dict) -> dict:
    scope = receipt["run"]["scope_receipt"]
    primary = scope["primary"]
    context: list[str] = []
    highlights = []
    for part in scope["supporting"]:
        if part["kind"] == "current_page":
            context.extend(part["extraction_ids"])
        elif part["kind"] == "reader_highlight":
            snapshot = {key: part.get(key) for key in _HIGHLIGHT_SNAPSHOT}
            highlights.append({"id": part["id"], "page": part["page"], "captured_sha256": _digest(canonical_bytes(snapshot))})
    return {"source_document": {"id": primary["source_document_id"], "file_hash": primary["source_document_hash"]},
            "focus": list(primary["extraction_ids"]), "focus_locator": primary["locator"],
            "context": context, "highlights": highlights}


def _units(supplied: dict) -> dict[tuple[str, str], dict]:
    units: dict[tuple[str, str], dict] = {}
    for role, identifiers in (("focus", supplied["focus"]), ("context", supplied["context"])):
        for identifier in identifiers:
            units.setdefault(("source_extractions", identifier), {"roles": set(), "captured": None})["roles"].add(role)
    for highlight in supplied["highlights"]:
        units[("reader_highlights", highlight["id"])] = {"roles": {"highlight"}, "captured": highlight["captured_sha256"]}
    return units


def _set_relation(sets: list[set]) -> str:
    if all(item == sets[0] for item in sets):
        return "identical"
    if all(not (a & b) for a, b in combinations(sets, 2)):
        return "disjoint"
    return "overlapping"


def _ref(key: tuple[str, str]) -> dict:
    return {"table": key[0], "key": {"id": key[1]}}


def _perspective_relation(left, right) -> str:
    (a_exec, a), (b_exec, b) = left, right
    if a_exec.family_state != "supported" or b_exec.family_state != "supported":
        return "family_unsupported"
    if a_exec.family_key == b_exec.family_key:
        return "same_family"
    # P4 distinct_perspective (§6): different families, full fingerprints and exact methodology.
    if (a["run"]["perspective"]["definition_fingerprint"] != b["run"]["perspective"]["definition_fingerprint"]
            and _methodology(a) != _methodology(b)):
        return "distinct_family_distinct_methodology"
    return "distinct_family_same_methodology"


def _participant(execution, receipt: dict, supplied: dict) -> dict:
    run, perspective = receipt["run"], receipt["run"]["perspective"]
    lineage = execution.lineage_ref
    return {
        "receipt_id": receipt["id"],
        "run_id": run["run_id"],
        "lineage_record": lineage["record"],
        "authorship": lineage["authorship"],
        "retention": dict(receipt["retention"]),
        "executed": {"created_at": run["created_at"], "completed_at": run["completed_at"]},
        "perspective": {
            "origin": perspective["origin"], "id": perspective["id"], "version": perspective["version"],
            "label": perspective["definition"]["label"], "definition_fingerprint": perspective["definition_fingerprint"],
            "methodology_sha256": _digest(_methodology(receipt)),
            "family": {"state": execution.family_state,
                       "key": list(execution.family_key) if execution.family_key is not None else None},
        },
        "execution": json.loads(json.dumps(run["execution"])),
        "digests": {key: run[key] for key in ("question_sha256", "scope_sha256", "prompt_sha256", "response_sha256")},
        "response": run["response"],
        "evidence_supplied": supplied,
    }


def compare_retained_perspectives(evidence: PerspectiveAchievementEvidence, receipt_ids: list[str]) -> dict:
    """Compare eligible retained Perspectives of one snapshot; refuses rather than guesses."""
    if not isinstance(evidence, PerspectiveAchievementEvidence):
        raise TypeError("Canonical PerspectiveAchievementEvidence adapter snapshot required")
    requested = list(receipt_ids)
    if len(set(requested)) != len(requested):
        raise ComparisonRefused("DUPLICATE_PARTICIPANT")
    if len(requested) < MIN_PARTICIPANTS:
        raise ComparisonRefused("TOO_FEW_PARTICIPANTS")
    if len(requested) > MAX_PARTICIPANTS:
        raise ComparisonRefused("TOO_MANY_PARTICIPANTS")
    if evidence.source_state != "supported":
        raise ComparisonRefused("COVERAGE_UNSUPPORTED")
    eligible = {}
    for execution in evidence.executions:
        value = json.loads(execution.receipt_json)
        # Recompute every digest from the canonical row; a digest claim alone is not equality.
        receipt = receipt_from_row({"id": value["id"], "run_id": value["run"]["run_id"], "receipt_json": execution.receipt_json})
        eligible[receipt["id"]] = (execution, receipt)
    if any(identifier not in eligible for identifier in requested):
        raise ComparisonRefused("INELIGIBLE_RECEIPT")
    chosen = sorted((eligible[identifier] for identifier in requested), key=lambda item: _order(item[1]))
    if any(not _same_question(chosen[0][1], receipt) for _, receipt in chosen[1:]):
        raise ComparisonRefused("QUESTION_MISMATCH")

    supplied = {receipt["id"]: _supplied(receipt) for _, receipt in chosen}
    units = {receipt["id"]: _units(supplied[receipt["id"]]) for _, receipt in chosen}
    ids = [receipt["id"] for _, receipt in chosen]
    all_units = sorted(set().union(*(units[identifier] for identifier in ids)))
    unit_rows = []
    for key in all_units:
        holders = [{"receipt_id": identifier, "roles": sorted(units[identifier][key]["roles"]),
                    "captured_sha256": units[identifier][key]["captured"]} for identifier in ids if key in units[identifier]]
        unit_rows.append({"ref": _ref(key), "supplied_to": holders,
                          "captured_snapshot_varies": len({holder["captured_sha256"] for holder in holders}) > 1})
    sets = {identifier: set(units[identifier]) for identifier in ids}
    shared = set.intersection(*sets.values())
    only = [{"receipt_id": identifier,
             "refs": [_ref(key) for key in sorted(sets[identifier] - set().union(*(sets[other] for other in ids if other != identifier)))]}
            for identifier in ids]

    relations = []
    for left, right in combinations(chosen, 2):
        a, b = left[1], right[1]
        a_id, b_id = a["id"], b["id"]
        focus = [{("source_extractions", identifier) for identifier in supplied[x]["focus"]} for x in (a_id, b_id)]
        relations.append({
            "participants": [a_id, b_id],
            "perspective": _perspective_relation(left, right),
            "execution": ("same_provider_model"
                          if (a["run"]["execution"]["provider_id"], a["run"]["execution"]["model_id"])
                          == (b["run"]["execution"]["provider_id"], b["run"]["execution"]["model_id"])
                          else "different_provider_model"),
            "response_text": ("identical" if a["run"]["response_sha256"] == b["run"]["response_sha256"]
                              and a["run"]["response"] == b["run"]["response"] else "different"),
            "evidence_units": _set_relation([sets[a_id], sets[b_id]]),
            "evidence_focus": _set_relation(focus),
            "same_source_document": supplied[a_id]["source_document"] == supplied[b_id]["source_document"],
        })

    coverage = evidence.coverage
    classified = coverage.get("classified_records", {})
    conditions = {
        "GOVERNING_QUESTION_NOT_BOUND": True,
        "SUPPLIED_NOT_RELIED_ON": True,
        "EXECUTION_SETTINGS_UNDISCLOSED": True,
        "NO_ADJUDICATION": True,
        "MODEL_DIFFERENCE_NOT_PERSPECTIVE": any(r["perspective"] == "same_family" for r in relations),
        "IDENTICAL_TEXT_NOT_AGREEMENT": any(r["response_text"] == "identical" for r in relations),
        "FAMILY_UNSUPPORTED": any(execution.family_state != "supported" for execution, _ in chosen),
        "HIGHLIGHT_SNAPSHOT_VARIES": any(row["captured_snapshot_varies"] for row in unit_rows),
        "RECEIPTS_NOT_ELIGIBLE": sum(classified.get(state, 0) for state in ("excluded", "unsupported", "invalid")) > 0,
    }
    first = chosen[0][1]["run"]
    return {
        "schema": SCHEMA,
        "policy_version": POLICY_VERSION,
        "comparison_id": "perspective-comparison:sha256:" + hashlib.sha256(canonical_bytes(
            {"schema": SCHEMA, "policy_version": POLICY_VERSION, "receipt_ids": sorted(ids)})).hexdigest(),
        "inputs": {"evidence_source": coverage.get("source"), "receipt_schema": RECEIPT_SCHEMA,
                   "eligibility": ELIGIBILITY, "receipt_ids": sorted(ids)},
        "coverage": coverage,
        "question": {"text": first["question"], "sha256": first["question_sha256"],
                     "binding": "exact_execution_question", "governing_question": "not_bound"},
        "participants": [_participant(execution, receipt, supplied[receipt["id"]]) for execution, receipt in chosen],
        "evidence": {"basis": "supplied_scope", "statement": EVIDENCE_STATEMENT, "units": unit_rows,
                     "shared_by_all": [_ref(key) for key in sorted(shared)], "supplied_only_to": only,
                     "overall": _set_relation(list(sets.values()))},
        "relations": relations,
        "semantic": dict(SEMANTIC_NOT_ESTABLISHED, fields=list(SEMANTIC_NOT_ESTABLISHED["fields"])),
        "uncertainty": [{"code": code, "statement": UNCERTAINTY[code]} for code in UNCERTAINTY if conditions[code]],
        "not_synthesis": NOT_SYNTHESIS,
    }
