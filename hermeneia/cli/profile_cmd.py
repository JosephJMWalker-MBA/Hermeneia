"""
herm profile list
herm profile view SLUG
herm profile create

Browse and create ExpressionProfiles.

An ExpressionProfile is not a presentation style — it is a philosophy of
communication. The same Architect Plan can be expressed through Literary,
Historical, Psychoanalytic, or any other profile. Language is just another
profile dimension: literary-sw produces Swahili literary criticism from the
same semantic commitments as literary-en.
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


def cmd_profile_list(bundle_or_db: str | None = None) -> None:
    from ..storage.sqlite import ensure_profile_tables
    from ..narrative.profiles import list_profiles

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_profile_tables(conn)

    profiles = list_profiles(conn)
    conn.close()

    if not profiles:
        console.print("[dim]No expression profiles found.[/]")
        return

    console.print(Rule("[bold cyan]Expression Profiles[/]", style="cyan"))
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Slug")
    table.add_column("Name")
    table.add_column("Lang")
    table.add_column("Audience")
    table.add_column("Source")

    for p in profiles:
        source_label = "[dim]built-in[/]" if p["source"] == "built-in" else "[cyan]custom[/]"
        table.add_row(
            p["slug"], p["name"], p.get("language", "en"),
            p.get("audience") or "—", source_label,
        )

    console.print(table)
    console.print(f"\n[dim]{len(profiles)} profile(s). Run [bold]herm profile view SLUG[/] for full details.[/]")


def cmd_profile_view(slug: str, bundle_or_db: str | None = None) -> None:
    from ..storage.sqlite import ensure_profile_tables
    from ..narrative.profiles import get_profile

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_profile_tables(conn)

    profile = get_profile(slug, conn)
    conn.close()

    if profile is None:
        console.print(f"[red]Profile '{slug}' not found.[/] Run [bold]herm profile list[/].")
        sys.exit(1)

    console.print(Rule(f"[bold cyan]{profile['name']}[/]", style="cyan"))
    console.print(f"\n  [dim]Slug:[/]          {profile['slug']}")
    console.print(f"  [dim]Language:[/]      {profile.get('language', 'en')}")
    if profile.get("audience"):
        console.print(f"  [dim]Audience:[/]      {profile['audience']}")
    if profile.get("reading_level"):
        console.print(f"  [dim]Reading level:[/] {profile['reading_level']}")
    if profile.get("tone"):
        console.print(f"  [dim]Tone:[/]          {profile['tone']}")
    if profile.get("voice"):
        console.print(f"  [dim]Voice:[/]         {profile['voice']}")
    console.print(f"  [dim]Source:[/]        {profile['source']}")
    console.print(f"  [dim]ID:[/]            {profile['id'][:16]}…\n")

    if profile.get("description"):
        console.print(Panel(profile["description"], title="[dim]Description[/]", border_style="dim"))

    console.print(Panel(profile["artist_prompt"], title="[dim]Artist directive[/]", border_style="cyan"))

    if profile.get("critic_expectations"):
        console.print(Panel(profile["critic_expectations"], title="[dim]Critic expectations[/]", border_style="dim"))

    console.print(f"\n[dim]Run Artist with this profile:[/] herm artist OBS-N --profile {profile['slug']}")


def cmd_profile_create(bundle_or_db: str | None = None) -> None:
    from ..storage.hashing import make_expression_profile_id
    from ..storage.sqlite import ensure_profile_tables

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_profile_tables(conn)

    console.print(Rule("[bold cyan]Create Expression Profile[/]", style="cyan"))
    console.print("[dim]An Expression Profile is a philosophy of communication — not a style.\n"
                  "The Architect Plan remains invariant. Only the Artist changes.[/]\n")

    slug = console.input("[cyan]Slug[/] (e.g. 'childrens-en', 'legal-sw'): ").strip().lower().replace(" ", "-")
    if not slug:
        console.print("[red]Slug is required.[/]")
        conn.close(); sys.exit(1)

    existing = conn.execute("SELECT id FROM expression_profiles WHERE slug = ?", (slug,)).fetchone()
    if existing:
        console.print(f"[red]A profile with slug '{slug}' already exists.[/]")
        conn.close(); sys.exit(1)

    name   = console.input("[cyan]Name[/] (display name, e.g. \"Children's\"): ").strip() or slug.split("-")[0].capitalize()
    desc   = console.input("[cyan]Description[/] (one line, optional): ").strip() or None
    lang   = console.input("[cyan]Language[/] (ISO code, default 'en'): ").strip() or "en"
    audience  = console.input("[cyan]Audience[/] (optional, e.g. 'children', 'executives'): ").strip() or None
    reading_level = console.input("[cyan]Reading level[/] (optional, e.g. 'grade 4'): ").strip() or None
    tone   = console.input("[cyan]Tone[/] (optional, e.g. 'accessible', 'formal'): ").strip() or None
    voice  = console.input("[cyan]Voice[/] (optional, e.g. 'narrative', 'third-person'): ").strip() or None

    console.print("\n[dim]Artist directive — what should the Artist attend to and how should they write?[/]")
    artist_prompt = console.input("> ").strip()
    if not artist_prompt:
        console.print("[red]Artist directive is required.[/]")
        conn.close(); sys.exit(1)

    console.print("\n[dim]Critic expectations — what makes a good output? (optional)[/]")
    critic_expectations = console.input("> ").strip() or None

    profile_id = make_expression_profile_id(slug)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO expression_profiles
            (id, slug, name, description, language, audience, reading_level,
             tone, voice, artist_prompt, critic_expectations, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'steward-authored', ?)
        """,
        (profile_id, slug, name, desc, lang, audience, reading_level,
         tone, voice, artist_prompt, critic_expectations, now),
    )
    conn.commit()
    conn.close()

    console.print(f"\n[green]✓  Expression profile '{name}' created.[/]")
    console.print(f"[dim]Run Artist with this profile:[/] herm artist OBS-N --profile {slug}")
