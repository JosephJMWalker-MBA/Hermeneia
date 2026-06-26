"""
Observation compiler — converts paragraphs into Observation + Provenance records
(ADR-0006, ADR-0012, ADR-0013, ADR-0014).

No LLM. No inference. No embeddings. Pure deterministic transformation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..storage.hashing import make_observation_id, make_semantic_hash, make_source_locator
from .normalization import normalize_sentence
from .paragraph_splitter import Paragraph
from .sentence_splitter import split_sentences

COMPILER_VERSION = "0.1.0"


@dataclass
class CompiledObservation:
    obs: dict   # row-ready dict for SQLiteStore
    prov: dict  # row-ready dict for SQLiteStore
    derived: dict


class ObservationCompiler:
    pass


def compile_observations(
    paragraphs: list[Paragraph],
    source_document_id: str,
    source_document_hash: str,
    compilation_run_id: str,
    now: datetime | None = None,
) -> list[CompiledObservation]:
    """Convert a list of Paragraphs into CompiledObservation records.

    Sets preceding/following adjacency IDs on each Observation (ADR-0014).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    ts = now.isoformat()

    # First pass: build all records without adjacency
    records: list[CompiledObservation] = []

    for para in paragraphs:
        sentences = split_sentences(para.text)
        for sent_idx, raw_sentence in enumerate(sentences):
            sentence_num = sent_idx + 1  # 1-indexed
            source_locator = make_source_locator(
                para.page,
                para.block_index,
                sentence_num,
            )
            obs_id = make_observation_id(
                source_hash=source_document_hash,
                source_locator=source_locator,
                raw_text=raw_sentence,
            )

            # raw_text: sentence as selected from SourceExtraction-derived text
            # normalized_text belongs only to ObservationDerived.
            normalized = normalize_sentence(raw_sentence)

            obs_row = {
                "id": obs_id,
                "epistemic_class": "Evidence",
                "source_document_id": source_document_id,
                "source_extraction_id": para.source_extraction_id,
                "raw_text": raw_sentence,
                "source_locator": source_locator,
                "semantic_hash": make_semantic_hash(raw_sentence),
                "page": para.page,
                "paragraph": para.paragraph,
                "sentence": sentence_num,
                "preceding_observation_id": None,  # filled in second pass
                "following_observation_id": None,
                "created_at": ts,
            }

            prov_row = {
                "id": obs_id,  # identical to observation ID by ADR-0012
                "observation_id": obs_id,
                "source_document_id": source_document_id,
                "source_extraction_id": para.source_extraction_id,
                "source_document_hash": source_document_hash,
                "page": para.page,
                "paragraph": para.paragraph,
                "sentence": sentence_num,
                "verbatim_text": raw_sentence,  # provenance always holds the raw form
                "location_precision": "sentence",
                "char_offset_start": None,
                "char_offset_end": None,
                "bbox_x": para.x0,
                "bbox_y": para.y0,
                "bbox_width": para.x1 - para.x0,
                "bbox_height": para.y1 - para.y0,
                "bbox_dpi": None,
                "created_at": ts,
                "compiler_version": COMPILER_VERSION,
                "compilation_run_id": compilation_run_id,
            }

            derived_row = {
                "observation_id": obs_id,
                "normalized_text": normalized,
                "sentence_tokens": "[]",
                "whitespace_map": "[]",
                "derivation_version": COMPILER_VERSION,
                "derived_at": ts,
            }

            records.append(CompiledObservation(obs=obs_row, prov=prov_row, derived=derived_row))

    # Second pass: fill adjacency (ADR-0014, immutable after creation)
    for i, record in enumerate(records):
        if i > 0:
            record.obs["preceding_observation_id"] = records[i - 1].obs["id"]
        if i < len(records) - 1:
            record.obs["following_observation_id"] = records[i + 1].obs["id"]

    return records
