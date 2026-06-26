"""
herm theme list
herm theme view SLUG
herm theme create

Browse and create SystemPrompt themes.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
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


def cmd_theme_list(bundle_or_db: str | None = None) -> None:
    from ..storage.sqlite import ensure_artist_tables
    from ..narrative.themes import list_themes

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_artist_tables(conn)

    themes = list_themes(conn)
    conn.close()

    if not themes:
        console.print("[dim]No themes found.[/]")
        return

    console.print(Rule("[bold cyan]Themes[/]", style="cyan"))
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Slug")
    table.add_column("Name")
    table.add_column("Source")
    table.add_column("Focus (excerpt)")

    for t in themes:
        excerpt = t["focus"][:72] + "…" if len(t["focus"]) > 72 else t["focus"]
        source_label = "[dim]built-in[/]" if t["source"] == "built-in" else "[cyan]custom[/]"
        table.add_row(t["slug"], t["name"], source_label, f"[dim]{excerpt}[/]")

    console.print(table)
    console.print(f"\n[dim]{len(themes)} theme(s). Run [bold]herm theme view SLUG[/] for full details.[/]")


def cmd_theme_view(slug: str, bundle_or_db: str | None = None) -> None:
    from ..storage.sqlite import ensure_artist_tables
    from ..narrative.themes import get_theme

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_artist_tables(conn)

    theme = get_theme(slug, conn)
    conn.close()

    if theme is None:
        console.print(f"[red]Theme '{slug}' not found.[/] Run [bold]herm theme list[/] to see available themes.")
        sys.exit(1)

    console.print(Rule(f"[bold cyan]{theme['name']}[/]", style="cyan"))
    console.print(f"\n  [dim]Slug:[/]   {theme['slug']}")
    console.print(f"  [dim]Source:[/] {theme['source']}")
    console.print(f"  [dim]ID:[/]     {theme['id'][:16]}…\n")

    console.print(Panel(theme["focus"], title="[dim]Focus[/]", border_style="cyan"))
    console.print(Panel(theme["quality_criteria"], title="[dim]Quality bar[/]", border_style="dim"))
    console.print(f"\n[dim]Run Artist with this theme:[/] herm artist OBS-N --theme {theme['slug']}")


def cmd_theme_create(bundle_or_db: str | None = None) -> None:
    from ..storage.hashing import make_system_prompt_id
    from ..storage.sqlite import ensure_artist_tables

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_artist_tables(conn)

    console.print(Rule("[bold cyan]Create Theme[/]", style="cyan"))
    console.print("[dim]New themes shape how the Artist renders prose — same ArchitectPlan, different focus.[/]\n")

    slug = console.input("[cyan]Slug[/] (url-safe, e.g. 'marxist'): ").strip().lower().replace(" ", "-")
    if not slug:
        console.print("[red]Slug is required.[/]")
        conn.close(); sys.exit(1)

    existing = conn.execute("SELECT id FROM system_prompts WHERE slug = ?", (slug,)).fetchone()
    if existing:
        console.print(f"[red]A theme with slug '{slug}' already exists.[/]")
        conn.close(); sys.exit(1)

    name = console.input("[cyan]Name[/] (display name, e.g. 'Marxist'): ").strip()
    if not name:
        name = slug.capitalize()

    console.print("\n[dim]Focus — what should the Artist attend to?[/]")
    console.print("[dim](Describe the interpretive lens, evidence to foreground, register to use)[/]")
    focus = console.input("> ").strip()

    console.print("\n[dim]Quality bar — what does a good output look like?[/]")
    console.print("[dim](Name 2-3 criteria that distinguish excellent from adequate output)[/]")
    quality_criteria = console.input("> ").strip()

    if not focus or not quality_criteria:
        console.print("[red]Focus and quality bar are required.[/]")
        conn.close(); sys.exit(1)

    theme_id = make_system_prompt_id(slug)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO system_prompts (id, slug, name, focus, quality_criteria, source, created_at)
        VALUES (?, ?, ?, ?, ?, 'steward-authored', ?)
        """,
        (theme_id, slug, name, focus, quality_criteria, now),
    )
    conn.commit()
    conn.close()

    console.print(f"\n[green]✓  Theme '{name}' created.[/]")
    console.print(f"[dim]Run Artist with this theme:[/] herm artist OBS-N --theme {slug}")
