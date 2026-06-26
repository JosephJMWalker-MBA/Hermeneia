"""
Deterministic ID generation for canonical objects.

Constitutional rules:
- SourceDocument ID: SHA-256 of file bytes
- SourceExtraction ID: SHA-256 of extraction occurrence payload
- Observation ID: SHA-256 of canonical(source_hash, source_locator, raw_text)
- semantic_hash: SHA-256 of raw_text bytes for textual equivalence
"""
import hashlib
import json
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    """SHA-256 of a file's raw bytes. Authoritative document ID."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(payload: dict) -> str:
    """SHA-256 of a deterministic JSON payload."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def make_semantic_hash(raw_text: str) -> str:
    """Textual-equivalence hash for an Observation's immutable text."""
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def make_source_locator(page: int, block: int, sentence: int | None = None) -> str:
    """Canonical human-readable source locator for extracted text occurrences."""
    if sentence is None:
        return f"page:{page}:block:{block}"
    return f"page:{page}:block:{block}:sentence:{sentence}"


def make_source_extraction_id(
    source_hash: str,
    source_locator: str,
    raw_text: str,
    parser: str,
    parser_version: str,
) -> str:
    """Deterministic SourceExtraction occurrence ID."""
    return _sha256_json(
        {
            "parser": parser,
            "parser_version": parser_version,
            "raw_text": raw_text,
            "source_hash": source_hash,
            "source_locator": source_locator,
        }
    )


def make_observation_id(
    source_hash: str,
    source_locator: str,
    raw_text: str,
) -> str:
    """Deterministic Observation occurrence ID.

    Constitutional formula:
        SHA256(canonical(source_hash, source_locator, raw_text))
    """
    return _sha256_json(
        {
            "raw_text": raw_text,
            "source_hash": source_hash,
            "source_locator": source_locator,
        }
    )


def make_blueprint_id(title: str, thesis: str, sections: list[dict]) -> str:
    """Deterministic NarrativeBlueprint ID.

    sha256(json({sections, thesis, title}, sort_keys=True))
    Content-addressable: the same structural argument always produces the same ID.
    """
    payload = json.dumps(
        {"sections": sections, "thesis": thesis, "title": title},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_perspective_id(name: str) -> str:
    """Deterministic Perspective ID.

    sha256(name.lower().strip()) — case-insensitive so "Literary" and "literary"
    resolve to the same registered Perspective.
    """
    return hashlib.sha256(name.lower().strip().encode("utf-8")).hexdigest()


def make_rendered_narrative_id(
    architect_plan_id: str,
    provider: str,
    system_prompt_id: str | None = None,
) -> str:
    """Deterministic RenderedNarrative ID.

    sha256(json({architect_plan_id, provider, system_prompt_id}))
    Same plan + same provider + same theme = same ID slot (INSERT OR IGNORE = idempotent).
    system_prompt_id=None means "no theme selected".
    """
    payload = json.dumps(
        {
            "architect_plan_id": architect_plan_id,
            "provider": provider,
            "system_prompt_id": system_prompt_id or "",
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_validation_report_id(rendered_narrative_id: str) -> str:
    """Deterministic ValidationReport ID.

    sha256("critic:" + rendered_narrative_id)
    One report per rendered narrative — INSERT OR IGNORE = idempotent.
    """
    return hashlib.sha256(f"critic:{rendered_narrative_id}".encode("utf-8")).hexdigest()


def make_expression_profile_id(slug: str) -> str:
    """Deterministic ExpressionProfile ID.

    sha256(slug.lower().strip()) — slug is the stable key.
    """
    return hashlib.sha256(slug.lower().strip().encode("utf-8")).hexdigest()


# Backwards-compat alias (used by v008 tests)
make_system_prompt_id = make_expression_profile_id


def make_architect_plan_id(blueprint_id: str) -> str:
    """Deterministic ArchitectPlan ID.

    sha256("architect:" + blueprint_id)
    Since the plan is fully determined by the blueprint (same blueprint → same plan),
    the plan ID is determined solely by the blueprint ID.
    """
    return hashlib.sha256(f"architect:{blueprint_id}".encode("utf-8")).hexdigest()


def make_blueprint_hash(title: str, thesis: str, sections: list[dict]) -> str:
    """Canonical hash of a Blueprint's content (same as make_blueprint_id).

    Stored inside the ArchitectPlan so staleness can be detected if the Blueprint
    is ever superseded by a new version (different ID means different content).
    """
    return make_blueprint_id(title, thesis, sections)


def make_obligation_id(dimension: str, plan_id: str, paragraph_order_idx: int, term_text: str) -> str:
    """Deterministic obligation ID for use in Finding identity (Amendment I of ADR-0041).

    Identity derives from the canonical obligation content, not presentation labels.
    term_text is lowercased so case variants of the same term are the same obligation.
    """
    payload = json.dumps(
        {
            "dimension": dimension,
            "plan_id": plan_id,
            "paragraph_order_idx": paragraph_order_idx,
            "term_text": term_text.lower(),
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(f"obligation:{payload}".encode("utf-8")).hexdigest()


def make_finding_id(rendered_narrative_id: str, dimension: str, obligation_id: str) -> str:
    """Deterministic Finding ID (ADR-0041).

    sha256("finding:" + rendered_narrative_id + ":" + dimension + ":" + obligation_id)
    Same canonical inputs → same ID; re-evaluation is idempotent via INSERT OR IGNORE.
    """
    key = f"finding:{rendered_narrative_id}:{dimension}:{obligation_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def make_ratification_record_id(
    rendered_narrative_id: str, ratified_by: str, ratified_at: str
) -> str:
    """Deterministic RatificationRecord ID.

    sha256("ratification:" + rendered_narrative_id + ":" + ratified_by + ":" + ratified_at)
    A steward ratifying the same narrative at the same moment produces the same ID.
    INSERT OR IGNORE is idempotent.
    """
    key = f"ratification:{rendered_narrative_id}:{ratified_by}:{ratified_at}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def make_witness_session_id(
    rendered_narrative_id: str, witness_profile: str, session_date: str
) -> str:
    """Deterministic WitnessSession ID.

    sha256("witness_session:" + rendered_narrative_id + ":" + witness_profile + ":" + session_date)
    Same witness profile tested against the same narrative on the same date → same ID slot.
    INSERT OR IGNORE is idempotent.
    """
    key = f"witness_session:{rendered_narrative_id}:{witness_profile}:{session_date}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def make_steward_decision_id(finding_id: str, verdict: str, decided_at: str) -> str:
    """Deterministic StewardDecision ID.

    sha256("steward_decision:" + finding_id + ":" + verdict + ":" + decided_at)
    Content-addressable: same steward act at the same moment on the same Finding
    produces the same ID. INSERT OR IGNORE is idempotent.
    """
    key = f"steward_decision:{finding_id}:{verdict}:{decided_at}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def make_proposed_interpretation_id(
    observation_id: str,
    perspective: str,
    text: str,
    generating_model: str,
    generation_timestamp: str,
) -> str:
    """Deterministic ProposedInterpretation staging ID (Sprint E8, ADR-0009).

    Unlike canonical Interpretation (content-addressable by observation/perspective/text
    alone), proposed interpretations include the model and timestamp. The same content
    generated by a different model at a different time is a different proposal.
    """
    return _sha256_json(
        {
            "generation_timestamp": generation_timestamp,
            "generating_model": generating_model,
            "observation_id": observation_id,
            "perspective": perspective,
            "text": text,
        }
    )


def make_ai_provenance_id(
    staged_object_id: str,
    generating_model: str,
    generation_timestamp: str,
) -> str:
    """Deterministic AIProvenance ID (Sprint E8, ADR-0009).

    sha256("ai_provenance:" + staged_object_id + ":" + model + ":" + timestamp)
    """
    key = f"ai_provenance:{staged_object_id}:{generating_model}:{generation_timestamp}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def make_critic_report_id(
    proposal_id: str,
    policy: str,
    generated_at: str,
) -> str:
    """Deterministic CriticReport ID (Sprint E9).

    Constitutional Status: OPERATIONAL — not yet canonical.
    Promotion criterion defined in CONSTITUTIONAL_COMPLIANCE.md.

    sha256("critic_report:" + proposal_id + ":" + policy + ":" + generated_at)
    One report per proposal+policy+timestamp slot. INSERT OR IGNORE is idempotent.
    """
    key = f"critic_report:{proposal_id}:{policy}:{generated_at}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def make_interpretation_id(observation_id: str, perspective: str, text: str) -> str:
    """Deterministic Interpretation ID.

    sha256(json({observation_id, perspective, text}))
    Content-addressable: identical readings of the same observation from the same
    perspective produce the same ID, preventing silent duplicates.
    """
    payload = json.dumps(
        {
            "observation_id": observation_id,
            "perspective": perspective,
            "text": text,
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
