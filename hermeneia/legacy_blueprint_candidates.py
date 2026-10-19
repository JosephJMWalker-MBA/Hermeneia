"""Governed candidates for the two legacy Blueprint generators (#251, contract v1.1).

In the non-default `proposal` mode of LEGACY_BLUEPRINT_WRITES, the legacy
Architect generator (`/api/architect/generate`) and the onboarding extractor
(`/api/pipeline/extract-blueprint`) only propose. Each proposal becomes a
server-held candidate that binds the complete input, the records shown, the
exact prompt, the recorded execution and the raw output (CI-011). Only an
explicit steward decision through the unchanged P8 accept route commits it,
with the P8 acceptance receipt. Nothing here writes. Nothing here establishes
that either legacy generator is competent.
Contract: docs/design/r251-legacy-blueprint-remediation-v1.1.md.
"""
from __future__ import annotations

import json
import re
import sqlite3

from .blueprint_proposals import _OBSERVATION_FIELDS, ProposalRefused, _digest, _row, candidate_id, text_digest

ARCHITECT_SCHEMA = "hermeneia.legacy-architect-candidate/v1"
EXTRACT_SCHEMA = "hermeneia.legacy-extract-candidate/v1"
SCHEMAS = (ARCHITECT_SCHEMA, EXTRACT_SCHEMA)
POLICY_VERSION = "1.0.0"
PROMPT_VERSIONS = {ARCHITECT_SCHEMA: "legacy-architect/v1", EXTRACT_SCHEMA: "legacy-extract/v1"}
BASIS_POLICIES = {ARCHITECT_SCHEMA: "legacy-architect-basis/v1", EXTRACT_SCHEMA: "legacy-extract-basis/v1"}
ABSENT_QUESTION = {"status": "absent", "text": None, "sha256": None}
EXTRACT_MAX_INPUT_CHARS = 40_000  # the extractor's own default, bound explicitly
OBSERVATION_LINE = "{label} (p.{page}) [{role_note}]: {text}"
INTERPRETATION_LINE = "{label} [{observation_label}] [{evidential_status}] [{role_note}]: {text}"


class ReferencesInvalid(ProposalRefused):
    """The model cited references that are unresolved, of the wrong type, excluded or not shown."""

    def __init__(self, invalid_references: list[dict]):
        super().__init__("BLUEPRINT_REFERENCE_INVALID", 422)
        self.invalid_references = invalid_references


# ── The legacy Architect prompt (prompt_version legacy-architect/v1) ─────────

def role_note(source_role, filename) -> str:
    role = source_role or "primary"
    return ("primary evidence" if role == "primary"
            else f"NON-PRIMARY {role} evidence from {filename}; do not treat as primary")


def architect_prompt(directive: str, view: dict) -> str:
    """The route's original prompt f-string, moved verbatim; tests pin it to a golden capture from d38fdbc."""
    interp_lines = [INTERPRETATION_LINE.format(**entry) for entry in view["interpretations"]]
    obs_lines = [OBSERVATION_LINE.format(**entry) for entry in view["observations"]]
    observations_total = view["observations_total"]
    return f"""You are the Hermeneia Architect. Your job is evidence-first research design, not thesis generation.

RESEARCH DIRECTIVE:
{directive}

CRITICAL INSTRUCTION — READ BEFORE PROCEEDING:
Do NOT start from a thesis and find supporting evidence.
Start from the evidence and let the structure emerge.

SOURCE ROLE RULE:
Excluded documents are absent from this prompt. If a line is labelled NON-PRIMARY,
preserve that role in reasoning and do not treat commentary, reference, notes, or
exploratory material as primary evidence.

Your process must be:
1. Survey the observations and interpretations for everything relevant to the directive
2. Group related evidence into distinct analytical sections
3. State a claim for each section that the evidence actually supports
4. Derive a thesis LAST, as a synthesis of what the sections establish

For a directive about metaphors, each section should be ONE metaphor or metaphor cluster with ALL its relevant observations. A 10-page analysis requires 8–12 sections minimum. Do not collapse multiple distinct metaphors into one section.

ACCEPTED INTERPRETATIONS ({len(interp_lines)} total):
{chr(10).join(interp_lines) or '(none yet — use observations only)'}

OBSERVATION SAMPLE ({len(obs_lines)} of {observations_total} total):
{chr(10).join(obs_lines)}

RULES:
- Each section = one distinct idea, metaphor, motif, or analytical point
- Each section must cite at least one OBS-N from the list above
- Do not invent observations or interpretations not in the lists above
- Aim for 8–12 sections for a research assignment; do not compress
- The thesis is derived from the sections, not imposed on them

Return ONLY valid JSON, no markdown, no explanation:
{{
  "title": "descriptive title for this analysis",
  "thesis": "one-sentence thesis synthesized from all sections below",
  "sections": [
    {{
      "claim": "the specific analytical claim this section establishes",
      "obs_refs": ["OBS-19", "OBS-23"],
      "interp_refs": ["INTERP-ab12cd34"]
    }}
  ]
}}"""


# ── Exact references (v1 §4; moved unchanged from the governed route) ────────

def _text(value) -> str:
    return str(value).strip() if value is not None else ""


def strict_architect_references(ai_sections: list, shown_numbers: set, shown_interps: list, hidden_prefixes: set):
    """Exact OBS-n / INTERP-xxxxxxxx references to records shown in the prompt; every failure itemized.

    `shown_numbers` is {(n, observation_id)}; `shown_interps` are records with an "id"; `hidden_prefixes`
    are the 8-character prefixes of Interpretations that exist but were not shown (reason "excluded").
    """
    prefixes: dict[str, list[str]] = {}
    for interp in shown_interps:
        prefixes.setdefault(interp["id"][:8], []).append(interp["id"])
    hidden = set(hidden_prefixes) - set(prefixes)
    n_to_id = {n: oid for n, oid in shown_numbers}
    invalid, resolved = [], []
    for index, sec in enumerate(ai_sections, 1):  # numbered as the model returned them
        obs_ids, interp_ids = [], []
        if not _text(sec.get("claim")):  # a claimless section is skipped, as before (#244)
            resolved.append((obs_ids, interp_ids))
            continue
        for ref in sec.get("obs_refs", []):
            token = str(ref).strip()
            obs = re.fullmatch(r"OBS-(\d+)", token)
            if obs and int(obs.group(1)) in n_to_id:
                obs_ids.append(n_to_id[int(obs.group(1))])
                continue
            reason = "unshown" if obs else "wrong_type" if re.fullmatch(r"INTERP-[0-9a-f]{8}", token) else "unresolved"
            invalid.append({"section": index, "field": "obs_refs", "ref": ref, "reason": reason})
        for ref in sec.get("interp_refs", []):
            token = str(ref).strip()
            found = re.fullmatch(r"INTERP-([0-9a-f]{8})", token)
            matches = prefixes.get(found.group(1), []) if found else []
            if len(matches) == 1:
                interp_ids.append(matches[0])
                continue
            reason = ("ambiguous" if len(matches) > 1 else "excluded" if found and found.group(1) in hidden
                      else "unknown" if found else "wrong_type" if re.fullmatch(r"OBS-\d+", token) else "unresolved")
            invalid.append({"section": index, "field": "interp_refs", "ref": ref, "reason": reason})
        resolved.append((obs_ids, interp_ids))
    return resolved, invalid


def parse_architect_output(output: str, view: dict, hidden_prefixes: frozenset = frozenset()) -> dict:
    """The legacy parse (fence stripping, null title, required thesis and sections) with exact references.

    Refuses rather than repairs: an unparseable or invalid reply, or any inexact reference, holds no candidate.
    """
    cleaned = re.sub(r"^```[a-z]*\n?|```$", "", output.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError) as exc:
        raise ProposalRefused("PROPOSAL_OUTPUT_UNPARSEABLE", 422, "the reply is not one JSON object") from exc
    if not isinstance(data, dict):
        raise ProposalRefused("PROPOSAL_OUTPUT_UNPARSEABLE", 422, "the reply is not one JSON object")
    title = "Untitled Blueprint" if data.get("title") is None else _text(data["title"])
    thesis, sections = _text(data.get("thesis")), data.get("sections", [])
    if not title or not thesis or not sections:
        raise ProposalRefused("PROPOSAL_OUTPUT_INVALID", 422, "title, thesis and sections are required")
    if not isinstance(sections, list) or not all(
            isinstance(s, dict) and isinstance(s.get("obs_refs", []), list) and isinstance(s.get("interp_refs", []), list)
            for s in sections):
        raise ProposalRefused("PROPOSAL_OUTPUT_INVALID", 422, "sections must be objects with list references")
    resolved, invalid = strict_architect_references(
        sections, {(int(o["label"][4:]), o["id"]) for o in view["observations"]}, view["interpretations"], hidden_prefixes)
    if invalid:
        raise ReferencesInvalid(invalid)
    shaped = [{"claim": _text(sec.get("claim")), "supporting_observations": obs_ids, "supporting_interpretations": interp_ids}
              for sec, (obs_ids, interp_ids) in zip(sections, resolved) if _text(sec.get("claim"))]
    if not shaped:
        raise ProposalRefused("PROPOSAL_OUTPUT_INVALID", 422, "no section has a claim")
    return {"title": title, "thesis": thesis, "sections": shaped}


# ── Bindings and candidates ──────────────────────────────────────────────────

def architect_binding(conn: sqlite3.Connection, directive: str, view: dict) -> dict:
    """Bind every record shown, with P8's digest conventions, from one Lineage projection."""
    from .study_lineage import project_study_lineage

    items = {(i["record"]["table"], i["record"]["key"].get("id")): i
             for i in project_study_lineage(conn)["items"] if i["event"] == "recorded"}
    observations, interpretations = [], []
    for entry in view["observations"]:
        item = items.get(("observations", entry["id"]))
        if item is None:
            raise ProposalRefused("BASIS_INELIGIBLE", 409, "a shown Observation is not eligible under Study Lineage")
        observations.append({"label": entry["label"], "id": entry["id"],
                             "sha256": _digest({k: item["record_data"].get(k) for k in _OBSERVATION_FIELDS})})
    for entry in view["interpretations"]:
        item = items.get(("interpretations", entry["id"]))
        if item is None:
            raise ProposalRefused("BASIS_INELIGIBLE", 409, "a shown Interpretation is not eligible under Study Lineage")
        interpretations.append({"label": entry["label"], "id": entry["id"], "sha256": _digest(item["record_data"]),
                                "authorship": item["authorship"]})
    return {"directive": {"text": directive, "sha256": text_digest(directive)}, "governing_question": dict(ABSENT_QUESTION),
            "basis": {"policy_version": BASIS_POLICIES[ARCHITECT_SCHEMA], "observations": observations,
                      "interpretations": interpretations},
            "predecessor": None, "view": view}


def _extraction(schema: str, *, prompt: str, execution: dict, output: str, created_at: str, completed_at: str, **extra) -> dict:
    return {"policy_version": POLICY_VERSION, "prompt_version": PROMPT_VERSIONS[schema], **extra, "prompt": prompt,
            "prompt_sha256": text_digest(prompt), "execution": json.loads(json.dumps(execution)), "created_at": created_at,
            "completed_at": completed_at, "output": output, "output_sha256": text_digest(output)}


def _finish(candidate: dict) -> dict:
    candidate["candidate_id"] = candidate_id(candidate)
    validate_candidate(candidate)
    return candidate


def architect_candidate(binding: dict, *, prompt: str, execution: dict, output: str, created_at: str, completed_at: str,
                        hidden_prefixes: frozenset = frozenset()) -> dict:
    blueprint = parse_architect_output(output, binding["view"], hidden_prefixes)
    return _finish({"schema": ARCHITECT_SCHEMA, "mode": "create", "binding": binding,
                    "extraction": _extraction(ARCHITECT_SCHEMA, prompt=prompt, execution=execution, output=output,
                                              created_at=created_at, completed_at=completed_at),
                    "proposal": {"blueprint": blueprint, "model_explanation": None}})


def parse_extract_output(output: str) -> dict:
    """The extractor's own parser; a blank title or thesis is refused rather than committed."""
    from .compiler.blueprint_extractor import BlueprintExtractionError, parse_extraction

    try:
        blueprint = parse_extraction(output)
    except BlueprintExtractionError as exc:
        raise ProposalRefused("PROPOSAL_OUTPUT_UNPARSEABLE", 422, "the extractor could not parse the reply") from exc
    if not blueprint["title"] or not blueprint["thesis"]:
        raise ProposalRefused("PROPOSAL_OUTPUT_INVALID", 422, "title and thesis are required")
    return blueprint


def extract_candidate(*, source_text: str, max_input_chars: int, system_prompt: str, prompt: str, execution: dict,
                      output: str, created_at: str, completed_at: str) -> dict:
    blueprint = parse_extract_output(output)
    binding = {"source_text": {"text": source_text, "sha256": text_digest(source_text)}, "max_input_chars": max_input_chars,
               "governing_question": dict(ABSENT_QUESTION),
               "basis": {"policy_version": BASIS_POLICIES[EXTRACT_SCHEMA], "observations": [], "interpretations": []},
               "predecessor": None}
    return _finish({"schema": EXTRACT_SCHEMA, "mode": "create", "binding": binding,
                    "extraction": _extraction(EXTRACT_SCHEMA, prompt=prompt, execution=execution, output=output,
                                              created_at=created_at, completed_at=completed_at, system_prompt=system_prompt,
                                              system_prompt_sha256=text_digest(system_prompt)),
                    "proposal": {"blueprint": blueprint, "model_explanation": None}})


# ── Receipt integrity and independent replay ─────────────────────────────────

def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_candidate(candidate: dict) -> dict:
    """Self-contained integrity of a legacy candidate (shape, versions, digests, bindings); raises ValueError."""
    schema = candidate.get("schema") if isinstance(candidate, dict) else None
    _check(schema in SCHEMAS, "unsupported legacy candidate schema")
    _check(set(candidate) == {"schema", "mode", "binding", "extraction", "proposal", "candidate_id"}
           and candidate["mode"] == "create" and candidate["candidate_id"] == candidate_id(candidate), "candidate identity")
    extraction, binding, proposal = candidate["extraction"], candidate["binding"], candidate["proposal"]
    fields = {"policy_version", "prompt_version", "prompt", "prompt_sha256", "execution", "created_at", "completed_at",
              "output", "output_sha256"}
    if schema == EXTRACT_SCHEMA:
        fields |= {"system_prompt", "system_prompt_sha256"}
    _check(set(extraction) == fields and extraction["policy_version"] == POLICY_VERSION
           and extraction["prompt_version"] == PROMPT_VERSIONS[schema], "unsupported legacy extraction policy")
    _check(extraction["prompt_sha256"] == text_digest(extraction["prompt"])
           and extraction["output_sha256"] == text_digest(extraction["output"])
           and (schema != EXTRACT_SCHEMA or extraction["system_prompt_sha256"] == text_digest(extraction["system_prompt"])),
           "extraction digests")
    execution = extraction["execution"]
    _check(isinstance(execution, dict) and _nonblank(execution.get("provider_id")) and _nonblank(execution.get("model_id")),
           "a CI-011 record needs provider and model identity")
    _check(binding.get("governing_question") == ABSENT_QUESTION and binding.get("predecessor") is None
           and binding["basis"]["policy_version"] == BASIS_POLICIES[schema], "legacy binding")
    basis = binding["basis"]
    if schema == ARCHITECT_SCHEMA:
        _check(set(binding) == {"directive", "governing_question", "basis", "predecessor", "view"}
               and binding["directive"]["sha256"] == text_digest(binding["directive"]["text"]), "directive binding")
        view = binding["view"]
        _check(set(view) == {"observations", "interpretations", "observations_total"}
               and isinstance(view["observations_total"], int), "view")
        for key in ("observations", "interpretations"):
            _check([(e["label"], e["id"]) for e in view[key]] == [(e["label"], e["id"]) for e in basis[key]],
                   f"view and basis disagree on {key}")
    else:
        _check(set(binding) == {"source_text", "max_input_chars", "governing_question", "basis", "predecessor"}
               and binding["source_text"]["sha256"] == text_digest(binding["source_text"]["text"])
               and isinstance(binding["max_input_chars"], int) and basis["observations"] == basis["interpretations"] == [],
               "source binding")
    _check(set(proposal) == {"blueprint", "model_explanation"} and proposal["model_explanation"] is None, "proposal")
    blueprint = proposal["blueprint"]
    _check(set(blueprint) == {"title", "thesis", "sections"} and _nonblank(blueprint["title"]) and _nonblank(blueprint["thesis"])
           and isinstance(blueprint["sections"], list) and blueprint["sections"], "proposed Blueprint")
    bound = {"supporting_observations": {e["id"] for e in basis["observations"]},
             "supporting_interpretations": {e["id"] for e in basis["interpretations"]}}
    for section in blueprint["sections"]:
        _check(set(section) == {"claim", *bound} and _nonblank(section["claim"])
               and all(isinstance(section[k], list) and set(section[k]) <= bound[k] for k in bound),
               "a proposed section cites only bound records")
    return candidate


def replay_matches(conn: sqlite3.Connection, candidate: dict) -> bool:
    """Bound records unchanged, view text derived from them, prompt rebuilt and output re-parsed; no model call."""
    binding, extraction = candidate["binding"], candidate["extraction"]
    blueprint = candidate["proposal"]["blueprint"]
    if candidate["schema"] == EXTRACT_SCHEMA:
        from .compiler.blueprint_extractor import extraction_request

        system, user = extraction_request(binding["source_text"]["text"], max_input_chars=binding["max_input_chars"])
        return (system == extraction["system_prompt"] and user == extraction["prompt"]
                and parse_extract_output(extraction["output"]) == blueprint)
    view = binding["view"]
    for entry, shown in zip(binding["basis"]["observations"], view["observations"]):
        row = _row(conn, "SELECT * FROM observations WHERE id = ?", (entry["id"],))
        if (row is None or _digest({k: row.get(k) for k in _OBSERVATION_FIELDS}) != entry["sha256"]
                or shown["text"] != row["raw_text"][:200] or shown["page"] != row["page"]):
            return False
    for entry, shown in zip(binding["basis"]["interpretations"], view["interpretations"]):
        row = _row(conn, "SELECT * FROM interpretations WHERE id = ?", (entry["id"],))
        if (row is None or _digest(row) != entry["sha256"] or shown["text"] != row["text"]
                or shown["evidential_status"] != row["evidential_status"]):
            return False
    return (architect_prompt(binding["directive"]["text"], view) == extraction["prompt"]
            and parse_architect_output(extraction["output"], view) == blueprint)
