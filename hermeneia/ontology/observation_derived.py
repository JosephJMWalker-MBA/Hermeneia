from datetime import datetime

from .base import HermeneiaObject


class ObservationDerived(HermeneiaObject):
    """Disposable metadata derived from an immutable Observation."""

    observation_id: str
    normalized_text: str
    sentence_tokens: str
    whitespace_map: str
    derivation_version: str
    derived_at: datetime
