"""Child-process runner for Publication Compositor's ``EditorialLocalJob``.

This file is executed by a *configured Publication Compositor Python*, not by
Hermeneia's interpreter, and deliberately imports nothing from Hermeneia. It is
an invocation adapter only: it marshals declared, hash-checked JSON artifacts
into Compositor's own facade and marshals Compositor's own results back out.
It holds no editorial policy of its own — every validation, replay, refusal and
proof decision is made by Compositor code.

Usage::

    <compositor-python> compositor_runner.py REQUEST.json RESULT.json

``EditorialLocalJob`` is an in-memory value rooted at C0. The runner rebuilds
the exact current job by replaying the stored approved revision records in
order through ``apply_approved`` and requiring every replayed receipt to equal
the stored receipt byte for byte. History is never reconstructed any other way.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

RUNNER_PROTOCOL = "hermeneia-compositor-runner/0.1"
OPERATIONS = ("inspect", "validate", "apply", "proof", "prepare")
WORK_MANIFEST = "compositor-work.json"
WORK_MANIFEST_SCHEMA = "hermeneia-compositor-work/0.1"

# Compositor modules whose exact source bytes define the pinned facade.
_PIN_MODULES = (
    "editorial_job.py",
    "editorial_revisions.py",
    "editorial_versions.py",
    "editorial_construction.py",
    "renderers/typst/editorial_bundle.py",
)


class RunnerRefusal(Exception):
    """A typed refusal returned to Hermeneia instead of a traceback."""

    def __init__(self, code: str, message: str, findings: list[dict] | None = None, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.findings = findings or []
        self.stage = stage


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _scoped(root: Path, relative: str) -> Path:
    """Resolve ``relative`` inside ``root``; refuse absolute, traversal and symlink escape."""
    if not relative or Path(relative).is_absolute():
        raise RunnerRefusal("RUNNER_PATH_REFUSED", f"artifact path must be relative: {relative!r}")
    candidate = (root / relative)
    resolved = candidate.resolve()
    if root.resolve() not in resolved.parents and resolved != root.resolve():
        raise RunnerRefusal("RUNNER_PATH_REFUSED", f"artifact path escapes the work directory: {relative!r}")
    if candidate.is_symlink():
        raise RunnerRefusal("RUNNER_PATH_REFUSED", f"artifact path is a symlink: {relative!r}")
    return resolved


def _read_declared(root: Path, entry: dict) -> bytes:
    path = _scoped(root, str(entry.get("path") or ""))
    if not path.is_file():
        raise RunnerRefusal("RUNNER_ARTIFACT_MISSING", f"declared artifact is missing: {entry.get('path')}")
    data = path.read_bytes()
    if _sha256(data) != entry.get("sha256"):
        raise RunnerRefusal("RUNNER_ARTIFACT_HASH_MISMATCH", f"declared artifact hash differs: {entry.get('path')}")
    return data


def facade_pin() -> dict:
    import publication_compositor
    from publication_compositor.editorial_job import EDITORIAL_LOCAL_JOB_SCHEMA_VERSION

    package_dir = Path(publication_compositor.__file__).resolve().parent
    digests = {}
    for relative in _PIN_MODULES:
        digests[relative] = _sha256((package_dir / relative).read_bytes())
    return {
        "editorial_local_job_schema_version": EDITORIAL_LOCAL_JOB_SCHEMA_VERSION,
        "module_sha256": digests,
        "facade_sha256": _sha256(_canonical(digests).encode("utf-8")),
    }


def _load_job(request: dict, work_dir: Path):
    from publication_compositor.canonical import CanonicalPublication
    from publication_compositor.construction import ConstructionPlan
    from publication_compositor.editorial_job import EditorialLocalJob
    from publication_compositor.ir import DocumentIR
    from publication_compositor.profiles import PublicationProfile, ResolvedLayoutPlan
    from publication_compositor.renderers.typst import build_typst_renderer_environment
    from publication_compositor.renderers.typst.fonts import hash_typst_renderer_environment

    inputs = request.get("inputs") or {}
    required = ("source_ir", "canonical_c0", "construction", "profile", "resolved_layout")
    missing = [name for name in required if name not in inputs]
    if missing:
        raise RunnerRefusal("RUNNER_INPUT_MISSING", "missing work inputs: " + ", ".join(missing))

    source = DocumentIR.model_validate_json(_read_declared(work_dir, inputs["source_ir"]))
    c0 = CanonicalPublication.model_validate_json(_read_declared(work_dir, inputs["canonical_c0"]))
    construction = ConstructionPlan.model_validate_json(_read_declared(work_dir, inputs["construction"]))
    profile = PublicationProfile.model_validate_json(_read_declared(work_dir, inputs["profile"]))
    resolved = ResolvedLayoutPlan.model_validate_json(_read_declared(work_dir, inputs["resolved_layout"]))

    environment = None
    fonts = inputs.get("fonts") or []
    if fonts:
        font_paths = []
        for entry in fonts:
            _read_declared(work_dir, entry)  # hash check before Compositor reads it
            font_paths.append(_scoped(work_dir, entry["path"]))
        environment = build_typst_renderer_environment(resolved, font_paths, profile=profile)
        expected_env = request.get("expected_renderer_environment_sha256")
        observed_env = hash_typst_renderer_environment(environment)
        if expected_env and expected_env != observed_env:
            raise RunnerRefusal(
                "RUNNER_RENDERER_ENVIRONMENT_MISMATCH",
                "rebuilt renderer environment differs from the attached work's environment",
            )

    try:
        job = EditorialLocalJob.create(
            source, c0, construction, profile, resolved, renderer_environment=environment
        )
    except ValueError as exc:
        raise RunnerRefusal("RUNNER_WORK_NOT_VERIFIED", str(exc)) from exc
    return job


def _replay(job, request: dict, work_dir: Path):
    from publication_compositor.editorial_revisions import EditorialRevisionRecord

    for index, item in enumerate(request.get("history") or []):
        record = EditorialRevisionRecord.model_validate_json(
            _read_declared(work_dir, {"path": item["record_path"], "sha256": item["record_sha256"]})
        )
        try:
            job, result = job.apply_approved(
                record,
                expected_parent_ref=item["expected_parent_ref"],
                idempotency_key=item["idempotency_key"],
            )
        except ValueError as exc:
            raise RunnerRefusal("RUNNER_HISTORY_REPLAY_REFUSED", f"history item {index}: {exc}") from exc
        replayed = _sha256(result.receipt.model_dump_json().encode("utf-8"))
        if replayed != item["receipt_sha256"]:
            raise RunnerRefusal(
                "RUNNER_HISTORY_DIVERGED",
                f"history item {index}: replayed receipt differs from the stored receipt",
            )
    return job


def _envelope(operation: str, payload) -> dict:
    from publication_compositor.editorial_job import (
        build_editorial_job_envelope,
        verify_editorial_job_envelope,
    )

    envelope = build_editorial_job_envelope(operation, payload)
    report = verify_editorial_job_envelope(envelope)
    if not report.passed:
        raise RunnerRefusal("RUNNER_ENVELOPE_INVALID", "Compositor refused its own envelope")
    return json.loads(envelope.model_dump_json())


def _findings(items) -> list[dict]:
    return [{"code": f.code, "message": f.message, "ids": list(f.ids)} for f in items]


def _typed_findings(items) -> list[dict]:
    out = []
    for item in items or ():
        ids = getattr(item, "ids", None)
        if ids is None:
            ids = tuple(value for value in (getattr(item, "block_id", None), getattr(item, "revision_id", None)) if value)
        out.append({"code": str(getattr(item, "code", "FINDING")), "message": str(getattr(item, "message", "")), "ids": list(ids or ())})
    return out


def _prepare(request: dict, pin: dict) -> dict:
    """Prepare a verified S1 work from one source PDF using Compositor's own pipeline.

    Every step is a Compositor builder followed by its verifier. Any refusal is
    returned with Compositor's findings and the stage that refused; nothing is
    inferred, relaxed or retried with different semantic/layout choices.
    """
    from publication_compositor.canonical.pipeline import canonicalize_classified_document
    from publication_compositor.classify import classify_document
    from publication_compositor.construction import (
        build_publication_construction_plan,
        verify_construction_plan,
    )
    from publication_compositor.editorial_job import EditorialLocalJob
    from publication_compositor.ingest.extract import extract_pdf
    from publication_compositor.profiles import (
        PublicationProfile,
        resolve_layout_plan,
        verify_resolved_layout_plan,
    )
    from publication_compositor.profiles.verify import verify_profile_for_construction
    from publication_compositor.renderers.typst import build_typst_renderer_environment
    from publication_compositor.renderers.typst.fonts import hash_typst_renderer_environment
    from publication_compositor.verify import verify_source

    source_pdf = Path(request["source_pdf"])
    expected = request["expected_source_sha256"]
    output_dir = Path(request["output_dir"])
    if output_dir.exists():
        raise RunnerRefusal("PREPARATION_OUTPUT_EXISTS", "preparation staging directory already exists")
    source_bytes = source_pdf.read_bytes()
    if _sha256(source_bytes) != expected:
        raise RunnerRefusal("PREPARATION_SOURCE_HASH_MISMATCH", "source bytes differ from the workspace source identity", stage="source")
    profile_bytes = Path(request["profile_path"]).read_bytes()
    font_paths = sorted(
        path for path in Path(request["fonts_dir"]).iterdir()
        if path.is_file() and path.suffix.lower() in {".ttf", ".otf"}
    )
    if not font_paths:
        raise RunnerRefusal("PREPARATION_FONTS_MISSING", "the configured font directory has no .ttf/.otf files", stage="renderer_environment")

    stages: list[dict] = []
    source = extract_pdf(source_pdf)
    if source.manifest.source_pdf_sha256 != expected:
        raise RunnerRefusal("PREPARATION_SOURCE_IDENTITY_MISMATCH", "Compositor extracted a different source identity", stage="extract")
    stages.append({"stage": "extract", "pages": source.manifest.page_count, "blocks": len(source.blocks)})
    source_report = verify_source(source)
    if not source_report.passed:
        raise RunnerRefusal("PREPARATION_SOURCE_NOT_VERIFIED", "Compositor did not verify the extracted source",
                            _typed_findings(source_report.findings), stage="verify_source")
    classified, _metrics = classify_document(source)
    c0, canonical_report = canonicalize_classified_document(classified)
    stages.append({"stage": "canonicalize", "units": len(c0.units), "unresolved": canonical_report.unresolved_count,
                   "passed": canonical_report.passed, "export_ready": canonical_report.export_ready})
    if not canonical_report.passed:
        raise RunnerRefusal("PREPARATION_CANONICAL_NOT_VERIFIED", "Compositor did not verify the canonical publication",
                            _typed_findings(canonical_report.findings), stage="canonicalize")
    if not canonical_report.export_ready:
        # Name each unresolved block by Compositor's own identity and page only;
        # classifier evidence strings can quote source text, so they stay out.
        page_by_block = {block.id: block.page_number for block in classified.blocks}
        unresolved = [
            {
                "code": "COMPOSITOR_UNRESOLVED_SOURCE_BLOCK",
                "message": f"page {page_by_block.get(item.source_block_id, '?')} · policy {item.policy_version}",
                "ids": [item.source_block_id],
            }
            for item in c0.manifest.source_dispositions
            if str(item.disposition) == "unresolved"
        ]
        raise RunnerRefusal(
            "PREPARATION_CANONICAL_NOT_EXPORT_READY",
            f"Compositor reports {canonical_report.unresolved_count} unresolved source block(s); "
            "authoring needs an export-ready canonical root and these need human review.",
            [*_typed_findings(canonical_report.findings), *unresolved], stage="canonicalize",
        )
    construction = build_publication_construction_plan(classified, c0)
    construction_report = verify_construction_plan(classified, c0, construction)
    if not construction_report.passed:
        raise RunnerRefusal("PREPARATION_CONSTRUCTION_NOT_VERIFIED", "Compositor did not verify the construction plan",
                            _typed_findings(construction_report.findings), stage="construction")
    profile = PublicationProfile.model_validate_json(profile_bytes)
    profile_report = verify_profile_for_construction(construction, profile)
    if not profile_report.passed:
        raise RunnerRefusal("PREPARATION_PROFILE_REFUSED", "Compositor refused the configured profile for this work",
                            _typed_findings(profile_report.findings), stage="profile")
    try:
        resolved = resolve_layout_plan(classified, c0, construction, profile)
    except ValueError as exc:
        raise RunnerRefusal("PREPARATION_LAYOUT_REFUSED", str(exc), stage="layout") from exc
    layout_report = verify_resolved_layout_plan(classified, c0, construction, profile, resolved)
    if not layout_report.passed:
        raise RunnerRefusal("PREPARATION_LAYOUT_NOT_VERIFIED", "Compositor did not verify the resolved layout",
                            _typed_findings(layout_report.findings), stage="layout")

    output_dir.mkdir(parents=True)
    (output_dir / "fonts").mkdir()
    staged_fonts = []
    for path in font_paths:
        target = output_dir / "fonts" / path.name
        target.write_bytes(path.read_bytes())
        staged_fonts.append(target)
    try:
        environment = build_typst_renderer_environment(resolved, staged_fonts, profile=profile)
    except ValueError as exc:
        raise RunnerRefusal("PREPARATION_RENDERER_ENVIRONMENT_REFUSED", str(exc), stage="renderer_environment") from exc
    try:
        EditorialLocalJob.create(classified, c0, construction, profile, resolved, renderer_environment=environment)
    except ValueError as exc:
        raise RunnerRefusal("PREPARATION_NOT_AUTHORABLE", str(exc), stage="editorial_job") from exc

    files = {
        "source_ir": ("source_ir.json", classified.model_dump_json()),
        "canonical_c0": ("canonical_c0.json", c0.model_dump_json()),
        "construction": ("construction.json", construction.model_dump_json()),
        "profile": ("profile.json", profile.model_dump_json()),
        "resolved_layout": ("resolved_layout.json", resolved.model_dump_json()),
    }
    inputs: dict = {}
    for kind, (name, text) in files.items():
        data = text.encode("utf-8")
        (output_dir / name).write_bytes(data)
        inputs[kind] = {"path": name, "sha256": _sha256(data)}
    inputs["fonts"] = [{"path": "fonts/" + p.name, "sha256": _sha256(p.read_bytes())} for p in staged_fonts]
    provenance = {
        **(request.get("provenance") or {}),
        "source_sha256": expected,
        "source_ir_source_pdf_sha256": source.manifest.source_pdf_sha256,
        "profile_sha256": _sha256(profile_bytes),
        "profile_id": profile.profile_id,
        "profile_revision": profile.revision,
        "font_sha256": [entry["sha256"] for entry in inputs["fonts"]],
        "compositor_facade_sha256": pin["facade_sha256"],
        "stages": stages,
    }
    provenance_bytes = _canonical(provenance).encode("utf-8")
    (output_dir / "preparation_provenance.json").write_bytes(provenance_bytes)
    inputs["preparation_provenance"] = {"path": "preparation_provenance.json", "sha256": _sha256(provenance_bytes)}
    manifest = {
        "schema": WORK_MANIFEST_SCHEMA,
        "label": (request.get("provenance") or {}).get("source_filename") or source_pdf.name,
        "synthetic": False,
        "inputs": inputs,
        "renderer_environment_sha256": hash_typst_renderer_environment(environment),
        "profile": {"id": profile.profile_id, "revision": profile.revision,
                    "page_pt": [profile.page.width_pt, profile.page.height_pt]},
    }
    (output_dir / WORK_MANIFEST).write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"operation": "prepare", "pin": pin, "status": "ok", "findings": [], "stages": stages}


def run(request: dict) -> dict:
    from publication_compositor.editorial_revisions import (
        EditorialRevisionDecision,
        EditorialRevisionRecord,
    )

    operation = request.get("operation")
    if request.get("protocol") != RUNNER_PROTOCOL:
        raise RunnerRefusal("RUNNER_PROTOCOL_MISMATCH", f"unsupported protocol {request.get('protocol')!r}")
    if operation not in OPERATIONS:
        raise RunnerRefusal("RUNNER_OPERATION_UNSUPPORTED", f"unsupported operation {operation!r}")

    pin = facade_pin()
    if operation == "prepare":
        return _prepare(request, pin)
    expected_pin = request.get("expected_facade_sha256")
    if expected_pin and expected_pin != pin["facade_sha256"]:
        raise RunnerRefusal(
            "RUNNER_FACADE_PIN_MISMATCH",
            "configured Compositor facade differs from the one this work was attached with",
        )

    work_dir = Path(request["work_dir"])
    job = _replay(_load_job(request, work_dir), request, work_dir)
    snapshot = job.inspect()
    out: dict = {"operation": operation, "pin": pin, "status": "ok", "findings": []}
    out["snapshot"] = _envelope("inspect", snapshot)

    if operation == "inspect":
        return out

    if operation in ("validate", "apply"):
        record = EditorialRevisionRecord.model_validate(request["record"])
        expected_parent = request["expected_parent_ref"]
        key = request.get("idempotency_key")
        if operation == "apply" and key and any(
            prior.receipt.idempotency_key == key for prior in job.accepted_results
        ):
            # Compositor's own idempotency path: an identical retry returns the
            # recorded result; a conflicting reuse of the key refuses.
            try:
                _same, prior = job.apply_approved(record, expected_parent_ref=expected_parent, idempotency_key=key)
            except ValueError as exc:
                out["status"] = "refused"
                out["findings"] = [{"code": "EDITORIAL_JOB_IDEMPOTENCY_CONFLICT", "message": str(exc), "ids": [record.id]}]
                return out
            out["idempotent_replay"] = True
            out["accepted"] = {
                "receipt_json": prior.receipt.model_dump_json(),
                "version_json": prior.version.model_dump_json(),
            }
            return out
        validation = job.validate_proposal(record, expected_parent_ref=expected_parent)
        out["validation"] = _envelope("validate_proposal", validation)
        findings = _findings(validation.findings)
        if validation.passed:
            # Construction eligibility is only decided when Compositor builds the
            # overlay, so run its own apply path on an approved copy and discard it.
            probe = record
            if record.decision is not EditorialRevisionDecision.APPROVED:
                # Re-validate through Compositor's model so the decision fields are
                # real typed values (model_copy(update=...) would skip validation).
                probe = EditorialRevisionRecord.model_validate(
                    {**record.model_dump(mode="json"), **(request.get("dry_run_approval") or {})}
                )
            try:
                applied_job, result = job.apply_approved(
                    probe,
                    expected_parent_ref=expected_parent,
                    idempotency_key=request.get("idempotency_key") or "hermeneia-dry-run",
                )
            except ValueError as exc:
                findings.append({"code": "EDITORIAL_JOB_APPLY_REFUSED", "message": str(exc), "ids": [record.id]})
            else:
                if operation == "apply":
                    out["accepted"] = {
                        "receipt_json": result.receipt.model_dump_json(),
                        "version_json": result.version.model_dump_json(),
                        "ledger_json": applied_job.ledger.model_dump_json(),
                        "overlay_json": applied_job.overlay.model_dump_json(),
                    }
                    out["snapshot"] = _envelope("inspect", applied_job.inspect())
        out["findings"] = findings
        if findings:
            out["status"] = "refused"
        return out

    # proof
    output_dir = Path(request["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    _job, result = job.rebuild_proof(
        output_dir, typst_executable=request.get("typst_executable") or "typst"
    )
    out["proof"] = _envelope("rebuild_proof", result)
    out["proof_status"] = result.status
    out["findings"] = _findings(result.findings)
    return out


def main(argv: list[str]) -> int:
    request_path, result_path = Path(argv[1]), Path(argv[2])
    raw = request_path.read_bytes()
    try:
        request = json.loads(raw)
        result = run(request)
    except RunnerRefusal as exc:
        result = {"status": "refused", "stage": exc.stage,
                  "findings": [{"code": exc.code, "message": exc.message, "ids": []}, *exc.findings]}
    except Exception as exc:  # surfaced as a typed error, never silently swallowed
        result = {"status": "error", "findings": [{"code": "RUNNER_EXCEPTION", "message": f"{type(exc).__name__}: {exc}", "ids": []}]}
    result["protocol"] = RUNNER_PROTOCOL
    result["request_sha256"] = _sha256(raw)
    result_path.write_text(_canonical(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
