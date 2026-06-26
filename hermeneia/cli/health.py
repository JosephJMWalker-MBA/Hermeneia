"""
Health dashboard — corpus confidence at a glance.

herm health

Shows the state of each layer in the epistemic pipeline:
  Compiler → Observations → Field → Interpretations → Perspectives →
  Contradictions → Blueprints → Essays

Coverage = % of observations that have entered the epistemic chain,
defined as: cited in at least one interpretation (as primary or evidence)
OR cited in at least one blueprint section.

An observation is "covered" when a steward has done something with it.
Uncovered observations are raw material waiting for interpretation.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from rich.console import Console
from rich.rule import Rule
from rich.table import Table
from rich import box

from ..storage.sqlite import SCHEMA_VERSION

console = Console()


# ── DB helpers ────────────────────────────────────────────────────────────────

def _open_db(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_db(bundle_or_db: str | None, default: str = "build/hermeneia.db") -> Path:
    if bundle_or_db is None:
        return Path(default)
    p = Path(bundle_or_db)
    if p.suffix == ".db" or p.name.endswith(".db"):
        return p
    if p.is_dir() and p.name.endswith(".herm"):
        candidate = p.parent / "hermeneia.db"
        if candidate.exists():
            return candidate
    return Path(default)


# ── Metric computations ───────────────────────────────────────────────────────

def compiler_ok(conn: sqlite3.Connection) -> tuple[bool, str]:
    """Check compiler health: schema version, source doc registered, obs exist."""
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if not row:
            return False, "schema_version table empty"
        if row[0] != SCHEMA_VERSION:
            return False, f"schema version {row[0]} (expected {SCHEMA_VERSION})"
        doc = conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
        if not doc:
            return False, "no source document registered"
        obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        if not obs:
            return False, "no observations"
        return True, f"schema v{row[0]} · {doc} document(s)"
    except sqlite3.OperationalError as e:
        return False, str(e)


def observation_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]


def interpretation_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM interpretations").fetchone()[0]


def perspective_count(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM perspectives").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def contradiction_count(conn: sqlite3.Connection) -> int:
    """Observations with interpretations that disagree on evidential status."""
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT observation_id
                FROM interpretations
                GROUP BY observation_id
                HAVING COUNT(DISTINCT evidential_status) > 1
            )
            """
        ).fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def architect_plan_count(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM architect_plans").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def blueprint_count(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM narrative_blueprints").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def field_term_count(conn: sqlite3.Connection) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def coverage_metrics(conn: sqlite3.Connection) -> tuple[int, int, float]:
    """Return (covered_obs_count, total_obs_count, coverage_fraction).

    An observation is 'covered' when it has entered the epistemic chain:
      - cited as the primary observation of at least one interpretation, OR
      - cited in any interpretation's evidence_observation_ids, OR
      - cited in any blueprint section (via blueprint_observation_links).

    Coverage measures steward engagement, not document completeness.
    """
    total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    if total == 0:
        return 0, 0, 0.0

    covered: set[str] = set()

    # Primary observations of interpretations
    for row in conn.execute("SELECT DISTINCT observation_id FROM interpretations"):
        covered.add(row[0])

    # Evidence observations (stored as JSON arrays)
    for row in conn.execute("SELECT evidence_observation_ids FROM interpretations"):
        try:
            ids = json.loads(row[0] or "[]")
            covered.update(ids)
        except (json.JSONDecodeError, TypeError):
            pass

    # Blueprint-linked observations
    try:
        for row in conn.execute("SELECT DISTINCT observation_id FROM blueprint_observation_links"):
            covered.add(row[0])
    except sqlite3.OperationalError:
        pass

    count = len(covered)
    return count, total, count / total if total else 0.0


# ── cmd_health ────────────────────────────────────────────────────────────────

def cmd_health(bundle_or_db: str | None = None) -> None:
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    console.print(Rule("[bold cyan]Hermeneia Health[/]", style="cyan"))
    console.print()

    table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 3),
        show_edge=False,
    )
    table.add_column("Layer", style="bold", min_width=24)
    table.add_column("Value", justify="right", min_width=10)
    table.add_column("Note", style="dim")

    # ── Compiler ──
    if conn is None:
        table.add_row("Compiler", "[red]✗[/]", f"database not found at {db_path}")
        console.print(table)
        return

    ok, compiler_note = compiler_ok(conn)
    table.add_row(
        "Compiler",
        "[green]✓[/]" if ok else "[red]✗[/]",
        compiler_note,
    )
    table.add_row("", "", "")

    # ── Observations ──
    n_obs = observation_count(conn)
    table.add_row("Observations", f"{n_obs:,}", "")

    # ── Field v0.1 ──
    n_terms = field_term_count(conn)
    table.add_row("Field terms", f"{n_terms:,}", "")
    table.add_row("", "", "")

    # ── Layer 1 ──
    n_interps = interpretation_count(conn)
    table.add_row("Interpretations", f"{n_interps:,}", "")

    n_perspectives = perspective_count(conn)
    table.add_row("Perspectives", f"{n_perspectives:,}", "")

    n_contradictions = contradiction_count(conn)
    contradiction_note = (
        "[yellow]requires steward review[/]" if n_contradictions > 0 else ""
    )
    table.add_row(
        "Contradictions",
        f"[yellow]{n_contradictions:,}[/]" if n_contradictions > 0 else "0",
        contradiction_note,
    )
    table.add_row("", "", "")

    # ── Future layers (placeholders) ──
    table.add_row("Dialogues", "[dim]0[/]", "[dim]not yet implemented[/]")
    table.add_row("Transformation Plans", "[dim]0[/]", "[dim]not yet implemented[/]")

    # ── Layer 3 ──
    n_blueprints = blueprint_count(conn)
    table.add_row("Narrative Blueprints", f"{n_blueprints:,}", "")
    table.add_row("Essays", "[dim]0[/]", "[dim]not yet implemented[/]")
    table.add_row("", "", "")

    # ── Coverage (computed before close) ──
    covered, total, fraction = coverage_metrics(conn)
    conn.close()
    console.print(table)
    bar_filled = int(fraction * 20)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    pct = f"{fraction:.1%}"
    coverage_color = "green" if fraction > 0.5 else "yellow" if fraction > 0.1 else "red"
    console.print(
        f"   [bold]Coverage[/]                        "
        f"[{coverage_color}]{pct:>8}[/]   [{coverage_color}]{bar}[/]"
    )
    console.print(
        f"   [dim]{'':24}{covered:,} of {total:,} observations in epistemic chain[/]"
    )
    console.print()
