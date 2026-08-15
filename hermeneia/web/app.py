"""
Hermeneia web server — minimal Flask API + single-page UI.

Endpoints:
  GET /                        → index.html
  GET /api/health              → corpus metrics
  GET /api/search?q=&limit=   → observation search
  GET /api/trace/<obs_index>  → full pipeline trace for OBS-N

Start with: python scripts/herm_server.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, make_response, request, send_from_directory

from ..cli.health import (
    blueprint_count,
    compiler_ok,
    contradiction_count,
    coverage_metrics,
    field_term_count,
    interpretation_count,
    observation_count,
    perspective_count,
)
from ..narrative.provider_registry import (
    ModelCatalog,
    ModelCatalogEntry,
    ProviderRegistry,
    unavailable_model_catalog,
)
from ..compiler.critic import generate_critic_report
from ..compiler.critic.policy import VALID_POLICIES
from ..compiler.staging.interpretation import (
    StagingError,
    accept_proposed_interpretation,
    propose_interpretation,
    reject_proposed_interpretation,
)
from ..compiler.projections.interpretive_divergence import (
    InterpretiveDivergenceError,
    interpretive_divergence_projection,
)
from ..storage.sqlite import SQLiteStore
from ..reader_span import reader_span_display_locator, reader_span_raw_locator
from ..connections_settings import (
    DEFAULT_OLLAMA_HOST,
    InvalidConnectionsSettingError,
    UnreadableConnectionsSettingsError,
    UnsupportedConnectionsSettingsError,
    empty_connections_settings,
    load_connections_settings,
    ollama_host_from_settings,
    provider_credential_source,
    save_connections_settings,
    selected_ollama_model,
    selected_provider_model,
    set_provider_credential_source,
    set_ollama_host,
    set_selected_ollama_model,
    set_selected_provider_model,
)
from ..credentials import (
    CredentialStore,
    CredentialStoreError,
    CredentialStoreUnavailable,
    SERVICE_NAME as CREDENTIAL_SERVICE_NAME,
    default_credential_store,
)
from ..workspace import (
    DEFAULT_LEGACY_DB,
    WorkspaceAlreadyExistsError,
    WorkspaceLifecycleError,
    WorkspaceNameReservedError,
    WorkspaceRecord,
    create_workspace,
    inspect_workspace,
    list_workspaces,
    read_workspace_identity,
)
from ..explorer.interpreter import (
    ExplorerError,
    _call_provider,
    generate_candidate_interpretation,
    generate_interpretation_from_bucket,
)
from ..explorer.bucketer import BucketingError, generate_candidate_buckets
from ..study import compile_study, compile_synthesis_packet
from .reader_projection import project_reader_page

STATIC_DIR = Path(__file__).parent / "static"


def _coerce_rank(value):
    """Validate an annotation rank (Issue #35). Returns (rank_or_None, error_or_None).

    Accepts None/'' (unranked is valid) and integers 1-5. Rejects everything else
    so the substrate never stores a meaningless rank.
    """
    if value is None:
        return None, None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None, None
        if not value.isdecimal():
            return None, "rank must be an integer 1-5 or null"
        r = int(value)
    elif isinstance(value, bool) or not isinstance(value, int):
        return None, "rank must be an integer 1-5 or null"
    else:
        r = value
    if not (1 <= r <= 5):
        return None, "rank must be between 1 and 5"
    return r, None


def _coerce_optional_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _reader_source_locator_fields(source_locator):
    raw_span = reader_span_raw_locator(source_locator)
    fields = {"source_locator": reader_span_display_locator(source_locator)}
    if raw_span:
        fields["reader_span_locator"] = raw_span
    return fields


def create_app(
    db_path: str | Path = "build/hermeneia.db",
    *,
    provider_registry: ProviderRegistry | None = None,
    credential_store: CredentialStore | None = None,
) -> Flask:
    db_path = Path(db_path)
    app = Flask(__name__, static_folder=str(STATIC_DIR))

    # Run all pending schema migrations on startup if the DB exists
    if db_path.exists():
        from ..storage.sqlite import ensure_profile_tables as _migrate
        _mconn = sqlite3.connect(str(db_path))
        _mconn.row_factory = sqlite3.Row
        try:
            _migrate(_mconn)
        finally:
            _mconn.close()

    from ..narrative.profiles import list_profiles as _list_profiles
    from ..narrative.artist_providers import DEFAULT_PROVIDER_REGISTRY

    active_provider_registry = provider_registry or DEFAULT_PROVIDER_REGISTRY
    active_credential_store = credential_store or default_credential_store()
    runtime_provider_keys: dict[str, str] = {}
    runtime_credential_sources: dict[str, str] = {}
    runtime_provider_keys_lock = threading.RLock()
    _connections_settings_lock = threading.RLock()
    _connections_settings_load_error: str | None = None
    try:
        runtime_connections_settings: dict = load_connections_settings()
    except (UnsupportedConnectionsSettingsError, UnreadableConnectionsSettingsError) as exc:
        runtime_connections_settings = empty_connections_settings()
        _connections_settings_load_error = str(exc)

    # ── Calibration store ──────────────────────────────────────────────────────
    # Persisted to calibration.json alongside the DB; loaded once at startup.
    _calibration_path: Path = db_path.parent / "calibration.json"
    _calibration_lock = threading.RLock()

    def _load_calibration_store() -> dict:
        if not _calibration_path.exists():
            return {"calibration_schema": "1.0", "records": {}}
        try:
            return json.loads(_calibration_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"calibration_schema": "1.0", "records": {}}

    def _save_calibration_store(store: dict) -> None:
        try:
            _calibration_path.parent.mkdir(parents=True, exist_ok=True)
            _calibration_path.write_text(json.dumps(store, indent=2, ensure_ascii=False))
        except OSError:
            pass

    runtime_calibration: dict = _load_calibration_store()
    # In-memory performance log — capped at 500 events per session
    _perf_log: list[dict] = []
    _PERF_LOG_MAX = 500

    _CALIBRATION_ROLES = ["Explorer", "Architect", "Artist", "Critic", "Witness"]

    # Structured-output calibration prompt for Explorer Bucketing
    _EXPLORER_CALIBRATION_PROMPT = (
        "You are an Explorer for Hermeneia. Assign this observation to exactly one thematic bucket.\n\n"
        "Observation: \"The green light burned at the end of the dock, visible across the water.\"\n\n"
        "Respond with ONLY valid JSON — no explanation, no markdown, no text outside the JSON:\n"
        "{\"bucket\": \"<name>\", \"confidence\": \"<high|medium|low>\", \"rationale\": \"<one sentence>\"}\n\n"
        "Valid bucket names: symbol_and_imagery, character_behavior, social_commentary, "
        "setting_and_atmosphere, plot_event"
    )

    # Narrative-generation calibration prompt for Artist
    _ARTIST_CALIBRATION_PROMPT = (
        "Write a single paragraph (3-5 sentences) interpreting the following observation. "
        "Write in clear, literary prose. Do not use bullet points or headers.\n\n"
        "Observation: \"He stretched out his arms toward the dark water in a trembling way.\""
    )

    def _empty_calibration_record(
        participant_key: str,
        *,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> dict:
        record = {
            "participant": participant_key,
            "role_status": {
                role: {"status": "untested", "last_updated": None, "steward_note": None}
                for role in _CALIBRATION_ROLES
            },
            "calibration_tests": [],
        }
        if provider_id:
            record["provider_id"] = provider_id
        if model_id:
            record["model_id"] = model_id
        return record

    def _calibration_key(
        participant_key: str,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> str:
        if provider_id and model_id:
            return f"{participant_key}::{provider_id}::{model_id}"
        return participant_key

    def _get_calibration_record(
        participant_key: str,
        *,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> dict:
        """Return calibration for the exact participant/provider/model identity."""
        with _calibration_lock:
            store = runtime_calibration
            key = _calibration_key(participant_key, provider_id, model_id)
            if key not in store.get("records", {}):
                store.setdefault("records", {})[key] = _empty_calibration_record(
                    participant_key,
                    provider_id=provider_id,
                    model_id=model_id,
                )
            return store["records"][key]

    def _get_participant_calibration(participant_key: str) -> dict:
        """Return the legacy participant calibration record."""
        return _get_calibration_record(participant_key)

    def _record_calibration_result(
        participant_key: str,
        role: str,
        test_name: str,
        status: str,
        latency_ms: int | None,
        failure_reason: str | None,
        recommendation: str,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> None:
        with _calibration_lock:
            rec = _get_calibration_record(
                participant_key,
                provider_id=provider_id,
                model_id=model_id,
            )
            now = datetime.now(timezone.utc).isoformat()
            test_id = f"t-{now[:10].replace('-','')}-{len(rec['calibration_tests'])+1:03d}"
            rec["calibration_tests"].append({
                "test_id": test_id,
                "timestamp": now,
                "provider_id": provider_id,
                "model_id": model_id,
                "role": role,
                "test_name": test_name,
                "status": status,
                "latency_ms": latency_ms,
                "failure_reason": failure_reason,
                "recommendation": recommendation,
            })
            # Update role_status based on result
            new_role_status = "allowed" if status == "pass" else (
                "rejected" if status == "fail" else "caution"
            )
            rec["role_status"][role] = {
                "status": new_role_status,
                "last_updated": now,
                "steward_note": None,
            }
            _save_calibration_store(runtime_calibration)

    def _log_performance_event(event: dict) -> None:
        """Append a lightweight performance event to the in-memory log."""
        _perf_log.append(event)
        if len(_perf_log) > _PERF_LOG_MAX:
            del _perf_log[0]

    def _performance_summary() -> dict[str, dict]:
        """Aggregate in-memory perf log by participant."""
        summary: dict[str, dict] = {}
        for ev in _perf_log:
            p = ev.get("participant", "unknown")
            if p not in summary:
                summary[p] = {
                    "calls": 0, "success": 0, "parse_ok": 0,
                    "total_latency_ms": 0, "errors": [],
                    "accepted": 0, "rejected": 0, "latencies": [],
                }
            s = summary[p]
            s["calls"] += 1
            if ev.get("success"):
                s["success"] += 1
            if ev.get("parse_ok"):
                s["parse_ok"] += 1
            lat = ev.get("latency_ms")
            if lat is not None:
                s["total_latency_ms"] += lat
                s["latencies"].append(lat)
            if ev.get("accepted"):
                s["accepted"] += 1
            if ev.get("rejected"):
                s["rejected"] += 1
            if ev.get("error"):
                s["errors"] = s["errors"][-4:] + [ev["error"]]
        # Compute averages
        for p, s in summary.items():
            n = len(s["latencies"])
            s["avg_latency_ms"] = round(s["total_latency_ms"] / n) if n else None
            del s["total_latency_ms"]
            del s["latencies"]
        return summary

    class _LineageError(Exception):
        pass

    class _ScopeAccessError(Exception):
        def __init__(self, message: str, status_code: int = 403) -> None:
            super().__init__(message)
            self.status_code = status_code

    _CONSTITUTIONAL_PROFILE_KEYS = {
        "constitution_version",
        "authority_index_version",
        "invariant_profile",
        "architecture_profile",
    }
    _EVIDENCE_IMMUTABILITY_TRIGGERS = {
        "source_documents_no_update",
        "source_documents_no_delete",
        "source_extractions_no_update",
        "source_extractions_no_delete",
        "observations_no_update",
        "observations_no_delete",
        "provenance_no_update",
        "provenance_no_delete",
    }
    _WORKSPACE_PROFILES = {"child", "elder", "scholar"}
    _WORKSPACE_CLASS_PATHS = {
        "RenderedNarrative": "rendered_narrative",
        "ArchitectPlan": "architect_plan",
        "Blueprint": "blueprint",
        "Interpretation": "interpretation",
        "Observation": "observation",
        "SourceExtraction": "source_extraction",
        "SourceDocument": "source_document",
    }
    _E10_PARTICIPANTS = {
        "gpt": ("GPT", "openai", "openai/gpt"),
        "claude": ("Claude", "anthropic", "anthropic/claude"),
        "gemini": ("Gemini", "gemini", "google/gemini"),
        "grok": ("Grok", "grok", "xai/grok"),
        "meta": ("Meta", "ollama-meta", "llama3.2:3b"),
        "local": ("Local Model", "ollama-local", "qwen3:4b"),
    }

    # Static role suitability: "recommended" | "allowed" | "untested" | "rejected"
    _ROLE_SUITABILITY: dict[str, dict[str, str]] = {
        "gpt": {
            "Explorer": "recommended", "Architect": "recommended",
            "Artist": "recommended", "Critic": "recommended", "Witness": "allowed",
        },
        "claude": {
            "Explorer": "recommended", "Architect": "recommended",
            "Artist": "recommended", "Critic": "recommended", "Witness": "allowed",
        },
        "gemini": {
            "Explorer": "allowed", "Architect": "allowed",
            "Artist": "allowed", "Critic": "allowed", "Witness": "allowed",
        },
        "grok": {
            "Explorer": "untested", "Architect": "untested",
            "Artist": "untested", "Critic": "untested", "Witness": "untested",
        },
        "meta": {
            "Explorer": "untested", "Architect": "untested",
            "Artist": "allowed", "Critic": "untested", "Witness": "allowed",
        },
        "local": {
            # Qwen3:4b failed strict JSON structured output during Explorer bucketing
            "Explorer": "rejected", "Architect": "untested",
            "Artist": "allowed", "Critic": "untested", "Witness": "allowed",
        },
    }

    _PROVIDER_SETUP: dict[str, dict] = {
        "gpt": {
            "about": "OpenAI GPT-4o. Strong reasoning, reliable structured output.",
            "credential_name": "OPENAI_API_KEY",
            "credential_hint": "Get a key at platform.openai.com/api-keys",
            "setup_steps": [],
        },
        "claude": {
            "about": "Anthropic Claude. Strong semantic precision and constitutional reasoning.",
            "credential_name": "ANTHROPIC_API_KEY",
            "credential_hint": "Get a key at console.anthropic.com",
            "setup_steps": [],
        },
        "gemini": {
            "about": "Google Gemini. Capable across roles. Not yet calibrated for Explorer.",
            "credential_name": "GEMINI_API_KEY",
            "credential_hint": "Get a key at aistudio.google.com/app/apikey",
            "setup_steps": [],
        },
        "grok": {
            "about": "xAI Grok. All roles untested within Hermeneia.",
            "credential_name": "GROK_API_KEY",
            "credential_hint": "Get a key at console.x.ai",
            "setup_steps": [],
        },
        "meta": {
            "about": "Meta Llama 3.2 running locally via Ollama. Private, no API key needed. Artist role verified.",
            "credential_name": None,
            "credential_hint": None,
            "setup_steps": [
                "Install Ollama from ollama.com",
                "Run: ollama pull llama3.2:3b",
                "Run: ollama serve",
            ],
        },
        "local": {
            "about": "Custom local model via Ollama (default: qwen3:4b). Explorer role rejected: failed structured JSON output.",
            "credential_name": None,
            "credential_hint": None,
            "setup_steps": [
                "Install Ollama from ollama.com",
                "Run: ollama pull qwen3:4b",
                "Run: ollama serve",
            ],
        },
    }

    def _empty_performance_record(*, suppressed: bool = False) -> dict:
        rec = {
            "calls": 0,
            "success": 0,
            "parse_ok": 0,
            "avg_latency_ms": None,
            "errors": [],
            "accepted": 0,
            "rejected": 0,
        }
        if suppressed:
            rec["suppressed"] = True
            rec["message"] = (
                "Participant-level performance is hidden for multi-model Ollama "
                "providers. Exact model analytics belong to the Model Observatory."
            )
        return rec

    def _model_specific_role_suitability(
        participant_key: str,
        provider_id: str,
        selected_model: str,
        default_model: str,
    ) -> dict[str, str]:
        if selected_model != default_model:
            return {role: "untested" for role in _CALIBRATION_ROLES}
        return _ROLE_SUITABILITY.get(participant_key, {})

    def _model_specific_provider_setup(
        participant_key: str,
        provider_id: str,
        selected_model: str,
        default_model: str,
    ) -> dict:
        setup = dict(_PROVIDER_SETUP.get(participant_key, {}))
        if selected_model != default_model:
            if provider_id.startswith("ollama-"):
                setup["about"] = (
                    "Local model running via Ollama. No static Hermeneia suitability "
                    "judgment is recorded for this exact selected model; use calibration "
                    "to establish role readiness."
                )
                setup["setup_steps"] = [
                    "Install Ollama from ollama.com",
                    "Choose an installed local model explicitly",
                    "Run: ollama serve",
                ]
            else:
                setup["about"] = (
                    "Explicitly selected cloud model. No static Hermeneia suitability "
                    "judgment is recorded for this exact selected model; use calibration "
                    "to establish role readiness."
                )
        return setup

    def _conn() -> sqlite3.Connection:
        uri = db_path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _conn_rw() -> sqlite3.Connection:
        """Read-write connection for pipeline write endpoints (Artist, Critic)."""
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _store() -> SQLiteStore:
        return SQLiteStore(db_path)

    def _canonical_path(path: Path) -> Path:
        return path.expanduser().resolve()

    def _same_runtime_db(candidate: Path) -> bool:
        try:
            return _canonical_path(candidate) == _canonical_path(db_path)
        except OSError:
            return False

    def _browser_draft_fingerprint(value: str) -> str:
        """Match the old browser FNV-1a base36 draft-scope fingerprint."""
        h = 2166136261
        for ch in value:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        if h == 0:
            return "0"
        chars = "0123456789abcdefghijklmnopqrstuvwxyz"
        out = ""
        while h:
            h, rem = divmod(h, 36)
            out = chars[rem] + out
        return out

    def _opaque_runtime_token(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]

    def _runtime_scope_for(
        *,
        kind: str,
        workspace_id: str | None,
        slug: str | None,
        runtime_db: Path,
    ) -> str:
        if kind == "legacy":
            return "legacy:gatsby"
        if workspace_id:
            prefix = "managed" if kind == "managed" else "custom"
            return f"{prefix}:{workspace_id}"
        if kind == "managed" and slug:
            token = _opaque_runtime_token(f"managed:{_canonical_path(runtime_db)}")
            return f"managed:{token}"
        token = _opaque_runtime_token(f"custom:{_canonical_path(runtime_db)}")
        return f"custom:{token}"

    def _with_runtime_draft_scope(payload: dict, *, runtime_db: Path) -> dict:
        return {
            **payload,
            "runtime_scope": _runtime_scope_for(
                kind=str(payload.get("kind") or "custom"),
                workspace_id=payload.get("id"),
                slug=payload.get("slug"),
                runtime_db=runtime_db,
            ),
            "draft_migration_scope": _browser_draft_fingerprint(str(db_path)),
        }

    def _runtime_workspace_identity() -> dict | None:
        if not db_path.exists():
            return None
        conn = None
        try:
            conn = _conn()
            return read_workspace_identity(conn)
        except sqlite3.DatabaseError:
            return None
        finally:
            if conn is not None:
                conn.close()

    def _workspace_payload(
        record: WorkspaceRecord,
        *,
        is_active: bool | None = None,
    ) -> dict:
        payload = {
            "id": record.workspace_id,
            "name": record.name,
            "slug": record.slug,
            "kind": record.kind,
            "managed": record.kind == "managed",
        }
        if is_active is not None:
            payload["is_active"] = is_active
        if record.created_at:
            payload["created_at"] = record.created_at
        if record.updated_at:
            payload["updated_at"] = record.updated_at
        return payload

    def _legacy_runtime_workspace_payload() -> dict:
        identity = _runtime_workspace_identity() or {}
        return {
            "id": identity.get("workspace_id"),
            "name": identity.get("workspace_name") or "Gatsby",
            "slug": "gatsby",
            "kind": "legacy",
            "managed": False,
        }

    def _custom_runtime_workspace_payload() -> dict:
        identity = _runtime_workspace_identity() or {}
        return {
            "id": identity.get("workspace_id"),
            "name": identity.get("workspace_name") or "Custom workspace",
            "slug": None,
            "kind": "custom",
            "managed": False,
        }

    def _runtime_workspace_payload(
        records: list[WorkspaceRecord] | None = None,
    ) -> dict:
        discovered = records if records is not None else list_workspaces(
            include_document_count=False
        )
        for record in discovered:
            if _same_runtime_db(record.db_path):
                return _with_runtime_draft_scope(
                    _workspace_payload(record),
                    runtime_db=record.db_path,
                )
        if _same_runtime_db(DEFAULT_LEGACY_DB):
            return _with_runtime_draft_scope(
                _legacy_runtime_workspace_payload(),
                runtime_db=db_path,
            )
        return _with_runtime_draft_scope(
            _custom_runtime_workspace_payload(),
            runtime_db=db_path,
        )

    def _workspace_catalog_payload() -> list[dict]:
        records = list_workspaces(include_document_count=False)
        return [
            _workspace_payload(record, is_active=_same_runtime_db(record.db_path))
            for record in records
        ]

    def _scope_error_response(exc: _ScopeAccessError):
        payload = {"error": str(exc)}
        if exc.status_code == 403:
            payload["scope"] = "excluded_from_analysis"
        return jsonify(payload), exc.status_code

    def require_active_document(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM source_documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if row is None:
            raise _ScopeAccessError("document not found", 404)
        if int(row["excluded_from_analysis"] or 0):
            raise _ScopeAccessError("document is excluded_from_analysis", 403)
        return row

    def require_active_observation(conn: sqlite3.Connection, obs_id: str) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT o.*, sd.original_filename, sd.file_hash,
                   COALESCE(sd.source_role, 'primary') AS source_role,
                   COALESCE(sd.excluded_from_analysis, 0) AS excluded_from_analysis
            FROM observations o
            JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE o.id = ?
            """,
            (obs_id,),
        ).fetchone()
        if row is None:
            raise _ScopeAccessError("observation not found", 404)
        if int(row["excluded_from_analysis"] or 0):
            raise _ScopeAccessError("observation is excluded_from_analysis", 403)
        return row

    def active_observation_ids(conn: sqlite3.Connection) -> list[str]:
        return [
            r[0]
            for r in conn.execute(
                """
                SELECT o.id
                FROM observations o
                JOIN source_documents sd ON sd.id = o.source_document_id
                WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
                ORDER BY o.page, o.paragraph, o.sentence
                """
            )
        ]

    def require_active_proposal_observations(
        conn: sqlite3.Connection, proposal_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT id, observation_id, evidence_observation_ids
            FROM proposed_interpretations
            WHERE id = ?
            """,
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise _ScopeAccessError("proposal not found", 404)
        evidence_ids = _json_loads(row["evidence_observation_ids"], [])
        scoped_ids = {row["observation_id"]}
        if isinstance(evidence_ids, list):
            scoped_ids.update(str(oid) for oid in evidence_ids)
        for obs_id in scoped_ids:
            require_active_observation(conn, obs_id)
        return row

    def _json_loads(value: object, fallback: object) -> object:
        if value is None:
            return fallback
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return fallback

    def _e10_prompt(observation_text: str, participant_label: str,
                    corpus_context: dict | None = None) -> str:
        lines = [
            "Hermeneia E10 Interpretation Lab",
            "Task: propose one perspective-scoped Interpretation for the Observation.",
            "Do not modify the Observation text. Preserve ambiguity.",
        ]
        if corpus_context:
            primary = corpus_context.get("primary_work")
            obs_name = corpus_context.get("observation_source")
            obs_role = corpus_context.get("observation_role", "primary")
            role_descriptions = {
                "primary":     "the primary work — the subject of interpretation",
                "reference":   "a reference work — comparative context, not primary evidence",
                "notes":       "supplementary notes — background context only",
                "commentary":  "critical commentary — external perspective on the primary work",
            }
            if primary:
                lines.append(f"Primary Work (subject of this interpretation): {primary}")
            if obs_name:
                lines.append(
                    f"Observation source: {obs_name}"
                    f" ({role_descriptions.get(obs_role, obs_role)})"
                )
            if obs_role != "primary" and primary:
                lines.append(
                    f"Instruction: this observation is from a {obs_role} corpus. "
                    f"Interpret how it illuminates or contrasts with {primary}. "
                    f"Do not treat it as primary evidence about {primary}."
                )
        lines.extend([
            f"Participant: {participant_label}",
            f"Observation: {observation_text}",
        ])
        return "\n".join(lines)

    def _e10_interpretation_text(observation_text: str, participant_label: str) -> str:
        compact = " ".join(observation_text.split())
        excerpt = compact[:180]
        if len(compact) > 180:
            excerpt += "..."
        return (
            f"{participant_label} proposes that this observation should be read as "
            f"evidence whose significance remains open under steward review. "
            f"The proposed reading is anchored to the observed wording: {excerpt!r}."
        )

    def _e10_participant(raw: str) -> tuple[str, str, str] | None:
        key = raw.strip().lower().replace("_", "-")
        key = {
            "openai": "gpt",
            "chatgpt": "gpt",
            "anthropic": "claude",
            "google": "gemini",
            "xai": "grok",
            "llama": "meta",
            "local-model": "local",
        }.get(key, key)
        item = _E10_PARTICIPANTS.get(key)
        if item is None:
            return None
        return key, item[0], item[2]

    def _ollama_host() -> str:
        env_host = str(os.environ.get("OLLAMA_HOST") or "").strip()
        if env_host:
            return env_host
        with _connections_settings_lock:
            configured_host = ollama_host_from_settings(runtime_connections_settings)
        return configured_host or DEFAULT_OLLAMA_HOST

    def _ollama_host_source() -> str:
        if str(os.environ.get("OLLAMA_HOST") or "").strip():
            return "environment"
        with _connections_settings_lock:
            if ollama_host_from_settings(runtime_connections_settings):
                return "user_config"
        return "default"

    def _ollama_model_names(model_rows: object) -> list[str]:
        names: list[str] = []
        for item in model_rows or []:
            if isinstance(item, dict):
                name = item.get("model") or item.get("name") or ""
            else:
                name = getattr(item, "model", "") or getattr(item, "name", "")
            name = str(name).strip()
            if name and name not in names:
                names.append(name)
        return sorted(names)

    def _ollama_catalog() -> dict:
        """Return configured Ollama host status and installed models."""
        host = _ollama_host()
        try:
            import ollama as _ollama  # noqa: F401
        except ImportError:
            return {
                "host": host,
                "online": False,
                "installed_models": [],
                "setup_action": "Run: pip install ollama",
                "error": "ollama Python package is not installed",
            }
        try:
            client = _ollama.Client(host=host)
            result = client.list()
            model_rows = getattr(result, "models", None)
            if model_rows is None and isinstance(result, dict):
                model_rows = result.get("models", [])
            return {
                "host": host,
                "online": True,
                "installed_models": _ollama_model_names(model_rows),
                "setup_action": None,
                "error": None,
            }
        except Exception as exc:
            return {
                "host": host,
                "online": False,
                "installed_models": [],
                "setup_action": "Run: ollama serve",
                "error": str(exc),
            }

    def _ollama_readiness(model: str, catalog: dict | None = None) -> dict:
        """Check Ollama server reachability and model availability without raising."""
        catalog = catalog or _ollama_catalog()
        installed = set(catalog.get("installed_models") or [])
        server_running = bool(catalog.get("online"))
        model_pulled = server_running and model in installed
        return {
            "host": catalog.get("host") or _ollama_host(),
            "server_running": server_running,
            "model_pulled": model_pulled,
            "installed_models": sorted(installed),
            "setup_action": (
                None if model_pulled
                else catalog.get("setup_action") if not server_running
                else f"Run: ollama pull {model}"
            ),
            "error": catalog.get("error"),
        }

    def _ollama_model_catalog_payload(catalog: dict) -> dict[str, object]:
        models = [
            ModelCatalogEntry(
                model_id=model,
                provider_id="ollama",
                display_label=model,
                catalog_source="provider_api",
                capabilities=("text",),
            ).to_dict()
            for model in (catalog.get("installed_models") or [])
        ]
        return {
            "provider": "ollama",
            "catalog_source": "provider_api" if catalog.get("online") else "unavailable",
            "status": "available" if catalog.get("online") else "unavailable",
            "error": catalog.get("error"),
            "models": models,
        }

    def _provider_model_catalog(provider_id: str, provider: dict) -> dict[str, object]:
        if provider_id.startswith("ollama-"):
            return _ollama_model_catalog_payload(_ollama_catalog())
        if provider.get("local_or_remote") != "remote":
            return unavailable_model_catalog(
                provider_id,
                "Model catalog is not exposed for this provider.",
            ).to_dict()
        if not provider.get("adapter_available"):
            return unavailable_model_catalog(
                provider_id,
                "Provider adapter is not installed.",
            ).to_dict()
        if provider.get("required_environment") and not _credential_configured(provider):
            return unavailable_model_catalog(
                provider_id,
                "Selected credential source is not configured.",
            ).to_dict()
        try:
            adapter = active_provider_registry.create(
                provider_id,
                **_provider_connection_kwargs(provider_id),
            )
            catalog_fn = getattr(adapter, "model_catalog", None)
            if not callable(catalog_fn):
                return unavailable_model_catalog(
                    provider_id,
                    "Provider adapter does not expose a model catalog.",
                ).to_dict()
            catalog = catalog_fn()
            if not isinstance(catalog, ModelCatalog):
                return unavailable_model_catalog(
                    provider_id,
                    "Provider adapter returned an invalid model catalog.",
                ).to_dict()
            return catalog.to_dict()
        except CredentialStoreError as exc:
            return unavailable_model_catalog(provider_id, str(exc)).to_dict()
        except Exception:
            return unavailable_model_catalog(
                provider_id,
                "Could not retrieve model catalog. Check provider credentials and connectivity.",
            ).to_dict()

    def _catalog_model_ids(catalog: dict[str, object]) -> set[str]:
        ids: set[str] = set()
        for model in catalog.get("models") or []:
            if isinstance(model, dict):
                model_id = str(model.get("model_id") or model.get("id") or "").strip()
                if model_id:
                    ids.add(model_id)
        return ids

    def _provider_default_model(provider_id: str, fallback: str | None = None) -> str | None:
        try:
            definition = active_provider_registry.definition(provider_id)
            return definition.default_model or fallback
        except KeyError:
            return fallback

    def _selected_model_for_provider(
        provider_id: str,
        fallback: str | None = None,
    ) -> tuple[str | None, str]:
        default_model = _provider_default_model(provider_id, fallback)
        with _connections_settings_lock:
            stored = (
                selected_ollama_model(runtime_connections_settings, provider_id)
                if provider_id.startswith("ollama-")
                else selected_provider_model(runtime_connections_settings, provider_id)
            )
        if stored:
            return stored, "user_config"
        return default_model, "default"

    def _set_selected_model_for_provider(provider_id: str, model: str) -> None:
        with _connections_settings_lock:
            if _connections_settings_load_error:
                raise UnsupportedConnectionsSettingsError(_connections_settings_load_error)
            if provider_id.startswith("ollama-"):
                next_settings = set_selected_ollama_model(
                    runtime_connections_settings,
                    provider_id,
                    model,
                )
            else:
                next_settings = set_selected_provider_model(
                    runtime_connections_settings,
                    provider_id,
                    model,
                )
            save_connections_settings(next_settings)
            runtime_connections_settings.clear()
            runtime_connections_settings.update(next_settings)

    def _set_ollama_host(host: str) -> None:
        with _connections_settings_lock:
            if _connections_settings_load_error:
                raise UnsupportedConnectionsSettingsError(_connections_settings_load_error)
            next_settings = set_ollama_host(runtime_connections_settings, host)
            save_connections_settings(next_settings)
            runtime_connections_settings.clear()
            runtime_connections_settings.update(next_settings)

    def _set_persisted_credential_source(provider_id: str, source: dict[str, object]) -> None:
        with _connections_settings_lock:
            if _connections_settings_load_error:
                raise UnsupportedConnectionsSettingsError(_connections_settings_load_error)
            next_settings = set_provider_credential_source(
                runtime_connections_settings,
                provider_id,
                source,
            )
            save_connections_settings(next_settings)
            runtime_connections_settings.clear()
            runtime_connections_settings.update(next_settings)

    def _system_credential_state(provider_id: str) -> dict[str, object]:
        status = active_credential_store.status()
        state: dict[str, object] = {
            "system_store_available": bool(status.get("available")),
            "system_store_backend": status.get("backend"),
            "message": status.get("message"),
            "system_credential_present": False,
        }
        if not state["system_store_available"]:
            return state
        try:
            state["system_credential_present"] = active_credential_store.has_password(provider_id)
        except CredentialStoreError as exc:
            state["system_store_available"] = False
            state["message"] = str(exc)
            state["system_credential_present"] = False
        return state

    def _credential_source_for_provider(provider: dict) -> dict[str, object]:
        provider_id = str(provider["id"])
        env_name = provider.get("required_environment")
        if not env_name:
            return {"kind": "not_required", "configured": True}
        system_state = _system_credential_state(provider_id)
        with runtime_provider_keys_lock:
            runtime_source = runtime_credential_sources.get(provider_id)
            session_present = bool(runtime_provider_keys.get(provider_id))
        if runtime_source == "session":
            return {"kind": "session", "configured": session_present, **system_state}
        with _connections_settings_lock:
            persisted = provider_credential_source(runtime_connections_settings, provider_id)
        if persisted:
            kind = persisted.get("kind")
            if kind == "session":
                return {"kind": "session", "configured": session_present, **system_state}
            if kind == "system_store":
                return {
                    "kind": "system_store",
                    "configured": bool(
                        system_state.get("system_store_available")
                        and system_state.get("system_credential_present")
                    ),
                    **system_state,
                    "service": persisted.get("service"),
                    "account": persisted.get("account"),
                }
            if kind == "environment":
                env_var = str(persisted.get("environment_variable") or env_name)
                return {
                    "kind": "environment",
                    "environment_variable": env_var,
                    "configured": bool(os.environ.get(env_var)),
                    **system_state,
                }
        return {
            "kind": "environment",
            "environment_variable": env_name,
            "configured": bool(os.environ.get(str(env_name))),
            **system_state,
        }

    def _credential_secret_for_provider(provider_id: str) -> str | None:
        try:
            provider = active_provider_registry.definition(provider_id).metadata()
        except KeyError:
            return None
        source = _credential_source_for_provider(provider)
        kind = source.get("kind")
        if kind == "not_required":
            return None
        if kind == "session":
            with runtime_provider_keys_lock:
                secret = runtime_provider_keys.get(provider_id)
            if not secret:
                raise CredentialStoreUnavailable("Session credential is not configured.")
            return secret
        if kind == "environment":
            env_name = str(source.get("environment_variable") or "")
            secret = os.environ.get(env_name) if env_name else None
            if not secret:
                raise CredentialStoreUnavailable("Selected environment credential is not configured.")
            return secret
        if kind == "system_store":
            if not source.get("system_store_available"):
                raise CredentialStoreUnavailable(str(source.get("message") or "System credential store is unavailable."))
            secret = active_credential_store.get_password(provider_id)
            if not secret:
                raise CredentialStoreUnavailable("System credential is not configured.")
            return secret
        return None

    def _credential_configured(provider: dict) -> bool:
        if not provider.get("required_environment"):
            return True
        source = _credential_source_for_provider(provider)
        if source.get("kind") == "system_store" and not source.get("system_store_available"):
            return False
        return bool(source.get("configured"))

    def _provider_kwargs(provider_id: str, *, api_key: str | None = None) -> dict:
        kwargs = _provider_connection_kwargs(provider_id, api_key=api_key)
        selected_model, _ = _selected_model_for_provider(provider_id)
        if selected_model:
            kwargs["model"] = selected_model
        return kwargs

    def _provider_connection_kwargs(provider_id: str, *, api_key: str | None = None) -> dict:
        kwargs: dict[str, object] = {}
        if provider_id.startswith("ollama-"):
            kwargs["host"] = _ollama_host()
        resolved_key = api_key if api_key is not None else _credential_secret_for_provider(provider_id)
        if resolved_key:
            kwargs["api_key"] = resolved_key
        return kwargs

    def _e10_provider_statuses() -> list[dict]:
        ecology = active_provider_registry.ecology()
        providers = {
            provider["id"]: provider
            for provider in ecology.get("providers", [])
        }
        ollama_catalog: dict | None = None
        rows = []
        for key, (label, provider_id, draft_model) in _E10_PARTICIPANTS.items():
            provider = providers.get(provider_id)
            if provider is None:
                rows.append({
                    "participant": key,
                    "label": label,
                    "provider_id": provider_id,
                    "configured": False,
                    "adapter_available": False,
                    "status": "not_wired",
                    "credential_source": None,
                    "default_model": draft_model,
                    "execution_mode": "deterministic_local_draft",
                    "message": "No provider adapter is registered for this participant.",
                })
                continue

            credential_source_state = _credential_source_for_provider(provider)
            configured = _credential_configured(provider)
            adapter_available = bool(provider.get("adapter_available"))
            available = configured and adapter_available and provider.get("provider_type") == "artist"
            requires_credential = bool(provider.get("required_environment"))
            is_ollama = provider_id.startswith("ollama-")
            default_model = provider.get("default_model") or draft_model
            selected_model, selected_model_source = _selected_model_for_provider(provider_id, default_model)
            model_catalog: dict[str, object]

            # Ollama: check actual server + model readiness, not just package install
            ollama_ready = None
            if is_ollama and adapter_available:
                if ollama_catalog is None:
                    ollama_catalog = _ollama_catalog()
                ollama_ready = _ollama_readiness(selected_model or "", ollama_catalog)
                model_catalog = _ollama_model_catalog_payload(ollama_catalog)
                ollama_fully_ready = ollama_ready["server_running"] and ollama_ready["model_pulled"]
            else:
                model_catalog = _provider_model_catalog(provider_id, provider)
                ollama_fully_ready = True  # non-Ollama providers are governed by credential
            catalog_ids = _catalog_model_ids(model_catalog)
            catalog_status = str(model_catalog.get("status") or "unavailable")
            selected_model_available = (
                bool(selected_model)
                and catalog_status == "available"
                and selected_model in catalog_ids
            )

            if is_ollama and adapter_available and not ollama_fully_ready:
                setup_action = ollama_ready["setup_action"] if ollama_ready else None
                if not ollama_ready["server_running"]:
                    message = f"Ollama package is installed, but the server is not running. {setup_action or 'Run: ollama serve'}"
                else:
                    message = (
                        f"Ollama server is running, but the selected model "
                        f"'{selected_model}' is not installed. Choose an installed model "
                        "or pull the model outside this PR's governed-install scope."
                    )
                effective_status = "not_connected"
            elif (
                provider.get("local_or_remote") == "remote"
                and adapter_available
                and configured
                and catalog_status == "available"
                and selected_model
                and not selected_model_available
            ):
                message = (
                    f"Selected model '{selected_model}' is not present in the current "
                    "provider catalog. Choose an available model explicitly."
                )
                effective_status = "not_connected"
            elif available and not requires_credential:
                message = "Ollama server is running and model is ready." if is_ollama else (
                    "Local SDK is installed. Use Test Connection to verify the runtime and selected model."
                )
                effective_status = "configured"
            elif available:
                message = "Credential is present and the Python adapter is available."
                effective_status = "configured"
            elif configured:
                message = (
                    "Credential is saved, but the Python adapter is missing. "
                    "Install the provider SDK before testing the configuration."
                )
                effective_status = "not_connected"
            elif credential_source_state.get("kind") == "system_store" and not credential_source_state.get("system_store_available"):
                message = str(credential_source_state.get("message") or "System credential store is unavailable.")
                effective_status = "not_connected"
            else:
                message = "No credential is configured."
                effective_status = "not_connected"

            row: dict = {
                "participant": key,
                "label": label,
                "provider_id": provider_id,
                "configured": configured,
                "requires_credential": requires_credential,
                "adapter_available": adapter_available,
                "status": effective_status,
                "credential_source": provider.get("required_environment"),
                "credential_scope": credential_source_state.get("kind"),
                "credential_source_kind": credential_source_state.get("kind"),
                "credential_source_configured": credential_source_state.get("configured"),
                "credential_environment_variable": credential_source_state.get("environment_variable"),
                "system_credential_store_available": credential_source_state.get("system_store_available"),
                "system_credential_store_backend": credential_source_state.get("system_store_backend"),
                "system_credential_configured": credential_source_state.get("system_credential_present"),
                "default_model": default_model,
                "selected_model": selected_model,
                "selected_model_source": selected_model_source,
                "selected_model_available": selected_model_available,
                "model_catalog": model_catalog,
                "model_catalog_source": model_catalog.get("catalog_source"),
                "model_catalog_status": model_catalog.get("status"),
                "model_catalog_error": model_catalog.get("error"),
                "available_models": sorted(catalog_ids),
                "execution_mode": "deterministic_local_draft",
                "message": message,
                "role_suitability": _model_specific_role_suitability(
                    key,
                    provider_id,
                    selected_model,
                    default_model,
                ),
                "setup": _model_specific_provider_setup(
                    key,
                    provider_id,
                    selected_model,
                    default_model,
                ),
            }
            if is_ollama:
                installed_models = ollama_ready["installed_models"] if ollama_ready else []
                row["ollama_server_running"] = bool(ollama_ready and ollama_ready["server_running"])
                row["ollama_model_pulled"] = bool(ollama_ready and ollama_ready["model_pulled"])
                row["selected_model_installed"] = bool(ollama_ready and ollama_ready["model_pulled"])
                row["selected_model_available"] = bool(ollama_ready and ollama_ready["model_pulled"])
                row["ollama_host"] = (ollama_ready or {}).get("host") or _ollama_host()
                row["ollama_host_source"] = _ollama_host_source()
                row["installed_models"] = installed_models
                row["ollama_setup_action"] = ollama_ready["setup_action"] if ollama_ready else None
                row["ollama_error"] = ollama_ready.get("error") if ollama_ready else None
            rows.append(row)
        return rows

    def _e10_critic_report_payload(row: sqlite3.Row | dict) -> dict:
        data = dict(row)
        data["claims"] = _json_loads(data.get("claims"), [])
        data["evidence_passages"] = _json_loads(data.get("evidence_passages"), [])
        return data

    def _e10_proposal_payload(conn: sqlite3.Connection, row: sqlite3.Row | dict) -> dict:
        data = dict(row)
        data["evidence_observation_ids"] = _json_loads(
            data.get("evidence_observation_ids"), []
        )
        if not _table_exists(conn, "critic_reports"):
            data["critic_reports"] = []
            return data
        reports = conn.execute(
            """
            SELECT *
            FROM critic_reports
            WHERE proposal_id = ?
            ORDER BY generated_at DESC, policy
            """,
            (data["id"],),
        ).fetchall()
        data["critic_reports"] = [_e10_critic_report_payload(r) for r in reports]
        return data

    def _e10_interpretation_payload(row: sqlite3.Row | dict) -> dict:
        data = dict(row)
        data["evidence_observation_ids"] = _json_loads(
            data.get("evidence_observation_ids"), []
        )
        return data

    def _all_obs_ids(conn: sqlite3.Connection) -> list[str]:
        return active_observation_ids(conn)

    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        return bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
        )

    def _table_count(conn: sqlite3.Connection, table_name: str) -> int:
        if not _table_exists(conn, table_name):
            return 0
        return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    def _lineage_class(raw: str) -> str | None:
        key = raw.replace("-", "_").replace(" ", "_").lower()
        return {
            "rendered": "RenderedNarrative",
            "rendered_narrative": "RenderedNarrative",
            "renderednarrative": "RenderedNarrative",
            "architect": "ArchitectPlan",
            "architect_plan": "ArchitectPlan",
            "architectplan": "ArchitectPlan",
            "blueprint": "Blueprint",
            "narrative_blueprint": "Blueprint",
            "narrativeblueprint": "Blueprint",
            "interpretation": "Interpretation",
            "observation": "Observation",
            "source_extraction": "SourceExtraction",
            "sourceextraction": "SourceExtraction",
            "source_document": "SourceDocument",
            "sourcedocument": "SourceDocument",
        }.get(key)

    def _lineage_graph(conn: sqlite3.Connection, root_class: str, root_id: str) -> dict:
        nodes: dict[tuple[str, str], dict] = {}
        edges: set[tuple[str, str, str, str, str]] = set()

        def add_node(cls: str, row: sqlite3.Row, data: dict | None = None) -> None:
            rid = row["id"]
            key = (cls, rid)
            if key not in nodes:
                nodes[key] = {
                    "id": rid,
                    "class": cls,
                    "data": data or {},
                }

        def add_edge(from_cls: str, from_id: str, to_cls: str, to_id: str, relation: str) -> None:
            edges.add((from_cls, from_id, to_cls, to_id, relation))

        def one(sql: str, params: tuple, missing: str) -> sqlite3.Row:
            row = conn.execute(sql, params).fetchone()
            if row is None:
                raise _LineageError(missing)
            return row

        def build_rendered_narrative(rid: str) -> None:
            row = one(
                "SELECT * FROM rendered_narratives WHERE id = ?",
                (rid,),
                f"RenderedNarrative missing: {rid}",
            )
            add_node("RenderedNarrative", row, {
                "architect_plan_id": row["architect_plan_id"],
                "provider": row["provider"],
                "expression_profile_id": row["expression_profile_id"],
                "created_at": row["created_at"],
            })
            build_architect_plan(row["architect_plan_id"])
            add_edge("RenderedNarrative", row["id"], "ArchitectPlan", row["architect_plan_id"], "architect_plan_id")

        def build_architect_plan(pid: str) -> None:
            row = one(
                "SELECT * FROM architect_plans WHERE id = ?",
                (pid,),
                f"ArchitectPlan missing: {pid}",
            )
            add_node("ArchitectPlan", row, {
                "blueprint_id": row["blueprint_id"],
                "blueprint_hash": row["blueprint_hash"],
                "title": row["title"],
                "source": row["source"],
                "created_at": row["created_at"],
            })
            build_blueprint(row["blueprint_id"])
            add_edge("ArchitectPlan", row["id"], "Blueprint", row["blueprint_id"], "blueprint_id")

        def build_blueprint(bid: str) -> None:
            row = one(
                "SELECT * FROM narrative_blueprints WHERE id = ?",
                (bid,),
                f"Blueprint missing: {bid}",
            )
            sections = json.loads(row["sections"])
            add_node("Blueprint", row, {
                "title": row["title"],
                "thesis": row["thesis"],
                "section_count": len(sections),
                "source": row["source"],
                "created_at": row["created_at"],
            })

            interp_rows = conn.execute(
                """
                SELECT interpretation_id
                FROM blueprint_interpretation_links
                WHERE blueprint_id = ?
                ORDER BY interpretation_id
                """,
                (bid,),
            ).fetchall()
            for linked in interp_rows:
                iid = linked["interpretation_id"]
                build_interpretation(iid)
                add_edge("Blueprint", bid, "Interpretation", iid, "supporting_interpretation")

            obs_rows = conn.execute(
                """
                SELECT observation_id
                FROM blueprint_observation_links
                WHERE blueprint_id = ?
                ORDER BY observation_id
                """,
                (bid,),
            ).fetchall()
            for linked in obs_rows:
                oid = linked["observation_id"]
                build_observation(oid)
                add_edge("Blueprint", bid, "Observation", oid, "supporting_observation")

        def build_interpretation(iid: str) -> None:
            row = one(
                "SELECT * FROM interpretations WHERE id = ?",
                (iid,),
                f"Interpretation missing: {iid}",
            )
            add_node("Interpretation", row, {
                "observation_id": row["observation_id"],
                "perspective": row["perspective"],
                "perspective_id": row["perspective_id"],
                "evidential_status": row["evidential_status"],
                "text": row["text"],
                "created_at": row["created_at"],
            })
            build_observation(row["observation_id"])
            add_edge("Interpretation", row["id"], "Observation", row["observation_id"], "observation_id")

            try:
                evidence_ids = json.loads(row["evidence_observation_ids"] or "[]")
            except json.JSONDecodeError:
                evidence_ids = []
            for oid in sorted(set(evidence_ids)):
                build_observation(oid)
                add_edge("Interpretation", row["id"], "Observation", oid, "evidence_observation_ids")

        def build_observation(oid: str) -> None:
            row = require_active_observation(conn, oid)
            add_node("Observation", row, {
                "source_document_id": row["source_document_id"],
                "source_extraction_id": row["source_extraction_id"],
                "raw_text": row["raw_text"],
                "source_locator": row["source_locator"],
                "semantic_hash": row["semantic_hash"],
                "page": row["page"],
                "paragraph": row["paragraph"],
                "sentence": row["sentence"],
                "source_role": row["source_role"],
            })
            build_source_extraction(row["source_extraction_id"])
            add_edge("Observation", row["id"], "SourceExtraction", row["source_extraction_id"], "source_extraction_id")

        def build_source_extraction(eid: str) -> None:
            row = one(
                "SELECT * FROM source_extractions WHERE id = ?",
                (eid,),
                f"SourceExtraction missing: {eid}",
            )
            add_node("SourceExtraction", row, {
                "document_id": row["document_id"],
                "page": row["page"],
                "region": row["region"],
                "raw_text": row["raw_text"],
                "parser": row["parser"],
                "parser_version": row["parser_version"],
                "coordinates": row["coordinates"],
                "source_locator": row["source_locator"],
                "source_hash": row["source_hash"],
            })
            build_source_document(row["document_id"])
            add_edge("SourceExtraction", row["id"], "SourceDocument", row["document_id"], "document_id")

        def build_source_document(did: str) -> None:
            row = require_active_document(conn, did)
            add_node("SourceDocument", row, {
                "original_filename": row["original_filename"],
                "file_hash": row["file_hash"],
                "total_pages": row["total_pages"],
                "registered_at": row["registered_at"],
                "compiler_version": row["compiler_version"],
                "source_role": row["source_role"],
            })

        builders = {
            "RenderedNarrative": build_rendered_narrative,
            "ArchitectPlan": build_architect_plan,
            "Blueprint": build_blueprint,
            "Interpretation": build_interpretation,
            "Observation": build_observation,
            "SourceExtraction": build_source_extraction,
            "SourceDocument": build_source_document,
        }
        builders[root_class](root_id)

        class_order = {
            "RenderedNarrative": 0,
            "ArchitectPlan": 1,
            "Blueprint": 2,
            "Interpretation": 3,
            "Observation": 4,
            "SourceExtraction": 5,
            "SourceDocument": 6,
        }
        return {
            "root": {"id": root_id, "class": root_class},
            "nodes": sorted(nodes.values(), key=lambda n: (class_order[n["class"]], n["id"])),
            "edges": [
                {
                    "from": {"id": from_id, "class": from_cls},
                    "to": {"id": to_id, "class": to_cls},
                    "relation": relation,
                }
                for from_cls, from_id, to_cls, to_id, relation in sorted(
                    edges,
                    key=lambda e: (class_order[e[0]], e[0], e[1], class_order[e[2]], e[2], e[3], e[4]),
                )
            ],
        }

    def _json_finding_list(value: object) -> list:
        if value is None or value == "":
            return []
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
        except (TypeError, json.JSONDecodeError):
            return [value]
        if parsed in (None, 0, 0.0, ""):
            return []
        return parsed if isinstance(parsed, list) else [parsed]

    def _trust_summary(conn: sqlite3.Connection, narrative_id: str) -> dict:
        narrative = conn.execute(
            "SELECT * FROM rendered_narratives WHERE id = ?",
            (narrative_id,),
        ).fetchone()
        if narrative is None:
            raise _LineageError(f"RenderedNarrative missing: {narrative_id}")

        lineage_error = None
        graph = None
        try:
            graph = _lineage_graph(conn, "RenderedNarrative", narrative_id)
        except (_LineageError, _ScopeAccessError, sqlite3.Error) as exc:
            lineage_error = str(exc)

        nodes = graph["nodes"] if graph else []
        nodes_by_class: dict[str, list[dict]] = {}
        for node in nodes:
            nodes_by_class.setdefault(node["class"], []).append(node)

        required_classes = {
            "RenderedNarrative",
            "ArchitectPlan",
            "Blueprint",
            "Interpretation",
            "Observation",
            "SourceExtraction",
            "SourceDocument",
        }
        missing_classes = sorted(required_classes - set(nodes_by_class))

        profile_id = narrative["expression_profile_id"] if "expression_profile_id" in narrative.keys() else None
        profile_exists = bool(
            profile_id
            and conn.execute(
                "SELECT 1 FROM expression_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        )

        missing_perspectives: list[str] = []
        for node in nodes_by_class.get("Interpretation", []):
            row = conn.execute(
                "SELECT perspective_id FROM interpretations WHERE id = ?",
                (node["id"],),
            ).fetchone()
            perspective_id = row["perspective_id"] if row else None
            if not perspective_id or not conn.execute(
                "SELECT 1 FROM perspectives WHERE id = ?",
                (perspective_id,),
            ).fetchone():
                missing_perspectives.append(node["id"])

        provenance_failures: list[str] = []
        for node in nodes_by_class.get("Observation", []):
            row = conn.execute(
                """
                SELECT o.raw_text, o.source_document_id, o.source_extraction_id,
                       p.verbatim_text, p.source_document_id AS provenance_document_id,
                       p.source_extraction_id AS provenance_extraction_id
                FROM observations o
                LEFT JOIN provenance p ON p.observation_id = o.id
                WHERE o.id = ?
                """,
                (node["id"],),
            ).fetchone()
            if (
                row is None
                or row["verbatim_text"] != row["raw_text"]
                or row["provenance_document_id"] != row["source_document_id"]
                or row["provenance_extraction_id"] != row["source_extraction_id"]
            ):
                provenance_failures.append(node["id"])

        trigger_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).fetchall()
        trigger_names = {row["name"] for row in trigger_rows}
        missing_triggers = sorted(_EVIDENCE_IMMUTABILITY_TRIGGERS - trigger_names)

        evidence_classes_present = all(
            nodes_by_class.get(cls)
            for cls in ("SourceDocument", "SourceExtraction", "Observation")
        )
        evidence_preserved = (
            evidence_classes_present
            and not provenance_failures
            and not missing_triggers
        )
        lineage_complete = (
            graph is not None
            and not missing_classes
            and profile_exists
            and not missing_perspectives
            and not provenance_failures
        )

        execution_config = None
        constitutional_profile = None
        execution_config_error = None
        if "execution_config" not in narrative.keys():
            execution_config_error = "execution_config column is absent"
        elif not narrative["execution_config"]:
            execution_config_error = "execution_config is absent"
        else:
            try:
                execution_config = json.loads(narrative["execution_config"])
            except (TypeError, json.JSONDecodeError):
                execution_config_error = "execution_config is not valid JSON"
            if isinstance(execution_config, dict):
                constitutional_profile = execution_config.get("constitutional_profile")

        profile_keys = (
            set(constitutional_profile)
            if isinstance(constitutional_profile, dict)
            else set()
        )
        constitutional_profile_recorded = (
            isinstance(constitutional_profile, dict)
            and _CONSTITUTIONAL_PROFILE_KEYS <= profile_keys
        )
        if not constitutional_profile_recorded and execution_config_error is None:
            execution_config_error = "constitutional_profile is incomplete"

        report = conn.execute(
            """
            SELECT *
            FROM validation_reports
            WHERE rendered_narrative_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (narrative_id,),
        ).fetchone()

        semantic_status = "pending"
        critic_status = "pending"
        semantic_evidence: dict = {"validation_report_id": None}
        critic_evidence: dict = {"validation_report_id": None}
        if report is not None:
            report_matches_contract = (
                report["architect_plan_id"] == narrative["architect_plan_id"]
                and report["expression_profile_id"] == profile_id
            )
            findings = {
                "required_terms_missing": _json_finding_list(report["required_terms_missing"]),
                "unsupported_claims": _json_finding_list(report["unsupported_claims"]),
                "omitted_observations": _json_finding_list(report["omitted_observations"]),
                "omitted_interpretations": _json_finding_list(report["omitted_interpretations"]),
                "semantic_drift": _json_finding_list(report["semantic_drift"]),
                "warnings": _json_finding_list(report["warnings"]),
            }
            semantic_contract_satisfied = (
                report_matches_contract
                and float(report["semantic_fidelity"]) == 100.0
                and not any(findings.values())
            )
            critic_approved = report_matches_contract and bool(report["approved"])
            semantic_status = "pass" if semantic_contract_satisfied else "fail"
            critic_status = "pass" if critic_approved else "fail"
            semantic_evidence = {
                "validation_report_id": report["id"],
                "semantic_fidelity": report["semantic_fidelity"],
                "report_matches_contract": report_matches_contract,
                **findings,
            }
            critic_evidence = {
                "validation_report_id": report["id"],
                "approved": bool(report["approved"]),
                "report_matches_contract": report_matches_contract,
            }

        return {
            "rendered_narrative_id": narrative_id,
            "checks": {
                "evidence_preserved": {
                    "status": "pass" if evidence_preserved else "fail",
                    "evidence": {
                        "evidence_classes_present": evidence_classes_present,
                        "provenance_failures": provenance_failures,
                        "missing_immutability_triggers": missing_triggers,
                    },
                },
                "lineage_complete": {
                    "status": "pass" if lineage_complete else "fail",
                    "evidence": {
                        "missing_classes": missing_classes,
                        "expression_profile_id": profile_id,
                        "expression_profile_exists": profile_exists,
                        "interpretations_without_perspective": missing_perspectives,
                        "provenance_failures": provenance_failures,
                        "lineage_error": lineage_error,
                    },
                },
                "constitutional_profile_recorded": {
                    "status": "pass" if constitutional_profile_recorded else "fail",
                    "evidence": {
                        "constitutional_profile": constitutional_profile,
                        "error": execution_config_error,
                    },
                },
                "semantic_contract_satisfied": {
                    "status": semantic_status,
                    "evidence": semantic_evidence,
                },
                "critic_approved": {
                    "status": critic_status,
                    "evidence": critic_evidence,
                },
            },
        }

    def _semantic_contract_obligations(
        para_rows: list[sqlite3.Row],
        rendered_paras: list[str],
        validation_report: sqlite3.Row | None,
    ) -> tuple[list[dict], dict[str, int]]:
        present_terms: set[str] = set()
        missing_terms: set[str] = set()
        unsupported_claims: set[str] = set()
        report_id = None
        if validation_report is not None:
            report_id = validation_report["id"]
            present_terms = {
                str(term).lower()
                for term in _json_finding_list(validation_report["required_terms_present"])
            }
            missing_terms = {
                str(term).lower()
                for term in _json_finding_list(validation_report["required_terms_missing"])
            }
            unsupported_claims = {
                str(claim).lower()
                for claim in _json_finding_list(validation_report["unsupported_claims"])
            }

        obligations: list[dict] = []

        def add(
            *,
            paragraph: int,
            kind: str,
            obligation: str,
            status: str,
            evidence: dict,
        ) -> None:
            obligations.append({
                "paragraph": paragraph,
                "kind": kind,
                "obligation": obligation,
                "status": status,
                "evidence": {
                    "validation_report_id": report_id,
                    **evidence,
                },
            })

        for index, row in enumerate(para_rows):
            paragraph = row["order_idx"]
            rendered_text = rendered_paras[index] if index < len(rendered_paras) else None

            add(
                paragraph=paragraph,
                kind="purpose",
                obligation=row["purpose"],
                status="not_evaluated",
                evidence={
                    "rendered_paragraph": rendered_text,
                    "reason": "Critic v0.1 does not evaluate paragraph purpose semantically.",
                },
            )

            for observation_id in _json_finding_list(row["required_observations"]):
                add(
                    paragraph=paragraph,
                    kind="required_observation",
                    obligation=str(observation_id),
                    status="not_evaluated",
                    evidence={
                        "source_id": observation_id,
                        "rendered_paragraph": rendered_text,
                        "reason": "Critic v0.1 does not evaluate Observation engagement.",
                    },
                )

            for interpretation_id in _json_finding_list(row["required_interpretations"]):
                add(
                    paragraph=paragraph,
                    kind="required_interpretation",
                    obligation=str(interpretation_id),
                    status="not_evaluated",
                    evidence={
                        "source_id": interpretation_id,
                        "rendered_paragraph": rendered_text,
                        "reason": "Critic v0.1 does not evaluate Interpretation application.",
                    },
                )

            for term in _json_finding_list(row["required_terms"]):
                name = str(term["term"])
                normalized = name.lower()
                if validation_report is None:
                    status = "not_evaluated"
                elif normalized in present_terms:
                    status = "satisfied"
                elif normalized in missing_terms:
                    status = "missing"
                else:
                    status = "not_evaluated"
                add(
                    paragraph=paragraph,
                    kind="required_term",
                    obligation=name,
                    status=status,
                    evidence={
                        "priority": term.get("priority", "recommended"),
                        "rendered_paragraph": rendered_text,
                    },
                )

            for claim in _json_finding_list(row["forbidden_claims"]):
                claim_text = str(claim)
                if validation_report is None:
                    status = "not_evaluated"
                elif claim_text.lower() in unsupported_claims:
                    status = "prohibited_claim_detected"
                else:
                    status = "satisfied"
                add(
                    paragraph=paragraph,
                    kind="forbidden_claim",
                    obligation=claim_text,
                    status=status,
                    evidence={"rendered_paragraph": rendered_text},
                )

        summary = {
            "total": len(obligations),
            "satisfied": sum(item["status"] == "satisfied" for item in obligations),
            "missing": sum(item["status"] == "missing" for item in obligations),
            "violations": sum(
                item["status"] == "prohibited_claim_detected"
                for item in obligations
            ),
            "not_evaluated": sum(
                item["status"] == "not_evaluated"
                for item in obligations
            ),
        }
        return obligations, summary

    def _provider_identity(
        provider_value: str,
        execution_config_value: object,
    ) -> tuple[str, str | None, dict | None]:
        execution_config = None
        if execution_config_value:
            try:
                parsed = json.loads(execution_config_value)
                if isinstance(parsed, dict):
                    execution_config = parsed
            except (TypeError, json.JSONDecodeError):
                execution_config = None

        provider_id = None
        model_id = None
        if execution_config:
            raw_provider = execution_config.get("provider")
            raw_model = execution_config.get("model_id")
            provider_id = str(raw_provider) if raw_provider else None
            model_id = str(raw_model) if raw_model else None
        if not provider_id:
            provider_id = provider_value.split("/", 1)[0]
        if not model_id and "/" in provider_value:
            model_id = provider_value.split("/", 1)[1]
        return provider_id, model_id, execution_config

    def _provider_matrix(
        conn: sqlite3.Connection,
        architect_plan_id: str,
        profile_slug: str,
    ) -> dict:
        plan = conn.execute(
            """
            SELECT ap.id, ap.blueprint_id, ap.title,
                   nb.title AS blueprint_title
            FROM architect_plans ap
            JOIN narrative_blueprints nb ON nb.id = ap.blueprint_id
            WHERE ap.id = ?
            """,
            (architect_plan_id,),
        ).fetchone()
        if plan is None:
            raise _LineageError(f"ArchitectPlan missing: {architect_plan_id}")

        profile = conn.execute(
            """
            SELECT id, slug, name, language
            FROM expression_profiles
            WHERE slug = ?
            """,
            (profile_slug,),
        ).fetchone()
        if profile is None:
            raise _LineageError(f"ExpressionProfile missing: {profile_slug}")

        narrative_rows = conn.execute(
            """
            SELECT id, provider, execution_config, created_at
            FROM rendered_narratives
            WHERE architect_plan_id = ?
              AND expression_profile_id = ?
            ORDER BY provider, created_at, id
            """,
            (architect_plan_id, profile["id"]),
        ).fetchall()

        registry_ids = set(active_provider_registry.ids())
        registry_definitions = {
            provider_id: active_provider_registry.definition(provider_id)
            for provider_id in registry_ids
        }
        executions = []
        for narrative in narrative_rows:
            provider_id, model_id, execution_config = _provider_identity(
                narrative["provider"],
                narrative["execution_config"],
            )
            definition = registry_definitions.get(provider_id)
            report = conn.execute(
                """
                SELECT id, approved, semantic_fidelity,
                       required_terms_missing, unsupported_claims,
                       warnings, created_at
                FROM validation_reports
                WHERE rendered_narrative_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (narrative["id"],),
            ).fetchone()

            validation_report = None
            if report:
                validation_report = {
                    "id": report["id"],
                    "approved": bool(report["approved"]),
                    "semantic_fidelity": report["semantic_fidelity"],
                    "required_terms_missing": json.loads(
                        report["required_terms_missing"]
                    ),
                    "unsupported_claims": json.loads(
                        report["unsupported_claims"]
                    ),
                    "warnings": json.loads(report["warnings"]),
                    "created_at": report["created_at"],
                }

            contract_href = (
                f"/api/fidelity/{plan['blueprint_id']}/{profile['slug']}"
                f"?narrative={narrative['id']}"
            )
            executions.append({
                "rendered_narrative": {
                    "id": narrative["id"],
                    "provider_identity": narrative["provider"],
                    "created_at": narrative["created_at"],
                },
                "provider": {
                    "id": provider_id,
                    "display_name": (
                        definition.display_name
                        if definition
                        else provider_id
                    ),
                    "registered": definition is not None,
                    "model_id": model_id,
                },
                "execution_config": execution_config,
                "validation_report": validation_report,
                "surfaces": {
                    "trust": (
                        f"/api/trust/rendered_narrative/{narrative['id']}"
                    ),
                    "lineage": (
                        f"/api/lineage/rendered_narrative/{narrative['id']}"
                    ),
                    "semantic_contract": contract_href,
                },
            })

        return {
            "architect_plan": {
                "id": plan["id"],
                "blueprint_id": plan["blueprint_id"],
                "title": plan["title"],
            },
            "expression_profile": {
                "id": profile["id"],
                "slug": profile["slug"],
                "name": profile["name"],
                "language": profile["language"],
            },
            "executions": executions,
        }

    def _reader_validation_report(
        conn: sqlite3.Connection,
        narrative_id: str,
    ) -> dict | None:
        report = conn.execute(
            """
            SELECT id, approved, semantic_fidelity,
                   required_terms_present, required_terms_missing,
                   unsupported_claims, warnings, created_at
            FROM validation_reports
            WHERE rendered_narrative_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (narrative_id,),
        ).fetchone()
        if report is None:
            return None
        pf_raw = report["profile_fidelity"] if "profile_fidelity" in report.keys() else None
        return {
            "id": report["id"],
            "approved": bool(report["approved"]),
            "semantic_fidelity": report["semantic_fidelity"],
            "required_terms_present": json.loads(
                report["required_terms_present"] or "[]"
            ),
            "required_terms_missing": json.loads(
                report["required_terms_missing"] or "[]"
            ),
            "unsupported_claims": json.loads(
                report["unsupported_claims"] or "[]"
            ),
            "warnings": json.loads(report["warnings"] or "[]"),
            "profile_fidelity": json.loads(pf_raw) if pf_raw else None,
            "created_at": report["created_at"],
        }

    def _reader_narrative_summary(
        conn: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict:
        return {
            "id": row["id"],
            "provider": row["provider"],
            "created_at": row["created_at"],
            "narrative_status": row["narrative_status"] or "pending",
            "narrative_rationale": row["narrative_rationale"],
            "profile": {
                "id": row["expression_profile_id"],
                "slug": row["profile_slug"],
                "name": row["profile_name"],
                "language": row["profile_language"],
            },
            "blueprint": {
                "id": row["blueprint_id"],
                "title": row["blueprint_title"],
                "thesis": row["blueprint_thesis"],
            },
            "architect_plan": {
                "id": row["architect_plan_id"],
                "title": row["architect_plan_title"],
            },
            "validation_report": _reader_validation_report(conn, row["id"]),
        }

    def _reader_narrative_detail(
        conn: sqlite3.Connection,
        narrative_id: str,
    ) -> dict:
        row = conn.execute(
            """
            SELECT rn.id, rn.architect_plan_id, rn.expression_profile_id,
                   rn.provider, rn.text, rn.prompt_used, rn.execution_config,
                   rn.created_at, rn.narrative_status, rn.narrative_rationale,
                   ep.slug AS profile_slug, ep.name AS profile_name,
                   ep.language AS profile_language, ep.audience AS profile_audience,
                   ep.reading_level AS profile_reading_level,
                   ap.title AS architect_plan_title,
                   ap.blueprint_id,
                   nb.title AS blueprint_title, nb.thesis AS blueprint_thesis
            FROM rendered_narratives rn
            JOIN architect_plans ap ON ap.id = rn.architect_plan_id
            JOIN narrative_blueprints nb ON nb.id = ap.blueprint_id
            LEFT JOIN expression_profiles ep ON ep.id = rn.expression_profile_id
            WHERE rn.id = ?
            """,
            (narrative_id,),
        ).fetchone()
        if row is None:
            raise _LineageError("rendered narrative not found")

        profile_slug = row["profile_slug"]
        semantic_contract = None
        if profile_slug:
            semantic_contract = (
                f"/api/fidelity/{row['blueprint_id']}/{profile_slug}"
                f"?narrative={row['id']}"
            )

        return {
            "rendered_narrative": {
                "id": row["id"],
                "provider": row["provider"],
                "text": row["text"],
                "prompt_used": row["prompt_used"],
                "execution_config": _json_loads(row["execution_config"], None),
                "created_at": row["created_at"],
            },
            "profile": {
                "id": row["expression_profile_id"],
                "slug": row["profile_slug"],
                "name": row["profile_name"],
                "language": row["profile_language"],
                "audience": row["profile_audience"],
                "reading_level": row["profile_reading_level"],
            },
            "blueprint": {
                "id": row["blueprint_id"],
                "title": row["blueprint_title"],
                "thesis": row["blueprint_thesis"],
            },
            "architect_plan": {
                "id": row["architect_plan_id"],
                "title": row["architect_plan_title"],
            },
            "validation_report": _reader_validation_report(conn, row["id"]),
            "surfaces": {
                "copy_source": "rendered_narrative.text",
                "trust": f"/api/trust/rendered_narrative/{row['id']}",
                "lineage": f"/api/lineage/rendered_narrative/{row['id']}",
                "semantic_contract": semantic_contract,
            },
        }

    def _canonical_ref(epistemic_class: str, object_id: str) -> dict[str, str]:
        return {
            "epistemic_class": epistemic_class,
            "id": object_id,
        }

    def _workspace_projection(
        conn: sqlite3.Connection,
        root_class: str,
        root_id: str,
        interface_profile: str,
    ) -> dict:
        ancestry = _lineage_graph(conn, root_class, root_id)
        references: set[tuple[str, str]] = {
            (node["class"], node["id"])
            for node in ancestry["nodes"]
        }
        descendant_queue: list[tuple[str, str]] = [(root_class, root_id)]
        expanded: set[tuple[str, str]] = set()

        def add_descendant(epistemic_class: str, object_id: str) -> None:
            ref = (epistemic_class, object_id)
            if ref not in references:
                references.add(ref)
                descendant_queue.append(ref)

        while descendant_queue:
            epistemic_class, object_id = descendant_queue.pop(0)
            ref = (epistemic_class, object_id)
            if ref in expanded:
                continue
            expanded.add(ref)

            if epistemic_class == "SourceDocument":
                rows = conn.execute(
                    "SELECT id FROM source_extractions WHERE document_id = ? ORDER BY id",
                    (object_id,),
                ).fetchall()
                for row in rows:
                    add_descendant("SourceExtraction", row["id"])
            elif epistemic_class == "SourceExtraction":
                rows = conn.execute(
                    "SELECT id FROM observations WHERE source_extraction_id = ? ORDER BY id",
                    (object_id,),
                ).fetchall()
                for row in rows:
                    add_descendant("Observation", row["id"])
            elif epistemic_class == "Observation":
                rows = conn.execute(
                    "SELECT id FROM interpretations WHERE observation_id = ? ORDER BY id",
                    (object_id,),
                ).fetchall()
                for row in rows:
                    add_descendant("Interpretation", row["id"])
                rows = conn.execute(
                    """
                    SELECT blueprint_id AS id
                    FROM blueprint_observation_links
                    WHERE observation_id = ?
                    ORDER BY blueprint_id
                    """,
                    (object_id,),
                ).fetchall()
                for row in rows:
                    add_descendant("Blueprint", row["id"])
            elif epistemic_class == "Interpretation":
                rows = conn.execute(
                    """
                    SELECT blueprint_id AS id
                    FROM blueprint_interpretation_links
                    WHERE interpretation_id = ?
                    ORDER BY blueprint_id
                    """,
                    (object_id,),
                ).fetchall()
                for row in rows:
                    add_descendant("Blueprint", row["id"])
            elif epistemic_class == "Blueprint":
                rows = conn.execute(
                    "SELECT id FROM architect_plans WHERE blueprint_id = ? ORDER BY id",
                    (object_id,),
                ).fetchall()
                for row in rows:
                    add_descendant("ArchitectPlan", row["id"])
            elif epistemic_class == "ArchitectPlan":
                rows = conn.execute(
                    """
                    SELECT id
                    FROM rendered_narratives
                    WHERE architect_plan_id = ?
                    ORDER BY id
                    """,
                    (object_id,),
                ).fetchall()
                for row in rows:
                    add_descendant("RenderedNarrative", row["id"])

        interpretation_ids = sorted(
            object_id
            for epistemic_class, object_id in references
            if epistemic_class == "Interpretation"
        )
        for interpretation_id in interpretation_ids:
            row = conn.execute(
                "SELECT perspective_id FROM interpretations WHERE id = ?",
                (interpretation_id,),
            ).fetchone()
            if row and row["perspective_id"]:
                perspective = conn.execute(
                    "SELECT id FROM perspectives WHERE id = ?",
                    (row["perspective_id"],),
                ).fetchone()
                if perspective:
                    references.add(("Perspective", perspective["id"]))

        narrative_ids = sorted(
            object_id
            for epistemic_class, object_id in references
            if epistemic_class == "RenderedNarrative"
        )
        for narrative_id in narrative_ids:
            narrative = conn.execute(
                """
                SELECT expression_profile_id
                FROM rendered_narratives
                WHERE id = ?
                """,
                (narrative_id,),
            ).fetchone()
            if narrative and narrative["expression_profile_id"]:
                profile = conn.execute(
                    "SELECT id FROM expression_profiles WHERE id = ?",
                    (narrative["expression_profile_id"],),
                ).fetchone()
                if profile:
                    references.add(("ExpressionProfile", profile["id"]))
            reports = conn.execute(
                """
                SELECT id
                FROM validation_reports
                WHERE rendered_narrative_id = ?
                ORDER BY id
                """,
                (narrative_id,),
            ).fetchall()
            for report in reports:
                references.add(("CriticReport", report["id"]))

        related: dict[str, list[str]] = {}
        for epistemic_class, object_id in sorted(references):
            if (epistemic_class, object_id) == (root_class, root_id):
                continue
            related.setdefault(epistemic_class, []).append(object_id)

        root_path = _WORKSPACE_CLASS_PATHS[root_class]
        trust_surfaces: list[dict] = []
        contract_surfaces: list[dict] = []
        critic_surfaces: list[dict] = []
        surfaces: dict[str, object] = {
            "lineage": {
                "focus": _canonical_ref(root_class, root_id),
                "href": f"/api/lineage/{root_path}/{root_id}",
            },
            "trust": trust_surfaces,
            "semantic_contract": contract_surfaces,
            "critic": critic_surfaces,
        }

        for narrative_id in narrative_ids:
            narrative_ref = _canonical_ref("RenderedNarrative", narrative_id)
            trust_surfaces.append({
                "rendered_narrative": narrative_ref,
                "href": f"/api/trust/rendered_narrative/{narrative_id}",
            })

            row = conn.execute(
                """
                SELECT rn.architect_plan_id, ap.blueprint_id, ep.slug
                FROM rendered_narratives rn
                JOIN architect_plans ap ON ap.id = rn.architect_plan_id
                LEFT JOIN expression_profiles ep
                  ON ep.id = rn.expression_profile_id
                WHERE rn.id = ?
                """,
                (narrative_id,),
            ).fetchone()
            if row and row["slug"]:
                contract_href = (
                    f"/api/fidelity/{row['blueprint_id']}/{row['slug']}"
                )
                contract_surfaces.append({
                    "architect_plan": _canonical_ref(
                        "ArchitectPlan",
                        row["architect_plan_id"],
                    ),
                    "rendered_narrative": narrative_ref,
                    "href": contract_href,
                })

                reports = conn.execute(
                    """
                    SELECT id
                    FROM validation_reports
                    WHERE rendered_narrative_id = ?
                    ORDER BY id
                    """,
                    (narrative_id,),
                ).fetchall()
                for report in reports:
                    critic_surfaces.append({
                        "critic_report": _canonical_ref(
                            "CriticReport",
                            report["id"],
                        ),
                        "rendered_narrative": narrative_ref,
                        "href": contract_href,
                    })

        return {
            "focus": _canonical_ref(root_class, root_id),
            "interface_profile": interface_profile,
            "related": related,
            "surfaces": surfaces,
        }

    # ── Static ──────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        resp = make_response(send_from_directory(str(STATIC_DIR), "index.html"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        return resp

    # ── /api/health ──────────────────────────────────────────────────────────

    # ── First-run setup (issue #20) ───────────────────────────────────
    # A fresh environment must be usable from the UI alone — no SSH,
    # Flask, SQLite, or pipeline-script knowledge required. These
    # endpoints are strictly additive: init never touches existing data,
    # and the demo compile is idempotent (SHA-256 dedupe in the Compiler).
    _DEMO_CORPUS = Path(__file__).resolve().parents[2] / "examples" / "gatsby.pdf"

    def _setup_state_payload() -> dict:
        exists = db_path.exists()
        doc_count = 0
        if exists:
            try:
                conn = _conn()
                doc_count = conn.execute(
                    "SELECT COUNT(*) FROM source_documents"
                ).fetchone()[0]
                conn.close()
            except Exception:
                doc_count = 0
        return {
            "database_exists": exists,
            "document_count": doc_count,
            "db_path": str(db_path),
            "runtime": {
                "workspace": _runtime_workspace_payload(),
            },
            "demo_available": _DEMO_CORPUS.exists(),
            "first_run": (not exists) or doc_count == 0,
        }

    @app.route("/api/setup/state")
    def api_setup_state():
        return jsonify(_setup_state_payload())

    @app.route("/api/setup/init", methods=["POST"])
    def api_setup_init():
        created = False
        if not db_path.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            from ..storage.sqlite import SQLiteStore as _Store
            from ..storage.sqlite import ensure_profile_tables as _migrate
            store = _Store(db_path)
            store.close()
            _mconn = sqlite3.connect(str(db_path))
            _mconn.row_factory = sqlite3.Row
            try:
                _migrate(_mconn)
            finally:
                _mconn.close()
            created = True
        return jsonify({"created": created, **_setup_state_payload()})

    @app.route("/api/setup/demo", methods=["POST"])
    def api_setup_demo():
        if not _DEMO_CORPUS.exists():
            return jsonify({"error": "no demo corpus is bundled with this install"}), 404
        api_setup_init()  # ensure the workspace exists; idempotent
        from ..compiler.compiler import Compiler
        try:
            compiler = Compiler(db_path=db_path, build_dir=db_path.parent)
            compiler.compile(_DEMO_CORPUS)
            compiler.close()
        except Exception as exc:
            return jsonify({"error": f"demo compile failed: {exc}"}), 500
        return jsonify(_setup_state_payload())

    @app.route("/api/runtime/workspace")
    def api_runtime_workspace():
        return jsonify({
            "workspace": _runtime_workspace_payload(),
            "capabilities": {"workspace_switch": False},
        })

    def _workspace_create_conflict_payload(slug: str) -> dict:
        payload: dict = {"error": f"workspace already exists: {slug}"}
        try:
            record = inspect_workspace(slug)
        except WorkspaceLifecycleError:
            return payload
        payload["workspace"] = _workspace_payload(
            record,
            is_active=_same_runtime_db(record.db_path),
        )
        return payload

    @app.route("/api/workspaces", methods=["GET", "POST"])
    def api_workspaces():
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            raw_name = body.get("name") if isinstance(body, dict) else None
            name = str(raw_name or "").strip()
            try:
                record = create_workspace(name)
            except WorkspaceAlreadyExistsError as exc:
                return jsonify(_workspace_create_conflict_payload(exc.slug)), 409
            except WorkspaceNameReservedError as exc:
                return jsonify({"error": str(exc)}), 400
            except WorkspaceLifecycleError as exc:
                return jsonify({"error": str(exc)}), 400
            return jsonify({
                "workspace": _workspace_payload(
                    record,
                    is_active=_same_runtime_db(record.db_path),
                )
            }), 201
        return jsonify({"workspaces": _workspace_catalog_payload()})

    @app.route("/api/health")
    def api_health():
        if not db_path.exists():
            return jsonify({"error": f"database not found: {db_path}"}), 404

        conn = _conn()
        doc_row = conn.execute(
            "SELECT original_filename FROM source_documents LIMIT 1"
        ).fetchone()

        ok, note = compiler_ok(conn)
        covered, total, fraction = coverage_metrics(conn)

        data = {
            "db_path": str(db_path),
            "runtime": {
                "endpoint_reachable": True,
                "database_available": True,
                "workspace": _runtime_workspace_payload(),
            },
            "compiler_ok": ok,
            "compiler_note": note,
            "document": {
                "filename": doc_row["original_filename"] if doc_row else None,
            },
            "observations": observation_count(conn),
            "field_terms": field_term_count(conn),
            "interpretations": interpretation_count(conn),
            "perspectives": perspective_count(conn),
            "contradictions": contradiction_count(conn),
            "blueprints": blueprint_count(conn),
            "essays": 0,
            "covered_count": covered,
            "total_count": total,
            "coverage_pct": round(fraction * 100, 1),
        }
        conn.close()
        return jsonify(data)

    # ── /api/search ──────────────────────────────────────────────────────────

    @app.route("/api/search")
    def api_search():
        q = request.args.get("q", "").strip()
        limit = min(int(request.args.get("limit", 15)), 50)

        if not q or not db_path.exists():
            return jsonify({"query": q, "count": 0, "results": []})

        conn = _conn()
        all_rows = conn.execute(
            """
            SELECT o.id, o.page, o.paragraph, o.sentence,
                   COALESCE(od.normalized_text, o.raw_text) AS normalized_text,
                   o.source_document_id, sd.original_filename, sd.source_role
            FROM observations o
            LEFT JOIN observation_derived od ON od.observation_id = o.id
            LEFT JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
            ORDER BY o.page, o.paragraph, o.sentence
            """
        ).fetchall()

        id_to_index = {r["id"]: i + 1 for i, r in enumerate(all_rows)}
        q_lower = q.lower()

        matches = [
            {
                "obs_index": id_to_index[r["id"]],
                "page": r["page"],
                "paragraph": r["paragraph"],
                "sentence": r["sentence"],
                "text": r["normalized_text"],
                "id": r["id"],
                "document_name": r["original_filename"],
                "source_role": r["source_role"] or "primary",
            }
            for r in all_rows
            if q_lower in r["normalized_text"].lower()
        ]
        conn.close()

        return jsonify({
            "query": q,
            "count": len(matches),
            "results": matches[:limit],
        })

    # ── /api/trace/<obs_index> ────────────────────────────────────────────────

    @app.route("/api/trace/<int:obs_index>")
    def api_trace(obs_index: int):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        all_ids = _all_obs_ids(conn)

        if obs_index < 1 or obs_index > len(all_ids):
            conn.close()
            return jsonify({"error": f"OBS-{obs_index} not found"}), 404

        obs_id = all_ids[obs_index - 1]
        obs_row = conn.execute(
            """
            SELECT o.id, o.page, o.paragraph, o.sentence,
                   COALESCE(od.normalized_text, o.raw_text) AS normalized_text
            FROM observations o
            LEFT JOIN observation_derived od ON od.observation_id = o.id
            WHERE o.id = ?
            """,
            (obs_id,),
        ).fetchone()

        layers = []

        # ── Layer 0: Observation ──
        layers.append({
            "type": "observation",
            "name": "Observation",
            "exists": True,
            "content": {
                "obs_index": obs_index,
                "text": obs_row["normalized_text"],
                "page": obs_row["page"],
                "paragraph": obs_row["paragraph"],
                "sentence": obs_row["sentence"],
                "id": obs_row["id"],
            },
        })

        # ── Layer 1: Interpretations ──
        interp_rows = conn.execute(
            "SELECT id, perspective, text, evidential_status FROM interpretations "
            "WHERE observation_id = ? ORDER BY created_at",
            (obs_id,),
        ).fetchall()

        if interp_rows:
            layers.append({
                "type": "interpretations",
                "name": "Interpretations",
                "exists": True,
                "content": [
                    {
                        "id": r["id"],
                        "perspective": r["perspective"],
                        "text": r["text"],
                        "evidential_status": r["evidential_status"],
                    }
                    for r in interp_rows
                ],
            })
        else:
            layers.append({
                "type": "interpretations",
                "name": "Interpretations",
                "exists": False,
                "content": None,
            })

        # ── Perspectives (derived from interpretations) ──
        if interp_rows:
            perspective_names = list(dict.fromkeys(r["perspective"] for r in interp_rows))
            persp_rows = []
            for name in perspective_names:
                row = conn.execute(
                    "SELECT name, description FROM perspectives WHERE name = ?", (name,)
                ).fetchone()
                if row:
                    persp_rows.append({"name": row["name"], "description": row["description"]})
                else:
                    persp_rows.append({"name": name, "description": ""})

            layers.append({
                "type": "perspectives",
                "name": "Perspectives",
                "exists": True,
                "content": persp_rows,
            })
        else:
            layers.append({
                "type": "perspectives",
                "name": "Perspectives",
                "exists": False,
                "content": None,
            })

        # ── Layer 3: Narrative Blueprint ──
        bp_rows = conn.execute(
            """
            SELECT nb.id, nb.title, nb.thesis, nb.sections
            FROM narrative_blueprints nb
            JOIN blueprint_observation_links bol ON bol.blueprint_id = nb.id
            WHERE bol.observation_id = ?
            ORDER BY nb.created_at LIMIT 1
            """,
            (obs_id,),
        ).fetchall()

        if bp_rows:
            bp = bp_rows[0]
            sections = json.loads(bp["sections"])
            layers.append({
                "type": "blueprint",
                "name": "Narrative Blueprint",
                "exists": True,
                "content": {
                    "title": bp["title"],
                    "thesis": bp["thesis"],
                    "section_count": len(sections),
                },
            })
        else:
            layers.append({
                "type": "blueprint",
                "name": "Narrative Blueprint",
                "exists": False,
                "content": None,
            })

        # ── Layer 4a: Architect Plan ──
        arch_stale = False
        arch_row = None
        if bp_rows:
            bp_id = bp_rows[0]["id"]
            arch_row = conn.execute(
                "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
                (bp_id,),
            ).fetchone()
            if arch_row:
                arch_row = dict(arch_row)
                bp_sections = json.loads(bp_rows[0]["sections"])
                from ..storage.hashing import make_blueprint_id as _mk_hash
                current_hash = _mk_hash(
                    bp_rows[0]["title"], bp_rows[0]["thesis"], bp_sections
                )
                arch_stale = arch_row["blueprint_hash"] != current_hash

        if arch_row:
            para_rows = conn.execute(
                "SELECT order_idx, purpose, required_observations, required_interpretations, required_terms "
                "FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
                (arch_row["id"],),
            ).fetchall()
            layers.append({
                "type": "architect",
                "name": "Architect",
                "exists": True,
                "stale": arch_stale,
                "content": {
                    "id": arch_row["id"],
                    "title": arch_row["title"],
                    "paragraph_count": len(para_rows),
                    "stale": arch_stale,
                },
            })
        else:
            layers.append({
                "type": "architect",
                "name": "Architect",
                "exists": False,
                "stale": False,
                "content": None,
            })

        # ── Layer 4b: Artist (Rendered Narratives — one per expression profile) ──
        rn_rows: list[dict] = []
        if arch_row:
            rows = conn.execute(
                """
                SELECT rn.id, rn.provider, rn.created_at,
                       rn.expression_profile_id,
                       ep.name AS profile_name, ep.slug AS profile_slug, ep.language AS profile_language
                FROM rendered_narratives rn
                LEFT JOIN expression_profiles ep ON ep.id = rn.expression_profile_id
                WHERE rn.architect_plan_id = ?
                ORDER BY rn.created_at
                """,
                (arch_row["id"],),
            ).fetchall()
            rn_rows = [dict(r) for r in rows]

        layers.append({
            "type": "artist",
            "name": "Artist",
            "exists": len(rn_rows) > 0,
            "content": [
                {
                    "id": r["id"],
                    "provider": r["provider"],
                    "profile_slug": r["profile_slug"],
                    "profile_name": r["profile_name"],
                    "profile_language": r["profile_language"],
                    "created_at": r["created_at"],
                }
                for r in rn_rows
            ],
        })

        # ── Layer 4c: Critic (ValidationReport) ──
        vr_rows: list[dict] = []
        if rn_rows:
            # Fetch validation reports for all rendered narratives
            for rn in rn_rows:
                vr = conn.execute(
                    "SELECT * FROM validation_reports WHERE rendered_narrative_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (rn["id"],),
                ).fetchone()
                if vr:
                    vr_dict = dict(vr)
                    vr_dict["profile_name"] = rn.get("profile_name")
                    vr_dict["profile_slug"] = rn.get("profile_slug")
                    vr_rows.append(vr_dict)

        layers.append({
            "type": "critic",
            "name": "Critic",
            "exists": len(vr_rows) > 0,
            "content": [
                {
                    "id": r["id"],
                    "rendered_narrative_id": r["rendered_narrative_id"],
                    "semantic_fidelity": r["semantic_fidelity"],
                    "approved": bool(r["approved"]),
                    "profile_name": r.get("profile_name"),
                    "profile_slug": r.get("profile_slug"),
                    "required_terms_missing": json.loads(r["required_terms_missing"]),
                    "warnings": json.loads(r["warnings"]),
                }
                for r in vr_rows
            ],
        })

        # ── Layer 4d: Essay (Critic-approved output — future) ──
        layers.append({
            "type": "essay",
            "name": "Essay",
            "exists": False,
            "content": None,
        })

        conn.close()
        return jsonify({"obs_index": obs_index, "layers": layers})

    # ── /api/lineage/<epistemic_class>/<object_id> ────────────────────────────
    # Canonical Lineage API: backend returns ontology graph only. The frontend
    # may express this graph with different vocabularies, but must not
    # reconstruct or infer lineage.

    @app.route("/api/lineage/<epistemic_class>/<object_id>")
    def api_lineage(epistemic_class: str, object_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        root_class = _lineage_class(epistemic_class)
        if root_class is None:
            return jsonify({"error": f"unsupported lineage class: {epistemic_class}"}), 400

        conn = _conn()
        try:
            graph = _lineage_graph(conn, root_class, object_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        except _LineageError as exc:
            conn.close()
            message = str(exc)
            status = 404 if message.startswith(f"{root_class} missing:") else 409
            return jsonify({"error": message}), status
        conn.close()

        return jsonify(graph)

    # ── /api/workspace/<epistemic_class>/<object_id> ────────────────────────
    # Disposable projection over canonical references. It has no identifier,
    # persistence, provenance, authority status, or independent lineage.

    @app.route("/api/workspace/<epistemic_class>/<object_id>")
    def api_workspace(epistemic_class: str, object_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        interface_profile = request.args.get("profile", "").strip().lower()
        if interface_profile not in _WORKSPACE_PROFILES:
            return jsonify({
                "error": "profile must be one of: child, elder, scholar"
            }), 400

        root_class = _lineage_class(epistemic_class)
        if root_class is None:
            return jsonify({
                "error": f"unsupported workspace focus class: {epistemic_class}"
            }), 400

        conn = _conn()
        try:
            projection = _workspace_projection(
                conn,
                root_class,
                object_id,
                interface_profile,
            )
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        except _LineageError as exc:
            conn.close()
            message = str(exc)
            status = 404 if message.startswith(f"{root_class} missing:") else 409
            return jsonify({"error": message}), status
        conn.close()
        return jsonify(projection)

    # ── /api/divergence/interpretations/<a>/<b> ─────────────────────────────
    # ADR-0043 Pure Projection over existing canonical interpretation lineage.
    # No comparison result is assigned an ID or persisted.

    @app.route(
        "/api/divergence/interpretations/"
        "<interpretation_a_id>/<interpretation_b_id>"
    )
    def api_interpretive_divergence(
        interpretation_a_id: str,
        interpretation_b_id: str,
    ):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        try:
            projection = interpretive_divergence_projection(
                conn,
                interpretation_a_id,
                interpretation_b_id,
            )
        except InterpretiveDivergenceError as exc:
            conn.close()
            message = str(exc)
            status = 404 if message.startswith("interpretation missing:") else 409
            return jsonify({"error": message}), status
        conn.close()
        return jsonify(projection)

    # ── /api/trust/rendered_narrative/<object_id> ────────────────────────────
    # Read-only projection of persisted lineage, execution, and Critic facts.
    # The frontend renders these findings; it does not infer trust.

    @app.route("/api/trust/rendered_narrative/<object_id>")
    def api_trust_rendered_narrative(object_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        try:
            summary = _trust_summary(conn, object_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        except _LineageError as exc:
            conn.close()
            return jsonify({"error": str(exc)}), 404
        conn.close()
        return jsonify(summary)

    # ── /api/reader/narratives ──────────────────────────────────────────────
    # Read-only Reader View projection over existing RenderedNarrative rows.
    # This creates no new report object; the report is the RenderedNarrative.

    @app.route("/api/reader/narratives")
    def api_reader_narratives():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        rows = conn.execute(
            """
            SELECT rn.id, rn.architect_plan_id, rn.expression_profile_id,
                   rn.provider, rn.created_at,
                   rn.narrative_status, rn.narrative_rationale,
                   ep.slug AS profile_slug, ep.name AS profile_name,
                   ep.language AS profile_language,
                   ap.title AS architect_plan_title,
                   ap.blueprint_id,
                   nb.title AS blueprint_title, nb.thesis AS blueprint_thesis
            FROM rendered_narratives rn
            JOIN architect_plans ap ON ap.id = rn.architect_plan_id
            JOIN narrative_blueprints nb ON nb.id = ap.blueprint_id
            LEFT JOIN expression_profiles ep ON ep.id = rn.expression_profile_id
            ORDER BY rn.created_at DESC, rn.id
            """
        ).fetchall()
        narratives = [_reader_narrative_summary(conn, row) for row in rows]
        conn.close()
        return jsonify({
            "count": len(narratives),
            "narratives": narratives,
        })

    @app.route("/api/reader/narratives/<narrative_id>")
    def api_reader_narrative_detail(narrative_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        try:
            detail = _reader_narrative_detail(conn, narrative_id)
        except _LineageError as exc:
            conn.close()
            return jsonify({"error": str(exc)}), 404
        conn.close()
        return jsonify(detail)

    @app.route("/api/reader/narratives/<narrative_id>/steward", methods=["PATCH"])
    def api_reader_narrative_steward(narrative_id: str):
        """Narrative Stewardship — accept or reject a rendered narrative with rationale.

        Body: { status: "accepted"|"rejected"|"pending", rationale: str }

        The rationale is required when accepting or rejecting. It records WHY
        this narrative was kept or discarded — building a corpus of meta-interpretation
        that prepares for Stage 07 Synthesis.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        payload = request.get_json(silent=True) or {}
        status    = str(payload.get("status", "")).strip()
        rationale = str(payload.get("rationale", "")).strip()

        if status not in ("accepted", "rejected", "pending"):
            return jsonify({"error": "status must be 'accepted', 'rejected', or 'pending'"}), 400
        if status in ("accepted", "rejected") and not rationale:
            return jsonify({"error": "rationale is required when accepting or rejecting"}), 400

        conn = _conn_rw()
        try:
            row = conn.execute(
                "SELECT id FROM rendered_narratives WHERE id = ?", (narrative_id,)
            ).fetchone()
            if not row:
                return jsonify({"error": "narrative not found"}), 404

            conn.execute(
                "UPDATE rendered_narratives SET narrative_status = ?, narrative_rationale = ? WHERE id = ?",
                (status, rationale or None, narrative_id),
            )
            conn.commit()
            return jsonify({"id": narrative_id, "status": status, "rationale": rationale})
        except Exception as exc:
            import traceback as _tb
            return jsonify({"error": str(exc), "detail": _tb.format_exc()}), 500
        finally:
            conn.close()

    # ── /api/profiles ─────────────────────────────────────────────────────────

    @app.route("/api/profiles")
    def api_profiles():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()
        profiles = _list_profiles(conn)
        conn.close()
        return jsonify({"profiles": profiles})

    @app.route("/api/profiles", methods=["POST"])
    def api_profiles_create():
        """Create a steward-authored ExpressionProfile from the Reader "Voice" tab.

        #93 — capture the witness constraints (voice, audience, non-negotiables,
        phrases to preserve / avoid, critic expectations) the future Artist must
        honor and the Critic must verify. The witness fields are composed into the
        `artist_prompt` directive client-side (so the saved text equals the live
        preview); this endpoint validates and persists. ExpressionProfiles are
        immutable by table trigger — revising means saving a new version.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        artist_prompt = str(payload.get("artist_prompt") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        if not artist_prompt:
            return jsonify({"error": "artist_prompt is required"}), 400

        language = str(payload.get("language") or "en").strip() or "en"
        audience = (str(payload.get("audience") or "").strip() or None)
        tone = (str(payload.get("tone") or "").strip() or None)
        voice = (str(payload.get("voice") or "").strip() or None)
        reading_level = (str(payload.get("reading_level") or "").strip() or None)
        description = (str(payload.get("description") or "").strip() or None)
        critic_expectations = (str(payload.get("critic_expectations") or "").strip() or None)

        from ..storage.hashing import make_expression_profile_id
        from datetime import datetime, timezone
        import re as _re

        base_slug = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "voice"

        conn = _conn_rw()
        try:
            # Unique slug: append a short time token on collision (honest versioning).
            slug = base_slug
            exists = conn.execute(
                "SELECT 1 FROM expression_profiles WHERE slug = ?", (slug,)
            ).fetchone()
            if exists:
                slug = f"{base_slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

            profile_id = make_expression_profile_id(slug)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO expression_profiles
                    (id, slug, name, description, language, audience, reading_level,
                     tone, voice, artist_prompt, critic_expectations, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'steward-authored', ?)
                """,
                (profile_id, slug, name, description, language, audience, reading_level,
                 tone, voice, artist_prompt, critic_expectations, now),
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({"id": profile_id, "slug": slug, "name": name}), 201

    # ── /api/ecology ─────────────────────────────────────────────────────────
    # Non-epistemic, read-only projection of locally registered Artist adapters.
    # Registration conveys no trust, rank, provenance, or semantic standing.

    @app.route("/api/ecology")
    def api_ecology():
        return jsonify(active_provider_registry.ecology())

    # ── /api/provider-matrix/<architect_plan_id>/<profile_slug> ─────────────
    # Provider-neutral inspection surface. Every persisted realization is
    # returned independently; no provider is ranked or collapsed into a winner.

    @app.route("/api/provider-matrix/<architect_plan_id>/<profile_slug>")
    def api_provider_matrix(architect_plan_id: str, profile_slug: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        try:
            matrix = _provider_matrix(conn, architect_plan_id, profile_slug)
        except _LineageError as exc:
            conn.close()
            return jsonify({"error": str(exc)}), 404
        conn.close()
        return jsonify(matrix)

    # ── /fidelity ────────────────────────────────────────────────────────────

    @app.route("/fidelity")
    def fidelity_page():
        return send_from_directory(str(STATIC_DIR), "fidelity.html")

    # ── /api/fidelity/<blueprint_id>/<profile_slug> ───────────────────────────

    @app.route("/api/fidelity/<blueprint_id>/<profile_slug>")
    def api_fidelity(blueprint_id: str, profile_slug: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()

        profile = conn.execute(
            "SELECT * FROM expression_profiles WHERE slug = ?", (profile_slug,)
        ).fetchone()
        if not profile:
            conn.close()
            return jsonify({"error": f"profile not found: {profile_slug}"}), 404
        profile = dict(profile)

        bp = conn.execute(
            "SELECT id, title, thesis FROM narrative_blueprints WHERE id = ?", (blueprint_id,)
        ).fetchone()
        if not bp:
            conn.close()
            return jsonify({"error": "blueprint not found"}), 404

        ap = conn.execute(
            "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
            (blueprint_id,),
        ).fetchone()
        if not ap:
            conn.close()
            return jsonify({"error": "no architect plan for this blueprint"}), 404
        ap = dict(ap)

        para_rows = conn.execute(
            "SELECT order_idx, purpose, required_observations, "
            "required_interpretations, required_terms, forbidden_claims "
            "FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
            (ap["id"],),
        ).fetchall()

        requested_narrative_id = request.args.get("narrative", "").strip()
        if requested_narrative_id:
            rn = conn.execute(
                """
                SELECT id, text, provider, created_at
                FROM rendered_narratives
                WHERE id = ?
                  AND architect_plan_id = ?
                  AND expression_profile_id = ?
                """,
                (requested_narrative_id, ap["id"], profile["id"]),
            ).fetchone()
            if rn is None:
                conn.close()
                return jsonify({
                    "error": "rendered narrative does not belong to this contract"
                }), 404
        else:
            rn = conn.execute(
                "SELECT id, text, provider, created_at FROM rendered_narratives "
                "WHERE architect_plan_id = ? AND expression_profile_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (ap["id"], profile["id"]),
            ).fetchone()

        vr = None
        if rn:
            vr = conn.execute(
                "SELECT * FROM validation_reports WHERE rendered_narrative_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (rn["id"],),
            ).fetchone()

        # Split rendered text into paragraphs
        rendered_paras: list[str] = []
        if rn and rn["text"]:
            rendered_paras = [p.strip() for p in rn["text"].split("\n\n") if p.strip()]

        obligations, obligation_summary = _semantic_contract_obligations(
            list(para_rows),
            rendered_paras,
            vr,
        )

        # Build term lookup from validation report
        terms_present: set[str] = set()
        terms_missing: set[str] = set()
        if vr:
            terms_present = {t.lower() for t in json.loads(vr["required_terms_present"])}
            terms_missing = {t.lower() for t in json.loads(vr["required_terms_missing"])}

        paragraphs = []
        for i, row in enumerate(para_rows):
            req_terms = json.loads(row["required_terms"])
            forbidden = json.loads(row["forbidden_claims"])
            term_status = [
                {
                    "term": t["term"],
                    "priority": t.get("priority", "recommended"),
                    "present": t["term"].lower() in terms_present,
                    "status": (
                        "not_evaluated"
                        if vr is None
                        else "satisfied"
                        if t["term"].lower() in terms_present
                        else "missing"
                        if t["term"].lower() in terms_missing
                        else "not_evaluated"
                    ),
                }
                for t in req_terms
            ]
            paragraphs.append({
                "order_idx": row["order_idx"],
                "purpose": row["purpose"],
                "required_observations": json.loads(row["required_observations"]),
                "required_interpretations": json.loads(row["required_interpretations"]),
                "required_terms": term_status,
                "forbidden_claims": forbidden,
                "rendered_text": rendered_paras[i] if i < len(rendered_paras) else None,
            })

        conn.close()
        return jsonify({
            "blueprint": {"id": bp["id"], "title": bp["title"], "thesis": bp["thesis"]},
            "profile": profile,
            "architect_plan": {"id": ap["id"], "title": ap["title"]},
            "rendered_narrative": {
                "id": rn["id"],
                "provider": rn["provider"],
                "created_at": rn["created_at"],
            } if rn else None,
            "validation_report": {
                "id": vr["id"],
                "semantic_fidelity": vr["semantic_fidelity"],
                "approved": bool(vr["approved"]),
                "warnings": json.loads(vr["warnings"]),
                "unsupported_claims": json.loads(vr["unsupported_claims"]),
            } if vr else None,
            "obligation_summary": obligation_summary,
            "obligations": obligations,
            "paragraphs": paragraphs,
        })

    # ── /api/semantic-fidelity/<narrative_id> ────────────────────────────────
    # Projection endpoint: grouped semantic Findings for a RenderedNarrative.
    # Returns verdicts grouped by support_level so UI can render fidelity report.

    @app.route("/api/semantic-fidelity/<narrative_id>")
    def api_semantic_fidelity(narrative_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        narrative_row = conn.execute(
            "SELECT id, architect_plan_id, text FROM rendered_narratives WHERE id = ?",
            (narrative_id,),
        ).fetchone()
        if not narrative_row:
            conn.close()
            return jsonify({"error": "narrative not found"}), 404

        findings = conn.execute(
            "SELECT id, obligation_id, operation, status, evidence, evaluation_method, created_at "
            "FROM findings WHERE rendered_narrative_id = ? AND dimension = 'semantic' "
            "ORDER BY created_at",
            (narrative_id,),
        ).fetchall()
        conn.close()

        if not findings:
            return jsonify({
                "narrative_id": narrative_id,
                "status": "no_findings",
                "message": "Run the Critic to generate semantic findings.",
                "groups": {},
            }), 200

        groups: dict[str, list[dict]] = {
            "supported": [],
            "partially_supported": [],
            "weak": [],
            "omitted": [],
        }

        for f in findings:
            ev = json.loads(f["evidence"] or "{}")
            trace = ev.get("supporting_trace", {})
            support_level = trace.get("support_level", f["status"])
            entry = {
                "finding_id": f["id"],
                "obligation_id": f["obligation_id"],
                "term": ev.get("contract_obligation"),
                "status": f["status"],
                "operation": f["operation"],
                "observed_render": ev.get("observed_render"),
                "interpretation_matches": trace.get("interpretation_matches", []),
                "observation_matches": trace.get("observation_matches", []),
                "evaluation_method": f["evaluation_method"],
                "created_at": f["created_at"],
            }
            bucket = support_level if support_level in groups else "weak"
            groups[bucket].append(entry)

        counts = {k: len(v) for k, v in groups.items()}
        total = sum(counts.values())
        score = round(counts.get("supported", 0) / total, 3) if total else 0.0

        return jsonify({
            "narrative_id": narrative_id,
            "total_obligations": total,
            "score": score,
            "counts": counts,
            "groups": groups,
        })

    # ── /api/matrix ──────────────────────────────────────────────────────────
    # Expression Matrix: blueprints × profiles with render/validation status.

    @app.route("/api/matrix")
    def api_matrix():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        profiles = _list_profiles(conn)

        all_obs_ids = _all_obs_ids(conn)
        obs_id_to_index = {oid: i + 1 for i, oid in enumerate(all_obs_ids)}

        bp_rows = conn.execute(
            "SELECT id, title, thesis FROM narrative_blueprints ORDER BY created_at"
        ).fetchall()

        matrix = []
        for bp in bp_rows:
            bp_id = bp["id"]

            # Find the most recent architect plan for this blueprint
            ap = conn.execute(
                "SELECT id FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
                (bp_id,),
            ).fetchone()

            cells = {}
            for p in profiles:
                slug = p["slug"]
                profile_id = p["id"]
                if ap:
                    rn_rows = conn.execute(
                        """
                        SELECT id
                        FROM rendered_narratives
                        WHERE architect_plan_id = ?
                          AND expression_profile_id = ?
                        ORDER BY provider, created_at, id
                        """,
                        (ap["id"], profile_id),
                    ).fetchall()
                    if rn_rows:
                        reviewed_count = 0
                        approved_count = 0
                        for rn in rn_rows:
                            vr = conn.execute(
                                """
                                SELECT approved
                                FROM validation_reports
                                WHERE rendered_narrative_id = ?
                                ORDER BY created_at DESC
                                LIMIT 1
                                """,
                                (rn["id"],),
                            ).fetchone()
                            if vr:
                                reviewed_count += 1
                                approved_count += int(bool(vr["approved"]))
                        cells[slug] = {
                            "rendered": True,
                            "render_count": len(rn_rows),
                            "reviewed_count": reviewed_count,
                            "approved_count": approved_count,
                        }
                    else:
                        cells[slug] = {
                            "rendered": False,
                            "render_count": 0,
                            "reviewed_count": 0,
                            "approved_count": 0,
                        }
                else:
                    cells[slug] = {
                        "rendered": False,
                        "render_count": 0,
                        "reviewed_count": 0,
                        "approved_count": 0,
                    }

            # Find an obs_index linked to this blueprint for deep-linking
            link_obs = conn.execute(
                "SELECT observation_id FROM blueprint_observation_links WHERE blueprint_id = ? LIMIT 1",
                (bp_id,),
            ).fetchone()
            linked_obs_index = obs_id_to_index.get(link_obs["observation_id"]) if link_obs else None

            matrix.append({
                "id": bp_id,
                "title": bp["title"],
                "thesis": bp["thesis"],
                "architect_plan_id": ap["id"] if ap else None,
                "obs_index": linked_obs_index,
                "cells": cells,
            })

        conn.close()
        return jsonify({"profiles": profiles, "blueprints": matrix})

    # ── /api/coverage ────────────────────────────────────────────────────────

    @app.route("/api/coverage")
    def api_coverage():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        all_rows = conn.execute(
            """
            SELECT o.id
            FROM observations o
            JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
            ORDER BY o.page, o.paragraph, o.sentence
            """
        ).fetchall()
        id_to_index = {r["id"]: i + 1 for i, r in enumerate(all_rows)}

        covered: set[str] = set()
        for row in conn.execute("SELECT DISTINCT observation_id FROM interpretations"):
            covered.add(row[0])
        for row in conn.execute("SELECT evidence_observation_ids FROM interpretations"):
            try:
                ids = json.loads(row[0] or "[]")
                covered.update(ids)
            except (json.JSONDecodeError, TypeError):
                pass
        try:
            for row in conn.execute("SELECT DISTINCT observation_id FROM blueprint_observation_links"):
                covered.add(row[0])
        except Exception:
            pass

        obs_rows = [
            {"obs_index": id_to_index[oid], "id": oid}
            for oid in sorted(covered, key=lambda x: id_to_index.get(x, 0))
            if oid in id_to_index
        ]
        conn.close()
        return jsonify({"count": len(obs_rows), "observations": obs_rows})

    # ── E10 vertical slice API ───────────────────────────────────────────────

    @app.route("/api/e10/observations")
    def api_e10_observations():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        q = request.args.get("q", "").strip().lower()
        filter_name = request.args.get("filter", "all").strip().lower()
        limit = min(max(int(request.args.get("limit", 40)), 1), 100)

        conn = _conn()
        rows = conn.execute(
            """
            SELECT o.id, o.page, o.paragraph, o.sentence, o.raw_text,
                   o.source_locator, o.source_document_id,
                   sd.original_filename, sd.source_role
            FROM observations o
            LEFT JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
            ORDER BY o.page, o.paragraph, o.sentence
            """
        ).fetchall()
        id_to_index = {row["id"]: index + 1 for index, row in enumerate(rows)}
        interp_counts = {
            row["observation_id"]: row["count"]
            for row in conn.execute(
                "SELECT observation_id, COUNT(*) AS count FROM interpretations GROUP BY observation_id"
            ).fetchall()
        } if _table_exists(conn, "interpretations") else {}
        proposal_counts = {
            row["observation_id"]: row["count"]
            for row in conn.execute(
                "SELECT observation_id, COUNT(*) AS count FROM proposed_interpretations GROUP BY observation_id"
            ).fetchall()
        } if _table_exists(conn, "proposed_interpretations") else {}
        critic_counts = {
            row["observation_id"]: row["count"]
            for row in conn.execute(
                "SELECT observation_id, COUNT(*) AS count FROM critic_reports GROUP BY observation_id"
            ).fetchall()
        } if _table_exists(conn, "critic_reports") else {}

        results = []
        for row in rows:
            text = row["raw_text"]
            interpretation_count = interp_counts.get(row["id"], 0)
            proposal_count = proposal_counts.get(row["id"], 0)
            critic_report_count = critic_counts.get(row["id"], 0)
            if q and q not in text.lower():
                continue
            if filter_name == "uninterpreted" and interpretation_count > 0:
                continue
            if filter_name == "interpreted" and interpretation_count == 0:
                continue
            if filter_name == "pending" and proposal_count == 0:
                continue
            if filter_name == "critic" and critic_report_count == 0:
                continue
            results.append({
                "obs_index": id_to_index[row["id"]],
                "id": row["id"],
                "page": row["page"],
                "paragraph": row["paragraph"],
                "sentence": row["sentence"],
                "source_locator": row["source_locator"],
                "source_document_id": row["source_document_id"],
                "document_name": row["original_filename"],
                "source_role": row["source_role"] or "primary",
                "raw_text": text,
                "interpretation_count": interpretation_count,
                "proposal_count": proposal_count,
                "critic_report_count": critic_report_count,
            })
        conn.close()
        return jsonify({
            "query": q,
            "filter": filter_name,
            "count": len(results),
            "observations": results[:limit],
        })

    @app.route("/api/e10/providers")
    def api_e10_providers():
        system_store_status = active_credential_store.status()
        return jsonify({
            "credential_storage": "session_environment_or_system_store",
            "stores_api_keys": True,
            "persistent_api_keys": bool(system_store_status.get("available")),
            "system_credential_store": system_store_status,
            "live_connection_test": True,
            "providers": _e10_provider_statuses(),
        })

    @app.route("/api/e10/scope")
    def api_e10_scope():
        """Return the active corpus scope: primary, supporting, muted documents and observation counts."""
        if not db_path.exists():
            return jsonify({"documents": [], "primary_count": 0, "supporting_count": 0, "muted_count": 0})
        conn = _conn()
        rows = conn.execute(
            """
            SELECT sd.id, sd.original_filename, sd.total_pages, sd.registered_at,
                   sd.excluded_from_analysis, sd.source_role,
                   COUNT(DISTINCT o.id) AS observation_count
            FROM source_documents sd
            LEFT JOIN observations o ON o.source_document_id = sd.id
            GROUP BY sd.id
            ORDER BY sd.registered_at ASC
            """
        ).fetchall()
        conn.close()
        docs = [
            {
                "id": r["id"],
                "filename": r["original_filename"],
                "total_pages": r["total_pages"],
                "observation_count": r["observation_count"],
                "excluded": bool(r["excluded_from_analysis"]),
                "source_role": r["source_role"] or "primary",
            }
            for r in rows
        ]
        primary   = [d for d in docs if not d["excluded"] and d["source_role"] == "primary"]
        supporting = [d for d in docs if not d["excluded"] and d["source_role"] != "primary"]
        muted     = [d for d in docs if d["excluded"]]
        return jsonify({
            "documents": docs,
            "primary":   primary,
            "supporting": supporting,
            "muted":     muted,
            "primary_count":   len(primary),
            "supporting_count": len(supporting),
            "muted_count":     len(muted),
            "boundary_clear":  len(primary) > 0 and len(docs) > 0,
        })

    @app.route("/api/e10/providers/<participant>/key", methods=["PUT", "DELETE"])
    def api_e10_provider_key(participant: str):
        participant_info = _e10_participant(participant)
        if participant_info is None:
            return jsonify({"error": f"unsupported participant: {participant}"}), 400
        key, label, _ = participant_info
        provider_id = _E10_PARTICIPANTS[key][1]
        try:
            active_provider_registry.definition(provider_id)
        except KeyError:
            return jsonify({
                "error": f"{label} has no registered provider adapter"
            }), 409

        payload = request.get_json(silent=True) or {}
        provider_meta = active_provider_registry.definition(provider_id).metadata()
        source_state = _credential_source_for_provider(provider_meta)

        if request.method == "DELETE":
            source_kind = str(payload.get("credential_source") or source_state.get("kind") or "").strip()
            if source_kind == "system_store":
                old_secret = None
                old_secret_present = False
                try:
                    old_secret = active_credential_store.get_password(provider_id)
                    old_secret_present = old_secret is not None
                    active_credential_store.delete_password(provider_id)
                    if source_state.get("kind") == "system_store":
                        _set_persisted_credential_source(provider_id, {
                            "kind": "system_store",
                            "configured": False,
                            "service": CREDENTIAL_SERVICE_NAME,
                            "account": provider_id,
                        })
                except (UnsupportedConnectionsSettingsError, OSError) as exc:
                    if old_secret_present and old_secret is not None:
                        try:
                            active_credential_store.set_password(provider_id, old_secret)
                        except CredentialStoreError as rollback_exc:
                            return jsonify({
                                "error": (
                                    "System credential was removed, but Hermeneia could not restore it "
                                    f"after metadata update failed: {rollback_exc}"
                                )
                            }), 500
                    return jsonify({"error": f"Could not update credential source after removing system credential: {exc}"}), 500
                except CredentialStoreError as exc:
                    return jsonify({"error": f"Could not remove system credential: {exc}"}), 500
                return jsonify({
                    "participant": key,
                    "configured": False,
                    "credential_scope": "system_store",
                    "credential_source_kind": "system_store",
                    "message": f"System credential removed for {label}.",
                })
            with runtime_provider_keys_lock:
                runtime_provider_keys.pop(provider_id, None)
                runtime_credential_sources.pop(provider_id, None)
            return jsonify({
                "participant": key,
                "configured": False,
                "credential_scope": "session",
                "credential_source_kind": "session",
                "message": f"Session key removed for {label}.",
            })

        api_key = str(payload.get("api_key", "")).strip()
        source_kind = str(payload.get("credential_source") or "session").strip()
        if source_kind == "environment":
            env_name = provider_meta.get("required_environment")
            if not env_name:
                return jsonify({"error": f"{label} has no environment credential source"}), 400
            try:
                _set_persisted_credential_source(provider_id, {
                    "kind": "environment",
                    "environment_variable": env_name,
                })
            except (UnsupportedConnectionsSettingsError, OSError, InvalidConnectionsSettingError) as exc:
                return jsonify({"error": f"Could not save credential source: {exc}"}), 500
            with runtime_provider_keys_lock:
                runtime_provider_keys.pop(provider_id, None)
                runtime_credential_sources.pop(provider_id, None)
            return jsonify({
                "participant": key,
                "configured": bool(os.environ.get(str(env_name))),
                "credential_scope": "environment",
                "credential_source_kind": "environment",
                "message": f"Environment credential source selected for {label}.",
            })
        if source_kind not in {"session", "system_store"}:
            return jsonify({"error": "credential_source must be session, environment, or system_store"}), 400
        if source_kind != "system_store" and len(api_key) < 8:
            return jsonify({"error": "api_key must contain at least 8 characters"}), 400
        if source_kind == "system_store":
            prior_secret = None
            prior_secret_present = False
            try:
                prior_secret = active_credential_store.get_password(provider_id)
                prior_secret_present = prior_secret is not None
                if api_key:
                    if len(api_key) < 8:
                        return jsonify({"error": "api_key must contain at least 8 characters"}), 400
                    active_credential_store.set_password(provider_id, api_key)
                elif not active_credential_store.has_password(provider_id):
                    return jsonify({"error": "System credential is not configured; enter an API key to save one."}), 400
                _set_persisted_credential_source(provider_id, {
                    "kind": "system_store",
                    "configured": True,
                    "service": CREDENTIAL_SERVICE_NAME,
                    "account": provider_id,
                })
            except CredentialStoreError as exc:
                return jsonify({"error": f"System credential store unavailable: {exc}"}), 503
            except (UnsupportedConnectionsSettingsError, OSError, InvalidConnectionsSettingError) as exc:
                try:
                    if prior_secret_present and prior_secret is not None:
                        active_credential_store.set_password(provider_id, prior_secret)
                    elif api_key:
                        active_credential_store.delete_password(provider_id)
                except CredentialStoreError as rollback_exc:
                    return jsonify({
                        "error": (
                            "System credential was changed, but Hermeneia could not restore the prior "
                            f"credential after metadata update failed: {rollback_exc}"
                        )
                    }), 500
                return jsonify({"error": f"Could not save credential source: {exc}"}), 500
            with runtime_provider_keys_lock:
                runtime_provider_keys.pop(provider_id, None)
                runtime_credential_sources.pop(provider_id, None)
            return jsonify({
                "participant": key,
                "configured": True,
                "credential_scope": "system_store",
                "credential_source_kind": "system_store",
                "message": f"System credential saved for {label}.",
            })
        with runtime_provider_keys_lock:
            runtime_credential_sources[provider_id] = "session"
        try:
            _set_persisted_credential_source(provider_id, {"kind": "session"})
        except (UnsupportedConnectionsSettingsError, OSError, InvalidConnectionsSettingError) as exc:
            with runtime_provider_keys_lock:
                runtime_credential_sources.pop(provider_id, None)
            return jsonify({"error": f"Could not save credential source: {exc}"}), 500
        with runtime_provider_keys_lock:
            runtime_provider_keys[provider_id] = api_key
        return jsonify({
            "participant": key,
            "configured": True,
            "credential_scope": "session",
            "credential_source_kind": "session",
            "message": (
                f"Session key saved for {label}. "
                "It will be forgotten when the Hermeneia server stops."
            ),
        })

    @app.route("/api/e10/providers/<participant>/model", methods=["PUT"])
    def api_e10_provider_model(participant: str):
        participant_info = _e10_participant(participant)
        if participant_info is None:
            return jsonify({"error": f"unsupported participant: {participant}"}), 400
        key, label, _ = participant_info
        provider_id = _E10_PARTICIPANTS[key][1]
        try:
            definition = active_provider_registry.definition(provider_id)
        except KeyError:
            return jsonify({
                "error": f"{label} has no registered provider adapter"
            }), 409

        payload = request.get_json(silent=True) or {}
        model = str(payload.get("model") or "").strip()
        if not model:
            return jsonify({"error": "model is required"}), 400

        catalog = _provider_model_catalog(provider_id, definition.metadata())
        catalog_ids = _catalog_model_ids(catalog)
        if catalog.get("status") != "available":
            verify_error = (
                "Ollama is not reachable, so Hermeneia cannot verify installed models. "
                "Start Ollama and choose from the discovered installed models."
                if provider_id.startswith("ollama-")
                else (
                    "Hermeneia cannot verify available models for this provider. "
                    "Resolve the catalog status and choose from the discovered models."
                )
            )
            return jsonify({
                "error": verify_error,
                "catalog_source": catalog.get("catalog_source"),
                "catalog_status": catalog.get("status"),
                "catalog_error": catalog.get("error"),
                "available_models": sorted(catalog_ids),
            }), 409
        if model not in catalog_ids:
            missing_message = (
                f"model '{model}' is not installed on the configured Ollama host"
                if provider_id.startswith("ollama-")
                else f"model '{model}' is not present in the current provider catalog"
            )
            return jsonify({
                "error": missing_message,
                "catalog_source": catalog.get("catalog_source"),
                "catalog_status": catalog.get("status"),
                "available_models": sorted(catalog_ids),
            }), 400

        try:
            _set_selected_model_for_provider(provider_id, model)
        except UnsupportedConnectionsSettingsError as exc:
            return jsonify({"error": str(exc)}), 409
        except OSError as exc:
            return jsonify({"error": f"Could not save Connections settings: {exc}"}), 500
        status = next(
            row for row in _e10_provider_statuses()
            if row["participant"] == key
        )
        return jsonify({
            **status,
            "message": f"Selected model for {label}: {model}",
        })

    @app.route("/api/e10/ollama/host", methods=["PUT"])
    def api_e10_ollama_host():
        payload = request.get_json(silent=True) or {}
        host = str(payload.get("host") or "").strip()
        if not host:
            return jsonify({"error": "host is required"}), 400
        try:
            _set_ollama_host(host)
        except InvalidConnectionsSettingError as exc:
            return jsonify({"error": str(exc)}), 400
        except UnsupportedConnectionsSettingsError as exc:
            return jsonify({"error": str(exc)}), 409
        except OSError as exc:
            return jsonify({"error": f"Could not save Connections settings: {exc}"}), 500
        source = _ollama_host_source()
        effective_host = _ollama_host()
        with _connections_settings_lock:
            configured_host = ollama_host_from_settings(runtime_connections_settings)
        return jsonify({
            "ollama_host": effective_host,
            "ollama_host_source": source,
            "configured_ollama_host": configured_host,
            "message": (
                "Ollama host saved in user Connections settings. "
                "The OLLAMA_HOST environment variable remains authoritative for this server session."
                if source == "environment"
                else "Ollama host saved in user Connections settings."
            ),
        })

    @app.route("/api/e10/providers/<participant>/test", methods=["POST"])
    def api_e10_provider_test(participant: str):
        selected = [
            provider
            for provider in _e10_provider_statuses()
            if provider["participant"] == participant
        ]
        if not selected:
            return jsonify({"error": f"unsupported participant: {participant}"}), 400
        provider = selected[0]
        provider_id = provider["provider_id"]
        if not provider["configured"]:
            return jsonify({
                **provider,
                "live_connection_test": False,
                "configuration_valid": False,
                "message": (
                    f"No credential is configured for {provider['label']}. "
                    "Add a key before testing."
                ),
            })
        if not provider["adapter_available"]:
            definition = active_provider_registry.definition(provider_id)
            return jsonify({
                **provider,
                "live_connection_test": False,
                "configuration_valid": False,
                "message": (
                    f"The credential is saved, but the {definition.sdk_module} "
                    "Python adapter is not installed. No provider request was sent."
                ),
            })
        validation_error = None
        try:
            provider_kwargs = _provider_kwargs(provider_id)
            adapter = active_provider_registry.create(provider_id, **provider_kwargs)
            adapter.test_connection()
        except Exception as exc:
            validation_error = str(exc)
        return jsonify({
            "participant": provider["participant"],
            "label": provider["label"],
            "status": provider["status"],
            "configured": provider["configured"],
            "adapter_available": provider["adapter_available"],
            "credential_source": provider["credential_source"],
            "default_model": provider["default_model"],
            "selected_model": provider.get("selected_model"),
            "live_connection_test": True,
            "configuration_valid": validation_error is None,
            "message": (
                f"Connection test failed: {validation_error}"
                if validation_error
                else "Connection succeeded. No generation request was sent."
            ),
        })

    @app.route("/api/e10/calibration")
    def api_e10_calibration():
        """Return full calibration records for all participants."""
        with _calibration_lock:
            perf = _performance_summary()
            result = {}
            for key in _E10_PARTICIPANTS:
                provider_id = _E10_PARTICIPANTS[key][1]
                selected_model, _ = _selected_model_for_provider(provider_id, _E10_PARTICIPANTS[key][2])
                rec = _get_calibration_record(
                    key,
                    provider_id=provider_id,
                    model_id=selected_model,
                )
                performance = (
                    _empty_performance_record(suppressed=True)
                    if provider_id.startswith("ollama-")
                    else perf.get(key, _empty_performance_record())
                )
                result[key] = {
                    **rec,
                    "calibration_identity": _calibration_key(key, provider_id, selected_model),
                    "performance": performance,
                }
        return jsonify({"calibration": result, "roles": _CALIBRATION_ROLES})

    @app.route("/api/e10/providers/<participant>/calibrate/<role>", methods=["POST"])
    def api_e10_calibrate_role(participant: str, role: str):
        """Run a calibration test for a provider/role combination."""
        participant_info = _e10_participant(participant)
        if participant_info is None:
            return jsonify({"error": f"unsupported participant: {participant}"}), 400
        if role not in _CALIBRATION_ROLES:
            return jsonify({"error": f"unknown role: {role}. Valid: {_CALIBRATION_ROLES}"}), 400

        key, label, _ = participant_info
        provider_id = _E10_PARTICIPANTS[key][1]

        # Check provider availability before attempting calibration
        statuses = _e10_provider_statuses()
        provider_status = next((p for p in statuses if p["participant"] == key), None)
        if provider_status is None or not provider_status["adapter_available"]:
            return jsonify({
                "participant": key, "role": role,
                "status": "error",
                "message": f"{label}: adapter not available. Cannot run calibration.",
            }), 400

        # For Ollama providers, check server + model readiness
        is_ollama = provider_id.startswith("ollama-")
        if is_ollama:
            model = provider_status.get("selected_model") or provider_status.get("default_model", "")
            readiness = _ollama_readiness(model)
            if not (readiness["server_running"] and readiness["model_pulled"]):
                action = readiness.get("setup_action", "Check Ollama setup")
                return jsonify({
                    "participant": key, "role": role,
                    "status": "error",
                    "message": f"Ollama not ready: {action}",
                }), 400

        # Select calibration prompt and validation by role
        if role == "Explorer":
            prompt = _EXPLORER_CALIBRATION_PROMPT
            test_name = "structured_output"
        elif role == "Artist":
            prompt = _ARTIST_CALIBRATION_PROMPT
            test_name = "narrative_generation"
        else:
            # For untested roles, do a basic connectivity test
            prompt = "Respond with exactly the word: READY"
            test_name = "connectivity"

        import time as _time
        start = _time.monotonic()
        raw_output = None
        error_msg = None
        selected_model = provider_status.get("selected_model") or provider_status.get("default_model")
        try:
            kwargs = _provider_kwargs(provider_id)
            adapter = active_provider_registry.create(provider_id, **kwargs)
            raw_output = adapter.render(prompt)
        except Exception as exc:
            error_msg = str(exc)
        latency_ms = int((_time.monotonic() - start) * 1000)

        if error_msg:
            _record_calibration_result(
                key, role, test_name, "fail", latency_ms,
                error_msg, f"Provider call failed: {error_msg}",
                provider_id=provider_id,
                model_id=selected_model,
            )
            _log_performance_event({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "participant": key, "role": role,
                "success": False, "parse_ok": False,
                "latency_ms": latency_ms, "error": error_msg,
            })
            return jsonify({
                "participant": key, "role": role, "test_name": test_name,
                "provider_id": provider_id,
                "model_id": selected_model,
                "status": "fail",
                "failure_reason": error_msg,
                "latency_ms": latency_ms,
                "recommendation": f"Provider call failed. Check connection and model availability.",
                "role_status": "rejected",
            })

        # Validate output by role
        parse_ok = False
        failure_reason = None
        if role == "Explorer":
            try:
                parsed = json.loads(raw_output.strip())
                required = {"bucket", "confidence", "rationale"}
                if isinstance(parsed, dict) and required.issubset(parsed.keys()):
                    parse_ok = True
                else:
                    failure_reason = (
                        f"JSON parsed but missing required keys. Got: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}"
                    )
            except (json.JSONDecodeError, ValueError) as exc:
                failure_reason = f"Response is not valid JSON: {exc}. Output begins: {raw_output[:120]!r}"
        elif role == "Artist":
            parse_ok = bool(raw_output and len(raw_output.strip()) > 30)
            if not parse_ok:
                failure_reason = f"Response too short or empty: {raw_output!r}"
        else:
            parse_ok = bool(raw_output and raw_output.strip())
            if not parse_ok:
                failure_reason = "Empty response"

        status = "pass" if parse_ok else "fail"
        recommendation = (
            f"Passed {test_name} calibration. Approved for {role}." if parse_ok else
            f"Failed {test_name}: {failure_reason}. Rejected for {role} until calibration passes."
        )
        _record_calibration_result(
            key,
            role,
            test_name,
            status,
            latency_ms,
            failure_reason,
            recommendation,
            provider_id=provider_id,
            model_id=selected_model,
        )
        _log_performance_event({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "participant": key, "role": role,
            "success": parse_ok, "parse_ok": parse_ok,
            "latency_ms": latency_ms, "error": failure_reason,
        })

        rec = _get_calibration_record(
            key,
            provider_id=provider_id,
            model_id=selected_model,
        )
        return jsonify({
            "participant": key, "role": role, "test_name": test_name,
            "provider_id": provider_id,
            "model_id": selected_model,
            "status": status,
            "failure_reason": failure_reason,
            "latency_ms": latency_ms,
            "raw_output_preview": (raw_output or "")[:200],
            "recommendation": recommendation,
            "role_status": rec["role_status"].get(role, {}).get("status", "untested"),
        }), (201 if parse_ok else 200)

    @app.route("/api/e10/providers/<participant>/roles/<role>", methods=["PATCH"])
    def api_e10_set_role_status(participant: str, role: str):
        """Steward manually sets role status: approved / rejected / untested."""
        participant_info = _e10_participant(participant)
        if participant_info is None:
            return jsonify({"error": f"unsupported participant: {participant}"}), 400
        if role not in _CALIBRATION_ROLES:
            return jsonify({"error": f"unknown role: {role}"}), 400

        payload = request.get_json(silent=True) or {}
        status = payload.get("status", "").strip().lower()
        note = str(payload.get("note", "")).strip() or None
        valid_statuses = {"approved", "rejected", "untested", "caution"}
        if status not in valid_statuses:
            return jsonify({
                "error": f"invalid status: {status!r}. Must be one of: {sorted(valid_statuses)}"
            }), 400

        key, label, _ = participant_info
        provider_id = _E10_PARTICIPANTS[key][1]
        selected_model, _ = _selected_model_for_provider(provider_id, _E10_PARTICIPANTS[key][2])
        now = datetime.now(timezone.utc).isoformat()
        with _calibration_lock:
            rec = _get_calibration_record(
                key,
                provider_id=provider_id,
                model_id=selected_model,
            )
            rec["role_status"][role] = {"status": status, "last_updated": now, "steward_note": note}
            _save_calibration_store(runtime_calibration)

        return jsonify({
            "participant": key, "role": role,
            "provider_id": provider_id,
            "model_id": selected_model,
            "status": status, "steward_note": note, "updated_at": now,
            "message": f"{label}: {role} role status set to '{status}' by Steward.",
        })

    @app.route("/api/e10/performance")
    def api_e10_performance():
        return jsonify({
            "summary": _performance_summary(),
            "event_count": len(_perf_log),
            "session_only": True,
        })

    @app.route("/api/edition/cycles")
    def api_edition_cycles():
        from hermeneia.cli.edition_cmd import _load_cycles, _edition_status, EDITION_MIN_CYCLES
        pub_dir = Path.cwd() / "publication"
        try:
            store = _load_cycles(pub_dir)
            status = _edition_status(store)
        except Exception:
            status = {"cycle_count": 0, "eligible": False, "status_label": "Working Draft", "cycles_remaining": EDITION_MIN_CYCLES}
        return jsonify({
            "cycle_count": status["cycle_count"],
            "eligible": status["eligible"],
            "status_label": status["status_label"],
            "cycles_remaining": status["cycles_remaining"],
            "minimum_required": EDITION_MIN_CYCLES,
        })

    @app.route("/api/e10/observations/<observation_id>")
    def api_e10_observation_detail(observation_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        try:
            require_active_observation(conn, observation_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        rows = conn.execute(
            """
            SELECT o.id
            FROM observations o
            JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
            ORDER BY o.page, o.paragraph, o.sentence
            """
        ).fetchall()
        id_to_index = {row["id"]: index + 1 for index, row in enumerate(rows)}
        obs = conn.execute(
            """
            SELECT o.*, sd.original_filename, sd.file_hash, se.raw_text AS extraction_raw_text,
                   se.parser, se.parser_version, sd.source_role
            FROM observations o
            JOIN source_documents sd ON sd.id = o.source_document_id
            JOIN source_extractions se ON se.id = o.source_extraction_id
            WHERE o.id = ?
            """,
            (observation_id,),
        ).fetchone()
        if obs is None:
            conn.close()
            return jsonify({"error": "observation not found"}), 404

        interps = conn.execute(
            "SELECT * FROM interpretations WHERE observation_id = ? ORDER BY created_at",
            (observation_id,),
        ).fetchall() if _table_exists(conn, "interpretations") else []
        proposals = (
            conn.execute(
                """
                SELECT *
                FROM proposed_interpretations
                WHERE observation_id = ?
                ORDER BY created_at
                """,
                (observation_id,),
            ).fetchall()
            if _table_exists(conn, "proposed_interpretations")
            else []
        )
        proposal_payloads = [_e10_proposal_payload(conn, r) for r in proposals]
        interpretation_payloads = [_e10_interpretation_payload(r) for r in interps]
        conn.close()

        return jsonify({
            "observation": {
                "obs_index": id_to_index.get(observation_id),
                "id": obs["id"],
                "page": obs["page"],
                "paragraph": obs["paragraph"],
                "sentence": obs["sentence"],
                "source_locator": obs["source_locator"],
                "raw_text": obs["raw_text"],
                "source_document_id": obs["source_document_id"],
                "source_extraction_id": obs["source_extraction_id"],
                "document": {
                    "original_filename": obs["original_filename"],
                    "file_hash": obs["file_hash"],
                    "source_role": obs["source_role"] or "primary",
                },
                "extraction": {
                    "parser": obs["parser"],
                    "parser_version": obs["parser_version"],
                    "raw_text": obs["extraction_raw_text"],
                },
            },
            "interpretations": interpretation_payloads,
            "proposals": proposal_payloads,
        })

    @app.route("/api/e10/interpretations/generate", methods=["POST"])
    def api_e10_generate_interpretations():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        from ..explorer.interpreter import VALID_RESPONSE_MODES
        payload = request.get_json(silent=True) or {}
        observation_id = str(payload.get("observation_id", "")).strip()
        raw_participants = payload.get("participants") or []
        response_mode = str(payload.get("response_mode") or "interpretive").strip()
        if response_mode not in VALID_RESPONSE_MODES:
            response_mode = "interpretive"
        if not observation_id:
            return jsonify({"error": "observation_id is required"}), 400
        if not isinstance(raw_participants, list) or not raw_participants:
            return jsonify({"error": "participants must be a non-empty list"}), 400

        participants = []
        for raw in raw_participants:
            participant = _e10_participant(str(raw))
            if participant is None:
                return jsonify({"error": f"unsupported participant: {raw}"}), 400
            participants.append(participant)

        # Build corpus context so the prompt knows primary vs reference role.
        # Direct IDs from excluded documents fail closed before any provider call.
        _ctx_conn = _conn()
        try:
            obs_doc_row = require_active_observation(_ctx_conn, observation_id)
        except _ScopeAccessError as exc:
            _ctx_conn.close()
            return _scope_error_response(exc)
        primary_doc_row = _ctx_conn.execute(
            """SELECT original_filename FROM source_documents
               WHERE COALESCE(excluded_from_analysis, 0) = 0
               AND COALESCE(source_role, 'primary') = 'primary'
               ORDER BY registered_at LIMIT 1""",
        ).fetchone()
        _ctx_conn.close()
        corpus_context = {
            "primary_work": primary_doc_row["original_filename"] if primary_doc_row else None,
            "observation_source": obs_doc_row["original_filename"] if obs_doc_row else None,
            "observation_role": (obs_doc_row["source_role"] or "primary") if obs_doc_row else "primary",
        }

        store = _store()
        try:
            observation = store.get_observation_by_id(observation_id)
            if observation is None:
                return jsonify({"error": "observation not found"}), 404
            proposals = []
            generated_at = datetime.now(timezone.utc).isoformat()
            for key, label, model in participants:
                _provider_id = _E10_PARTICIPANTS[key][1]
                selected_model, _ = _selected_model_for_provider(_provider_id, model)
                try:
                    _adapter = active_provider_registry.create(
                        _provider_id,
                        **_provider_kwargs(_provider_id),
                    )
                except Exception:
                    _adapter = active_provider_registry.create("null")
                import time as _time
                _gen_start = _time.monotonic()
                _gen_error = None
                try:
                    interp_text, prompt_used = generate_candidate_interpretation(
                        observation_text=observation["raw_text"],
                        perspective_label=label,
                        provider=_adapter,
                        corpus_context=corpus_context,
                        response_mode=response_mode,
                    )
                except ExplorerError as exc:
                    _gen_error = str(exc)
                    _log_performance_event({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "participant": key, "role": "Explorer",
                        "success": False, "parse_ok": False,
                        "latency_ms": int((_time.monotonic() - _gen_start) * 1000),
                        "error": _gen_error,
                    })
                    raise StagingError(f"Explorer failed for participant {key!r}: {exc}") from exc
                except Exception as exc:
                    _gen_error = str(exc)
                    _log_performance_event({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "participant": key, "role": "Explorer",
                        "success": False, "parse_ok": False,
                        "latency_ms": int((_time.monotonic() - _gen_start) * 1000),
                        "error": _gen_error,
                    })
                    raise StagingError(f"Provider error for participant {key!r}: {exc}") from exc
                _log_performance_event({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "participant": key, "role": "Explorer",
                    "success": True, "parse_ok": True,
                    "latency_ms": int((_time.monotonic() - _gen_start) * 1000),
                    "error": None,
                })
                proposal = propose_interpretation(
                    observation_id=observation_id,
                    perspective=label,
                    text=interp_text,
                    evidential_status="speculative",
                    generating_model=selected_model or model,
                    prompt_reference=prompt_used,
                    prompt_reference_type="full_text",
                    conn=store,
                    generation_timestamp=generated_at,
                    parent_object_ids=[observation_id],
                    generation_parameters={
                        "surface": "E10 Interpretation Lab",
                        "participant": key,
                        "mode": "explorer-llm",
                        "observation_source_role": corpus_context.get("observation_role", "primary"),
                        "observation_source_document": corpus_context.get("observation_source"),
                        "primary_document": corpus_context.get("primary_work"),
                    },
                    evidence_observation_ids=[observation_id],
                )
                proposals.append(proposal)
        except StagingError as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            store.close()

        # Write response_mode onto each proposal row
        rw = _conn_rw()
        for proposal in proposals:
            rw.execute(
                "UPDATE proposed_interpretations SET response_mode = ? WHERE id = ?",
                (response_mode, proposal["id"]),
            )
        rw.commit()

        conn = _conn()
        enriched = []
        for proposal in proposals:
            payload = _e10_proposal_payload(
                conn,
                conn.execute(
                    "SELECT * FROM proposed_interpretations WHERE id = ?",
                    (proposal["id"],),
                ).fetchone(),
            )
            # Fetch generation_parameters from ai_provenance (not on proposal row)
            prov_row = conn.execute(
                "SELECT generation_parameters FROM ai_provenance WHERE staged_object_id = ?",
                (proposal["id"],),
            ).fetchone()
            gen_params = _json_loads(
                prov_row["generation_parameters"] if prov_row else None, {}
            )
            payload["generation_parameters"] = gen_params
            payload["obs_source_role"] = gen_params.get("observation_source_role", "primary")
            payload["obs_source_document"] = gen_params.get("observation_source_document")
            payload["primary_document"] = gen_params.get("primary_document")
            payload["response_mode"] = response_mode
            enriched.append(payload)
        conn.close()
        return jsonify({"created_count": len(enriched), "proposals": enriched}), 201

    @app.route("/api/e10/interpretations/discover", methods=["POST"])
    def api_e10_discover_interpretations():
        """Explorer discovery: bucket multiple observations, generate one interpretation per bucket.

        Buckets are ephemeral compiler internals — never stored.
        Only the speculative Interpretations (with evidence_observation_ids) are persisted.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        payload = request.get_json(silent=True) or {}
        raw_obs_ids = payload.get("observation_ids") or []
        raw_participants = payload.get("participants") or []

        if not isinstance(raw_obs_ids, list) or len(raw_obs_ids) < 1:
            return jsonify({"error": "observation_ids must be a non-empty list"}), 400
        if not isinstance(raw_participants, list) or not raw_participants:
            return jsonify({"error": "participants must be a non-empty list"}), 400

        participants = []
        for raw in raw_participants:
            participant = _e10_participant(str(raw))
            if participant is None:
                return jsonify({"error": f"unsupported participant: {raw}"}), 400
            participants.append(participant)

        # Load observations
        conn_ro = _conn()
        obs_rows = []
        for obs_id in raw_obs_ids:
            try:
                row = require_active_observation(conn_ro, str(obs_id))
            except _ScopeAccessError as exc:
                conn_ro.close()
                return _scope_error_response(exc)
            obs_rows.append({"id": row["id"], "raw_text": row["raw_text"]})

        # Corpus context from first observation's source document
        obs_doc_row = require_active_observation(conn_ro, str(raw_obs_ids[0]))
        primary_doc_row = conn_ro.execute(
            """SELECT original_filename FROM source_documents
               WHERE COALESCE(excluded_from_analysis, 0) = 0
               AND COALESCE(source_role, 'primary') = 'primary'
               ORDER BY registered_at LIMIT 1""",
        ).fetchone()
        conn_ro.close()

        corpus_context = {
            "primary_work": primary_doc_row["original_filename"] if primary_doc_row else None,
            "observation_source": obs_doc_row["original_filename"] if obs_doc_row else None,
            "observation_role": (obs_doc_row["source_role"] or "primary") if obs_doc_row else "primary",
        }

        # Bucketing pass — ephemeral, never stored
        bucket_provider_id = _E10_PARTICIPANTS[participants[0][0]][1]
        try:
            _bucketing_provider = active_provider_registry.create(
                bucket_provider_id,
                **_provider_kwargs(bucket_provider_id),
            )
        except Exception:
            _bucketing_provider = active_provider_registry.create("null")
        try:
            buckets = generate_candidate_buckets(obs_rows, _bucketing_provider)
        except BucketingError as exc:
            return jsonify({"error": f"Bucketing failed: {exc}"}), 400

        store = _store()
        proposals = []
        skipped = 0
        generated_at = datetime.now(timezone.utc).isoformat()

        try:
            for bucket_ids in buckets:
                bucket_obs = [o for o in obs_rows if o["id"] in bucket_ids]
                primary_obs_id = sorted(bucket_ids)[0]
                sorted_evidence_ids = sorted(bucket_ids)

                for key, label, model in participants:
                    # Idempotency: skip if a pending/accepted proposal already exists
                    # for this primary observation + same sorted evidence set
                    existing = store._conn.execute(
                        "SELECT id FROM proposed_interpretations "
                        "WHERE observation_id = ? AND perspective = ? "
                        "AND status IN ('pending', 'accepted')",
                        (primary_obs_id, label),
                    ).fetchall()
                    duplicate = False
                    for ex in existing:
                        ex_row = store._conn.execute(
                            "SELECT evidence_observation_ids FROM proposed_interpretations WHERE id = ?",
                            (ex["id"],),
                        ).fetchone()
                        if ex_row:
                            import json as _json
                            ex_ids = sorted(_json.loads(ex_row["evidence_observation_ids"] or "[]"))
                            if ex_ids == sorted_evidence_ids:
                                duplicate = True
                                break
                    if duplicate:
                        skipped += 1
                        continue

                    _provider_id = _E10_PARTICIPANTS[key][1]
                    selected_model, _ = _selected_model_for_provider(_provider_id, model)
                    try:
                        _adapter = active_provider_registry.create(
                            _provider_id,
                            **_provider_kwargs(_provider_id),
                        )
                    except Exception:
                        _adapter = active_provider_registry.create("null")

                    try:
                        interp_text, prompt_used = generate_interpretation_from_bucket(
                            bucket_obs,
                            label,
                            _adapter,
                            corpus_context,
                        )
                    except ExplorerError as exc:
                        raise StagingError(f"Explorer failed for participant {key!r}: {exc}") from exc

                    proposal = propose_interpretation(
                        observation_id=primary_obs_id,
                        perspective=label,
                        text=interp_text,
                        evidential_status="speculative",
                        generating_model=selected_model or model,
                        prompt_reference=prompt_used,
                        prompt_reference_type="full_text",
                        conn=store,
                        generation_timestamp=generated_at,
                        parent_object_ids=sorted_evidence_ids,
                        generation_parameters={
                            "surface": "E10 Explorer Discovery",
                            "participant": key,
                            "mode": "explorer-bucket",
                            "bucket_size": len(bucket_ids),
                            "bucket_observation_ids": sorted_evidence_ids,
                        },
                        evidence_observation_ids=sorted_evidence_ids,
                    )
                    proposals.append(proposal)
        except StagingError as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            store.close()

        conn_ro2 = _conn()
        enriched = [
            _e10_proposal_payload(
                conn_ro2,
                conn_ro2.execute(
                    "SELECT * FROM proposed_interpretations WHERE id = ?",
                    (p["id"],),
                ).fetchone(),
            )
            for p in proposals
        ]
        conn_ro2.close()
        return jsonify({
            "bucket_count": len(buckets),
            "created_count": len(enriched),
            "skipped_count": skipped,
            "proposals": enriched,
        }), 201

    @app.route("/api/e10/proposals/<proposal_id>/accept", methods=["POST"])
    def api_e10_accept_proposal(proposal_id: str):
        payload = request.get_json(silent=True) or {}
        steward_id = str(payload.get("steward_id") or "web-steward").strip()
        rationale = str(payload.get("comment") or payload.get("rationale") or "").strip()
        if not rationale:
            rationale = "Accepted in E10 Steward Review."

        conn = _conn()
        try:
            require_active_proposal_observations(conn, proposal_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        conn.close()

        store = _store()
        try:
            canonical = accept_proposed_interpretation(
                proposal_id,
                steward_id,
                rationale,
                store,
            )
        except StagingError as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            store.close()
        return jsonify({"interpretation": canonical})

    @app.route("/api/e10/proposals/<proposal_id>/reject", methods=["POST"])
    def api_e10_reject_proposal(proposal_id: str):
        payload = request.get_json(silent=True) or {}
        steward_id = str(payload.get("steward_id") or "web-steward").strip()
        rationale = str(payload.get("comment") or payload.get("rationale") or "").strip()
        if not rationale:
            rationale = "Rejected in E10 Steward Review."

        store = _store()
        try:
            proposal = reject_proposed_interpretation(
                proposal_id,
                steward_id,
                rationale,
                store,
            )
        except StagingError as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            store.close()
        return jsonify({"proposal": proposal})

    @app.route("/api/e10/critic/run", methods=["POST"])
    def api_e10_run_critic():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        payload = request.get_json(silent=True) or {}
        proposal_id = str(payload.get("proposal_id", "")).strip()
        policies = payload.get("policies") or ["conservative"]
        if not proposal_id:
            return jsonify({"error": "proposal_id is required"}), 400
        if not isinstance(policies, list):
            return jsonify({"error": "policies must be a list"}), 400
        unknown = [p for p in policies if p not in VALID_POLICIES]
        if unknown:
            return jsonify({
                "error": f"unknown policies: {', '.join(unknown)}",
                "valid_policies": sorted(VALID_POLICIES),
            }), 400

        conn = _conn()
        try:
            require_active_proposal_observations(conn, proposal_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        conn.close()

        store = _store()
        reports = []
        try:
            for policy in policies:
                reports.append(generate_critic_report(
                    proposal_id,
                    store,
                    policy=policy,
                ))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            store.close()

        return jsonify({
            "reports": [_e10_critic_report_payload(report) for report in reports],
        }), 201

    @app.route("/api/e10/findings")
    def api_e10_findings():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        if not _table_exists(conn, "findings"):
            conn.close()
            return jsonify({"count": 0, "findings": []})
        rows = conn.execute(
            """
            SELECT f.*, rn.provider, ap.title AS architect_plan_title,
                   nb.title AS blueprint_title
            FROM findings f
            LEFT JOIN rendered_narratives rn ON rn.id = f.rendered_narrative_id
            LEFT JOIN architect_plans ap ON ap.id = f.architect_plan_id
            LEFT JOIN narrative_blueprints nb ON nb.id = ap.blueprint_id
            ORDER BY f.created_at DESC
            LIMIT 100
            """
        ).fetchall()
        conn.close()
        return jsonify({"count": len(rows), "findings": [dict(row) for row in rows]})

    @app.route("/api/e10/findings/<finding_id>/lineage")
    def api_e10_finding_lineage(finding_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        if not _table_exists(conn, "findings"):
            conn.close()
            return jsonify({"error": "finding not found"}), 404
        finding = conn.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        if finding is None:
            conn.close()
            return jsonify({"error": "finding not found"}), 404
        finding = dict(finding)
        graph = None
        try:
            graph = _lineage_graph(
                conn,
                "RenderedNarrative",
                finding["rendered_narrative_id"],
            )
        except (_LineageError, _ScopeAccessError):
            graph = None
        conn.close()
        return jsonify({"finding": finding, "lineage": graph})

    # ── /api/lineage/rendered_narratives ────────────────────────────────────

    @app.route("/api/lineage/rendered_narratives")
    def api_lineage_rendered_narratives():
        """List all RenderedNarratives for the Lineage Explorer picker.

        Read-only. No mutation. P3 — Lineage Explorer.
        Returns enough context to label each narrative meaningfully in the UI.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        rows = conn.execute(
            """
            SELECT rn.id,
                   rn.provider,
                   rn.expression_profile_id,
                   rn.architect_plan_id,
                   rn.created_at,
                   ep.slug          AS profile_slug,
                   nb.title         AS blueprint_title
            FROM rendered_narratives rn
            LEFT JOIN expression_profiles ep ON ep.id = rn.expression_profile_id
            LEFT JOIN architect_plans ap     ON ap.id = rn.architect_plan_id
            LEFT JOIN narrative_blueprints nb ON nb.id = ap.blueprint_id
            ORDER BY rn.created_at DESC
            """
        ).fetchall()
        conn.close()
        return jsonify({
            "count": len(rows),
            "rendered_narratives": [dict(r) for r in rows],
        })

    # ── /api/architect/blueprints ────────────────────────────────────────────

    @app.route("/api/architect/blueprints")
    def api_architect_blueprints():
        """List all NarrativeBlueprints with Architect Plan status.

        Read-only. No mutation. Phase 1 — Architect Explorer.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        bp_rows = conn.execute(
            "SELECT id, title, thesis, created_at FROM narrative_blueprints ORDER BY created_at"
        ).fetchall()

        result = []
        for bp in bp_rows:
            bp_id = bp["id"]

            section_count = len(json.loads(
                conn.execute(
                    "SELECT sections FROM narrative_blueprints WHERE id = ?", (bp_id,)
                ).fetchone()["sections"]
            ))

            ap = conn.execute(
                "SELECT id FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
                (bp_id,),
            ).fetchone()

            linked_obs = conn.execute(
                "SELECT COUNT(*) FROM blueprint_observation_links WHERE blueprint_id = ?", (bp_id,)
            ).fetchone()[0]
            linked_interp = conn.execute(
                "SELECT COUNT(*) FROM blueprint_interpretation_links WHERE blueprint_id = ?", (bp_id,)
            ).fetchone()[0]

            result.append({
                "id": bp_id,
                "title": bp["title"],
                "thesis": bp["thesis"],
                "section_count": section_count,
                "has_architect_plan": ap is not None,
                "architect_plan_id": ap["id"] if ap else None,
                "linked_obs_count": linked_obs,
                "linked_interp_count": linked_interp,
                "created_at": bp["created_at"],
            })

        conn.close()
        return jsonify({"count": len(result), "blueprints": result})

    @app.route("/api/architect/blueprints/<blueprint_id>")
    def api_architect_blueprint_detail(blueprint_id: str):
        """Full detail for one NarrativeBlueprint + its ArchitectPlan paragraphs.

        Read-only. No mutation. Phase 1 — Architect Explorer.

        Returns:
        - blueprint: {id, title, thesis, sections[{index, claim, supporting_observations,
                      supporting_interpretations, obs_texts, interp_texts}]}
        - architect_plan: {id, created_at, paragraphs[{order_idx, purpose, blueprint_section,
                           required_observations, required_interpretations, required_terms,
                           forbidden_claims, notes}]} or null if none compiled yet
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        bp_row = conn.execute(
            "SELECT * FROM narrative_blueprints WHERE id = ?", (blueprint_id,)
        ).fetchone()
        if bp_row is None:
            conn.close()
            return jsonify({"error": "blueprint not found"}), 404

        bp = dict(bp_row)
        raw_sections = json.loads(bp["sections"])

        # Collect all observation IDs referenced in sections
        all_obs_ids: set[str] = set()
        all_interp_ids: set[str] = set()
        for sec in raw_sections:
            for oid in sec.get("supporting_observations", []):
                all_obs_ids.add(oid)
            for iid in sec.get("supporting_interpretations", []):
                all_interp_ids.add(iid)

        # Fetch text for referenced observations (normalized_text preferred)
        obs_texts: dict[str, str] = {}
        for oid in all_obs_ids:
            try:
                scoped_obs = require_active_observation(conn, oid)
            except _ScopeAccessError as exc:
                conn.close()
                return _scope_error_response(exc)
            row = conn.execute(
                """
                SELECT COALESCE(od.normalized_text, o.raw_text) AS text,
                       o.page, o.paragraph, o.sentence, o.source_locator
                FROM observations o
                LEFT JOIN observation_derived od ON od.observation_id = o.id
                WHERE o.id = ?
                """,
                (oid,),
            ).fetchone()
            if row:
                obs_texts[oid] = {
                    "text": row["text"],
                    "page": row["page"],
                    "paragraph": row["paragraph"],
                    "sentence": row["sentence"],
                    "source_locator": row["source_locator"],
                    "source_role": scoped_obs["source_role"],
                }

        # Fetch text for referenced interpretations
        interp_texts: dict[str, str] = {}
        for iid in all_interp_ids:
            row = conn.execute(
                """
                SELECT i.text, i.perspective, i.evidential_status,
                       i.observation_id, i.evidence_observation_ids,
                       COALESCE(sd.source_role, 'primary') AS source_role
                FROM interpretations i
                JOIN observations o ON o.id = i.observation_id
                JOIN source_documents sd ON sd.id = o.source_document_id
                WHERE i.id = ?
                  AND COALESCE(sd.excluded_from_analysis, 0) = 0
                """,
                (iid,)
            ).fetchone()
            if row is None:
                stale = conn.execute(
                    "SELECT observation_id, evidence_observation_ids FROM interpretations WHERE id = ?",
                    (iid,),
                ).fetchone()
                if stale is not None:
                    try:
                        require_active_observation(conn, stale["observation_id"])
                        evidence_ids = _json_loads(stale["evidence_observation_ids"], [])
                        if isinstance(evidence_ids, list):
                            for oid in evidence_ids:
                                require_active_observation(conn, str(oid))
                    except _ScopeAccessError as exc:
                        conn.close()
                        return _scope_error_response(exc)
            if row:
                evidence_ids = _json_loads(row["evidence_observation_ids"], [])
                if isinstance(evidence_ids, list):
                    for oid in evidence_ids:
                        try:
                            require_active_observation(conn, str(oid))
                        except _ScopeAccessError as exc:
                            conn.close()
                            return _scope_error_response(exc)
                interp_texts[iid] = {
                    "text": row["text"],
                    "perspective": row["perspective"],
                    "evidential_status": row["evidential_status"],
                    "source_role": row["source_role"],
                }

        # Build enriched sections
        sections = []
        for idx, sec in enumerate(raw_sections):
            sections.append({
                "index": idx,
                "claim": sec.get("claim", ""),
                "supporting_observations": sec.get("supporting_observations", []),
                "supporting_interpretations": sec.get("supporting_interpretations", []),
                "obs_texts": {
                    oid: obs_texts[oid]
                    for oid in sec.get("supporting_observations", [])
                    if oid in obs_texts
                },
                "interp_texts": {
                    iid: interp_texts[iid]
                    for iid in sec.get("supporting_interpretations", [])
                    if iid in interp_texts
                },
            })

        # Fetch most recent ArchitectPlan for this blueprint
        ap_row = conn.execute(
            "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
            (blueprint_id,),
        ).fetchone()

        architect_plan = None
        if ap_row:
            ap = dict(ap_row)
            para_rows = conn.execute(
                """
                SELECT order_idx, purpose, blueprint_section,
                       required_observations, required_interpretations,
                       required_terms, forbidden_claims, notes
                FROM architect_plan_paragraphs
                WHERE plan_id = ?
                ORDER BY order_idx
                """,
                (ap["id"],),
            ).fetchall()
            paragraphs = []
            for p in para_rows:
                paragraphs.append({
                    "order_idx": p["order_idx"],
                    "purpose": p["purpose"],
                    "blueprint_section": p["blueprint_section"],
                    "required_observations": json.loads(p["required_observations"] or "[]"),
                    "required_interpretations": json.loads(p["required_interpretations"] or "[]"),
                    "required_terms": json.loads(p["required_terms"] or "[]"),
                    "forbidden_claims": json.loads(p["forbidden_claims"] or "[]"),
                    "notes": p["notes"],
                })
            architect_plan = {
                "id": ap["id"],
                "created_at": ap["created_at"],
                "paragraph_count": len(paragraphs),
                "paragraphs": paragraphs,
            }

        conn.close()
        return jsonify({
            "id": blueprint_id,
            "title": bp["title"],
            "thesis": bp["thesis"],
            "section_count": len(sections),
            "sections": sections,
            "architect_plan": architect_plan,
            "obs_texts": obs_texts,
            "interp_texts": interp_texts,
        })

    # ── /api/architect/generate ───────────────────────────────────────────────

    @app.route("/api/architect/generate", methods=["POST"])
    def api_architect_generate():
        """Generate a new NarrativeBlueprint + ArchitectPlan from a research directive.

        Body: { directive: str, provider: str }

        The AI receives:
          - The directive (research question / essay goal)
          - All accepted interpretations with OBS-N references
          - A sample of up to 40 observations for context
        and returns a structured blueprint JSON which is stored and compiled
        into an ArchitectPlan.
        """
        import datetime as _dt, hashlib as _hl, traceback as _tb, re as _re

        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        payload = request.get_json(silent=True) or {}
        directive = str(payload.get("directive", "")).strip()
        provider  = str(payload.get("provider", "")).strip()
        if not directive:
            return jsonify({"error": "directive is required"}), 400
        if not provider:
            return jsonify({"error": "provider is required"}), 400

        from ..narrative.artist_providers import get_provider
        from ..compiler.architect import compile_architect_plan
        from ..storage.hashing import make_blueprint_id, make_architect_plan_id

        conn = _conn_rw()
        try:
            # ── Build OBS-N index ──────────────────────────────────────────
            all_obs = conn.execute(
                """
                SELECT o.id, o.raw_text, o.page,
                       COALESCE(sd.source_role, 'primary') AS source_role,
                       sd.original_filename
                FROM observations o
                JOIN source_documents sd ON sd.id = o.source_document_id
                WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
                ORDER BY o.page, o.paragraph, o.sentence
                """
            ).fetchall()
            id_to_n = {r["id"]: i + 1 for i, r in enumerate(all_obs)}
            n_to_id = {i + 1: r["id"] for i, r in enumerate(all_obs)}
            active_ids = set(id_to_n)

            # ── Accepted interpretations ───────────────────────────────────
            raw_interps = conn.execute(
                """SELECT i.id, i.observation_id, i.text, i.evidential_status,
                          i.evidence_observation_ids,
                          COALESCE(sd.source_role, 'primary') AS source_role,
                          sd.original_filename
                   FROM interpretations i
                   JOIN observations o ON o.id = i.observation_id
                   JOIN source_documents sd ON sd.id = o.source_document_id
                   WHERE i.evidential_status IN ('established','accepted','speculative')
                     AND COALESCE(sd.excluded_from_analysis, 0) = 0
                   ORDER BY i.created_at"""
            ).fetchall()
            interps = []
            for interp in raw_interps:
                evidence_ids = _json_loads(interp["evidence_observation_ids"], [])
                if isinstance(evidence_ids, list) and any(str(oid) not in active_ids for oid in evidence_ids):
                    continue
                interps.append(interp)

            interp_lines = []
            for i in interps:
                n = id_to_n.get(i["id"]) or id_to_n.get(i["observation_id"], "?")
                obs_n = id_to_n.get(i["observation_id"], "?")
                role = i["source_role"] or "primary"
                role_note = (
                    "primary evidence"
                    if role == "primary"
                    else f"NON-PRIMARY {role} evidence from {i['original_filename']}; do not treat as primary"
                )
                interp_lines.append(
                    f"INTERP-{i['id'][:8]} [OBS-{obs_n}] [{i['evidential_status']}] [{role_note}]: {i['text']}"
                )

            # ── Sample observations (spread across corpus) ─────────────────
            step = max(1, len(all_obs) // 40)
            sample_obs = all_obs[::step][:40]
            obs_lines = []
            for r in sample_obs:
                role = r["source_role"] or "primary"
                role_note = (
                    "primary evidence"
                    if role == "primary"
                    else f"NON-PRIMARY {role} evidence from {r['original_filename']}; do not treat as primary"
                )
                obs_lines.append(
                    f"OBS-{id_to_n[r['id']]} (p.{r['page']}) [{role_note}]: {r['raw_text'][:200]}"
                )

            # ── Build prompt ───────────────────────────────────────────────
            prompt = f"""You are the Hermeneia Architect. Your job is evidence-first research design, not thesis generation.

RESEARCH DIRECTIVE:
{directive}

CRITICAL INSTRUCTION — READ BEFORE PROCEEDING:
Do NOT start from a thesis and find supporting evidence.
Start from the evidence and let the structure emerge.

SOURCE ROLE RULE:
Excluded documents are absent from this prompt. If a line is labelled NON-PRIMARY,
preserve that role in reasoning and do not treat commentary, reference, notes, or
exploratory material as primary evidence.

Your process must be:
1. Survey the observations and interpretations for everything relevant to the directive
2. Group related evidence into distinct analytical sections
3. State a claim for each section that the evidence actually supports
4. Derive a thesis LAST, as a synthesis of what the sections establish

For a directive about metaphors, each section should be ONE metaphor or metaphor cluster with ALL its relevant observations. A 10-page analysis requires 8–12 sections minimum. Do not collapse multiple distinct metaphors into one section.

ACCEPTED INTERPRETATIONS ({len(interps)} total):
{chr(10).join(interp_lines) or '(none yet — use observations only)'}

OBSERVATION SAMPLE ({len(sample_obs)} of {len(all_obs)} total):
{chr(10).join(obs_lines)}

RULES:
- Each section = one distinct idea, metaphor, motif, or analytical point
- Each section must cite at least one OBS-N from the list above
- Do not invent observations or interpretations not in the lists above
- Aim for 8–12 sections for a research assignment; do not compress
- The thesis is derived from the sections, not imposed on them

Return ONLY valid JSON, no markdown, no explanation:
{{
  "title": "descriptive title for this analysis",
  "thesis": "one-sentence thesis synthesized from all sections below",
  "sections": [
    {{
      "claim": "the specific analytical claim this section establishes",
      "obs_refs": ["OBS-19", "OBS-23"],
      "interp_refs": ["INTERP-ab12cd34"]
    }}
  ]
}}"""

            provider_kwargs = _provider_kwargs(provider)
            prov = get_provider(provider, **provider_kwargs)
            raw = prov.render(prompt)

            # ── Parse AI response ──────────────────────────────────────────
            # Strip markdown code fences if present
            cleaned = _re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=_re.MULTILINE).strip()
            try:
                bp_data = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                return jsonify({"error": f"AI returned invalid JSON: {exc}", "raw": raw[:500]}), 500

            title   = str(bp_data.get("title", "Untitled Blueprint")).strip()
            thesis  = str(bp_data.get("thesis", "")).strip()
            ai_sections = bp_data.get("sections", [])
            if not thesis or not ai_sections:
                return jsonify({"error": "AI response missing thesis or sections", "raw": raw[:500]}), 500

            # ── Resolve obs/interp refs to IDs ─────────────────────────────
            interp_id_map = {i["id"][:8]: i["id"] for i in interps}
            sections_data = []
            for sec in ai_sections:
                claim = str(sec.get("claim", "")).strip()
                obs_ids_sec = []
                for ref in sec.get("obs_refs", []):
                    m = _re.search(r"(\d+)", str(ref))
                    if m:
                        n = int(m.group(1))
                        if n in n_to_id:
                            obs_ids_sec.append(n_to_id[n])
                interp_ids_sec = []
                for ref in sec.get("interp_refs", []):
                    short = str(ref).replace("INTERP-", "")[:8]
                    if short in interp_id_map:
                        interp_ids_sec.append(interp_id_map[short])
                if claim:
                    sections_data.append({
                        "claim": claim,
                        "supporting_observations": obs_ids_sec,
                        "supporting_interpretations": interp_ids_sec,
                    })

            if not sections_data:
                return jsonify({"error": "No valid sections could be built from AI response", "raw": raw[:500]}), 500

            # ── Store blueprint ────────────────────────────────────────────
            now = _dt.datetime.now(_dt.timezone.utc).isoformat()
            bp_id = make_blueprint_id(title, thesis, sections_data)

            conn.execute(
                """INSERT OR IGNORE INTO narrative_blueprints
                   (id, title, thesis, sections, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (bp_id, title, thesis, json.dumps(sections_data), "ai-generated", now),
            )
            for sec in sections_data:
                for oid in sec["supporting_observations"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO blueprint_observation_links (blueprint_id, observation_id) VALUES (?, ?)",
                        (bp_id, oid),
                    )
                for iid in sec["supporting_interpretations"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO blueprint_interpretation_links (blueprint_id, interpretation_id) VALUES (?, ?)",
                        (bp_id, iid),
                    )
            conn.commit()

            # ── Compile ArchitectPlan ──────────────────────────────────────
            from ..storage.sqlite import ensure_architect_tables
            ensure_architect_tables(conn)

            plan = compile_architect_plan(bp_id, conn)
            pr   = plan["plan_row"]
            plan_id = pr["id"]

            conn.execute(
                """INSERT OR IGNORE INTO architect_plans
                   (id, blueprint_id, blueprint_hash, title, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (plan_id, pr["blueprint_id"], pr["blueprint_hash"],
                 pr["title"], pr["source"], pr["created_at"]),
            )
            for para in plan["paragraph_rows"]:
                conn.execute(
                    """INSERT OR IGNORE INTO architect_plan_paragraphs
                       (plan_id, order_idx, purpose, blueprint_section,
                        required_observations, required_interpretations,
                        required_terms, forbidden_claims, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (para["plan_id"], para["order_idx"], para["purpose"],
                     para["blueprint_section"], para["required_observations"],
                     para["required_interpretations"], para["required_terms"],
                     para["forbidden_claims"], para["notes"]),
                )
            conn.commit()

            return jsonify({
                "blueprint_id": bp_id,
                "plan_id": plan_id,
                "title": title,
                "thesis": thesis,
                "section_count": len(sections_data),
            }), 201

        except Exception as exc:
            return jsonify({
                "error": str(exc),
                "error_type": type(exc).__name__,
                "detail": _tb.format_exc(),
            }), 500
        finally:
            conn.close()

    # ── /api/architect/import ─────────────────────────────────────────────────

    @app.route("/api/architect/import", methods=["POST"])
    def api_architect_import():
        """Import a user-authored blueprint directly.

        Body:
          {
            "title": str,
            "thesis": str,
            "sections": [
              { "claim": str, "obs_refs": ["OBS-N", ...] }
            ]
          }

        obs_refs are optional. Sections without obs_refs are stored with
        empty supporting_observations (the plan will still compile and
        render — it just won't have observation-level traceability).
        """
        import datetime as _dt, traceback as _tb

        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        payload = request.get_json(silent=True) or {}
        title   = str(payload.get("title", "")).strip()
        thesis  = str(payload.get("thesis", "")).strip()
        raw_sections = payload.get("sections", [])

        if not title:
            return jsonify({"error": "title is required"}), 400
        if not thesis:
            return jsonify({"error": "thesis is required"}), 400
        if not raw_sections:
            return jsonify({"error": "at least one section is required"}), 400

        from ..storage.hashing import make_blueprint_id, make_architect_plan_id
        from ..compiler.architect import compile_architect_plan
        from ..storage.sqlite import ensure_architect_tables
        import re as _re

        conn = _conn_rw()
        try:
            all_obs = active_observation_ids(conn)
            n_to_id = {i + 1: oid for i, oid in enumerate(all_obs)}

            sections_data = []
            for sec in raw_sections:
                claim = str(sec.get("claim", "")).strip()
                if not claim:
                    continue
                obs_ids_sec = []
                for ref in sec.get("obs_refs", []):
                    m = _re.search(r"(\d+)", str(ref))
                    if m:
                        n = int(m.group(1))
                        if n in n_to_id:
                            obs_ids_sec.append(n_to_id[n])
                sections_data.append({
                    "claim": claim,
                    "supporting_observations": obs_ids_sec,
                    "supporting_interpretations": [],
                })

            if not sections_data:
                return jsonify({"error": "No valid sections found"}), 400

            now = _dt.datetime.now(_dt.timezone.utc).isoformat()
            bp_id = make_blueprint_id(title, thesis, sections_data)

            conn.execute(
                """INSERT OR IGNORE INTO narrative_blueprints
                   (id, title, thesis, sections, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (bp_id, title, thesis, json.dumps(sections_data), "steward-authored", now),
            )
            for sec in sections_data:
                for oid in sec["supporting_observations"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO blueprint_observation_links (blueprint_id, observation_id) VALUES (?, ?)",
                        (bp_id, oid),
                    )
            conn.commit()

            ensure_architect_tables(conn)
            plan = compile_architect_plan(bp_id, conn)
            pr   = plan["plan_row"]
            plan_id = pr["id"]

            conn.execute(
                """INSERT OR IGNORE INTO architect_plans
                   (id, blueprint_id, blueprint_hash, title, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (plan_id, pr["blueprint_id"], pr["blueprint_hash"],
                 pr["title"], pr["source"], pr["created_at"]),
            )
            for para in plan["paragraph_rows"]:
                conn.execute(
                    """INSERT OR IGNORE INTO architect_plan_paragraphs
                       (plan_id, order_idx, purpose, blueprint_section,
                        required_observations, required_interpretations,
                        required_terms, forbidden_claims, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (para["plan_id"], para["order_idx"], para["purpose"],
                     para["blueprint_section"], para["required_observations"],
                     para["required_interpretations"], para["required_terms"],
                     para["forbidden_claims"], para["notes"]),
                )
            conn.commit()

            return jsonify({
                "blueprint_id": bp_id,
                "plan_id": plan_id,
                "title": title,
                "thesis": thesis,
                "section_count": len(sections_data),
            }), 201

        except Exception as exc:
            return jsonify({
                "error": str(exc),
                "error_type": type(exc).__name__,
                "detail": _tb.format_exc(),
            }), 500
        finally:
            conn.close()

    # ── /api/documents ────────────────────────────────────────────────────────

    @app.route("/api/documents")
    def api_documents():
        """List source documents with scope status."""
        if not db_path.exists():
            return jsonify({"documents": []})
        conn = _conn()
        rows = conn.execute(
            """
            SELECT sd.id, sd.original_filename, sd.total_pages, sd.registered_at,
                   sd.excluded_from_analysis, sd.source_role,
                   COUNT(DISTINCT o.id) AS observation_count
            FROM source_documents sd
            LEFT JOIN observations o ON o.source_document_id = sd.id
            GROUP BY sd.id
            ORDER BY sd.registered_at ASC
            """
        ).fetchall()
        conn.close()
        return jsonify({
            "documents": [
                {
                    "id": r["id"],
                    "filename": r["original_filename"],
                    "total_pages": r["total_pages"],
                    "registered_at": r["registered_at"],
                    "observation_count": r["observation_count"],
                    "excluded": bool(r["excluded_from_analysis"]),
                    "source_role": r["source_role"] or "primary",
                }
                for r in rows
            ]
        })

    @app.route("/api/documents/<doc_id>/scope", methods=["PATCH"])
    def api_document_scope(doc_id: str):
        """Set a document's analysis scope (exclude/include, source_role).

        Body: { excluded: bool, source_role: str }
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        store = _store()
        try:
            excluded = payload["excluded"] if "excluded" in payload else None
            source_role = str(payload["source_role"]).strip() if "source_role" in payload else None
            # Primary corpus documents cannot be excluded — they are the evidentiary foundation.
            if excluded:
                conn = _conn()
                row = conn.execute(
                    "SELECT source_role FROM source_documents WHERE id = ?", (doc_id,)
                ).fetchone()
                if row and (row["source_role"] or "primary") == "primary":
                    return jsonify({"error": "Primary corpus documents cannot be excluded. Change the document's role first if you intend to demote it."}), 400
            try:
                updated = store.set_document_scope(
                    doc_id,
                    excluded=excluded,
                    source_role=source_role,
                )
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            if updated is None:
                return jsonify({"error": "document not found"}), 404
            return jsonify({
                "id": updated["id"],
                "filename": updated["original_filename"],
                "excluded": bool(updated["excluded_from_analysis"]),
                "source_role": updated["source_role"],
            })
        finally:
            store.close()

    # ── Inquiry Notes (/api/observations/<id>/review, /api/observations/<id>/inquiry) ──

    _VALID_REVIEW_STATUSES = {"approved", "rejected", "unsure"}
    _VALID_QUESTION_TYPES = {
        "evidence_needed", "meaning_unclear", "classification_unclear",
        "contradiction", "connection_possible", "overreach_suspected",
        "sequence_question", "unclassified",
    }

    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    @app.route("/api/observations/<observation_id>/review", methods=["GET"])
    def api_obs_review_get(observation_id: str):
        if not db_path.exists():
            return jsonify({"review": None, "inquiry_notes": []}), 200
        conn = _conn_rw()
        try:
            require_active_observation(conn, observation_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        review = conn.execute(
            "SELECT * FROM observation_reviews WHERE observation_id = ?", (observation_id,)
        ).fetchone()
        notes = conn.execute(
            "SELECT * FROM inquiry_notes WHERE observation_id = ? ORDER BY created_at",
            (observation_id,),
        ).fetchall()
        conn.close()
        return jsonify({
            "review": dict(review) if review else None,
            "inquiry_notes": [dict(n) for n in notes],
        })

    @app.route("/api/observations/<observation_id>/review", methods=["POST"])
    def api_obs_review_post(observation_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        status = payload.get("review_status", "")
        if status not in _VALID_REVIEW_STATUSES:
            return jsonify({"error": f"review_status must be one of {sorted(_VALID_REVIEW_STATUSES)}"}), 400
        conn = _conn_rw()
        try:
            require_active_observation(conn, observation_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        obs = conn.execute("SELECT id FROM observations WHERE id = ?", (observation_id,)).fetchone()
        if not obs:
            return jsonify({"error": "observation not found"}), 404
        now = _now_iso()
        review_id = str(__import__("uuid").uuid4())
        existing = conn.execute(
            "SELECT id FROM observation_reviews WHERE observation_id = ?", (observation_id,)
        ).fetchone()
        if existing:
            review_id = existing["id"]
            conn.execute(
                """UPDATE observation_reviews
                   SET review_status=?, steward_note=?, reason_for_status=?,
                       follow_up_needed=?, pass_id=?, updated_at=?
                   WHERE id=?""",
                (
                    status,
                    payload.get("steward_note") or None,
                    payload.get("reason_for_status") or None,
                    1 if payload.get("follow_up_needed") else 0,
                    payload.get("pass_id") or None,
                    now,
                    review_id,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO observation_reviews
                   (id, observation_id, review_status, steward_note, reason_for_status,
                    follow_up_needed, pass_id, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    review_id,
                    observation_id,
                    status,
                    payload.get("steward_note") or None,
                    payload.get("reason_for_status") or None,
                    1 if payload.get("follow_up_needed") else 0,
                    payload.get("pass_id") or None,
                    now,
                    now,
                ),
            )
        conn.commit()
        review = conn.execute(
            "SELECT * FROM observation_reviews WHERE id = ?", (review_id,)
        ).fetchone()
        return jsonify({"review": dict(review)})

    @app.route("/api/observations/<observation_id>/inquiry", methods=["POST"])
    def api_obs_inquiry_post(observation_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        question_text = (payload.get("question_text") or "").strip()
        if not question_text:
            return jsonify({"error": "question_text is required"}), 400
        question_type = payload.get("question_type") or "unclassified"
        if question_type not in _VALID_QUESTION_TYPES:
            question_type = "unclassified"
        conn = _conn_rw()
        try:
            require_active_observation(conn, observation_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        obs = conn.execute("SELECT id FROM observations WHERE id = ?", (observation_id,)).fetchone()
        if not obs:
            return jsonify({"error": "observation not found"}), 404
        review = conn.execute(
            "SELECT id FROM observation_reviews WHERE observation_id = ?", (observation_id,)
        ).fetchone()
        now = _now_iso()
        note_id = str(__import__("uuid").uuid4())
        conn.execute(
            """INSERT INTO inquiry_notes
               (id, observation_id, review_id, question_text, question_type, created_at)
               VALUES (?,?,?,?,?,?)""",
            (note_id, observation_id, review["id"] if review else None,
             question_text, question_type, now),
        )
        conn.commit()
        note = conn.execute("SELECT * FROM inquiry_notes WHERE id = ?", (note_id,)).fetchone()
        return jsonify({"inquiry_note": dict(note)}), 201

    @app.route("/api/observations/<observation_id>/inquiry/<note_id>", methods=["DELETE"])
    def api_obs_inquiry_delete(observation_id: str, note_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn_rw()
        try:
            require_active_observation(conn, observation_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        conn.execute(
            "DELETE FROM inquiry_notes WHERE id = ? AND observation_id = ?",
            (note_id, observation_id),
        )
        conn.commit()
        return jsonify({"deleted": note_id})

    @app.route("/api/observations/reviews/summary")
    def api_obs_reviews_summary():
        if not db_path.exists():
            return jsonify({"total": 0, "approved": 0, "rejected": 0, "unsure": 0,
                            "questions": 0, "follow_up_needed": 0, "by_question_type": {}}), 200
        conn = _conn_rw()
        rows = conn.execute(
            """SELECT review_status, COUNT(*) as cnt, SUM(follow_up_needed) as fup
               FROM observation_reviews GROUP BY review_status"""
        ).fetchall()
        counts = {"approved": 0, "rejected": 0, "unsure": 0, "follow_up_needed": 0}
        for r in rows:
            counts[r["review_status"]] = r["cnt"]
            counts["follow_up_needed"] += r["fup"] or 0
        total = counts["approved"] + counts["rejected"] + counts["unsure"]
        qtypes = conn.execute(
            "SELECT question_type, COUNT(*) as cnt FROM inquiry_notes GROUP BY question_type"
        ).fetchall()
        by_type = {r["question_type"]: r["cnt"] for r in qtypes}
        total_questions = sum(by_type.values())
        return jsonify({
            "total": total,
            "approved": counts["approved"],
            "rejected": counts["rejected"],
            "unsure": counts["unsure"],
            "questions": total_questions,
            "follow_up_needed": counts["follow_up_needed"],
            "by_question_type": by_type,
        })

    # ── /api/upload ────────────────────────────────────────────────────────────

    _VALID_SOURCE_ROLES = {"primary", "reference", "commentary", "notes", "exploratory"}

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        """Accept a PDF upload, compile it into the corpus, return observation counts.

        Multipart form-data with field name 'file'.
        Optional form field 'role': primary (default), reference, commentary, notes, exploratory.
        Optional form field 'label': human-readable label for the document.
        Idempotent: recompiling the same PDF (same SHA-256) inserts nothing.
        """
        from ..compiler.compiler import Compiler

        if "file" not in request.files:
            return jsonify({"error": "No file field in request"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"error": "Empty filename"}), 400
        if not f.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are supported"}), 415

        source_role = request.form.get("role", "primary").strip().lower()
        if source_role not in _VALID_SOURCE_ROLES:
            source_role = "primary"

        build_dir = db_path.parent
        uploads_dir = build_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # Save to a named temp file so the compiler can hash it
        suffix = Path(f.filename).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(
            dir=uploads_dir, suffix=suffix, delete=False,
            prefix=Path(f.filename).stem + "_",
        ) as tmp:
            f.save(tmp.name)
            saved_path = Path(tmp.name)

        try:
            compiler = Compiler(db_path=db_path, build_dir=build_dir)
            compiler.compile(saved_path)
            compiler.close()
        except Exception as exc:
            saved_path.unlink(missing_ok=True)
            return jsonify({"error": f"Compilation failed: {exc}"}), 500

        # Read back counts from the freshly compiled document
        conn = _conn()
        doc = conn.execute(
            "SELECT id, original_filename, total_pages FROM source_documents ORDER BY registered_at DESC LIMIT 1"
        ).fetchone()
        obs_count = 0
        term_count = 0
        if doc:
            # Apply the requested source role via the storage layer (not raw SQL)
            if source_role != "primary":
                _upload_store = _store()
                _upload_store.set_document_scope(doc["id"], source_role=source_role)
                _upload_store.close()
            obs_count = conn.execute(
                "SELECT COUNT(*) FROM observations WHERE source_document_id = ?", (doc["id"],)
            ).fetchone()[0]
            term_count = conn.execute(
                """
                SELECT COUNT(DISTINCT ot.term_id)
                FROM observation_terms ot
                WHERE ot.observation_id IN (
                    SELECT id FROM observations WHERE source_document_id = ?
                )
                """,
                (doc["id"],),
            ).fetchone()[0]
        conn.close()

        # Rename temp file to the original filename for future reference
        final_path = uploads_dir / f.filename
        if not final_path.exists():
            saved_path.rename(final_path)
        else:
            saved_path.unlink(missing_ok=True)

        return jsonify({
            "status": "compiled",
            "filename": f.filename,
            "document_id": doc["id"] if doc else None,
            "total_pages": doc["total_pages"] if doc else None,
            "observation_count": obs_count,
            "term_count": term_count,
            "source_role": source_role,
        })

    @app.route("/api/project/summary")
    def api_project_summary():
        """Read-only project goal banner derived from current corpus state."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()
        doc = conn.execute(
            """
            SELECT id, original_filename, total_pages
            FROM source_documents
            ORDER BY registered_at DESC, id
            LIMIT 1
            """
        ).fetchone()
        bp = conn.execute(
            "SELECT title, thesis FROM narrative_blueprints ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        counts = {
            "observations": _table_count(conn, "observations"),
            "interpretations": _table_count(conn, "interpretations"),
            "proposed_interpretations": _table_count(conn, "proposed_interpretations"),
            "blueprints": _table_count(conn, "narrative_blueprints"),
            "architect_plans": _table_count(conn, "architect_plans"),
            "narratives": _table_count(conn, "rendered_narratives"),
            "audits": _table_count(conn, "validation_reports"),
            "critic_reports": _table_count(conn, "critic_reports"),
            "findings": _table_count(conn, "findings"),
        }
        _raw_pipeline = [
            {
                "key": "observations",
                "label": "Observe",
                "description": "Extract evidence from source documents",
                "count": counts["observations"],
                "surface": "/api/e10/observations",
                "nav_target": "corpus",
            },
            {
                "key": "interpretations",
                "label": "Interpret",
                "description": "Assign meaning to what was observed",
                "count": counts["interpretations"],
                "surface": "/api/review/interpretations",
                "nav_target": "lab",
            },
            {
                "key": "blueprints",
                "label": "Organize",
                "description": "Arrange interpretations into a coherent argument",
                "count": counts["blueprints"],
                "surface": "/api/architect/blueprints",
                "nav_target": "architect",
            },
            {
                "key": "architect_plans",
                "label": "Plan",
                "description": "Specify what the report must communicate",
                "count": counts["architect_plans"],
                "surface": "/api/architect/blueprints",
                "nav_target": "architect",
            },
            {
                "key": "narratives",
                "label": "Render",
                "description": "Generate the report with an AI provider",
                "count": counts["narratives"],
                "surface": "/api/reader/narratives",
                "nav_target": "reports",
            },
            {
                "key": "audits",
                "label": "Audit",
                "description": "Measure how faithfully the report preserved the evidence",
                "count": counts["audits"],
                "surface": "/api/critic/reports",
                "nav_target": "critic",
            },
        ]
        # Derive completion status: complete → current → pending
        # The first stage with count == 0 after a run of complete stages is "current".
        found_current = False
        pipeline = []
        for stage in _raw_pipeline:
            if found_current:
                status = "pending"
            elif stage["count"] > 0:
                status = "complete"
            else:
                status = "current"
                found_current = True
            pipeline.append({**stage, "status": status})
        conn.close()
        thesis = bp["thesis"] if bp else None
        return jsonify({
            "blueprint_title": bp["title"] if bp else None,
            "thesis": thesis,
            "project_goal": {
                "label": "Research Question",
                "text": thesis,
                "source": "latest_narrative_blueprint" if bp else None,
            },
            "document": {
                "source_document_id": doc["id"] if doc else None,
                "filename": doc["original_filename"] if doc else None,
                "total_pages": doc["total_pages"] if doc else None,
            },
            "counts": counts,
            "pipeline": pipeline,
        })

    @app.route("/api/pipeline/extract-blueprint", methods=["POST"])
    def api_pipeline_extract_blueprint():
        """Extract a Blueprint Intent Hypothesis from an existing document.

        Body: {
          "text": "<document text>",
          "provider": "anthropic",   // optional, default "null"
          "model": null,             // optional
          "save": true               // optional: save and compile Blueprint (default false)
        }

        Returns:
          { "proposed_blueprint": {title, thesis, sections} }
          or if save=true:
          { "blueprint_id": "...", "plan_id": "...", "proposed_blueprint": {...} }
        """
        payload = request.get_json(silent=True) or {}
        text     = str(payload.get("text", "")).strip()
        provider = str(payload.get("provider", "null")).strip()
        save     = bool(payload.get("save", False))

        if not text:
            return jsonify({"error": "text is required"}), 400

        if save and not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        from ..compiler.blueprint_extractor import extract_blueprint_from_text, BlueprintExtractionError
        from ..narrative.artist_providers import get_provider
        import traceback as _tb

        try:
            kwargs = _provider_kwargs(provider)
            prov = get_provider(provider, **kwargs)
            proposed = extract_blueprint_from_text(text, prov)
        except BlueprintExtractionError as exc:
            return jsonify({"error": str(exc), "error_type": "BlueprintExtractionError"}), 422
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": _tb.format_exc()}), 500

        if not save:
            return jsonify({"proposed_blueprint": proposed}), 200

        # Save the Blueprint and run Architect
        from ..storage.hashing import make_blueprint_id
        from ..compiler.architect import compile_architect_plan
        import json as _json
        from datetime import datetime, timezone

        conn = _conn_rw()
        try:
            bp_id = make_blueprint_id(proposed["title"], proposed["thesis"], proposed["sections"])
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                """
                INSERT OR IGNORE INTO narrative_blueprints
                    (id, title, thesis, sections, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (bp_id, proposed["title"], proposed["thesis"],
                 _json.dumps(proposed["sections"]), "extracted", now),
            )
            conn.commit()

            result = compile_architect_plan(bp_id, conn)
            from ..storage.sqlite import SQLiteStore
            store = SQLiteStore(db_path)
            store.insert_architect_plan(result["plan_row"], result["paragraph_rows"])
            store.close()

            return jsonify({
                "proposed_blueprint": proposed,
                "blueprint_id": bp_id,
                "plan_id": result["plan_row"]["id"],
            }), 201
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": _tb.format_exc()}), 500
        finally:
            conn.close()

    @app.route("/api/pipeline/run-artist", methods=["POST"])
    def api_pipeline_run_artist():
        """Trigger an Artist render from the UI.

        Body (active blueprint): { plan_id: "<id>", provider: "openai", profile: "literary-en" }
        Body (obs lookup):       { obs_ref: "OBS-19", provider: "openai", profile: "literary-en" }
        Returns the rendered narrative id and a preview of the text.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        plan_id  = str(payload.get("plan_id", "")).strip()
        obs_ref  = str(payload.get("obs_ref", "")).strip()
        provider = str(payload.get("provider", "openai")).strip()
        profile  = str(payload.get("profile", "literary-en")).strip()
        if not plan_id and not obs_ref:
            return jsonify({"error": "plan_id or obs_ref is required"}), 400

        from ..narrative.artist_service import ArtistRenderError, render_for_observation, render_for_plan
        import traceback as _tb
        conn = _conn_rw()
        try:
            provider_kwargs = _provider_kwargs(provider)
            if plan_id:
                result = render_for_plan(
                    plan_id,
                    conn,
                    provider_name=provider,
                    profile_slug=profile,
                    provider_kwargs=provider_kwargs,
                )
            else:
                result = render_for_observation(
                    obs_ref,
                    conn,
                    provider_name=provider,
                    profile_slug=profile,
                    provider_kwargs=provider_kwargs,
                )
            status_code = 201 if result.created else 200
            return jsonify({
                "id": result.row["id"],
                "provider": result.row["provider"],
                "profile": profile,
                "text_preview": result.row["text"][:300],
                "created_at": result.row["created_at"],
                "status": "created" if result.created else "already_exists",
            }), status_code
        except ArtistRenderError as exc:
            return jsonify({
                "error": str(exc),
                "error_type": type(exc).__name__,
            }), 400

        except Exception as exc:
            return jsonify({
                "error": str(exc),
                "error_type": type(exc).__name__,
                "detail": _tb.format_exc(),
            }), 500
        finally:
            conn.close()

    @app.route("/api/pipeline/preview-artist", methods=["POST"])
    def api_pipeline_preview_artist():
        """Preview an Artist draft WITHOUT persisting it (Reader "Draft" tab).

        Body: { plan_id: "<id>", profile: "<slug>"?, provider: "null"? }

        Renders the ArchitectPlan under the chosen ExpressionProfile and returns
        the full draft text. Nothing is written to `rendered_narratives`: this is
        a preview, not an accepted narrative. Provider defaults to the stub
        ("null") so the preview is safe and free unless a provider is chosen.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        plan_id = str(payload.get("plan_id", "")).strip()
        provider = str(payload.get("provider", "null")).strip() or "null"
        profile = str(payload.get("profile", "")).strip() or None
        if not plan_id:
            return jsonify({"error": "plan_id is required"}), 400

        from ..narrative.artist_service import ArtistRenderError, render_for_plan
        import traceback as _tb

        # Read-only connection: structurally guarantees the preview writes nothing.
        conn = _conn()
        try:
            provider_kwargs = _provider_kwargs(provider)
            result = render_for_plan(
                plan_id,
                conn,
                provider_name=provider,
                profile_slug=profile,
                provider_kwargs=provider_kwargs,
                persist=False,
            )
            prof = result.profile
            return jsonify({
                "preview": True,
                "persisted": False,
                "plan_id": plan_id,
                "provider": result.row["provider"],
                "profile_slug": profile,
                "profile_name": (prof["name"] if prof else None),
                "text": result.row["text"],
            }), 200
        except ArtistRenderError as exc:
            return jsonify({"error": str(exc), "error_type": type(exc).__name__}), 400
        except Exception as exc:
            return jsonify({
                "error": str(exc),
                "error_type": type(exc).__name__,
                "detail": _tb.format_exc(),
            }), 500
        finally:
            conn.close()

    @app.route("/api/pipeline/ratify-draft", methods=["POST"])
    def api_pipeline_ratify_draft():
        """Ratify & save the EXACT previewed Artist draft as a RenderedNarrative.

        Body: { plan_id, provider, profile_slug?, text }

        Persists the bytes the steward saw and judged — verbatim, no re-render,
        no provider call. Deterministic id means a second ratify is idempotent;
        the record is immutable (no post-save mutation). Explicit action only.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        plan_id = str(payload.get("plan_id", "")).strip()
        provider = str(payload.get("provider", "")).strip() or "null"
        profile_slug = str(payload.get("profile_slug", "")).strip() or None
        text = payload.get("text")
        if not plan_id:
            return jsonify({"error": "plan_id is required"}), 400
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "text is required"}), 400

        from ..narrative.artist_service import ArtistRenderError, ratify_draft

        conn = _conn_rw()
        try:
            result = ratify_draft(
                plan_id, conn, provider=provider, profile_slug=profile_slug, text=text,
            )
        except ArtistRenderError as exc:
            return jsonify({"error": str(exc), "error_type": type(exc).__name__}), 400
        finally:
            conn.close()

        row = result["row"]
        return jsonify({
            "id": row["id"],
            "created": result["created"],
            "status": "ratified" if result["created"] else "already_ratified",
            "provider": row["provider"],
            "profile_slug": profile_slug,
            "plan_id": plan_id,
            "blueprint_id": result.get("blueprint_id"),
        }), (201 if result["created"] else 200)

    @app.route("/api/critic/voice-preview", methods=["POST"])
    def api_critic_voice_preview():
        """Judge an Artist draft against an ExpressionProfile's witness constraints.

        Body: { text: "<draft>", profile_slug: "<slug>" }

        Deterministic voice/witness audit: preserve/avoid phrase checks + the
        built-in profile expression checks + surfaced critic_expectations. Reads
        only; writes nothing. Runs on a previewed (unsaved) draft, before ratify —
        so discernment comes before persistence.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        profile_slug = str(payload.get("profile_slug", "")).strip()
        if not text:
            return jsonify({"error": "text is required"}), 400
        if not profile_slug:
            return jsonify({"error": "profile_slug is required"}), 400

        from ..narrative.profiles import get_profile
        from ..compiler.critic.profile_fidelity import check_witness_fidelity

        conn = _conn()
        try:
            profile = get_profile(profile_slug, conn)
            if profile is None:
                return jsonify({"error": f"profile '{profile_slug}' not found"}), 404
            report = check_witness_fidelity(text, dict(profile))
        finally:
            conn.close()
        report.update({"preview": True, "persisted": False})
        return jsonify(report), 200

    @app.route("/api/pipeline/run-artist-all-profiles", methods=["POST"])
    def api_pipeline_run_artist_all_profiles():
        """Render the same ArchitectPlan with every available Expression Profile.

        Body: { plan_id: "<id>", provider: "openai", model: null }
        Returns: { results: [{profile_slug, narrative_id, status, language}] }
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        plan_id  = str(payload.get("plan_id", "")).strip()
        provider = str(payload.get("provider", "openai")).strip()

        if not plan_id:
            return jsonify({"error": "plan_id is required"}), 400

        from ..narrative.artist_service import ArtistRenderError, render_for_plan
        from ..narrative.profiles import list_profiles
        import traceback as _tb

        conn = _conn_rw()
        try:
            provider_kwargs = _provider_kwargs(provider)

            profiles = list_profiles(conn)
            if not profiles:
                return jsonify({"error": "No Expression Profiles found"}), 400

            results = []
            for profile in profiles:
                slug = profile["slug"]
                try:
                    result = render_for_plan(
                        plan_id, conn,
                        provider_name=provider,
                        profile_slug=slug,
                        provider_kwargs=provider_kwargs,
                    )
                    results.append({
                        "profile_slug": slug,
                        "profile_name": profile["name"],
                        "language": profile.get("language", "en"),
                        "narrative_id": result.row["id"],
                        "status": "created" if result.created else "exists",
                    })
                except ArtistRenderError as exc:
                    results.append({
                        "profile_slug": slug,
                        "profile_name": profile["name"],
                        "language": profile.get("language", "en"),
                        "narrative_id": None,
                        "status": "error",
                        "error": str(exc),
                    })
            return jsonify({"plan_id": plan_id, "results": results}), 200
        except Exception as exc:
            return jsonify({"error": str(exc), "detail": _tb.format_exc()}), 500
        finally:
            conn.close()

    @app.route("/api/pipeline/run-critic", methods=["POST"])
    def api_pipeline_run_critic():
        """Trigger a Critic evaluation from the UI.

        Body: { narrative_id: "<id>" }  — or obs_ref to auto-pick latest narrative.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        narrative_id = str(payload.get("narrative_id", "")).strip() or None
        obs_ref = str(payload.get("obs_ref", "")).strip() or None

        conn = _conn_rw()
        try:
            from ..compiler.critic import run_critic
            from ..storage.sqlite import ensure_critic_tables

            ensure_critic_tables(conn)

            if narrative_id:
                all_ids = []
                n = 0
            elif obs_ref:
                n_str = obs_ref.upper().replace("OBS-", "")
                n = int(n_str)
                all_ids = active_observation_ids(conn)
            else:
                return jsonify({"error": "narrative_id or obs_ref required"}), 400

            report = run_critic(n, all_ids, conn, narrative_id=narrative_id)

            existing = conn.execute(
                "SELECT * FROM validation_reports WHERE id = ?", (report["id"],)
            ).fetchone()
            if existing:
                return jsonify({"status": "already_exists", "report": dict(existing)}), 200

            conn.execute(
                """INSERT INTO validation_reports
                   (id, rendered_narrative_id, architect_plan_id, expression_profile_id,
                    semantic_fidelity, required_terms_present, required_terms_missing,
                    unsupported_claims, omitted_observations, omitted_interpretations,
                    semantic_drift, warnings, approved, profile_fidelity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report["id"], report["rendered_narrative_id"], report["architect_plan_id"],
                    report.get("expression_profile_id"),
                    report["semantic_fidelity"],
                    report["required_terms_present"],
                    report["required_terms_missing"],
                    report.get("unsupported_claims", "[]"),
                    report.get("omitted_observations", "[]"),
                    report.get("omitted_interpretations", "[]"),
                    report.get("semantic_drift", "[]"),
                    report.get("warnings", "[]"),
                    int(report.get("approved", False)),
                    report.get("profile_fidelity"),
                    report["created_at"],
                ),
            )
            conn.commit()

            # Run all Evaluation Functions and persist Findings
            ef_run_result = None
            ef_errors: dict = {}
            try:
                from ..compiler.evaluation_functions.runner import run_all_evaluation_functions
                from ..storage.sqlite import SQLiteStore
                ef_run_result = run_all_evaluation_functions(
                    report["rendered_narrative_id"],
                    report["architect_plan_id"],
                    conn,
                )
                if ef_run_result.all_findings:
                    store = SQLiteStore(db_path)
                    store.insert_findings_batch(ef_run_result.all_findings)
                    store.close()
                ef_errors = ef_run_result.errors
            except Exception as run_exc:
                ef_errors = {"runner": str(run_exc)}

            pf = report.get("profile_fidelity")
            return jsonify({"status": "created", "report": {
                "id": report["id"],
                "semantic_fidelity": report["semantic_fidelity"],
                "approved": report.get("approved", False),
                "profile_fidelity": json.loads(pf) if pf else None,
                "total_findings": ef_run_result.total_findings if ef_run_result else 0,
                "findings_by_dimension": {
                    dim: len(findings)
                    for dim, findings in (ef_run_result.findings_by_dimension if ef_run_result else {}).items()
                },
                "ef_errors": ef_errors or None,
            }}), 201

        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        finally:
            conn.close()

    @app.route("/api/review/interpretations")
    def api_review_interpretations():
        """All canonical interpretations for the Review tab, with observation context."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()
        rows = conn.execute("""
            SELECT i.id, i.observation_id, i.perspective, i.text,
                   i.evidential_status, i.steward_note, i.source, i.created_at,
                   o.raw_text, o.page, o.paragraph
            FROM interpretations i
            JOIN observations o ON o.id = i.observation_id
            JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
            ORDER BY i.created_at DESC
        """).fetchall()
        conn.close()
        return jsonify({
            "count": len(rows),
            "interpretations": [
                {
                    "id": r["id"],
                    "observation_id": r["observation_id"],
                    "perspective": r["perspective"],
                    "text": r["text"],
                    "evidential_status": r["evidential_status"],
                    "steward_note": r["steward_note"],
                    "source": r["source"],
                    "created_at": r["created_at"],
                    "obs_text": r["raw_text"],
                    "obs_page": r["page"],
                    "obs_paragraph": r["paragraph"],
                }
                for r in rows
            ],
        })

    @app.route("/api/review/interpretations/<interpretation_id>", methods=["GET"])
    def api_review_interpretation_get(interpretation_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()
        row = conn.execute(
            """
            SELECT i.id, i.evidential_status, i.steward_note
            FROM interpretations i
            JOIN observations o ON o.id = i.observation_id
            JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE i.id=?
              AND COALESCE(sd.excluded_from_analysis, 0) = 0
            """,
            (interpretation_id,),
        ).fetchone()
        conn.close()
        return jsonify(dict(row)) if row else (jsonify({"error": "not found"}), 404)

    @app.route("/api/review/interpretations/<interpretation_id>", methods=["PATCH"])
    def api_review_interpretation_update(interpretation_id: str):
        """Reject in-place edits to canonical interpretations."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()
        row = conn.execute(
            """
            SELECT i.id
            FROM interpretations i
            JOIN observations o ON o.id = i.observation_id
            JOIN source_documents sd ON sd.id = o.source_document_id
            WHERE i.id=?
              AND COALESCE(sd.excluded_from_analysis, 0) = 0
            """,
            (interpretation_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({
            "error": "canonical interpretations are append-only",
            "detail": (
                "In-place review edits require a ratified append-only "
                "review or supersession model."
            ),
        }), 409

    @app.route("/api/critic/reports")
    def api_critic_reports():
        """List all validation reports for the Critic Explorer."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()
        rows = conn.execute("""
            SELECT vr.id, vr.rendered_narrative_id, vr.semantic_fidelity,
                   vr.required_terms_present, vr.required_terms_missing,
                   vr.unsupported_claims, vr.warnings, vr.approved, vr.created_at,
                   rn.provider, rn.expression_profile_id,
                   ep.slug AS profile_slug, ep.name AS profile_name,
                   nb.title AS blueprint_title
            FROM validation_reports vr
            JOIN rendered_narratives rn ON rn.id = vr.rendered_narrative_id
            LEFT JOIN expression_profiles ep ON ep.id = rn.expression_profile_id
            LEFT JOIN architect_plans ap ON ap.id = rn.architect_plan_id
            LEFT JOIN narrative_blueprints nb ON nb.id = ap.blueprint_id
            ORDER BY vr.created_at DESC
        """).fetchall()
        conn.close()
        return jsonify({
            "count": len(rows),
            "reports": [
                {
                    "id": r["id"],
                    "rendered_narrative_id": r["rendered_narrative_id"],
                    "semantic_fidelity": r["semantic_fidelity"],
                    "approved": bool(r["approved"]),
                    "created_at": r["created_at"],
                    "provider": r["provider"],
                    "profile_slug": r["profile_slug"],
                    "profile_name": r["profile_name"],
                    "blueprint_title": r["blueprint_title"],
                    "terms_present": json.loads(r["required_terms_present"] or "[]"),
                    "terms_missing": json.loads(r["required_terms_missing"] or "[]"),
                    "unsupported_claims": json.loads(r["unsupported_claims"] or "[]"),
                    "warnings": json.loads(r["warnings"] or "[]"),
                }
                for r in rows
            ],
        })

    @app.route("/api/critic/reports/<report_id>")
    def api_critic_report_detail(report_id: str):
        """Full detail for a single validation report including rendered narrative text."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()
        vr = conn.execute(
            "SELECT * FROM validation_reports WHERE id = ?", (report_id,)
        ).fetchone()
        if not vr:
            conn.close()
            return jsonify({"error": "not found"}), 404
        rn = conn.execute(
            "SELECT * FROM rendered_narratives WHERE id = ?", (vr["rendered_narrative_id"],)
        ).fetchone()
        ep = None
        if rn and rn["expression_profile_id"]:
            ep = conn.execute(
                "SELECT slug, name, language FROM expression_profiles WHERE id = ?",
                (rn["expression_profile_id"],),
            ).fetchone()
        nb_title = None
        if rn and rn["architect_plan_id"]:
            ap = conn.execute(
                "SELECT blueprint_id FROM architect_plans WHERE id = ?", (rn["architect_plan_id"],)
            ).fetchone()
            if ap:
                nb = conn.execute(
                    "SELECT title FROM narrative_blueprints WHERE id = ?", (ap["blueprint_id"],)
                ).fetchone()
                if nb:
                    nb_title = nb["title"]
        conn.close()
        return jsonify({
            "id": vr["id"],
            "rendered_narrative_id": vr["rendered_narrative_id"],
            "narrative_text": rn["text"] if rn else None,
            "provider": rn["provider"] if rn else None,
            "profile_slug": ep["slug"] if ep else None,
            "profile_name": ep["name"] if ep else None,
            "blueprint_title": nb_title,
            "semantic_fidelity": vr["semantic_fidelity"],
            "approved": bool(vr["approved"]),
            "created_at": vr["created_at"],
            "terms_present": json.loads(vr["required_terms_present"] or "[]"),
            "terms_missing": json.loads(vr["required_terms_missing"] or "[]"),
            "unsupported_claims": json.loads(vr["unsupported_claims"] or "[]"),
            "warnings": json.loads(vr["warnings"] or "[]"),
        })

    # ── Close Reading Workspace ───────────────────────────────────────────────

    @app.route("/api/reader/documents")
    def api_reader_documents():
        """List source documents with their reading progress."""
        if not db_path.exists():
            return jsonify({"documents": []}), 200
        conn = _conn_rw()
        docs = conn.execute(
            """SELECT sd.id, sd.original_filename, sd.source_role, sd.total_pages,
                      sd.excluded_from_analysis,
                      rp.last_page, rp.percent_read, rp.pages_read, rp.completed_at
               FROM source_documents sd
               LEFT JOIN reading_progress rp ON rp.document_id = sd.id
               WHERE sd.excluded_from_analysis = 0
               ORDER BY sd.source_role = 'primary' DESC, sd.original_filename"""
        ).fetchall()
        result = []
        for d in docs:
            result.append({
                "id": d["id"],
                "filename": d["original_filename"],
                "source_role": d["source_role"] or "primary",
                "total_pages": d["total_pages"] or 1,
                "excluded": bool(d["excluded_from_analysis"]),
                "last_page": d["last_page"] or 1,
                "percent_read": d["percent_read"] or 0.0,
                "pages_read": json.loads(d["pages_read"] or "[]"),
                "completed_at": d["completed_at"],
            })
        conn.close()
        return jsonify({"documents": result})

    @app.route("/api/reader/documents/<doc_id>/pages")
    def api_reader_document_pages(doc_id: str):
        """Return extracted text pages for a document, grouped by page number."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn_rw()
        try:
            doc = require_active_document(conn, doc_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        extractions = conn.execute(
            """SELECT id, page, region, raw_text, source_locator
               FROM source_extractions
               WHERE document_id = ?
               ORDER BY page,
                        CASE
                          WHEN region GLOB 'block:[0-9]*'
                          THEN CAST(substr(region, 7) AS INTEGER)
                          ELSE 2147483647
                        END,
                        source_locator""",
            (doc_id,)
        ).fetchall()

        # Group canonical extractions by page, then build disposable Reader
        # projections per page. The projection never mutates the stored
        # evidence — it only assembles display blocks (e.g. PDF drop-cap
        # repair) that carry their contributing extraction IDs.
        raw_by_page: dict[int, list] = {}
        for ex in extractions:
            pg = ex["page"] or 1
            raw_by_page.setdefault(pg, []).append(dict(ex))
        pages: dict[int, dict[str, object]] = {
            pg: project_reader_page(rows)
            for pg, rows in raw_by_page.items()
        }

        # Fetch highlights for this doc
        highlights = conn.execute(
            "SELECT id, page, source_locator, selected_text, note_text, question_text, relevance, status, created_at "
            "FROM reader_highlights WHERE source_document_id = ? AND status != 'dismissed' "
            "ORDER BY page, created_at",
            (doc_id,)
        ).fetchall()
        highlights_by_page: dict[int, list] = {}
        for h in highlights:
            pg = h["page"] or 0
            highlights_by_page.setdefault(pg, []).append(dict(h))

        conn.close()
        return jsonify({
            "document": {
                "id": doc["id"],
                "filename": doc["original_filename"],
                "source_role": doc["source_role"] or "primary",
                "total_pages": doc["total_pages"] or 1,
                "excluded": bool(doc["excluded_from_analysis"]),
            },
            "pages": [
                {
                    "page": pg,
                    "extractions": page["extractions"],
                    "projection_coverage": page["projection_coverage"],
                    "highlights": highlights_by_page.get(pg, []),
                }
                for pg, page in sorted(pages.items())
            ],
            "total_pages": doc["total_pages"] or 1,
        })

    @app.route("/api/reader/highlights", methods=["POST"])
    def api_reader_save_highlight():
        """Save a human highlight from the Close Reading workspace."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(force=True) or {}
        doc_id = str(payload.get("source_document_id") or "").strip()
        selected_text = str(payload.get("selected_text") or "").strip()
        if not doc_id or not selected_text:
            return jsonify({"error": "source_document_id and selected_text required"}), 400

        conn = _conn_rw()
        try:
            doc = require_active_document(conn, doc_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)

        import uuid
        highlight_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        relevance = str(payload.get("relevance") or "unclear").strip()
        valid_relevance = {"supports", "complicates", "contradicts", "background", "unclear"}
        if relevance not in valid_relevance:
            relevance = "unclear"

        # Issue #35 substrate: rank (1-5 or None), theme_bucket, evidence_bucket.
        rank, rank_err = _coerce_rank(payload.get("rank"))
        if rank_err:
            conn.close()
            return jsonify({"error": rank_err}), 400
        theme_bucket = _coerce_optional_text(payload.get("theme_bucket"))
        evidence_bucket = _coerce_optional_text(payload.get("evidence_bucket"))

        conn.execute(
            """INSERT INTO reader_highlights
               (id, source_document_id, source_role, page, source_locator,
                selected_text, context_before, context_after,
                note_text, question_text, question_type, relevance, tags,
                status, rank, theme_bucket, evidence_bucket, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                highlight_id,
                doc_id,
                doc["source_role"] or "primary",
                payload.get("page"),
                payload.get("source_locator"),
                selected_text,
                payload.get("context_before"),
                payload.get("context_after"),
                payload.get("note_text"),
                payload.get("question_text"),
                payload.get("question_type") or "unclassified",
                relevance,
                json.dumps(payload.get("tags") or []),
                "saved_highlight",
                rank,
                theme_bucket,
                evidence_bucket,
                now,
                now,
            )
        )
        conn.commit()
        conn.close()
        return jsonify({"id": highlight_id, "status": "saved_highlight"}), 201

    @app.route("/api/reader/highlights/<highlight_id>", methods=["PATCH"])
    def api_reader_update_highlight(highlight_id: str):
        """Update note, question, relevance, status, or tags on a highlight."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(force=True) or {}
        conn = _conn_rw()
        row = conn.execute(
            "SELECT id, source_document_id FROM reader_highlights WHERE id = ?",
            (highlight_id,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "not found"}), 404
        try:
            require_active_document(conn, row["source_document_id"])
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)

        allowed = {"note_text", "question_text", "question_type", "relevance", "tags",
                   "status", "page", "source_locator",
                   "rank", "theme_bucket", "evidence_bucket"}
        valid_status = {"saved_highlight", "observation_candidate", "promoted_to_observation", "dismissed"}
        valid_relevance = {"supports", "complicates", "contradicts", "background", "unclear"}
        sets, vals = [], []
        for key, val in payload.items():
            if key not in allowed:
                continue
            if key == "status" and val not in valid_status:
                continue
            if key == "relevance" and val not in valid_relevance:
                continue
            if key == "rank":
                val, rank_err = _coerce_rank(val)
                if rank_err:
                    conn.close()
                    return jsonify({"error": rank_err}), 400
            if key in ("theme_bucket", "evidence_bucket"):
                val = _coerce_optional_text(val)
            if key == "tags":
                val = json.dumps(val if isinstance(val, list) else [])
            sets.append(f"{key} = ?")
            vals.append(val)

        if sets:
            sets.append("updated_at = ?")
            vals.append(datetime.now(timezone.utc).isoformat())
            vals.append(highlight_id)
            conn.execute(f"UPDATE reader_highlights SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/reader/highlights/<highlight_id>", methods=["DELETE"])
    def api_reader_delete_highlight(highlight_id: str):
        """Dismiss (soft-delete) a highlight."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn_rw()
        row = conn.execute(
            "SELECT id, source_document_id FROM reader_highlights WHERE id = ?",
            (highlight_id,),
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "not found"}), 404
        try:
            require_active_document(conn, row["source_document_id"])
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE reader_highlights SET status = 'dismissed', updated_at = ? WHERE id = ?",
            (now, highlight_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/study/compile")
    def api_study_compile():
        """Compile study records and an LLM-ready synthesis packet.

        Deterministic and provider-free. Optional ``?document_id=`` scopes to
        one active document; otherwise compilation spans all active documents.
        The Issue #35 summary keys remain at the response root for compatibility.
        """
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        doc_id = str(request.args.get("document_id") or "").strip()
        conn = _conn()
        if doc_id:
            try:
                require_active_document(conn, doc_id)
            except _ScopeAccessError as exc:
                conn.close()
                return _scope_error_response(exc)
            rows = conn.execute(
                "SELECT * FROM reader_highlights WHERE source_document_id = ? "
                "ORDER BY page, created_at, id",
                (doc_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT rh.* FROM reader_highlights rh
                   JOIN source_documents sd ON sd.id = rh.source_document_id
                   WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
                   ORDER BY rh.page, rh.created_at, rh.id"""
            ).fetchall()
        annotations = []
        for r in rows:
            d = dict(r)
            d["tags"] = _json_list(d.get("tags"))
            annotations.append(d)

        if doc_id:
            documents = conn.execute(
                """SELECT id, original_filename AS filename, file_hash,
                          source_role, total_pages
                   FROM source_documents WHERE id = ?""",
                (doc_id,),
            ).fetchall()
            field_notes = conn.execute(
                """SELECT il.*, sd.original_filename
                   FROM investigation_log il
                   LEFT JOIN source_documents sd ON sd.id = il.source_document_id
                   WHERE il.source_document_id = ?
                   ORDER BY il.created_at, il.id""",
                (doc_id,),
            ).fetchall()
            reading_progress = conn.execute(
                """SELECT document_id, pages_read, last_page, completed_at, updated_at
                   FROM reading_progress WHERE document_id = ?""",
                (doc_id,),
            ).fetchall()
        else:
            documents = conn.execute(
                """SELECT id, original_filename AS filename, file_hash,
                          source_role, total_pages
                   FROM source_documents
                   WHERE COALESCE(excluded_from_analysis, 0) = 0
                   ORDER BY original_filename, id"""
            ).fetchall()
            field_notes = conn.execute(
                """SELECT il.*, sd.original_filename
                   FROM investigation_log il
                   LEFT JOIN source_documents sd ON sd.id = il.source_document_id
                   WHERE il.source_document_id IS NULL
                      OR COALESCE(sd.excluded_from_analysis, 0) = 0
                   ORDER BY il.created_at, il.id"""
            ).fetchall()
            reading_progress = conn.execute(
                """SELECT rp.document_id, rp.pages_read, rp.last_page,
                          rp.completed_at, rp.updated_at
                   FROM reading_progress rp
                   JOIN source_documents sd ON sd.id = rp.document_id
                   WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
                   ORDER BY rp.document_id"""
            ).fetchall()
        # The durable governing question (issue #71) is the source of truth for
        # the packet's compass; field-note snapshots remain a fallback.
        try:
            inv_row = conn.execute(
                "SELECT thesis FROM workspace_investigation WHERE id = 'current'"
            ).fetchone()
        except sqlite3.OperationalError:
            inv_row = None
        governing = inv_row["thesis"] if inv_row and inv_row["thesis"] else None
        conn.close()

        summary = compile_study(annotations)
        summary["synthesis_packet"] = compile_synthesis_packet(
            annotations,
            documents=[dict(document) for document in documents],
            field_notes=[dict(note) for note in field_notes],
            reading_progress=[dict(progress) for progress in reading_progress],
            compiled_at=datetime.now(timezone.utc).isoformat(),
            scope_document_id=doc_id or None,
            governing_question=governing,
        )
        return jsonify(summary)

    # ── Attention timeline (PR 3) ─────────────────────────────────────────────
    # "What have I discovered so far?" — a chronological feed of the steward's
    # captured attention (highlights, notes, questions, field notes) across the
    # corpus. Read-only aggregation; excludes dismissed highlights and muted
    # documents. Human attention only — machine observations are kept separate.
    @app.route("/api/reader/timeline")
    def api_reader_timeline():
        if not db_path.exists():
            return jsonify({"entries": [], "count": 0}), 200
        conn = _conn()
        entries: list[dict] = []
        highlights = conn.execute(
            """SELECT rh.id, rh.selected_text, rh.note_text, rh.question_text,
                      rh.rank, rh.theme_bucket, rh.page, rh.source_locator,
                      rh.source_document_id, sd.original_filename, rh.created_at
               FROM reader_highlights rh
               LEFT JOIN source_documents sd ON sd.id = rh.source_document_id
               WHERE rh.status != 'dismissed'
                 AND COALESCE(sd.excluded_from_analysis, 0) = 0
               ORDER BY rh.created_at DESC"""
        ).fetchall()
        for r in highlights:
            if (r["question_text"] or "").strip():
                kind = "question"
            elif (r["note_text"] or "").strip():
                kind = "note"
            else:
                kind = "highlight"
            entries.append({
                "kind": kind,
                "id": r["id"],
                "selected_text": r["selected_text"],
                "note_text": r["note_text"],
                "question_text": r["question_text"],
                "rank": r["rank"],
                "theme_bucket": r["theme_bucket"],
                "document_id": r["source_document_id"],
                "document_name": r["original_filename"],
                "page": r["page"],
                **_reader_source_locator_fields(r["source_locator"]),
                "created_at": r["created_at"],
            })
        field_notes = conn.execute(
            """SELECT il.id, il.understanding, il.pressing_questions, il.page,
                      il.source_document_id, sd.original_filename, il.created_at
               FROM investigation_log il
               LEFT JOIN source_documents sd ON sd.id = il.source_document_id
               WHERE il.source_document_id IS NULL
                  OR COALESCE(sd.excluded_from_analysis, 0) = 0
               ORDER BY il.created_at DESC"""
        ).fetchall()
        for r in field_notes:
            entries.append({
                "kind": "field_note",
                "id": r["id"],
                "understanding": r["understanding"],
                "pressing_questions": r["pressing_questions"],
                "document_id": r["source_document_id"],
                "document_name": r["original_filename"],
                "page": r["page"],
                "created_at": r["created_at"],
            })
        conn.close()
        entries.sort(key=lambda e: str(e.get("created_at") or ""), reverse=True)
        return jsonify({"entries": entries, "count": len(entries)})

    @app.route("/api/reader/documents/<doc_id>/highlights")
    def api_reader_document_highlights(doc_id: str):
        """All non-dismissed highlights for a document."""
        if not db_path.exists():
            return jsonify({"highlights": []}), 200
        conn = _conn_rw()
        try:
            require_active_document(conn, doc_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        rows = conn.execute(
            """SELECT * FROM reader_highlights
               WHERE source_document_id = ? AND status != 'dismissed'
               ORDER BY page, created_at""",
            (doc_id,)
        ).fetchall()
        conn.close()
        result = []
        for h in rows:
            d = dict(h)
            d["tags"] = _json_list(d.get("tags"))
            result.append(d)
        return jsonify({"highlights": result})

    @app.route("/api/reader/progress", methods=["POST"])
    def api_reader_update_progress():
        """Upsert reading progress for a document."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(force=True) or {}
        doc_id = str(payload.get("document_id") or "").strip()
        page = int(payload.get("page") or 1)
        if not doc_id:
            return jsonify({"error": "document_id required"}), 400

        conn = _conn_rw()
        try:
            doc = require_active_document(conn, doc_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)

        total_pages = max(int(doc["total_pages"] or 1), 1)
        import uuid as _uuid

        existing = conn.execute(
            "SELECT id, pages_read FROM reading_progress WHERE document_id = ?", (doc_id,)
        ).fetchone()

        now = datetime.now(timezone.utc).isoformat()
        if existing:
            pages_read: list = json.loads(existing["pages_read"] or "[]")
            if page not in pages_read:
                pages_read.append(page)
            percent = round(len(pages_read) / total_pages * 100, 1)
            completed_at = now if percent >= 100 else None
            conn.execute(
                """UPDATE reading_progress
                   SET pages_read = ?, last_page = ?, percent_read = ?,
                       completed_at = COALESCE(completed_at, ?), updated_at = ?
                   WHERE document_id = ?""",
                (json.dumps(pages_read), page, percent, completed_at, now, doc_id)
            )
        else:
            pages_read = [page]
            percent = round(1 / total_pages * 100, 1)
            conn.execute(
                """INSERT INTO reading_progress
                   (id, document_id, pages_read, last_page, total_pages, percent_read, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (_uuid.uuid4().hex, doc_id, json.dumps(pages_read), page, total_pages, percent, now)
            )

        conn.commit()
        conn.close()
        return jsonify({"ok": True, "pages_read": len(pages_read), "percent_read": percent})

    @app.route("/api/reader/highlights/<highlight_id>/promote", methods=["POST"])
    def api_reader_promote_highlight(highlight_id: str):
        """Promote a highlight to observation_candidate status (does not create an Observation)."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn_rw()
        row = conn.execute(
            "SELECT * FROM reader_highlights WHERE id = ?", (highlight_id,)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "not found"}), 404
        try:
            require_active_document(conn, row["source_document_id"])
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE reader_highlights SET status = 'observation_candidate', updated_at = ? WHERE id = ?",
            (now, highlight_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": "observation_candidate"})

    # ── Companion (issue #10) ─────────────────────────────────────────
    # A reading participant, not an authority. Context is explicit: only
    # the sections the reader checked are gathered and sent — never
    # silently expanded — and every reply reports exactly what was used.
    _COMPANION_SYSTEM = (
        "You are the Hermeneia Companion — a reading participant beside a human "
        "investigator, not an authority over them. Ground your reply ONLY in the "
        "context sections provided below. If the provided context is insufficient "
        "to answer well, say precisely what is missing rather than inventing. "
        "You may propose interpretations, distinctions, questions, and connections; "
        "you never decide — the reader is the steward, and nothing you say enters "
        "the investigation record unless the reader chooses to save it. Be concise. "
        "When natural, end with one question worth investigating next."
    )

    @app.route("/api/companion/ask", methods=["POST"])
    def api_companion_ask():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400

        raw_provider = str(payload.get("provider") or "").strip()
        if raw_provider.lower() == "stub":
            participant_key, participant_label, provider_id = "stub", "Stub (no AI)", "null"
            model_id = None
        else:
            participant = _e10_participant(raw_provider)
            if participant is None:
                return jsonify({"error": f"unsupported provider: {raw_provider}"}), 400
            participant_key, participant_label, model_id = participant
            provider_id = _E10_PARTICIPANTS[participant_key][1]
            model_id, _ = _selected_model_for_provider(provider_id, model_id)

        try:
            adapter = active_provider_registry.create(
                provider_id,
                **_provider_kwargs(provider_id),
            )
        except Exception as exc:
            return jsonify({"error": f"provider unavailable: {exc}"}), 502

        flags = payload.get("context_flags") or {}
        doc_id = str(payload.get("document_id") or "").strip()
        page = payload.get("page")
        sections: list[tuple[str, str]] = []
        context_used: list[dict] = []

        def _use(key: str, summary: str, body: str) -> None:
            sections.append((key, body))
            context_used.append({"key": key, "summary": summary})

        if flags.get("governing_question"):
            q = str(payload.get("governing_question_text") or "").strip()
            if q:
                _use("governing_question", "the governing question",
                     f"GOVERNING QUESTION (the investigation's compass — inform it, "
                     f"do not merely validate it):\n{q}")
            else:
                context_used.append({"key": "governing_question",
                                     "summary": "requested, but none is set"})

        if flags.get("selected_passage"):
            sel = str(payload.get("selected_text") or "").strip()
            if sel:
                _use("selected_passage", f"selected passage ({len(sel)} chars)",
                     f"SELECTED PASSAGE (the reader is asking about this):\n\"{sel}\"")
            else:
                context_used.append({"key": "selected_passage",
                                     "summary": "requested, but nothing is selected"})

        conn = _conn()
        try:
            if flags.get("current_page") and doc_id and page:
                rows = conn.execute(
                    """SELECT se.raw_text FROM source_extractions se
                       JOIN source_documents sd ON sd.id = se.document_id
                       WHERE se.document_id = ? AND se.page = ?
                         AND COALESCE(sd.excluded_from_analysis, 0) = 0
                       ORDER BY se.id""",
                    (doc_id, int(page)),
                ).fetchall()
                page_text = "\n".join(r["raw_text"] for r in rows)[:6000]
                if page_text:
                    _use("current_page", f"page {page} text",
                         f"CURRENT PAGE (p.{page}):\n{page_text}")
                else:
                    context_used.append({"key": "current_page",
                                         "summary": f"requested, but page {page} has no text"})

            if flags.get("saved_highlights") and doc_id:
                rows = conn.execute(
                    """SELECT selected_text, note_text, question_text, page
                       FROM reader_highlights
                       WHERE source_document_id = ? AND status != 'dismissed'
                       ORDER BY page, created_at LIMIT 20""",
                    (doc_id,),
                ).fetchall()
                if rows:
                    body = "\n".join(
                        f"- p.{r['page']}: \"{r['selected_text'][:160]}\""
                        + (f" — note: {r['note_text'][:160]}" if r["note_text"] else "")
                        + (f" — question: {r['question_text'][:160]}" if r["question_text"] else "")
                        for r in rows
                    )
                    _use("saved_highlights", f"{len(rows)} saved highlights",
                         f"THE READER'S SAVED HIGHLIGHTS:\n{body}")
                else:
                    context_used.append({"key": "saved_highlights",
                                         "summary": "requested, but none saved yet"})

            if flags.get("reading_trail") and doc_id:
                prog = conn.execute(
                    "SELECT pages_read FROM reading_progress WHERE document_id = ?",
                    (doc_id,),
                ).fetchone()
                counts = conn.execute(
                    """SELECT COUNT(*) AS n,
                              SUM(CASE WHEN question_text IS NOT NULL AND question_text != '' THEN 1 ELSE 0 END) AS q,
                              SUM(CASE WHEN note_text IS NOT NULL AND note_text != '' THEN 1 ELSE 0 END) AS notes
                       FROM reader_highlights
                       WHERE source_document_id = ? AND status != 'dismissed'""",
                    (doc_id,),
                ).fetchone()
                pages_read = 0
                if prog and prog["pages_read"]:
                    try:
                        pages_read = len(json.loads(prog["pages_read"]))
                    except Exception:
                        pages_read = 0
                _use("reading_trail", "reading trail summary",
                     f"READING TRAIL: {pages_read} pages read; {counts['n'] or 0} highlights, "
                     f"{counts['q'] or 0} questions, {counts['notes'] or 0} notes so far.")

            if flags.get("page_observations") and doc_id and page:
                rows = conn.execute(
                    """SELECT o.raw_text FROM observations o
                       JOIN source_documents sd ON sd.id = o.source_document_id
                       WHERE o.source_document_id = ? AND o.page = ?
                         AND COALESCE(sd.excluded_from_analysis, 0) = 0
                       ORDER BY o.paragraph, o.sentence LIMIT 20""",
                    (doc_id, int(page)),
                ).fetchall()
                if rows:
                    body = "\n".join(f"- \"{r['raw_text'][:200]}\"" for r in rows)
                    _use("page_observations",
                         f"{len(rows)} machine observations from p.{page}",
                         f"MACHINE OBSERVATIONS FOR PAGE {page}:\n{body}")
                else:
                    context_used.append({"key": "page_observations",
                                         "summary": f"requested, but p.{page} has none"})
        finally:
            conn.close()

        user_prompt = "\n\n".join(body for _, body in sections)
        user_prompt = (user_prompt + "\n\n" if user_prompt else "") + f"READER'S MESSAGE:\n{message}"

        try:
            reply = _call_provider(adapter, _COMPANION_SYSTEM, user_prompt)
        except Exception as exc:
            return jsonify({"error": f"provider call failed: {exc}"}), 502

        return jsonify({
            "reply": reply,
            "provider": participant_label,
            "model": model_id,
            "context_used": context_used,
        })

    # ── Investigation Log / Field Notes (issue #18) ───────────────────
    # Append-only snapshots of the investigator's evolving understanding.
    # Two lanes: 'corpus' (learning about the text) and 'instrument'
    # (learning about Hermeneia while using it). These are the raw
    # material of U(n) — captured live, never rewritten.
    @app.route("/api/investigation-log", methods=["POST"])
    def api_investigation_log_create():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        lane = str(payload.get("lane") or "corpus").strip().lower()
        if lane not in ("corpus", "instrument"):
            return jsonify({"error": "lane must be 'corpus' or 'instrument'"}), 400
        understanding = str(payload.get("understanding") or "").strip()
        pressing = str(payload.get("pressing_questions") or "").strip()
        if not understanding and not pressing:
            return jsonify({"error": "an entry needs an understanding, pressing questions, or both"}), 400

        import uuid
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = _conn_rw()
        doc_id = str(payload.get("source_document_id") or "").strip() or None
        if doc_id:
            row = conn.execute(
                "SELECT id FROM source_documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if not row:
                doc_id = None
        conn.execute(
            """INSERT INTO investigation_log
               (id, lane, understanding, pressing_questions,
                source_document_id, page, governing_question, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (entry_id, lane, understanding or None, pressing or None,
             doc_id, payload.get("page"),
             str(payload.get("governing_question") or "").strip() or None, now),
        )
        conn.commit()
        conn.close()
        return jsonify({"id": entry_id, "created_at": now}), 201

    # ── Governing question (issue #71) ────────────────────────────────────────
    # The interpretive root of the workspace. Durable, DB-backed, single mutable
    # record; the browser keeps only a cache. This is what the Workspace Bundle
    # (#70) serializes as investigation.json.

    @app.route("/api/investigation", methods=["GET"])
    def api_investigation_get():
        if not db_path.exists():
            return jsonify({"investigation": None}), 200
        conn = _conn_rw()
        try:
            row = conn.execute(
                "SELECT thesis, purpose, lenses, reconsider, created_at, updated_at "
                "FROM workspace_investigation WHERE id = 'current'"
            ).fetchone()
        except sqlite3.OperationalError:
            row = None  # pre-migration DB; treated as no record
        conn.close()
        if not row:
            return jsonify({"investigation": None}), 200
        return jsonify({"investigation": {
            "thesis": row["thesis"],
            "purpose": row["purpose"],
            "lenses": _json_list(row["lenses"]),
            "reconsider": row["reconsider"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }}), 200

    @app.route("/api/investigation", methods=["PUT"])
    def api_investigation_put():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        payload = request.get_json(silent=True) or {}
        thesis = str(payload.get("thesis") or "").strip()
        if not thesis:
            return jsonify({"error": "thesis is required"}), 400
        purpose = str(payload.get("purpose") or "").strip() or None
        reconsider = str(payload.get("reconsider") or "").strip() or None
        lenses = payload.get("lenses")
        lenses_json = json.dumps(lenses if isinstance(lenses, list) else [])
        now = datetime.now(timezone.utc).isoformat()
        conn = _conn_rw()
        # Preserve the original created_at across revisions.
        existing = conn.execute(
            "SELECT created_at FROM workspace_investigation WHERE id = 'current'"
        ).fetchone()
        created_at = (
            existing["created_at"]
            if existing and existing["created_at"]
            else (str(payload.get("created") or "").strip() or now)
        )
        conn.execute(
            """INSERT INTO workspace_investigation
                 (id, thesis, purpose, lenses, reconsider, created_at, updated_at)
               VALUES ('current', ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 thesis=excluded.thesis, purpose=excluded.purpose,
                 lenses=excluded.lenses, reconsider=excluded.reconsider,
                 updated_at=excluded.updated_at""",
            (thesis, purpose, lenses_json, reconsider, created_at, now),
        )
        conn.commit()
        conn.close()
        return jsonify({"investigation": {
            "thesis": thesis,
            "purpose": purpose,
            "lenses": lenses if isinstance(lenses, list) else [],
            "reconsider": reconsider,
            "created_at": created_at,
            "updated_at": now,
        }}), 200

    # ── Export Workspace (issues #70/#76/#79) ────────────────────────────────
    # Download the whole workspace as a portable, deterministic WBS v1 bundle
    # (.zip). Read-only over the DB; the browser receives a self-contained
    # artifact. Storage adapters (server path, Git, folder) come later.
    @app.route("/api/workspace/export")
    def api_workspace_export():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        from ..workspace import build_workspace_zip, ensure_workspace_identity

        # The bundle carries the workspace's durable identity (issue #83), not a
        # corpus fingerprint. Ensure one exists before exporting.
        rw = _conn_rw()
        try:
            identity = ensure_workspace_identity(rw)
        finally:
            rw.close()

        generated_at = datetime.now(timezone.utc).isoformat()
        data = build_workspace_zip(
            db_path, generated_at=generated_at,
            workspace_id=identity["workspace_id"],
        )
        stamp = generated_at[:10]
        response = make_response(data)
        response.headers["Content-Type"] = "application/zip"
        response.headers["Content-Disposition"] = (
            f'attachment; filename="hermeneia-workspace-{stamp}.zip"'
        )
        return response

    # ── Workspace identity (issue #83) ────────────────────────────────────────
    # Who the workspace is, independent of the corpus it contains.
    @app.route("/api/workspace/identity", methods=["GET"])
    def api_workspace_identity_get():
        if not db_path.exists():
            return jsonify({"identity": None}), 200
        from ..workspace import ensure_workspace_identity

        rw = _conn_rw()
        try:
            identity = ensure_workspace_identity(rw)
        finally:
            rw.close()
        return jsonify({"identity": identity}), 200

    @app.route("/api/workspace/identity", methods=["PUT"])
    def api_workspace_identity_put():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        from ..workspace import set_workspace_name

        payload = request.get_json(silent=True) or {}
        rw = _conn_rw()
        try:
            identity = set_workspace_name(rw, payload.get("workspace_name"))
        finally:
            rw.close()
        return jsonify({"identity": identity}), 200

    # ── Import Workspace (issues #70/#76/#81) ─────────────────────────────────
    # Inspect before acting: preview a bundle .zip read-only, then restore only
    # on explicit confirmation. v1 restores into a fresh workspace only; a
    # non-empty target is surfaced, never silently overwritten.
    @app.route("/api/workspace/import/preview", methods=["POST"])
    def api_workspace_import_preview():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        from ..workspace import RestoreError, preview_restore, safe_extract_zip

        file = request.files.get("bundle")
        if file is None:
            return jsonify({"error": "a bundle .zip is required"}), 400
        data = file.read()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = safe_extract_zip(data, td)
                preview = preview_restore(db_path, root)
        except RestoreError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(preview)

    @app.route("/api/workspace/import/restore", methods=["POST"])
    def api_workspace_import_restore():
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        from ..workspace import RestoreError, restore_workspace, safe_extract_zip

        file = request.files.get("bundle")
        if file is None:
            return jsonify({"error": "a bundle .zip is required"}), 400
        data = file.read()
        try:
            with tempfile.TemporaryDirectory() as td:
                root = safe_extract_zip(data, td)
                result = restore_workspace(db_path, root, overwrite=False)
        except RestoreError as exc:
            # A non-empty target is a refusal the user must resolve, not a
            # malformed bundle — 409 Conflict, with the reason surfaced.
            status = 409 if "not empty" in str(exc) else 400
            return jsonify({"error": str(exc)}), status
        return jsonify(result)

    @app.route("/api/investigation-log")
    def api_investigation_log_list():
        if not db_path.exists():
            return jsonify({"entries": []}), 200
        lane = str(request.args.get("lane") or "").strip().lower()
        try:
            limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        except ValueError:
            limit = 50
        conn = _conn()
        if lane in ("corpus", "instrument"):
            rows = conn.execute(
                """SELECT il.*, sd.original_filename
                   FROM investigation_log il
                   LEFT JOIN source_documents sd ON sd.id = il.source_document_id
                   WHERE il.lane = ? ORDER BY il.created_at DESC LIMIT ?""",
                (lane, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT il.*, sd.original_filename
                   FROM investigation_log il
                   LEFT JOIN source_documents sd ON sd.id = il.source_document_id
                   ORDER BY il.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        conn.close()
        return jsonify({"entries": [dict(r) for r in rows]})

    @app.route("/api/reader/documents/<doc_id>/summary")
    def api_reader_document_summary(doc_id: str):
        """Deterministic reading trail summary for one document. No AI. No scoring."""
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404
        conn = _conn()

        try:
            doc = require_active_document(conn, doc_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)

        # Reading progress
        prog = conn.execute(
            "SELECT last_page, percent_read, pages_read, total_pages, completed_at, updated_at "
            "FROM reading_progress WHERE document_id = ?", (doc_id,)
        ).fetchone()
        total_pages = doc["total_pages"] or 1
        try:
            stored_pages = json.loads(prog["pages_read"] or "[]") if prog else []
        except (json.JSONDecodeError, TypeError):
            stored_pages = []
        pages_read_list = sorted({
            int(page)
            for page in stored_pages
            if isinstance(page, (int, float)) and 1 <= int(page) <= total_pages
        })
        percent_read = round(len(pages_read_list) / total_pages * 100, 1)
        stored_last_page = prog["last_page"] if prog else None
        last_page = (
            int(stored_last_page)
            if isinstance(stored_last_page, (int, float))
            and 1 <= int(stored_last_page) <= total_pages
            else (pages_read_list[-1] if pages_read_list else None)
        )
        last_updated = prog["updated_at"] if prog else None
        completed_at = prog["completed_at"] if prog else None

        # Highlights — always fetch active separately; dismissed count via separate query
        active_hl = conn.execute(
            "SELECT * FROM reader_highlights WHERE source_document_id = ? AND status != 'dismissed' "
            "ORDER BY page IS NULL, page, created_at, id",
            (doc_id,)
        ).fetchall()
        dismissed_count = conn.execute(
            "SELECT COUNT(*) FROM reader_highlights WHERE source_document_id = ? AND status = 'dismissed'",
            (doc_id,)
        ).fetchone()[0]

        # Counts by status
        by_status: dict[str, int] = {
            "saved_highlight": 0,
            "observation_candidate": 0,
            "promoted_to_observation": 0,
        }
        for h in active_hl:
            by_status[h["status"]] = by_status.get(h["status"], 0) + 1

        # Counts by relevance
        by_relevance: dict[str, int] = {
            "supports": 0,
            "complicates": 0,
            "contradicts": 0,
            "background": 0,
            "unclear": 0,
        }
        for h in active_hl:
            r = h["relevance"] or "unclear"
            by_relevance[r] = by_relevance.get(r, 0) + 1

        # Counts by source_role
        by_role: dict[str, int] = {}
        for h in active_hl:
            sr = h["source_role"] or "primary"
            by_role[sr] = by_role.get(sr, 0) + 1

        # Question trail
        questions = [
            h for h in active_hl
            if isinstance(h["question_text"], str) and h["question_text"].strip()
        ]
        pages_with_questions: dict[int, int] = {}
        for h in questions:
            if isinstance(h["page"], int) and h["page"] > 0:
                pages_with_questions[h["page"]] = (
                    pages_with_questions.get(h["page"], 0) + 1
                )

        # Notes
        notes = [
            h for h in active_hl
            if isinstance(h["note_text"], str) and h["note_text"].strip()
        ]
        pages_with_notes = sorted({
            h["page"] for h in notes
            if isinstance(h["page"], int) and h["page"] > 0
        })

        # Observation candidates
        candidates = [
            h for h in active_hl if h["status"] == "observation_candidate"
        ]
        previously_promoted = [
            h for h in active_hl if h["status"] == "promoted_to_observation"
        ]

        # Attention clusters — fixed 20-page windows
        window = 20
        clusters: dict[str, dict] = {}
        for h in active_hl:
            pg = h["page"]
            if not isinstance(pg, int) or pg < 1:
                continue
            bucket_start = ((pg - 1) // window) * window + 1
            bucket_end = min(bucket_start + window - 1, total_pages)
            key = f"{bucket_start}–{bucket_end}"
            if key not in clusters:
                clusters[key] = {"start": bucket_start, "end": bucket_end, "highlights": 0, "questions": 0, "pages": set()}
            clusters[key]["highlights"] += 1
            clusters[key]["pages"].add(pg)
            if h["question_text"]:
                clusters[key]["questions"] += 1

        cluster_list = sorted(
            [{"range": k, "start": v["start"], "end": v["end"],
              "highlights": v["highlights"], "questions": v["questions"],
              "page_count": len(v["pages"])}
             for k, v in clusters.items()],
            key=lambda c: c["start"]
        )

        # Top pages by highlight density
        pages_by_hl: dict[int, int] = {}
        for h in active_hl:
            pg = h["page"]
            if isinstance(pg, int) and pg > 0:
                pages_by_hl[pg] = pages_by_hl.get(pg, 0) + 1
        top_pages = sorted(
            pages_by_hl.items(), key=lambda item: (-item[1], item[0])
        )[:5]

        # Machine observation count for comparison — no content exposed
        machine_obs_count = conn.execute(
            "SELECT COUNT(*) FROM observations WHERE source_document_id = ?", (doc_id,)
        ).fetchone()[0]

        # Next unread page
        read_set = set(pages_read_list)
        next_unread = None
        for pg in range(1, total_pages + 1):
            if pg not in read_set:
                next_unread = pg
                break

        # Recent attention records, with a stable ID tie-breaker.
        recent = sorted(
            active_hl,
            key=lambda h: (h["created_at"] or "", h["id"]),
            reverse=True,
        )[:5]
        recent_questions = sorted(
            questions,
            key=lambda h: (h["created_at"] or "", h["id"]),
            reverse=True,
        )[:5]

        conn.close()

        non_primary_hl = [h for h in active_hl if (h["source_role"] or "primary") != "primary"]
        complete = len(pages_read_list) >= total_pages
        top_question_pages = sorted(
            pages_with_questions.items(),
            key=lambda item: (-item[1], item[0]),
        )[:5]

        return jsonify({
            "document": {
                "id": doc["id"],
                "filename": doc["original_filename"],
                "source_role": doc["source_role"] or "primary",
                "is_primary_source": (doc["source_role"] or "primary") == "primary",
                "total_pages": total_pages,
            },
            "reading_progress": {
                "pages_read": len(pages_read_list),
                "total_pages": total_pages,
                "percent_read": percent_read,
                "last_page": last_page,
                "next_unread_page": next_unread,
                "last_updated": last_updated,
                "completed_at": completed_at,
                "complete": complete,
            },
            "continue_reading": {
                "available": next_unread is not None,
                "page": next_unread,
                "label": (
                    f"Continue reading on page {next_unread}"
                    if next_unread is not None
                    else "All pages have been read"
                ),
            },
            "highlight_trail": {
                "total_active": len(active_hl),
                "dismissed_count": dismissed_count,
                "by_status": by_status,
                "by_relevance": by_relevance,
                "by_source_role": by_role,
                "non_primary_count": len(non_primary_hl),
                "unlocated_count": sum(
                    1 for h in active_hl
                    if not isinstance(h["page"], int) or h["page"] < 1
                ),
                "top_pages": [{"page": pg, "count": cnt} for pg, cnt in top_pages],
            },
            "question_trail": {
                "total_questions": len(questions),
                "pages_with_most_questions": [
                    {"page": pg, "count": cnt}
                    for pg, cnt in top_question_pages
                ],
                "recent_questions": [
                    {
                        "id": h["id"],
                        "page": h["page"],
                        "question_text": h["question_text"],
                        "source_role": h["source_role"] or "primary",
                        "is_primary_source": (
                            h["source_role"] or "primary"
                        ) == "primary",
                        "created_at": h["created_at"],
                    }
                    for h in recent_questions
                ],
            },
            "notes": {
                "total_notes": len(notes),
                "pages_with_notes": pages_with_notes,
            },
            "observation_candidates": {
                "count": len(candidates),
                "previously_promoted_count": len(previously_promoted),
                "items": [
                    {"id": h["id"], "page": h["page"], "source_role": h["source_role"] or "primary",
                     "is_primary_source": (h["source_role"] or "primary") == "primary",
                     "status": h["status"],
                     "text_preview": (h["selected_text"] or "")[:120]}
                    for h in candidates
                ],
            },
            "attention_clusters": cluster_list,
            "machine_coverage": {
                "observation_count": machine_obs_count,
                "note": "Machine coverage is separate from human reading progress.",
            },
            "recent_highlights": [
                {"id": h["id"], "page": h["page"], "selected_text": (h["selected_text"] or "")[:160],
                 "note_text": h["note_text"], "question_text": h["question_text"],
                 "relevance": h["relevance"], "status": h["status"],
                 **_reader_source_locator_fields(h["source_locator"]),
                 "source_role": h["source_role"] or "primary",
                 "is_primary_source": (h["source_role"] or "primary") == "primary",
                 "created_at": h["created_at"]}
                for h in recent
            ],
            "empty": len(active_hl) == 0 and len(pages_read_list) == 0,
        })

    @app.route("/api/reader/summary")
    def api_reader_investigation_summary():
        """Whole-investigation reading trail summary across all readable documents."""
        if not db_path.exists():
            return jsonify({
                "reading_progress": {
                    "total_pages": 0,
                    "total_pages_read": 0,
                    "overall_percent_read": 0.0,
                },
                "continue_reading": {
                    "available": False,
                    "document_id": None,
                    "filename": None,
                    "page": None,
                },
                "highlight_trail": {
                    "total_active": 0,
                    "dismissed_count": 0,
                    "by_status": {
                        "saved_highlight": 0,
                        "observation_candidate": 0,
                        "promoted_to_observation": 0,
                    },
                    "by_relevance": {
                        "supports": 0,
                        "complicates": 0,
                        "contradicts": 0,
                        "background": 0,
                        "unclear": 0,
                    },
                    "by_source_role": {},
                    "non_primary_count": 0,
                },
                "question_trail": {
                    "total_questions": 0,
                    "recent_questions": [],
                },
                "notes": {"total_notes": 0},
                "observation_candidates": {
                    "count": 0,
                    "previously_promoted_count": 0,
                },
                "attention_clusters": [],
                "top_pages": [],
                "recent_highlights": [],
                "documents": [],
                "machine_coverage": {
                    "observation_count": 0,
                    "note": "Machine coverage is separate from human reading progress.",
                },
                "empty": True,
            }), 200
        conn = _conn()
        docs = conn.execute(
            "SELECT id, original_filename, source_role, total_pages "
            "FROM source_documents WHERE excluded_from_analysis = 0 "
            "ORDER BY source_role = 'primary' DESC, original_filename, id"
        ).fetchall()

        active_hl = conn.execute(
            """SELECT rh.*, sd.original_filename
               FROM reader_highlights rh
               JOIN source_documents sd ON sd.id = rh.source_document_id
               WHERE sd.excluded_from_analysis = 0
                 AND rh.status != 'dismissed'
               ORDER BY rh.created_at, rh.id"""
        ).fetchall()
        dismissed_count = conn.execute(
            """SELECT COUNT(*)
               FROM reader_highlights rh
               JOIN source_documents sd ON sd.id = rh.source_document_id
               WHERE sd.excluded_from_analysis = 0
                 AND rh.status = 'dismissed'"""
        ).fetchone()[0]

        prog_rows = conn.execute(
            """SELECT rp.document_id, rp.pages_read, rp.last_page,
                      rp.completed_at, rp.updated_at
               FROM reading_progress rp
               JOIN source_documents sd ON sd.id = rp.document_id
               WHERE sd.excluded_from_analysis = 0"""
        ).fetchall()
        progress_by_doc = {r["document_id"]: r for r in prog_rows}

        doc_summaries = []
        for d in docs:
            prog = progress_by_doc.get(d["id"])
            total_doc_pages = max(int(d["total_pages"] or 1), 1)
            try:
                stored_pages = json.loads(prog["pages_read"] or "[]") if prog else []
            except (json.JSONDecodeError, TypeError):
                stored_pages = []
            pages_read = sorted({
                int(page)
                for page in stored_pages
                if isinstance(page, (int, float))
                and 1 <= int(page) <= total_doc_pages
            })
            next_unread = next(
                (
                    page for page in range(1, total_doc_pages + 1)
                    if page not in set(pages_read)
                ),
                None,
            )
            stored_last_page = prog["last_page"] if prog else None
            last_page = (
                int(stored_last_page)
                if isinstance(stored_last_page, (int, float))
                and 1 <= int(stored_last_page) <= total_doc_pages
                else (pages_read[-1] if pages_read else None)
            )
            doc_summaries.append({
                "id": d["id"],
                "filename": d["original_filename"],
                "source_role": d["source_role"] or "primary",
                "is_primary_source": (d["source_role"] or "primary") == "primary",
                "total_pages": total_doc_pages,
                "pages_read": len(pages_read),
                "percent_read": round(
                    len(pages_read) / total_doc_pages * 100, 1
                ),
                "last_page": last_page,
                "next_unread_page": next_unread,
                "last_updated": prog["updated_at"] if prog else None,
                "complete": next_unread is None,
            })

        total_pages = sum(d["total_pages"] for d in doc_summaries)
        total_pages_read = sum(d["pages_read"] for d in doc_summaries)
        overall_pct = round(total_pages_read / total_pages * 100, 1) if total_pages else 0.0

        doc_summary_by_id = {d["id"]: d for d in doc_summaries}
        by_status: dict[str, int] = {
            "saved_highlight": 0,
            "observation_candidate": 0,
            "promoted_to_observation": 0,
        }
        by_relevance: dict[str, int] = {
            "supports": 0,
            "complicates": 0,
            "contradicts": 0,
            "background": 0,
            "unclear": 0,
        }
        by_role: dict[str, int] = {}
        questions = []
        notes = []
        page_counts: dict[tuple[str, int], dict] = {}
        clusters: dict[tuple[str, int], dict] = {}
        for h in active_hl:
            by_status[h["status"]] = by_status.get(h["status"], 0) + 1
            relevance = h["relevance"] or "unclear"
            by_relevance[relevance] = by_relevance.get(relevance, 0) + 1
            source_role = h["source_role"] or "primary"
            by_role[source_role] = by_role.get(source_role, 0) + 1

            has_question = (
                isinstance(h["question_text"], str)
                and bool(h["question_text"].strip())
            )
            if has_question:
                questions.append(h)
            if isinstance(h["note_text"], str) and h["note_text"].strip():
                notes.append(h)

            page = h["page"]
            if not isinstance(page, int) or page < 1:
                continue
            page_key = (h["source_document_id"], page)
            if page_key not in page_counts:
                page_counts[page_key] = {
                    "document_id": h["source_document_id"],
                    "filename": h["original_filename"],
                    "source_role": source_role,
                    "page": page,
                    "highlight_count": 0,
                    "question_count": 0,
                }
            page_counts[page_key]["highlight_count"] += 1
            if has_question:
                page_counts[page_key]["question_count"] += 1

            window_start = ((page - 1) // 20) * 20 + 1
            doc_meta = doc_summary_by_id[h["source_document_id"]]
            window_end = min(window_start + 19, doc_meta["total_pages"])
            cluster_key = (h["source_document_id"], window_start)
            if cluster_key not in clusters:
                clusters[cluster_key] = {
                    "document_id": h["source_document_id"],
                    "filename": h["original_filename"],
                    "source_role": source_role,
                    "start": window_start,
                    "end": window_end,
                    "highlights": 0,
                    "questions": 0,
                    "pages": set(),
                }
            clusters[cluster_key]["highlights"] += 1
            clusters[cluster_key]["pages"].add(page)
            if has_question:
                clusters[cluster_key]["questions"] += 1

        top_pages = sorted(
            page_counts.values(),
            key=lambda item: (
                -item["highlight_count"],
                -item["question_count"],
                item["filename"],
                item["page"],
            ),
        )[:10]
        cluster_list = sorted(
            [
                {
                    key: value
                    for key, value in cluster.items()
                    if key != "pages"
                }
                | {"page_count": len(cluster["pages"])}
                for cluster in clusters.values()
            ],
            key=lambda item: (
                item["filename"],
                item["start"],
                item["document_id"],
            ),
        )
        recent_highlights = sorted(
            active_hl,
            key=lambda h: (h["created_at"] or "", h["id"]),
            reverse=True,
        )[:10]
        recent_questions = sorted(
            questions,
            key=lambda h: (h["created_at"] or "", h["id"]),
            reverse=True,
        )[:10]

        incomplete_docs = [d for d in doc_summaries if not d["complete"]]
        progressed_docs = [d for d in incomplete_docs if d["last_updated"]]
        continue_doc = (
            sorted(
                progressed_docs,
                key=lambda d: (d["last_updated"], d["id"]),
                reverse=True,
            )[0]
            if progressed_docs
            else (incomplete_docs[0] if incomplete_docs else None)
        )

        machine_obs_count = conn.execute(
            """SELECT COUNT(*)
               FROM observations o
               JOIN source_documents sd ON sd.id = o.source_document_id
               WHERE sd.excluded_from_analysis = 0"""
        ).fetchone()[0]
        conn.close()

        return jsonify({
            "reading_progress": {
                "total_pages": total_pages,
                "total_pages_read": total_pages_read,
                "overall_percent_read": overall_pct,
            },
            "continue_reading": {
                "available": continue_doc is not None,
                "document_id": continue_doc["id"] if continue_doc else None,
                "filename": continue_doc["filename"] if continue_doc else None,
                "source_role": (
                    continue_doc["source_role"] if continue_doc else None
                ),
                "page": (
                    continue_doc["next_unread_page"] if continue_doc else None
                ),
            },
            "highlight_trail": {
                "total_active": len(active_hl),
                "dismissed_count": dismissed_count,
                "by_status": by_status,
                "by_relevance": by_relevance,
                "by_source_role": by_role,
                "non_primary_count": sum(
                    count for role, count in by_role.items()
                    if role != "primary"
                ),
            },
            "question_trail": {
                "total_questions": len(questions),
                "recent_questions": [
                    {
                        "id": h["id"],
                        "document_id": h["source_document_id"],
                        "filename": h["original_filename"],
                        "page": h["page"],
                        "question_text": h["question_text"],
                        **_reader_source_locator_fields(h["source_locator"]),
                        "source_role": h["source_role"] or "primary",
                        "is_primary_source": (
                            h["source_role"] or "primary"
                        ) == "primary",
                        "created_at": h["created_at"],
                    }
                    for h in recent_questions
                ],
            },
            "notes": {"total_notes": len(notes)},
            "observation_candidates": {
                "count": by_status["observation_candidate"],
                "previously_promoted_count": by_status["promoted_to_observation"],
            },
            "attention_clusters": cluster_list,
            "top_pages": top_pages,
            "recent_highlights": [
                {
                    "id": h["id"],
                    "document_id": h["source_document_id"],
                    "filename": h["original_filename"],
                    "page": h["page"],
                    "selected_text": (h["selected_text"] or "")[:160],
                    "note_text": h["note_text"],
                    "question_text": h["question_text"],
                    "relevance": h["relevance"],
                    "status": h["status"],
                    **_reader_source_locator_fields(h["source_locator"]),
                    "source_role": h["source_role"] or "primary",
                    "is_primary_source": (
                        h["source_role"] or "primary"
                    ) == "primary",
                    "created_at": h["created_at"],
                }
                for h in recent_highlights
            ],
            "documents": doc_summaries,
            "machine_coverage": {
                "observation_count": machine_obs_count,
                "note": "Machine coverage is separate from human reading progress.",
            },
            "empty": len(active_hl) == 0 and total_pages_read == 0,
        })

    @app.route("/api/reader/documents/<doc_id>/related-observations")
    def api_reader_related_observations(doc_id: str):
        """Find machine observations near a passage (by page) or from this document."""
        if not db_path.exists():
            return jsonify({"observations": []}), 200
        page = request.args.get("page", type=int)
        conn = _conn_rw()
        try:
            require_active_document(conn, doc_id)
        except _ScopeAccessError as exc:
            conn.close()
            return _scope_error_response(exc)
        if page is not None:
            rows = conn.execute(
                """SELECT o.id, o.raw_text, o.page, o.source_locator,
                          sd.original_filename, sd.source_role,
                          orv.review_status
                   FROM observations o
                   JOIN source_documents sd ON sd.id = o.source_document_id
                   LEFT JOIN observation_reviews orv ON orv.observation_id = o.id
                   WHERE o.source_document_id = ? AND ABS(o.page - ?) <= 1
                     AND sd.excluded_from_analysis = 0
                   ORDER BY ABS(o.page - ?), o.paragraph
                   LIMIT 10""",
                (doc_id, page, page)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT o.id, o.raw_text, o.page, o.source_locator,
                          sd.original_filename, sd.source_role,
                          orv.review_status
                   FROM observations o
                   JOIN source_documents sd ON sd.id = o.source_document_id
                   LEFT JOIN observation_reviews orv ON orv.observation_id = o.id
                   WHERE o.source_document_id = ?
                     AND sd.excluded_from_analysis = 0
                   ORDER BY o.page, o.paragraph
                   LIMIT 20""",
                (doc_id,)
            ).fetchall()
        conn.close()
        return jsonify({"observations": [dict(r) for r in rows]})

    return app
