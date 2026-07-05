# Frozen Product Direction — Hermeneia

**Status:** Canonical product direction. Read this first at the start of a session.
**Companion documents:** `CLAUDE.md` (architecture freeze), `docs/workspace-bundle-spec.md` (WBS), `docs/evaluation-harness-design.md` (evaluation).

This document is the single authoritative source for *where the product is going*
and *why*. It exists so no session has to reconstruct the direction from chat
history. Architecture is governed by `CLAUDE.md`; this governs experience.

---

## 1. The product in one line

> Hermeneia is a **reading workbench** for governed interpretation — not a website
> with pages, but a place where the Reader stays at the center and tools unfold
> around the work.

The turning point: we stopped designing *software* and started designing *a way
of studying*. Software copies features; a method is much harder to copy.

## 2. The moat (the methodology, not the screens)

If someone copied every screen tomorrow, they still would not have the method
Hermeneia is converging on:

- **Governed by a thesis** — a governing question is the study's compass, visible
  everywhere.
- **Preserving lineage** — every claim can be walked back to the evidence and the
  human judgment that produced it.
- **Canonical vs derived** — imported/authored records are truth; syntheses,
  lineage, and evaluations are regenerated, never hand-edited.
- **Attention as a first-class artifact** — highlights, questions, field notes,
  and Companion dialogue are evidence of the inquiry, not side chatter.
- **Regenerating projections rather than editing outputs** — you change inputs and
  recompile; you do not polish generated prose in place.
- **The Reader as the center of gravity** — tools accompany reading; they never
  replace it.

## 3. Product philosophy (the frozen principles)

```
Reader        = the main canvas.
Companion     = a persistent assistant, always reachable.
Tools unfold around the Reader.
Nothing steals the work.

Observations, questions, highlights, field notes = the attention timeline.
Corpus Search lives beside the Reader — never a page you leave to.
Workspace is tooling, not navigation.
```

**The one sentence that governs everything:** *the tools should unfold around the
work.* Every new surface should reinforce that instead of adding another page.

## 4. The workflow the product teaches

```
Thesis
  ↓
Read
  ↓
Observe
  ↓
Search       (Reader ↔ Corpus, never leaving the book)
  ↓
Interpret
  ↓
Blueprint
  ↓
Critic
  ↓
Meta-synthesis
```

Onboarding, when it comes, teaches *this workflow* — not the buttons.

## 5. Staged implementation plan

Each PR is one disciplined slice: focused, tested, no scope creep. **None of the
near-term PRs are "AI features" — they are all workflow.** That is intentional:
the foundation (preservation, lineage, evaluation, identity) is strong enough
that the work now is shaping the *experience*.

```
PR 1  ✅ Reader cleanup                         (#91 — merged)
PR 2  ▶  Reader-side Corpus Search              (next)
PR 3     Observation / attention timeline
PR 4     Bottom workflow rail
PR 5     Companion onboarding
PR 6     Thesis → Blueprint workflow
PR 7     Blueprint editor
PR 8     Meta-synthesis
```

### Why this order

- **Corpus Search first.** The natural act while reading Gatsby is *"where else
  does this idea appear?"* — not "go to the Corpus page, search, come back." So
  Corpus Search must live *beside* the Reader: search "green light", results
  appear next to the book, reading never stops.
- **Then the timeline.** Once search lives beside the Reader, the next obvious
  question is *"what have I discovered so far?"* — not *"where are my observations
  stored?"* Replace long scrolling cards with an actual attention timeline.
- **Then onboarding.** Only after Corpus Search and the timeline exist, because
  then onboarding teaches a *workflow* ("set your thesis, read, notice, capture,
  search, interpret, repeat") rather than explaining controls.

## 6. Parallel frozen design — voice fidelity / witness preservation

Captured as **Issue #93** ("Design: voice fidelity and witness preservation
layer"). Not a near-term build, but frozen now because it touches Companion,
Field Notes, Artist, Critic, Lineage, and Meta-synthesis.

**Core statement:** *an output can preserve the thesis and still lose the
witness.* Hermeneia should notice when an expression preserved the evidence but
flattened the human manner of thought — turned a question into a conclusion,
polished away tension, replaced witness with generic professionalism.

**Where it plugs in:** after Artist, *alongside* Critic — not inside Artist. The
Critic gains a third check beyond semantic fidelity and profile adherence: voice
erosion / witness loss.

```
Architect Plan → Artist renders → Critic checks:
   1. Semantic fidelity   (evidence preserved?)
   2. Profile adherence   (declared voice honored?)
   3. Voice erosion       (human witness preserved?)
```

**Safe first build — do not start with custom training.** Start with the existing
`ExpressionProfile` shape (`tone`, `voice`, `artist_prompt`,
`critic_expectations`) and a `profile_adherence` evaluation function. Structured
and auditable, not vibes.

```
P1  Author / Companion ExpressionProfiles
P2  profile_adherence evaluation function
P3  rejected rewrites as hard negatives
P4  selected Companion / user messages commit to record
```

Priority: after Reader-side Corpus Search.

## 7. What this phase is (and is not)

The last several days made Hermeneia **trustworthy** — preservation, lineage,
workspace bundles, evaluation, deterministic behavior, identity. This phase makes
Hermeneia **enjoyable to use**. Different engineering problems; the foundation is
now solid enough to spend the effort on experience.

**Do, this phase:** transform pages into panels; keep the Reader primary; let
tools unfold around the work; one focused slice per PR, tested.

**Do not, this phase:** add AI features, models, or providers; redesign the whole
app at once; change database semantics, the WBS format, or restore behavior;
collapse human highlights and machine observations into one thing.
