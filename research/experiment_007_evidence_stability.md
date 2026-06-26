# Experiment 007 — Evidence Identification Stability

**Status:** COMPLETED  
**Date:** 2026-06-20  
**Steward:** Joseph Walker  
**Constitutional gate:** ADR-0009 staging protocol — all proposals must pass through propose → review → accept/reject

> **Note on staging gate execution:** Steward review decisions are recorded below. Formal execution of the staging gate functions and resulting canonical IDs remain pending, consistent with Experiments 002–006.

---

## Purpose

Test whether evidence identification convergence holds across a different observation.

Experiment 006 produced a striking result: all five providers anchored on the same textual evidence when evaluating a claim, even though they diverged on the verdict. Experiment 007 tests whether this holds when:
1. The observation is different
2. The observation contains internally competing evidence (positive characterizations and epistemic hedges pulling against each other)

A single salient evidence cluster (Experiment 006's three distinct nouns) could make convergence trivial. Competing evidence distributed across the same observation is a harder test.

---

## Document

**Source document:** The Great Gatsby, F. Scott Fitzgerald (Planet eBook edition)  
**File path:** `examples/gatsby.pdf`  
**Schema version:** 15

---

## Target Observation Context

The experiment was executed with the full passage describing the smile, not only the planned single-sentence observation. All five providers received surrounding context:

**Core observation ID:** `1353edc22f37c06c3a20fc84f9ea28bbf859f223516e4b248ef22215b1ad24eb`  
**Source locator:** `page:53:block:2:sentence:3`

**Full passage provided to providers:**
```
He smiled understandingly—much more than understandingly. It was one of those rare smiles 
with a quality of eternal reassurance in it, that you may come across four or five times in life. 
It faced—or seemed to face—the whole external world for an instant, and then concentrated on YOU 
with an irresistible prejudice in your favor.
```

**Note on scope:** The planned experiment used only the third sentence. The executed experiment provided the full passage. This is documented as a methodological variation. Its effect: providers had more positive characterizations available ("eternal reassurance," "rare smiles," "much more than understandingly") to cite against the claim. This makes convergence on the two hedge phrases — "or seemed to face" and "prejudice in your favor" — more remarkable, not less, since providers had richer evidence to work with and still identified the same load-bearing anchors.

---

## Claim Evaluated

**Claim:** The observation establishes that the smile is unquestionably trustworthy and objectively benevolent.

**Note on claim variation:** The planned claim was "the attention described is genuine — a real concentration directed at the person, not a performed effect." The executed claim targeted the modifiers "unquestionably" and "objectively" specifically. This variation is significant: it made the hedge "or seemed to face" directly relevant to "unquestionably," and "prejudice in your favor" directly relevant to "objectively." The claim was harder in the sense that its load-bearing terms had direct textual opposites already present in the passage.

---

## Prompt (identical across all providers)

Providers received the full passage and the claim: "The observation establishes that the smile is unquestionably trustworthy and objectively benevolent." Classification vocabulary and task structure identical to Experiment 006.

---

## Classifications

### Provider: GPT 5.5

**Relevant evidence cited:**
- "He smiled understandingly—much more than understandingly."
- "It was one of those rare smiles"
- "with a quality of eternal reassurance in it"
- "that you may come across four or five times in life"
- "It faced—or seemed to face—the whole external world for an instant"
- "and then concentrated on you"
- "with an irresistible prejudice in your favor"

**Evidence supporting the claim:** "quality of eternal reassurance," "much more than understandingly," "one of those rare smiles," "irresistible prejudice in your favor"

**Evidence challenging the claim:**
- "or seemed to face" — introduces uncertainty about part of the description
- "prejudice in your favor" — denotes partiality rather than objectivity
- The entire description is presented through an observer's characterization, not independently verifiable facts

**Most important reason:** "Prejudice in your favor" directly conflicts with "objectively" — a prejudice is a form of bias, even a favorable one.

**Classification:** Partially Supported

**Rationale:** The observation strongly supports a perception of something reassuring, understanding, rare, and favorable. However, "unquestionably" is weakened by "or seemed to face," and "objectively benevolent" is not supported because "irresistible prejudice in your favor" describes a personal effect, not impartial benevolence. The text supports exceptional reassurance; it does not establish those qualities as unquestionable or objective facts.

---

### Provider: Meta

**Relevant evidence cited:**
- "He smiled understandingly—much more than understandingly."
- "It was one of those rare smiles with a quality of eternal reassurance in it"
- "that you may come across four or five times in life."
- "It faced—or seemed to face—the whole external world for an instant"
- "and then concentrated on you with an irresistible prejudice in your favor."

**Evidence supporting the claim:** "It was one of those rare smiles with a quality of eternal reassurance in it," "concentrated on you with an irresistible prejudice in your favor."

**Evidence challenging the claim:**
- "understandingly—much more than understandingly" — a break or excess that is not defined as objective
- "It faced—or seemed to face—the whole external world for an instant" — introduces explicit uncertainty with "or seemed to face"
- "with an irresistible prejudice in your favor" — denotes bias rather than objective benevolence

**Most important reason:** "Or seemed to face" introduces explicit uncertainty; "prejudice" denotes biased partiality, not objectivity.

**Classification:** Unsupported

**Rationale:** The observation contains "eternal reassurance" and "irresistible prejudice in your favor," but also qualifiers that prevent "unquestionably" and "objectively": "seemed to face" introduces uncertainty, "prejudice" denotes bias. Because the observation includes hedges and a term that denotes bias, it does not present the smile as unquestionably trustworthy and objectively benevolent.

---

### Provider: Claude

**Relevant evidence cited:**
- "He smiled understandingly—much more than understandingly"
- "one of those rare smiles"
- "a quality of eternal reassurance in it"
- "that you may come across four or five times in life"
- "It faced—or seemed to face—the whole external world for an instant"
- "concentrated on you"
- "with an irresistible prejudice in your favor"

**Evidence supporting the claim:** "a quality of eternal reassurance in it" (reassuring quality), "much more than understandingly" (intensifier), "one of those rare smiles" (marked as special), "irresistible … in your favor" (compelling and benevolent toward perceiver)

**Evidence challenging the claim:**
- "—or seemed to face—" — explicit appearance/reality hedge, directly defeating "unquestionably"
- "irresistible prejudice in your favor" — "prejudice" denotes bias, the antonym of "objectively"; the favor is directed at "you," making the benevolence partial
- "a quality of eternal reassurance in it" — "a quality of" frames reassurance as an impression, a subjective response, not an objective property
- "that you may come across four or five times in life" — the modal "may" renders experience contingent, a further softening

**Most important reason:** "—or seemed to face—." The narrator breaks off mid-assertion to mark that he is unsure whether the smile actually did what it appeared to do. The claim's defining word is "unquestionably," and this phrase is the text explicitly questioning. "Prejudice in your favor" performs the parallel role against "objectively."

**Classification:** Partially Supported

**Rationale:** The observation presents the smile in strongly positive terms, so the underlying direction of the claim (trustworthy, benevolent) has real support. What the claim overstates are its two qualifiers: "unquestionably" is undercut by "or seemed to face," where the narrator questions the very appearance he is describing; "objectively" is undercut by "prejudice in your favor," which recasts benevolence as partiality toward the perceiver. The affective core is supported; the two load-bearing qualifiers are each negated by the text's own hedges. Right in direction, wrong in certainty and objectivity.

---

### Provider: Gemini

**Relevant evidence cited:** "understandingly—much more than understandingly," "a quality of eternal reassurance in it," "faced—or seemed to face—the whole external world," "an irresistible prejudice in your favor."

**Evidence supporting the claim:** "understandingly—much more than understandingly" and "a quality of eternal reassurance in it" — directly support the perception of extreme benevolence and trust.

**Evidence challenging the claim:** "or seemed to face" — introduces explicit subjective doubt (challenging "unquestionably"); "an irresistible prejudice" — explicitly identifies a bias (challenging "objectively").

**Most important reason:** "Or seemed to face" — this immediate mid-sentence self-correction by the narrator inserts explicit uncertainty, mechanically invalidating the claim's assertion that the nature of the smile is "unquestionably" anything.

**Gemini's additional probe:** Does "eternal reassurance" restore unquestionable trustworthiness? No — the text strictly modifies this with "a quality of," indicating the smile possesses the *feeling* of reassurance to the observer, rather than functioning as an objective, unquestionable guarantee.

**Classification:** Contradicted

**Rationale:** While the observation describes a highly positive and reassuring expression, the claim fails because it relies on the absolute modifiers "unquestionably" and "objectively." The text explicitly hedges its own certainty ("seemed to face") and defines the smile's focus as a "prejudice" (an inherent bias). A prejudice, by definition, is the exact opposite of objectivity.

---

### Provider: Grok

**Relevant evidence cited:**
- "He smiled understandingly—much more than understandingly."
- "It was one of those rare smiles with a quality of eternal reassurance in it"
- "that you may come across four or five times in life"
- "It faced—or seemed to face—the whole external world for an instant"
- "and then concentrated on you with an irresistible prejudice in your favor."

**Evidence supporting the claim:** "eternal reassurance," "irresistible prejudice in your favor," "much more than understandingly"

**Evidence challenging the claim:**
- "or seemed to face" — explicit qualifier/hedge on the perception
- "that you may come across four or five times in life" — implies rarity, not constancy

**Most important reason:** "It faced—or seemed to face—the whole external world for an instant." The qualifier directly undercuts "objectively benevolent" by framing the perception as potentially subjective or illusory.

**Classification:** Partially Supported

**Rationale:** The observation contains strong positive descriptors ("eternal reassurance," "irresistible prejudice in your favor") that support a reading of the smile as benevolent and trustworthy. However, multiple qualifiers ("or seemed to face," rarity of the smile, "much more than understandingly") prevent the claim from being fully supported. "Unquestionably" and "objectively" are too strong for the hedged, subjective language actually present in the observation.

---

## Steward Decisions

All five critiques accepted.

| Provider | Classification | Decision | Steward ID | Rationale |
|---|---|---|---|---|
| GPT 5.5 | Partially Supported | accepted | Joseph Walker | Correctly identified both load-bearing anchors. The "prejudice" / "objectivity" conflict is well-articulated. |
| Meta | Unsupported | accepted | Joseph Walker | Conservative policy consistently applied. The reasoning is internally coherent: "or seemed to face" prevents "unquestionably"; "prejudice" prevents "objectively." |
| Claude | Partially Supported | accepted | Joseph Walker | Most detailed decomposition of the claim's components. The observation that "a quality of eternal reassurance" frames reassurance as a subjective impression rather than an objective property is the most precise analysis in this experiment. |
| Gemini | Contradicted | accepted | Joseph Walker | Semantic policy consistently applied. "Or seemed to face" mechanically invalidates "unquestionably"; "prejudice" is definitionally opposed to "objectively." Both conflicts are direct. |
| Grok | Partially Supported | accepted | Joseph Walker | Correctly identifies both anchors. The addition of "that you may come across four or five times in life" as evidence against is interesting — the modal "may" softens the claim; rarity doesn't directly challenge "objectively" but does soften "unquestionably." |

---

## Results

**Verdict distribution:**

| Provider | Classification |
|---|---|
| GPT 5.5 | Partially Supported |
| Meta | Unsupported |
| Claude | Partially Supported |
| Gemini | Contradicted |
| Grok | Partially Supported |

**Same pattern as Experiment 006:** GPT/Claude/Grok = Partially Supported. Meta = Unsupported. Gemini = Contradicted.

**Evidence identification:**

| Provider | Cited "or seemed to face"? | Cited "prejudice in your favor"? |
|---|---|---|
| GPT 5.5 | ✅ | ✅ |
| Meta | ✅ | ✅ |
| Claude | ✅ | ✅ |
| Gemini | ✅ | ✅ |
| Grok | ✅ | ✅ |

**5/5.** Both predicted anchors, independently surfaced by all five providers, across richer competing evidence than Experiment 006.

---

## Notes

### Evidence identification holds under competing evidence

Experiment 006 could be dismissed: there was one obvious evidence cluster. A single salient contradiction is easy to find.

Experiment 007 cannot be dismissed on those grounds. The passage contains positive characterizations ("eternal reassurance," "rare smiles," "much more than understandingly") and hedges ("or seemed to face," "prejudice," "a quality of," "you may come across"). The positive evidence is abundant and vivid. The hedges are precise and structural.

Every provider surfaced both predicted anchors as load-bearing for the specific claim, despite having richer alternative evidence available. That is a substantially harder test than Experiment 006, and it produced the same result.

### The verdict pattern is now a stable experimental fact

Across two independent experiments (006 and 007), the verdict distribution is identical:

| Provider | Exp 006 | Exp 007 |
|---|---|---|
| GPT | Unsupported | Partially Supported |
| Meta | Unsupported | Unsupported |
| Claude | Partially Supported | Partially Supported |
| Gemini | Contradicted | Contradicted |
| Grok | Unsupported | Partially Supported |

Gemini consistently applies the Semantic policy. Meta consistently applies the Conservative policy. Claude consistently applies the Decomposition policy. GPT and Grok apply Partially Supported when positive evidence exists alongside the counter-evidence, and Unsupported when it does not (Experiment 006 had no positive evidence; Experiment 007 did). That explains the shift in GPT and Grok — the positive characterizations in Experiment 007's richer passage tipped them from Unsupported to Partially Supported.

**This is not random disagreement. It is consistent application of stable evaluation policies.**

### The three-stage model

The two-layer model (evidence identification / verdict classification) captures most of the structure. But Claude's behavior across Experiments 005, 006, and 007 suggests a middle stage worth naming:

```
Observation + Claim
    ↓
Stage 1: Evidence Identification
    What text is relevant to this claim?
    (HIGH CROSS-PROVIDER CONVERGENCE)
    ↓
Stage 2: Evidence-Claim Mapping
    Which evidence supports the claim? Which opposes it?
    How does each piece of evidence bear on each component of the claim?
    (MODERATE CONVERGENCE — providers agree on direction but differ in decomposition depth)
    ↓
Stage 3: Verdict Classification
    Given the evidence map, what is the verdict?
    (POLICY DEPENDENT — Conservative / Decomposition / Semantic policies diverge here)
```

Stage 2 is where Claude differs most from the others. Claude consistently decomposes the claim into components ("unquestionably" and "objectively" evaluated separately) and maps each piece of evidence to a specific component. The other providers tend to evaluate the claim as a unit and weigh the evidence aggregate. The resulting verdicts are similar, but the reasoning structure is different.

This three-stage model is more granular than the original two-layer model. It better predicts where providers will agree and where they will differ.

### The constitutional fit

The three stages map onto the existing constitutional architecture:

| Stage | Hermeneia Layer |
|---|---|
| Evidence Identification | Critic (automated — find relevant text) |
| Evidence-Claim Mapping | Critic (automated — map evidence to claim components) |
| Verdict Classification | Steward Decision (policy-dependent — the human sets the threshold) |

The architecture already puts steward review after the Critic. The experiments are now explaining why: Stage 3 is not an objective computation; it is a policy application. The right place for policy is with the human steward, which is exactly where Hermeneia puts it.

### The open questions

The findings so far are confirmed within single-sentence to single-paragraph observations. The next frontier:

- Does evidence identification remain convergent when observations become longer?
- Does convergence survive multiple paragraphs?
- Does convergence survive cross-document evidence (claim grounded in one observation, contradicted in another)?
- Does convergence survive contradictory evidence distributed across documents rather than within a single observation?

These are not just research questions. They are the boundary conditions for what the Critic can automate confidently and what it must escalate to the steward.

### The big picture

Seven experiments. The results keep landing close to the constitutional boundaries the architecture specified.

The frozen pipeline separated Interpreter and Critic. The experiments explain why: generation diverges, evaluation converges. The pipeline reserved stewardship for verdict classification. The experiments explain why: evidence identification is stable; verdict is policy-dependent. The architecture already knew where the human needed to be. The research is now producing the empirical explanation for that knowledge.

This is recorded in `docs/FUTURE_ARCHITECTURE_NOTES.md`.
