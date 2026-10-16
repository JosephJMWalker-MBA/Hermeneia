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
for _method in ("provenance-v1.0", "provenance-v1.1"):
    READINGS[(_method, "preservation", "preserved", True, True)] = (_OBSERVATION_AND_RECORD, _NOT_COMPARED)
    READINGS[(_method, "omission", "omitted", False, False)] = (_NO_OBSERVATION, ())
    READINGS[(_method, "omission", "omitted", False, True)] = (_NO_OBSERVATION_BUT_RECORD, ())
READINGS[("provenance-v1.0", "transformation", "transformed", True, False)] = (
    _ABSENT_RECORD, ("any alteration of the Observation", "the Observation's custody"))
READINGS[("provenance-v1.1", "unverifiable", "unverifiable", True, False)] = (
    _ABSENT_RECORD, ("whether the Observation was preserved or altered",))


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
    if isinstance(observed, dict):
        key = (method, finding.get("operation"), status, observed.get("observation_exists"), observed.get("provenance_exists"))
        if key in READINGS:
            established, not_established = READINGS[key]
            reading["established"], reading["not_established"] = list(established), list(not_established)
    return reading
