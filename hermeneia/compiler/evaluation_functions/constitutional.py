"""
Constitutional Evaluation Function — ADR-0042, Era II Sprint E3.

Verifies that the RenderedNarrative carries a valid constitutional profile
in its execution_config. One Finding per required field.

Zero LLM. Deterministic. Read-only. Orthogonal.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from hermeneia.storage.hashing import make_finding_id, make_obligation_id

# ── Constitutional contract ───────────────────────────────────────────────────
dimension = "constitutional"
scope = ["execution_config"]
guarantees = ["deterministic", "complete", "read_only", "orthogonal", "zero_llm"]

# ── Internal constants ────────────────────────────────────────────────────────
DIMENSION = dimension
EVALUATION_METHOD = "constitutional-v1.0"

CONSTITUTIONAL_PROFILE = {
    "constitution_version": "1.0.0",
    "authority_index_version": "1.0.0",
    "invariant_profile": "CI-001..CI-016",
    "architecture_profile": "v1.0",
    "adr": "ADR-0042",
}

# Each obligation key and the JSON path to check
REQUIRED_PROFILE_FIELDS = [
    "execution_config",                              # top-level: must be present
    "constitutional_profile.constitution_version",
    "constitutional_profile.authority_index_version",
    "constitutional_profile.invariant_profile",
    "constitutional_profile.architecture_profile",
]


def evaluate_constitutional(
    rendered_narrative_id: str,
    architect_plan_id: str,
    conn: sqlite3.Connection,
) -> list[dict]:
    """Run the Constitutional Evaluation Function.

    One Finding per required constitutional profile field.
    """
    now = datetime.now(timezone.utc).isoformat()

    narrative_row = conn.execute(
        "SELECT id, architect_plan_id, execution_config FROM rendered_narratives WHERE id = ?",
        (rendered_narrative_id,),
    ).fetchone()
    if narrative_row is None:
        raise ValueError(f"RenderedNarrative not found: {rendered_narrative_id}")
    if narrative_row["architect_plan_id"] != architect_plan_id:
        raise ValueError(
            f"RenderedNarrative {rendered_narrative_id} belongs to plan "
            f"{narrative_row['architect_plan_id']}, not {architect_plan_id}"
        )

    raw_config = narrative_row["execution_config"]
    config: dict = {}
    config_parseable = False
    if raw_config:
        try:
            config = json.loads(raw_config)
            config_parseable = True
        except (json.JSONDecodeError, TypeError):
            pass

    cp = config.get("constitutional_profile", {}) if config_parseable else {}

    findings: list[dict] = []

    for field_key in REQUIRED_PROFILE_FIELDS:
        obligation_id = make_obligation_id(
            dimension=DIMENSION,
            plan_id=architect_plan_id,
            paragraph_order_idx=0,      # narrative-level obligation; paragraph=0 by convention
            term_text=field_key,
        )
        finding_id = make_finding_id(rendered_narrative_id, DIMENSION, obligation_id)

        if field_key == "execution_config":
            present = config_parseable
            observed = "present" if present else ("unparseable" if raw_config else "null")
        else:
            sub_key = field_key.split(".")[-1]
            value = cp.get(sub_key)
            present = bool(value)
            observed = str(value) if present else None

        evidence = json.dumps({
            "contract_obligation": field_key,
            "observed_render": observed,
            "supporting_trace": [rendered_narrative_id, architect_plan_id],
        }, ensure_ascii=True)

        findings.append({
            "id": finding_id,
            "rendered_narrative_id": rendered_narrative_id,
            "architect_plan_id": architect_plan_id,
            "dimension": DIMENSION,
            "obligation_id": obligation_id,
            "operation": "preservation" if present else "omission",
            "status": "preserved" if present else "omitted",
            "evidence": evidence,
            "evaluation_method": EVALUATION_METHOD,
            "constitution_version": json.dumps(CONSTITUTIONAL_PROFILE, sort_keys=True),
            "created_at": now,
        })

    if len(findings) != len(REQUIRED_PROFILE_FIELDS):
        raise RuntimeError(
            f"Completeness Invariant violated: expected {len(REQUIRED_PROFILE_FIELDS)} "
            f"findings, produced {len(findings)}"
        )

    return findings
