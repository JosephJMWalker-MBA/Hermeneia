"""
herm explorer discover — Explorer Discovery Report

Usage:
    herm explorer discover [--limit N] [--provider PROVIDER] [--model MODEL] [--profile SLUG]
    herm explorer discover OBS-1 OBS-7 OBS-23 [--provider PROVIDER]

Runs the Explorer bucketing pass on selected or recent observations, generates
speculative interpretations for each bucket, and prints an inspection report.

Buckets are ephemeral compiler internals — not stored. Only the speculative
Interpretation and its evidence_observation_ids are persisted.

The report answers: are the buckets any good?
"""
from __future__ import annotations

import json
import sqlite3
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from ..explorer.bucketer import BucketingError, generate_candidate_buckets
from ..explorer.interpreter import ExplorerError, generate_interpretation_from_bucket
from ..compiler.staging.interpretation import StagingError, propose_interpretation
from ..storage.sqlite import SQLiteStore
from ..narrative.artist_providers import DEFAULT_PROVIDER_REGISTRY, get_provider

console = Console()


def cmd_explorer_discover(
    obs_refs: list[str],
    limit: int = 30,
    provider_name: str = "null",
    model: str | None = None,
    perspective: str = "Literary",
    bundle_or_db: str | None = None,
) -> None:
    from .inspector import _resolve_db, _parse_obs_ref

    db_path = _resolve_db(bundle_or_db)
    if not db_path.exists():
        console.print(f"[red]Database not found:[/] {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # ── Resolve observations ──────────────────────────────────────────────────
    all_ids: list[str] = [
        r[0] for r in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]
    id_to_n = {oid: i + 1 for i, oid in enumerate(all_ids)}

    if obs_refs:
        # Explicit OBS-N list
        obs_rows = []
        for ref in obs_refs:
            n = _parse_obs_ref(ref)
            if n < 1 or n > len(all_ids):
                console.print(f"[red]{ref} not found (total: {len(all_ids)})[/]")
                conn.close()
                sys.exit(1)
            obs_id = all_ids[n - 1]
            row = conn.execute(
                "SELECT id, raw_text FROM observations WHERE id = ?", (obs_id,)
            ).fetchone()
            obs_rows.append({"id": row["id"], "raw_text": row["raw_text"]})
    else:
        # Most recent observations up to limit
        rows = conn.execute(
            "SELECT id, raw_text FROM observations ORDER BY page, paragraph, sentence LIMIT ?",
            (limit,),
        ).fetchall()
        obs_rows = [{"id": r["id"], "raw_text": r["raw_text"]} for r in rows]

    # Corpus context
    primary_doc = conn.execute(
        """SELECT original_filename FROM source_documents
           WHERE COALESCE(excluded_from_analysis, 0) = 0
           AND COALESCE(source_role, 'primary') = 'primary'
           ORDER BY registered_at LIMIT 1"""
    ).fetchone()
    corpus_context = {
        "primary_work": primary_doc["original_filename"] if primary_doc else None,
        "observation_role": "primary",
    }
    conn.close()

    if not obs_rows:
        console.print("[yellow]No observations found.[/]")
        return

    # ── Provider ──────────────────────────────────────────────────────────────
    provider_kwargs: dict[str, Any] = {}
    if model:
        provider_kwargs["model"] = model
    try:
        provider = get_provider(provider_name, **provider_kwargs)
    except Exception as exc:
        console.print(f"[red]Provider error:[/] {exc}")
        sys.exit(1)

    # ── Bucketing pass (ephemeral) ─────────────────────────────────────────────
    console.print(Rule(f"[bold cyan]Explorer Discovery[/]  [dim]{db_path.name}[/]", style="cyan"))
    console.print(f"[dim]Observations:[/] {len(obs_rows)}  [dim]Provider:[/] {provider_name}  [dim]Perspective:[/] {perspective}\n")

    try:
        buckets = generate_candidate_buckets(obs_rows, provider)
    except BucketingError as exc:
        console.print(f"[red]Bucketing failed:[/] {exc}")
        sys.exit(1)

    singletons = sum(1 for b in buckets if len(b) == 1)
    console.print(f"Buckets proposed: [bold]{len(buckets)}[/]  Singletons: [dim]{singletons}[/]")

    # ── Generate interpretations ──────────────────────────────────────────────
    store = SQLiteStore(db_path)
    obs_lookup = {o["id"]: o for o in obs_rows}
    generated_at = datetime.now(timezone.utc).isoformat()

    created = 0
    skipped = 0
    results: list[dict] = []

    for bucket_ids in buckets:
        bucket_obs = [obs_lookup[oid] for oid in bucket_ids if oid in obs_lookup]
        primary_obs_id = sorted(bucket_ids)[0]
        sorted_evidence_ids = sorted(bucket_ids)

        # Idempotency check
        existing = store._conn.execute(
            "SELECT id, evidence_observation_ids FROM proposed_interpretations "
            "WHERE observation_id = ? AND perspective = ? AND status IN ('pending','accepted')",
            (primary_obs_id, perspective),
        ).fetchall()
        duplicate = any(
            sorted(json.loads(r["evidence_observation_ids"] or "[]")) == sorted_evidence_ids
            for r in existing
        )
        if duplicate:
            skipped += 1
            results.append({
                "bucket_ids": bucket_ids,
                "skipped": True,
                "text": None,
                "prompt": None,
            })
            continue

        try:
            interp_text, prompt_used = generate_interpretation_from_bucket(
                bucket_obs, perspective, provider, corpus_context
            )
        except ExplorerError as exc:
            console.print(f"[yellow]Explorer failed for bucket {sorted(bucket_ids)[:2]}…: {exc}[/]")
            continue

        try:
            proposal = propose_interpretation(
                observation_id=primary_obs_id,
                perspective=perspective,
                text=interp_text,
                evidential_status="speculative",
                generating_model=f"{provider_name}/{model or 'default'}",
                prompt_reference=prompt_used,
                prompt_reference_type="full_text",
                conn=store,
                generation_timestamp=generated_at,
                parent_object_ids=sorted_evidence_ids,
                generation_parameters={
                    "surface": "herm explorer discover",
                    "perspective": perspective,
                    "mode": "explorer-bucket",
                    "bucket_size": len(bucket_ids),
                    "bucket_observation_ids": sorted_evidence_ids,
                },
                evidence_observation_ids=sorted_evidence_ids,
            )
            created += 1
            results.append({
                "bucket_ids": bucket_ids,
                "skipped": False,
                "text": interp_text,
                "prompt": prompt_used,
                "proposal_id": proposal["id"],
            })
        except StagingError as exc:
            console.print(f"[yellow]Staging failed:[/] {exc}")

    store.close()

    # ── Report ────────────────────────────────────────────────────────────────
    console.print(f"Speculative interpretations created: [bold green]{created}[/]")
    console.print(f"Skipped (already exist):             [dim]{skipped}[/]\n")

    for i, result in enumerate(results, 1):
        bucket_ids = result["bucket_ids"]
        obs_labels = [f"OBS-{id_to_n.get(oid, '?')}" for oid in bucket_ids]
        size_note = f"[dim]singleton[/]" if len(bucket_ids) == 1 else f"[dim]{len(bucket_ids)} observations[/]"

        console.print(Rule(f"[bold]Bucket {i}[/]  {', '.join(obs_labels)}  {size_note}", style="dim"))

        if result["skipped"]:
            console.print("[dim]  (skipped — proposal already exists)[/]\n")
            continue

        console.print("\n[bold cyan]Candidate interpretation:[/]")
        wrapped = textwrap.fill(result["text"] or "", width=90, initial_indent="  ", subsequent_indent="  ")
        console.print(wrapped)

        console.print("\n[dim]Evidence observations:[/]")
        for oid in bucket_ids:
            n = id_to_n.get(oid, "?")
            obs = obs_lookup.get(oid, {})
            excerpt = (obs.get("raw_text") or "")[:120].replace("\n", " ")
            if len(obs.get("raw_text", "")) > 120:
                excerpt += "…"
            console.print(f"  [cyan]OBS-{n}[/]  {excerpt}")

        console.print()

    console.print(Rule(style="dim"))
    console.print(f"[dim]Status: speculative — Steward review required before any interpretation becomes established.[/]")
