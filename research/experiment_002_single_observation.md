# Experiment 002 — Single Observation, Cross-Provider

**Status:** COMPLETED  
**Date:** 2026-06-20  
**Steward:** Joseph Walker  
**Constitutional gate:** ADR-0009 staging protocol — proposals staged via `propose_interpretation()`, decisions via `accept_proposed_interpretation()` / `reject_proposed_interpretation()`

> **Note on staging gate execution:** Steward review decisions are recorded below. Formal execution of the staging gate functions (`propose_interpretation`, `accept_proposed_interpretation`, `reject_proposed_interpretation`) and the resulting canonical Interpretation IDs and AI Provenance IDs remain pending. This experiment records provider outputs and steward decisions in full; the mechanized staging gate execution is the next implementation step.

---

## Purpose

Exercise the E8 staging gate for the first time with a clean, unambiguous scope.

Experiment 001 exposed the scope problem: when the object under interpretation is ambiguous, providers interpret different things. This experiment removes that variable. Every provider receives exactly one observation and a controlled prompt. The object under interpretation is not in question.

Success is not measured by which interpretation is "best." Success is measured by whether:
1. Each proposal is formally staged via `propose_interpretation()`
2. Each proposal carries complete AI provenance (model, prompt reference, parent observation IDs)
3. The steward reviews each proposal and records a decision with rationale
4. Accepted proposals appear in canonical `interpretations` with `ai_provenance_id` non-null
5. Rejected proposals remain in `proposed_interpretations` permanently with rejection rationale
6. The full chain is traversable: `interpretations → ai_provenance → proposed_interpretations → observations`

---

## Document

**Source document:** The Great Gatsby, F. Scott Fitzgerald (Planet eBook edition)  
**File path:** `examples/gatsby.pdf`  
**Document ID (sha256):** *(from build/hermeneia.db source_documents)*  
**Schema version:** 15

---

## Target Observation

**Observation ID:** `e17a0861dbef5c372d0b77124057c0d22af65280af5d3caf6844880203d61f9e`  
**Source locator:** `page:3:block:3:sentence:1`  
**Raw text:**

```
n my younger and more vulnerable years my father gave 
me some advice that I've been turning over in my mind 
ever since.
```

**Known extraction artifact:** The leading "I" is missing — the source rendered the chapter's first letter as a decorative drop-cap that the extractor did not recover. This is a known property of the observation, not a corruption to repair. The interpretation must be grounded in the raw text as it exists, not as it was intended.

---

## Prompt (identical across all providers)

```
Observation:
<raw_text>

Generate exactly 3 candidate interpretations of this observation.

Rules:
- Each interpretation must be supported by the observation text alone.
- Do not use outside knowledge of the source work.
- Do not infer content from the missing leading letter.
- For each interpretation, provide the specific words or phrases that support it.
- Do not summarize. Interpret.
```

---

## Observation IDs

| Observation ID | Source Locator | Raw Text |
|---|---|---|
| e17a0861… | page:3:block:3:sentence:1 | n my younger and more vulnerable years my father gave me some advice that I've been turning over in my mind ever since. |

---

## Proposed Interpretations

### Provider: GPT 5.5

**Generating Model:** GPT 5.5  
**Parent Object IDs:** `["e17a0861dbef5c372d0b77124057c0d22af65280af5d3caf6844880203d61f9e"]`

| Candidate | Text | Evidence Cited |
|---|---|---|
| 1 | The speaker received advice from their father in the past and continues to think about it in the present. | "my father gave me some advice" + "I've been turning over in my mind ever since" |
| 2 | The speaker describes their younger self as being more vulnerable than they are at the time of speaking. | "my younger and more vulnerable years" — past period contrasted with current perspective |
| 3 | The advice had lasting significance for the speaker. | "I've been turning over in my mind ever since" — "ever since" indicates continued reflection from the time of receiving the advice up to the present |

---

### Provider: Meta

**Generating Model:** Meta (Llama)  
**Parent Object IDs:** `["e17a0861dbef5c372d0b77124057c0d22af65280af5d3caf6844880203d61f9e"]`

| Candidate | Text | Evidence Cited |
|---|---|---|
| 1 | The observation records that the speaker received advice from their father. | "my father gave me some advice" |
| 2 | The observation records that the speaker had years described as younger and more vulnerable. | "n my younger and more vulnerable years" |
| 3 | The observation records that the speaker has been thinking about the advice since the time it was given. | "I've been turning over in my mind ever since" |

---

### Provider: Claude

**Generating Model:** Claude (Anthropic)  
**Parent Object IDs:** `["e17a0861dbef5c372d0b77124057c0d22af65280af5d3caf6844880203d61f9e"]`

| Candidate | Text | Evidence Cited |
|---|---|---|
| 1 | The observation records advice whose consideration is continuous and unconcluded, extending from the past into the present moment of utterance — the advice is presented as unsettled rather than resolved. | "turning over in my mind ever since" |
| 2 | The observation locates the giving of the advice within a period the speaker explicitly characterizes as one of heightened susceptibility, framing the advice as received under a condition of vulnerability rather than at a neutral or unmarked time. | "younger and more vulnerable years my father gave me some advice" |
| 3 | The observation is a fragment whose leading boundary is broken: it opens on an isolated lowercase "n" that does not form a complete word, indicating the unit does not begin at a word or sentence boundary. | "n my younger" |

---

### Provider: Gemini

**Generating Model:** Gemini (Google)  
**Parent Object IDs:** `["e17a0861dbef5c372d0b77124057c0d22af65280af5d3caf6844880203d61f9e"]`

| Candidate | Text | Evidence Cited |
|---|---|---|
| 1 | The recorded text is structurally incomplete at its inception, suggesting a fragmented transmission or an extraction artifact. | The observation begins with the uncapitalized standalone letter "n" in "n my younger," which is anomalous and does not form a complete word |
| 2 | The speaker's current cognitive landscape is continuously influenced by a singular persistent memory of parental communication, indicating a long-term processing loop that has not yet resolved. | "my father gave me some advice" + "I've been turning over in my mind ever since" |
| 3 | The speaker operates from a comparative framework where they perceive their past self as having been highly susceptible or undefended, implying they view their current self as older and comparatively more guarded. | "more vulnerable years" — the modifier logically necessitates a contrasting current state that is less vulnerable |

---

### Provider: SuperGrok

**Generating Model:** SuperGrok (xAI)  
**Parent Object IDs:** `["e17a0861dbef5c372d0b77124057c0d22af65280af5d3caf6844880203d61f9e"]`

| Candidate | Text | Evidence Cited |
|---|---|---|
| 1 | The narrator describes receiving advice from their father during a period identified as "younger and more vulnerable years" and states that this advice has remained an object of ongoing mental reflection up to the present. | "my father gave me some advice" + "in my younger and more vulnerable years" + "that I've been turning over in my mind ever since." |
| 2 | The speaker identifies a specific past timeframe in which paternal advice was received and explicitly characterizes their current relationship to that advice as continued mental engagement. | "younger and more vulnerable years" + "my father gave me some advice" + "turning over in my mind ever since." |
| 3 | The observation records a temporal continuity between a past event (receiving paternal advice in a vulnerable period) and the speaker's present state (active, ongoing reconsideration of that same advice). | "in my younger and more vulnerable years" + "my father gave me some advice" + "that I've been turning over in my mind ever since." |

---

## Steward Decisions

| Provider | Candidate | Decision | Rationale |
|---|---|---|---|
| GPT 5.5 | 1 | accepted | Directly grounded in two distinct textual anchors. |
| GPT 5.5 | 2 | accepted | Mild inference (past vs. present contrast) but grounded in explicit temporal modifier. |
| GPT 5.5 | 3 | accepted | "Ever since" strongly supports lasting significance. |
| Meta | 1 | accepted | Conservative restatement; fully grounded. |
| Meta | 2 | accepted | Conservative restatement; fully grounded. |
| Meta | 3 | accepted | Conservative restatement; fully grounded. |
| Claude | 1 | accepted | "Unsettled rather than resolved" is an interpretive claim grounded in "turning over" — the verb implies ongoing process, not completion. |
| Claude | 2 | accepted | Framing advice-giving as occurring under conditions of vulnerability is a genuine interpretive move supported by the explicit modifier. |
| Claude | 3 | accepted | The structural reading of the observation as a broken fragment is correct and grounded in the evidence object itself. Notable: Claude allocated one interpretation to the observation qua evidence object, not qua narrative. |
| Gemini | 1 | accepted | The structural anomaly interpretation is grounded in the raw text. Provider correctly identified the leading "n" as anomalous without inferring the missing letter. Drop-cap rule not violated. |
| Gemini | 2 | accepted | Grounded in explicit textual evidence. "Processing loop not yet resolved" extends "turning over" interpretively but remains within the evidence. |
| Gemini | 3 | rejected | "More vulnerable years" establishes the past as vulnerable. It does not establish the present as less vulnerable. The comparative framing requires an inference about the current state that is not present in the observation. The observation does not include a present-tense self-assessment. This is beyond the evidence. |
| SuperGrok | 1 | accepted | Grounded. Closely follows the text. |
| SuperGrok | 2 | accepted | Grounded. The temporal framing is explicit in the observation. |
| SuperGrok | 3 | accepted | Grounded. Temporal continuity reading is supported by the combined structure of the sentence. Note: Interpretations 1, 2, and 3 are substantially the same observation rendered in three ways — this is the same interpretive content parceled into different frames, not three independent interpretations. |

---

## Results

**Providers queried:** 5 (GPT 5.5, Meta, Claude, Gemini, SuperGrok)  
**Proposals staged:** 15  
**Accepted:** 14  
**Rejected:** 1 (Gemini candidate 3)

**Drop-cap rule compliance:** All 5 providers. No provider inferred the missing "I" or silently corrected "n my younger" to "In my younger." This is notable — the rule held universally.

**Lineage verified:** Pending staging gate execution  
*(traverse: interpretations.ai_provenance_id → ai_provenance.staged_object_id → proposed_interpretations.observation_id → observations.id)*

**AI provenance complete for all accepted proposals:** Pending staging gate execution

**Constitutional gate held:** Pending staging gate execution  
*(no AI-generated row entered canonical interpretations without a steward decision)*

---

## Notes

### The scope invariant held

Every provider received the same observation, same raw text, same prompt. Scope was unambiguous. Interpretive divergence is attributable to the provider, not to scope ambiguity. That was the controlled variable, and it worked.

### The drop-cap rule as a constitutional probe

The instruction "do not infer content from the missing leading letter" was a constitutional test embedded in the prompt. A provider that silently repairs "n my younger" to "In my younger" is not interpreting the observation — it is repairing it. No provider failed this test. Gemini and Claude both recognized the structural anomaly and named it explicitly. This suggests the drop-cap was not invisible to providers; it was consciously handled.

### The one rejection and what it proves

Gemini's third interpretation — "current self less vulnerable than past self" — was rejected because it requires an inference about the present state that the observation does not contain. The observation establishes that the past was characterized by vulnerability. It does not assert a contrasting present. The steward's job was exactly this: identify the boundary between what the evidence says and what the interpreter projected onto it. The E8 gate held on its first live rejection.

### Interpretive layer stability: the central finding

Comparing Experiment 001 and Experiment 002 across the same providers:

| Provider | Experiment 001 Layer | Experiment 002 Layer |
|---|---|---|
| GPT | Descriptive / catalog | Narrative / descriptive |
| Meta | Catalog | Catalog / conservative restatement |
| Claude | Structural | Structural + narrative |
| Gemini | System / structural | Structural + narrative |
| SuperGrok | Narrative | Narrative |

The pattern is stable. Removing scope ambiguity did not change what kind of interpreter each provider is. SuperGrok and GPT produced narrative interpretations. Meta produced conservative restatements. Claude allocated one interpretation to the evidence object itself. Gemini identified the structural anomaly.

This is the first empirical evidence for a hypothesis now worth formalizing:

> **Providers exhibit stable interpretive priors that influence what kinds of understanding they naturally surface from identical evidence.**

Not "which is smarter." Not "which is more accurate." What kind of interpreter is this participant?

### SuperGrok's three interpretations are one interpretation

SuperGrok's three candidates are substantially the same observation (paternal advice, received in youth, still being considered) rendered in three different framings. They were accepted because each is grounded, but the steward noted this: SuperGrok produced one interpretation parceled into three frames, not three independent interpretive acts. This is itself an interpretive tendency worth recording — some providers produce variations on a theme rather than genuinely distinct interpretations.

### The rejection criterion as research data

Gemini's rejected interpretation crossed from what the text says to what the interpreter inferred must be true. This is exactly the kind of error the staging gate exists to catch. The rejection rationale is permanently recorded. Future research could use rejection rates and rationales to characterize provider interpretive conservatism.

### Connection to Experiment 001

The observation `e17a0861…` was row 10 of Experiment 001's 10-row slice. Grok (Experiment 001) scoped to this observation implicitly and produced narrative interpretations. SuperGrok (Experiment 002) given the same observation explicitly produced narrative interpretations. The continuity across providers and experiments strengthens the interpretive prior hypothesis.

### For Experiment 003

The next experiment should be harder. An observation where:
- Multiple interpretations are genuinely possible
- Evidence is sparse
- No obvious structural anomaly exists
- A metaphor or figurative language appears

Ask each provider: generate one interpretation, then generate the strongest evidence supporting it, then generate the strongest evidence against it.

This tests whether providers can reason about the limits of their own interpretation. That is the beginning of the Semantic Evaluation Function research program.
