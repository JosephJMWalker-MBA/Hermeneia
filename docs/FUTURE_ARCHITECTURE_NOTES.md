# Future Architecture Notes

Ideas that emerged during implementation but are deferred until after Architecture Freeze v1.0 is lifted.

Per the freeze directive: if implementation suggests a better architecture, record it here and keep building.

---

## Priority Index

These are the notes most likely to shape the next era of the architecture. Read these first when the freeze lifts.

| Priority | Topic | Why it matters |
|---|---|---|
| **P0** | [Recursive Artist — Fractal Execution Protocol](#recursive-artist--fractal-execution-protocol) | The Artist executes Hermeneia's own methodology internally (Witness → Reconstruction → Draft → Self-Critique → Revision). No schema change. Multi-model comparison becomes investigation quality comparison, not prose preference. Testable immediately. |
| **P0** | [Witness Cognitive Responsibility + Marginalia Interface](#witness-cognitive-responsibility--marginalia-interface) | Attention precedes interpretation. A Witness layer records pre-interpretive human notice (highlights, labels, reflections) as epistemic artifacts, producing an Authorship Deed. Connects reading, inquiry, and institutional trust. |
| **P0** | [Question Constructor](#question-constructor) | Experiments 001–002 suggest question selection is the primary culture-adaptive variable. A Question Constructor between Explorer and Architect would make this explicit. Requires no ontology changes — governing question is a Steward decision. |
| **P0** | [Stage 07 — Synthesis](#stage-07--synthesis) | The pipeline currently produces specialized reports but has no mechanism to compound them into higher-order understanding. Synthesis is the missing final stage. |
| **P0** | [Source Boundary Integrity](#source-boundary-integrity) | Secondary documents silently contaminate interpretation of primary sources. Every claim must answer "which document did this come from?" Without this, provenance is untrustworthy. |
| **P0** | [Corpus-Level Semantic Objects — The Motif Problem](#corpus-level-semantic-objects--the-motif-problem) | The primary unit of understanding may not be the observation. It may be the pattern. This reframes the entire pipeline. |
| **P1** | [Guided Onboarding and Value Clarity](#guided-onboarding-and-value-clarity) | New users are dropped into the system without context. The workflow and value are not immediately obvious. Learn-by-doing required. |
| **P1** | [Workspace Isolation and Document Scope Control](#workspace-isolation-and-document-scope-control) | Users need clean environments per project. Active analysis scope must be visible and controllable. Documents should be detachable, not deleted. |
| **P1** | [Navigation and Workflow Freedom](#navigation-and-workflow-freedom) | Movement through the pipeline is one-directional. Users need back/forward navigation and workflow position indicators. |
| **P1** | [Data Persistence Transparency](#data-persistence-transparency) | The platform's preservation guarantees are not visible. Users don't know their work is being saved or why that matters. |
| **P1** | [Work Identity and Corpus Deduplication](#work-identity-and-corpus-deduplication) | Determines whether Hermeneia is a personal tool or shared understanding network. Without it, network effects fragment rather than accumulate. |
| **P2** | [User Accounts and Personal Libraries](#user-accounts-and-personal-libraries) | Prerequisite for multi-user deployment. Users need persistent identity to build a corpus over time. |
| **P2** | [Multiple Document Management](#multiple-document-management) | Current workflow is single-document. Users need a document library, switching, and active-document indicators. |
| **P2** | [Report as a Node with Version Lineage](#report-as-a-node-with-version-lineage) | Makes Hermeneia a research instrument rather than a one-shot renderer. The recursive research loop. |
| **P3** | [Cross-Document Intelligence](#cross-document-intelligence) | Compare interpretations across documents. Identify recurring themes, conflicting claims, and supporting evidence appearing in multiple works. |
| **P3** | [Concept / Theme Explorer](#concept--theme-explorer) | Pattern-level analysis across the corpus. Literary analysis works through recurring ideas, not single observations. |
| **P4** | [Center of Gravity Shift](#center-of-gravity-shift) | Navigation redesign: report-first instead of pipeline-first. Most users arrive wanting understanding, not database objects. |
| **P5** | [Project as a First-Class Entity](#project-as-a-first-class-entity) | Prerequisite for multi-project and multi-user deployment. Required before any shared corpus feature. |
| **P6** | [Living Understanding — Recursive Report Versioning](#living-understanding--recursive-report-versioning) | The Era III thesis: understanding should accumulate, not restart. |

The new P0–P1 items above were identified during the first real-world user session (2026-06-23). They represent issues a first-time user hit immediately, making them higher priority than the architectural horizons that follow.

---

<!-- Add entries below as implementation reveals architectural pressures.
     Format: date, observation, what it might imply.
     Do not act on these during the freeze. -->

---

## Artist v3 — Knowledge Compiler *(P0 — Validation Phase)*

*Recorded: 2026-06-25*

### Observation

The Artist currently compiles from a Blueprint and plan paragraphs. It does not know what evidence exists in the research program, cannot measure whether a section has sufficient evidential coverage, and does not distinguish between an assertion and a ratified finding.

This means two sections with different evidential maturity look identical to the compiler. Weakness is invisible until a human reads the prose.

### The Compiler Analogy

Traditional writing workflows:

```
Draft → Edit → Edit → Edit → Final
```

Hermeneia should work like:

```
Ratified Knowledge → Semantic Assembly → Coverage Analysis → Compilation → Publication
```

**Constitutional Principle:** *Communication artifacts are compiled from ratified understanding, not incrementally edited into correctness.*

This is not stylistic. It is operational: it predicts that a Critic finding never results in prose edits. It results in either "re-render faithful" or "Blueprint incomplete — ratify the revision first."

### Compiler Architecture

Analogous to a source compiler:

```
Source Code          →  Ratified Knowledge
Parser               →  Semantic Assembly (tag artifacts)
AST                  →  Intermediate Representation (ephemeral tags)
Optimizer            →  Coverage Analysis
Compiler             →  Artist rendering
Executable           →  Publication
```

**Stage 1 — Semantic Assembly**

Before writing, the compiler scans research artifacts and assigns ephemeral compiler tags. These are not canonical ontology — they are intermediate representation that disappears after compilation.

Tag categories:
- `type`: finding | replicated | candidate-pattern | hypothesis | governance
- `topic`: calibration | question-selection | evidence-weighting | methodology | ...
- `rhetorical`: claim | evidence | example | limitation | figure | transition | definition | research-question | counterpoint
- `confidence`: observed | replicated | candidate | hypothesis

**Stage 2 — Coverage Analysis**

Each section declares its required functional components. Before writing any prose, the compiler measures coverage:

```
Section 6 — Calibration Findings

Coverage:
  Replicated Findings     ██████████  100%
  Candidate Patterns      ██████████  100%
  Figures                 ████░░░░░░   40%
  Counter-Evidence        ██░░░░░░░░   20%
  Concrete Examples       ██████░░░░   60%
```

Weakness is structural before it is prose. The compiler can report: "Section 7 lacks a Replicated Finding. Candidate source: `experiment_001_002_003_comparative_analysis.md`, RF-003."

**Stage 3 — Compilation**

Only after coverage is assessed does the Artist render. Input is assembled evidence, not a previous draft. The output is a publication plus a compilation report showing why each paragraph earned its place.

### Constitutional Constraint

Compiler tags (ephemeral) must never become canonical objects. They are not Observations, Interpretations, or Blueprints. They are intermediate representation — a temporary scaffold that the compiler uses and discards.

This preserves the constitutional model: the architecture can become arbitrarily sophisticated at the compilation stage without introducing new governed objects.

### Multi-Model Specialist Pattern

With Artist v3, multiple models stop competing and collaborate:

| Model Role | Cognitive Responsibility |
|---|---|
| Explorer | Generate candidate buckets from corpus |
| Architect | Build semantic assembly (IR from ratified knowledge) |
| Critic | Measure coverage; flag missing evidence; identify overclaims |
| Artist | Compile prose from assembled evidence |
| Steward | Produce release recommendation |

Each model is a specialist executing one stage. The models don't write four different papers. They execute four stages of one compilation.

### Evolution Path

```
Artist v1  — Generate prose from Blueprint                     (done)
Artist v2  — Internal Hermeneia loop before rendering          (implemented 2026-06-25)
Artist v3  — Semantic Assembly → Coverage → Compile            (future)
```

### Research Hypothesis

Evidential coverage measured before prose generation will produce better-calibrated publications than prose generated from a Blueprint alone. The mechanism: sections that feel weak typically lack evidential coverage, not prose quality. Coverage analysis makes this diagnosable before writing.

---

## Recursive Artist — Fractal Execution Protocol *(P0 — Validation Phase)*

*Recorded: 2026-06-25*

### Observation

The three Gatsby experiments demonstrated that understanding matures through repeated cycles of observation, reconstruction, verification, and revision. The Artist currently executes a single pass: one prompt, one response, one narrative. There is no internal review.

This is architecturally inconsistent. Every other cognitive responsibility in the pipeline involves reconstruction and accountability. The Artist alone is exempt.

### The Fractal Property

The methodology is self-similar across scales. The full investigation cycle — Witness → Discovery → Reconstruction → Verification → Governance → Communication — is not specific to the whole investigation. It applies at every level:

- Whole investigation → full pipeline
- Single Blueprint section → Artist rendering
- Single paragraph → Artist internal reasoning
- Potentially: single sentence

This is not metaphor. The white paper itself was produced by exactly this recursive process. Every section went through Intent Hypothesis → Critic Findings → Governance → Revision. The Artist should do the same internally.

### Proposed Protocol: Recursive Artist

Instead of single-pass rendering, the Artist executes a Hermeneia cycle internally:

```
ArchitectPlan
    ↓
Witness         Read the Blueprint section. Record what it is asking.
    ↓
Reconstruction  State the Intent Hypothesis: what is this paragraph
                attempting to establish?
    ↓
Draft           Produce initial prose honoring semantic commitments.
    ↓
Self-Critique   Against each critical semantic commitment: is it
                expressed? Is it weak? What is missing?
    ↓
Revision        Produce revised prose addressing the critique.
    ↓
Final Narrative
```

This is three LLM calls instead of one. Intermediate outputs (Intent Hypothesis, Self-Critique) are stored in `execution_config["recursive_provenance"]` — no schema change required.

### What This Changes for Multi-Model Comparison

Today, multi-model comparison asks: which prose sounds better?

With recursive rendering, comparison asks:
- Which model's Intent Hypothesis most faithfully reconstructed the Blueprint's claim?
- Which model's self-critique identified the weakest semantic commitments?
- Which model's revision addressed the critique?

The Critic then evaluates all models against the same semantic obligations. The comparison becomes investigation quality, not prose preference.

This is a structurally different question — and a much more useful one.

### Research Hypothesis

*[Low Confidence — proposed for experimental validation]*

Applying Hermeneia's recursive methodology within the Artist produces more semantically faithful outputs than single-pass generation, as measured by the Critic's semantic evaluation function.

**Experiment design:**
1. Render Blueprint N with single-pass Artist → run Critic → record semantic findings
2. Render Blueprint N with recursive Artist → run Critic → record semantic findings
3. Compare: semantic commitment coverage, critical obligation scores, self-critique accuracy
4. Repeat across 3+ Blueprints and 3+ providers

If recursive Artist consistently produces stronger Critic scores, the fractal property has moved from hypothesis to empirical finding.

### Implementation Notes

- Protocol: 3 LLM calls (reconstruction, draft, revision)
- Storage: intermediate steps in `execution_config["recursive_provenance"]`
- Interface: `herm artist OBS-N --recursive` (single flag, invisible to UI users)
- Provenance: the Intent Hypothesis and Self-Critique should be readable in the Semantic Contract Audit view
- No new tables. No new canonical objects. No schema migration.

### Why Not Expose the Internal Steps

The recursion should be invisible to casual users. A user who says `herm artist OBS-N` sees a narrative. A researcher who says `herm artist OBS-N --recursive --verbose` sees the full provenance trail. This mirrors how a compiler runs optimizations invisibly but exposes them on request.

---

## Corpus-Level Semantic Objects — The Motif Problem *(P0 — most important post-freeze item)*

*Recorded: 2026-06-22*

### The Observation

A user searched "green light" in the Corpus tab and found 4 occurrences across the novel. The immediate reaction was not "what does OBS-2819 mean?" — it was "there are only 4 references?"

That shift is diagnostic. The moment the user saw the count, the research question became corpus-level, not observation-level. This is how scholars actually work.

No literature professor interprets:

> "Now it was again a green light on a dock."

in isolation. They interpret the **pattern** across all four occurrences: how the symbol shifts, what it gains and loses, how it behaves at the beginning vs. the end. The meaning is **in the repetition**, not in any single sentence.

### The Current Model vs. The Mental Model

Current pipeline:
```
Document → Observations → Interpretations → Blueprint → Report
```

What the human actually does:
```
Document → Observations → Term Clusters / Motifs → Interpret the pattern → Blueprint → Report
```

The current model assumes: **observation is the primary unit of understanding.**

For literary analysis (and arguably for most scholarly inquiry), this is false. The primary unit is often the **pattern** — the distribution of a concept across the corpus.

### The General Case

This is not unique to literature:

| Domain | Corpus-Level Semantic Object |
|---|---|
| Literature | Motif, symbol, recurring image |
| Bible | Theological concept, type/antitype |
| Research papers | Contested term ("alignment," "trust") |
| Legal documents | Operative phrase ("reasonable person," "material breach") |
| Corporate documents | Recurring framing, euphemism patterns |

In every case, meaning emerges from **distribution across the corpus**, not from individual occurrence.

### What This Implies

The current pipeline has a **unit-of-analysis mismatch** between what the machine produces (individual observations) and what the human investigates (patterns across observations).

Correcting this fully would require:
- A new ontology object: `MotifCluster` or `CorpusObject` — a named grouping of observations around a shared concept
- A new pipeline stage between Observation and Interpretation: **Pattern Recognition / Motif Assembly**
- Interpretations that are anchored to a cluster, not a single observation
- Blueprints organized around motifs, not individual interpretations

This is a freeze violation in its full form.

### What Can Be Done Within the Freeze

The infrastructure is 90% present:
- The compiler already extracts terms
- Search already finds all occurrences
- The corpus tab already shows them grouped by query

The missing piece within the freeze is a **Motif Panel** in the Corpus/Lab tab: when a search returns multiple results, show all of them simultaneously in a "pattern view" alongside each other, with their page/context, so the human can see the pattern before generating an interpretation.

The interpretation would still be generated observation-by-observation (to avoid freeze violation), but the **human's context** for making that judgment would be correct: they'd see all 4 before judging any 1.

This is a UI projection over existing data. No new tables. No new ontology. Allowed under the freeze.

### The Deeper Reframe

The green light example exposed something important: **Hermeneia stopped behaving like a pipeline and started behaving like a research environment** the moment the user saw the count. That's the product.

A pipeline produces a report. A research environment answers the question the user didn't know they had. The count of occurrences was the question. The 4 passages together are the evidence. The interpretation is what happens when you see all 4 at once.

If the current architecture can be stretched to support this through UI projection, the freeze holds. If it cannot, this is the first item to address when the freeze lifts.

### The Research Workflow Implication

This also connects to P2 (Report as Node with Version Lineage). The actual research loop is:

```
Pattern noticed
↓
Investigate pattern across corpus
↓
Generate understanding of pattern
↓
Notice new pattern
↓
Investigate deeper
```

Not:
```
Observation → Report → Done
```

This makes Hermeneia a recursive research instrument rather than a one-shot renderer. The green light search was the first moment in testing where the system demonstrated this possibility.

---

## Constitutional Invariants vs. Optimization Objectives *(Architectural Principle — applies now)*

*Recorded: 2026-06-19*

This distinction applies during the freeze and after it. It is not deferred.

**Constitutional invariants** are protected by structure. They cannot be negotiated by any participant, including the Critic, the marketplace, or the community:

- Evidence is immutable
- Provenance is preserved
- No hallucinated observations
- Auditability maintained
- Side-effect-free reads

These are enforced by database triggers, schema constraints, and static source analysis. They do not improve — they hold.

**Optimization objectives** are bounded by the Constitution and improved by practice (Kaizen):

- Semantic fidelity
- Human comprehension
- Accessibility
- Reading level
- Retention
- Cultural resonance
- Cost and latency

These are never "done." They converge asymptotically. The competition is not to be number one. It is to reduce semantic loss by another 0.000001%.

**The canonical statement:**

> **Truth is constitutionally protected. Communication is continuously perfected.**

Protection is absolute. Perfection is asymptotic. Or, in full: *Evidence is constitutionally fixed. Expression is constitutionally bounded and continuously optimized.*

Some things are protected by law. Others are improved by practice. That separation is what makes unlimited innovation safe.

**The analogy:** TCP/IP is fixed enough that millions of applications can innovate on top of it. Hermeneia's Constitution may play the same role for understanding. The immovable foundation is precisely what allows unlimited movement above it. Most people think freezing architecture limits innovation. The freeze demonstrates the opposite.

---

## Community Marketplace for Architect Wrappers *(Deferred — post-v1.0)*

*Recorded: 2026-06-19*

### The Constitutional Principle

> **Expression is a competitive market. Evidence is not.**

Hermeneia owns truth preservation. The community owns expression innovation. These must never be conflated. An open marketplace flourishes without compromising epistemic integrity precisely because the Constitution already defines the boundary.

### The Pipeline Extension

The marketplace introduces one new community-contributed artifact — the **ArchitectWrapper** — between Blueprint and Artist:

```
Evidence
    ↓
Interpretation
    ↓
Blueprint           ← frozen; community may not touch
    ↓
ArchitectWrapper    ← community-contributed communication contract
    ↓
Artist
    ↓
Expression
    ↓
Critic              ← measures fidelity of the above
```

The underlying evidence, observations, interpretations, and blueprint remain unchanged. Only the communication contract changes. This is a natural extension of the frozen architecture, not a new layer — the Architect role already exists; the marketplace allows community specializations of it.

### What the Marketplace Sells

Wrappers are not AI outputs. They are communication strategies. Example wrappers:

```
📚  Elementary Science Teacher
👵  Grandparent Explainer
⚖️  Legal Brief
📖  Sunday School Lesson
🎓  Graduate Seminar
📺  Kurzgesagt-style Narrative
🎙️  Podcast Conversation
📰  Associated Press Style
❤️  Empathetic Counselor
🧑‍💻 Technical Documentation
```

These compete on communication quality, not popularity, because the Critic already measures fidelity.

### The Wrapper as a Signed, Versioned Artifact

```yaml
wrapper_id:               elementary_science_v3
author:                   Jane Smith
constitution_version:     1.0.0
architecture_profile:     v1.0
compatible_artist_models:
  - claude-sonnet-4-6
  - gpt-5.5
critic_score:             99.2
human_witness_score:      97.1
downloads:                15432
license:                  MIT
```

Users choose the mind they want communicating through the model — not just the model itself. This inverts the current AI ecosystem: competition shifts from raw capability to faithful understanding transfer.

### Performance Is Measurable

Because Hermeneia has a Critic layer and is moving toward Axiom 10 Witness Sessions, wrapper quality is empirically assessable:

| Metric | Source |
|---|---|
| Contract fidelity | Critic (automated) |
| Observation coverage | Critic (automated) |
| Hallucination rate | Critic (automated) |
| Reading level | Automated |
| Time to comprehension | Human witness session |
| Task completion rate | Human witness session |
| User trust | Survey |
| Retention after 24h | Study |

Reputation becomes evidence-based rather than popularity-based.

### The Constitutional Safeguard

The marketplace **may only contribute**:
- `ArchitectWrapper` (communication contract)
- `ExpressionProfile` (rendering style)

The marketplace **may never alter**:
- `SourceDocument`
- `SourceExtraction`
- `Observation`
- `Interpretation`
- `NarrativeBlueprint`

This boundary is already enforced by the Constitutional Invariants (CI-007, CI-009) and the immutability triggers. No new machinery is required. The Constitution written during the freeze is already the safeguard.

### The Research Corpus

With thousands of community wrappers answering the same Blueprint, Hermeneia becomes a laboratory for communication science. Researchable questions:

- Which expressions maximize understanding retention?
- Which reduce misconceptions?
- Which work best across age groups or cultures?
- Which metaphors transfer knowledge most effectively across languages?
- What is the measurable relationship between reading level and Critic fidelity?

No other system produces this corpus, because no other system separates evidence from expression with constitutional rigor.

### Fidelity Is Not a Rating — It Is a Kaizen Target

The mistake is treating fidelity as a popularity contest. It is instead precision engineering. Constitutional compliance is a prerequisite (pass/fail gate), not a dimension of competition:

```
Constitutional Compliance
        │
        ├── Pass → enters the optimization space
        └── Fail → excluded entirely
                         │
                         ▼
         Continuous Fidelity Optimization (Kaizen)
```

Only compliant wrappers enter the optimization space. Within it, iteration drives asymptotic convergence:

```
Elementary_v1   99.991241%
Elementary_v2   99.993872%
Elementary_v3   99.995441%
Elementary_v4   99.995618%
```

Those improvements matter. The goal is not "be number one." It is to reduce semantic loss by another 0.000001%. The Critic is not an evaluator in this model — it is a calibrated measurement instrument.

### Multi-Objective Pareto Frontier

Wrappers exist on a Pareto frontier of independent optimization objectives. One wrapper may maximize fidelity. Another may trade 0.00000001% fidelity for a dramatic comprehension gain among eight-year-olds. Neither is wrong. Both are constitutionally valid.

```
                    Comprehension
                           ▲
                           │
               ○
                     ○
         ○
                           ○
────────────────────────────────▶ Fidelity
```

The Constitution defines the acceptable floor. Kaizen drives improvement within the safe region. This is not a leaderboard — it is a Fidelity Observatory.

### Dual Provenance Extends Upward

Every expression carries two independent lineages (Axiom 9), and the marketplace extends this structure upward:

**Evidence lineage** (what the expression is made of):
```
RenderedNarrative → Blueprint → Observation → SourceExtraction → SourceDocument
```

**Expression lineage** (why it looks the way it does):
```
RenderedNarrative → ArchitectWrapper → Author → Wrapper Version → Performance History
```

One explains why the content exists. The other explains why it was communicated this way. These are independent forms of accountability.

### Communication Becomes a Scholarly Object

Imagine citing a narrative:

```
Source:
  Genesis 1:1–3, King James Version

Expression:
  ElementaryScience_v4.2
  Author: Jane Smith
  Constitution: v1.0.0
  Critic Fidelity: 99.8%
  Human Witness Score: 97.4%
  Witness Sessions: 413
```

Communication itself becomes citable, reproducible, and auditable. This opens entirely new research questions. Which expressions maximize understanding across generations? Which reduce misconceptions most efficiently? Which metaphors cross cultural boundaries without loss? No existing system produces this corpus.

### The Evolutionary Consequence

Because every wrapper is measured, authors receive objective feedback. The ecosystem evolves not by trend but by demonstrated effectiveness. The most faithful and comprehensible strategies survive — not because they are popular, but because they demonstrably help humans understand. This is an extraordinarily healthy incentive structure.

When evidence and expression are inseparable, incentives to communicate well eventually become incentives to alter the underlying evidence. History bears this out. Hermeneia's Constitution prevents it structurally — not through virtue, but through architecture.

### Relationship to Current Architecture

Nothing in this vision requires schema changes during the freeze. The `ExpressionProfile` table already exists. The `ArchitectPlan` already separates communication contract from prose rendering. The Critic already measures fidelity. The Axiom 10 Witness Session format already exists. The marketplace is an ecosystem layer above the frozen architecture, not a modification of it.

**The largest audited corpus of faithful human communication strategies ever assembled** will not be Hermeneia's most valuable output as code. It will be its most valuable output as a scientific object — a benchmark not of intelligence, but of understanding transfer.

---

## UI Vocabulary Toggle as ExpressionProfile *(Deferred — Architecture Freeze v2.0)*

*Recorded: 2026-06-19*

The current ⚙ Expert toggle is implemented as a CSS class swap that changes labels and tooltips. It correctly changes only expression, never data. The child and the scholar see the same underlying graph.

The architectural implication: this toggle is not a "mode" — it is an ExpressionProfile applied to the interface layer itself. It is architecturally identical to the profiles that govern how prose is rendered. The same vocabulary transformation that turns a Literary profile into a Children's profile could govern the interface vocabulary.

Future profiles for the UI layer:

```
👶 Child         Simplest possible labels. Emoji-first navigation.
👴 Senior        Larger touch targets. Slower animations. No jargon.
🎓 Academic      Full technical vocabulary. Compact density.
⚙  Technical     CLI equivalents visible everywhere.
🌍 Plain Language Maximum accessibility. WCAG AAA target.
```

All render the identical underlying graph. No profile reveals "extra truth." No profile hides truth.

**Why this matters:** Once the interface is treated as a rendering surface governed by ExpressionProfiles, the Axiom 10 Witness Session (see `docs/07_First_Principles.md`) becomes a reproducible test: run the same session under the Child profile and the Academic profile. If the outputs differ, it should be only in expression. If the test completion rate differs, it should be diagnosable. The interface becomes empirically accountable in the same way the Critic makes the Artist empirically accountable.

**Implementation note:** The CSS `.ho` / `.xo` class system in `index.html` is the seed of this. The architecture already exists. What is needed is a profile registry, a UI rendering pipeline, and a profile switcher. None of these require schema changes. They are implementation, not architecture.

---

## Accessible Interface Design *(Deferred — Architecture Freeze v1.0)*

*Recorded: 2026-06-19*

### The Principle (Axiom 10)

The interface is the final interpreter. The implementation notes here translate Axiom 10 (docs/07_First_Principles.md) into concrete UI decisions without altering the underlying architecture.

### Navigation: Recognition Over Recall

Replace nested menus with a persistent four-action home:

```
📖 Read      Browse the corpus
🔍 Explore   Search observations and interpretations
✍️ Create    Compile a new document
🧬 Trace     Follow the lineage of any expression
```

Every action visible. Every label self-explanatory. No mental model required to find the entry point.

### Expression Profile Selection: One Decision Per Screen

Never expose ExpressionProfile slugs, language codes, or reading-level fields to a casual user. Show:

```
"How would you like this explained?"

👶  For a child          [childrens-en]
🎓  Academically         [literary-en]
📜  Historically         [historical-en]
❤️  Pastorally           [pastoral-en]
🏢  For executives       [executive-en]
🌍  In Swahili           [literary-sw]
```

Large touch targets. Single selection. The profile slug is resolved behind the interface. The user never sees it.

### Progressive Disclosure: Three Depths

Every view should support three depths without mode-switching:

**Surface (default — child, elder, first-time user)**
- What is this?
- Where did it come from?
- Can I trust it?

**Informed (researcher, student, curious adult)**
- Which interpretation produced this?
- What observations does this rest on?
- How was the expression profile selected?

**Expert (steward, auditor, developer)**
- Full lineage: RenderedNarrative → ArchitectPlan → Blueprint → Interpretation → Observation → SourceExtraction → SourceDocument
- Constitutional regime: constitution_version, invariant_profile
- Critic report: term coverage, fidelity score, unsupported claims

Disclosure control: a single `▼ Show more` expands one depth at a time. No separate pages, no mode toggle.

### Lineage Explorer: Two Vocabularies, One Architecture

The `/lineage?narrative=<id>` page should render the same provenance chain in both registers, switchable by the user:

**Human register (default)**
```
📖 This story
    ⬇️ came from a plan made by
📝 An Architect Plan
    ⬇️ built from
💡 Ideas (Interpretations)
    ⬇️ grounded in
👀 What was observed
    ⬇️ found in
📄 The original page
```

**Expert register (expand)**
```
RenderedNarrative  [id: a3f2...]
    ↓ architect_plan_id
ArchitectPlan  [id: 7b91...]
    ↓ blueprint_id
NarrativeBlueprint  [id: 2e44...]
    ↓ via interpretation_links
Interpretation  [id: f8c1...]
    ↓ observation_id
Observation  OBS-312  [id: 9d02...]
    ↓ source_extraction_id
SourceExtraction  [page 14, block 3]
    ↓ document_id
SourceDocument  gatsby.pdf  [sha256: 4a7f...]
```

Same nodes. Same edges. Different labels. Toggle at the top of the page.

### Typography and Touch

- Minimum 18px body text (WCAG AA Large)
- Minimum 44×44px touch targets
- No action hidden in hover states
- No critical information in color alone
- All interactive elements keyboard-navigable

### Test of Axiom 10

Before any UI feature is marked complete, it must pass two human tests (not automated):

1. An eight-year-old can complete the task without explanation.
2. An eighty-year-old can complete the task without explanation.

If either fails, the interface has not fulfilled its constitutional purpose regardless of what the underlying implementation can do.

### Why Deferred

This section requires no new ontology objects, database tables, or pipeline stages. It is pure implementation work on the web layer. Deferred until after Architecture Freeze v1.0 is lifted.

**Implement when:** Sprint 1 canonical demo is complete and the UI is being prepared for external audiences.

---

## Constitutional Ledger & Machine-Verifiable Governance *(Deferred — Architecture Freeze v1.0)*

*Recorded: 2026-06-19*

### The Insight

`CONSTITUTIONAL_PROFILE` is a module-level constant compiled into the package at deploy time. Every `RenderedNarrative` now carries two independent provenance chains: an evidence chain (Observation → Blueprint → ArchitectPlan → Narrative) and a constitutional chain (Constitution version → Invariant Set → Architecture Profile). This is Axiom 9 (Dual Provenance) in practice.

The current implementation satisfies the principle. Two deferred extensions would complete it architecturally.

### Constitutional Ledger

`CONSTITUTIONAL_COMPLIANCE.md` is currently a single file that is updated in place. This violates the append-only principle the rest of the system observes.

Proposed structure:

```
constitutional_audits/
    2026-06-19-v1.0.0.md   ← frozen at ratification; never overwritten
    2026-08-14-v1.1.0.md
    2027-02-03-v2.0.0.md
```

`CONSTITUTIONAL_COMPLIANCE.md` becomes a symlink or pointer to the latest audit. The audit history becomes permanent. Hermeneia's constitutional history obeys its own constitutional principles.

Each audit file carries its own header:

```markdown
---
constitution_version: "1.0.0"
authority_index_version: "1.0.0"
generated: "2026-06-19T23:17Z"
commit: "abc123"
pytest_version: "9.1.0"
---
```

Now the compliance report itself is a provenance-bearing artifact. It participates in Hermeneia's ontology rather than sitting outside it.

### Machine-Verifiable Compliance

The current `CONSTITUTIONAL_COMPLIANCE.md` is maintained by discipline. A future CI gate should make it machine-verifiable:

1. Parse the compliance markdown.
2. Extract every row where Status = ✅.
3. For each such row, derive the `Verified By` test name.
4. Assert that test exists and passes.
5. Fail CI if a ✅ claim has no passing test.

A ✅ with no corresponding test is a constitutional violation. The document cannot lie while the pipeline is green.

Full schema for each compliance row:

```text
Invariant      — canonical ID (CI-011, INV-08, etc.)
Status         — ✅ | ⚠️ | ❌
Proof Type     — Mechanical | Static | Property | Dynamic | Audit | Documentation
Confidence     — Mechanical | High | Partial | Low | None
Automation     — Full | Partial | None
Verified By    — test function name(s) or schema constraint
Evidence       — specific assertion, not a general claim
Ratified       — ISO date or —
```

When the schema is machine-readable, the CI parser becomes deterministic. Every Automation=Full entry is actually executed in CI. Every Mechanical proof points to a schema trigger or static analysis. Every ✅ has a passing test.

The compliance matrix stops being documentation and becomes executable governance.

### Compliance Report as Auditable Object

Eventually, a compliance report should be a first-class artifact in the database:

```
constitutional_reports
    id              TEXT PRIMARY KEY   -- sha256 of (commit, run_timestamp, constitution_version)
    constitution_version   TEXT
    generated_at    TEXT
    commit          TEXT
    pytest_version  TEXT
    results         TEXT               -- JSON: per-invariant status + evidence
```

Now the compliance history is queryable. A future `herm constitutional-audit` command could show:

```
CI-011   ✅ 2026-06-19  ✅ 2026-08-14  ✅ 2027-02-03
INV-08   ✅ 2026-06-19  ✅ 2026-08-14  ❌ 2027-01-11  ← regression event
```

Regressions become part of the constitutional record, not silent failures.

### Why Deferred

The current implementation (module-level constant + compliance markdown + pytest) satisfies Axiom 9. The ledger and machine-verifiable gate are governance improvements, not architectural changes. They require no new ontology objects or pipeline stages.

**Implement when:** the project reaches a release candidate and the compliance document needs to be formally versioned alongside the binary.

---

## Provider Comparison Matrix & SCF Benchmark *(Deferred — Architecture Freeze v1.0)*

*Recorded: 2026-06-19*

### The Insight

The Expression Matrix currently shows `Blueprint × Profile`. Because providers are interchangeable, the matrix has a second dimension: `Profile × Provider`. The same Architect Contract can be fulfilled by any provider. The Critic evaluates the output independently of the source.

This creates something no existing benchmark offers: **Semantic Contract Fulfillment (SCF)**.

### Provider Comparison Matrix

```
Profile          OpenAI    Anthropic    Gemini    Grok
────────────────────────────────────────────────────
literary-en       98%        99%         96%      95%
literary-sw       94%        97%          —         —
historical-en     91%        95%         93%      89%
```

Providers are not ranked by vibes, fluency, or perplexity. They are ranked by semantic fidelity to the same contract — the Architect Plan — which neither they nor the Critic wrote. The contract is neutral. The evaluation is deterministic.

### Semantic Contract Fulfillment (SCF)

A provider-neutral benchmark derived entirely from existing pipeline outputs:

```
Required concepts preserved      18 / 20
Forbidden claims introduced           0
Structural compliance             100%
Placeholder detection                No
Overall fidelity                  97.3%
```

Every model is measured against the same Architect Plan for the same Blueprint. No contamination, no prompt-engineering advantage: the Artist prompt is generated deterministically and identically for every provider.

This is publishable. No benchmark currently measures LLM semantic fidelity to a pre-specified epistemic contract.

### Multi-Provider Semantic Contract Audit

The Semantic Contract Audit page could eventually show tabs across providers for the same Blueprint + Profile:

```
[OpenAI]  [Anthropic]  [Gemini]  [Grok]
```

The Contract column (Architect) never changes.
The Fulfillment column (Artist) changes per tab.
The Compliance column (Critic) changes per tab.

Meaning becomes the invariant. Expression becomes the variable.

### `herm provider` CLI *(deferred)*

```bash
herm provider add anthropic    # stores name, model, env var reference — never the secret
herm provider add openai
herm provider add gemini
herm provider add grok
herm provider list
herm provider remove openai
```

Stored as a local config file (`.hermeneia/providers.toml` or similar). Each entry records:
- provider name
- default model
- environment variable name for the API key

Never the secret itself. The key stays in the environment; Hermeneia only knows where to look.

Then:
```bash
herm artist OBS-312 --profile literary-sw --provider gemini
```

becomes trivial regardless of which providers are registered.

### Constitutional Boundary

Per Invariant XIV, provider-specific logic must never touch:
- Observation
- Interpretation
- Perspective
- Blueprint
- Architect
- Critic

The only replaceable component is the Artist. The corpus and all epistemic artifacts survive any provider.

---

## Perspective Providers *(Deferred — Architecture Freeze v1.0)*

*Recorded: 2026-06-19*

### The Question PUA Never Asks

PUA should never ask: "Who owns the truth?"

It should ask: "What perspectives exist, what observations support them, and how were they stewarded?"

This reframes every external knowledge system — Wikipedia, xAI's collaborative knowledge graph, PubMed, arXiv, local archives, oral histories — from competitors into participants. PUA doesn't replace them. It treats them as Perspective Providers.

### Architecture

```
                    PUA
                     │
     ┌───────────────┼───────────────┐
     │               │               │
Wikipedia       xAI Living KB    PubMed
     │               │               │
     └───────────────┼───────────────┘
                     │
             Observation Import
                     │
             Provenance Preserved
                     │
             Interpretation Layer
                     │
          Human + AI Stewardship
```

Wikipedia contributes one perspective. xAI contributes another. PubMed another. A local church archive another. A Maasai oral history another. PUA does not flatten them into consensus. It preserves them as parallel, co-existing perspectives with independent provenance.

### Example: The Exodus

PUA could contain:

- **Perspective: Biblical Theology** — interpretations grounded in Scripture
- **Perspective: Archaeology** — interpretations grounded in excavations  
- **Perspective: Egyptian History** — interpretations grounded in Egyptian records
- **Perspective: xAI Collaborative Knowledge** — interpretations emerging from community synthesis
- **Perspective: Wikipedia Consensus** — interpretations reflecting editorial consensus

The Critic never asks which is true. It asks:
- Are they internally consistent?
- Are observations cited?
- What evidence supports them?
- Where do they contradict?
- What lineage produced them?

### Imported Artifacts Become First-Class Objects

Importing an xAI article does not store it as a blob. PUA compiles it:

```
Observation 1
Observation 2
Observation 3
     ↓
Interpretations
     ↓
Perspective: "xAI Collaborative"
     ↓
Blueprint
     ↓
Expression Profiles
     ↓
Critic
     ↓
Stewardship
```

The imported knowledge can then be translated, challenged, expanded, merged with local observations, rendered for children, rendered for legal audiences, and validated independently — without losing its origin. The provenance chain remains intact across the import boundary.

### This Solves AI's Provenance Problem

Current systems:

```
Internet → LLM → Answer
```

Provenance is opaque. PUA instead:

```
Internet
     ↓
Wikipedia Perspective
     ↓
xAI Perspective
     ↓
PubMed Perspective
     ↓
Local Corpus Perspective
     ↓
Architect → Artist → Critic
     ↓
Validated Response
```

The user can inspect where each idea came from. Every claim has ancestry.

### The Ecology

```
Ecology
  ├── Human scholars
  ├── Wikipedia
  ├── xAI collaborative knowledge
  ├── Local experts
  ├── Universities
  ├── Government archives
  └── Hermeneia stewards
```

No participant is privileged absolutely. Every participant contributes observations and interpretations with provenance. xAI's contribution becomes ecological — not "the answer" but a perspective within a living system. This aligns directly with Axioms VII and VIII: healthy ecologies create better preservers, and stewardship is relational.

### Proposed Abstraction: `PerspectiveProvider`

```python
class PerspectiveProvider:
    name: str
    provenance_policy: ProvenancePolicy
    
    def import_source(self) -> list[Observation]: ...
    def declare_perspective(self) -> Perspective: ...
    def compile(self) -> NarrativeBlueprint: ...
```

Adapters:
- `WikipediaProvider`
- `xAIProvider`
- `arXivProvider`
- `PubMedProvider`
- `PersonalJournalProvider`
- `ArchiveProvider`

All plug into the same ecology using existing ontology objects. No new pipeline stages required. The current architecture already supports this through its existing Observation, Interpretation, Perspective, and Blueprint objects.

### Why This Is Deferred

The current ontology can already model this using existing concepts. A Wikipedia article imported as observations with `source: "wikipedia"` and a declared Perspective named "Wikipedia Consensus" is fully expressible today. The `PerspectiveProvider` abstraction formalizes the import interface — it does not change the ontology.

**Implement when:** multi-source corpus import becomes a user-facing need. Until then, manual observation import via the existing compiler is sufficient.

---

## Steward Reputation Model *(Deferred — Architecture Freeze v1.0)*

*Recorded: 2026-06-19*

### Background

Session 011 established Invariant XIII: steward credentials are provenance, not evidence. They may be surfaced contextually but may never alter semantic standing. That settles the constitutional question. The architectural question — how to model stewardship rigorously — is deferred here.

### Core Distinction

Two kinds of steward attributes exist and must never be conflated:

**Declared attributes** — credentials asserted by the steward or an institution. Real information, but unverified by the system.

**Derived attributes** — properties emergent from the steward's participation in the corpus. Computable. Unfakeable.

The derived attributes are the more important signal. No résumé required.

### Proposed: `DerivedStewardship`

```python
class DerivedStewardship:
    observations_contributed: int
    interpretations_created: int
    interpretations_self_revised: int      # steward updated their own view in response to evidence
    interpretations_corroborated: int      # subsequently supported by independent observations
    domains_observed: tuple[Domain]        # inferred from linked observations, not declared
    contradictions_resolved: int
    stewardship_cycles_completed: int
```

These are properties of the ecology, not the steward's profile. The ecology observes participation and computes stewardship from lineage. This connects directly to Axiom VII: a healthy ecology creates better preservers, and recognizes them not by what they claim but by what the corpus can derive.

### Open Questions

- Should `Stewardship` become a first-class ontology object alongside `Observation` and `Interpretation`?
- Can experiential scope (the domains where a steward has demonstrated corpus participation) be inferred automatically, or does it require human designation?
- Should `interpretations_self_revised` become a positive trust signal? A steward who corrects themselves is more trustworthy than one who never faces challenge.
- Should corroboration be longitudinal rather than instantaneous — weighted by how long the corroboration has held against subsequent evidence?
- How should institutional credentials be stored? As a `Credential` object with issuing institution, date, domain scope, and expiry?
- How should experiential credentials emerge from corpus participation? Threshold-based? Continuous?
- Can stewardship metrics be gamed recursively? If corroboration count becomes visible, does it create incentive to corroborate strategically?
- Should reputation ever influence UI defaults (sort order, display prominence) while remaining constitutionally prohibited from influencing semantic standing? Is that distinction maintainable in practice?
- `overturned_interpretations` is ambiguous: was the steward wrong, or ahead of consensus? Store the overturning event's own provenance rather than collapsing it to a scalar.

### Three Kinds of Stewardship

These must never be conflated:

| Kind | Source | Verified by system? |
|---|---|---|
| **Declared** | Degrees, licenses, titles, certifications | No — stored as provenance |
| **Derived** | Computed from corpus participation | Yes — computable from lineage |
| **Conferred** | Invited reviewer, ratification signer, editorial board, constitutional steward | Yes — governance record |

Conferred stewardship is procedural, not epistemic. A conferred role grants the authority to initiate a stewardship cycle; it does not grant semantic standing to the interpretations that steward produces.

### Four Kinds of Authority

| Type | Source | Stable? |
|---|---|---|
| **Declared** | Degrees, licenses, titles | External |
| **Conferred** | Governance roles | Procedural |
| **Derived** | Computed from corpus participation | Ecological |
| **Validated** | Longitudinal success across stewardship cycles | Historical |

Validated authority is the most important and the hardest to game. It can only emerge through time. Someone can manufacture 10,000 observations overnight. They cannot manufacture decades of survival, repeated reuse, successful translation across domains, adoption into future Architect Plans, correction under criticism, and continued inheritance by subsequent stewards.

The ecology naturally discounts shallow activity and rewards durable contribution — not through any explicit penalty mechanism, but because the relational structure of the corpus exposes isolation. A manufactured observation has no citations, no corroboration, no downstream interpretations, no blueprint inheritance. The ecology sees the gap.

### Named Concept: Stewardship Legacy

Not reputation. Not influence. Not prestige.

> **Stewardship Legacy**: the accumulated record of contributions that continue to demonstrate semantic validity, preserve provenance, survive criticism, and remain useful across successive stewardship cycles.

This is what Semmelweis eventually accumulated. At the time of his institutional rejection, his Derived Stewardship existed in the corpus. His Validated authority emerged retrospectively, when the lineage was re-examined. PUA would eventually converge toward recognizing his stewardship because the ecology preserves lineage instead of freezing consensus. Authority becomes retrospective evidence, not merely contemporaneous status.

### The Gaming Problem — Resolved

The mistake is thinking the score is the thing. The ecology should never optimize for the score. It should optimize for recoverable lineage.

Quantity alone is insufficient because the ecology evaluates relationships, not counts. The Critic can always ask:
- Are observations independent of one another?
- Are interpretations corroborated by subsequent evidence?
- Do later interpretations cite them?
- Did they survive stewardship cycles?
- Were they self-corrected when challenged?
- Did they produce durable Architect Plans?
- Are they still being inherited?

No fabrication strategy survives all of those questions simultaneously.

### Named Concept: Derived Stewardship

The principle worth preserving regardless of implementation:

> **Stewardship is inferred through participation, but authority emerges through validated stewardship across time.**

A steward's most important attributes are not declared. They are emergent from what the ecology can observe about their participation. This is consistent with the rest of the architecture: just as the Architect derives structure from observations rather than asserting it, the system should derive stewardship from participation rather than accepting credential claims at face value.

Declared credentials are provenance. Derived stewardship is signal. Validated authority is history.

### Connection to Invariant XIII

The UI may surface all four kinds of stewardship contextually. It may never use any of them as a ranking or suppression input. The human steward reads the provenance and exercises judgment. The system preserves the ecology. That is the correct division of labor.

---

## Durability and Canonicality Are Not the Same Thing *(Constitutional Principle — 2026-06-20)*

*Recorded during Sprint E9 constitutional design review.*

The original design review for `critic_reports` contained a quiet conflation:

```
Critic exists
    ↓
Critic produces report
    ↓
Report must be canonical
```

This conflated two separate properties: **durability** (the artifact persists and is immutable) and **canonical status** (the artifact has acquired constitutional effect and is integrated into the lineage chain).

The correct principle:

```
Critic exists
    ↓
Critic produces durable artifact
    ↓
Artifact becomes canonical only when it acquires constitutional effect
```

**Constitutional effect** is defined as: the artifact is explicitly referenced in a recorded steward decision whose downstream consequence persists in the canonical corpus. Before that event, the artifact is advisory. After it, the artifact is part of the historical explanation for why the canonical corpus looks the way it does.

**The Operational Artifact Pattern:**

An operational artifact is a persisted, immutable, non-canonical database object. It satisfies:
- Immutable after creation (triggers on UPDATE and DELETE)
- Never deleted
- Indexed and queryable
- Referenced softly (in text fields) by canonical objects, not by hard FK

An operational artifact is promoted to canonical by the steward when the promotion criterion is satisfied, not by the implementation author when the table is created.

**The general rule:** Table existence does not imply canonical status. The question to ask when creating any new table is not "is this canonical?" but "under what condition does this become canonical?" That condition should be recorded before implementation, not discovered afterward.

This distinction applies recursively to any future artifact the Critic or other pipeline phases produce. The DDL comment pattern:

```python
# Constitutional Status: OPERATIONAL — not yet canonical.
# Promotion criterion defined in CONSTITUTIONAL_COMPLIANCE.md.
# Table is immutable and permanent. Not supersession-eligible.
# No canonical FK dependencies until promotion.
```

---

## The Convergence-Governance Pattern *(Empirical Finding — 2026-06-20)*

*Recorded at the conclusion of the Experiments 001–008 research program.*

Across eight experiments, the same pattern appeared repeatedly at different layers:

```
Generation          → diverges  (providers produce different interpretations)
Evidence Identification → converges  (providers find the same relevant phrases)
Judgment (verdict)  → diverges  (providers apply different evaluation policies)
Governance          → reconciles  (steward determines which verdict applies)
```

This pattern is not a coincidence of experimental design. It appears to describe something structural about the relationship between automated AI processes and human governance.

**Why this matters for the architecture:**

The current Hermeneia architecture places humans at the governance layer — steward decisions, ratification records, witness sessions. The research program produced an empirical justification for exactly that placement: the human is placed where variance remains *after* the available convergence has already occurred.

Evidence identification converges without human input — it can be automated. Verdict classification diverges even after providers have agreed on the evidence — it requires a policy decision that a human must make or configure. The architecture does not place the human everywhere; it places the human precisely at the points of unresolved variance.

**The recursive consistency:**

The same pattern that governs interpretation → evidence → evaluation governs storage → governance → canonicalization:

```
Operational artifact  (exists, is durable)
    ↓
Governance event  (steward explicitly references it in a constitutional act)
    ↓
Canonical artifact  (has constitutional effect, enters the permanent record)
```

The architecture is applying the same separation at the storage layer that the research program revealed at the evaluation layer. The principle is the same in both contexts: durable artifacts become constitutional artifacts through governance events, not through creation.

**The stewardship model as empirical necessity:**

Before Experiments 001–008, the stewardship model was justified constitutionally (by ADR and design decision). After them, it is also justified empirically. The experiments did not design a system that happens to need stewards. They discovered that the natural structure of AI interpretation — convergence at the evidence layer, divergence at the judgment layer — produces exactly the boundary at which human governance is necessary rather than merely desirable.

That is a stronger foundation for the governance model than either design authority or philosophical principle alone.

---

## Generation Diverges, Evaluation Converges *(Empirical Finding — 2026-06-20)*

*Recorded during Era III research program (Experiments 001–005). Constitutional implication for the Critic phase.*

### The Finding

Across five research experiments using the E8 staging gate, two distinct cognitive operations were tested:

1. **Interpretation generation** — ask providers to interpret an observation
2. **Evidence evaluation** — ask providers to evaluate whether an existing interpretation is grounded in an observation

These operations produce systematically different levels of agreement.

**Generation:** High divergence across providers. Different interpretive layers, different thematic priorities, different levels of conservatism. The same observation produces a narrative reading (Grok), a structural reading (Claude), a conservative restatement (Meta), a system reading (Gemini), a descriptive reading (GPT). These are not random differences — they are stable priors that persist across observation types.

**Evaluation:** High convergence across providers. In Experiment 005, five providers independently evaluated the same interpretation against the same observation. All five independently identified the same principal gap — the *tertium comparationis* of the moth simile is unstated — without being told what to look for. Four of five reached the verdict "Partially Supported." The fifth reached "Not Supported" via a different evaluation policy applied to the same evidence.

The disagreement that remained was not about the facts but about evaluation policy: if the load-bearing claims fail, does the interpretation fail (Meta) or is the verdict partial because the structural core holds (GPT, Claude, Gemini, Grok)? Both positions are coherent and articulated from the evidence.

### The Constitutional Implication

If this pattern continues across future experiments, it provides empirical grounding for the following distinction:

> **The Interpreter surfaces plurality. The Critic evaluates grounding. They are not the same operation and appear to produce systematically different levels of convergence.**

Merging the Critic into the Interpreter — or treating them as the same phase — would collapse a constitutionally significant distinction. The pipeline's frozen separation of Interpreter and Critic phases is architecturally correct for a reason that was not articulable before this research. The empirical evidence now provides that reason.

### The Evaluation Policy Problem

Experiment 005 revealed that evaluation convergence is bounded by evaluation policy. Providers agreed on the evidence and diverged on the threshold. Experiment 006 refined this precisely: **evidence identification converges more strongly than verdict classification**.

In six experiments, when providers were asked to classify a specific claim against a specific observation, all five anchored on the same textual evidence. The divergence emerged only when evidence was translated into a verdict.

This produces a two-layer model for the Critic:

**Layer 1 — Evidence Identification:** What evidence in the observation is relevant to this claim? Cross-provider convergence is high. May be automatable.

**Layer 2 — Verdict Classification:** Given the identified evidence, what is the verdict? Policy-dependent. Three distinct policies emerged in Experiment 006:

| Policy | Rule |
|---|---|
| Conservative | Claim is Unsupported if the observation lacks vocabulary or structure to license it. No active contradiction required. |
| Decomposition | Claims are composite; components receive separate classifications; the verdict reflects the composite. |
| Semantic | If the claim's key term has a literal meaning that the observation explicitly violates, the verdict is Contradicted. |

The Critic implementation must adopt an explicit policy or expose it as a steward-configurable parameter. These are steward decisions, not technical questions. They should be recorded as constitutional decisions before the Critic is built, not discovered during implementation.

**The constitutional consequence:** The disagreement does not live in what the text says. It lives in the threshold where evidence is translated into judgment. That is precisely where Hermeneia already reserves stewardship and human governance. A Critic that collapses evidence identification and verdict classification into one operation will produce verdicts that are not auditable — the steward cannot inspect which layer produced the disagreement.

### The Three-Stage Refinement (from Experiment 007)

The two-layer model (evidence identification / verdict classification) required a middle stage after Experiments 006 and 007:

```
Observation + Claim
    ↓
Stage 1: Evidence Identification
    What text is relevant to this claim?
    Cross-provider convergence: HIGH (5/5 across two independent observations)
    ↓
Stage 2: Evidence-Claim Mapping
    Which evidence supports the claim? Which opposes it?
    How does each piece of evidence bear on each component of the claim?
    Cross-provider convergence: MODERATE
    (providers agree on direction but differ in decomposition depth)
    ↓
Stage 3: Verdict Classification
    Given the evidence map, what is the verdict?
    Cross-provider convergence: LOW — policy-dependent
    Three stable policies identified:
      Conservative: absence of support = Unsupported (no active contradiction required)
      Decomposition: split claim into components, evaluate separately, reassemble verdict
      Semantic: if claim's load-bearing term has literal meaning the observation violates, verdict = Contradicted
```

Stage 2 is where Claude's behavior consistently differs from the others. Claude decomposes the claim into components before mapping evidence to each component. The other providers evaluate the claim as a unit. The resulting verdicts are similar, but the reasoning structure is different. This matters for Critic implementation: Stage 2 outputs are not just "supporting evidence" and "opposing evidence" — they are component-level mappings that allow Stage 3 to produce more precise verdicts.

The verdict pattern across Experiments 006 and 007 is identical provider-to-provider. This is not random disagreement. It is consistent application of stable evaluation policies. The policies are themselves auditable — the Critic should expose which policy produced which verdict.

### Claim Extraction Is Interpretive (from Experiment 008)

Experiment 008 revealed that claim extraction — reading an interpretation and identifying its constituent claims — is itself an interpretive act, not a neutral decomposition step.

Given the same one-sentence interpretation, five providers extracted 3–7 distinct claims. The claim sets were internally coherent but not identical. More significantly: Claude's claim extraction introduced a claim ("the show was exaggerated") that was present in neither the observation nor the interpretation provided. It emerged during the act of extracting claims.

This means the Critic pipeline has an additional step that requires governance:

```
Observation
    ↓
Interpreter → Interpretation
    ↓
Claim Extractor → Claims
    (this step is itself interpretive — new claims may be introduced)
    ↓
STEWARD CLAIM REVIEW (new governance act)
    Are these the right claims?
    Has any claim been introduced that isn't in the interpretation?
    Has any claim been omitted?
    ↓
Evidence Finder → Evidence Set  (high convergence)
    ↓
Critic Policy → Verdict  (policy-dependent)
```

**The implication:** The Critic itself needs a Critic — not for verdicts, but for claim boundaries. Before the Critic evaluates claims, a steward may need to normalize the claim set. Otherwise, the Critic's verdicts are only as reliable as the claims it was given, and those claims are produced by another interpretive act that is itself subject to steward review.

**What converged despite the granularity divergence:** All five providers identified the same core semantic structure (signal → specific handling → failure) and all classified it as Supported. Evidence identification remains convergent even when claim count diverges. The convergent layer is evidence; the divergent layer is claim boundaries.

**The research program's conclusion:** The Critic can be built. The pipeline of operations is now empirically grounded:

| Stage | Convergence | Governance |
|---|---|---|
| Evidence Identification | High (5/5 across two independent observations) | Automated |
| Evidence-Claim Mapping | Moderate | Automated with audit |
| Claim Normalization | N/A — policy-dependent | Steward |
| Verdict Classification | Low — policy-dependent | Steward (with policy configuration) |

### Connection to the Critic Phase

The frozen pipeline includes a Critic phase. This research program suggests the Critic should be designed to:

1. Evaluate whether specific claims in a rendered narrative are grounded in the canonical observations
2. Distinguish "unsupported" (claim has no textual anchor) from "contradicted" (claim conflicts with what the observation explicitly states)
3. Expose which evaluation policy produced which verdict (Conservative / Decomposition / Semantic), so the steward can inspect the policy, not just the verdict
4. Route claim sets through steward review before evaluation, since claim extraction is itself interpretive
5. Produce Findings that are themselves subject to steward review

The current Evaluation Functions are deterministic (structural, provenance, observation-coverage, constitutional, accessibility). A future LLM-backed Evaluation Function — one capable of evaluating whether an interpretation's specific claims are licensed by the evidence — would be the implementation of this research finding.

This is not authorized during Architecture Freeze v1.0. Record here and revisit post-freeze.

---

## Semantic Continuity Infrastructure *(Horizon Note — 2026-06-20)*

*Recorded during Era II Sprint E5. These observations are architectural horizon notes, not implementation directives.*

### The Reframe

Hermeneia is not a framework for AI generation. It is a framework for **semantic continuity**.

The question it answers is not "what did the document say?" It is "did the understanding survive the transformation?"

That question recurs across every domain where meaning must cross a boundary:

| Transmission boundary | Typical failure mode |
|---|---|
| Teacher → student | Memorization without comprehension |
| Author → reader | Expression without reception |
| Lawyer → client | Precision without intelligibility |
| Doctor → patient | Accuracy without actionable understanding |
| Legislature → citizen | Complexity without accessible inference |
| Scientist → policymaker | Evidence without applicable conclusion |
| Engineer → maintainer | Implementation without intention |
| Parent → child | Wisdom without context |

The same architecture applies to each. The ArchitectPlan is the semantic contract. The ExpressionProfile is the audience constraint. The EvaluationFunction is the fidelity check. The StewardDecision is the human governance act. None of these change. The ecology above them does.

### Domain Applications

**Education:** The student is not graded on memorization. The system measures whether the understanding was transmitted. A teacher can inspect the exact Finding where meaning was lost.

**Semantic proofreading:** Current proofreading asks "is this grammatically correct?" Hermeneia asks "did this revision preserve my intended understanding?" Preserved / omitted / injected / transformed — those four operations constitute a fundamentally different kind of editorial audit.

**Books with expression ecologies:** Every chapter of a book could carry a canonical ArchitectPlan. Child edition, scholar edition, audiobook, graphic novel, Spanish translation, Apple Intelligence summary — all evaluated against the same contract. The book gains an ecology of expression without losing itself.

**Software documentation:** Documentation rots because there is no contract between the original understanding and the downstream expression. With a canonical ArchitectPlan, every version of a guide — beginner, expert, CLI help, video script, interactive tutorial — can be checked against the same semantic obligations.

**Medicine:** Did the patient understand the diagnosis? Can they explain back the medication protocol? Was the explanation simplified without omitting a critical warning? That is a different safety model than grammatical review.

**Decision Point Initiative:** Legislative text ingested as Observations → Interpretations → ArchitectPlan → Citizen Profile → Rendered Explanation → Evaluation Functions → Finding[] → Human Stewardship. A citizen can inspect exactly which obligations were omitted or transformed. The system does not tell people what to think. It makes every transformation of legislative understanding inspectable, provenance-preserving, and human-governed. The stewardship — and ultimately the decision — remains human. That is the crucial distinction.

### Semantic Discovery of Persistent Generative Structures

*This is an entirely separate research program. Recorded here to preserve the hypothesis.*

A body of work — a lifetime of essays, letters, books, interviews — could be ingested as Observations. The system would derive ArchitectPlans across each work. It would then ask: do these plans compress toward recurring semantic structures?

Today's discovery systems ask: what is textually similar? What occupies nearby vector space?

Hermeneia could ask: what repeatedly generates correct inference across many expressive contexts?

An unknown author publishes a blog, a book, ten essays, a lecture, three interviews. Most search engines index words. Hermeneia could index persistent semantic contracts. It might discover the underlying generative structures — subsidiarity, distributed governance, ecological resilience — without caring whether those ideas were expressed through economics, theology, biology, or fiction.

Authors would become connected because they instantiate similar generative structures. Not because they cite one another. Not because they share vocabulary. Because they preserve the same underlying understanding.

**Constitutional constraint on this application:** Hermeneia must never claim to "measure if someone has understanding." That claim is not constitutionally defensible. What it can measure is "evidence that a body of work instantiates stable generative structures across transformations." Whether that constitutes understanding is a human judgment.

**The Goodhart warning:** This must never become an "Understanding Score." People will optimize for the score. Hermeneia should expose the substrate — recurring ArchitectPlans, recurring obligations, preserved transformations, lineage graphs, evaluation findings — and let scholars, readers, publishers, or institutions draw their own conclusions.

**Research hypothesis (not a constitutional principle):**

> The enduring contribution of a thinker may be measured not by the quantity of their writings nor the popularity of their expressions, but by the persistence of the generative structures that survive across their works, audiences, translations, and generations.

### The Infrastructure Threshold

A software project reaches the infrastructure threshold when its value is no longer determined by the applications it ships, but by the applications others build on it.

Hermeneia reaches that threshold if the development community treats the Constitution and its canonical objects as stable substrate — and builds their own expression profiles, evaluation functions, stewardship workflows, and domain applications above it without needing to extend the constitutional layer.

They won't extend the Constitution. They'll bring new participants, new ExpressionProfiles, and new stewardship workflows for domains the original authors haven't imagined.

That is exactly why the architecture freeze mattered. It did not freeze innovation. It froze the meaning of the substrate, so that innovation could flourish above it without breaking the foundation.

---

## Synthesis Layer *(Potential Future Layer — post-v1.0)*

*Recorded: 2026-06-21*

### Purpose

Aggregate accepted interpretations across a corpus into larger artifacts: essays, books, reports, courses, translations.

The frozen pipeline produces one RenderedNarrative per ArchitectPlan per ExpressionProfile. The Synthesis layer would aggregate across multiple ArchitectPlans — potentially across multiple source documents — into a single coherent artifact with its own provenance chain.

### Status

Future work. Not part of Architecture Freeze v1.0.

### What it would not change

The frozen ontology objects (Observation, Interpretation, Perspective, Blueprint, Architect, Artist, Critic) remain unchanged. Synthesis would be an aggregation layer above them, not a replacement for any existing stage.

### The open architectural question

Where does Synthesis sit in the pipeline? Two positions are plausible:

**Option A — above Artist:**
```
Blueprint × N  →  Synthesis Blueprint  →  Architect  →  Artist  →  Critic
```
The synthesized Blueprint aggregates claims from multiple source Blueprints, then passes through the existing Architect → Artist → Critic pipeline normally. No new canonical objects required.

**Option B — above Critic:**
```
RenderedNarrative × N  →  Synthesis  →  Synthesized Artifact
```
The Synthesis layer aggregates already-rendered narratives. Requires a new canonical object (SynthesizedArtifact) and a new Critic evaluation that measures fidelity across the composite source set rather than a single ArchitectPlan.

Option A is constitutionally simpler — it reuses all existing pipeline stages. Option B produces richer audit trails. Both are deferred.

### Connection to existing architecture

`blueprint_interpretation_links` and `blueprint_observation_links` already model many-to-many relationships between a Blueprint and its sources. A Synthesis Blueprint would extend this naturally — linking to Observations and Interpretations drawn from multiple source documents rather than one.

No schema changes are needed during the freeze. This can be explored in implementation using existing tables once the exit criteria for Architecture Freeze v1.0 are satisfied.

---

## Report as a Node with Version Lineage *(Potential Future Architecture — post-v1.0)*

*Recorded: 2026-06-21. Surfaced during Sprint demo preparation.*

### The Gap

The current pipeline treats the RenderedNarrative as a destination — the terminus of the chain. Real scholarly and analytical work is iterative. A report is not a final product; it is a round in a recursive conversation:

```
Blueprint v1  →  Architect  →  Artist  →  Critic  →  RenderedNarrative v1
                                                              ↓
                                                    Reader Annotations
                                                              ↓
                                                    New / Revised Blueprint v2
                                                              ↓
                                                    Additional Observations
                                                              ↓
                                              RenderedNarrative v2  (cites v1)
```

Currently, v1 and v2 exist as unrelated rows. There is no lineage between report versions. A reader cannot inspect what changed between them, what prompted the revision, or what new evidence entered the chain between cycles.

### What Is Missing

- A `superseded_by` or `parent_narrative_id` link between RenderedNarrative versions
- A record of what governance act (StewardDecision, FindingSet review, reader annotation) triggered the new cycle
- A view in the UI that shows report evolution as a vertical chain rather than a flat list
- A Critic that can compare v1 and v2 and report what changed semantically, not just textually

### Connection to Existing Architecture

The `StewardDecision` object already models the governance event that connects Finding → decision outcome. The extension is: a StewardDecision should be able to trigger a new blueprint cycle, and the resulting RenderedNarrative should reference the triggering StewardDecision as its provenance origin. That creates a full recursive lineage without a new pipeline stage.

### Why Deferred

Requires extending the RenderedNarrative schema and the blueprint creation workflow. Not a change to the ontology — no new canonical object needed — but a relational extension of existing objects. Record here; implement post-freeze.

**Priority (post-freeze):** High. This is the missing mechanism that makes Hermeneia a research instrument rather than a one-shot renderer.

---

## Concept / Theme Explorer *(Potential Future Layer — post-v1.0)*

*Recorded: 2026-06-21. Surfaced during Sprint demo preparation.*

### The Gap

Literary and scholarly analysis does not work observation-by-observation. It works through pattern recognition across a corpus. The current pipeline is observation-centric: one observation → interpretations → blueprint → narrative. There is no interface or data structure for the question "where does this concept appear across the entire corpus, and what do all observations sharing it say together?"

Example: a "Concept: Moral Authority" view might surface:

```
Concept: Moral Authority
    ├── OBS-19   "fundamental decencies is parcelled out unequally at birth"
    ├── OBS-23   "Only Gatsby … was exempt from my reaction"
    ├── OBS-203  [future observation]
    ├── OBS-477  [future observation]
    └── OBS-1201 [future observation]

Synthesis Interpretation:
  "The novel repeatedly questions the source and stability of moral
   authority — positioning it as inherited, performed, and ultimately
   untethered from virtue."
```

### What Is Missing

- A concept/theme registry (a lightweight tagging or clustering layer above observations)
- A concept → observation many-to-many join
- A Synthesis Interpretation that aggregates across multiple observations (distinct from a single-observation interpretation)
- A UI explorer that shows the concept, all linked observations, and the synthesis interpretation

### Relationship to the Synthesis Layer

This is architecturally related to the Synthesis Layer note above (aggregating Blueprints → Synthesis Blueprint). The difference: the Concept Explorer operates *below* the Blueprint level — it aggregates observations before interpretation, rather than aggregating narratives after rendering. Both are valid aggregation strategies; they answer different questions.

| Level | Aggregates | Answers |
|---|---|---|
| Concept Explorer | Observations | "Where does this idea appear across the corpus?" |
| Synthesis Layer | Blueprints or Narratives | "How do separate arguments combine into a larger argument?" |

### Why Deferred

Requires a concept registry — either a new table or a tagging extension of the observations table. Both are schema changes. Frozen under Architecture Freeze v1.0.

**Priority (post-freeze):** High. The Lineage Explorer shows trust for individual observations; the Concept Explorer would show pattern-level trust across the corpus. These are complementary views of the same underlying evidence base.

**Note:** The existing `herm concept <term>` CLI command is a primitive precursor — it does full-text search across observations for a term. The Concept Explorer would add steward-curated concept definitions, explicit observation tagging, and synthesis interpretations on top of that search foundation.

---

## Human Legibility Gap *(UX Architecture Gap — post-demo)*

*Recorded: 2026-06-21. Surfaced during Sprint demo preparation.*

### The Observation

The current UI exposes internal epistemic artifacts effectively: Observations, Interpretations, Blueprints, Architect Plans, Validation Reports, Lineage graphs. However, the primary human-facing artifact — the rendered narrative itself — has no dedicated reading experience.

A RenderedNarrative currently exists only as:
- a node inside the Lineage graph (labelled "Story")
- a text field inside the Critic audit detail screen

It cannot be easily read as a standalone document. It cannot be exported, copied, downloaded, or shared.

### The Symptom

New users encounter internal system objects before encountering the actual result. The UI optimizes for inspection (provenance, audit, lineage) rather than consumption (reading, sharing, exporting). A professor, government reviewer, or hiring manager encountering the interface for the first time will ask:

> "Can I read the report?"

That question has no obvious answer in the current UI.

### Current vs. Future Information Hierarchy

**Current** — user enters through the database:
```
Lineage
 → Plan
 → Blueprint
 → Story
```

**Future** — user enters through the report:
```
Report
 ├─ Read
 ├─ Audit
 ├─ Provenance
 ├─ Sources
 └─ Versions
```

The same data exists in both cases. The difference is entry point and framing.

### The ID Problem

Current UI surfaces hash IDs prominently:
```
b399600d…
da9b322f…
cdf5c169…
```

These are essential for provenance and useful for developers. A human reader wants:
```
The Moral Architecture of The Great Gatsby
v1.0 · Literary Profile · OpenAI GPT-4o
63% Semantic Fidelity · Generated June 21, 2026
```

then the actual report text.

The hashes belong behind an "Inspect Provenance" button. The report belongs front and center.

### Future Direction: Reader View

```
Reader View
 ├─ Read report (full-screen prose view)
 ├─ Download PDF
 ├─ Export Markdown
 ├─ Export DOCX
 ├─ View lineage
 ├─ View audit
 └─ Create revised version
```

The report should become a first-class artifact. The lineage, audit, and provenance tools should be accessible from it, not the other way around.

### Why Deferred

No schema changes required — the RenderedNarrative already exists. This is a routing and rendering change: the entry point for the application should be "here is your report" rather than "here is your corpus." Implement when preparing for external audiences post-demo.

**Priority (post-demo):** P1. This is the most common question from first-time users and the easiest gap to close — the data exists, the surface is missing.

---

## Guided Onboarding *(UX Architecture Gap — post-demo)*

*Recorded: 2026-06-21. Surfaced during Sprint demo preparation.*

### The Observation

The system currently assumes prior knowledge. A first-time user lands on:

```
Corpus  Lab  Review  Critic  Lineage  Architect
```

and immediately asks: *What am I supposed to do?*

Not because the system is bad — because it contains an entire epistemology. The six tabs look like unrelated tools. The sequential pipeline relationship between them exists only in the builder's head, not in the product.

A new user does not know that:
```
Observation → Interpretation → Blueprint → Architect → Artist → Critic
```

is a single pipeline, not six separate features.

### The Hidden Problem

The system explains *what happened*. It does not explain *why the user should care*.

For example: **63% Semantic Fidelity**

A returning user reads: *the narrative failed to preserve enough of the Architect contract.*
A new user asks: *Is 63 good? What happens at 80? What happens at 95?*

The same gap applies to every canonical term: Observation, Interpretation, Blueprint, Architect Plan. The system exposes the objects but not their purpose.

### Future Direction: First Launch Walkthrough

```
Welcome to Hermeneia

Hermeneia helps you transform evidence into auditable reports.

The workflow has six stages:

  1. Observe       Extract claims from source documents
  2. Interpret     Assign meaning to what was found
  3. Organize      Arrange interpretations into a coherent argument
  4. Specify       Define what the report must communicate
  5. Write         Generate the report with a chosen AI provider
  6. Audit         Measure how faithfully the report preserved the evidence

What are you trying to do?

  ○  Research a topic
  ○  Analyze a document
  ○  Create a report
  ○  Compare interpretations
  ○  Audit AI output
```

This gives context before the user touches anything.

### Minimum Viable Onboarding Copy

**What Hermeneia Does:**
> Most AI systems generate text. Hermeneia preserves the chain between source evidence and final report.

**Why It Matters:**
> Every statement can be traced back to its source. Every report can be audited. Every AI-generated narrative can be measured for semantic fidelity.

**Workflow:**
```
Evidence → Observation → Interpretation → Blueprint → Report → Audit
```

**Result:**
```
Evidence → Understanding → Report
```

### Why Deferred

No schema changes required. Pure UI and copy work. Deferred until after the demo — the demo audience (investors, researchers, collaborators) will already have been briefed by the presenter. Onboarding becomes critical when the product reaches self-serve external users.

**Priority (post-demo):** P3. Necessary before any public-facing distribution. Without it, the architecture is not self-explanatory.

---

## "How Hermeneia Works" — Interactive Pipeline Map *(UX Architecture Gap — post-demo)*

*Recorded: 2026-06-21. Surfaced during Sprint demo preparation.*

### The Observation

People understand systems faster when they can see the map. The frozen pipeline diagram exists in documentation (`CLAUDE.md`, `docs/`) but not in the product itself.

A persistent `Guide` or `Help` screen — not a documentation link, but an interactive visualization — would give every user a navigable mental model before they touch the corpus.

### Proposed Screen

```
How Hermeneia Works

 Document
    ↓
 Observation     [click → go to Corpus]
    ↓
 Interpretation  [click → go to Review]
    ↓
 Blueprint       [click → go to Lab]
    ↓
 Architect Plan  [click → go to Architect]
    ↓
 Narrative       [click → open Reader View]
    ↓
 Critic Audit    [click → go to Critic]
```

Every box is clickable and routes to the relevant screen. Hovering shows a one-sentence description of what that stage does and why it matters.

### Why This Matters

The Lineage Explorer already shows the pipeline for a specific narrative. The interactive map would show the pipeline in the abstract — before any corpus exists, before any report has been generated. It is the conceptual entry point that the rest of the UI currently lacks.

### Why Deferred

Pure UI work. No schema changes. Deferred until post-demo when the application is being prepared for external distribution.

**Priority (post-demo):** P4. Dramatically reduces time-to-comprehension for new users. Once present, most of the onboarding copy becomes redundant — the map does the explaining.

---

## Stage Count Noun Labels *(UI Polish — post-demo)*

*Recorded: 2026-06-21.*

Current pipeline stage counts read as:

```
Observe      2,823 preserved
Interpret    3 preserved
Organize     1 preserved
Plan         1 preserved
Read         3 preserved
Audit        3 preserved
```

"Preserved" is architecturally correct (evidence is preserved through the pipeline) but reads oddly for middle stages. Humans think in nouns. The cleaner form:

```
Observe      2,823 observations
Interpret    3 interpretations
Organize     1 blueprint
Plan         1 architect plan
Read         3 reports
Audit        3 validations
```

Each stage should use its own canonical noun as the count label. The nouns are already the frozen names — this is a display change only, no data change.

**Implementation:** each pipeline stage object in `/api/project/summary` already has a `key` field. Add a `noun` field (singular and plural) alongside it, or derive it from a frontend lookup table keyed on `stage.key`.

**Priority:** Low. Polish pass after demo.

---

## Report Identity on the Start Screen *(UI Polish — post-demo)*

*Recorded: 2026-06-21.*

Current Start screen shows:

```
Read    3 preserved
```

A user immediately asks: *which three?* The count is less useful than the identity of the reports. The moment a user clicks "Read Report" they want to know what they're choosing between — not just that three exist.

Proposed: the pipeline stage card for "Read" should expand to show report identities inline:

```
Read
├─ Literary Profile · OpenAI GPT-4o
├─ Executive Profile · OpenAI GPT-4o
└─ Children's Profile · OpenAI GPT-4o
```

Each entry is clickable and routes directly into that report's Reader View.

This is the same data already returned by `/api/reader/narratives` — it just needs to be surfaced one level earlier, inside the pipeline stage card rather than requiring a tab navigation first.

**Implementation:** fetch `/api/reader/narratives` alongside the project summary on the Start screen, and inject report identities into the "Read" stage card when count > 0.

**Priority:** Medium. Becomes important once there are multiple reports with different profiles/providers, which is already the case with the Gatsby demo corpus.

---

## Three-Layer Onboarding *(UX Architecture — post-demo)*

*Recorded: 2026-06-21.*

The current Start screen addresses only Layer 3 (operational onboarding — what are the stages?). Layers 1 and 2 are missing.

**Layer 1 — What is this?**
A new user sees the six pipeline stages but could still conclude "another document analysis tool." Nothing on the current screen answers the identity question: *what makes Hermeneia different from an AI summarizer?*

**Layer 2 — Why is this different?**
The philosophical differentiator needs to be visible before the pipeline:
- Evidence is permanent.
- Meaning requires human stewardship.
- Reports are disposable. Lineage is preserved.
- Every conclusion can be traced back to source evidence.

Without Layer 2, users see workflow. With it, users see architecture.

**Layer 3 — How do I work here?** (currently implemented as the pipeline grid)
- Upload document → review observations → propose interpretations → steward them → generate reports → audit → trace lineage.

**The current gap:** The Start page jumps straight to Layer 3 while skipping Layers 1 and 2. A user who doesn't already know what Hermeneia is will see six buttons and no reason to care about them.

**Proposed structure for the Start screen:**

```
[Layer 1]  One-sentence identity statement
[Layer 2]  Three-line philosophical differentiator
[Layer 3]  Six pipeline stages with completion indicators  ← currently built
[CTA]      Current stage → go
```

**Implementation:** Layers 1 and 2 are static copy, no API calls. They can be added above the existing onboarding grid without any backend changes.

---

## Center of Gravity Shift *(UX Architecture Horizon — post-v1.0)*

*Recorded: 2026-06-21.*

The current navigation assumes users want to move forward through the pipeline:

```
Start → Observe → Interpret → Organize → Plan → Read → Audit
```

This is correct for stewards building a corpus. It is probably wrong for most users.

Most users arrive wanting understanding, not pipeline stages. Their natural trajectory is:

```
Start
 ↓
Read Report          ← most people arrive here first
 ↓
Investigate Claims   ← "where did this come from?"
 ↓
Trace Lineage        ← "show me the evidence"
 ↓
Return to Corpus     ← "I want to explore more"
```

The pipeline-forward navigation optimizes for corpus builders. A second navigation pattern — report-first — should eventually exist alongside it for readers and reviewers.

This is not an architecture change. It is a second entry point into the same data. Both paths are valid. The current implementation supports only the builder path. The reader path requires the Start screen to feature "Read Report" as prominently as "Open Corpus."

**Connection to Human Legibility Gap:** This note is the navigational expression of the same underlying gap — the system treats the pipeline as primary and the report as output, when most users will treat the report as primary and the pipeline as provenance they can optionally inspect.

---

## Living Understanding — Recursive Report Versioning *(Era III Horizon)*

*Recorded: 2026-06-21.*

The current mental model is:

```
Document → Report
```

What actual research produces is:

```
Document
 → Report v1
    → Questions raised by v1
    → Additional investigation
    → Report v2
       → Questions raised by v2
       → Additional investigation
       → Report v3
```

Hermeneia currently preserves lineage for evidence and interpretations, but not yet for *understanding itself*. A report is a terminal artifact, not a stewardable object capable of generating new research questions.

The architectural implication: reports should eventually become versioned, stewardable artifacts that feed recursively back into the corpus. A reader's annotation on Report v1 should be traceable through the corpus it prompted, the blueprint revision it generated, and the Report v2 it produced.

This is not a UI feature. It is a fundamental reframing of what Hermeneia preserves. Currently it preserves:
- The chain from evidence to report (upstream)

Eventually it should also preserve:
- The chain from report to new understanding (downstream)

**The canonical statement:**

> Hermeneia currently preserves lineage for evidence and interpretations, but not yet for understanding itself. Reports should eventually become stewardable, versioned artifacts capable of generating new research questions that recursively feed investigation back into the corpus.

**Connection to Report Versioning note** (already in this file): that note describes the mechanism (`superseded_by` link, StewardDecision as trigger). This note describes the *purpose* — the recursive research loop is not just a convenience feature; it is what makes Hermeneia a research instrument rather than a one-shot renderer.

**Priority:** Era III. Do not implement during Architecture Freeze v1.0. The exit criteria for the freeze do not include this capability. It is the most important thing to build after the freeze is lifted.

---

## Project as a First-Class Entity *(Potential Future Layer — post-v1.0)*

*Recorded: 2026-06-21.*

Currently the Hermeneia data model has no object above the corpus. Everything is organized around a single flat collection of observations, interpretations, and blueprints. The mental model a user brings is different:

```
Project: The Great Gatsby
 ├── Corpus (observations, source extractions)
 ├── Interpretations
 ├── Blueprints
 ├── Reports
 └── Audits

Project: FDA Guidance Corpus
 ├── Corpus
 ├── Interpretations
 ...
```

A user thinks in terms of investigations or projects, not in terms of observations. "I'm working on the Ohio Budget Analysis" — not "I'm working on a corpus."

**The current workaround:** the app is opened against a specific `hermeneia.db` file, which implicitly defines the project scope. Multi-project is possible today by running separate databases.

**What a Project entity would add:**
- Named, datable investigations with a description and research question
- Multiple source documents per project
- Project-level switching in the UI ("Recent Projects" list)
- A unit of sharing and export

**Why deferred:** introducing `projects` as a table that owns `source_documents`, `observations`, etc. requires restructuring the entire schema. That is a significant architecture change. The current implicit-project-per-database model is sufficient for the demo and for single-investigator use.

**Implement when:** multi-project, multi-user, or shared corpus use cases emerge. Until then, the single-database model is correct.

---

## Work Identity and Corpus Deduplication *(Era III Architecture — post-v1.0)*

*Recorded: 2026-06-21. One of the highest-priority post-freeze architectural additions.*

### The Problem

Without Work identity, Hermeneia fragments over time:

```
gatsby.pdf                 → corpus A
The_Great_Gatsby.pdf       → corpus B
gatsby-cleaned.pdf         → corpus C
gatsby.epub                → corpus D
```

These are not four corpora. They are four manifestations of one Work. Without a canonical identity layer above documents, network effects disappear — 100 researchers studying Gatsby produce 100 separate corpora, 100,000 duplicate observations, and no accumulated understanding.

### The Missing Layer

The current hierarchy is:

```
Document → Extraction → Observation
```

The correct hierarchy is:

```
Work
 ↓
Edition
 ↓
Document      (gatsby.pdf, the_great_gatsby.pdf, gatsby.epub)
 ↓
Extraction
 ↓
Observation
```

**Work:** The persistent intellectual object. *The Great Gatsby* by F. Scott Fitzgerald. Survives across all editions, formats, and digitizations.

**Edition:** A specific textual instantiation. Scribner 1925 first edition. Oxford World's Classics 2009 edition. These may have meaningful textual differences.

**Document:** A specific digital artifact. A PDF, EPUB, or plain text file. Multiple documents can represent the same Edition. Multiple editions can represent the same Work.

### Three Layers of Identity

**Layer 1 — Exact duplicate detection (already solved):**
The compiler hashes the file contents (`sha256(file)`) and uses it as the document ID with `INSERT OR IGNORE`. Two uploads of the identical file produce one document record. No steward action required.

**Layer 2 — Near-duplicate detection (deferred):**
`gatsby.pdf` and `gatsby-cleaned.pdf` have different hashes but nearly identical content. A corpus signature derived from extracted terms, sentence hashes, or semantic embeddings could surface this. If similarity exceeds a configurable threshold, the system flags a possible duplicate and routes to a steward decision. Does not merge automatically.

**Layer 3 — Work identification (deferred):**
When a corpus is created, the system prompts for or infers `title`, `author`, `publication year`. This produces a `Work` record. Future uploads attempt to resolve against existing Works by metadata match or corpus similarity. The steward ratifies the identity claim:

```
Upload: the_great_gatsby.pdf

Possible Match Found
The Great Gatsby · F. Scott Fitzgerald · 1925
Similarity: 99.7%

Attach to existing Work?   [Yes]   [Create New Work]
```

### The Constitutional Constraint

**Do not auto-merge. Ever.**

High similarity does not imply identity. Counter-examples:
- King James Bible vs. New International Version (similar vocabulary, different text)
- Original report vs. revised report (deliberate change, meaningful difference)
- Draft policy vs. final policy (legal distinction)

The machine proposes identity. The steward ratifies identity. This is identical to the pattern everywhere else in Hermeneia: machines propose, humans canonize. Merging documents without steward ratification would corrupt the provenance chain.

### Two Separate Identity Proposals

This is the critical design distinction to preserve when implementing:

**Document Identity** — is this file the same as another file?
```
This upload appears to be:
  The Great Gatsby.pdf
  99.9% content match with existing document [sha256: 4a7f...]
```
A straightforward binary question. SHA-256 solves Layer 1. Near-duplicate detection solves Layer 2.

**Work Identity** — does this document participate in the same understanding space as other documents?
```
This document appears related to:
  The Great Gatsby (Work)
  F. Scott Fitzgerald · 1925
  98.7% confidence
```
A semantic question. A scholarly edition, a collection containing Gatsby, a paper *analyzing* Gatsby — all have high textual overlap but are not the same Work. The system is not merely asking "are these the same file?" It is asking "are these participating in the same understanding space?"

These are different decisions and must be kept separate. Collapsing them would produce wrong merges at the edges (a paper about Gatsby attached to the Gatsby Work; a revised draft treated as the same document as the original).

### What Becomes Possible

With Work identity, understanding accumulates rather than fragments:

```
Work: The Great Gatsby

Researchers: 100
Observations: 50,000
Interpretations: 8,000
Blueprints: 900
Reports: 300
```

Every new researcher starts with accumulated understanding. A researcher can ask:
- Show me all accepted interpretations related to moral authority
- Show me the highest-ratified interpretations of the green light metaphor
- Show me interpretations rejected by stewards and why

At that point Hermeneia stops looking like an AI report generator and starts looking like **GitHub for understanding** — where understanding accumulates rather than restarting from zero every time a new person uploads a document.

### The Canonical Object

The thing that persists across generations is not `gatsby.pdf`. It is *The Great Gatsby*. The PDF is merely evidence of the Work. The correct canonical object is `Work`, not `Document`. `SourceDocument` should eventually become a leaf node — evidence pointing upward at an Edition pointing upward at a Work.

### Relationship to Existing Architecture

- The `source_documents` table already stores the SHA-256 hash (Layer 1 complete)
- The `observations` table already links to `source_document_id`
- The `observation_terms` table already provides the vocabulary needed for corpus signature comparison (Layer 2 input)
- No new schema changes are needed during the freeze. The `Work` entity is post-freeze.

### Why This Is the Right Time to Record It

The upload endpoint just built makes this problem real. A user can now upload documents through the UI. The first time two users upload different scans of the same text, Hermeneia will silently create duplicate corpora. Recording this now means the deduplication logic is designed intentionally rather than discovered as a bug at scale.

**Priority (post-freeze):** P1 for any multi-user deployment. Without it, shared corpora fragment rather than accumulate.

---

## Witness Cognitive Responsibility + Marginalia Interface

*Recorded: 2026-06-25*  
*Source: Convergence of Gatsby comparative analysis (Experiments 001–002) and Marginalia/Authorship Deed synthesis*  
*Full design: [`docs/research/witness_marginalia_authorship_deed.md`](research/witness_marginalia_authorship_deed.md)*

### The Observation

Two separate threads converged on the same principle simultaneously.

The Gatsby experiments showed that observation and classification remained stable across English and Spanish executions, while question selection diverged. This pointed to something earlier than observation: the act of human attention that precedes interpretation.

Separately, the Marginalia proposal identified a missing interface: a place where the human act of reading — highlighting, labeling, noting, reflecting — produces epistemic artifacts rather than comments.

These are the same insight at different scales. The Marginalia interface is what Witness looks like as product. The Gatsby finding is what Witness looks like as research. The Authorship Deed is what Witness produces as an institutional artifact.

### The Cognitive Responsibility

```
Witness        ← records human attention before interpretation begins
    ↓
Explorer       ← discovers candidate interpretations
    ↓
Architect
    ↓
Artist
    ↓
Critic
    ↓
Governance
```

Witness asks: *"What caught my notice?"*

It does not interpret. It records: "I saw this. This caught my attention. I don't know why yet."

### What Witness Captures

- Reader highlights (text selection or bounding box coordinates for scanned pages)
- Human labels (Claim, Evidence, Question, Contradiction, Theme, etc.)
- Cognitive role buckets (Attention, Discovery, Reconstruction, Verification, Governance)
- Notes and annotations
- Post-section reflections (structured: central claim, what mattered most, what confused, what changed)

### The Authorship Deed

The provenance chain culminating from the Witness layer becomes a portable, author-owned artifact establishing rightful relation to the work. Not surveillance. Not a teacher dashboard. The author controls what is shared.

Constitutional classification:
- HumanWitness annotations → Canonical Objects (immutable, lineage-bearing)
- AuthorshipDeed → Derived Artifact (regenerable from the chain)
- Marginalia interface → Projection (disposable view over Witness objects)
- Post-section reflections → Human Judgments (irreducible)

### The Refined Central Claim

This synthesis refines the white paper's central claim:

Before: *Hermeneia separates cognitive responsibilities.*  
After: *Hermeneia preserves the evolution of understanding by separating and governing the cognitive responsibilities through which understanding develops.*

Witness is the earliest stage of that preservation, and therefore its foundation.

**Priority (post-freeze):** P0. Witness is the missing first stage of the cognitive architecture. The MVP is the Marginalia interface with highlights, labels, buckets, and post-section reflection. The Authorship Deed follows from the full chain.

---

## Question Constructor *(P0 — first post-freeze implementation)*

*Recorded: 2026-06-25*  
*Source: Comparative Analysis Experiment 001 (English) vs Experiment 002 (Spanish) on The Great Gatsby*

### The Observation That Forced This

Experiments 001 and 002 showed that observations and classifications were nearly identical across English and Spanish executions. The divergence appeared at exactly one point: **question selection**.

English investigation asked: *Can people reinvent themselves?*  
Spanish investigation asked: *Can people ever separate themselves from history?*

The same observations. Different governing questions. Everything downstream — evidence weighting, model construction, compression — followed from that single difference.

This suggests the pipeline is currently missing an explicit stage between Explorer and Architect where competing investigative questions are surfaced and the governing question is selected by the Steward.

### Proposed Cognitive Responsibility

```
Explorer
    ↓
Question Constructor     ← surfaces competing investigative questions
    ↓
Human Steward selects    ← governing question is a Steward decision
    ↓
Architect
```

The Question Constructor does not interpret. It does not weight evidence. It generates candidate investigative questions from the observation set and presents them for Steward selection.

Example output from a Gatsby corpus:

- What is the function of aspiration?
- What is the function of wealth?
- What is the function of memory?
- What is the function of class?
- What is the function of history?

The Steward selects one (or several). Everything downstream follows.

### Why No Ontology Change Is Required

The governing question is a **Steward decision** — already a constitutional category. No new canonical objects. No new tables. The question becomes an input to the Architect rather than a new pipeline stage requiring its own schema.

This could be implemented as:
- A field on the NarrativeBlueprint (`governing_question`)
- A Steward-ratified annotation on the Blueprint before Architect compilation
- A new prompt parameter surfaced in the Explorer output

### What This Changes

If question selection is the primary culture-adaptive variable, then:

1. Expression profiles control *how* understanding is communicated.
2. Governing questions control *what* understanding is constructed.

These are orthogonal. The same governing question can be expressed in literary English, children's Spanish, or historical Arabic. Different governing questions produce different understandings of the same corpus, all textually grounded, none incorrect.

**The deeper implication:** disagreement between investigators may begin before evidence is ever weighed. Exposing the governing question explicitly makes that divergence visible and discussable rather than hidden in the interpretation.

### Research Connection

Full analysis in [`docs/research/experiment_001_002_comparative_analysis.md`](research/experiment_001_002_comparative_analysis.md).

Hypothesis status: *supported by two executions, requires replication across additional corpora and domains.*

**Priority (post-freeze):** P0. This is the missing cognitive role between Explorer and Architect. It requires no ADR under the frozen architecture — governing question maps to an existing Steward decision category.

---

## Stage 07 — Synthesis *(P0 — first post-freeze implementation)*

*Recorded: 2026-06-22*

### The Observation That Forced This

The current pipeline ends at `Rendered Narrative`. A user running six providers × three profiles generates 18 specialized reports — each elaborating the same Architect Plan in a different register. The problem: every report is correct, but none of them compound. The Mandarin literary report and the Executive report cover the same semantic ground in different words. There is no mechanism to ask: *which of these taught us something new?*

This is not a bug in the Artist or the Critic. It is a missing stage. The specialized reports were designed to be **research memos**, not **final deliverables**. Without a Synthesis stage, the pipeline has no destination for those memos to go.

The pressure became visible during an essay-writing session: a user uploading *The Great Gatsby* for a 10-page metaphor essay received four paragraphs repeated across ten profiles. The problem was not the models. It was that there was no compounding step.

### The Diagnosis: Stewardship Currently Stops at Interpretation

The constitutional principle is: *Meaning requires stewardship.* But as of the freeze, stewardship applies only at the interpretation level — observations are observed, interpretations are accepted or contested, and then the pipeline runs without any further human gate.

The natural extension is:

```
Observation Stewardship   (✓ exists)
      ↓
Interpretation Stewardship  (✓ exists)
      ↓
Narrative Stewardship     (within freeze: accept/reject rendered narratives with rationale)
      ↓
Synthesis                 (post-freeze: Stage 07)
```

This is internally consistent with the existing constitution. It does not contradict the frozen ontology — it extends stewardship to a layer that already has objects.

### Stage 07 Specification (ADR Draft)

**Stage 07 — Synthesis**

```
Purpose:
  Construct a higher-order understanding from steward-approved
  work product of the earlier stages.

Inputs (only steward-approved items pass through):
  - Accepted observations
  - Accepted interpretations
  - Accepted blueprints
  - Accepted rendered narratives  ← requires Narrative Stewardship first
  - Accepted critic findings

Output (Synthesis Dossier):
  - Research position (what the evidence establishes)
  - Distinct insights extracted per accepted report
  - Rejected reports with steward rationale (documented, not discarded)
  - Evidence map (which observations support which conclusions)
  - Final thesis (synthesized from accepted work product, not raw observations)
  - Essay outline / teaching artifact / comparative analysis
    (determined by ExpressionProfile applied to the Synthesis stage)
```

**Key design constraints:**
- Synthesis is generated from accepted work product, not from raw observations. This is what makes it higher-order.
- A Synthesis Dossier is NOT another rendered narrative. It is a structured artifact with provenance links to all the accepted work that produced it.
- The ExpressionProfile still applies at Synthesis — the same dossier can be expressed as an academic essay, a teaching artifact, a comparative analysis, or an executive briefing.
- Rejected reports are preserved with steward rationale. The "rejected" set is itself data — it shows which lenses added noise vs. signal for a given directive.

**New object required:**
```
SynthesisDossier
  id
  blueprint_id
  directive
  accepted_narrative_ids: list[str]
  rejected_narrative_ids: list[str]
  rejection_rationales: dict[narrative_id, str]
  distinct_insights: list[str]
  research_position: str
  evidence_map: dict[claim, list[obs_id]]
  final_thesis: str
  created_at: str
  source: "ai-generated" | "steward-authored"
```

**New table required:**
```sql
CREATE TABLE synthesis_dossiers (
  id TEXT PRIMARY KEY,
  blueprint_id TEXT REFERENCES narrative_blueprints(id),
  directive TEXT NOT NULL,
  accepted_narrative_ids TEXT NOT NULL DEFAULT '[]',   -- JSON
  rejected_narrative_ids TEXT NOT NULL DEFAULT '[]',   -- JSON
  rejection_rationales TEXT NOT NULL DEFAULT '{}',     -- JSON
  distinct_insights TEXT NOT NULL DEFAULT '[]',        -- JSON
  research_position TEXT,
  evidence_map TEXT NOT NULL DEFAULT '{}',             -- JSON
  final_thesis TEXT,
  created_at TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'ai-generated'
);
```

### What Narrative Stewardship (within freeze) Prepares

Before Stage 07 can run, the system needs a corpus of **narrative stewardship decisions** to draw from. Within the freeze, this means:

1. **Accept/Reject for rendered narratives** — a steward marks each report as accepted or rejected
2. **Required rationale** — the rationale is the most important artifact. "Introduces culturally distinct reading of social obligation" vs. "No novel insights beyond Executive report." This is meta-interpretation: the system begins accumulating knowledge about which lenses produce signal vs. paraphrase.
3. **Narrative comparison view** — side-by-side view of two or more rendered narratives so the steward can make informed decisions

The acceptance record is stored on `rendered_narratives` as two new columns:
```sql
ALTER TABLE rendered_narratives ADD COLUMN narrative_status TEXT DEFAULT 'pending';
ALTER TABLE rendered_narratives ADD COLUMN narrative_rationale TEXT;
```

This is within freeze: new columns on an existing table, no new objects, no new pipeline stages.

### Why The Rationale Is The Most Valuable Artifact

The accept/reject button is not the point. The rationale corpus is.

Over time, the pattern of rationales answers:
- Which ExpressionProfiles consistently produce novel insight vs. paraphrase?
- Which provider × profile combinations add the most signal?
- Which types of directives benefit from the Mandarin lens vs. the Executive lens?

This is the system learning what works — not from model fine-tuning, but from accumulated steward judgment. It is the most Hermeneia-native form of intelligence: human stewardship as structured data.

### Relationship to Existing Architecture

| Object | Status |
|---|---|
| `rendered_narratives` | Exists. Add `narrative_status` + `narrative_rationale` columns within freeze. |
| `expression_profiles` | Exists. Apply at Synthesis stage to determine output form. |
| `SynthesisDossier` | New object. Requires ADR approval and freeze lift. |
| `synthesis_dossiers` table | New table. Post-freeze. |
| Stage 07 pipeline position | Post-freeze. Below Critic, above final deliverable. |

### The Frozen Pipeline Does Not Change

The frozen pipeline diagram is preserved:

```
Critic
  ↓
Rendered Narrative
```

Stage 07 sits **after** Rendered Narrative. The freeze diagram stops at Rendered Narrative. Stage 07 extends it. This is not a redrawing of the frozen diagram — it is a new entry below it.

**Priority (post-freeze):** P0. This is the missing stage that completes the pipeline's intellectual purpose. Without it, specialized reports are terminal outputs. With it, they become research memos in a compounding understanding process.

---

## Source Boundary Integrity *(P0 — trust-critical)*

*Recorded: 2026-06-23*

### The Incident That Forced This

A user uploaded a supplemental document about Warhammer 40k alongside The Great Gatsby. The system had no mechanism to separate these sources. Observations from the Warhammer document became part of the same corpus as Gatsby observations. The system subsequently suggested Warhammer concepts as potentially relevant to the Gatsby thesis.

This is not a minor UX issue. It is a methodological failure. Hermeneia's entire value proposition is trustworthy provenance. If a user cannot know which document originated a claim, the system cannot be trusted.

### The Core Problem

The current schema has `source_document_id` on observations — the lineage information *exists*. But:
1. There is no UI to see or filter by source document
2. The pipeline does not enforce source scope during analysis
3. There is no concept of "primary source" vs "reference material" vs "user notes"
4. Multiple uploaded documents are silently merged into one corpus

### Required Architecture

**Source Classification**: Every source document needs a `source_role` field:
- `primary` — the text being analyzed
- `reference` — secondary scholarly material
- `notes` — user's own notes and annotations
- `commentary` — imported analytical commentary
- `excluded` — document present but not participating in analysis

**Analysis Scope Control**: Before any interpretation, observation, or blueprint generation, the user must be able to set:
```
Current Analysis Scope
✓ The Great Gatsby (primary)
☐ User Notes
☐ Warhammer 40k Document (excluded)
```

This scope is enforced at every pipeline stage — observations, interpretations, blueprint generation, and Artist rendering.

**Cross-Reference Instead of Merge**: The long-term pattern is not `Document A + Document B = one corpus` but:
```
Document A (primary)
    ↕
Relationship Layer
    ↕
Document B (reference)
```

Document B observations can *reference* Document A claims. They cannot silently become indistinguishable from them.

**Evidence Attribution on Every Claim**: Every interpretation, blueprint section, and rendered narrative must be able to answer "which source document did this evidence originate from?" This is a display requirement, not just a storage requirement.

### Document Detachment (Not Deletion)

The user instinct to prevent deletion is correct. The user's need is not to destroy data — it is to stop data from influencing analysis. These are different operations:

- `DELETE document` — destroys irreversibly
- `Detach from workspace` — removes from active scope, data preserved
- `Exclude from analysis` — document present, not participating
- `Archive` — demoted to historical record, not active

The right affordance is `Exclude from analysis scope`, not a delete button.

### Why This Is P0

Hermeneia's constitution says: *Evidence is permanent. Meaning requires stewardship.* If the system cannot reliably answer "where did this claim come from," the permanence guarantee is meaningless. Source boundary integrity is the foundation on which all other trust properties rest.

---

## Guided Onboarding and Value Clarity *(P1)*

*Recorded: 2026-06-23*

### The Problem

First-time users are dropped into the system with no guide. The workflow is non-obvious. The value proposition — why structured interpretation, why preserved evidence, why this vs. just asking GPT — is not demonstrated.

The result: users explore randomly, miss key features, and do not understand why the data permanence and provenance guarantees matter until they've already done something wrong (like mixing sources).

### What Users Need to Understand Within 3 Minutes

1. What the system does (not the pipeline steps — the *purpose*)
2. Why documents are valuable to preserve
3. Why structured interpretation matters over raw AI output
4. What becomes possible as more documents accumulate
5. That their work is being saved and what that means

### Onboarding Design Principles

**Learn by doing, not reading.** The current explainer cards are better than nothing but they explain steps rather than demonstrating value. The first experience should be interactive: upload a document, watch the system extract observations, pick one, ask a question.

**Progressive disclosure.** The pipeline terminology (Observation, Interpretation, Perspective, Blueprint, Architect, Artist, Critic) is meaningful to an expert user but overwhelming on first contact. Introduce terms as they become relevant, not all at once.

**Show a result first.** The fastest path to understanding is seeing a good output, then working backward to how it was produced. Consider a "try a demo" mode that shows a pre-populated result before the user uploads anything.

**The guide must be a mode, not a modal.** A popup that explains the system is immediately dismissed. A guided workflow that walks the user through their first document in context cannot be dismissed because it *is* the first experience.

### Sequence for First-Time User

```
1. Upload a document (immediate action, immediate result)
2. System shows extracted observations — "here's what we found"
3. User picks one observation — "what do you want to know about this?"
4. System generates interpretations — "here are competing readings"
5. User accepts one — "you've made your first steward decision"
6. System explains: "this decision is now permanent and traceable"
7. User sees their interpretation linked to the observation forever
8. System offers: "want to generate a report? want to explore more?"
```

At no point does the user read documentation. They do work and understand by doing it.

---

## Workspace Isolation and Document Scope Control *(P1)*

*Recorded: 2026-06-23*

### The Problem

A user's workspace can become contaminated. In the first real session, a Warhammer 40k document was added to a Gatsby workspace. The documents merged silently. The user had no way to know, no way to see the scope, and no way to fix it without destroying data.

The deeper issue: there is currently no concept of a Workspace as a first-class object. Everything lives in one global database. This is fine for a single-user, single-document proof of concept. It is a methodological problem the moment any complexity arrives.

### Workspace as a First-Class Object

```sql
CREATE TABLE workspaces (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'active',   -- active | archived
  created_at TEXT NOT NULL
);

CREATE TABLE workspace_documents (
  workspace_id TEXT REFERENCES workspaces(id),
  source_document_id TEXT REFERENCES source_documents(id),
  role TEXT DEFAULT 'primary',    -- primary | reference | notes | excluded
  added_at TEXT NOT NULL,
  PRIMARY KEY (workspace_id, source_document_id)
);
```

A workspace contains documents. Analysis is always scoped to a workspace. Switching workspaces switches the entire analytical context.

### Document Lifecycle Within a Workspace

- **Add to workspace** — document enters scope
- **Exclude from analysis** — document stays in workspace, does not participate
- **Detach from workspace** — document removed from scope (not deleted)
- **Archive workspace** — entire workspace preserved but demoted (does not affect other workspaces)
- **Clone workspace** — experiment without affecting original

### Active Scope Indicator

At all times, the UI must show:

```
Working in: Gatsby Research
Primary source: The Great Gatsby (2,823 obs)
Active documents: 1 of 3
```

When the scope changes, all pipeline outputs update to reflect it.

---

## Navigation and Workflow Freedom *(P1)*

*Recorded: 2026-06-23*

### The Problem

The current pipeline navigation is a row of top-level buttons. There is no sense of position, no back/forward history, and no way to understand where you are in the workflow or how far you've come.

Users report feeling "constrained" — they are afraid to navigate away because they don't know if they'll be able to return to their current state.

### Requirements

**Workflow position indicator**: A progress display at the top of each screen that shows where the current screen sits in the pipeline:
```
Upload → Corpus → Lab → Review → Architect → Read → Critic
                  ▲ you are here
```

**Back/Forward navigation**: Browser-native back/forward should work correctly (requires routing). Within a pipeline session, "Continue →" and "← Back" buttons on each screen.

**State preservation**: Navigating away from a screen must not lose work in progress. Forms should be preserved in sessionStorage or local state.

**No dead ends**: Every screen must have a clear "what do I do next?" affordance. The pipeline steps on the home screen already hint at this — it needs to be visible throughout, not just on entry.

---

## Data Persistence Transparency *(P1)*

*Recorded: 2026-06-23*

### The Problem

Users do not know that their work is being saved. They do not understand why saving matters. The system's core value — that interpretations are preserved permanently, with provenance, traceable to evidence — is invisible during normal use.

A user who doesn't know their work is saved will treat the system as ephemeral. They will not build up interpretations over time. They will not steward carefully. They will not understand why the "established" vs "speculative" distinction matters.

### What Needs to Be Visible

**Persistent save status**: Every interpretation, steward decision, and accepted narrative should show a "saved" indicator. Not a spinner — a permanent marker that this item is part of the permanent record.

**Corpus growth feedback**: As the user works, they should see their corpus growing. "You have established 4 interpretations. They are permanently preserved."

**The permanence principle stated explicitly**: The home screen, onboarding, and the steward review screen should all clearly state: "Observations and accepted interpretations cannot be deleted. This is by design."

**Why it matters**: "Because understanding evolves. The interpretation you accept today may be contested in five years. The evidence it was based on remains. The chain of reasoning is preserved."

---

## User Accounts and Personal Libraries *(P2)*

*Recorded: 2026-06-23*

### Requirements

Standard authentication (email/password minimum, OAuth recommended). Each user has:
- Personal document library
- Personal workspace collection
- Personal steward identity (steward decisions are attributed to them)
- Persistent session state

### Architecture Note

The existing `steward_decisions` table already has a steward identity field. User accounts extend this to a real authenticated identity. The schema changes are additive:

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT,
  created_at TEXT NOT NULL
);

ALTER TABLE steward_decisions ADD COLUMN user_id TEXT REFERENCES users(id);
ALTER TABLE workspaces ADD COLUMN owner_id TEXT REFERENCES users(id);
```

### Sequence dependency

User accounts require Workspace as a first-class object (see above). Implement workspaces first, then attach user identity to them.

---

## Multiple Document Management *(P2)*

*Recorded: 2026-06-23*

### Requirements

- Document library view (list of all uploaded documents with metadata)
- Create and name documents on upload
- Switch active document
- Visual indicator of which document is "primary" in the current analysis
- Document metadata: title, author, upload date, page count, observation count

### Relationship to Workspace

A document library is a workspace-scoped view. The user sees documents belonging to their current workspace. Global document search (across all workspaces) is a separate, later feature.

---

## Cross-Document Intelligence *(P3)*

*Recorded: 2026-06-23*

### The Vision

The system becomes exponentially more valuable as documents accumulate. A single document gives you one perspective. Ten documents on related subjects give you a knowledge network.

Use cases:
- "How do other scholars interpret the green light symbol?" → compare interpretations across uploaded commentary
- "Does this theme appear in Fitzgerald's other works?" → cross-reference corpus
- "Which of my reference documents best supports this claim?" → evidence network

### Architecture

The Relationship Layer (from Source Boundary Integrity, above) is the prerequisite. Once documents have explicit relationships rather than silent merging, cross-document queries become possible:

```
Primary Text: The Great Gatsby
    ↕ 
Reference: Fitzgerald biography (supports OBS-19 interpretation)
    ↕
Commentary: Harold Bloom essay (contests established interpretation)
    ↕
User Notes: Research annotations (author-of-record: user)
```

Each edge in this graph has a type (supports, contests, extends, illustrates) and provenance.

### The Long-Term Value Proposition

A user who has been using Hermeneia for two years has not just a library of documents — they have a knowledge network where every claim is traceable to evidence, every interpretation is dated and attributed, and conflicting readings are surfaced rather than hidden.

This is the vision: not a document-to-report pipeline, but a compounding understanding engine. The value is in the accumulated graph, not in any individual report.


---

## Semantic Obligation Quality (discovered Sprint E3, 2026-06-24)

### The Finding

The Semantic Evaluation Function revealed that the Architect is generating **lexical obligations**, not **semantic obligations**.

Running the Semantic Critic against Gatsby narratives produced:
- 9 supported (terms with interpretation + observation evidence)
- 47 weak (terms present but only observation-backed)
- 7 omitted

The weak and omitted buckets were dominated by tokens like "the", "and", "from", "gorgeous", "series" — individual words extracted from required phrases, not semantic commitments.

### The Distinction

| Lexical Obligation | Semantic Obligation |
|--------------------|---------------------|
| "the" | "moral inheritance" |
| "gorgeous" | "aspiration exceeds social class" |
| "from" | "narrator's detachment from judgment" |
| "unbroken" | "performed continuity of selfhood" |

A **lexical obligation** checks whether a word appears.  
A **semantic obligation** checks whether a *proposition was established*.

### What This Means for the Architect

The current Architect prompt extracts `required_terms` at token granularity. The Semantic Critic has now given us empirical evidence that this produces obligations which cannot carry semantic weight — because a term like "the" appearing in a narrative tells you nothing about whether the intended meaning was preserved.

### The Direction (not a decision)

Future Architect contracts may need to distinguish:

```
required_terms      →  [lexical, checked by Structural Critic]
required_propositions → [semantic, checked by Semantic Critic]
```

Where a proposition is something like:
```json
{
  "claim": "Gatsby's aspiration is aesthetic, not moral",
  "evidence_anchor": "extraordinary gift for hope",
  "negation": "Gatsby achieves legitimate moral standing"
}
```

The Semantic Critic would then evaluate whether the proposition (not just its vocabulary) was instantiated in the narrative.

### The Proof Analogy

A formal proof doesn't verify that the word "therefore" appears.  
It verifies that the necessary proposition was established before the conclusion was drawn.

Hermeneia may be approaching the point where obligations need to be modeled as **propositions** rather than vocabulary. The Semantic Critic is already architecturally capable of evaluating proposition-level evidence chains — the gap is entirely in obligation *generation* (the Architect prompt), not in evaluation (the Semantic Critic function).

### What Does Not Change Under the Freeze

- No new ontology objects
- No new tables
- No new pipeline phases

The fix, when made, lives entirely in the Architect prompt and in how `required_terms` are populated — both of which are implementation, not architecture.

### Trigger Condition for Acting

When Architect plans consistently produce phrase-level or concept-level required_terms, the Semantic Critic's score will become a meaningful fidelity signal rather than a lexical coverage metric. That's the condition that makes this worth acting on.

---

## "Bring Your Own Report" Onboarding Path (2026-06-24)

### The Insight

Most experts don't start with a blank investigation. They start with existing work — a draft, memo, paper, sermon, proposal — and need a rigorous reviewer, not a content generator.

The current onboarding assumes:
```
Human states thesis → Hermeneia builds on it
```

The proposed path inverts this:
```
Human writes report → Hermeneia reconstructs the intent → Human ratifies or corrects
```

### Why This Fits the Frozen Architecture

No new tables, ontology, or pipeline phases are required. The mapping is:

| New concept | Existing artifact |
|---|---|
| Uploaded report | source_document |
| Extracted claims/observations | observations (from the report itself) |
| Intent Hypothesis | narrative_blueprint (framed differently) |
| Human ratification | steward review (upstream of investigation) |
| Correction artifact | interpretation (of the gap between surface meaning and authorial intent) |

The Blueprint was always an intent hypothesis. The current onboarding just asks humans to state their intent before generating it. This path extracts the intent from work already done.

### The Delta Loop

When Hermeneia says:
```
Your thesis appears to be: "Gatsby is a critique of economic inequality."
```

And the human responds:
```
Close. My actual thesis is: "A critique of status pursuit, not wealth itself."
```

That correction is itself a meaningful artifact — it captures the gap between the surface reading of the report and the author's actual intent. This gap is precisely what Hermeneia is designed to surface and preserve.

### Implementation Path (within the freeze)

Three changes, all implementation:

1. **New onboarding UI path** — "Start from Existing Work" alongside "Start from Thesis". Accepts upload of report document.

2. **Architect prompt variant** — reads the uploaded report and generates a Blueprint framed as Intent Hypothesis:
   - Thesis (as Hermeneia reads it)
   - Purpose
   - Perspective
   - Key Claims
   - Intended Audience
   - Open Questions (where intent is ambiguous)

3. **Blueprint review reframe** — present the Blueprint as "Here is my understanding of your intent. Is this right?" with inline editing and a ratification step before the investigation proceeds. The confirmed Blueprint becomes the investigation charter.

### Why This Is the Practical On-Ramp

People don't wake up wanting to create observations and interpretations. They wake up with reports that need to be stronger. "Is this any good?" is the real question Hermeneia can answer — but only if the entry point matches where people actually start.

This also resolves the tension between "Hermeneia isn't finished" and "I need to submit applications." You don't need Hermeneia to generate the report. You write the report. Hermeneia becomes the system that stress-tests it.

### The Philosophical Foundation

The first thing Hermeneia proves in this path is not something about the source text. It's something about the investigator's own intent: "Before we analyze the text, let's establish what you're actually trying to establish." That's an unusually rigorous foundation for everything that follows — and it's exactly what the proof-system-for-meaning framing requires.

---

## Human-AI Division of Labor: Automate Discovery, Ratify Meaning (2026-06-24)

### The Finding

The Gatsby essay algorithm revealed a precise division of labor:

**Mechanical (automatable):**
- Collect candidates (extract metaphors, claims, structures)
- Classify (distinguish metaphor from atmosphere from symbol)
- Cluster (group by concept)
- Compress (identify what the clusters share)
- Generate competing thesis candidates
- Generate counterarguments against each candidate

**Judgment (human-sovereign):**
- Which compression survives scrutiny?
- Which interpretation misreads the evidence?
- Which candidate is worth pursuing?
- What does the investigation ultimately claim?

Currently, Hermeneia asks humans to do both. The labor of extraction sits between corpus and useful investigation. Most users will not do that labor. They will leave.

### The Principle

> Automate discovery. Human-ratify meaning.

Or more precisely: **AI proposes. Human disposes.**

This does not weaken constitutional sovereignty — it concentrates it. If the human exercises judgment AND does extraction labor, sovereignty is diluted by work. If the AI does extraction and the human exercises pure judgment over the surviving compressions, the human is doing only what only a human should do.

### The Multiple Blueprint Candidates Pattern

No schema change required. The Architect already generates one Blueprint per investigation. Generating three competing candidates and presenting them for human selection is a workflow change, not an architectural one.

For Gatsby:
- **Candidate A:** "The novel critiques the American Dream." (broad, defensible, shallow)
- **Candidate B:** "The novel explores desire and longing." (thematically richer)
- **Candidate C:** "The novel examines the conflict between interpretation and reality." (analytically precise)

Human response: "C is strongest. B contributes. A remains subordinate."

The ratified Blueprint is the same artifact. The difference is what the human was asked to do: *select and refine* rather than *originate*.

### The Adversarial-Before-Ratification Pattern

Current pipeline:
```
Blueprint → ArchitectPlan → Artist → Critic
```

The Gatsby algorithm suggests:
```
Corpus
  → AI: collect, classify, cluster, compress, generate candidates, attack candidates
  → Human: select + amend surviving candidate
  → Ratified Blueprint → ArchitectPlan → Artist → (Critic)
```

The Critic still runs after rendering. But the thesis has survived adversarial pressure *before* it reaches the Architect. Rendering starts from a hardened interpretation, not a fresh hypothesis.

This is the architectural implication of Stage 7 (adversarial testing) from the Gatsby algorithm. It does not require a new Critic phase — it requires that the Blueprint generation step include adversarial compression before presenting candidates to the human.

### Connection to "Start From Existing Work"

When a user uploads an existing report or corpus, Hermeneia should run the full discovery cycle automatically and present the compressed outputs — not ask the human to manually create observations and interpretations one at a time. The human's first meaningful interaction should be:

> "Here are the strongest interpretations I found. Here is the evidence. Here are the objections. Which direction should we pursue?"

That is dramatically lower friction and dramatically higher value than the current onboarding. It is also closer to how experts actually work.

### What Does Not Change

- Human judgment remains sovereign over meaning
- The Blueprint is still ratified before investigation proceeds
- The Critic still validates the rendered narrative against its evidence chain
- No new ontology, tables, or pipeline phases required

---

## Translation vs. Cross-Cultural Interpretation: A Critical Distinction (2026-06-24)

### The Finding

Running the Gatsby metaphor algorithm under the constraint "interpret as a natural Spanish-speaking reader would" produced a different clustering, a different thesis center of gravity, and a convergent meta-conclusion:

**Anglo-American path:** Dream → Failure → *loyalty to interpretation over reality*
**Hispanic cultural prior path:** Identity → History → Failure → *stories detached from the realities that formed you*

Not the same claim. Not contradictory. Two valid compressions of the same evidence shaped by different priors about what kind of loss matters most.

Crucially: **the metaphors did not change. The grouping changed.**

Cultural influence entered at the clustering/compression stage (Stages 4–5 in the Gatsby algorithm), not at the rendering stage.

### The Architectural Distinction

| Mode | What changes | Pipeline stage |
|---|---|---|
| Translation profile | Rendering language and style | Artist (last) |
| Cross-cultural interpretation frame | Clustering, compression, thesis candidates | Perspective (early) |

A Spanish translation of an Anglo-American Gatsby reading ≠ a Hispanic-cultural-prior reading rendered in Spanish.

- The first re-skins the output. The algorithm ran once; the Artist renders in a different language.
- The second re-runs the algorithm from Stage 4 with different cultural defaults active during clustering.

Hermeneia must be able to do both, and must know which one is being requested.

### Where This Lives in the Frozen Pipeline

The **Perspective stage** (between Interpretation and Blueprint) was always the right slot for cultural interpretive frame. It has not yet been used for this purpose. Cultural interpretation frame is a Perspective-level artifact, not an ExpressionProfile-level artifact.

ExpressionProfiles govern: tone, voice, audience, language, reading level.
Cultural interpretation frames govern: what counts as a meaningful cluster, what loss is most significant, what relationships carry the most weight, what the evidence is evidence *of*.

### The ADR Question

Before implementing Translation Profile support (Era II Exit Criteria), resolve:

> Is the requested output a translation of an existing interpretation, or a re-interpretation from a different cultural prior?

These require different pipeline entry points and produce constitutionally different artifacts. A translated narrative traces to an Anglo-American Blueprint. A cross-culturally interpreted narrative traces to a Hispanic-prior Blueprint. The provenance chain is different. The lineage is different. The Critic would need to know which Blueprint it is validating against.

### The Convergence Signal

Both readings converge at roughly the same meta-level truth. This is either evidence that Fitzgerald wrote something genuinely universal, or evidence that robust interpretations tend to converge at sufficient abstraction levels, or both. That convergence is itself a finding worth recording — it is evidence that strong interpretations are not merely culturally relative projections but can achieve cross-cultural validity through different paths.

---

## Meaning = Text × Interpretive Framework (2026-06-24)

### The Formal Statement

> **Meaning = Text × Interpretive Framework**

This is not a metaphor. It is a specification of what interpretation is.

The Gatsby cross-cultural algorithm demonstrated this precisely. The text did not change. The evidence did not change. The quotations did not change. What changed was the interpretive weighting — what the reader considers important, tragic, admirable, sacred, or obvious. And when the weighting changed, an entirely different novel emerged without altering a single word of Fitzgerald.

### The Pipeline Implication

The current frozen pipeline places Perspective *after* Interpretations:

```
Observations → Interpretations → Perspective → Blueprint
```

Cross-cultural interpretation reveals that the framework operates *before* observations are meaningfully extracted. Readers with different cultural defaults do not just cluster observations differently — they notice different things in the first place.

A reader whose defaults weight Family > Individual will register Gatsby's abandonment of his father as a morally significant observation. A reader whose defaults weight Self-Invention > Belonging may not register it as primary evidence at all.

The framework shapes what counts as an observation worth recording. Therefore:

```
Text × [Interpretive Framework] → Observations → Interpretations → Blueprint
```

The framework is a parameter to the extraction process, not a stage that follows it.

### What Does Not Change

The frozen stage name "Perspective" is correct. The stage is in the right place in the canonical diagram. What needs to be formalized is that the Perspective specification must be established *before* observation extraction begins, and must be held consistently through the extraction process.

This is a prompt engineering and workflow question, not a schema change.

### Cultural Defaults as Framework Parameters

From the Gatsby exercise, cultural defaults that shaped the Hispanic-prior interpretation included:

```
Family > Individual
History > Reinvention
Belonging > Self-Creation
Relationships > Achievement
Community > Personal Ambition
Duty > Desire
```

These are not facts about the text. They are facts about what the reader's worldview treats as significant. They shaped:
- What observations were foregrounded (Gatsby's rejection of his father)
- How metaphors were grouped (memory, identity, belonging, loss rather than desire, distance, vision, decay)
- What constituted the fatal error (refusing to accept the past as part of the present, not refusing to revise interpretation)
- What the final metaphor meant (history carrying humanity, not humanity striving toward the future)

### Framework-Invariant vs. Framework-Dependent Claims

Both readings converged at the meta-level: "human beings suffer when the stories they tell about themselves become detached from the realities that formed them."

This convergence is structurally significant. It suggests some claims are **framework-invariant** — they survive lens rotation across culturally distinct interpretive frames. Other claims are **framework-dependent** — they emerge from a specific set of cultural defaults and would not survive the rotation.

A future Critic function could identify which claims in a reading are framework-dependent and which are framework-robust. Framework-robust claims have stronger evidential standing because they have been validated across multiple interpretive frames without collapsing.

### The Deepest Disagreement

The most important sentence from the exercise:

> "The deepest disagreement between readers often occurs before interpretation begins, at the level of what they consider important, sacred, tragic, admirable, or obvious."

This is where Hermeneia's provenance model becomes critical. If two readings of the same text disagree, the disagreement is rarely about the text. It is about the framework. Making frameworks explicit — specifying the cultural defaults, weightings, and priors that shaped an interpretation — is the prerequisite for any productive disagreement about the text itself.

Hermeneia is a system for making readings accountable. Making the framework explicit is part of making the reading accountable.

---

## Epistemological Shift: Assumptions vs. Questions (2026-06-24)

### The Discovery

Cross-cultural re-interpretation revealed two distinct layers beneath any reading:

1. **Cultural Assumptions** — what a reader treats as background fact (Family > Individual; History > Reinvention)
2. **Cultural Questions** — what a reader instinctively treats as the *problem worth investigating*

These are not the same thing. Assumptions shape how evidence is weighted. Questions shape what the reader is even looking for.

**American critical question:** *What does the green light symbolize?*
**Hispanic-prior critical question:** *What kind of person needs a green light?*

The second question doesn't just weight evidence differently. It reframes the entire inquiry from semantic (what does it mean?) to anthropological (what wound does it reveal?). The object becomes a symptom. Theme becomes human condition.

### The Algorithm Evolution

```
Stage 1 (basic):
  Extract Metaphors → Find Themes → Build Thesis

Stage 2 (Hermeneian):
  Extract Metaphors → Find Assumptions → Find Lens → Generate Thesis

Stage 3 (cross-cultural):
  Extract Metaphors
  → Extract Cultural Assumptions
  → Extract Cultural Questions          ← new
  → Reweight Evidence
  → Generate Alternate Thesis
  → Compare Interpretations
```

"Extract Cultural Questions" is not reducible to "Extract Cultural Assumptions." Questions are generative. They determine what counts as a finding in the first place.

### The Deepest Conclusion

> The algorithm exposes not only what a text says, but what a reader must already believe in order to hear it.

Two coherent, well-evidenced, valid readings of the same text can produce different conclusions — not because one misread, but because they were asking different questions before they opened the book. Each interpretation reveals what its culture instinctively treats as the deepest problem:

- American reading asks: *Can a person reinvent themselves?*
- Hispanic-prior reading asks: *Can a person escape their history?*

Neither proves the other wrong. Together they reveal the space of what the novel is capable of sustaining.

### Implications for Hermeneia

**Comparative interpretation** is Hermeneia's most distinctive potential capability — not generating a single authoritative reading, but running multiple interpretive frameworks against the same corpus and surfacing what each framework requires and reveals.

This requires:
1. Explicit framework specification (cultural assumptions + cultural questions) before observation extraction begins
2. Multiple Blueprint candidates generated under different frameworks
3. A comparison layer that maps which claims survive framework rotation (framework-robust) and which do not (framework-dependent)

Framework-robust claims have stronger evidential standing. Framework-dependent claims are not weaker — but they require their framework to be disclosed.

Making a reading accountable means making its prerequisites visible: the background questions that caused certain observations to register as significant and others to fade. Without explicit prerequisites, two readers can argue about conclusions while the real disagreement remains invisible, buried in what each considered too obvious to state.

---

## The Minimum Input Schema: Five Questions (2026-06-24)

### The Design Spec

The minimum information a human must provide for the interpretation algorithm to execute reliably is not a thesis. It is a **reading frame** — five questions:

```yaml
1. What text are we interpreting?
2. What culture/worldview should we prioritize?
3. What question are we trying to answer?
4. What counts as evidence?
5. What would prove us wrong?
```

Everything else is derived.

### Mapping to the Frozen Pipeline

| Question | Pipeline stage |
|---|---|
| What text are we interpreting? | Corpus / source_documents |
| What culture/worldview should we prioritize? | Perspective specification |
| What question are we trying to answer? | Blueprint (intent hypothesis) |
| What counts as evidence? | Observation classification schema |
| What would prove us wrong? | Adversarial Critic / counterargument generation |

### The Full Schema (detailed interface)

```yaml
document:
  title:
  author:
  corpus:

reader_profile:
  culture:
  language:
  philosophical_tradition:
  historical_orientation:    # future_focused | history_focused | cyclical | etc.

interpretive_focus:
  primary_question:
  secondary_questions: []

evidence_types:
  - metaphor
  - symbol
  - character
  - setting
  - dialogue
  - narrative_structure

counterarguments:
  required: []              # competing readings that must be addressed
  falsification_condition:  # what evidence would disprove the thesis
```

### Output Schema

```yaml
thesis:
  statement:

evidence:
  supporting: []
  contradicting: []

clusters:
  - name:
    evidence: []

alternative_readings:
  - reading:
    strengths: []
    weaknesses: []

framework_dependencies:      # which claims require this specific lens
  - claim:
    required_assumption:

framework_robust_claims:     # which claims survive lens rotation
  - claim:
    surviving_across: []
```

### Implementation Note: This IS the "Start From Existing Work" Onboarding

The five-question minimum is the design spec for the Hermeneia onboarding form. Rather than asking "what is your thesis?" (wrong starting point) or presenting a blank investigation form, the system asks:

1. What are we reading?
2. Through whose eyes?
3. What question are we asking?
4. What will count as evidence?
5. What would change our mind?

The UI can present these progressively. Answers to questions 1 and 3 are sufficient to begin observation extraction. Questions 2 and 4 shape classification. Question 5 triggers the adversarial layer.

### The Domain-Agnostic Claim

The algorithm is not literary analysis. It is interpretation. The same five questions apply to:

- Scripture (what does this passage require of its congregation?)
- Legal documents (what does this contract require its signatories to already believe?)
- Government policy (what does this memo require as prior commitment?)
- Scientific papers (what theoretical assumptions must be held for this data to yield these conclusions?)
- Personal narratives (what wound produced this story?)
- Business plans (what market assumptions must be true for this model to work?)

Same input schema. Same pipeline. Different corpus and lens. This is the Semantic Continuity Horizon — interpretation infrastructure that applies wherever meaning matters and accountability is required.

---

## The Full Evolved Pipeline: From Interpretation to Meta-Thesis (2026-06-24)

### The Recursive Step

In the Gatsby exercise, we didn't just interpret the novel. We applied the interpretation algorithm to the interpretation process itself — and produced a more general version of it. The methodology was its own first subject. That recursive capacity is what distinguishes a mature interpretive system from a one-pass analysis tool.

### Interpretive Dimensions > Cultural Labels

"Spanish-speaking reader" is not a lens. It is a shortcut to a configuration across a space of interpretive dimensions:

```yaml
dimensions:
  identity:
    range: [inherited, constructed]
  time:
    range: [cyclical, linear]
  community:
    range: [primary, secondary]
  history:
    range: [active_force, inert_record]
  wealth:
    range: [virtue, suspicion, stewardship]
  authority:
    range: [hierarchical, egalitarian]
  truth:
    range: [correspondence, coherence, pragmatic]
  obligation:
    range: [relational, contractual]
```

A "lens profile" is a specific configuration across these dimensions. Mexico ≠ Spain ≠ Argentina — but they occupy nearby regions of this space. A Christian American may share more dimensions with a Catholic Mexican than with a secular American. Cultural labels are heuristics for dimension configurations, not the dimensions themselves.

### Stage -1: Lens Discovery

Before choosing a lens, discover which dimensions are likely to produce meaningful interpretive divergence for this specific corpus.

```
Document
↓
Extract latent assumptions (what does this text assume without stating?)
↓
Map assumptions to interpretive dimensions
↓
Identify dimensions that vary across readers
↓
Generate candidate lens profiles
↓
Rank expected interpretive divergence
↓
Present candidate lenses to human for selection
```

This changes Hermeneia from a guided analysis tool into an interpretive exploration engine. The user doesn't need to know which lens to try — Hermeneia surfaces the lenses that are likely to produce meaningfully different readings.

### The Full Pipeline (current evolved form)

```
Corpus
↓
Observation (culture-independent)
↓
Classification (culture-independent)
↓
Assumption Extraction (what does the document assume?)
↓
Interpretive Dimension Mapping (which assumptions vary?)
↓
Lens Generation (build profiles from dimensions)
↓
Question Generation (per lens: what question naturally arises?)
↓
Interpretation (per lens)
↓
Adversarial Testing (per lens)
↓
Cross-Lens Comparison
↓
Invariant Extraction (what survives all lenses?)
↓
Meta-Thesis (emerges from convergence, not chosen)
```

### The Meta-Thesis as Emergent Discovery

The meta-thesis is not selected. It emerges from asking what claim survives rotation across all lenses:

```
American:      Interpretation vs Reality
Hispanic:      Identity vs History
Christian:     Idolatry vs Truth
Psychological: Projection vs Acceptance
Economic:      Incentives vs Desire

Invariant: Humans organize their lives around internal models
           that reality eventually tests.
```

That statement was not available to any single lens. It required five independent readings to converge on it. The meta-thesis has stronger epistemic standing than any individual reading because it is framework-robust — it survived lens rotation.

### The Highest Critic Function

Not: "does the narrative honor its evidence?"
But: "which claims survive lens rotation?"

- A claim that appears in one reading is a **finding**
- A claim that appears across all readings is a **discovery**

Framework-dependent claims are not weaker — they require their framework to be disclosed. Framework-robust claims are stronger because they have been validated across multiple genuinely different question-generating machines.

### The Contribution, Precisely Stated

> By exposing the assumptions, questions, evidence, counterarguments, and convergence points for each lens, the system turns interpretation from an opaque act into a structured, inspectable, and comparable workflow.

Traditional criticism: *What does this text mean?*
Hermeneia: *What does this text become under different explicit interpretive frameworks — and what survives across all of them?*

That is a different research question. It does not replace interpretation with relativism. It makes the interpretive process itself observable. And it produces a class of claims — framework-robust findings — that have earned their generality by surviving the comparison.

---

## Observation Clustering: Ephemeral Computation, Not Canonical Object (2026-06-24)

### The Pattern

Three times this sprint, the instinct to add a new object was wrong:

| Initial instinct | Reality |
|---|---|
| Need a better Semantic Critic | Need better Architect obligations |
| Blueprint is a planning artifact | Blueprint is an Intent Hypothesis |
| Need Observation Clusters | Clusters are ephemeral; Interpretations are canonical |

### The Constitutional Question

The proposed schema (observation_clusters + observation_cluster_memberships) stores the grouping as a first-class object. But the grouping is how a candidate interpretation was *generated* — not what the human evaluates.

Tomorrow a better model may group the same observations differently:

- Today: Identity, Memory, Belonging, Status
- Tomorrow: Performance, Self-Invention, Social Distance, Time

Neither is wrong. They are different compressions. What the human evaluates is the *claim* each compression produces — not the compression itself.

**The grouping is ephemeral. Like embeddings. Like nearest-neighbor search. We use it; we don't store it constitutionally.**

### The Canonical Object Is Already There

The pipeline is:

```
Observations
↓
AI grouping pass  ← ephemeral
↓
Candidate Interpretations  ← stored, evidential_status='speculative'
↓
Human review  ← steward review (existing)
↓
Ratified Interpretations  ← stored, evidential_status='established'
```

The support indicator is already computable:
- `interpretation.evidence_observation_ids` — which observations back this claim
- `coverage_metrics()` — what fraction of observations are covered

What the human wants to see ("Hermeneia believes these observations collectively suggest: Identity Formation, confidence 0.82, with these supporting observations") is an Interpretation, not a Cluster.

### The Prototype That Proves It

Run a grouping pass over observations, generate candidate interpretations from each group, store as `evidential_status='speculative'`, surface in existing review UI. No new tables required.

**The ADR trigger:** If stewards repeatedly wish they could navigate back to the grouping — "show me the other observations in this cluster" — then the grouping itself is load-bearing and deserves its own object. If they only ever care about the interpretation the grouping produced, the grouping was correctly ephemeral.

The ADR is only needed if the prototype reveals the grouping is something people want to preserve. Until then: use it, don't store it.

---

## The Explorer: Fourth Cognitive Job (2026-06-24)

### The Insight

"The writing itself is the final stage. Not the first." — established the Artist's position.
"Interpretation is not the first stage either. Discovery is." — establishes the Explorer's position.

The same recursive move, applied one level deeper.

### Four Cognitive Jobs (distinct and non-overlapping)

```
Explorer     discovers what might be meaningful
Architect    reconstructs what the investigation is actually claiming
Artist       expresses that claim faithfully
Critic       tests whether the expression honored the claim
```

Each fails independently. Diagnosable failures are the goal.

### The Explorer's Contract

**Internal implementation:** clustering, embeddings, nearest-neighbor search, graph algorithms — whatever produces good candidate interpretations. Can change without notice.

**External contract:** "Hermeneia searched the evidence for candidate interpretations." Stable across implementations.

**External name:** Interpretive Exploration (not "grouping pass," not "clustering").

### Constitutional Safety

The Explorer produces `evidential_status='speculative'` interpretations into the existing `interpretations` table. No new ontology. No new tables. The steward is the only path to `established`. The constitutional center holds.

```
4,446 observations
↓
Explorer generates 50 candidate interpretations (speculative)
↓
Human: reject 42 / strengthen 6 / merge 2
↓
8 ratified interpretations (established)
```

### The Research Notebook (UX target)

For each candidate interpretation, the investigator sees:

```
Candidate: "Identity Formation"
Confidence: Medium

Supporting observations: OBS-17, OBS-41, OBS-88, OBS-143
Potential counter-evidence: OBS-211, OBS-402
Related candidate: "Social Performance"

Actions: ✓ Accept  ✎ Modify  ⇄ Merge  ✗ Reject  🕒 Defer
```

The steward isn't editing rows. They're conducting research.

### What This Resolves

- The friction problem: humans shouldn't discover obvious patterns manually. The Explorer should.
- The Architect's role: receives candidate understandings from exploration, reconstructs what the investigation is actually claiming.
- The onboarding problem: "Start From Existing Work" can run the Explorer first, then present candidate interpretations for ratification before the Architect ever generates a Blueprint.

### The Governing Principle

**AI accelerates inquiry. Humans remain responsible for judgment.**

Discovery is accelerated. Judgment is not delegated.

---

## Interpretation Science: Comparative Execution and the Diff (2026-06-24)

### The Breakthrough

Running two lens executions against identical corpora and diffing the results produces a finding about how interpretation works — not just about the specific text.

**Gatsby diff results:**

| Stage | English/American | Hispanic prior | Divergence |
|---|---|---|---|
| Observations | green light, valley, boats | green light, valley, boats | NONE |
| Classification | symbol, metaphor, atmosphere | symbol, metaphor, atmosphere | NONE |
| Questions | "Can Gatsby reinvent himself?" | "Can someone escape history?" | MAJOR |
| Evidence emphasis | green light, "you can't repeat the past", boats | James Gatz, father, marriage, child, Wilson | moderate |
| Compression | Interpretation | Identity | MAJOR |
| Thesis | loyalty to interpretation over reality | separation from history and relationships | MAJOR |

**The empirical finding:** Cultural influence enters at question generation, not at observation or classification. The thesis changed because the same evidence was compressed differently — not because different evidence was found. The lenses asked different questions of identical evidence.

### What This Means for Interpretive Disputes

Most interpretive disagreements are not about evidence. Arguing about evidence when the real disagreement is at the question level is what makes most interpretive disputes irresolvable. Hermeneia's diff makes the layer of disagreement explicit and locatable.

### The Interpretation Diff as Projection

No new tables required. The diff compares two existing execution traces:

```
Execution A (lens profile 1): observations → questions → compressions → blueprint → narrative
Execution B (lens profile 2): observations → questions → compressions → blueprint → narrative

Diff: at each stage, what changed? What stayed stable?
```

The invariant extraction follows: what claim survives when the diff shows convergence?

### The Four Outputs of a Hermeneian Analysis

1. **Execution Trace** — provenance chain: observations → questions → compressions → blueprint → narrative → findings
2. **Lens-Specific Thesis** — what this interpretive framework emphasizes, premises explicit
3. **Interpretation Diff** — where this reading diverges from other coherent readings, and at which stage
4. **Invariant Extraction** — what claim survives across all executed frameworks

### Object of Study Shift

The object of study is no longer only the text. It is the space of plausible interpretations generated by different lenses.

Traditional criticism: "What does this text mean?"
Hermeneia: "What interpretations does this text sustain, how do they diverge, and what invariant survives all of them?"

That is interpretation science, not just interpretation. The methodology is reproducible, the execution is traceable, and the disagreements are locatable — which is what distinguishes a research program from an opinion.

---

## Four-Layer Architecture of Understanding (2026-06-24)

### The Discovery

The Gatsby execution, when carried to completion, extracted not meaning but computation. The loop that emerged:

```
Observation → Interpretation → Prediction → Behavior → Reality → Prediction Error → Revision → [back to Interpretation]
```

This is a general cognitive architecture. It describes how any learning system — human, organizational, fictional, theological, scientific — builds, tests, and revises its model of reality.

Gatsby's tragedy: the Revision node is blocked. Nick's reliability: the Revision node executes every cycle. The father in Chapter 9: History arriving as a Revision trigger that is too late.

### The Four Layers

```
Layer 4  PURPOSE     "Why does this algorithm exist?"    almost no systems model this
Layer 3  PROCESS     "What algorithm generated this?"    rare; this is the breakthrough
Layer 2  MEANING     "What does it mean?"                where most systems stop
Layer 1  PERCEPTION  "What exists?"                      all systems begin here
```

Most AI systems are strong at Layers 1–2. Layer 3 requires extracting the causal model that generates observed behaviors, not just naming what they mean. Layer 4 requires forming and testing hypotheses about *purpose* — why this algorithm was built, what it is for, what it would take to falsify it.

### The Functional Reframe (Layer 3)

When Layer 3 analysis is applied, characters stop being symbols and become agents with computational roles:

| Character/Object | Interpretive reading (L2) | Computational function (L3) |
|---|---|---|
| Green Light | hope, aspiration | prediction generator |
| Daisy | romantic ideal | reality generator |
| Tom | privilege, opposition | prediction challenger |
| Nick | observer, narrator | revision engine |
| Father (Ch. 9) | grief, history | history restorer |
| Valley of Ashes | moral decay | reality cost function |
| Boats against current | human striving | continuous learning loop |

The same functional descriptions apply to agents in other domains: a startup's product team, a scientific hypothesis, a constitutional article, a theological covenant.

### The Bidirectional Architecture

Hermeneia is not a pipeline. It is a recursive knowledge engine.

```
                    PURPOSE
                      ▲
                      │
                (Teleology)
                      │
PROCESS ◄────────────► MEANING
(Causal Models)        (Interpretation)
      ▲                     ▲
      │                     │
      └────────────┬────────┘
                   │
              PERCEPTION
             (Observation)
```

Every arrow is bidirectional:
- New observations can overturn an interpretation
- A revised interpretation can change the inferred process
- A better process model can alter what purposes seem plausible
- A new understanding of purpose can send you back to re-read the observations

### The Validation

The conversation that produced this architecture executed the same learning loop it extracted:

```
Rough mental model ("find the metaphors")
↓ gathered observations
↓ generated hypotheses
↓ encountered contradictions
↓ revised the model
↓ ended with a more general architecture
```

The methodology validated itself by being applied to itself. That recursive result is the strongest evidence that the loop is real and portable.

### Hermeneia's New Description

Not: Document Interpreter
Not: Essay Generator
Not: Literary Analysis System

**Algorithm Discovery Engine** — a system that extracts the computational processes embedded in documents, tests those processes against evidence, and compares how different interpretive frameworks expose different aspects of the same underlying computation.

Documents become programs. Stories become simulations. Characters become agents. Themes become state variables. Plots become execution traces. Meaning becomes emergent behavior.

### What the Current Architecture Already Supports

- Layer 1 (Perception): Observations — fully implemented
- Layer 2 (Meaning): Interpretations, Blueprint — fully implemented
- Layer 3 (Process): Causal graph extraction via incremental Bayesian execution — not yet formalized, but the architecture has the right slots (Perspective + Blueprint can encode process models)
- Layer 4 (Purpose): Teleological hypothesis — entirely new territory, not yet modeled

### The Portable Primitive

The learning loop is the primitive:
```
Observation → Interpretation → Prediction → Behavior → Reality → Prediction Error → Revision
```

Gatsby: Revision blocked → tragedy
Nick: Revision executes → reliable narrator
Scientific discovery: Revision executes → progress
Business strategy: Revision blocked → disruption
Therapy: Revision executes → growth
Machine learning: Revision executes → generalization

Same graph. Different domains. Hermeneia is the engine that extracts and compares instantiations of it.

---

## Methodological Breakthrough vs. Research Hypotheses: A Critical Separation (2026-06-24)

### The Separation

The deep Gatsby execution produced two distinct kinds of outputs that must not be treated the same.

**Methodological breakthrough (implementable now):**
Ask what computational role something plays before asking what it means.

```
Old question: What does the green light mean?
New question: What latent variable is the green light implementing?
             What would be lost if it were removed?
             What other representations carry the same load?
```

This changes the Architect's prompt, not the schema. It produces functional descriptions rather than symbolic interpretations — findings into the same `interpretations` table, same `evidential_status` field, higher explanatory value.

**Research hypotheses (require empirical testing):**
- Characters as parameterized cognitive agents with inferred revision rates, identity attachment, etc.
- Novels as compressed world models where metaphors behave as efficient encodings of latent variables
- Computational kernels: minimal simulations that still produce the world (Gatsby kernel candidate: "Agent constructs identity around an interpretation of the past; reality contradicts it; agent cannot revise without losing the identity; tragedy follows")
- Cross-domain recurrence of the same latent variables and kernel structures

Each of these is a research hypothesis, not an established result. Correct treatment:

```yaml
candidate_kernel:
  statement: "Agent constructs identity around interpretation of past..."
  confidence: low
  supporting_evidence: [gatsby_execution_001]
  competing_kernels: []
  counter_evidence: []
  empirical_program: run full pipeline on Crime and Punishment, Don Quixote, Genesis, Federalist Papers
```

### The New Analytical Distinction

There is a difference between reconstructing:
- *What this text is saying* — interpretation (Layer 2)
- *What model best explains why this text has the structure it has* — explanatory model (Layer 3+)

These are not identical questions. Multiple explanatory models may fit the same interpretive evidence. Hermeneia should allow explanatory models to compete rather than assuming one is final.

### Representation Independence (implementable now)

Key finding from counterfactual testing: the green light can be replaced by a mountain, a star, a distant house, and the story survives. What cannot be replaced is *distance* — the underlying latent variable.

This gives a testable operation:
```
Concrete representation → Abstract function → Structural variable

Green Light → Deferred Fulfillment → Prediction
Boats → Resistance → Reality Feedback
Ashes → Decay → Consequence/Entropy
Daisy's Voice → Status Signal → Identity Validation
```

Representations are interfaces. Latent variables are the ontology. The novel has redundant encodings of the same latent variables — fault tolerance in the compression.

### The Methodological Contribution (what endures)

Hermeneia's greatest contribution is not which world model it reconstructs. It is giving investigators a repeatable way to move through increasingly deeper explanatory layers while preserving the evidence trail at each transition:

- Which observations were selected
- Which interpretations were proposed
- Which explanatory models competed
- Which hypotheses were rejected
- Why one model survived over another

The interpretations will be superseded. The provenance trail that enables this audit persists.

**The constitutional discipline applies to the research program itself.** One execution of one corpus (Gatsby) is evidence, not proof. "That is a bold hypothesis, not a conclusion" — Hermeneia's own standards require treating it that way. The empirical program is: run the full pipeline on radically different corpora and see whether the same decomposition emerges without forcing it.
