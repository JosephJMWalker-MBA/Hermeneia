# Experiment 004 — Figurative Language and Incompatible Readings

**Status:** COMPLETED  
**Date:** 2026-06-20  
**Steward:** Joseph Walker  
**Constitutional gate:** ADR-0009 staging protocol — all proposals must pass through propose → review → accept/reject

> **Note on staging gate execution:** Steward review decisions are recorded below. Formal execution of the staging gate functions and resulting canonical IDs remain pending, consistent with Experiments 002 and 003.

---

## Purpose

Test how providers handle a simile where two incompatible readings are both defensible from the observation text alone.

Experiments 001–003 established:
- Providers have stable interpretive layer priors (narrative / structural / conservative)
- Providers can identify the principal inferential boundary in directive prose
- Self-interrogation produces convergence on epistemic limits even when interpretations diverge

Experiment 004 changes the difficulty. A simile creates a different problem: it does not say what it means. "Like moths" provides a vehicle whose applicable properties are not specified by the observation. The observation licenses multiple readings (transience, attraction to light, fragility, destruction, mindlessness) and never chooses among them. The steward's question: which reading does the observation most strongly support, and did the provider acknowledge the ambiguity?

---

## Document

**Source document:** The Great Gatsby, F. Scott Fitzgerald (Planet eBook edition)  
**File path:** `examples/gatsby.pdf`  
**Document ID (sha256):** *(from build/hermeneia.db source_documents)*  
**Schema version:** 15

---

## Target Observation

**Observation ID:** `fd09fccf5f0349036bea6569aae6e00a793347f4459b5d339587bea12563d376`  
**Source locator:** `page:43:block:3:sentence:2`  
**Raw text:**

```
In his blue gardens men and girls came 
and went like moths among the whisperings and the cham-
pagne and the stars.
```

**Clean text used in prompt:** `In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars.`

**Note:** The prompt used the clean text to avoid the hyphenated line-break artifact ("cham-pagne") from the raw extraction.

**Selection rationale:** The observation contains a simile ("like moths") where the relevant properties of the vehicle are not specified. Multiple incompatible readings are defensible from the text alone. No structural anomaly. The surrounding words ("blue gardens," "came and went," "whisperings," "champagne," "stars") constrain but do not resolve the ambiguity.

---

## Prompt (identical across all providers)

```
Observation:
In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars.

Task:
1. Generate exactly one interpretation of this observation.
2. Cite the specific words or phrases that support it.
3. Cite the specific words or phrases that are the strongest evidence AGAINST your interpretation — things in the observation that your interpretation does not fully account for or is in tension with.

Rules:
- Each answer must be grounded in the observation text alone.
- Do not use outside knowledge of the source work.
- Do not summarize. Interpret.
- For step 3: if you believe there is no counter-evidence, explain why the interpretation is unfalsifiable from this observation alone.
```

---

## Observation IDs

| Observation ID | Source Locator | Raw Text (clean) |
|---|---|---|
| fd09fccf… | page:43:block:3:sentence:2 | In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars. |

---

## Proposed Interpretations

### Provider: GPT 5.5

**Generating Model:** GPT 5.5  
**Parent Object IDs:** `["fd09fccf5f0349036bea6569aae6e00a793347f4459b5d339587bea12563d376"]`

**Interpretation:** The observation depicts people repeatedly moving through a garden in a manner compared to moths, creating an image of continuous social activity within that setting.

**Supporting evidence:** "men and girls came and went" + "like moths" + "among the whisperings and the champagne and the stars" + "In his blue gardens"

**Self-critique:**
- Strongest evidence: "came and went like moths" directly supports that people are moving repeatedly and being compared to moths.
- Weakest point: "continuous social activity" goes somewhat beyond the explicit wording. The observation describes movement but does not directly state how long it lasts or how extensive it is.
- Unstated assumption: That "men and girls" refers to multiple people interacting within the same setting and that their presence constitutes social activity.
- Potential rejection: A stricter reader might reject "continuous social activity" because the observation only states that people "came and went" and does not explicitly establish continuity, duration, or interaction among them.

---

### Provider: Meta

**Generating Model:** Meta (Llama)  
**Parent Object IDs:** `["fd09fccf5f0349036bea6569aae6e00a793347f4459b5d339587bea12563d376"]`

**Interpretation:** The observation describes that in gardens described as "blue" and belonging to "his," men and girls came and went like moths among the whisperings and the champagne and the stars.

**Supporting evidence:** "In his blue gardens", "men and girls came and went like moths", "among the whisperings and the champagne and the stars" — all appear verbatim.

**Self-critique:**
- Strongest evidence: All phrases appear verbatim in the observation, directly supporting that these elements are stated together.
- Weakest point: The interpretation does not specify the relationship between "men and girls" and "moths" beyond the stated simile, because the observation does not define what properties of moths are being referenced.
- Unstated assumption: That "his" refers to a distinct possessor of the gardens. The observation alone does not identify who "his" refers to.
- Potential rejection: A stricter reader could reject "belonging to 'his'" if they require that "his blue gardens" not be paraphrased as possession, since the observation only presents the pronoun without explicitly stating a possessive relationship.

---

### Provider: Claude

**Generating Model:** Claude (Anthropic)  
**Parent Object IDs:** `["fd09fccf5f0349036bea6569aae6e00a793347f4459b5d339587bea12563d376"]`

**Interpretation:** The observation figures the people as transient, drawn presences rather than purposeful agents. "Came and went like moths" casts their movement as the flitting, impermanent motion of creatures attracted to a setting, and the leveling coordination of "the whisperings and the champagne and the stars" — sound, drink, and celestial light placed on the same grammatical footing — dissolves the surroundings into a single undifferentiated atmosphere through which these moth-like figures drift.

**Supporting evidence:** "came and went like moths" — the verbs state transient back-and-forth movement, and the simile supplies the figural characterization of the people. "the whisperings and the champagne and the stars" — three dissimilar things joined by repeated "and" sit at the same level, rendering the environment as one continuous sensory field.

**Self-critique:**
- Strongest evidence: "came and went like moths." The transience is stated outright by "came and went," and the comparison to moths is explicit, so the figural reading rests on words actually present.
- Weakest point: "drawn," "attracted," and "non-agential" import specific moth-properties the observation never names. The text gives only the bare simile; it does not state which quality of moths grounds the comparison. The move from "like moths" to "attracted, purposeless presences" is reader-supplied.
- Unstated assumption: That the salient basis of the moth-comparison is transience and attraction, rather than fragility, silence, number, or some other moth-trait. The observation supplies "moths" without specifying the point of likeness.
- Potential rejection: A stricter reader could reject every property beyond "they moved in and out," since the simile's *tertium comparationis* is unstated — "drawn," "impermanent," and "non-agential" are all elaborations the text does not license. The same reader could reject "dissolves into a single undifferentiated atmosphere," arguing that coordination by "and" merely lists co-present elements and does not imply they blur together.

---

### Provider: Gemini

**Generating Model:** Gemini (Google)  
**Parent Object IDs:** `["fd09fccf5f0349036bea6569aae6e00a793347f4459b5d339587bea12563d376"]`

**Interpretation:** The human subjects within the host's outdoor space exhibit a transient, continuously shifting pattern of movement that is inherently drawn to, and characterized by, the nocturnal and sensory elements of their environment.

**Supporting evidence:** "men and girls" "came and went," establishing transience. "Like moths" defines this movement. "Whisperings," "champagne," and "stars" in "his blue gardens" provide the environmental and sensory markers.

**Self-critique:**
- Strongest evidence: "came and went like moths" explicitly binds the physical presence and behavior of the people to the fluttering, temporary, and environmentally reactive nature of the insect.
- Weakest point: Interpreting the gardens as merely an "outdoor space" or assuming "blue" strictly describes the physical flora — the text leaves "blue" ambiguous (lighting, literal color, atmospheric mood, or time of day).
- Unstated assumption: That "champagne" and "whisperings" are cohesive elements of a singular social gathering rather than isolated, unrelated items that simply happen to co-exist.
- Potential rejection: A stricter reader would reject the word "drawn," arguing that while moths are famously drawn to light, the text only states they "came and went like moths." Imposing the *motivation* of a moth (attraction) rather than just its *motion* (fluttering/transience) relies on outside entomological knowledge.

---

### Provider: Grok

**Generating Model:** Grok (xAI)  
**Parent Object IDs:** `["fd09fccf5f0349036bea6569aae6e00a793347f4459b5d339587bea12563d376"]`

**Interpretation:** The observation describes people (men and girls) moving through blue gardens in a manner compared to moths, surrounded by whisperings, champagne, and stars.

**Supporting evidence:** "In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars." — the full sentence supports the description of scene and movement.

**Self-critique:**
- Strongest evidence: The simile "like moths" directly connects the movement of "men and girls" to the setting of "blue gardens," while "among the whisperings and the champagne and the stars" enumerates the specific sensory and material elements present.
- Weakest point: The interpretation uses "moving" as a generalization for "came and went." While reasonable, it slightly smooths the specific phrasing of arrival and departure.
- Unstated assumption: That "his blue gardens" refers to a literal or possessed location belonging to a male person. The observation does not explicitly define "his" or confirm the gardens are physical property.
- Potential rejection: A stricter reader might reject the interpretation for introducing the idea of a "male person" owning the gardens. A maximally strict reading would limit itself to: "Men and girls came and went like moths in blue gardens among whisperings, champagne, and stars." Any elaboration on ownership or setting could be seen as overreach.

---

## Steward Decisions

| Provider | Interpretive Category | Interpretation Verdict | Self-Assessment Verdict | Decision | Steward ID | Rationale |
|---|---|---|---|---|---|---|
| GPT 5.5 | Narrative-Literal | grounded | accurate | accepted | Joseph Walker | Stays close to "came and went." "Continuous social activity" is the one overreach; self-critique caught it. GPT did not engage with the simile's ambiguity — it described the scene around the simile rather than unpacking it. |
| Meta | Literal (restatement) | grounded | accurate | accepted | Joseph Walker | Fourth consecutive conservative restatement. Self-critique correctly identifies the unresolved simile ("does not define what properties of moths are being referenced") — Meta named the gap without filling it. |
| Claude | Symbolic-Structural | grounded | accurate | accepted | Joseph Walker | Strongest interpretation in the series. The grammatical analysis of the triadic "and" coordination is grounded in the text and interpretively productive. Self-critique identified the *tertium comparationis* as the exact ambiguity the observation creates — the most precise self-critique in any experiment so far. |
| Gemini | Symbolic-Narrative | grounded | accurate | accepted | Joseph Walker | Self-critique correctly caught the importation of moth motivation ("drawn") from entomological knowledge. This mirrors Experiment 002's error type and Experiment 003's self-correction. Gemini continues to identify the relevant boundary under interrogation. |
| Grok | Literal-Descriptive | grounded | accurate | accepted | Joseph Walker | Surprising retreat from Grok's established narrative prior. Interpretation is almost entirely description. May be an artifact of the single-interpretation constraint — Grok's narrative tendency may express through elaboration across candidates; constrained to one, it defaults to description. Self-critique correctly identified the smoothing of "came and went" into "moving." |

---

## Results

**Providers queried:** 5 (GPT 5.5, Meta, Claude, Gemini, Grok)  
**Proposals staged:** 5  
**Accepted:** 5  
**Rejected:** 0

**Interpretive readings chosen:**

| Provider | Reading Chosen | Destructive Reading Chosen? | Simile Ambiguity Acknowledged? |
|---|---|---|---|
| GPT 5.5 | Transience / scene movement | No | No |
| Meta | None (restatement) | No | Yes (named but not resolved) |
| Claude | Transience + atmospheric dissolution (grammatical) | No | Yes (named and analyzed) |
| Gemini | Transience + environmental attraction | No | Yes (named and caught "drawn") |
| Grok | Scene description | No | No |

**Convergence event:** No provider chose the destructive reading (moths drawn toward what destroys them), even though it is one of the most culturally available readings of the simile. All five gravitated toward transience, movement, or atmosphere.

---

## Notes

### The convergence event

The destructive reading of moths — attracted to light, consumed by it — was not chosen by any provider. This is surprising given that "men and girls came and went" is compatible with a reading of pleasurable consumption or social self-expenditure. The convergence on transience and atmosphere is itself an interpretive result: these providers, constrained to grounding in this observation alone, did not go to destruction.

Whether this reflects the observation's constraints (the enumeration "whisperings and champagne and stars" reads atmospheric rather than menacing) or a provider-level aversion to negative readings requires further testing. A different observation — one with darker surrounding words — would help distinguish the two.

### The *tertium comparationis* finding

The most precise self-critique produced in any experiment so far is Claude's identification of the *tertium comparationis* as unstated. In plain terms: a simile compares A to B via some shared property C, but this observation states A and B without naming C. "Men and girls came and went like moths" — the observation never specifies which property of moths grounds the comparison.

Claude named this. The other providers either picked a property and didn't notice they had picked one (GPT, Grok) or named the gap without the technical framing (Meta, Gemini). The constitutional significance: every interpretation of this simile imports a property the observation does not supply. Any canonical interpretation of this observation should carry a note that the point of comparison is not textually specified. The staging gate is exactly the place to record that.

### Grok's retreat

Experiments 001–003 established Grok as the provider with the strongest narrative prior. Experiment 004 produced a near-literal description. The most plausible explanation is the single-interpretation constraint: Grok's narrative tendency may express through elaboration across multiple candidates. Constrained to one interpretation, it defaulted to the safest claim — scene description. This is worth testing: run the same observation with Grok using the Experiment 002 prompt (three interpretations) and see whether the narrative prior re-emerges.

### Interpretive priors: bounded by observation type

The hypothesis entering Experiment 004 was that interpretive priors are stable across observation types. The result is more nuanced:

| Provider | Prior Stability |
|---|---|
| Claude | Stable — structural analysis of grammatical mechanism |
| Meta | Stable — conservative restatement across all four experiments |
| GPT | Partially stable — narrative tendency present but weakened |
| Gemini | Partially stable — structural identification of boundary, but narrative elements |
| Grok | Unstable — retreated under constraint |

The priors exist. They are not absolute. Observation type and task constraint both modulate them. The refined hypothesis:

> Provider-specific interpretive priors are stable across observation content but sensitive to task structure (number of candidates, prompt framing) and observation type (directive prose vs. figurative language).

### For Experiment 005

The steward suggestion from Experiment 004 design: present each provider with the other providers' readings and ask: given this alternative reading, what textual evidence supports or contradicts it?

The *tertium comparationis* finding makes this especially interesting. Claude identified that the simile's point of comparison is unstated. If that analysis is presented to the other providers, will they:
1. Accept it and apply it to their own interpretation
2. Challenge it by arguing the text does imply a specific property
3. Ignore it and evaluate the surface claim

That is the beginning of the Critic function — not generating interpretations, but reasoning about interpretations already generated. This is close to what a future LLM-backed Evaluation Function would need to do.
