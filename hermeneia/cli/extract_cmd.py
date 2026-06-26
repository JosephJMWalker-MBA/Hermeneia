"""
Blueprint Extraction CLI — "Start From Existing Work" onboarding path.

Usage:
    herm extract FILE            # read from file
    herm extract --stdin         # read from stdin / paste
    herm extract FILE --provider anthropic
    herm extract FILE --provider openai --model gpt-4o

After extraction Hermeneia shows the proposed Blueprint and asks you to ratify
or discard it. If ratified, the Blueprint is stored and the Architect runs
deterministically to produce an ArchitectPlan.

No schema changes. This is prompt engineering + existing pipeline.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.rule import Rule
from rich.table import Table
from rich import box

from ..storage.hashing import make_blueprint_id
from ..compiler.blueprint_extractor import extract_blueprint_from_text, BlueprintExtractionError
from ..compiler.architect import compile_architect_plan

console = Console()


def _open_db(bundle_or_db: str | None) -> tuple[Path, sqlite3.Connection]:
    default = "build/hermeneia.db"
    if bundle_or_db is None:
        db_path = Path(default)
    else:
        p = Path(bundle_or_db)
        db_path = p if (p.suffix == ".db" or "hermeneia.db" in p.name) else Path(default)

    if not db_path.exists():
        console.print(f"[red]Database not found:[/] {db_path}")
        console.print("Run [bold]herm bootstrap[/] first.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return db_path, conn


def _get_provider(provider_name: str, model: str | None, api_key: str | None) -> Any:
    from ..narrative.artist_providers import get_provider
    kwargs: dict = {}
    if model:
        kwargs["model"] = model
    if api_key:
        kwargs["api_key"] = api_key
    return get_provider(provider_name, **kwargs)


def _display_proposed_blueprint(proposed: dict) -> None:
    console.print()
    console.print(Rule("[bold cyan]Intent Hypothesis[/bold cyan]"))
    console.print(
        "[dim]Hermeneia's reconstruction of what you are trying to establish.[/dim]"
    )
    console.print()
    console.print(Panel(
        f"[bold]{proposed['title']}[/bold]\n\n{proposed['thesis']}",
        title="[green]Thesis[/green]",
        border_style="green",
    ))
    console.print()

    t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    t.add_column("#", style="dim", width=3)
    t.add_column("Supporting Claim")
    for i, section in enumerate(proposed["sections"], 1):
        t.add_row(str(i), section["claim"])
    console.print(t)
    console.print()


def cmd_extract(
    input_path: str | None,
    *,
    from_stdin: bool = False,
    provider_name: str = "null",
    model: str | None = None,
    api_key: str | None = None,
    bundle_or_db: str | None = None,
    run_architect: bool = True,
) -> None:
    """Extract an Intent Hypothesis Blueprint from an existing document."""

    # ── Read input ─────────────────────────────────────────────────────────
    if from_stdin or input_path == "-":
        console.print("[dim]Reading from stdin… (Ctrl-D to finish)[/dim]")
        text = sys.stdin.read()
    elif input_path:
        p = Path(input_path)
        if not p.exists():
            console.print(f"[red]File not found:[/] {input_path}")
            sys.exit(1)
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        console.print("[red]Provide a file path or --stdin[/]")
        sys.exit(1)

    if not text.strip():
        console.print("[red]Input text is empty.[/]")
        sys.exit(1)

    console.print(f"\n[dim]Input: {len(text):,} characters[/dim]")

    # ── Extract ─────────────────────────────────────────────────────────────
    console.print(f"[dim]Provider: {provider_name}[/dim]")
    console.print("[cyan]Extracting Intent Hypothesis…[/cyan]")

    provider = _get_provider(provider_name, model, api_key)

    try:
        proposed = extract_blueprint_from_text(text, provider)
    except BlueprintExtractionError as exc:
        console.print(f"\n[red]Extraction failed:[/] {exc}")
        sys.exit(1)

    # ── Display proposal ─────────────────────────────────────────────────────
    _display_proposed_blueprint(proposed)

    console.print(
        Panel(
            "A wrong Blueprint is not a planning failure — it is a reading failure.\n"
            "Hermeneia's reconstruction may be imprecise. You are the authority.",
            border_style="yellow",
            title="[yellow]Ratification Required[/yellow]",
        )
    )
    console.print()

    if not Confirm.ask("Is this an accurate reconstruction of your intent?"):
        console.print("[dim]Blueprint discarded. Run again with a different provider or edit the input.[/dim]")
        sys.exit(0)

    # ── Store Blueprint ─────────────────────────────────────────────────────
    db_path, conn = _open_db(bundle_or_db)

    bp_id = make_blueprint_id(proposed["title"], proposed["thesis"], proposed["sections"])
    now = datetime.now(timezone.utc).isoformat()

    existing = conn.execute(
        "SELECT id FROM narrative_blueprints WHERE id = ?", (bp_id,)
    ).fetchone()

    if existing:
        console.print(f"\n[yellow]Blueprint already exists:[/] {bp_id[:16]}…")
    else:
        conn.execute(
            """
            INSERT INTO narrative_blueprints
                (id, title, thesis, sections, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                bp_id,
                proposed["title"],
                proposed["thesis"],
                json.dumps(proposed["sections"]),
                "extracted",
                now,
            ),
        )
        conn.commit()
        console.print(f"\n[green]Blueprint stored:[/] {bp_id[:16]}…")
        console.print(f"  Title:  {proposed['title']}")
        console.print(f"  Thesis: {proposed['thesis'][:80]}…" if len(proposed["thesis"]) > 80 else f"  Thesis: {proposed['thesis']}")

    # ── Run Architect ────────────────────────────────────────────────────────
    if run_architect:
        console.print("\n[cyan]Running Architect…[/cyan]")
        try:
            result = compile_architect_plan(bp_id, conn)

            from ..storage.sqlite import SQLiteStore
            store = SQLiteStore(db_path)
            store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])
            store.close()

            plan_id = result["plan_row"]["id"]
            n_terms = sum(
                len(json.loads(p["required_terms"]))
                for p in result["paragraph_rows"]
            )
            console.print(f"[green]Architect Plan ready:[/] {plan_id[:16]}…")
            console.print(f"  Paragraphs: {len(result['paragraph_rows'])}")
            console.print(f"  Obligations: {n_terms} semantic terms")
        except Exception as exc:
            console.print(f"[yellow]Architect warning:[/] {exc}")

    console.print()
    console.print(
        f"[bold green]Done.[/bold green] "
        f"Blueprint is live. Use [bold]herm artist[/bold] to render, "
        f"[bold]herm critic[/bold] to evaluate."
    )
    conn.close()
