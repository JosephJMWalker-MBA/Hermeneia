"""Reader span locator decoding utilities.

Reader span locators are durable reconstruction data for the Reader. Other
surfaces should present their canonical source endpoints rather than exposing
the encoded reconstruction envelope as the human-facing source location.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote


READER_SPAN_LOCATOR_PREFIX = "reader-span:v1:"


def decode_reader_span_locator(source_locator: object) -> dict[str, Any] | None:
    raw = str(source_locator or "")
    if not raw.startswith(READER_SPAN_LOCATOR_PREFIX):
        return None
    try:
        decoded = json.loads(unquote(raw[len(READER_SPAN_LOCATOR_PREFIX):]))
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _point_locator(point: object) -> str | None:
    if not isinstance(point, dict):
        return None
    return _text(point.get("source_locator")) or next(
        (
            locator
            for locator in (
                _text(item) for item in point.get("source_locators") or []
            )
            if locator
        ),
        None,
    )


def reader_span_display_locator(source_locator: object) -> str | None:
    """Return an inspectable source location for legacy or v1 Reader locators."""
    raw = _text(source_locator)
    span = decode_reader_span_locator(raw)
    if span is None:
        return raw

    start = _point_locator(span.get("start"))
    end = _point_locator(span.get("end"))
    if start and end:
        return start if start == end else f"{start}..{end}"
    if start or end:
        return start or end

    locators = [
        locator
        for locator in (_text(item) for item in span.get("source_locators") or [])
        if locator
    ]
    if locators:
        return locators[0] if locators[0] == locators[-1] else f"{locators[0]}..{locators[-1]}"
    return raw


def reader_span_raw_locator(source_locator: object) -> str | None:
    """Return the raw v1 locator only when the value is a Reader span envelope."""
    raw = _text(source_locator)
    return raw if decode_reader_span_locator(raw) is not None else None
