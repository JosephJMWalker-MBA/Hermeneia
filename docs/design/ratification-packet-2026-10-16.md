# Ratification packet: ADR-0046, ADR-0048, ADR-0047 (2026-10-16)

**Status:** prepared for the Primary Human Steward. **This packet confers no
authority.** The engineering brief of 2026-10-16 recommended these decisions;
they take effect only through the ratification records in each ADR.

## 1. Authority documents, in constitutional order

The Constitution, the Authority Index and the ratified amendments are not
changed by any of these ADRs, except for the register row listed in §3.

| Order | Authority | Draft PR | Decides | Depends on | Relation to existing authority |
| --- | --- | --- | --- | --- | --- |
| 1 | **ADR-0046** v0.3 | #259 | D-1: `unverifiable`, scoped to provenance; D-2: historical readings; D-3: the ledger write guard | none | supersedes ADR-0042 **in part** (the missing-provenance disposition). Additive under ADR-0041 §5 |
| 2 | **ADR-0048** v0.1 | #264 | refusal of newer workspace schemas | none | adds a migration rule to the storage specification (Art. XIII) |
| 3 | **ADR-0047** v0.1 | #260 | S1: ratified dimensions only; L2-a: link integrity at write and restore; L2-b: read-time link detection, plus the disposition for a missing link | ADR-0046 D-3 (for S1), ADR-0046 U (for L2-b) | **extends** ADR-0042; nothing is weakened |

**Recording a ratification.** For each ADR, complete its "Ratification
record":
- the decision and its scope;
- ratified by;
- the date;
- the ratified proposal HEAD;
- any amendments.

Then set its status line to RATIFIED. ADR-0046's executable activation gate
reads these records (`tests/test_adr0046_activation_gate.py`, in #266).

## 2. Implementation packets

**Every packet is a draft. None merges before its authority is ratified.**

| Packet | PR | Base | Requires ratified | What changes when merged | Schema |
| --- | --- | --- | --- | --- | --- |
| D-3: the ledger write guard | #263 | #259 | ADR-0046 D-3 | Finding writes become atomic and fail closed; refusals are visible (the Critic returns 409); retained versions are reported | none |
| P2: newer-schema refusal | #264 | `main` | ADR-0048 | newer, ambiguous and malformed markers are refused before any write | none |
| S1: ratified dimensions only | #265 | #263, with #260 merged in | ADR-0047 S1 | no new `semantic` Findings; historical ones are labelled and kept out of the verdict | none |
| D-2 and U, implementation-ready | #266 | #265, with #264 merged in | ADR-0046 D-2 (presentation). **U stays inactive** | Finding readings in the API and Reader; migration code present but never run on open | migration code only |
| U activation | **not prepared** | after #266 | ADR-0046 **and** ADR-0048 ratified; #264 released at least one release earlier; the gate passes | `provenance-v1.1` default, schema 22, `unverifiable` admitted for provenance | the `findings` rebuild |
| L2-a | **not prepared** | — | ADR-0047 L2-a | refusals at the store API and at chain export and restore | none |
| L2-b | **not prepared** | with or after U | ADR-0047 L2-b and its disposition | the EF checks and records the link | none beyond U |

**Merge order** (for eventual merging; nothing is merged now):
1. The existing stack: #253 → #254 → #256 → #255 → #257. #258 and #261 may
   merge at any point.
2. Then: #259 → #263 → #260 → #265.
3. #264 may land on its own, but must ship at least one release before U
   activation.
4. #266 last.

## 3. On ratification: the Authority Index

| Earlier authority | Status | Successor | Superseded scope | Reason |
| --- | --- | --- | --- | --- |
| ADR-0042 | SUPERSEDED IN PART | ADR-0046 | Provenance EF: the missing-provenance disposition and its stated meaning | An absent custody record makes custody unverifiable; it does not show material alteration (ADR-0041 §5) |

The other two ADRs need no supersession row:
- **ADR-0047** extends ADR-0042;
- **ADR-0048**'s rule is added to the storage specification's migration rules.

## 4. Migration risks (U activation)

1. **Rebuilding the canonical `findings` table in every workspace.**
   - **What the tests show:** it is row-identical; the guards and relations
     are preserved; any failure rolls back everything; it is idempotent (#266).
   - **Version dependency:** it relies on SQLite's legacy rename mode, verified
     with SQLite 3.49.1 and Python 3.13.5. Re-verify on the SQLite version that
     ships.
2. **Builds older than ADR-0048** would open a migrated workspace, downgrade
   its marker, and fail in the trust card and dashboard (`KeyError`). No
   Finding is lost.
   - **Mitigation:** release ADR-0048 first. The migration recognises a lowered
     marker.
3. **Forged lower marker.** Newer content behind a forged current marker is
   not detectable from the marker (pinned in #264).
4. **Critic re-runs will be refused.** After activation, re-running the Critic
   on a narrative that holds a v1.0 `transformed` Finding for an absent record
   is refused as divergent (D-3). This is intended and visible, but users will
   see refusals where re-runs used to succeed silently.
5. **No real workspace has been migrated.** On the real study, an
   earlier-exporter restore would yield 2,369 `unverifiable` instead of 2,369
   `transformed`. A fresh private-copy validation is needed before any
   production migration, and requires approval.
6. **The store-open race (#261, issue #262)** touches the same open path and
   the same supersession triggers that the migration rebuilds around. It merges
   cleanly with #264 and #266 (`git merge-tree`). It should land before
   activation.
7. **Verification environment.** A full suite writes about 2.2 GB of temporary
   files per run. On the development machine, three parallel runs filled the
   disk. That is an environment limit, not a product defect, and the runs were
   repeated.

## 5. Smallest remaining decisions

1. **ADR-0046:** ratify D-1 (U), D-2 and D-3.
2. **ADR-0048:** ratify.
3. **ADR-0047:**
   - ratify S1 and L2-a;
   - choose L2-b's missing-link disposition (`unverifiable` is recommended);
   - ratify L2-b.
4. **Merge order** (§2): approve it.
5. **U activation:** approve it, and its timing (at least one release after
   ADR-0048). It is a separate step.
6. **Private-copy validation:** approve one before any real workspace is
   migrated.
