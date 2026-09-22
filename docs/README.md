# Hermeneia Documentation Map

Hermeneia contains documents from several development eras and with several different authority levels.

Do not infer authority from filename age, numeric prefix, detail level, or proximity to the code.

For constitutional conflicts, always resolve through:

`01_Authority_Index.md`

---

## Start here

For a capable fresh reader or agent, the recommended order is:

1. `../README.md` — repository landing page and current identity
2. `What_Hermeneia_Is.md` — project identity statement
3. `ORIGIN_AND_EVOLUTION.md` — founding Gatsby/Treasury use case and how the system grew beyond it
4. `FROZEN_PRODUCT_DIRECTION.md` — current product direction
5. `../IMPLEMENTATION_STATUS.md` — dated operational state
6. `01_Authority_Index.md` — canonical authority routing
7. `00_Constitution.md` — highest governing law
8. `02_Constitutional_Invariants.md` — executable constitutional obligations
9. `05_Architecture.md` / `06_Ontology.md` / active ADRs and specifications as needed

For implementation work, also read `../AGENTS.md`.

For Claude-oriented work, also read `../CLAUDE.md`.

---

## Document classes

### Constitutional authority

These govern the system within their declared scope:

- `00_Constitution.md`
- `01_Authority_Index.md`
- `02_Constitutional_Invariants.md`
- `amendments/`
- active ADRs under `adr/`
- active implementation specifications under `specs/`

The Authority Index is the routing table for determining what is active, superseded, retired, or draft.

### Current identity and product orientation

These explain what the system currently is and where the product is going, but do not outrank constitutional law:

- `What_Hermeneia_Is.md`
- `FROZEN_PRODUCT_DIRECTION.md`
- `ORIGIN_AND_EVOLUTION.md`
- `Architecture_Patterns.md`
- `FUTURE_ARCHITECTURE_NOTES.md` — explicitly non-authoritative future ideas

### Dated operational state

- `../IMPLEMENTATION_STATUS.md`
- `../CLAUDE.md`

These are synchronization/orientation documents. They may become stale as code and issues advance. Do not treat an older implementation snapshot as stronger than current repository evidence or governing authority.

### Implementation verification records

- [`2026-09-22 — Preservation build digests`](verification/2026-09-22-preservation-build-digests.md)
  — demonstrated missing-digest bypass, verifier correction, tests, and remaining limits.
- [`2026-09-22 — Compile emitted bytes`](verification/2026-09-22-compile-emitted-bytes.md)
  — output/hash race, atomic artifact replacement, refusal checks, and regression evidence.
- [`2026-09-22 — Manifest captured bytes`](verification/2026-09-22-manifest-captured-bytes.md)
  — parse/hash divergence, shared byte capture, later drift refusal, and regression evidence.
- [`2026-09-22 — Atomic build record`](verification/2026-09-22-atomic-build-record.md)
  — interrupted record writes, private staging, atomic replacement, and failure evidence.

These records describe bounded implementation evidence; they do not amend authority.

### Ratification-era root artifacts

The following root files preserve the architecture-discovery / ratification process:

- `../EPISTEMIC_BACKLOG.md`
- `../QUESTION_DEPENDENCY_GRAPH.md`
- `../RATIFICATION.md`

They remain scientifically and historically useful, but parts of their internal authority language predate the ratified 2026-06-19 Constitution and Authority Index.

Therefore:

```text
historical/internal hierarchy text
!= current authority routing
```

When they disagree with `01_Authority_Index.md`, the current Authority Index controls.

`RATIFICATION.md` already carries a partial-supersession notice. The backlog and dependency graph should be read as preserved research/governance lineage rather than as independent replacements for current constitutional authority.

### Historical / superseded constitutional material

Examples include:

- `03_Constitution.md`
- `04_Invariants.md`
- ADRs marked superseded or superseded-in-part in the Authority Index

These are preserved for lineage. They must not silently regain authority because an agent discovers them first.

### Early conceptual notes

Several small numbered documents such as `01_problem_statement.md`, `02_core_thesis.md`, `08_epistemology.md`, `09_hermeneutic_field.md`, and related files preserve early conceptual development.

They are useful historical orientation unless another active authority explicitly gives them current governing status.

Do not read the numeric sequence as a modern canonical specification series.

### Research and papers

Material under `papers/`, research-oriented documents, and experimental notes may contain hypotheses, arguments, comparisons, and findings.

Research evidence can pressure architecture. It does not silently amend constitutional authority.

---

## Identity distinction

The repository has evolved materially from its founding use case.

The original Gatsby/Treasury work remains valid lineage and a useful demonstration, but it is no longer the complete product definition.

Current shorthand:

```text
origin
= AI-assisted Gatsby essays with provenance, human authorship boundaries,
  and culturally distinct interpretive lenses

current system
= operating environment for the disciplined evolution of understanding

current product
= Reader-centered workbench for governed interpretation
```

See `ORIGIN_AND_EVOLUTION.md` for the full relationship.

---

## Corpus / fixture distinction

Gatsby remains a useful founding corpus and real-corpus validation fixture.

It is not a special architectural dependency.

See `../corpora/README.md` for the current multi-corpus framing.

---

## Cleanup rule

Prefer:

- indexes;
- explicit status banners;
- authority routing;
- supersession notices;
- preserved lineage;

before destructive renaming or deletion.

A confusing historical document should normally be labeled and routed before it is removed.

The goal is not to make the history look linear.

The goal is to make current authority and historical evolution legible at the same time.
