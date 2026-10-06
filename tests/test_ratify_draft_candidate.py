"""Promoted regressions for #231 and #235: ratification records what the steward judged.

A ratified Artist draft is the persisted output of a nondeterministic
invocation, so its record keeps that invocation's provider, model,
configuration and timestamp (CI-011), and the bytes saved are the bytes the
server previewed. When the record does not hold the submitted bytes, the API
says so and the Reader does not claim verbatim recording (`ratify_draft`:
"It must save the artifact the steward actually saw and judged"). Only a
server-held preview can be ratified (06_Ontology.md RenderedNarrative).
Commits 4738bbf and 4eb0970 preserve the negative versions; the repairs
demonstrated strict unexpected passes before the expected failures were removed.
Fake in-process Artists; the real `_crRatifyDraft` runs under Node.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from hermeneia.narrative import artist_service
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_constitutional_p0 import _seed_full_chain
from test_evidence_board_ui import _extract_function

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"
PROFILE = "literary-en"
TEXT = "Rendered prose from the local model.\n"
CONFIG = {"provider": "ollama-local", "model_id": "qwen3:4b", "max_tokens": 1024, "temperature": 0.7,
          "sdk_version": "0.6.2", "request_schema_version": "1"}


class RatificationRecordFailure(AssertionError):
    """Only the observed ratification-record failures are expected here."""


class FakeLocalArtist:
    provider_name = "ollama-local"

    def render(self, prompt: str) -> str:
        return TEXT

    def execution_config(self) -> dict:
        return dict(CONFIG)


class ScriptedArtist:
    """In-process Artist that renders the given texts in order under one provider name."""

    def __init__(self, provider_name: str, texts: list[str]):
        self.provider_name = provider_name
        self._texts = texts

    def render(self, prompt: str) -> str:
        return self._texts.pop(0)

    def execution_config(self) -> dict:
        return {"provider": self.provider_name, "model_id": "scripted-artist", "max_tokens": 1024}


def preview_candidates(client, monkeypatch, plan_id: str, texts: list[str], *,
                       provider: str = "ratify-test", profile: str | None = PROFILE) -> list[dict]:
    """Preview each text through the real preview route; each result names its server-held candidate."""
    artist = ScriptedArtist(provider, list(texts))
    monkeypatch.setattr(artist_service, "get_provider", lambda *_a, **_k: artist)
    previews = []
    for _ in texts:
        response = client.post("/api/pipeline/preview-artist", json={
            "plan_id": plan_id, "provider": provider, **({"profile": profile} if profile else {})})
        assert response.status_code == 200, response.get_data(as_text=True)
        previews.append(response.get_json())
    return previews


def ratify_candidate(client, preview: dict):
    """Ratify exactly what the Reader sends for a previewed draft."""
    return client.post("/api/pipeline/ratify-draft", json={
        "plan_id": preview["plan_id"], "provider": preview["provider"], "text": preview["text"],
        "candidate_id": preview["candidate_id"],
        **({"profile_slug": preview["profile_slug"]} if preview["profile_slug"] else {})})


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    db_path = tmp_path / "ratify.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    monkeypatch.setattr(artist_service, "get_provider", lambda *_a, **_k: FakeLocalArtist())
    return db_path, ids, create_app(db_path=db_path).test_client()


def _preview(client, ids) -> dict:
    response = client.post("/api/pipeline/preview-artist",
                           json={"plan_id": ids["plan_id"], "profile": PROFILE, "provider": "ollama-local"})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def _ratify(client, ids, preview: dict, text: str | None = None):
    return client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"], "provider": preview["provider"], "profile_slug": PROFILE,
        "text": preview["text"] if text is None else text, "candidate_id": preview.get("candidate_id")})


def _narrative(db, narrative_id: str) -> tuple[str, dict]:
    text, config = sqlite3.connect(db).execute(
        "SELECT text, execution_config FROM rendered_narratives WHERE id = ?", (narrative_id,)).fetchone()
    return text, json.loads(config)


def _narrative_texts(db) -> list[str]:
    return [r[0] for r in sqlite3.connect(db).execute("SELECT text FROM rendered_narratives")]


def _render_ratify_result(status: int, server_json: dict, draft_text: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for the ratify result test")
    function = _extract_function(INDEX.read_text(), "async function _crRatifyDraft(")
    script = r"""
const els = {'cr-draft-ratify-btn': {disabled:false, textContent:'Ratify & Save Draft'}, 'cr-draft-ratify-result': {innerHTML:''}};
const document = {getElementById: id => els[id] || null};
const x = s => String(s);
const fetch = async () => ({ok: RESP_OK, json: async () => (RESP_JSON)});
let _crLastArtistDraft = DRAFT;
""" + function + r"""
_crRatifyDraft().then(() => console.log(
  els['cr-draft-ratify-result'].innerHTML.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()));
"""
    draft = {"text": draft_text, "planId": server_json.get("plan_id"), "provider": "ollama-local",
             "profileSlug": PROFILE, "profileName": PROFILE, "candidateId": None}
    script = (script.replace("RESP_OK", json.dumps(status < 400)).replace("RESP_JSON", json.dumps(server_json))
              .replace("DRAFT", json.dumps(draft)))
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_ratified_preview_keeps_the_invocations_execution_record(seeded):
    db, ids, client = seeded
    response = _ratify(client, ids, _preview(client, ids))
    assert response.status_code == 201, response.get_data(as_text=True)
    text, config = _narrative(db, response.get_json()["id"])
    assert text == TEXT
    if any(config.get(key) != value for key, value in CONFIG.items()) or not config.get("execution_timestamp"):
        raise RatificationRecordFailure(f"execution_config={config}")


def test_candidate_ratification_refuses_text_the_preview_did_not_produce(seeded):
    db, ids, client = seeded
    response = _ratify(client, ids, _preview(client, ids), text="Text the provider never produced.")
    if response.status_code < 400 or "Text the provider never produced." in _narrative_texts(db):
        raise RatificationRecordFailure(f"{response.status_code} {response.get_json()}")


def test_already_ratified_response_says_whether_the_record_holds_the_submitted_text(seeded, monkeypatch):
    _db, ids, client = seeded
    draft_a, draft_b = preview_candidates(client, monkeypatch, ids["plan_id"],
                                          ["Draft A the steward first approved.", "Draft B, a different text."])
    first = ratify_candidate(client, draft_a)
    second = ratify_candidate(client, draft_b)
    assert (first.status_code, second.status_code) == (201, 200)
    assert second.get_json()["status"] == "already_ratified"
    if first.get_json().get("matches_submitted") is not True or second.get_json().get("matches_submitted") is not False:
        raise RatificationRecordFailure(f"first={first.get_json()} second={second.get_json()}")


def test_reader_does_not_claim_verbatim_recording_of_unsaved_text(seeded, monkeypatch):
    _db, ids, client = seeded
    draft_a, draft_b = preview_candidates(client, monkeypatch, ids["plan_id"],
                                          ["Draft A the steward first approved.", "Draft B, a different text."])
    assert ratify_candidate(client, draft_a).status_code == 201
    second = ratify_candidate(client, draft_b)
    shown = _render_ratify_result(second.status_code, second.get_json(), "Draft B, a different text.")
    if "recorded verbatim" in shown or "not saved" not in shown:
        raise RatificationRecordFailure(shown)


def test_reader_confirms_verbatim_recording_of_saved_text(seeded, monkeypatch):
    _db, ids, client = seeded
    [draft_a] = preview_candidates(client, monkeypatch, ids["plan_id"], ["Draft A the steward first approved."])
    first = ratify_candidate(client, draft_a)
    shown = _render_ratify_result(first.status_code, first.get_json(), "Draft A the steward first approved.")
    assert "recorded verbatim" in shown, shown


# ── #235 direct-API boundary ─────────────────────────────────────────────────
# 06_Ontology.md: a RenderedNarrative is expression produced by an ArtistProvider
# from ArchitectPlan, ExpressionProfile and ArtistProvider invocation metadata,
# and preserves that execution context. The server can only record an
# invocation it observed, so text without a server-held preview is not ratified.

def test_ratification_without_a_server_held_candidate_persists_nothing(seeded):
    db, ids, client = seeded
    before = _narrative_texts(db)
    response = client.post("/api/pipeline/ratify-draft", json={
        "plan_id": ids["plan_id"], "provider": "ollama-local", "profile_slug": PROFILE,
        "text": "Text whose generation the server never observed."})
    if response.status_code < 400 or _narrative_texts(db) != before:
        raise RatificationRecordFailure(f"{response.status_code} {response.get_json()}")


def test_ratify_draft_service_requires_the_observed_invocation_record(seeded):
    db, ids, _client = seeded
    before = _narrative_texts(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        artist_service.ratify_draft(ids["plan_id"], conn, provider="ollama-local", profile_slug=PROFILE,
                                    text="Text whose generation the server never observed.")
    except artist_service.ArtistRenderError:
        pass
    finally:
        conn.close()
    if _narrative_texts(db) != before:
        raise RatificationRecordFailure("ratify_draft persisted a narrative without an execution record")
