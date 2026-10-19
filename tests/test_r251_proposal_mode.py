"""#251 contract v1.1: `proposal` mode routes legacy model output through exact steward acceptance.

In `proposal` mode the legacy Architect generator and the onboarding extractor
only propose. Their candidates bind CI-011 provenance, and only the unchanged
P8 accept route commits them, with the P8 acceptance receipt. Lineage
authorship comes from that receipt alone. The legacy prompt is byte-identical
to a golden capture from the unmodified route. Synthetic workspaces under P5
isolation (outbound network blocked); in-process fake providers; no live
model; no real workspace.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace
import unittest.mock as mock

import pytest

import r251_fixtures as fixtures
import synthetic_study_lab as lab
from hermeneia.blueprint_proposals import (
    _CANDIDATE_DOMAIN, CANDIDATE_SCHEMA, canonical_bytes, candidate_id, receipt_from_row, verify_receipt,
)
from hermeneia.legacy_blueprint_candidates import ARCHITECT_SCHEMA, EXTRACT_SCHEMA
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study_lineage import project_study_lineage
from hermeneia.web.app import create_app

DOC = ["The lamp burned all night.", "Nobody asked why it burned.", "The keeper wrote nothing down.",
       "By morning the harbor was empty.", "A second lamp was lit at dusk.", "The ledger records only the oil."]
REPLY = {"title": "The unasked lamp", "thesis": "The lamp records a vigil nobody explains.",
         "sections": [{"claim": "The lamp burns without explanation.", "obs_refs": ["OBS-1", "OBS-2"], "interp_refs": []},
                      {"claim": "The ledger is silent.", "obs_refs": ["OBS-6"], "interp_refs": []}]}
PREVIEWED = {"title": "Previewed proposal", "thesis": "What the steward reviewed.", "sections": [{"claim": "Reviewed claim."}]}
RESAMPLED = {"title": "Resampled proposal", "thesis": "What the second model call produced.", "sections": [{"claim": "Unreviewed claim."}]}
EXECUTION = {"provider": "ollama", "model_id": "fake-architect:1b", "max_tokens": 2048, "sdk_version": "test"}


@pytest.fixture
def isolated(tmp_path):
    with lab.isolated(tmp_path):
        yield tmp_path


class FakeArchitect:
    """An in-process artist provider: scripted replies, recorded prompts, and an execution record."""

    def __init__(self, *replies, execution=EXECUTION):
        self.replies, self.prompts, self._execution = [json.dumps(r) if isinstance(r, dict) else r for r in replies], [], execution

    def render(self, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0)

    def execution_config(self):
        return dict(self._execution)


def chat_provider(*replies, model="fake-extractor"):
    queue, calls = list(replies), []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(queue.pop(0))))])

    return SimpleNamespace(_model=model, _client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))), calls


class Study:
    def __init__(self, workdir: Path, mode: str = "proposal"):
        self.db = workdir / "ws" / "workspace.db"
        SQLiteStore(self.db).close()
        self.app = create_app(db_path=self.db, credential_store=lab._NoCredentials())
        self.app.config["LEGACY_BLUEPRINT_WRITES"] = mode
        self.client = self.app.test_client()
        body = lab._ok(self.client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(DOC)), "synthetic.pdf")},
                                        content_type="multipart/form-data"))
        self.document_id = body["document_id"]
        self.obs = [r[0] for r in self.rows("SELECT id FROM observations ORDER BY page, paragraph, sentence")]

    def rows(self, sql, args=()):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def count(self, table):
        try:
            return self.rows(f"SELECT COUNT(*) FROM {table}")[0][0]
        except sqlite3.OperationalError:
            return 0

    def generate(self, provider, directive="Build from the evidence."):
        with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=provider):
            return self.client.post("/api/architect/generate", json={"directive": directive, "provider": "fake-architect"})

    def decide(self, candidate_id, body):
        with mock.patch("hermeneia.narrative.artist_providers.get_provider", side_effect=AssertionError("no provider at decision")):
            return self.client.post(f"/api/blueprint/proposals/{candidate_id}/{'discard' if body['decision'] == 'discard' else 'accept'}",
                                    json={"candidate_id": candidate_id, **body})

    def lineage(self):
        conn = lab._read_only(self.db)
        try:
            return project_study_lineage(conn)
        finally:
            conn.close()

    def authorship(self, table, identifier):
        return next((i["authorship"] for i in self.lineage()["items"]
                     if i["record"] == {"table": table, "key": {"id": identifier}} and i["event"] == "recorded"), None)

    def verify(self, receipt_id, db=None):
        conn = lab._read_only(db or self.db)
        try:
            return verify_receipt(conn, receipt_id)
        finally:
            conn.close()


@pytest.mark.parametrize("mode", ["legacy", "governed", "proposal"])
def test_the_legacy_prompt_is_byte_identical_to_the_golden_capture(isolated, mode):
    _db, app = fixtures.golden_workspace(isolated, mode)
    provider = FakeArchitect({"title": "T", "thesis": "Th", "sections": [{"claim": "C", "obs_refs": ["OBS-1"], "interp_refs": []}]})
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=provider):
        response = app.test_client().post("/api/architect/generate", json={"directive": fixtures.GOLDEN_DIRECTIVE, "provider": "fake"})
    assert response.status_code == 201, response.get_json()
    assert provider.prompts == [fixtures.GOLDEN_PROMPT.read_text()]
    if mode == "proposal":  # three Interpretations shown, one on an Observation outside the 40 sampled
        view = response.get_json()["binding"]["view"]
        assert (len(view["observations"]), len(view["interpretations"]), view["observations_total"]) == (40, 3, 55)


def test_generation_writes_nothing_and_holds_a_candidate_with_its_ci011_record(isolated):
    study = Study(isolated)
    before = lab._logical_digest(study.db)
    provider = FakeArchitect(REPLY)
    response = study.generate(provider, directive="  Build from the evidence.  ")
    candidate = response.get_json()
    assert response.status_code == 201 and candidate["canonical_status"] == "not_persisted"
    assert lab._logical_digest(study.db) == before and study.count("narrative_blueprints") == 0
    assert candidate["schema"] == ARCHITECT_SCHEMA and candidate["mode"] == "create"
    binding, extraction = candidate["binding"], candidate["extraction"]
    # complete input, direct parents, prompt, provider/model/configuration, timestamps, raw output
    assert binding["directive"] == {"text": "Build from the evidence.",
                                    "sha256": "sha256:" + hashlib.sha256(b"Build from the evidence.").hexdigest()}
    assert [e["id"] for e in binding["basis"]["observations"]] == study.obs
    assert extraction["prompt"] == provider.prompts[0] and extraction["output"] == json.dumps(REPLY)
    assert extraction["execution"] == {**EXECUTION, "provider_id": "fake-architect", "adapter": "FakeArchitect"}
    assert extraction["created_at"] <= extraction["completed_at"]
    assert candidate["proposal"]["blueprint"]["sections"][0]["supporting_observations"] == study.obs[:2]


def test_exact_acceptance_commits_the_held_proposal_with_a_verifiable_receipt(isolated):
    study = Study(isolated)
    candidate = study.generate(FakeArchitect(REPLY)).get_json()
    response = study.decide(candidate["candidate_id"], {"decision": "accept"})
    receipt = response.get_json()
    assert response.status_code == 201 and receipt["origin"] == {"kind": "model_proposed_steward_accepted"}
    held = {k: v for k, v in candidate.items() if k != "canonical_status"}
    assert receipt["candidate"] == held and receipt["acceptance"]["accepted_blueprint"] == held["proposal"]["blueprint"]
    blueprint_id = receipt["result"]["resulting_blueprint_id"]
    (title, source, sections), = study.rows("SELECT title, source, sections FROM narrative_blueprints")
    assert (title, source, json.loads(sections)) == ("The unasked lamp", "proposal-accepted",
                                                      held["proposal"]["blueprint"]["sections"])
    assert study.count("architect_plans") == 1 and study.count("blueprint_proposal_acceptances") == 1
    assert study.verify(receipt["id"]) == {"record_integrity": "valid", "candidate_replay": "verified",
                                           "result_closure": "verified", "model_output": "preserved_not_replayed"}
    assert study.authorship("narrative_blueprints", blueprint_id) == "accepted_model"
    assert study.authorship("blueprint_proposal_acceptances", receipt["id"]) == "accepted_model"
    assert study.decide(candidate["candidate_id"], {"decision": "accept"}).get_json() == receipt  # idempotent


def test_an_edit_is_human_and_preserves_the_model_proposal(isolated):
    study = Study(isolated)
    candidate = study.generate(FakeArchitect(REPLY)).get_json()
    edited = {**candidate["proposal"]["blueprint"], "thesis": "The steward's own thesis."}
    receipt = study.decide(candidate["candidate_id"], {"decision": "edit_and_accept", "blueprint": edited}).get_json()
    assert receipt["origin"] == {"kind": "model_proposed_steward_edited"} and receipt["acceptance"]["edited"] is True
    assert receipt["candidate"]["proposal"]["blueprint"]["thesis"] == REPLY["thesis"]
    assert study.rows("SELECT thesis, source FROM narrative_blueprints") == [("The steward's own thesis.", "proposal-edited")]
    assert study.authorship("narrative_blueprints", receipt["result"]["resulting_blueprint_id"]) == "human"
    assert study.verify(receipt["id"])["candidate_replay"] == "verified"


def test_discard_leaves_no_history_and_no_client_substitution_is_possible(isolated):
    study = Study(isolated)
    candidate = study.generate(FakeArchitect(REPLY)).get_json()
    substituted = study.decide(candidate["candidate_id"], {"decision": "accept", "blueprint": {"title": "Mine", "thesis": "T",
                                                                                              "sections": [{"claim": "C"}]}})
    assert substituted.status_code == 400 and study.count("narrative_blueprints") == 0
    other = "blueprint-proposal-candidate:sha256:" + "0" * 64
    mismatched = study.client.post(f"/api/blueprint/proposals/{other}/accept", json={"decision": "accept", "candidate_id": candidate["candidate_id"]})
    assert mismatched.status_code == 404 and study.count("narrative_blueprints") == 0
    assert study.decide(candidate["candidate_id"], {"decision": "discard"}).get_json()["state"] == "discarded"
    gone = study.decide(candidate["candidate_id"], {"decision": "accept"})
    assert gone.status_code == 404 and gone.get_json()["code"] == "UNKNOWN_CANDIDATE"
    assert study.count("narrative_blueprints") == study.count("blueprint_proposal_acceptances") == 0


def test_a_candidate_whose_bound_evidence_changed_eligibility_is_stale(isolated):
    study = Study(isolated)
    candidate = study.generate(FakeArchitect(REPLY)).get_json()
    for patch in ({"source_role": "reference"}, {"excluded": True}):
        assert study.client.patch(f"/api/documents/{study.document_id}/scope", json=patch).status_code == 200
    response = study.decide(candidate["candidate_id"], {"decision": "accept"})
    assert response.status_code == 409 and response.get_json()["code"] == "STALE_CANDIDATE"
    assert study.count("narrative_blueprints") == study.count("blueprint_proposal_acceptances") == 0


def test_the_extract_preview_is_the_candidate_and_acceptance_commits_exactly_it(isolated):
    study = Study(isolated)
    provider, calls = chat_provider(PREVIEWED, RESAMPLED)
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=provider):
        preview = study.client.post("/api/pipeline/extract-blueprint", json={"text": "A source text.", "provider": "fake", "save": False})
        saved = study.client.post("/api/pipeline/extract-blueprint", json={"text": "A source text.", "provider": "fake", "save": True})
    body = preview.get_json()
    assert preview.status_code == 200 and body["proposed_blueprint"]["title"] == "Previewed proposal"
    assert saved.status_code == 409 and saved.get_json()["code"] == "EXACT_RATIFICATION_REQUIRED" and len(calls) == 1
    candidate = body["candidate"]
    assert candidate["schema"] == EXTRACT_SCHEMA and candidate["binding"]["source_text"]["text"] == "A source text."
    extraction = candidate["extraction"]
    assert calls[0]["messages"] == [{"role": "system", "content": extraction["system_prompt"]},
                                    {"role": "user", "content": extraction["prompt"]}]
    assert {k: extraction["execution"][k] for k in ("provider_id", "interface", "model_id", "max_tokens")} == {
        "provider_id": "fake", "interface": "openai", "model_id": "fake-extractor", "max_tokens": calls[0]["max_tokens"]}
    receipt = study.decide(candidate["candidate_id"], {"decision": "accept"}).get_json()
    assert [r[0] for r in study.rows("SELECT title FROM narrative_blueprints")] == ["Previewed proposal"] and len(calls) == 1
    assert study.verify(receipt["id"])["candidate_replay"] == "verified"
    assert study.authorship("narrative_blueprints", receipt["result"]["resulting_blueprint_id"]) == "accepted_model"


def test_proposal_refusals_hold_nothing_and_write_nothing(isolated):
    study = Study(isolated)
    before = lab._logical_digest(study.db)
    null = study.client.post("/api/architect/generate", json={"directive": "D", "provider": "null"})
    assert (null.status_code, null.get_json()["code"]) == (409, "NO_MODEL_EXECUTED")
    unrecordable = SimpleNamespace(render=mock.Mock(side_effect=AssertionError("must not run")))
    response = study.generate(unrecordable)
    assert (response.status_code, response.get_json()["code"]) == (409, "EXECUTION_NOT_RECORDABLE")
    invalid = study.generate(FakeArchitect({"title": "T", "thesis": "Th", "sections": [{"claim": "C", "obs_refs": ["OBS-99"], "interp_refs": []}]}))
    assert (invalid.status_code, invalid.get_json()["code"]) == (422, "BLUEPRINT_REFERENCE_INVALID")
    assert invalid.get_json()["invalid_references"] == [{"section": 1, "field": "obs_refs", "ref": "OBS-99", "reason": "unshown"}]
    unparseable = study.generate(FakeArchitect("not json"))
    assert (unparseable.status_code, unparseable.get_json()["code"]) == (422, "PROPOSAL_OUTPUT_UNPARSEABLE")
    assert unparseable.get_json()["output"] == "not json"
    failing = FakeArchitect()
    failing.render = mock.Mock(side_effect=RuntimeError("runtime offline"))
    failed = study.generate(failing)
    assert (failed.status_code, failed.get_json()["code"]) == (502, "PROVIDER_FAILED") and "detail" not in failed.get_json()
    placeholder = study.client.post("/api/pipeline/extract-blueprint", json={"text": "T", "provider": "null", "save": False})
    assert (placeholder.status_code, placeholder.get_json()["code"]) == (409, "NO_MODEL_EXECUTED")
    nameless, _calls = chat_provider(PREVIEWED, model=None)
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=nameless):
        anonymous = study.client.post("/api/pipeline/extract-blueprint", json={"text": "T", "provider": "fake", "save": False})
    assert (anonymous.status_code, anonymous.get_json()["code"]) == (409, "EXECUTION_NOT_RECORDABLE") and _calls == []
    assert lab._logical_digest(study.db) == before


def test_a_tampered_legacy_receipt_is_invalid_and_loses_its_authorship(isolated):
    study = Study(isolated)
    candidate = study.generate(FakeArchitect(REPLY)).get_json()
    receipt = study.decide(candidate["candidate_id"], {"decision": "accept"}).get_json()
    blueprint_id = receipt["result"]["resulting_blueprint_id"]
    tampered = isolated / "tampered.db"
    shutil.copy(study.db, tampered)
    conn = sqlite3.connect(tampered)
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='blueprint_proposal_acceptances'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    (stored,), = conn.execute("SELECT receipt_json FROM blueprint_proposal_acceptances").fetchall()
    conn.execute("UPDATE blueprint_proposal_acceptances SET receipt_json = ?", (stored.replace("fake-architect:1b", "other-model:9b"),))
    conn.commit()
    conn.close()
    assert study.verify(receipt["id"], tampered)["record_integrity"] == "invalid"
    conn = lab._read_only(tampered)
    try:
        lineage = project_study_lineage(conn)
    finally:
        conn.close()
    assert not any(i["record"]["table"] == "blueprint_proposal_acceptances" for i in lineage["items"])
    assert next(i["authorship"] for i in lineage["items"]
                if i["record"] == {"table": "narrative_blueprints", "key": {"id": blueprint_id}}) == "unknown"


def test_replay_detects_a_bound_record_that_no_longer_matches(isolated):
    study = Study(isolated)
    candidate = study.generate(FakeArchitect(REPLY)).get_json()
    receipt = study.decide(candidate["candidate_id"], {"decision": "accept"}).get_json()
    altered = isolated / "altered.db"
    shutil.copy(study.db, altered)
    conn = sqlite3.connect(altered)
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='observations'").fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    conn.execute("UPDATE observations SET raw_text = 'Rewritten.' WHERE id = ?", (study.obs[0],))
    conn.commit()
    conn.close()
    assert study.verify(receipt["id"], altered)["candidate_replay"] == "mismatch"


def test_p8_candidate_identity_bytes_are_unchanged():
    body = {"schema": CANDIDATE_SCHEMA, "mode": "create", "binding": {"x": 1}, "extraction": {"y": 2}, "proposal": {"z": 3}}
    expected = "blueprint-proposal-candidate:sha256:" + hashlib.sha256(_CANDIDATE_DOMAIN + canonical_bytes(body)).hexdigest()
    assert candidate_id(body) == expected
    legacy = {**body, "schema": ARCHITECT_SCHEMA}
    assert candidate_id(legacy) != candidate_id({**legacy, "schema": EXTRACT_SCHEMA})


def test_a_stored_legacy_receipt_round_trips_through_the_p8_codec(isolated):
    study = Study(isolated)
    candidate = study.generate(FakeArchitect(REPLY)).get_json()
    receipt = study.decide(candidate["candidate_id"], {"decision": "accept"}).get_json()
    conn = sqlite3.connect(study.db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM blueprint_proposal_acceptances").fetchone()
    finally:
        conn.close()
    assert receipt_from_row(row) == receipt and row["candidate_id"] == candidate["candidate_id"]
