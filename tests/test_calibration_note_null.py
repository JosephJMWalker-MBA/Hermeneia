"""Frozen witness for #245: a null calibration note stays absent, never "None".

`PATCH /api/e10/providers/<participant>/roles/<role>` treats the steward note
as optional: an absent or blank note is stored as null (`... .strip() or
None`), which is also how never-calibrated roles appear in calibration.json.
JSON null means the same thing; it never becomes the steward note "None".
Synthetic workspace; no provider calls.
"""
from __future__ import annotations

import json

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app


class FabricatedNote(AssertionError):
    """Only the observed null-to-"None" note failure is expected here."""


@pytest.fixture
def workspace(tmp_path):
    db = tmp_path / "ws" / "workspace.db"
    SQLiteStore(db).close()
    return db.parent, create_app(db_path=db).test_client()


def _calibrate(client, **note):
    response = client.patch("/api/e10/providers/local/roles/Explorer", json={"status": "approved", **note})
    assert response.status_code == 200, response.get_json()
    return response


def _explorer_notes(ws) -> list:
    store = json.loads((ws / "calibration.json").read_text())
    return [record["role_status"]["Explorer"].get("steward_note") for record in store["records"].values()
            if "Explorer" in record.get("role_status", {})]


@pytest.mark.xfail(strict=True, raises=FabricatedNote,
                   reason="#245: a null note is stored as the steward note 'None'; repair requires its own packet")
def test_null_note_is_stored_as_no_note(workspace):
    ws, client = workspace
    _calibrate(client, note=None)
    if _explorer_notes(ws) != [None]:
        raise FabricatedNote(f"steward_note={_explorer_notes(ws)!r}")


@pytest.mark.parametrize("note", [{}, {"note": ""}, {"note": "   "}])
def test_absent_or_blank_note_is_stored_as_no_note(workspace, note):
    ws, client = workspace
    _calibrate(client, **note)
    assert _explorer_notes(ws) == [None]


def test_stated_note_is_recorded_verbatim(workspace):
    ws, client = workspace
    _calibrate(client, note="Reliable for candidate discovery.")
    assert _explorer_notes(ws) == ["Reliable for candidate discovery."]
