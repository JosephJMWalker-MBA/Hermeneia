# Release sequence: newer-schema refusal before schema 22 (2026-10-16)

**Status:** a deployment plan for the Steward. Nothing is merged, released or
activated.

**Authority:** ADR-0048 (newer-schema refusal) and ADR-0046 (U activation),
both PROPOSED.

## Why there must be a boundary

**What happens without one.** A build without ADR-0048 that opens a schema-22
workspace:
- silently downgrades the schema marker;
- migrates whatever it knows;
- fails in the trust card and audit dashboard (`KeyError`) on `unverifiable`
  Findings.

That was measured: ADR-0046's rehearsal and #266.

**What ADR-0048 changes.** Only builds that contain it refuse such a workspace.
So at least one release containing ADR-0048 at schema 21 must ship, and be
installed, before any release migrates a workspace to schema 22.

## The two releases

| Release | Contents | Schema | Evaluation semantics |
| --- | --- | --- | --- |
| **R1: the boundary** | the approved stack (#253 → #254 → #256 → #255 → #257), #258, #261, then #259 → #263 (D-3) → #260 → #265 (S1) → L2-a, #264 (ADR-0048), and #266 (D-2, U implementation-ready and inactive) | **21** | D-3, S1 and L2-a only, each after its ratification. U is inactive |
| **R2: activation** | the U activation step (with L2-b, if ratified with it) | **22**: the `findings` rebuild on first open | `provenance-v1.1` |

## Rules (the first two are executable)

1. **Schema 22 cannot become active before the boundary release exists.**
   `tests/test_adr0046_activation_gate.py` requires
   `findings_vocabulary.REFUSING_RELEASE_TAG` to name a git tag whose tree:
   - contains ADR-0048's `NewerSchemaError`;
   - declares `SCHEMA_VERSION = 21`.

   Verified:
   - the check **accepts** the ADR-0048 branch;
   - it **rejects** `main` and the existing `v0.6.0` tag;
   - setting schema 22 without a tag fails the gate.
2. **U activates whole, and only after both ADRs record ratification.** This is
   the same gate.
3. **Installs.** Every install must run R1 or later before R2 is installed
   anywhere. Builds older than R1 cannot be protected (ADR-0048, residual
   risk).
4. **Every R2 migration takes a verified backup first.** A copy is made through
   SQLite's backup API, and its logical content is proved equal before the
   rebuild begins. Then the rebuild runs in one transaction; it is rolled back
   whole on any failure, and the marker is set to 22 only after success.

   The private-copy test of this procedure is in
   `docs/verification/2026-10-16-schema22-private-copy-migration.md`.

## Release-identity gap (needs an owner decision)

Version metadata is inconsistent:
- `pyproject.toml` and `hermeneia.__version__` say **0.1.0**;
- the only tag is **`v0.6.0`** (2026-07-01).

The boundary therefore relies on a git tag that contains the refusal, not on a
version number.

**Decision needed:** a release-identity scheme. That means aligning the
package version and tags so that R1 and R2 have unambiguous identities.
