"""Observation receipts for preservation findings, not package/report identity.

The receipt records exactly what this verification read (including absence).
Only supported, validated build evidence earns a core claim. Historical checks
retain their own outcomes; this module never promotes or replaces findings.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from hermeneia.build_core import InvalidRecord, UnsupportedProfile, canonical_json, core_digest
from hermeneia.build_reproducibility import _Captures, validate_captured_build

SCHEMA = "hermeneia.preservation-verification-inputs/v1"
INPUT_DOMAIN = b"Hermeneia preservation verification inputs v1\n"


def _report_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRecord(f"Duplicate report JSON key: {key}")
        result[key] = value
    return result


def _same_observation(left, right) -> bool:
    # Historical report values (including release signature observations) are
    # not build-core values. Retain JSON number types/ranges, without Python's
    # equality collapsing true, 1 and 1.0 into the same observation.
    return json.dumps(left, sort_keys=True, ensure_ascii=True) == json.dumps(
        right, sort_keys=True, ensure_ascii=True)


class VerificationInputs(_Captures):
    """One capture for interpretation, hashing and core validation.

    Outside-root/unsupported-platform reads remain available to legacy checks,
    but cannot earn a validated core claim. Later reads only detect drift.
    """

    def __init__(self, root: Path):
        super().__init__(root)
        self.observations: dict[Path, dict] = {}
        self.unsupported: str | None = None

    def _path(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _read_observed(self, path: Path) -> tuple[Path, bytes]:
        try:
            _, resolved = self.location(path)
            return resolved, self._read_confined(resolved)
        except UnsupportedProfile as exc:
            # Preserve historical readers, without claiming new-profile coverage.
            self.unsupported = str(exc)
            return path.resolve(), path.read_bytes()

    def _observe(self, value: str | Path, role: str) -> dict:
        path = self._path(value)
        if path not in self.observations:
            item = {"resolved": None, "roles": set()}
            try:
                item["resolved"] = path.resolve()
                item["resolved"], item["raw"] = self._read_observed(path)
            except InvalidRecord as exc:
                # Historical artifact readers classify non-files as I/O failure.
                item["error"] = OSError(str(exc))
            except OSError as exc:
                item["error"] = exc
            except ValueError as exc:
                # Path.exists historically treats an embedded-NUL locator as
                # absent. Preserve that failed check, but do not claim a target.
                item["error"] = OSError(str(exc))
                item["invalid_locator"] = True
            self.observations[path] = item
        item = self.observations[path]
        item["roles"].add(role)
        return item

    def read(self, value: str | Path, role: str = "build-core-validation") -> bytes:
        item = self._observe(value, role)
        if "error" in item:
            raise item["error"]
        return item["raw"]

    def exists(self, value: str | Path, role: str) -> bool:
        item = self._observe(value, role)
        return not item.get("invalid_locator", False) and not isinstance(item.get("error"), FileNotFoundError)

    def text(self, value: str | Path, role: str) -> str:
        # Match historical read_text decoding/newline handling, from captured bytes.
        with io.TextIOWrapper(io.BytesIO(self.read(value, role))) as stream:
            return stream.read()

    def sha256(self, value: str | Path, role: str) -> str:
        return hashlib.sha256(self.read(value, role)).hexdigest()

    def unchanged(self) -> None:
        for path, item in self.observations.items():
            if item.get("invalid_locator"):
                raise InvalidRecord(f"Invalid verification input locator: {path}")
            if path.resolve() != item["resolved"]:
                raise InvalidRecord(f"Verification input locator changed: {path}")
            try:
                _, current = self._read_observed(path)
            except FileNotFoundError:
                if isinstance(item.get("error"), FileNotFoundError):
                    continue
                raise InvalidRecord(f"Verification input disappeared: {path}")
            if "raw" not in item or current != item["raw"]:
                raise InvalidRecord(f"Verification input changed: {path}")

    def receipt(self, build_path: Path) -> dict:
        core = None
        try:
            core = validate_captured_build(build_path, self)
            if self.unsupported:
                raise UnsupportedProfile(self.unsupported)
            status = {"integrity": "valid"}
        except UnsupportedProfile as exc:
            status = {"integrity": "unsupported", "reason": str(exc)}
        except (InvalidRecord, OSError, RuntimeError) as exc:
            status = {"integrity": "invalid", "reason": str(exc)}
        try:
            self.unchanged()
        except (InvalidRecord, UnsupportedProfile, OSError, RuntimeError) as exc:
            status = {"integrity": "invalid", "reason": str(exc)}
        inputs = []
        for path, item in sorted(self.observations.items(), key=lambda pair: str(pair[0])):
            entry = {"path": str(path), "resolved_path": str(item["resolved"]) if item["resolved"] is not None else None,
                     "roles": sorted(item["roles"])}
            if "raw" in item:
                entry.update(state="present", sha256=hashlib.sha256(item["raw"]).hexdigest(),
                             size_bytes=len(item["raw"]))
            elif isinstance(item["error"], FileNotFoundError):
                entry.update(state="missing")
            else:
                entry.update(state="unreadable", error=str(item["error"]))
            inputs.append(entry)
        result = {"schema": SCHEMA, **status, "inputs": inputs,
                  "inputs_sha256": hashlib.sha256(INPUT_DOMAIN + canonical_json(inputs)).hexdigest()}
        if status["integrity"] == "valid":
            result["build_core"] = {"profile": core["schema"], "sha256": core_digest(core)}
        return result


def verify_report_binding(report_path: Path, build_path: Path, *, project_root: Path) -> dict:
    """Read-only association check, not report/package equivalence or authority.

    Re-evaluate the current inputs and compare, never update a historical report.
    Changed evidence makes the old report inapplicable even if it now passes.
    """
    from hermeneia.cli.preserve_cmd import PreservationError, _evaluate_verification, _summarize

    try:
        raw = report_path.read_bytes()
        report = json.loads(raw, object_pairs_hook=_report_pairs)
        provenance = report.get("provenance") if isinstance(report, dict) else None
        if not isinstance(provenance, dict) or provenance.get("schema") != SCHEMA:
            raise UnsupportedProfile("Insufficient supported report provenance")
        if report.get("preservation_engine_version") != "0.1.0":
            raise UnsupportedProfile("Unsupported preservation verifier version")
        if provenance.get("integrity") != "valid":
            raise UnsupportedProfile("Report makes no validated build-core claim")
        inputs = VerificationInputs(project_root)
        build, reconstruction, continuation, current = _evaluate_verification(build_path, project_root, inputs)
        if current["integrity"] != "valid":
            return {"integrity": current["integrity"], "reason": current["reason"]}
        if canonical_json(provenance) != canonical_json(current):
            raise InvalidRecord("Report core or exact verification inputs differ from this execution")
        # Also refuse edited findings. This is verification, not signed authorship.
        for name, checks in [("reconstruction", reconstruction), ("continuation", continuation)]:
            if not _same_observation(report.get(name), {"summary": _summarize(checks), "checks": checks}):
                raise InvalidRecord("Report findings disagree with captured verification inputs")
        overall = "fail" if any(c["status"] == "FAIL" for c in reconstruction + continuation) else (
            "warn" if any(c["status"] == "WARN" for c in reconstruction + continuation) else "pass")
        if report.get("build_id") != build.get("build_id", "unknown") or report.get("overall_outcome") != overall:
            raise InvalidRecord("Report summary disagrees with captured verification inputs")
        if report_path.read_bytes() != raw:
            raise InvalidRecord("Report changed during association check")
        inputs.unchanged()
        return {"integrity": "valid", "build_core": current["build_core"], "findings_outcome": overall}
    except UnsupportedProfile as exc:
        return {"integrity": "unsupported", "reason": str(exc)}
    except (InvalidRecord, PreservationError, OSError, RuntimeError, ValueError, UnicodeError) as exc:
        return {"integrity": "invalid", "reason": str(exc)}
