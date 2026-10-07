"""Promoted regressions for #220 and #233: read paths read historical and read-only states as they are.

Read-only operations have zero side effects: a lineage inspection or other
read shall not create or migrate schemas or seed profiles (Constitution
Art. XII; CI-012; 15_Storage.md Read-Only Storage Rule). So the CLI pipeline
trace and profile listing work on a read-only workspace and create nothing on
an older one, and the proof-PDF reader answers its documented 404 on a
workspace without authoring tables. Commit 90c1acb preserves the negative
versions; the repair demonstrated strict unexpected passes before the expected
failures were removed. Synthetic workspaces only.
"""
from __future__ import annotations

import os
import sqlite3
import stat

import pytest

from hermeneia.cli.inspector import cmd_trace
from hermeneia.cli.profile_cmd import cmd_profile_list
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain

AUTHORING_TABLES = ("authoring_decisions", "authoring_drafts", "authoring_outcomes", "authoring_proofs",
                    "authoring_proposals", "authoring_requests", "publication_artifacts", "publication_works")
LATER_LAYER_TABLES = ("architect_plan_paragraphs", "architect_plans", "rendered_narratives", "expression_profiles")


class ReadPathSideEffect(AssertionError):
    """Only the observed read-path failures are expected here."""


@pytest.fixture
def workspace(tmp_path):
    db = tmp_path / "hermeneia.db"
    store = SQLiteStore(db)
    _seed_full_chain(store)
    store.close()
    return db


def _schema(db) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db)
    try:
        return set(conn.execute("SELECT type, name FROM sqlite_master"))
    finally:
        conn.close()


def _drop(db, tables) -> None:
    conn = sqlite3.connect(db)
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.close()


def test_trace_and_profile_list_work_on_a_read_only_workspace(workspace, capsys):
    os.chmod(workspace, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    try:
        cmd_trace("OBS-1", bundle_or_db=str(workspace))
        cmd_profile_list(bundle_or_db=str(workspace))
    except sqlite3.OperationalError as exc:
        raise ReadPathSideEffect(str(exc)) from exc
    finally:
        os.chmod(workspace, stat.S_IRUSR | stat.S_IWUSR)
    out = capsys.readouterr().out
    assert "Pipeline Trace: OBS-1" in out and "Expression Profiles" in out


def test_trace_and_profile_list_create_no_schema_on_an_older_workspace(workspace, capsys):
    _drop(workspace, LATER_LAYER_TABLES)
    before = _schema(workspace)
    cmd_trace("OBS-1", bundle_or_db=str(workspace))
    cmd_profile_list(bundle_or_db=str(workspace))
    created = _schema(workspace) - before
    if created:
        raise ReadPathSideEffect(f"read paths created {sorted(created)}")
    assert "Pipeline Trace: OBS-1" in capsys.readouterr().out


def test_proof_pdf_is_a_structured_404_without_authoring_tables(workspace):
    _drop(workspace, AUTHORING_TABLES)
    client = create_app(db_path=workspace).test_client()
    response = client.get("/api/authoring/proofs/unknown/pdf")
    body = response.get_json(silent=True) or {}
    if response.status_code != 404 or body.get("code") != "NO_PROOF_PDF":
        raise ReadPathSideEffect(f"{response.status_code} {response.mimetype}")
