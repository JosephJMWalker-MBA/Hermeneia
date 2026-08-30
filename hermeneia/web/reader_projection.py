"""Derived, non-canonical text projections for the Reader."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


_BLOCK_REGION = re.compile(r"block:(\d+)")
_PARAGRAPH_BREAK = re.compile(r"\n{2,}")


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


def _normalize_prose_display_text(raw_text: object) -> str:
    """Collapse layout soft-wraps for Reader display without changing evidence."""
    text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = []
    for paragraph in _PARAGRAPH_BREAK.split(text):
        lines = [line.strip(" \t\f\v") for line in paragraph.split("\n")]
        merged = lines[0] if lines else ""
        for line in lines[1:]:
            if merged.rstrip().endswith("-"):
                merged = merged.rstrip() + line.lstrip()
            else:
                merged = merged.rstrip() + " " + line.lstrip()
        paragraphs.append(merged.strip(" \t\f\v"))
    return "\n\n".join(paragraphs)


def _projection_source_metadata(
    canonical: Sequence[Mapping[str, object]],
) -> tuple[list[object], list[object], list[object]]:
    source_ids = [item.get("id") for item in canonical]
    source_locators = [item.get("source_locator") for item in canonical]
    regions = [item.get("region") for item in canonical]
    return source_ids, source_locators, regions


def _is_obvious_heading_like(text: object) -> bool:
    trimmed = str(text or "").strip()
    if not trimmed:
        return True
    single_line = _normalize_prose_display_text(trimmed)
    if "\n\n" in single_line:
        return False
    words = re.findall(r"[A-Za-z0-9']+", single_line)
    if not words:
        return True
    if len(words) <= 6 and re.search(r"\b(CHAPTER|PART|SECTION)\b", single_line, re.I):
        return True
    letters = [char for char in single_line if char.isalpha()]
    if letters and all(char.isupper() for char in letters) and len(words) <= 8:
        return True
    if len(words) <= 5 and single_line[-1:] not in ".?!,;:)]}”’\"'":
        title_like = all(
            word[:1].isupper() or word.lower() in {"a", "an", "and", "as", "for", "in", "of", "on", "or", "the", "to"}
            for word in words
        )
        if title_like:
            return True
    return False


def _is_ordinary_block_extraction(extraction: Mapping[str, object]) -> bool:
    return _block_index(extraction) is not None


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


def _is_safe_prose_continuation(
    previous: Mapping[str, object],
    following: Mapping[str, object],
) -> bool:
    previous_text = str(previous.get("raw_text") or "")
    following_text = str(following.get("raw_text") or "")
    previous_trimmed = _normalize_prose_display_text(previous_text).strip()
    following_trimmed = _normalize_prose_display_text(following_text).strip()
    first_following = following_trimmed[:1]
    last_previous = previous_trimmed[-1:] if previous_trimmed else ""

    return bool(
        previous.get("page") == following.get("page")
        and _is_ordinary_block_extraction(previous)
        and _is_ordinary_block_extraction(following)
        and previous_trimmed
        and following_trimmed
        and first_following
        and first_following.isalpha()
        and first_following.islower()
        and last_previous not in ".?!"
        and not _is_obvious_heading_like(previous_text)
        and not _is_obvious_heading_like(following_text)
    )


def _project_single(extraction: Mapping[str, object]) -> dict[str, object]:
    text = _normalize_prose_display_text(extraction.get("raw_text"))
    if text != str(extraction.get("raw_text") or ""):
        canonical = [_canonical_extraction(extraction)]
        source_ids, source_locators, _regions = _projection_source_metadata(canonical)
        return {
            "region": extraction.get("region"),
            "text": text,
            "source_locator": extraction.get("source_locator"),
            "reader_projection": {
                "kind": "soft_wrap_normalization",
                "source_extraction_ids": source_ids,
                "source_locators": source_locators,
                "display_source_spans": [
                    {
                        "source_extraction_id": source_ids[0],
                        "source_locator": source_locators[0],
                        "start": 0,
                        "end": len(text),
                    }
                ],
            },
            "canonical_extractions": canonical,
        }
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
    source_ids, source_locators, regions = _projection_source_metadata(canonical)
    text = previous_text + following_text
    previous_end = len(previous_text)
    return {
        "region": " + ".join(str(region) for region in regions),
        "text": text,
        "source_locator": " + ".join(str(locator) for locator in source_locators),
        "reader_projection": {
            "kind": "drop_cap_merge",
            "source_extraction_ids": source_ids,
            "source_locators": source_locators,
            "display_source_spans": [
                {
                    "source_extraction_id": source_ids[0],
                    "source_locator": source_locators[0],
                    "start": 0,
                    "end": previous_end,
                },
                {
                    "source_extraction_id": source_ids[1],
                    "source_locator": source_locators[1],
                    "start": previous_end,
                    "end": len(text),
                },
            ],
        },
        "canonical_extractions": canonical,
    }


def _join_prose_continuation(
    parts: Sequence[str],
) -> tuple[str, list[tuple[int, int]]]:
    merged = parts[0].strip(" \t\f\v") if parts else ""
    spans = [(0, len(merged))] if parts else []
    for part in parts[1:]:
        following = part.strip(" \t\f\v")
        if merged.rstrip().endswith("-"):
            merged = merged.rstrip() + following.lstrip()
        else:
            merged = merged.rstrip() + " " + following.lstrip()
        spans.append((len(merged) - len(following.lstrip()), len(merged)))
    return merged, spans


def _project_prose_continuation_group(
    group: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    canonical = [_canonical_extraction(extraction) for extraction in group]
    source_ids, source_locators, regions = _projection_source_metadata(canonical)
    text, spans = _join_prose_continuation([
        _normalize_prose_display_text(extraction.get("raw_text"))
        for extraction in group
    ])
    display_source_spans = [
        {
            "source_extraction_id": source_id,
            "source_locator": source_locator,
            "start": start,
            "end": end,
        }
        for source_id, source_locator, (start, end) in zip(
            source_ids,
            source_locators,
            spans,
            strict=True,
        )
    ]
    return {
        "region": " + ".join(str(region) for region in regions),
        "text": text,
        "source_locator": " + ".join(str(locator) for locator in source_locators),
        "reader_projection": {
            "kind": "prose_continuation_merge",
            "source_extraction_ids": source_ids,
            "source_locators": source_locators,
            "display_source_spans": display_source_spans,
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

    Cross-block repairs are conservative: the existing PDF drop-cap case, plus
    lower-case prose continuations across adjacent projected extraction order.
    The projection keeps exact contributing extraction IDs, locators, and raw
    text in ``canonical_extractions``.
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
        group = [current]
        lookahead = index + 1
        while lookahead < len(extractions) and _is_safe_prose_continuation(
            group[-1],
            extractions[lookahead],
        ):
            group.append(extractions[lookahead])
            lookahead += 1
        if len(group) > 1:
            projected.append(_project_prose_continuation_group(group))
            index = lookahead
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
