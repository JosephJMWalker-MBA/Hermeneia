"""
Manifest — storage artifact only, NOT a canonical ontology object (ADR-0008).

Written atomically as the last step after all content is checksummed.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class ManifestStore:
    pass


def build_manifest(
    source_document_id: str,
    original_filename: str,
    total_observations: int,
    total_provenance: int,
    compiler_version: str,
    compilation_run_id: str,
    observations_checksum: str,
    provenance_checksum: str,
) -> dict:
    return {
        "schema": "hermeneia-manifest-v1",
        "source_document_id": source_document_id,
        "original_filename": original_filename,
        "total_observations": total_observations,
        "total_provenance": total_provenance,
        "compiler_version": compiler_version,
        "compilation_run_id": compilation_run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checksums": {
            "observations_jsonl": observations_checksum,
            "provenance_jsonl": provenance_checksum,
        },
    }


def jsonl_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(manifest: dict, path: Path) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True))
