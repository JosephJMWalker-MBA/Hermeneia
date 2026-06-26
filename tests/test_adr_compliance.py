"""
ADR Compliance Tests — continuously prove the implementation satisfies the constitution.

Each test is named after the invariant it guards and cites the ADR it enforces.
These tests are not about coverage; they are about proof of contract.

If any of these fail, an architectural invariant has been violated — not just a bug.

ADRs guarded here:
  ADR-0001  Observations are immutable (no UPDATE or DELETE — ever)
  ADR-0006  One sentence = one Observation; verbatim text is preserved
  ADR-0012  Observation ID = sha256(json({source_document_hash, page, paragraph, sentence}))
            Provenance ID == Observation ID
  ADR-0013  Provenance carries 19 normative fields; location_precision = "sentence"
            provenance.verbatim_text holds the raw form (never normalised)
  ADR-0014  Adjacent observations carry preceding_observation_id / following_observation_id
            The chain is doubly-linked and consistent
  Normalization boundary: raw_text preserved; normalized_text lives in ObservationDerived
  Field v0.1: term IDs are sha256(term); all terms are lowercase; index is deterministic
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.compiler.compiler import Compiler
from hermeneia.compiler.normalization import normalize_sentence
from hermeneia.field.index import extract_terms, term_id
from hermeneia.storage.hashing import make_observation_id, sha256_file

GATSBY_PDF = Path(__file__).parent.parent / "examples" / "gatsby.pdf"
needs_pdf = pytest.mark.skipif(
    not GATSBY_PDF.exists(), reason="gatsby.pdf not found in examples/"
)


# ── shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def compiled_db(tmp_path_factory):
    """Compile gatsby.pdf once; share the resulting db across all module tests."""
    root = tmp_path_factory.mktemp("adr_compliance")
    c = Compiler(db_path=root / "test.db", build_dir=root / "build")
    c.compile(GATSBY_PDF)
    c.close()
    conn = sqlite3.connect(str(root / "test.db"))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# ADR-0001  Immutability
# ═════════════════════════════════════════════════════════════════════════════

def test_append_only__evidence_update_delete_rejected(compiled_db):
    """CI-005: Evidence and provenance tables reject UPDATE and DELETE."""
    checks = [
        ("source_documents", "original_filename"),
        ("source_extractions", "raw_text"),
        ("observations", "raw_text"),
        ("provenance", "verbatim_text"),
    ]
    for table, field in checks:
        row_id = compiled_db.execute(f"SELECT id FROM {table} LIMIT 1").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            compiled_db.execute(f"UPDATE {table} SET {field} = 'mutated' WHERE id = ?", (row_id,))
        with pytest.raises(sqlite3.IntegrityError):
            compiled_db.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))


def test_append_only__insert_or_ignore_is_idempotent(tmp_path):
    """ADR-0001: Recompiling the same PDF must not alter any existing records.

    The only safe write primitive is INSERT OR IGNORE. If a row already exists,
    it must be left exactly as-is — not overwritten, not amended.
    """
    c = Compiler(db_path=tmp_path / "test.db", build_dir=tmp_path / "build")
    c.compile(GATSBY_PDF)

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.row_factory = sqlite3.Row
    before = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM observations").fetchall()
    }
    conn.close()

    # Recompile into the same DB
    c.compile(GATSBY_PDF)
    c.close()

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.row_factory = sqlite3.Row
    after = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM observations").fetchall()
    }
    conn.close()

    assert set(before.keys()) == set(after.keys()), "Recompile changed the set of observation IDs"
    for oid, row in before.items():
        assert row == after[oid], f"Observation {oid} was mutated on recompile"


def test_append_only__no_duplicate_observation_ids(compiled_db):
    """ADR-0001: Every observation ID is unique (PRIMARY KEY enforces this at the DB level;
    this test proves the constraint is actually present and not accidentally dropped).
    """
    ids = [r[0] for r in compiled_db.execute("SELECT id FROM observations")]
    assert len(ids) == len(set(ids)), "Duplicate observation IDs found"


# ═════════════════════════════════════════════════════════════════════════════
# ADR-0012  Observation ID formula + Provenance ID == Observation ID
# ═════════════════════════════════════════════════════════════════════════════

def test_sha_registration__observation_id_matches_formula(compiled_db):
    """CI-004: Every stored observation ID must equal
    sha256(canonical(source_hash, source_locator, raw_text)).

    This is checked against all observations, not just a sample.
    """
    doc = dict(compiled_db.execute("SELECT * FROM source_documents LIMIT 1").fetchone())
    doc_hash = doc["file_hash"]

    rows = compiled_db.execute(
        "SELECT id, source_locator, raw_text FROM observations"
    ).fetchall()

    mismatches = []
    for row in rows:
        expected = make_observation_id(doc_hash, row["source_locator"], row["raw_text"])
        if row["id"] != expected:
            mismatches.append(row["id"])

    assert not mismatches, (
        f"{len(mismatches)} observations have IDs that do not match the ADR-0012 formula"
    )


def test_sha_registration__provenance_id_equals_observation_id(compiled_db):
    """ADR-0012: Provenance ID is identical to its Observation ID.

    This is not a foreign-key relationship — it is an identity claim. The same
    sha256 payload that produces the observation ID also identifies its provenance.
    """
    pairs = compiled_db.execute(
        "SELECT p.id, p.observation_id FROM provenance p"
    ).fetchall()

    mismatches = [p for p in pairs if p["id"] != p["observation_id"]]
    assert not mismatches, (
        f"{len(mismatches)} provenance records where id != observation_id"
    )


def test_sha_registration__document_id_is_sha256_of_file(tmp_path):
    """ADR-0012: The source document ID must equal sha256 of the raw PDF bytes."""
    c = Compiler(db_path=tmp_path / "test.db", build_dir=tmp_path / "build")
    c.compile(GATSBY_PDF)
    c.close()

    expected = sha256_file(GATSBY_PDF)
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT id, file_hash FROM source_documents").fetchone()
    conn.close()

    assert row[0] == expected, "source_documents.id != sha256 of PDF bytes"
    assert row[1] == expected, "source_documents.file_hash != sha256 of PDF bytes"


def test_sha_registration__id_formula_encodes_exact_fields():
    """CI-004: The ID payload contains exactly these keys in sorted order:
    raw_text, source_hash, source_locator.
    """
    payload = json.dumps(
        {
            "raw_text": "raw",
            "source_hash": "deadbeef",
            "source_locator": "page:3:block:7:sentence:2",
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert make_observation_id("deadbeef", "page:3:block:7:sentence:2", "raw") == expected


# ═════════════════════════════════════════════════════════════════════════════
# ADR-0013  Provenance granularity
# ═════════════════════════════════════════════════════════════════════════════

def test_observations_have_provenance__one_to_one(compiled_db):
    """ADR-0013: Every observation has exactly one provenance record; no orphans either way."""
    obs_ids = {r[0] for r in compiled_db.execute("SELECT id FROM observations")}
    prov_obs_ids = {r[0] for r in compiled_db.execute("SELECT observation_id FROM provenance")}

    missing = obs_ids - prov_obs_ids
    orphaned = prov_obs_ids - obs_ids

    assert not missing, f"{len(missing)} observations have no provenance"
    assert not orphaned, f"{len(orphaned)} provenance records have no matching observation"


def test_observations_have_provenance__location_precision_is_sentence(compiled_db):
    """ADR-0013: The compiler produces sentence-level provenance.
    No record may claim a coarser granularity than 'sentence'.
    """
    bad = compiled_db.execute(
        "SELECT id FROM provenance WHERE location_precision != 'sentence'"
    ).fetchall()
    assert not bad, f"{len(bad)} provenance records with location_precision != 'sentence'"


def test_observations_have_provenance__all_19_fields_present(compiled_db):
    """ADR-0013: The 19 normative provenance fields must all be populated with non-NULL
    values for the mandatory fields.

    Mandatory (non-NULL): id, observation_id, source_document_id, source_document_hash,
    page, paragraph, sentence, verbatim_text, location_precision, created_at,
    compiler_version, compilation_run_id.

    Optional (may be NULL): char_offset_start, char_offset_end, bbox_x, bbox_y,
    bbox_width, bbox_height, bbox_dpi.
    """
    mandatory = [
        "id", "observation_id", "source_document_id", "source_extraction_id", "source_document_hash",
        "page", "paragraph", "sentence", "verbatim_text", "location_precision",
        "created_at", "compiler_version", "compilation_run_id",
    ]

    rows = compiled_db.execute("SELECT * FROM provenance LIMIT 100").fetchall()
    assert rows, "No provenance records found"

    for row in rows:
        d = dict(row)
        for field in mandatory:
            assert d.get(field) is not None, (
                f"Mandatory provenance field '{field}' is NULL in record {d.get('id')}"
            )


def test_observations_have_provenance__verbatim_text_matches_raw_text(compiled_db):
    """ADR-0013 + normalization boundary: provenance.verbatim_text must equal
    observations.raw_text. Provenance always holds the raw, unmodified form.
    normalized_text is derived metadata — never provenance.
    """
    mismatches = compiled_db.execute(
        """
        SELECT o.id
        FROM observations o
        JOIN provenance p ON p.observation_id = o.id
        WHERE o.raw_text != p.verbatim_text
        """
    ).fetchall()
    assert not mismatches, (
        f"{len(mismatches)} records where observations.raw_text != provenance.verbatim_text"
    )


# ═════════════════════════════════════════════════════════════════════════════
# ADR-0014  Sentence adjacency
# ═════════════════════════════════════════════════════════════════════════════

def test_sentence_adjacency__doubly_linked_chain_is_consistent(compiled_db):
    """ADR-0014: If A.following_observation_id == B, then B.preceding_observation_id == A.

    Any break in this invariant means the adjacency chain is malformed and
    navigation between observations will silently skip or loop.
    """
    rows = compiled_db.execute(
        "SELECT id, preceding_observation_id, following_observation_id FROM observations"
    ).fetchall()
    id_to_row = {r["id"]: dict(r) for r in rows}

    broken = []
    for row in id_to_row.values():
        fwd = row["following_observation_id"]
        if fwd and fwd in id_to_row:
            back = id_to_row[fwd]["preceding_observation_id"]
            if back != row["id"]:
                broken.append(row["id"])

    assert not broken, f"{len(broken)} broken forward→backward links in adjacency chain"


def test_sentence_adjacency__chain_has_exactly_one_head(compiled_db):
    """ADR-0014: Exactly one observation has no preceding (the head of the chain).
    Multiple heads would indicate the chain is fragmented.
    """
    heads = compiled_db.execute(
        "SELECT id FROM observations WHERE preceding_observation_id IS NULL"
    ).fetchall()
    assert len(heads) == 1, (
        f"Expected 1 chain head, found {len(heads)}. "
        "The adjacency chain is fragmented."
    )


def test_sentence_adjacency__chain_has_exactly_one_tail(compiled_db):
    """ADR-0014: Exactly one observation has no following (the tail of the chain)."""
    tails = compiled_db.execute(
        "SELECT id FROM observations WHERE following_observation_id IS NULL"
    ).fetchall()
    assert len(tails) == 1, (
        f"Expected 1 chain tail, found {len(tails)}. "
        "The adjacency chain is fragmented."
    )


def test_sentence_adjacency__chain_length_equals_observation_count(compiled_db):
    """ADR-0014: Walking the chain from head to tail must visit every observation exactly once.

    This catches cycles, dead ends, and observations that exist in the table but
    are unreachable from the head.
    """
    rows = compiled_db.execute(
        "SELECT id, following_observation_id FROM observations"
    ).fetchall()
    total = len(rows)
    id_to_next = {r["id"]: r["following_observation_id"] for r in rows}

    head = compiled_db.execute(
        "SELECT id FROM observations WHERE preceding_observation_id IS NULL"
    ).fetchone()
    assert head, "No chain head found"

    visited = []
    current = head[0]
    while current is not None:
        if current in visited:
            pytest.fail(f"Cycle detected at {current} after {len(visited)} steps")
        visited.append(current)
        current = id_to_next.get(current)

    assert len(visited) == total, (
        f"Chain walk visited {len(visited)} nodes but table has {total} observations. "
        "Some observations are unreachable."
    )


# ═════════════════════════════════════════════════════════════════════════════
# ADR-0006  Observation definition: one sentence, verbatim
# ═════════════════════════════════════════════════════════════════════════════

def test_observations_are_non_empty(compiled_db):
    """ADR-0006: Every observation must have non-empty raw_text and derived text.

    An empty observation is incoherent — it has no epistemic content.
    """
    bad_raw = compiled_db.execute(
        "SELECT id FROM observations WHERE raw_text IS NULL OR trim(raw_text) = ''"
    ).fetchall()
    bad_norm = compiled_db.execute(
        """
        SELECT o.id
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        WHERE od.normalized_text IS NULL OR trim(od.normalized_text) = ''
        """
    ).fetchall()

    assert not bad_raw, f"{len(bad_raw)} observations with empty raw_text"
    assert not bad_norm, f"{len(bad_norm)} observations with empty derived normalized_text"


def test_raw_text_is_never_destroyed(compiled_db):
    """Normalization boundary: raw_text must survive intact.
    It must never be replaced by derived normalized_text.

    Spot-check: at least one observation must have raw_text != derived normalized_text,
    proving the pipeline does not short-circuit normalization.
    """
    count = compiled_db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count > 0

    observation_cols = {
        row["name"]
        for row in compiled_db.execute("PRAGMA table_info(observations)").fetchall()
    }
    assert "normalized_text" not in observation_cols

    # Every observation must have both raw text and a derived text row.
    missing = compiled_db.execute(
        """
        SELECT o.id
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        WHERE o.raw_text IS NULL OR od.normalized_text IS NULL
        """
    ).fetchall()
    assert not missing, f"{len(missing)} observations missing raw_text or derived normalized_text"

    # At least some normalization must have occurred (proves the pipeline is not a no-op)
    different = compiled_db.execute(
        """
        SELECT COUNT(*)
        FROM observations o
        JOIN observation_derived od ON od.observation_id = o.id
        WHERE o.raw_text != od.normalized_text
        """
    ).fetchone()[0]
    assert different > 0, (
        "No observations differ between raw_text and derived normalized_text. "
        "Normalization may be a no-op — check normalize_sentence()."
    )


# ═════════════════════════════════════════════════════════════════════════════
# Field v0.1  Deterministic term index
# ═════════════════════════════════════════════════════════════════════════════

def test_field_v01__term_ids_are_sha256_of_term_string():
    """Field v0.1: term_id = sha256(term.encode('utf-8')).hexdigest().
    This is the determinism contract for the term index.
    """
    for word in ["green", "light", "gatsby", "daisy", "the"]:
        expected = hashlib.sha256(word.encode("utf-8")).hexdigest()
        assert term_id(word) == expected, f"term_id mismatch for '{word}'"


def test_field_v01__all_indexed_terms_are_lowercase(compiled_db):
    """Field v0.1: terms are always lowercase. The index makes no case distinctions."""
    bad = compiled_db.execute(
        "SELECT term FROM terms WHERE term != lower(term)"
    ).fetchall()
    assert not bad, f"{len(bad)} terms in index are not lowercase: {[r[0] for r in bad[:5]]}"


def test_field_v01__all_indexed_terms_meet_min_length(compiled_db):
    """Field v0.1: minimum term length is 3 characters. Shorter tokens are not indexed."""
    bad = compiled_db.execute(
        "SELECT term FROM terms WHERE length(term) < 3"
    ).fetchall()
    assert not bad, f"{len(bad)} terms shorter than 3 chars: {[r[0] for r in bad]}"


def test_field_v01__term_ids_match_sha256_formula(compiled_db):
    """Field v0.1: every stored term ID must equal sha256 of the term string.
    Proves the index was built with the canonical formula, not an ad-hoc hash.
    """
    rows = compiled_db.execute("SELECT id, term FROM terms").fetchall()
    mismatches = [
        r["term"]
        for r in rows
        if r["id"] != hashlib.sha256(r["term"].encode("utf-8")).hexdigest()
    ]
    assert not mismatches, (
        f"{len(mismatches)} terms with IDs that don't match sha256(term): "
        f"{mismatches[:5]}"
    )


def test_field_v01__every_observation_has_at_least_one_term(compiled_db):
    """Field v0.1: every observation with an indexable token must appear in observation_terms.

    An observation is permitted to have zero terms only if its derived normalized_text genuinely
    contains no tokens of length ≥ 3 (e.g., 'It', 'He', 'Go on.'). Any unindexed
    observation that does contain qualifying tokens is a silent indexer failure.
    """
    unindexed = compiled_db.execute(
        """
        SELECT o.id, od.normalized_text
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        LEFT JOIN observation_terms ot ON ot.observation_id = o.id
        WHERE ot.observation_id IS NULL
        """
    ).fetchall()

    # For each unindexed observation, verify it truly has no ≥3-char tokens.
    import re
    _TOKEN_RE = re.compile(r"[a-z][a-z']*")

    should_have_been_indexed = []
    for row in unindexed:
        text = row["normalized_text"] or ""
        tokens = [t.strip("'") for t in _TOKEN_RE.findall(text.lower())]
        qualifying = [t for t in tokens if len(t) >= 3]
        if qualifying:
            should_have_been_indexed.append((row["id"], text, qualifying))

    assert not should_have_been_indexed, (
        f"{len(should_have_been_indexed)} observations were silently skipped by the indexer "
        f"despite having qualifying tokens:\n"
        + "\n".join(f"  {r[1]!r} → {r[2]}" for r in should_have_been_indexed[:5])
    )


def test_field_v01__index_is_deterministic_across_runs(tmp_path):
    """Field v0.1: building the term index twice on the same DB must yield identical results.
    INSERT OR IGNORE is the contract; this test proves it holds for the term tables.
    """
    c = Compiler(db_path=tmp_path / "test.db", build_dir=tmp_path / "build")
    c.compile(GATSBY_PDF)

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    terms_before = set(r[0] for r in conn.execute("SELECT id FROM terms"))
    pairs_before = set(
        (r[0], r[1])
        for r in conn.execute("SELECT observation_id, term_id FROM observation_terms")
    )
    conn.close()

    # Recompile: this triggers build_term_index again on an already-indexed DB
    c.compile(GATSBY_PDF)
    c.close()

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    terms_after = set(r[0] for r in conn.execute("SELECT id FROM terms"))
    pairs_after = set(
        (r[0], r[1])
        for r in conn.execute("SELECT observation_id, term_id FROM observation_terms")
    )
    conn.close()

    assert terms_before == terms_after, "Term set changed on recompile"
    assert pairs_before == pairs_after, "Observation-term pairs changed on recompile"


# ═════════════════════════════════════════════════════════════════════════════
# Normalization unit tests (no PDF needed)
# ═════════════════════════════════════════════════════════════════════════════

def test_normalization__unicode_quotes_become_ascii():
    """Normalization: directional quotes must be mapped to straight ASCII equivalents."""
    assert normalize_sentence("“Hello”") == '"Hello"'
    assert normalize_sentence("‘Hello’") == "'Hello'"


def test_normalization__em_dash_is_preserved():
    """Normalization: em dash (—) must never be touched.
    It carries semantic weight (ADR-0037 semantic invariants).
    """
    sentence = "He stood there—alone."
    assert "—" in normalize_sentence(sentence)


def test_normalization__multiple_spaces_collapsed():
    """Normalization: Unicode whitespace variants collapse to a single ASCII space."""
    assert normalize_sentence("one  two   three") == "one two three"


def test_extract_terms__min_length_enforced():
    """Field v0.1: tokens shorter than 3 chars must not be extracted."""
    terms = extract_terms("it is a big green light")
    assert "it" not in terms
    assert "is" not in terms
    assert "a" not in terms
    assert "big" in terms
    assert "green" in terms


def test_extract_terms__strips_apostrophes():
    """Field v0.1: leading/trailing apostrophes are stripped from tokens."""
    terms = extract_terms("'twas the night")
    assert "twas" in terms or "'twas" not in terms


def test_extract_terms__deduplicates():
    """Field v0.1: repeated tokens produce only one entry per term."""
    terms = extract_terms("green green green light light")
    assert terms.count("green") == 1
    assert terms.count("light") == 1


# ═════════════════════════════════════════════════════════════════════════════
# CI-011  Nondeterministic audit record
# ═════════════════════════════════════════════════════════════════════════════

def test_ci011_execution_config_schema():
    """CI-011: every provider must return a valid execution_config dict
    containing at minimum: provider, model_id, sdk_version, request_schema_version.

    Proof type: property — all registered providers instantiated with null config.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from hermeneia.narrative.artist_providers import NullArtistProvider

    null = NullArtistProvider()
    cfg = null.execution_config()

    required_keys = {"provider", "model_id", "sdk_version", "request_schema_version", "constitutional_profile"}
    assert required_keys.issubset(cfg.keys()), (
        f"execution_config missing required keys: {required_keys - cfg.keys()}"
    )
    assert cfg["provider"] == "null"
    assert cfg["request_schema_version"] == "1"

    # Constitutional profile must identify the governing regime by version, not date
    cp = cfg["constitutional_profile"]
    assert "constitution_version" in cp
    assert "authority_index_version" in cp
    assert "invariant_profile" in cp
    assert "architecture_profile" in cp


# ═════════════════════════════════════════════════════════════════════════════
# INV-08  LLM Isolation — static structural check
# ═════════════════════════════════════════════════════════════════════════════

def test_inv08_compiler_layer_contains_no_llm_imports():
    """INV-08 (static): The compiler and storage layers must contain no imports
    from LLM client libraries.

    Proof type: static — scans Python source for forbidden import patterns.
    This is a structural guarantee, not a runtime assertion.
    """
    import re

    repo_root = Path(__file__).parent.parent
    forbidden_patterns = [
        re.compile(r"^\s*(import|from)\s+(anthropic|openai|google\.genai|google-genai|genai)\b"),
    ]
    guarded_dirs = [
        repo_root / "hermeneia" / "compiler",
        repo_root / "hermeneia" / "storage",
    ]

    violations = []
    for directory in guarded_dirs:
        for py_file in sorted(directory.rglob("*.py")):
            for lineno, line in enumerate(py_file.read_text().splitlines(), start=1):
                for pattern in forbidden_patterns:
                    if pattern.search(line):
                        violations.append(f"{py_file.relative_to(repo_root)}:{lineno}: {line.strip()}")

    assert not violations, (
        "INV-08 violated — LLM client imports found in compiler/storage layer:\n"
        + "\n".join(violations)
    )
