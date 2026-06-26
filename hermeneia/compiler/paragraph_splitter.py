"""
Paragraph splitter — groups RawBlocks into paragraphs (ADR-0006, ADR-0013).

In PDF extraction, each text block from pymupdf is treated as one paragraph.
Blocks with only whitespace or single characters are filtered.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

from .parser import RawBlock
from ..storage.hashing import make_source_extraction_id, make_source_locator

MIN_PARAGRAPH_LENGTH = 2  # characters; filters headers, page numbers, etc.


@dataclass(frozen=True)
class Paragraph:
    page: int         # 1-indexed
    paragraph: int    # 1-indexed within page
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    source_extraction_id: str
    source_locator: str
    block_index: int


def extract_paragraphs(
    blocks: list[RawBlock],
    source_document_hash: str,
    parser: str,
    parser_version: str,
) -> Generator[Paragraph, None, None]:
    """Yield Paragraphs from a flat list of RawBlocks.

    Assigns per-page paragraph indices (1-indexed).
    Filters blocks that are too short to contain meaningful content.
    """
    page_paragraph_counter: dict[int, int] = {}

    for block in blocks:
        text = block.text
        if len(text.strip()) < MIN_PARAGRAPH_LENGTH:
            continue

        page = block.page
        page_paragraph_counter[page] = page_paragraph_counter.get(page, 0) + 1
        source_locator = make_source_locator(block.page, block.block_index)
        source_extraction_id = make_source_extraction_id(
            source_hash=source_document_hash,
            source_locator=source_locator,
            raw_text=block.text,
            parser=parser,
            parser_version=parser_version,
        )

        yield Paragraph(
            page=page,
            paragraph=page_paragraph_counter[page],
            text=text,
            x0=block.x0,
            y0=block.y0,
            x1=block.x1,
            y1=block.y1,
            source_extraction_id=source_extraction_id,
            source_locator=source_locator,
            block_index=block.block_index,
        )
