"""R-P8-LEGACY-1 (#251) containment: the gate, exact references and provider labels.

docs/design/r251-legacy-blueprint-remediation-v1.md §4, §6 and §7. The
gate defaults to legacy, so current Reader behavior is unchanged until the
owner enables governed or disabled. Governed refuses inexact references and
placeholder output. Disabled also stops model-direct generation before any
provider call. Extract responses always say whether a model ran. Synthetic
workspaces; in-process fakes; no network.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
import unittest.mock as mock

import pytest

from hermeneia.compiler import blueprint_extractor
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from test_r251_legacy_blueprint_witnesses import DOC, PREVIEWED, Study, _chat_replies, isolated  # noqa: F401

SHOWN_A, SHOWN_B, UNIQUE = "abcdef12" + "0" * 56, "abcdef12" + "1" * 56, "1234abcd" + "2" * 56
HIDDEN = "deadbee5" + "3" * 56


def _interpretation(study: Study, identifier: str, observation_id: str, text: str) -> None:
    store = SQLiteStore(study.db)
    try:
        store.insert_interpretation({"id": identifier, "observation_id": observation_id, "perspective": "Synthetic",
                                     "text": text, "evidential_status": "speculative",
                                     "evidence_observation_ids": json.dumps([observation_id]), "confidence": "human",
                                     "source": "steward-authored", "created_at": "2026-10-10T00:00:00+00:00"})
    finally:
        store.close()


@pytest.fixture
def interpreted(isolated):  # noqa: F811
    """Doc A shown; doc B excluded. Two shown Interpretations share a prefix, one is unique, one is on B."""
    study = Study(isolated, "governed", [DOC, ["The bell rang twice at noon.", "The square fell silent."]])
    doc_b = study.rows("SELECT id FROM source_documents ORDER BY registered_at DESC LIMIT 1")[0][0]
    b_obs = study.rows("SELECT id FROM observations WHERE source_document_id = ?", (doc_b,))[0][0]
    a_obs = [o for o in study.obs if o != b_obs]
    _interpretation(study, SHOWN_A, a_obs[0], "A vigil.")
    _interpretation(study, SHOWN_B, a_obs[1], "An absence.")
    _interpretation(study, UNIQUE, a_obs[2], "A silence.")
    _interpretation(study, HIDDEN, b_obs, "A bell reading.")
    lab_client = create_app(db_path=study.db).test_client()
    for patch in ({"source_role": "reference"}, {"excluded": True}):
        assert lab_client.patch(f"/api/documents/{doc_b}/scope", json=patch).status_code == 200
    return study


def test_gate_defaults_to_legacy_and_fails_closed(tmp_path, monkeypatch):
    def mode(env):
        if env is None:
            monkeypatch.delenv("HERMENEIA_LEGACY_BLUEPRINT_WRITES", raising=False)
        else:
            monkeypatch.setenv("HERMENEIA_LEGACY_BLUEPRINT_WRITES", env)
        return create_app(db_path=tmp_path / str(env) / "w.db").config["LEGACY_BLUEPRINT_WRITES"]

    assert [mode(None), mode("legacy"), mode("governed"), mode("proposal"), mode("disabled"), mode("enabled")] == [
        "legacy", "legacy", "governed", "proposal", "disabled", "disabled"]


def test_governed_itemizes_every_inexact_reference_and_writes_nothing(interpreted):
    response, _ = interpreted.generate({"title": "T", "thesis": "Th", "sections": [
        {"claim": "One", "obs_refs": ["OBS-1", "INTERP-1234abcd", "OBS-9"], "interp_refs": ["INTERP-abcdef12", "OBS-2"]},
        {"claim": "", "obs_refs": ["ignored"], "interp_refs": []},
        {"claim": "Three", "obs_refs": ["OBS-1"], "interp_refs": ["INTERP-deadbee5", "INTERP-00000000", "I1"]}]})
    body = response.get_json()
    assert response.status_code == 422 and body["code"] == "BLUEPRINT_REFERENCE_INVALID"
    assert [(r["section"], r["field"], r["ref"], r["reason"]) for r in body["invalid_references"]] == [
        (1, "obs_refs", "INTERP-1234abcd", "wrong_type"), (1, "obs_refs", "OBS-9", "unshown"),
        (1, "interp_refs", "INTERP-abcdef12", "ambiguous"), (1, "interp_refs", "OBS-2", "wrong_type"),
        (3, "interp_refs", "INTERP-deadbee5", "excluded"), (3, "interp_refs", "INTERP-00000000", "unknown"),
        (3, "interp_refs", "I1", "unresolved")]
    assert not interpreted.blueprints() and interpreted.plans() == 0


def test_governed_writes_exact_references_exactly_as_legacy_does(isolated):  # noqa: F811
    reply = {"title": "T", "thesis": "Th", "sections": [{"claim": "C", "obs_refs": ["OBS-1", " OBS-2 "], "interp_refs": []}]}
    written = {}
    for mode in ("legacy", "governed"):
        study = Study(isolated / mode, mode, [DOC])
        response, _ = study.generate(reply)
        assert response.status_code == 201
        written[mode] = (response.get_json(), study.blueprints()[0]["sections"], study.plans())
    assert written["legacy"] == written["governed"]


def test_disabled_stops_generation_before_any_provider_call_or_write(isolated):  # noqa: F811
    study = Study(isolated, "disabled", [DOC])
    response, prompts = study.generate({"title": "T", "thesis": "Th", "sections": [{"claim": "C", "obs_refs": ["OBS-1"]}]})
    assert response.status_code == 403 and response.get_json()["code"] == "LEGACY_DIRECT_WRITE_DISABLED"
    assert prompts == [] and not study.blueprints()


@pytest.mark.parametrize("mode", ["legacy", "governed", "proposal", "disabled"])
def test_extract_responses_say_whether_a_model_ran(isolated, mode):  # noqa: F811
    study = Study(isolated, mode, [DOC])
    provider, _calls = _chat_replies(PREVIEWED)
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=provider):
        executed = study.client.post("/api/pipeline/extract-blueprint", json={"text": "A source.", "provider": "fake", "save": False})
    assert executed.status_code == 200 and executed.get_json()["execution"] == {
        "provider": "fake", "interface": "openai", "model_executed": True, "placeholder": False}
    placeholder = study.client.post("/api/pipeline/extract-blueprint", json={"text": "A source.", "provider": "null", "save": False})
    body = placeholder.get_json()
    assert body["execution"] == {"provider": "null", "interface": "placeholder", "model_executed": False, "placeholder": True}
    if mode == "legacy":  # unchanged by default, but labelled
        assert placeholder.status_code == 200 and body["proposed_blueprint"]["title"] == "Extracted Blueprint"
    else:
        assert placeholder.status_code == 409 and body["code"] == "NO_MODEL_EXECUTED" and "proposed_blueprint" not in body


def test_disabled_keeps_preview_and_exact_ratification(isolated):  # noqa: F811
    study = Study(isolated, "disabled", [DOC])
    provider, _calls = _chat_replies(PREVIEWED)
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=provider):
        preview = study.client.post("/api/pipeline/extract-blueprint", json={"text": "A source.", "provider": "fake", "save": False})
    committed = study.client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": preview.get_json()["proposed_blueprint"]})
    assert committed.status_code == 201 and [b["title"] for b in study.blueprints()] == ["Previewed proposal"]


@pytest.mark.parametrize("provider,interface", [
    (SimpleNamespace(_client=SimpleNamespace(messages=object())), "anthropic"),
    (SimpleNamespace(_client=SimpleNamespace(chat=object())), "openai"),
    (SimpleNamespace(_model_obj=object()), "gemini"),
    (object(), "placeholder"),
])
def test_provider_interface_is_the_branch_the_extractor_takes(provider, interface):
    assert blueprint_extractor.provider_interface(provider) == interface
    if interface == "placeholder":
        assert json.loads(blueprint_extractor._call_provider(provider, "s", "u"))["title"] == "Extracted Blueprint"
