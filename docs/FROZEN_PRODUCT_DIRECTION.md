# Frozen Product Direction — Hermeneia

**Status:** Canonical product direction  
**Orientation synchronized:** 2026-08-29  
**Companion documents:** `CLAUDE.md` (architecture/validation orientation), `IMPLEMENTATION_STATUS.md` (dated operational state), `docs/01_Authority_Index.md` (constitutional authority routing)

This document governs the product experience: where the workbench is going and why. It does not outrank the Constitution, ratified amendments, invariants, active ADRs, or implementation specifications within their scopes.

---

## 1. Product in one line

> Hermeneia is a **reading workbench for governed interpretation**: the Reader remains the center of attention while tools unfold around the work.

Hermeneia is not primarily a collection of pages, a chatbot wrapper, a summarizer, or a report generator. Its product identity is a way of studying in which evidence, attention, questions, machine proposals, human judgment, synthesis, expression, and audit remain distinguishable.

---

## 2. The durable product method

The moat is the methodology, not the screen arrangement.

- **Governed by a question.** The governing question is a compass, not a conclusion to validate.
- **Reading first.** Human encounter with the source remains primary.
- **Attention is preserved.** Highlights, questions, notes, concepts, Companion exchanges, and selected machine suggestions can become inspectable parts of how the inquiry developed.
- **Machine proposals remain proposals.** Generated material does not become authoritative merely because a model produced it.
- **Lineage remains walkable.** Important claims and artifacts should be traceable to the evidence and judgments that produced them.
- **Canonical and derived remain distinct.** Projections can be regenerated; evidence and governed history are not silently rewritten.
- **Expression follows understanding.** Blueprint and Architect protect meaning before Artist rendering.
- **Critic evaluates; Steward decides.** Evaluation does not become governance merely because it is automated.

The sentence that governs product design remains:

> **The tools should unfold around the work.**

---

## 3. Reader-centered interaction model

```text
Reader        = main canvas
Companion     = persistent assistant / conversational instrument
Question      = investigation compass
Scope         = what the current operation is allowed to know
Perspectives  = interpretive frames
Workstation   = tools brought to the Reader
Timeline      = accumulated attention / study history
```

The right side should remain quiet and intentional: Companion is a coherent docked conversation surface; other support tools should unfold rather than permanently stack.

The bottom workstation is a **mode switcher**, not a second navigation system. Exactly one primary workstation mode should dominate at a time unless a shared utility is deliberately persistent.

The user should always be able to return cleanly to the book.

---

## 4. Current workflow the product teaches

The original linear pipeline has matured into a Reader-centered investigation loop:

```text
Question
  ↓
Read
  ↓
Mark / Notice / Ask
  ↓
Search / Group / Relate
  ↓
Perspective / Compare
  ↓
Steward what survives
  ↓
Refine Blueprint
  ↓
Architect compiles semantic obligations
  ↓
Choose ExpressionProfile + execution configuration
  ↓
Artist renders
  ↓
Critic audits
  ↓
Ratify / Revise / Reject
  ↓
Record / Preserve
  ↺
Return to inquiry when new evidence changes understanding
```

This is not a requirement that every user manually operate every architectural stage. The workbench should progressively disclose machinery as the investigation requires it.

---

## 5. What is already product reality

The following should not be treated as future roadmap assumptions:

- Reader-first shell and workbench
- docked Companion and support-tool geography
- Reader-side Corpus Search and literal concordance
- attention timeline and Field Notes
- bottom workflow/workstation rail
- workspace lifecycle and isolated named workspaces
- first-run upload and recovery paths
- durable Reader highlights/annotations
- explicit capture intents: highlight, note, question, concept, observation candidate
- question compass and reading-first Guide
- question-relative Corpus and Lab framing
- Blueprint / Render / Critic workstation chain
- Voice / ExpressionProfile capture
- Draft Preview → Ratify → Record
- workspace bundle export/import/restore
- Perspective definitions/revisions and governed Perspective-run infrastructure
- Focus mode, large-text support, inline selection read-aloud, and page read-aloud
- provider registry, credential-source boundaries, model catalogs, and local-runtime foundations

Older staged PR lists are historical evidence of how the product was assembled, not a current implementation queue.

---

## 6. Current product priorities

### P1 — Sustain real use

The highest-value source of truth now is actual use on real corpora and manuscripts.

```text
Use the product first.
Record friction when it appears.
Do not redesign from imagination.
```

The Reader should be judged by whether someone can stay in the work for long periods without interface friction, provenance ambiguity, or needless interruption.

### P1 — Whole-study synthesis

Hermeneia has become strong at capturing the study. The next major product challenge is helping the user reason over the **whole accumulated study record**, not one observation at a time.

Evidence Board / study-level lineage should help the user:

- inspect all captured material;
- organize and reorganize buckets;
- see unused evidence;
- compare motifs and themes;
- run governed analysis over selected groups;
- attach evidence groups to Blueprint sections;
- preserve authorship/provenance distinctions;
- understand how the investigation changed over time.

The Blueprint should behave as a living working map while canonical committed revisions remain append-only.

### P1 — Coherent workstation behavior

Search, Timeline, Field Notes, Blueprint, Render, Critic, Voice, Draft, Record, and future modes should feel like one instrument with different modes—not unrelated mini-pages sharing a tab strip.

### P1/P2 — Explicit execution control

Connections must distinguish:

```text
Connection ≠ Provider ≠ Model ≠ Model Version ≠ Configuration ≠ Perspective
```

The product should make it easy to know:

- what runtime is connected;
- which models are actually available;
- what configuration will run;
- what exact configuration actually ran;
- what leaves the machine;
- how to recover from missing credentials/models/runtime state.

Saved configurations, defaults, assignments, and per-run overrides are execution conveniences. They do not become epistemic identity.

### P2 — Model Observatory

Longitudinal model analytics are valuable **after** run identity, Scope, Perspective, evaluation, and stewardship lineage are trustworthy.

The Observatory is a derived research/decision surface, not the center of the product and not a universal model leaderboard.

### P2 — Developer/support channel

A human Developer channel may provide support, feedback, questions, and optional external support links. It remains product infrastructure outside the epistemic pipeline.

---

## 7. Scope as an attention boundary

Hermeneia may know more than the Reader should have to see at once.

Scope answers:

> **What existing material is this operation allowed to know about right now?**

Scope is initially a selection/boundary layer, not a new canonical epistemic class.

Search finds material.  
Buckets organize material.  
Relationships connect material.  
Scope determines what participates now.  
Perspective determines from where the material is examined.

A provider-backed run should preserve the resolved input boundary that actually participated.

---

## 8. Perspective, Blueprint, Architect, and Expression remain separate

The workbench should make these distinctions understandable without requiring the user to learn ontology first.

```text
Perspective
  From where are we looking?

Blueprint
  What do we currently understand and intend to communicate?

ArchitectPlan
  What semantic obligations must survive communication?

ExpressionProfile
  Under what audience/language/voice/tone/rhetorical constraints may it be expressed?

Model configuration
  What execution system and inference conditions will perform the run?
```

Do not collapse Perspective into style.  
Do not collapse Perspective into model identity.  
Do not collapse Blueprint into prose.  
Do not collapse ArchitectPlan into a prompt.  
Do not let Artist reconstruct an alternate semantic contract.

---

## 9. Multi-corpus direction

Multi-corpus capability must not destroy close-reading focus.

One corpus/document may remain primary in the Reader while explicitly admitted secondary material participates through Scope, search, buckets, relationships, or Perspective work.

The machine may expose relationships across a larger evidence field. The human decides what enters the current act of inquiry.

---

## 10. Product guardrails

Do not:

- turn Hermeneia back into a page-first pipeline UI;
- let tools permanently crowd out the Reader;
- silently expand model Scope because more workspace material exists;
- silently send secondary corpora or private investigation material to providers;
- blur user-authored and model-authored material;
- auto-promote machine suggestions into governed understanding;
- add ontology merely to support a UI convenience;
- make model/provider configuration part of Perspective semantics;
- make analytics replace run lineage;
- infer that a product feature is missing merely because an older roadmap predates its implementation.

---

## 11. Validation discipline

The correct current product-development loop is:

```text
real use
→ friction observed
→ classify whether the problem is UX, projection, configuration, derivation, implementation, or architecture
→ choose the smallest lawful correction
→ test
→ use again
```

Hermeneia should earn complexity through demonstrated need.

---

## 12. Release direction

A v1.0 release candidate remains a target, not a claimed completed release.

A credible release candidate should demonstrate at minimum:

- clean installation and workspace creation;
- reliable Reader-first use on multiple real corpora;
- trustworthy capture and provenance;
- coherent whole-study movement toward synthesis;
- working Blueprint → Architect → Artist → Critic → Steward chain;
- explicit provider/model/runtime boundaries;
- preservation/export/restore confidence;
- stable tests and repeatable smoke validation;
- documentation that describes the product that actually exists.

Communication artifacts—demo video, pitch deck, public positioning—should follow demonstrated product reality rather than outrun it.

---

## North stars

```text
Reader first.
Tools unfold.
Nothing steals the work.
```

```text
A governing question is a compass, not a conclusion.
```

```text
The machine may help organize and examine the evidence.
The human remains responsible for what survives.
```

```text
Preserve how understanding developed, not merely what the final answer said.
```
