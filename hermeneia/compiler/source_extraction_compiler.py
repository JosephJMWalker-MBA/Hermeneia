"""
SourceExtraction compiler.

Transforms exact parser blocks into immutable SourceExtraction rows before any
normalization, segmentation, or derived metadata is produced.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from ..storage.hashing import make_source_extraction_id, make_source_locator
from .parser import RawBlock


@dataclass(frozen=True)
class CompiledSourceExtraction:
    row: dict


def compile_source_extractions(
    blocks: list[RawBlock],
    source_document_id: str,
    source_document_hash: str,
    parser: str,
    parser_version: str,
    now: datetime | None = None,
) -> list[CompiledSourceExtraction]:
    """Convert parser RawBlocks to row-ready SourceExtraction records."""
    if now is None:
        now = datetime.now(timezone.utc)
    ts = now.isoformat()

    rows: list[CompiledSourceExtraction] = []
    for block in blocks:
        source_locator = make_source_locator(block.page, block.block_index)
        coordinates = json.dumps(
            {
                "x0": block.x0,
                "y0": block.y0,
                "x1": block.x1,
                "y1": block.y1,
            },
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        extraction_id = make_source_extraction_id(
            source_hash=source_document_hash,
            source_locator=source_locator,
            raw_text=block.text,
            parser=parser,
            parser_version=parser_version,
        )
        rows.append(
            CompiledSourceExtraction(
                row={
                    "id": extraction_id,
                    "epistemic_class": "Evidence",
                    "document_id": source_document_id,
                    "page": block.page,
                    "region": f"block:{block.block_index}",
                    "raw_text": block.text,
                    "parser": parser,
                    "parser_version": parser_version,
                    "coordinates": coordinates,
                    "source_locator": source_locator,
                    "source_hash": source_document_hash,
                    "hash": extraction_id,
                    "extracted_at": ts,
                }
            )
        )

    return rows
