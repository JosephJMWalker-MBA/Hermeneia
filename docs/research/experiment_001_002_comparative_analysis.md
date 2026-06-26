# Comparative Analysis: Experiment 001 vs Experiment 002

**Corpus:** The Great Gatsby (F. Scott Fitzgerald)  
**Experiment 001:** English execution  
**Experiment 002:** Spanish execution  
**Date:** 2026-06-25  
**Status:** Research note — hypotheses require further investigation

---

## Systems-Level Summary

The algorithm applied in both executions:

```
Input
    ↓
Observe
    ↓
Classify
    ↓
Generate Questions
    ↓
Gather Evidence
    ↓
Weight Evidence
    ↓
Construct Model
    ↓
Compress
    ↓
Communicate
```

---

## Layer-by-Layer Analysis

### Layer 1 — Observation

Observations were largely identical across both executions.

Both identified: Green Light, Water, Valley of Ashes, Clock, Parties, Daisy's Voice, Boats.

**Finding:** Observation appears largely culture-independent, at least for salient textual phenomena.

**Evidential status:** Supported by these two executions. Not proven generally.

---

### Layer 2 — Classification

Classifications showed minimal divergence.

Heat remained atmosphere. Green Light remained metaphor. Eyes remained symbol. Clock remained metaphor.

**Finding:** Literary classification may be relatively invariant across executions.

**Evidential status:** Supported here. Requires replication.

---

### Layer 3 — Question Generation

This is the first layer of genuine divergence.

| Execution | Governing Question |
|---|---|
| English | Can people reinvent themselves? |
| Spanish | Can people ever separate themselves from history? |

Neither question comes from Fitzgerald. Both are textually supported. The reader selected them.

**Finding:** Question selection is the first culturally adaptive component observed in the pipeline.

---

### Layer 4 — Attention Allocation

The finding here requires precise language.

People did not *interpret differently*.  
People *allocated attention differently*.

Those are not the same claim.

Representational weights (illustrative):

| Observation | English weight | Spanish weight |
|---|---|---|
| Green Light | 0.98 | 0.84 |
| Father | 0.42 | 0.94 |
| Future | 0.91 | 0.53 |
| History | 0.51 | 0.95 |

Neither execution ignored the other observations. They assigned different salience.

**Finding:** Investigative emphasis may be representable as measurable weighting profiles.

**Evidential status:** Illustrative. Measurement methodology not yet formalized.

---

### Layer 5 — Evidence Network

The evidence nodes did not change. The causal organization changed.

English graph structure: Green Light → Dream → Interpretation → Reality  
Spanish graph structure: Father → History → Identity → Belonging

**Finding:** Hermeneia does not discover new evidence across executions. It reorganizes the same evidence graph according to different governing questions.

---

### Layer 6 — Compression

English compression: *Reality corrects interpretation.*  
Spanish compression: *History remains active.*

These compressions do not contradict each other. They are different summaries of the same dataset under different governing questions.

---

### Layer 7 — The Moving Part

After comparing all layers, exactly one component changed between executions:

**The Priority Function** — which observations the investigation considered worth pursuing.

Everything downstream followed automatically.

This is a candidate minimal architecture:

```
Document
    ↓
Observation
    ↓
Priority Function       ← the single culturally adaptive component
    ↓
Question Selection
    ↓
Evidence Weighting
    ↓
Model
    ↓
Compressed Expression
```

---

## Revised Hypothesis: Question Primacy

The Priority Function may actually be downstream of question selection rather than upstream.

Proposed order:

```
Observation
    ↓
Question Selection      ← the governing variable
    ↓
Priority Function       ← conditioned on the governing question
    ↓
Evidence Weighting
```

Why: questions determine what counts as relevant. The weighting is not arbitrary — it is conditioned on the investigative question.

**Implication:** The hidden variable may be *question selection*, not *priority weighting*.

---

## The Core Hypothesis

> **Culture may influence which questions investigators consider worth asking before interpretation begins.**

This is distinct from:
- Culture changes answers (weaker — observed to be mostly false here)
- Culture changes interpretations (partially true — but downstream)

If question selection is the primary culturally adaptive component, then:

1. Two investigators can reason perfectly from identical evidence.
2. Produce different, textually grounded interpretations.
3. Not because either reasoned poorly.
4. Because they investigated different questions.

**Implication:** Disagreement may begin before interpretation — at question selection. This places the divergence point upstream of evidence weighting, upstream of argument, upstream of conclusions.

---

## Secondary Observation: Generalization Asymmetry

English execution remained centered on Gatsby as agent throughout.

Spanish execution gradually generalized from Gatsby to humanity by the conclusion.

**Hypothesis:** Collectivist-leaning investigations may naturally generalize from agent to relationship over the course of an inquiry. Individualist-leaning investigations may remain centered on the agent.

**Evidential status:** Single observation. Not established.

---

## The Fingerprint Concept

Each investigation produces a quantitative emphasis profile. Possible dimensions:

- Agency Score
- Relationship Score
- History Score
- Future Score
- Community Score
- Individual Score
- Identity Score

These profiles would describe the investigation rather than replace the essay. Two essays on the same text with different profiles are both valid. The profiles make the investigative emphasis explicit and comparable.

**Evidential status:** Conceptual. Measurement methodology requires design.

---

## Candidate Hypotheses

### Supported by Experiments 001–002

- Salient observations remained largely stable across these two executions.
- Basic literary classifications remained largely stable across these two executions.
- Different governing questions emerged despite similar observations.
- Evidence weighting differed substantially across executions.
- Final compressions were distinct but non-contradictory.

### Requires Further Investigation

- Question selection is the primary culture-adaptive component of the pipeline.
- Evidence weighting is largely downstream of question selection rather than an independent variable.
- Investigative emphasis can be represented as measurable quantitative profiles.
- Collectivist-leaning investigations generalize from agent to relationship.
- These patterns generalize beyond The Great Gatsby.
- These patterns generalize beyond literary analysis.

### Planned Experiments

- Experiment 003: Mandarin execution — tests whether the same question-selection divergence appears in a third cultural context.
- Experiment 004: A non-literary corpus — tests whether the pipeline decomposition emerges without forcing it.

---

## Architectural Implications

*(Deferred under Architecture Freeze v1.0 — recorded for post-freeze consideration)*

This analysis suggests a possible new cognitive responsibility between Explorer and Architect:

```
Explorer
    ↓
Question Constructor    ← surfaces competing investigative questions
    ↓
Architect
```

The Question Constructor would not interpret. It would generate competing investigative questions from the observation set and present them to the Steward for selection.

Example: Hermeneia uploads Gatsby. It proposes:
- What is the function of aspiration?
- What is the function of wealth?
- What is the function of memory?
- What is the function of class?
- What is the function of history?

The Steward selects. Everything downstream follows.

This requires no evidence changes. No new canonical objects. The governing question is a Steward decision — which is already an established constitutional category.

See [`docs/FUTURE_ARCHITECTURE_NOTES.md`](../FUTURE_ARCHITECTURE_NOTES.md) for the deferred architectural note.

---

## Methodological Note

Hermeneia's constitutional standards apply to Hermeneia's own research program.

Two executions of one corpus is evidence, not proof.

The empirical program is: run the full pipeline on radically different corpora and see whether the same decomposition emerges without forcing it.

The hypotheses above should be treated as candidates for investigation, not conclusions.
