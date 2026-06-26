# Semantic Contract Fulfillment (SCF)
## A Provider-Neutral Benchmark for Measuring Epistemic Fidelity in Large Language Model Outputs

**Position Paper — Draft v0.1**

Joseph J.M. Walker, MBA

Companion Architecture: Persistent Understanding Architecture (PUA)
Reference Implementation: Hermeneia

---

## Abstract

Current evaluation benchmarks for large language models primarily measure retrieval accuracy, reasoning performance, code generation, or lexical similarity. These benchmarks evaluate whether a model can produce an expected answer but generally do not evaluate whether a model can faithfully realize a predefined semantic understanding while preserving required conceptual commitments.

This paper introduces Semantic Contract Fulfillment (SCF), a provider-neutral benchmark for measuring epistemic fidelity.

SCF evaluates language models against an externally specified semantic contract generated through a human-stewarded epistemic chain. The benchmark measures whether generated expressions preserve required concepts, avoid unsupported additions, satisfy structural obligations, and maintain semantic continuity independent of rhetorical style.

Unlike static benchmark datasets, SCF derives evaluation contracts from living, provenance-preserving understanding structures whose Architect, Artist, and Critic roles remain constitutionally separated.

SCF therefore measures a distinct dimension of model capability: faithful realization of understanding rather than generation of plausible language.

---

## 1. Introduction

Modern language model benchmarks evaluate many aspects of performance:

- factual recall,
- mathematical reasoning,
- programming ability,
- multilingual translation,
- summarization,
- lexical similarity.

Yet none directly answer a fundamental question:

> **Can a model faithfully express an already-established understanding without altering its meaning?**

This distinction becomes increasingly important as AI systems transition from isolated chat interfaces to components within persistent knowledge infrastructures.

Persistent Understanding Architecture (PUA) separates understanding from expression.

SCF provides the corresponding evaluation framework.

---

## 2. The Benchmark Gap

Existing benchmarks evaluate outputs.
SCF evaluates semantic fidelity.

| Benchmark | Primary Measurement |
|---|---|
| MMLU | Knowledge retrieval |
| HumanEval | Code generation |
| GSM8K | Mathematical reasoning |
| BLEU | Surface similarity |
| ROUGE | Lexical overlap |
| HELM | General capability evaluation |
| **SCF** | **Semantic contract fulfillment** |

SCF measures a dimension orthogonal to lexical similarity and factual recall.

---

## 3. The Semantic Contract

A semantic contract is an explicit specification of meaning that must survive expression.

The contract defines:

- intended communicative purpose,
- required semantic concepts,
- prohibited unsupported claims,
- structural obligations,
- evidential dependencies.

The contract intentionally does not prescribe wording.

It specifies meaning.

### Example

**Contract**

| Field | Value |
|---|---|
| Purpose | Explain Gatsby's longing. |
| Required concepts | green, light, distance, hope |
| Forbidden additions | Daisy speaks; physical contact |

**Valid fulfillment**

> Gatsby reached toward the distant green light, embodying his unattainable hope.

**Invalid fulfillment**

> Daisy called Gatsby from the dock beneath the green lantern.

The second sentence preserves vocabulary while violating semantic obligations.

BLEU may score it highly.

SCF does not.

---

## 4. Architect–Artist–Critic Separation

SCF depends upon constitutional separation of roles.

```
Human Steward

↓

Observation

↓

Interpretation

↓

Perspective

↓

Blueprint

↓

Architect Contract

═══════════════════════

Language Model
(Artist)

═══════════════════════

↓

Rendered Narrative

↓

Independent Critic

↓

Semantic Contract Fulfillment
```

The evaluated model does not create its own contract.

The evaluated model does not evaluate itself.

The benchmark remains provider-neutral.

---

## 5. Semantic Contract Audit

Every SCF evaluation produces an audit artifact.

| Contract | Fulfillment | Compliance |
|---|---|---|
| semantic obligations | generated realization | independent evaluation |

For every semantic section, the audit reports:

- intended purpose,
- required concepts,
- fulfilled concepts,
- omitted concepts,
- unsupported additions,
- structural compliance,
- semantic fidelity.

The evaluation is fully inspectable.

---

## 6. Formal Definition

> **Semantic Contract Fulfillment** measures the extent to which a generated artifact satisfies an externally specified semantic contract while preserving required concepts, avoiding unsupported additions, and maintaining structural obligations independently of rhetorical style or provider implementation.

---

## 7. Semantic Fidelity Score

A generalized SCF score may be represented as:

$$SCF = f(C_p,\ C_o,\ S_c,\ U_a)$$

where

- $C_p$ = preserved required concepts
- $C_o$ = omitted required concepts
- $S_c$ = structural compliance
- $U_a$ = unsupported additions

The exact weighting function remains implementation-dependent.

The architecture requires only that the evaluation be deterministic and independently reproducible.

---

## 8. Why SCF Is Different

Traditional benchmarks compare outputs to reference outputs.

SCF compares outputs to semantic obligations.

Consequently:

- Two radically different texts may receive identical SCF scores.
- Two lexically similar texts may receive radically different SCF scores.

Meaning becomes primary.

Surface realization becomes secondary.

---

## 9. Translation

Translation illustrates the distinction.

Traditional evaluation asks:

> Is this translation similar to a reference translation?

SCF asks:

> Does this translation preserve the semantic contract established by the Architect?

The same semantic contract may generate:

- literary English,
- literary Swahili,
- historical Arabic,
- children's Spanish,

while preserving identical understanding.

Translation therefore becomes semantic preservation rather than semantic reconstruction.

---

## 10. Provider Neutrality

SCF intentionally evaluates semantic fulfillment rather than provider capability.

```
Architect Contract

↓

OpenAI          →  SCF
────────────────
Anthropic       →  SCF
────────────────
Gemini          →  SCF
────────────────
Grok            →  SCF
```

Every provider receives the same contract.

Every provider is evaluated by the same Critic.

The benchmark measures fulfillment rather than implementation.

---

## 11. Resistance to Benchmark Contamination

Many benchmark suites become optimized through repeated exposure.

Static datasets encourage benchmark-specific optimization.

SCF derives evaluation contracts from living, stewarded epistemic chains.

The evaluated model neither constructs the contract nor controls the evaluation logic.

Optimization toward benchmark artifacts therefore becomes substantially more difficult than optimization toward static datasets.

The benchmark measures fidelity to understanding rather than memorization of answers.

---

## 12. Relationship to Persistent Understanding Architecture

SCF is not an independent architecture.

It is the canonical evaluation methodology for Persistent Understanding Architecture.

Within PUA:

- Architect establishes semantic obligations.
- Artist realizes expression.
- Critic computes Semantic Contract Fulfillment.

SCF operationalizes the constitutional separation between understanding and expression.

---

## 13. Research Agenda

Potential future investigations include:

- SCF vs BLEU correlation
- SCF vs ROUGE correlation
- SCF vs human preference
- SCF across translation tasks
- SCF across summarization
- SCF across legal drafting
- SCF across educational adaptation
- SCF across multimodal generation
- SCF robustness under adversarial prompting
- longitudinal SCF stability across model versions

SCF establishes a new research axis independent of lexical similarity metrics.

---

## 14. Conclusion

Semantic Contract Fulfillment introduces a provider-neutral methodology for evaluating whether language models faithfully realize externally specified understanding.

Rather than measuring similarity to reference text, SCF measures fidelity to semantic obligation.

Its evaluation artifacts are transparent, reproducible, inspectable, and constitutionally independent of the evaluated model.

As Persistent Understanding Architecture externalizes understanding into durable semantic artifacts, SCF provides the corresponding mechanism by which those artifacts may be audited across providers, languages, and generations.

If previous benchmark suites measured whether models could retrieve knowledge or generate language, Semantic Contract Fulfillment measures whether they can faithfully preserve understanding itself.

SCF is possible only because Hermeneia separates the cognitive acts that modern AI systems typically collapse into a single prompt.

When Discovery, Reconstruction, Communication, and Verification occur in constitutionally separated roles — with the model occupying exactly one of them — the output of any individual role becomes inspectable, auditable, and independently comparable across providers.

That separation is not a software design choice.

It is the prerequisite for measurement.

---

## Proposed Citation

Walker, J. J. M. (2026). *Semantic Contract Fulfillment (SCF): A Provider-Neutral Benchmark for Measuring Epistemic Fidelity in Large Language Model Outputs.* Companion methodology to *Persistent Understanding Architecture (PUA): A Provider-Independent Framework for Persistent Understanding, Provenance, Expression, Validation, and Ecological Stewardship.*

---

## The Research Program

| Work | Role |
|---|---|
| *Toward an Ecology of Intelligence* | Philosophical foundation |
| *Persistent Understanding Architecture (PUA)* | Architectural framework |
| *Semantic Contract Fulfillment (SCF)* | Benchmark methodology |
| *Hermeneia* | Reference implementation |

Theory → Architecture → Measurement → Implementation.
