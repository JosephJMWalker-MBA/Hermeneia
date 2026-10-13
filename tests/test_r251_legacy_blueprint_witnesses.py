"""Permanent negative regression witnesses for R-P8-LEGACY-1 (#251).

The six reproduced risks of the legacy model-to-canonical Blueprint write
routes are kept as witnesses, per docs/design/r251-legacy-blueprint-remediation-v1.md
§2. Each witness reproduces the exact defect recorded in #251 on a synthetic
workspace with an in-process fake provider. When it sees that defect it raises
the risk's own AssertionError subclass; otherwise it asserts the governed
outcome. A configuration in which the risk is still exposed is a strict
expected failure restricted to that class, so no unrelated failure is masked.
A marker is removed only after a repair demonstrates a strict unexpected
pass. The evidence is never weakened. P5 isolation; no network; no real
workspace.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest.mock as mock

import pytest

import synthetic_study_lab as lab
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.study_lineage import project_study_lineage
from hermeneia.web.app import create_app

DOC = ["The lamp burned all night.", "Nobody asked why it burned.", "The keeper wrote nothing down.",
       "By morning the harbor was empty.", "A second lamp was lit at dusk.", "The ledger records only the oil."]
PREVIEWED = {"title": "Previewed proposal", "thesis": "What the steward reviewed.", "sections": [{"claim": "Reviewed claim."}]}
RESAMPLED = {"title": "Resampled proposal", "thesis": "What the second model call produced.", "sections": [{"claim": "Unreviewed claim."}]}


class R1UnresolvedReferenceDropped(AssertionError):
    """Unresolved references vanished and the Blueprint persisted without them."""


class R2aWrongTypeBound(AssertionError):
    """A label of another kind was bound to an unrelated Observation."""


class R2bUnshownRecordBound(AssertionError):
    """A reference the model was never shown was bound to a real Observation."""


class R3OrphanBlueprint(AssertionError):
    """The Blueprint committed although its ArchitectPlan did not."""


class R4ModelDirectWrite(AssertionError):
    """A generation request wrote model output to canonical state without a steward decision."""


class R5UnreviewedResample(AssertionError):
    """'Ratify & Save' committed a second, unreviewed model result instead of the previewed one."""


class R6PlaceholderCommitted(AssertionError):
    """A canned placeholder Blueprint was committed although no model ran."""


def exposed(mode: str, risk: type[AssertionError]):
    return pytest.param(mode, marks=pytest.mark.xfail(strict=True, raises=risk, reason=f"{risk.__name__} under {mode} (#251)"))


@pytest.fixture
def isolated(tmp_path):
    with lab.isolated(tmp_path):
        yield tmp_path


class Study:
    """A disposable synthetic workspace with the legacy-write configuration under test."""

    def __init__(self, workdir: Path, mode: str, documents: list[list[str]]):
        self.db = workdir / "ws" / "workspace.db"
        SQLiteStore(self.db).close()
        app = create_app(db_path=self.db, credential_store=lab._NoCredentials())
        app.config["LEGACY_BLUEPRINT_WRITES"] = mode
        self.client = app.test_client()
        for n, lines in enumerate(documents):
            lab._ok(self.client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(lines)), f"synthetic-{n}.pdf")},
                                     content_type="multipart/form-data"))
        self.obs = [r[0] for r in self.rows("SELECT id FROM observations ORDER BY page, paragraph, sentence")]

    def rows(self, sql: str, args=()):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def blueprints(self):
        return [{"id": i, "title": t, "source": s, "sections": json.loads(sec)}
                for i, t, s, sec in self.rows("SELECT id, title, source, sections FROM narrative_blueprints")]

    def plans(self) -> int:
        return self.rows("SELECT COUNT(*) FROM architect_plans")[0][0]

    def text_of(self, observation_id: str) -> str:
        return self.rows("SELECT raw_text FROM observations WHERE id = ?", (observation_id,))[0][0].strip()

    def generate(self, reply: dict):
        provider = SimpleNamespace(prompts=[])
        provider.render = lambda prompt: (provider.prompts.append(prompt), json.dumps(reply))[1]
        # Only `proposal` mode reads the execution record (CI-011, contract v1.1); other modes never call it.
        provider.execution_config = lambda: {"provider": "fake", "model_id": "fake-model"}
        with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=provider):
            response = self.client.post("/api/architect/generate", json={"directive": "Build from the evidence.", "provider": "fake"})
        return response, provider.prompts


def _refused_without_rows(study: Study, response, codes: set[str]) -> dict:
    body = response.get_json() or {}
    assert response.status_code in (403, 409, 422), response.get_data(as_text=True)
    assert body.get("code") in codes and not study.blueprints() and study.plans() == 0
    return body


def _chat_replies(*replies):
    """OpenAI-shaped client returning a different reply on each call, like a sampled model."""
    queue, calls = list(replies), []

    def create(**_kwargs):
        calls.append(1)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(queue.pop(0))))])

    return SimpleNamespace(_model="fake", _client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))), calls


@pytest.mark.parametrize("mode", [exposed("legacy", R1UnresolvedReferenceDropped), "governed", "proposal", "disabled"])
def test_r1_unresolved_references_are_refused_not_dropped(isolated, mode):
    study = Study(isolated, mode, [DOC])
    response, _ = study.generate({"title": "T", "thesis": "Th", "sections": [
        {"claim": "Out of range and unknown references.", "obs_refs": ["OBS-1", "OBS-99"], "interp_refs": ["INTERP-deadbeef"]}]})
    saved = study.blueprints()
    if (response.status_code == 201 and len(saved) == 1 and saved[0]["sections"][0]["supporting_observations"] == [study.obs[0]]
            and saved[0]["sections"][0]["supporting_interpretations"] == []):
        raise R1UnresolvedReferenceDropped("OBS-99 and INTERP-deadbeef were dropped silently; only OBS-1 was kept")
    body = _refused_without_rows(study, response, {"BLUEPRINT_REFERENCE_INVALID", "LEGACY_DIRECT_WRITE_DISABLED"})
    if body["code"] == "BLUEPRINT_REFERENCE_INVALID":
        assert {(r["ref"], r["reason"]) for r in body["invalid_references"]} == {("OBS-99", "unshown"), ("INTERP-deadbeef", "unknown")}


@pytest.mark.parametrize("mode", [exposed("legacy", R2aWrongTypeBound), "governed", "proposal", "disabled"])
def test_r2a_a_label_of_another_kind_never_binds_an_observation(isolated, mode):
    study = Study(isolated, mode, [DOC])
    response, _ = study.generate({"title": "T", "thesis": "Th", "sections": [
        {"claim": "An interpretation-style label in obs_refs.", "obs_refs": ["I3"], "interp_refs": []}]})
    saved = study.blueprints()
    if (response.status_code == 201 and len(saved) == 1
            and saved[0]["sections"][0]["supporting_observations"] == [study.obs[2]] and study.text_of(study.obs[2]) == DOC[2]):
        raise R2aWrongTypeBound("'I3' in obs_refs was bound to Observation 3, 'The keeper wrote nothing down.'")
    body = _refused_without_rows(study, response, {"BLUEPRINT_REFERENCE_INVALID", "LEGACY_DIRECT_WRITE_DISABLED"})
    if body["code"] == "BLUEPRINT_REFERENCE_INVALID":
        assert [(r["ref"], r["reason"]) for r in body["invalid_references"]] == [("I3", "unresolved")]


@pytest.mark.parametrize("mode", [exposed("legacy", R2bUnshownRecordBound), "governed", "proposal", "disabled"])
def test_r2b_a_reference_the_model_was_never_shown_never_binds(isolated, mode):
    documents = [[f"Document {d}, line {n}." for n in range(1, 31)] for d in ("one", "two", "three")]
    study = Study(isolated, mode, documents)
    assert len(study.obs) == 90
    response, prompts = study.generate({"title": "T2", "thesis": "Th2", "sections": [
        {"claim": "Cites an observation number it was not shown.", "obs_refs": ["OBS-2"], "interp_refs": []}]})
    if prompts:
        assert sum(1 for line in prompts[0].splitlines() if line.startswith("OBS-")) == 40 and "\nOBS-2 (" not in prompts[0]
    saved = [b for b in study.blueprints() if b["title"] == "T2"]
    if response.status_code == 201 and len(saved) == 1:
        bound = saved[0]["sections"][0]["supporting_observations"]
        if len(bound) == 1 and study.text_of(bound[0]) not in prompts[0]:
            raise R2bUnshownRecordBound(f"OBS-2 was bound to {study.text_of(bound[0])!r}, which the prompt never showed")
    body = _refused_without_rows(study, response, {"BLUEPRINT_REFERENCE_INVALID", "LEGACY_DIRECT_WRITE_DISABLED"})
    if body["code"] == "BLUEPRINT_REFERENCE_INVALID":
        assert [(r["ref"], r["reason"]) for r in body["invalid_references"]] == [("OBS-2", "unshown")]


@pytest.mark.parametrize("mode", ["legacy", "governed", "proposal", "disabled"])
def test_r3_blueprint_links_and_plan_commit_together_or_not_at_all(isolated, mode):
    study = Study(isolated, mode, [DOC])
    with mock.patch("hermeneia.compiler.architect.compile_architect_plan", side_effect=RuntimeError("compile failed")):
        response, _ = study.generate({"title": "T", "thesis": "Th", "sections": [{"claim": "C", "obs_refs": ["OBS-1"], "interp_refs": []}]})
    if response.status_code == 500 and len(study.blueprints()) == 1 and study.plans() == 0:
        raise R3OrphanBlueprint("plan compilation failed but the Blueprint stayed committed without a plan")
    held = mode == "proposal" and response.status_code == 201 and response.get_json()["canonical_status"] == "not_persisted"
    assert (response.status_code in (403, 500) or held) and not study.blueprints() and study.plans() == 0
    assert study.rows("SELECT COUNT(*) FROM blueprint_observation_links")[0][0] == 0


@pytest.mark.parametrize("mode", [exposed("legacy", R4ModelDirectWrite), exposed("governed", R4ModelDirectWrite), "proposal", "disabled"])
def test_r4_a_generation_request_never_writes_model_output_to_canonical_state(isolated, mode):
    study = Study(isolated, mode, [DOC])
    response, prompts = study.generate({"title": "T", "thesis": "Th", "sections": [{"claim": "C", "obs_refs": ["OBS-1"], "interp_refs": []}]})
    saved = study.blueprints()
    if response.status_code == 201 and len(saved) == 1 and saved[0]["source"] == "ai-generated" and study.plans() == 1:
        conn = lab._read_only(study.db)
        try:
            authorship = next(i["authorship"] for i in project_study_lineage(conn)["items"]
                              if i["record"] == {"table": "narrative_blueprints", "key": {"id": saved[0]["id"]}})
        finally:
            conn.close()
        raise R4ModelDirectWrite(f"one request committed an ai-generated Blueprint and plan; Lineage authorship {authorship!r}")
    if mode == "proposal":  # the model ran once; its reply is a held candidate, never a canonical write (v1.1 §3)
        body = response.get_json()
        assert response.status_code == 201 and body["canonical_status"] == "not_persisted" and len(prompts) == 1
        assert body["schema"] == "hermeneia.legacy-architect-candidate/v1" and not study.blueprints() and study.plans() == 0
        return
    _refused_without_rows(study, response, {"LEGACY_DIRECT_WRITE_DISABLED"})
    assert prompts == []


@pytest.mark.parametrize("mode", [exposed("legacy", R5UnreviewedResample), "governed", "proposal", "disabled"])
def test_r5_ratify_and_save_never_commits_an_unreviewed_model_result(isolated, mode):
    study = Study(isolated, mode, [DOC])
    provider, calls = _chat_replies(PREVIEWED, RESAMPLED)
    with mock.patch("hermeneia.narrative.artist_providers.get_provider", return_value=provider):
        preview = study.client.post("/api/pipeline/extract-blueprint", json={"text": "A source text.", "provider": "fake", "save": False})
        saved = study.client.post("/api/pipeline/extract-blueprint", json={"text": "A source text.", "provider": "fake", "save": True})
    assert preview.status_code == 200 and preview.get_json()["proposed_blueprint"]["title"] == "Previewed proposal"
    committed = study.blueprints()
    if saved.status_code == 201 and [b["title"] for b in committed] == ["Resampled proposal"] and len(calls) == 2:
        raise R5UnreviewedResample("the steward previewed 'Previewed proposal'; 'Ratify & Save' committed 'Resampled proposal'")
    _refused_without_rows(study, saved, {"EXACT_RATIFICATION_REQUIRED"})
    assert len(calls) == 1


@pytest.mark.parametrize("mode", [exposed("legacy", R6PlaceholderCommitted), "governed", "proposal", "disabled"])
def test_r6_no_placeholder_blueprint_is_committed_when_no_model_ran(isolated, mode):
    study = Study(isolated, mode, [DOC])
    saved = study.client.post("/api/pipeline/extract-blueprint", json={"text": "Any source text at all.", "provider": "null", "save": True})
    committed = study.blueprints()
    if (saved.status_code == 201 and len(committed) == 1 and committed[0]["title"] == "Extracted Blueprint"
            and committed[0]["source"] == "extracted"):
        raise R6PlaceholderCommitted("the canned 'Extracted Blueprint' was committed as extracted though no model ran")
    _refused_without_rows(study, saved, {"EXACT_RATIFICATION_REQUIRED", "NO_MODEL_EXECUTED"})


# Found while repairing R3 (2026-10-10): the shared exact-persistence helper ran
# ensure_architect_tables() mid-transaction, whose executescript() commits, so
# steward ratification and P8 acceptance were not atomic either. The required
# provenance (#251 area 3) includes the P8 acceptance receipt.

class R3PartialAcceptance(AssertionError):
    """A P8 acceptance failed but its Blueprint stayed committed without plan or receipt."""


def test_r3_steward_ratification_commits_blueprint_and_plan_together(isolated):
    study = Study(isolated, "legacy", [DOC])
    candidate = {"title": "Steward Blueprint", "thesis": "Th.",
                 "sections": [{"claim": "C", "supporting_observations": [study.obs[0]], "supporting_interpretations": []}]}
    with mock.patch("hermeneia.compiler.architect.compile_architect_plan", side_effect=RuntimeError("compile failed")):
        response = study.client.post("/api/pipeline/ratify-blueprint", json={"proposed_blueprint": candidate})
    if response.status_code == 500 and len(study.blueprints()) == 1 and study.plans() == 0:
        raise R3OrphanBlueprint("ratification failed at plan compilation but the Blueprint stayed committed")
    assert response.status_code == 500 and not study.blueprints() and study.plans() == 0


@pytest.mark.parametrize("failing", ["hermeneia.blueprint_proposals.store_receipt", "hermeneia.compiler.architect.compile_architect_plan"])
def test_r3_p8_acceptance_commits_blueprint_plan_and_receipt_together(isolated, failing):
    import blueprint_proposal_lab as proposal_lab
    from test_e10_vertical_slice_api import _FakeOllamaClient

    corpus = proposal_lab.load()
    _FakeOllamaClient.models = [corpus["extraction_model"]]
    case = next(c for c in corpus["cases"] if c["case_id"] == "P05_exact_accept")
    ws = proposal_lab.Workspace(corpus, isolated)
    for op in case["setup"]:
        ws.apply(op)
    candidate = proposal_lab.propose(ws, case["generate"], case["generate"]["script"], corpus["extraction_model"])[0].get_json()
    with mock.patch(failing, side_effect=RuntimeError("injected failure")):
        response = proposal_lab.decide(ws, candidate, {"decision": "accept"})
    counts = {t: ws.count(t) for t in ("narrative_blueprints", "blueprint_observation_links", "architect_plans",
                                       "blueprint_proposal_acceptances")}
    if response.status_code >= 500 and counts["narrative_blueprints"] == 1 and counts["blueprint_proposal_acceptances"] == 0:
        raise R3PartialAcceptance(f"acceptance failed ({failing.rsplit('.', 1)[1]}) but left {counts}")
    assert response.status_code >= 500 and set(counts.values()) == {0}
