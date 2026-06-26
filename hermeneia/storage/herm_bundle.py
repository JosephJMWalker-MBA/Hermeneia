""".herm bundle writer.

Constitutional bundle shape:
  context.json
  hermeneia.db
"""
import json
from pathlib import Path


class HermBundle:
    """Portable corpus container."""
    pass


def write_herm_bundle(
    bundle_dir: Path,
    source_document: dict,
    compiler_version: str,
    compilation_run_id: str,
) -> Path:
    """Write constitutional bundle metadata.

    The SQLite database is copied by the repository after context creation.
    Legacy JSONL files are removed so the bundle does not advertise a competing
    authoritative format.
    """
    bundle_dir.mkdir(parents=True, exist_ok=True)

    for legacy_name in (
        "manifest.json",
        "observations.jsonl",
        "provenance.jsonl",
        "source_document.json",
    ):
        legacy = bundle_dir / legacy_name
        if legacy.exists():
            legacy.unlink()

    context = {
        "schema": "hermeneia-bundle-v1",
        "source_document_id": source_document["id"],
        "original_filename": source_document["original_filename"],
        "compiler_version": compiler_version,
        "compilation_run_id": compilation_run_id,
        "storage": {
            "database": "hermeneia.db",
            "authoritative": True,
        },
    }
    (bundle_dir / "context.json").write_text(
        json.dumps(context, indent=2, ensure_ascii=True, default=str),
        encoding="utf-8",
    )

    return bundle_dir
