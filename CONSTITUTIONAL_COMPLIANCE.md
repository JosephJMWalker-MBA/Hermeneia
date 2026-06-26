# Constitutional Compliance

Living audit of the sixteen constitutional invariants defined in
[`docs/02_Constitutional_Invariants.md`](docs/02_Constitutional_Invariants.md).

---

## How to read this table

| Symbol | Meaning |
|---|---|
| ✅ | Verified — passing test cited |
| ⚠️ | Partial — some coverage, gaps noted |
| ❌ | Pending — no verifying test yet |

**Proof types** (from highest to lowest confidence):

| Type | Description |
|---|---|
| **Mechanical** | Schema trigger or structural constraint — cannot be bypassed at runtime |
| **Static** | Source analysis (grep/AST) — proves a dependency cannot exist |
| **Property** | Deterministic function tested against known inputs |
| **Dynamic** | Runtime observation (e.g., DB hash before/after) |
| **Audit** | Lineage traversal from artifact back to source |
| **Documentation** | Written constraint, not yet executable |

Update this file when a test is written or an invariant status changes.
The evidence column must cite a specific test or storage mechanism, not a general claim.

---

## Constitutional Invariants (CI-001 – CI-016)

| Invariant | Title | Status | Proof Type | Confidence | Automation | Verified By | Evidence | Ratified |
|---|---|---|---|---|---|---|---|---|
| CI-001 | Source Artifact Integrity | ⚠️ | Property + Dynamic | High | Partial | `test_ci001_ci002_ci003_compiler_persists_evidence_chain` (needs gatsby.pdf) | `doc["id"] == sha256_file(GATSBY_PDF)` | — |
| CI-002 | Exact Source Extraction | ✅ | Property | High | Full | `test_ci002_source_extraction_preserves_exact_parser_text` | `rows[0].row["raw_text"] == raw` — no normalization before persistence | 2026-06-19 |
| CI-003 | Observation Fidelity | ⚠️ | Property + Dynamic | High | Partial | `test_ci001_ci002_ci003_compiler_persists_evidence_chain` (needs gatsby.pdf) | Chain: `obs["source_extraction_id"] == extraction["id"]` | — |
| CI-004 | Occurrence Identity | ✅ | Property | Mechanical | Full | `test_ci004_observation_identity_is_occurrence_based`, `test_ci004_observation_identity_ignores_normalization` | Same locator + text → same ID; different locator → different ID | 2026-06-19 |
| CI-005 | Immutable Persistence | ✅ | Mechanical | Mechanical | Full | `test_ci005_database_rejects_update_delete_for_immutable_evidence` | SQLite triggers raise `ABORT` on UPDATE/DELETE for all evidence tables | 2026-06-19 |
| CI-006 | Strict Ancestry | ✅ | Mechanical + Dynamic | Full | Full | `test_ci006_foreign_keys_enforced_on_each_layer`, `test_ci006_full_ancestry_chain_traversable` | FK constraints reject dangling parents at every layer; full chain traversal confirmed leaf → root | 2026-06-19 |
| CI-007 | Downward Non-Interference | ✅ | Static | High | Full | `test_ci007_narrative_layer_cannot_write_evidence_tables` | Source scan of `hermeneia/web/` and `hermeneia/cli/` — zero writes to evidence tables outside permitted ingest path | 2026-06-19 |
| CI-008 | Plural Interpretation | ✅ | Dynamic | Full | Full | `test_ci008_multiple_interpretations_coexist_per_observation` | Three independent perspectives inserted for one observation; all three survive and are independently retrievable | 2026-06-19 |
| CI-009 | Contract Dominance | ✅ | Property + Static | High | Full | `test_ci009_architect_plan_id_is_content_addressable`, `test_inv_xi_critic_source_only_writes_validation_reports` | Plan ID is content-addressable (same blueprint → same ID, INSERT OR IGNORE prevents overwrite); Critic static scan confirms write scope | 2026-06-19 |
| CI-010 | Deterministic Reproduction | ⚠️ | Property | High | Partial | `test_field_v01__index_is_deterministic_across_runs`, `test_append_only__insert_or_ignore_is_idempotent` | Covers term index and observation recompile; Architect/Critic round-trip test pending | — |
| CI-011 | Nondeterministic Audit Record | ✅ | Property + Schema | Mechanical | Full | `test_ci011_execution_config_schema` | `execution_config` on `rendered_narratives`; all providers return `{provider, model_id, sdk_version, request_schema_version, execution_timestamp, constitutional_profile: {constitution_version, authority_index_version, invariant_profile, architecture_profile}}` | 2026-06-19 |
| CI-012 | Side-Effect-Free Reads | ⚠️ | Dynamic | High | Partial | `test_ci012_web_get_requests_do_not_mutate_database` (needs gatsby.pdf) | SHA256 of DB file + row counts unchanged after representative GET requests | — |
| CI-013 | Singular Portable Format | ⚠️ | Dynamic | High | Partial | `test_ci013_compiler_emits_constitutional_bundle_shape` (needs gatsby.pdf) | `context.json` schema validated; competing format check pending | — |
| CI-014 | Monotonic Supersession | ✅ | Mechanical + Dynamic | High | Full | `test_ci014_supersession_preserves_original_object`, `test_ci014_supersession_relation_is_append_only`, `test_ci014_multiple_competing_supersessions_coexist`, `test_ci014_full_supersession_chain_is_traversable` | `supersession_relations` appends `old_id → new_id` relations only; triggers reject UPDATE/DELETE; competing descendants coexist; historical chains traverse root → leaf | 2026-06-20 |
| CI-015 | Anti-Helpfulness Compliance | ✅ | Static + Dynamic + Mechanical | High | Full | `test_ci015_source_extraction_preserves_pathological_parser_text_exactly`, `test_ci015_observation_raw_text_partitions_source_without_normalization`, `test_ci015_normalization_storage_only_in_observation_derived`, `test_ci015_pathological_pdf_source_extractions_equal_parser_output`, `test_ci015_no_downstream_layer_rewrites_evidence_static`, `test_ci015_no_pre_source_extraction_text_repair_helpers_static` | SourceExtraction equals parser output; Observation stores raw text only; normalization exists only in `observation_derived`; pathological PDF parser output is persisted exactly; downstream layers have no evidence writes; parser/extraction compiler contain no text-repair helpers | 2026-06-20 |
| CI-016 | Derived Artifact Disposability | ✅ | Dynamic | High | Full | `test_ci016_observation_derived_is_disposable` | DELETE from `observation_derived` leaves parent observation intact | 2026-06-19 |

---

## Pipeline Invariants (INV-06 – INV-XIV)

Ratified during Architecture Freeze v1.0.
See [`docs/04_Invariants.md`](docs/04_Invariants.md).

| Invariant | Title | Status | Proof Type | Confidence | Automation | Verified By | Evidence |
|---|---|---|---|---|---|---|---|
| INV-06 | Immutability of All Pipeline Artifacts | ✅ | Mechanical | Mechanical | Full | `test_ci005_database_rejects_update_delete_for_immutable_evidence` | `INSERT OR IGNORE` enforced; triggers reject mutation on evidence tables |
| INV-07 | Content-Addressable Identity | ✅ | Property | Mechanical | Full | `test_sha_registration__observation_id_matches_formula` | Every stored observation ID verified against sha256 formula across all rows |
| INV-08 | LLM Isolation | ✅ | Static | Mechanical | Full | `test_inv08_compiler_layer_contains_no_llm_imports` | Source scan of `hermeneia/compiler/` and `hermeneia/storage/` — zero LLM client imports |
| INV-09 | Architect Invariance Across Profiles | ✅ | Property | Full | Full | `test_inv09_same_blueprint_produces_same_plan_id_regardless_of_profile` | `compile_architect_plan` called twice on same blueprint; IDs match; `make_architect_plan_id` is deterministic | 2026-06-19 |
| INV-10 | Critic Determinism | ✅ | Property | Full | Full | `test_inv10_validation_report_id_is_deterministic` | `make_validation_report_id` is idempotent; duplicate INSERT is silently ignored; original score survives | 2026-06-19 |
| INV-XI | Critic Authority Boundary | ✅ | Static | Full | Full | `test_inv_xi_critic_source_only_writes_validation_reports` | Source scan of `critic_cmd.py` and `compiler/critic.py` — zero writes to any table other than `validation_reports` | 2026-06-19 |
| INV-XII | Stewardship Produces New Artifacts Only | ✅ | Mechanical | Mechanical | Full | Schema + triggers | No `UPDATE`/`DELETE` on pipeline tables; all writes use `INSERT OR IGNORE` |
| INV-XIII | Steward Context Shall Not Determine Semantic Standing | ✅ | Static | High | Full | `test_inv_xiii_steward_credentials_do_not_drive_semantic_standing` | Source scan of decision surfaces confirms steward credential/status fields do not feed sort, filter, ranking, suppression, or scoring logic |
| INV-XIV | Artist Provider Interchangeability | ✅ | Property | High | Partial | `test_ci011_execution_config_schema` + Protocol | All providers implement `ArtistProvider` Protocol including `execution_config()`; provider isolation test pending |

---

## CI/CD Gate (P0-A2)

A future CI check shall enforce that every invariant marked ✅ in this file has a
corresponding passing test. The document is a contract, not a narrative.

Proposed enforcement: a test that parses this file, extracts all `✅` rows, derives the
`Verified By` test name, and asserts that test exists and passes. A `✅` with no
corresponding test is a constitutional compliance violation.

Until that gate exists, this document is maintained by discipline. After it exists,
it is maintained by the pipeline.

---

## P0 Exit Criterion

> Given the same source document, Hermeneia preserves the original artifact and exact parser
> extraction immutably, assigns deterministic occurrence identities, maintains an append-only
> provenance graph, and permits unlimited future interpretations without ever altering the
> original evidence.

**Current status:** CI-006, CI-007, CI-008, CI-009, INV-09, INV-10, INV-XI verified 2026-06-19.
CI-014 verified 2026-06-20 through append-only supersession storage, immutability triggers, competing-descendant tests, and chain traversal tests.
CI-015 verified 2026-06-20 through static, dynamic, and mechanical tests proving evidence is not improved before persistence and normalization is isolated to derived metadata.
CI-001, CI-003, CI-012, CI-013 require `gatsby.pdf` in `examples/` to run.

**Verification domains:**

| Domain | Verified By | Proves |
|---|---|---|
| Structure | Static analysis | Architectural boundaries cannot be crossed |
| Behavior | Executable tests | Operational correctness at runtime |
| Understanding | Human witnesses | Successful communication to humans |

Each domain has its own constitutional role. No domain substitutes for another.
Human witness sessions remain required evidence for Axiom 10 and Axiom 12, but
they are not a substitute for executable constitutional tests.

---

## Operational Artifact Promotion Criteria

An operational artifact is a persisted, immutable, non-canonical database object. It satisfies durability and immutability requirements without having yet acquired constitutional effect. Durability and immutability are not the same thing as canonical status.

An operational artifact is promoted to canonical status when it **acquires constitutional effect** — defined as: the artifact is explicitly referenced in a recorded steward decision and the steward decision's downstream consequence (an accepted interpretation, a ratification) persists intact in the canonical corpus.

Before that event: the artifact is advisory. After that event: the artifact is part of the historical explanation for why the canonical corpus looks the way it does. That transition, not the moment of creation, is the canonical boundary.

**Currently operational (not yet canonical):**

| Table | Promotion Criterion | Recorded |
|---|---|---|
| `critic_reports` | First steward explicitly references a `critic_report.id` in a recorded `acceptance_rationale` whose downstream accepted interpretation reaches ratification | 2026-06-20 |

**Constitutional status comment required in DDL and module:**
```python
# Constitutional Status: OPERATIONAL — not yet canonical.
# Promotion criterion defined in CONSTITUTIONAL_COMPLIANCE.md.
# Table is immutable and permanent. Not supersession-eligible.
# No canonical FK dependencies until promotion.
```

This prevents future contributors from treating table existence as canonical status.

---

## Ratification Log

| Date | Action | Ratified By |
|---|---|---|
| 2026-06-19 | CI-001 through CI-016 ratified in `docs/02_Constitutional_Invariants.md` | Primary Human Steward |
| 2026-06-19 | INV-XI ratified (Critic Authority Boundary) | Primary Human Steward |
| 2026-06-19 | INV-XII ratified (Stewardship Produces New Artifacts Only) | Primary Human Steward |
| 2026-06-19 | INV-XIII ratified (Steward Context Shall Not Determine Semantic Standing) | Primary Human Steward |
| 2026-06-19 | INV-XIV ratified (Artist Provider Interchangeability) | Primary Human Steward |
| 2026-06-19 | CI-011 verified: `execution_config` column + provider method implemented | — |
| 2026-06-19 | INV-08 verified: static source scan test added to `test_adr_compliance.py` | — |
| 2026-06-19 | CI-006 verified: FK enforcement + full chain traversal tests added to `test_constitutional_p0.py` | — |
| 2026-06-19 | CI-007 verified: downward non-interference static scan test added | — |
| 2026-06-19 | CI-008 verified: plural interpretation coexistence test added | — |
| 2026-06-19 | CI-009 verified: architect plan content-addressability test added | — |
| 2026-06-19 | INV-09 verified: architect invariance across profiles test added | — |
| 2026-06-19 | INV-10 verified: critic determinism / idempotency test added | — |
| 2026-06-19 | INV-XI verified: critic authority boundary static scan test added | — |
| 2026-06-20 | CI-014 verified: append-only `supersession_relations` storage, UPDATE/DELETE triggers, competing descendants, and chain traversal tests added | — |
| 2026-06-20 | CI-015 verified: anti-helpfulness tests added for exact parser output, raw Observation storage, derived-only normalization, pathological PDFs, downstream non-rewrite, and pre-extraction helper absence | — |
| 2026-06-20 | INV-XIII verified: static guard added to prove steward credential/status fields do not drive semantic standing decisions | — |
| 2026-06-20 | Sprint E8 (Interpretation Staging) verified: `proposed_interpretations` and `ai_provenance` implemented per ADR-0009. Two-Table Invariant enforced structurally and by tests. Acceptance workflow: status→'accepted', ai_provenance acceptance fields populated, canonical `interpretations` row inserted with `ai_provenance_id`. Rejection workflow: status→'rejected', ai_provenance acceptance fields remain NULL, no canonical row created. Immutability triggers: ai_provenance generation fields immutable; acceptance fields settable only once; staging rows non-deletable; terminal status non-re-transitionable. Lineage completeness: accepted interpretation traversable to Observation via direct FK and via ai_provenance→proposal→observation chain. 46 tests passing in `test_era2_sprint_e8.py`. Schema version 15. | — |
| 2026-06-20 | Staging Constitutional Principle recorded in `docs/Architecture_Proofs.md`: a proposed interpretation is not an interpretation with lower confidence — it is a different constitutional state. The Two-Table Invariant derived: `proposed_interpretations` and `interpretations` must remain separate tables. The collapse error (single table with mutable status) is a constitutional violation. | — |
| 2026-06-20 | Sprint E9 (Interpretation Grounding Critic) verified: `critic_reports` operational artifact implemented. Three-stage model (evidence identification / claim extraction / verdict classification) implemented across four named policies (conservative / decomposition / contradiction_sensitive / aggregate_weighting). `make_critic_report_id` deterministic. Immutability triggers on core fields. `normalized` flag mutable by steward claim normalization review. Projections: `critic_queue`, `critic_report_detail`, `critic_summary`. Constitutional Status OPERATIONAL: `proposal_id` is plain TEXT (no FK), no canonical table references `critic_reports.id`. INV-XI static scan updated to reflect `critic/narrative_fidelity.py` path. 49 tests passing in `test_era2_sprint_e9.py`. Schema version 16. | — |
| 2026-06-20 | Sprint E7 (Ratification) verified: `RatificationRecord` implemented as the terminal canonical object. Three pre-condition gates enforced in code (Finding, StewardDecision, WitnessSession all required). Audit snapshot frozen at ratification time. Immutability triggers. `ratification_certificate` and `institutional_memory` projections. Full epistemic chain traversal test. 27 tests passing in `test_era2_sprint_e7.py`. Schema version 14. Era II — Constitutional Engineering complete. | — |
| 2026-06-20 | Sprint E6 (Witness Layer) verified: `WitnessSession` added as second irreducible human primitive, orthogonal to StewardDecision. Directionality constraint enforced (rendered_narrative_id FK; no witness_session_id in rendered_narratives). Immutability triggers, supersession coverage, witness_summary and understanding_ledger projections. 31 tests passing in `test_era2_sprint_e6.py`. Schema version 13. | — |
| 2026-06-20 | Sprint E5 (Stewardship Layer) verified: `StewardDecision` added as first irreducible human governance primitive. Directionality constraint enforced in schema (finding_id FK; no steward_decision_id in findings). Immutability triggers, supersession coverage, review_queue and steward_ledger projections. 27 tests passing in `test_era2_sprint_e5.py`. Schema version 12. | — |
| 2026-06-20 | Sprint E4 (Projection Layer) verified: `audit_dashboard`, `trust_card`, `semantic_inspector` implemented as pure projections over Finding[]. 25 tests passing in `test_era2_sprint_e4.py`. All three projections confirmed read-only, regeneratable, and consistent in Finding totals. | — |
