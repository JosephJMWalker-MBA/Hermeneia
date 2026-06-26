"""
herm architect OBS-N

Appoints the Architect for the NarrativeBlueprint that cites OBS-N.
Produces a deterministic ArchitectPlan from that Blueprint.

If a plan already exists for this Blueprint, shows it instead of
regenerating (idempotent). Warns if the Blueprint has changed since the
plan was generated.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich import box
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
    if p.suffix == ".db" or p.name.endswith(".db"):
        return p
    return Path(default)


def _parse_obs_ref(ref: str) -> int:
    ref = ref.upper().strip()
    if ref.startswith("OBS-"):
        return int(ref[4:])
    return int(ref)


def cmd_architect(obs_ref: str, bundle_or_db: str | None = None) -> None:
    """Appoint the Architect for the blueprint that cites OBS-N."""
    from ..compiler.architect import compile_architect_plan
    from ..storage.hashing import make_blueprint_id
    from ..storage.sqlite import ensure_architect_tables

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_architect_tables(conn)

    # ── Resolve OBS-N ───────────────────────────────────────────────────────
    n = _parse_obs_ref(obs_ref)
    all_ids = [
        r[0] for r in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]
    if n < 1 or n > len(all_ids):
        console.print(f"[red]OBS-{n} not found (total: {len(all_ids)})[/]")
        conn.close()
        sys.exit(1)
    obs_id = all_ids[n - 1]

    # ── Find blueprint citing this observation ──────────────────────────────
    bp_row = conn.execute(
        """
        SELECT nb.* FROM narrative_blueprints nb
        JOIN blueprint_observation_links bol ON bol.blueprint_id = nb.id
        WHERE bol.observation_id = ?
        ORDER BY nb.created_at LIMIT 1
        """,
        (obs_id,),
    ).fetchone()

    if bp_row is None:
        console.print(f"[red]No Narrative Blueprint cites OBS-{n}.[/]")
        console.print("[dim]Create one first with: herm blueprint create[/]")
        conn.close()
        sys.exit(1)

    bp = dict(bp_row)
    blueprint_id = bp["id"]

    console.print(Rule(f"[bold cyan]Architect: OBS-{n}[/]", style="cyan"))
    console.print(f'\n  Blueprint: [bold]"{bp["title"]}"[/]')
    console.print(f'  ID: [dim]{blueprint_id[:16]}…[/]\n')

    # ── Check for existing plan ─────────────────────────────────────────────
    existing = conn.execute(
        "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
        (blueprint_id,),
    ).fetchone()

    if existing:
        existing = dict(existing)
        # Staleness check
        sections = json.loads(bp["sections"])
        current_hash = make_blueprint_id(bp["title"], bp["thesis"], sections)
        is_stale = existing["blueprint_hash"] != current_hash

        if is_stale:
            console.print(
                "[yellow]⚠  Existing plan is out of date.[/]\n"
                "[dim]   Blueprint has changed since this plan was generated.[/]\n"
            )
        else:
            console.print("[dim]  Plan already exists (idempotent).[/]\n")

        _display_plan(conn, existing, n)
        conn.close()
        return

    # ── Compile new plan ────────────────────────────────────────────────────
    console.print("  Compiling deterministic plan…\n")

    result = compile_architect_plan(blueprint_id, conn)

    # Persist via raw SQL (mirrors SQLiteStore.insert_architect_plan)
    conn.execute(
        """
        INSERT OR IGNORE INTO architect_plans
            (id, blueprint_id, blueprint_hash, title, source, created_at)
        VALUES
            (:id, :blueprint_id, :blueprint_hash, :title, :source, :created_at)
        """,
        result["plan_row"],
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO architect_plan_paragraphs
            (plan_id, order_idx, purpose, blueprint_section,
             required_observations, required_interpretations,
             required_terms, forbidden_claims, notes)
        VALUES
            (:plan_id, :order_idx, :purpose, :blueprint_section,
             :required_observations, :required_interpretations,
             :required_terms, :forbidden_claims, :notes)
        """,
        result["paragraph_rows"],
    )
    conn.commit()

    console.print("[green]✓  Architect Plan created.[/]\n")

    plan = conn.execute(
        "SELECT * FROM architect_plans WHERE id = ?", (result["plan_row"]["id"],)
    ).fetchone()
    _display_plan(conn, dict(plan), n)
    conn.close()


def _display_plan(
    conn: sqlite3.Connection,
    plan: dict,
    obs_n: int,
) -> None:
    console.print(f"  [dim]Plan ID:[/] {plan['id'][:16]}…")
    console.print(f"  [dim]Source:[/]  {plan['source']}")
    console.print(f"  [dim]Created:[/] {plan['created_at'][:19].replace('T', ' ')} UTC\n")

    paras = conn.execute(
        "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
        (plan["id"],),
    ).fetchall()

    # Build index for display
    all_ids = [
        r[0] for r in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]
    id_to_n = {oid: i + 1 for i, oid in enumerate(all_ids)}

    for para in paras:
        para = dict(para)
        obs_ids   = json.loads(para["required_observations"])
        interp_ids = json.loads(para["required_interpretations"])
        terms     = json.loads(para["required_terms"])

        console.print(
            Panel(
                f'[bold]{para["purpose"]}[/]',
                title=f"[dim]§{para['order_idx']} — Blueprint section {para['blueprint_section']}[/]",
                border_style="cyan",
                padding=(0, 1),
            )
        )

        if obs_ids:
            obs_refs = "  ".join(
                f"[cyan]OBS-{id_to_n.get(oid, '?')}[/]" for oid in obs_ids
            )
            console.print(f"  [dim]Evidence:[/]        {obs_refs}")

        if interp_ids:
            console.print(
                f"  [dim]Interpretations:[/] {len(interp_ids)} required"
            )

        critical    = [t["term"] for t in terms if t["priority"] == "critical"]
        recommended = [t["term"] for t in terms if t["priority"] == "recommended"]

        if critical:
            crit_str = "  ".join(f"[bold]{t}[/]" for t in critical)
            console.print(f"  [dim]Critical terms:[/]   {crit_str}")
        if recommended:
            rec_str = "  ".join(f"[dim]{t}[/]" for t in recommended[:5])
            more = f"  [dim]… +{len(recommended)-5}[/]" if len(recommended) > 5 else ""
            console.print(f"  [dim]Recommended:[/]      {rec_str}{more}")

        console.print()
