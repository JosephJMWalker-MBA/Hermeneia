"""
herm coverage — Coverage Engine

Determines whether a publication is ready to be compiled by measuring
whether every declared section requirement has accountable evidence.

Sprint 003 v0.1

Coverage Invariant:
    Coverage measures declared obligations, never inferred obligations.
    If a requirement is unresolved, the report says so. That is all.

Inputs:  build.json → manifest → Blueprint
NOT an input: white_paper.md (too late by then)

Outputs: coverage.json + coverage.md
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


class CoverageError(Exception):
    """Raised when coverage cannot proceed. No outputs written."""


# ── Stages ───────────────────────────────────────────────────────────────────

def _load_build_json(build_path: Path) -> dict:
    if not build_path.exists():
        raise CoverageError(f"build.json not found: {build_path}")
    try:
        data = json.loads(build_path.read_text())
    except json.JSONDecodeError as exc:
        raise CoverageError(f"build.json malformed: {exc}") from exc
    for key in ["build_id", "manifest_path", "source_artifacts"]:
        if key not in data:
            raise CoverageError(f"build.json missing required key: '{key}'")
    return data


def _load_manifest(build: dict, project_root: Path) -> dict:
    manifest_path = project_root / build["manifest_path"]
    if not manifest_path.exists():
        raise CoverageError(f"Manifest not found: {manifest_path}")
    try:
        data = yaml.safe_load(manifest_path.read_text())
    except yaml.YAMLError as exc:
        raise CoverageError(f"Manifest YAML malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise CoverageError("Manifest must be a YAML mapping")
    return data


def _load_blueprint(manifest: dict, project_root: Path) -> Path:
    bp_path = project_root / manifest["blueprint"]
    if not bp_path.exists():
        raise CoverageError(f"Blueprint not found: {bp_path}")
    return bp_path


def _build_tag_index(build: dict, project_root: Path) -> dict[str, list[str]]:
    """Build {tag → [artifact_path, ...]} from build.json resolved artifacts.

    Fails if any artifact path no longer exists on disk — build integrity check.
    """
    tag_index: dict[str, list[str]] = {}
    for artifact in build["source_artifacts"]:
        path = project_root / artifact["path"]
        if not path.exists():
            raise CoverageError(
                f"Artifact declared in build.json not found on disk: {path}\n"
                f"Re-run 'herm build' to refresh build.json."
            )
        for tag in artifact.get("tags", []):
            tag_index.setdefault(tag, []).append(artifact["path"])
    return tag_index


def _evaluate_sections(
    manifest: dict, tag_index: dict[str, list[str]]
) -> list[dict]:
    """Evaluate each section's required_tags against the resolved tag index.

    Claims are recorded but not evaluated in v0.1 (requires Critic — Sprint 004).
    """
    results = []
    for section in manifest.get("sections", []):
        name = section.get("section", "unknown")
        required_tags = section.get("required_tags", [])
        required_claims = section.get("required_claims", [])

        tag_results = []
        section_status = "PASS"

        for tag in required_tags:
            resolved_by = tag_index.get(tag, [])
            if resolved_by:
                tag_results.append({
                    "tag": tag,
                    "status": "PASS",
                    "resolved_by": resolved_by,
                })
            else:
                tag_results.append({
                    "tag": tag,
                    "status": "WARN",
                    "resolved_by": [],
                    "note": "Requirement unresolved",
                })
                section_status = "WARN"

        results.append({
            "section": name,
            "status": section_status,
            "required_tags": required_tags,
            "tag_results": tag_results,
            "required_claims": required_claims,
            "claims_checkable": False,
            "claims_note": (
                "Programmatic claim evaluation deferred to Sprint 004 Critic integration"
            ),
        })

    return results


def _emit_coverage_md(
    build: dict, section_results: list[dict], summary: dict, output_dir: Path
) -> None:
    lines = [
        "# Coverage Report\n\n",
        f"**Build:** {build['build_id']}  \n",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n\n",
        "## Coverage Summary\n\n",
        "| Metric | Count |\n",
        "|--------|-------|\n",
        f"| Sections evaluated | {summary['sections_evaluated']} |\n",
        f"| PASS | {summary['pass']} |\n",
        f"| WARN | {summary['warn']} |\n",
        f"| FAIL | {summary['fail']} |\n",
        f"| Overall | {summary['overall_pct']}% |\n\n",
        "_Overall = PASS / (PASS + WARN + FAIL). "
        "The percentage is informational. The unresolved requirements are what matter._\n\n",
        "---\n\n",
        "## Section Detail\n\n",
    ]

    for r in section_results:
        icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(r["status"], "?")
        lines.append(f"### {r['section']} — {r['status']} {icon}\n\n")
        lines.append(f"Required tags: {', '.join(f'`{t}`' for t in r['required_tags'])}\n\n")

        if r["status"] == "PASS":
            lines.append("All tags resolved. ✓\n\n")
        else:
            lines.append("| Tag | Status | Resolved by |\n")
            lines.append("|-----|--------|-------------|\n")
            for tr in r["tag_results"]:
                resolved = ", ".join(tr["resolved_by"]) if tr["resolved_by"] else "—"
                status_str = "✓" if tr["status"] == "PASS" else "✗ UNRESOLVED"
                lines.append(f"| `{tr['tag']}` | {status_str} | {resolved} |\n")
            lines.append("\n")
            unresolved = [tr["tag"] for tr in r["tag_results"] if tr["status"] != "PASS"]
            if unresolved:
                lines.append(f"**Missing:** {', '.join(f'`{t}`' for t in unresolved)}  \n")
                lines.append("Requirement unresolved.\n\n")

        if r["required_claims"]:
            lines.append(
                f"_Claims ({len(r['required_claims'])} declared): "
                "evaluation requires programmatic Critic (Sprint 004)._\n\n"
            )

    (output_dir / "coverage.md").write_text("".join(lines))


def _emit_coverage_json(
    build: dict,
    manifest: dict,
    tag_index: dict[str, list[str]],
    section_results: list[dict],
    summary: dict,
    output_dir: Path,
) -> dict:
    coverage = {
        "coverage_engine_version": "0.1.0",
        "build_id": build["build_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": build["manifest_path"],
        "blueprint_id": manifest.get("blueprint_id", "unknown"),
        "tag_index": {tag: paths for tag, paths in sorted(tag_index.items())},
        "sections": section_results,
        "summary": summary,
        "outcome": "fail" if summary["fail"] > 0 else (
            "warn" if summary["warn"] > 0 else "pass"
        ),
        "claims_note": (
            "Programmatic claim evaluation deferred to Sprint 004. "
            "Required claims are recorded in each section's required_claims field."
        ),
    }
    (output_dir / "coverage.json").write_text(
        json.dumps(coverage, indent=2, ensure_ascii=False)
    )
    return coverage


# ── CLI entry point ───────────────────────────────────────────────────────────

def cmd_coverage(
    build_path: str | None = None,
    output_dir: str | None = None,
    verbose: bool = False,
) -> None:
    project_root = Path.cwd()
    build_path_ = Path(build_path) if build_path else project_root / "publication" / "build.json"
    output_dir_ = Path(output_dir) if output_dir else project_root / "publication"

    try:
        console.print(Rule(style="dim"))

        # Stage 1 — Load build.json
        build = _load_build_json(build_path_)
        build_id = build["build_id"]
        console.print(f"\n  [bold]herm coverage[/]  [cyan]{build_id}[/]\n")
        console.print("  Reading build.json...          [green]PASS[/]")

        # Stage 2 — Load manifest
        manifest = _load_manifest(build, project_root)
        console.print("  Loading manifest...            [green]PASS[/]")

        # Stage 3 — Load Blueprint (verify it exists)
        _load_blueprint(manifest, project_root)
        console.print("  Loading Blueprint...           [green]PASS[/]")

        # Stage 4 — Build tag index
        tag_index = _build_tag_index(build, project_root)
        unique_tags = len(tag_index)
        artifact_count = len(build["source_artifacts"])
        console.print(
            f"  Building tag index...          [green]PASS[/]  "
            f"[dim][{unique_tags} tags across {artifact_count} artifacts][/]"
        )

        # Stage 5 — Evaluate sections
        section_results = _evaluate_sections(manifest, tag_index)
        console.print("  Checking section requirements  [green]PASS[/]")

        if verbose:
            console.print()
            for r in section_results:
                icon = {"PASS": "[green]✓[/]", "WARN": "[yellow]⚠[/]", "FAIL": "[red]✗[/]"}.get(
                    r["status"], "?"
                )
                console.print(f"    {r['section']:<25} {icon}")
                for tr in r["tag_results"]:
                    t_icon = "[green]✓[/]" if tr["status"] == "PASS" else "[yellow]—[/]"
                    console.print(f"      {t_icon}  [dim]{tr['tag']}[/]")

        # Summarize
        n_pass = sum(1 for r in section_results if r["status"] == "PASS")
        n_warn = sum(1 for r in section_results if r["status"] == "WARN")
        n_fail = sum(1 for r in section_results if r["status"] == "FAIL")
        n_total = len(section_results)
        overall_pct = round(n_pass / n_total * 100) if n_total else 0

        summary = {
            "sections_evaluated": n_total,
            "pass": n_pass,
            "warn": n_warn,
            "fail": n_fail,
            "overall_pct": overall_pct,
        }

        # Stage 6 — Emit outputs
        output_dir_.mkdir(parents=True, exist_ok=True)
        _emit_coverage_md(build, section_results, summary, output_dir_)
        _emit_coverage_json(build, manifest, tag_index, section_results, summary, output_dir_)

        # Summary
        console.print()
        console.print(Rule(style="dim"))
        console.print()

        outcome_str = (
            "[green]PASS[/]" if n_fail == 0 and n_warn == 0
            else f"[yellow]{n_warn} WARNING(S)[/]" if n_fail == 0
            else f"[red]{n_fail} FAIL(S)[/]"
        )
        console.print(f"  Coverage: [cyan]{build_id}[/]  {outcome_str}\n")
        console.print(f"    [dim]{n_total} sections evaluated[/]")
        console.print(f"    [green]{n_pass} PASS[/]")
        if n_warn:
            console.print(f"    [yellow]{n_warn} WARNING[/]")
            for r in section_results:
                if r["status"] == "WARN":
                    unresolved = [tr["tag"] for tr in r["tag_results"] if tr["status"] != "PASS"]
                    console.print(f"      [dim]→ {r['section']}: missing {unresolved}[/]")
        if n_fail:
            console.print(f"    [red]{n_fail} FAIL[/]")
        console.print(f"    [dim]Overall: {overall_pct}%[/]")

        console.print()
        console.print("  [dim]coverage.json written.[/]")
        console.print("  [dim]coverage.md written.[/]")
        console.print()
        console.print(Rule(style="dim"))

        if n_fail > 0:
            sys.exit(1)

    except CoverageError as exc:
        console.print()
        console.print(Rule(style="red"))
        console.print(f"\n  [bold red]Coverage failed[/]\n")
        console.print(f"  [red]ERROR:[/] {exc}\n")
        console.print("  [dim]No outputs written.[/]")
        console.print()
        console.print(Rule(style="red"))
        sys.exit(1)
