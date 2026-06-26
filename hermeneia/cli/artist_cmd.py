"""
herm artist OBS-N [--provider PROVIDER] [--model MODEL] [--profile SLUG] [--show-prompt] [--recursive]

Renders prose from the ArchitectPlan covering OBS-N's blueprint.

Providers:
  null        No LLM — returns placeholder (default)
  anthropic   Claude via Anthropic API  (ANTHROPIC_API_KEY)
  openai      GPT-4o via OpenAI API     (OPENAI_API_KEY)
  gemini      Gemini via Google API     (GEMINI_API_KEY)
  grok        Grok via xAI API          (XAI_API_KEY)
  ollama-meta Meta Llama via Ollama     (local service)
  ollama-local Configured local model   (local service)

An Expression Profile shapes how the Artist renders — same Architect Plan,
different expression. Each profile produces its own RenderedNarrative slot.

If a narrative already exists for this plan + provider + profile, displays it.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax

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
    return int(ref[4:]) if ref.startswith("OBS-") else int(ref)


def cmd_artist(
    obs_ref: str,
    provider_name: str = "null",
    theme_slug: str | None = None,
    show_prompt: bool = False,
    bundle_or_db: str | None = None,
    model: str | None = None,
    all_profiles: bool = False,
    recursive: bool = False,
) -> None:
    from ..narrative.artist_service import ArtistRenderError, render_for_observation
    from ..storage.sqlite import ensure_profile_tables as ensure_artist_tables

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_artist_tables(conn)

    if all_profiles:
        _cmd_artist_all_profiles(obs_ref, provider_name, model, conn)
        conn.close()
        return

    if recursive:
        console.print("[dim]Recursive protocol: Reconstruction → Draft → Self-Critique → Revision[/]")

    try:
        result = render_for_observation(
            obs_ref,
            conn,
            provider_name=provider_name,
            profile_slug=theme_slug,
            model=model,
            recursive=recursive,
        )
    except (ArtistRenderError, ImportError, ValueError) as e:
        console.print(f"[red]{e}[/]")
        conn.close()
        sys.exit(1)

    profile = result.profile
    profile_label = (
        f"[cyan]{profile['name']}[/] [{profile.get('language','en')}]"
        if profile
        else "[dim]none[/]"
    )
    n = _parse_obs_ref(obs_ref)
    console.print(Rule(f"[bold cyan]Artist: OBS-{n}[/]", style="cyan"))
    console.print(f'\n  Blueprint:        [bold]"{result.blueprint["title"]}"[/]')
    console.print(f"  Architect Plan:   [dim]{result.plan['id'][:16]}…[/]")
    console.print(f"  Provider:         [cyan]{provider_name}[/]")
    console.print(f"  Expression Profile: {profile_label}\n")

    if not result.created:
        console.print("[dim]  Narrative already exists (idempotent).[/]\n")
        _display_narrative(result.row, show_prompt)
        conn.close()
        return

    if show_prompt:
        console.print(Panel(
            Syntax(result.prompt, "text", theme="monokai", word_wrap=True),
            title="[dim]Generated Prompt (inspectable artifact)[/]",
            border_style="dim",
        ))
        console.print()

    console.print(f"  Rendering via [cyan]{result.row['provider']}[/]…\n")
    console.print("[green]✓  Narrative rendered and stored.[/]\n")
    _display_narrative(result.row, show_prompt=False)
    conn.close()


def _cmd_artist_all_profiles(
    obs_ref: str,
    provider_name: str,
    model: str | None,
    conn: sqlite3.Connection,
) -> None:
    """Render the same ArchitectPlan with every available Expression Profile."""
    from ..narrative.artist_service import ArtistRenderError, render_for_observation
    from ..narrative.profiles import list_profiles
    from rich.table import Table
    from rich import box

    profiles = list_profiles(conn)
    if not profiles:
        console.print("[red]No Expression Profiles found. Run [bold]herm bootstrap[/] first.[/]")
        return

    n = _parse_obs_ref(obs_ref)
    console.print(Rule(f"[bold cyan]Artist (all profiles): OBS-{n}[/]", style="cyan"))
    console.print(f"  Provider: [cyan]{provider_name}[/]  |  Profiles: {len(profiles)}\n")

    results_table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    results_table.add_column("Profile", style="cyan", min_width=18)
    results_table.add_column("Language", width=8)
    results_table.add_column("Status", width=10)
    results_table.add_column("Narrative ID", style="dim", width=20)

    for profile in profiles:
        slug = profile["slug"]
        lang = profile.get("language", "?")
        try:
            result = render_for_observation(
                obs_ref,
                conn,
                provider_name=provider_name,
                profile_slug=slug,
                model=model,
            )
            status = "[dim]exists[/]" if not result.created else "[green]created[/]"
            nid = result.row["id"][:16] + "…"
        except ArtistRenderError as exc:
            status = "[red]error[/]"
            nid = str(exc)[:20]
        results_table.add_row(slug, lang, status, nid)

    console.print(results_table)
    console.print(f"\n[green]Done.[/] {len(profiles)} profiles rendered for OBS-{n}.")


def _display_narrative(row: dict, show_prompt: bool = False) -> None:
    console.print(f"  [dim]Provider:[/]  {row['provider']}")
    console.print(f"  [dim]ID:[/]        {row['id'][:16]}…")
    console.print(f"  [dim]Created:[/]   {row['created_at'][:19].replace('T', ' ')} UTC\n")

    console.print(Panel(
        row["text"],
        title="[bold]Rendered Narrative[/]",
        border_style="cyan",
        padding=(1, 2),
    ))

    if show_prompt and row.get("prompt_used"):
        console.print(Panel(
            Syntax(row["prompt_used"], "text", theme="monokai", word_wrap=True),
            title="[dim]Prompt Used[/]",
            border_style="dim",
        ))
