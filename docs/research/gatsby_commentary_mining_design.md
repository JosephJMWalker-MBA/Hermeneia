# Gatsby Commentary Mining — Research Design

**Investigation type:** Interpretive reception analysis  
**Primary corpus:** The Great Gatsby (Fitzgerald)  
**Commentary corpus:** Draft essays (marked as `commentary` role)  
**Research question:** Do commentary artifacts overweight culturally iconic symbols relative to their actual frequency, placement, and interpretive function in the primary text?

---

## The Keeper Distinction

The essays are not evidence for Gatsby.  
They are evidence for how Gatsby is being interpreted.

That distinction changes everything about how the commentary is handled:

| What commentary is NOT | What commentary IS |
|------------------------|-------------------|
| Evidence from the novel | Evidence of interpretive reception |
| Support for claims about Fitzgerald | Claims made about Fitzgerald |
| Primary corpus | `source_role: commentary` |
| Evidence of what the text says | Evidence of what readers (and AI) assume it says |

---

## Corpus Setup

- Upload `The Great Gatsby` as `Primary`
- Upload draft essays as `Commentary`
- All commentary observations carry `source_role: commentary` throughout the pipeline
- Commentary proposals are flagged: "derived from commentary source — not primary evidence"
- The scope API will report `boundary_clear: true` only when a primary document is present

---

## The Green Light as Test Case

### Primary corpus facts
- "green light" appears **4 times** in the novel
- Two mentions in the middle of the book (planting desire and distance)
- Two mentions at the very end (converting the symbol to historical and national scale)
- The symbol works through **strategic placement**, not repetition

### The hypothesis
Commentary and AI-generated essays overweight culturally famous symbols relative to their textual frequency, sequence, and evidentiary role in the primary corpus.

### What to measure

| Signal | Source | Method |
|--------|--------|--------|
| Primary frequency | Primary corpus search | Pattern View → Primary count |
| Commentary frequency | Commentary corpus search | Pattern View → Commentary count |
| Commentary ratio | Computed | ×N relative to primary |
| Placement in primary | Observation pages | Distribution bar |
| Surrounding context | Each observation | Who perceives it? What does it resolve? |
| Commentary placement | N/A | Commentary doesn't have narrative structure |

### What frequency alone does not tell you

A low-frequency symbol may be highly important. The question is not whether frequency equals importance. The question is:

> Is commentary emphasis supported by textual placement, sequence, and interpretive function — or by cultural repetition alone?

Fitzgerald's mastery is compression. "Green light" is powerful because it is **strategically placed**, not because it is frequent. Hermeneia can surface whether commentary substitutes cultural salience for textual evidence.

---

## Symbol categories the Pattern View can surface

When searching a term with both primary and commentary corpus loaded:

- **High-frequency primary / low-frequency commentary** → Primary evidence not discussed
- **Low-frequency primary / high-frequency commentary** → Potential overweighting (green light is this)  
- **Equal frequency** → Commentary tracking the text
- **Commentary only** → Claim with no primary evidence

The "Commentary emphasis ×N" signal appears in the Pattern View when commentary references a term 3× or more relative to primary corpus frequency.

---

## Mining workflow for essay drafts

1. Load Gatsby as Primary, essays as Commentary
2. Search key symbols and themes
3. For each: record primary count, commentary count, ratio
4. For primary hits: note placement (early / mid / late), surrounding passage, who perceives it
5. For commentary hits: note what claim is made, whether it cites page/passage support
6. Classify claims:
   - **Text-supported** — references specific passage with accurate characterization
   - **Partially supported** — claim is plausible but not directly evidenced
   - **Inherited/commonplace** — received wisdom not checked against the text
   - **Weakly supported** — specific claim made, thin or no textual anchor
   - **Contradicted** — claim contradicted by primary observation

7. Cross-reference: for each major commentary claim, find the primary observation it should be anchored to. Missing anchor = unsupported claim.

---

## Symbols and themes to investigate

Priority order:
1. `green light` — canonical test case (4× primary, likely 10–20× commentary)
2. `old money` / `new money` — class claims
3. `American Dream` — not Fitzgerald's phrase; does the text support it?
4. `careless` / `carelessness` — Fitzgerald's own word; does commentary track it?
5. `yellow` / `gold` — color coding; how does commentary use vs. the text?
6. `time` / `past` — Gatsby's obsession; is it evenly distributed or climactic?
7. `hope` — final sentence territory; does commentary front-load it?

---

## Expected findings (hypotheses, not conclusions)

These are hypotheses to test, not assume:

- Commentary will mention "green light" more than 3× per primary occurrence
- Commentary will use "American Dream" — a phrase Fitzgerald never wrote
- Commentary will underweight `careless` / `carelessness` despite Fitzgerald's explicit use
- Commentary will distribute attention to symbols evenly; the text will cluster them structurally
- AI-generated essays will score higher on "inherited/commonplace" claim categories

---

## Research output format

After mining, produce a commentary report with:

1. Symbol frequency table (primary count, commentary count, ratio)
2. Green light focused section — 4 primary placements annotated
3. Claim inventory — major claims made in commentary, classified
4. Missing evidence log — commentary claims with no primary anchor
5. Fitzgerald compression notes — where the text does more with less than commentary assumes

---

## Constitutional notes

- This investigation must not promote commentary claims into canonical interpretations
- Every proposal generated from commentary observations must carry `obs_source_role: commentary`
- The Steward must explicitly note when accepting a commentary-derived proposal
- "Commentary says X" is never equivalent to "Gatsby says X"
