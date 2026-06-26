# Constitution of Hermeneia

**Status:** RATIFIED  
**Version:** 1.0  
**Date:** 2026-06-19  
**Ratified by:** Primary Human Steward  
**Authority:** Highest

---

## Preamble

Hermeneia preserves evidence, accumulates interpretations, constrains
communication through explicit semantic contracts, and records every act of
understanding as an append-only, auditable lineage.

Hermeneia is a durable epistemic ledger. It shall preserve the record before
permitting interpretation, preserve plurality before selecting expression, and
preserve ancestry before accepting any generated result.

---

## Article I — Immutable Ancestry

Every Hermeneia object shall possess permanently verifiable lineage to
immutable ancestors.

No descendant shall modify, replace, or obscure the evidence from which it
derives.

Knowledge shall accumulate monotonically through append-only objects and
relations.

---

## Article II — Auditability Over Determinism

Deterministic objects shall be reproducible from their immutable ancestors.

Nondeterministic objects shall preserve the complete inputs, provider identity,
model identity, configuration, execution metadata, output, and provenance
necessary for independent audit and evaluation.

Byte-for-byte reproduction is required where the process is deterministic.
Where an external or stochastic system makes byte-for-byte reproduction
impossible, complete auditability is required instead.

---

## Article III — The Evidence Boundary

The forensic evidence chain is:

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
```

`SourceDocument` is the original artifact.

`SourceExtraction` is the immutable record of parser output exactly as
encountered, together with its source location and extraction custody.

`Observation` is one immutable semantic unit, canonically one sentence,
segmented from a `SourceExtraction` without altering its characters.

Parser output is not an Observation. An Observation may not exist without its
parent SourceExtraction.

Normalization, tokenization, whitespace mapping, field extraction, and other
computational conveniences are derived metadata. They shall never replace or
mutate forensic evidence.

---

## Article IV — Anti-Helpfulness

Hermeneia preserves reality rather than an idealized version of reality.

No compiler, model, interface, or maintainer may silently correct source text,
normalize punctuation, resolve ambiguity, repair malformed spacing, improve
grammar, or otherwise make evidence more convenient.

Any correction or reinterpretation shall be represented as a descendant claim,
never as a mutation of evidence.

---

## Article V — Occurrence Identity

Evidence identity shall represent an occurrence, not merely textual
equivalence.

The canonical Observation identity is:

```text
SHA256(canonical(source_hash, source_locator, raw_text))
```

The canonical encoding and framing of these components shall be specified by
the active storage specification and shall be deterministic.

Textual equivalence may be represented separately as:

```text
semantic_hash = SHA256(UTF8(raw_text))
```

Normalization, sentence splitting algorithms, interpretations, and downstream
artifacts shall not affect occurrence identity.

---

## Article VI — Provenance and Chain of Custody

SourceExtraction is an object. Provenance is the orthogonal metadata and
relations that describe lineage and custody.

Every generated object shall identify its direct parent or parents. No object
may float without ancestry.

At minimum, the forensic chain shall preserve:

- the parent SourceDocument;
- the parent SourceExtraction;
- source hash and source locator;
- parser identity and parser version;
- extraction timestamp;
- original page or region coordinates where available; and
- the append-only chain of custody.

Generation shall fail when required provenance cannot be established.

---

## Article VII — Epistemic Classes

Every canonical object shall have an explicit epistemic class:

| Object | Epistemic class | Purpose |
|---|---|---|
| SourceDocument | Artifact | Original object |
| SourceExtraction | Evidence | Exact extraction |
| Observation | Evidence | Atomic observed unit |
| Perspective | Frame | Interpretive lens |
| Interpretation | Claim | Meaning proposed under a frame |
| NarrativeBlueprint | Synthesis | Structured organization of claims |
| ArchitectPlan | Contract | Communication obligations |
| ExpressionProfile | Constraint | Stylistic and rhetorical limits |
| RenderedNarrative | Expression | Human-facing realization |
| CriticReport | Evaluation | Assessment of expression against contract |

An object may reference objects beneath it. It shall not acquire authority to
rewrite them.

---

## Article VIII — Canonical Pipeline

The constitutional pipeline is:

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
    ↓
Interpretation
    ↓
Perspective
    ↓
NarrativeBlueprint
    ↓
ArchitectPlan
    ↓
ExpressionProfile
    ↓
Artist
    ↓
RenderedNarrative
    ↓
Critic
    ↓
Stewardship
```

Stages shall not be added, removed, merged, renamed, or reordered without a
ratified constitutional amendment.

---

## Article IX — Synthesis, Contract, and Expression

The NarrativeBlueprint answers: **What should be communicated?**

The ArchitectPlan answers: **What obligations must every valid communication
satisfy?**

The ExpressionProfile constrains how those obligations may be expressed.

The ArchitectPlan is the compiled semantic contract and the canonical
interface between synthesis and expression. An Artist provider shall fulfill
the ArchitectPlan; it shall not independently reconstruct the communication
obligations from the NarrativeBlueprint.

The Artist provider is replaceable. The contract and its ancestry are not.

---

## Article X — Monotonic Knowledge

Hermeneia shall append, never overwrite.

A later interpretation shall coexist with earlier interpretations. A new
parser shall create a new SourceExtraction. A new Perspective shall create a
new Interpretation. A new Artist invocation shall create a new
RenderedNarrative. A new Critic invocation shall create a new CriticReport.

Supersession changes authority status. It shall not erase history.

---

## Article XI — Human Stewardship

Hermeneia exists to increase human interpretation, not replace it.

Ambiguity shall be exposed rather than silently collapsed. Multiple
perspectives shall be preserved. Perspective debt and uncertainty shall remain
visible.

Human stewardship retains final authority over ratification, supersession, and
release.

---

## Article XII — Read-Only Integrity

Read-only operations shall have zero side effects.

An HTTP `GET`, lineage inspection, audit query, or other read operation shall
not create schemas, migrate storage, seed profiles, create objects, modify
timestamps, or perform any mutation.

---

## Article XIII — Singular Storage Authority

Hermeneia shall have one authoritative portable storage format.

The active storage specification shall define the `.herm` bundle, its required
contents, identity encodings, append-only constraints, and migration rules.
Competing authoritative formats are forbidden.

---

## Article XIV — Executable Constitutional Law

Constitutional invariants shall be expressed as executable tests.

The implementation is constitutionally compliant only when those tests pass.
Code coverage alone is not evidence of compliance.

Refactoring is permitted. Violation of constitutional behavior is not.

---

## Article XV — Authority and Amendment

The authority hierarchy is:

```text
Constitution
    ↓
Authority Index
    ↓
Ratified Amendments
    ↓
ADRs
    ↓
Implementation Documents
    ↓
Code
    ↓
Generated Artifacts
```

No lower authority may contradict a higher authority.

Constitutional text, amendments, and ADRs are historical records and shall not
be silently rewritten. A later authority may supersede an earlier authority
only through an explicit append-only supersession relation recorded in the
Authority Index.

Constitutional change requires ratification by the Primary Human Steward.

---

## Governing Invariant

> Every object in Hermeneia shall maintain permanently verifiable lineage to
> immutable ancestors. No descendant shall modify, replace, or obscure the
> evidence from which it derives. Deterministic acts shall be reproducible;
> nondeterministic acts shall be independently auditable.

