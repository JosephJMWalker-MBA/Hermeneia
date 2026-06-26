# Research Synthesis 001 — The Convergence-Governance Pattern

**Date:** 2026-06-20  
**Covers:** Experiments 001–008  
**Status:** Recorded at research program conclusion

---

## The Pattern

Eight experiments, conducted across five AI providers, on observations from a single source document, using the E8 staging gate as the constitutional substrate, produced the following pattern at every layer of analysis:

```
Generation          → diverges
Evidence Identification → converges
Judgment            → diverges
Governance          → reconciles
```

This pattern was not designed into the experiments. It emerged from them.

---

## What Each Experiment Established

| Experiment | Question | Finding |
|---|---|---|
| 001 | Do providers generate interpretations from identical evidence? | Yes, and they diverge by interpretive layer (narrative / structural / catalog) |
| 002 | Does the interpretive layer prior hold with unambiguous scope? | Yes — removing scope ambiguity did not change which layer each provider interprets at |
| 003 | Can providers identify where their own interpretations exceed the evidence? | Yes — self-critique produced convergence on the same inferential boundary across all providers |
| 004 | Does the prior hold for figurative language? | Partially — priors are stable but bounded by task structure (single vs. multiple candidates) |
| 005 | Can providers evaluate an interpretation they did not generate? | Yes — cross-critique produced convergence on the same unsupported inference (the *tertium comparationis*) |
| 006 | Can providers apply a three-way classification (supported / unsupported / contradicted)? | Evidence identification converges; verdict classification is policy-dependent |
| 007 | Does evidence identification convergence hold under competing evidence? | Yes — 5/5 providers found the same two load-bearing phrases in a passage with rich competing evidence |
| 008 | Can providers extract and classify all claims in a full interpretation? | Evidence identification converges; claim boundaries diverge; claim extraction is itself interpretive |

---

## The Three-Stage Model

The research produced a three-stage model of the Critic operation:

```
Observation + Claim
    ↓
Stage 1: Evidence Identification
    What text is relevant to this claim?
    Cross-provider convergence: HIGH
    Automatable with high confidence

    ↓
Stage 2: Evidence-Claim Mapping
    Which evidence supports the claim? Which opposes it?
    How does each piece of evidence bear on each component?
    Cross-provider convergence: MODERATE
    Automatable with audit

    ↓
Stage 3: Verdict Classification
    Given the evidence map, what is the verdict?
    Cross-provider convergence: LOW — policy-dependent
    Three stable policies identified:
      Conservative: absence of support = Unsupported
      Decomposition: split claim into components, evaluate separately
      Contradiction-Sensitive: if key term is definitionally opposed, = Contradicted
    Requires steward policy configuration
```

---

## The Three Stable Evaluation Policies

Across Experiments 005–008, three evaluation policies appeared consistently:

**Conservative** (Meta)  
Rule: If supporting evidence is absent, verdict = Unsupported. Active contradiction not required.  
Characteristic: Never returns Contradicted. Always returns Unsupported at the lower bound.

**Decomposition** (Claude)  
Rule: Decompose the claim into components. Evaluate each component. Aggregate.  
Characteristic: Produces Partially Supported when components receive mixed verdicts. May introduce new claims during decomposition (Experiment 008).

**Contradiction-Sensitive** (Gemini)  
Rule: If the claim's load-bearing term has a literal meaning the observation explicitly violates, verdict = Contradicted.  
Characteristic: Applies semantic definition of the claim's key terms as the test. Caught the same error in Experiment 003 that Experiment 002 missed.

**Aggregate-Weighting** (GPT, Grok)  
Rule: Weigh supporting against challenging evidence. Partially Supported when both present.  
Characteristic: Most sensitive to the richness of positive evidence — shifts from Unsupported (Experiment 006) to Partially Supported (Experiment 007) when positive evidence is present.

---

## The Finding That Changed Architecture

**Experiment 008:** Claim extraction is not a parsing step. It is an interpretive act.

Given the same one-sentence interpretation, providers extracted 3–7 distinct claims. Evidence identification remained stable across all claim sets. Claim boundaries diverged.

One provider (Claude) introduced a claim during extraction that was not present in the observation or the interpretation provided. The same decomposition prior that made Claude a structural reader made its claim extraction generative.

**Constitutional consequence:** The Critic requires a steward-governed claim normalization step before evidence evaluation. The claim set is another product of interpretation and should be subject to steward review. The Critic itself needs a Critic — not for verdicts, but for claim boundaries.

---

## The Stewardship Model as Empirical Necessity

Before this research program, the stewardship model in Hermeneia was justified constitutionally: ADRs, invariants, design decisions by the primary steward.

After this research program, it is also justified empirically.

The experiments placed humans at the governance layer not by fiat but by necessity: the human is placed where variance remains after the available convergence has already occurred. Evidence identification converges without human input. Verdict classification and claim boundary determination diverge after providers have agreed on the evidence. The human is not placed everywhere. The human is placed precisely at the points of unresolved variance.

The architecture did not design a system that happens to need stewards. The research discovered that the natural structure of AI interpretation — convergence at the evidence layer, divergence at the judgment and boundary layers — produces exactly the interface at which human governance is necessary rather than merely desirable.

---

## The Larger Pattern

The convergence-governance pattern appeared not only in the research but in the constitutional design review for Sprint E9.

When the question arose whether `critic_reports` should be a canonical table or an operational artifact, the same structure appeared:

```
Operational artifact  (durable, exists)
    ↓
Governance event  (steward references it in a constitutional act)
    ↓
Canonical artifact  (constitutional effect acquired)
```

The pattern that governs interpretation evaluation also governs storage status. The architecture applies the same separation at multiple layers. This is not a coincidence of design — it is recursive consistency: the same principle (governance events, not creation events, determine constitutional status) operating at different scales.

---

## What the Research Program Did Not Establish

These questions remain open and define the boundary conditions for implementation:

1. Does evidence identification remain convergent across longer texts (multiple paragraphs)?
2. Does convergence survive cross-document evidence — a claim grounded in one observation, contradicted in another?
3. Does convergence survive contradictory evidence distributed across documents rather than within a single passage?
4. Can the three evaluation policies be parameterized so the Critic exposes which policy produced which verdict?
5. Does claim normalization require a fixed vocabulary, a steward, or a separate AI layer?

These are implementation boundary conditions, not research questions. The research program has answered its foundational questions. Experiments 009+ should validate implementation behavior, not discover additional architectural principles.

---

## What This Research Program Was

Eight experiments to discover whether AI providers can reliably perform the operations required to implement a constitutional Critic.

The answer: yes, with a specific governance boundary. Evidence identification is stable and automatable. Claim boundaries and verdict classification require human governance at the boundary where provider variance persists.

That answer is sufficient to build the Critic.

The research program is complete.
