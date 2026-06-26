"""SQLite persistence adapter.

Evidence tables are append-only and database-enforced immutable.
Derived tables are disposable/regenerable.
"""
import sqlite3
from pathlib import Path

from .hashing import make_semantic_hash

SCHEMA_VERSION = 16  # bumped from 15: critic_reports operational artifact (Sprint E9)

# Supersession triggers must be dropped and recreated whenever the canonical object
# list grows. SQLite has no ALTER TRIGGER.
_SUPERSESSION_TRIGGER_MIGRATION = """
DROP TRIGGER IF EXISTS supersession_relations_old_exists;
DROP TRIGGER IF EXISTS supersession_relations_new_exists;

CREATE TRIGGER supersession_relations_old_exists
BEFORE INSERT ON supersession_relations
BEGIN
    SELECT RAISE(ABORT, 'Supersession old object missing')
    WHERE NOT (
        EXISTS (SELECT 1 FROM source_documents    WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM source_extractions WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM observations       WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM perspectives       WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM interpretations    WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM narrative_blueprints WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM architect_plans    WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM expression_profiles WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM rendered_narratives WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM validation_reports  WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM findings            WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM steward_decisions   WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM witness_sessions      WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM ratification_records  WHERE id = NEW.old_id)
    );
END;

CREATE TRIGGER supersession_relations_new_exists
BEFORE INSERT ON supersession_relations
BEGIN
    SELECT RAISE(ABORT, 'Supersession new object missing')
    WHERE NOT (
        EXISTS (SELECT 1 FROM source_documents    WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM source_extractions WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM observations       WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM perspectives       WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM interpretations    WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM narrative_blueprints WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM architect_plans    WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM expression_profiles WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM rendered_narratives WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM validation_reports  WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM findings            WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM steward_decisions   WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM witness_sessions    WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM ratification_records WHERE id = NEW.new_id)
    );
END;
"""

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_documents (
    id                TEXT PRIMARY KEY,
    epistemic_class   TEXT NOT NULL DEFAULT 'Artifact'
        CHECK(epistemic_class = 'Artifact'),
    original_filename TEXT NOT NULL,
    file_hash         TEXT NOT NULL,
    total_pages       INTEGER NOT NULL,
    registered_at     TEXT NOT NULL,
    compiler_version  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_extractions (
    id                TEXT PRIMARY KEY,
    epistemic_class   TEXT NOT NULL DEFAULT 'Evidence'
        CHECK(epistemic_class = 'Evidence'),
    document_id       TEXT NOT NULL REFERENCES source_documents(id),
    page              INTEGER NOT NULL,
    region            TEXT NOT NULL,
    raw_text          TEXT NOT NULL,
    parser            TEXT NOT NULL,
    parser_version    TEXT NOT NULL,
    coordinates       TEXT NOT NULL,
    source_locator    TEXT NOT NULL,
    source_hash       TEXT NOT NULL,
    hash              TEXT NOT NULL,
    extracted_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    id                        TEXT PRIMARY KEY,
    epistemic_class           TEXT NOT NULL DEFAULT 'Evidence'
        CHECK(epistemic_class = 'Evidence'),
    source_document_id        TEXT NOT NULL REFERENCES source_documents(id),
    source_extraction_id      TEXT NOT NULL REFERENCES source_extractions(id),
    raw_text                  TEXT NOT NULL,
    source_locator            TEXT NOT NULL,
    semantic_hash             TEXT NOT NULL,
    page                      INTEGER NOT NULL,
    paragraph                 INTEGER NOT NULL,
    sentence                  INTEGER NOT NULL,
    preceding_observation_id  TEXT,
    following_observation_id  TEXT,
    created_at                TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provenance (
    id                    TEXT PRIMARY KEY,
    observation_id        TEXT NOT NULL REFERENCES observations(id),
    source_document_id    TEXT NOT NULL REFERENCES source_documents(id),
    source_extraction_id  TEXT NOT NULL REFERENCES source_extractions(id),
    source_document_hash  TEXT NOT NULL,
    page                  INTEGER NOT NULL,
    paragraph             INTEGER NOT NULL,
    sentence              INTEGER NOT NULL,
    verbatim_text         TEXT NOT NULL,
    location_precision    TEXT NOT NULL CHECK(location_precision IN ('sentence','paragraph','page')),
    char_offset_start     INTEGER,
    char_offset_end       INTEGER,
    bbox_x                REAL,
    bbox_y                REAL,
    bbox_width            REAL,
    bbox_height           REAL,
    bbox_dpi              INTEGER,
    created_at            TEXT NOT NULL,
    compiler_version      TEXT NOT NULL,
    compilation_run_id    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observation_derived (
    observation_id      TEXT PRIMARY KEY REFERENCES observations(id),
    normalized_text     TEXT NOT NULL,
    sentence_tokens     TEXT NOT NULL DEFAULT '[]',
    whitespace_map      TEXT NOT NULL DEFAULT '[]',
    derivation_version  TEXT NOT NULL,
    derived_at          TEXT NOT NULL
);

-- Field v0.1: deterministic term index, no AI, no embeddings
CREATE TABLE IF NOT EXISTS terms (
    id   TEXT PRIMARY KEY,   -- sha256 of the term string
    term TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS observation_terms (
    observation_id TEXT NOT NULL REFERENCES observations(id),
    term_id        TEXT NOT NULL REFERENCES terms(id),
    PRIMARY KEY (observation_id, term_id)
);

-- Perspective registry: named interpretive lenses (append-only)
CREATE TABLE IF NOT EXISTS perspectives (
    id          TEXT PRIMARY KEY,   -- sha256(lower(name))
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

-- Layer 1: perspective-scoped interpretations (append-only, immutable).
-- source='steward-authored': human-authored (ai_provenance_id IS NULL).
-- source='ai-accepted': AI-generated, steward-accepted (ai_provenance_id references ai_provenance).
-- Two-Table Invariant: a proposed interpretation is not an interpretation with lower confidence.
-- It is a different constitutional state. See docs/Architecture_Proofs.md.
CREATE TABLE IF NOT EXISTS interpretations (
    id                        TEXT PRIMARY KEY,
    observation_id            TEXT NOT NULL REFERENCES observations(id),
    perspective               TEXT NOT NULL,
    perspective_id            TEXT REFERENCES perspectives(id),
    text                      TEXT NOT NULL,
    evidential_status         TEXT NOT NULL
        CHECK(evidential_status IN ('established','contested','speculative','uncertain')),
    evidence_observation_ids  TEXT NOT NULL DEFAULT '[]',  -- JSON array of obs IDs
    confidence                TEXT NOT NULL DEFAULT 'human',
    source                    TEXT NOT NULL DEFAULT 'steward-authored',
    ai_provenance_id          TEXT REFERENCES ai_provenance(id),  -- NULL = human-authored; non-NULL = AI-assisted, steward-accepted
    created_at                TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_interp_obs  ON interpretations(observation_id);
CREATE INDEX IF NOT EXISTS idx_interp_persp ON interpretations(perspective_id);
CREATE TRIGGER IF NOT EXISTS interpretations_no_update
BEFORE UPDATE ON interpretations
BEGIN
    SELECT RAISE(ABORT, 'Interpretation immutable');
END;
CREATE TRIGGER IF NOT EXISTS interpretations_no_delete
BEFORE DELETE ON interpretations
BEGIN
    SELECT RAISE(ABORT, 'Interpretation immutable');
END;

-- Layer 3: steward-authored structural argument skeleton (append-only)
CREATE TABLE IF NOT EXISTS narrative_blueprints (
    id          TEXT PRIMARY KEY,   -- sha256({title, thesis, sections})
    title       TEXT NOT NULL,
    thesis      TEXT NOT NULL,
    sections    TEXT NOT NULL,      -- JSON array of {claim, supporting_observations, supporting_interpretations}
    source      TEXT NOT NULL DEFAULT 'steward-authored',
    created_at  TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS narrative_blueprints_no_update
BEFORE UPDATE ON narrative_blueprints
BEGIN
    SELECT RAISE(ABORT, 'NarrativeBlueprint immutable');
END;
CREATE TRIGGER IF NOT EXISTS narrative_blueprints_no_delete
BEFORE DELETE ON narrative_blueprints
BEGIN
    SELECT RAISE(ABORT, 'NarrativeBlueprint immutable');
END;

-- Denormalized link tables for O(1) lookup in both directions
CREATE TABLE IF NOT EXISTS blueprint_observation_links (
    blueprint_id   TEXT NOT NULL REFERENCES narrative_blueprints(id),
    observation_id TEXT NOT NULL REFERENCES observations(id),
    PRIMARY KEY (blueprint_id, observation_id)
);
CREATE TRIGGER IF NOT EXISTS blueprint_observation_links_no_update
BEFORE UPDATE ON blueprint_observation_links
BEGIN
    SELECT RAISE(ABORT, 'BlueprintObservationLink immutable');
END;
CREATE TRIGGER IF NOT EXISTS blueprint_observation_links_no_delete
BEFORE DELETE ON blueprint_observation_links
BEGIN
    SELECT RAISE(ABORT, 'BlueprintObservationLink immutable');
END;

CREATE TABLE IF NOT EXISTS blueprint_interpretation_links (
    blueprint_id      TEXT NOT NULL REFERENCES narrative_blueprints(id),
    interpretation_id TEXT NOT NULL REFERENCES interpretations(id),
    PRIMARY KEY (blueprint_id, interpretation_id)
);
CREATE TRIGGER IF NOT EXISTS blueprint_interpretation_links_no_update
BEFORE UPDATE ON blueprint_interpretation_links
BEGIN
    SELECT RAISE(ABORT, 'BlueprintInterpretationLink immutable');
END;
CREATE TRIGGER IF NOT EXISTS blueprint_interpretation_links_no_delete
BEFORE DELETE ON blueprint_interpretation_links
BEGIN
    SELECT RAISE(ABORT, 'BlueprintInterpretationLink immutable');
END;

CREATE INDEX IF NOT EXISTS idx_bp_obs_link   ON blueprint_observation_links(observation_id);
CREATE INDEX IF NOT EXISTS idx_bp_interp_link ON blueprint_interpretation_links(interpretation_id);

-- Layer 4: Composition — Architect (deterministic, not steward-authored)
CREATE TABLE IF NOT EXISTS architect_plans (
    id             TEXT PRIMARY KEY,   -- sha256("architect:" + blueprint_id)
    blueprint_id   TEXT NOT NULL REFERENCES narrative_blueprints(id),
    blueprint_hash TEXT NOT NULL,      -- snapshot of blueprint content hash at plan creation
    title          TEXT NOT NULL,      -- copied from blueprint
    source         TEXT NOT NULL DEFAULT 'deterministic',
    created_at     TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS architect_plans_no_update
BEFORE UPDATE ON architect_plans
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlan immutable');
END;
CREATE TRIGGER IF NOT EXISTS architect_plans_no_delete
BEFORE DELETE ON architect_plans
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlan immutable');
END;

CREATE TABLE IF NOT EXISTS architect_plan_paragraphs (
    plan_id                  TEXT NOT NULL REFERENCES architect_plans(id),
    order_idx                INTEGER NOT NULL,
    purpose                  TEXT NOT NULL,
    blueprint_section        INTEGER NOT NULL,
    required_observations    TEXT NOT NULL DEFAULT '[]',   -- JSON array of obs IDs
    required_interpretations TEXT NOT NULL DEFAULT '[]',   -- JSON array of interp IDs
    required_terms           TEXT NOT NULL DEFAULT '[]',   -- JSON array of {term, priority}
    forbidden_claims         TEXT NOT NULL DEFAULT '[]',   -- JSON array of strings
    notes                    TEXT,
    PRIMARY KEY (plan_id, order_idx)
);
CREATE TRIGGER IF NOT EXISTS architect_plan_paragraphs_no_update
BEFORE UPDATE ON architect_plan_paragraphs
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlanParagraph immutable');
END;
CREATE TRIGGER IF NOT EXISTS architect_plan_paragraphs_no_delete
BEFORE DELETE ON architect_plan_paragraphs
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlanParagraph immutable');
END;

CREATE INDEX IF NOT EXISTS idx_arch_plan_bp ON architect_plans(blueprint_id);

-- Expression Profiles: named philosophies of communication that shape Artist output.
-- Language is just another profile dimension — the Architect is invariant across all profiles.
CREATE TABLE IF NOT EXISTS expression_profiles (
    id                  TEXT PRIMARY KEY,   -- sha256(slug)
    slug                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT,
    language            TEXT NOT NULL DEFAULT 'en',  -- ISO 639-1 code
    audience            TEXT,
    reading_level       TEXT,
    tone                TEXT,
    voice               TEXT,
    artist_prompt       TEXT NOT NULL,      -- injected into the Artist prompt
    critic_expectations TEXT,               -- what the Critic should verify
    source              TEXT NOT NULL DEFAULT 'built-in',
    created_at          TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS expression_profiles_no_update
BEFORE UPDATE ON expression_profiles
BEGIN
    SELECT RAISE(ABORT, 'ExpressionProfile immutable');
END;
CREATE TRIGGER IF NOT EXISTS expression_profiles_no_delete
BEFORE DELETE ON expression_profiles
BEGIN
    SELECT RAISE(ABORT, 'ExpressionProfile immutable');
END;

-- Layer 4b: Composition — Artist (rendered prose, profile-scoped)
-- expression_profile_id added by ensure_profile_tables migration for existing DBs
CREATE TABLE IF NOT EXISTS rendered_narratives (
    id                   TEXT PRIMARY KEY,   -- sha256({architect_plan_id, provider, expression_profile_id})
    architect_plan_id    TEXT NOT NULL REFERENCES architect_plans(id),
    provider             TEXT NOT NULL,
    expression_profile_id TEXT REFERENCES expression_profiles(id),
    text                 TEXT NOT NULL,
    prompt_used          TEXT NOT NULL,
    execution_config     TEXT,               -- CI-011: JSON audit record {provider,model_id,max_tokens,...,sdk_version}
    created_at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rendered_plan    ON rendered_narratives(architect_plan_id);
CREATE INDEX IF NOT EXISTS idx_rendered_profile ON rendered_narratives(expression_profile_id);
CREATE TRIGGER IF NOT EXISTS rendered_narratives_no_update
BEFORE UPDATE ON rendered_narratives
BEGIN
    SELECT RAISE(ABORT, 'RenderedNarrative immutable');
END;
CREATE TRIGGER IF NOT EXISTS rendered_narratives_no_delete
BEFORE DELETE ON rendered_narratives
BEGIN
    SELECT RAISE(ABORT, 'RenderedNarrative immutable');
END;

-- Validation Reports: Critic's deterministic semantic fidelity assessment
CREATE TABLE IF NOT EXISTS validation_reports (
    id                    TEXT PRIMARY KEY,   -- sha256("critic:" + rendered_narrative_id)
    rendered_narrative_id TEXT NOT NULL REFERENCES rendered_narratives(id),
    architect_plan_id     TEXT NOT NULL REFERENCES architect_plans(id),
    expression_profile_id TEXT REFERENCES expression_profiles(id),
    semantic_fidelity     REAL NOT NULL,      -- 0.0–100.0
    required_terms_present TEXT NOT NULL DEFAULT '[]',
    required_terms_missing TEXT NOT NULL DEFAULT '[]',
    unsupported_claims    TEXT NOT NULL DEFAULT '[]',
    omitted_observations  TEXT NOT NULL DEFAULT '[]',
    omitted_interpretations TEXT NOT NULL DEFAULT '[]',
    semantic_drift        TEXT NOT NULL DEFAULT '[]',
    warnings              TEXT NOT NULL DEFAULT '[]',
    approved              INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vr_narrative ON validation_reports(rendered_narrative_id);
CREATE INDEX IF NOT EXISTS idx_vr_plan      ON validation_reports(architect_plan_id);
CREATE TRIGGER IF NOT EXISTS validation_reports_no_update
BEFORE UPDATE ON validation_reports
BEGIN
    SELECT RAISE(ABORT, 'ValidationReport immutable');
END;
CREATE TRIGGER IF NOT EXISTS validation_reports_no_delete
BEFORE DELETE ON validation_reports
BEGIN
    SELECT RAISE(ABORT, 'ValidationReport immutable');
END;

-- Findings: canonical Evaluation objects produced by Evaluation Functions (ADR-0041).
-- One Finding per obligation per dimension. Append-only. Immutable once written.
-- ai_provenance: permanent provenance records for AI-generated objects (Sprint E8, ADR-0009).
-- Written at generation time; acceptance fields start NULL and are populated at most once
-- when a human steward accepts the staged object. Generation fields are immutable after write.
-- This is a single record spanning two events, as specified by ADR-0009.
CREATE TABLE IF NOT EXISTS ai_provenance (
    id                    TEXT PRIMARY KEY,
    staged_object_id      TEXT NOT NULL,      -- references proposed_interpretations.id (plain TEXT: avoids circular FK)
    generating_model      TEXT NOT NULL CHECK (length(trim(generating_model)) > 0),
    model_version         TEXT NOT NULL DEFAULT '',
    generation_timestamp  TEXT NOT NULL,
    prompt_reference      TEXT NOT NULL,
    prompt_reference_type TEXT NOT NULL CHECK (prompt_reference_type IN ('template_id', 'hash', 'full_text')),
    parent_object_ids     TEXT NOT NULL DEFAULT '[]',   -- JSON array of Hermeneia object IDs provided as input
    generation_parameters TEXT NOT NULL DEFAULT '{}',   -- JSON: model params at generation time
    schema_version        TEXT NOT NULL DEFAULT 'ADR-0009-v1.0',
    -- Acceptance fields: NULL until a human steward accepts the staged object.
    -- Remain NULL permanently for rejected proposals.
    accepting_steward     TEXT,
    acceptance_timestamp  TEXT,
    acceptance_rationale  TEXT,
    created_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_aip_staged ON ai_provenance(staged_object_id);
CREATE INDEX IF NOT EXISTS idx_aip_model  ON ai_provenance(generating_model);

-- Immutability: generation fields cannot change after write.
CREATE TRIGGER IF NOT EXISTS ai_provenance_no_alter_generation
BEFORE UPDATE OF generating_model, model_version, generation_timestamp,
                 prompt_reference, prompt_reference_type, parent_object_ids,
                 generation_parameters ON ai_provenance
BEGIN
    SELECT RAISE(ABORT, 'AIProvenance generation fields immutable');
END;

-- Acceptance fields may be written exactly once (NULL → value).
CREATE TRIGGER IF NOT EXISTS ai_provenance_acceptance_once
BEFORE UPDATE OF accepting_steward ON ai_provenance
BEGIN
    SELECT RAISE(ABORT, 'AIProvenance acceptance already recorded')
    WHERE OLD.accepting_steward IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS ai_provenance_no_delete
BEFORE DELETE ON ai_provenance
BEGIN
    SELECT RAISE(ABORT, 'AIProvenance immutable — provenance records are permanent');
END;

-- proposed_interpretations: staging table for AI-generated Interpretation candidates (Sprint E8, ADR-0009).
-- Constitutional note: a proposed interpretation is not an interpretation with lower confidence.
-- It is a different constitutional state. See Architecture_Proofs.md — Staging Constitutional Principle.
-- Status transitions: pending → accepted | rejected (terminal; enforced by trigger).
-- Rejected objects are never deleted — they remain as permanent record of what was generated and why not accepted.
CREATE TABLE IF NOT EXISTS proposed_interpretations (
    id                       TEXT PRIMARY KEY,
    observation_id           TEXT NOT NULL REFERENCES observations(id),
    perspective              TEXT NOT NULL,
    perspective_id           TEXT REFERENCES perspectives(id),
    text                     TEXT NOT NULL CHECK (length(trim(text)) > 0),
    evidential_status        TEXT NOT NULL
        CHECK (evidential_status IN ('established','contested','speculative','uncertain')),
    evidence_observation_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of obs IDs
    ai_provenance_id         TEXT NOT NULL REFERENCES ai_provenance(id),
    status                   TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    -- Decision fields: NULL until steward makes a decision
    steward_id               TEXT,
    decided_at               TEXT,
    steward_rationale        TEXT,
    created_at               TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pi_observation ON proposed_interpretations(observation_id);
CREATE INDEX IF NOT EXISTS idx_pi_status      ON proposed_interpretations(status);
CREATE INDEX IF NOT EXISTS idx_pi_provenance  ON proposed_interpretations(ai_provenance_id);

-- Status may transition from pending to a terminal state, but never from a terminal state.
CREATE TRIGGER IF NOT EXISTS proposed_interpretations_no_restatus
BEFORE UPDATE OF status ON proposed_interpretations
BEGIN
    SELECT RAISE(ABORT, 'ProposedInterpretation terminal status immutable')
    WHERE OLD.status IN ('accepted', 'rejected');
END;

-- Rejected objects are never deleted (ADR-0009).
CREATE TRIGGER IF NOT EXISTS proposed_interpretations_no_delete
BEFORE DELETE ON proposed_interpretations
BEGIN
    SELECT RAISE(ABORT, 'ProposedInterpretation immutable — rejected objects are permanent record');
END;

-- critic_reports: Interpretation Grounding Critic output (Sprint E9, ADR-0009 pipeline).
-- Constitutional Status: OPERATIONAL — not yet canonical.
-- Promotion criterion defined in CONSTITUTIONAL_COMPLIANCE.md.
-- Table is immutable and permanent. Not supersession-eligible.
-- No canonical FK dependencies until promotion.
-- Each row is the output of Stage 1 (evidence identification) + Stage 2 (evidence-claim mapping)
-- + Stage 3 (verdict classification) applied to a proposed_interpretation under a named policy.
CREATE TABLE IF NOT EXISTS critic_reports (
    id                    TEXT PRIMARY KEY,   -- sha256("critic_report:" + proposal_id + ":" + policy + ":" + generated_at)
    proposal_id           TEXT NOT NULL,      -- references proposed_interpretations.id (plain TEXT: operational artifact)
    observation_id        TEXT NOT NULL REFERENCES observations(id),
    policy                TEXT NOT NULL
        CHECK (policy IN ('conservative', 'decomposition', 'contradiction_sensitive', 'aggregate_weighting')),
    claims                TEXT NOT NULL DEFAULT '[]',     -- JSON: [{text, verdict, evidence_cited, rationale}]
    evidence_passages     TEXT NOT NULL DEFAULT '[]',     -- JSON: [str] — Stage 1 output
    overall_verdict       TEXT NOT NULL
        CHECK (overall_verdict IN ('supported', 'partially_supported', 'unsupported', 'contradicted')),
    normalized            INTEGER NOT NULL DEFAULT 0,     -- 1 after steward claim normalization review
    normalization_notes   TEXT,                           -- steward's claim normalization notes (NULL until reviewed)
    generated_at          TEXT NOT NULL,
    created_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cr_proposal    ON critic_reports(proposal_id);
CREATE INDEX IF NOT EXISTS idx_cr_observation ON critic_reports(observation_id);
CREATE INDEX IF NOT EXISTS idx_cr_policy      ON critic_reports(policy);
CREATE INDEX IF NOT EXISTS idx_cr_verdict     ON critic_reports(overall_verdict);

CREATE TRIGGER IF NOT EXISTS critic_reports_no_update
BEFORE UPDATE OF id, proposal_id, observation_id, policy, claims,
                 evidence_passages, overall_verdict, generated_at ON critic_reports
BEGIN
    SELECT RAISE(ABORT, 'CriticReport core fields immutable');
END;

CREATE TRIGGER IF NOT EXISTS critic_reports_no_delete
BEFORE DELETE ON critic_reports
BEGIN
    SELECT RAISE(ABORT, 'CriticReport immutable — operational artifact is permanent');
END;

CREATE TABLE IF NOT EXISTS findings (
    id                    TEXT PRIMARY KEY,   -- sha256("finding:" + narrative_id + ":" + dimension + ":" + obligation_id)
    rendered_narrative_id TEXT NOT NULL REFERENCES rendered_narratives(id),
    architect_plan_id     TEXT NOT NULL REFERENCES architect_plans(id),
    dimension             TEXT NOT NULL,      -- orthogonal evaluation dimension, e.g. "structural"
    obligation_id         TEXT NOT NULL,      -- sha256("obligation:" + canonical obligation content)
    operation             TEXT NOT NULL CHECK (operation IN ('preservation','omission','transformation','injection','not_evaluated')),
    status                TEXT NOT NULL CHECK (status IN ('preserved','omitted','transformed','injected','not_evaluated')),
    evidence              TEXT NOT NULL,      -- JSON: {contract_obligation, observed_render, supporting_trace}
    evaluation_method     TEXT NOT NULL,      -- function name + version, e.g. "structural-v1.0"
    constitution_version  TEXT NOT NULL,      -- JSON constitutional profile
    created_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_narrative ON findings(rendered_narrative_id);
CREATE INDEX IF NOT EXISTS idx_findings_plan      ON findings(architect_plan_id);
CREATE INDEX IF NOT EXISTS idx_findings_dimension ON findings(dimension);

CREATE TRIGGER IF NOT EXISTS findings_no_update
BEFORE UPDATE ON findings
BEGIN
    SELECT RAISE(ABORT, 'Finding immutable');
END;

CREATE TRIGGER IF NOT EXISTS findings_no_delete
BEFORE DELETE ON findings
BEGIN
    SELECT RAISE(ABORT, 'Finding immutable');
END;

-- StewardDecisions: irreducible human governance acts (Sprint E5).
-- Each records a steward's verdict on a specific Finding. Append-only. Immutable.
-- The directionality constraint: StewardDecision.finding_id → findings.id.
-- Finding has no steward_decision_id column. The governance layer annotates itself.
CREATE TABLE IF NOT EXISTS steward_decisions (
    id                   TEXT PRIMARY KEY,  -- sha256("steward_decision:" + finding_id + ":" + verdict + ":" + decided_at)
    finding_id           TEXT NOT NULL REFERENCES findings(id),
    verdict              TEXT NOT NULL CHECK (verdict IN ('accepted','rejected','deferred')),
    rationale            TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    steward_id           TEXT NOT NULL CHECK (length(trim(steward_id)) > 0),
    decided_at           TEXT NOT NULL,
    constitution_version TEXT NOT NULL,
    created_at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sd_finding ON steward_decisions(finding_id);
CREATE INDEX IF NOT EXISTS idx_sd_steward ON steward_decisions(steward_id);
CREATE INDEX IF NOT EXISTS idx_sd_verdict ON steward_decisions(verdict);

CREATE TRIGGER IF NOT EXISTS steward_decisions_no_update
BEFORE UPDATE ON steward_decisions
BEGIN
    SELECT RAISE(ABORT, 'StewardDecision immutable');
END;

CREATE TRIGGER IF NOT EXISTS steward_decisions_no_delete
BEFORE DELETE ON steward_decisions
BEGIN
    SELECT RAISE(ABORT, 'StewardDecision immutable');
END;

-- WitnessSessions: irreducible human understanding verification acts (Sprint E6).
-- Records whether a human with a specific profile completed a task using a RenderedNarrative.
-- Orthogonal to StewardDecision: StewardDecision evaluates machine output (Finding);
-- WitnessSession verifies human reception (did the understanding reach the audience?).
-- Append-only. Immutable once written. Points to RenderedNarrative; RenderedNarrative
-- has no witness_session_id column.
CREATE TABLE IF NOT EXISTS witness_sessions (
    id                    TEXT PRIMARY KEY,  -- sha256("witness_session:" + narrative_id + ":" + profile + ":" + session_date)
    rendered_narrative_id TEXT NOT NULL REFERENCES rendered_narratives(id),
    witness_profile       TEXT NOT NULL CHECK (length(trim(witness_profile)) > 0),
    task_description      TEXT NOT NULL CHECK (length(trim(task_description)) > 0),
    task_completed        INTEGER NOT NULL CHECK (task_completed IN (0, 1)),
    notes                 TEXT,              -- human-authored facilitation notes; may be NULL
    facilitated_by        TEXT NOT NULL CHECK (length(trim(facilitated_by)) > 0),
    session_date          TEXT NOT NULL,
    constitution_version  TEXT NOT NULL,
    created_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ws_narrative ON witness_sessions(rendered_narrative_id);
CREATE INDEX IF NOT EXISTS idx_ws_profile   ON witness_sessions(witness_profile);
CREATE INDEX IF NOT EXISTS idx_ws_completed ON witness_sessions(task_completed);

CREATE TRIGGER IF NOT EXISTS witness_sessions_no_update
BEFORE UPDATE ON witness_sessions
BEGIN
    SELECT RAISE(ABORT, 'WitnessSession immutable');
END;

CREATE TRIGGER IF NOT EXISTS witness_sessions_no_delete
BEFORE DELETE ON witness_sessions
BEGIN
    SELECT RAISE(ABORT, 'WitnessSession immutable');
END;

-- RatificationRecords: the terminal canonical object in the epistemic chain (Sprint E7).
-- Answers: shall this RenderedNarrative become institutional memory?
-- A RatificationRecord is only valid when:
--   (1) at least one Finding exists (machine evaluation happened),
--   (2) every Finding has at least one StewardDecision (governance happened), and
--   (3) at least one WitnessSession confirms understanding reached the audience.
-- The audit_snapshot captures the full constitutional state as an immutable JSON document.
-- Append-only. Immutable once written.
CREATE TABLE IF NOT EXISTS ratification_records (
    id                     TEXT PRIMARY KEY,  -- sha256("ratification:" + narrative_id + ":" + ratified_by + ":" + ratified_at)
    rendered_narrative_id  TEXT NOT NULL REFERENCES rendered_narratives(id),
    ratified_by            TEXT NOT NULL CHECK (length(trim(ratified_by)) > 0),
    ratified_at            TEXT NOT NULL,
    steward_declaration    TEXT NOT NULL CHECK (length(trim(steward_declaration)) > 0),
    -- Snapshot counts at moment of ratification
    finding_count          INTEGER NOT NULL,
    steward_decision_count INTEGER NOT NULL,
    witness_session_count  INTEGER NOT NULL,
    -- Constitutional state at ratification (JSON)
    constitution_version   TEXT NOT NULL,
    audit_snapshot         TEXT NOT NULL,     -- JSON: full state at ratification
    created_at             TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rr_narrative ON ratification_records(rendered_narrative_id);
CREATE INDEX IF NOT EXISTS idx_rr_ratified_by ON ratification_records(ratified_by);

CREATE TRIGGER IF NOT EXISTS ratification_records_no_update
BEFORE UPDATE ON ratification_records
BEGIN
    SELECT RAISE(ABORT, 'RatificationRecord immutable');
END;

CREATE TRIGGER IF NOT EXISTS ratification_records_no_delete
BEFORE DELETE ON ratification_records
BEGIN
    SELECT RAISE(ABORT, 'RatificationRecord immutable');
END;

-- CI-014: Monotonic supersession is an append-only relation.
-- It records that one already-persistent object is superseded by another
-- already-persistent object without mutating either object.
CREATE TABLE IF NOT EXISTS supersession_relations (
    old_id      TEXT NOT NULL,
    new_id      TEXT NOT NULL,
    reason      TEXT NOT NULL CHECK(length(trim(reason)) > 0),
    ratified_at TEXT NOT NULL CHECK(length(trim(ratified_at)) > 0),
    PRIMARY KEY (old_id, new_id, reason, ratified_at)
);

CREATE INDEX IF NOT EXISTS idx_supersession_old ON supersession_relations(old_id);
CREATE INDEX IF NOT EXISTS idx_supersession_new ON supersession_relations(new_id);

CREATE INDEX IF NOT EXISTS idx_obs_source_doc  ON observations(source_document_id);
CREATE INDEX IF NOT EXISTS idx_extraction_doc  ON source_extractions(document_id);
CREATE INDEX IF NOT EXISTS idx_obs_extraction  ON observations(source_extraction_id);
CREATE INDEX IF NOT EXISTS idx_obs_page        ON observations(page, paragraph, sentence);
CREATE INDEX IF NOT EXISTS idx_prov_obs        ON provenance(observation_id);
CREATE INDEX IF NOT EXISTS idx_obs_terms_term  ON observation_terms(term_id);

CREATE TRIGGER IF NOT EXISTS supersession_relations_old_exists
BEFORE INSERT ON supersession_relations
BEGIN
    SELECT RAISE(ABORT, 'Supersession old object missing')
    WHERE NOT (
        EXISTS (SELECT 1 FROM source_documents WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM source_extractions WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM observations WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM perspectives WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM interpretations WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM narrative_blueprints WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM architect_plans WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM expression_profiles WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM rendered_narratives WHERE id = NEW.old_id)
        OR EXISTS (SELECT 1 FROM validation_reports WHERE id = NEW.old_id)
    );
END;

CREATE TRIGGER IF NOT EXISTS supersession_relations_new_exists
BEFORE INSERT ON supersession_relations
BEGIN
    SELECT RAISE(ABORT, 'Supersession new object missing')
    WHERE NOT (
        EXISTS (SELECT 1 FROM source_documents WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM source_extractions WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM observations WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM perspectives WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM interpretations WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM narrative_blueprints WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM architect_plans WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM expression_profiles WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM rendered_narratives WHERE id = NEW.new_id)
        OR EXISTS (SELECT 1 FROM validation_reports WHERE id = NEW.new_id)
    );
END;

CREATE TRIGGER IF NOT EXISTS supersession_relations_no_update
BEFORE UPDATE ON supersession_relations
BEGIN
    SELECT RAISE(ABORT, 'SupersessionRelation append-only');
END;

CREATE TRIGGER IF NOT EXISTS supersession_relations_no_delete
BEFORE DELETE ON supersession_relations
BEGIN
    SELECT RAISE(ABORT, 'SupersessionRelation append-only');
END;

CREATE TRIGGER IF NOT EXISTS source_documents_no_update
BEFORE UPDATE ON source_documents
WHEN NEW.id              != OLD.id
  OR NEW.file_hash       != OLD.file_hash
  OR NEW.original_filename != OLD.original_filename
  OR NEW.registered_at   != OLD.registered_at
BEGIN
    SELECT RAISE(ABORT, 'SourceDocument immutable');
END;

CREATE TRIGGER IF NOT EXISTS source_documents_no_delete
BEFORE DELETE ON source_documents
BEGIN
    SELECT RAISE(ABORT, 'SourceDocument immutable');
END;

CREATE TRIGGER IF NOT EXISTS source_extractions_no_update
BEFORE UPDATE ON source_extractions
BEGIN
    SELECT RAISE(ABORT, 'SourceExtraction immutable');
END;

CREATE TRIGGER IF NOT EXISTS source_extractions_no_delete
BEFORE DELETE ON source_extractions
BEGIN
    SELECT RAISE(ABORT, 'SourceExtraction immutable');
END;

CREATE TRIGGER IF NOT EXISTS observations_no_update
BEFORE UPDATE ON observations
BEGIN
    SELECT RAISE(ABORT, 'Observation immutable');
END;

CREATE TRIGGER IF NOT EXISTS observations_no_delete
BEFORE DELETE ON observations
BEGIN
    SELECT RAISE(ABORT, 'Observation immutable');
END;

CREATE TRIGGER IF NOT EXISTS provenance_no_update
BEFORE UPDATE ON provenance
BEGIN
    SELECT RAISE(ABORT, 'Provenance immutable');
END;

CREATE TRIGGER IF NOT EXISTS provenance_no_delete
BEFORE DELETE ON provenance
BEGIN
    SELECT RAISE(ABORT, 'Provenance immutable');
END;
"""


_ARCHITECT_DDL = """
CREATE TABLE IF NOT EXISTS architect_plans (
    id             TEXT PRIMARY KEY,
    blueprint_id   TEXT NOT NULL REFERENCES narrative_blueprints(id),
    blueprint_hash TEXT NOT NULL,
    title          TEXT NOT NULL,
    source         TEXT NOT NULL DEFAULT 'deterministic',
    created_at     TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS architect_plans_no_update
BEFORE UPDATE ON architect_plans
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlan immutable');
END;
CREATE TRIGGER IF NOT EXISTS architect_plans_no_delete
BEFORE DELETE ON architect_plans
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlan immutable');
END;
CREATE TABLE IF NOT EXISTS architect_plan_paragraphs (
    plan_id                  TEXT NOT NULL REFERENCES architect_plans(id),
    order_idx                INTEGER NOT NULL,
    purpose                  TEXT NOT NULL,
    blueprint_section        INTEGER NOT NULL,
    required_observations    TEXT NOT NULL DEFAULT '[]',
    required_interpretations TEXT NOT NULL DEFAULT '[]',
    required_terms           TEXT NOT NULL DEFAULT '[]',
    forbidden_claims         TEXT NOT NULL DEFAULT '[]',
    notes                    TEXT,
    PRIMARY KEY (plan_id, order_idx)
);
CREATE TRIGGER IF NOT EXISTS architect_plan_paragraphs_no_update
BEFORE UPDATE ON architect_plan_paragraphs
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlanParagraph immutable');
END;
CREATE TRIGGER IF NOT EXISTS architect_plan_paragraphs_no_delete
BEFORE DELETE ON architect_plan_paragraphs
BEGIN
    SELECT RAISE(ABORT, 'ArchitectPlanParagraph immutable');
END;
CREATE INDEX IF NOT EXISTS idx_arch_plan_bp ON architect_plans(blueprint_id);
"""


def ensure_architect_tables(conn: "sqlite3.Connection") -> None:
    """Idempotently create architect tables on any open connection."""
    conn.executescript(_ARCHITECT_DDL)
    conn.commit()


_PROFILE_BASE_DDL = """
CREATE TABLE IF NOT EXISTS expression_profiles (
    id                  TEXT PRIMARY KEY,
    slug                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    description         TEXT,
    language            TEXT NOT NULL DEFAULT 'en',
    audience            TEXT,
    reading_level       TEXT,
    tone                TEXT,
    voice               TEXT,
    artist_prompt       TEXT NOT NULL,
    critic_expectations TEXT,
    source              TEXT NOT NULL DEFAULT 'built-in',
    created_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rendered_narratives (
    id                    TEXT PRIMARY KEY,
    architect_plan_id     TEXT NOT NULL REFERENCES architect_plans(id),
    provider              TEXT NOT NULL,
    expression_profile_id TEXT REFERENCES expression_profiles(id),
    text                  TEXT NOT NULL,
    prompt_used           TEXT NOT NULL,
    execution_config      TEXT,
    created_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rendered_plan    ON rendered_narratives(architect_plan_id);
"""


_PROFILE_IMMUTABILITY_DDL = """
CREATE TRIGGER IF NOT EXISTS expression_profiles_no_update
BEFORE UPDATE ON expression_profiles
BEGIN
    SELECT RAISE(ABORT, 'ExpressionProfile immutable');
END;
CREATE TRIGGER IF NOT EXISTS expression_profiles_no_delete
BEFORE DELETE ON expression_profiles
BEGIN
    SELECT RAISE(ABORT, 'ExpressionProfile immutable');
END;
CREATE TRIGGER IF NOT EXISTS rendered_narratives_no_update
BEFORE UPDATE ON rendered_narratives
BEGIN
    SELECT RAISE(ABORT, 'RenderedNarrative immutable');
END;
CREATE TRIGGER IF NOT EXISTS rendered_narratives_no_delete
BEFORE DELETE ON rendered_narratives
BEGIN
    SELECT RAISE(ABORT, 'RenderedNarrative immutable');
END;
"""


def ensure_profile_tables(conn: "sqlite3.Connection") -> None:
    """Idempotently create expression_profiles + rendered_narratives on any open connection.

    Handles three migration scenarios:
    1. Fresh DB: creates both tables from scratch.
    2. v8 DB: has system_prompts + rendered_narratives with system_prompt_id — migrates data.
    3. v9 DB: expression_profiles already exists — no-op.
    """
    ensure_architect_tables(conn)
    conn.executescript(_PROFILE_BASE_DDL)

    # ── Column migrations on rendered_narratives ──────────────────────────────
    rn_cols = {r[1] for r in conn.execute("PRAGMA table_info(rendered_narratives)").fetchall()}

    # v8 → v9: rename system_prompt_id → expression_profile_id
    if "system_prompt_id" in rn_cols and "expression_profile_id" not in rn_cols:
        conn.execute("DROP TRIGGER IF EXISTS rendered_narratives_no_update")
        conn.execute(
            "ALTER TABLE rendered_narratives ADD COLUMN expression_profile_id TEXT REFERENCES expression_profiles(id)"
        )
        conn.execute("UPDATE rendered_narratives SET expression_profile_id = system_prompt_id")

    rn_cols = {r[1] for r in conn.execute("PRAGMA table_info(rendered_narratives)").fetchall()}
    if "expression_profile_id" not in rn_cols:
        conn.execute(
            "ALTER TABLE rendered_narratives ADD COLUMN expression_profile_id TEXT REFERENCES expression_profiles(id)"
        )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rendered_profile ON rendered_narratives(expression_profile_id)"
    )

    # CI-011: execution_config captures full nondeterministic audit record
    rn_cols = {r[1] for r in conn.execute("PRAGMA table_info(rendered_narratives)").fetchall()}
    if "execution_config" not in rn_cols:
        conn.execute(
            "ALTER TABLE rendered_narratives ADD COLUMN execution_config TEXT"
        )

    # CI-013: document scope control — exclude documents from analysis without deleting
    sd_cols = {r[1] for r in conn.execute("PRAGMA table_info(source_documents)").fetchall()}
    if "excluded_from_analysis" not in sd_cols:
        conn.execute(
            "ALTER TABLE source_documents ADD COLUMN excluded_from_analysis INTEGER DEFAULT 0"
        )
    if "source_role" not in sd_cols:
        conn.execute(
            "ALTER TABLE source_documents ADD COLUMN source_role TEXT DEFAULT 'primary'"
        )

    # CI-013b: narrow the source_documents immutability trigger so that scope
    # columns (excluded_from_analysis, source_role) remain updatable while
    # identity fields (id, file_hash, original_filename, registered_at) are still
    # protected. SQLite has no ALTER TRIGGER — must DROP and recreate.
    old_trigger = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='source_documents_no_update'"
    ).fetchone()
    if old_trigger and "WHEN" not in (old_trigger["sql"] or ""):
        conn.execute("DROP TRIGGER IF EXISTS source_documents_no_update")
        conn.execute("""
CREATE TRIGGER source_documents_no_update
BEFORE UPDATE ON source_documents
WHEN NEW.id               != OLD.id
  OR NEW.file_hash        != OLD.file_hash
  OR NEW.original_filename != OLD.original_filename
  OR NEW.registered_at    != OLD.registered_at
BEGIN
    SELECT RAISE(ABORT, 'SourceDocument immutable');
END""")

    conn.commit()

    # CI-012: narrative stewardship — accept/reject with rationale
    rn_cols = {r[1] for r in conn.execute("PRAGMA table_info(rendered_narratives)").fetchall()}
    if "narrative_status" not in rn_cols:
        conn.execute(
            "ALTER TABLE rendered_narratives ADD COLUMN narrative_status TEXT DEFAULT 'pending'"
        )
    if "narrative_rationale" not in rn_cols:
        conn.execute(
            "ALTER TABLE rendered_narratives ADD COLUMN narrative_rationale TEXT"
        )
    conn.commit()

    # CI-014: profile_fidelity column on validation_reports
    vr_cols = {r[1] for r in conn.execute("PRAGMA table_info(validation_reports)").fetchall()}
    if "profile_fidelity" not in vr_cols:
        conn.execute(
            "ALTER TABLE validation_reports ADD COLUMN profile_fidelity TEXT"
        )
    conn.commit()

    # ── Migrate system_prompts → expression_profiles (v8 DBs) ────────────────
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "system_prompts" in tables:
        sp_cols = {r[1] for r in conn.execute("PRAGMA table_info(system_prompts)").fetchall()}
        if "focus" in sp_cols:
            conn.execute("""
                INSERT OR IGNORE INTO expression_profiles
                    (id, slug, name, artist_prompt, critic_expectations, source, created_at, language)
                SELECT id, slug, name, focus, quality_criteria, source, created_at, 'en'
                FROM system_prompts
            """)

    conn.executescript(_PROFILE_IMMUTABILITY_DDL)
    conn.commit()
    # Seed built-in profiles (idempotent — INSERT OR IGNORE)
    from ..narrative.profiles import seed_built_in_profiles
    seed_built_in_profiles(conn)


# Backwards-compat alias used by CLI commands written before v9
ensure_artist_tables = ensure_profile_tables


_CRITIC_DDL = """
CREATE TABLE IF NOT EXISTS validation_reports (
    id                    TEXT PRIMARY KEY,
    rendered_narrative_id TEXT NOT NULL REFERENCES rendered_narratives(id),
    architect_plan_id     TEXT NOT NULL REFERENCES architect_plans(id),
    expression_profile_id TEXT REFERENCES expression_profiles(id),
    semantic_fidelity     REAL NOT NULL,
    required_terms_present TEXT NOT NULL DEFAULT '[]',
    required_terms_missing TEXT NOT NULL DEFAULT '[]',
    unsupported_claims    TEXT NOT NULL DEFAULT '[]',
    omitted_observations  TEXT NOT NULL DEFAULT '[]',
    omitted_interpretations TEXT NOT NULL DEFAULT '[]',
    semantic_drift        TEXT NOT NULL DEFAULT '[]',
    warnings              TEXT NOT NULL DEFAULT '[]',
    approved              INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vr_narrative ON validation_reports(rendered_narrative_id);
CREATE INDEX IF NOT EXISTS idx_vr_plan      ON validation_reports(architect_plan_id);
CREATE TRIGGER IF NOT EXISTS validation_reports_no_update
BEFORE UPDATE ON validation_reports
BEGIN
    SELECT RAISE(ABORT, 'ValidationReport immutable');
END;
CREATE TRIGGER IF NOT EXISTS validation_reports_no_delete
BEFORE DELETE ON validation_reports
BEGIN
    SELECT RAISE(ABORT, 'ValidationReport immutable');
END;
"""


def ensure_critic_tables(conn: "sqlite3.Connection") -> None:
    """Idempotently create validation_reports on any open connection."""
    ensure_profile_tables(conn)
    conn.executescript(_CRITIC_DDL)
    conn.commit()


class SQLiteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()

    def _apply_schema(self) -> None:
        self._conn.executescript(DDL)
        self._conn.executescript(_SUPERSESSION_TRIGGER_MIGRATION)
        self._apply_column_migrations()
        ensure_profile_tables(self._conn)
        from datetime import datetime, timezone
        cur = self._conn.execute("SELECT version FROM schema_version")
        row = cur.fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO schema_version VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()
        elif row[0] != SCHEMA_VERSION:
            # Migrate: DDL is already idempotent (CREATE TABLE IF NOT EXISTS).
            # Only the version record needs updating.
            self._conn.execute(
                "UPDATE schema_version SET version = ?, applied_at = ?",
                (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def _apply_column_migrations(self) -> None:
        """Idempotent column additions for existing databases.

        CREATE TABLE IF NOT EXISTS handles new databases.
        These ALTER TABLE statements handle existing databases that predate a column.
        """
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(interpretations)")}
        if "ai_provenance_id" not in cols:
            self._conn.execute(
                "ALTER TABLE interpretations ADD COLUMN ai_provenance_id TEXT REFERENCES ai_provenance(id)"
            )
            self._conn.commit()
        if "steward_note" not in cols:
            self._conn.execute("ALTER TABLE interpretations ADD COLUMN steward_note TEXT")
            self._conn.commit()

    # --- source_documents ---

    def insert_source_document(self, doc: dict) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO source_documents
                (id, original_filename, file_hash, total_pages, registered_at, compiler_version)
            VALUES
                (:id, :original_filename, :file_hash, :total_pages, :registered_at, :compiler_version)
            """,
            doc,
        )
        self._conn.commit()

    # --- source_extractions (append-only evidence) ---

    def insert_source_extractions_batch(self, rows: list[dict]) -> None:
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO source_extractions
                (id, epistemic_class, document_id, page, region, raw_text,
                 parser, parser_version, coordinates, source_locator,
                 source_hash, hash, extracted_at)
            VALUES
                (:id, :epistemic_class, :document_id, :page, :region, :raw_text,
                 :parser, :parser_version, :coordinates, :source_locator,
                 :source_hash, :hash, :extracted_at)
            """,
            rows,
        )
        self._conn.commit()

    def source_document_exists(self, doc_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM source_documents WHERE id = ?", (doc_id,)
        )
        return cur.fetchone() is not None

    # --- observations (append-only) ---

    def insert_observations_batch(self, rows: list[dict]) -> None:
        prepared = []
        for row in rows:
            r = dict(row)
            r.setdefault("epistemic_class", "Evidence")
            r.setdefault("semantic_hash", make_semantic_hash(r["raw_text"]))
            prepared.append(r)
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO observations
                (id, epistemic_class, source_document_id, source_extraction_id,
                 raw_text, source_locator, semantic_hash,
                 page, paragraph, sentence,
                 preceding_observation_id, following_observation_id, created_at)
            VALUES
                (:id, :epistemic_class, :source_document_id, :source_extraction_id,
                 :raw_text, :source_locator, :semantic_hash,
                 :page, :paragraph, :sentence,
                 :preceding_observation_id, :following_observation_id, :created_at)
            """,
            prepared,
        )
        self._conn.commit()

    def insert_observation_derived_batch(self, rows: list[dict]) -> None:
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO observation_derived
                (observation_id, normalized_text, sentence_tokens, whitespace_map,
                 derivation_version, derived_at)
            VALUES
                (:observation_id, :normalized_text, :sentence_tokens, :whitespace_map,
                 :derivation_version, :derived_at)
            """,
            rows,
        )
        self._conn.commit()

    # --- provenance (append-only) ---

    def insert_provenance_batch(self, rows: list[dict]) -> None:
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO provenance
                (id, observation_id, source_document_id, source_document_hash,
                 source_extraction_id,
                 page, paragraph, sentence, verbatim_text, location_precision,
                 char_offset_start, char_offset_end,
                 bbox_x, bbox_y, bbox_width, bbox_height, bbox_dpi,
                 created_at, compiler_version, compilation_run_id)
            VALUES
                (:id, :observation_id, :source_document_id, :source_document_hash,
                 :source_extraction_id,
                 :page, :paragraph, :sentence, :verbatim_text, :location_precision,
                 :char_offset_start, :char_offset_end,
                 :bbox_x, :bbox_y, :bbox_width, :bbox_height, :bbox_dpi,
                 :created_at, :compiler_version, :compilation_run_id)
            """,
            rows,
        )
        self._conn.commit()

    # --- Field v0.1: term index (append-only) ---

    def insert_terms_batch(self, term_rows: list[dict]) -> None:
        """term_rows: list of {id, term}"""
        self._conn.executemany(
            "INSERT OR IGNORE INTO terms (id, term) VALUES (:id, :term)",
            term_rows,
        )
        self._conn.commit()

    def insert_observation_terms_batch(self, rows: list[dict]) -> None:
        """rows: list of {observation_id, term_id}"""
        self._conn.executemany(
            "INSERT OR IGNORE INTO observation_terms (observation_id, term_id) VALUES (:observation_id, :term_id)",
            rows,
        )
        self._conn.commit()

    def observations_for_term(self, term: str) -> list[dict]:
        """Return all observations that contain the given term (exact token match)."""
        cur = self._conn.execute(
            """
            SELECT o.id, o.page, o.paragraph, o.sentence, o.raw_text,
                   od.normalized_text,
                   o.preceding_observation_id, o.following_observation_id
            FROM observations o
            LEFT JOIN observation_derived od ON od.observation_id = o.id
            JOIN observation_terms ot ON ot.observation_id = o.id
            JOIN terms t ON t.id = ot.term_id
            WHERE t.term = ?
            ORDER BY o.page, o.paragraph, o.sentence
            """,
            (term.lower(),),
        )
        return [dict(row) for row in cur.fetchall()]

    def term_exists(self, term: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM terms WHERE term = ?", (term.lower(),))
        return cur.fetchone() is not None

    def term_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]

    # --- perspectives (append-only registry) ---

    def register_perspective(self, row: dict) -> None:
        """INSERT OR IGNORE — same name always yields the same ID."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO perspectives (id, name, description, created_at)
            VALUES (:id, :name, :description, :created_at)
            """,
            row,
        )
        self._conn.commit()

    def get_perspective_by_name(self, name: str) -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM perspectives WHERE lower(name) = lower(?)", (name,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def all_perspectives(self) -> list[dict]:
        cur = self._conn.execute("SELECT * FROM perspectives ORDER BY name")
        return [dict(r) for r in cur.fetchall()]

    def perspective_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM perspectives").fetchone()[0]

    def interpretations_for_perspective(self, perspective_id: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM interpretations WHERE perspective_id = ? ORDER BY created_at",
            (perspective_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- interpretations (append-only, steward-authored) ---

    def insert_interpretation(self, row: dict) -> None:
        """INSERT OR IGNORE — content-addressable ID prevents silent duplicates."""
        row = {**row, "perspective_id": row.get("perspective_id")}  # default NULL
        self._conn.execute(
            """
            INSERT OR IGNORE INTO interpretations
                (id, observation_id, perspective, perspective_id, text, evidential_status,
                 evidence_observation_ids, confidence, source, created_at)
            VALUES
                (:id, :observation_id, :perspective, :perspective_id, :text, :evidential_status,
                 :evidence_observation_ids, :confidence, :source, :created_at)
            """,
            row,
        )
        self._conn.commit()

    def interpretations_for_observation(self, observation_id: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM interpretations WHERE observation_id = ? ORDER BY created_at",
            (observation_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def interpretation_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM interpretations").fetchone()[0]

    # --- narrative_blueprints (append-only, steward-authored) ---

    def insert_blueprint(self, row: dict, obs_ids: list[str], interp_ids: list[str]) -> None:
        """Atomically insert a blueprint and populate both link tables."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO narrative_blueprints
                (id, title, thesis, sections, source, created_at)
            VALUES
                (:id, :title, :thesis, :sections, :source, :created_at)
            """,
            row,
        )
        self._conn.executemany(
            "INSERT OR IGNORE INTO blueprint_observation_links (blueprint_id, observation_id) VALUES (?, ?)",
            [(row["id"], oid) for oid in set(obs_ids)],
        )
        self._conn.executemany(
            "INSERT OR IGNORE INTO blueprint_interpretation_links (blueprint_id, interpretation_id) VALUES (?, ?)",
            [(row["id"], iid) for iid in set(interp_ids)],
        )
        self._conn.commit()

    def blueprints_for_observation(self, observation_id: str) -> list[dict]:
        """Return all blueprints that cite this observation in any section."""
        cur = self._conn.execute(
            """
            SELECT nb.* FROM narrative_blueprints nb
            JOIN blueprint_observation_links bol ON bol.blueprint_id = nb.id
            WHERE bol.observation_id = ?
            ORDER BY nb.created_at
            """,
            (observation_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def all_blueprints(self) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM narrative_blueprints ORDER BY created_at"
        )
        return [dict(r) for r in cur.fetchall()]

    def blueprint_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM narrative_blueprints").fetchone()[0]

    # --- supersession_relations (append-only) ---

    def insert_supersession_relation(self, row: dict) -> None:
        """Append a SupersessionRelation without mutating either endpoint."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO supersession_relations
                (old_id, new_id, reason, ratified_at)
            VALUES
                (:old_id, :new_id, :reason, :ratified_at)
            """,
            row,
        )
        self._conn.commit()

    def supersessions_from(self, old_id: str) -> list[dict]:
        cur = self._conn.execute(
            """
            SELECT * FROM supersession_relations
            WHERE old_id = ?
            ORDER BY ratified_at, new_id
            """,
            (old_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def supersessions_to(self, new_id: str) -> list[dict]:
        cur = self._conn.execute(
            """
            SELECT * FROM supersession_relations
            WHERE new_id = ?
            ORDER BY ratified_at, old_id
            """,
            (new_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def supersession_descendants(self, root_id: str) -> list[dict]:
        """Return every supersession edge reachable from root_id."""
        cur = self._conn.execute(
            """
            WITH RECURSIVE chain(depth, old_id, new_id, reason, ratified_at, path) AS (
                SELECT
                    1,
                    old_id,
                    new_id,
                    reason,
                    ratified_at,
                    '|' || old_id || '|' || new_id || '|'
                FROM supersession_relations
                WHERE old_id = ?

                UNION ALL

                SELECT
                    chain.depth + 1,
                    sr.old_id,
                    sr.new_id,
                    sr.reason,
                    sr.ratified_at,
                    chain.path || sr.new_id || '|'
                FROM supersession_relations sr
                JOIN chain ON sr.old_id = chain.new_id
                WHERE instr(chain.path, '|' || sr.new_id || '|') = 0
            )
            SELECT depth, old_id, new_id, reason, ratified_at
            FROM chain
            ORDER BY depth, ratified_at, old_id, new_id
            """,
            (root_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def supersession_relation_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM supersession_relations").fetchone()[0]

    # --- reads ---

    def count_observations(self, source_document_id: str | None = None) -> int:
        if source_document_id:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM observations WHERE source_document_id = ?",
                (source_document_id,),
            )
        else:
            cur = self._conn.execute("SELECT COUNT(*) FROM observations")
        return cur.fetchone()[0]

    def all_observations(self, source_document_id: str | None = None) -> list[dict]:
        if source_document_id:
            cur = self._conn.execute(
                "SELECT * FROM observations WHERE source_document_id = ? "
                "ORDER BY page, paragraph, sentence",
                (source_document_id,),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM observations ORDER BY page, paragraph, sentence"
            )
        return [dict(row) for row in cur.fetchall()]

    def all_observations_with_derived(self, source_document_id: str | None = None) -> list[dict]:
        """Return observations joined to disposable derived metadata."""
        if source_document_id:
            cur = self._conn.execute(
                """
                SELECT o.*, od.normalized_text, od.sentence_tokens, od.whitespace_map
                FROM observations o
                LEFT JOIN observation_derived od ON od.observation_id = o.id
                WHERE o.source_document_id = ?
                ORDER BY o.page, o.paragraph, o.sentence
                """,
                (source_document_id,),
            )
        else:
            cur = self._conn.execute(
                """
                SELECT o.*, od.normalized_text, od.sentence_tokens, od.whitespace_map
                FROM observations o
                LEFT JOIN observation_derived od ON od.observation_id = o.id
                ORDER BY o.page, o.paragraph, o.sentence
                """
            )
        return [dict(row) for row in cur.fetchall()]

    def all_source_extractions(self, source_document_id: str | None = None) -> list[dict]:
        if source_document_id:
            cur = self._conn.execute(
                "SELECT * FROM source_extractions WHERE document_id = ? "
                "ORDER BY page, source_locator",
                (source_document_id,),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM source_extractions ORDER BY page, source_locator"
            )
        return [dict(row) for row in cur.fetchall()]

    def all_provenance(self, source_document_id: str | None = None) -> list[dict]:
        if source_document_id:
            cur = self._conn.execute(
                "SELECT p.* FROM provenance p "
                "WHERE p.source_document_id = ? "
                "ORDER BY p.page, p.paragraph, p.sentence",
                (source_document_id,),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM provenance ORDER BY page, paragraph, sentence"
            )
        return [dict(row) for row in cur.fetchall()]

    def get_source_document(self, doc_id: str) -> dict | None:
        cur = self._conn.execute(
            "SELECT * FROM source_documents WHERE id = ?", (doc_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def set_document_scope(
        self,
        doc_id: str,
        *,
        excluded: bool | None = None,
        source_role: str | None = None,
    ) -> dict | None:
        """Update stewardship metadata on a source_document (scope, role).

        Only non-None arguments are updated. Returns the updated row, or None
        if the document does not exist. Raises ValueError for invalid role.

        This is the only permitted UPDATE path for source_documents. Evidence
        content (raw_text, page, paragraph, sentence) is immutable — only the
        stewardship columns (excluded_from_analysis, source_role) may change.
        """
        _VALID_ROLES = {"primary", "reference", "notes", "commentary", "exploratory", "excluded"}
        if source_role is not None and source_role not in _VALID_ROLES:
            raise ValueError(f"invalid source_role: {source_role!r}")

        row = self._conn.execute(
            "SELECT id FROM source_documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            return None

        updates: list[str] = []
        params: list = []
        if excluded is not None:
            updates.append("excluded_from_analysis = ?")
            params.append(1 if excluded else 0)
        if source_role is not None:
            updates.append("source_role = ?")
            params.append(source_role)

        if updates:
            params.append(doc_id)
            self._conn.execute(
                f"UPDATE source_documents SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            self._conn.commit()

        return self.get_source_document(doc_id)

    def all_ordered_observation_ids(self) -> list[str]:
        """Return all observation IDs ordered by (page, paragraph, sentence)."""
        cur = self._conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        )
        return [r[0] for r in cur.fetchall()]

    def get_observation_by_id(self, obs_id: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM observations WHERE id = ?", (obs_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    # --- architect_plans (append-only, deterministic) ---

    def insert_architect_plan(self, plan_row: dict, paragraph_rows: list[dict]) -> None:
        """Atomically insert a plan and its ordered paragraphs."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO architect_plans
                (id, blueprint_id, blueprint_hash, title, source, created_at)
            VALUES
                (:id, :blueprint_id, :blueprint_hash, :title, :source, :created_at)
            """,
            plan_row,
        )
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO architect_plan_paragraphs
                (plan_id, order_idx, purpose, blueprint_section,
                 required_observations, required_interpretations,
                 required_terms, forbidden_claims, notes)
            VALUES
                (:plan_id, :order_idx, :purpose, :blueprint_section,
                 :required_observations, :required_interpretations,
                 :required_terms, :forbidden_claims, :notes)
            """,
            paragraph_rows,
        )
        self._conn.commit()

    def architect_plan_for_blueprint(self, blueprint_id: str) -> dict | None:
        """Return the most recent ArchitectPlan for a given Blueprint, with its paragraphs."""
        row = self._conn.execute(
            "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
            (blueprint_id,),
        ).fetchone()
        if row is None:
            return None
        plan = dict(row)
        paras = self._conn.execute(
            "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
            (plan["id"],),
        ).fetchall()
        plan["paragraphs"] = [dict(p) for p in paras]
        return plan

    def architect_plan_count(self) -> int:
        try:
            return self._conn.execute("SELECT COUNT(*) FROM architect_plans").fetchone()[0]
        except Exception:
            return 0

    # --- expression_profiles ---

    def insert_expression_profile(self, row: dict) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO expression_profiles
                (id, slug, name, description, language, audience, reading_level,
                 tone, voice, artist_prompt, critic_expectations, source, created_at)
            VALUES
                (:id, :slug, :name, :description, :language, :audience, :reading_level,
                 :tone, :voice, :artist_prompt, :critic_expectations, :source, :created_at)
            """,
            row,
        )
        self._conn.commit()

    def expression_profile_by_slug(self, slug: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM expression_profiles WHERE slug = ?", (slug,)
        ).fetchone()
        return dict(row) if row else None

    def all_expression_profiles(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM expression_profiles ORDER BY source DESC, language ASC, name ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def expression_profile_count(self) -> int:
        try:
            return self._conn.execute("SELECT COUNT(*) FROM expression_profiles").fetchone()[0]
        except Exception:
            return 0

    # --- rendered_narratives (append-only, artist-produced) ---

    def insert_rendered_narrative(self, row: dict) -> None:
        # Accept both old (system_prompt_id) and new (expression_profile_id) key names
        if "system_prompt_id" in row and "expression_profile_id" not in row:
            row = dict(row, expression_profile_id=row["system_prompt_id"])
        row = {**row, "execution_config": row.get("execution_config")}
        self._conn.execute(
            """
            INSERT OR IGNORE INTO rendered_narratives
                (id, architect_plan_id, provider, expression_profile_id, text,
                 prompt_used, execution_config, created_at)
            VALUES
                (:id, :architect_plan_id, :provider, :expression_profile_id, :text,
                 :prompt_used, :execution_config, :created_at)
            """,
            row,
        )
        self._conn.commit()

    def rendered_narrative_for_plan(
        self,
        plan_id: str,
        provider: str | None = None,
        expression_profile_id: str | None = None,
        system_prompt_id: str | None = None,  # backwards compat
    ) -> dict | None:
        profile_id = expression_profile_id or system_prompt_id
        clauses = ["architect_plan_id = ?"]
        params: list = [plan_id]
        if provider is not None:
            clauses.append("provider = ?")
            params.append(provider)
        if profile_id is not None:
            clauses.append("expression_profile_id = ?")
            params.append(profile_id)
        row = self._conn.execute(
            f"SELECT * FROM rendered_narratives WHERE {' AND '.join(clauses)} "
            "ORDER BY created_at DESC LIMIT 1",
            params,
        ).fetchone()
        return dict(row) if row else None

    def rendered_narratives_for_plan(self, plan_id: str) -> list[dict]:
        """All rendered narratives for a given architect plan (all profiles)."""
        rows = self._conn.execute(
            "SELECT rn.*, ep.name AS profile_name, ep.slug AS profile_slug, ep.language AS profile_language "
            "FROM rendered_narratives rn "
            "LEFT JOIN expression_profiles ep ON ep.id = rn.expression_profile_id "
            "WHERE rn.architect_plan_id = ? ORDER BY rn.created_at",
            (plan_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def rendered_narrative_count(self) -> int:
        try:
            return self._conn.execute("SELECT COUNT(*) FROM rendered_narratives").fetchone()[0]
        except Exception:
            return 0

    # --- validation_reports (Critic output, append-only) ---

    def insert_validation_report(self, row: dict) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO validation_reports
                (id, rendered_narrative_id, architect_plan_id, expression_profile_id,
                 semantic_fidelity, required_terms_present, required_terms_missing,
                 unsupported_claims, omitted_observations, omitted_interpretations,
                 semantic_drift, warnings, approved, created_at)
            VALUES
                (:id, :rendered_narrative_id, :architect_plan_id, :expression_profile_id,
                 :semantic_fidelity, :required_terms_present, :required_terms_missing,
                 :unsupported_claims, :omitted_observations, :omitted_interpretations,
                 :semantic_drift, :warnings, :approved, :created_at)
            """,
            row,
        )
        self._conn.commit()

    def validation_report_for_narrative(self, rendered_narrative_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM validation_reports WHERE rendered_narrative_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (rendered_narrative_id,),
        ).fetchone()
        return dict(row) if row else None

    def validation_report_count(self) -> int:
        try:
            return self._conn.execute("SELECT COUNT(*) FROM validation_reports").fetchone()[0]
        except Exception:
            return 0

    # --- critic_reports (Sprint E9, operational artifact — not yet canonical) ---

    def insert_critic_report(self, row: dict) -> None:
        """Write a CriticReport. Immutable and permanent once written. INSERT OR IGNORE is idempotent."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO critic_reports
                (id, proposal_id, observation_id, policy, claims,
                 evidence_passages, overall_verdict, normalized,
                 normalization_notes, generated_at, created_at)
            VALUES
                (:id, :proposal_id, :observation_id, :policy, :claims,
                 :evidence_passages, :overall_verdict, :normalized,
                 :normalization_notes, :generated_at, :created_at)
            """,
            row,
        )
        self._conn.commit()

    def get_critic_report(self, report_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM critic_reports WHERE id = ?", (report_id,)
        ).fetchone()
        return dict(row) if row else None

    def critic_reports_for_proposal(self, proposal_id: str) -> list[dict]:
        """All CriticReports for a given ProposedInterpretation, ordered by generated_at."""
        rows = self._conn.execute(
            "SELECT * FROM critic_reports WHERE proposal_id = ? ORDER BY generated_at, policy",
            (proposal_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def latest_critic_report_for_proposal(self, proposal_id: str, policy: str | None = None) -> dict | None:
        """Most recent CriticReport for a proposal, optionally filtered by policy."""
        if policy is not None:
            row = self._conn.execute(
                "SELECT * FROM critic_reports WHERE proposal_id = ? AND policy = ? "
                "ORDER BY generated_at DESC LIMIT 1",
                (proposal_id, policy),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM critic_reports WHERE proposal_id = ? "
                "ORDER BY generated_at DESC LIMIT 1",
                (proposal_id,),
            ).fetchone()
        return dict(row) if row else None

    def mark_critic_report_normalized(self, report_id: str, normalization_notes: str) -> None:
        """Record that a steward has reviewed the claim set. Sets normalized=1 and records notes.

        This is the only mutable field on critic_reports. All core fields are immutable.
        """
        self._conn.execute(
            "UPDATE critic_reports SET normalized = 1, normalization_notes = ? WHERE id = ?",
            (normalization_notes, report_id),
        )
        self._conn.commit()

    def critic_report_count(self) -> int:
        try:
            return self._conn.execute("SELECT COUNT(*) FROM critic_reports").fetchone()[0]
        except Exception:
            return 0

    # --- findings (ADR-0041 Evaluation Functions, append-only) ---

    def insert_findings_batch(self, rows: list[dict]) -> None:
        """Atomically insert a batch of Findings. INSERT OR IGNORE — idempotent."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO findings
                (id, rendered_narrative_id, architect_plan_id, dimension,
                 obligation_id, operation, status, evidence,
                 evaluation_method, constitution_version, created_at)
            VALUES
                (:id, :rendered_narrative_id, :architect_plan_id, :dimension,
                 :obligation_id, :operation, :status, :evidence,
                 :evaluation_method, :constitution_version, :created_at)
            """,
            rows,
        )
        self._conn.commit()

    def findings_for_narrative(self, rendered_narrative_id: str, dimension: str | None = None) -> list[dict]:
        """Return all Findings for a given RenderedNarrative, optionally filtered by dimension."""
        if dimension is not None:
            rows = self._conn.execute(
                "SELECT * FROM findings WHERE rendered_narrative_id = ? AND dimension = ? ORDER BY created_at",
                (rendered_narrative_id, dimension),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM findings WHERE rendered_narrative_id = ? ORDER BY dimension, created_at",
                (rendered_narrative_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def finding_count(self) -> int:
        try:
            return self._conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        except Exception:
            return 0

    def get_finding_lineage(self, finding_id: str) -> dict | None:
        """Traverse the full ancestry chain from a Finding back to the SourceDocument.

        Returns a dict with keys: finding, rendered_narrative, architect_plan,
        blueprint, observations, source_extractions, source_documents.
        Returns None if the finding does not exist.
        """
        finding = self._conn.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        if finding is None:
            return None
        finding = dict(finding)

        narrative = self._conn.execute(
            "SELECT * FROM rendered_narratives WHERE id = ?",
            (finding["rendered_narrative_id"],),
        ).fetchone()

        plan = self._conn.execute(
            "SELECT * FROM architect_plans WHERE id = ?",
            (finding["architect_plan_id"],),
        ).fetchone()

        blueprint = None
        observations: list[dict] = []
        source_extractions: list[dict] = []
        source_documents: list[dict] = []

        if plan:
            blueprint = self._conn.execute(
                "SELECT * FROM narrative_blueprints WHERE id = ?",
                (dict(plan)["blueprint_id"],),
            ).fetchone()

        if blueprint:
            obs_rows = self._conn.execute(
                "SELECT o.* FROM observations o "
                "JOIN blueprint_observation_links bol ON bol.observation_id = o.id "
                "WHERE bol.blueprint_id = ?",
                (dict(blueprint)["id"],),
            ).fetchall()
            observations = [dict(r) for r in obs_rows]

            extraction_ids = {r["source_extraction_id"] for r in observations}
            for eid in extraction_ids:
                row = self._conn.execute(
                    "SELECT * FROM source_extractions WHERE id = ?", (eid,)
                ).fetchone()
                if row:
                    source_extractions.append(dict(row))

            doc_ids = {r["document_id"] for r in source_extractions}
            for did in doc_ids:
                row = self._conn.execute(
                    "SELECT * FROM source_documents WHERE id = ?", (did,)
                ).fetchone()
                if row:
                    source_documents.append(dict(row))

        return {
            "finding": finding,
            "rendered_narrative": dict(narrative) if narrative else None,
            "architect_plan": dict(plan) if plan else None,
            "blueprint": dict(blueprint) if blueprint else None,
            "observations": observations,
            "source_extractions": source_extractions,
            "source_documents": source_documents,
        }

    # --- ratification_records (append-only, immutable) ---

    def insert_ratification_record(self, record: dict) -> None:
        """Append a RatificationRecord. Immutable once written. INSERT OR IGNORE is idempotent."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO ratification_records
                (id, rendered_narrative_id, ratified_by, ratified_at,
                 steward_declaration, finding_count, steward_decision_count,
                 witness_session_count, constitution_version, audit_snapshot, created_at)
            VALUES
                (:id, :rendered_narrative_id, :ratified_by, :ratified_at,
                 :steward_declaration, :finding_count, :steward_decision_count,
                 :witness_session_count, :constitution_version, :audit_snapshot, :created_at)
            """,
            record,
        )
        self._conn.commit()

    def ratification_records_for_narrative(self, rendered_narrative_id: str) -> list[dict]:
        """All RatificationRecords for a RenderedNarrative, oldest first."""
        cur = self._conn.execute(
            "SELECT * FROM ratification_records WHERE rendered_narrative_id = ? ORDER BY ratified_at, created_at",
            (rendered_narrative_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def all_ratification_records(self) -> list[dict]:
        """All RatificationRecords across all narratives, oldest first."""
        cur = self._conn.execute(
            "SELECT * FROM ratification_records ORDER BY ratified_at, created_at"
        )
        return [dict(r) for r in cur.fetchall()]

    def ratification_record_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM ratification_records").fetchone()[0]

    # --- witness_sessions (append-only, immutable) ---

    def insert_witness_session(self, session: dict) -> None:
        """Append a WitnessSession. Immutable once written. INSERT OR IGNORE is idempotent."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO witness_sessions
                (id, rendered_narrative_id, witness_profile, task_description,
                 task_completed, notes, facilitated_by, session_date,
                 constitution_version, created_at)
            VALUES
                (:id, :rendered_narrative_id, :witness_profile, :task_description,
                 :task_completed, :notes, :facilitated_by, :session_date,
                 :constitution_version, :created_at)
            """,
            session,
        )
        self._conn.commit()

    def sessions_for_narrative(self, rendered_narrative_id: str) -> list[dict]:
        """All WitnessSessions for a RenderedNarrative, oldest first."""
        cur = self._conn.execute(
            "SELECT * FROM witness_sessions WHERE rendered_narrative_id = ? ORDER BY session_date, created_at",
            (rendered_narrative_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def sessions_for_profile(self, witness_profile: str) -> list[dict]:
        """All WitnessSessions for a given audience profile across all narratives."""
        cur = self._conn.execute(
            "SELECT * FROM witness_sessions WHERE witness_profile = ? ORDER BY session_date, created_at",
            (witness_profile,),
        )
        return [dict(r) for r in cur.fetchall()]

    def witness_session_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM witness_sessions").fetchone()[0]

    # --- steward_decisions (append-only, immutable) ---

    def insert_steward_decision(self, decision: dict) -> None:
        """Append a StewardDecision. Immutable once written. INSERT OR IGNORE is idempotent."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO steward_decisions
                (id, finding_id, verdict, rationale, steward_id,
                 decided_at, constitution_version, created_at)
            VALUES
                (:id, :finding_id, :verdict, :rationale, :steward_id,
                 :decided_at, :constitution_version, :created_at)
            """,
            decision,
        )
        self._conn.commit()

    def decisions_for_finding(self, finding_id: str) -> list[dict]:
        """All StewardDecisions that govern a specific Finding, oldest first."""
        cur = self._conn.execute(
            "SELECT * FROM steward_decisions WHERE finding_id = ? ORDER BY decided_at, created_at",
            (finding_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def decisions_for_narrative(self, rendered_narrative_id: str) -> list[dict]:
        """All StewardDecisions governing Findings produced from a RenderedNarrative."""
        cur = self._conn.execute(
            """
            SELECT sd.* FROM steward_decisions sd
            JOIN findings f ON f.id = sd.finding_id
            WHERE f.rendered_narrative_id = ?
            ORDER BY sd.decided_at, sd.created_at
            """,
            (rendered_narrative_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def steward_decision_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM steward_decisions").fetchone()[0]

    # --- ai_provenance (Sprint E8, ADR-0009) ---

    def insert_ai_provenance(self, record: dict) -> None:
        """Write a new AIProvenance record at generation time.

        Acceptance fields (accepting_steward, acceptance_timestamp, acceptance_rationale)
        should be None at creation. They are populated by complete_ai_provenance_acceptance().
        """
        self._conn.execute(
            """
            INSERT OR IGNORE INTO ai_provenance
                (id, staged_object_id, generating_model, model_version,
                 generation_timestamp, prompt_reference, prompt_reference_type,
                 parent_object_ids, generation_parameters, schema_version,
                 accepting_steward, acceptance_timestamp, acceptance_rationale,
                 created_at)
            VALUES
                (:id, :staged_object_id, :generating_model, :model_version,
                 :generation_timestamp, :prompt_reference, :prompt_reference_type,
                 :parent_object_ids, :generation_parameters, :schema_version,
                 :accepting_steward, :acceptance_timestamp, :acceptance_rationale,
                 :created_at)
            """,
            record,
        )
        self._conn.commit()

    def complete_ai_provenance_acceptance(
        self,
        ai_provenance_id: str,
        accepting_steward: str,
        acceptance_timestamp: str,
        acceptance_rationale: str | None,
    ) -> None:
        """Populate acceptance fields. May only be called once per record (trigger enforced)."""
        self._conn.execute(
            """
            UPDATE ai_provenance
               SET accepting_steward    = ?,
                   acceptance_timestamp = ?,
                   acceptance_rationale = ?
             WHERE id = ?
            """,
            (accepting_steward, acceptance_timestamp, acceptance_rationale, ai_provenance_id),
        )
        self._conn.commit()

    def get_ai_provenance(self, ai_provenance_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM ai_provenance WHERE id = ?", (ai_provenance_id,)
        ).fetchone()
        return dict(row) if row else None

    def ai_provenance_for_staged_object(self, staged_object_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM ai_provenance WHERE staged_object_id = ?", (staged_object_id,)
        ).fetchone()
        return dict(row) if row else None

    # --- proposed_interpretations (Sprint E8, ADR-0009) ---

    def insert_proposed_interpretation(self, proposal: dict) -> None:
        """Write a proposed interpretation to staging. Status starts as 'pending'."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO proposed_interpretations
                (id, observation_id, perspective, perspective_id, text,
                 evidential_status, evidence_observation_ids, ai_provenance_id,
                 status, steward_id, decided_at, steward_rationale, created_at)
            VALUES
                (:id, :observation_id, :perspective, :perspective_id, :text,
                 :evidential_status, :evidence_observation_ids, :ai_provenance_id,
                 :status, :steward_id, :decided_at, :steward_rationale, :created_at)
            """,
            proposal,
        )
        self._conn.commit()

    def get_proposed_interpretation(self, proposal_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM proposed_interpretations WHERE id = ?", (proposal_id,)
        ).fetchone()
        return dict(row) if row else None

    def decide_proposed_interpretation(
        self,
        proposal_id: str,
        status: str,
        steward_id: str,
        decided_at: str,
        steward_rationale: str,
    ) -> None:
        """Transition a proposal from pending to accepted or rejected.

        Status transition is enforced by trigger: once accepted or rejected,
        the status is immutable.
        """
        self._conn.execute(
            """
            UPDATE proposed_interpretations
               SET status           = ?,
                   steward_id       = ?,
                   decided_at       = ?,
                   steward_rationale = ?
             WHERE id = ?
            """,
            (status, steward_id, decided_at, steward_rationale, proposal_id),
        )
        self._conn.commit()

    def pending_proposed_interpretations(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM proposed_interpretations WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def proposed_interpretations_for_observation(self, observation_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM proposed_interpretations WHERE observation_id = ? ORDER BY created_at",
            (observation_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def all_proposed_interpretations(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM proposed_interpretations ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def proposed_interpretation_count(self, status: str | None = None) -> int:
        if status is None:
            return self._conn.execute("SELECT COUNT(*) FROM proposed_interpretations").fetchone()[0]
        return self._conn.execute(
            "SELECT COUNT(*) FROM proposed_interpretations WHERE status = ?", (status,)
        ).fetchone()[0]

    # --- interpretations: ai_provenance_id-aware insertion (Sprint E8) ---

    def insert_interpretation_with_provenance(self, interp: dict) -> None:
        """Insert a canonical interpretation that carries ai_provenance_id.

        Used when a proposed interpretation is accepted by a steward.
        INSERT OR IGNORE: if identical content was already canonicalized (human-authored
        or prior AI acceptance), the existing row takes precedence.
        """
        self._conn.execute(
            """
            INSERT OR IGNORE INTO interpretations
                (id, observation_id, perspective, perspective_id, text,
                 evidential_status, evidence_observation_ids,
                 confidence, source, ai_provenance_id, created_at)
            VALUES
                (:id, :observation_id, :perspective, :perspective_id, :text,
                 :evidential_status, :evidence_observation_ids,
                 :confidence, :source, :ai_provenance_id, :created_at)
            """,
            interp,
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def backup_to(self, destination: str | Path) -> None:
        """Copy the live SQLite database safely, including WAL state."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._conn.commit()
        with sqlite3.connect(str(destination)) as out:
            self._conn.backup(out)
