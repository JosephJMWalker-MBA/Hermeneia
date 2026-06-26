"""
herm preserve — Preservation Layer

Infrastructure for constitutional lineage. Two responsibilities:

  Reconstruction — Can I prove how this understanding came to exist?
                   Verifies lineage: Blueprint → Build → Coverage → Release

  Continuation  — Can another steward responsibly continue this investigation?
                  Verifies prerequisites: corpus, intent hypothesis, evidence
                  trail, steward history, constitutional references

Sprint 005 v0.1

Preservation Invariants:
    Preservation never changes authority.
    Preservation never edits artifacts.
    Preservation never performs restore.
    Preservation never creates canonical knowledge.

    Automation may: verify, hash, package, report.
    Automation may not: decide, ratify, restore authority.

Subcommands:
    herm preserve verify   — verify lineage and continuation prerequisites
    herm preserve export   — assemble preservation package to disk

Restore is constitutionally blocked in v0.1.
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


class PreservationError(Exception):
    """Raised when preservation cannot proceed. No outputs written."""


# ── Hash utility ──────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_json(path: Path, label: str) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise PreservationError(f"{label} malformed: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _load_manifest(manifest_rel: str, project_root: Path) -> dict:
    path = project_root / manifest_rel
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


# ── Reconstruction verification ───────────────────────────────────────────────

def _verify_reconstruction(
    build: dict,
    coverage: dict,
    release: dict,
    project_root: Path,
) -> list[dict]:
    """Verify the lineage chain. Returns list of check results."""
    results: list[dict] = []

    def _check(name: str, path: Path | None, expected_hash: str | None) -> dict:
        if path is None or not path.exists():
            return {"name": name, "status": "FAIL", "note": "Artifact not found"}
        actual_hash = _sha256(path)
        if expected_hash and actual_hash != expected_hash:
            return {
                "name": name,
                "status": "FAIL",
                "path": str(path),
                "note": "Hash mismatch — artifact modified since build",
                "hash_at_build": expected_hash,
                "hash_now": actual_hash,
            }
        return {
            "name": name,
            "status": "PASS",
            "path": str(path),
            "sha256": actual_hash,
        }

    # Blueprint
    bp_info = build.get("blueprint", {})
    bp_path_str = bp_info.get("path")
    bp_path = Path(bp_path_str) if bp_path_str else None
    results.append(_check("Blueprint", bp_path, bp_info.get("sha256")))

    # Compile manifest
    manifest_rel = build.get("manifest_path")
    if manifest_rel:
        manifest_path = project_root / manifest_rel
        results.append(_check("Compile Manifest", manifest_path, build.get("manifest_hash")))
    else:
        results.append({"name": "Compile Manifest", "status": "FAIL", "note": "manifest_path not in build.json"})

    # Source artifacts
    for artifact in build.get("source_artifacts", []):
        art_path = project_root / artifact["path"]
        results.append(_check(
            f"Source: {artifact['path']}",
            art_path,
            artifact.get("sha256"),
        ))

    # Pipeline outputs — these are checked for existence only (no hash in build.json for them)
    for label, path_str in [
        ("Build Record (build.json)", None),  # it's the entry point; already loaded
        ("Coverage Record", "publication/coverage.json"),
        ("Release Recommendation", "publication/release_recommendation.json"),
    ]:
        if path_str is None:
            continue
        p = project_root / path_str
        results.append({
            "name": label,
            "status": "PASS" if p.exists() else "FAIL",
            "path": str(p),
            "sha256": _sha256(p) if p.exists() else None,
            **({"note": "Artifact not found"} if not p.exists() else {}),
        })

    # Signature check — advisory
    sig = release.get("steward_signature")
    results.append({
        "name": "Steward Signature",
        "status": "ADVISORY" if sig is None else "PASS",
        "note": (
            "Release recommendation has not been signed by a human Steward. "
            "Reconstruction chain is complete but canonical publication requires signature."
            if sig is None else None
        ),
        "value": sig,
    })

    return results


# ── Continuation verification ─────────────────────────────────────────────────

def _verify_continuation(
    build: dict,
    manifest: dict,
    release: dict,
    project_root: Path,
) -> list[dict]:
    """Verify continuation prerequisites. Returns list of check results."""
    results: list[dict] = []

    def _present(name: str, exists: bool, note: str | None = None) -> dict:
        r: dict[str, Any] = {"name": name, "status": "PASS" if exists else "WARN"}
        if note:
            r["note"] = note
        return r

    # Blueprint (already checked in reconstruction; here we check intent hypothesis)
    bp_path_str = build.get("blueprint", {}).get("path")
    bp_path = Path(bp_path_str) if bp_path_str else None
    has_blueprint = bool(bp_path and bp_path.exists())
    results.append(_present("Blueprint", has_blueprint))

    if has_blueprint and bp_path:
        text = bp_path.read_text()
        has_intent = (
            "intent" in text.lower()
            or "hypothesis" in text.lower()
            or "governing question" in text.lower()
        )
        results.append(_present(
            "Intent Hypothesis",
            has_intent,
            note=None if has_intent else (
                "Blueprint does not appear to contain an intent hypothesis or governing question. "
                "A future steward may not know what reading drove this Blueprint."
            ),
        ))

    # Corpus — at least one source artifact with role evidence or primary-contract
    corpus_artifacts = [
        a for a in build.get("source_artifacts", [])
        if a.get("role") in ("evidence", "primary-contract", "provenance-record")
    ]
    results.append(_present(
        "Evidence Trail",
        len(corpus_artifacts) > 0,
        note=None if corpus_artifacts else "No evidence or primary-contract artifacts found in build.",
    ))

    # Sections declared
    sections = manifest.get("sections", [])
    results.append(_present(
        "Section Requirements",
        len(sections) > 0,
        note=None if sections else "Manifest declares no sections. Continuation scope is unclear.",
    ))

    # Research hypotheses / open questions
    research_artifacts = [
        a for a in build.get("source_artifacts", [])
        if "hypothesis" in a.get("tags", []) or "research-program" in a.get("tags", [])
    ]
    results.append(_present(
        "Research Hypotheses",
        len(research_artifacts) > 0,
        note=None if research_artifacts else (
            "No artifacts tagged 'hypothesis' or 'research-program'. "
            "Open questions may not be visible to a future steward."
        ),
    ))

    # Steward history (blueprint ratification)
    bp_status = build.get("blueprint_status", "unknown")
    results.append(_present(
        "Blueprint Ratification",
        bp_status == "ratified",
        note=None if bp_status == "ratified" else f"Blueprint status is '{bp_status}' — not ratified.",
    ))

    # Release recommendation present and outcome verified
    rel_outcome = release.get("outcome") if release else None
    if rel_outcome == "RECOMMEND_RELEASE":
        rel_status, rel_note = "PASS", None
    elif release:
        rel_status = "WARN"
        rel_note = (
            f"Release recommendation outcome is '{rel_outcome}', not RECOMMEND_RELEASE. "
            "A future steward should review before continuing."
        )
    else:
        rel_status, rel_note = "WARN", "release_recommendation.json not found."
    rec_result: dict[str, Any] = {
        "name": "Release Recommendation",
        "status": rel_status,
        "outcome": rel_outcome,
    }
    if rel_note:
        rec_result["note"] = rel_note
    results.append(rec_result)

    # Steward notes (advisory — nice to have for future steward)
    steward_notes = release.get("steward_notes")
    results.append({
        "name": "Steward Notes",
        "status": "ADVISORY" if not steward_notes else "PASS",
        "note": (
            "No steward notes recorded in release_recommendation.json. "
            "A future steward will not have context on why this recommendation was made."
            if not steward_notes else None
        ),
    })

    return results


# ── Report emission ───────────────────────────────────────────────────────────

def _summarize(results: list[dict]) -> dict:
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_warn = sum(1 for r in results if r["status"] == "WARN")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_advisory = sum(1 for r in results if r["status"] == "ADVISORY")
    outcome = (
        "fail" if n_fail > 0
        else "warn" if n_warn > 0
        else "pass"
    )
    return {
        "pass": n_pass, "warn": n_warn, "fail": n_fail, "advisory": n_advisory,
        "outcome": outcome,
    }


def _emit_report_json(
    build: dict,
    reconstruction: list[dict],
    continuation: list[dict],
    output_dir: Path,
) -> dict:
    r_summary = _summarize(reconstruction)
    c_summary = _summarize(continuation)
    overall = "fail" if (r_summary["outcome"] == "fail" or c_summary["outcome"] == "fail") else (
        "warn" if (r_summary["outcome"] == "warn" or c_summary["outcome"] == "warn") else "pass"
    )
    doc = {
        "preservation_engine_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_id": build.get("build_id", "unknown"),
        "reconstruction": {
            "summary": r_summary,
            "checks": reconstruction,
        },
        "continuation": {
            "summary": c_summary,
            "checks": continuation,
        },
        "overall_outcome": overall,
        "note": (
            "Restoration is constitutionally deferred in v0.1. "
            "This report verifies lineage and continuation prerequisites only."
        ),
    }
    (output_dir / "preservation_report.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False)
    )
    return doc


def _emit_report_md(doc: dict, output_dir: Path) -> None:
    build_id = doc["build_id"]
    r = doc["reconstruction"]
    c = doc["continuation"]
    rs = r["summary"]
    cs = c["summary"]

    lines = [
        "# Preservation Report\n\n",
        f"**Build:** {build_id}  \n",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n\n",
        "---\n\n",
        "## Reconstruction\n\n",
        "_Can I prove how this understanding came to exist?_\n\n",
        f"| PASS | WARN | FAIL | Advisory |\n",
        f"|------|------|------|----------|\n",
        f"| {rs['pass']} | {rs['warn']} | {rs['fail']} | {rs['advisory']} |\n\n",
    ]

    for check in r["checks"]:
        icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "ADVISORY": "·"}.get(check["status"], "?")
        lines.append(f"- {icon} **{check['name']}**")
        if check.get("note"):
            lines.append(f"  — _{check['note']}_")
        lines.append("\n")

    lines += [
        "\n---\n\n",
        "## Continuation\n\n",
        "_Can another steward responsibly continue this investigation?_\n\n",
        f"| PASS | WARN | FAIL | Advisory |\n",
        f"|------|------|------|----------|\n",
        f"| {cs['pass']} | {cs['warn']} | {cs['fail']} | {cs['advisory']} |\n\n",
    ]

    for check in c["checks"]:
        icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "ADVISORY": "·"}.get(check["status"], "?")
        lines.append(f"- {icon} **{check['name']}**")
        if check.get("note"):
            lines.append(f"  — _{check['note']}_")
        lines.append("\n")

    outcome = doc["overall_outcome"].upper()
    lines += [
        "\n---\n\n",
        f"## Overall: {outcome}\n\n",
        "_Restoration is constitutionally deferred in v0.1._  \n",
        "_This report verifies lineage and continuation prerequisites only._\n",
    ]

    (output_dir / "preservation_report.md").write_text("".join(lines))


# ── Export ────────────────────────────────────────────────────────────────────

def _run_export(
    build: dict,
    project_root: Path,
    output_dir: Path,
    verbose: bool,
) -> None:
    """Assemble preservation package: copy all artifacts, write manifest.json."""
    pkg_dir = output_dir / "preservation_package"
    artifacts_dir = pkg_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[dict] = []
    hash_mismatches: list[str] = []
    missing_artifacts: list[str] = []

    def _copy_artifact(src: Path, dest_name: str, expected_hash: str | None) -> dict:
        if not src.exists():
            missing_artifacts.append(str(src))
            return {"path": dest_name, "status": "MISSING"}
        actual_hash = _sha256(src)
        mismatch = expected_hash is not None and actual_hash != expected_hash
        dest = artifacts_dir / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        entry: dict = {
            "original_path": str(src),
            "preserved_as": str(dest.relative_to(pkg_dir)),
            "sha256": actual_hash,
            "status": "FAIL" if mismatch else "PASS",
        }
        if mismatch:
            entry["sha256_at_build"] = expected_hash
            entry["note"] = "Hash mismatch — artifact modified since build"
            hash_mismatches.append(str(src))
        return entry

    # Blueprint
    bp_path_str = build.get("blueprint", {}).get("path")
    if bp_path_str:
        entry = _copy_artifact(Path(bp_path_str), "blueprint.md", build["blueprint"].get("sha256"))
        manifest_entries.append(entry)
        if verbose:
            console.print(f"  [dim]blueprint.md[/]  {entry['status']}")

    # Compile manifest
    manifest_rel = build.get("manifest_path")
    if manifest_rel:
        mp = project_root / manifest_rel
        entry = _copy_artifact(mp, "compile_manifest.yaml", build.get("manifest_hash"))
        manifest_entries.append(entry)
        if verbose:
            console.print(f"  [dim]compile_manifest.yaml[/]  {entry['status']}")

    # Source artifacts
    for artifact in build.get("source_artifacts", []):
        src = project_root / artifact["path"]
        dest_name = "source/" + artifact["path"].replace("/", "_")
        entry = _copy_artifact(src, dest_name, artifact.get("sha256"))
        manifest_entries.append(entry)
        if verbose:
            console.print(f"  [dim]{dest_name}[/]  {entry['status']}")

    # Pipeline outputs
    for label, rel in [
        ("build.json", "publication/build.json"),
        ("coverage.json", "publication/coverage.json"),
        ("release_recommendation.json", "publication/release_recommendation.json"),
    ]:
        src = project_root / rel
        entry = _copy_artifact(src, label, None)
        manifest_entries.append(entry)
        if verbose:
            console.print(f"  [dim]{label}[/]  {entry.get('status', 'OK')}")

    if missing_artifacts or hash_mismatches:
        msg_parts = []
        if missing_artifacts:
            msg_parts.append(
                "Missing artifacts (absent from filesystem):\n"
                + "\n".join(f"  {p}" for p in missing_artifacts)
            )
        if hash_mismatches:
            msg_parts.append(
                "Hash mismatches (modified since build):\n"
                + "\n".join(f"  {p}" for p in hash_mismatches)
            )
        raise PreservationError(
            "Preservation halted — artifacts cannot be verified.\n"
            + "\n".join(msg_parts)
            + "\nA preservation package with missing or modified artifacts would misrepresent the investigation."
        )

    # Write manifest.json
    pkg_manifest = {
        "preservation_engine_version": "0.1.0",
        "build_id": build.get("build_id", "unknown"),
        "packaged_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": manifest_entries,
        "hash_mismatches": len(hash_mismatches),
        "note": (
            "This package contains copies of all declared artifacts at time of preservation. "
            "Verify each artifact's sha256 independently of this system."
        ),
    }
    (pkg_dir / "manifest.json").write_text(
        json.dumps(pkg_manifest, indent=2, ensure_ascii=False)
    )


# ── CLI entry points ──────────────────────────────────────────────────────────

def _load_inputs(
    build_path: Path, project_root: Path
) -> tuple[dict, dict, dict, dict]:
    if not build_path.exists():
        raise PreservationError(f"build.json not found: {build_path}")
    build = _load_json(build_path, "build.json")
    if not build:
        raise PreservationError(f"build.json is empty or malformed: {build_path}")

    build_dir = build_path.parent
    coverage_path = build_dir / "coverage.json"
    coverage = _load_json(coverage_path, "coverage.json")

    release_path = build_dir / "release_recommendation.json"
    release = _load_json(release_path, "release_recommendation.json")

    manifest_rel = build.get("manifest_path", "")
    manifest = _load_manifest(manifest_rel, project_root)

    return build, coverage, release, manifest


def cmd_preserve_verify(
    build_path: str | None = None,
    output_dir: str | None = None,
    verbose: bool = False,
) -> None:
    project_root = Path.cwd()
    build_path_ = Path(build_path) if build_path else project_root / "publication" / "build.json"
    output_dir_ = Path(output_dir) if output_dir else project_root / "publication"

    try:
        console.print(Rule(style="dim"))
        build, coverage, release, manifest = _load_inputs(build_path_, project_root)
        build_id = build.get("build_id", "unknown")
        console.print(f"\n  [bold]herm preserve verify[/]  [cyan]{build_id}[/]\n")

        console.print("  Reading build.json...          [green]PASS[/]")

        console.print("\n  Verifying lineage (Reconstruction)...\n")
        reconstruction = _verify_reconstruction(build, coverage, release, project_root)
        for r in reconstruction:
            icon = {"PASS": "[green]✓[/]", "WARN": "[yellow]⚠[/]",
                    "FAIL": "[red]✗[/]", "ADVISORY": "[dim]·[/]"}.get(r["status"], "?")
            name = r["name"]
            console.print(f"  {icon}  {name}")
            if r.get("note") and (verbose or r["status"] in ("FAIL", "WARN")):
                console.print(f"       [dim]{r['note']}[/]")

        console.print("\n  Checking continuation prerequisites...\n")
        continuation = _verify_continuation(build, manifest, release, project_root)
        for r in continuation:
            icon = {"PASS": "[green]✓[/]", "WARN": "[yellow]⚠[/]",
                    "FAIL": "[red]✗[/]", "ADVISORY": "[dim]·[/]"}.get(r["status"], "?")
            name = r["name"]
            console.print(f"  {icon}  {name}")
            if r.get("note") and (verbose or r["status"] in ("FAIL", "WARN")):
                console.print(f"       [dim]{r['note']}[/]")

        output_dir_.mkdir(parents=True, exist_ok=True)
        doc = _emit_report_json(build, reconstruction, continuation, output_dir_)
        _emit_report_md(doc, output_dir_)

        r_sum = doc["reconstruction"]["summary"]
        c_sum = doc["continuation"]["summary"]
        overall = doc["overall_outcome"]

        console.print()
        console.print(Rule(style="dim"))
        console.print()

        if overall == "pass":
            outcome_str = "[green]PASS[/]"
        elif overall == "warn":
            outcome_str = "[yellow]WARN[/]"
        else:
            outcome_str = "[red]FAIL[/]"

        console.print(f"  Preservation: [cyan]{build_id}[/]  {outcome_str}\n")
        console.print(f"    Reconstruction:  [green]{r_sum['pass']} PASS[/]"
                      + (f"  [yellow]{r_sum['warn']} WARN[/]" if r_sum['warn'] else "")
                      + (f"  [red]{r_sum['fail']} FAIL[/]" if r_sum['fail'] else ""))
        console.print(f"    Continuation:    [green]{c_sum['pass']} PASS[/]"
                      + (f"  [yellow]{c_sum['warn']} WARN[/]" if c_sum['warn'] else "")
                      + (f"  [red]{c_sum['fail']} FAIL[/]" if c_sum['fail'] else ""))
        console.print()
        console.print("  [dim]preservation_report.json written.[/]")
        console.print("  [dim]preservation_report.md written.[/]")
        console.print()
        console.print(Rule(style="dim"))

        if overall == "fail":
            sys.exit(1)

    except PreservationError as exc:
        console.print()
        console.print(Rule(style="red"))
        console.print("\n  [bold red]Preservation failed[/]\n")
        console.print(f"  [red]ERROR:[/] {exc}\n")
        console.print("  [dim]No outputs written.[/]")
        console.print()
        console.print(Rule(style="red"))
        sys.exit(1)


def cmd_preserve_export(
    build_path: str | None = None,
    output_dir: str | None = None,
    verbose: bool = False,
) -> None:
    project_root = Path.cwd()
    build_path_ = Path(build_path) if build_path else project_root / "publication" / "build.json"
    output_dir_ = Path(output_dir) if output_dir else project_root / "preservation"

    try:
        console.print(Rule(style="dim"))
        build, coverage, release, manifest = _load_inputs(build_path_, project_root)
        build_id = build.get("build_id", "unknown")
        console.print(f"\n  [bold]herm preserve export[/]  [cyan]{build_id}[/]\n")

        n_artifacts = len(build.get("source_artifacts", [])) + 5  # +5 for pipeline outputs
        console.print(f"  Assembling preservation package...  [{n_artifacts} artifacts]\n")

        _run_export(build, project_root, output_dir_, verbose)

        console.print()
        console.print(Rule(style="dim"))
        console.print()
        console.print(f"  Preservation package written.")
        console.print(f"  [dim]preservation_package/ contains all declared artifacts.[/]")
        console.print(f"  [dim]Each artifact is independently verifiable by SHA-256.[/]")
        console.print()
        console.print(Rule(style="dim"))

    except PreservationError as exc:
        console.print()
        console.print(Rule(style="red"))
        console.print("\n  [bold red]Export failed[/]\n")
        console.print(f"  [red]ERROR:[/] {exc}\n")
        console.print()
        console.print(Rule(style="red"))
        sys.exit(1)
