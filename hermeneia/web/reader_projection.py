"""Derived, non-canonical text projections for the Reader."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


_BLOCK_REGION = re.compile(r"block:(\d+)")


class ReaderProjectionCoverageError(RuntimeError):
    """Raised when a Reader projection loses canonical extraction coverage."""


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


def reader_projection_coverage(
    extractions: Sequence[Mapping[str, object]],
    projected: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Account for every SourceExtraction consumed by a Reader projection.

    Each canonical extraction must be displayed directly, incorporated into a
    provenance-preserving merged block, or explicitly suppressed as a layout
    artifact. The current projection has no suppression rule; this helper makes
    any future rule prove its accounting rather than silently dropping text.
    """
    expected: dict[str, Mapping[str, object]] = {}
    for extraction in extractions:
        source_id = str(extraction.get("id") or "")
        if source_id:
            expected[source_id] = extraction

    seen: dict[str, dict[str, object]] = {}
    for projection_index, block in enumerate(projected):
        status, source_ids, reason = _projection_accounting(block)
        if not source_ids:
            raise ReaderProjectionCoverageError(
                f"projection block {projection_index} has no source extraction ids"
            )
        for source_id in source_ids:
            if source_id not in expected:
                raise ReaderProjectionCoverageError(
                    f"projection block {projection_index} references unknown extraction {source_id}"
                )
            if source_id in seen:
                raise ReaderProjectionCoverageError(
                    f"source extraction {source_id} is accounted more than once"
                )
            extraction = expected[source_id]
            entry = {
                "source_extraction_id": source_id,
                "page": extraction.get("page"),
                "region": extraction.get("region"),
                "source_locator": extraction.get("source_locator"),
                "status": status,
                "projection_index": projection_index,
            }
            if reason:
                entry["reason"] = reason
            seen[source_id] = entry

    missing = [source_id for source_id in expected if source_id not in seen]
    if missing:
        raise ReaderProjectionCoverageError(
            "Reader projection lost source extraction coverage: "
            + ", ".join(missing)
        )
    return [seen[source_id] for source_id in expected]


def _projection_accounting(
    block: Mapping[str, object],
) -> tuple[str, list[str], str | None]:
    direct_id = str(block.get("source_extraction_id") or "")
    if direct_id:
        return "displayed", [direct_id], None

    projection = block.get("reader_projection")
    projection = projection if isinstance(projection, Mapping) else {}
    kind = str(projection.get("kind") or "")
    raw_ids = projection.get("source_extraction_ids")
    source_ids = [
        str(source_id)
        for source_id in raw_ids
        if source_id
    ] if isinstance(raw_ids, Sequence) and not isinstance(raw_ids, (str, bytes)) else []

    if not source_ids:
        canonical = block.get("canonical_extractions")
        if isinstance(canonical, Sequence) and not isinstance(canonical, (str, bytes)):
            source_ids = [
                str(item.get("id") or "")
                for item in canonical
                if isinstance(item, Mapping) and item.get("id")
            ]

    if kind == "layout_artifact_suppression":
        reason = str(projection.get("reason") or "").strip()
        if not reason:
            raise ReaderProjectionCoverageError(
                "layout artifact suppression requires an explicit reason"
            )
        return "suppressed", source_ids, reason

    return "incorporated", source_ids, kind or None


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
    reader_projection_coverage(extractions, projected)
    return projected


def project_reader_page(
    extractions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Return projected Reader blocks plus canonical coverage accounting."""
    projected = project_reader_extractions(extractions)
    return {
        "extractions": projected,
        "projection_coverage": reader_projection_coverage(extractions, projected),
    }
