# ADR-0039: Narrative Fidelity — Definition and Measurement

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P4-002 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

Q-P4-002 asks: Is Narrative Fidelity a binary property or a continuous score? Is it measured claim-by-claim or holistically? The Critic must return a structured result — not a qualitative judgment. ADR-0038 defined the Critic's three-pass algorithm and its `CriticReport`. This ADR defines Narrative Fidelity as the scalar metric derived from that report.

---

## Decision

**Narrative Fidelity is a continuous score in [0.0, 1.0], computed claim-by-claim and aggregated.**

A rendering identical to the Blueprint's propositions scores 1.0. A rendering with blocking violations scores below a minimum threshold (see below). A rendering that passes all checks but triggers advisory violations may score between threshold and 1.0.

---

### Formal Definition

```
NF(rendering, blueprint) = (blocking_weight × B + advisory_weight × A) / total_claims
```

Where:
- `total_claims` = `|blueprint.claims|`
- `B` = number of claims with no blocking violation
- `A` = number of claims with no advisory violation
- `blocking_weight` = 0.8
- `advisory_weight` = 0.2

This yields:
- A rendering with no violations of any kind: NF = 1.0
- A rendering with one blocking violation (on one claim): NF decreases by at least `0.8 / total_claims`
- A rendering with only advisory violations: NF ≥ 0.8 (if all blocking checks pass)

### Delivery Threshold

A rendering may only be delivered to the reader if `NF ≥ 0.85`. Below this threshold, the Critic blocks delivery and the Artist must revise.

The 0.85 threshold is a calibration parameter, not a constitutional commitment. Future amendment may adjust it.

### When NF Is Undefined

If `total_claims = 0` (an empty Blueprint), NF is undefined. This is an Architect error: Blueprints must contain at least one BlueprintClaim. The Critic returns `undefined` and the rendering is blocked.

---

### Is Narrative Fidelity a Measure of Quality?

**No.**

A rendering can have NF = 1.0 and be rhetorically poor, difficult to read, or pedagogically ineffective. Narrative Fidelity measures only the Critic's pass/fail rates against the four semantic invariants from ADR-0037. It does not measure:
- Rhetorical effectiveness
- Reader engagement
- Clarity or accessibility
- Completeness relative to the reader's needs

These are the Artist's domain and the steward's judgment. They cannot be algorithmically scored without LLM involvement, which would violate Invariant 4 (Architectural Decoupling).

---

### CriticReport and NF Together

The Critic always produces a `CriticReport` (ADR-0038) alongside the NF score. The NF score is derived from the CriticReport. The steward receives both. The steward's decision to approve a low-NF rendering (when the violations are advisory) is a human-only decision (ADR-0010).

The NF score is stored alongside the rendering in the database:

| Field | Type | Description |
|---|---|---|
| `narrative_fidelity_score` | Float [0.0, 1.0] | Computed from CriticReport. |
| `critic_report_id` | String | FK to `critic_reports` table. |
| `delivery_approved_by` | String | Steward ID if manual approval was required. Null if automatic. |
| `delivery_approved_date` | ISO 8601 datetime | When approval was given. |

---

## Validation Test

Q-P4-002 proposed: *"A prose rendering identical to the NarrativeBlueprint (verbatim) should return NF = 1.0. A prose rendering that inverts a claim should return a measurably low fidelity score."*

- Verbatim rendering: all claims present, all invariants preserved → B = `total_claims`, A = `total_claims` → NF = 1.0. ✓
- One inverted claim: one blocking violation (Invariant 1 — truth conditions) → B = `total_claims - 1` → NF = `(0.8×(n-1) + 0.2×(n-1)) / n` < 1.0, and if `n` is small (say 5 claims), the single inversion produces NF ≈ 0.8, which is below the 0.85 delivery threshold → delivery blocked. ✓

---

## Constitutional Alignment

- **ADR-0038** (Meaning-preserving transformations): NF is derived from the CriticReport defined there.
- **ADR-0036** (NarrativeBlueprint): `total_claims` is `|blueprint.claims|`.
- **ADR-0010** (Human-only decisions): Manual delivery approval when `NF < 1.0` but steward judges violations acceptable.
- **Invariant 4** (Architectural Decoupling): NF is a ratio of claim-level pass/fail counts. No LLM involvement.
