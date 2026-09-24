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
import os
import re
import secrets
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.rule import Rule

from hermeneia.build_core import InvalidRecord
from hermeneia.build_reproducibility import BINDING_NAME
from hermeneia.preservation_provenance import VerificationInputs

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

def _load_json(path: Path, label: str, inputs: VerificationInputs | None = None,
               role: str = "json") -> dict:
    if not (inputs.exists(path, role) if inputs else path.exists()):
        return {}
    try:
        data = json.loads(inputs.text(path, role) if inputs else path.read_text())
    except json.JSONDecodeError as exc:
        raise PreservationError(f"{label} malformed: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _load_manifest(manifest_rel: str, project_root: Path,
                   inputs: VerificationInputs | None = None) -> dict:
    path = project_root / manifest_rel
    if not (inputs.exists(path, "manifest-interpretation") if inputs else path.exists()):
        return {}
    try:
        data = yaml.safe_load(inputs.text(path, "manifest-interpretation") if inputs else path.read_text())
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


# ── Reconstruction verification ───────────────────────────────────────────────

def _verify_reconstruction(
    build: dict,
    coverage: dict,
    release: dict,
    project_root: Path,
    inputs: VerificationInputs | None = None,
    *,
    build_dir: Path | None = None,
) -> list[dict]:
    """Verify the lineage chain. Returns list of check results."""
    results: list[dict] = []

    _EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def _check(name: str, path: Path | None, expected_hash: str | None) -> dict:
        role = "reconstruction:" + name
        if path is None or not (inputs.exists(path, role) if inputs else path.exists()):
            return {"name": name, "status": "FAIL", "note": "Artifact not found"}
        # These artifacts are hashed by herm build. Observing a digest now cannot
        # replace the recorded build-time provenance needed for comparison.
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            return {
                "name": name,
                "status": "FAIL",
                "path": str(path),
                "note": "Missing or invalid build-time SHA-256 — integrity cannot be verified",
            }
        actual_hash = inputs.sha256(path, role) if inputs else _sha256(path)
        if actual_hash != expected_hash:
            return {
                "name": name,
                "status": "FAIL",
                "path": str(path),
                "note": "Hash mismatch — artifact modified since build",
                "hash_at_build": expected_hash,
                "hash_now": actual_hash,
            }
        if actual_hash == _EMPTY_SHA256:
            return {
                "name": name,
                "status": "WARN",
                "path": str(path),
                "sha256": actual_hash,
                "note": "Artifact is empty (0 bytes) — present and hash-valid but contains no content.",
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

    # Verify the emitted bytes, never the original compile source or a guessed
    # conventional path. Both the output path and digest come from build.json.
    outputs = build.get("outputs")
    compiled_path = outputs.get("white_paper") if isinstance(outputs, dict) else None
    compile_record = build.get("compile")
    compiled_hash = compile_record.get("sha256") if isinstance(compile_record, dict) else None
    if not isinstance(compiled_path, str) or not compiled_path:
        results.append({
            "name": "Compiled Artifact",
            "status": "FAIL",
            "note": "Missing or invalid outputs.white_paper in build.json — emitted artifact cannot be verified",
        })
    else:
        path = project_root / compiled_path
        try:
            results.append(_check("Compiled Artifact", path, compiled_hash))
        except OSError as exc:
            results.append({
                "name": "Compiled Artifact",
                "status": "FAIL",
                "path": str(path),
                "note": f"Cannot read compiled artifact: {exc}",
            })

    # Other pipeline outputs — existence only (no build-time hash recorded).
    build_dir = build_dir if build_dir is not None else project_root / "publication"
    for label, filename in [
        ("Coverage Record", "coverage.json"),
        ("Release Recommendation", "release_recommendation.json"),
    ]:
        p = build_dir / filename
        role = "reconstruction:" + label
        present = inputs.exists(p, role) if inputs else p.exists()
        results.append({
            "name": label,
            "status": "PASS" if present else "FAIL",
            "path": str(p),
            "sha256": (inputs.sha256(p, role) if inputs else _sha256(p)) if present else None,
            **({"note": "Artifact not found"} if not present else {}),
        })

    # F01: Coverage build_id cross-check — coverage must attest to the same build
    cov_build_id = coverage.get("build_id") if coverage else None
    bld_build_id = build.get("build_id")
    if coverage and cov_build_id and bld_build_id and cov_build_id != bld_build_id:
        results.append({
            "name": "Coverage Build ID",
            "status": "WARN",
            "note": (
                f"coverage.json was generated for build '{cov_build_id}' "
                f"but build.json identifies this build as '{bld_build_id}'. "
                "Re-run herm coverage to generate coverage for the current build."
            ),
        })

    # F02: Coverage corpus cross-check — coverage must not attest to artifacts absent from build
    if coverage:
        tag_index = coverage.get("tag_index", {})
        covered_paths: set[str] = {p for paths in tag_index.values() for p in paths}
        build_paths: set[str] = {a["path"] for a in build.get("source_artifacts", [])}
        ghost_paths = covered_paths - build_paths
        if ghost_paths:
            results.append({
                "name": "Coverage Corpus Integrity",
                "status": "WARN",
                "note": (
                    "coverage.json attests to artifact(s) not declared in build.json: "
                    + ", ".join(sorted(ghost_paths))
                    + ". Coverage may have been generated from a different corpus than this build."
                ),
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
    inputs: VerificationInputs | None = None,
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
    has_blueprint = bool(bp_path and (
        inputs.exists(bp_path, "continuation:Blueprint") if inputs else bp_path.exists()))
    results.append(_present("Blueprint", has_blueprint))

    if has_blueprint and bp_path:
        text = inputs.text(bp_path, "continuation:Blueprint") if inputs else bp_path.read_text()
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

@contextmanager
def _report_directory(path: Path):
    """Pin the checked output directory against later parent/symlink redirection."""
    resolved = path.resolve(strict=True)
    if (os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW")
            or not hasattr(os, "O_DIRECTORY")):
        # Such platforms cannot claim supported build-core provenance either.
        yield resolved, None
        return
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(resolved.anchor, flags)
    try:
        for component in resolved.parts[1:]:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield resolved, descriptor
    finally:
        os.close(descriptor)


def _write_report(path: Path, content: str, directory_fd: int | None = None) -> None:
    """Replace the report entry, never truncate a linked verification input."""
    raw = content.encode("utf-8")
    if directory_fd is not None:
        staged_name = ".herm-report-" + secrets.token_hex(16)

        def read_at(name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            with os.fdopen(fd, "rb") as stream:
                return stream.read()

        fd = os.open(staged_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
            if read_at(staged_name) != raw:
                raise PreservationError("Staged preservation report differs from intended bytes")
            os.replace(staged_name, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            if read_at(path.name) != raw:
                raise PreservationError("Installed preservation report differs from intended bytes")
        finally:
            try:
                os.unlink(staged_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        return
    staged = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".herm-report-", dir=path.parent, delete=False) as stream:
            staged = Path(stream.name)
            stream.write(raw)
            stream.flush()
        if staged.read_bytes() != raw:
            raise PreservationError("Staged preservation report differs from intended bytes")
        os.replace(staged, path)
        if path.read_bytes() != raw:
            raise PreservationError("Installed preservation report differs from intended bytes")
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


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
    provenance: dict | None = None,
    directory_fd: int | None = None,
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
    if provenance is not None:
        doc["provenance"] = provenance
    _write_report(output_dir / "preservation_report.json", json.dumps(doc, indent=2, ensure_ascii=False), directory_fd)
    return doc


def _emit_report_md(doc: dict, output_dir: Path, directory_fd: int | None = None) -> None:
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

    if "provenance" in doc:
        provenance = doc["provenance"]
        claim = provenance.get("build_core")
        detail = (f"{claim['profile']} `{claim['sha256']}`" if claim else
                  f"{provenance['integrity']} — {provenance['reason']}")
        lines.insert(3, f"**Build provenance:** {detail}  \n"
                     f"**Verification inputs:** `{provenance['inputs_sha256']}`  \n"
                     "_Exact input observations are recorded in preservation_report.json._\n\n")

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

    _write_report(output_dir / "preservation_report.md", "".join(lines), directory_fd)


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
    build_path: Path, project_root: Path, inputs: VerificationInputs | None = None,
) -> tuple[dict, dict, dict, dict]:
    if not (inputs.exists(build_path, "build-record") if inputs else build_path.exists()):
        raise PreservationError(f"build.json not found: {build_path}")
    build = _load_json(build_path, "build.json", inputs, "build-record")
    if not build:
        raise PreservationError(f"build.json is empty or malformed: {build_path}")

    build_dir = build_path.parent
    coverage_path = build_dir / "coverage.json"
    coverage = _load_json(coverage_path, "coverage.json", inputs, "coverage-interpretation")

    release_path = build_dir / "release_recommendation.json"
    release = _load_json(release_path, "release_recommendation.json", inputs, "release-interpretation")

    manifest_rel = build.get("manifest_path", "")
    manifest = _load_manifest(manifest_rel, project_root, inputs)

    return build, coverage, release, manifest


def _evaluate_verification(build_path: Path, project_root: Path,
                           inputs: VerificationInputs | None = None) -> tuple[dict, list, list, dict]:
    """Read-only evaluation shared by report generation and association checks."""
    inputs = inputs if inputs is not None else VerificationInputs(project_root)
    build_path = build_path if build_path.is_absolute() else inputs.root / build_path
    build_dir = build_path.parent
    try:
        namespace = build_dir.resolve()
        for path in (build_path, build_dir / BINDING_NAME, build_dir / "coverage.json",
                     build_dir / "release_recommendation.json"):
            inputs.require_sibling(path, namespace)
        build, coverage, release, manifest = _load_inputs(build_path, project_root, inputs)
        reconstruction = _verify_reconstruction(
            build, coverage, release, project_root, inputs, build_dir=build_dir)
    except (InvalidRecord, OSError, RuntimeError, ValueError) as exc:
        raise PreservationError(str(exc)) from exc
    continuation = _verify_continuation(build, manifest, release, project_root, inputs)
    return build, reconstruction, continuation, inputs.receipt(build_path)


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
        build, reconstruction, continuation, provenance = _evaluate_verification(build_path_, project_root)
        build_id = build.get("build_id", "unknown")
        console.print(f"\n  [bold]herm preserve verify[/]  [cyan]{build_id}[/]\n")

        console.print("  Reading build.json...          [green]PASS[/]")

        console.print("\n  Verifying lineage (Reconstruction)...\n")
        for r in reconstruction:
            icon = {"PASS": "[green]✓[/]", "WARN": "[yellow]⚠[/]",
                    "FAIL": "[red]✗[/]", "ADVISORY": "[dim]·[/]"}.get(r["status"], "?")
            name = r["name"]
            console.print(f"  {icon}  {name}")
            if r.get("note") and (verbose or r["status"] in ("FAIL", "WARN")):
                console.print(f"       [dim]{r['note']}[/]")

        console.print("\n  Checking continuation prerequisites...\n")
        for r in continuation:
            icon = {"PASS": "[green]✓[/]", "WARN": "[yellow]⚠[/]",
                    "FAIL": "[red]✗[/]", "ADVISORY": "[dim]·[/]"}.get(r["status"], "?")
            name = r["name"]
            console.print(f"  {icon}  {name}")
            if r.get("note") and (verbose or r["status"] in ("FAIL", "WARN")):
                console.print(f"       [dim]{r['note']}[/]")

        # A requested report destination must not overwrite evidence it evaluated.
        evidence_paths = {item["resolved_path"] for item in provenance["inputs"]}
        output_dir_.mkdir(parents=True, exist_ok=True)
        with _report_directory(output_dir_) as (report_dir, directory_fd):
            for name in ("preservation_report.json", "preservation_report.md"):
                target = report_dir / name
                if str(target) in evidence_paths or str(target.resolve()) in evidence_paths:
                    raise PreservationError("Report destination aliases a verification input")
            doc = _emit_report_json(build, reconstruction, continuation, report_dir, provenance, directory_fd)
            _emit_report_md(doc, report_dir, directory_fd)

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

        if overall != "fail":
            # Advisory: show edition cycle eligibility status
            try:
                from hermeneia.cli.edition_cmd import _load_cycles, _edition_status, _check_cycle_qualification
                pub_dir = output_dir_ if output_dir_ else project_root / "publication"
                store = _load_cycles(pub_dir)
                est = _edition_status(store)
                qual, _, _ = _check_cycle_qualification(pub_dir)
                if qual:
                    console.print(
                        f"  [dim]Edition:[/] {est['status_label']} "
                        f"({est['cycle_count']}/{est['minimum_required']} cycles)"
                    )
                    console.print(
                        "  [dim]Preservation is qualified. Run: herm edition record[/]"
                    )
                else:
                    console.print(
                        f"  [dim]Edition:{est['status_label']} — "
                        "not all pipeline stages are complete for edition cycle recording.[/]"
                    )
            except Exception:
                pass  # Edition advisory is non-blocking

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
