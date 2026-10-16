"""ADR-0046 D-2: what a Finding's own evidence established, attributed to the evaluator version that recorded it.

A pure function of the Finding's stored fields: no live lookup, no rewrite. Historical dispositions are reported as
recorded ("recorded as transformed by provenance-v1.0"), next to what that method's evidence could and could not
establish.
"""
from __future__ import annotations

import json

from ..evaluation_functions.base import RATIFIED_DIMENSIONS

_OBSERVATION_AND_RECORD = ("the Observation existed", "a provenance record existed")
_NOT_COMPARED = ("that the record agrees with the Observation", "that the Observation is linked to the plan's Blueprint")
_ABSENT_RECORD = ("the Observation existed", "no provenance record existed")
_NO_OBSERVATION = ("no Observation with this ID existed",)
_NO_OBSERVATION_BUT_RECORD = ("no Observation with this ID existed", "a provenance record existed")

# (evaluation_method, operation, status, observation_exists, provenance_exists) -> (established, not established).
READINGS: dict[tuple, tuple[tuple[str, ...], tuple[str, ...]]] = {}
READINGS[("provenance-v1.0", "preservation", "preserved", True, True)] = (_OBSERVATION_AND_RECORD, _NOT_COMPARED)
READINGS[("provenance-v1.0", "omission", "omitted", False, False)] = (_NO_OBSERVATION, ())
READINGS[("provenance-v1.0", "omission", "omitted", False, True)] = (_NO_OBSERVATION_BUT_RECORD, ())
READINGS[("provenance-v1.0", "transformation", "transformed", True, False)] = (
    _ABSENT_RECORD, ("any alteration of the Observation", "the Observation's custody"))



def _v1_1_reading(operation: str, status: str, observed: dict) -> tuple[list[str], list[str]] | None:
    """provenance-v1.1 (ADR-0046 U, ADR-0047 L2-b): composed from its three recorded facts, each kept distinct."""
    facts = (observed.get("observation_exists"), observed.get("provenance_exists"), observed.get("blueprint_link_exists", "absent"))
    if facts[0] not in (True, False) or facts[1] not in (True, False) or facts[2] not in (True, False, None):
        return None
    observation, record, link = facts
    established = ["the Observation existed" if observation else "no Observation with this ID existed",
                   "a provenance record existed" if record else "no provenance record existed"]
    not_established = []
    if link is None:
        not_established.append("whether the plan's Blueprint links this Observation (the Blueprint could not be resolved)")
    else:
        established.append("the plan's Blueprint links this Observation" if link
                           else "the plan's Blueprint does not link this Observation")
    expected = (("omission", "omitted") if not observation
                else ("preservation", "preserved") if record and link else ("unverifiable", "unverifiable"))
    if (operation, status) != expected:
        return None
    if status == "preserved":
        not_established.append("that the record agrees with the Observation")
    elif status == "unverifiable":
        if not record:
            not_established.append("whether the Observation was preserved or altered")
        if link is not True:
            not_established.append("the obligation's provenance relationship to the Blueprint")
    return established, not_established


def finding_reading(finding: dict) -> dict:
    """The presentation of one Finding: its method, its recorded disposition, and what its evidence established."""
    method, status = finding.get("evaluation_method"), finding.get("status")
    reading = {
        "evaluation_method": method,
        "recorded": f"{finding.get('operation')} / {status}",
        "attribution": f"recorded as {status} by {method}",
        "ratified_dimension": finding.get("dimension") in RATIFIED_DIMENSIONS,
        "established": None,
        "not_established": None,
    }
    try:
        observed = json.loads(finding.get("evidence") or "{}").get("observed_render")
    except (TypeError, ValueError):
        observed = None
    if isinstance(observed, dict) and method == "provenance-v1.1":
        composed = _v1_1_reading(finding.get("operation"), status, observed)
        if composed is not None:
            reading["established"], reading["not_established"] = composed
    elif isinstance(observed, dict):
        key = (method, finding.get("operation"), status, observed.get("observation_exists"), observed.get("provenance_exists"))
        if key in READINGS:
            established, not_established = READINGS[key]
            reading["established"], reading["not_established"] = list(established), list(not_established)
    return reading
