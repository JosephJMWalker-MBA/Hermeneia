# Performance Manuscript — Future Convergence Note

**Status:** Historical convergence hypothesis; one seam activated  
**Captured:** 2026-09-27  
**Activated seam:** human-attention bridge  
**Current rule:** Repositories, canonical ontologies, and execution pipelines remain independent. The bounded observation ↔ attention handoff is now an active integration experiment.

The active bridge specification is [`performance-manuscript-human-attention-bridge.md`](performance-manuscript-human-attention-bridge.md). This note remains the broader convergence record.

## Working hypothesis

Hermeneia's Reader-centered environment and Performance Manuscript's governed audiobook-production pipeline appear to have a natural future convergence around a simple interaction:

> **Write, read, analyze, and listen as one continuous practice.**

A future user may be able to write a manuscript while continuously hearing the current performance projection, or analyze a source while generating governed audio explanations, Perspective dialogues, or a living podcast from the evolving investigation.

The audio layer should remain a projection over preserved source and governed interpretation state rather than becoming a competing source of truth.

## Potential experience

~~~text
READ / WRITE
    ↓
notice / question / revise
    ↓
steward current text or understanding
    ↓
performance / audio projection
    ↓
LISTEN
    ↓
notice rhythm, ambiguity, pacing, attribution, or new questions
    ↺
~~~

For authored work, this may allow an audiobook to grow alongside the manuscript.

For analytical work, it may allow the investigation to produce evolving narrated or conversational audio without collapsing source, interpretation, and expression.

## Architectural fit

Hermeneia already preserves distinctions such as:

~~~text
source
!= machine proposal
!= human notice
!= stewarded understanding
!= expression
~~~

Performance Manuscript preserves neighboring distinctions such as:

~~~text
manuscript
!= speaker attribution
!= cast
!= performance direction
!= render
!= QC
!= packaged audiobook
~~~

These are compatible in spirit because both systems treat generated outputs as derived, inspectable artifacts rather than as authority merely because they were generated.

## Future surfaces

Possible integration surfaces include:

- listen to a draft while editing it;
- selective audio regeneration after a manuscript revision;
- proof listening inside the Reader/workbench;
- author observations captured while listening;
- audiobook build state visible alongside manuscript state;
- audio renderings of interpretations or Perspectives;
- living podcast projections from an evolving investigation;
- switching among source reading, authored prose, analytical explanation, and performance while retaining lineage;
- using audio as a comprehension and revision instrument, not only a publication format.

## Non-negotiable boundaries

A combined system must not collapse:

~~~text
evidence
interpretation
authored text
performance plan
voice/cast choice
rendered audio
human listening observation
publication authority
~~~

A listener deciding that a passage sounds wrong is valuable evidence for revision. It is not itself a text revision until a steward/author makes one.

A generated podcast may express the current investigation. It does not become the investigation record.

An audiobook render may reveal an attribution problem. It does not silently repair the manuscript.

## What remains deferred

The broader systems should not be joined merely because one integration seam has become useful.

Independent development currently has higher research value:

- Hermeneia can prove whether its Reader-centered inquiry/writing environment works without leaning on an audiobook product.
- Performance Manuscript can prove whether its governed production pipeline reduces audiobook labor without leaning on Hermeneia.
- Failures remain attributable to the project that owns them.
- Schemas and ontologies are less likely to be distorted around premature integration.

The sequence has now advanced one step:

~~~text
Hermeneia works independently
+
Performance Manuscript works independently
↓
define explicit handoff contract          ← active now
↓
test combined proofreading/listening workflow
↓
integrate only what measurably improves the work
~~~

## Current decision

Preserve the broader convergence as a future product/architecture direction, while actively testing the narrow human-attention bridge.

Do **not** merge repositories, ontologies, or execution pipelines.

The currently authorized bridge is explicit sidecar exchange between Performance Manuscript machine observations and Hermeneia human-attention events, with a Reader-first path toward proof-listening, touch highlighting, and voice annotation. Broader write/read/listen, living-podcast, and continuous-audiobook convergence remains deferred until the bounded bridge earns it through real use.
