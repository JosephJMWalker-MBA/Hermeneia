"""
Top-level orchestration for deterministic compilation (ADR-0006 – ADR-0014).

PDF → Parser → Paragraphs → Sentences → Observations → Storage
    → Field v0.1 (term index) → .herm bundle

No LLM. No inference. No AI of any kind.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..field.index import build_term_index
from ..storage.hashing import sha256_file
from ..storage.repository import Repository
from .observation_compiler import COMPILER_VERSION, compile_observations
from .paragraph_splitter import extract_paragraphs
from .parser import RawBlock, page_count, parse_pdf, parser_name, parser_version
from .source_extraction_compiler import compile_source_extractions


class Compiler:
    """Coordinates compilation stages."""

    def __init__(self, db_path: str | Path, build_dir: str | Path):
        self.db_path = Path(db_path)
        self.build_dir = Path(build_dir)
        self.repo = Repository(self.db_path)

    def compile(self, pdf_path: str | Path) -> Path:
        """Compile a PDF to a .herm bundle directory.

        Returns the path to the bundle directory.
        Idempotent: recompiling the same PDF inserts nothing (INSERT OR IGNORE).
        """
        pdf_path = Path(pdf_path)
        compilation_run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # --- Step 1: Register source document ---
        doc_hash = sha256_file(pdf_path)
        total_pages = page_count(pdf_path)

        source_doc = {
            "id": doc_hash,
            "original_filename": pdf_path.name,
            "file_hash": doc_hash,
            "total_pages": total_pages,
            "registered_at": now.isoformat(),
            "compiler_version": COMPILER_VERSION,
        }
        self.repo.register_source_document(source_doc)

        # --- Step 2: Exact parser output → immutable SourceExtraction ---
        raw_blocks: list[RawBlock] = list(parse_pdf(pdf_path))
        parser = parser_name()
        p_version = parser_version()
        source_extractions = compile_source_extractions(
            blocks=raw_blocks,
            source_document_id=doc_hash,
            source_document_hash=doc_hash,
            parser=parser,
            parser_version=p_version,
            now=now,
        )
        self.repo.persist_source_extractions([r.row for r in source_extractions])

        # --- Step 3: SourceExtraction-derived paragraphs ---
        paragraphs = list(
            extract_paragraphs(
                raw_blocks,
                source_document_hash=doc_hash,
                parser=parser,
                parser_version=p_version,
            )
        )

        # --- Step 4: Compile observations ---
        records = compile_observations(
            paragraphs=paragraphs,
            source_document_id=doc_hash,
            source_document_hash=doc_hash,
            compilation_run_id=compilation_run_id,
            now=now,
        )

        # --- Step 5: Persist (append-only) ---
        self.repo.persist_observations([r.obs for r in records])
        self.repo.persist_provenance([r.prov for r in records])
        self.repo.persist_observation_derived([r.derived for r in records])

        # --- Step 5b: Build Field v0.1 term index ---
        n_terms, n_pairs = build_term_index(self.repo.store)
        print(f"  Field v0.1: {n_terms:,} terms, {n_pairs:,} observation-term pairs")

        # --- Step 6: Write .herm bundle ---
        stem = pdf_path.stem
        bundle_dir = self.build_dir / f"{stem}.herm"
        self.repo.write_bundle(
            bundle_dir=bundle_dir,
            source_document_id=doc_hash,
            compiler_version=COMPILER_VERSION,
            compilation_run_id=compilation_run_id,
        )

        print(
            f"Compiled {pdf_path.name}: "
            f"{len(records)} observations → {bundle_dir}"
        )
        return bundle_dir

    def close(self) -> None:
        self.repo.close()
