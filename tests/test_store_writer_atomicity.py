"""SQLiteStore record writers defer their commit inside store.atomic().

atomic() promises all or nothing: a writer called inside the block must not
commit on its own, so an exception later in the block rolls its write back.
Outside atomic() every writer still commits at once, so a caller that closes
the store and reads through another connection (the upload route's
source-role write) still sees the row.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Callable

import pytest

from hermeneia.storage.hashing import make_interpretation_id
from hermeneia.storage.sqlite import SQLiteStore
from test_constitutional_p0 import _seed_full_chain

NOW = "2026-10-16T12:00:00+00:00"


class LaterFailure(Exception):
    """Raised inside the block after the write under test."""


@dataclass(frozen=True)
class Writer:
    write: Callable[[SQLiteStore, dict], object]
    probe: str  # SQL for one value the write changes
    prepare: Callable[[SQLiteStore, dict], object] = lambda store, ids: None  # committed first, outside atomic()


@pytest.fixture
def chain(tmp_path):
    store = SQLiteStore(tmp_path / "workspace.db")
    ids = _seed_full_chain(store, include_report=False)
    try:
        yield store, ids
    finally:
        store.close()


def _committed(db: Path, sql: str):
    """Read through a second connection, which sees only committed state."""
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def _interpretation(ids: dict, text: str) -> dict:
    return {
        "id": make_interpretation_id(ids["obs_id"], "literary", text),
        "observation_id": ids["obs_id"],
        "perspective": "literary",
        "perspective_id": None,
        "text": text,
        "evidential_status": "contested",
        "evidence_observation_ids": json.dumps([ids["obs_id"]]),
        "confidence": 0.5,
        "source": "test",
        "created_at": NOW,
    }


WRITERS: dict[str, Writer] = {}

# --- source scope, interpretations, supersession ---

WRITERS["set_document_scope"] = Writer(
    write=lambda store, ids: store.set_document_scope(ids["doc_id"], source_role="reference"),
    probe="SELECT source_role FROM source_documents",
)
WRITERS["insert_interpretation"] = Writer(
    write=lambda store, ids: store.insert_interpretation(_interpretation(ids, "A second reading.")),
    probe="SELECT COUNT(*) FROM interpretations",
)
WRITERS["insert_supersession_relation"] = Writer(
    prepare=lambda store, ids: store.insert_interpretation(_interpretation(ids, "A revised reading.")),
    write=lambda store, ids: store.insert_supersession_relation({
        "old_id": ids["interp_id"],
        "new_id": _interpretation(ids, "A revised reading.")["id"],
        "reason": "Revised.",
        "ratified_at": NOW,
    }),
    probe="SELECT COUNT(*) FROM supersession_relations",
)


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_a_later_failure_inside_atomic_rolls_the_write_back(chain, name):
    store, ids = chain
    writer = WRITERS[name]
    writer.prepare(store, ids)
    before = _committed(store.db_path, writer.probe)
    with pytest.raises(LaterFailure):
        with store.atomic():
            writer.write(store, ids)
            assert store._conn.execute(writer.probe).fetchone()[0] != before  # written inside the block
            assert _committed(store.db_path, writer.probe) == before  # but not committed
            raise LaterFailure
    assert _committed(store.db_path, writer.probe) == before


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_outside_atomic_the_write_commits_at_once(chain, name):
    store, ids = chain
    writer = WRITERS[name]
    writer.prepare(store, ids)
    before = _committed(store.db_path, writer.probe)
    writer.write(store, ids)
    assert _committed(store.db_path, writer.probe) != before
