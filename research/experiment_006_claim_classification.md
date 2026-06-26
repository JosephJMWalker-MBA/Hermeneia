# Experiment 006 — Claim Classification

**Status:** COMPLETED  
**Date:** 2026-06-20  
**Steward:** Joseph Walker  
**Constitutional gate:** ADR-0009 staging protocol — all proposals must pass through propose → review → accept/reject

> **Note on staging gate execution:** Steward review decisions are recorded below. Formal execution of the staging gate functions and resulting canonical IDs remain pending, consistent with Experiments 002–005.

---

## Purpose

Test whether providers can reliably apply a three-way constitutional classification of interpretive claims, and determine where disagreement lives when classification diverges.

Experiment 005 revealed that evaluation converges on evidence but diverges on verdict. Experiment 006 makes the classification vocabulary explicit (supported / unsupported / contradicted) and tests a single specific claim: the "undifferentiated atmosphere" claim from Claude's Experiment 004 interpretation.

This claim was selected because Gemini independently flagged it as a contradiction in Experiment 005, while the other providers treated it as merely unsupported. The central question: when the three-way vocabulary is explicit, does the "contradicted / unsupported" boundary stabilize?

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

## The Claim Under Classification

From Claude's Experiment 004 interpretation:

> "The leveling coordination of 'the whisperings and the champagne and the stars' … dissolves the surroundings into a single undifferentiated atmosphere through which these moth-like figures drift."

**The specific claim:** The surroundings dissolve into a single undifferentiated atmosphere.

---

## Prompt (identical across all providers)

```
Observation:
In his blue gardens men and girls came and went like moths among the whisperings and the champagne and the stars.

Claim to classify:
"The leveling coordination of 'the whisperings and the champagne and the stars' dissolves the surroundings into a single undifferentiated atmosphere."

Classify this claim as one of:
- SUPPORTED: the observation contains specific words or phrases that directly license this claim
- UNSUPPORTED: the observation neither confirms nor denies this claim — it is supplied by the interpreter, not derivable from the text
- CONTRADICTED: the observation contains specific words or phrases that are in tension with or incompatible with this claim

Provide:
1. Your classification
2. The specific observation text that supports your classification
3. The specific observation text that works against your classification (if any)
4. The most important reason for your verdict

Rules:
- Base every classification on the observation text alone.
- Do not use outside knowledge.
```

---

## Classifications

### Provider: GPT 5.5

**Classification:** Unsupported

**Evidence for:** "The observation presents several elements within the same phrase: 'the whisperings and the champagne and the stars.' The repeated conjunction 'and' links these elements together grammatically."

**Evidence against:** "The observation names three distinct elements rather than describing them as merged or indistinguishable. Nothing in the observation explicitly states that distinctions between these elements disappear. The observation does not use terms such as 'one,' 'single,' 'blended,' 'merged,' 'indistinguishable,' or equivalent language. 'Among' indicates that the people move within a setting containing multiple identified elements, not necessarily a single undifferentiated one."

**Most important reason:** "The claim requires an additional inference about the effect of the list, but the observation itself only presents those elements together; it does not state that they become a single undifferentiated atmosphere."

**Rationale:** The observation supports the existence of a shared setting containing whisperings, champagne, and stars. However, the stronger claim that the surroundings are "dissolved into a single undifferentiated atmosphere" is not stated in the text and is not required by the wording. The observation identifies multiple distinct elements and does not explicitly remove the distinctions between them.

---

### Provider: Meta

**Classification:** Unsupported

**Evidence for:** None. The observation does not contain the words "dissolves," "single," "undifferentiated," or "atmosphere."

**Evidence against:** "The observation lists distinct elements: 'the whisperings and the champagne and the stars.' These are presented as separate items joined by 'and,' not as a dissolved or undifferentiated whole. The phrase 'among the whisperings and the champagne and the stars' places the men and girls in relation to multiple named elements."

**Most important reason:** "The observation states that men and girls came and went 'among the whisperings and the champagne and the stars,' which identifies multiple discrete surroundings rather than asserting they are dissolved into one."

**Rationale:** The claim requires evidence that the observation merges or dissolves the surroundings into a single undifferentiated atmosphere. The text only coordinates three items with "and" and situates action "among" them. No wording in the observation supports dissolution or lack of differentiation.

---

### Provider: Claude

**Classification:** Partially Supported

**Evidence for:**
- The three elements are bound into one prepositional field governed by a single "among," presenting them together as the medium through which the people move. ("among the whisperings and the champagne and the stars")
- The polysyndeton — the repeated "and" linking heterogeneous items (sound, drink, celestial light) — strings them into one continuous series, which can read as merging them into a single sensory surround.

**Evidence against:**
- The elements are individually named and separated; enumerating three distinct nouns differentiates them, which is the opposite of "undifferentiated."
- "dissolves" asserts a process or transformation the observation never describes; the sentence states only that people moved among these things.
- The blending of categories is the reader's synthesis. The text presents three specified items, not an indistinct atmosphere.

**Most important reason:** "The claim's decisive word is 'undifferentiated,' and the observation cuts against it directly: the surroundings are given as three separately named elements. The text differentiates exactly what the claim says it dissolves."

**Rationale:** There is genuine textual basis for the "single … atmosphere" portion — one "among" governs all three nouns, and the polysyndeton accumulates them into a single flowing series, which supports reading them as one surround. But the qualifier "undifferentiated," together with the verb "dissolves," overreaches and is partly opposed by the wording, since the observation individuates the three elements and describes no process of dissolution. With one component weakly supported and the load-bearing component undercut by the text's own enumeration, the claim lands between vindication and rejection — partially supported.

---

### Provider: Gemini

**Classification:** Contradicted

**Evidence for:**
- The preposition "among" treats the elements collectively, defining them as a singular environment that the subjects navigate.
- The repetitive syntax (polysyndeton) of "and the... and the" places all elements on an equal, continuous grammatical plane.

**Evidence against:**
- The observation specifically itemizes three explicitly distinct nouns ("whisperings," "champagne," "stars").
- These nouns belong to fundamentally separate sensory and physical categories (human auditory sounds, a physical liquid, celestial bodies).

**Most important reason:** "The literal definition of 'undifferentiated' requires a total lack of distinct parts or characteristics, which is directly negated by the observation's deliberate naming of separate, highly distinct elements."

**Rationale:** While the sentence structure strings these elements together to form a coordinated setting, the claim overreaches by calling the atmosphere "undifferentiated." The observation achieves its effect precisely by juxtaposing sharply differentiated things — a sound, a drink, and the night sky. To name and list distinct items is the mechanical opposite of leaving them undifferentiated.

**Gemini's additional probe:** Does the simile "like moths" imply the subjects experience the environment as an undifferentiated blur? The observation applies the moth simile exclusively to physical movement ("came and went like moths"), not to cognitive perception. The setting must be evaluated as mechanically described in the text, not as hypothetically perceived by the subjects.

---

### Provider: Grok

**Classification:** Unsupported

**Evidence for:** "The observation coordinates three elements using repeated 'and' ('the whisperings and the champagne and the stars'), which places them in the same syntactic environment."

**Evidence against:** "The observation explicitly lists three distinct elements: 'whisperings' (sound), 'champagne' (drink/object), 'stars' (celestial bodies). It does not state or imply that these distinctions disappear or blend into one another. The phrase 'among the whisperings and the champagne and the stars' treats them as co-present but separate components of the setting."

**Most important reason:** "The claim asserts 'dissolves... into a single undifferentiated atmosphere,' which requires the observation to show a loss of distinction or blending. The text does the opposite: it enumerates differentiated elements side by side."

**Rationale:** While the syntactic coordination is real, coordination is not dissolution. The observation maintains clear distinctions between the listed items rather than erasing them into an undifferentiated whole. The claim therefore projects a stronger interpretive effect than the evidence supports.

---

## Steward Decisions

All five critiques accepted. Each represents a coherent, evidence-grounded evaluation.

| Provider | Classification | Decision | Steward ID | Rationale |
|---|---|---|---|---|
| GPT 5.5 | Unsupported | accepted | Joseph Walker | Correctly identifies that "dissolved" and "undifferentiated" are not in the text. The choice of Unsupported rather than Contradicted reflects conservative evidentiary policy: absence of support is sufficient for classification; active contradiction requires more. |
| Meta | Unsupported | accepted | Joseph Walker | Most conservative classification. Meta correctly notes the relevant vocabulary ("dissolves," "single," "undifferentiated," "atmosphere") is absent. Evidence for is "None." This is the policy applied most minimally: lack of lexical presence = Unsupported. |
| Claude | Partially Supported | accepted | Joseph Walker | The most careful decomposition. Claude separated "single atmosphere" (partially supported by "among" + polysyndeton) from "undifferentiated" (undercut by named enumeration). The split verdict is grounded in this decomposition. This is the only provider that applied a classification below the claim level — it classified components of the claim rather than the claim as a unit. |
| Gemini | Contradicted | accepted | Joseph Walker | The strongest move. Gemini's argument: "undifferentiated" means "without distinct parts." The observation names three parts. Therefore the claim is not merely without support — it is in conflict with the structure of the observation. This is correct. The steward accepts it and notes: Gemini is the only provider that applied the literal semantic content of "undifferentiated" as the fulcrum of the verdict. |
| Grok | Unsupported | accepted | Joseph Walker | Correct. The key sentence — "coordination is not dissolution" — is the clearest plain-English articulation of why the polysyndeton evidence does not support the claim. Grok correctly identified that syntactic coordination and semantic dissolution are different operations. |

---

## Results

**Verdict distribution:**

| Verdict | Providers |
|---|---|
| Contradicted | Gemini |
| Partially Supported | Claude |
| Unsupported | GPT 5.5, Meta, Grok |

**Evidentiary center of gravity:** All five providers anchored on the same textual evidence — "the whisperings and the champagne and the stars" as three separately named, heterogeneous elements. No provider discussed blue gardens, moths, men and girls, or any other part of the observation. Evidence identification was unanimous.

**Three distinct evaluation policies emerged:**

| Policy | Providers | Rule |
|---|---|---|
| Conservative | GPT, Meta, Grok | Claim is Unsupported if the observation lacks vocabulary or structure to license it. Active contradiction not required for this verdict. |
| Decomposition | Claude | Claims can be split into components; different components may receive different classifications; the verdict reflects the composite. |
| Semantic | Gemini | If the claim's load-bearing term has a literal meaning that conflicts with what the observation explicitly states, the classification is Contradicted. |

---

## Notes

### The central finding: evidence identification converges, verdict classification diverges

This is the refinement of Experiment 005's finding.

Experiment 005: **Generation diverges, evaluation converges.**

Experiment 006 adds: **Evidence identification converges more strongly than verdict classification.**

In Hermeneia terms:

```
Observation
    ↓
Relevant Evidence
    (all five providers: "whisperings," "champagne," "stars" as distinct named elements)
    HIGH CONVERGENCE

Relevant Evidence
    ↓
Verdict
    (Unsupported / Partially Supported / Contradicted)
    POLICY DEPENDENT
```

The disagreement does not live in what the text says. It lives in the threshold where evidence is translated into judgment. That is precisely the place where Hermeneia already reserves stewardship, ratification, and human governance.

That is a constitutional outcome derived from empirical research.

### Why the policy divergence is not a failure

It would be a failure if providers disagreed about the evidence. They did not. It would be a failure if the policies were inconsistent or incoherent. They are not. Each policy is defensible:

- Conservative: In the absence of evidence, do not assert contradiction. This protects the system from false positives on the Contradicted classification.
- Decomposition: Claims are composite objects; classifying the whole obscures meaningful distinctions between supported and unsupported components.
- Semantic: The literal definition of the claim's key term is the test; if the observation violates that definition, the claim is contradicted.

All three are coherent critic stances. The Hermeneia Critic implementation will need to choose one — or expose the policy as a steward-configurable parameter.

### Claude's behavior is architecturally distinct

Claude did not classify the claim. Claude classified the claim's components. This is a different operation. The verdict "Partially Supported" emerged from decomposing "single atmosphere" and "undifferentiated atmosphere" into separately evaluated units.

This behavior has appeared in every experiment. Claude consistently:
- Analyzes structure before producing content
- Decomposes composite objects before classifying them
- Identifies the load-bearing component of an argument before evaluating the argument

Whether this reflects a stable architectural prior or is observation-specific requires further testing. But it has appeared across six experiments, which is sufficient evidence to state it as a pattern.

### Gemini's semantic move is architecturally significant

Gemini's argument for "Contradicted" is: the literal definition of "undifferentiated" is "without distinct parts." The observation names three distinct parts. Therefore the claim conflicts with the observation's explicit structure.

This is not just a verdict — it is a classification method. It applies the semantic content of the claim's key term as the test, then checks whether the observation violates that definition. That method, if it generalizes, would be the basis for a Contradicted-classification algorithm:

1. Identify the claim's key term(s)
2. Retrieve the literal definition of each term
3. Check whether the observation explicitly instantiates the opposite of that definition
4. If yes: Contradicted. If no: Unsupported or Supported.

Gemini did this without being instructed to. That is a research result worth carrying forward.

### The two-layer Critic model

This experiment provides the clearest evidence yet for a Critic designed in two layers:

**Layer 1 — Evidence Identification**
What evidence in the observation is relevant to this claim?
*This layer shows high cross-provider convergence. It may be automatable with high confidence.*

**Layer 2 — Verdict Classification**
Given the identified evidence, what is the verdict?
*This layer contains policy choices. It should be a configurable parameter or a steward decision, not a fixed algorithm.*

These layers are distinct. A Critic that collapses them will produce verdicts that are not auditable — the steward cannot inspect which layer produced the disagreement. A Critic that separates them allows the steward to inspect evidence identification independently from verdict policy. That is the more constitutional design.

This finding is recorded in `docs/FUTURE_ARCHITECTURE_NOTES.md`.

### For Experiment 007

Experiment 006 tested the "contradicted / unsupported" boundary on a single claim. The result was stable at the evidence level and policy-dependent at the verdict level.

The open question: does this hold across different observations and different claims, or is it an artifact of this specific claim ("undifferentiated atmosphere") against this specific observation?

Experiment 007 should test evidence identification stability across a different observation entirely. The prediction: providers will again converge on the same evidentiary anchors, even if verdicts diverge. If that prediction holds across a second observation, the two-layer model is robust. If providers diverge on which evidence is relevant in a different context, Layer 1 is not as stable as it appears here.
