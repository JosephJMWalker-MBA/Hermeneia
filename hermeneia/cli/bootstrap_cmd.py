"""
herm bootstrap

Non-interactive pipeline bootstrap for the demo corpus (gatsby.pdf).

Creates the minimum viable epistemic chain needed to reach the first
provider render without any interactive prompts:

  Perspective → Interpretations → Blueprint → Architect Plan → [user runs artist]

All created objects are steward-authored (source='steward-authored') and
marked with source='bootstrap' in the notes field of the blueprint.

After running bootstrap, the next step is:

  scripts/herm artist OBS-23 --provider anthropic --profile literary-en

or any other configured provider.

Idempotent: running bootstrap twice is safe — all INSERT OR IGNORE.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.rule import Rule

console = Console()


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
    return p if (p.suffix == ".db" or p.name.endswith(".db")) else Path(default)


def _obs_id_by_n(conn: sqlite3.Connection, n: int) -> str | None:
    rows = conn.execute(
        "SELECT id FROM observations ORDER BY page, paragraph, sentence"
    ).fetchall()
    if n < 1 or n > len(rows):
        return None
    return rows[n - 1][0]


def _obs_n(conn: sqlite3.Connection, obs_id: str) -> int | None:
    rows = conn.execute(
        "SELECT id FROM observations ORDER BY page, paragraph, sentence"
    ).fetchall()
    for i, r in enumerate(rows, 1):
        if r[0] == obs_id:
            return i
    return None


# ── Bootstrap content ─────────────────────────────────────────────────────────
#
# Steward-authored interpretations for three key observations from gatsby.pdf.
# These are interpretations of the opening chapter's moral framing — chosen
# because they produce a coherent Blueprint with a clear thesis.
#
# Observation numbers are corpus-position references, not absolute IDs.
# The bootstrap resolves them at runtime.

BOOTSTRAP_PERSPECTIVE = {
    "name": "Literary",
    "description": (
        "Close reading of the text's rhetorical and moral architecture. "
        "Attends to the narrator's stance, the use of figurative language, "
        "and the structural logic of the argument."
    ),
}

BOOTSTRAP_INTERPRETATIONS: list[dict] = [
    {
        "obs_n": 19,    # p.4 §2: "fundamental decencies is parcelled out"
        "text": (
            "The narrator claims a quasi-aristocratic inheritance of moral clarity — "
            "a 'sense of the fundamental decencies' passed down like property. "
            "This establishes him as a moral observer rather than participant, "
            "positioning his tolerance as a virtue rather than a failure of judgment."
        ),
        "evidential_status": "established",
    },
    {
        "obs_n": 23,    # p.4 §3: "Only Gatsby... was exempt from my reaction"
        "text": (
            "Gatsby is explicitly carved out from the narrator's moral disillusionment. "
            "The exemption is not earned through virtue but through the quality of his "
            "aspiration — 'an extraordinary gift for hope.' This makes Gatsby not a moral "
            "exemplar but a category exception: someone whose meaning lies in what he "
            "reaches for, not what he does."
        ),
        "evidential_status": "established",
    },
    {
        "obs_n": 24,    # p.4 §3: "If personality is an unbroken series of successful gestures"
        "text": (
            "Fitzgerald frames personality as performed continuity — 'an unbroken series "
            "of successful gestures.' This is not admiration of authenticity but of "
            "sustained aesthetic coherence. Gatsby's 'gorgeous' quality is an artistic "
            "achievement: the maintenance of a fiction so complete it reads as reality."
        ),
        "evidential_status": "speculative",
    },
]

BOOTSTRAP_BLUEPRINT = {
    "title": "The Moral Architecture of The Great Gatsby",
    "thesis": (
        "Fitzgerald's narrator constructs a moral framework in Chapter 1 that positions "
        "Gatsby as a unique exception — exempt from the corruption that surrounds him "
        "not through virtue but through the quality of his aspiration, revealing the "
        "novel's central tension between romantic idealism and moral collapse."
    ),
    "sections": [
        {
            "claim": (
                "The narrator's moral authority rests on an inherited sensibility, "
                "not earned judgment — establishing him as observer rather than participant."
            ),
            "obs_ns": [19],
            "interp_ns": [0],   # index into BOOTSTRAP_INTERPRETATIONS
        },
        {
            "claim": (
                "Gatsby is exempt from the narrator's disillusionment because his aspiration "
                "is aesthetically coherent — personality as performed continuity, not moral achievement."
            ),
            "obs_ns": [23, 24],
            "interp_ns": [1, 2],
        },
    ],
    "source": "bootstrap",
}


def cmd_bootstrap(bundle_or_db: str | None = None) -> None:
    from ..storage.hashing import (
        make_blueprint_id,
        make_interpretation_id,
        make_perspective_id,
    )
    from ..storage.sqlite import ensure_profile_tables
    from ..cli.architect_cmd import cmd_architect

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_profile_tables(conn)

    console.print(Rule("[bold cyan]Bootstrap — First Provider Path[/]", style="cyan"))
    console.print()

    now = datetime.now(timezone.utc).isoformat()

    # ── 1. Validate observations exist ────────────────────────────────────────
    obs_ids: dict[int, str] = {}
    needed = {i["obs_n"] for i in BOOTSTRAP_INTERPRETATIONS}
    for section in BOOTSTRAP_BLUEPRINT["sections"]:
        for n in section["obs_ns"]:
            needed.add(n)

    for n in sorted(needed):
        oid = _obs_id_by_n(conn, n)
        if oid is None:
            console.print(
                f"[red]OBS-{n} not found in database.[/] "
                f"Is this the gatsby.pdf corpus? Run: herm stats build/hermeneia.db"
            )
            conn.close()
            sys.exit(1)
        obs_ids[n] = oid

    console.print(f"  [dim]Corpus validated:[/] OBS-{min(needed)}…OBS-{max(needed)} present")

    # ── 2. Perspective ────────────────────────────────────────────────────────
    persp_id = make_perspective_id(BOOTSTRAP_PERSPECTIVE["name"])
    conn.execute(
        "INSERT OR IGNORE INTO perspectives (id, name, description, created_at) VALUES (?, ?, ?, ?)",
        (persp_id, BOOTSTRAP_PERSPECTIVE["name"], BOOTSTRAP_PERSPECTIVE["description"], now),
    )
    conn.commit()
    existing_p = conn.execute("SELECT id FROM perspectives WHERE id = ?", (persp_id,)).fetchone()
    console.print(f"  [dim]Perspective:[/]  {BOOTSTRAP_PERSPECTIVE['name']} ({'existing' if existing_p else 'created'})")

    # ── 3. Interpretations ────────────────────────────────────────────────────
    created_interps: list[str] = []
    for spec in BOOTSTRAP_INTERPRETATIONS:
        obs_id = obs_ids[spec["obs_n"]]
        interp_id = make_interpretation_id(obs_id, BOOTSTRAP_PERSPECTIVE["name"], spec["text"])
        conn.execute(
            """
            INSERT OR IGNORE INTO interpretations
                (id, observation_id, perspective, perspective_id, text,
                 evidential_status, evidence_observation_ids,
                 confidence, source, ai_provenance_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, '[]', 'human', 'steward-authored', NULL, ?)
            """,
            (
                interp_id, obs_id, BOOTSTRAP_PERSPECTIVE["name"], persp_id,
                spec["text"], spec["evidential_status"], now,
            ),
        )
        conn.commit()
        created_interps.append(interp_id)
        console.print(
            f"  [dim]Interpretation OBS-{spec['obs_n']}:[/] "
            f"[{spec['evidential_status']}] {spec['text'][:60]}…"
        )

    # ── 4. Blueprint ──────────────────────────────────────────────────────────
    sections_data = []
    for sec_spec in BOOTSTRAP_BLUEPRINT["sections"]:
        obs_list = [obs_ids[n] for n in sec_spec["obs_ns"]]
        interp_list = [created_interps[i] for i in sec_spec["interp_ns"]]
        sections_data.append({
            "claim": sec_spec["claim"],
            "supporting_observations": obs_list,
            "supporting_interpretations": interp_list,
        })

    bp_id = make_blueprint_id(
        BOOTSTRAP_BLUEPRINT["title"],
        BOOTSTRAP_BLUEPRINT["thesis"],
        sections_data,
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO narrative_blueprints
            (id, title, thesis, sections, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            bp_id,
            BOOTSTRAP_BLUEPRINT["title"],
            BOOTSTRAP_BLUEPRINT["thesis"],
            json.dumps(sections_data),
            BOOTSTRAP_BLUEPRINT["source"],
            now,
        ),
    )
    conn.commit()

    # Blueprint observation links
    for sec in sections_data:
        for oid in sec["supporting_observations"]:
            conn.execute(
                "INSERT OR IGNORE INTO blueprint_observation_links (blueprint_id, observation_id) VALUES (?, ?)",
                (bp_id, oid),
            )
    # Blueprint interpretation links
    for sec in sections_data:
        for iid in sec["supporting_interpretations"]:
            conn.execute(
                "INSERT OR IGNORE INTO blueprint_interpretation_links (blueprint_id, interpretation_id) VALUES (?, ?)",
                (bp_id, iid),
            )
    conn.commit()
    console.print(f"\n  [dim]Blueprint:[/]    {BOOTSTRAP_BLUEPRINT['title']}")
    console.print(f"  [dim]  ID:[/]         {bp_id[:16]}…")
    conn.close()

    # ── 5. Architect Plan ─────────────────────────────────────────────────────
    console.print()
    console.print(f"  [dim]Compiling Architect Plan…[/]")
    # Use the first OBS-N linked to the blueprint as the entry point
    anchor_obs_n = BOOTSTRAP_BLUEPRINT["sections"][0]["obs_ns"][0]
    cmd_architect(f"OBS-{anchor_obs_n}", bundle_or_db=bundle_or_db)

    # ── 6. Next step ──────────────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold green]Bootstrap complete[/]", style="green"))
    console.print()
    console.print("  The pipeline is ready for the first provider render.")
    console.print()
    console.print("  [bold]Next step:[/]")
    console.print()
    console.print(
        f"    [cyan]ANTHROPIC_API_KEY=<your-key>[/] "
        f"[bold]python3 scripts/herm artist OBS-{anchor_obs_n} "
        f"--provider anthropic --profile literary-en[/]"
    )
    console.print()
    console.print("  Other providers:")
    console.print(f"    [dim]OPENAI_API_KEY=<key>  herm artist OBS-{anchor_obs_n} --provider openai  --profile literary-en[/]")
    console.print(f"    [dim]GEMINI_API_KEY=<key>  herm artist OBS-{anchor_obs_n} --provider gemini  --profile literary-en[/]")
    console.print(f"    [dim]XAI_API_KEY=<key>     herm artist OBS-{anchor_obs_n} --provider grok    --profile literary-en[/]")
    console.print()
    console.print("  [dim]Local (no key required):[/]")
    console.print(f"    [dim]herm artist OBS-{anchor_obs_n} --provider ollama-local --profile literary-en[/]")
    console.print()
