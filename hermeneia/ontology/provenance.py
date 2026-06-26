from datetime import datetime
from typing import Literal, Optional
from .base import HermeneiaObject

LocationPrecision = Literal["sentence", "paragraph", "page"]


class Provenance(HermeneiaObject):
    """Layer 1: Mandatory provenance record for every Observation (ADR-0012, ADR-0013).

    ID is SHA-256 of (source_document_hash, page, paragraph, sentence).
    Identical to Observation ID by construction.
    """
    id: str                           # SHA-256 matching observation id
    observation_id: str               # FK to Observation.id
    source_document_id: str
    source_extraction_id: str
    source_document_hash: str         # SHA-256 of source file bytes

    page: int                         # 1-indexed
    paragraph: int                    # 1-indexed within page
    sentence: int                     # 1-indexed within paragraph
    verbatim_text: str                # copy from observation for self-contained record

    location_precision: LocationPrecision  # "sentence" is normative

    # Optional character offsets (ADR-0013 rule 1)
    char_offset_start: Optional[int] = None
    char_offset_end: Optional[int] = None

    # Optional OCR bounding box (ADR-0013 rule 2)
    bbox_x: Optional[float] = None
    bbox_y: Optional[float] = None
    bbox_width: Optional[float] = None
    bbox_height: Optional[float] = None
    bbox_dpi: Optional[int] = None

    created_at: datetime
    compiler_version: str
    compilation_run_id: str           # UUID for this compilation run
