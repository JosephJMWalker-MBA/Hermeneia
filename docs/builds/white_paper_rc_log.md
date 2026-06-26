# White Paper — Release Candidate Log

**Blueprint:** 000001  
**Convention:** Each RC is a rendering of the ratified Blueprint at a specific maturity level.  
A new RC is cut when Critic findings or Steward decisions warrant revision.  
The RC log records what changed and why — not what the paper says.

---

## RC-1 — 2026-06-24

**Artifact:** `docs/papers/hermeneia_white_paper_v1.md` (preserved as witness)

**Status at cut:** Pre-Blueprint. Paper had evolved organically from software documentation into methodology argument. The communication had not caught up with the understanding.

**Critic Findings at RC-1:**
- Blueprint Fidelity: FAIL — no Blueprint existed; paper was its own implicit contract
- Evidence Coverage: PARTIAL — Gatsby experiments present but evidential tiers unspecified
- Instrument Framing: FAIL — advocacy language in sections that should read as research; paper described itself as a product in places

**Steward Decision:**
Major Revision. The investigation had substantially matured beyond the communication. A ratified Blueprint must precede the next rendering. The paper must be re-rendered from the Blueprint, not incrementally edited.

**What the revision revealed:**
The central claim had shifted from "here is software" to "here is a methodology for studying the evolution of understanding." That shift was never explicitly made. RC-1 contained the argument in fragments across sections that were originally written for a different claim.

**Blueprint action:** Blueprint 000001 drafted and ratified 2026-06-25.

---

## RC-2 — 2026-06-25

**Artifact:** `docs/papers/hermeneia_white_paper.md` (current)

**Status at cut:** First rendering from ratified Blueprint 000001. Architecture re-centered on methodology, not software. Five cognitive responsibilities named. Evidential tiers (Demonstrated / Empirical Finding / Research Hypothesis) applied throughout. Calibration experiments present with four replicated findings and divergence figure. Forbidden claims removed.

**Critic Findings at RC-2:**
- Blueprint Fidelity: PASS
- Evidence Coverage: WARNING — three gaps (see coverage report)
- Instrument Framing: PASS

**Coverage gaps at RC-2:**
1. Mandarin meta-observation absent — the strongest evidence for architectural necessity
2. Explorer underspecified in architecture section — Phase 1 implementation in progress
3. Layer 4 / Purpose absent from future work — labeled as Research Hypothesis, not yet written

**Steward Decision:**
Approved for circulation as working position paper. Not yet canonical. RC-3 required to close three coverage gaps before canonical status awarded.

**What RC-2 established:**
The first rendering where the paper argues from evidence rather than from aspiration. Evidential tiers make it possible for a skeptical reader to evaluate the claims independently. The Gatsby experiments are correctly framed as calibration, not proof.

**RC-2 patch — 2026-06-25:**
Mandarin meta-observation added to Section 9 with Figure 4 (Independent Methodological Convergence). Wording distinguishes two classes of evidence: interpretation divergence (Experiments 001/002) vs. methodological convergence (Experiment 003). Evidential status correctly labeled Observed, single execution. Coverage report updated: 7 PASS / 2 WARNING.

**RC-2.1 — Critic pass 2026-06-25:**
Three classification corrections applied:
1. Section 5 (Attention): Removed "Comparative experiments suggest" — replaced with architectural prediction language. Experiments established divergence at question selection; they did not isolate attention as causal. Hypothesis preserved; overclaim removed.
2. Section 9 (Compression): Added evidential status label *[Observed — 3 executions; single corpus]*. Restructured to separate observation from interpretation. "One possible interpretation is that the executions traversed different regions..." — interpretation is now explicitly downstream from the observation.
3. Section 9 (Summary table): Added Compression row — "Three independent executions produced distinct yet non-contradictory compressions of the same corpus — Observed (3 executions)."

These changes did not alter any claim. They classified confidence correctly.

**Conditions for RC-3:**
1. ~~Include Mandarin meta-observation~~ ✅ Done in RC-2 patch
2. Specify Explorer as named cognitive responsibility (Section 3) — deferred; Phase 1 implementation in progress
3. Add Layer 4 / Purpose and cross-domain recurrence to Section 8 — Research Hypothesis tier

---

## RC-3 — (pending)

**Target:** First coverage-passing rendering. Canonical status awarded if all section requirements pass with no warnings.

**Planned additions:**
- Mandarin meta-observation and its evidential significance
- Explorer cognitive responsibility specification
- Layer 4 research directions as explicitly-labeled hypotheses

**Ratification condition:**
Coverage report shows all PASS, no WARNING, no FAIL. Steward approves. Canonical v1.0 awarded.

---

## The Version Problem — Why This Log Exists

Before this convention, version history looked like:

```
hermeneia_white_paper.md
hermeneia_white_paper_v1.md
hermeneia_white_paper_FINAL.md
hermeneia_white_paper_FINAL_v2.md
```

The "best version" was undefined. Chronology was the only ordering principle.

Under the compile convention, the best version is defined:

> The rendering produced from the highest ratified Blueprint that passes all section requirements.

This log is the record of how we got there.
The canonical artifact is not the newest. It is the most ratified reconstruction.
That is a different philosophy.
