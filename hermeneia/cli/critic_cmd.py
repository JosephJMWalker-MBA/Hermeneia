"""
herm critic OBS-N [--narrative-id ID]

Runs the Critic on the most recent Rendered Narrative for OBS-N's blueprint.
The Critic is deterministic — no LLM, no subjectivity.
It checks whether the Artist satisfied the semantic contract defined by the Architect.

If a ValidationReport already exists for the narrative, displays it (idempotent).
Use --narrative-id to target a specific render (e.g. a specific Expression Profile).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console()


def _open_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        console.print(f"[red]Database not found:[/] {db_path}")
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_db(bundle_or_db: str | None, default: str = "build/hermeneia.db") -> Path:
    if bundle_or_db is None:
        return Path(default)
    p = Path(bundle_or_db)
    return p if (p.suffix == ".db" or p.name.endswith(".db")) else Path(default)


def _parse_obs_ref(ref: str) -> int:
    ref = ref.upper().strip()
    return int(ref[4:]) if ref.startswith("OBS-") else int(ref)


def cmd_critic(
    obs_ref: str,
    narrative_id: str | None = None,
    bundle_or_db: str | None = None,
) -> None:
    from ..compiler.critic import run_critic
    from ..storage.sqlite import ensure_critic_tables

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_critic_tables(conn)

    n = _parse_obs_ref(obs_ref)
    all_ids = [
        r[0] for r in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]

    try:
        report = run_critic(n, all_ids, conn, narrative_id=narrative_id)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        conn.close()
        sys.exit(1)

    # Check idempotency — report already exists?
    existing = conn.execute(
        "SELECT * FROM validation_reports WHERE id = ?", (report["id"],)
    ).fetchone()

    if existing:
        console.print("[dim]  Validation report already exists (idempotent).[/]\n")
        _display_report(dict(existing))
        conn.close()
        return

    # Store
    conn.execute(
        """
        INSERT OR IGNORE INTO validation_reports
            (id, rendered_narrative_id, architect_plan_id, expression_profile_id,
             semantic_fidelity, required_terms_present, required_terms_missing,
             unsupported_claims, omitted_observations, omitted_interpretations,
             semantic_drift, warnings, approved, created_at)
        VALUES
            (:id, :rendered_narrative_id, :architect_plan_id, :expression_profile_id,
             :semantic_fidelity, :required_terms_present, :required_terms_missing,
             :unsupported_claims, :omitted_observations, :omitted_interpretations,
             :semantic_drift, :warnings, :approved, :created_at)
        """,
        report,
    )
    conn.commit()

    console.print(Rule(f"[bold cyan]Critic: OBS-{n}[/]", style="cyan"))
    console.print("[green]✓  Validation report stored.[/]\n")
    _display_report(report)

    # Run all Evaluation Functions and persist Findings
    _run_and_display_evaluation_functions(
        report["rendered_narrative_id"],
        report["architect_plan_id"],
        db_path,
        conn,
    )

    conn.close()


def _run_and_display_evaluation_functions(
    narrative_id: str,
    plan_id: str,
    db_path: "Path",
    conn: sqlite3.Connection,
) -> None:
    """Run all EFs, store findings, display summary table."""
    from rich.table import Table
    from rich import box
    from ..compiler.evaluation_functions.runner import run_all_evaluation_functions
    from ..storage.sqlite import SQLiteStore

    try:
        run = run_all_evaluation_functions(narrative_id, plan_id, conn)
    except Exception as exc:
        console.print(f"[yellow]⚠  Evaluation functions failed: {exc}[/]")
        return

    if run.all_findings:
        store = SQLiteStore(db_path)
        store.insert_findings_batch(run.all_findings)
        store.close()

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Dimension", style="cyan", min_width=20)
    table.add_column("Findings", justify="right", width=9)
    table.add_column("Errors", width=8)
    for ef in run.ef_results:
        err_cell = f"[red]{ef.error[:30]}[/]" if ef.error else "[dim]—[/]"
        table.add_row(ef.dimension, str(len(ef.findings)), err_cell)

    console.print()
    console.print(f"  [dim]Evaluation Functions[/]  ({run.total_findings} findings)")
    console.print(table)
    if run.errors:
        console.print(f"\n  [yellow]⚠  {len(run.errors)} EF(s) encountered errors[/]")


def _display_report(row: dict) -> None:
    present = json.loads(row["required_terms_present"])
    missing = json.loads(row["required_terms_missing"])
    forbidden = json.loads(row["unsupported_claims"])
    warnings = json.loads(row["warnings"])
    approved = bool(row["approved"])
    fidelity = row["semantic_fidelity"]

    # Profile badge
    profile_info = ""
    if row.get("expression_profile_id"):
        profile_info = f"  [dim]Profile:[/]  {row['expression_profile_id'][:16]}…\n"

    console.print(f"  [dim]Narrative:[/] {row['rendered_narrative_id'][:16]}…")
    if profile_info:
        console.print(profile_info, end="")
    console.print(f"  [dim]Created:[/]   {row['created_at'][:19].replace('T', ' ')} UTC\n")

    # Fidelity score
    color = "green" if fidelity >= 80 else "yellow" if fidelity >= 50 else "red"
    console.print(f"  Semantic Fidelity  [{color}]{fidelity}%[/]")
    status = "[green]APPROVED ✓[/]" if approved else "[red]NOT APPROVED ✗[/]"
    console.print(f"  Status             {status}\n")

    # Terms table
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Required Terms", min_width=20)
    table.add_column("Status")

    for t in present:
        table.add_row(t, "[green]✓ present[/]")
    for t in missing:
        table.add_row(t, "[red]✗ missing[/]")

    if present or missing:
        console.print(table)
        console.print()

    if forbidden:
        console.print(Panel(
            "\n".join(f"  ✗ {c}" for c in forbidden),
            title="[red]Forbidden Claims Detected[/]",
            border_style="red",
        ))

    if warnings:
        for w in warnings:
            console.print(f"  [yellow]⚠[/]  {w}")
