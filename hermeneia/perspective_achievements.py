"""Two frozen Perspective predicates, evaluated without SQL, providers or writes.

Results are current evaluations, never durable awards. Evidence must come from
the read-only canonical adapter; this is not an API for client-authored facts.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json

from .perspective_achievement_evidence import (
    BUILTIN_V1_FINGERPRINTS, TEMPLATE_IMPLEMENTATION_SHA256,
    PerspectiveAchievementEvidence,
)
from .perspective_execution_receipts import canonical_bytes, receipt_from_row

SCHEMA = "hermeneia.perspective-achievement-evaluation/v1"
EVALUATOR_VERSION = "1.0.0"

# Explicit frozen rule metadata, separate from capability readiness and awards.
# These declarations identify only this bounded evaluator, not a generic engine.
_RULES = (
    {
        "achievement_id": "perspective_explorer",
        "rule_id": "achievement.perspective_explorer",
        "rule_version": "1.0.0",
        "predicate": "exists Explorer-valid eligible retained P3 execution",
        "evidence_schema": "hermeneia.perspective-execution-receipt/v1",
        "coverage_capability": "perspective-retained-execution-v1",
        "prompt_version": "perspective-run/v1",
        "prompt_template_implementation_sha256": TEMPLATE_IMPLEMENTATION_SHA256,
        "validity_checks": [
            "canonical_p3_row_and_all_digests", "successful_explicit_local_retention",
            "supported_exact_frame_revision", "captured_prompt_template_binding",
            "durable_reference_closure", "eligible_typed_lineage_identity",
            "aware_ordered_timestamps_with_utc_order", "supported_extant_coverage",
        ],
        "builtin_support": [{"id": identifier, "version": version,
                             "definition_fingerprint": fingerprint}
                            for (identifier, version), fingerprint in sorted(BUILTIN_V1_FINGERPRINTS.items())],
        "witness_order": ["retained_at_utc", "receipt_id_ascii"],
    },
    {
        "achievement_id": "second_opinion",
        "rule_id": "achievement.second_opinion",
        "rule_version": "1.0.0",
        "predicate": "exists two Explorer-valid executions with exact inquiry/frame and distinct family/methodology",
        "question_equality": "exact_utf8_and_validated_sha256",
        "scope_equality": "complete_p3_canonical_bytes_and_validated_sha256",
        "family_equality": "namespaced_builtin_id_or_validated_saved_root",
        "methodology_fields": ["purpose", "questions", "challenges", "limitations"],
        "distinctness": "different_families_and_full_fingerprints_and_exact_methodology",
        "pair_order": ["left_retained_at_utc", "left_receipt_id_ascii", "right_retained_at_utc", "right_receipt_id_ascii"],
    },
)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def perspective_achievement_rules() -> list[dict]:
    """Return independent copies of the two versioned declarations."""
    return deepcopy(list(_RULES))


def _receipt(execution) -> dict:
    value = json.loads(execution.receipt_json)
    return receipt_from_row({"id": value["id"], "run_id": value["run"]["run_id"],
                             "receipt_json": execution.receipt_json})


def _order(receipt: dict) -> tuple[datetime, str]:
    # P3 already rejects naive, malformed and reversed timestamps.
    instant = datetime.fromisoformat(receipt["retention"]["retained_at"].replace("Z", "+00:00"))
    return instant.astimezone(timezone.utc), receipt["id"]


def _same_inquiry(left: dict, right: dict) -> bool:
    a, b = left["run"], right["run"]
    return (a["question_sha256"] == b["question_sha256"]
            and a["question"].encode("utf-8") == b["question"].encode("utf-8")
            and a["scope_sha256"] == b["scope_sha256"]
            and canonical_bytes(a["scope_receipt"]) == canonical_bytes(b["scope_receipt"])
            and a["operation"] == b["operation"] == "perspective_run"
            and a["prompt_version"] == b["prompt_version"] == "perspective-run/v1")


def _methodology(receipt: dict) -> bytes:
    definition = receipt["run"]["perspective"]["definition"]
    return canonical_bytes({key: definition[key] for key in _RULES[1]["methodology_fields"]})


def _different_methodology(left: dict, right: dict) -> bool:
    return (left["run"]["perspective"]["definition_fingerprint"]
            != right["run"]["perspective"]["definition_fingerprint"]
            and _methodology(left) != _methodology(right))


def _negative(source_state: str, diagnostics: list[dict], family_states: set[str]) -> tuple[str, str, str]:
    execution_states = {item["state"] for item in diagnostics if item["stage"] != "family"}
    if source_state == "invalid" or "invalid" in execution_states | family_states:
        return ("invalid_evidence", "INVALID_EVIDENCE",
                "Required claimed supported evidence fails integrity or identity validation.")
    if source_state == "unsupported" or "unsupported" in execution_states | family_states:
        return ("unsupported_due_to_missing_coverage", "COVERAGE_UNSUPPORTED",
                "Required evidence coverage or identity/version support is insufficient; past activity is unknown.")
    return ("not_earned", "NO_QUALIFYING_RETAINED_EVIDENCE",
            "No qualifying retained evidence exists in this supported extant eligible snapshot under this rule version.")


def evaluate_perspective_achievements(evidence: PerspectiveAchievementEvidence) -> dict:
    """Evaluate the frozen rules purely over a canonical adapter snapshot.

    No current clock, database connection, provider, UI or persistence is used.
    Source integrity takes precedence. Otherwise a validated existential witness
    survives unrelated local diagnostics; without a witness invalidity precedes
    unsupported coverage, then the bounded extant-snapshot negative result.
    """
    if not isinstance(evidence, PerspectiveAchievementEvidence):
        raise TypeError("Canonical PerspectiveAchievementEvidence adapter snapshot required")
    if evidence.source_state not in {"supported", "unsupported", "invalid"}:
        raise ValueError("Invalid evidence source state")
    coverage = json.loads(evidence.coverage_json)
    diagnostics = json.loads(evidence.diagnostics_json)
    candidates = sorted(((execution, _receipt(execution)) for execution in evidence.executions),
                        key=lambda item: _order(item[1]))
    if len({receipt["id"] for _, receipt in candidates}) != len(candidates):
        raise ValueError("Duplicate canonical receipt in evidence snapshot")
    if len({receipt["run"]["run_id"] for _, receipt in candidates}) != len(candidates):
        raise ValueError("Duplicate canonical execution in evidence snapshot")

    pair = None
    unresolved_family_states = set()
    # Candidates and combinations are lexicographically ordered by the frozen K.
    for left, right in combinations(candidates, 2):
        a, b = left[1], right[1]
        if not _same_inquiry(a, b) or not _different_methodology(a, b):
            continue
        states = {left[0].family_state, right[0].family_state}
        if states != {"supported"}:
            unresolved_family_states.update(states - {"supported"})
            continue
        if left[0].family_key != right[0].family_key:
            pair = (left, right)
            break

    # Definition and input digests identify this assessment without minting an
    # award/evaluation object identity or copying canonical model output to it.
    basis = {
        "source_state": evidence.source_state, "coverage": coverage,
        "diagnostics": diagnostics,
        "executions": [{
            "receipt_sha256": _digest(execution.receipt_json.encode("utf-8")),
            "lineage_ref": json.loads(execution.lineage_ref_json),
            "family_key": list(execution.family_key) if execution.family_key is not None else None,
            "family_state": execution.family_state,
            "family_evidence": json.loads(execution.family_evidence_json),
            "family_reason_code": execution.family_reason_code,
            "dependency_evidence": json.loads(execution.dependency_evidence_json),
            "eligibility_observations": json.loads(execution.eligibility_json),
        } for execution, _ in candidates],
    }
    rules = perspective_achievement_rules()
    results = []
    for index, definition in enumerate(rules):
        witness = candidates[:1] if index == 0 else list(pair or ())
        if evidence.source_state != "supported":
            witness = []
        if witness:
            status, code, reason = ("earned", "SUPPORTED_RETAINED_WITNESS",
                "Validated retained execution evidence satisfies the exact frozen predicate; this evaluation creates no award.")
        else:
            status, code, reason = _negative(evidence.source_state, diagnostics,
                set() if index == 0 else unresolved_family_states)
        result = {
            **{key: definition[key] for key in ("achievement_id", "rule_id", "rule_version")},
            "rule_reference": definition["rule_id"] + ".v" + definition["rule_version"],
            "rule_sha256": _digest(canonical_bytes(definition)),
            "status": status, "reason_code": code, "reason": reason,
            "evidence_refs": [json.loads(execution.lineage_ref_json) for execution, _ in witness],
            "qualifying_receipt_ids": [receipt["id"] for _, receipt in witness],
            "validated_evidence": [{
                "receipt_id": receipt["id"],
                "receipt_sha256": _digest(execution.receipt_json.encode("utf-8")),
                "dependency_evidence": json.loads(execution.dependency_evidence_json),
                "eligibility_observations": json.loads(execution.eligibility_json),
            } for execution, receipt in witness],
            "coverage": deepcopy(coverage),
            "selection_basis": {
                "order": "retained_at_utc_then_receipt_id_ascii",
                "candidate_receipt_ids": [r["id"] for _, r in candidates],
                "selected": [{"receipt_id": r["id"],
                              "retained_at": r["retention"]["retained_at"],
                              "retained_at_utc": _order(r)[0].isoformat()} for _, r in witness],
            },
        }
        if index == 1:
            result["question_comparison_basis"] = None
            result["scope_comparison_basis"] = None
            result["perspective_distinctness_basis"] = None
            if witness:
                result["question_comparison_basis"] = {
                    "codec": "exact_utf8", "sha256": witness[0][1]["run"]["question_sha256"],
                    "bytes_equal": True,
                }
                result["scope_comparison_basis"] = {
                    "codec": "complete_p3_canonical_bytes", "sha256": witness[0][1]["run"]["scope_sha256"],
                    "bytes_equal": True, "receipt_version": "resolved-scope:v1",
                    "prompt_version": "perspective-run/v1",
                }
                result["perspective_distinctness_basis"] = {
                    "family_keys": [list(execution.family_key) for execution, _ in witness],
                    "revision_ids": [r["run"]["perspective"]["id"] for _, r in witness],
                    "definition_fingerprints": [r["run"]["perspective"]["definition_fingerprint"] for _, r in witness],
                    "methodology_fields": deepcopy(_RULES[1]["methodology_fields"]),
                    "methodology_sha256": [_digest(_methodology(r)) for _, r in witness],
                    "family_evidence": [json.loads(execution.family_evidence_json) for execution, _ in witness],
                    "methodology_bytes_different": True,
                }
        results.append(result)
    return {
        "schema": SCHEMA, "evaluator_version": EVALUATOR_VERSION,
        "rules_sha256": _digest(canonical_bytes(rules)),
        "evidence_sha256": _digest(canonical_bytes(basis)),
        "achievements": results, "coverage": coverage, "diagnostics": diagnostics,
        "limitations": [
            "Evaluation only; no award, persistence, agreement, mastery or named-human identity is established.",
            "Coverage concerns extant eligible retained receipts, never complete past Perspective activity.",
            "Complete Scope metadata, including packet compilation timestamps, participates in exact equality.",
            "Exact methodology differences cannot detect paraphrased duplicates or prove intellectual independence.",
        ],
    }
