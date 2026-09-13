# Hermeneia Agent Guidance

Hermeneia is specification-driven, but it is no longer in the original architecture-freeze implementation phase.

**Current phase:** validation through real use, bounded implementation, and research pressure.

The foundation is:

```text
stable against preference
not stable against evidence
```

Agents may assist with engineering, research, evaluation, documentation, and product validation depending on the assigned task. They may not silently change constitutional ontology, evidence identity, authority, or provenance rules.

---

## Start here

Before substantive work, read the smallest relevant current-state path:

1. `README.md` — current project identity and repository map
2. `docs/README.md` — documentation classes / current-vs-historical routing
3. `docs/What_Hermeneia_Is.md` — project identity
4. `docs/FROZEN_PRODUCT_DIRECTION.md` — current Reader-centered product direction
5. `IMPLEMENTATION_STATUS.md` — dated operational state
6. `docs/01_Authority_Index.md` — canonical authority routing
7. `docs/00_Constitution.md` — highest governing law
8. `docs/02_Constitutional_Invariants.md` — executable constitutional obligations
9. relevant active ADRs/specifications for the surface being changed

For historical context, use `docs/ORIGIN_AND_EVOLUTION.md` and superseded material identified by the Authority Index.

Do not reconstruct current state from old roadmap checkboxes, stale root snapshots, filename order, or issue chronology alone.

---

## Current project identity

Hermeneia began with AI-assisted *Great Gatsby* essay work for a Department of the Treasury hiring exercise, including preservation of human authorship/judgment and culturally distinct interpretive lenses.

That use case remains valid lineage and a useful test case.

It is not the current product boundary.

Current identity:

> **Hermeneia is an operating environment for the disciplined evolution of understanding.**

Current product direction:

> **Hermeneia is a Reader-centered workbench for governed interpretation.**

Do not reduce the system to Gatsby, essay generation, cultural-lens prompting, one model workflow, or one linear pipeline.

---

## Authority hierarchy

When conflicts occur, resolve them in this order:

1. `docs/00_Constitution.md`
2. `docs/01_Authority_Index.md`
3. ratified documents in `docs/amendments/`
4. `docs/02_Constitutional_Invariants.md`
5. active ADRs
6. active implementation documents and compiler specifications
7. code
8. generated artifacts

Never reverse this order.

A detailed old document does not outrank a newer active authority merely because it contains more implementation detail.

---

## Agent mission

Your job is to help Hermeneia learn and improve **without silently corrupting the epistemic foundation**.

Depending on the task, this may mean:

- implement an already-governed design;
- reproduce and diagnose product friction;
- build a bounded projection or derived surface;
- evaluate a hypothesis;
- compare architecture with observed use;
- preserve a negative result;
- identify a genuine architectural insufficiency and escalate it for human/constitutional review.

Do not treat “do not invent architecture” as “do not notice architectural problems.”

The correct rule is:

```text
observe freely
analyze explicitly
propose clearly
change constitutional architecture only through its governing process
```

---

## Constitutional evidence boundary

The ratified forensic evidence chain is:

```text
SourceDocument
    ↓
SourceExtraction
    ↓
Observation
```

SourceDocument is the original artifact.

SourceExtraction preserves parser output exactly as encountered.

Observation is the constitutional semantic unit segmented from SourceExtraction without altering its characters.

Normalization, readable reconstruction, tokens, whitespace maps, search indexes, summaries, and projections are derived conveniences. They must not silently replace evidence.

### Anti-helpfulness rule

Do not silently “fix” malformed source text, spelling, punctuation, spacing, ambiguity, or parser artifacts in canonical evidence.

A correction or readable reconstruction belongs in a descendant claim/projection unless governing authority explicitly changes the evidence model.

Preserve reality first. Improve usability downstream.

---

## Cognitive and authority boundaries

Keep these roles distinguishable:

```text
source evidence
human attention / questions
machine proposal
human interpretation
Perspective
stewarded synthesis
semantic contract
expression constraints
rendered expression
Critic finding
Steward judgment
```

Do not silently promote a machine suggestion into governed understanding.

Do not make a projection canonical because it is polished.

Do not make Critic findings governance decisions.

Do not make model/provider/configuration part of Perspective identity.

Do not infer that multiple Perspectives must converge.

---

## Ontology discipline

Prefer established primitives before creating new domain objects.

Do not silently:

- invent canonical object types;
- rename constitutional objects;
- merge or split constitutional objects;
- add a field/table merely because a UI would be easier;
- promote a useful workflow concept into ontology without evidence and review.

First ask whether the requirement can be represented as:

```text
canonical object
function
derived artifact
projection
configuration
relationship
human judgment
```

If not, document the architectural pressure explicitly.

---

## Product-validation discipline

Hermeneia is currently validated through real use.

Default loop:

```text
use the product
→ observe actual friction
→ preserve the witness
→ classify the problem
→ choose the smallest lawful correction
→ test
→ use again
```

Classify before redesigning:

```text
UX
projection
configuration
provider/runtime
function/derivation
implementation defect
specification gap
architecture
constitutional insufficiency
```

Do not jump directly from inconvenience to ontology.

The Reader remains the center of gravity. Tools should unfold around the work rather than crowding it out.

---

## Scope, Perspective, and execution identity

Keep these distinct:

```text
Scope
Perspective
Connection
Provider
Model
Model Version
Configuration
Investigation
```

Scope answers what existing material an operation may know about.

Perspective answers from where material is examined.

Provider/model/configuration identifies execution conditions.

None silently substitutes for another.

---

## Provenance

Every canonical or governed derived object must retain the lineage required by its active specification.

No floating interpretations.

No floating generated artifacts where provenance is required.

No hidden replacement of the source record.

Where execution is nondeterministic, preserve enough provider/model/configuration/input/output metadata for audit rather than pretending byte-for-byte reproducibility.

---

## Database operations

The `.herm` store is append-only for canonical objects and relations where constitutional/storage authority requires it.

Do not use UPDATE or DELETE to mutate forensic evidence or governed history.

If a correction requires a new lineage, create a new lineage or governed successor rather than rewriting the past.

Consult the active storage specification before changing persistence semantics.

---

## Testing as enforcement

Tests are not merely code-coverage devices. They enforce constitutional and product invariants.

For architecture-sensitive changes, tests should establish the relevant boundary explicitly.

Examples:

- evidence remains immutable;
- derived readability does not mutate SourceExtraction/Observation;
- machine output does not auto-ratify;
- provider/configuration changes do not alter Perspective identity;
- workspace boundaries remain isolated;
- lineage survives export/import/restore;
- a Reader improvement does not destroy source anchoring.

Record infrastructure failures as infrastructure failures rather than semantic/product failures.

---

## Pull request expectations

Every substantive PR should make clear:

1. What observed problem, issue, specification, or research result motivates this change?
2. What active authority/specification governs the changed surface?
3. What invariant or product boundary must remain true?
4. Is the change canonical, derived, projection-only, configuration-only, or UI-only?
5. What tests or real-use witness demonstrate the change?
6. What remains unresolved or deliberately out of scope?

A PR does **not** need an artificial direct lineage to the original white paper if a more precise current authority governs the work.

Use the strongest current governing source, not ceremonial ancestry.

---

## Historical material

Hermeneia intentionally preserves superseded and early-stage material.

Do not infer:

```text
file exists
→ file is current authority
```

Use `docs/01_Authority_Index.md` and `docs/README.md` to route old documents.

Do not rewrite historical Gatsby/Treasury or early architecture artifacts to make the present system look inevitable. Preserve the actual evolution.

---

## Git operating policy

Before substantive engineering work, verify repository state:

```bash
git rev-parse --show-toplevel
git status
git remote -v
git branch
```

Default branch: `main`.

Do not create nested repositories inside canonical project directories.

Do not force-push without explicit human approval.

Commits should describe architectural or product intent, not merely file movement.

Track authoritative/research artifacts; ignore disposable build/runtime artifacts according to `.gitignore` and active repository policy.

---

## When architecture is ambiguous

Do not guess a constitutional answer.

Instead:

1. identify the ambiguity;
2. show the competing interpretations;
3. identify the active authorities involved;
4. preserve relevant evidence from code/use/history;
5. propose the smallest options;
6. require human/constitutional resolution before changing ontology or authority.

A delayed architectural change is preferable to silent semantic corruption.

---

## Final principle

The greatest failure is not a compiler error.

The greatest failure is silently corrupting the relationship among evidence, interpretation, authorship, provenance, and stewardship.

Protect that relationship while allowing the product and research program to keep learning from reality.
