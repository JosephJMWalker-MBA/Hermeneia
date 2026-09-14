"""S1 authoring orchestration over Publication Compositor's ``EditorialLocalJob``.

Hermeneia owns the author interaction, the human decision and rationale, and
the references that bind them to exact Compositor artifacts. Compositor owns
publication content: every version, receipt, refusal and proof below is
produced by Compositor code running in a separate configured process
(``compositor_runner.py``) and stored here byte for byte.

HISTORY IS IMMUTABLE; THE CURRENT WORK IS REVISABLE.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..workspace.identity import ensure_workspace_identity, read_workspace_id
from . import store
from .store import canonical_json, sha256_bytes

RUNNER_PATH = Path(__file__).with_name("compositor_runner.py")
RUNNER_PROTOCOL = "hermeneia-compositor-runner/0.1"
WORK_MANIFEST = "compositor-work.json"
WORK_MANIFEST_SCHEMA = "hermeneia-compositor-work/0.1"
EDITABLE_OPERATIONS = ("replace_text", "delete_text")
PROOF_NOT_UPDATED = "Manuscript saved; proof not updated"
READER_BRIDGE_STATUS = "unresolved"
READER_BRIDGE_NOTE = (
    "No verified bridge links this manuscript unit to Reader extractions. "
    "Reader evidence and annotations stay attached to their original source."
)


class AuthoringError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, findings: list | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.findings = findings or []

    def payload(self) -> dict:
        return {"error": self.message, "code": self.code, "findings": self.findings}


@dataclass(frozen=True)
class CompositorConfig:
    python: str | None
    pythonpath: str | None
    typst: str | None
    timeout_s: float = 180.0

    @classmethod
    def from_env(cls) -> "CompositorConfig":
        return cls(
            python=os.environ.get("HERMENEIA_COMPOSITOR_PYTHON") or None,
            pythonpath=os.environ.get("HERMENEIA_COMPOSITOR_PATH") or None,
            typst=os.environ.get("HERMENEIA_TYPST") or None,
        )

    @property
    def configured(self) -> bool:
        return bool(self.python)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _child_env(config: CompositorConfig) -> dict[str, str]:
    env = {
        name: value
        for name, value in os.environ.items()
        if not any(token in name.upper() for token in ("API_KEY", "ACCESS_TOKEN", "AUTH_TOKEN", "SECRET", "PASSWORD"))
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if config.pythonpath:
        env["PYTHONPATH"] = config.pythonpath
    else:
        env.pop("PYTHONPATH", None)
    return env


def call_runner(config: CompositorConfig, request: dict) -> dict:
    """Invoke the runner with an argument array and a request file; verify the response binding."""
    if not config.configured:
        raise AuthoringError(
            "COMPOSITOR_NOT_CONFIGURED",
            "No Publication Compositor environment is configured (HERMENEIA_COMPOSITOR_PYTHON).",
            503,
        )
    request = {"protocol": RUNNER_PROTOCOL, **request}
    with tempfile.TemporaryDirectory(prefix="hermeneia-compositor-") as tmp:
        request_path = Path(tmp) / "request.json"
        result_path = Path(tmp) / "result.json"
        raw = canonical_json(request).encode("utf-8")
        request_path.write_bytes(raw)
        try:
            proc = subprocess.run(
                [config.python, str(RUNNER_PATH), str(request_path), str(result_path)],
                env=_child_env(config),
                capture_output=True,
                text=True,
                timeout=config.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise AuthoringError("COMPOSITOR_TIMEOUT", "The Compositor process timed out.", 504) from exc
        except OSError as exc:
            raise AuthoringError("COMPOSITOR_UNAVAILABLE", f"Could not start Compositor: {exc}", 503) from exc
        if proc.returncode != 0 or not result_path.is_file():
            raise AuthoringError(
                "COMPOSITOR_PROCESS_FAILED",
                "The Compositor process failed before returning a result.",
                502,
                [{"code": "RUNNER_STDERR", "message": (proc.stderr or "")[-2000:], "ids": []}],
            )
        result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("protocol") != RUNNER_PROTOCOL or result.get("request_sha256") != sha256_bytes(raw):
        raise AuthoringError("COMPOSITOR_STALE_RESPONSE", "Compositor response is not bound to this request.", 502)
    return result


def _envelope_payload(envelope: dict) -> dict:
    """Check Compositor's envelope hash before trusting its payload."""
    payload_json = envelope.get("payload_json") or ""
    if sha256_bytes(payload_json.encode("utf-8")) != envelope.get("payload_sha256"):
        raise AuthoringError("COMPOSITOR_ENVELOPE_HASH_MISMATCH", "Compositor envelope hash mismatch.", 502)
    return json.loads(payload_json)


def _refusal(result: dict, fallback_code: str, message: str) -> AuthoringError:
    findings = result.get("findings") or []
    code = findings[0]["code"] if findings else fallback_code
    return AuthoringError(code, message, 409 if result.get("status") == "refused" else 502, findings)


# ── Work attachment ─────────────────────────────────────────────────────────


def _conn_rw(db_path: Path) -> sqlite3.Connection:
    from ..storage.sqlite import SQLiteStore

    SQLiteStore(db_path).close()  # write path: ensures schema, including authoring tables
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _conn_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _scoped_copy(source_dir: Path, relative: str, dest_dir: Path) -> Path:
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise AuthoringError("WORK_PATH_REFUSED", f"Work manifest path is not a safe relative path: {relative!r}")
    src = source_dir / relative
    if src.is_symlink() or not src.is_file():
        raise AuthoringError("WORK_ARTIFACT_MISSING", f"Declared work artifact is missing: {relative}")
    dest = dest_dir / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest


def attach_work(db_path: str | Path, source_dir: str | Path, *, actor: str, config: CompositorConfig) -> dict:
    """Attach one prepared, verified Compositor work to this workspace (S1: at most one)."""
    db_path = Path(db_path)
    source_dir = Path(source_dir)
    manifest_path = source_dir / WORK_MANIFEST
    if not manifest_path.is_file():
        raise AuthoringError("WORK_MANIFEST_MISSING", f"No {WORK_MANIFEST} in the selected directory.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != WORK_MANIFEST_SCHEMA:
        raise AuthoringError("WORK_MANIFEST_UNSUPPORTED", f"Unsupported work manifest schema {manifest.get('schema')!r}.")
    inputs = manifest.get("inputs") or {}
    declared = [entry for key, entry in inputs.items() if key != "fonts"] + list(inputs.get("fonts") or [])
    for entry in declared:
        data = (source_dir / entry["path"]).read_bytes() if (source_dir / entry["path"]).is_file() else None
        if data is None or sha256_bytes(data) != entry.get("sha256"):
            raise AuthoringError("WORK_ARTIFACT_HASH_MISMATCH", f"Work artifact failed its hash check: {entry.get('path')}")

    conn = _conn_rw(db_path)
    try:
        if store.get_work(conn) is not None:
            raise AuthoringError("WORK_ALREADY_ATTACHED", "This workspace already has an attached publication work.", 409)
        identity = ensure_workspace_identity(conn)
        conn.commit()
    finally:
        conn.close()

    staging = Path(tempfile.mkdtemp(prefix="work-", dir=_publication_root(db_path)))
    try:
        for entry in declared:
            _scoped_copy(source_dir, entry["path"], staging)
        # Verify with Compositor before anything is activated.
        result = call_runner(config, {
            "operation": "inspect",
            "work_dir": str(staging),
            "inputs": inputs,
            "expected_renderer_environment_sha256": manifest.get("renderer_environment_sha256"),
            "history": [],
        })
        if result.get("status") != "ok":
            raise _refusal(result, "WORK_NOT_VERIFIED", "Compositor did not verify this work; nothing was attached.")
        snapshot = _envelope_payload(result["snapshot"])
        work_root = {
            "source_artifact_sha256": snapshot["source_artifact_sha256"],
            "root_canonical_text_sha256": snapshot["root_canonical_text_sha256"],
            "root_canonical_semantic_sha256": snapshot["root_canonical_semantic_sha256"],
            "root_version_ref": snapshot["current_version_ref"],
            "input_sha256": {key: (entry["sha256"] if key != "fonts" else [f["sha256"] for f in entry]) for key, entry in inputs.items()},
        }
        work_id = "work-" + sha256_bytes(canonical_json(work_root).encode("utf-8"))[:32]
        final_dir = store.work_dir(db_path, work_id)
        if final_dir.exists():
            raise AuthoringError("WORK_AREA_EXISTS", "A publication area for this work already exists.", 409)
        staging.rename(final_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    now = _now()
    conn = _conn_rw(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT INTO publication_works (id, workspace_id, label, work_root_json, inputs_json,
                   renderer_environment_sha256, facade_pin_json, root_version_ref, synthetic, attached_by, attached_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                work_id, identity["workspace_id"], manifest.get("label"), canonical_json(work_root),
                canonical_json(inputs), manifest.get("renderer_environment_sha256"), canonical_json(result["pin"]),
                snapshot["current_version_ref"], 1 if manifest.get("synthetic") else 0, actor, now,
            ),
        )
        for key, entry in inputs.items():
            for item in (entry if key == "fonts" else [entry]):
                data = (final_dir / item["path"]).read_bytes()
                conn.execute(
                    "INSERT OR IGNORE INTO publication_artifacts (sha256, work_id, kind, relpath, byte_length, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (item["sha256"], work_id, f"input:{key}", item["path"], len(data), now),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"work_id": work_id, "work_root": work_root, "pin": result["pin"]}


def _publication_root(db_path: Path) -> Path:
    root = Path(db_path).parent / "publication"
    root.mkdir(parents=True, exist_ok=True)
    return root


# ── Current state (read-only) ────────────────────────────────────────────────


def _runner_request(conn: sqlite3.Connection, db_path: Path, work: dict, operation: str, **extra) -> dict:
    history = [
        {
            "record_path": store.artifact_relpath(conn, item["record_artifact_sha256"]),
            "record_sha256": item["record_artifact_sha256"],
            "expected_parent_ref": item["expected_parent_ref"],
            "idempotency_key": item["idempotency_key"],
            "receipt_sha256": item["receipt_artifact_sha256"],
        }
        for item in store.accepted_chain(conn, work["id"])
    ]
    pin = json.loads(work["facade_pin_json"])
    return {
        "operation": operation,
        "work_dir": str(store.work_dir(db_path, work["id"])),
        "inputs": json.loads(work["inputs_json"]),
        "expected_renderer_environment_sha256": work["renderer_environment_sha256"],
        "expected_facade_sha256": pin.get("facade_sha256"),
        "history": history,
        **extra,
    }


def _require_work(conn: sqlite3.Connection) -> dict:
    work = store.get_work(conn)
    if work is None:
        raise AuthoringError("NO_ATTACHED_WORK", "No publication work is attached to this workspace.", 404)
    return work


def _inspect(conn, db_path: Path, work: dict, config: CompositorConfig) -> dict:
    result = call_runner(config, _runner_request(conn, db_path, work, "inspect"))
    if result.get("status") != "ok":
        raise _refusal(result, "HISTORY_NOT_VERIFIED", "Compositor could not reconstruct this work's history.")
    return _envelope_payload(result["snapshot"])


def _version_units(conn, db_path: Path, work: dict, version_ref: str) -> list[dict] | None:
    """Units of an exact stored version (C0 or accepted editorial version), or None."""
    if version_ref == work["root_version_ref"]:
        inputs = json.loads(work["inputs_json"])
        c0 = json.loads((store.work_dir(db_path, work["id"]) / inputs["canonical_c0"]["path"]).read_text(encoding="utf-8"))
        return [{**unit, "source_content_id": unit["id"]} for unit in c0["units"]]
    for item in store.accepted_chain(conn, work["id"]):
        if item["result_version_ref"] == version_ref:
            version = json.loads(store.read_artifact(conn, db_path, item["version_artifact_sha256"]))
            return version["units"]
    return None


def verify_history(db_path: str | Path, *, config: CompositorConfig) -> dict:
    """Replay the complete accepted history through Compositor and report the verified head."""
    db_path = Path(db_path)
    conn = _conn_ro(db_path)
    try:
        work = _require_work(conn)
        snapshot = _inspect(conn, db_path, work, config)
        chain = store.accepted_chain(conn, work["id"])
    finally:
        conn.close()
    expected_head = chain[-1]["result_version_ref"] if chain else work["root_version_ref"]
    if snapshot["current_version_ref"] != expected_head:
        raise AuthoringError("HISTORY_HEAD_MISMATCH", "Replayed head differs from the recorded accepted chain.", 502)
    return {"work_id": work["id"], "current_version_ref": snapshot["current_version_ref"], "accepted_versions": len(chain)}


def projection(db_path: str | Path, *, config: CompositorConfig) -> dict:
    """Read-only Authoring projection of the exact current Compositor version."""
    db_path = Path(db_path)
    if not db_path.exists():
        return {"attached": False}
    conn = _conn_ro(db_path)
    try:
        work = store.get_work(conn)
        if work is None:
            return {"attached": False, "compositor_configured": config.configured}
        snapshot = _inspect(conn, db_path, work, config)
        chain = store.accepted_chain(conn, work["id"])
        versions = [{"version_ref": work["root_version_ref"], "label": "C0 (source-derived root)", "units": _version_units(conn, db_path, work, work["root_version_ref"])}]
        for index, item in enumerate(chain, start=1):
            versions.append({"version_ref": item["result_version_ref"], "label": f"N+{index}", "units": _version_units(conn, db_path, work, item["result_version_ref"])})
        drafts = store.rows(conn, "SELECT * FROM authoring_drafts WHERE work_id = ? ORDER BY created_at, id", (work["id"],))
        proposals = store.rows(
            conn,
            """SELECT p.id, p.parent_version_ref, p.unit_id, p.operation, p.start_offset, p.end_offset,
                      p.before_value, p.after_value, p.rationale, p.proposed_by, p.proposal_sha256,
                      p.validation_status, p.validation_json, p.created_at,
                      d.id AS decision_id, d.decision, d.actor AS decision_actor, d.rationale AS decision_rationale,
                      d.decided_at
               FROM authoring_proposals p LEFT JOIN authoring_decisions d ON d.proposal_id = p.id
               WHERE p.work_id = ? ORDER BY p.created_at, p.id""",
            (work["id"],),
        )
        outcomes = store.rows(
            conn,
            """SELECT o.id, o.status, o.chain_index, o.result_version_ref, o.findings_json, o.created_at,
                      r.decision_id, r.attempt, r.expected_parent_ref, r.idempotency_key, r.id AS request_id
               FROM authoring_outcomes o JOIN authoring_requests r ON r.id = o.request_id
               WHERE o.work_id = ? ORDER BY o.created_at, o.id""",
            (work["id"],),
        )
        proofs = store.rows(conn, "SELECT * FROM authoring_proofs WHERE work_id = ? ORDER BY created_at, id", (work["id"],))
    finally:
        conn.close()

    current_ref = snapshot["current_version_ref"]
    latest_drafts: dict[tuple[str, str], dict] = {}
    for draft in drafts:
        latest_drafts[(draft["unit_id"], draft["parent_version_ref"])] = draft
    units = []
    for unit in snapshot["units"]:
        origin = unit.get("source_content_id")
        lineage = []
        for version in versions:
            match = next((u for u in (version["units"] or []) if (u.get("source_content_id") or u.get("id")) == origin), None)
            if match is not None:
                lineage.append({"version_ref": version["version_ref"], "label": version["label"], "unit_id": match["id"], "text": match["text"]})
        draft = latest_drafts.get((unit["id"], current_ref))
        units.append({
            **unit,
            "editable": not unit.get("locked"),
            "not_editable_reason": "Locked by Compositor (unsupported content)." if unit.get("locked") else None,
            "origin_ref": origin,
            "lineage": lineage,
            "draft": draft["draft_text"] if draft else None,
            "reader_correspondence": {"status": READER_BRIDGE_STATUS, "note": READER_BRIDGE_NOTE},
        })
    latest_proof = proofs[-1] if proofs else None
    last_verified = next((p for p in reversed(proofs) if p["status"] == "verified"), None)
    return {
        "attached": True,
        "compositor_configured": config.configured,
        "work": {
            "id": work["id"], "label": work["label"], "synthetic": bool(work["synthetic"]),
            "root_version_ref": work["root_version_ref"], "work_root": json.loads(work["work_root_json"]),
            "attached_by": work["attached_by"], "attached_at": work["attached_at"],
        },
        "current_version_ref": current_ref,
        "current_version_label": "C0 (source-derived root)" if not chain else f"N+{len(chain)}",
        "supported_operations": list(snapshot.get("supported_operations") or []),
        "units": units,
        "versions": [{"version_ref": v["version_ref"], "label": v["label"]} for v in versions],
        "proposals": proposals,
        "outcomes": outcomes,
        "proofs": proofs,
        "proof_state": _proof_state(latest_proof, last_verified, current_ref),
    }


def _proof_state(latest: dict | None, last_verified: dict | None, current_ref: str) -> dict:
    if last_verified is None:
        state = {"status": "none", "message": "No verified proof yet."}
    elif last_verified["version_ref"] == current_ref:
        state = {"status": "current", "message": "Proof matches the current accepted version.", "proof_id": last_verified["id"]}
    else:
        state = {"status": "stale", "message": "Proof shows an earlier version.", "proof_id": last_verified["id"], "proof_version_ref": last_verified["version_ref"]}
    if latest is not None and latest["status"] != "verified" and latest["version_ref"] == current_ref:
        state["last_attempt"] = {"status": latest["status"], "message": PROOF_NOT_UPDATED, "findings": json.loads(latest["findings_json"])}
    return state


# ── Drafts, proposals, decisions ────────────────────────────────────────────


def save_draft(db_path: str | Path, *, unit_id: str, parent_version_ref: str, text: str) -> dict:
    db_path = Path(db_path)
    conn = _conn_rw(db_path)
    try:
        work = _require_work(conn)
        draft = {"id": _new_id("draft"), "work_id": work["id"], "parent_version_ref": parent_version_ref,
                 "unit_id": unit_id, "draft_text": text, "created_at": _now()}
        conn.execute(
            "INSERT INTO authoring_drafts (id, work_id, parent_version_ref, unit_id, draft_text, created_at) VALUES (?,?,?,?,?,?)",
            tuple(draft.values()),
        )
        conn.commit()
        return draft
    finally:
        conn.close()


def plain_text_delta(before: str, after: str) -> dict:
    """Exact minimal range edit in Unicode scalar positions (Python ``str`` indices).

    A pure insertion is expressed as a replacement of the smallest containing
    range (one adjacent character), as the architecture's first slice allows.
    """
    if before == after:
        raise AuthoringError("NO_CHANGE", "The edited text is identical to the current text.")
    prefix = 0
    limit = min(len(before), len(after))
    while prefix < limit and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    while suffix < limit - prefix and before[len(before) - 1 - suffix] == after[len(after) - 1 - suffix]:
        suffix += 1
    start, end = prefix, len(before) - suffix
    new_end = len(after) - suffix
    if start == end:  # insertion: widen to include one neighbouring character
        if start > 0:
            start -= 1
            prefix -= 1
        else:
            end += 1
            new_end += 1
    replacement = after[prefix:new_end]
    return {
        "operation": "delete_text" if replacement == "" else "replace_text",
        "start_offset": start,
        "end_offset": end,
        "before_value": before[start:end],
        "after_value": replacement,
    }


def propose(db_path: str | Path, *, unit_id: str, parent_version_ref: str, new_text: str,
            rationale: str, actor: str, config: CompositorConfig) -> dict:
    """Record a proposed plain-text revision against an exact unit/version and validate it."""
    if not rationale.strip():
        raise AuthoringError("RATIONALE_REQUIRED", "A rationale is required for a proposed revision.")
    db_path = Path(db_path)
    conn = _conn_rw(db_path)
    try:
        work = _require_work(conn)
        units = _version_units(conn, db_path, work, parent_version_ref)
        if units is None:
            raise AuthoringError("UNKNOWN_PARENT_VERSION", "The proposal names a version this work does not have.", 404)
        unit = next((u for u in units if u["id"] == unit_id), None)
        if unit is None:
            raise AuthoringError("UNKNOWN_UNIT", "That unit does not exist in the named version.", 404)
        delta = plain_text_delta(unit["text"], new_text)
        proposal_id = _new_id("proposal")
        record = {
            "id": f"hermeneia-{proposal_id}",
            "sequence": 1,
            "operation": delta["operation"],
            "target_content_id": unit["id"],
            "target_text_sha256": unit["text_sha256"],
            "target_semantic_sha256": unit["semantic_sha256"],
            "start_offset": delta["start_offset"],
            "end_offset": delta["end_offset"],
            "before_value": delta["before_value"],
            "after_value": delta["after_value"],
            "category": "copy_edit",
            "reason": rationale,
            "proposal_provenance_reference": f"hermeneia:proposal:{proposal_id}",
            "decision": "proposed",
        }
        result = call_runner(config, _runner_request(conn, db_path, work, "validate",
            record=record, expected_parent_ref=parent_version_ref,
            dry_run_approval={
                "decision": "approved", "decision_actor_role": "author",
                "decision_actor_reference": "hermeneia:validation-dry-run",
                "decision_provenance_reference": f"hermeneia:dry-run:{proposal_id}",
            }))
        if result.get("status") not in ("ok", "refused"):
            raise _refusal(result, "VALIDATION_FAILED", "Compositor could not validate this proposal.")
        validation_status = "valid" if result.get("status") == "ok" else "refused"
        proposal = {
            "id": proposal_id, "work_id": work["id"], "parent_version_ref": parent_version_ref,
            "unit_id": unit["id"], "unit_text_sha256": unit["text_sha256"], "unit_semantic_sha256": unit["semantic_sha256"],
            "operation": delta["operation"], "start_offset": delta["start_offset"], "end_offset": delta["end_offset"],
            "before_value": delta["before_value"], "after_value": delta["after_value"], "rationale": rationale,
            "proposed_by": actor, "record_json": canonical_json(record),
            "proposal_sha256": sha256_bytes(canonical_json(record).encode("utf-8")),
            "validation_status": validation_status,
            "validation_json": canonical_json({"findings": result.get("findings") or []}),
            "created_at": _now(),
        }
        conn.execute(
            f"INSERT INTO authoring_proposals ({', '.join(proposal)}) VALUES ({', '.join('?' for _ in proposal)})",
            tuple(proposal.values()),
        )
        conn.commit()
        return {**proposal, "findings": result.get("findings") or []}
    finally:
        conn.close()


def decide(db_path: str | Path, *, proposal_id: str, decision: str, rationale: str, actor: str,
           config: CompositorConfig) -> dict:
    """Append an explicit human decision; an approval is then submitted to Compositor."""
    if decision not in ("approved", "rejected"):
        raise AuthoringError("DECISION_INVALID", "Decision must be 'approved' or 'rejected'.")
    if not rationale.strip():
        raise AuthoringError("RATIONALE_REQUIRED", "A rationale is required for a decision.")
    db_path = Path(db_path)
    conn = _conn_rw(db_path)
    try:
        work = _require_work(conn)
        proposal = next(iter(store.rows(conn, "SELECT * FROM authoring_proposals WHERE id = ?", (proposal_id,))), None)
        if proposal is None:
            raise AuthoringError("UNKNOWN_PROPOSAL", "No such proposal.", 404)
        if store.rows(conn, "SELECT id FROM authoring_decisions WHERE proposal_id = ?", (proposal_id,)):
            raise AuthoringError("ALREADY_DECIDED", "This proposal already has a recorded decision.", 409)
        if decision == "approved" and proposal["validation_status"] != "valid":
            raise AuthoringError("PROPOSAL_NOT_VALID", "Compositor refused this proposal; it cannot be approved.", 409,
                                 json.loads(proposal["validation_json"])["findings"])
        workspace_id = read_workspace_id(conn) or work["workspace_id"]
        body = {
            "proposal_id": proposal_id, "proposal_sha256": proposal["proposal_sha256"], "decision": decision,
            "actor": actor, "rationale": rationale, "workspace_id": workspace_id,
            "target_version_ref": proposal["parent_version_ref"],
        }
        row = {"id": _new_id("decision"), **body,
               "decision_sha256": sha256_bytes(canonical_json(body).encode("utf-8")), "decided_at": _now()}
        conn.execute(
            f"INSERT INTO authoring_decisions ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
            tuple(row.values()),
        )
        conn.commit()
    finally:
        conn.close()
    if decision == "rejected":
        return {"decision": row, "outcome": None}
    return {"decision": row, "outcome": submit(db_path, decision_id=row["id"], config=config)}


def submit(db_path: str | Path, *, decision_id: str, config: CompositorConfig) -> dict:
    """Submit (or retry) the approved revision request for one decision."""
    db_path = Path(db_path)
    conn = _conn_rw(db_path)
    try:
        work = _require_work(conn)
        decision = next(iter(store.rows(conn, "SELECT * FROM authoring_decisions WHERE id = ?", (decision_id,))), None)
        if decision is None or decision["decision"] != "approved":
            raise AuthoringError("NOT_APPROVED", "Only an approved decision can be submitted.", 409)
        prior = store.rows(
            conn,
            """SELECT o.*, r.attempt FROM authoring_outcomes o JOIN authoring_requests r ON r.id = o.request_id
               WHERE r.decision_id = ? ORDER BY r.attempt""",
            (decision_id,),
        )
        accepted = next((o for o in prior if o["status"] == "accepted"), None)
        if accepted is not None:
            return {**accepted, "duplicate": True}
        proposal = store.rows(conn, "SELECT * FROM authoring_proposals WHERE id = ?", (decision["proposal_id"],))[0]
        record = json.loads(proposal["record_json"])
        record.update({
            "decision": "approved",
            "decision_actor_role": "author",
            "decision_actor_reference": f"hermeneia:actor:{decision['actor']}",
            "decision_provenance_reference": f"hermeneia:decision:{decision_id}:{decision['decision_sha256']}",
        })
        now = _now()
        record_bytes = canonical_json(record).encode("utf-8")
        record_sha = store.store_artifact(conn, db_path, work["id"], "revision_record", record_bytes, now=now)
        idempotency_key = f"hermeneia:decision:{decision_id}"
        request_row = {
            "id": _new_id("request"), "decision_id": decision_id, "work_id": work["id"],
            "expected_parent_ref": proposal["parent_version_ref"], "idempotency_key": idempotency_key,
            "record_artifact_sha256": record_sha, "attempt": len(prior) + 1, "created_at": now,
        }
        conn.execute(
            f"INSERT INTO authoring_requests ({', '.join(request_row)}) VALUES ({', '.join('?' for _ in request_row)})",
            tuple(request_row.values()),
        )
        conn.commit()

        result = call_runner(config, _runner_request(conn, db_path, work, "apply", record=record,
                             expected_parent_ref=proposal["parent_version_ref"], idempotency_key=idempotency_key))
        outcome = {"id": _new_id("outcome"), "request_id": request_row["id"], "work_id": work["id"],
                   "chain_index": None, "receipt_artifact_sha256": None, "version_artifact_sha256": None,
                   "ledger_artifact_sha256": None, "overlay_artifact_sha256": None, "result_version_ref": None,
                   "result_version_sha256": None, "findings_json": canonical_json(result.get("findings") or []),
                   "created_at": _now()}
        accepted_payload = result.get("accepted") if result.get("status") == "ok" else None
        if accepted_payload and not result.get("idempotent_replay"):
            receipt = json.loads(accepted_payload["receipt_json"])
            if (receipt["parent_version_ref"] != proposal["parent_version_ref"]
                    or receipt["idempotency_key"] != idempotency_key
                    or receipt["approved_revision_ids"] != [record["id"]]):
                raise AuthoringError("COMPOSITOR_STALE_RESPONSE", "Receipt does not bind this request.", 502)
            conn.execute("BEGIN IMMEDIATE")
            chain = store.accepted_chain(conn, work["id"])
            head = chain[-1]["result_version_ref"] if chain else work["root_version_ref"]
            if head != proposal["parent_version_ref"]:
                conn.rollback()
                outcome.update(status="refused", findings_json=canonical_json([{
                    "code": "EDITORIAL_JOB_STALE_PARENT",
                    "message": "Another revision was accepted first; this request's parent is no longer current.",
                    "ids": [proposal["parent_version_ref"], head]}]))
            else:
                outcome.update(
                    status="accepted", chain_index=len(chain),
                    receipt_artifact_sha256=store.store_artifact(conn, db_path, work["id"], "receipt", accepted_payload["receipt_json"].encode("utf-8"), now=now),
                    version_artifact_sha256=store.store_artifact(conn, db_path, work["id"], "version", accepted_payload["version_json"].encode("utf-8"), now=now),
                    ledger_artifact_sha256=store.store_artifact(conn, db_path, work["id"], "ledger", accepted_payload["ledger_json"].encode("utf-8"), now=now),
                    overlay_artifact_sha256=store.store_artifact(conn, db_path, work["id"], "overlay", accepted_payload["overlay_json"].encode("utf-8"), now=now),
                    result_version_ref="editorial:" + receipt["result_version_sha256"],
                    result_version_sha256=receipt["result_version_sha256"],
                )
        else:
            outcome["status"] = "refused" if result.get("status") in ("refused", "ok") else "error"
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            f"INSERT INTO authoring_outcomes ({', '.join(outcome)}) VALUES ({', '.join('?' for _ in outcome)})",
            tuple(outcome.values()),
        )
        conn.commit()
        return outcome
    finally:
        conn.close()


# ── Proof ──────────────────────────────────────────────────────────────────


def build_proof(db_path: str | Path, *, config: CompositorConfig) -> dict:
    """Generate (or retry) the saved 6×9 proof from the exact current accepted version."""
    db_path = Path(db_path)
    conn = _conn_rw(db_path)
    try:
        work = _require_work(conn)
        chain = store.accepted_chain(conn, work["id"])
        current_ref = chain[-1]["result_version_ref"] if chain else work["root_version_ref"]
        with tempfile.TemporaryDirectory(prefix="hermeneia-proof-") as tmp:
            result = call_runner(config, _runner_request(conn, db_path, work, "proof",
                                 output_dir=str(Path(tmp) / "out"), typst_executable=config.typst or "typst"))
            now = _now()
            row = {"id": _new_id("proof"), "work_id": work["id"], "version_ref": current_ref, "status": "error",
                   "result_artifact_sha256": None, "pdf_artifact_sha256": None, "references_json": "[]",
                   "findings_json": canonical_json(result.get("findings") or []), "created_at": now}
            if result.get("status") == "ok":
                proof = _envelope_payload(result["proof"])
                row["status"] = proof["status"]
                row["references_json"] = canonical_json(proof.get("references") or [])
                row["result_artifact_sha256"] = store.store_artifact(
                    conn, db_path, work["id"], "proof_result", result["proof"]["payload_json"].encode("utf-8"), now=now)
                if proof["status"] == "verified" and proof.get("output_path"):
                    pdf = Path(proof["output_path"]).read_bytes()
                    if sha256_bytes(pdf) != proof.get("pdf_sha256"):
                        raise AuthoringError("PROOF_HASH_MISMATCH", "Proof PDF does not match its reported hash.", 502)
                    if proof.get("version_sha256") and current_ref != "editorial:" + proof["version_sha256"]:
                        raise AuthoringError("COMPOSITOR_STALE_RESPONSE", "Proof was built for a different version.", 502)
                    row["pdf_artifact_sha256"] = store.store_artifact(conn, db_path, work["id"], "proof_pdf", pdf, suffix=".pdf", now=now)
            elif result.get("status") == "refused":
                row["status"] = "refused"
        conn.execute(
            f"INSERT INTO authoring_proofs ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
            tuple(row.values()),
        )
        conn.commit()
        out = {**row, "references": json.loads(row["references_json"]), "findings": json.loads(row["findings_json"])}
        if row["status"] != "verified":
            out["message"] = PROOF_NOT_UPDATED if chain else "No accepted version to proof yet."
        return out
    finally:
        conn.close()


def proof_pdf(db_path: str | Path, proof_id: str) -> bytes:
    conn = _conn_ro(Path(db_path))
    try:
        row = next(iter(store.rows(conn, "SELECT * FROM authoring_proofs WHERE id = ?", (proof_id,))), None)
        if row is None or not row["pdf_artifact_sha256"]:
            raise AuthoringError("NO_PROOF_PDF", "No verified PDF for that proof.", 404)
        return store.read_artifact(conn, Path(db_path), row["pdf_artifact_sha256"])
    finally:
        conn.close()
