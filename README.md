# Hermeneia

> **An operating environment for the disciplined evolution of understanding.**

Hermeneia is a local-first, evidence-preserving, human-stewarded environment for inquiry. It keeps source evidence, human attention, questions, machine proposals, interpretations, Perspectives, synthesis, expression, evaluation, and governance distinguishable while preserving how they relate over time.

It is not primarily an AI, chatbot, document analyzer, essay generator, or summarizer.

At the product level, Hermeneia is a **Reader-centered workbench for governed interpretation**: the work remains primary while tools unfold around it.

---

## Origin and evolution

Hermeneia began with a concrete Department of the Treasury hiring exercise involving essays on *The Great Gatsby*.

The original challenge was not simply to produce good essays. It was to use AI tools while preserving a defensible record of human authorship and judgment, grounding claims in the source corpus, and examining the same text through different cultural and semantic lenses.

That use case still applies. It no longer defines the limits of the system.

The project evolved from:

```text
AI-assisted Gatsby essay provenance
→ governed corpus interpretation
→ constitutional epistemic architecture
→ Reader-centered investigation workbench
→ operating environment for disciplined understanding
```

See [`docs/ORIGIN_AND_EVOLUTION.md`](docs/ORIGIN_AND_EVOLUTION.md) for the full lineage.

---

## Core claim

Reliable AI-assisted inquiry requires preserving the evolution of understanding by separating the cognitive responsibilities through which understanding develops.

Hermeneia therefore preserves distinctions such as:

```text
what the source says
!= what a machine proposes
!= what a human notices
!= what a steward accepts
!= what a Perspective contributes
!= what a projection renders
```

Generated content does not become authoritative merely because a model produced it.

A polished projection does not become the evidentiary record merely because it is useful.

---

## Cognitive responsibilities

```text
Explorer       surfaces candidate interpretations from evidence
Architect      reconstructs semantic obligations from stewarded understanding
Artist         realizes understanding in a chosen expressive form
Critic         evaluates whether expression preserved declared obligations
Steward        exercises human judgment and governance
```

These are cognitive responsibilities, not merely software modules.

`Witness` remains under investigation as attention-before-interpretation. Witness-oriented interfaces and experiments may exist without promoting Witness into canonical ontology merely because it is useful.

---

## Reader-centered investigation

The original linear pipeline has matured into an investigation loop:

```text
Question
  ↓
Read
  ↓
Notice / Mark / Ask
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
```

The accumulated study record—not merely the final answer—is a durable object of value.

---

## Constitutional evidence boundary

The ratified evidence chain is:

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
```

Evidence is preserved rather than silently repaired. Corrections, interpretations, readable projections, and other conveniences remain descendants of the preserved record.

Current constitutional authority always resolves through [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md).

---

## Repository map

| Surface | Role |
|---|---|
| [`docs/00_Constitution.md`](docs/00_Constitution.md) | Highest governing law |
| [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md) | Canonical authority / supersession routing |
| [`docs/02_Constitutional_Invariants.md`](docs/02_Constitutional_Invariants.md) | Executable constitutional obligations |
| [`docs/What_Hermeneia_Is.md`](docs/What_Hermeneia_Is.md) | Current project identity |
| [`docs/ORIGIN_AND_EVOLUTION.md`](docs/ORIGIN_AND_EVOLUTION.md) | Founding Gatsby/Treasury lineage and system evolution |
| [`docs/FROZEN_PRODUCT_DIRECTION.md`](docs/FROZEN_PRODUCT_DIRECTION.md) | Current Reader-centered product direction |
| [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) | Dated operational snapshot |
| [`AGENTS.md`](AGENTS.md) | General agent operating rules |
| [`CLAUDE.md`](CLAUDE.md) | Claude-oriented validation-phase orientation |
| [`docs/README.md`](docs/README.md) | Documentation classes and reading order |

Do not infer current authority from numeric filename order, document age, or detail level.

---

## Current product reality

Hermeneia currently includes, in bounded implemented forms:

- Reader-centered workbench and persistent Companion;
- corpus search, highlights, questions, notes, concepts, observations, buckets, and attention history;
- durable named workspaces and Workspace Bundle export/import/restore;
- Perspective definitions and governed Perspective-run infrastructure;
- Blueprint → Architect → Artist → Critic → Steward workflows;
- Draft Preview → Ratify → Record;
- provider registry, model catalogs, local/cloud runtime foundations, and credential-source boundaries;
- provenance, hashing, preservation, release, and constitutional compliance infrastructure;
- research and evaluation infrastructure for real-corpus use.

The exact dated operational state lives in [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md). Older roadmap checkboxes should not be used to reconstruct current completion.

---

## Governing principles

- **Evidence before interpretation.** Preserve the record before improving its readability or usefulness.
- **Explicit provenance.** Important artifacts retain inspectable ancestry and origin.
- **Human stewardship.** Machines may preserve, transform, propose, compare, and evaluate; human authority remains explicit.
- **Plurality without forced consensus.** Perspectives and disagreement remain traceable.
- **Canonical vs derived.** Projections may be regenerated; canonical evidence and governed history are not silently rewritten.
- **Conservation of ontology.** Earn new ontological objects through demonstrated need.
- **Provider independence.** Models and providers are participants and execution infrastructure, not the identity of the system.
- **Real-use validation.** Prefer observed friction over imagined redesign.

---

## Quick start

Hermeneia requires Python 3.11+.

```bash
pip install -e .
herm serve
```

Create and launch an isolated workspace:

```bash
herm workspace create "The Second Sale"
herm serve --workspace "The Second Sale"
```

Inspect current pipeline/runtime health:

```bash
herm health
```

Exercise the explicit cognitive pipeline when appropriate:

```bash
herm explorer discover --limit 30 --provider anthropic
herm architect OBS-23
herm artist OBS-23 --provider anthropic --all-profiles
herm critic OBS-23
herm trace OBS-23
```

Provider names and available models are runtime concerns, not constitutional facts.

---

## Research program

| Work | Role |
|---|---|
| *Hermeneia* | Reference implementation and research environment |
| *Persistent Understanding Architecture (PUA)* | Architectural framework |
| *Semantic Contract Fulfillment (SCF)* | Evaluation / benchmark methodology |
| *Toward an Ecology of Intelligence* | Philosophical foundation |

Key papers:

- [`docs/papers/hermeneia_white_paper.md`](docs/papers/hermeneia_white_paper.md)
- [`docs/papers/scf_position_paper.md`](docs/papers/scf_position_paper.md)

Research artifacts are evidence from an active program of inquiry. They do not prove universal generalization beyond the corpora, experiments, and implementations actually examined.

---

## Current phase

**Validation Phase — active development.**

The original architecture freeze has been lifted. The foundation is treated as stable against preference, not against evidence.

Current work emphasizes:

- sustained real-corpus and manuscript use;
- whole-study synthesis from accumulated study records;
- Reader/workstation coherence;
- explicit Scope and provider/model/runtime boundaries;
- preservation and restore confidence;
- empirical evaluation and research instrumentation;
- a stable release path only after demonstrated use warrants it.

---

## Reading order

For a fresh researcher or agent:

1. [`README.md`](README.md)
2. [`docs/What_Hermeneia_Is.md`](docs/What_Hermeneia_Is.md)
3. [`docs/ORIGIN_AND_EVOLUTION.md`](docs/ORIGIN_AND_EVOLUTION.md)
4. [`docs/FROZEN_PRODUCT_DIRECTION.md`](docs/FROZEN_PRODUCT_DIRECTION.md)
5. [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)
6. [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md)
7. [`docs/00_Constitution.md`](docs/00_Constitution.md)
8. [`docs/02_Constitutional_Invariants.md`](docs/02_Constitutional_Invariants.md)
9. [`docs/README.md`](docs/README.md) for historical/current documentation routing

For implementation, read [`AGENTS.md`](AGENTS.md) before modifying architecture-sensitive code.

---

## License and citation

Hermeneia is distributed under the MIT License. See [`LICENSE`](LICENSE).

Academic and research users should cite the repository using [`CITATION.cff`](CITATION.cff).
