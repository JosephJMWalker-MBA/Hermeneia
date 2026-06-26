# ADR-0038: Meaning-Preserving vs. Meaning-Altering Transformations

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P4-001 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

ADR-0037 established that style and semantics can be partially separated, and defined four semantic invariants the Artist must preserve. Q-P4-001 asks for the detailed taxonomy: which specific transformations are meaning-preserving, and which are meaning-altering?

The Critic must validate this taxonomy algorithmically. A qualitative judgment ("this sounds wrong") is not sufficient — the Critic must identify which invariant was violated and which BlueprintClaim was affected.

---

## Decision

### The Taxonomy

Transformations are classified against the four semantic invariants from ADR-0037:

| Invariant | Checked By |
|---|---|
| Truth conditions | Proposition set comparison |
| Entailments | Logical dependency graph |
| Evidential status | `evidential_status` field comparison |
| Uncertainty attribution | Perspective and source attribution check |

---

### Category A: Meaning-Preserving Transformations (Permitted)

These transformations may be applied by the Artist without Critic review:

| Transformation | Permitted Because |
|---|---|
| Synonym substitution within the same semantic field | Does not alter truth conditions. ("Remarkable" → "notable") |
| Reordering paragraphs where no logical dependency is violated | Dependency sequence from `depends_on_claim_ids` still satisfied. |
| Adding analogies flagged explicitly as analogies | Analogies are not claims. They are explanatory devices. Must be marked as analogies in the output. |
| Register adjustment (formal → accessible) | Propositional content and evidential status unchanged. |
| Active/passive voice conversion | Does not alter truth conditions or attribution. |
| Sentence-level restructuring preserving propositional content | Same proposition, different syntax. |
| Selecting among multiple `cited_observation_ids` for the same claim | All are permitted by the Blueprint. The Artist chooses which to foreground. |
| Acknowledging a FieldContradiction implicitly rather than explicitly | Permitted only if `field_contradiction_ids` are still acknowledged in some form. |

---

### Category B: Meaning-Altering Transformations (Forbidden)

These transformations are detected by the Critic as violations. Each maps to the invariant it violates.

**Violations of Invariant 1 — Truth Conditions:**
| Transformation | Why It Alters Meaning |
|---|---|
| Adding a causal claim not in any `claims[*].proposition` | Introduces new truth conditions. |
| Inverting a claim's valence ("not X" → "X" or vice versa) | Directly alters truth conditions. |
| Changing the scope of a claim (particular → universal) | "In this Perspective, X" → "X" is a scope change that alters truth conditions. |
| Introducing a new Observation not in `cited_observation_ids` | Adds evidentiary support not authorized by the Architect. |

**Violations of Invariant 2 — Entailments:**
| Transformation | Why It Alters Meaning |
|---|---|
| Presenting a dependent claim before its prerequisite | Violates logical dependency sequence; reader may conclude the dependent claim holds without its premise. |
| Omitting a claim that is a prerequisite for a later claim | Later claim appears groundless; the entailment chain is broken. |
| Merging two claims with different Perspectives into one | Creates a synthetic claim that does not exist in the Blueprint; entailment structure is distorted. |

**Violations of Invariant 3 — Evidential Status:**
| Transformation | Why It Alters Meaning |
|---|---|
| Presenting a `speculative` claim as unhedged assertion | Converts uncertain epistemic status to certain. |
| Presenting an `established` claim as `contested` | Misrepresents the epistemic status recorded in the Blueprint. |
| Removing hedges ("it is possible that" → "it is") | Changes truth conditions AND evidential status. |

**Violations of Invariant 4 — Uncertainty Attribution:**
| Transformation | Why It Alters Meaning |
|---|---|
| Removing Perspective attribution from a claim ("From a Marxist perspective, X" → "X") | Uncertainty is attributed to a declared epistemic frame. Removing the frame converts a perspectival claim to a universal claim. |
| Suppressing a FieldContradiction acknowledgment | Presents a contested reading as uncontested. |
| Attributing a claim to the wrong Perspective | Changes who is making the claim, which is a semantic change. |

---

### The Critic's Algorithm

The Critic validates the Artist's output in three passes:

**Pass 1 — Proposition inventory:**  
Extract all propositions from the Artist's output (using the Architect's proposition parser). Check that every proposition in the output is present in `claims[*].proposition` or is flagged as an analogy. Any unrecognized proposition is a Category B violation (Invariant 1).

**Pass 2 — Evidential status check:**  
For each recognized proposition, retrieve its `evidential_status` from the corresponding `BlueprintClaim`. Check that the output's framing is consistent with that status. Hedges must be present for `speculative` and `uncertain` claims. Perspective attribution must be present for all claims (since every claim has exactly one `perspective_id`).

**Pass 3 — Dependency sequence check:**  
Verify that the output's presentation order respects the `depends_on_claim_ids` partial order. A claim may not appear before a claim it depends on.

The Critic returns a structured `CriticReport`:

```python
@dataclass
class CriticReport:
    blueprint_id: str
    rendering_id: str
    passed: bool
    violations: List[CriticViolation]

@dataclass  
class CriticViolation:
    invariant: Literal["truth_conditions", "entailments", "evidential_status", "uncertainty_attribution"]
    claim_id: Optional[str]  # Which BlueprintClaim was violated
    description: str          # What was violated
    severity: Literal["blocking", "advisory"]
```

Blocking violations prevent the rendering from being delivered to the reader. Advisory violations are surfaced to the human steward for review.

---

### Ambiguous Cases

Some transformations cannot be algorithmically classified. These are advisory violations for human steward review:

- An analogy that the Architect believes obscures rather than illuminates the claim
- A metaphor whose implications extend beyond the Blueprint's claims
- A rhetorical framing that technically preserves truth conditions but creates a misleading gestalt impression

These cases are recognized by the Critic's confidence score falling below a threshold. The Critic flags them as advisory and routes them to the steward. The steward may approve or reject. This is a human-only decision (ADR-0010).

---

## Constitutional Alignment

- **ADR-0037** (Style/semantics separation): This ADR provides the concrete taxonomy that ADR-0037's four invariants imply.
- **ADR-0036** (NarrativeBlueprint): The `claims[*]` structure, `evidential_status`, `forbidden_inferences`, and `depends_on_claim_ids` fields are the Critic's input.
- **ADR-0010** (Human-only decisions): Ambiguous violations require steward resolution.
- **Invariant 4** (Architectural Decoupling): The three-pass Critic algorithm is arithmetic over structured data, not qualitative judgment.
