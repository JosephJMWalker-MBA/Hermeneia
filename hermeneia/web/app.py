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

import json
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

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
from ..narrative.provider_registry import ProviderRegistry
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
from ..explorer.interpreter import (
    ExplorerError,
    generate_candidate_interpretation,
    generate_interpretation_from_bucket,
)
from ..explorer.bucketer import BucketingError, generate_candidate_buckets

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    db_path: str | Path = "build/hermeneia.db",
    *,
    provider_registry: ProviderRegistry | None = None,
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
    runtime_provider_keys: dict[str, str] = {}
    runtime_provider_keys_lock = threading.RLock()

    class _LineageError(Exception):
        pass

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

    def _e10_provider_statuses() -> list[dict]:
        ecology = active_provider_registry.ecology()
        providers = {
            provider["id"]: provider
            for provider in ecology.get("providers", [])
        }
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

            with runtime_provider_keys_lock:
                runtime_key_present = bool(runtime_provider_keys.get(provider_id))
            configured = bool(provider.get("configured")) or runtime_key_present
            adapter_available = bool(provider.get("adapter_available"))
            available = configured and adapter_available and provider.get("provider_type") == "artist"
            requires_credential = bool(provider.get("required_environment"))
            if available and not requires_credential:
                message = (
                    "Local SDK is installed. Use Test Connection to verify "
                    "the runtime and selected model."
                )
            elif available:
                message = "Credential is present and the Python adapter is available."
            elif configured:
                message = (
                    "Credential is saved, but the Python adapter is missing. "
                    "Install the provider SDK before testing the configuration."
                )
            else:
                message = "No credential is configured."
            rows.append({
                "participant": key,
                "label": label,
                "provider_id": provider_id,
                "configured": configured,
                "requires_credential": requires_credential,
                "adapter_available": adapter_available,
                "status": "configured" if available else "not_connected",
                "credential_source": provider.get("required_environment"),
                "credential_scope": (
                    "server_session"
                    if runtime_key_present
                    else "environment"
                    if provider.get("configured") and requires_credential
                    else None
                ),
                "default_model": provider.get("default_model") or draft_model,
                "execution_mode": "deterministic_local_draft",
                "message": message,
            })
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
        return [
            r[0]
            for r in conn.execute(
                "SELECT id FROM observations ORDER BY page, paragraph, sentence"
            )
        ]

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
            row = one(
                "SELECT * FROM observations WHERE id = ?",
                (oid,),
                f"Observation missing: {oid}",
            )
            add_node("Observation", row, {
                "source_document_id": row["source_document_id"],
                "source_extraction_id": row["source_extraction_id"],
                "raw_text": row["raw_text"],
                "source_locator": row["source_locator"],
                "semantic_hash": row["semantic_hash"],
                "page": row["page"],
                "paragraph": row["paragraph"],
                "sentence": row["sentence"],
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
            row = one(
                "SELECT * FROM source_documents WHERE id = ?",
                (did,),
                f"SourceDocument missing: {did}",
            )
            add_node("SourceDocument", row, {
                "original_filename": row["original_filename"],
                "file_hash": row["file_hash"],
                "total_pages": row["total_pages"],
                "registered_at": row["registered_at"],
                "compiler_version": row["compiler_version"],
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
        except (_LineageError, sqlite3.Error) as exc:
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
        return send_from_directory(str(STATIC_DIR), "index.html")

    # ── /api/health ──────────────────────────────────────────────────────────

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
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
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
        return jsonify({
            "credential_storage": "server_session_or_environment",
            "stores_api_keys": True,
            "persistent_api_keys": False,
            "live_connection_test": True,
            "providers": _e10_provider_statuses(),
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

        if request.method == "DELETE":
            with runtime_provider_keys_lock:
                runtime_provider_keys.pop(provider_id, None)
            return jsonify({
                "participant": key,
                "configured": False,
                "credential_scope": None,
                "message": f"Session key removed for {label}.",
            })

        payload = request.get_json(silent=True) or {}
        api_key = str(payload.get("api_key", "")).strip()
        if len(api_key) < 8:
            return jsonify({"error": "api_key must contain at least 8 characters"}), 400
        with runtime_provider_keys_lock:
            runtime_provider_keys[provider_id] = api_key
        return jsonify({
            "participant": key,
            "configured": True,
            "credential_scope": "server_session",
            "message": (
                f"Session key saved for {label}. "
                "It will be forgotten when the Hermeneia server stops."
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
        with runtime_provider_keys_lock:
            runtime_key = runtime_provider_keys.get(provider_id)
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
            provider_kwargs: dict[str, object] = {
                "model": provider["default_model"],
            }
            if runtime_key:
                provider_kwargs["api_key"] = runtime_key
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
            "live_connection_test": True,
            "configuration_valid": validation_error is None,
            "message": (
                f"Connection test failed: {validation_error}"
                if validation_error
                else "Connection succeeded. No generation request was sent."
            ),
        })

    @app.route("/api/e10/observations/<observation_id>")
    def api_e10_observation_detail(observation_id: str):
        if not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        conn = _conn()
        rows = conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
        id_to_index = {row["id"]: index + 1 for index, row in enumerate(rows)}
        obs = conn.execute(
            """
            SELECT o.*, sd.original_filename, sd.file_hash, se.raw_text AS extraction_raw_text,
                   se.parser, se.parser_version
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

        payload = request.get_json(silent=True) or {}
        observation_id = str(payload.get("observation_id", "")).strip()
        raw_participants = payload.get("participants") or []
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

        # Build corpus context so the prompt knows primary vs reference role
        _ctx_conn = _conn()
        obs_doc_row = _ctx_conn.execute(
            """SELECT sd.original_filename, sd.source_role
               FROM source_documents sd
               JOIN observations o ON o.source_document_id = sd.id
               WHERE o.id = ?""",
            (observation_id,),
        ).fetchone()
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
                try:
                    _adapter = active_provider_registry.create(_provider_id)
                except Exception:
                    _adapter = active_provider_registry.create("null")
                try:
                    interp_text, prompt_used = generate_candidate_interpretation(
                        observation_text=observation["raw_text"],
                        perspective_label=label,
                        provider=_adapter,
                        corpus_context=corpus_context,
                    )
                except ExplorerError as exc:
                    raise StagingError(f"Explorer failed for participant {key!r}: {exc}") from exc
                proposal = propose_interpretation(
                    observation_id=observation_id,
                    perspective=label,
                    text=interp_text,
                    evidential_status="speculative",
                    generating_model=model,
                    prompt_reference=prompt_used,
                    prompt_reference_type="full_text",
                    conn=store,
                    generation_timestamp=generated_at,
                    parent_object_ids=[observation_id],
                    generation_parameters={
                        "surface": "E10 Interpretation Lab",
                        "participant": key,
                        "mode": "explorer-llm",
                    },
                    evidence_observation_ids=[observation_id],
                )
                proposals.append(proposal)
        except StagingError as exc:
            return jsonify({"error": str(exc)}), 400
        finally:
            store.close()

        conn = _conn()
        enriched = [
            _e10_proposal_payload(
                conn,
                conn.execute(
                    "SELECT * FROM proposed_interpretations WHERE id = ?",
                    (proposal["id"],),
                ).fetchone(),
            )
            for proposal in proposals
        ]
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
            row = conn_ro.execute(
                "SELECT id, raw_text FROM observations WHERE id = ?", (obs_id,)
            ).fetchone()
            if row is None:
                conn_ro.close()
                return jsonify({"error": f"observation not found: {obs_id}"}), 404
            obs_rows.append({"id": row["id"], "raw_text": row["raw_text"]})

        # Corpus context from first observation's source document
        obs_doc_row = conn_ro.execute(
            """SELECT sd.original_filename, sd.source_role
               FROM source_documents sd
               JOIN observations o ON o.source_document_id = sd.id
               WHERE o.id = ?""",
            (raw_obs_ids[0],),
        ).fetchone()
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
        try:
            _bucketing_provider = active_provider_registry.create(participants[0][0])
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
                    try:
                        _adapter = active_provider_registry.create(_provider_id)
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
                        generating_model=model,
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
        except _LineageError:
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
                }

        # Fetch text for referenced interpretations
        interp_texts: dict[str, str] = {}
        for iid in all_interp_ids:
            row = conn.execute(
                "SELECT text, perspective, evidential_status FROM interpretations WHERE id = ?", (iid,)
            ).fetchone()
            if row:
                interp_texts[iid] = {
                    "text": row["text"],
                    "perspective": row["perspective"],
                    "evidential_status": row["evidential_status"],
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
                "SELECT id, raw_text, page FROM observations ORDER BY page, paragraph, sentence"
            ).fetchall()
            id_to_n = {r["id"]: i + 1 for i, r in enumerate(all_obs)}
            n_to_id = {i + 1: r["id"] for i, r in enumerate(all_obs)}

            # ── Accepted interpretations ───────────────────────────────────
            interps = conn.execute(
                """SELECT i.id, i.observation_id, i.text, i.evidential_status
                   FROM interpretations i
                   WHERE i.evidential_status IN ('established','accepted','speculative')
                   ORDER BY i.created_at"""
            ).fetchall()

            interp_lines = []
            for i in interps:
                n = id_to_n.get(i["id"]) or id_to_n.get(i["observation_id"], "?")
                obs_n = id_to_n.get(i["observation_id"], "?")
                interp_lines.append(
                    f"INTERP-{i['id'][:8]} [OBS-{obs_n}] [{i['evidential_status']}]: {i['text']}"
                )

            # ── Sample observations (spread across corpus) ─────────────────
            step = max(1, len(all_obs) // 40)
            sample_obs = all_obs[::step][:40]
            obs_lines = []
            for r in sample_obs:
                obs_lines.append(f"OBS-{id_to_n[r['id']]} (p.{r['page']}): {r['raw_text'][:200]}")

            # ── Build prompt ───────────────────────────────────────────────
            prompt = f"""You are the Hermeneia Architect. Your job is evidence-first research design, not thesis generation.

RESEARCH DIRECTIVE:
{directive}

CRITICAL INSTRUCTION — READ BEFORE PROCEEDING:
Do NOT start from a thesis and find supporting evidence.
Start from the evidence and let the structure emerge.

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

            with runtime_provider_keys_lock:
                runtime_key = runtime_provider_keys.get(provider)
            provider_kwargs: dict = {}
            if runtime_key:
                provider_kwargs["api_key"] = runtime_key
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
            all_obs = conn.execute(
                "SELECT id FROM observations ORDER BY page, paragraph, sentence"
            ).fetchall()
            n_to_id = {i + 1: r[0] for i, r in enumerate(all_obs)}

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

    # ── /api/upload ────────────────────────────────────────────────────────────

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        """Accept a PDF upload, compile it into the corpus, return observation counts.

        Multipart form-data with field name 'file'.
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
                "label": "Read",
                "description": "Generate the report with an AI provider",
                "count": counts["narratives"],
                "surface": "/api/reader/narratives",
                "nav_target": "reader",
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
        model    = payload.get("model") or None
        save     = bool(payload.get("save", False))
        api_key  = payload.get("api_key") or None

        if not text:
            return jsonify({"error": "text is required"}), 400

        if save and not db_path.exists():
            return jsonify({"error": "database not found"}), 404

        from ..compiler.blueprint_extractor import extract_blueprint_from_text, BlueprintExtractionError
        from ..narrative.artist_providers import get_provider
        import traceback as _tb

        try:
            with runtime_provider_keys_lock:
                runtime_key = runtime_provider_keys.get(provider)
            kwargs: dict = {}
            if model:
                kwargs["model"] = model
            if api_key or runtime_key:
                kwargs["api_key"] = api_key or runtime_key
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
            with runtime_provider_keys_lock:
                runtime_key = runtime_provider_keys.get(provider)
            provider_kwargs: dict = {}
            if runtime_key:
                provider_kwargs["api_key"] = runtime_key
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
        model    = payload.get("model") or None

        if not plan_id:
            return jsonify({"error": "plan_id is required"}), 400

        from ..narrative.artist_service import ArtistRenderError, render_for_plan
        from ..narrative.profiles import list_profiles
        import traceback as _tb

        conn = _conn_rw()
        try:
            with runtime_provider_keys_lock:
                runtime_key = runtime_provider_keys.get(provider)
            provider_kwargs: dict = {}
            if runtime_key:
                provider_kwargs["api_key"] = runtime_key
            if model:
                provider_kwargs["model"] = model

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
                all_ids = [r[0] for r in conn.execute(
                    "SELECT id FROM observations ORDER BY page, paragraph, sentence"
                ).fetchall()]
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
            "SELECT id, evidential_status, steward_note FROM interpretations WHERE id=?",
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
            "SELECT id FROM interpretations WHERE id=?",
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

    return app
