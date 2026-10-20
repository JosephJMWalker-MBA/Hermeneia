"""What a WBS bundle does not carry (#252 coverage audit): declared and counted, never repaired.

Blueprint-chain portability is not complete study portability. Every runtime
table is either exported by a WBS file, carried by a capability component, or
listed here. Export records how many source records each listed surface left
behind. Restore reports every listed surface as unsupported; older bundles
report it with unknown counts. Nothing is reconstructed, backfilled or
rebuilt. Contract: docs/design/blueprint-chain-portability-v1.md §9.
"""
from __future__ import annotations

import sqlite3

# (surface, tables, kind, reason). "kind" separates history that is lost from derived state that is not rebuilt.
NOT_CARRIED: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("study_reviews", ("observation_reviews", "inquiry_notes"), "history",
     "Observation reviews and inquiry questions are not written by any WBS exporter (spec §6.3)."),
    ("reports", ("rendered_narratives", "critic_reports", "validation_reports"), "history",
     "Rendered narratives, Critic reports and validation reports are not written by any WBS exporter (spec §6.3)."),
    ("governance", ("steward_decisions", "findings", "ratification_records", "witness_sessions"), "history",
     "Steward decisions, findings, ratification records and Witness sessions are not written by any WBS exporter (spec §6.3)."),
    ("custom_expression_profiles", ("expression_profiles",), "history",
     "Expression Profiles other than the built-in defaults are not written by any WBS exporter."),
    ("reading_progress", ("reading_progress",), "state",
     "Per-document reading progress is not written by any WBS exporter."),
    ("derived_indexes", ("observation_derived", "terms", "observation_terms"), "derived_not_rebuilt",
     "Compile-time search and term indexes are neither exported nor rebuilt by restore; a restored workspace has them empty."),
    ("observation_provenance", ("provenance",), "provenance_not_rebuilt",
     "Compile-time Observation provenance (verbatim text, character offsets) is neither exported nor rebuilt by restore. "
     "In a restored workspace the Critic's provenance check reports Observations as transformed, narrative trust summaries "
     "cannot confirm verbatim text, and Reader character offsets are unavailable."),
)
CHAIN_SURFACE = "blueprint_dependency_chain"
PORTABILITY_REASON = ("A WBS bundle carries the documented surfaces only. The surfaces under not_carried are absent from "
                      "this bundle and from any workspace restored from it; nothing is reconstructed.")


def _count(conn: sqlite3.Connection, table: str) -> int | None:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is None:
        return None
    if table == "expression_profiles":
        columns = {row[1] for row in conn.execute("PRAGMA table_info(expression_profiles)")}
        if "source" not in columns:
            return None
        return conn.execute("SELECT COUNT(*) FROM expression_profiles WHERE source IS NOT 'built-in'").fetchone()[0]
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


# Surfaces the Observation compile-records component carries when a bundle has it.
COMPILE_RECORD_SURFACES = ("derived_indexes", "observation_provenance")


def not_exported(conn: sqlite3.Connection, *, chain_tables: tuple[str, ...] | None, chain_reason: str | None,
                 compile_records_carried: bool = False) -> dict:
    """Source record counts left behind by this export, per surface; None means the table is absent (unknown)."""
    out = {surface: {"kind": kind, "tables": {table: _count(conn, table) for table in tables}, "reason": reason}
           for surface, tables, kind, reason in NOT_CARRIED
           if not (compile_records_carried and surface in COMPILE_RECORD_SURFACES)}
    if chain_tables is not None:
        out[CHAIN_SURFACE] = {"kind": "history", "tables": {table: _count(conn, table) for table in chain_tables},
                              "reason": chain_reason}
    return out


def restore_coverage(manifest: dict, *, chain_covered: bool, compile_records_covered: bool = False) -> dict:
    """Declared absence for every surface a bundle does not carry, with the source counts when the bundle has them."""
    recorded = manifest.get("not_exported") if isinstance(manifest.get("not_exported"), dict) else None
    surfaces = {}
    for surface, tables, kind, reason in NOT_CARRIED:
        if compile_records_covered and surface in COMPILE_RECORD_SURFACES:
            continue
        entry = (recorded or {}).get(surface)
        surfaces[surface] = {"status": "unsupported", "kind": kind, "reason": reason,
                             "source_records": entry.get("tables") if isinstance(entry, dict) else "unknown"}
    if not compile_records_covered and "derived_indexes" in surfaces:
        # CI-016: restore rebuilds these from the restored Observations; provenance is never rebuilt.
        surfaces["derived_indexes"]["status"] = "rebuilt_on_restore"
    if not chain_covered and recorded is not None and isinstance(recorded.get(CHAIN_SURFACE), dict):
        entry = recorded[CHAIN_SURFACE]
        surfaces[CHAIN_SURFACE] = {"status": "unsupported", "kind": "history", "reason": entry.get("reason"),
                                   "source_records": entry.get("tables")}
    return {"study_portability": {"status": "partial", "reason": PORTABILITY_REASON,
                                  "source_counts": "recorded" if recorded is not None else "unknown"},
            "not_carried": surfaces}
