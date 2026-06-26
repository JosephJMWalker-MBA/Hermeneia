"""
herm build — Publication Build Compiler

Consumes a compile manifest, resolves and hashes source artifacts,
runs coverage analysis, assembles publication outputs, and emits build.json.

Sprint 002 v0.1 — compiler scaffold:
  Stage 5 (Compile Sections) copies the existing compiled_artifact rather
  than driving the Artist. This proves inputs, outputs, and provenance are
  correct before automation replaces manual stages.

Build Invariants (from spec):
  1. A build never changes authoritative understanding. It only renders it.
  2. A build is reproducible from its manifest.
  3. Every emitted artifact has a provenance record.
  4. Build failure never mutates authoritative artifacts.
  5. Release status is descriptive, not generative.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.rule import Rule

console = Console()

# ── Failure conditions ────────────────────────────────────────────────────────

class BuildError(Exception):
    """Raised when the build cannot proceed. No outputs are written."""


class BuildWarning:
    def __init__(self, message: str):
        self.message = message


# ── Stages ───────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _stage_load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        raise BuildError(f"Manifest not found: {manifest_path}")
    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise BuildError(f"Manifest YAML malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise BuildError("Manifest must be a YAML mapping")
    required = ["build_id", "compiled_artifact", "blueprint", "blueprint_id",
                "blueprint_status", "source_artifacts", "sections"]
    missing = [k for k in required if k not in data]
    if missing:
        raise BuildError(f"Manifest missing required keys: {missing}")
    return data


def _stage_resolve_blueprint(manifest: dict, project_root: Path) -> dict:
    bp_path = project_root / manifest["blueprint"]
    if not bp_path.exists():
        raise BuildError(f"Blueprint not found: {bp_path}")
    if manifest.get("blueprint_status") != "ratified":
        raise BuildError(
            f"Blueprint status is '{manifest.get('blueprint_status')}' — "
            f"only 'ratified' blueprints may be built"
        )
    return {
        "path": str(bp_path),
        "id": manifest["blueprint_id"],
        "status": manifest["blueprint_status"],
        "sha256": _sha256(bp_path),
    }


def _stage_resolve_tags(
    manifest: dict, project_root: Path
) -> tuple[list[dict], dict[str, list[str]], list[BuildWarning]]:
    """Resolve artifacts, compute hashes, build tag index."""
    warnings: list[BuildWarning] = []
    resolved: list[dict] = []
    tag_index: dict[str, list[str]] = {}  # tag → [artifact_path, ...]

    for artifact in manifest["source_artifacts"]:
        path = project_root / artifact["path"]
        if not path.exists():
            raise BuildError(f"Source artifact not found: {path}")
        h = _sha256(path)
        tags = artifact.get("tags", [])
        entry = {
            "path": artifact["path"],
            "sha256": h,
            "tags": tags,
            "status": artifact.get("status", "unknown"),
            "role": artifact.get("role", "unknown"),
            "resolved": True,
        }
        resolved.append(entry)
        for tag in tags:
            tag_index.setdefault(tag, []).append(artifact["path"])

    return resolved, tag_index, warnings


def _stage_coverage(
    manifest: dict, tag_index: dict[str, list[str]]
) -> tuple[list[dict], list[BuildWarning]]:
    """Check section requirements against resolved tag index."""
    warnings: list[BuildWarning] = []
    results: list[dict] = []

    for section in manifest.get("sections", []):
        name = section.get("section", "unknown")
        required_tags = section.get("required_tags", [])
        required_claims = section.get("required_claims", [])

        missing_tags = [t for t in required_tags if t not in tag_index]
        status = "FAIL" if missing_tags else "PASS"

        if missing_tags:
            w = BuildWarning(
                f"Section '{name}' missing required tags: {missing_tags}"
            )
            warnings.append(w)
            status = "WARN"

        results.append({
            "section": name,
            "status": status,
            "required_tags": required_tags,
            "missing_tags": missing_tags,
            "required_claims": required_claims,
            "claims_checked": False,  # v0.1: manual critic
        })

    return results, warnings


def _stage_compile(
    manifest: dict, project_root: Path, output_dir: Path
) -> dict:
    """v0.1: copy existing compiled_artifact; hash and record it."""
    src = project_root / manifest["compiled_artifact"]
    if not src.exists():
        raise BuildError(f"Compiled artifact not found: {src}")

    dest = output_dir / "white_paper.md"
    shutil.copy2(src, dest)
    return {
        "source": str(src),
        "sha256": _sha256(src),
        "method": "copy",  # v0.1 scaffold; future: artist_render
        "note": "v0.1 copies existing compiled artifact. Future versions drive Artist.",
    }


def _stage_steward_report(
    manifest: dict, project_root: Path, output_dir: Path, coverage_results: list[dict]
) -> None:
    """Copy or generate release_decision.md, rc_log.md, coverage.md."""
    builds_dir = project_root / "docs" / "builds"

    # coverage.md
    coverage_lines = [
        "# Coverage Report\n",
        f"**Build:** {manifest['build_id']}  \n",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n\n",
        "| Section | Status | Missing Tags |\n",
        "|---------|--------|--------------|\n",
    ]
    for r in coverage_results:
        missing = ", ".join(r["missing_tags"]) if r["missing_tags"] else "—"
        coverage_lines.append(f"| {r['section']} | {r['status']} | {missing} |\n")
    (output_dir / "coverage.md").write_text("".join(coverage_lines))

    # rc_log.md — copy existing if present, else generate stub
    rc_log_src = builds_dir / "white_paper_rc_log.md"
    if rc_log_src.exists():
        shutil.copy2(rc_log_src, output_dir / "rc_log.md")
    else:
        (output_dir / "rc_log.md").write_text(
            f"# RC Log\n\n**Build:** {manifest['build_id']}\n\n"
            "_RC log not yet written. See steward for history._\n"
        )

    # release_decision.md — copy existing if present, else generate stub
    rd_src = builds_dir / "white_paper_release_decision.md"
    if rd_src.exists():
        shutil.copy2(rd_src, output_dir / "release_decision.md")
    else:
        (output_dir / "release_decision.md").write_text(
            f"# Release Decision\n\n**Build:** {manifest['build_id']}  \n"
            "**Status:** Pending steward review  \n\n"
            "_No release decision has been recorded for this build._\n"
        )


def _emit_build_json(
    manifest: dict,
    manifest_path: Path,
    blueprint: dict,
    resolved_artifacts: list[dict],
    coverage_results: list[dict],
    compile_record: dict,
    warnings: list[BuildWarning],
    output_dir: Path,
    hermeneia_version: str = "0.1.0",
) -> dict:
    n_pass = sum(1 for r in coverage_results if r["status"] == "PASS")
    n_warn = sum(1 for r in coverage_results if r["status"] == "WARN")
    n_fail = sum(1 for r in coverage_results if r["status"] == "FAIL")
    outcome = "fail" if n_fail > 0 else ("warn" if n_warn > 0 else "pass")

    build = {
        "build_id": manifest["build_id"],
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "hermeneia_version": hermeneia_version,
        "blueprint": blueprint,
        "manifest_path": str(manifest_path),
        "manifest_hash": _sha256(manifest_path),
        "source_artifacts": resolved_artifacts,
        "coverage": {
            "sections_evaluated": len(coverage_results),
            "sections_pass": n_pass,
            "sections_warn": n_warn,
            "sections_fail": n_fail,
            "section_detail": coverage_results,
        },
        "compile": compile_record,
        "critic": {
            "enabled": False,
            "note": "v0.1: critic pass is manual; future versions integrate programmatic critic",
        },
        "warnings": [w.message for w in warnings],
        "outcome": outcome,
        "release_status": manifest.get("status", "unknown"),
        "release_ratification": manifest.get("ratification", "pending"),
        "outputs": {
            "white_paper": str(output_dir / "white_paper.md"),
            "coverage": str(output_dir / "coverage.md"),
            "rc_log": str(output_dir / "rc_log.md"),
            "release_decision": str(output_dir / "release_decision.md"),
            "build_json": str(output_dir / "build.json"),
        },
    }

    (output_dir / "build.json").write_text(
        json.dumps(build, indent=2, ensure_ascii=False)
    )
    return build


# ── CLI entry point ───────────────────────────────────────────────────────────

def cmd_build(
    manifest_path: str | None = None,
    output_dir: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    project_root = Path.cwd()
    manifest_path_: Path = Path(manifest_path) if manifest_path else (
        project_root / "docs" / "builds" / "white_paper.compile.yaml"
    )
    output_dir_: Path = Path(output_dir) if output_dir else (
        project_root / "publication"
    )

    build_id = "unknown"
    stages: list[dict] = []
    all_warnings: list[BuildWarning] = []

    def _record(stage: str, status: str, detail: Any = None) -> None:
        stages.append({"stage": stage, "status": status, "detail": detail or {}})
        if verbose or status in ("fail", "warn"):
            icon = {"pass": "[green]PASS[/]", "warn": "[yellow]WARN[/]",
                    "fail": "[red]FAIL[/]", "manual": "[dim]MANUAL[/]",
                    "pending": "[dim]PENDING[/]"}.get(status, status)
            console.print(f"  {stage:<35} {icon}")

    try:
        # ── Header ────────────────────────────────────────────────────────────
        console.print(Rule(style="dim"))

        # Stage 1 — Load Manifest
        manifest = _stage_load_manifest(manifest_path_)
        build_id = manifest["build_id"]
        console.print(f"\n  [bold]herm build[/]  [cyan]{build_id}[/]\n")
        _record("load_manifest", "pass")

        # Stage 2 — Resolve Blueprint
        blueprint = _stage_resolve_blueprint(manifest, project_root)
        _record("blueprint", "pass",
                {"id": blueprint["id"], "status": blueprint["status"]})
        if not verbose:
            console.print(
                f"  [dim]Blueprint {blueprint['id']} ({blueprint['status']})[/]    "
                "[green]PASS[/]"
            )

        # Stage 3 — Resolve Tags
        resolved, tag_index, tag_warnings = _stage_resolve_tags(manifest, project_root)
        all_warnings.extend(tag_warnings)
        _record("resolve_artifacts", "pass" if not tag_warnings else "warn",
                {"count": len(resolved)})
        if not verbose:
            console.print(
                f"  [dim]Resolving {len(resolved)} artifacts...[/]           "
                "[green]PASS[/]"
            )

        # Stage 4 — Coverage Analysis
        coverage_results, cov_warnings = _stage_coverage(manifest, tag_index)
        all_warnings.extend(cov_warnings)
        n_pass = sum(1 for r in coverage_results if r["status"] == "PASS")
        n_warn = sum(1 for r in coverage_results if r["status"] == "WARN")
        n_fail = sum(1 for r in coverage_results if r["status"] == "FAIL")
        cov_status = "fail" if n_fail else ("warn" if n_warn else "pass")
        _record("coverage", cov_status,
                {"pass": n_pass, "warn": n_warn, "fail": n_fail})
        if not verbose:
            cov_icon = "[green]PASS[/]" if cov_status == "pass" else "[yellow]WARN[/]"
            console.print(
                f"  [dim]Coverage analysis...[/]               {cov_icon}  "
                f"[dim][{n_pass} PASS  {n_warn} WARN  {n_fail} FAIL][/]"
            )

        if dry_run:
            console.print("\n  [dim]Dry run — no outputs written.[/]")
            console.print(Rule(style="dim"))
            return

        # ── Prepare output directory (only on non-dry-run, before writing) ───
        output_dir_.mkdir(parents=True, exist_ok=True)

        # Stage 5 — Compile Sections
        compile_record = _stage_compile(manifest, project_root, output_dir_)
        _record("compile", "pass", compile_record)
        if not verbose:
            console.print(
                "  [dim]Compiling publication...[/]             [green]PASS[/]"
            )

        # Stage 6 — Critic Pass (manual in v0.1)
        _record("critic", "manual")
        if not verbose:
            console.print(
                "  [dim]Critic pass...[/]                       [dim]MANUAL (v0.1)[/]"
            )

        # Stage 7 — Steward Report
        _stage_steward_report(manifest, project_root, output_dir_, coverage_results)
        _record("steward_report", "pending")
        if not verbose:
            console.print(
                "  [dim]Steward report...[/]                    [dim]PENDING[/]"
            )

        # Stage 8 — Emit Build
        build_json = _emit_build_json(
            manifest=manifest,
            manifest_path=manifest_path_,
            blueprint=blueprint,
            resolved_artifacts=resolved,
            coverage_results=coverage_results,
            compile_record=compile_record,
            warnings=all_warnings,
            output_dir=output_dir_,
        )

        # ── Summary ───────────────────────────────────────────────────────────
        outcome = build_json["outcome"]
        console.print()
        console.print(Rule(style="dim"))
        console.print()
        console.print("  [bold green]Publication Build Complete[/]\n")
        console.print(f"  Outputs written to: [cyan]{output_dir_}/[/]")
        for name in ["white_paper.md", "coverage.md", "rc_log.md",
                     "release_decision.md", "build.json"]:
            console.print(f"    [dim]{name}[/]")

        console.print()
        status_str = (
            "[green]PASS[/]" if outcome == "pass"
            else f"[yellow]PASS with {len(all_warnings)} warning(s)[/]"
        )
        console.print(f"  Build status:   {status_str}")
        console.print(
            f"  Release status: [dim]{build_json['release_ratification']}[/]"
        )

        if all_warnings:
            console.print()
            for w in all_warnings:
                console.print(f"  [yellow]⚠[/]  {w.message}")

        console.print()
        console.print(Rule(style="dim"))

    except BuildError as exc:
        console.print()
        console.print(Rule(style="red"))
        console.print(f"\n  [bold red]Build failed[/]\n")
        console.print(f"  [red]ERROR:[/] {exc}\n")
        console.print("  [dim]No outputs written. Authoritative artifacts unchanged.[/]")
        console.print()
        console.print(Rule(style="red"))
        sys.exit(1)
