# ADR-0016: Reflection Is Not a Canonical Ontology Object

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-18  
**Supersedes:** None  
**Closes:** Q-P0-004 in EPISTEMIC_BACKLOG.md  
**Constitutional Cost of Error:** High

---

## Context

`Reflection` appears in the epistemology chain documented in `docs/08_epistemology.md`, between Dialogue and Narrative. A class stub exists at `hermeneia/ontology/reflection.py`. It does not appear in `docs/06_Ontology.md` or `docs/specs/ontology.spec.md`.

The question is whether Reflection belongs in the canonical ontology — as a stored, provenance-tracked object — or whether it names a human cognitive act that produces outputs stored through other canonical objects.

This matters because if Reflection is a first-class stored object, it needs a schema, a provenance chain, a place in the `.herm` database, and an ADR for its fields. If it is a human cognitive act, the class stub at `reflection.py` should be removed.

---

## Decision

**Reflection is NOT a canonical ontology object.**

Reflection is a human cognitive act: the act of standing back from an accumulated Hermeneutic Field and noticing patterns, gaps, contradictions, and implications across the whole. It is an internal epistemic event, not a stored artifact.

The outputs of a Reflection are stored through the objects that already exist in the ontology:

| Output of Reflection | Stored as |
|---|---|
| A new question surfaced by noticing a gap | A `Dialogue` entry of `type: question` |
| A new Interpretation arising from synthesizing multiple Observations | An `Interpretation` object with `derivation_type: synthesis` |
| A new Perspective opened by recognizing a missing frame | A `Perspective` declaration |
| A noticed contradiction between two Perspectives | A `FieldContradiction` annotation on two Relationships (see ADR-0023) |
| The decision to begin narrating | The creation of a `NarrativeBlueprint` |

Reflection is the act that motivates these outputs. It is not itself an output. Storing the act of noticing in the database would require modeling a subjective cognitive event as an objective record — a constitutional violation (Observations are objective records of source content; Reflections are subjective internal states).

---

## The Class Stub Must Be Removed

The stub at `hermeneia/ontology/reflection.py` is an unauthorized ontology object. It was created before Q-P0-004 was ratified, constituting Constitutional Debt (see RATIFICATION.md Part III). This ADR discharges that debt.

**Required action:** Delete `hermeneia/ontology/reflection.py`. If it is imported anywhere in the codebase, those imports must be removed or redirected to the appropriate canonical object.

---

## What Belongs Between Dialogue and Narrative?

The epistemology chain places Reflection between Dialogue and Narrative. This position is conceptually correct — it names the cognitive transition from accumulated field data to narrative intent. But the transition is not a stored object; it is a human decision.

The NarrativeBlueprint is what Reflection produces when it is ready to be expressed. The `NarrativeBlueprint` captures the steward's intent ("I want to tell this story, from these Perspectives, starting from these Observations"). The Reflection that generated that intent is not separately stored.

---

## Constitutional Alignment

- **Article I** (Reality precedes interpretation): Reflection is an internal cognitive state, not an external observable fact. Storing it as a database record would blur the line between what is observed and what is privately experienced.
- **Axiom 1** (Immutability): An internal cognitive state cannot be made immutable in any meaningful sense. Reflection is recursive by nature — stewards reflect on their reflections. A stored Reflection object would immediately require versioning of internal states, which is architectural complexity with no epistemic payoff.

---

## Consequences

**Positive:**
- The ontology is simplified. Reflection as a stored object would have created significant design questions (Who authors a Reflection? Can AI generate a Reflection? Is a Reflection versioned?). All of these questions are dissolved.
- The outputs of Reflection are already covered by existing canonical objects. No epistemic information is lost.

**Negative:**
- The concept of Reflection remains important in the documentation and philosophy of the system, but it has no implementation. Newcomers may expect to find it in the codebase and find nothing. The epistemology documentation must be updated to clarify that Reflection names a human act, not a stored object.

---

## Alternatives Considered

**Alternative: Reflection as a steward journal entry — a free-text note with timestamp and provenance**  
Considered. A `StewardNote` object (free-text, dated, attributed to a steward) was considered as a home for Reflection. Rejected. A StewardNote does not carry the epistemic weight the term "Reflection" implies, and a free-text note is not machine-processable. If steward notes are needed for the system, they should be proposed as a separate lightweight object in a future ADR — not called Reflection.

**Alternative: Reflection as a synthetic Interpretation — a high-level claim synthesizing many Observations**  
Rejected. High-level synthetic claims are already representable as Interpretations with `derivation_type: synthesis`. There is no need for a separate class.
