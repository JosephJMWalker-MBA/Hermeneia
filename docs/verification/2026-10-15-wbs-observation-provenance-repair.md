# WBS Observation provenance-loss repair — 2026-10-15

**Status:** branch `wbs-observation-provenance`, stacked on #255.

- Nothing is merged, and no default switch is made for `proposal`, P8
  generation or chain export.
- The new `observation-compile-records-v1` component **is** on by default.
  That is the repair (contract §2), with decision R1 below.

**Result.** A WBS round trip now restores Observation provenance and the
derived indexes byte for byte, synthetically and on the real study. The two
strict-xfail witnesses showed `XPASS(strict)` and are now passing
regressions. Real-study validation also exposed, and this branch fixes, a
storage-order dependence in the Reader's related-observations endpoint.

## Sequence

| Commit | Step |
| --- | --- |
| `9c90c52` | Contract frozen first, including the investigation (`docs/design/wbs-observation-compile-records-v1.md`) |
| `9730f7a` | The component and the CI-016 rebuild for component-less bundles; witnesses converted; 17 tests |
| `de197ce` | Reader related observations ordered deterministically (found by the real-study validation) |

## Investigation findings

- **`provenance` is not reconstructible** (contract §1):
  - a random `compilation_run_id`;
  - compile timestamps;
  - parser paragraph bounding boxes that `source_extractions` does not
    store per paragraph.

  It is preserved verbatim and **never manufactured**.
- **`observation_derived` and the term index** are CI-016 derived
  artifacts. Rebuilding them from the Observations reproduced them exactly,
  apart from `derived_at`, on a synthetic probe and on **all 2,369
  Observations of the real study**.
- **Consumers of a missing provenance row:**
  - Study Lineage (each Observation item's provenance records);
  - the Critic provenance evaluation;
  - narrative trust summaries;
  - the Reader's related-observations anchors.
- **ADR-0042** defines a missing row as `operation=transformation`,
  `status=transformed`. This repair makes restored studies **have** their
  rows. It does not change the ADR (see the authority question below).

## Witnesses

`RestoredProvenanceLost` and `RestoredObservationLooksTransformed` both
reported `XPASS(strict)` once the component was in place. Their markers
were removed and their assertions are unchanged.

The two coverage tests that had encoded the loss now expect the repaired
behavior. One exact default-capability expectation in
`test_publication_authoring_s1` was advanced for decision R1.

## Tests: 18 new

`test_wbs_compile_records.py` (17) and
`test_reader_related_observations_order.py` (1).

| Area | Result |
| --- | --- |
| Round trip | byte-for-byte rows for all four tables |
| Unchanged before and after | Critic provenance findings (all `preserved`); Lineage Observation items with their provenance records; Reader related observations; `/api/search` (two probes); the narrative trust summary. All are 200 responses with substantive bodies |
| Component-less bundle | no provenance manufactured; indexes rebuilt exactly; coverage reports `rebuilt` / `rebuilt_on_restore`; the Critic reports `transformed` per ADR-0042, unchanged |
| Export negatives (5) | each declared unsupported with its code; no component file; the rest of the workspace exported |
| Restore negatives (8) | each refused before or at closure; target empty |
| Determinism | deterministic, read-only export |
| Reader order | identical across a reversed-storage copy and equal to compile order. The test fails without the fix |

## Compatibility with actual older code

Bundles were built in separate processes from each code root, then
restored by each code root:
- `origin/main` `09b72cc`;
- #255 `37883e5`;
- this branch.

| Bundle ↓ / restorer → | `main` | #255 | this branch |
| --- | --- | --- | --- |
| `main` default | restores; provenance lost (old defect) | same | restores; provenance **not** manufactured; indexes rebuilt |
| #255 default (adds `not_exported`) | **restores; additive key ignored** | same | as above |
| This branch, default | **refused**: "requires capabilities … `observation-compile-records-v1`" | **refused** | restores **with** provenance and indexes |
| This branch, component declared unsupported (adds `declared_unsupported`) | **restores; additive keys ignored** | restores | restores; provenance unsupported; indexes rebuilt |

**Decision R1.** New default bundles cannot be restored by earlier
Hermeneia; they are refused rather than silently stripped of provenance.
That follows the P3/P4/P7 capability doctrine. The alternative is to make
the component optional, so that older restorers silently drop provenance
again. It is recorded and was not chosen.

## Real-study validation (fresh private copies of `study-d88c4a642956`)

The G2 safeguards were repeated:
- the original's 7 files are byte-identical before and after;
- no SQLite connection to the original;
- sockets blocked; no provider;
- counts and booleans only;
- the copies are deleted afterwards.

| Check | As stored (schema 16) | Startup-migrated (schema 21) |
| --- | --- | --- |
| Component exported | yes | yes |
| Observations without provenance in the source | 0 | 0 |
| Restored provenance, `observation_derived`, `terms`, `observation_terms` | 2,369 / 2,369 / 3,320 / 15,847, **byte-identical** | same |
| Lineage Observation items | identical | identical |
| Every Observation has provenance after restore | yes | yes |
| Route probes (5 search terms drawn from the study's own index; 5 Reader pages) | **10 / 10 identical** after `de197ce` (7 / 10 before) | 10 / 10 |
| Rebuild from a component-less bundle | exact on all rows apart from `derived_at`; 0 provenance rows manufactured | same |

- **The ordering defect.** Before `de197ce`, 3 of the 5 Reader page probes
  differed after restore. Two had the same set in a different order. One
  had a **different set**, because a tie fell at the `LIMIT` boundary. The
  cause was ordering that ended at `paragraph`, leaving ties to physical row
  order.
- **No change for existing studies.** On the original-order copy, old and
  new code return identical related observations for **86 of 86** probes
  (every page, plus the page-less form).
- **Unexplained, low risk.** On the startup-migrated copy only, the copy's
  `-wal` and `-shm` sidecar files changed bytes during the validation's
  export step. The logical dump was unchanged, and export opens only
  `mode=ro` connections. It was not reproduced in five standalone replays.
  It is consistent with SQLite WAL and shared-memory bookkeeping after the
  migration had just written. The as-stored copy was byte-identical.

### Critic classification and Reader offsets on the real study

This was a second fresh private copy, under the same safeguards. The original's 7 files were unchanged, and the copy was deleted afterwards.

**Critic.** A probe Blueprint cited every Observation. It was ratified through the product route, on the copy only; chain export was enabled for this scratch probe alone. An identical null-provider narrative was stored on each side, and `evaluate_provenance` ran over all 2,369 obligations.

| Restored from | Findings identical to the source | Statuses |
| --- | --- | --- |
| Default bundle (component carried) | **yes** | 2,369 `preserved` |
| Earlier-exporter bundle (component stripped) | no | 2,369 `transformed` |

**Reader offsets.** Related observations were compared for every page and the page-less form: 86 probes, 870 items, all with a canonical span.

| Restored from | Responses identical | Items with a span |
| --- | --- | --- |
| Default bundle | 86 / 86 | 870 / 870 |
| Earlier-exporter bundle | 86 / 86 | 870 / 870 |

**Why provenance loss left the Reader unchanged on this study.** All 2,369 provenance rows have `location_precision = sentence` and **null** character offsets. The Reader's spans therefore come from deterministic sentence segmentation (`basis: sentence_segmentation`), which does not read provenance. This is a measured property of this study, not a general one: a study compiled with stored offsets would lose `provenance_char_offsets` spans without the component.

**What the earlier loss actually changed on this study:**
- the Critic's classification of every cited Observation;
- Lineage's provenance records;
- the 2,369 paragraph bounding boxes;
- the compile-run identity.

All four are now preserved.

## Authority question (not acted on)

ADR-0042 calls a missing provenance row "transformation"/"transformed". In
a workspace restored from a bundle that lacks provenance (older exporters,
or a declared-unsupported component), the Critic will therefore describe
untouched evidence as transformed. The record is absent, not altered.
Changing that classification would amend ADR-0042, which needs owner
review.

## Verification

| Run | Passed | Skipped | Expected failures | Failed |
| --- | --- | --- | --- | --- |
| Clean worktree of `de197ce` (this branch, on #255) | 2948 | 22 | — | 6 |
| Scratch merge of #256 (`e892603`, containing #253 and #254) with this branch: the full stack | 3020 | 21 | 7 strict | 6 |

- **Failures.** Both runs fail exactly the inherited Reader baseline:
  - `test_reader_accessibility` ×2;
  - `test_reader_blueprint_workstation`;
  - `test_reader_record_view` ×2;
  - `test_reader_voice_profile`.
- **The extra skip** on this branch alone is the #251 interplay module,
  which waits for #254.
- **Expected failures.** The 7 on the full stack are the R1–R6 witnesses in
  `legacy`/`governed`, per the #251 contract matrix. The two provenance
  witnesses now **pass**. There are no unexpected passes or errors.
- **Datasets.** All nine offline datasets reproduce on the full stack: P5,
  P6, P7 (Layer 1, candidate, authored), P8 governance, P8 ceiling, P8
  phi4-mini, and P10.

## Remaining unknowns

- Studies whose source has Observations without provenance. The component
  carries them as they are, and counts them in
  `observations_without_provenance`. No real study with that state has been
  observed.
- Other endpoints that may depend on physical row order. Only the one
  exposed by the probes was fixed; no broad audit was done.
- The sidecar-byte observation above.
