# G2 real-study validation: Blueprint chain and coverage declarations — 2026-10-13

**Authorization:** the owner approved G2 on 2026-10-13: one local
private-copy validation. Safe alias: `study-d88c4a642956`. This note holds
counts, codes and booleans only, and no study text, path or name.

**Code under test:** scratch integration merge `79f1ada`. It merges the
Reader integration branch `71ed82f` (which contains #253 and #254) with
#255 at `34a3b84`. The `observation_provenance` reclassification
(`6319728`) was made **after** this run, in response to it.

## Safeguards

| Safeguard | Result |
| --- | --- |
| Original files hashed before (7 regular files, filesystem reads only) | done |
| Two private copies made by filesystem copy; each byte-identical to the original before use | true, true |
| SQLite connections to the original | **none** |
| Network | sockets blocked in-process; no provider or model call; no credential store; throwaway connection settings |
| Original files after the run | **byte-identical** (7 of 7) |
| Each private copy unchanged by export (file hashes and logical dump) | true, true |
| Public artifacts | this note only: no study text, path, name or record content |

## Two copies

| Copy | Schema | Chain export (gate on) |
| --- | --- | --- |
| **A. as stored** | 16 (last written 2026-10-04 by an older build) | declared `CHAIN_SCHEMA_INCOMPLETE`; no chain file; the rest exported; restore reports the reason |
| **B. startup-migrated** (the product's own `SQLiteStore` initializer, applied to the private copy only) | 21 | **covered**; restore covered |

On B the round trip is exact:
- chain rows identical;
- Lineage chain items identical;
- P1 capability decisions identical (no difference);
- receipt verdicts identical.

**Material limitation: the real study holds zero chain records.** It has no
Interpretations, Blueprints, plans, revisions, E10 proposals or acceptance
receipts. This validation therefore exercises, on real data:
- schema detection;
- closure checking;
- the empty-chain path;
- coverage declarations.

It does **not** round-trip real chain records. That evidence still comes only
from the synthetic laboratory (9 lawful cases) and the #254 interplay test.

## What the real study holds that WBS does not carry

The counts are the source's own, as recorded in `manifest.not_exported`.

| Surface | Source records | After restore |
| --- | --- | --- |
| Observations (exported) | 2,369 | 2,369 |
| Reader highlights, field notes (exported) | 395, 8 | carried |
| Retained Perspective receipt (P3, exported) | 1 | covered |
| `derived_indexes`: `observation_derived`, `observation_terms`, `terms` | 2,369 / 15,847 / 3,320 | **0 / 0 / 0** |
| `observation_provenance`: `provenance` | 2,369 | **0** |
| `reading_progress` | 1 | 0 |
| Reviews, inquiry notes, reports, governance, custom profiles | 0 | 0 |

**Material finding.** The loss of compile-time Observation provenance and
indexes was silent before this audit, and it applies to every WBS restore of
a real study:
- Critic provenance checks would report restored Observations as
  "transformed";
- narrative trust summaries cannot confirm verbatim text;
- Reader character offsets and concordance search are degraded.

It is now:
- declared (`not_exported`, `coverage.not_carried`, and the import preview);
- pinned by two strict-xfail witnesses.

It is **not repaired**. Carrying or rebuilding provenance needs its own
contract and owner decision.

## Coverage report on restore (both copies)

- `coverage.study_portability` is `partial`, with `source_counts` set to
  `recorded`.
- Every `not_carried` surface is `unsupported`, with the counts above.
- Nothing is reconstructed: every not-carried table is empty in the
  restored target, apart from the 9 built-in Expression Profiles that every
  store seeds.

## What remains unvalidated on real data

- A real study containing Interpretations, Blueprints or P8/legacy
  acceptance receipts.
- Reader proposal review with a real model. No provider was called, by
  design.
