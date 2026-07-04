"""Derived, non-canonical text projections for the Reader."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


_BLOCK_REGION = re.compile(r"block:(\d+)")


def _canonical_extraction(extraction: Mapping[str, object]) -> dict[str, object]:
    """Copy the canonical fields carried underneath a Reader projection."""
    return {
        "id": extraction.get("id"),
        "page": extraction.get("page"),
        "region": extraction.get("region"),
        "raw_text": extraction.get("raw_text"),
        "source_locator": extraction.get("source_locator"),
    }


def _block_index(extraction: Mapping[str, object]) -> int | None:
    match = _BLOCK_REGION.fullmatch(str(extraction.get("region") or ""))
    return int(match.group(1)) if match else None


def _is_safe_drop_cap_pair(
    previous: Mapping[str, object],
    following: Mapping[str, object],
) -> bool:
    previous_text = str(previous.get("raw_text") or "")
    following_text = str(following.get("raw_text") or "")
    drop_cap = previous_text.strip()
    continuation = following_text.lstrip()
    previous_block = _block_index(previous)
    following_block = _block_index(following)

    return bool(
        previous.get("page") == following.get("page")
        and previous_block is not None
        and following_block == previous_block + 1
        and len(drop_cap) == 1
        and drop_cap.isalpha()
        and drop_cap.isupper()
        and continuation
        and continuation[0].isalpha()
        and continuation[0].islower()
    )


def _project_single(extraction: Mapping[str, object]) -> dict[str, object]:
    return {
        "region": extraction.get("region"),
        "text": extraction.get("raw_text"),
        "source_locator": extraction.get("source_locator"),
        "source_extraction_id": extraction.get("id"),
        "reader_projection": None,
    }


def _project_drop_cap_pair(
    previous: Mapping[str, object],
    following: Mapping[str, object],
) -> dict[str, object]:
    canonical = [
        _canonical_extraction(previous),
        _canonical_extraction(following),
    ]
    previous_text = str(previous.get("raw_text") or "").strip()
    following_text = str(following.get("raw_text") or "").lstrip()
    source_ids = [item["id"] for item in canonical]
    source_locators = [item["source_locator"] for item in canonical]
    regions = [item["region"] for item in canonical]
    return {
        "region": " + ".join(str(region) for region in regions),
        "text": previous_text + following_text,
        "source_locator": " + ".join(str(locator) for locator in source_locators),
        "reader_projection": {
            "kind": "drop_cap_merge",
            "source_extraction_ids": source_ids,
            "source_locators": source_locators,
        },
        "canonical_extractions": canonical,
    }


def project_reader_extractions(
    extractions: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Build disposable Reader blocks without changing canonical evidence.

    The only cross-block repair is a conservative PDF drop-cap case: a
    one-letter uppercase block immediately followed, on the same page and at
    the next block index, by lowercase continuation text. The projection keeps
    exact contributing extraction IDs, locators, and raw text in
    ``canonical_extractions``.
    """
    projected: list[dict[str, object]] = []
    index = 0
    while index < len(extractions):
        current = extractions[index]
        following = extractions[index + 1] if index + 1 < len(extractions) else None
        if following is not None and _is_safe_drop_cap_pair(current, following):
            projected.append(_project_drop_cap_pair(current, following))
            index += 2
            continue
        projected.append(_project_single(current))
        index += 1
    return projected
