# Hermeneia Writing Protocol v1.0

**A methodology for producing accountable, inspectable documents**

**Version:** 1.0  
**Date:** 2026-06-25  
**Status:** Working draft

---

## Purpose

This protocol specifies how to produce a document whose understanding can be traced, challenged, and improved — not just its conclusions, but the reasoning that produced them.

It applies the same cognitive architecture Hermeneia uses for investigative inquiry to the act of writing itself:

```
Witness
    ↓
Discovery
    ↓
Reconstruction
    ↓
Verification
    ↓
Governance
    ↓
Communication
```

This is not a style guide. It is a protocol for making the evolution of understanding in a document inspectable.

---

## Scope

This protocol applies to any document that makes claims, draws conclusions, or advances an argument: research papers, policy documents, legal analyses, grant proposals, technical specifications, investigative reports.

It is unit-level: each section of a document is treated as a separate investigation. A document is not complete until every section has completed the full cycle.

---

## The Six Stages

### Stage 0 — Witness

**Question:** What artifact are we examining?

The artifact is recorded exactly as it exists. Nothing changes at this stage. The purpose is to establish what we are actually working with before interpretation begins.

**Record:**
- Document name and version
- Section identifier
- Date of examination

**Output:** Artifact record

**Rule:** Do not proceed to Stage 1 until the artifact has been recorded. Examination that begins without a stable artifact produces interpretations of a moving target.

---

### Stage 1 — Discovery

**Question:** What is this section actually trying to accomplish?

This is not a summary. A summary answers "what does it say?" Discovery answers "what understanding is it attempting to produce?"

The distinction matters. A section may say something clearly while attempting to accomplish something different — or attempting to accomplish six things at once, or attempting to accomplish nothing in particular.

**Output:** Intent Hypothesis — one sentence stating the specific understanding this section is attempting to produce.

**Examples:**

Not: "This section discusses the relationship between the Architect and the Critic."

Yes: "This section attempts to establish that the Critic's evaluation functions reveal failures in the Architect's contract, not failures in the Artist's execution."

**Rule:** The Intent Hypothesis must be falsifiable. If the section could succeed regardless of what the Architect or Critic say, the hypothesis is too vague.

---

### Stage 2 — Reconstruction

**Question:** Did we correctly understand the author's intention?

The author reviews the Intent Hypothesis and determines whether it matches what they were trying to accomplish.

**Outcomes:**

| Verdict | Meaning | Action |
|---|---|---|
| ✓ Ratified | Intent Hypothesis matches authorial intent | Proceed to Verification |
| ✎ Partial | Intent Hypothesis is close but missing something | Revise Intent Hypothesis |
| ✗ Rejected | Intent Hypothesis missed the point | Rewrite Intent Hypothesis |

**Rule:** If the Intent Hypothesis is rejected or substantially revised, the author should ask whether the *section itself* is accomplishing the right thing. Sometimes a rejected Intent Hypothesis reveals that the section is unclear because the author's intent was itself unclear. In that case, clarify intent before proceeding.

**Do not revise the section at this stage.** The section has not yet been evaluated. Revising it now would be editing before diagnosis.

---

### Stage 3 — Verification

**Question:** Does the section accomplish what the Intent Hypothesis claims it accomplishes?

The Critic examines the section across five dimensions. For each dimension, the Critic records a verdict and supporting evidence.

**Dimensions:**

| Dimension | Question |
|---|---|
| **Intent** | Did the section accomplish the stated Intent Hypothesis? |
| **Evidence** | Which claims are directly supported? Which are merely asserted? |
| **Scope** | Does the section establish one idea, or several? |
| **Clarity** | Could another researcher restate this section accurately in their own words? |
| **Confidence** | Are observations separated from hypotheses? Is the stated confidence level warranted? |

**Verdicts per dimension:**

| Verdict | Meaning |
|---|---|
| **Strong** | The section performs well on this dimension without qualification |
| **Appropriate** | The section performs adequately; no revision needed on this dimension |
| **Needs Revision** | A specific, identified issue requires attention |
| **Fails** | The section does not meet the standard on this dimension |

**Output:** Critic Findings — a verdict and brief evidence note for each dimension.

**Rule:** The Critic produces findings, not edits. The Critic's job is diagnosis, not prescription. What to do with the findings is decided in Stage 4.

---

### Stage 4 — Governance

**Question:** What should happen to this section?

The author reviews the Critic Findings and issues one of four decisions.

**Decisions:**

| Decision | Meaning |
|---|---|
| **Ratified** | The section is complete. No revision needed. |
| **Minor Revision** | One or two specific issues identified. Targeted edits only. |
| **Major Revision** | Multiple dimensions need attention. Significant rewrite of this section. |
| **Rewrite** | The section is not accomplishing its stated Intent Hypothesis. Start over. |

**Rule:** A Rewrite decision should prompt a review of the Intent Hypothesis itself before rewriting. If the section failed because the Intent Hypothesis was wrong, revising the section against the wrong hypothesis will produce a different failure.

**Rule:** Governance decisions are recorded and do not disappear. A section that was once a Rewrite and is now Ratified has a different provenance than a section that was Ratified on first review. That difference is meaningful.

---

### Stage 5 — Communication

**Question:** How should the section be expressed, given the Intent Hypothesis and Critic Findings?

Only at this stage does the Author or Artist write.

If the governance decision was Ratified: no communication work needed.

If the decision was Minor Revision, Major Revision, or Rewrite: the Author produces a revised draft. The revised draft targets the specific issues identified in the Critic Findings. It does not introduce new material not previously diagnosed.

After revision, the cycle repeats from Stage 3 (Verification) for the new draft. Governance is issued again. The cycle continues until Ratified.

**Rule:** The revision must be traceable to the Critic Findings that prompted it. If a revision introduces changes not justified by any Critic Finding, those changes belong in a new cycle, not the current one.

---

## The Review Card

After each cycle completes, the Review Card is recorded. It captures the state of the section at the point of governance.

```
Section Review
──────────────────────────────────────
Section: [identifier]
Draft version: [n]
Date: [date]

Dimensions:
  Intent:      [Strong | Appropriate | Needs Revision | Fails]
  Evidence:    [Strong | Appropriate | Needs Revision | Fails]
  Scope:       [Strong | Appropriate | Needs Revision | Fails]
  Clarity:     [Strong | Appropriate | Needs Revision | Fails]
  Confidence:  [Strong | Appropriate | Needs Revision | Fails]

Governance:  [Ratified | Minor Revision | Major Revision | Rewrite]
Notes: [specific issues that determined the governance decision]
──────────────────────────────────────
```

**Rule:** No dimension rated Fails may receive a Ratified governance decision. A Fails verdict on any dimension requires at minimum a Minor Revision targeting that dimension.

---

## What This Protocol Produces

Running this protocol against a document produces two artifacts:

1. **The document itself** — clean, complete, readable without reference to the process.
2. **The provenance record** — the complete history of how each section evolved: what was attempted, what was found, what was decided, and what changed.

These are different artifacts with different purposes.

The document is the claim.

The provenance record is the evidence that the claim was produced by a disciplined process — one in which failures were diagnosed and addressed, rather than accumulated silently.

---

## Relationship to Hermeneia

This protocol applies Hermeneia's cognitive architecture to the act of writing rather than to document analysis. The stages map directly:

| Writing Protocol Stage | Hermeneia Responsibility |
|---|---|
| Witness | Attention — recording what exists before interpretation |
| Discovery | Explorer — surfacing what is actually being attempted |
| Reconstruction | Architect — reconstructing the intent the evidence supports |
| Verification | Critic — evaluating whether the artifact fulfills its contract |
| Governance | Steward — deciding what happens next |
| Communication | Artist — producing the expression |

The methodology is not specific to Hermeneia. It is the general structure of disciplined inquiry applied to writing.

---

## Hermeneia Writing Protocol v1.0 — Compact Reference

```
For each section of the document:

0. WITNESS     Record the artifact exactly as it is.
1. DISCOVERY   State the Intent Hypothesis: what understanding is this attempting to produce?
2. RECONSTRUCT Ratify, revise, or reject the Intent Hypothesis.
3. VERIFY      Issue Critic Findings across: Intent, Evidence, Scope, Clarity, Confidence.
4. GOVERN      Decide: Ratified / Minor Revision / Major Revision / Rewrite.
5. COMMUNICATE Only now, write. Target the Critic Findings. Record the Review Card.
               Repeat from Stage 3 until Ratified.
```
