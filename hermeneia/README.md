# Hermeneia

> **An operating environment for disciplined inquiry.**

Hermeneia separates the cognitive acts that modern AI systems typically collapse into a single prompt.

Discovery, reconstruction, communication, verification, and governance become distinct responsibilities — each with explicit evidence, provenance, and accountability.

The result is not another language model application. It is an environment where inquiry itself is inspectable, revisable, and auditable.

---

## The Central Claim

Reliable AI-assisted inquiry requires separating cognitive responsibilities that modern language-model systems typically collapse into a single prompt.

When one model is asked to discover evidence, construct interpretations, communicate conclusions, evaluate its own output, and govern the process — simultaneously — reasoning becomes difficult to inspect, failures become difficult to diagnose, and conclusions become difficult to trust.

Hermeneia separates these responsibilities.

---

## Five Cognitive Roles

```
Explorer       discovers candidate interpretations from evidence
Architect      reconstructs semantic obligations from understanding
Artist         realizes understanding in a chosen expressive form
Critic         verifies that expression preserved meaning
Steward        exercises judgment that cannot be reduced to computation
```

These are not software modules. They are cognitive responsibilities.

Each may succeed while another fails. That separation makes failures diagnosable rather than opaque.

---

## The Pipeline

```
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
    ↓
Interpretation         ← human stewardship
    ↓
NarrativeBlueprint     ← human ratification
    ↓
ArchitectPlan          ← deterministic compiler
    ↓
RenderedNarrative      ← LLM (Artist), one role
    ↓
Finding[]              ← deterministic Critic, six evaluation dimensions
    ↓
ValidationReport       ← human governance
```

The LLM occupies exactly one stage. Every other stage is deterministic, human-governed, or both.

---

## What Is Implemented

**Constitutional Infrastructure**

- Immutable evidence lineage from SourceDocument to RenderedNarrative
- Six independent Evaluation Functions (structural, semantic, provenance, observation coverage, accessibility, constitutional)
- End-to-end traceability: any Finding traces back to its originating SourceDocument
- Multi-profile rendering across audiences, registers, and languages
- Semantic obligation extraction (n-gram semantic contracts from Blueprint claims)
- Constitutional compliance tracking across 16 invariants

**Cognitive Architecture**

- Architect: deterministic compiler, no LLM, no inference
- Artist: provider-neutral (Anthropic, OpenAI, Gemini, Grok, Null)
- Critic: unified Evaluation Function runner across all six dimensions
- Blueprint Extractor: reconstruct Intent Hypothesis from existing reports

**Interfaces**

- Web UI with Expression Matrix (Blueprint × Profile grid), Semantic Contract Audit, Trust Card, Lineage Explorer
- CLI: `herm architect`, `herm artist`, `herm critic`, `herm extract`, `herm profile`, `herm trace`
- REST API for all pipeline operations

**557 automated tests** validate constitutional invariants, semantic contracts, provenance, and end-to-end traceability.

---

## Governing Principles

- **Immutable evidence:** source artifacts and observations preserve reality rather than improving it.
- **Explicit semantic contracts:** generated expression is constrained by inspectable obligations, not hidden prompts.
- **Deterministic evaluation:** Evaluation Functions produce bounded Findings from canonical inputs.
- **Human stewardship:** machines may preserve, transform, and evaluate; humans ratify.
- **Conservation of ontology:** no new ontological object if it can be derived from existing ones.
- **Regeneration:** projections and views are regenerable from canonical knowledge.

---

## Quick Start

```bash
# Install
pip install -e .

# Upload a document and extract observations
herm trace create --document path/to/document.pdf

# OR start from existing work (report, essay, analysis)
herm extract path/to/existing-report.md --provider anthropic

# Compile a semantic contract
herm architect OBS-1

# Render across all expression profiles
herm artist OBS-1 --provider anthropic --all-profiles

# Evaluate fidelity
herm critic OBS-1

# Launch the web UI
herm serve
```

---

## Research Program

| Work | Role |
|---|---|
| *Hermeneia* | Reference implementation |
| *Persistent Understanding Architecture (PUA)* | Architectural framework |
| *Semantic Contract Fulfillment (SCF)* | Benchmark methodology |
| *Toward an Ecology of Intelligence* | Philosophical foundation |

White paper: [`docs/papers/hermeneia_white_paper.md`](docs/papers/hermeneia_white_paper.md)

SCF benchmark: [`docs/papers/scf_position_paper.md`](docs/papers/scf_position_paper.md)

---

## Reading Order

1. [`docs/papers/hermeneia_white_paper.md`](docs/papers/hermeneia_white_paper.md) — the argument
2. [`docs/What_Hermeneia_Is.md`](docs/What_Hermeneia_Is.md) — the identity statement
3. [`docs/00_Constitution.md`](docs/00_Constitution.md) — the governing law
4. [`docs/02_Constitutional_Invariants.md`](docs/02_Constitutional_Invariants.md) — the invariants
5. [`docs/Architecture_Patterns.md`](docs/Architecture_Patterns.md) — the patterns
6. [`docs/18_roadmap.md`](docs/18_roadmap.md) — the roadmap

---

## Status

**Architecture Freeze v1.0** — implementation proving the existing architecture is sufficient.

| Exit Criterion | Status |
|---|---|
| Critic fully implemented | ✓ |
| Multi-profile Artist rendering | ✓ |
| Translation profile support | ✓ |
| End-to-end traceability | ✓ |
| Semantic fidelity reporting | ✓ |
| White paper draft | ✓ |
| Live demonstration video | — |
| Pitch deck | — |
| Stable v1.0 release candidate | — |

See [`CLAUDE.md`](CLAUDE.md) for the full freeze directive.
