"""
Compiler kernel tests — proves the ratified invariants hold (Session 002).

Tests:
1. Determinism: identical PDF → identical Observation IDs
2. Append-only: second compile of same PDF inserts nothing
3. Provenance integrity: every observation has a matching provenance record
4. Sentence adjacency: preceding/following chains are consistent
5. SHA-256 document registration: document ID == sha256 of file bytes
6. ID formula: observation ID == sha256(json payload)
"""
import hashlib
import json
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Allow import without package install
sys.path.insert(0, str(Path(__file__).parent.parent))

from hermeneia.compiler.compiler import Compiler
from hermeneia.compiler.observation_compiler import compile_observations
from hermeneia.compiler.paragraph_splitter import Paragraph
from hermeneia.compiler.sentence_splitter import split_sentences
from hermeneia.storage.hashing import make_observation_id, make_source_locator, sha256_file
from hermeneia.storage.sqlite import SQLiteStore

GATSBY_PDF = Path(__file__).parent.parent / "examples" / "gatsby.pdf"
pytestmark = pytest.mark.skipif(
    not GATSBY_PDF.exists(), reason="gatsby.pdf not found in examples/"
)


# ── helpers ──────────────────────────────────────────────────────────────────

def fresh_compiler(tmp_path: Path) -> Compiler:
    return Compiler(db_path=tmp_path / "test.db", build_dir=tmp_path / "build")


# ── 1. Determinism ────────────────────────────────────────────────────────────

def test_identical_pdf_produces_identical_observation_ids(tmp_path):
    """Compiling the same PDF twice must produce byte-for-byte identical IDs."""
    c1 = fresh_compiler(tmp_path / "run1")
    c1.compile(GATSBY_PDF)
    c1.close()

    c2 = fresh_compiler(tmp_path / "run2")
    c2.compile(GATSBY_PDF)
    c2.close()

    db1 = sqlite3.connect(str(tmp_path / "run1" / "test.db"))
    db2 = sqlite3.connect(str(tmp_path / "run2" / "test.db"))

    ids1 = {r[0] for r in db1.execute("SELECT id FROM observations")}
    ids2 = {r[0] for r in db2.execute("SELECT id FROM observations")}

    db1.close()
    db2.close()

    assert ids1 == ids2, "Observation IDs differ between runs on same PDF"
    assert len(ids1) > 0


# ── 2. Append-only ────────────────────────────────────────────────────────────

def test_recompile_same_pdf_inserts_nothing(tmp_path):
    """Second compile of the same PDF must not change the observation count."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    count_after_first = c.repo.observation_count()

    c.compile(GATSBY_PDF)
    count_after_second = c.repo.observation_count()
    c.close()

    assert count_after_first == count_after_second, (
        f"Observation count changed on recompile: "
        f"{count_after_first} → {count_after_second}"
    )


def test_evidence_update_delete_is_rejected(tmp_path):
    """SQLite schema must reject UPDATE and DELETE on observations/provenance."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    db = sqlite3.connect(str(tmp_path / "test.db"))
    obs_id = db.execute("SELECT id FROM observations LIMIT 1").fetchone()[0]
    prov_id = db.execute("SELECT id FROM provenance LIMIT 1").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE observations SET raw_text = 'mutated' WHERE id = ?", (obs_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM observations WHERE id = ?", (obs_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE provenance SET verbatim_text = 'mutated' WHERE id = ?", (prov_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM provenance WHERE id = ?", (prov_id,))
    db.close()


# ── 3. Provenance integrity ───────────────────────────────────────────────────

def test_every_observation_has_provenance(tmp_path):
    """Every observation ID must have a matching provenance record."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    db = sqlite3.connect(str(tmp_path / "test.db"))
    obs_ids = {r[0] for r in db.execute("SELECT id FROM observations")}
    prov_ids = {r[0] for r in db.execute("SELECT observation_id FROM provenance")}
    db.close()

    missing = obs_ids - prov_ids
    assert not missing, f"{len(missing)} observations lack provenance records"


def test_provenance_verbatim_matches_observation(tmp_path):
    """Provenance verbatim_text must equal observation raw_text."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    db = sqlite3.connect(str(tmp_path / "test.db"))
    mismatches = list(db.execute(
        """
        SELECT o.id
        FROM observations o
        JOIN provenance p ON p.observation_id = o.id
        WHERE o.raw_text != p.verbatim_text
        """
    ))
    db.close()

    assert not mismatches, f"{len(mismatches)} provenance/observation text mismatches"


def test_provenance_location_precision_is_sentence(tmp_path):
    """All provenance records must have location_precision = 'sentence'."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    db = sqlite3.connect(str(tmp_path / "test.db"))
    bad = list(db.execute(
        "SELECT id FROM provenance WHERE location_precision != 'sentence'"
    ))
    db.close()

    assert not bad, f"{len(bad)} provenance records with wrong location_precision"


# ── 4. Sentence adjacency ─────────────────────────────────────────────────────

def test_adjacency_chains_are_consistent(tmp_path):
    """If A.following == B, then B.preceding == A."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    db = sqlite3.connect(str(tmp_path / "test.db"))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, preceding_observation_id, following_observation_id "
        "FROM observations"
    ).fetchall()
    db.close()

    id_to_row = {r["id"]: dict(r) for r in rows}
    broken = []
    for row in id_to_row.values():
        fwd = row["following_observation_id"]
        if fwd and fwd in id_to_row:
            if id_to_row[fwd]["preceding_observation_id"] != row["id"]:
                broken.append(row["id"])
    assert not broken, f"{len(broken)} broken adjacency chains"


def test_first_observation_has_no_preceding(tmp_path):
    """The very first observation in the document has no preceding_observation_id."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    db = sqlite3.connect(str(tmp_path / "test.db"))
    first = db.execute(
        "SELECT preceding_observation_id FROM observations "
        "ORDER BY page, paragraph, sentence LIMIT 1"
    ).fetchone()
    db.close()

    assert first[0] is None


# ── 5. SHA-256 document registration ─────────────────────────────────────────

def test_document_id_is_sha256_of_file_bytes(tmp_path):
    """The registered source document ID must equal sha256 of the PDF's raw bytes."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    expected = sha256_file(GATSBY_PDF)

    db = sqlite3.connect(str(tmp_path / "test.db"))
    row = db.execute("SELECT id, file_hash FROM source_documents").fetchone()
    db.close()

    assert row is not None
    assert row[0] == expected, "Source document ID != sha256 of file"
    assert row[1] == expected, "Source document file_hash != sha256 of file"


# ── 6. Observation ID formula ─────────────────────────────────────────────────

def test_observation_id_matches_formula(tmp_path):
    """Spot-check stored IDs match the constitutional occurrence formula."""
    c = fresh_compiler(tmp_path)
    c.compile(GATSBY_PDF)
    c.close()

    doc_hash = sha256_file(GATSBY_PDF)
    db = sqlite3.connect(str(tmp_path / "test.db"))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, source_locator, raw_text FROM observations "
        "ORDER BY page, paragraph, sentence LIMIT 10"
    ).fetchall()
    db.close()

    for row in rows:
        expected_id = make_observation_id(doc_hash, row["source_locator"], row["raw_text"])
        assert row["id"] == expected_id


# ── Unit tests: sentence splitter ─────────────────────────────────────────────

def test_sentence_splitter_basic():
    text = "The green light blinked. Daisy waved. He stood there alone."
    result = split_sentences(text)
    assert len(result) == 3
    assert result[0].startswith("The green")
    assert result[1].startswith("Daisy")
    assert result[2].startswith("He stood")


def test_sentence_splitter_abbreviation_not_split():
    text = "Dr. Eckleburg watched. The eyes did not move."
    result = split_sentences(text)
    # "Dr." should not split
    assert len(result) == 2
    assert "Dr." in result[0]


def test_sentence_splitter_question_and_exclamation():
    text = "Was it real? Of course! She smiled."
    result = split_sentences(text)
    assert len(result) == 3


def test_sentence_splitter_single_sentence():
    text = "He had not once ceased looking at Daisy."
    result = split_sentences(text)
    assert len(result) == 1
    assert result[0] == text


def test_sentence_splitter_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


# ── Unit tests: ID generation ─────────────────────────────────────────────────

def test_make_observation_id_deterministic():
    id1 = make_observation_id("abc123", "page:1:block:1:sentence:1", "text")
    id2 = make_observation_id("abc123", "page:1:block:1:sentence:1", "text")
    assert id1 == id2


def test_make_observation_id_different_positions():
    id1 = make_observation_id("abc123", "page:1:block:1:sentence:1", "same text")
    id2 = make_observation_id("abc123", "page:1:block:1:sentence:2", "same text")
    assert id1 != id2


def test_make_observation_id_formula():
    """Verify the exact constitutional occurrence formula."""
    payload = json.dumps(
        {
            "raw_text": "raw",
            "source_hash": "abc",
            "source_locator": "page:1:block:1:sentence:1",
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert make_observation_id("abc", "page:1:block:1:sentence:1", "raw") == expected
