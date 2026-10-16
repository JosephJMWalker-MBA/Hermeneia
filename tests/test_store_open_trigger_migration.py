"""Regression: concurrent SQLiteStore opens raced the supersession trigger replacement.

Witness: test_upload_source_binding.py::test_concurrent_same_filename_uploads_both_keep_source_bytes
failed under heavy CPU load with statuses=[500, 200]; the 500 body was
"Compilation failed: trigger supersession_relations_old_exists already exists".
Every store open drops and recreates both supersession existence triggers; as
separate autocommit statements, two opens could both drop and then both create,
and between the drops and the creates supersession inserts went unchecked.

This test pauses one open between its drops and its creates and asks what
another connection can see and do there, so it does not depend on load.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from hermeneia.storage.sqlite import SQLiteStore

_TRIGGERS = {"supersession_relations_old_exists", "supersession_relations_new_exists"}


def test_supersession_trigger_replacement_is_invisible_and_exclusive(tmp_path):
    db = tmp_path / "workspace.db"
    SQLiteStore(db).close()
    seen = []

    def probe():
        with closing(sqlite3.connect(db, timeout=0)) as other:
            names = {r[0] for r in other.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name IN (?, ?)",
                sorted(_TRIGGERS),
            )}
            try:
                other.execute("BEGIN IMMEDIATE")
                other.rollback()
                could_interleave = True
            except sqlite3.OperationalError:
                could_interleave = False
        seen.append((names, could_interleave))

    class PausedOpen(SQLiteStore):
        def _apply_schema(self):
            def trace(sql):
                if sql.lstrip().startswith("CREATE TRIGGER supersession_relations_old_exists"):
                    probe()

            self._conn.set_trace_callback(trace)
            super()._apply_schema()
            self._conn.set_trace_callback(None)

    PausedOpen(db).close()
    assert seen == [(_TRIGGERS, False)]
