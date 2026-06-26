"""
Domain repository — maps compiler output to SQLiteStore.

This is the only layer that touches both ontology objects and storage.
No business logic. No inference.
"""
from pathlib import Path

from .sqlite import SQLiteStore
from .herm_bundle import write_herm_bundle


class Repository:
    def __init__(self, db_path: str | Path):
        self.store = SQLiteStore(db_path)

    def register_source_document(self, doc: dict) -> None:
        self.store.insert_source_document(doc)

    def is_document_registered(self, doc_id: str) -> bool:
        return self.store.source_document_exists(doc_id)

    def persist_observations(self, rows: list[dict]) -> None:
        self.store.insert_observations_batch(rows)

    def persist_source_extractions(self, rows: list[dict]) -> None:
        self.store.insert_source_extractions_batch(rows)

    def persist_provenance(self, rows: list[dict]) -> None:
        self.store.insert_provenance_batch(rows)

    def persist_observation_derived(self, rows: list[dict]) -> None:
        self.store.insert_observation_derived_batch(rows)

    def write_bundle(
        self,
        bundle_dir: Path,
        source_document_id: str,
        compiler_version: str,
        compilation_run_id: str,
    ) -> Path:
        source_doc = self.store.get_source_document(source_document_id)
        bundle_path = write_herm_bundle(
            bundle_dir=bundle_dir,
            source_document=source_doc,
            compiler_version=compiler_version,
            compilation_run_id=compilation_run_id,
        )
        self.store.backup_to(bundle_path / "hermeneia.db")
        return bundle_path

    def observation_count(self, source_document_id: str | None = None) -> int:
        return self.store.count_observations(source_document_id)

    def close(self) -> None:
        self.store.close()
