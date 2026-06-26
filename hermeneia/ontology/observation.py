from datetime import datetime
from typing import Optional
from .base import HermeneiaObject


class Observation(HermeneiaObject):
    """Layer 1: Smallest immutable epistemic record.

    One sentence = one Observation. Occurrence identity is based on
    source_hash + source_locator + raw_text.
    """
    id: str                                  # deterministic SHA-256 hash
    epistemic_class: str = "Evidence"
    source_document_id: str                  # FK to SourceDocument.id
    source_extraction_id: str                # FK to SourceExtraction.id
    raw_text: str                            # exact selected text, no normalization
    source_locator: str
    semantic_hash: str
    page: int                                # 1-indexed
    paragraph: int                           # 1-indexed within page
    sentence: int                            # 1-indexed within paragraph
    preceding_observation_id: Optional[str]  # navigation only, immutable
    following_observation_id: Optional[str]  # navigation only, immutable
    created_at: datetime
