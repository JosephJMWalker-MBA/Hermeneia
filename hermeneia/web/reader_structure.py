"""Derived authored-structure inference for Reader source evidence.

This module reads immutable SourceExtraction rows and produces a deterministic,
read-only structural projection. It classifies presentation patterns; it never
rewrites source text, suppresses blocks, or creates canonical objects.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


STRUCTURE_INFERENCE_VERSION = "reader-authored-structure-v1"

_BLOCK_REGION = re.compile(r"block:(\d+)")
_LOCATOR_BLOCK = re.compile(r"page:(\d+):block:(\d+)")
_CHAPTER_RE = re.compile(
    r"^chapter\s+(?P<num>[0-9]{1,4}|[ivxlcdm]{1,12}|[a-z][a-z -]{1,30})\.?$",
    re.I,
)
_PART_RE = re.compile(
    r"^part\s+(?P<num>[0-9]{1,4}|[ivxlcdm]{1,12}|[a-z][a-z -]{1,30})\.?$",
    re.I,
)
_NUMERIC_SECTION_RE = re.compile(r"^(?P<num>[0-9]{1,3}|[ivxlcdm]{1,12})\.?$", re.I)
_PAGE_HEADER_RE = re.compile(r"^\d{1,4}\s*[A-Z][A-Z0-9 '&.,:-]{3,}$")
_ROMAN_VALUES = {
    "i": 1,
    "v": 5,
    "x": 10,
    "l": 50,
    "c": 100,
    "d": 500,
    "m": 1000,
}
_WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


@dataclass(frozen=True)
class SourceBlock:
    """Ordered SourceExtraction evidence available to the Reader."""

    order: int
    id: str
    document_id: str
    page: int
    region: str
    raw_text: str
    source_locator: str
    coordinates: Mapping[str, object] = field(default_factory=dict)

    @property
    def block_index(self) -> int | None:
        match = _BLOCK_REGION.fullmatch(self.region)
        if match:
            return int(match.group(1))
        locator_match = _LOCATOR_BLOCK.fullmatch(self.source_locator)
        if locator_match:
            return int(locator_match.group(2))
        return None

    @property
    def lines(self) -> list[str]:
        return [line for line in self.raw_text.splitlines() if line.strip()]

    @property
    def stripped_lines(self) -> list[str]:
        return [line.strip() for line in self.lines]


@dataclass
class StructureCandidate:
    document_id: str
    kind: str
    heading_text: str
    heading_number: int | None
    heading_family: str
    heading_block: SourceBlock
    heading_line_index: int
    basis: list[str]
    confidence_score: int
    title_text: str | None = None
    title_block: SourceBlock | None = None
    resumes_block: SourceBlock | None = None
    preceding_prose_block: SourceBlock | None = None
    running_header_block: SourceBlock | None = None
    start_context_block: SourceBlock | None = None

    def add_basis(self, basis: str) -> None:
        if basis not in self.basis:
            self.basis.append(basis)
            self.confidence_score += 1

    @property
    def confidence(self) -> str:
        if (
            self.confidence_score >= 5
            and "heading_shape" in self.basis
            and "prose_resumes_after" in self.basis
            and (
                "adjacent_title_block" in self.basis
                or "adjacent_title_line" in self.basis
                or "repeated_document_pattern" in self.basis
            )
            and (
                "page_transition_context" in self.basis
                or "repeated_document_pattern" in self.basis
                or "preceding_prose_context" in self.basis
            )
        ):
            return "high"
        if (
            self.confidence_score >= 4
            and "heading_shape" in self.basis
            and "prose_resumes_after" in self.basis
        ):
            return "medium"
        return "candidate"

    @property
    def start_context(self) -> SourceBlock:
        return self.start_context_block or self.heading_block

    def to_item(self) -> dict[str, object]:
        evidence_blocks = _dedupe_evidence_blocks(
            [
                ("preceding_prose", self.preceding_prose_block),
                ("probable_running_header", self.running_header_block),
                ("heading", self.heading_block),
                ("title", self.title_block),
                ("prose_resumes", self.resumes_block),
            ]
        )
        contributing_ids = [block["source_extraction_id"] for block in evidence_blocks]
        contributing_locators = [block["source_locator"] for block in evidence_blocks]
        return {
            "id": _structure_id(
                self.document_id,
                self.kind,
                self.heading_block.source_locator,
                self.heading_text,
            ),
            "document_id": self.document_id,
            "kind": self.kind,
            "heading_text": self.heading_text,
            "title_text": self.title_text,
            "start_page": self.heading_block.page,
            "start_locator": self.heading_block.source_locator,
            "start_context_page": self.start_context.page,
            "start_context_locator": self.start_context.source_locator,
            "start_status": "inferred_from_source_evidence",
            "end_page": None,
            "end_locator": None,
            "end_status": "open",
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "confidence_model": "deterministic additive basis count",
            "basis": self.basis,
            "contributing_extraction_ids": contributing_ids,
            "contributing_locators": contributing_locators,
            "evidence_blocks": evidence_blocks,
            "status": "derived",
            "inference_version": STRUCTURE_INFERENCE_VERSION,
        }


def infer_reader_structure(
    document_id: str,
    extractions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Infer authored structure from ordered SourceExtraction rows."""
    blocks = _source_blocks(document_id, extractions)
    candidates = _initial_candidates(document_id, blocks)
    _apply_repetition(candidates)
    items = [candidate.to_item() for candidate in candidates]
    _apply_derived_ends(items, candidates, blocks)
    return {
        "document_id": document_id,
        "status": "derived",
        "inference_version": STRUCTURE_INFERENCE_VERSION,
        "storage": "computed_on_demand",
        "evidence_available": {
            "source_extraction_ids": True,
            "page": True,
            "region_block_order": True,
            "source_locator": True,
            "raw_text": True,
            "block_coordinates": True,
            "font_metadata": False,
            "line_level_typography": False,
        },
        "items": items,
    }


def _source_blocks(
    document_id: str,
    extractions: Sequence[Mapping[str, object]],
) -> list[SourceBlock]:
    blocks: list[SourceBlock] = []
    for order, row in enumerate(sorted(extractions, key=_sort_key)):
        blocks.append(
            SourceBlock(
                order=order,
                id=str(row.get("id") or ""),
                document_id=str(row.get("document_id") or document_id),
                page=_int_or_default(row.get("page"), 1),
                region=str(row.get("region") or ""),
                raw_text=str(row.get("raw_text") or ""),
                source_locator=str(row.get("source_locator") or ""),
                coordinates=_parse_coordinates(row.get("coordinates")),
            )
        )
    return blocks


def _sort_key(row: Mapping[str, object]) -> tuple[int, int, str]:
    page = _int_or_default(row.get("page"), 1)
    region = str(row.get("region") or "")
    region_match = _BLOCK_REGION.fullmatch(region)
    if region_match:
        block = int(region_match.group(1))
    else:
        locator_match = _LOCATOR_BLOCK.fullmatch(str(row.get("source_locator") or ""))
        block = int(locator_match.group(2)) if locator_match else 2_147_483_647
    return page, block, str(row.get("source_locator") or "")


def _parse_coordinates(raw: object) -> Mapping[str, object]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _initial_candidates(
    document_id: str,
    blocks: Sequence[SourceBlock],
) -> list[StructureCandidate]:
    candidates: list[StructureCandidate] = []
    for index, block in enumerate(blocks):
        heading = _heading_line(block)
        if heading is None:
            continue
        heading_line_index, heading_text, kind, family, number = heading
        basis = ["heading_shape"]
        score = 1
        if _isolated_heading_block(block, heading_line_index):
            basis.append("isolated_heading_block")
            score += 1

        candidate = StructureCandidate(
            document_id=document_id,
            kind=kind,
            heading_text=heading_text,
            heading_number=number,
            heading_family=family,
            heading_block=block,
            heading_line_index=heading_line_index,
            basis=basis,
            confidence_score=score,
        )
        _add_context(candidate, blocks, index)
        if candidate.kind == "section" and not _is_supported_numeric_section(candidate):
            continue
        candidates.append(candidate)
    return candidates


def _heading_line(
    block: SourceBlock,
) -> tuple[int, str, str, str, int | None] | None:
    for line_index, line in enumerate(block.stripped_lines):
        chapter = _CHAPTER_RE.fullmatch(line)
        if chapter:
            return (
                line_index,
                line,
                "chapter",
                "chapter_keyword",
                _parse_number(chapter.group("num")),
            )
        part = _PART_RE.fullmatch(line)
        if part:
            return (
                line_index,
                line,
                "part",
                "part_keyword",
                _parse_number(part.group("num")),
            )
        section = _NUMERIC_SECTION_RE.fullmatch(line)
        if section:
            return (
                line_index,
                line,
                "section",
                "numeric_section",
                _parse_number(section.group("num")),
            )
    return None


def _add_context(
    candidate: StructureCandidate,
    blocks: Sequence[SourceBlock],
    block_index: int,
) -> None:
    block = candidate.heading_block
    preceding = _previous_prose(blocks, block_index)
    if preceding is not None:
        candidate.preceding_prose_block = preceding
        candidate.add_basis("preceding_prose_context")

    header = _running_header_before(block, blocks, block_index, preceding)
    if header is not None:
        candidate.running_header_block = header
        candidate.start_context_block = header
        candidate.add_basis("probable_running_header")

    if _has_page_transition_context(block, preceding, header):
        candidate.add_basis("page_transition_context")

    title_line = _next_title_line(block, candidate.heading_line_index)
    if title_line:
        candidate.title_text = title_line
        candidate.add_basis("adjacent_title_line")

    next_index = block_index + 1
    if candidate.title_text is None and next_index < len(blocks):
        next_block = blocks[next_index]
        if _is_title_like(_block_text(next_block)):
            candidate.title_block = next_block
            candidate.title_text = _block_text(next_block)
            candidate.add_basis("adjacent_title_block")
            next_index += 1

    if next_index < len(blocks) and _is_prose_like(_block_text(blocks[next_index])):
        candidate.resumes_block = blocks[next_index]
        candidate.add_basis("prose_resumes_after")


def _apply_repetition(candidates: Sequence[StructureCandidate]) -> None:
    by_family: dict[str, list[StructureCandidate]] = defaultdict(list)
    for candidate in candidates:
        has_title = bool(candidate.title_text)
        if has_title and candidate.resumes_block is not None:
            by_family[candidate.heading_family].append(candidate)

    for repeated in by_family.values():
        if len(repeated) < 2:
            continue
        for candidate in repeated:
            candidate.add_basis("repeated_document_pattern")
        numbered = [candidate.heading_number for candidate in repeated]
        if all(number is not None for number in numbered) and _strictly_increasing(
            [int(number) for number in numbered if number is not None]
        ):
            for candidate in repeated:
                candidate.add_basis("coherent_sequence")


def _is_supported_numeric_section(candidate: StructureCandidate) -> bool:
    """Keep numbered sections conservative so page numbers do not become structure."""
    if candidate.title_block is None:
        return False
    if candidate.resumes_block is None:
        return False
    block_index = candidate.heading_block.block_index
    if (
        candidate.heading_number == candidate.heading_block.page
        and block_index is not None
        and block_index <= 1
    ):
        return False
    title = candidate.title_text or ""
    if _looks_like_repeated_publication_footer(title):
        return False
    return True


def _apply_derived_ends(
    items: list[dict[str, object]],
    candidates: Sequence[StructureCandidate],
    blocks: Sequence[SourceBlock],
) -> None:
    inferred = [
        (item, candidate)
        for item, candidate in zip(items, candidates, strict=True)
        if item["confidence"] in {"high", "medium"}
    ]
    for (item, _candidate), (_next_item, next_candidate) in zip(
        inferred, inferred[1:], strict=False
    ):
        end_block = _block_before_context(blocks, next_candidate.start_context.order)
        if end_block is None:
            continue
        item["end_page"] = end_block.page
        item["end_locator"] = end_block.source_locator
        item["end_status"] = "derived_from_next_structure_start"
        item["end_contributing_extraction_id"] = end_block.id


def _block_before_context(
    blocks: Sequence[SourceBlock],
    context_order: int,
) -> SourceBlock | None:
    for block in reversed(blocks[:context_order]):
        if not _looks_like_running_header(_block_text(block)):
            return block
    return None


def _previous_prose(
    blocks: Sequence[SourceBlock],
    index: int,
) -> SourceBlock | None:
    for previous in reversed(blocks[max(0, index - 4):index]):
        if _is_prose_like(_block_text(previous)):
            return previous
    return None


def _running_header_before(
    block: SourceBlock,
    blocks: Sequence[SourceBlock],
    index: int,
    preceding_prose: SourceBlock | None,
) -> SourceBlock | None:
    if index == 0:
        return None
    previous = blocks[index - 1]
    if not _looks_like_running_header(_block_text(previous)):
        return None
    if previous.page != block.page:
        return None
    if preceding_prose is not None and preceding_prose.page < block.page:
        return previous
    previous_block_index = previous.block_index
    if previous_block_index is not None and previous_block_index <= 2:
        return previous
    return None


def _has_page_transition_context(
    block: SourceBlock,
    preceding_prose: SourceBlock | None,
    header: SourceBlock | None,
) -> bool:
    if preceding_prose is not None and preceding_prose.page < block.page:
        return True
    if header is not None and header.page == block.page:
        return True
    block_index = block.block_index
    return bool(block.page > 1 and block_index is not None and block_index <= 2)


def _next_title_line(block: SourceBlock, heading_line_index: int) -> str | None:
    lines = block.stripped_lines
    following = lines[heading_line_index + 1: heading_line_index + 2]
    if following and _is_title_like(following[0]):
        return following[0]
    return None


def _isolated_heading_block(block: SourceBlock, heading_line_index: int) -> bool:
    lines = block.stripped_lines
    if len(lines) == 1:
        return True
    if len(lines) <= 3:
        before = lines[:heading_line_index]
        after = lines[heading_line_index + 1:]
        return all(_looks_like_running_header(line) for line in before) and all(
            _is_title_like(line) for line in after
        )
    return False


def _block_text(block: SourceBlock) -> str:
    return " ".join(line.strip() for line in block.lines).strip()


def _is_title_like(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _heading_line_for_text(stripped) is not None:
        return False
    if _looks_like_running_header(stripped):
        return False
    words = re.findall(r"[A-Za-z0-9']+", stripped)
    if not words or len(words) > 8 or len(stripped) > 90:
        return False
    if stripped[-1:] in ".!?;":
        return False
    alpha_words = [word for word in words if re.search(r"[A-Za-z]", word)]
    if not alpha_words:
        return False
    if sum(len(re.sub(r"[^A-Za-z]", "", word)) for word in alpha_words) <= 1:
        return False
    if stripped.isupper():
        return True
    return any(word[:1].isupper() for word in alpha_words)


def _is_prose_like(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _heading_line_for_text(stripped) is not None:
        return False
    if _looks_like_running_header(stripped):
        return False
    words = re.findall(r"[A-Za-z0-9']+", stripped)
    if len(words) < 6:
        return False
    return bool(re.search(r"[a-z]", stripped))


def _heading_line_for_text(text: str) -> bool | None:
    if _CHAPTER_RE.fullmatch(text) or _PART_RE.fullmatch(text):
        return True
    if _NUMERIC_SECTION_RE.fullmatch(text):
        return True
    return None


def _looks_like_running_header(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.isdecimal() and len(stripped) <= 4:
        return True
    compact = stripped.replace(" ", "")
    if _PAGE_HEADER_RE.fullmatch(stripped) and not _heading_line_for_text(stripped):
        return True
    return bool(re.fullmatch(r"\d{1,4}[A-Z][A-Z0-9'&.-]{3,}", compact))


def _looks_like_repeated_publication_footer(text: str) -> bool:
    lowered = text.strip().lower()
    return bool(
        lowered.startswith("free ebooks at ")
        or " ebook" in lowered
        or lowered.endswith(".com")
    )


def _parse_number(raw: str) -> int | None:
    value = raw.strip().lower().rstrip(".")
    if value.isdecimal():
        return int(value)
    if value in _WORD_NUMBERS:
        return _WORD_NUMBERS[value]
    if re.fullmatch(r"[ivxlcdm]+", value):
        return _parse_roman(value)
    return None


def _parse_roman(value: str) -> int | None:
    total = 0
    previous = 0
    for char in reversed(value.lower()):
        current = _ROMAN_VALUES.get(char)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total or None


def _strictly_increasing(values: Sequence[int]) -> bool:
    return all(left < right for left, right in zip(values, values[1:], strict=False))


def _dedupe_evidence_blocks(
    role_blocks: Sequence[tuple[str, SourceBlock | None]],
) -> list[dict[str, object]]:
    seen: set[str] = set()
    evidence: list[dict[str, object]] = []
    for role, block in role_blocks:
        if block is None or block.id in seen:
            continue
        seen.add(block.id)
        evidence.append(
            {
                "role": role,
                "source_extraction_id": block.id,
                "page": block.page,
                "region": block.region,
                "source_locator": block.source_locator,
                "raw_text": block.raw_text,
            }
        )
    return evidence


def _structure_id(
    document_id: str,
    kind: str,
    source_locator: str,
    heading_text: str,
) -> str:
    payload = json.dumps(
        {
            "document_id": document_id,
            "kind": kind,
            "source_locator": source_locator,
            "heading_text": heading_text,
            "version": STRUCTURE_INFERENCE_VERSION,
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
