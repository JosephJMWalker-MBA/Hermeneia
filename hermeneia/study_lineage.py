"""Read-only study history projected from existing durable records.

No persistence, provider calls, inferred events, or schema initialization belong
here. A typed source key remains the identity; an event is only a view of it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

SCHEMA = "hermeneia.study-lineage/v1"

# table: (record type, title, historical time field, content field)
_SPECS = {
    "source_documents": ("source_document", "Source registered", "registered_at", "original_filename"),
    "source_extractions": ("source_extraction", "Source extraction", "extracted_at", "raw_text"),
    "observations": ("canonical_observation", "Canonical Observation", "created_at", "raw_text"),
    "reader_highlights": ("reader_highlight", "Reader mark — current snapshot", "updated_at", "selected_text"),
    "inquiry_notes": ("inquiry_note", "Inquiry question", "created_at", "question_text"),
    "observation_reviews": ("observation_review", "Observation review — current snapshot", "updated_at", "steward_note"),
    "workspace_investigation": ("workspace_investigation", "Governing question — current snapshot", "updated_at", "thesis"),
    "investigation_log": ("field_note", "Corpus Field Note", "created_at", "understanding"),
    "perspectives": ("perspective", "Saved Perspective", "created_at", "name"),
    "proposed_interpretations": ("proposed_interpretation", "Model interpretation proposal", "created_at", "text"),
    "interpretations": ("interpretation", "Canonical Interpretation", "created_at", "text"),
    "narrative_blueprints": ("blueprint", "Saved Blueprint", "created_at", "thesis"),
    "supersession_relations": ("supersession", "Recorded supersession", "ratified_at", "reason"),
    "architect_plans": ("architect_plan", "Architect Plan", "created_at", "title"),
    "rendered_narratives": ("rendered_narrative", "Rendered narrative", "created_at", "text"),
    "critic_reports": ("critic_report", "Interpretation Critic report", "generated_at", "overall_verdict"),
    "validation_reports": ("validation_report", "Narrative Critic report", "created_at", None),
    "findings": ("finding", "Evaluation finding", "created_at", "status"),
    "steward_decisions": ("steward_decision", "Steward decision", "decided_at", "rationale"),
    "witness_sessions": ("witness_session", "Witness session", "session_date", "task_description"),
    "ratification_records": ("ratification_record", "Ratification", "ratified_at", "steward_declaration"),
    "publication_works": ("publication_work", "Publication work attached", "attached_at", "label"),
    "publication_artifacts": ("publication_artifact", "Publication artifact recorded", "created_at", "kind"),
    "authoring_drafts": ("authoring_draft", "Editorial draft recorded", "created_at", "draft_text"),
    "authoring_proposals": ("authoring_proposal", "Editorial proposal", "created_at", "rationale"),
    "authoring_decisions": ("authoring_decision", "Editorial decision", "decided_at", "rationale"),
    "authoring_requests": ("authoring_request", "Editorial application requested", "created_at", None),
    "authoring_outcomes": ("authoring_outcome", "Editorial application result", "created_at", "status"),
    "authoring_proofs": ("authoring_proof", "Publication proof result", "created_at", "status"),
}
_AUXILIARY = (
    "workspace_identity", "provenance", "ai_provenance",
    "blueprint_observation_links", "blueprint_interpretation_links",
    "architect_plan_paragraphs", "expression_profiles",
)
_COMPOSITE = ("old_id", "new_id", "reason", "ratified_at")
_RELATED_KEYS = {
    "blueprint_observation_links": ("blueprint_id", "observation_id"),
    "blueprint_interpretation_links": ("blueprint_id", "interpretation_id"),
    "architect_plan_paragraphs": ("plan_id", "order_idx"),
}
_CANONICAL_CLASSES = {
    "source_documents": "source_document", "source_extractions": "source_extraction",
    "observations": "observation", "interpretations": "interpretation",
    "narrative_blueprints": "blueprint", "architect_plans": "architect_plan",
    "rendered_narratives": "rendered_narrative",
}
_SUPERSESSION_TABLES = (*_CANONICAL_CLASSES, "perspectives", "findings",
                       "steward_decisions", "witness_sessions", "ratification_records",
                       "expression_profiles", "validation_reports")
_MUTABLE = {"reader_highlights", "observation_reviews", "workspace_investigation"}
# These values are copied verbatim by accept_proposed_interpretation. Missing
# fields or disagreement cannot establish that the canonical text is the model
# contribution the Steward accepted; neither permits inventing an edit event.
_ACCEPTANCE_COPY_FIELDS = (
    "observation_id", "perspective", "perspective_id", "text",
    "evidential_status", "evidence_observation_ids", "ai_provenance_id",
)
_PARENTS = {
    "source_extractions": (("document_id", "source_documents", False),),
    "observations": (("source_document_id", "source_documents", False), ("source_extraction_id", "source_extractions", False)),
    "reader_highlights": (("source_document_id", "source_documents", False), ("observation_id", "observations", True)),
    "inquiry_notes": (("observation_id", "observations", False), ("review_id", "observation_reviews", True)),
    "observation_reviews": (("observation_id", "observations", False),),
    "investigation_log": (("source_document_id", "source_documents", True),),
    "proposed_interpretations": (("observation_id", "observations", False), ("perspective_id", "perspectives", True)),
    "interpretations": (("observation_id", "observations", False), ("perspective_id", "perspectives", True)),
    "architect_plans": (("blueprint_id", "narrative_blueprints", False),),
    "rendered_narratives": (("architect_plan_id", "architect_plans", False),),
    "critic_reports": (("proposal_id", "proposed_interpretations", False), ("observation_id", "observations", False)),
    "validation_reports": (("rendered_narrative_id", "rendered_narratives", False), ("architect_plan_id", "architect_plans", False)),
    "findings": (("rendered_narrative_id", "rendered_narratives", False), ("architect_plan_id", "architect_plans", False)),
    "steward_decisions": (("finding_id", "findings", False),),
    "witness_sessions": (("rendered_narrative_id", "rendered_narratives", False),),
    "ratification_records": (("rendered_narrative_id", "rendered_narratives", False),),
    "publication_artifacts": (("work_id", "publication_works", False),),
    "authoring_drafts": (("work_id", "publication_works", False),),
    "authoring_proposals": (("work_id", "publication_works", False),),
    "authoring_decisions": (("proposal_id", "authoring_proposals", False),),
    "authoring_requests": (("work_id", "publication_works", False), ("decision_id", "authoring_decisions", False)),
    "authoring_outcomes": (("work_id", "publication_works", False), ("request_id", "authoring_requests", False)),
    "authoring_proofs": (("work_id", "publication_works", False),),
}


def _encoded(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def serialize_projection(projection: dict) -> bytes:
    """Stable derived export; no current time, local path or fresh identity."""
    return (_encoded(projection) + "\n").encode("utf-8")


def _key(table: str, row: dict) -> dict:
    fields = _RELATED_KEYS.get(table) or (_COMPOSITE if table == "supersession_relations" else (
        ("sha256",) if table == "publication_artifacts" else ("id",)
    ))
    return {field: row[field] for field in fields}


def _timestamp(field: str, value: Any) -> dict:
    result = {"field": field, "value": value, "status": "unknown", "sort_key": None}
    if value is None or value == "":
        return result
    result["status"] = "unorderable"
    if not isinstance(value, str):
        return result
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return result
        result.update(status="ordered", sort_key=parsed.astimezone(timezone.utc).isoformat(timespec="microseconds"))
    except (ValueError, OverflowError):
        pass
    return result


def _list(value: Any) -> list | None:
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, list) else None


def project_study_lineage(conn: sqlite3.Connection) -> dict:
    """Project a caller-owned read-only SQLite snapshot without any writes.

    Older tables are discovered and never migrated. Missing reference evidence
    omits the affected association instead of guessing from current context.
    """
    available = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    data: dict[str, list[dict]] = {}
    missing_columns: dict[str, list[str]] = {}
    missing_tables = []
    for table in (*_SPECS, *_AUXILIARY):
        if table not in available:
            missing_tables.append(table)
            data[table] = []
            continue
        cursor = conn.execute(f'SELECT * FROM "{table}"')
        columns = [column[0] for column in cursor.description]
        data[table] = [dict(zip(columns, row)) for row in cursor.fetchall()]
        required = set()
        if table in _SPECS:
            required.update(_COMPOSITE if table == "supersession_relations" else ("sha256",) if table == "publication_artifacts" else ("id",))
            required.update(field for field, _, optional in _PARENTS.get(table, ()) if not optional)
        # Timestamp absence leaves a visible unknown time. Missing source
        # exclusion state, however, cannot establish Reader access eligibility.
        documented = set(required)
        if table in _SPECS:
            documented.add(_SPECS[table][2])
            if _SPECS[table][3]:
                documented.add(_SPECS[table][3])
        if table == "source_documents":
            documented.add("excluded_from_analysis")
        if table in ("interpretations", "narrative_blueprints", "architect_plans"):
            documented.add("source")
        documented.update(_RELATED_KEYS.get(table, ()))
        if table == "architect_plan_paragraphs":
            documented.update(("required_observations", "required_interpretations"))
        absent = sorted(documented - set(columns))
        if absent:
            missing_columns[table] = absent
        if required - set(columns):
            data[table] = []
    indexes = {table: {row.get("id", row.get("sha256")): row for row in rows}
               for table, rows in data.items() if table != "supersession_relations"}
    identity = next((r for r in data["workspace_identity"] if r.get("id") == "current"), {})
    workspace_id = identity.get("workspace_id")
    workspace = {"id": workspace_id, "name": identity.get("workspace_name")}
    allowed: dict[tuple[str, str], bool] = {}
    checking: set[tuple[str, str]] = set()

    def parent(table: str, identifier: Any) -> dict | None:
        if not isinstance(identifier, str) or not identifier:
            return None
        return indexes.get(table, {}).get(identifier)

    def generic_target(identifier: Any) -> tuple[str, dict] | None:
        matches = [(t, indexes[t][identifier]) for t in _SUPERSESSION_TABLES
                   if isinstance(identifier, str) and identifier in indexes[t]]
        return matches[0] if len(matches) == 1 else None

    def refs_allowed(table: str, row: dict) -> bool:
        for field, target, optional in _PARENTS.get(table, ()):
            identifier = row.get(field)
            if not identifier and optional:
                continue
            p = parent(target, identifier)
            if p is None or not eligible(target, p):
                return False
        return True

    def evidence_ids_allowed(value: Any) -> bool:
        ids = _list(value)
        return ids is not None and all(parent("observations", oid) is not None and eligible("observations", parent("observations", oid)) for oid in ids)

    def ai_allowed(ai: dict | None, proposal_id: str) -> bool:
        if ai is None or ai.get("staged_object_id") != proposal_id:
            return False
        ids = _list(ai.get("parent_object_ids", "[]"))
        if ids is None:
            return False
        for identifier in ids:
            target = generic_target(identifier)
            if target is None or not eligible(*target):
                return False
        return True

    def linked_ai(table: str, row: dict) -> dict | None:
        ai = parent("ai_provenance", row.get("ai_provenance_id"))
        if ai is None:
            return None
        proposal_id = row["id"] if table == "proposed_interpretations" else ai.get("staged_object_id")
        proposal = parent("proposed_interpretations", proposal_id)
        if proposal is None or proposal.get("ai_provenance_id") != ai.get("id"):
            return None
        return ai if ai_allowed(ai, proposal_id) else None

    def eligible(table: str, row: dict) -> bool:
        if table != "supersession_relations":
            identifier = row.get("sha256" if table == "publication_artifacts" else "id")
            if not isinstance(identifier, str) or not identifier:
                return False
        token = (table, _encoded(_key(table, row)))
        if token in allowed:
            return allowed[token]
        if token in checking:
            return False
        checking.add(token)
        ok = refs_allowed(table, row)
        if table == "source_documents":
            ok = "excluded_from_analysis" in row and row["excluded_from_analysis"] in (0, None)
        elif table == "observations" and ok:
            extraction = parent("source_extractions", row.get("source_extraction_id"))
            ok = extraction.get("document_id") == row.get("source_document_id")
        elif table == "investigation_log":
            ok = ok and row.get("lane") == "corpus"
        elif table in ("interpretations", "proposed_interpretations"):
            ok = ok and evidence_ids_allowed(row.get("evidence_observation_ids", "[]"))
            if ok and row.get("ai_provenance_id"):
                ai = parent("ai_provenance", row["ai_provenance_id"])
                proposal_id = row["id"] if table == "proposed_interpretations" else (ai or {}).get("staged_object_id")
                # Missing/detached generation provenance is not repaired. The
                # interpretation itself can still be shown with unknown origin;
                # a real link to excluded parents must not disclose its payload.
                if ai is not None and ai.get("staged_object_id") == proposal_id:
                    ok = ai_allowed(ai, proposal_id)
                if ok and table == "interpretations" and linked_ai(table, row):
                    proposal = parent("proposed_interpretations", proposal_id)
                    ok = proposal is not None and eligible("proposed_interpretations", proposal)
        elif table == "narrative_blueprints":
            sections = _list(row.get("sections"))
            ok = sections is not None
            for section in sections or []:
                if not isinstance(section, dict) or not evidence_ids_allowed(section.get("supporting_observations", [])):
                    ok = False
                    break
                ids = section.get("supporting_interpretations", [])
                if not isinstance(ids, list) or any(parent("interpretations", iid) is None or not eligible("interpretations", parent("interpretations", iid)) for iid in ids):
                    ok = False
                    break
            for link_table, field, target in (("blueprint_observation_links", "observation_id", "observations"), ("blueprint_interpretation_links", "interpretation_id", "interpretations")):
                for link in data[link_table]:
                    if link.get("blueprint_id") == row["id"]:
                        linked = parent(target, link.get(field))
                        ok = ok and linked is not None and eligible(target, linked)
        elif table == "supersession_relations":
            endpoints = [generic_target(row.get(field)) for field in ("old_id", "new_id")]
            ok = all(target is not None and eligible(*target) for target in endpoints)
        elif table == "architect_plans" and ok:
            # Paragraph requirements are durable inputs in their own right.
            # Do not assume they match the linked Blueprint's support lists.
            ok = "architect_plan_paragraphs" not in missing_columns
            for paragraph in data["architect_plan_paragraphs"]:
                if paragraph.get("plan_id") != row["id"]:
                    continue
                ids = _list(paragraph.get("required_interpretations"))
                ok = (ok and evidence_ids_allowed(paragraph.get("required_observations"))
                      and ids is not None
                      and all(parent("interpretations", iid) is not None
                              and eligible("interpretations", parent("interpretations", iid))
                              for iid in ids))
        elif table == "publication_works":
            ok = bool(workspace_id) and row.get("workspace_id") == workspace_id
        elif table == "authoring_decisions":
            ok = ok and bool(workspace_id) and row.get("workspace_id") == workspace_id
        elif table == "authoring_requests" and ok:
            decision = parent("authoring_decisions", row.get("decision_id"))
            proposal = parent("authoring_proposals", decision.get("proposal_id"))
            ok = proposal.get("work_id") == row.get("work_id")
        elif table == "authoring_outcomes" and ok:
            request = parent("authoring_requests", row.get("request_id"))
            ok = request.get("work_id") == row.get("work_id")
        checking.remove(token)
        allowed[token] = bool(ok)
        return bool(ok)

    def authorship(table: str, row: dict) -> tuple[str, str]:
        source = row.get("source")
        ai = linked_ai(table, row) if table in ("proposed_interpretations", "interpretations") else None
        if table == "proposed_interpretations" and ai and str(ai.get("generating_model") or "").strip():
            return "model", "Linked generation provenance."
        if table == "interpretations":
            if source == "steward-authored" and not row.get("ai_provenance_id"):
                return "human", "Stored source is steward-authored."
            proposal = parent("proposed_interpretations", (ai or {}).get("staged_object_id"))
            if (source == "ai-accepted" and ai and str(ai.get("generating_model") or "").strip()
                    and proposal and proposal.get("status") == "accepted"
                    and all(field in row and field in proposal
                            and row[field] == proposal[field]
                            and (field == "perspective_id" or row[field] is not None)
                            for field in _ACCEPTANCE_COPY_FIELDS)
                    and row.get("confidence") == "ai-accepted"
                    and row.get("created_at") == ai.get("acceptance_timestamp")
                    and ai.get("accepting_steward") and ai.get("acceptance_timestamp")
                    and ai.get("acceptance_timestamp") == proposal.get("decided_at")
                    and ai.get("accepting_steward") == proposal.get("steward_id")):
                return "accepted_model", "Linked generation and recorded Steward acceptance."
        if table == "narrative_blueprints":
            if source == "steward-authored":
                return "human", "Stored source is steward-authored."
            if source == "extracted":
                return "derived", "Stored source is extracted; model identity is not established."
        if table in ("source_extractions", "observations", "architect_plans", "validation_reports", "findings"):
            return "derived", "Stored evidence or evaluation derivation; not human interpretation."
        if table in ("steward_decisions", "witness_sessions", "ratification_records"):
            return "human", "Stored human governance or witness record."
        return "unknown", "Authorship is not established by the stored record."

    def context(table: str, row: dict) -> list[dict]:
        if table in _CANONICAL_CLASSES:
            return [{"kind": "lineage", "epistemic_class": _CANONICAL_CLASSES[table], "object_id": row["id"]}]
        doc_id, page = row.get("source_document_id"), row.get("page")
        if not doc_id and row.get("observation_id"):
            obs = parent("observations", row["observation_id"])
            if obs:
                doc_id, page = obs.get("source_document_id"), obs.get("page")
        if doc_id and isinstance(page, int) and not isinstance(page, bool) and page > 0:
            result = {"kind": "reader", "document_id": doc_id, "page": page}
            if table == "reader_highlights":
                result["highlight_id"] = row["id"]
            return [result]
        return []

    def provenance(table: str, row: dict, basis: str) -> dict:
        refs = [{"table": target, "key": {"id": row[field]}}
                for field, target, _ in _PARENTS.get(table, ()) if row.get(field)]
        records = []
        if table in ("proposed_interpretations", "interpretations") and row.get("ai_provenance_id"):
            ai = linked_ai(table, row)
            if ai:
                records.append({"table": "ai_provenance", "key": {"id": ai["id"]}, "record_data": ai})
        if table == "observations":
            for record in data["provenance"]:
                if (record.get("observation_id") == row["id"] and record.get("source_document_id") == row.get("source_document_id")
                        and record.get("source_extraction_id") == row.get("source_extraction_id")):
                    records.append({"table": "provenance", "key": {"id": record.get("id")}, "record_data": record})
        if table == "supersession_relations":
            for field in ("old_id", "new_id"):
                target, endpoint = generic_target(row[field])
                refs.append({"table": target, "key": _key(target, endpoint), "role": field})
        related = (("blueprint_observation_links", "blueprint_id"),
                   ("blueprint_interpretation_links", "blueprint_id")) if table == "narrative_blueprints" else (
                       (("architect_plan_paragraphs", "plan_id"),) if table == "architect_plans" else ())
        for related_table, parent_field in related:
            for record in data[related_table]:
                if record.get(parent_field) == row["id"]:
                    records.append({"table": related_table, "key": _key(related_table, record), "record_data": record})
        records.sort(key=lambda value: (value["table"], _encoded(value["key"])))
        return {"basis": basis, "references": refs, "records": records}

    items = []
    omitted = {}
    for table, (record_type, title, time_field, content_field) in _SPECS.items():
        omitted[table] = 0
        for row in data[table]:
            if not eligible(table, row):
                omitted[table] += 1
                continue
            author, basis = authorship(table, row)
            text = row.get(content_field) if content_field else ""
            if table == "investigation_log" and not text:
                text = row.get("pressing_questions")
            item = {
                "record": {"table": table, "key": _key(table, row)},
                "event": "current_snapshot" if table in _MUTABLE else "recorded",
                "record_type": record_type, "title": title,
                "content": text[:1000] if isinstance(text, str) else "",
                "timestamp": _timestamp(time_field, row.get(time_field)),
                "authorship": author, "provenance": provenance(table, row, basis),
                "record_data": row, "contexts": context(table, row),
            }
            items.append(item)
            if (table == "proposed_interpretations" and row.get("status") in ("accepted", "rejected")
                    and row.get("decided_at") and row.get("steward_id")):
                items.append({**item, "event": "decision", "record_type": "proposal_decision",
                              "title": "Model proposal " + row["status"],
                              "content": (row.get("steward_rationale") or "")[:1000],
                              "timestamp": _timestamp("decided_at", row["decided_at"]),
                              "authorship": "human",
                              "provenance": {**item["provenance"], "basis": "Explicit stored Steward decision fields."}})
    items.sort(key=lambda item: (item["timestamp"]["status"] != "ordered", item["timestamp"]["sort_key"] or "", _encoded(item["record"]), item["event"]))
    return {
        "schema": SCHEMA, "workspace": workspace, "items": items,
        "coverage": {
            "missing_tables": sorted(missing_tables), "missing_columns": missing_columns,
            "omitted": omitted, "unsupported_categories": [
                "Transient Perspective and Room runs", "Overwritten annotation and governing-question revisions",
                "Deleted inquiry questions", "Unrecorded workspace exports and CLI publication events",
                "Reading sessions and page traversal history", "Bucket and motif creation or revision history",
            ],
            "limitations": [
                "This is a derived projection of extant records, not a complete event log.",
                "Current mutable records retain only their latest stored state; original timestamps do not date later text.",
                "Unknown, naive and malformed timestamps are not chronologically ordered; equal times use identity order only.",
                "Excluded evidence, unavailable or ambiguous parents, non-corpus notes and unbound publication works are omitted.",
                "Unknown authorship remains unknown. Artifact references are recorded metadata, not a fresh integrity verification.",
            ],
        },
    }
