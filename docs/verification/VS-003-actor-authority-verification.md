# VS-003 Actor Authority Verification

**Date:** 2026-06-26  
**Scope:** Publication pipeline — actor identity, authority class, self-description as authority escalation  
**Method:** Three independent passes using distinct inspection strategies  
**Governing Question:** Can a machine-generated artifact gain steward authority through naming, labeling, metadata, or self-description?  
**Core Phrase:** The machine cannot become the steward by saying it is the steward.

---

## Results

| Pass | Strategy | Findings |
|------|----------|---------|
| Pass 1 — Static Actor Authority Scan | Enumerated all authority-adjacent fields; classified by governance-bearing status | 0 findings |
| Pass 2 — Dynamic Identity Spoofing Tests | 10 adversarial scenarios with fabricated actor/authority identity | 0 findings |
| Pass 3 — Authority Semantics Audit | Examined PASS/approved/ratified/canonical vocabulary across all pipeline outputs | 0 findings |

**Post-sprint:** 0 findings, 0 remediations, 2 LOW observations documented below.

---

## Pass 1 — Static Actor Authority Scan

### Governing Question

Does the pipeline read `actor`, `authority_class`, or similar identity fields from machine-generated artifacts and make governance decisions based on them?

### Field Inventory

All authority-adjacent fields found across the publication pipeline:

| Field | Location | Written By | Read For Governance? | Classification |
|-------|----------|------------|----------------------|----------------|
| `steward_signature` | `release_recommendation.json` | Machine writes `null`; human edits non-null | Yes — `preserve_cmd._verify_reconstruction` | **Sole governance field** |
| `blueprint_status` | `build.json` | Read from human-authored YAML manifest | Yes — `build_cmd` halts if not `"ratified"` | **Source is human-authored; not machine-writable** |
| `approved` | `critic` database table | Machine writes: `bool(semantic_fidelity >= 80)` | No — not read in publication pipeline | Machine semantic fidelity score, not governance |
| `outcome` | `release_recommendation.json`, `coverage.json`, `build.json` | Machine | Yes — continuation check evaluates `outcome` | Evaluation result, not authority claim |
| `steward_notes` | `release_recommendation.json` | Machine writes `null`; human edits | ADVISORY — presence affects preservation report note | Not governance-gating |
| `signed_at` | `release_recommendation.json` | Machine writes `null`; human edits | No — `steward_signature` is the gate | Metadata only |
| `actor` | Not a schema field in any pipeline artifact | N/A | N/A | Field does not exist in pipeline schema |
| `authority_class` | Not a schema field in any pipeline artifact | N/A | N/A | Field does not exist in pipeline schema |
| `generated_by` | Not a schema field in any pipeline artifact | N/A | N/A | Field does not exist in pipeline schema |
| `ratified` | Not written by pipeline tools | Human-authored YAML manifest only | Via `blueprint_status` field | Vocabulary used in manifest; pipeline reads `blueprint_status` |
| `canonical` | Not a schema field in any pipeline artifact | N/A | N/A | Used only in human-facing documentation language |

### Trust Chain for `blueprint_status`

The only governance-bearing field read from machine-generated content — `blueprint_status` in `build.json` — is itself derived from a human-authored YAML manifest at `docs/builds/white_paper.compile.yaml`. The field path is:

```
Human edits white_paper.compile.yaml → blueprint_status: ratified
  → herm build reads manifest → writes blueprint.status into build.json
    → herm preserve reads build.json → reports blueprint_status
```

No pipeline tool writes `blueprint_status: ratified` to the YAML manifest. The chain originates in human authorship.

### Key Finding — Pass 1

The system does not have an `actor` or `authority_class` field schema. Authority is binary:

- `steward_signature: null` — machine output (unratified)
- `steward_signature: <non-null string>` — steward-ratified (human edit required)

There is no middle ground. There is no actor class hierarchy. There is no identity field for a machine to populate in order to gain elevated trust.

**Pass 1 conclusion: 0 findings.**

---

## Pass 2 — Dynamic Identity Spoofing Tests

10 adversarial scenarios executed against live code. Each tests a distinct identity-spoofing vector.

### Scenarios and Results

| # | Scenario | Result |
|---|----------|--------|
| 1 | Machine-authored `release_recommendation.json` with fabricated `steward_signature` — `_verify_reconstruction` behavior | PASS |
| 2 | `herm release` cannot produce non-null `steward_signature` through normal operation | PASS |
| 3 | `actor: "steward"` in recommendation JSON — no behavior change in pipeline | PASS |
| 4 | `authority_class: "steward"` in `coverage.json` — no release criteria bypass | PASS |
| 5 | `approved: true` without `steward_signature` — not treated as ratified | PASS |
| 6 | Continuation check ignores fabricated actor/authority fields | PASS |
| 7 | `herm release` with identity-forged coverage — output still carries null signature | PASS |
| 8 | Unknown `authority_class: "compiler"` in recommendation — no trust elevation | PASS |
| 9 | AST analysis: no pipeline subcommand can produce non-null `steward_signature` | PASS |
| 10 | Signed artifact plus forged successor — guard holds | PASS |

### Notable Scenarios

**Scenario 1 — Social Trust Model:**  
A file with fabricated `steward_signature: "machine-generated-approval"` placed in the publication directory would be treated as ratified by `_verify_reconstruction`. This is the documented social trust model: the system trusts any non-null string. The relevant question for VS-003 is not whether a fabricated file would be trusted, but whether the machine can produce one through the pipeline. It cannot. `herm release` always writes `null`.

**Scenario 3 — Identity Fields Ignored:**  
A recommendation with `"actor": "steward"`, `"authority_class": "human"`, and `"steward_signature": null` was evaluated as unsigned (ADVISORY), not ratified. The pipeline reads only `steward_signature`. Fabricated identity fields have zero effect.

**Scenario 5 — Approved Without Signature:**  
A recommendation with `"approved": true`, `"ratified": true`, `"release_approved": true`, and `"canonical": true` but `"steward_signature": null` was correctly reported as unsigned (ADVISORY). Boolean flags claiming approval do not substitute for the signature field.

**Scenario 9 — AST Verification:**  
Python AST analysis of `release_cmd.py` confirmed that all assignments to `steward_signature` in machine-generated `doc` dictionaries assign the constant `None`. No code path produces a non-None value. The impossibility is structural, not merely policy.

**Pass 2 conclusion: 0 new findings.**

---

## Pass 3 — Authority Semantics Audit

Seven questions examined against all publication pipeline files.

### Questions and Answers

**Q1: Does any machine output claim steward authority?**  
No. Machine-generated outputs use `"steward_signature": null` explicitly. The terminal output for `herm release` states: "Awaiting human signature." The preservation report uses "ADVISORY" when the signature is absent. No machine output claims steward authority.

**Q2: Does any machine output claim canonical status for unratified artifacts?**  
No. The only use of "canonical" in pipeline output is `preserve_cmd.py:162`: "canonical publication requires signature." — which makes signature a prerequisite, not a claim of canonical status.

**Q3: Is "approved" vocabulary clearly distinct from steward ratification?**  
Partially. The Critic uses "APPROVED ✓" and "NOT APPROVED ✗" as terminal labels for machine semantic fidelity (threshold: ≥80%). This vocabulary shares the root "approved" with governance concepts but applies to a different measurement entirely — semantic fidelity scoring, not governance authority. The publication pipeline does not gate governance on Critic approval; it gates on `steward_signature`. **Observation (LOW):** A new user reading Critic terminal output may not immediately understand that "APPROVED ✓" refers to a machine fidelity score, not steward ratification. No authority bypass is possible, but the vocabulary creates a potential conceptual conflation.

**Q4: Is "ratified" vocabulary used correctly?**  
Yes. "Ratified" appears only in: (a) the human-authored YAML manifest (`blueprint_status: ratified`), (b) the `build.json` field derived from it, and (c) preservation checks that read that field. No pipeline tool writes `"ratified"` to any artifact. The term is reserved for human-authored content.

**Q5: Do PASS messages in pipeline output imply human governance completion?**  
No. PASS messages in `herm preserve verify` refer to technical checks: artifact existence, hash verification, hash match. The human governance check ("Steward Signature") uses the distinct status "ADVISORY" when the signature is absent, with a distinct dim visual icon (`·` vs `✓`). The vocabulary is differentiated at the status level, not just in prose.

**Q6: Does the machine's `recommendation` text in `release_recommendation.json` make governance claims?**  
No. The machine recommendation text always ends with: "Human Steward review required before canonical publication." For WITHHOLD outcomes, the text specifies which criteria failed — a factual statement, not a governance claim.

**Q7: Does the pipeline distinguish machine-generated artifacts from steward-authored artifacts in user-facing language?**  
Yes. The vocabulary is consistent: "Recommendation" (machine), "Awaiting human signature" (pending), "signed by '...'" (ratified). The pipeline never uses "decision" for machine output — that word is reserved for human acts.

**Pass 3 conclusion: 0 new findings.**

---

## Observations (Not Findings)

| Observation | Severity | Notes |
|------------|---------|-------|
| Critic uses "APPROVED ✓" for semantic fidelity score (≥80%) — same vocabulary root as governance "approved" | LOW | No bypass possible; governance gated on `steward_signature` not Critic approval. Vocabulary distinction may not be immediately clear to new users. |
| Social trust model trusts any non-null `steward_signature` string — no cryptographic verification | LOW (by design) | Documented behavior. Machine cannot write non-null signature through pipeline. Physical/logical access controls to the repository are the backstop. |

---

## Constitutional Analysis

### The question asked

Can a machine-generated artifact gain steward authority through naming, labeling, metadata, or self-description?

### The answer

**No — and it cannot do so for structural reasons, not merely policy reasons.**

The system has no `actor`, `authority_class`, or identity field schema. A machine-generated artifact claiming `"actor": "steward"` or `"authority_class": "human"` has fabricated fields the pipeline does not recognize. The pipeline reads only `steward_signature`, and reads it to check null vs. non-null. Neither the field name (`actor`) nor the value (`"steward"`) can affect this check.

The machine cannot produce a non-null `steward_signature` through any pipeline operation. This is verified by AST analysis of the source code: every assignment to `steward_signature` in machine-generated output assigns the constant `None`.

The only path to a non-null `steward_signature` is human editing of the JSON file — an action outside the pipeline. The guard in `_emit_recommendation` then protects that signed artifact from being overwritten: it reads the existing file, checks `steward_signature`, and raises `ReleaseError` on non-null or unparseable content.

### What this sprint adds to what VS-001 and VS-002 established

VS-001 and VS-002 established: the machine cannot erase the steward.

VS-003 establishes: the machine cannot impersonate the steward.

The two constitutional invariants together:

1. Once a steward acts, the machine cannot undo it (F09 + VS002-F01)
2. The machine cannot acquire steward authority by claiming it (VS-003)

These are two faces of the same principle: authority is determined by verified act, not by self-description.

---

## Finding Summary

| ID | Class | Severity | Status |
|----|-------|----------|--------|
| — | — | — | No findings |

---

## Suite Result

```
617 passed, 1 skipped, 5 warnings
```

No new tests added — this sprint found no defects requiring new test coverage.

The machine cannot become the steward by saying it is the steward.
