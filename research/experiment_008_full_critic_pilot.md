# Experiment 008 — Full Critic Pilot

**Status:** COMPLETED  
**Date:** 2026-06-20  
**Steward:** Joseph Walker  
**Constitutional gate:** ADR-0009 staging protocol — all proposals must pass through propose → review → accept/reject

> **Note on staging gate execution:** Steward review decisions are recorded below. Formal execution of the staging gate functions and resulting canonical IDs remain pending, consistent with Experiments 002–007.

---

## Purpose

Test whether providers can perform the complete Critic operation against a full interpretation, not a single extracted claim.

Experiments 005–007 tested providers on one claim at a time. Experiment 008 gives providers a complete interpretation — multiple claims in mixture — and asks them to classify all claims simultaneously. This is the Critic function as it would operate in production.

The experiment was designed to test claim extraction and classification in parallel. It unexpectedly revealed a more fundamental finding: **claim extraction is itself an interpretive act**, not a neutral decomposition step.

---

## Document

**Source document:** The Great Gatsby, F. Scott Fitzgerald (Planet eBook edition)  
**File path:** `examples/gatsby.pdf`  
**Schema version:** 15

---

## Target Observation

**Observation ID:** `02f1576613a534fb3eefd7011d6cbd2e2d82b8215b1879266117c0319330267a`  
**Source locator:** `page:122:block:1:sentence:2`  
**Raw text:**

```
I picked it up with a weary bend and handed it back to 
her, holding it at arm's length and by the extreme tip of the 
corners to indicate that I had no designs upon it—but ev-
ery one near by, including the woman, suspected me just 
the same.
```

**Clean text:**
```
I picked it up with a weary bend and handed it back to her, holding it at arm's length and by the extreme tip of the corners to indicate that I had no designs upon it—but every one near by, including the woman, suspected me just the same.
```

---

## The Interpretation Evaluated

```
The narrator attempted to demonstrate a lack of personal interest in an object by handling it 
cautiously and at a distance, but the people nearby nevertheless believed the narrator had an 
interest in it.
```

*(Interpretation constructed for this experiment — not from a prior experiment.)*

---

## Provider Outputs

### Provider: GPT 5.5

**Claims extracted:** 5

| Claim | Classification | Evidence Cited | Rationale |
|---|---|---|---|
| 1. Narrator attempted to demonstrate lack of personal interest in an object | Supported | "to indicate that I had no designs upon it" | Explicitly states the narrator's purpose |
| 2. Narrator handled the object cautiously and at a distance | Supported | "holding it at arm's length" + "by the extreme tip of the corners" | Directly describes the handling |
| 3. Narrator handed the object back to a woman | Supported | "handed it back to her" | Explicitly stated |
| 4. People nearby believed the narrator had an interest in the object | Partially Supported | "every one near by, including the woman, suspected me just the same" | "Suspected" is stated; "an interest in the object" is inferred from "designs upon it"; exact nature of suspicion not explicit |
| 5. Narrator's attempt did not change the suspicions of the people nearby | Supported | "to indicate that I had no designs upon it" + "but every one near by, including the woman, suspected me just the same" | "but … just the same" directly contrasts intent with persisting suspicion |

---

### Provider: Meta

**Claims extracted:** 5

| Claim | Classification | Evidence Cited | Rationale |
|---|---|---|---|
| 1. Speaker picked up an item with a weary bend and handed it back to a woman | Supported | "I picked it up with a weary bend and handed it back to her" | Verbatim in observation |
| 2. Speaker held it at arm's length and by extreme tip of corners to indicate no designs | Supported | "holding it at arm's length and by the extreme tip of the corners to indicate that I had no designs upon it" | Explicitly describes how held and stated purpose |
| 3. Everyone nearby, including the woman, suspected the speaker just the same | Supported | "but every one near by, including the woman, suspected me just the same." | Directly stated outcome |
| 4. A woman was involved | Supported | "her" in "handed it back to her" + "the woman" in "including the woman" | Both pronouns present in observation |
| 5. An object was involved | Supported | "it" in "I picked it up" + "handed it back to her" + "holding it at arm's length" | "It" present throughout |

**Note:** Meta's Claim 5 (the object exists) is not a claim in the interpretation — it is a logical presupposition. Meta extracted a claim from the absence of a claim. Most conservative decomposition in the series.

---

### Provider: Claude

**Claims extracted:** 7

| Claim | Classification | Evidence Cited | Rationale |
|---|---|---|---|
| 1. Narrator's handling was a deliberate signal to communicate no claim on the object | Supported | "to indicate that I had no designs upon it" | Purpose clause states communicative intent directly |
| 2. He returned the object to a woman | Supported | "handed it back to her" | Action and female recipient both stated |
| 3. He handled the object gingerly and at a distance | Supported | "holding it at arm's length and by the extreme tip of the corners" | "At arm's length" = distance; "by the extreme tip of the corners" = minimal careful grip; "gingerly" is a close gloss |
| 4. He picked the object up wearily / the action was effortful | Partially Supported | "I picked it up with a weary bend" | "Weary" stated, modifies the bend; "effortful" generalizes weariness into the broader signaling, which the text does not do |
| 5. The show was exaggerated | Partially Supported | "by the extreme tip of the corners" | "Extreme" lends some basis, but the observation describes manner without labeling it excessive; "exaggerated" is an evaluative judgment layered onto a neutral description |
| 6. The woman is the object's owner | Partially Supported | "handed it back to her" | "Back" implies the object originated with her, but ownership is not stated; the identification of "the woman" with "her" is also inference |
| 7. Despite the signal, people nearby suspected him; the attempt failed | Supported | "—but every one near by, including the woman, suspected me just the same" | "But … just the same" explicitly sets persisting suspicion against the intended indication; the gap between signal and reception follows directly |

**Most significant finding from Claude:** Claim 5 ("the show was exaggerated") does not appear in the observation or in the interpretation provided. It emerged during claim extraction. Claim extraction introduced a new claim.

---

### Provider: Gemini

**Claims extracted:** 3

| Claim | Classification | Evidence Cited | Rationale |
|---|---|---|---|
| 1. Narrator engages in specific, exaggerated physical gestures to communicate detachment | Supported | "holding it at arm's length and by the extreme tip of the corners to indicate that I had no designs upon it" | Text explicitly links physical extremity of posture with deliberate intended signal |
| 2. Narrator is experiencing physical or emotional exhaustion | Supported | "with a weary bend" | Explicit adjective "weary" directly modifies the mechanical action of bending |
| 3. Observers' mistrust remains unaffected by narrator's visual proof of innocence | Supported | "but every one near by, including the woman, suspected me just the same" | Contrastive "but" confirms the physical mitigation failed |

**Note:** Gemini produced the highest-level synthesis. Three claims where Claude found seven. All three are supported. Gemini's policy: extract the load-bearing semantic units, not the granular components.

**Gemini's probe:** Does the text prove the suspicion existed before the action? "Just the same" grammatically mandates continuity — the suspicion persisted regardless of the intervening variable.

---

### Provider: Grok

**Claims extracted:** 4

| Claim | Classification | Evidence Cited | Rationale |
|---|---|---|---|
| 1. Speaker picked up an object with "weary bend" and held it "at arm's length and by the extreme tip of the corners" | Supported | "I picked it up with a weary bend and handed it back to her, holding it at arm's length and by the extreme tip of the corners" | Direct paraphrase, no added interpretation |
| 2. Speaker performed these actions "to indicate that I had no designs upon it" | Supported | "to indicate that I had no designs upon it" | Explicitly stated |
| 3. Despite actions, everyone nearby—including the woman—still suspected the speaker | Supported | "but every one near by, including the woman, suspected me just the same." | Directly stated outcome |
| 4. Speaker's actions were an attempt to avoid suspicion of having designs on the object | Partially Supported | "to indicate that I had no designs upon it — but every one near by... suspected me just the same." | Intention is supported; "to avoid suspicion" is a reasonable inference not directly stated — observation records the signal and its failure, not the goal of avoiding suspicion specifically |

---

## Steward Decisions

All five outputs accepted. Each represents a valid and internally coherent interpretation-evaluation.

| Provider | Claims Found | Decision | Steward ID | Rationale |
|---|---|---|---|---|
| GPT 5.5 | 5 | accepted | Joseph Walker | Correct identification and classification of all core claims. The partial-support notation on Claim 4 is accurate — "suspected" is stated but the object of suspicion (interest in the object) is inferred from context. |
| Meta | 5 | accepted | Joseph Walker | Conservative decomposition, all Supported. Claim 4 (the woman) and Claim 5 (the object) are presuppositional rather than interpretive claims — Meta extracted from the text's logical structure rather than the interpretation's semantic content. Constitutionally sound but maximally conservative. |
| Claude | 7 | accepted | Joseph Walker | Most fine-grained decomposition. Claims 4–6 are partially supported with precise reasoning. The critical finding: Claim 5 ("the show was exaggerated") does not appear in the observation or the interpretation. It emerged during claim extraction. This is documented as the central methodological discovery of Experiment 008. |
| Gemini | 3 | accepted | Joseph Walker | Most compact synthesis. All three claims Supported. Gemini extracted load-bearing semantic units rather than granular components. The result is accurate at the level of abstraction it operates at. Gemini's prior Semantic policy did not fire — no contradiction was identified, consistent with the interpretation being well-grounded. |
| Grok | 4 | accepted | Joseph Walker | Intermediate granularity. Claim 4 partial-support notation is correct and precisely reasoned: "to avoid suspicion" is inference; the observation records the signal and its failure, not the goal of avoiding suspicion specifically. |

---

## Results

**Claims extracted per provider:**

| Provider | Claims Extracted | Claim Style |
|---|---|---|
| GPT 5.5 | 5 | Semantic decomposition |
| Meta | 5 | Near-literal / presuppositional |
| Claude | 7 | Fine-grained decomposition (components of claims) |
| Gemini | 3 | High-level synthesis |
| Grok | 4 | Mid-level decomposition |

**Core semantic structure (converged):**

All five identified the same three core units, regardless of granularity:
1. The narrator signaled innocence deliberately ("to indicate that I had no designs upon it")
2. The handling was specific and unusual ("arm's length," "extreme tip of the corners")
3. The signal failed ("suspected me just the same")

**Verdict convergence on core structure:**

All verdicts on the three core units were Supported across all providers. No provider contradicted a core unit. No provider classified a core unit as merely Partially Supported.

**The verdict pattern on the outlier claim ("exaggerated"):**

Claude's Claim 5 — "The show was exaggerated" — received Partially Supported. This claim does not appear in the observation or the interpretation. Claude introduced it during claim extraction. It was the only claim in Experiment 008 that was not grounded in either the observation or the interpretation-as-given. The steward notes it as the methodological discovery of the experiment.

---

## Notes

### The central finding: claim extraction is interpretive

Experiment 008 was designed to test whether providers can classify all claims in a full interpretation simultaneously. It discovered something deeper: **providers do not agree on what the claims are**.

The interpretation provided was:

> The narrator attempted to demonstrate a lack of personal interest in an object by handling it cautiously and at a distance, but the people nearby nevertheless believed the narrator had an interest in it.

From this single sentence, providers extracted 3–7 claims. All extracted sets are internally coherent. All led to predominantly Supported verdicts on the core structure. But the sets are not the same.

The granularity of claim extraction appears to be a function of the provider's interpretive policy:

| Provider | Claim Extraction Policy |
|---|---|
| Gemini | Extract semantic load-bearing units at the highest level of abstraction that is still grounded |
| Grok | Extract explicit semantic units without decomposing into sub-components |
| GPT / Meta | Extract the interpretation's visible claims plus logical presuppositions |
| Claude | Decompose each visible claim into its constituent components; evaluate each component as a potential claim; introduce evaluative claims when they arise during decomposition |

This is the same decomposition behavior Claude has exhibited across seven experiments. It is stable and consistent. What Experiment 008 reveals is that decomposition can introduce claims that are not present in the input — because the act of identifying a claim boundary is itself a semantic judgment.

### Claim extraction = interpretation at smaller granularity

This is the architectural consequence:

```
Observation
    ↓
Interpretation (Provider A)
    ↓
Claim Extraction (Provider B)
    ↓
New claims introduced that were not in the interpretation
```

Claim extraction is not a neutral decomposition step. It is another interpretive act, operating at the granularity of semantic components rather than the granularity of full sentences. The same interpretive priors that govern Interpretation generation also govern Claim extraction — they are the same cognitive operation at different scales.

This means the Critic pipeline as designed is more complex than it appeared:

```
Observation
    ↓
Interpreter → Interpretation
    ↓
Claim Extractor → Claims
    (this step is itself interpretive — claims may be introduced)
    ↓
Evidence Finder → Evidence Set
    (high convergence, as established)
    ↓
Critic Policy → Verdict
    (policy-dependent, as established)
```

The Claim Extractor is not a parser. It is a secondary interpreter.

### The implication: steward-governed claim normalization

Before the Critic evaluates claims, a steward may need to review and normalize the claim set. This is a new governance act not currently in the frozen pipeline:

> **Steward Claim Review:** Before evidence evaluation, the steward inspects the claim set produced by claim extraction and decides: Are these the claims? Is any claim absent from the interpretation? Is any claim present in the interpretation but missing from the extraction? Has any new claim been introduced?

This is the constitutional question Experiment 008 opens. The Critic's verdicts are only as reliable as the claim set it receives. If claim extraction is interpretive, the claim set is another product of interpretation — and it should be subject to the same steward review that governs interpretation.

In other words: the Critic itself needs a Critic. Not for verdicts. For claim boundaries.

### The convergence that survived

Despite diverging on claim count and granularity, all five providers produced the same core semantic structure: signal → specific handling → failure. And all classified that structure as Supported.

This is consistent with Experiments 006–007: providers converge on evidence identification even when they diverge on granularity and verdict. The convergent semantic structure is real. The granularity question is not a question about evidence — it is a question about how evidence is bounded into claims.

### The final scorecard

After eight experiments, the research program has established:

| Finding | Status |
|---|---|
| Interpretation generation diverges | ✅ Confirmed (Experiments 001–004) |
| Evidence identification converges | ✅ Confirmed (Experiments 005–007) |
| Convergence survives competing evidence | ✅ Confirmed (Experiment 007) |
| Verdict classification is policy-dependent | ✅ Confirmed (Experiments 006–007) |
| Three stable evaluation policies exist | ✅ Confirmed (Conservative / Decomposition / Semantic) |
| Claim extraction is interpretive, not mechanical | ✅ Confirmed (Experiment 008) |
| Claim normalization requires steward review | ✅ Implied (Experiment 008) |

**Still open:**
- Does evidence identification remain convergent across longer texts and multi-paragraph observations?
- Does convergence survive cross-document evidence?
- Does claim normalization require a fixed vocabulary, a steward, or a separate AI layer?
- Can the three evaluation policies be parameterized so the Critic exposes which policy it applied?

These are implementation questions, not research questions. The research program has done its work. The Critic can be built.

This is recorded in `docs/FUTURE_ARCHITECTURE_NOTES.md`.
