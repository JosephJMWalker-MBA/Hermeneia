# Author Journal first slice / source-free manuscript creation boundary

**Status:** Implemented first slice on feature branch; blank manuscript creation remains blocked by a publication-authority contract.  
**Motivation:** User wants to livestream writing a book from its first thought and eventually enter Amazon KDP publishing details without importing an already-finished manuscript.  
**Related:** [Hermeneia #205](https://github.com/JosephJMWalker-MBA/Hermeneia/issues/205); `docs/integrations/publication-compositor-authoring-architecture-v0.md`.

## Implemented: author reflection with an empty workspace

The Workspace drawer has an **Author Journal** link. It opens a quiet text-and-questions composer independent of an imported source. A successful save posts to the pre-existing `/api/investigation-log` route using the `corpus` lane. The corresponding list reads the same lane. It is intentionally titled "Workspace reflections," because existing Reader Field Notes in that lane may appear too.

- A blank workspace can record and later reopen thoughts before a manuscript or source document exists.
- Entries remain immutable in the existing Investigation Log; no new table, object ontology, migration, or publication authority is introduced.
- A failed request leaves the unsaved text in the browser.
- This first slice **does not** create manuscript text, chapters, publication profiles, source-equivalence bridges, paragraph anchors, or live-stream export.
- The 200-entry list is a browsing window, not a claim of complete history; the existing Workspace Bundle owns persisted Field Notes portability.
- The private User Journal must not be assumed safe for OBS capture; a separate opt-in public projection is required.

## Why no fabricated blank Compositor work?

Current `/api/authoring/prepare` chooses an **existing primary source PDF**; `/api/authoring/work/attach` requires a verified Compositor work manifest. Current S1 revisions are **source-derived** and are accepted by Compositor, not a Hermeneia-owned text store. Treating a blank PDF, synthetic fixture, or exported Markdown as an author's zero-source root would conflate real authorship with source evidence.

Creating a real blank book therefore requires a **Publication Compositor-owned authored-root/initial-version contract** with a verifiable history, plus a Hermeneia UX that uses that contract. This is not the same as a simple empty SQLite workspace and should not be worked around by a second competing manuscript store.

## Required next vertical slices (not implemented)

1. **Authored work genesis.** Compositor exposes creation/verification of a zero-source authored publication root, stable manuscript-unit IDs, insertion of first paragraph and chapters, approved successor versions, and complete export/restore evidence. No fake SourceDocument or fabricated SourceExtraction.
2. **Book setup.** Hermeneia presents "Study an existing work" / "Write a new work" at workspace entry. KDP details are optional, revisable *publishing profile/configuration*, not SourceEvidence or an authorial manuscript: working title, subtitle, pen name, language, description, keywords, categories, ISBN/imprint choices, trim/format options, rights, and publication status. Platform-specific rules must be validated at use time.
3. **Writing flow.** Freeform text composition with quiet auto-save of *drafts*, explicit human ratification for publication changes, and preserve machine proposals separately from author text. Linking journal entries to manuscript unit/version identity must be a verified relationship, not a guessed page number.
4. **Public view.** OBS-readable opt-in projection of selected manuscript text and selected journal reflections; no default transmission of private notes, provider credentials, unreleased proof artifacts, or manuscript history.

### Full acceptance scenario

Create a fresh workspace -> choose **Write a New Book** -> enter optional KDP metadata -> write and save the first paragraph without an imported source -> attach a specific author reflection -> reopen the workspace and recover the exact draft, reflection, and version relationship -> export and restore the manuscript and history -> produce a compositor-owned publication proof without manual transcription.

**Current result:** Only the workspace + author-reflection subset of this scenario is implemented on this branch. Do not present it as completed blank manuscript authoring.

## Existing authority

`docs/00_Constitution.md` and `docs/01_Authority_Index.md` govern forensic integrity and human stewardship. Active `docs/02_Constitutional_Invariants.md`, ADR-0048, and ADR-0050 require evidence preservation, read-only GETs, and guarded write transactions. This slice uses an existing guarded Field Notes write route and does **not** change schema. The reader and publication models remain separate.

## Verification

`tests/test_author_journal_first_slice.py` exercises a real empty workspace, reflection persistence after app restart, absence of fabricated sources/works, immutable Field Notes, and packaging references. Run it alongside `tests/test_investigation_log.py` and `tests/test_workspace_browser_create_ui.py`, then the whole test suite and a Jetson/SSH live-workspace smoke before merge. This PR must remain draft until verified; no live execution is claimed merely from GitHub writes.
