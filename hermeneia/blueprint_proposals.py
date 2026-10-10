"""Natural-language Blueprint proposals (#215 P8): governed candidates and append-only acceptance receipts.

Natural language is the interaction layer; the structured Blueprint remains
the governed substrate. A model drafts a complete Blueprint or successor from
the steward's intent over an evidence basis that Study Lineage deems eligible.
Only exposed labels resolve, so the model cannot invent record IDs. Candidates
are transient. Only an explicit steward decision commits a Blueprint, through
the existing persistence seams, together with a receipt proving which
candidate was reviewed, what the model proposed, what the steward accepted
and whether it was edited. Contract: docs/design/blueprint-proposal-v1.md.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

from .perspective_execution_receipts import canonical_bytes

CANDIDATE_SCHEMA = "hermeneia.blueprint-proposal-candidate/v1"
RECEIPT_SCHEMA = "hermeneia.blueprint-proposal-acceptance/v1"
POLICY_VERSION = "1.0.0"
PROMPT_VERSION = "blueprint-proposal/v1"
BASIS_POLICY = "blueprint-proposal-basis/v1"
TABLE = "blueprint_proposal_acceptances"
MAX_OBSERVATIONS, MAX_INTERPRETATIONS, MAX_SECTIONS = 200, 100, 12
ORIGINS = {"accept": "model_proposed_steward_accepted", "edit_and_accept": "model_proposed_steward_edited"}
SOURCES = {"accept": "proposal-accepted", "edit_and_accept": "proposal-edited"}
MEANING = ("The steward accepted this Blueprint (as proposed, or as edited) from this exact model proposal. It does not "
           "establish that the Blueprint's claims are true or that the model's explanation is the steward's rationale.")
PORTABILITY_REASON = ("Blueprint proposal acceptances are not covered by WBS 1.x: their closure (Blueprints, ArchitectPlans, "
                      "Blueprint supersessions and Interpretations) is not exported; round-tripping is scheduled for P10 (#215).")

# The frozen prompt policy (tests/fixtures/blueprint_proposal/v1/proposal_policy_v1.json).
HEADER = (
    "You are proposing a NarrativeBlueprint for a Hermeneia study. A steward will review it; nothing you write is saved or decided by you.",
    "Ground every section in the evidence listed below and cite evidence only by its label. Do not invent evidence. A section may cite nothing when no listed evidence supports it.",
    "Observations are source evidence. Interpretations are recorded readings with stated authorship; an accepted model contribution is not the steward's own reasoning.",
)
INTENT_INTRO = "Steward's request:"
GOVERNING_INTRO = "Governing question (the steward's current question; context, not evidence):"
OBSERVATIONS_INTRO = "Observations:"
INTERPRETATIONS_INTRO = "Interpretations:"
NONE_LINE = "(none)"
OBSERVATION_LINE = "O{n} (page {page}): {raw_text}"
INTERPRETATION_LINE = "I{n} ({authorship}; on {observation_label}): {text}"
AUTHORSHIP_LABELS = {"human": "steward-authored", "accepted_model": "accepted model contribution", "unknown": "authorship not recorded"}
PREDECESSOR_INTRO = "Current Blueprint to revise (return its complete successor, not a diff):"
PREDECESSOR_LINES = ("Title: {title}", "Thesis: {thesis}", "Section {k}: {claim} [{labels}]")
RETURN_INTRO = "Return only one JSON object with exactly these fields, and nothing else:"
CREATE_SHAPE = '{"title":"...","thesis":"...","sections":[{"claim":"...","observations":["O1"],"interpretations":["I1"]}]}'
REVISE_SHAPE = '{"title":"...","thesis":"...","sections":[{"claim":"...","observations":["O1"],"interpretations":["I1"]}],"change_summary":"..."}'
RULES_INTRO = "Rules:"
RULES = (
    "- Between 1 and 12 sections. Every field is required; use [] when a section cites nothing.",
    "- Cite only the labels listed above (O... for Observations, I... for Interpretations).",
)
REVISE_RULE = "- Return the complete successor Blueprint. change_summary explains your proposal to the steward; it is not the recorded rationale."

_CANDIDATE_DOMAIN = b"hermeneia.blueprint-proposal-candidate/v1\0"
_RECEIPT_DOMAIN = b"hermeneia.blueprint-proposal-acceptance/v1\0"
_FENCE = re.compile(r"\A\s*```(?:json)?[ \t]*\n(.*)\n[ \t]*```\s*\Z", re.S)
_OBSERVATION_FIELDS = ("id", "source_document_id", "source_extraction_id", "page", "paragraph", "sentence", "raw_text")


class ProposalRefused(ValueError):
    """Generation or acceptance is refused; nothing is held or written."""

    def __init__(self, code: str, status: int, detail: str = ""):
        self.code, self.status = code, status
        super().__init__(f"{code}: {detail}" if detail else code)


class InvalidReceipt(ValueError):
    """A stored or proposed acceptance receipt violates its contract."""


def _digest(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def text_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def blueprint_content(row: dict) -> dict:
    sections = json.loads(row["sections"]) if isinstance(row["sections"], str) else row["sections"]
    return {"id": row["id"], "title": row["title"], "thesis": row["thesis"], "sections": sections}


# ── Evidence basis (blueprint-proposal-basis/v1): Lineage decides eligibility ──

def governing_question(conn: sqlite3.Connection) -> dict:
    try:
        row = conn.execute("SELECT thesis FROM workspace_investigation WHERE id = 'current'").fetchone()
    except sqlite3.Error:
        row = None
    text = row[0] if row is not None and isinstance(row[0], str) and row[0].strip() else None
    return {"status": "captured" if text is not None else "absent", "text": text, "sha256": text_digest(text) if text else None}


def _successors(conn: sqlite3.Connection, blueprint_id: str) -> list[str]:
    return sorted({row[0] for row in conn.execute(
        "SELECT new_id FROM supersession_relations WHERE old_id = ? AND new_id IN (SELECT id FROM narrative_blueprints)",
        (blueprint_id,))})


def proposal_basis(conn: sqlite3.Connection, mode: str, predecessor_id: str | None = None) -> dict:
    """The exposed evidence, its bindings and the prompt view, from one read snapshot."""
    from .study_lineage import project_study_lineage

    lineage = project_study_lineage(conn)
    observations = sorted((i["record_data"] for i in lineage["items"]
                           if i["record"]["table"] == "observations" and i["event"] == "recorded"),
                          key=lambda r: (str(r.get("source_document_id")), r.get("page") or 0, r.get("paragraph") or 0,
                                         r.get("sentence") or 0, r["id"]))
    interpretations = sorted(((i["record_data"], i["authorship"]) for i in lineage["items"]
                              if i["record"]["table"] == "interpretations" and i["event"] == "recorded"),
                             key=lambda pair: (str(pair[0].get("created_at")), pair[0]["id"]))
    if len(observations) > MAX_OBSERVATIONS or len(interpretations) > MAX_INTERPRETATIONS:
        raise ProposalRefused("BASIS_TOO_LARGE", 409, "the eligible basis exceeds the v1 bound; scope selection is future work")
    obs_label = {row["id"]: f"O{n}" for n, row in enumerate(observations, 1)}
    exposed_ids = set(obs_label) | {row["id"] for row, _ in interpretations}
    ineligible = set()
    for table in ("observations", "interpretations"):
        try:
            ineligible |= {r[0] for r in conn.execute(f"SELECT id FROM {table}")} - exposed_ids
        except sqlite3.Error:
            pass
    predecessor = None
    if mode == "revise":
        row = _row(conn, "SELECT * FROM narrative_blueprints WHERE id = ?", (predecessor_id,)) if predecessor_id else None
        if row is None:
            raise ProposalRefused("PREDECESSOR_UNKNOWN", 404, "unknown predecessor Blueprint")
        if not any(i["record"] == {"table": "narrative_blueprints", "key": {"id": predecessor_id}} for i in lineage["items"]):
            raise ProposalRefused("PREDECESSOR_INELIGIBLE", 409, "the predecessor Blueprint is not eligible under the study's exclusions")
        content = blueprint_content(row)
        predecessor = {"content": content, "binding": {"id": predecessor_id, "sha256": _digest(content),
                                                      "successors_at_generation": _successors(conn, predecessor_id)}}
    interp_label = {row["id"]: f"I{n}" for n, (row, _a) in enumerate(interpretations, 1)}
    return {
        "mode": mode,
        "governing_question": governing_question(conn),
        "ineligible_ids": ineligible,
        "binding": {
            "policy_version": BASIS_POLICY,
            "observations": [{"label": obs_label[r["id"]], "id": r["id"], "sha256": _digest({k: r.get(k) for k in _OBSERVATION_FIELDS})}
                             for r in observations],
            "interpretations": [{"label": interp_label[r["id"]], "id": r["id"], "sha256": _digest(r), "authorship": a}
                                for r, a in interpretations],
        },
        "predecessor": predecessor,
        "view": {
            "observations": [{"label": obs_label[r["id"]], "page": r.get("page"), "raw_text": r.get("raw_text")} for r in observations],
            "interpretations": [{"label": interp_label[r["id"]], "authorship": a, "text": r.get("text"),
                                 "observation_label": obs_label.get(r.get("observation_id"), "an unexposed Observation")}
                                for r, a in interpretations],
        },
    }


def build_prompt(basis: dict, intent: str) -> str:
    view, labels = basis["view"], {**{o["id"]: o["label"] for o in basis["binding"]["observations"]},
                                   **{i["id"]: i["label"] for i in basis["binding"]["interpretations"]}}
    lines = [*HEADER, "", INTENT_INTRO, "<<<", intent, ">>>"]
    if basis["governing_question"]["status"] == "captured":
        lines += ["", GOVERNING_INTRO, basis["governing_question"]["text"]]
    lines += ["", OBSERVATIONS_INTRO]
    lines += [OBSERVATION_LINE.format(n=o["label"][1:], page=o["page"], raw_text=o["raw_text"]) for o in view["observations"]] or [NONE_LINE]
    lines += ["", INTERPRETATIONS_INTRO]
    lines += [INTERPRETATION_LINE.format(n=i["label"][1:], authorship=AUTHORSHIP_LABELS.get(i["authorship"], AUTHORSHIP_LABELS["unknown"]),
                                         observation_label=i["observation_label"], text=i["text"])
              for i in view["interpretations"]] or [NONE_LINE]
    if basis["mode"] == "revise":
        content = basis["predecessor"]["content"]
        lines += ["", PREDECESSOR_INTRO, PREDECESSOR_LINES[0].format(title=content["title"]),
                  PREDECESSOR_LINES[1].format(thesis=content["thesis"])]
        for k, section in enumerate(content["sections"], 1):
            cited = [labels.get(r, r) for r in [*section.get("supporting_observations", []), *section.get("supporting_interpretations", [])]]
            lines.append(PREDECESSOR_LINES[2].format(k=k, claim=section["claim"], labels=", ".join(cited)))
    lines += ["", RETURN_INTRO, REVISE_SHAPE if basis["mode"] == "revise" else CREATE_SHAPE, "", RULES_INTRO, *RULES]
    if basis["mode"] == "revise":
        lines.append(REVISE_RULE)
    return "\n".join(lines)


# ── Strict model output ──────────────────────────────────────────────────────

def _strict(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def parse_output(text: str, basis: dict) -> dict:
    """The model's proposal with labels resolved to exposed records; refuses rather than repairs."""
    match = _FENCE.match(text) if isinstance(text, str) else None
    try:
        value = json.loads(match.group(1) if match else text, object_pairs_hook=_strict)
    except (ValueError, TypeError) as exc:
        raise ProposalRefused("PROPOSAL_OUTPUT_UNPARSEABLE", 422) from exc
    if not isinstance(value, dict):
        raise ProposalRefused("PROPOSAL_OUTPUT_UNPARSEABLE", 422)

    def invalid(detail):
        raise ProposalRefused("PROPOSAL_OUTPUT_INVALID", 422, detail)

    def text_of(item, name):
        if not isinstance(item, str) or not item.strip():
            invalid(f"{name} must be a non-blank string")
        return item.strip()

    revise = basis["mode"] == "revise"
    if set(value) != ({"title", "thesis", "sections", "change_summary"} if revise else {"title", "thesis", "sections"}):
        invalid("exact fields required")
    title, thesis = text_of(value["title"], "title"), text_of(value["thesis"], "thesis")
    explanation = text_of(value["change_summary"], "change_summary") if revise else None
    if not isinstance(value["sections"], list) or not 1 <= len(value["sections"]) <= MAX_SECTIONS:
        invalid("between 1 and 12 sections")
    shaped = []
    for section in value["sections"]:
        if not isinstance(section, dict) or set(section) != {"claim", "observations", "interpretations"}:
            invalid("a section is {claim, observations, interpretations}")
        claim = text_of(section["claim"], "claim")
        for key in ("observations", "interpretations"):
            refs = section[key]
            if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs) or len(set(refs)) != len(refs):
                invalid(f"{key} must be a list of distinct labels")
        shaped.append((claim, section["observations"], section["interpretations"]))
    obs = {o["label"]: o["id"] for o in basis["binding"]["observations"]}
    interps = {i["label"]: i["id"] for i in basis["binding"]["interpretations"]}

    def resolve(token, table):
        if token in table:
            return table[token]
        code = "PROPOSAL_REFERENCE_EXCLUDED" if token.strip() in basis["ineligible_ids"] else "PROPOSAL_REFERENCE_UNKNOWN"
        raise ProposalRefused(code, 422, "a reference is not an exposed label")

    sections = [{"claim": claim, "supporting_observations": [resolve(t, obs) for t in o],
                 "supporting_interpretations": [resolve(t, interps) for t in i]} for claim, o, i in shaped]
    return {"blueprint": {"title": title, "thesis": thesis, "sections": sections}, "model_explanation": explanation}


# ── Candidate ────────────────────────────────────────────────────────────────

def candidate_id(candidate: dict) -> str:
    body = {key: candidate[key] for key in ("schema", "mode", "binding", "extraction", "proposal")}
    return "blueprint-proposal-candidate:sha256:" + hashlib.sha256(_CANDIDATE_DOMAIN + canonical_bytes(body)).hexdigest()


def build_candidate(basis: dict, *, intent: str, prompt: str, execution: dict, output: str,
                    created_at: str, completed_at: str) -> dict:
    proposal = parse_output(output, basis)
    candidate = {
        "schema": CANDIDATE_SCHEMA, "mode": basis["mode"],
        "binding": {"intent": {"text": intent, "sha256": text_digest(intent)},
                    "governing_question": basis["governing_question"], "basis": basis["binding"],
                    "predecessor": basis["predecessor"]["binding"] if basis["predecessor"] else None},
        "extraction": {"policy_version": POLICY_VERSION, "prompt_version": PROMPT_VERSION, "prompt": prompt,
                       "prompt_sha256": text_digest(prompt), "execution": json.loads(canonical_bytes(execution)),
                       "created_at": created_at, "completed_at": completed_at, "output": output, "output_sha256": text_digest(output)},
        "proposal": proposal,
    }
    candidate["candidate_id"] = candidate_id(candidate)
    return candidate


def stale_reasons(conn: sqlite3.Connection, candidate: dict) -> list[str]:
    """Bound inputs only: exposed records, a captured governing question, the predecessor."""
    from .study_lineage import project_study_lineage

    lineage = project_study_lineage(conn)
    eligible = {(i["record"]["table"], i["record"]["key"].get("id")): i for i in lineage["items"] if i["event"] == "recorded"}
    reasons = []
    for entry in candidate["binding"]["basis"]["observations"]:
        item = eligible.get(("observations", entry["id"]))
        if item is None or _digest({k: item["record_data"].get(k) for k in _OBSERVATION_FIELDS}) != entry["sha256"]:
            reasons.append(f"observation {entry['label']} is missing, changed or ineligible")
    for entry in candidate["binding"]["basis"]["interpretations"]:
        item = eligible.get(("interpretations", entry["id"]))
        if item is None or _digest(item["record_data"]) != entry["sha256"]:
            reasons.append(f"interpretation {entry['label']} is missing, changed or ineligible")
    bound_question = candidate["binding"]["governing_question"]
    if bound_question["status"] == "captured" and governing_question(conn) != bound_question:
        reasons.append("the governing question changed")
    predecessor = candidate["binding"]["predecessor"]
    if predecessor is not None:
        item = eligible.get(("narrative_blueprints", predecessor["id"]))
        if item is None or _digest(blueprint_content(item["record_data"])) != predecessor["sha256"]:
            reasons.append("the predecessor is missing, changed or ineligible")
        elif _successors(conn, predecessor["id"]) != predecessor["successors_at_generation"]:
            reasons.append("the predecessor was revised after generation")
    return reasons


# ── Acceptance receipt (append-only) ─────────────────────────────────────────

def receipt_id(receipt: dict) -> str:
    body = {key: value for key, value in receipt.items() if key != "id"}
    return "blueprint-proposal-acceptance:sha256:" + hashlib.sha256(_RECEIPT_DOMAIN + canonical_bytes(body)).hexdigest()


def make_receipt(candidate: dict, *, decision: str, accepted_blueprint: dict, result: dict, rationale: str | None,
                 accepted_at: str) -> dict:
    receipt = {
        "schema": RECEIPT_SCHEMA, "mode": candidate["mode"], "origin": {"kind": ORIGINS[decision]},
        "candidate": candidate, "result": result,
        "acceptance": {"decision": decision, "actor": "local_steward", "actor_identity": "unknown", "accepted_at": accepted_at,
                       "reviewed_candidate_id": candidate["candidate_id"], "accepted_blueprint": accepted_blueprint,
                       "edited": decision == "edit_and_accept", "rationale": rationale, "meaning": MEANING},
    }
    receipt["id"] = receipt_id(receipt)
    return validate_receipt(json.loads(canonical_bytes(receipt)))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidReceipt(message)


def validate_receipt(receipt) -> dict:
    """Self-contained integrity: shape, identities, origin and decision, rationale and result bindings."""
    _require(isinstance(receipt, dict) and set(receipt) == {"schema", "id", "mode", "origin", "candidate", "result", "acceptance"}
             and receipt["schema"] == RECEIPT_SCHEMA, "receipt fields")
    _require(receipt["id"] == receipt_id(receipt), "receipt identity digest mismatch")
    candidate, result, acceptance = receipt["candidate"], receipt["result"], receipt["acceptance"]
    _require(isinstance(candidate, dict) and candidate.get("schema") == CANDIDATE_SCHEMA
             and candidate.get("candidate_id") == candidate_id(candidate) == acceptance.get("reviewed_candidate_id"), "candidate binding")
    _require(candidate["mode"] == receipt["mode"] and candidate["extraction"]["policy_version"] == POLICY_VERSION
             and candidate["extraction"]["prompt_version"] == PROMPT_VERSION, "unsupported candidate policy")
    _require(candidate["extraction"]["prompt_sha256"] == text_digest(candidate["extraction"]["prompt"])
             and candidate["extraction"]["output_sha256"] == text_digest(candidate["extraction"]["output"])
             and candidate["binding"]["intent"]["sha256"] == text_digest(candidate["binding"]["intent"]["text"]), "candidate digests")
    _require(set(acceptance) == {"decision", "actor", "actor_identity", "accepted_at", "reviewed_candidate_id", "accepted_blueprint",
                                 "edited", "rationale", "meaning"} and acceptance["meaning"] == MEANING
             and acceptance["actor"] == "local_steward" and acceptance["actor_identity"] == "unknown", "acceptance fields")
    decision = acceptance["decision"]
    _require(ORIGINS.get(decision) == receipt["origin"].get("kind") and set(receipt["origin"]) == {"kind"}, "origin must match decision")
    _require(acceptance["edited"] == (decision == "edit_and_accept"), "edited flag must match decision")
    if decision == "accept":
        _require(acceptance["accepted_blueprint"] == candidate["proposal"]["blueprint"], "exact acceptance keeps the proposal")
    _require(set(result) == {"resulting_blueprint_id", "plan_id", "blueprint_preexisted", "predecessor_id", "supersession"}, "result fields")
    if receipt["mode"] == "revise":
        supersession = result["supersession"]
        _require(isinstance(acceptance["rationale"], str) and acceptance["rationale"].strip() == acceptance["rationale"]
                 and acceptance["rationale"], "a revision needs the steward rationale")
        _require(result["predecessor_id"] == candidate["binding"]["predecessor"]["id"]
                 and isinstance(supersession, dict) and set(supersession) == {"old_id", "new_id", "reason", "ratified_at"}
                 and supersession["old_id"] == result["predecessor_id"] and supersession["new_id"] == result["resulting_blueprint_id"]
                 and supersession["reason"] == acceptance["rationale"], "revision result binding")
    else:
        _require(acceptance["rationale"] is None and result["predecessor_id"] is None and result["supersession"] is None, "create result binding")
    return receipt


def receipt_from_row(row) -> dict:
    row = dict(row)
    _require(set(row) == {"id", "candidate_id", "receipt_json"} and isinstance(row["receipt_json"], str), "row columns")
    receipt = json.loads(row["receipt_json"], object_pairs_hook=_strict)
    _require(canonical_bytes(receipt).decode("utf-8") == row["receipt_json"], "stored bytes are not canonical")
    validate_receipt(receipt)
    _require(row["id"] == receipt["id"] and row["candidate_id"] == receipt["candidate"]["candidate_id"], "row identity mismatch")
    return receipt


def ensure_blueprint_proposal_tables(conn: sqlite3.Connection) -> None:
    """Explicit additive initialization; never called by reads."""
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL UNIQUE, receipt_json TEXT NOT NULL)")
    for operation in ("UPDATE", "DELETE"):
        conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_{operation.lower()} BEFORE {operation} ON {TABLE} "
                     "BEGIN SELECT RAISE(ABORT, 'Blueprint proposal acceptance immutable'); END")
    conn.execute(f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_replace BEFORE INSERT ON {TABLE} "
                 f"WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE id=NEW.id OR candidate_id=NEW.candidate_id) "
                 "BEGIN SELECT RAISE(ABORT, 'Blueprint proposal acceptance already exists'); END")


def _row(conn, sql, parameters):
    cursor = conn.execute(sql, parameters)
    raw = cursor.fetchone()
    return dict(zip((c[0] for c in cursor.description), raw)) if raw is not None else None


def store_receipt(conn: sqlite3.Connection, receipt: dict) -> dict:
    """Insert inside the caller's write transaction, then reread and validate."""
    validate_receipt(receipt)
    conn.execute(f"INSERT INTO {TABLE} (id, candidate_id, receipt_json) VALUES (?, ?, ?)",
                 (receipt["id"], receipt["candidate"]["candidate_id"], canonical_bytes(receipt).decode("utf-8")))
    return receipt_from_row(_row(conn, f"SELECT * FROM {TABLE} WHERE id = ?", (receipt["id"],)))


def load_receipt(conn: sqlite3.Connection, identifier: str) -> dict | None:
    row = _row(conn, f"SELECT * FROM {TABLE} WHERE id = ?", (identifier,))
    return receipt_from_row(row) if row is not None else None


def _replay_basis(conn: sqlite3.Connection, candidate: dict) -> dict:
    """The prompt view rebuilt from the bound records themselves (immutable rows), not from current eligibility."""
    binding = candidate["binding"]
    obs_rows, view_obs, labels = {}, [], {}
    for entry in binding["basis"]["observations"]:
        row = _row(conn, "SELECT * FROM observations WHERE id = ?", (entry["id"],))
        _require(row is not None and _digest({k: row.get(k) for k in _OBSERVATION_FIELDS}) == entry["sha256"], "bound observation")
        obs_rows[entry["id"]] = row
        labels[entry["id"]] = entry["label"]
        view_obs.append({"label": entry["label"], "page": row.get("page"), "raw_text": row.get("raw_text")})
    view_interps = []
    for entry in binding["basis"]["interpretations"]:
        row = _row(conn, "SELECT * FROM interpretations WHERE id = ?", (entry["id"],))
        _require(row is not None and _digest(row) == entry["sha256"], "bound interpretation")
        view_interps.append({"label": entry["label"], "authorship": entry["authorship"], "text": row.get("text"),
                             "observation_label": labels.get(row.get("observation_id"), "an unexposed Observation")})
    predecessor = None
    if binding["predecessor"] is not None:
        row = _row(conn, "SELECT * FROM narrative_blueprints WHERE id = ?", (binding["predecessor"]["id"],))
        _require(row is not None and _digest(blueprint_content(row)) == binding["predecessor"]["sha256"], "bound predecessor")
        predecessor = {"content": blueprint_content(row), "binding": binding["predecessor"]}
    return {"mode": candidate["mode"], "governing_question": binding["governing_question"], "ineligible_ids": set(),
            "binding": binding["basis"], "predecessor": predecessor,
            "view": {"observations": view_obs, "interpretations": view_interps}}


def verify_receipt(conn: sqlite3.Connection, identifier: str) -> dict:
    """Read-only verification over one snapshot; the model is never called again."""
    own = not conn.in_transaction
    try:
        if own:
            conn.execute("BEGIN")
        result = {"record_integrity": "invalid", "candidate_replay": "unverified", "result_closure": "unverified",
                  "model_output": "preserved_not_replayed"}
        try:
            receipt = load_receipt(conn, identifier)
        except (InvalidReceipt, ValueError, KeyError, TypeError):
            return result
        if receipt is None:
            raise KeyError(identifier)
        result["record_integrity"] = "valid"
        candidate = receipt["candidate"]
        try:
            basis = _replay_basis(conn, candidate)
            same = (build_prompt(basis, candidate["binding"]["intent"]["text"]) == candidate["extraction"]["prompt"]
                    and parse_output(candidate["extraction"]["output"], basis) == candidate["proposal"])
            result["candidate_replay"] = "verified" if same else "mismatch"
        except (InvalidReceipt, ProposalRefused, ValueError, KeyError, TypeError):
            result["candidate_replay"] = "mismatch"
        outcome = receipt["result"]
        row = _row(conn, "SELECT * FROM narrative_blueprints WHERE id = ?", (outcome["resulting_blueprint_id"],))
        accepted = receipt["acceptance"]["accepted_blueprint"]
        closed = (row is not None and {k: v for k, v in blueprint_content(row).items() if k != "id"} == accepted
                  and _row(conn, "SELECT id FROM architect_plans WHERE id = ? AND blueprint_id = ?",
                           (outcome["plan_id"], outcome["resulting_blueprint_id"])) is not None)
        if receipt["mode"] == "revise":
            edge = outcome["supersession"]
            closed = closed and _row(conn, "SELECT * FROM supersession_relations WHERE old_id=? AND new_id=? AND reason=? AND ratified_at=?",
                                     (edge["old_id"], edge["new_id"], edge["reason"], edge["ratified_at"])) is not None
        result["result_closure"] = "verified" if closed else "mismatch"
        return result
    finally:
        if own and conn.in_transaction:
            conn.rollback()
