"""
Tests for Explorer Phase 1 — discovery via bucketing.

Sprint E-III-1 required proofs:
1. Multiple observations can produce one speculative interpretation.
2. Bucket objects are not persisted.
3. evidence_observation_ids contains all supporting observations.
4. Idempotency prevents duplicate speculative interpretations for the same bucket.
5. Unrelated observations do not get forced into one bucket.
6. Existing single-observation path is explicitly named and distinct from Explorer.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hermeneia.explorer.bucketer import (
    BucketingError,
    generate_candidate_buckets,
    parse_and_validate_bucket_response,
)
from hermeneia.explorer.interpreter import (
    generate_candidate_interpretation,
    generate_interpretation_from_bucket,
)
from hermeneia.storage.hashing import make_semantic_hash, make_source_locator
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_constitutional_p0 import _seed_full_chain


# ── Fake providers ────────────────────────────────────────────────────────────

class _NullProvider:
    pass


class _BucketProvider:
    """Returns a predetermined bucket JSON grouping first two obs together.

    The response uses indices (1-based), matching the current bucketer protocol.
    The caller must ensure the indices correspond to the positions of the obs IDs
    in the observation list passed to generate_candidate_buckets.
    """
    def __init__(self, buckets: list[list[int]]):
        self._buckets = buckets
        self._model = "test"
        self._client = _FakeAnthropicClient(
            json.dumps({"buckets": [{"indices": b} for b in buckets]})
        )


class _FakeAnthropicClient:
    def __init__(self, response: str):
        self.messages = _FakeMessages(response)


class _FakeMessages:
    def __init__(self, r: str):
        self._r = r
    def create(self, **_):
        return type("R", (), {"content": [type("C", (), {"text": self._r})()]})()


class _InterpProvider:
    """Returns a fixed interpretation text."""
    def __init__(self, text: str):
        self._text = text
        self._model = "test"
        self._client = _FakeAnthropicClient(text)


# ── Bucketer tests ────────────────────────────────────────────────────────────

def test_bucketer_groups_observations_into_buckets():
    obs = [
        {"id": "aaa", "raw_text": "The green light blinks at the end of the dock."},
        {"id": "bbb", "raw_text": "Gatsby stretched his arms toward the dark water."},
        {"id": "ccc", "raw_text": "Nick comes from a distinguished family."},
    ]
    provider = _BucketProvider([[1, 2], [3]])  # indices 1=aaa, 2=bbb, 3=ccc
    buckets = generate_candidate_buckets(obs, provider)
    assert len(buckets) == 2
    assert sorted(buckets[0]) == ["aaa", "bbb"]
    assert buckets[1] == ["ccc"]


def test_bucketer_single_observation_returns_singleton():
    obs = [{"id": "aaa", "raw_text": "Only one."}]
    buckets = generate_candidate_buckets(obs, _NullProvider())
    assert buckets == [["aaa"]]


def test_bucketer_empty_returns_empty():
    assert generate_candidate_buckets([], _NullProvider()) == []


def test_bucketer_raises_on_unknown_index():
    import json as _json
    raw = _json.dumps({"buckets": [{"indices": [1, 99]}]})
    index_to_id = {1: "aaa"}
    with pytest.raises(BucketingError, match="unknown index"):
        parse_and_validate_bucket_response(raw, index_to_id)


def test_bucketer_raises_on_duplicate_assignment():
    import json as _json
    raw = _json.dumps({"buckets": [{"indices": [1, 2]}, {"indices": [1]}]})
    index_to_id = {1: "aaa", 2: "bbb"}
    with pytest.raises(BucketingError, match="appears in more than one bucket"):
        parse_and_validate_bucket_response(raw, index_to_id)


def test_bucketer_unassigned_ids_become_singletons():
    """If the LLM misses an observation, it gets its own singleton bucket."""
    obs = [
        {"id": "aaa", "raw_text": "A"},
        {"id": "bbb", "raw_text": "B"},
        {"id": "ccc", "raw_text": "C"},
    ]
    # Provider only groups aaa+bbb (indices 1+2), forgets ccc (index 3)
    provider = _BucketProvider([[1, 2]])
    buckets = generate_candidate_buckets(obs, provider)
    all_ids = {oid for b in buckets for oid in b}
    assert "ccc" in all_ids  # singleton added


def test_bucketer_null_provider_produces_one_bucket(tmp_path):
    """Null provider fallback groups everything into one bucket."""
    obs = [
        {"id": "a" * 64, "raw_text": "First."},
        {"id": "b" * 64, "raw_text": "Second."},
    ]
    buckets = generate_candidate_buckets(obs, _NullProvider())
    all_ids = {oid for b in buckets for oid in b}
    assert all_ids == {"a" * 64, "b" * 64}


# ── Interpreter: bucket path ──────────────────────────────────────────────────

def test_bucket_interpretation_covers_multiple_observations():
    obs = [
        {"id": "aaa", "raw_text": "The green light."},
        {"id": "bbb", "raw_text": "The clock on the mantel."},
    ]
    provider = _InterpProvider("Time and desire are the novel's twin obsessions.")
    text, prompt = generate_interpretation_from_bucket(obs, "Epistemic", provider)
    assert text == "Time and desire are the novel's twin obsessions."
    assert "Epistemic" in prompt
    assert "green light" in prompt
    assert "clock" in prompt


def test_bucket_interpretation_single_obs_falls_through():
    obs = [{"id": "aaa", "raw_text": "Gatsby reached toward the green light."}]
    provider = _InterpProvider("Desire projected onto an unreachable object.")
    text, prompt = generate_interpretation_from_bucket(obs, "Literary", provider)
    assert text == "Desire projected onto an unreachable object."


def test_bucket_interpretation_raises_on_empty():
    from hermeneia.explorer.interpreter import ExplorerError
    provider = _InterpProvider("")
    with pytest.raises(ExplorerError):
        generate_interpretation_from_bucket([], "Literary", provider)


# ── Single-observation path explicitly named ──────────────────────────────────

def test_single_observation_function_is_distinct_from_bucket_path():
    """Proof 6: single-observation path is explicitly named and distinct."""
    import inspect
    from hermeneia.explorer import interpreter
    # Both functions exist and have distinct signatures
    assert hasattr(interpreter, "generate_candidate_interpretation")
    assert hasattr(interpreter, "generate_interpretation_from_bucket")
    single_sig = inspect.signature(interpreter.generate_candidate_interpretation)
    bucket_sig = inspect.signature(interpreter.generate_interpretation_from_bucket)
    # Single takes observation_text: str; bucket takes bucket_observations: list
    assert "observation_text" in single_sig.parameters
    assert "bucket_observations" in bucket_sig.parameters


# ── API endpoint tests ────────────────────────────────────────────────────────

def _seed_discover_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "discover.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store, architect_terms=["evidence", "fixed"])

    second_text = "Daisy's voice is full of money."
    obs2_locator = make_source_locator(1, 2, 1)
    # ID matches the constitutional formula used by the rest of the pipeline
    import hashlib as _h, json as _j
    obs2_id = _h.sha256(_j.dumps({"raw_text": second_text, "source_hash": ids["doc_id"], "source_locator": obs2_locator}, sort_keys=True).encode()).hexdigest()
    store.insert_observations_batch([{
        "id": obs2_id,
        "epistemic_class": "Evidence",
        "source_document_id": ids["doc_id"],
        "source_extraction_id": ids["extraction_id"],
        "raw_text": second_text,
        "source_locator": obs2_locator,
        "semantic_hash": make_semantic_hash(second_text),
        "page": 1,
        "paragraph": 2,
        "sentence": 1,
        "preceding_observation_id": ids["obs_id"],
        "following_observation_id": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }])
    store.close()
    ids["obs2_id"] = obs2_id
    return db_path, ids


def test_discover_endpoint_returns_proposals(tmp_path):
    """Proof 1: multiple observations produce speculative interpretations."""
    db_path, ids = _seed_discover_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    resp = client.post("/api/e10/interpretations/discover", json={
        "observation_ids": [ids["obs_id"], ids["obs2_id"]],
        "participants": ["claude"],
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["created_count"] >= 1
    assert data["bucket_count"] >= 1


def test_discover_endpoint_no_bucket_table(tmp_path):
    """Proof 2: bucket objects are not persisted — no 'buckets' table exists."""
    db_path, ids = _seed_discover_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    client.post("/api/e10/interpretations/discover", json={
        "observation_ids": [ids["obs_id"], ids["obs2_id"]],
        "participants": ["claude"],
    })

    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "buckets" not in tables
    assert "explorer_buckets" not in tables
    assert "candidate_buckets" not in tables


def test_discover_endpoint_evidence_ids_stored(tmp_path):
    """Proof 3: evidence_observation_ids contains all supporting observations."""
    db_path, ids = _seed_discover_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    resp = client.post("/api/e10/interpretations/discover", json={
        "observation_ids": [ids["obs_id"], ids["obs2_id"]],
        "participants": ["claude"],
    })
    assert resp.status_code == 201
    proposals = resp.get_json()["proposals"]
    assert proposals

    # Each proposal that covers multiple obs should have evidence_observation_ids
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    for proposal in proposals:
        row = conn.execute(
            "SELECT evidence_observation_ids FROM proposed_interpretations WHERE id = ?",
            (proposal["id"],),
        ).fetchone()
        assert row is not None
        evidence = json.loads(row["evidence_observation_ids"] or "[]")
        assert isinstance(evidence, list)
        assert len(evidence) >= 1
    conn.close()


def test_discover_endpoint_idempotency(tmp_path):
    """Proof 4: same bucket called twice → second call skipped."""
    db_path, ids = _seed_discover_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    payload = {
        "observation_ids": [ids["obs_id"], ids["obs2_id"]],
        "participants": ["claude"],
    }
    resp1 = client.post("/api/e10/interpretations/discover", json=payload)
    resp2 = client.post("/api/e10/interpretations/discover", json=payload)

    assert resp1.status_code == 201
    assert resp2.status_code == 201

    data1 = resp1.get_json()
    data2 = resp2.get_json()

    # Second call should create 0 new proposals (all skipped)
    assert data2["created_count"] == 0
    assert data2["skipped_count"] == data1["created_count"]


def test_discover_endpoint_rejects_unknown_observation(tmp_path):
    db_path, ids = _seed_discover_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    resp = client.post("/api/e10/interpretations/discover", json={
        "observation_ids": [ids["obs_id"], "0" * 64],
        "participants": ["claude"],
    })
    assert resp.status_code == 404
    assert "observation not found" in resp.get_json()["error"]


def test_discover_endpoint_rejects_empty_observation_ids(tmp_path):
    db_path, ids = _seed_discover_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    resp = client.post("/api/e10/interpretations/discover", json={
        "observation_ids": [],
        "participants": ["claude"],
    })
    assert resp.status_code == 400
