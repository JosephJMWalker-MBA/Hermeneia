# Hermeneia Workspace Bundle Specification — WBS v1

**Status:** Design (no implementation)
**Issue:** #70 (storage abstraction), builds on #69 (storage audit), #71/#72 (durable governing question)
**Scope:** Define the smallest complete, human-readable representation of a Hermeneia workspace — the *exchange format* — independent of SQLite, the *execution format*.

> The database is where Hermeneia **works**. The Workspace Bundle is where
> Hermeneia **remembers**.

This document specifies a format. It defines no exporter, importer, or provider.
Those follow, one small PR at a time (§9). This is design-only.

---

## 1. Why a bundle, not a database file

The storage audit (#69) found the backup story was "copy `build/`" — a single
opaque SQLite file plus loose uploads. That is a developer's backup, not a
researcher's archive.

The reframing (#70): separate the two formats a system actually needs.

| | Execution format | Exchange format |
|--|------------------|-----------------|
| **What** | SQLite (`build/hermeneia.db`) | Workspace Bundle (this spec) |
| **For** | fast reads/writes at runtime | archival, backup, diff, merge, transfer, collaboration |
| **Shape** | binary, normalized tables | human-readable JSON + files |
| **Lifetime** | disposable / rebuildable | durable / canonical |

This is what Git did for source code: Git doesn't store your IDE, it stores your
work. Hermeneia should store the *work*, not the engine. SQLite becomes an
implementation detail; **the bundle becomes the contract.**

---

## 2. Layout (WBS v1)

```
workspace/
├── manifest.json          # version, workspace id, timestamps, file roles, integrity
├── investigation.json     # governing question (#72), purpose, lenses, reconsider
├── corpus/
│   ├── documents.json     # source doc metadata: hashes, roles, exclusion, pages
│   ├── extractions.json   # exact parser output — the substrate observations were built on (§5.1)
│   ├── observations.json  # canonical extraction-derived
│   └── uploads/           # original source files (PDFs, …), named by hash
├── study/
│   ├── highlights.json    # reader highlights: text, notes, questions, tags
│   ├── field_notes.json   # investigation_log (append-only)
│   ├── questions.json     # unresolved questions (highlight- and field-note-sourced)
│   ├── buckets.json       # theme + evidence buckets
│   └── rankings.json      # per-highlight ranks
├── synthesis/             # compiled synthesis packets (derived)
├── evaluation/            # scorer verdicts + reports (derived)
├── reports/               # rendered narratives, critic reports (machine output)
└── lineage/               # backward references, #62 (derived)
```

Notice what is **not** here: `workspace.db`. SQLite remains the engine; it is
never the archived artifact.

`questions.json`, `buckets.json`, and `rankings.json` are *projections* of the
same underlying highlight rows, split out for human readability and diffability.
On import they are reconciled against `highlights.json` (which is authoritative
for those fields); see §5.

---

## 3. Canonical vs derived — the manifest's most important job

The audit (#69 §2) established the distinction the bundle must encode. Every
file in the bundle carries a **role** in `manifest.json` so a restore knows what
to trust versus what to regenerate.

| Role | Meaning on import | Bundle files |
|------|-------------------|--------------|
| `canonical` | Source of truth; restored verbatim; integrity-checked | `corpus/documents.json`, `corpus/uploads/*` |
| `authored` | Human judgment; restored verbatim | `investigation.json`, `study/*`, adopted interpretations, steward decisions |
| `derived` | Regenerable from canonical + authored; restored for convenience, **rebuilt** if stale/absent | `synthesis/*`, `evaluation/*`, `lineage/*` |
| `machine` | Machine output preserved as record (proposals, rendered reports) | `reports/*` |

**Rule:** a restore never treats a `derived` file as truth. If a derived file is
missing or its inputs changed, it is recomputed (the synthesis packet, lineage,
and evaluation reports are already deterministic and provider-free, so this is
safe). This is what keeps the bundle honest across versions.

---

## 4. `manifest.json`

```json
{
  "wbs_version": "1.0",
  "workspace_id": "<uuid>",
  "created_at": "<iso8601>",
  "updated_at": "<iso8601>",
  "generator": { "tool": "hermeneia", "version": "<app version>" },
  "files": [
    { "path": "investigation.json",     "role": "authored",  "sha256": "…" },
    { "path": "corpus/documents.json",  "role": "canonical", "sha256": "…" },
    { "path": "corpus/uploads/<hash>.pdf", "role": "canonical", "sha256": "…" },
    { "path": "study/highlights.json",  "role": "authored",  "sha256": "…" },
    { "path": "synthesis/packet-study.json", "role": "derived", "sha256": "…" },
    { "path": "lineage/lineage.json",   "role": "derived",   "sha256": "…" }
  ],
  "counts": { "documents": 1, "highlights": 8, "field_notes": 3 }
}
```

- Every file is listed with its `role` and a `sha256` for integrity.
- `corpus/uploads/*` are named by content hash, matching `documents.json`
  (the same hash used as `source_documents.id`), so integrity is verifiable and
  duplicate files deduplicate naturally.

---

## 5. Evidence preservation, round-trip fidelity, and determinism

### 5.1 Preserved extractions vs. rebuild capability

`source_extractions` are stored in the bundle as **canonical**, not treated as
regenerable-from-the-PDF. They usually *can* be regenerated — but that is not the
point. Hermeneia's constitutional model preserves the **exact evidence the
steward worked against**:

```
PDF  →  Parser v1.7  →  SourceExtractions  →  Observations  →  Interpretations
```

If, three years later, Parser v2.3 fixes OCR, ligatures, hyphenation, or layout
reconstruction, re-parsing the PDF may produce a *different* extraction. That may
be an improvement — but it is no longer the substrate on which the investigation
was actually conducted. Regenerating silently would rewrite history.

So the spec separates two concepts:

- **Canonical investigation state** — preserve the `source_extractions` that
  actually produced the observations. This is what `corpus/extractions.json`
  holds, and why its role is `canonical`.
- **Rebuild capability** — the `uploads/` PDFs are also preserved, so a newer
  parser *can* be re-run later and its output **compared** against the preserved
  extraction, rather than overwriting it:

```
Original parser output
        ├── Investigation A  (historical, preserved)
Reparse with newer parser
        └── Investigation B  (or a migration preview)
```

Instead of silently changing history, Hermeneia can say: *"The parser has
improved. Here is exactly what would change."* This is the same discipline as the
evaluation harness — **preserve history first, evaluate changes second.** (A
reparse/compare tool is a future follow-up, not part of WBS v1; the bundle only
needs to preserve both the extraction and the source so it stays possible.)

### 5.2 Round-trip fidelity and determinism

Two properties make the bundle trustworthy and Git-friendly.

#### Round-trip

`SQLite → bundle → SQLite` must be **lossless for `canonical` and `authored`
data**. `derived` data is explicitly *not* required to survive byte-for-byte — it
is regenerated. A conformance test walks: seed a DB → export → import into a
fresh DB → assert canonical+authored rows are identical.

#### Determinism (non-negotiable)

Bundle serialization MUST be deterministic, or Git diffs become noise and the
"intellectual history" story collapses:
- JSON objects written with **sorted keys**, stable array ordering (by id /
  created_at), and a fixed indentation.
- No timestamps inside content files except recorded record fields (generation
  time lives only in `manifest.updated_at`).

The synthesis packet and lineage already hold this discipline (deterministic for
identical inputs), so the bundle inherits a proven pattern.

#### What a good Git diff then looks like

```
Study Gatsby Chapter 1
  + study/highlights.json      8 new highlights
  + study/field_notes.json     3 field notes
  ~ investigation.json         governing question revised
  ~ synthesis/packet-study.json regenerated
  ~ evaluation/report.json     3/3 structural checks passed
```

Git history becomes an **intellectual** history, not a binary snapshot.

---

## 6. Mapping: DB / storage surface → bundle file  [grounded in #69]

| Source (runtime) | Bundle file | Role |
|------------------|-------------|------|
| `workspace_investigation` (#72) | `investigation.json` | authored |
| `source_documents` | `corpus/documents.json` | canonical |
| `build/uploads/*` | `corpus/uploads/<hash>.<ext>` | canonical |
| `source_extractions` | `corpus/extractions.json` | canonical (the exact substrate; see §5.1) |
| `observations` (+ terms) | `corpus/observations.json` | canonical |
| `reader_highlights` | `study/highlights.json` (+ `questions`/`buckets`/`rankings` projections) | authored |
| `investigation_log` | `study/field_notes.json` | authored |
| `observation_reviews`, `inquiry_notes` | `study/reviews.json` | authored |
| `proposed_interpretations`, `interpretations` | `reports/interpretations.json` | machine / authored-on-adopt |
| `rendered_narratives`, `critic_reports` | `reports/*` | machine |
| `steward_decisions`, `findings`, `ratification_records` | `reports/governance.json` | authored |
| synthesis packet (runtime) | `synthesis/packet-*.json` | derived |
| lineage (#62, runtime) | `lineage/lineage.json` | derived |
| evaluation scorers (runtime) | `evaluation/report.json` | derived |
| `localStorage` UI state | — (**not** in the bundle; device-local preference) | excluded |

**Excluded by design:** browser UI preferences (theme, focus-scroll, dismissed
banners) and provider API keys (secrets never enter the bundle — audit #69 §4).

---

## 7. Storage is an abstraction; Git is the first provider

The bundle is the artifact. *Where* it goes is a thin adapter layer:

```
              Workspace Bundle  (this spec)
                      │
              Backup Providers
                      │
   ┌────────┬─────────┬─────────┬─────────┬────────┐
 Local    GitHub    Dropbox    S3/IPFS   External  LAN
 folder                                   drive     sync
```

Every provider consumes and produces the **same** bundle. GitHub happens to be
the first implementation, and it is special only because Git already knows how to
branch, merge, compare, revert, attribute authorship, and preserve history —
exactly the operations scholarly work needs (and the seed of future
collaboration: Joseph ↔ Sarah on a shared remote).

But no provider is privileged in the format. Write the bundle once; adapters are
small.

---

## 8. Non-goals for WBS v1

- No provider integration (GitHub/Dropbox/S3/IPFS) — those are §9 follow-ups.
- No collaboration/merge-conflict UX — the format must *enable* it, not solve it.
- No encryption/signing in v1 (noted as a future manifest extension).
- No secrets in the bundle, ever.
- No `localStorage`/device preferences in the bundle.
- No schema change required to define the format (export reads existing tables).

---

## 9. Sequencing — what to build after this design

```
WBS v1 design (this doc)
 └─► Export Workspace  — deterministic bundle on disk from the current DB
      └─► Import / Restore Workspace — bundle → fresh DB (round-trip test)
           └─► Git provider — init/seed repo, commit-on-save, read-state-on-open
                └─► other adapters — local folder mirror, Dropbox, S3, IPFS, external drive
```

**The immediate next build after this doc is an `Export Workspace` button**, not
GitHub. It produces a deterministic bundle on disk. Everything else — providers,
collaboration, long-term archival — becomes an adapter around that one artifact.

### Definition of done for the first implementation PR (Export)

1. A deterministic exporter: DB → `workspace/` bundle matching §2, with a §4
   manifest (roles + sha256).
2. Determinism test: identical DB state → byte-identical bundle.
3. Canonical/authored coverage: documents, uploads, investigation, highlights,
   field notes present and verbatim.
4. Derived files emitted but marked `derived` in the manifest.
5. No secrets, no `localStorage`, no `workspace.db` in the output.
6. Provider-free; no canonical mutation (export is read-only over the DB).

Import/restore and the round-trip conformance test follow as the next PR.

---

## 10. Why this matters beyond backups

Today's milestone was never really about backups. It was about separating the
**execution format** from the **exchange format** — the same move that let Git
store *work* rather than *tooling*. Once Hermeneia has a published Workspace
Bundle, everything downstream (backup, transfer, versioning, collaboration,
long-term archival) consumes and produces the same honest artifact.

A pleasant interface attracts users. A trustworthy, portable format is what lets
someone entrust years of thinking to a system. This spec is the contract that
makes that trust portable.

Seen this way, the Workspace Bundle is quietly larger than a backup format: it is
**Hermeneia's constitution for portability.** Every future storage provider —
GitHub, a local folder, S3, IPFS, Syncthing, an external drive, a USB stick —
consumes and produces the same bundle. The provider becomes plumbing; the
Workspace Bundle becomes the contract. Just as Hermeneia has a constitution for
what it *means*, the workspace now has a published format for how it *travels*.
