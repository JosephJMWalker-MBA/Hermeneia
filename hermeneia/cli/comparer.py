"""
Comparison CLI — structural analysis of multiple interpretations of one Observation.

Command:
    compare <OBS-N>

What this does (and does NOT do):
  Does:     surface structural contradictions (evidential status conflict,
            divergent evidence sets, exclusive citations)
  Does NOT: judge which interpretation is correct
  Does NOT: use AI, embeddings, or semantic inference
  Does NOT: resolve the contradiction — that is the steward's job

The output is a map of the epistemic landscape, not a verdict.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box

console = Console()

_STATUS_RANK = {
    "established": 0,
    "contested": 1,
    "speculative": 2,
    "uncertain": 3,
}


# ── DB helpers ────────────────────────────────────────────────────────────────

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


# ── Analysis (deterministic, no AI) ──────────────────────────────────────────

def _analyze(interps: list[dict], id_to_index: dict[str, int]) -> dict:
    """Structural comparison of N interpretations.

    Returns a dict with:
      status_conflict   — True if interpretations disagree on evidential status
      statuses          — list of (perspective, status) pairs
      shared_evidence   — obs IDs present in ALL evidence sets
      exclusive         — per-interpretation: obs IDs cited only by that interpretation
      union_evidence    — all cited obs IDs across all interpretations
      divergence_score  — 0.0 (identical evidence) to 1.0 (completely disjoint)
    """
    evidence_sets: list[set[str]] = []
    for interp in interps:
        ids = json.loads(interp.get("evidence_observation_ids") or "[]")
        evidence_sets.append(set(ids))

    union: set[str] = set()
    for s in evidence_sets:
        union |= s

    shared: set[str] = union.copy()
    for s in evidence_sets:
        shared &= s

    exclusive: list[set[str]] = []
    for i, s in enumerate(evidence_sets):
        others = set()
        for j, other in enumerate(evidence_sets):
            if j != i:
                others |= other
        exclusive.append(s - others)

    statuses = [(interp["perspective"], interp["evidential_status"]) for interp in interps]
    unique_statuses = {s for _, s in statuses}
    status_conflict = len(unique_statuses) > 1

    divergence_score = 0.0
    if union:
        divergence_score = 1.0 - len(shared) / len(union)

    return {
        "status_conflict": status_conflict,
        "statuses": statuses,
        "unique_statuses": unique_statuses,
        "shared_evidence": shared,
        "exclusive": exclusive,
        "union_evidence": union,
        "divergence_score": divergence_score,
        "evidence_sets": evidence_sets,
    }


# ── cmd_compare ───────────────────────────────────────────────────────────────

def cmd_compare(obs_ref: str, bundle_or_db: str | None = None) -> None:
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

    console.print(Rule(f"[bold cyan]Compare: OBS-{n}[/]", style="cyan"))
    console.print(
        Panel(
            f'[italic]"{obs["normalized_text"]}"[/]',
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()

    # ── No interpretations ────────────────────────────────────────────────────
    if not interps:
        console.print(
            "[dim]No interpretations for this observation.\n"
            "Use 'herm interpret create OBS-N' to add one.[/]"
        )
        return

    # ── Single interpretation — nothing to compare ────────────────────────────
    if len(interps) == 1:
        interp = interps[0]
        console.print(
            Panel(
                f'[italic]"{interp["text"]}"[/]',
                title=f"[dim]Interpretation 1 — [bold]{interp['perspective']}[/][/dim]",
                border_style="green",
                padding=(0, 1),
            )
        )
        console.print(
            "\n[dim]Only one interpretation exists. Add more with "
            "'herm interpret create OBS-N' to enable comparison.[/]"
        )
        return

    # ── Multiple interpretations ──────────────────────────────────────────────
    analysis = _analyze(interps, id_to_index)

    console.print(Rule("[bold]Interpretations[/]", style="dim"))
    console.print()

    for i, interp in enumerate(interps, 1):
        excl = analysis["exclusive"][i - 1]
        excl_refs = sorted(
            f"OBS-{id_to_index[eid]}" for eid in excl if eid in id_to_index
        )
        evidence_ids = json.loads(interp.get("evidence_observation_ids") or "[]")
        evidence_refs = [
            f"OBS-{id_to_index[eid]}" for eid in evidence_ids if eid in id_to_index
        ]

        status_color = {
            "established": "green",
            "contested": "yellow",
            "speculative": "blue",
            "uncertain": "dim",
        }.get(interp["evidential_status"], "white")

        body = (
            f'[italic]"{interp["text"]}"[/]\n\n'
            f'[dim]Evidential status:[/] [{status_color}]{interp["evidential_status"]}[/]\n'
            f'[dim]Evidence:[/]         {" ".join(evidence_refs) or "(none)"}'
        )
        if excl_refs:
            body += f'\n[dim]Exclusive to this:[/] [yellow]{" ".join(excl_refs)}[/]'

        console.print(
            Panel(
                body,
                title=f"[dim]{i} — [bold]{interp['perspective']}[/][/dim]",
                border_style="green",
                padding=(0, 1),
            )
        )
        console.print()

    # ── Contradictions ────────────────────────────────────────────────────────
    console.print(Rule("[bold]Contradictions[/]", style="red"))
    console.print()

    if analysis["status_conflict"]:
        console.print("  [bold red]Evidential status conflict[/]")
        for perspective, status in analysis["statuses"]:
            color = {
                "established": "green", "contested": "yellow",
                "speculative": "blue",  "uncertain": "dim",
            }.get(status, "white")
            console.print(f"    [dim]{perspective}:[/] [{color}]{status}[/]")
        console.print()
        console.print(
            "  [dim]These interpretations make incompatible epistemic claims.\n"
            "  A steward must adjudicate which status is warranted.[/]"
        )
    else:
        status = next(iter(analysis["unique_statuses"]))
        console.print(f"  [dim]Evidential status:[/] no conflict — all [bold]{status}[/]")

    console.print()

    has_exclusive = any(bool(e) for e in analysis["exclusive"])
    if has_exclusive:
        console.print("  [bold yellow]Evidence divergence[/]")
        for i, (interp, excl) in enumerate(zip(interps, analysis["exclusive"]), 1):
            if excl:
                refs = sorted(
                    f"OBS-{id_to_index[eid]}" for eid in excl if eid in id_to_index
                )
                console.print(
                    f"    [dim]{i}. {interp['perspective']}:[/] "
                    f"[yellow]{' '.join(refs)}[/] cited here only"
                )
    else:
        console.print("  [dim]Evidence divergence:[/] none — identical evidence sets")

    # ── Agreement ─────────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]Agreement[/]", style="green"))
    console.print()

    shared = analysis["shared_evidence"]
    if shared:
        shared_refs = sorted(
            f"OBS-{id_to_index[eid]}" for eid in shared if eid in id_to_index
        )
        console.print(f"  [dim]Shared evidence ({len(shared_refs)}):[/]  " + "  ".join(
            f"[cyan]{r}[/]" for r in shared_refs
        ))
    else:
        console.print(
            "  [dim]Shared evidence:[/] [red]none[/]\n"
            "  [dim]These interpretations cite completely disjoint evidence.\n"
            "  They are structurally unrelated arguments.[/]"
        )

    score = analysis["divergence_score"]
    score_bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
    score_color = "green" if score < 0.3 else "yellow" if score < 0.7 else "red"
    console.print()
    console.print(
        f"  [dim]Divergence score:[/]  [{score_color}]{score_bar}[/]  "
        f"[bold]{score:.0%}[/]  [dim](0% = identical evidence, 100% = completely disjoint)[/]"
    )
    console.print()
