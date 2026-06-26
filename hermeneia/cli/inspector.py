"""
Hermeneia inspection CLI — the compiler's debugger.

Commands:
    stats      <bundle_dir>          — corpus summary
    search     <query>               — full-text search in observations
    neighbors  <OBS-N>               — adjacency chain
    provenance <OBS-N>               — full provenance record
    concept    <term>                — Field v0.1: all observations containing term
    trace      <OBS-N>               — pipeline trace (shows unfilled layers)

OBS-N references the Nth observation ordered by (page, paragraph, sentence).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box

console = Console()


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
        SELECT o.id, o.page, o.paragraph, o.sentence, o.raw_text,
               COALESCE(od.normalized_text, o.raw_text) AS normalized_text,
               o.preceding_observation_id, o.following_observation_id
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        ORDER BY o.page, o.paragraph, o.sentence
        """
    ).fetchall()
    if n < 1 or n > len(rows):
        return None
    row = rows[n - 1]
    return dict(row) | {"obs_index": n, "total": len(rows)}


def _all_ids(conn: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]


def _parse_obs_ref(ref: str) -> int:
    ref = ref.upper().strip()
    if ref.startswith("OBS-"):
        return int(ref[4:])
    return int(ref)


# ── stats ─────────────────────────────────────────────────────────────────────

def cmd_stats(bundle_or_db: str) -> None:
    db_path = _resolve_db(bundle_or_db)

    manifest: dict = {}
    p = Path(bundle_or_db)
    if p.is_dir() and p.name.endswith(".herm"):
        mf = p / "manifest.json"
        if mf.exists():
            manifest = json.loads(mf.read_text())

    conn = _open_db(db_path)

    doc = conn.execute("SELECT * FROM source_documents LIMIT 1").fetchone()
    if not doc:
        console.print("[red]No source document registered.[/]")
        conn.close()
        return
    doc = dict(doc)

    total_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    total_pages = conn.execute("SELECT MAX(page) FROM observations").fetchone()[0] or 0
    total_paras = conn.execute(
        "SELECT COUNT(DISTINCT page || '_' || paragraph) FROM observations"
    ).fetchone()[0]

    texts = conn.execute(
        """
        SELECT COALESCE(od.normalized_text, o.raw_text) AS normalized_text
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        """
    ).fetchall()
    word_counts = [len(r[0].split()) for r in texts]
    mean_words = sum(word_counts) / len(word_counts) if word_counts else 0.0

    total_terms = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]

    prov_sample = conn.execute("SELECT compiler_version FROM provenance LIMIT 1").fetchone()
    compiler_version = prov_sample[0] if prov_sample else doc.get("compiler_version", "—")

    conn.close()

    title = doc["original_filename"].replace(".pdf", "").replace("_", " ").title()
    console.print(Rule(f"[bold cyan]{title}[/]", style="cyan"))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Pages", f"{total_pages:,}")
    table.add_row("Paragraphs", f"{total_paras:,}")
    table.add_row("Observations", f"{total_obs:,}")
    table.add_row("Mean sentence length", f"{mean_words:.1f} words")
    table.add_row("", "")
    table.add_row("Field v0.1 terms", f"{total_terms:,}")
    table.add_row("", "")
    table.add_row("Source document", doc["original_filename"])
    table.add_row("SHA-256", doc["file_hash"][:16] + "…" + doc["file_hash"][-8:])
    table.add_row("Compiler version", compiler_version)
    table.add_row("Registered", doc["registered_at"][:19].replace("T", " ") + " UTC")

    if manifest:
        table.add_row("", "")
        table.add_row("ADR schema", manifest.get("schema", "—"))
        table.add_row("Compilation run", manifest.get("compilation_run_id", "—")[:8] + "…")

    console.print(table)


# ── search ────────────────────────────────────────────────────────────────────

def cmd_search(query: str, bundle_or_db: str | None = None, limit: int = 10) -> None:
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    all_rows = conn.execute(
        """
        SELECT o.id, o.page, o.paragraph, o.sentence, o.raw_text,
               COALESCE(od.normalized_text, o.raw_text) AS normalized_text
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        ORDER BY o.page, o.paragraph, o.sentence
        """
    ).fetchall()

    id_to_index: dict[str, int] = {r["id"]: i + 1 for i, r in enumerate(all_rows)}
    q_lower = query.lower()

    matches = [
        (id_to_index[r["id"]], dict(r))
        for r in all_rows
        if q_lower in r["normalized_text"].lower()
    ]

    conn.close()

    console.print(Rule(f'[bold cyan]Search: "{query}"[/] — {len(matches)} matches', style="cyan"))

    if not matches:
        console.print("[dim]No observations contain this text.[/]")
        return

    for obs_idx, obs in matches[:limit]:
        _print_observation(obs_idx, obs, highlight=query)

    if len(matches) > limit:
        console.print(f"[dim]  … {len(matches) - limit} more matches[/]")


# ── concept ───────────────────────────────────────────────────────────────────

def cmd_concept(term: str, bundle_or_db: str | None = None, limit: int = 20) -> None:
    """Field v0.1: show all observations that contain the given term (exact token)."""
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    # Get all IDs in order for index mapping
    all_ids = _all_ids(conn)
    id_to_index = {oid: i + 1 for i, oid in enumerate(all_ids)}

    # Look up term in index
    term_lower = term.lower().strip("'")
    cur = conn.execute(
        """
        SELECT o.id, o.page, o.paragraph, o.sentence, o.raw_text,
               COALESCE(od.normalized_text, o.raw_text) AS normalized_text,
               o.preceding_observation_id, o.following_observation_id
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        JOIN observation_terms ot ON ot.observation_id = o.id
        JOIN terms t ON t.id = ot.term_id
        WHERE t.term = ?
        ORDER BY o.page, o.paragraph, o.sentence
        """,
        (term_lower,),
    )
    rows = cur.fetchall()
    conn.close()

    console.print(Rule(
        f'[bold cyan]Concept: "{term_lower}"[/] — {len(rows)} observations',
        style="cyan",
    ))

    if not rows:
        console.print(f"[dim]Term '{term_lower}' not found in index.[/]")
        console.print("[dim]Tip: terms are 3+ character alphabetic tokens.[/]")
        return

    for row in rows[:limit]:
        obs = dict(row)
        idx = id_to_index.get(obs["id"], 0)
        _print_observation(idx, obs, highlight=term)

    if len(rows) > limit:
        console.print(f"[dim]  … {len(rows) - limit} more (use --limit to see more)[/]")


# ── neighbors ─────────────────────────────────────────────────────────────────

def cmd_neighbors(obs_ref: str, bundle_or_db: str | None = None) -> None:
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    n = _parse_obs_ref(obs_ref)
    obs = _obs_by_index(conn, n)
    if not obs:
        total = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        console.print(f"[red]OBS-{n} not found (total: {total})[/]")
        conn.close()
        return

    all_ids = _all_ids(conn)
    id_to_index = {oid: i + 1 for i, oid in enumerate(all_ids)}

    def _fetch(obs_id: str) -> tuple[int, dict] | None:
        row = conn.execute(
            """
            SELECT o.id, o.page, o.paragraph, o.sentence, o.raw_text,
                   COALESCE(od.normalized_text, o.raw_text) AS normalized_text,
                   o.preceding_observation_id, o.following_observation_id
            FROM observations o
            LEFT JOIN observation_derived od ON od.observation_id = o.id
            WHERE o.id = ?
            """,
            (obs_id,),
        ).fetchone()
        if not row:
            return None
        return id_to_index.get(obs_id, 0), dict(row)

    prev = _fetch(obs["preceding_observation_id"]) if obs["preceding_observation_id"] else None
    nxt = _fetch(obs["following_observation_id"]) if obs["following_observation_id"] else None

    conn.close()

    console.print(Rule(f"[bold cyan]Neighbors of OBS-{n}[/]", style="cyan"))

    if prev:
        _print_observation(prev[0], prev[1], dim=True, label="↑ Preceding")
    else:
        console.print("[dim]  ↑ (first observation — no preceding)[/]\n")

    _print_observation(n, obs, label="⦿ Target")

    if nxt:
        _print_observation(nxt[0], nxt[1], dim=True, label="↓ Following")
    else:
        console.print("[dim]  ↓ (last observation — no following)[/]\n")


# ── provenance ────────────────────────────────────────────────────────────────

def cmd_provenance(obs_ref: str, bundle_or_db: str | None = None) -> None:
    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)

    n = _parse_obs_ref(obs_ref)
    obs = _obs_by_index(conn, n)
    if not obs:
        console.print(f"[red]OBS-{n} not found.[/]")
        conn.close()
        return

    prov = conn.execute(
        "SELECT * FROM provenance WHERE observation_id = ?", (obs["id"],)
    ).fetchone()

    if not prov:
        console.print(f"[red]No provenance record for OBS-{n}.[/]")
        conn.close()
        return
    prov = dict(prov)

    doc = conn.execute(
        "SELECT * FROM source_documents WHERE id = ?", (prov["source_document_id"],)
    ).fetchone()
    doc = dict(doc) if doc else {}

    conn.close()

    console.print(Rule(f"[bold cyan]Provenance: OBS-{n}[/]", style="cyan"))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Field", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Observation ID", prov["observation_id"])
    table.add_row("", "")
    table.add_row("Source document", doc.get("original_filename", "—"))
    table.add_row("Document hash (SHA-256)", prov["source_document_hash"])
    table.add_row("", "")
    table.add_row("Page", str(prov["page"]))
    table.add_row("Paragraph", str(prov["paragraph"]))
    table.add_row("Sentence", str(prov["sentence"]))
    table.add_row("Location precision", prov["location_precision"])
    table.add_row("", "")
    table.add_row("Bounding box X", _fmt_opt(prov.get("bbox_x")))
    table.add_row("Bounding box Y", _fmt_opt(prov.get("bbox_y")))
    table.add_row("Bounding box W", _fmt_opt(prov.get("bbox_width")))
    table.add_row("Bounding box H", _fmt_opt(prov.get("bbox_height")))
    table.add_row("", "")
    table.add_row("Compiler version", prov["compiler_version"])
    table.add_row("Compilation run", prov["compilation_run_id"])
    table.add_row("Created at", prov["created_at"][:19].replace("T", " ") + " UTC")

    console.print(table)

    # Show both forms
    console.print(
        Panel(
            f'[dim]raw:[/]        [italic]"{obs["raw_text"]}"[/]\n'
            f'[dim]normalized:[/] [italic]"{obs["normalized_text"]}"[/]',
            title="[dim]text forms[/]",
            border_style="dim",
        )
    )


# ── trace ─────────────────────────────────────────────────────────────────────

def cmd_trace(obs_ref: str, bundle_or_db: str | None = None) -> None:
    """Show the full pipeline trace for an observation.

    Layers that don't yet exist are shown as '(not yet generated)'.
    As later pipeline stages are implemented, this fills in automatically.
    """
    from ..storage.sqlite import ensure_architect_tables

    db_path = _resolve_db(bundle_or_db)
    conn = _open_db(db_path)
    ensure_architect_tables(conn)

    n = _parse_obs_ref(obs_ref)
    obs = _obs_by_index(conn, n)
    if not obs:
        console.print(f"[red]OBS-{n} not found.[/]")
        conn.close()
        return

    # Field v0.1: get terms for this observation
    terms_rows = conn.execute(
        """
        SELECT t.term FROM terms t
        JOIN observation_terms ot ON ot.term_id = t.id
        WHERE ot.observation_id = ?
        ORDER BY t.term
        """,
        (obs["id"],),
    ).fetchall()
    terms = [r[0] for r in terms_rows]

    # Layer 1: interpretations (steward-authored)
    interpretations = conn.execute(
        "SELECT perspective, evidential_status, confidence, source, text, created_at "
        "FROM interpretations WHERE observation_id = ? ORDER BY created_at",
        (obs["id"],),
    ).fetchall()
    interpretations = [dict(r) for r in interpretations]

    # Layer 3: blueprints that cite this observation
    blueprints = conn.execute(
        """
        SELECT nb.id, nb.title, nb.thesis, nb.sections, nb.created_at
        FROM narrative_blueprints nb
        JOIN blueprint_observation_links bol ON bol.blueprint_id = nb.id
        WHERE bol.observation_id = ?
        ORDER BY nb.created_at
        """,
        (obs["id"],),
    ).fetchall()
    blueprints = [dict(r) for r in blueprints]

    has_interpretation = len(interpretations) > 0
    has_blueprint = len(blueprints) > 0

    from ..storage.sqlite import ensure_artist_tables
    ensure_artist_tables(conn)

    # Layer 4: Architect Plan (Composition layer 1)
    architect_plan = None
    architect_stale = False
    if has_blueprint:
        import json as _json2
        from ..storage.hashing import make_blueprint_id as _make_bp_hash
        bp = blueprints[0]
        ap_row = conn.execute(
            "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
            (bp["id"],),
        ).fetchone()
        if ap_row:
            architect_plan = dict(ap_row)
            sections = _json2.loads(bp["sections"])
            current_hash = _make_bp_hash(bp["title"], bp["thesis"], sections)
            architect_stale = architect_plan["blueprint_hash"] != current_hash

    # Layer 4b: Rendered Narrative (Artist)
    rendered_narrative = None
    if architect_plan is not None:
        rn_row = conn.execute(
            "SELECT id, provider, created_at FROM rendered_narratives "
            "WHERE architect_plan_id = ? ORDER BY created_at DESC LIMIT 1",
            (architect_plan["id"],),
        ).fetchone()
        if rn_row:
            rendered_narrative = dict(rn_row)

    # Layer 4c: Critic validation for the selected RenderedNarrative
    validation_report = None
    if rendered_narrative is not None:
        vr_row = conn.execute(
            "SELECT id, semantic_fidelity, approved, created_at "
            "FROM validation_reports WHERE rendered_narrative_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (rendered_narrative["id"],),
        ).fetchone()
        if vr_row:
            validation_report = dict(vr_row)

    conn.close()

    console.print(Rule(f"[bold cyan]Pipeline Trace: OBS-{n}[/]", style="cyan"))

    # ── Layer 0: Observation ──
    console.print(f"\n[bold green]▶ Layer 0 — Observation[/]  [dim]OBS-{n}[/]")
    console.print(f"  [dim]p.{obs['page']} · para {obs['paragraph']} · sent {obs['sentence']}[/]")
    console.print(f"  [dim]ID: {obs['id']}[/]")
    console.print(
        Panel(
            f'[italic]"{obs["normalized_text"]}"[/]',
            border_style="green",
            padding=(0, 1),
        )
    )

    # ── Layer 0b: Field v0.1 ──
    console.print(f"\n[bold green]▶ Field v0.1 — Term Memberships[/]  [dim]{len(terms)} terms[/]")
    if terms:
        term_str = "  " + "  ".join(f"[cyan]{t}[/]" for t in terms[:30])
        console.print(term_str)
        if len(terms) > 30:
            console.print(f"  [dim]… {len(terms) - 30} more[/]")
    console.print()

    adj_prev = f"OBS-{n-1}" if obs.get("preceding_observation_id") else "(none)"
    adj_next = f"OBS-{n+1}" if obs.get("following_observation_id") else "(none)"
    console.print(f"  [dim]adjacent_to:[/] {adj_prev} ← [bold]OBS-{n}[/] → {adj_next}")

    # ── Layer 1: Interpretation ──
    console.print(f"\n[{'bold green' if has_interpretation else 'dim'}]"
                  f"▶ Layer 1 — Interpretation[/]  "
                  f"[dim]{len(interpretations)} interpretation(s)[/]")
    if has_interpretation:
        for i, interp in enumerate(interpretations, 1):
            console.print(f"\n  [bold]{i}[/]")
            console.print(f"  [dim]Perspective:[/]       {interp['perspective']}")
            console.print(f"  [dim]Evidential status:[/] {interp['evidential_status']}")
            console.print(f"  [dim]Confidence:[/]        {interp['confidence'].title()}")
            console.print(f"  [dim]Source:[/]            {interp['source'].title()}")
    else:
        console.print("  [dim](none — use 'herm interpret create OBS-N' to add one)[/]")

    # ── Layer 3: Narrative Blueprint ──
    console.print(f"\n[{'bold green' if has_blueprint else 'dim'}]"
                  f"▶ Layer 3 — Narrative Blueprint[/]  "
                  f"[dim]{len(blueprints)} blueprint(s)[/]")
    if has_blueprint:
        for bp in blueprints:
            import json as _json
            sections = _json.loads(bp["sections"])
            # Find which sections cite this observation
            citing = [
                i + 1 for i, s in enumerate(sections)
                if obs["id"] in s.get("supporting_observations", [])
            ]
            console.print(f"\n  [bold cyan]\"{bp['title']}\"[/]")
            console.print(f"  [dim]Thesis:[/] {bp['thesis'][:70]}{'…' if len(bp['thesis']) > 70 else ''}")
            console.print(f"  [dim]Sections:[/] {len(sections)}  [dim]Cited in:[/] section(s) {', '.join(str(s) for s in citing)}")
    else:
        console.print("  [dim](none — use 'herm blueprint create' to build one)[/]")

    # ── Authorship column ──
    console.print("\n" + "─" * 48)
    console.print("[bold]Composition[/]")

    has_architect = architect_plan is not None
    if has_architect and architect_stale:
        arch_marker = "[yellow]⚠  Architect[/]"
        arch_detail = "[yellow]Out of date — Blueprint has changed since plan was generated.[/]"
    elif has_architect:
        arch_marker = "[green]✓  Architect[/]"
        arch_detail = f"[dim]{architect_plan['id'][:16]}…[/]"
    else:
        arch_marker = "[dim]○  Architect[/]"
        arch_detail = "[dim]Use: herm architect OBS-N[/]"

    has_artist = rendered_narrative is not None
    if has_artist:
        art_marker = "[green]✓  Artist[/]"
        art_detail = f"[dim]{rendered_narrative['provider']}[/]"
    else:
        art_marker = "[dim]○  Artist[/]"
        art_detail = "[dim]Use: herm artist OBS-N[/]" if has_architect else "[dim](requires Architect)[/]"

    console.print(f"\n  {arch_marker}  {arch_detail}")
    console.print(f"  {art_marker}   {art_detail}")
    if validation_report is not None:
        critic_marker = "[green]✓  Critic[/]"
        approved = "approved" if validation_report["approved"] else "not approved"
        critic_detail = (
            f"[dim]{validation_report['semantic_fidelity']}% · {approved}[/]"
        )
    else:
        critic_marker = "[dim]○  Critic[/]"
        critic_detail = "[dim]Use: herm critic OBS-N[/]" if has_artist else "[dim](requires Artist)[/]"
    console.print(f"  {critic_marker}   {critic_detail}")

    console.print()


# ── shared rendering ──────────────────────────────────────────────────────────

def _print_observation(
    idx: int,
    obs: dict,
    highlight: str | None = None,
    dim: bool = False,
    label: str | None = None,
) -> None:
    style = "dim" if dim else "bold"
    label_str = f"[dim]{label}[/]  " if label else ""

    text = obs.get("normalized_text") or obs.get("raw_text", "")
    if highlight and not dim:
        hl = highlight.lower()
        i = text.lower().find(hl)
        if i >= 0:
            text = (
                text[:i]
                + f"[bold yellow]{text[i:i+len(highlight)]}[/]"
                + text[i + len(highlight):]
            )

    short_id = obs["id"][:8] + "…"

    console.print(
        f"{label_str}[{style}]OBS-{idx}[/]  "
        f"[dim]p.{obs['page']} · para {obs['paragraph']} · sent {obs['sentence']}[/]  "
        f"[dim]id:{short_id}[/]"
    )
    console.print(f'  [italic]"{text}"[/]\n')


def _fmt_opt(v) -> str:
    if v is None:
        return "[dim]—[/]"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)
