"""
Blueprint CLI — create and inspect Narrative Blueprints.

Commands:
    blueprint view   <OBS-N>   — show all blueprints referencing this observation
    blueprint create           — interactive creation flow
    blueprint list             — list all blueprints

A Blueprint is pure structure: thesis + ordered sections, each with a claim,
evidence (Observation IDs), and interpretations (Interpretation IDs).
No prose. No style. No LLM.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich import box

from ..storage.hashing import make_blueprint_id

console = Console()


# ── DB helpers ────────────────────────────────────────────────────────────────

def _open_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        console.print(f"[red]Database not found:[/] {db_path}")
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
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


def _obs_by_index(conn: sqlite3.Connection, n: int) -> Optional[dict]:
    rows = conn.execute(
        """
        SELECT o.id, o.page, o.paragraph, o.sentence,
               COALESCE(od.normalized_text, o.raw_text) AS normalized_text
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        ORDER BY o.page, o.paragraph, o.sentence
        """
    ).fetchall()
    if n < 1 or n > len(rows):
        return None
    return dict(rows[n - 1]) | {"obs_index": n}


def _all_ids_ordered(conn: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]


def _parse_obs_ref(ref: str) -> int:
    ref = ref.upper().strip()
    return int(ref[4:]) if ref.startswith("OBS-") else int(ref)


def _resolve_obs_refs(refs: list[str], all_ids: list[str]) -> list[str]:
    resolved = []
    for ref in refs:
        try:
            n = _parse_obs_ref(ref)
            if 1 <= n <= len(all_ids):
                resolved.append(all_ids[n - 1])
            else:
                console.print(f"  [yellow]Warning:[/] {ref} out of range, skipped")
        except ValueError:
            console.print(f"  [yellow]Warning:[/] '{ref}' is not a valid OBS-N ref, skipped")
    return resolved


# ── cmd_blueprint_view ────────────────────────────────────────────────────────

def cmd_blueprint_view(obs_ref: str, bundle_or_db: str | None = None) -> None:
    """Show all blueprints that reference this observation, with the full chain."""
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    n = _parse_obs_ref(obs_ref)
    obs = _obs_by_index(conn, n)
    if not obs:
        total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        console.print(f"[red]OBS-{n} not found (total: {total})[/]")
        conn.close()
        return

    blueprints = conn.execute(
        """
        SELECT nb.* FROM narrative_blueprints nb
        JOIN blueprint_observation_links bol ON bol.blueprint_id = nb.id
        WHERE bol.observation_id = ?
        ORDER BY nb.created_at
        """,
        (obs["id"],),
    ).fetchall()
    blueprints = [dict(r) for r in blueprints]

    all_ids = _all_ids_ordered(conn)
    id_to_index = {oid: i + 1 for i, oid in enumerate(all_ids)}

    console.print(Rule(f"[bold cyan]Blueprints referencing OBS-{n}[/]", style="cyan"))
    console.print(
        Panel(
            f'[italic]"{obs["normalized_text"]}"[/]',
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()

    if not blueprints:
        console.print(
            "[dim]No blueprints reference this observation.\n"
            "Use 'herm blueprint create' to build one.[/]"
        )
        conn.close()
        return

    for bp in blueprints:
        _print_blueprint_chain(bp, obs["id"], id_to_index, conn)

    conn.close()


# ── cmd_blueprint_list ────────────────────────────────────────────────────────

def cmd_blueprint_list(bundle_or_db: str | None = None) -> None:
    """List all blueprints with title, thesis preview, and section count."""
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    blueprints = conn.execute(
        "SELECT * FROM narrative_blueprints ORDER BY created_at"
    ).fetchall()
    blueprints = [dict(r) for r in blueprints]
    conn.close()

    console.print(Rule(f"[bold cyan]Narrative Blueprints[/]  [dim]({len(blueprints)} total)[/]", style="cyan"))
    console.print()

    if not blueprints:
        console.print("[dim]None yet. Use 'herm blueprint create' to build one.[/]")
        return

    for i, bp in enumerate(blueprints, 1):
        sections = json.loads(bp["sections"])
        console.print(f"[bold]{i}.[/]  [cyan]{bp['title']}[/]")
        console.print(f"     [dim]Thesis:[/] {bp['thesis'][:80]}{'…' if len(bp['thesis']) > 80 else ''}")
        console.print(f"     [dim]Sections:[/] {len(sections)}  [dim]ID:[/] {bp['id'][:12]}…")
        console.print(f"     [dim]Created:[/] {bp['created_at'][:19].replace('T', ' ')} UTC")
        console.print()


# ── cmd_blueprint_create ──────────────────────────────────────────────────────

def cmd_blueprint_create(bundle_or_db: str | None = None) -> None:
    """Interactive creation flow for a Narrative Blueprint."""
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    all_ids = _all_ids_ordered(conn)
    id_to_index = {oid: i + 1 for i, oid in enumerate(all_ids)}

    console.print(Rule("[bold cyan]New Narrative Blueprint[/]", style="cyan"))
    console.print("[dim]No prose. No style. Pure structure.[/]\n")

    # ── Title ──
    title = ""
    while not title.strip():
        title = Prompt.ask("[bold]Title[/]")
        if not title.strip():
            console.print("  [red]Title cannot be blank.[/]")

    # ── Thesis ──
    console.print("\n[bold]Thesis[/]  [dim](the single claim this blueprint defends)[/]")
    thesis = ""
    while not thesis.strip():
        thesis = Prompt.ask("Thesis")
        if not thesis.strip():
            console.print("  [red]Thesis cannot be blank.[/]")

    # ── Sections ──
    sections: list[dict] = []
    console.print()

    while True:
        section_n = len(sections) + 1
        console.print(Rule(f"[dim]Section {section_n}[/]", style="dim"))

        # Claim
        console.print(
            "  [dim]A claim states a specific relational proposition — not a topic or label.[/]\n"
            "  [dim]Prefer: 'Fitzgerald uses X to show that Y' over 'X represents Y'.[/]"
        )
        claim = ""
        while not claim.strip():
            claim = Prompt.ask("  [bold]Claim[/]")
            if not claim.strip():
                console.print("  [red]Claim cannot be blank.[/]")

        # Supporting observations
        console.print("  [bold]Supporting observations[/]  [dim](space-separated OBS-N refs)[/]")
        raw_obs = Prompt.ask("  Observations", default="")
        obs_refs = [r.strip() for r in raw_obs.split() if r.strip()]
        section_obs_ids = _resolve_obs_refs(obs_refs, all_ids)

        # Show available interpretations for those observations
        interp_ids: list[str] = []
        if section_obs_ids:
            available_interps = _fetch_interpretations_for_obs(conn, section_obs_ids)
            if available_interps:
                console.print(
                    f"\n  [bold]Available interpretations[/]  "
                    f"[dim]({len(available_interps)} across these observations)[/]"
                )
                for i, interp in enumerate(available_interps, 1):
                    obs_idx = id_to_index.get(interp["observation_id"], "?")
                    preview = interp["text"][:60] + ("…" if len(interp["text"]) > 60 else "")
                    console.print(
                        f"    [dim]{i}.[/] [cyan]{interp['perspective']}[/] "
                        f"[dim](OBS-{obs_idx}):[/] {preview}"
                    )
                raw_interps = Prompt.ask(
                    "\n  Select interpretations [dim](numbers, space-separated, blank to skip)[/]",
                    default="",
                )
                chosen = [r.strip() for r in raw_interps.split() if r.strip()]
                for c in chosen:
                    try:
                        idx = int(c) - 1
                        if 0 <= idx < len(available_interps):
                            interp_ids.append(available_interps[idx]["id"])
                        else:
                            console.print(f"  [yellow]Warning:[/] {c} out of range, skipped")
                    except ValueError:
                        console.print(f"  [yellow]Warning:[/] '{c}' is not a number, skipped")
            else:
                console.print("  [dim](no interpretations exist for these observations yet)[/]")

        sections.append({
            "claim": claim.strip(),
            "supporting_observations": section_obs_ids,
            "supporting_interpretations": interp_ids,
        })

        console.print()
        if not Confirm.ask("  Add another section?", default=False):
            break

    # ── Build and save ──
    bp_id = make_blueprint_id(title.strip(), thesis.strip(), sections)
    now = datetime.now(timezone.utc).isoformat()

    existing = conn.execute(
        "SELECT id FROM narrative_blueprints WHERE id = ?", (bp_id,)
    ).fetchone()
    if existing:
        console.print("\n[yellow]An identical blueprint already exists.[/] Nothing saved.")
        conn.close()
        return

    # Flatten all cited IDs for link tables
    all_obs_ids = list({oid for s in sections for oid in s["supporting_observations"]})
    all_interp_ids = list({iid for s in sections for iid in s["supporting_interpretations"]})

    conn.execute(
        """
        INSERT INTO narrative_blueprints (id, title, thesis, sections, source, created_at)
        VALUES (?, ?, ?, ?, 'steward-authored', ?)
        """,
        (bp_id, title.strip(), thesis.strip(), json.dumps(sections), now),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO blueprint_observation_links (blueprint_id, observation_id) VALUES (?, ?)",
        [(bp_id, oid) for oid in all_obs_ids],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO blueprint_interpretation_links (blueprint_id, interpretation_id) VALUES (?, ?)",
        [(bp_id, iid) for iid in all_interp_ids],
    )
    conn.commit()
    conn.close()

    console.print(f"\n[bold green]✓ Blueprint saved[/]  [dim]ID: {bp_id[:16]}…[/]")
    console.print(f"  [dim]{len(sections)} section(s), {len(all_obs_ids)} observation(s), {len(all_interp_ids)} interpretation(s)[/]")


# ── shared rendering ──────────────────────────────────────────────────────────

def _fetch_interpretations_for_obs(
    conn: sqlite3.Connection, obs_ids: list[str]
) -> list[dict]:
    placeholders = ",".join("?" * len(obs_ids))
    cur = conn.execute(
        f"SELECT id, observation_id, perspective, text FROM interpretations "
        f"WHERE observation_id IN ({placeholders}) ORDER BY perspective",
        obs_ids,
    )
    return [dict(r) for r in cur.fetchall()]


def _print_blueprint_chain(
    bp: dict,
    target_obs_id: str,
    id_to_index: dict[str, int],
    conn: sqlite3.Connection,
) -> None:
    """Print a blueprint as a chain: Thesis → Sections → Interpretations → Observations."""
    sections = json.loads(bp["sections"])

    console.print(
        Panel(
            f"[bold]{bp['title']}[/]",
            border_style="cyan",
            padding=(0, 1),
        )
    )

    # ── Thesis ──
    console.print(f"\n[bold cyan]Thesis[/]")
    console.print(
        Panel(
            f'[italic]"{bp["thesis"]}"[/]',
            border_style="green",
            padding=(0, 1),
        )
    )

    for sec_idx, section in enumerate(sections, 1):
        obs_ids: list[str] = section.get("supporting_observations", [])
        interp_ids: list[str] = section.get("supporting_interpretations", [])

        # Mark which sections contain the target observation
        contains_target = target_obs_id in obs_ids
        section_style = "bold green" if contains_target else "bold"
        target_marker = "  [dim cyan]◀ this observation[/]" if contains_target else ""

        console.print(f"\n[dim]↓[/]\n")
        console.print(f"[{section_style}]Section {sec_idx}[/]{target_marker}")
        console.print(
            Panel(
                f'[italic]"{section["claim"]}"[/]',
                border_style="green" if contains_target else "dim",
                padding=(0, 1),
            )
        )

        # Interpretations cited in this section
        if interp_ids:
            interps = conn.execute(
                f"SELECT id, perspective, evidential_status, text FROM interpretations "
                f"WHERE id IN ({','.join('?' * len(interp_ids))})",
                interp_ids,
            ).fetchall()
            console.print(f"\n  [dim]↓[/]  [bold]Interpretations[/]  [dim]({len(interps)})[/]")
            for interp in interps:
                console.print(
                    f"  [cyan]{interp['perspective']}[/]  "
                    f"[dim]{interp['evidential_status']}[/]  "
                    f"[italic]\"{interp['text'][:70]}{'…' if len(interp['text']) > 70 else ''}\"[/]"
                )

        # Observations cited in this section
        if obs_ids:
            obs_rows = conn.execute(
                f"""
                SELECT o.id, o.page, o.paragraph, o.sentence,
                       COALESCE(od.normalized_text, o.raw_text) AS normalized_text
                FROM observations o
                LEFT JOIN observation_derived od ON od.observation_id = o.id
                WHERE o.id IN ({','.join('?' * len(obs_ids))})
                """,
                obs_ids,
            ).fetchall()
            console.print(f"\n  [dim]↓[/]  [bold]Evidence[/]  [dim]({len(obs_rows)} observations)[/]")
            for obs_row in obs_rows:
                idx = id_to_index.get(obs_row["id"], "?")
                is_target = obs_row["id"] == target_obs_id
                label = "[bold cyan]▶[/] " if is_target else "  "
                console.print(
                    f"  {label}[bold]OBS-{idx}[/]  "
                    f"[dim]p.{obs_row['page']} · para {obs_row['paragraph']} · sent {obs_row['sentence']}[/]"
                )
                preview = obs_row["normalized_text"][:90]
                if len(obs_row["normalized_text"]) > 90:
                    preview += "…"
                console.print(f"       [italic]\"{preview}\"[/]")

    console.print()
    console.print(
        f"  [dim]Blueprint ID: {bp['id'][:16]}…  "
        f"Created: {bp['created_at'][:19].replace('T', ' ')} UTC[/]"
    )
    console.print()
