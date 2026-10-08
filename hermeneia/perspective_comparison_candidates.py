"""Structured Perspective Comparison Layer 2 (#215 P7): governed, traceable comparison candidates.

A model may propose comparison structure over a deterministic Layer 1
comparison. Nothing it proposes is admitted unless it is traceable to the exact
text of the participant it is attributed to; untraced items stay unknown.
Agreement, disagreement, minorities and evidence use are never taken from the
model: they are derived here from traced positions. Candidates are transient;
only an explicit steward decision creates a durable record
(accepted_perspective_comparisons). No truth, majority, verdict or
adjudication is represented. Contract: docs/design/perspective-comparison-layer2-v1.md.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
import json
import re
import sqlite3

from .perspective_comparison import (
    POLICY_VERSION as LAYER1_POLICY_VERSION, SCHEMA as LAYER1_SCHEMA, _supplied, _units, compare_retained_perspectives,
)
from .perspective_execution_receipts import canonical_bytes, receipt_from_row

STRUCTURE_SCHEMA = "hermeneia.perspective-comparison-structure/v1"
CANDIDATE_SCHEMA = "hermeneia.perspective-comparison-candidate/v1"
EXTRACTION_POLICY_VERSION = "1.0.0"
PROMPT_VERSION = "perspective-comparison-extraction/v1"
# Experimental policy 1.1.0 (docs/design/perspective-comparison-extraction-v1.1.md): opt-in, never acceptable.
EXPERIMENTAL_POLICY_VERSION = "1.1.0"
PROMPT_VERSION_V1_1 = "perspective-comparison-extraction/v1.1"
MAX_ITEMS = 50
STANCES = ("asserts", "denies", "unclassifiable", "does_not_address", "unknown")
SPAN_STANCES = frozenset({"asserts", "denies", "unclassifiable"})
UNTRACEABLE_KINDS = frozenset({"untraceable_position", "contradictory_position", "position_not_classified",
                               "reliance_outside_supplied_scope", "untraceable_proposition", "untraceable_assumption"})
AUTHORITY_KEYS = frozenset({"truth", "true", "correct", "correctness", "best", "winner", "majority", "consensus",
                            "verdict", "adjudication", "answer", "synthesis", "score", "confidence", "probability"})
_LAYER1_DOMAIN = b"hermeneia.perspective-comparison/v1\0"
_CANDIDATE_DOMAIN = b"hermeneia.perspective-comparison-candidate/v1\0"
_LAYER1_CORE = ("schema", "policy_version", "comparison_id", "question", "participants", "evidence", "relations")
_FENCE = re.compile(r"\A\s*```(?:json)?[ \t]*\n(.*)\n[ \t]*```\s*\Z", re.S)
_OUTPUT_STANCES = ("asserts", "denies", "does_not_address", "unclassifiable")


class ExtractionRefused(ValueError):
    """Model output violates the extraction contract; no candidate exists."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class StructureRefused(ValueError):
    """A steward-supplied structure is invalid or untraceable; nothing is accepted."""

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def text_digest(text: str) -> str:
    return _digest(text.encode("utf-8"))


def layer1_digest(layer1: dict) -> str:
    """Digest of the participant-determined Layer 1 core; coverage and uncertainty are snapshot context."""
    return _digest(_LAYER1_DOMAIN + canonical_bytes({key: layer1[key] for key in _LAYER1_CORE}))


def _key(ref: dict) -> tuple[str, str]:
    return ref["table"], ref["key"]["id"]


def _ref(key: tuple[str, str]) -> dict:
    return {"table": key[0], "key": {"id": key[1]}}


# ── The comparison view: everything Layer 2 reads, from Layer 1 or from bound receipts ──

def view_from_layer1(layer1: dict) -> dict:
    roles: dict[str, dict] = {p["receipt_id"]: {} for p in layer1["participants"]}
    for unit in layer1["evidence"]["units"]:
        for holder in unit["supplied_to"]:
            roles[holder["receipt_id"]][_key(unit["ref"])] = list(holder["roles"])
    return {"question": layer1["question"]["text"],
            "units": [_key(unit["ref"]) for unit in layer1["evidence"]["units"]],
            "participants": [{"receipt_id": p["receipt_id"], "label": p["perspective"]["label"],
                              "perspective_id": p["perspective"]["id"], "response": p["response"],
                              "units": roles[p["receipt_id"]]} for p in layer1["participants"]]}


def view_from_receipts(receipts: list[dict]) -> dict:
    """The same view rebuilt from bound receipts alone (no eligibility), for replay."""
    participants = []
    for receipt in receipts:
        units = _units(_supplied(receipt))
        participants.append({"receipt_id": receipt["id"], "label": receipt["run"]["perspective"]["definition"]["label"],
                             "perspective_id": receipt["run"]["perspective"]["id"], "response": receipt["run"]["response"],
                             "units": {key: sorted(value["roles"]) for key, value in units.items()}})
    return {"question": receipts[0]["run"]["question"],
            "units": sorted({key for p in participants for key in p["units"]}),
            "participants": participants}


def unit_texts(conn: sqlite3.Connection, view: dict, receipts: list[dict]) -> dict:
    """Canonical text of each unit: extraction raw_text; a highlight's captured text from the receipts."""
    texts = {}
    for table, identifier in view["units"]:
        if table == "source_extractions":
            row = conn.execute("SELECT raw_text FROM source_extractions WHERE id = ?", (identifier,)).fetchone()
            if row is None or not isinstance(row[0], str):
                raise ValueError("A supplied source extraction is unavailable")
            texts[(table, identifier)] = row[0]
        else:
            parts = [part for receipt in receipts for part in receipt["run"]["scope_receipt"]["supporting"]
                     if part["kind"] == "reader_highlight" and part["id"] == identifier]
            texts[(table, identifier)] = parts[0]["text"]
    return texts


def governing_question_snapshot(conn: sqlite3.Connection) -> dict:
    try:
        row = conn.execute("SELECT thesis FROM workspace_investigation WHERE id = 'current'").fetchone()
    except sqlite3.Error:
        row = None
    text = row[0] if row is not None and isinstance(row[0], str) and row[0].strip() else None
    return {"status": "captured" if text is not None else "absent", "text": text,
            "sha256": text_digest(text) if text is not None else None, "basis": "current_snapshot_at_generation"}


def candidate_inputs(conn: sqlite3.Connection, evidence, receipt_ids: list[str]) -> dict:
    """Layer 1 and everything a candidate binds, from one read snapshot (Layer 1 refusals propagate)."""
    layer1 = compare_retained_perspectives(evidence, receipt_ids)
    rows = {}
    for execution in evidence.executions:
        value = json.loads(execution.receipt_json)
        rows[value["id"]] = execution.receipt_json
    receipts = [receipt_from_row({"id": p["receipt_id"], "run_id": p["run_id"], "receipt_json": rows[p["receipt_id"]]})
                for p in layer1["participants"]]
    view = view_from_layer1(layer1)
    governing = governing_question_snapshot(conn)
    return {"layer1": layer1, "view": view, "texts": unit_texts(conn, view, receipts), "receipts": receipts,
            "binding": {
                "receipts": [{"receipt_id": p["receipt_id"],
                              "receipt_sha256": _digest(rows[p["receipt_id"]].encode("utf-8")),
                              "response_sha256": p["digests"]["response_sha256"],
                              "scope_sha256": p["digests"]["scope_sha256"]} for p in layer1["participants"]],
                "question": {"text": layer1["question"]["text"], "sha256": layer1["question"]["sha256"]},
                "governing_question": governing,
                "layer1": {"schema": LAYER1_SCHEMA, "policy_version": LAYER1_POLICY_VERSION,
                           "comparison_id": layer1["comparison_id"], "digest": layer1_digest(layer1)}}}


# ── Prompt (perspective-comparison-extraction/v1) ────────────────────────────

def _prompt_body(view: dict, texts: dict) -> list[str]:
    """The shared question, evidence-unit and participant blocks (identical in every policy version)."""
    plabel = {p["receipt_id"]: f"P{index}" for index, p in enumerate(view["participants"], 1)}
    ulabel = {key: f"U{index}" for index, key in enumerate(view["units"], 1)}
    lines = ["", "Question every Perspective answered:", view["question"], "", "Evidence units:"]
    for key in view["units"]:
        kind = "source extraction" if key[0] == "source_extractions" else "Reader highlight"
        lines.append(f"{ulabel[key]} ({kind}): {texts[key]}")
    for p in view["participants"]:
        supplied = ", ".join(f"{ulabel[key]} [{'/'.join(p['units'][key])}]" for key in view["units"] if key in p["units"])
        lines += ["", f"{plabel[p['receipt_id']]}: {p['label']} (Perspective {p['perspective_id']})",
                  f"Supplied evidence: {supplied}", "Response (quote exactly from this text only):", "<<<", p["response"], ">>>"]
    return lines


def build_prompt(view: dict, texts: dict) -> str:
    lines = [
        "You are proposing a structured comparison of retained Hermeneia Perspective readings.",
        "This is a proposal for a steward to review. It is not a synthesis, a verdict or an adjudication.",
        "Do not decide which Perspective is correct. Do not count votes. Do not output any field that is not listed below.",
        *_prompt_body(view, texts),
    ]
    lines += [
        "",
        "Return only JSON of exactly this shape:",
        '{"propositions":[{"id":"p1","statement":"a neutral restatement of one claim","positions":[{"participant":"P1",'
        '"stance":"asserts|denies|does_not_address|unclassifiable","quote":"text copied exactly from that participant\'s '
        'response, or null","relies_on":["U1"]}]}],"assumptions":[{"participant":"P1","quote":"text copied exactly"}]}',
        "",
        "Rules:",
        "- Give every participant exactly one position for every proposition.",
        "- asserts, denies and unclassifiable need a quote copied exactly from that participant's own response.",
        "- Use does_not_address, with quote null and no relies_on, when the response does not speak to the proposition.",
        "- Paraphrases of the same claim are one proposition. Different wording is not disagreement.",
        "- relies_on lists only evidence units the response itself explicitly connects to its quote. Supplied evidence is not reliance.",
        "- Record an assumption only when the response states it.",
    ]
    return "\n".join(lines)


# ── Experimental prompt and wire format v1.1 (frozen in extraction_policy_v1.1.json) ──

V1_1_HEADER = (
    "You are building a structured comparison across retained Hermeneia Perspective readings.",
    "This is a proposal for a steward to review. It is not a synthesis, a verdict or an adjudication.",
    "Do not decide which Perspective is correct. Do not count votes.",
)
V1_1_WORK_ORDER = (
    "Work in this order:",
    "1. Find the claims that can be compared across the Perspectives. Write each as one neutral proposition about the passage, not about any one Perspective.",
    "   Two responses that make the same claim in different words share ONE proposition. Two responses that make opposite claims share ONE proposition that one supports and the other opposes.",
    "   Never write one proposition per Perspective by restating each response separately.",
    "2. For each proposition, classify EVERY participant ({participant_labels}) with exactly one value:",
    "   supports = the response asserts the proposition; opposes = the response denies it; mixed = the response speaks to it but is qualified or undecided; silent = the response does not speak to it; unknown = you cannot tell.",
    "3. For supports, opposes and mixed, copy the quote exactly, character for character, from that participant's own response. For silent and unknown, quote is null.",
    "4. Only then fill relies_on with the evidence units that the participant's quoted words explicitly draw on. relies_on: [] means no reliance established. Supplied evidence is not reliance.",
    "5. Only then list assumptions that a response explicitly states, each with an exact quote. If there are none, use [].",
    "Leave a classification unknown rather than inventing support.",
)
V1_1_OUTPUT_RULES = (
    "Output rules:",
    "- Output one JSON object only. No markdown, no code fences, no text before or after it.",
    "- Include every field shown in the example in every object. Use [] for an empty list; never omit a field.",
    "- Allowed classification values: \"supports\", \"opposes\", \"mixed\", \"silent\", \"unknown\".",
    "- Participant labels: {participant_labels}. Evidence unit labels: {unit_labels}.",
    "- At most {proposition_bound} propositions.",
)
V1_1_EXAMPLE_INTRO = "Example of the exact shape (illustrative content, not about this passage):"
V1_1_EXAMPLE = ('{"propositions":[{"id":"p1","statement":"The bridge was closed for repairs.","classifications":['
                '{"participant":"P1","classification":"supports","quote":"the bridge was shut for repairs","relies_on":["U1"]},'
                '{"participant":"P2","classification":"opposes","quote":"nothing shows the bridge was closed","relies_on":[]}]}],'
                '"assumptions":[{"participant":"P1","quote":"assuming the notice was official"}]}')
V1_1_CLASSIFICATIONS = {"supports": "asserts", "opposes": "denies", "mixed": "unclassifiable",
                        "silent": "does_not_address", "unknown": "unknown"}


def _v1_1_values(view: dict) -> dict:
    n = len(view["participants"])
    return {"participant_labels": ", ".join(f"P{i}" for i in range(1, n + 1)),
            "unit_labels": ", ".join(f"U{i}" for i in range(1, len(view["units"]) + 1)),
            "proposition_bound": 2 * n}


def build_prompt_v1_1(view: dict, texts: dict) -> str:
    values = _v1_1_values(view)
    lines = [*V1_1_HEADER, *_prompt_body(view, texts), "",
             *(line.format(**values) for line in V1_1_WORK_ORDER), "",
             *(line.format(**values) for line in V1_1_OUTPUT_RULES), "",
             V1_1_EXAMPLE_INTRO, V1_1_EXAMPLE]
    return "\n".join(lines)


def parse_output_v1_1(text: str, view: dict) -> dict:
    """Strict v1.1 wire parsing; returns the internal shape that normalize() consumes."""
    match = _FENCE.match(text) if isinstance(text, str) else None
    body = match.group(1) if match else text
    try:
        value = json.loads(body, object_pairs_hook=_strict)
    except (ValueError, TypeError) as exc:
        raise ExtractionRefused("EXTRACTION_OUTPUT_UNPARSEABLE") from exc
    if not isinstance(value, dict):
        raise ExtractionRefused("EXTRACTION_OUTPUT_UNPARSEABLE")
    if _authority(value):
        raise ExtractionRefused("EXTRACTION_OUTPUT_AUTHORITY_FIELD")
    participants = {f"P{index}" for index in range(1, len(view["participants"]) + 1)}
    units = {f"U{index}" for index in range(1, len(view["units"]) + 1)}

    def require(condition):
        if not condition:
            raise ExtractionRefused("EXTRACTION_OUTPUT_CONTRACT_VIOLATION")

    def nonblank(item):
        return isinstance(item, str) and bool(item.strip())

    require(set(value) == {"propositions", "assumptions"})
    require(isinstance(value["propositions"], list) and len(value["propositions"]) <= 2 * len(participants))
    require(isinstance(value["assumptions"], list) and len(value["assumptions"]) <= MAX_ITEMS)
    ids, propositions = set(), []
    for proposition in value["propositions"]:
        require(isinstance(proposition, dict) and set(proposition) == {"id", "statement", "classifications"})
        require(nonblank(proposition["id"]) and proposition["id"] not in ids and nonblank(proposition["statement"]))
        ids.add(proposition["id"])
        require(isinstance(proposition["classifications"], list))
        seen, positions = set(), []
        for item in proposition["classifications"]:
            require(isinstance(item, dict) and set(item) == {"participant", "classification", "quote", "relies_on"})
            require(item["participant"] in participants and item["participant"] not in seen)
            seen.add(item["participant"])
            require(item["classification"] in V1_1_CLASSIFICATIONS)
            require(item["quote"] is None or isinstance(item["quote"], str))
            require(isinstance(item["relies_on"], list) and all(label in units for label in item["relies_on"]))
            positions.append({"participant": item["participant"], "stance": V1_1_CLASSIFICATIONS[item["classification"]],
                              "quote": item["quote"], "relies_on": item["relies_on"]})
        propositions.append({"id": proposition["id"], "statement": proposition["statement"], "positions": positions})
    for assumption in value["assumptions"]:
        require(isinstance(assumption, dict) and set(assumption) == {"participant", "quote"})
        require(assumption["participant"] in participants and nonblank(assumption["quote"]))
    return {"propositions": propositions, "assumptions": value["assumptions"]}


POLICIES = {
    EXTRACTION_POLICY_VERSION: {"prompt_version": PROMPT_VERSION, "build_prompt": build_prompt, "parse": None},
    EXPERIMENTAL_POLICY_VERSION: {"prompt_version": PROMPT_VERSION_V1_1, "build_prompt": build_prompt_v1_1,
                                  "parse": parse_output_v1_1},
}


def prompt_for(policy_version: str, view: dict, texts: dict) -> str:
    return POLICIES[policy_version]["build_prompt"](view, texts)


def parse_for(policy_version: str, text: str, view: dict) -> dict:
    parse = POLICIES[policy_version]["parse"] or parse_output
    return parse(text, view)


# ── Model output: strict parsing, then traceability normalization ────────────

def _strict(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _authority(value) -> bool:
    if isinstance(value, dict):
        return any(key in AUTHORITY_KEYS or _authority(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_authority(item) for item in value)
    return False


def parse_output(text: str, view: dict) -> dict:
    match = _FENCE.match(text) if isinstance(text, str) else None
    body = match.group(1) if match else text
    try:
        value = json.loads(body, object_pairs_hook=_strict)
    except (ValueError, TypeError) as exc:
        raise ExtractionRefused("EXTRACTION_OUTPUT_UNPARSEABLE") from exc
    if not isinstance(value, dict):
        raise ExtractionRefused("EXTRACTION_OUTPUT_UNPARSEABLE")
    if _authority(value):
        raise ExtractionRefused("EXTRACTION_OUTPUT_AUTHORITY_FIELD")
    participants = {f"P{index}" for index in range(1, len(view["participants"]) + 1)}
    units = {f"U{index}" for index in range(1, len(view["units"]) + 1)}

    def require(condition):
        if not condition:
            raise ExtractionRefused("EXTRACTION_OUTPUT_CONTRACT_VIOLATION")

    def nonblank(item):
        return isinstance(item, str) and bool(item.strip())

    require(set(value) == {"propositions", "assumptions"})
    require(isinstance(value["propositions"], list) and len(value["propositions"]) <= MAX_ITEMS)
    require(isinstance(value["assumptions"], list) and len(value["assumptions"]) <= MAX_ITEMS)
    ids = set()
    for proposition in value["propositions"]:
        require(isinstance(proposition, dict) and set(proposition) == {"id", "statement", "positions"})
        require(nonblank(proposition["id"]) and proposition["id"] not in ids and nonblank(proposition["statement"]))
        ids.add(proposition["id"])
        require(isinstance(proposition["positions"], list))
        seen = set()
        for position in proposition["positions"]:
            require(isinstance(position, dict) and set(position) == {"participant", "stance", "quote", "relies_on"})
            require(position["participant"] in participants and position["participant"] not in seen)
            seen.add(position["participant"])
            require(position["stance"] in _OUTPUT_STANCES)
            require(position["quote"] is None or isinstance(position["quote"], str))
            require(isinstance(position["relies_on"], list) and all(item in units for item in position["relies_on"]))
    for assumption in value["assumptions"]:
        require(isinstance(assumption, dict) and set(assumption) == {"participant", "quote"})
        require(assumption["participant"] in participants and nonblank(assumption["quote"]))
    return value


def _span(response: str, quote) -> dict | None:
    """The quote's exact, unique occurrence in the attributed response, or None (untraceable)."""
    if not isinstance(quote, str) or not quote:
        return None
    start = response.find(quote)
    if start < 0 or response.find(quote, start + 1) >= 0:
        return None
    return {"start": start, "end": start + len(quote), "text": quote}


def _unknown(receipt_id: str) -> dict:
    return {"participant": receipt_id, "stance": "unknown", "span": None, "reliance": []}


def normalize(output: dict, view: dict) -> dict:
    """Admit only traced items; everything else becomes unknown and is listed as untraceable."""
    by_label = {f"P{index}": p for index, p in enumerate(view["participants"], 1)}
    units = {f"U{index}": key for index, key in enumerate(view["units"], 1)}
    order = [p["receipt_id"] for p in view["participants"]]
    untraceable, propositions = [], []
    for index, proposition in enumerate(output["propositions"], 1):
        pid = f"p{index}"
        given = {by_label[position["participant"]]["receipt_id"]: position for position in proposition["positions"]}
        positions = []
        for participant in view["participants"]:
            rid = participant["receipt_id"]
            position = given.get(rid)
            if position is None:
                positions.append(_unknown(rid))
                untraceable.append({"kind": "position_not_classified", "proposition": pid, "participant": rid})
                continue
            proposed = {"proposed_stance": position["stance"], "quote": position["quote"],
                        "relies_on": [_ref(units[label]) for label in position["relies_on"]]}
            if position["stance"] in ("does_not_address", "unknown"):
                # v1 output never carries "unknown"; a v1.1 explicit unknown is kept without inventing support.
                if position["quote"] is None and not position["relies_on"]:
                    positions.append({"participant": rid, "stance": position["stance"], "span": None, "reliance": []})
                else:
                    positions.append(_unknown(rid))
                    untraceable.append({"kind": "contradictory_position", "proposition": pid, "participant": rid, **proposed})
                continue
            span = _span(participant["response"], position["quote"])
            if span is None:
                positions.append(_unknown(rid))
                untraceable.append({"kind": "untraceable_position", "proposition": pid, "participant": rid, **proposed})
                continue
            reliance = set()
            for label in dict.fromkeys(position["relies_on"]):
                if units[label] in participant["units"]:
                    reliance.add(units[label])
                else:
                    untraceable.append({"kind": "reliance_outside_supplied_scope", "proposition": pid,
                                        "participant": rid, "ref": _ref(units[label])})
            positions.append({"participant": rid, "stance": position["stance"], "span": span,
                              "reliance": [_ref(key) for key in sorted(reliance)]})
        if not any(position["stance"] in SPAN_STANCES for position in positions):
            untraceable.append({"kind": "untraceable_proposition", "proposition": pid, "statement": proposition["statement"]})
            continue
        propositions.append({"id": pid, "statement": proposition["statement"], "positions": positions})
    assumptions = []
    for index, assumption in enumerate(output["assumptions"], 1):
        participant = by_label[assumption["participant"]]
        span = _span(participant["response"], assumption["quote"])
        if span is None:
            untraceable.append({"kind": "untraceable_assumption", "participant": participant["receipt_id"],
                                "quote": assumption["quote"]})
            continue
        assumptions.append({"id": f"a{index}", "participant": participant["receipt_id"], "span": span})
    return _structure(order, propositions, assumptions, untraceable, view)


# ── Derived relations (never authored) ───────────────────────────────────────

def _reliance_relation(sets: list[set]) -> str:
    if any(not item for item in sets):
        return "some_uncited"
    if all(item == sets[0] for item in sets):
        return "identical"
    if all(not (a & b) for a, b in combinations(sets, 2)):
        return "disjoint"
    return "overlapping"


def derive_relations(propositions: list[dict], view: dict) -> dict:
    agreement, disagreement, unresolved, unknown_positions = [], [], [], []
    for proposition in propositions:
        positions = proposition["positions"]
        by = {stance: [p["participant"] for p in positions if p["stance"] == stance] for stance in STANCES}
        reliance = {p["participant"]: {_key(ref) for ref in p["reliance"]} for p in positions}
        unknown = [p["participant"] for p in positions if p["stance"] in ("unknown", "unclassifiable")]
        unknown_positions += [{"proposition": proposition["id"], "participant": p["participant"], "stance": p["stance"]}
                              for p in positions if p["stance"] in ("unknown", "unclassifiable")]
        if by["asserts"] and by["denies"]:
            groups = [{"stance": stance, "participants": by[stance]} for stance in ("asserts", "denies")]
            largest = max(len(group["participants"]) for group in groups)
            disagreement.append({
                "proposition": proposition["id"], "groups": groups,
                "minority_participants": [rid for group in groups if len(group["participants"]) < largest
                                          for rid in group["participants"]],
                "not_established_for": unknown,
                "reliance": _reliance_relation([reliance[rid] for rid in by["asserts"] + by["denies"]]),
                "resolution": "none_recorded"})
            unresolved.append(proposition["id"])
            continue
        for stance in ("asserts", "denies"):
            if len(by[stance]) >= 2:
                agreement.append({"proposition": proposition["id"], "stance": stance, "participants": by[stance],
                                  "not_established_for": unknown,
                                  "reliance": _reliance_relation([reliance[rid] for rid in by[stance]]),
                                  "same_reasoning": "not_established"})
    evidence_use = []
    for participant in view["participants"]:
        rid = participant["receipt_id"]
        relied = {_key(ref) for proposition in propositions for p in proposition["positions"]
                  if p["participant"] == rid for ref in p["reliance"]}
        evidence_use.append({"participant": rid, "relied_on": [_ref(key) for key in sorted(relied)],
                             "supplied_not_relied_on": [_ref(key) for key in sorted(set(participant["units"]) - relied)]})
    return {"agreement": agreement, "disagreement": disagreement, "unresolved": unresolved,
            "unknown_positions": unknown_positions, "evidence_use": evidence_use}


def _structure(order, propositions, assumptions, untraceable, view) -> dict:
    return {"schema": STRUCTURE_SCHEMA, "participants": order, "propositions": propositions, "assumptions": assumptions,
            "untraceable": untraceable, "relations": derive_relations(propositions, view)}


# ── Strict structure validation: steward edits, authored structures, stored records ──

def _check_core(participants, propositions, assumptions, view) -> tuple[list, list]:
    def invalid(detail):
        raise StructureRefused("STRUCTURE_INVALID", detail)

    def untraceable(detail):
        raise StructureRefused("STRUCTURE_UNTRACEABLE", detail)

    order = [p["receipt_id"] for p in view["participants"]]
    if participants != order:
        invalid("participants must equal the Layer 1 participants")
    by_id = {p["receipt_id"]: p for p in view["participants"]}
    if not isinstance(propositions, list) or not isinstance(assumptions, list) \
            or len(propositions) > MAX_ITEMS or len(assumptions) > MAX_ITEMS:
        invalid("propositions and assumptions must be bounded lists")

    def span_of(response, span):
        if not (isinstance(span, dict) and set(span) == {"start", "end", "text"}
                and all(type(span[k]) is int for k in ("start", "end")) and isinstance(span["text"], str)):
            invalid("a span is {start, end, text}")
        if not (0 <= span["start"] < span["end"] <= len(response)) or response[span["start"]:span["end"]] != span["text"]:
            untraceable("a span does not equal the participant's exact response text")
        return {"start": span["start"], "end": span["end"], "text": span["text"]}

    canonical, ids = [], set()
    for proposition in propositions:
        if not (isinstance(proposition, dict) and set(proposition) == {"id", "statement", "positions"}):
            invalid("a proposition is {id, statement, positions}")
        if not (isinstance(proposition["id"], str) and re.fullmatch(r"p[1-9][0-9]*", proposition["id"])) or proposition["id"] in ids:
            invalid("proposition IDs are unique p<n>")
        ids.add(proposition["id"])
        if not (isinstance(proposition["statement"], str) and proposition["statement"].strip()):
            invalid("a proposition needs a statement")
        positions = proposition["positions"]
        named = [p.get("participant") if isinstance(p, dict) else None for p in positions] if isinstance(positions, list) else None
        if named is None or not all(isinstance(rid, str) for rid in named) or sorted(named) != sorted(order):
            invalid("exactly one position per participant is required")
        by_participant = {p["participant"]: p for p in positions}
        result = []
        for rid in order:
            position = by_participant[rid]
            if set(position) != {"participant", "stance", "span", "reliance"} or position["stance"] not in STANCES:
                invalid("a position is {participant, stance, span, reliance} with a contract stance")
            if not isinstance(position["reliance"], list):
                invalid("reliance is a list")
            if position["stance"] in SPAN_STANCES:
                if position["span"] is None:
                    untraceable("asserts, denies and unclassifiable require a span")
                span = span_of(by_id[rid]["response"], position["span"])
            else:
                if position["span"] is not None or position["reliance"]:
                    untraceable("does_not_address and unknown carry no span and no reliance")
                span = None
            keys = set()
            for ref in position["reliance"]:
                if not (isinstance(ref, dict) and set(ref) == {"table", "key"} and isinstance(ref["key"], dict)
                        and set(ref["key"]) == {"id"} and ref["table"] in ("source_extractions", "reader_highlights")):
                    invalid("a reliance entry is a typed unit reference")
                if _key(ref) not in by_id[rid]["units"] or _key(ref) in keys:
                    invalid("reliance must be distinct units supplied to that participant")
                keys.add(_key(ref))
            result.append({"participant": rid, "stance": position["stance"], "span": span,
                           "reliance": [_ref(key) for key in sorted(keys)]})
        canonical.append({"id": proposition["id"], "statement": proposition["statement"], "positions": result})
    admitted, assumption_ids = [], set()
    for assumption in assumptions:
        if not (isinstance(assumption, dict) and set(assumption) == {"id", "participant", "span"}):
            invalid("an assumption is {id, participant, span}")
        if not (isinstance(assumption["id"], str) and re.fullmatch(r"a[1-9][0-9]*", assumption["id"])) \
                or assumption["id"] in assumption_ids or assumption["participant"] not in by_id:
            invalid("assumption IDs are unique a<n> for a participant")
        assumption_ids.add(assumption["id"])
        admitted.append({"id": assumption["id"], "participant": assumption["participant"],
                         "span": span_of(by_id[assumption["participant"]]["response"], assumption["span"])})
    return canonical, admitted


def structure_from_edit(edit, view: dict) -> dict:
    """A steward's edited structure, validated strictly and never downgraded; relations are derived."""
    if not isinstance(edit, dict) or _authority(edit) or set(edit) != {"participants", "propositions", "assumptions"}:
        raise StructureRefused("STRUCTURE_INVALID", "an edit supplies exactly participants, propositions and assumptions")
    propositions, assumptions = _check_core(edit["participants"], edit["propositions"], edit["assumptions"], view)
    return _structure(list(edit["participants"]), propositions, assumptions, [], view)


def validate_structure(structure, view: dict, *, allow_untraceable: bool) -> dict:
    """A stored structure must already be canonical, traced, and carry exactly the derived relations."""
    fields = {"schema", "participants", "propositions", "assumptions", "untraceable", "relations"}
    if not isinstance(structure, dict) or set(structure) != fields or structure["schema"] != STRUCTURE_SCHEMA:
        raise StructureRefused("STRUCTURE_INVALID", "structure fields")
    propositions, assumptions = _check_core(structure["participants"], structure["propositions"], structure["assumptions"], view)
    untraceable = structure["untraceable"]
    if not isinstance(untraceable, list) or (untraceable and not allow_untraceable) \
            or any(not isinstance(item, dict) or item.get("kind") not in UNTRACEABLE_KINDS for item in untraceable):
        raise StructureRefused("STRUCTURE_INVALID", "untraceable entries")
    expected = _structure(structure["participants"], propositions, assumptions, untraceable, view)
    if canonical_bytes(expected) != canonical_bytes(structure):
        raise StructureRefused("STRUCTURE_INVALID", "structure is not canonical or its relations are not the derived relations")
    return structure


# ── Candidate ────────────────────────────────────────────────────────────────

def candidate_id(candidate: dict) -> str:
    body = {key: candidate[key] for key in ("schema", "binding", "extraction", "structure")}
    return "perspective-comparison-candidate:sha256:" + hashlib.sha256(_CANDIDATE_DOMAIN + canonical_bytes(body)).hexdigest()


def build_candidate(inputs: dict, *, prompt: str, execution: dict, output: str, created_at: str, completed_at: str,
                    policy_version: str = EXTRACTION_POLICY_VERSION) -> dict:
    """Parse and normalize one model output into a transient candidate (raises ExtractionRefused)."""
    if policy_version not in POLICIES:
        raise ValueError("Unsupported extraction policy")
    if not (isinstance(execution, dict) and isinstance(execution.get("provider_id"), str) and execution["provider_id"]
            and isinstance(execution.get("model_id"), str) and execution["model_id"]):
        raise ValueError("Execution must record provider_id and model_id")
    structure = normalize(parse_for(policy_version, output, inputs["view"]), inputs["view"])
    candidate = {
        "schema": CANDIDATE_SCHEMA,
        "binding": inputs["binding"],
        "extraction": {"policy_version": policy_version, "prompt_version": POLICIES[policy_version]["prompt_version"],
                       "prompt": prompt, "prompt_sha256": text_digest(prompt), "execution": json.loads(canonical_bytes(execution)),
                       "created_at": created_at, "completed_at": completed_at,
                       "output": output, "output_sha256": text_digest(output)},
        "structure": structure,
    }
    candidate["candidate_id"] = candidate_id(candidate)
    return candidate
