# RATIFICATION
### Hermeneia Constitutional Governance Process

> **Authority notice (2026-06-19):** This document is partially superseded by
> [`docs/00_Constitution.md`](docs/00_Constitution.md) and
> [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md). Constitutional
> change now proceeds through ratified amendments and append-only supersession,
> not solely through ADR replacement. Unaffected historical process remains
> inspectable.

**Purpose:** This document defines how open questions in `EPISTEMIC_BACKLOG.md` progress to ratified architectural decisions, how those decisions are protected after ratification, and how the costs of premature or incorrect decisions are recognized and tracked.

**Authority:** Same hierarchy as all constitutional documents:
Philosophy → Project Axioms → Constitution → Invariants → Ontology → Architecture → Specifications → Implementation → Research Literature.

---

## Part I: The Ratification Process

### Question Lifecycle

An ontology or architectural question progresses through the following states. No question may skip a state. No question may be implemented before it is Ratified.

```
Draft
  ↓
Research
  ↓
Discussion
  ↓
ADR Proposal
  ↓
Review
  ↓
Ratified
  ↓
Implemented
  ↓
Validated
```

---

### State Definitions

**Draft**
The question has been identified and added to `EPISTEMIC_BACKLOG.md`. Its scope is understood. Its dependencies have been mapped. No answer has been proposed.

Entry criteria: Question is registered in `EPISTEMIC_BACKLOG.md` with Priority, Constitutional Cost of Error, Dependencies, and Blocked packages.

Exit criteria: A research brief has been written that surveys relevant architecture documents, existing ADRs, and constitutional constraints. The research brief does not propose an answer — it surveys the decision space.

---

**Research**
The decision space has been surveyed. Constitutional constraints have been applied. The research literature has been consulted where relevant, with explicit notes on where literature conflicts with the Constitution.

Entry criteria: Research brief complete.

Exit criteria: A list of candidate answers has been produced, each with a constitutional compatibility assessment. At least one candidate is constitutionally viable. The research brief is committed to the repository as `docs/research/Q-PXXX-<slug>.md`.

---

**Discussion**
The candidate answers are under active consideration. For questions with Constitutional Cost of Error = Existential or High, this state requires at least one synchronous discussion session with the primary architect and steward. For Medium or Low cost questions, written discussion is sufficient.

Entry criteria: At least two candidate answers with constitutional compatibility assessments.

Exit criteria: A preferred candidate has been selected and the rationale documented. Edge cases and exclusion criteria have been addressed explicitly. The selected candidate is ready to be written as an ADR.

---

**ADR Proposal**
A formal Architecture Decision Record has been drafted. It follows the existing ADR format in `docs/adr/`. It includes:
- Context and problem statement
- Decision drivers
- Considered options
- Decision outcome
- Formal definition (for ontology questions: field-level schema)
- Inclusion criteria
- Exclusion criteria
- Examples
- Counterexamples
- Edge cases
- Serialization rules (if applicable)
- Provenance implications
- Validation rules
- Migration policy
- Consequences (positive and negative)

Entry criteria: Discussion complete. Preferred candidate selected.

Exit criteria: ADR document is complete and submitted for review.

---

**Review**
The ADR is under review. For questions with Constitutional Cost of Error = Existential, review must include explicit verification that the proposed decision:
1. Does not contradict the Philosophy.
2. Does not contradict the Project Axioms.
3. Does not contradict the Constitution.
4. Does not contradict the Invariants.
5. Does not create orphan nodes in the dependency graph (i.e. no downstream question is invalidated by the decision).

For all questions, the reviewer must attempt to construct a counterexample that breaks the proposed definition. If a counterexample is found, the question returns to Discussion.

Entry criteria: ADR Proposal complete.

Exit criteria: ADR is accepted with no outstanding counterexamples. Review sign-off documented in the ADR.

---

**Ratified**
The ADR has been accepted. The decision is now a constitutional commitment. It is recorded in the ADR with:

```
Status: RATIFIED
Version: 1.0
Date: YYYY-MM-DD
Supersedes: None
Ratified by: [name or role]
```

The corresponding question in `EPISTEMIC_BACKLOG.md` is updated:

```
Status: Ratified
ADR: ADR-XXXX
Ratified: YYYY-MM-DD
```

Implementation of the affected packages may now begin.

Entry criteria: Review complete. ADR accepted.

Exit criteria: Implementation is complete and the decision has been expressed in code.

---

**Implemented**
The ratified decision has been expressed in the codebase. The implementation is traceable to the ADR. No implementation detail may deviate from the ADR without triggering the amendment process (see Part II).

Entry criteria: Ratified.

Exit criteria: All tests specified in the ADR's validation rules pass. The implementation has been reviewed against the ADR for fidelity.

---

**Validated**
The implementation has been verified against all validation rules specified in the ADR. The constitutional invariant tests in `validation/invariants.py` and `validation/constitution.py` confirm compliance. The question is closed.

Entry criteria: Implemented. All specified tests pass.

Exit criteria: None. Validated is a terminal state. The decision is now part of the constitutional foundation.

---

## Part II: Amending a Ratified Decision

Once a question reaches **Ratified**, the decision it encodes is a constitutional commitment. It may not be changed informally, silently, or by implementation divergence.

A ratified constitutional decision may only be amended through the following process:

### Amendment Requirements

Any proposed amendment to a Ratified decision must include all of the following before the amendment may be accepted:

**1. Superseding ADR**
A new ADR that explicitly references the original and provides a complete replacement definition. The new ADR must pass the same Review criteria as the original.

**2. Migration Strategy**
A written strategy for converting all existing `.herm` bundles compiled under the original decision to conformance with the new decision, or a documented argument for why migration is not required. If migration requires UPDATE or DELETE on the observations or provenance tables, the amendment is constitutionally prohibited (AGENTS.md, Invariants 1 and 3).

**3. Backwards Compatibility Analysis**
A written analysis of every package that depends on the original decision and an assessment of whether the amendment breaks, modifies, or preserves each dependency. For Constitutional Cost of Error = Existential decisions, every downstream question in `QUESTION_DEPENDENCY_GRAPH.md` must be re-evaluated.

**4. Provenance Impact Assessment**
A written analysis of how the amendment affects the provenance chain. If the amendment changes the structure of Observation, Provenance, or any object that participates in the mandatory provenance chain (Article II), a full provenance audit must be performed on any existing corpus compiled under the original decision.

**5. Ontology Impact Assessment**
A written analysis of whether the amendment introduces, removes, or redefines any canonical ontology object, field, or relationship. If it does, the Canonical Object List (Q-P1-008) must be updated and the amendment must propagate to all affected schemas.

### Amendment Status Codes

When a Ratified decision is under amendment, it carries the status `Under Amendment` until the new ADR is accepted, at which point the original ADR receives status `Superseded` and the new ADR receives status `Ratified`.

No implementation may assume an `Under Amendment` decision remains in effect. Work on affected packages must pause until the amendment is resolved.

---

## Part III: Constitutional Debt

### Definition

**Constitutional Debt** is the accumulated cost of decisions made — implicitly or explicitly — before the relevant question has been ratified. It is distinct from technical debt, ontology debt, provenance debt, and perspective debt, and it is the most dangerous of all debt types because it corrupts the conceptual integrity of the system at the foundation rather than the surface.

Unlike technical debt, which can usually be paid by refactoring, constitutional debt may be impossible to pay if it has caused violations of the append-only constraint or invalidated the provenance chain.

### Taxonomy of Debt

Hermeneia recognizes five categories of debt, ordered from least to most dangerous:

| Debt Type | Definition | Example | Recovery Cost |
|---|---|---|---|
| **Technical Debt** | A known shortcut in implementation quality that will need to be revisited. | Temporary parser implementation that handles only PDFs. | Low. Replaceable without affecting other layers. |
| **Ontology Debt** | Two overlapping object definitions, missing field specifications, or undocumented objects (stubs without ADRs). | `ContinuityNode` existing in code without a definition. | Medium. Requires ADR and potential schema migration. |
| **Provenance Debt** | Missing, incomplete, or incorrect lineage information for a persisted object. | An Interpretation with no `source_observation_id`. | High. May require recompilation or invalidation of affected bundles. |
| **Perspective Debt** | A missing disciplinary viewpoint in the Hermeneutic Field for a given corpus or concept. | A corpus with no feminist or post-colonial reading. | High. Cannot be corrected by retroactive inference — requires new human contribution. |
| **Constitutional Debt** | Any implementation that proceeds before the relevant question has been ratified. | Writing the compiler before Q-P0-001 is ratified. | Existential. If the pre-ratification implementation conflicts with the eventual ratification, the append-only constraint may make recovery impossible. |

### Constitutional Debt Incurred by Common Anti-Patterns

The following choices constitute Constitutional Debt and must be avoided:

| Anti-pattern | Debt incurred | Why recovery may be impossible |
|---|---|---|
| Using `uuid4()` for Observation IDs before Q-P0-001 is ratified | Constitutional + Ontology | Any corpus compiled with UUID IDs cannot be merged with one compiled with deterministic IDs. The append-only constraint prevents rewriting existing Observation IDs. |
| Implementing Claim as a field on Interpretation before Q-P1-001 is ratified | Constitutional + Ontology | If Claim is later ratified as a first-class object, all existing Interpretations in the database are structurally incorrect — but the append-only constraint prevents retroactive correction. |
| Writing Perspective schema before Q-P0-003 is ratified | Constitutional | If Perspective is later distinguished more finely from Interpretation, the `.herm` schema cannot be migrated without violating the append-only constraint. |
| Implementing Architect and Artist before Q-P4-003 is ratified | Constitutional | If style and semantics cannot be separated, ADR-0003 must be reconsidered. An Artist implementation built on a potentially invalid ADR is constitutionally unauthorized. |
| Adding LLM imports to the compiler package | Constitutional | Violates Invariant 4 (Architectural Decoupling) immediately. Not a future risk — an active violation from the moment of introduction. |
| Treating research literature recommendations as architectural answers | Constitutional + Ontology | The research literature describes what others have done. Adopting it without an explicit constitutional compatibility check introduces foreign ontology into Hermeneia's foundation. |

### Tracking Constitutional Debt

Every instance of Constitutional Debt must be documented. A `CONSTITUTIONAL_DEBT.md` file should be maintained at the repository root with entries in the following format:

```markdown
## CD-001

**Incurred:** YYYY-MM-DD
**Type:** Constitutional / Ontology / Provenance / Perspective
**Question affected:** Q-PXXX
**Description:** [What was implemented prematurely or incorrectly]
**Impact:** [What it blocks or corrupts]
**Resolution required:** [What ADR or ratification is needed to discharge the debt]
**Status:** Open / Discharged
```

A debt entry may only be marked `Discharged` when the relevant question has been ratified and the implementation has been corrected to conform to the ratified definition.

---

## Part IV: The First Ratification Session

The next development session has one goal.

**Ratify Q-P0-001: What constitutes an Observation?**

This single question unlocks more implementation than any other. Its ratification permits:
- The `Observation` class fields
- The `Provenance` class fields
- The SQLite schema for `observations` and `provenance`
- The append-only repository insert methods
- The `observation_compiler.py` structural skeleton
- The entire `storage/` package foundation
- The `validation/invariants.py` immutability checks

Until it is ratified, compiler implementation is constitutionally prohibited.

### What the Session Must Produce

The session is not complete until all of the following have been produced and committed:

**1. Formal definition**
A single, unambiguous prose sentence defining what an Observation is. The definition must be precise enough that any two engineers, reading it independently, would produce the same Observation boundaries on the same source document.

**2. Inclusion criteria**
An explicit list of what qualifies as an Observation. Examples:
- A typographically complete sentence terminated by `.`, `?`, or `!`
- A dialogue turn terminated by a speaker change, if the source is a dialogue text
- [to be determined by the ratification session]

**3. Exclusion criteria**
An explicit list of what does not qualify as an Observation. Examples:
- Subsentential fragments that are not standalone propositions
- Page headers and footers
- Footnote markers within a sentence (the footnote itself may or may not be a separate Observation — this is an edge case to resolve)
- [to be determined by the ratification session]

**4. Examples**
A minimum of five examples drawn from real source texts (e.g. *The Great Gatsby*), showing how the definition applies to normal sentences.

**5. Counterexamples**
A minimum of five attempted Observations that the definition correctly excludes, with explanation of why they are excluded.

**6. Edge cases**
An explicit treatment of at least the following edge cases:
- A sentence that is syntactically malformed but semantically complete (e.g. "He went. And he stayed.")
- A sentence that spans a paragraph boundary in the source PDF
- A sentence containing an embedded block quotation
- A sentence containing a numbered list
- A footnote or endnote referenced within a sentence
- A sentence that is entirely punctuation or whitespace
- A sentence in a language other than English

**7. Serialization rules**
Exact specification of the `text` field: is it the verbatim string from the source, including whitespace? Is whitespace normalized? Are smart quotes preserved or converted? The answer must be testable.

**8. Provenance implications**
A statement of what Provenance fields are required and sufficient to uniquely identify the source of any given Observation. Must address: page number, paragraph number, sentence number, character offsets, document version hash.

**9. Validation rules**
A set of machine-executable rules that can verify an Observation is correctly formed. Examples:
- `len(observation.text) > 0`
- `observation.text` is a substring of the source document (verbatim check)
- `observation.paragraph >= 1`
- `observation.sentence >= 1`
- `observation.provenance_id` references a valid Provenance record
- [to be determined by the ratification session]

**10. Migration policy**
A statement of what happens when the Observation definition is amended in a future version. Under what circumstances is recompilation required? Under what circumstances are existing `.herm` bundles considered valid under the new definition?

### Ratification Record

When the session is complete, the ADR must be marked:

```
Status: RATIFIED
Version: 1.0
Date: YYYY-MM-DD
Supersedes: None
Ratified by: [name or role]
```

And the corresponding entry in `EPISTEMIC_BACKLOG.md` must be updated:

```
Status: Ratified
ADR: ADR-0006 (or next available number)
Ratified: YYYY-MM-DD
```

After that update is committed, compiler implementation may begin.

---

## Appendix: Ratification Checklist

Use this checklist for every question moving from Discussion to ADR Proposal.

```
[ ] Formal definition written (single unambiguous sentence)
[ ] Inclusion criteria enumerated
[ ] Exclusion criteria enumerated
[ ] Minimum 5 examples provided
[ ] Minimum 5 counterexamples provided
[ ] All known edge cases explicitly addressed
[ ] Serialization rules specified (if applicable)
[ ] Provenance implications stated
[ ] Validation rules specified (machine-executable)
[ ] Migration policy stated
[ ] Constitutional compatibility verified:
    [ ] Does not contradict Philosophy
    [ ] Does not contradict Project Axioms
    [ ] Does not contradict Constitution (all 6 Articles)
    [ ] Does not contradict Invariants (all 5)
    [ ] Does not invalidate any downstream question in EPISTEMIC_BACKLOG.md
[ ] ADR drafted in standard format
[ ] ADR reviewed and accepted
[ ] EPISTEMIC_BACKLOG.md updated (Status: Ratified, ADR reference)
[ ] QUESTION_DEPENDENCY_GRAPH.md updated (milestone progress)
[ ] Implementation may begin
```

---

*End of RATIFICATION.md*

*This document is itself a constitutional document. It may be amended only through the process it defines — by ADR, with migration strategy, backwards compatibility analysis, provenance impact assessment, and ontology impact assessment.*
