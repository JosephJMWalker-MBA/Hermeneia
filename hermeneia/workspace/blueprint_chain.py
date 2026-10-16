"""Blueprint dependency chain portability (#252, P10): one all-or-nothing WBS component.

The chain is Interpretations with their ADR-0009 proposals and provenance,
Blueprints and their links, ArchitectPlans and paragraphs, Blueprint revision
edges, and P8 acceptance receipts. It travels through a bundle only with its
closure intact. Otherwise export declares it unsupported with a reason and
writes no chain file. Rows are exact; nothing is fabricated, relabelled,
repaired or cherry-picked. The same closure rules check the source at export
and the target after restore.
Contract: docs/design/blueprint-chain-portability-v1.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

CAPABILITY = "blueprint-dependency-chain-v1"
COVERAGE_KEY = "blueprint_dependency_chain"
EDGE_KEY = "blueprint_supersessions"
RECEIPT_KEY = "blueprint_proposal_acceptances"

# (key, runtime table, bundle file, primary key, exact columns), in restore dependency order.
COMPONENTS: tuple[tuple[str, str, str, tuple[str, ...], frozenset[str]], ...] = (
    ("ai_provenance", "ai_provenance", "reports/ai_provenance.json", ("id",), frozenset({
        "id", "staged_object_id", "generating_model", "model_version", "generation_timestamp", "prompt_reference",
        "prompt_reference_type", "parent_object_ids", "generation_parameters", "schema_version", "accepting_steward",
        "acceptance_timestamp", "acceptance_rationale", "created_at"})),
    ("proposed_interpretations", "proposed_interpretations", "reports/proposed_interpretations.json", ("id",), frozenset({
        "id", "observation_id", "perspective", "perspective_id", "text", "evidential_status", "evidence_observation_ids",
        "ai_provenance_id", "status", "steward_id", "decided_at", "steward_rationale", "created_at", "response_mode"})),
    ("interpretations", "interpretations", "reports/interpretations.json", ("id",), frozenset({
        "id", "observation_id", "perspective", "perspective_id", "text", "evidential_status", "evidence_observation_ids",
        "confidence", "source", "ai_provenance_id", "created_at", "steward_note"})),
    ("narrative_blueprints", "narrative_blueprints", "study/blueprints.json", ("id",),
     frozenset({"id", "title", "thesis", "sections", "source", "created_at"})),
    ("blueprint_observation_links", "blueprint_observation_links", "study/blueprint_observation_links.json",
     ("blueprint_id", "observation_id"), frozenset({"blueprint_id", "observation_id"})),
    ("blueprint_interpretation_links", "blueprint_interpretation_links", "study/blueprint_interpretation_links.json",
     ("blueprint_id", "interpretation_id"), frozenset({"blueprint_id", "interpretation_id"})),
    ("architect_plans", "architect_plans", "study/architect_plans.json", ("id",),
     frozenset({"id", "blueprint_id", "blueprint_hash", "title", "source", "created_at"})),
    ("architect_plan_paragraphs", "architect_plan_paragraphs", "study/architect_plan_paragraphs.json", ("plan_id", "order_idx"),
     frozenset({"plan_id", "order_idx", "purpose", "blueprint_section", "required_observations", "required_interpretations",
                "required_terms", "forbidden_claims", "notes"})),
    (EDGE_KEY, "supersession_relations", "study/blueprint_supersessions.json", ("old_id", "new_id", "reason", "ratified_at"),
     frozenset({"old_id", "new_id", "reason", "ratified_at"})),
    (RECEIPT_KEY, "blueprint_proposal_acceptances", "study/blueprint_proposal_acceptances.json", ("id",),
     frozenset({"id", "candidate_id", "receipt_json"})),
)
FILES = {key: path for key, _table, path, _pk, _cols in COMPONENTS}
# Supersession edges touching any of these tables must be Blueprint→Blueprint to stay in scope.
_CHAIN_ENDPOINT_TABLES = ("narrative_blueprints", "interpretations", "architect_plans", "proposed_interpretations")
_PRECEDENCE = ("CHAIN_SCHEMA_INCOMPLETE", "CHAIN_INTEGRITY_INVALID", "CHAIN_SUPERSESSION_OUT_OF_SCOPE", "CHAIN_CLOSURE_INCOMPLETE")
REASONS = {
    "CHAIN_SCHEMA_INCOMPLETE": "A Blueprint chain table is missing or has columns other than the supported schema; the chain is not exported.",
    "CHAIN_INTEGRITY_INVALID": "A Blueprint chain record fails its integrity check; the chain is not exported rather than exported in part.",
    "CHAIN_SUPERSESSION_OUT_OF_SCOPE": "A supersession edge touches the Blueprint chain but is not Blueprint-to-Blueprint; the chain is not exported.",
    "CHAIN_CLOSURE_INCOMPLETE": "A Blueprint chain record references a record that does not exist; the chain is not exported rather than left dangling.",
}
UNSUPPORTED_LEGACY = ("This bundle does not carry the Blueprint dependency chain (no blueprint-dependency-chain-v1); "
                      "its Interpretations, Blueprints, plans, revisions and acceptance receipts are unknown.")
COVERED_REASON = "Extant Blueprint dependency chain covered with closure; no claim of complete historical activity."


class ChainComponentError(ValueError):
    """A bundle's chain component is malformed, contradictory or not closed; nothing is restored."""


# ── Shared closure rules (source at export, target after restore) ────────────

def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _dicts(conn: sqlite3.Connection, sql: str) -> list[dict]:
    cursor = conn.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def schema_supported(conn: sqlite3.Connection) -> bool:
    return all(_columns(conn, table) == set(columns) for _key, table, _path, _pk, columns in COMPONENTS)


def _id_list(value) -> list | None:
    if value is None or value == "":
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return None
    return parsed if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed) else None


def chain_problems(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Every integrity, scope and closure problem of the chain in this connection's snapshot, most severe first.

    Details name tables and record identities only, never study text.
    """
    from ..blueprint_proposals import receipt_from_row

    problems: list[tuple[str, str]] = []

    def ids(table: str) -> set[str]:
        return {row[0] for row in conn.execute(f'SELECT id FROM "{table}"')}

    observations, perspectives = ids("observations"), ids("perspectives")
    provenance, proposals, interpretations = ids("ai_provenance"), ids("proposed_interpretations"), ids("interpretations")
    blueprints, plans = ids("narrative_blueprints"), ids("architect_plans")

    receipts = []
    for row in _dicts(conn, "SELECT * FROM blueprint_proposal_acceptances ORDER BY id"):
        try:
            receipts.append(receipt_from_row(row))
        except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
            problems.append(("CHAIN_INTEGRITY_INVALID", f"blueprint_proposal_acceptances {row['id']}"))
    for row in _dicts(conn, "SELECT id, sections FROM narrative_blueprints ORDER BY id"):
        try:
            sections = json.loads(row["sections"])
            valid = isinstance(sections, list) and all(
                isinstance(s, dict) and _id_list(s.get("supporting_observations", [])) is not None
                and _id_list(s.get("supporting_interpretations", [])) is not None for s in sections)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            problems.append(("CHAIN_INTEGRITY_INVALID", f"narrative_blueprints {row['id']} sections"))
            continue
        for section in sections:
            if not set(section.get("supporting_observations", [])) <= observations:
                problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"narrative_blueprints {row['id']} → observations"))
            if not set(section.get("supporting_interpretations", [])) <= interpretations:
                problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"narrative_blueprints {row['id']} → interpretations"))

    chain_ids = blueprints | interpretations | plans | proposals
    for old_id, new_id in conn.execute("SELECT old_id, new_id FROM supersession_relations ORDER BY old_id, new_id"):
        if (old_id in chain_ids or new_id in chain_ids) and not (old_id in blueprints and new_id in blueprints):
            problems.append(("CHAIN_SUPERSESSION_OUT_OF_SCOPE", f"supersession {old_id} → {new_id}"))

    for table in ("proposed_interpretations", "interpretations"):
        for row in _dicts(conn, f"SELECT id, observation_id, perspective_id, ai_provenance_id, evidence_observation_ids FROM {table}"):
            evidence = _id_list(row["evidence_observation_ids"])
            if evidence is None:
                problems.append(("CHAIN_INTEGRITY_INVALID", f"{table} {row['id']} evidence_observation_ids"))
                continue
            if (row["observation_id"] not in observations or not set(evidence) <= observations
                    or (row["perspective_id"] is not None and row["perspective_id"] not in perspectives)
                    or (row["ai_provenance_id"] is not None and row["ai_provenance_id"] not in provenance)):
                problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"{table} {row['id']}"))
    for identifier, staged in conn.execute("SELECT id, staged_object_id FROM ai_provenance"):
        if staged not in proposals:
            problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"ai_provenance {identifier} → proposed_interpretations"))
    for table, column, targets in (("blueprint_observation_links", "observation_id", observations),
                                   ("blueprint_interpretation_links", "interpretation_id", interpretations)):
        for blueprint_id, target in conn.execute(f"SELECT blueprint_id, {column} FROM {table}"):
            if blueprint_id not in blueprints or target not in targets:
                problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"{table} {blueprint_id} → {target}"))
    for identifier, blueprint_id in conn.execute("SELECT id, blueprint_id FROM architect_plans"):
        if blueprint_id not in blueprints:
            problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"architect_plans {identifier} → narrative_blueprints"))
    for (plan_id,) in conn.execute("SELECT DISTINCT plan_id FROM architect_plan_paragraphs"):
        if plan_id not in plans:
            problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"architect_plan_paragraphs → architect_plans {plan_id}"))
    # ADR-0047 L2-a: every Observation a plan requires is linked to the plan's Blueprint. An inconsistent historical
    # chain is declared, not carried; a bundle carrying one is refused at restore.
    linked: dict[str, set[str]] = {}
    for blueprint_id, observation in conn.execute("SELECT blueprint_id, observation_id FROM blueprint_observation_links"):
        linked.setdefault(blueprint_id, set()).add(observation)
    owners = dict(conn.execute("SELECT id, blueprint_id FROM architect_plans").fetchall())
    for plan_id, order_idx, raw in conn.execute(
            "SELECT plan_id, order_idx, required_observations FROM architect_plan_paragraphs ORDER BY plan_id, order_idx"):
        required = _id_list(raw)
        if required is None or not set(required) <= linked.get(owners.get(plan_id), set()):
            problems.append(("CHAIN_INTEGRITY_INVALID", f"architect_plan_paragraphs {plan_id}:{order_idx} → blueprint_observation_links"))

    edges = {tuple(row) for row in conn.execute("SELECT old_id, new_id, reason, ratified_at FROM supersession_relations")}
    plan_owner = dict(conn.execute("SELECT id, blueprint_id FROM architect_plans").fetchall())
    for receipt in receipts:
        result, basis = receipt["result"], receipt["candidate"]["binding"]["basis"]
        edge = result["supersession"]
        closed = (result["resulting_blueprint_id"] in blueprints
                  and plan_owner.get(result["plan_id"]) == result["resulting_blueprint_id"]
                  and (result["predecessor_id"] is None or result["predecessor_id"] in blueprints)
                  and (edge is None or (edge["old_id"], edge["new_id"], edge["reason"], edge["ratified_at"]) in edges)
                  and {e["id"] for e in basis["observations"]} <= observations
                  and {e["id"] for e in basis["interpretations"]} <= interpretations)
        if not closed:
            problems.append(("CHAIN_CLOSURE_INCOMPLETE", f"blueprint_proposal_acceptances {receipt['id']}"))
    return sorted(problems, key=lambda item: (_PRECEDENCE.index(item[0]), item[1]))


# ── Export ───────────────────────────────────────────────────────────────────

def _component_rows(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    rows = {}
    for key, table, _path, pk, _columns_ in COMPONENTS:
        order = ", ".join(pk)
        if key == EDGE_KEY:
            sql = ("SELECT * FROM supersession_relations WHERE old_id IN (SELECT id FROM narrative_blueprints) "
                   f"AND new_id IN (SELECT id FROM narrative_blueprints) ORDER BY {order}")
        else:
            sql = f'SELECT * FROM "{table}" ORDER BY {order}'
        rows[key] = _dicts(conn, sql)
    return rows


def export_chain(conn: sqlite3.Connection) -> tuple[dict[str, list[dict]] | None, dict | None]:
    """From the caller's read snapshot: (exact rows by key, None), or (None, the unsupported declaration)."""
    present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    needed = {table for _key, table, _path, _pk, _cols in COMPONENTS} | {"observations", "perspectives"}
    if not needed <= present or not schema_supported(conn):
        code = "CHAIN_SCHEMA_INCOMPLETE"
        return None, {"reason_code": code, "reason": REASONS[code]}
    problems = chain_problems(conn)
    if problems:
        code = problems[0][0]
        return None, {"reason_code": code, "reason": REASONS[code], "problem_count": len(problems)}
    return _component_rows(conn), None


# ── Restore ──────────────────────────────────────────────────────────────────

def _unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def read_component(root: Path, manifest: dict) -> tuple[dict[str, list[dict]] | None, dict]:
    """Validate the chain component before any write: (rows by key, coverage), or ChainComponentError."""
    declared = CAPABILITY in (manifest.get("required_capabilities") or [])
    unsupported = (manifest.get("declared_unsupported") or {}).get(CAPABILITY)
    entries = {entry.get("path"): entry for entry in manifest.get("files") or [] if entry.get("path") in FILES.values()}
    present = [path for path in FILES.values() if (root / path).exists()]
    if unsupported is not None:
        if declared or entries or present:
            raise ChainComponentError("Blueprint chain is declared unsupported but chain files or the capability are present")
        if not isinstance(unsupported, dict) or unsupported.get("reason_code") not in REASONS:
            raise ChainComponentError("Blueprint chain unsupported declaration is malformed")
        return None, {"status": "unsupported", "reason_code": unsupported["reason_code"], "reason": REASONS[unsupported["reason_code"]]}
    if not declared:
        if entries or present:
            raise ChainComponentError("Blueprint chain files are present without their required capability declaration")
        return None, {"status": "unsupported", "reason": UNSUPPORTED_LEGACY}
    listed = [entry for entry in manifest.get("files") or [] if entry.get("path") in FILES.values()]
    if len(listed) != len(FILES) or len(entries) != len(FILES):
        raise ChainComponentError("Blueprint chain component must list every chain file exactly once")
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ChainComponentError("Blueprint chain component requires explicit record counts")
    rows: dict[str, list[dict]] = {}
    resolved_root = root.resolve()
    for key, _table, path, pk, columns in COMPONENTS:
        entry, file = entries[path], root / path
        if entry.get("role") != "canonical" or not file.is_file() or resolved_root not in file.resolve().parents:
            raise ChainComponentError(f"Blueprint chain file {path} must be a canonical file inside the bundle")
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise ChainComponentError(f"Blueprint chain file {path} failed its hash check")
        try:
            table_rows = json.loads(data, object_pairs_hook=_unique_keys)
        except (ValueError, UnicodeError) as exc:
            raise ChainComponentError(f"Blueprint chain file {path} is not valid JSON") from exc
        if not isinstance(table_rows, list) or not all(isinstance(row, dict) and set(row) == columns for row in table_rows):
            raise ChainComponentError(f"Blueprint chain file {path} must hold rows with exactly the supported columns")
        keys = [tuple(row[column] for column in pk) for row in table_rows]
        if len(set(keys)) != len(keys) or keys != sorted(keys):
            raise ChainComponentError(f"Blueprint chain file {path} must use unique keys in primary-key order")
        if type(counts.get(key)) is not int or counts[key] != len(table_rows):
            raise ChainComponentError(f"Blueprint chain count for {key} disagrees with its file")
        rows[key] = table_rows
    from ..blueprint_proposals import receipt_from_row

    for row in rows[RECEIPT_KEY]:
        try:
            receipt_from_row(row)
        except (ValueError, TypeError, KeyError, UnicodeError, OverflowError) as exc:
            raise ChainComponentError(f"Blueprint proposal acceptance {row.get('id')} fails its integrity check") from exc
    return rows, {"status": "covered", "extant_records": {key: len(value) for key, value in rows.items()}, "reason": COVERED_REASON}


def insert_component(conn: sqlite3.Connection, rows: dict[str, list[dict]]) -> dict[str, int]:
    """Insert exact rows in dependency order inside the caller's restore transaction, then prove closure."""
    from ..blueprint_proposals import verify_receipt

    restored = {}
    for key, table, _path, _pk, columns in COMPONENTS:
        if not set(columns) <= _columns(conn, table):
            raise ChainComponentError(f"target cannot store the complete {table} row")
        ordered = sorted(columns)
        for row in rows[key]:
            conn.execute(f'INSERT INTO "{table}" ({", ".join(ordered)}) VALUES ({", ".join("?" for _ in ordered)})',
                         [row[column] for column in ordered])
        restored[key] = len(rows[key])
    problems = chain_problems(conn)
    if problems:
        raise ChainComponentError(f"restored Blueprint chain is not closed: {problems[0][0]} ({problems[0][1]})")
    for row in rows[RECEIPT_KEY]:
        verdict = verify_receipt(conn, row["id"])
        if verdict["record_integrity"] != "valid" or verdict["result_closure"] != "verified":
            raise ChainComponentError(f"restored Blueprint proposal acceptance {row['id']} does not verify")
    return restored
