from datetime import datetime

from .base import HermeneiaObject


class SourceExtraction(HermeneiaObject):
    """Forensic parser-output record.

    SourceExtraction preserves exact parser text before normalization,
    segmentation, or interpretation.
    """

    id: str
    epistemic_class: str = "Evidence"
    document_id: str
    page: int
    region: str
    raw_text: str
    parser: str
    parser_version: str
    coordinates: str
    source_locator: str
    source_hash: str
    hash: str
    extracted_at: datetime
