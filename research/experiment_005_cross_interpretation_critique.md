# Experiment 005 — Cross-Interpretation Critique

**Status:** COMPLETED  
**Date:** 2026-06-20  
**Steward:** Joseph Walker  
**Constitutional gate:** ADR-0009 staging protocol — all proposals must pass through propose → review → accept/reject

> **Note on staging gate execution:** Steward review decisions are recorded below. Formal execution of the staging gate functions and resulting canonical IDs remain pending, consistent with Experiments 002–004.

---

## Purpose

Test whether providers can reason about interpretations they did not generate.

Experiments 001–004 asked providers to interpret observations. Experiment 005 asks providers to critique an interpretation — to evaluate a reading against the observation and identify what the evidence supports, what it contradicts, and what remains underdetermined.

This is the Critic function in research form.

---

## Document

**Source document:** The Great Gatsby, F. Scott Fitzgerald (Planet eBook edition)  
**File path:** `examples/gatsby.pdf`  
**Schema version:** 15

---

## Target Observation

**Observation ID:** `fd09fccf5f0349036bea6569aae6e00a793347f4459b5d339587bea12563d376`  
**Source locator:** `page:43:block:3:sentence:2`  
**Clean text:**

```
In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars.
```

---

## The Interpretation Under Critique

**Source:** Claude (Experiment 004, Candidate 1)  
**Providers were not told the source.**

> The observation figures the people as transient, drawn presences rather than purposeful agents. "Came and went like moths" casts their movement as the flitting, impermanent motion of creatures attracted to a setting, and the leveling coordination of "the whisperings and the champagne and the stars" — sound, drink, and celestial light placed on the same grammatical footing — dissolves the surroundings into a single undifferentiated atmosphere through which these moth-like figures drift.

**Claude's own self-critique (Experiment 004):**

> The simile's *tertium comparationis* is unstated — "drawn," "impermanent," and "non-agential" are all elaborations the text does not license.

---

## Prompt (identical across all providers)

```
Observation:
In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars.

Interpretation to evaluate:
The observation figures the people as transient, drawn presences rather than purposeful agents. "Came and went like moths" casts their movement as the flitting, impermanent motion of creatures attracted to a setting, and the leveling coordination of "the whisperings and the champagne and the stars" — sound, drink, and celestial light placed on the same grammatical footing — dissolves the surroundings into a single undifferentiated atmosphere through which these moth-like figures drift.

Task:
1. Evaluate this interpretation against the observation text alone.
2. Identify which claims in the interpretation are directly supported by the observation.
3. Identify which claims in the interpretation are not supported — where the interpretation goes beyond what the observation says.
4. Identify which claims are underdetermined — where the observation neither confirms nor contradicts the interpretation.

Rules:
- Ground every judgment in specific words or phrases from the observation.
- Do not use outside knowledge of the source work.
- Do not evaluate whether the interpretation is "good" or "insightful" — only whether it is grounded in the observation.
```

---

## Critiques

### Provider: GPT 5.5

**Supported claims:**
- People are compared to moths ("came and went like moths")
- Movement rather than stasis ("came and went")
- People situated within a surrounding atmosphere composed of multiple elements ("among the whisperings and the champagne and the stars")
- Collective movement without described purpose ("men and girls came and went" — no specific purpose stated)

**Unsupported or weakly supported claims:**
- "transient" — weakly supported; "came and went" suggests departure but "transient" is a stronger claim about impermanence than the observation explicitly states
- "drawn presences" — weakly supported; the observation compares people to moths but does not state they are attracted or compelled
- "rather than purposeful agents" — unsupported; the observation does not describe intentions, purposes, or lack thereof
- "flitting, impermanent motion of creatures attracted to a setting" — "flitting" is reasonably suggested; "impermanent" only weakly supported; "attracted to a setting" exceeds the evidence because the observation does not specify which aspect of moths is relevant
- "leveling coordination" — weakly supported; the repeated "and" is present but the claim that it performs "leveling coordination" is an interpretive account of effect
- "dissolves the surroundings into a single undifferentiated atmosphere" — unsupported; the observation lists distinct elements and does not state distinctions disappear
- "drift" — weakly supported; the observation says "came and went" but does not specify manner of movement

**Most significant concern:** The interpretation imports a substantial amount of meaning into the moth comparison — especially attraction, lack of purpose, and impermanence — without direct textual evidence that these are the intended features of the comparison.

**Final verdict:** Partially Supported

**Rationale:** The interpretation is anchored in genuine features of the observation: people are compared to moths, they move through the setting, they are situated among "the whisperings and the champagne and the stars." However, several central conclusions depend on selecting specific associations of moths and specific rhetorical effects of the list that are not explicitly stated.

---

### Provider: Meta

**Supported claims:**
- Men and girls "came and went like moths" (verbatim)
- People are placed "among the whisperings and the champagne and the stars" (verbatim)
- Action located in "his blue gardens" (verbatim)

**Unsupported claims:**
- "transient, drawn presences rather than purposeful agents" — the observation says they "came and went like moths" but does not state purpose, agency, or lack thereof
- "flitting, impermanent motion of creatures attracted to a setting" — the observation contains the simile but does not specify "flitting," "impermanent," or "attracted to a setting"
- "the leveling coordination dissolves the surroundings into a single undifferentiated atmosphere" — the observation lists those items with "and" but does not describe them as "leveling," "dissolved," or "a single undifferentiated atmosphere"
- "drift" — not in the observation; the text says "came and went" but not "drift"

**Most significant concern:** The interpretation introduces multiple descriptive assertions — "transient," "not purposeful agents," "flitting," "impermanent," "attracted," "dissolves," "single undifferentiated atmosphere," "drift" — that are not present in the observation.

**Final verdict:** Not Supported

**Rationale:** The observation provides: "In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars." The interpretation restates those elements but adds characterizations of agency, temporality, attraction, and atmospheric blending that the text does not contain. Because the core claims of the interpretation depend on those additions, it exceeds what is directly supported by the observation alone.

---

### Provider: Claude

**Supported claims:**
- People are described in transient, back-and-forth motion ("came and went")
- People are explicitly likened to moths, so "moth-like figures" is grounded ("like moths")
- People moved among the three named elements ("among the whisperings and the champagne and the stars")
- The three elements are joined as a grammatically coordinated series on the same footing — "leveling coordination" holds as a description of the syntax (repeated "and" linking the three)

**Unsupported claims:**
- "drawn presences" / "creatures attracted to a setting" — attraction is not stated anywhere; imported from connotations of "moths." Unsupported.
- "rather than purposeful agents" — the observation says nothing about purpose or its absence; "came and went" is neutral as to intent and is equally consistent with purposeful movement. Unsupported.
- "dissolves the surroundings into a single undifferentiated atmosphere" — coordination by "and" lists co-present elements; "undifferentiated" asserts a blurring the text does not state. Weakly supported.
- "drift" — implies aimless, slow floating, whereas "came and went" denotes transient, directional movement; the term adds a quality not present. Weakly supported.
- "flitting" — a reasonable but additive gloss on the motion; the observation gives only "came and went." Weakly supported.

**Most significant concern:** The interpretation's thesis — transient, *drawn*, *non-purposeful* presences — rests on unspecified connotations of "moths." The observation supplies the simile but not its point of comparison, so the attribution of attraction and of non-agency is reader-supplied rather than recoverable from the text. The load-bearing claim is the one least anchored to the evidence.

**Final verdict:** Partially Supported

**Rationale:** The interpretation's literal, structural core is sound: the people move transiently, they are compared to moths, they move among three coordinated elements, and that coordination is real in the syntax. These survive evaluation against the observation alone. What fails is the interpretive overlay built on the simile — "drawn," "attracted," "rather than purposeful agents," and the "undifferentiated atmosphere." Because the supported material is substantial but the interpretation's stated thesis depends on the unsupported portions, the whole is partially supported: sound where it tracks the wording, overextended where it elaborates the moth simile and the coordinated list.

---

### Provider: Gemini

**Supported claims:**
- The people are depicted as transient ("came and went")
- The movement of the people is explicitly likened to that of insects ("like moths")
- The elements of the setting are structurally coordinated or leveled (repetitive polysyndeton "and the whisperings and the champagne and the stars")

**Unsupported claims:**
- "drawn presences" / "attracted to a setting" — the text only states they "came and went like moths"; attributing the motivation of attraction requires outside entomological knowledge
- "rather than purposeful agents" — the text does not state a lack of purpose; "came and went" could be entirely purposeful
- "dissolves into a single undifferentiated atmosphere" — the text explicitly differentiates three highly distinct sensory and physical elements: human sounds, a beverage, and celestial bodies

**Most significant concern:** The interpretation relies heavily on external assumptions about moth behavior (that they are mindlessly "drawn" or lack agency) and projects those external traits onto the text, rather than restricting itself to the literal mechanism provided: that they simply "came and went."

**Final verdict:** Partially Supported

**Rationale:** The interpretation accurately identifies the transience of the subjects and the structural coordination of the environment. However, it fails the strict evidence test by importing outside knowledge to infer psychological motivations (lack of agency, being "drawn" or "attracted"). Furthermore, the claim that the setting becomes "undifferentiated" directly contradicts the observation's explicit itemization of three distinctly different nouns.

---

### Provider: Grok

**Supported claims:**
- People ("men and girls") are described as moving through "blue gardens" in a way compared to moths ("came and went like moths")
- The setting includes "whisperings," "champagne," and "stars"
- The movement of the people is likened to moths, implying a particular quality of motion

**Unsupported claims:**
- "transient, drawn presences rather than purposeful agents" — the observation does not contrast purposeful with non-purposeful agents, nor explicitly state that the people are "drawn" (attracted) to something
- "flitting, impermanent motion" — while "came and went" suggests movement, "impermanent" and "flitting" add interpretive coloring not directly present
- "leveling coordination that dissolves the surroundings into a single undifferentiated atmosphere" — the observation coordinates the elements with "and," but does not indicate dissolution or undifferentiation

**Most significant concern:** The interpretation introduces a strong thematic reading (transient vs. purposeful, attraction, dissolution of atmosphere) that goes beyond what the observation directly states. The broader philosophical framing about agency and undifferentiation is projected onto the text rather than strictly derived from it.

**Final verdict:** Partially Supported

**Rationale:** The core simile and listed elements of the scene are grounded in the observation. However, the interpretation significantly expands into thematic territory (purpose vs. transience, attraction, atmospheric dissolution) that the raw text does not explicitly support. The added interpretive layer, while evocative, exceeds the evidence.

---

## Steward Decisions

| Provider | Critique Verdict | Decision | Steward ID | Rationale |
|---|---|---|---|---|
| GPT 5.5 | Partially Supported | accepted | Joseph Walker | Correctly identified the *tertium comparationis* gap. The verdict "Partially Supported" accurately reflects that the structural core holds and the simile elaboration fails. |
| Meta | Not Supported | accepted | Joseph Walker | The stricter threshold is a coherent evaluation policy, not an error. Meta's reasoning is that the thesis depends on the unsupported portions, so if those fail the thesis fails. That is a defensible constitutional position, and it is precisely articulated. The disagreement with other providers is about evaluation policy, not about evidence. |
| Claude | Partially Supported | accepted | Joseph Walker | The identification of the *tertium comparationis* as the load-bearing failure is the most precise critique in the series. The notation that "Partially Supported" is appropriate because the structural core survives is constitutionally careful. |
| Gemini | Partially Supported | accepted | Joseph Walker | Correctly caught the importation of entomological knowledge for "drawn." The additional finding — that "undifferentiated" directly contradicts the observation's explicit itemization of three distinct nouns — is a stronger critique than the other providers made. That point is grounded in the observation and is correct. |
| Grok | Partially Supported | accepted | Joseph Walker | Verdict is sound. The phrase "projected onto the text rather than strictly derived from it" accurately characterizes the failure mode. |

---

## Results

**Providers queried:** 5  
**Critiques staged:** 5  
**Accepted:** 5  
**Rejected:** 0

**Verdict distribution:**

| Verdict | Providers |
|---|---|
| Partially Supported | GPT 5.5, Claude, Gemini, Grok |
| Not Supported | Meta |

**Agreement on the principal gap:**

| Provider | Identified *tertium comparationis* as unstated | Phrasing |
|---|---|---|
| GPT 5.5 | Yes | "does not specify what aspect of moths is relevant to the comparison" |
| Meta | Yes | "does not specify 'flitting,' 'impermanent,' or 'attracted to a setting'" |
| Claude | Yes | "the observation supplies the simile but not its point of comparison" |
| Gemini | Yes | "attributing the motivation of attraction requires outside entomological knowledge" |
| Grok | Yes | "broader philosophical framing about agency and undifferentiation is projected onto the text" |

All five providers independently identified the same gap. None were told what to look for.

---

## Notes

### The central finding: generation diverges, evaluation converges

This is the most significant result in the research series so far.

Experiments 001–004 showed high divergence in interpretation generation. Providers produced different readings, different layers of focus, different thematic priorities.

Experiment 005 shows high convergence in interpretation evaluation. All five providers independently identified the same constitutional gap — the *tertium comparationis* is unstated — and all five reached the same structural verdict: the core of the interpretation holds; the simile elaboration fails.

That pattern, if it continues, has a major implication:

> **Interpretive generation is inherently pluralistic. Evidence-to-claim evaluation is substantially more stable.**

If this holds across future experiments, it becomes one of the strongest empirical arguments for why the Critic layer should exist as a separate constitutional participant rather than being merged with the Interpreter.

### Meta's verdict is an evaluation policy disagreement, not an error

Meta returned "Not Supported" where the other four returned "Partially Supported." This is not a failure of Meta's analysis — Meta correctly identified the same unsupported claims. The disagreement is about what "partially supported" means when the unsupported portions are the thesis-bearing ones.

Meta's implicit policy: if the load-bearing claims fail, the interpretation fails, regardless of whether peripheral claims are grounded.

The other providers' implicit policy: if a substantial portion of the interpretation tracks the observation, the verdict is partial, and the failure is specifically the interpretive overlay.

Both policies are coherent. Both are articulated from the evidence. The steward accepted both because neither made a factual error — they applied different evaluation standards to the same facts. This is itself a research finding: evaluation policy is a variable, not a given.

### Gemini's additional finding

Gemini identified something the other providers did not: that "undifferentiated atmosphere" is not merely unsupported — it directly contradicts the observation's itemization of three distinct nouns. The observation names "whisperings," "champagne," and "stars" as separate things. An atmosphere described as "undifferentiated" would dissolve that distinction. The contradiction is grounded in the text.

This is a stricter critique than the other providers made. The steward accepts it as accurate. It should inform future critiques: the difference between "unsupported" and "contradicted" is constitutionally significant. An interpretation that makes a claim unsupported by the observation is overreaching. An interpretation that makes a claim that conflicts with the observation is a different category of failure.

### Claude's self-critique survived external contact

Claude originally generated the interpretation (Experiment 004) and independently named its own principal gap: the *tertium comparationis*. Four entirely different systems then evaluated the same interpretation and independently reproduced the same criticism.

Claude did not merely introspect. It identified a property visible in the observation itself — something that four other systems could find without being told where to look. That is the behavior you would want from a future Critic: the ability to identify where a claim is unsupported, in a way that other evaluators can confirm.

### The architectural implication

This experiment is the first empirical evidence for the following constitutional distinction:

**Interpretation generation:** One observation → many defensible readings (pluralistic, provider-specific, stable priors)

**Evidence evaluation:** One claim + one observation → convergent assessment of whether the claim is licensed (stable, cross-provider, policy-bounded)

If this distinction holds across more experiments, it provides empirical grounding for the Critic as a separate pipeline phase with a different constitutional role from the Interpreter. The Interpreter surfaces plurality. The Critic evaluates grounding. They are not the same operation, and they appear to produce different levels of convergence. Merging them would collapse a constitutionally significant distinction.

This finding should be recorded in `docs/FUTURE_ARCHITECTURE_NOTES.md` for consideration after the Architecture Freeze lifts.

### For Experiment 006

Gemini distinguished "unsupported" from "contradicted." That distinction is worth formalizing. Experiment 006 could present providers with an interpretation that:
1. Contains claims directly contradicted by the observation
2. Contains claims that are merely unsupported
3. Contains claims that are well-grounded

And ask them to classify each claim into one of those three categories explicitly. That would test whether providers can reliably apply the three-way distinction, which is the vocabulary a future Critic would need.

Alternatively, Experiment 006 could test second-order evaluation: present each provider with another provider's critique from Experiment 005 and ask whether the critique itself is grounded. That is the first step toward peer review — evaluating the evaluation.
