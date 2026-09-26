"""Identity, provenance and non-mutation boundaries of the lineage projection."""
import json
import sqlite3

import pytest

from hermeneia.study_lineage import project_study_lineage, serialize_projection


TIME = "2026-09-20T10:00:00+00:00"


def _table(conn, name, rows):
    columns = sorted({column for row in rows for column in row})
    conn.execute(f'CREATE TABLE "{name}" (' + ",".join(f'"{c}"' for c in columns) + ")")
    for row in rows:
        conn.execute(f'INSERT INTO "{name}" (' + ",".join(f'"{c}"' for c in row) + ") VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))


def _evidence(conn, excluded=False):
    _table(conn, "source_documents", [{"id": "doc", "original_filename": "source.txt", "excluded_from_analysis": int(excluded), "registered_at": TIME}])
    _table(conn, "source_extractions", [{"id": "extract", "document_id": "doc", "raw_text": "Same text", "extracted_at": TIME}])
    _table(conn, "observations", [
        {"id": oid, "source_document_id": "doc", "source_extraction_id": "extract", "raw_text": "Same text", "source_locator": locator, "created_at": TIME, "page": 2}
        for oid, locator in (("same", "occurrence-a"), ("other", "occurrence-b"))
    ])


def _items(conn, table=None):
    rows = project_study_lineage(conn)["items"]
    return rows if table is None else [r for r in rows if r["record"]["table"] == table]


def test_typed_identity_and_equal_text_occurrences_are_not_collapsed():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "reader_highlights", [{"id": "same", "source_document_id": "doc", "selected_text": "Same text", "note_text": "Note", "question_text": "Question?", "created_at": TIME, "updated_at": TIME, "page": 2}])
    items = _items(conn)
    matching = [item for item in items if item["record"]["key"] == {"id": "same"}]
    assert {item["record"]["table"] for item in matching} == {"observations", "reader_highlights"}
    assert len(_items(conn, "observations")) == 2
    highlight = _items(conn, "reader_highlights")[0]
    assert highlight["authorship"] == "unknown"
    assert highlight["event"] == "current_snapshot"
    assert highlight["record_data"]["question_text"] == "Question?"
    assert highlight["contexts"] == [{"kind": "reader", "document_id": "doc", "page": 2, "highlight_id": "same"}]
    assert not any(item["record_type"] in ("note", "question") for item in items)


def test_timestamp_strings_are_preserved_with_only_aware_chronology():
    conn = sqlite3.connect(":memory:")
    values = {"first": "2026-01-01T13:00:00+02:00", "tie": "2026-01-01T11:00:00Z", "later": "2026-01-01T12:00:00Z", "naive": "2020-01-01T00:00:00", "date": "2010-01-01", "bad": "not-time", "none": None, "overflow": "0001-01-01T00:00:00+23:00"}
    _table(conn, "perspectives", [{"id": key, "name": key, "created_at": value} for key, value in values.items()])
    items = _items(conn)
    assert [item["record"]["key"]["id"] for item in items[:3]] == ["first", "tie", "later"]
    assert items[0]["timestamp"]["sort_key"] == items[1]["timestamp"]["sort_key"]
    for item in items:
        assert item["timestamp"]["value"] == values[item["record"]["key"]["id"]]
    assert {item["timestamp"]["status"] for item in items[3:]} == {"unknown", "unorderable"}


def test_current_snapshot_never_dates_current_text_to_creation():
    conn = sqlite3.connect(":memory:")
    _table(conn, "workspace_investigation", [{"id": "current", "thesis": "New question", "created_at": "2000-01-01T00:00:00Z", "updated_at": TIME}])
    item = _items(conn)[0]
    assert item["event"] == "current_snapshot"
    assert item["timestamp"]["field"] == "updated_at"
    assert item["timestamp"]["value"] == TIME
    assert item["record_data"]["created_at"] == "2000-01-01T00:00:00Z"


def _model_records(conn):
    copied = {"observation_id": "same", "perspective": "Recorded perspective", "perspective_id": None,
              "text": "Interpretation", "evidential_status": "contested",
              "ai_provenance_id": "ai", "evidence_observation_ids": '["other"]'}
    _table(conn, "ai_provenance", [{"id": "ai", "staged_object_id": "proposal", "generating_model": "recorded-model", "model_version": "historic-v1", "generation_timestamp": TIME, "parent_object_ids": '["same"]', "generation_parameters": '{"temperature":0.2}', "prompt_reference": "exact stored prompt", "accepting_steward": "steward", "acceptance_timestamp": "2026-09-21T10:00:00Z"}])
    _table(conn, "proposed_interpretations", [{**copied, "id": "proposal", "status": "accepted", "steward_id": "steward", "decided_at": "2026-09-21T10:00:00Z", "steward_rationale": "Recorded reason", "created_at": TIME}])
    _table(conn, "interpretations", [
        {**copied, "id": "accepted", "source": "ai-accepted", "confidence": "ai-accepted", "created_at": "2026-09-21T10:00:00Z"},
        {"id": "human", "observation_id": "same", "text": "Interpretation", "source": "steward-authored", "ai_provenance_id": None, "created_at": TIME, "evidence_observation_ids": "[]"},
        {"id": "contradiction", "observation_id": "same", "text": "Interpretation", "source": "steward-authored", "ai_provenance_id": "ai", "created_at": TIME, "evidence_observation_ids": "[]"},
        {"id": "missing-ai", "observation_id": "same", "text": "Interpretation", "source": "ai-accepted", "ai_provenance_id": "missing", "created_at": TIME, "evidence_observation_ids": "[]"},
    ])


def test_generation_acceptance_and_human_authorship_use_real_links():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    items = _items(conn, "interpretations")
    assert {item["record"]["key"]["id"]: item["authorship"] for item in items} == {"accepted": "accepted_model", "human": "human", "contradiction": "unknown", "missing-ai": "unknown"}
    proposal, decision = sorted(_items(conn, "proposed_interpretations"), key=lambda item: item["event"], reverse=True)
    assert proposal["authorship"] == "model"
    assert decision["record"] == proposal["record"]
    assert decision["event"] == "decision"
    assert decision["timestamp"]["value"] == "2026-09-21T10:00:00Z"
    assert proposal["provenance"]["records"][0]["record_data"]["generating_model"] == "recorded-model"
    assert proposal["provenance"]["records"][0]["record_data"]["prompt_reference"] == "exact stored prompt"


@pytest.mark.parametrize("status,decided,actor,rationale,expected", [
    ("rejected", "2026-09-22T12:00:00Z", "steward", "No", True),
    ("accepted", None, "steward", "Yes", False),
    ("rejected", TIME, None, "No", False),
    ("pending", TIME, "steward", "Pending", False),
    ("rejected", TIME, "steward", None, True),
])
def test_no_decision_event_is_invented_from_status_alone(status, decided, actor, rationale, expected):
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    conn.execute("UPDATE proposed_interpretations SET status=?,decided_at=?,steward_id=?,steward_rationale=?", (status, decided, actor, rationale))
    assert any(item["event"] == "decision" for item in _items(conn, "proposed_interpretations")) is expected


def test_field_notes_do_not_gain_model_or_human_origin_and_instrument_is_omitted():
    conn = sqlite3.connect(":memory:")
    _table(conn, "investigation_log", [{"id": "corpus", "lane": "corpus", "understanding": "Saved text", "created_at": TIME}, {"id": "instrument", "lane": "instrument", "understanding": "Tool issue", "created_at": TIME}])
    projection = project_study_lineage(conn)
    assert projection["items"][0]["authorship"] == "unknown"
    assert [i["record"]["key"]["id"] for i in projection["items"]] == ["corpus"]
    assert projection["coverage"]["omitted"]["investigation_log"] == 1


def test_supersession_preserves_composite_identity_and_refuses_ambiguous_endpoints():
    conn = sqlite3.connect(":memory:")
    _table(conn, "perspectives", [{"id": "old", "name": "Old", "created_at": TIME}, {"id": "new", "name": "New", "created_at": TIME}])
    edge = {"old_id": "old", "new_id": "new", "reason": "Revised question", "ratified_at": TIME}
    _table(conn, "supersession_relations", [edge])
    assert _items(conn, "supersession_relations")[0]["record"]["key"] == edge
    _table(conn, "narrative_blueprints", [{"id": "old", "sections": "[]", "created_at": TIME}])
    assert _items(conn, "supersession_relations") == []
    assert project_study_lineage(conn)["coverage"]["omitted"]["supersession_relations"] == 1


def test_excluded_evidence_closure_hides_derived_records_and_provenance():
    conn = sqlite3.connect(":memory:")
    _evidence(conn, excluded=True)
    _model_records(conn)
    _table(conn, "reader_highlights", [{"id": "highlight", "source_document_id": "doc", "selected_text": "Hidden passage", "updated_at": TIME}])
    _table(conn, "inquiry_notes", [{"id": "question", "observation_id": "same", "question_text": "Hidden question", "created_at": TIME}])
    _table(conn, "narrative_blueprints", [{"id": "bp", "sections": '[{"supporting_observations":["same"],"supporting_interpretations":["accepted"]}]', "thesis": "Hidden thesis", "created_at": TIME}])
    _table(conn, "architect_plans", [{"id": "plan", "blueprint_id": "bp", "created_at": TIME}])
    _table(conn, "rendered_narratives", [{"id": "render", "architect_plan_id": "plan", "text": "Hidden render", "created_at": TIME}])
    _table(conn, "validation_reports", [{"id": "critic", "architect_plan_id": "plan", "rendered_narrative_id": "render", "created_at": TIME}])
    result = project_study_lineage(conn)
    assert result["items"] == []
    assert all(result["coverage"]["omitted"][table] > 0 for table in ("observations", "interpretations", "reader_highlights", "narrative_blueprints", "rendered_narratives", "validation_reports"))
    assert b"Hidden" not in serialize_projection(result)
    assert b"recorded-model" not in serialize_projection(result)


def test_excluded_supporting_evidence_cannot_leak_through_active_primary():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    conn.execute("INSERT INTO source_documents (id,excluded_from_analysis,original_filename,registered_at) VALUES ('secret',1,'secret.txt',?)", (TIME,))
    conn.execute("INSERT INTO source_extractions (id,document_id,extracted_at,raw_text) VALUES ('secret-extract','secret',?,'Hidden')", (TIME,))
    conn.execute("INSERT INTO observations (id,source_document_id,source_extraction_id,created_at,page,raw_text,source_locator) VALUES ('secret-obs','secret','secret-extract',?,1,'Hidden','locator')", (TIME,))
    _table(conn, "interpretations", [{"id": "interp", "observation_id": "same", "text": "Hidden dependency", "source": "steward-authored", "evidence_observation_ids": '["secret-obs"]', "created_at": TIME}])
    assert _items(conn, "interpretations") == []


@pytest.mark.parametrize("workspace_id,work_id", [(None, "workspace"), ("workspace", "other"), ("workspace", "workspace")])
def test_publication_requires_exact_workspace_binding(workspace_id, work_id):
    conn = sqlite3.connect(":memory:")
    if workspace_id:
        _table(conn, "workspace_identity", [{"id": "current", "workspace_id": workspace_id, "workspace_name": "Study"}])
    _table(conn, "publication_works", [{"id": "work", "workspace_id": work_id, "attached_at": TIME, "attached_by": "recorded-actor"}])
    _table(conn, "authoring_proofs", [{"id": "proof", "work_id": "work", "version_ref": "v1", "status": "verified", "created_at": TIME}])
    result = project_study_lineage(conn)
    assert bool(result["items"]) is (workspace_id == work_id)
    assert result["workspace"]["id"] == workspace_id
    if result["items"]:
        assert all(i["authorship"] == "unknown" for i in result["items"])


def test_old_schema_projection_and_export_are_read_only_and_deterministic(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    _table(conn, "perspectives", [{"id": "p", "name": "Old frame", "created_at": TIME}])
    conn.commit()
    conn.close()
    before = path.read_bytes(), path.stat().st_mtime_ns
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.execute("BEGIN")
    first = project_study_lineage(conn)
    second = project_study_lineage(conn)
    assert first == second
    assert first["workspace"] == {"id": None, "name": None}
    assert "reader_highlights" in first["coverage"]["missing_tables"]
    assert serialize_projection(first) == serialize_projection(second)
    assert json.loads(serialize_projection(first)) == first
    assert b"generated_at" not in serialize_projection(first)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("DELETE FROM perspectives")
    conn.close()
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_missing_identity_column_is_reported_without_migration():
    conn = sqlite3.connect(":memory:")
    _table(conn, "perspectives", [{"name": "Identity absent"}])
    result = project_study_lineage(conn)
    assert result["items"] == []
    assert result["coverage"]["missing_columns"] == {"perspectives": ["created_at", "id"]}


def test_missing_exclusion_state_cannot_make_old_evidence_active():
    conn = sqlite3.connect(":memory:")
    _table(conn, "source_documents", [{"id": "doc", "original_filename": "Unavailable scope", "registered_at": TIME}])
    result = project_study_lineage(conn)
    assert result["items"] == []
    assert result["coverage"]["missing_columns"]["source_documents"] == ["excluded_from_analysis"]
    assert result["coverage"]["omitted"]["source_documents"] == 1


@pytest.mark.parametrize("required_field,required_id", [
    ("required_observations", "excluded-obs"),
    ("required_interpretations", "excluded-interp"),
])
def test_plan_paragraph_evidence_is_checked_before_showing_plan_or_render(required_field, required_id):
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    conn.execute("INSERT INTO source_documents (id,excluded_from_analysis) VALUES ('excluded-doc',1)")
    conn.execute("INSERT INTO source_extractions (id,document_id) VALUES ('excluded-extract','excluded-doc')")
    conn.execute("INSERT INTO observations (id,source_document_id,source_extraction_id) VALUES ('excluded-obs','excluded-doc','excluded-extract')")
    _table(conn, "interpretations", [{"id": "excluded-interp", "observation_id": "excluded-obs", "text": "Excluded interpretation", "created_at": TIME}])
    _table(conn, "narrative_blueprints", [{"id": "bp", "sections": "[]", "created_at": TIME}])
    _table(conn, "architect_plans", [{"id": "plan", "blueprint_id": "bp", "title": "Plan with excluded paragraph", "created_at": TIME}])
    paragraph = {"plan_id": "plan", "order_idx": 0, "required_observations": "[]", "required_interpretations": "[]", "notes": "Hidden paragraph provenance"}
    paragraph[required_field] = json.dumps([required_id])
    _table(conn, "architect_plan_paragraphs", [paragraph])
    _table(conn, "rendered_narratives", [{"id": "render", "architect_plan_id": "plan", "text": "Hidden rendered content", "created_at": TIME}])
    result = project_study_lineage(conn)
    assert not any(item["record"]["table"] in {"architect_plans", "rendered_narratives"} for item in result["items"])
    assert b"Hidden" not in serialize_projection(result)
    assert result["coverage"]["omitted"]["architect_plans"] == 1
    assert result["coverage"]["omitted"]["rendered_narratives"] == 1


def test_blueprint_links_and_plan_paragraphs_keep_their_real_composite_keys():
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _table(conn, "interpretations", [{"id": "interp", "observation_id": "same", "text": "Human interpretation", "source": "steward-authored", "created_at": TIME}])
    _table(conn, "narrative_blueprints", [{"id": "bp", "sections": "[]", "created_at": TIME}])
    obs_link = {"blueprint_id": "bp", "observation_id": "same"}
    interp_link = {"blueprint_id": "bp", "interpretation_id": "interp"}
    _table(conn, "blueprint_observation_links", [obs_link])
    _table(conn, "blueprint_interpretation_links", [interp_link])
    _table(conn, "architect_plans", [{"id": "plan", "blueprint_id": "bp", "created_at": TIME}])
    paragraph = {"plan_id": "plan", "order_idx": 3, "purpose": "Recorded purpose", "required_observations": '["other"]', "required_interpretations": '["interp"]', "notes": "Exact original paragraph"}
    _table(conn, "architect_plan_paragraphs", [paragraph])
    bp_records = _items(conn, "narrative_blueprints")[0]["provenance"]["records"]
    assert {record["table"] for record in bp_records} == {"blueprint_observation_links", "blueprint_interpretation_links"}
    assert all(record["key"] == record["record_data"] for record in bp_records)
    plan_records = _items(conn, "architect_plans")[0]["provenance"]["records"]
    assert plan_records == [{"table": "architect_plan_paragraphs", "key": {"plan_id": "plan", "order_idx": 3}, "record_data": paragraph}]
    assert serialize_projection(project_study_lineage(conn)) == serialize_projection(project_study_lineage(conn))


@pytest.mark.parametrize("field,value", [
    ("required_observations", '["missing"]'),
    ("required_observations", "not-json"),
    ("required_interpretations", '["missing"]'),
    ("required_interpretations", "not-json"),
])
def test_unavailable_plan_paragraph_dependencies_do_not_invent_lineage(field, value):
    conn = sqlite3.connect(":memory:")
    _table(conn, "narrative_blueprints", [{"id": "bp", "sections": "[]", "created_at": TIME}])
    _table(conn, "architect_plans", [{"id": "plan", "blueprint_id": "bp", "created_at": TIME}])
    paragraph = {"plan_id": "plan", "order_idx": 0, "required_observations": "[]", "required_interpretations": "[]"}
    paragraph[field] = value
    _table(conn, "architect_plan_paragraphs", [paragraph])
    assert _items(conn, "architect_plans") == []


def test_incomplete_paragraph_schema_is_reported_without_inventing_absent_dependencies():
    conn = sqlite3.connect(":memory:")
    _table(conn, "narrative_blueprints", [{"id": "bp", "sections": "[]", "created_at": TIME}])
    _table(conn, "architect_plans", [{"id": "plan", "blueprint_id": "bp", "created_at": TIME}])
    _table(conn, "architect_plan_paragraphs", [{"plan_id": "plan", "order_idx": 0}])
    result = project_study_lineage(conn)
    assert not any(item["record"]["table"] == "architect_plans" for item in result["items"])
    assert result["coverage"]["missing_columns"]["architect_plan_paragraphs"] == ["required_interpretations", "required_observations"]


@pytest.mark.parametrize("other_table", ["expression_profiles", "validation_reports"])
def test_supersession_ambiguity_checks_all_storage_supported_canonical_types(other_table):
    conn = sqlite3.connect(":memory:")
    _table(conn, "narrative_blueprints", [{"id": "old", "sections": "[]", "created_at": TIME}, {"id": "new", "sections": "[]", "created_at": TIME}])
    _table(conn, other_table, [{"id": "old", "rendered_narrative_id": "unavailable", "architect_plan_id": "unavailable", "created_at": TIME}])
    _table(conn, "supersession_relations", [{"old_id": "old", "new_id": "new", "reason": "Ambiguous old identity", "ratified_at": TIME}])
    assert _items(conn, "supersession_relations") == []


@pytest.mark.parametrize("field,value", [
    ("text", "Unrecorded replacement text"),
    ("observation_id", "other"),
    ("perspective", "Different perspective"),
    ("perspective_id", "different-frame"),
    ("evidential_status", "established"),
    ("evidence_observation_ids", "[]"),
    ("confidence", "steward-authored"),
    ("created_at", TIME),
    ("text", None),
    ("perspective", None),
    ("evidential_status", None),
])
def test_contradictory_accepted_content_stays_unknown_with_raw_provenance(field, value):
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    _table(conn, "perspectives", [{"id": "different-frame", "name": "Different frame", "created_at": TIME}])
    conn.execute(f'UPDATE interpretations SET "{field}"=? WHERE id=?', (value, "accepted"))
    item = next(item for item in _items(conn, "interpretations") if item["record"]["key"]["id"] == "accepted")
    assert item["authorship"] == "unknown"
    assert item["record_data"][field] == value
    assert item["provenance"]["records"][0]["record_data"]["id"] == "ai"
    assert item["provenance"]["records"][0]["record_data"]["acceptance_timestamp"] == "2026-09-21T10:00:00Z"


@pytest.mark.parametrize("table,field", [
    ("interpretations", "perspective"),
    ("interpretations", "perspective_id"),
    ("interpretations", "text"),
    ("interpretations", "evidential_status"),
    ("interpretations", "evidence_observation_ids"),
    ("interpretations", "confidence"),
    ("interpretations", "created_at"),
    ("proposed_interpretations", "perspective"),
    ("proposed_interpretations", "perspective_id"),
    ("proposed_interpretations", "text"),
    ("proposed_interpretations", "evidential_status"),
    ("proposed_interpretations", "evidence_observation_ids"),
])
def test_incomplete_acceptance_content_cannot_gain_accepted_model_authorship(table, field):
    conn = sqlite3.connect(":memory:")
    _evidence(conn)
    _model_records(conn)
    conn.execute(f'ALTER TABLE "{table}" DROP COLUMN "{field}"')
    item = next(item for item in _items(conn, "interpretations") if item["record"]["key"]["id"] == "accepted")
    assert item["authorship"] == "unknown"
    assert item["provenance"]["records"][0]["record_data"]["id"] == "ai"


@pytest.mark.parametrize("identifier", [None, "", 0])
def test_absent_simple_identity_is_omitted_without_fabricating_a_key(identifier):
    conn = sqlite3.connect(":memory:")
    _table(conn, "perspectives", [{"id": identifier, "name": "No durable identity", "created_at": TIME}])
    result = project_study_lineage(conn)
    assert result["items"] == []
    assert result["coverage"]["omitted"]["perspectives"] == 1


def test_supersession_empty_reason_is_a_real_composite_key_value():
    conn = sqlite3.connect(":memory:")
    _table(conn, "perspectives", [{"id": "old", "created_at": TIME}, {"id": "new", "created_at": TIME}])
    edge = {"old_id": "old", "new_id": "new", "reason": "", "ratified_at": TIME}
    _table(conn, "supersession_relations", [edge])
    assert _items(conn, "supersession_relations")[0]["record"]["key"] == edge
