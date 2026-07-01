"""
Edition Eligibility — Hermeneia publication governance.

An edition is not an export. It is a signed maturity state.
A cycle does not count unless the system can prove disciplined completion.

Protected publication statuses (in ascending order):
  Working Draft       — generated render, no complete cycle on record
  Reviewed Draft      — at least 1 qualified cycle
  Release Candidate   — coverage pass + Critic complete + no blocking issues
  Edition-Eligible    — at least EDITION_MIN_CYCLES qualified cycles
  Edition             — Edition-Eligible + human Steward designation (signed)
  Canonical Edition   — Edition + preservation verification complete

A "qualified cycle" requires evidence that the work passed through the
complete Hermeneia loop:
  1. Corpus scope declared  (build.json present with source_artifacts)
  2. Coverage measured      (coverage.json present, outcome == "pass")
  3. Release decision made  (release_recommendation.json present)
  4. Preservation verified  (preservation_report.json present, outcome != "fail")

Anti-gaming: a cycle that produces no change may still be recorded, but
only if the Steward supplies a reaffirmation note explaining that the prior
understanding was reviewed and intentionally preserved.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.rule import Rule

console = Console(highlight=False)

EDITION_MIN_CYCLES: int = 12
_CYCLE_STORE_FILENAME = "cycles.json"
_EDITION_STORE_FILENAME = "edition.json"
_CYCLE_SCHEMA_VERSION = "1.0"


class EditionError(Exception):
    pass


# ── Cycle store ────────────────────────────────────────────────────────────────

def _cycle_store_path(publication_dir: Path) -> Path:
    return publication_dir / _CYCLE_STORE_FILENAME


def _load_cycles(publication_dir: Path) -> dict:
    path = _cycle_store_path(publication_dir)
    if not path.exists():
        return {
            "edition_cycle_schema": _CYCLE_SCHEMA_VERSION,
            "minimum_cycles_for_eligibility": EDITION_MIN_CYCLES,
            "cycles": [],
        }
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise EditionError(
            f"cycles.json cannot be parsed: {exc}. "
            "Restore from version control before proceeding."
        ) from exc


def _save_cycles(store: dict, publication_dir: Path) -> None:
    publication_dir.mkdir(parents=True, exist_ok=True)
    (_cycle_store_path(publication_dir)).write_text(
        json.dumps(store, indent=2, ensure_ascii=False)
    )


# ── Qualification check ────────────────────────────────────────────────────────

def _check_cycle_qualification(
    publication_dir: Path,
) -> tuple[bool, list[str], dict[str, bool]]:
    """
    Returns (is_qualified, disqualification_reasons, evidence_dict).

    Checks four evidence requirements. All four must be satisfied for a cycle
    to be recorded as qualified. Missing evidence or failing outcomes are
    collected as reasons; the caller decides what to display.
    """
    build_path = publication_dir / "build.json"
    coverage_path = publication_dir / "coverage.json"
    release_path = publication_dir / "release_recommendation.json"
    preservation_path = publication_dir / "preservation_report.json"

    reasons: list[str] = []
    evidence: dict[str, bool] = {
        "build_present": False,
        "source_artifacts_nonempty": False,
        "coverage_pass": False,
        "release_recommendation_present": False,
        "preservation_verified": False,
    }

    # 1 — Build
    if not build_path.exists():
        reasons.append("build.json is missing — run: herm build")
    else:
        try:
            build = json.loads(build_path.read_text())
            evidence["build_present"] = True
            artifacts = build.get("source_artifacts", [])
            if not artifacts:
                reasons.append("build.json declares no source_artifacts — corpus is empty")
            else:
                evidence["source_artifacts_nonempty"] = True
        except json.JSONDecodeError:
            reasons.append("build.json cannot be parsed")

    # 2 — Coverage
    if not coverage_path.exists():
        reasons.append("coverage.json is missing — run: herm coverage")
    else:
        try:
            coverage = json.loads(coverage_path.read_text())
            outcome = coverage.get("outcome", "")
            if outcome == "pass":
                evidence["coverage_pass"] = True
            else:
                reasons.append(
                    f"coverage.json outcome is '{outcome}' (must be 'pass') — "
                    "complete coverage before recording this cycle"
                )
        except json.JSONDecodeError:
            reasons.append("coverage.json cannot be parsed")

    # 3 — Release recommendation
    if not release_path.exists():
        reasons.append(
            "release_recommendation.json is missing — run: herm release"
        )
    else:
        evidence["release_recommendation_present"] = True

    # 4 — Preservation
    if not preservation_path.exists():
        reasons.append(
            "preservation_report.json is missing — run: herm preserve verify"
        )
    else:
        try:
            preservation = json.loads(preservation_path.read_text())
            overall = preservation.get("overall_outcome", "")
            if overall == "fail":
                reasons.append(
                    "preservation_report.json overall_outcome is 'fail' — "
                    "preservation must pass or warn before recording this cycle"
                )
            else:
                evidence["preservation_verified"] = True
        except json.JSONDecodeError:
            reasons.append("preservation_report.json cannot be parsed")

    return (len(reasons) == 0), reasons, evidence


# ── Edition status ─────────────────────────────────────────────────────────────

def _edition_status(store: dict) -> dict:
    """
    Returns a status dict describing the current edition maturity state.

    Keys:
      cycle_count       — number of qualified cycles recorded
      status_label      — one of the six protected publication statuses
      eligible          — True if cycle_count >= EDITION_MIN_CYCLES
      cycles_remaining  — cycles still needed for eligibility (0 if eligible)
      edition           — dict from edition.json if a designation exists, else None
    """
    cycles = [c for c in store.get("cycles", []) if c.get("qualified", False)]
    count = len(cycles)
    min_required = store.get("minimum_cycles_for_eligibility", EDITION_MIN_CYCLES)
    eligible = count >= min_required

    if count == 0:
        label = "Working Draft"
    elif eligible:
        label = "Edition-Eligible"
    else:
        label = f"Reviewed Draft ({count}/{min_required} cycles)"

    return {
        "cycle_count": count,
        "status_label": label,
        "eligible": eligible,
        "cycles_remaining": max(0, min_required - count),
        "minimum_required": min_required,
    }


# ── CLI commands ───────────────────────────────────────────────────────────────

def cmd_edition_status(
    build_path: str | None = None,
    output_dir: str | None = None,
) -> None:
    project_root = Path.cwd()
    pub_dir = (
        Path(output_dir) if output_dir
        else project_root / "publication"
    )

    console.print(Rule(style="dim"))
    console.print()

    store = _load_cycles(pub_dir)
    status = _edition_status(store)
    cycles = store.get("cycles", [])
    total = len(cycles)
    qualified = status["cycle_count"]

    console.print(f"  [bold]Edition Status[/]  [cyan]{status['status_label']}[/]\n")
    console.print(f"  Qualified cycles recorded:  [bold]{qualified}[/]")
    console.print(f"  Total cycles in store:       {total}")
    console.print(f"  Required for Edition-Eligible: {status['minimum_required']}")
    if status["eligible"]:
        console.print(
            f"\n  [green]✓ Minimum edition discipline satisfied.[/]  "
            "Steward judgment still required to designate an Edition."
        )
    else:
        remaining = status["cycles_remaining"]
        console.print(
            f"\n  [dim]{remaining} more qualified cycle(s) required for Edition-Eligible status.[/]"
        )

    if qualified:
        console.print(f"\n  Qualified cycle history:")
        for c in cycles:
            if c.get("qualified"):
                ts = c.get("recorded_at", "")[:10]
                bid = c.get("build_id", "—")
                note = f"  [dim]({c['steward_reaffirmation']})[/]" if c.get("steward_reaffirmation") else ""
                console.print(f"    [green]✓[/]  {ts}  {bid}{note}")

    console.print()
    console.print(
        "  [dim]To record a cycle: herm edition record[/]"
    )
    console.print(
        "  [dim]To designate an Edition: herm edition designate --steward \"Name\"[/]"
    )
    console.print()
    console.print(Rule(style="dim"))


def cmd_edition_record(
    build_path: str | None = None,
    output_dir: str | None = None,
    steward_reaffirmation: str | None = None,
) -> None:
    """
    Record a cycle. Checks all four qualification prerequisites.
    If the cycle is disqualified, prints what is missing and exits 1.
    If all four are satisfied, appends a qualified cycle entry to cycles.json.
    """
    project_root = Path.cwd()
    pub_dir = (
        Path(output_dir) if output_dir
        else project_root / "publication"
    )

    console.print(Rule(style="dim"))
    store = _load_cycles(pub_dir)

    # Read build_id for labeling
    build_json_path = pub_dir / "build.json"
    build_id = "unknown"
    if build_json_path.exists():
        try:
            build_id = json.loads(build_json_path.read_text()).get("build_id", "unknown")
        except json.JSONDecodeError:
            pass

    console.print(f"\n  [bold]herm edition record[/]  [cyan]{build_id}[/]\n")

    qualified, reasons, evidence = _check_cycle_qualification(pub_dir)

    # Print evidence
    checks = [
        ("build_present",                 "Build emitted (build.json)"),
        ("source_artifacts_nonempty",     "Corpus non-empty (source_artifacts)"),
        ("coverage_pass",                 "Coverage measured and passing"),
        ("release_recommendation_present","Release decision recorded"),
        ("preservation_verified",         "Preservation verified"),
    ]
    for key, label in checks:
        ok = evidence.get(key, False)
        icon = "[green]✓[/]" if ok else "[red]✗[/]"
        console.print(f"  {icon}  {label}")

    if not qualified:
        console.print()
        for r in reasons:
            console.print(f"  [red]→[/] {r}")
        console.print()
        console.print(
            "  [red]Cycle not recorded.[/] A qualified cycle requires all five checks to pass.\n"
            "  An edition is earned by disciplined completion, not by export."
        )
        console.print()
        console.print(Rule(style="dim"))
        sys.exit(1)

    # Check for duplicate (same build_id already recorded)
    existing_ids = {c.get("build_id") for c in store.get("cycles", []) if c.get("qualified")}
    if build_id in existing_ids and not steward_reaffirmation:
        console.print()
        console.print(
            f"  [yellow]⚠ A qualified cycle for build '{build_id}' has already been recorded.[/]\n"
            "  If this is a reaffirmation (no material change, prior understanding reviewed),\n"
            "  re-run with --reaffirmation \"<note explaining why prior understanding is preserved>\"."
        )
        console.print()
        console.print(Rule(style="dim"))
        sys.exit(1)

    # Append cycle
    now = datetime.now(timezone.utc).isoformat()
    existing_cycles = store.get("cycles", [])
    cycle_number = len(existing_cycles) + 1
    cycle: dict = {
        "cycle_number": cycle_number,
        "cycle_id": f"c-{now[:10].replace('-','')}-{cycle_number:03d}",
        "recorded_at": now,
        "build_id": build_id,
        "qualified": True,
        "evidence": evidence,
        "disqualification_reasons": [],
        "steward_reaffirmation": steward_reaffirmation or None,
    }
    existing_cycles.append(cycle)
    store["cycles"] = existing_cycles
    _save_cycles(store, pub_dir)

    status = _edition_status(store)
    console.print()
    console.print(
        f"  [green]✓ Qualified cycle {cycle_number} recorded.[/]  "
        f"[cyan]{status['status_label']}[/]"
    )
    if status["eligible"]:
        console.print(
            "\n  [green]Minimum edition discipline satisfied.[/]\n"
            "  Steward judgment still required to designate an Edition.\n"
            "  Run: herm edition designate --steward \"Your Name\""
        )
    else:
        remaining = status["cycles_remaining"]
        console.print(
            f"\n  [dim]{remaining} more qualified cycle(s) required for Edition-Eligible status.[/]"
        )
    console.print()
    console.print(Rule(style="dim"))


def cmd_edition_designate(
    steward: str,
    edition_label: str | None = None,
    output_dir: str | None = None,
    notes: str | None = None,
) -> None:
    """
    Steward designation of an Edition. Requires Edition-Eligible status.
    Writes edition.json to the publication directory.
    Only a human Steward may designate an Edition.
    """
    project_root = Path.cwd()
    pub_dir = (
        Path(output_dir) if output_dir
        else project_root / "publication"
    )

    console.print(Rule(style="dim"))

    store = _load_cycles(pub_dir)
    status = _edition_status(store)

    console.print(f"\n  [bold]herm edition designate[/]\n")

    if not status["eligible"]:
        remaining = status["cycles_remaining"]
        console.print(
            f"  [red]Cannot designate Edition.[/]\n"
            f"  This work has completed {status['cycle_count']} qualified cycle(s).\n"
            f"  {remaining} more qualified cycle(s) required for Edition-Eligible status.\n"
            f"  Current status: {status['status_label']}\n\n"
            "  An edition is earned by disciplined completion, not by declaration.\n"
            "  Complete the remaining cycles before designating an Edition."
        )
        console.print()
        console.print(Rule(style="dim"))
        sys.exit(1)

    edition_path = pub_dir / _EDITION_STORE_FILENAME
    if edition_path.exists():
        try:
            existing = json.loads(edition_path.read_text())
            existing_label = existing.get("edition_label", "")
            existing_steward = existing.get("steward", "")
            console.print(
                f"  [red]An Edition designation already exists:[/] '{existing_label}' "
                f"signed by '{existing_steward}'.\n"
                "  An existing Edition designation cannot be overwritten by automation.\n"
                "  Remove edition.json manually before re-designating."
            )
            console.print()
            console.print(Rule(style="dim"))
            sys.exit(1)
        except json.JSONDecodeError:
            pass

    now = datetime.now(timezone.utc).isoformat()
    label = edition_label or f"Edition {status['cycle_count']}"
    doc = {
        "edition_schema": "1.0",
        "edition_label": label,
        "designated_at": now,
        "steward": steward,
        "steward_notes": notes or None,
        "qualified_cycle_count": status["cycle_count"],
        "minimum_required": status["minimum_required"],
        "status_at_designation": "Edition",
    }

    pub_dir.mkdir(parents=True, exist_ok=True)
    edition_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))

    console.print(
        f"  [green]✓ Edition designated.[/]\n\n"
        f"  Label:    [cyan]{label}[/]\n"
        f"  Steward:  {steward}\n"
        f"  Cycles:   {status['cycle_count']} qualified cycles\n"
        f"  Signed:   {now[:10]}\n"
    )
    if notes:
        console.print(f"  Notes:    [dim]{notes}[/]\n")
    console.print(
        "  [dim]edition.json written. Run herm preserve verify to create a Canonical Edition.[/]"
    )
    console.print()
    console.print(Rule(style="dim"))
