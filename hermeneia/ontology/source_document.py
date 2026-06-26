from datetime import datetime
from .base import HermeneiaObject


class SourceDocument(HermeneiaObject):
    """Layer 0: Registered source document (ADR-0013).

    id == sha256 of file content. Immutable after registration.
    """
    id: str                          # SHA-256 of file bytes
    original_filename: str
    file_hash: str                   # same as id; kept explicit for clarity
    total_pages: int
    registered_at: datetime
    compiler_version: str
