"""
PDF parser — converts PDF pages to structured text blocks (ADR-0006, ADR-0013).

Uses pymupdf (fitz). No AI. No inference. Pure text extraction.

Returns a sequence of RawBlock: (page, block_index, text, bbox).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import fitz  # pymupdf


@dataclass(frozen=True)
class RawBlock:
    page: int         # 1-indexed
    block_index: int  # 0-indexed within page
    text: str         # raw extracted text, may contain internal newlines
    x0: float
    y0: float
    x1: float
    y1: float


def parser_name() -> str:
    return "pymupdf"


def parser_version() -> str:
    return str(getattr(fitz, "VersionBind", "unknown"))


def parse_pdf(pdf_path: str | Path) -> Generator[RawBlock, None, None]:
    """Yield RawBlock objects for every text block in the PDF.

    RawBlock.text is exact parser output for the block. Do not strip, normalize,
    or repair it here; SourceExtraction persistence owns the forensic record.
    """
    doc = fitz.open(str(pdf_path))
    try:
        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("blocks")
            for block in blocks:
                x0, y0, x1, y1, text, block_no, block_type = block
                if block_type != 0:  # skip images
                    continue
                if text == "":
                    continue
                yield RawBlock(
                    page=page_num + 1,
                    block_index=block_no,
                    text=text,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                )
    finally:
        doc.close()


def page_count(pdf_path: str | Path) -> int:
    doc = fitz.open(str(pdf_path))
    n = doc.page_count
    doc.close()
    return n
