"""
herm release — Release Steward

Evaluates declared release criteria against build.json and coverage.json.
Produces release_recommendation.json.

Sprint 004 v0.1

Constitutional Principles:
    The Release Steward may recommend publication, but it may never declare
    publication.

    Release criteria evaluate declared facts, not executable policy.

    Release criteria must be inspectable without executing code.

Inputs:  build.json + coverage.json + release_criteria.yaml
Output:  release_recommendation.json

The steward_signature field is intentionally null on emission.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from rich.console import Console
from rich.rule import Rule

console = Console()


class ReleaseError(Exception):
    """Raised when the release steward cannot proceed. No outputs written."""


# ── Criterion resolution ──────────────────────────────────────────────────────

def _resolve_path(data: dict, dot_path: str) -> object:
    """Walk a dot-notation path through a dict. Raises KeyError on miss."""
    parts = dot_path.split(".")
    node = data
    for part in parts:
        if not isinstance(node, dict):
            raise KeyError(f"Expected dict at '{part}', got {type(node).__name__}")
        node = node[part]
    return node


# ── Stages ───────────────────────────────────────────────────────────────────

def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        raise ReleaseError(f"{label} not found: {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"{label} malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError(f"{label} must be a JSON object")
    return data


def _load_criteria(criteria_path: Path) -> dict:
    if not criteria_path.exists():
        raise ReleaseError(f"Release criteria not found: {criteria_path}")
    try:
        data = yaml.safe_load(criteria_path.read_text())
    except yaml.YAMLError as exc:
        raise ReleaseError(f"Release criteria YAML malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError("Release criteria must be a YAML mapping")
    if "criteria" not in data or not isinstance(data["criteria"], list):
        raise ReleaseError("Release criteria must contain a 'criteria' list")
    return data


_SOURCES = {"build.json", "coverage.json"}


def _evaluate_criteria(
    criteria_def: dict,
    build: dict,
    coverage: dict,
) -> tuple[list[dict], str]:
    """Evaluate all criteria. Returns (results, outcome)."""
    source_map = {"build.json": build, "coverage.json": coverage}
    results: list[dict] = []
    any_required_failed = False

    for criterion in criteria_def["criteria"]:
        name = criterion.get("name", "unnamed")
        source_key = criterion.get("source", "")
        dot_path = criterion.get("path", "")
        expected = criterion.get("equals")
        required = criterion.get("required", True)

        if source_key not in _SOURCES:
            raise ReleaseError(
                f"Criterion '{name}': unknown source '{source_key}'. "
                f"Must be one of: {sorted(_SOURCES)}"
            )

        source_data = source_map[source_key]

        try:
            actual = _resolve_path(source_data, dot_path)
        except KeyError as exc:
            raise ReleaseError(
                f"Criterion '{name}': path '{dot_path}' not found in {source_key} — {exc}"
            ) from exc

        passed = actual == expected

        if required:
            if not passed:
                any_required_failed = True
            result = {
                "name": name,
                "source": source_key,
                "path": dot_path,
                "expected": expected,
                "actual": actual,
                "required": True,
                "status": "PASS" if passed else "FAIL",
            }
        else:
            result = {
                "name": name,
                "source": source_key,
                "path": dot_path,
                "expected": expected,
                "actual": actual,
                "required": False,
                "status": "ADVISORY",
                "passed": passed,
            }
            if not passed:
                result["note"] = f"Advisory: expected {expected!r}, got {actual!r}"

        results.append(result)

    outcome = "WITHHOLD" if any_required_failed else "RECOMMEND_RELEASE"
    return results, outcome


def _emit_recommendation(
    build: dict,
    criteria_path: Path,
    build_path: Path,
    coverage_path: Path,
    criteria_results: list[dict],
    outcome: str,
    output_dir: Path,
) -> dict:
    n_required = sum(1 for r in criteria_results if r["required"])
    n_required_pass = sum(1 for r in criteria_results if r["required"] and r["status"] == "PASS")
    n_advisory = sum(1 for r in criteria_results if not r["required"])
    n_advisory_flagged = sum(
        1 for r in criteria_results if not r["required"] and not r.get("passed", True)
    )

    if outcome == "RECOMMEND_RELEASE":
        recommendation = (
            "All mandatory release criteria satisfied. "
            "Human Steward review required before canonical publication."
        )
    else:
        failed = [r["name"] for r in criteria_results if r["required"] and r["status"] == "FAIL"]
        recommendation = (
            f"{len(failed)} mandatory criterion/criteria not satisfied: "
            + ", ".join(f'"{n}"' for n in failed)
            + ". Address the flagged items before re-attempting."
        )

    doc = {
        "release_engine_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_id": build.get("build_id", "unknown"),
        "inputs": {
            "build_json": str(build_path),
            "coverage_json": str(coverage_path),
            "release_criteria": str(criteria_path),
        },
        "criteria_results": criteria_results,
        "summary": {
            "required": n_required,
            "required_pass": n_required_pass,
            "required_fail": n_required - n_required_pass,
            "advisory": n_advisory,
            "advisory_flagged": n_advisory_flagged,
        },
        "outcome": outcome,
        "recommendation": recommendation,
        "steward_signature": None,
        "steward_notes": None,
        "signed_at": None,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "release_recommendation.json"
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
        except json.JSONDecodeError:
            raise ReleaseError(
                "release_recommendation.json exists but cannot be parsed as JSON. "
                "Inspect the file before re-running herm release. "
                "If the file is corrupt, restore it from version control before proceeding."
            )
        sig = existing.get("steward_signature")
        if sig is not None:
            raise ReleaseError(
                f"release_recommendation.json is already signed by '{sig}'. "
                "A signed recommendation cannot be overwritten by automation. "
                "Remove the signature manually before re-running herm release."
            )
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    return doc


# ── CLI entry point ───────────────────────────────────────────────────────────

def cmd_release(
    build_path: str | None = None,
    coverage_path: str | None = None,
    criteria_path: str | None = None,
    output_dir: str | None = None,
    verbose: bool = False,
) -> None:
    project_root = Path.cwd()
    build_path_ = Path(build_path) if build_path else project_root / "publication" / "build.json"
    coverage_path_ = Path(coverage_path) if coverage_path else project_root / "publication" / "coverage.json"
    criteria_path_ = Path(criteria_path) if criteria_path else project_root / "docs" / "builds" / "release_criteria.yaml"
    output_dir_ = Path(output_dir) if output_dir else project_root / "publication"

    try:
        console.print(Rule(style="dim"))

        # Stage 1 — Load inputs
        build = _load_json(build_path_, "build.json")
        build_id = build.get("build_id", "unknown")
        console.print(f"\n  [bold]herm release[/]  [cyan]{build_id}[/]\n")
        console.print("  Reading build.json...          [green]PASS[/]")

        coverage = _load_json(coverage_path_, "coverage.json")
        console.print("  Reading coverage.json...       [green]PASS[/]")

        criteria_def = _load_criteria(criteria_path_)
        n_required = sum(1 for c in criteria_def["criteria"] if c.get("required", True))
        n_advisory = sum(1 for c in criteria_def["criteria"] if not c.get("required", True))
        console.print(
            f"  Reading release criteria...    [green]PASS[/]  "
            f"[dim][{n_required} required, {n_advisory} advisory][/]"
        )

        # Stage 2 — Evaluate
        console.print("  Evaluating criteria...\n")
        criteria_results, outcome = _evaluate_criteria(criteria_def, build, coverage)

        # Print per-criterion results
        for r in criteria_results:
            if r["required"]:
                icon = "[green]✓[/]" if r["status"] == "PASS" else "[red]✗[/]"
                console.print(f"  {icon}  {r['name']}")
                if r["status"] == "FAIL":
                    console.print(f"       [dim]Expected:[/] {r['expected']!r}")
                    console.print(f"       [dim]Actual:  [/] [red]{r['actual']!r}[/]")
            else:
                passed = r.get("passed", True)
                icon = "[green]✓[/]" if passed else "[yellow]·[/]"
                note = "" if passed else f"  [dim][advisory — actual: {r['actual']!r}][/]"
                console.print(f"  {icon}  {r['name']}{note}")

        # Stage 3 — Emit
        doc = _emit_recommendation(
            build, criteria_path_, build_path_, coverage_path_,
            criteria_results, outcome, output_dir_
        )

        console.print()
        console.print(Rule(style="dim"))
        console.print()

        if outcome == "RECOMMEND_RELEASE":
            console.print("  Recommendation:")
            console.print("      [bold green]RECOMMEND_RELEASE[/]\n")
            if doc["summary"]["advisory_flagged"]:
                console.print(
                    f"  [dim]{doc['summary']['advisory_flagged']} advisory item(s) flagged "
                    f"(non-blocking — see release_recommendation.json)[/]\n"
                )
            console.print("  Release Steward Recommendation written.")
            console.print("  [dim]Awaiting human signature.[/]")
        else:
            n_fail = doc["summary"]["required_fail"]
            console.print("  Recommendation:")
            console.print(f"      [bold red]WITHHOLD[/]\n")
            console.print(
                f"  [red]{n_fail} required criterion/criteria not satisfied.[/]"
            )
            console.print(
                "  [dim]Address the flagged items and re-run "
                "herm coverage before re-attempting.[/]"
            )

        console.print()
        console.print("  [dim]release_recommendation.json written.[/]")
        console.print()
        console.print(Rule(style="dim"))

        if outcome == "WITHHOLD":
            sys.exit(1)

    except ReleaseError as exc:
        console.print()
        console.print(Rule(style="red"))
        console.print("\n  [bold red]Release evaluation failed[/]\n")
        console.print(f"  [red]ERROR:[/] {exc}\n")
        console.print("  [dim]No outputs written.[/]")
        console.print()
        console.print(Rule(style="red"))
        sys.exit(2)
