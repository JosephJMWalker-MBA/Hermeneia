# Hermeneia

> **An operating environment for the disciplined evolution of understanding.**

Hermeneia separates discovery, reconstruction, communication, verification, and governance into explicit cognitive responsibilities with inspectable evidence, provenance, and accountability.

It is not primarily an AI, a document analyzer, or a chatbot. It is a research environment and reference implementation for making inquiry itself inspectable, revisable, auditable, and preservable.

---

## The Central Claim

Reliable AI-assisted inquiry requires preserving the evolution of understanding by separating and governing the cognitive responsibilities through which understanding develops.

When one model is asked to discover, interpret, communicate, evaluate, and govern simultaneously, intermediate reasoning becomes difficult to inspect, failures become difficult to diagnose, and the history of how understanding developed is easily lost.

Hermeneia preserves that history by separating responsibilities, recording lineage, and keeping human authority explicit.

**Models may participate in bounded cognitive roles. Model output is never authoritative merely because a model produced it.** Generated material must remain distinguishable from evidence, human interpretation, ratification, and stewardship.

---

## Cognitive Responsibilities

```text
Explorer       surfaces candidate interpretations from evidence
Architect      reconstructs semantic obligations from understanding
Artist         realizes understanding in a chosen expressive form
Critic         evaluates whether expression preserved meaning
Steward        exercises judgment that cannot be reduced to computation
```

These are cognitive responsibilities, not merely software modules.

**Explorer** may use a configured model to generate speculative candidates. Those candidates remain proposals for human review; they do not silently become ratified understanding.

**Architect** compiles explicit semantic obligations into an inspectable contract.

**Artist** is provider-independent by design and produces expression under those constraints.

**Critic** applies bounded evaluation functions and produces findings rather than final authority.

**Steward** remains human governance: acceptance, amendment, rejection, ratification, and release judgment cannot be delegated simply because automation is available.

A candidate responsibility remains under active investigation: **Witness** — attention before interpretation. The repository contains Witness-oriented interfaces and experiments, but the role remains constitutionally non-canonical until practice justifies promotion.

---

## The Epistemic Pipeline

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
    ↓
Candidate Interpretation    ← Explorer may assist; candidate only
    ↓
Interpretation              ← human accept / amend / reject
    ↓
NarrativeBlueprint          ← human-governed understanding
    ↓
ArchitectPlan               ← deterministic semantic contract
    ↓
RenderedNarrative           ← Artist / configured provider
    ↓
Finding[]                   ← bounded Critic evaluation
    ↓
Validation / Stewardship    ← human governance
```

The important boundary is not “AI in one box.” The boundary is **authority**: generated content, derived projections, deterministic evaluations, and human judgments remain distinguishable throughout the system.

---

## Constitutional Authority

Hermeneia has an explicit authority hierarchy so that old files, generated artifacts, and implementation details cannot accidentally outrank governing decisions.

Current authority resolves in this order:

1. [`docs/00_Constitution.md`](docs/00_Constitution.md)
2. [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md)
3. ratified constitutional amendments
4. [`docs/02_Constitutional_Invariants.md`](docs/02_Constitutional_Invariants.md)
5. active Architecture Decision Records
6. active implementation documents and specifications
7. code
8. generated artifacts

Superseded material is preserved as history rather than deleted. Authority changes without erasing provenance.

---

## What Is Implemented

### Constitutional and provenance infrastructure

- SourceDocument → SourceExtraction → Observation lineage
- occurrence-aware observation identity and provenance records
- constitutional authority, amendments, invariants, and compliance checks
- deterministic hashing and integrity utilities
- explicit human-only governance boundaries
- preservation, release, and ratification artifacts
- workspace identity plus export / restore infrastructure

### Cognitive architecture

- Explorer discovery and speculative interpretation workflows
- deterministic Architect compilation of semantic obligations
- provider-neutral Artist rendering
- multi-profile expression and comparison
- Critic evaluation across structural, semantic, provenance, observation-coverage, accessibility, and constitutional dimensions
- human stewardship and ratification surfaces
- interpretive-divergence and lineage projections

### Reader and workspace experience

- reading-centered workbench with tools unfolding around the source material
- highlights, questions, observations, field notes, and attention history
- corpus search beside the Reader
- Companion, Blueprint, Render, Critic, Voice, Draft, Ratify, and Record workflows
- durable named workspaces with CLI/runtime lifecycle support
- workspace bundle export/import and restoration
- provider connection settings, credential-source boundaries, and model-selection infrastructure

### Publication and research infrastructure

- publication build manifests
- coverage evaluation
- release recommendations
- preservation verification and export
- research experiments and comparative analyses
- white paper, institutional brief, position papers, and architecture documentation

The repository contains an **extensive automated test suite** covering constitutional invariants, provenance, semantic contracts, corpus boundaries, reader behavior, workspace lifecycle, provider behavior, preservation, and end-to-end traceability. The README intentionally does not hard-code a test count because the suite evolves with the system.

---

## Governing Principles

- **Immutable evidence:** source artifacts and observations preserve the record rather than being silently “improved.”
- **Explicit provenance:** important artifacts retain inspectable ancestry and origin.
- **Explicit semantic contracts:** expression is constrained by inspectable obligations rather than hidden intent alone.
- **Bounded evaluation:** Critic functions produce findings from declared inputs; they do not become autonomous judges.
- **Human stewardship:** machines may preserve, transform, propose, and evaluate; humans retain ratification and governance authority.
- **Conservation of ontology:** no new ontological object should be introduced when established architectural primitives are sufficient.
- **Regeneration:** derived views and projections should be reproducible from canonical knowledge rather than treated as irreplaceable truth.
- **Provider independence:** models, providers, interfaces, and algorithms may change without becoming the identity of the system.

---

## Quick Start

Hermeneia requires Python 3.11+.

```bash
# Install the package in editable mode
pip install -e .

# Launch the Reader / web workbench
herm serve

# Inspect the current pipeline state
herm health

# Create an isolated named workspace
herm workspace create "The Second Sale"

# Launch that workspace
herm serve --workspace "The Second Sale"
```

To reconstruct a blueprint from an existing report, essay, or analysis:

```bash
herm extract path/to/existing-report.md --provider anthropic
```

Once a workspace contains the relevant observations and blueprint, the cognitive pipeline can be exercised explicitly:

```bash
# Surface speculative candidate interpretations
herm explorer discover --limit 30 --provider anthropic

# Compile the semantic contract for a blueprint citing an observation
herm architect OBS-23

# Render through the Artist
herm artist OBS-23 --provider anthropic --all-profiles

# Evaluate the rendered narrative
herm critic OBS-23

# Inspect lineage for an observation
herm trace OBS-23
```

Provider names and model availability are runtime concerns rather than constitutional facts. Use the configured Connections/model-selection surfaces or the relevant CLI options for the environment in which Hermeneia is running.

---

## Research Program

| Work | Role |
|---|---|
| *Hermeneia* | Reference implementation and research environment |
| *Persistent Understanding Architecture (PUA)* | Architectural framework |
| *Semantic Contract Fulfillment (SCF)* | Evaluation / benchmark methodology |
| *Toward an Ecology of Intelligence* | Philosophical foundation |

White paper: [`docs/papers/hermeneia_white_paper.md`](docs/papers/hermeneia_white_paper.md)

SCF position paper: [`docs/papers/scf_position_paper.md`](docs/papers/scf_position_paper.md)

Research artifacts in this repository are evidence from an active program of inquiry. They should not be read as proof that Hermeneia's hypotheses generalize universally beyond the corpora, experiments, and implementation actually examined.

---

## Current Status

**Validation Phase — active development.**

The original architecture freeze was lifted after the foundation demonstrated enough stability under implementation and repeated use to continue building without treating every new idea as an architectural rewrite. The foundation is therefore treated as stable **against preference, not against evidence**.

Current work is concentrated on validating the architecture across more real use, improving the Reader/workspace experience, strengthening corpus and provider boundaries, refining semantic quality, and preparing a stable release path. A v1.0 release candidate remains a target rather than a claimed completed release.

For current direction:

- [`docs/FROZEN_PRODUCT_DIRECTION.md`](docs/FROZEN_PRODUCT_DIRECTION.md) — canonical product direction
- [`CLAUDE.md`](CLAUDE.md) — architecture and validation-phase orientation
- [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md) — canonical authority routing
- [`docs/FUTURE_ARCHITECTURE_NOTES.md`](docs/FUTURE_ARCHITECTURE_NOTES.md) — ideas that have not earned architectural authority

---

## Reading Order

1. [`docs/What_Hermeneia_Is.md`](docs/What_Hermeneia_Is.md) — project identity
2. [`docs/papers/hermeneia_white_paper.md`](docs/papers/hermeneia_white_paper.md) — core argument
3. [`docs/00_Constitution.md`](docs/00_Constitution.md) — highest governing law
4. [`docs/01_Authority_Index.md`](docs/01_Authority_Index.md) — which documents currently govern
5. [`docs/02_Constitutional_Invariants.md`](docs/02_Constitutional_Invariants.md) — executable constitutional obligations
6. [`docs/FROZEN_PRODUCT_DIRECTION.md`](docs/FROZEN_PRODUCT_DIRECTION.md) — product direction and workbench philosophy
7. [`docs/Architecture_Patterns.md`](docs/Architecture_Patterns.md) — recurring architectural patterns
8. [`docs/18_roadmap.md`](docs/18_roadmap.md) — roadmap context

---

## License and Citation

Hermeneia is distributed under the MIT License. See [`LICENSE`](LICENSE).

Academic and research users should cite the repository using [`CITATION.cff`](CITATION.cff).
