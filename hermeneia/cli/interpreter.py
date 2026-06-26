"""
Interpretation CLI — create and inspect steward-authored interpretations.

Commands:
    interpret view   <OBS-N>   — list all interpretations for an observation
    interpret create <OBS-N>   — interactive creation flow
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
from rich import box
from rich.table import Table

from ..storage.hashing import make_interpretation_id, make_perspective_id

console = Console()

_EVIDENTIAL_STATUSES = ["established", "contested", "speculative", "uncertain"]


# ── DB helpers (self-contained so interpreter.py has no import cycle) ─────────

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
        SELECT o.id, o.page, o.paragraph, o.sentence, o.raw_text,
               COALESCE(od.normalized_text, o.raw_text) AS normalized_text
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        ORDER BY o.page, o.paragraph, o.sentence
        """
    ).fetchall()
    if n < 1 or n > len(rows):
        return None
    return dict(rows[n - 1]) | {"obs_index": n, "total": len(rows)}


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
    """Resolve a list of 'OBS-N' strings to observation IDs. Skips invalid refs."""
    resolved = []
    for ref in refs:
        ref = ref.strip()
        if not ref:
            continue
        try:
            n = _parse_obs_ref(ref)
            if 1 <= n <= len(all_ids):
                resolved.append(all_ids[n - 1])
            else:
                console.print(f"  [yellow]Warning:[/] {ref} out of range, skipped")
        except ValueError:
            console.print(f"  [yellow]Warning:[/] '{ref}' is not a valid OBS-N ref, skipped")
    return resolved


# ── cmd_interpret_view ────────────────────────────────────────────────────────

def cmd_interpret_view(obs_ref: str, bundle_or_db: str | None = None) -> None:
    """Show the observation and all its interpretations. Offer to create if none exist."""
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    n = _parse_obs_ref(obs_ref)
    obs = _obs_by_index(conn, n)
    if not obs:
        total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        console.print(f"[red]OBS-{n} not found (total: {total})[/]")
        conn.close()
        return

    interps = conn.execute(
        "SELECT * FROM interpretations WHERE observation_id = ? ORDER BY created_at",
        (obs["id"],),
    ).fetchall()
    interps = [dict(r) for r in interps]

    all_ids = _all_ids_ordered(conn)
    id_to_index = {oid: i + 1 for i, oid in enumerate(all_ids)}
    conn.close()

    console.print(Rule(f"[bold cyan]OBS-{n}[/]  [dim]p.{obs['page']} · para {obs['paragraph']} · sent {obs['sentence']}[/]", style="cyan"))
    console.print(
        Panel(
            f'[italic]"{obs["normalized_text"]}"[/]',
            border_style="cyan",
            padding=(0, 1),
        )
    )

    console.print(f"\n[bold]Interpretations[/]  [dim]({len(interps)} total)[/]\n")

    if not interps:
        console.print("  [dim](none)[/]\n")
        if sys.stdout.isatty():
            if Confirm.ask("  Create one?", default=False):
                conn2 = _open_db(db_path)
                _run_create_flow(n, obs, conn2, id_to_index, all_ids)
                conn2.close()
    else:
        for i, interp in enumerate(interps, 1):
            _print_interpretation(i, interp, id_to_index)


# ── cmd_interpret_create ──────────────────────────────────────────────────────

def cmd_interpret_create(obs_ref: str, bundle_or_db: str | None = None) -> None:
    """Interactive flow: create a new steward-authored interpretation."""
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    n = _parse_obs_ref(obs_ref)
    obs = _obs_by_index(conn, n)
    if not obs:
        total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        console.print(f"[red]OBS-{n} not found (total: {total})[/]")
        conn.close()
        return

    all_ids = _all_ids_ordered(conn)
    id_to_index = {oid: i + 1 for i, oid in enumerate(all_ids)}

    _run_create_flow(n, obs, conn, id_to_index, all_ids)
    conn.close()


def _run_create_flow(
    n: int,
    obs: dict,
    conn: sqlite3.Connection,
    id_to_index: dict[str, int],
    all_ids: list[str],
) -> None:
    """Shared interactive creation flow used by both view (if user says yes) and create."""
    console.print(Rule(f"[bold cyan]New Interpretation — OBS-{n}[/]", style="cyan"))
    console.print(
        Panel(
            f'[italic]"{obs["normalized_text"]}"[/]',
            border_style="dim",
            padding=(0, 1),
        )
    )
    console.print()

    # ── Perspective ──
    perspective = ""
    while not perspective.strip():
        perspective = Prompt.ask("[bold]Perspective[/]")
        if not perspective.strip():
            console.print("  [red]Perspective cannot be blank.[/]")

    # ── Interpretation text ──
    console.print("\n[bold]Interpretation[/]  [dim](press Enter twice to finish)[/]")
    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    text = " ".join(l for l in lines if l.strip()).strip()

    if not text:
        console.print("[red]Interpretation text cannot be blank. Aborted.[/]")
        return

    # ── Evidential status ──
    console.print("\n[bold]Evidential status[/]")
    for i, s in enumerate(_EVIDENTIAL_STATUSES, 1):
        console.print(f"  [dim]{i}.[/] {s}")
    choice = ""
    while choice not in "1234" or not choice:
        choice = Prompt.ask("Choice", default="4")
    evidential_status = _EVIDENTIAL_STATUSES[int(choice) - 1]

    # ── Evidence ──
    console.print(
        "\n[bold]Evidence[/]  [dim](space-separated OBS-N refs, blank to skip)[/]"
    )
    raw_evidence = Prompt.ask("  Supports", default="")
    evidence_refs = [r.strip() for r in raw_evidence.split() if r.strip()]
    evidence_ids = _resolve_obs_refs(evidence_refs, all_ids)

    # Always include the primary observation in evidence if not already there
    if obs["id"] not in evidence_ids:
        evidence_ids = [obs["id"]] + evidence_ids

    # ── Register perspective (idempotent) ──
    persp_name = perspective.strip()
    persp_id = make_perspective_id(persp_name)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        "INSERT OR IGNORE INTO perspectives (id, name, description, created_at) VALUES (?, ?, ?, ?)",
        (persp_id, persp_name, "", now),
    )
    conn.commit()

    # ── Build and save interpretation ──
    interp_id = make_interpretation_id(obs["id"], persp_name, text)

    row = {
        "id": interp_id,
        "observation_id": obs["id"],
        "perspective": persp_name,
        "perspective_id": persp_id,
        "text": text,
        "evidential_status": evidential_status,
        "evidence_observation_ids": json.dumps(evidence_ids),
        "confidence": "human",
        "source": "steward-authored",
        "created_at": now,
    }

    existing = conn.execute(
        "SELECT id FROM interpretations WHERE id = ?", (interp_id,)
    ).fetchone()

    if existing:
        console.print(
            "\n[yellow]An identical interpretation already exists for this observation "
            "and perspective.[/] Nothing saved."
        )
        return

    conn.execute(
        """
        INSERT INTO interpretations
            (id, observation_id, perspective, perspective_id, text, evidential_status,
             evidence_observation_ids, confidence, source, created_at)
        VALUES
            (:id, :observation_id, :perspective, :perspective_id, :text, :evidential_status,
             :evidence_observation_ids, :confidence, :source, :created_at)
        """,
        row,
    )
    conn.commit()

    console.print(f"\n[bold green]✓ Saved[/]  [dim]ID: {interp_id[:16]}…[/]")
    console.print()

    id_to_index_fresh = {oid: i + 1 for i, oid in enumerate(all_ids)}
    _print_interpretation(1, row, id_to_index_fresh)


# ── shared rendering ──────────────────────────────────────────────────────────

def _print_interpretation(n: int, interp: dict, id_to_index: dict[str, int]) -> None:
    evidence_ids = json.loads(interp.get("evidence_observation_ids") or "[]")
    evidence_refs = []
    for eid in evidence_ids:
        idx = id_to_index.get(eid)
        evidence_refs.append(f"OBS-{idx}" if idx else eid[:12] + "…")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), expand=False)
    table.add_column("Field", style="dim", min_width=20)
    table.add_column("Value", style="bold")

    table.add_row("Perspective", interp["perspective"])
    table.add_row("Evidential status", interp["evidential_status"])
    table.add_row("Confidence", interp["confidence"].title())
    table.add_row("Source", interp["source"].title())
    table.add_row("Created", interp["created_at"][:19].replace("T", " ") + " UTC")
    if evidence_refs:
        table.add_row("Evidence", "  ".join(evidence_refs))

    console.print(
        Panel(
            f'[italic]"{interp["text"]}"[/]\n',
            title=f"[dim]Interpretation {n}[/]",
            border_style="green",
            padding=(0, 1),
        )
    )
    console.print(table)
