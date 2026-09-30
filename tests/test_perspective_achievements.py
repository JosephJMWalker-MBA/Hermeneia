"""Frozen P4 predicates over synthetic canonical P3 records, never model calls."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import uuid

import pytest

from hermeneia.perspective_achievement_evidence import read_perspective_achievement_evidence
from hermeneia.perspective_achievements import evaluate_perspective_achievements
from hermeneia.perspective_achievements import perspective_achievement_rules
from hermeneia.perspective_execution_receipts import (
    TABLE, canonical_bytes, capture_execution_run, store_retained_execution,
)
from hermeneia.perspective_identity import frame_v2_row_from_draft, resolution_from_frame_v2_row
from hermeneia.perspective_runs import build_perspective_prompt, perspective_definition
from hermeneia.scope_resolution import resolve_scope_for_provider
from hermeneia.study_lineage import project_study_lineage
from test_scope_resolution import _seed_scope_db, _selection_scope

START = "2026-09-30T10:00:00+00:00"
END = "2026-09-30T10:00:01+00:00"
KEPT = "2026-09-30T10:01:00+00:00"
QUESTION = "What does this exact evidence support? ✓"
EARNED = "earned"
NO = "not_earned"
UNSUPPORTED = "unsupported_due_to_missing_coverage"
INVALID = "invalid_evidence"


class Study:
    def __init__(self, path):
        self.path = path
        self.seed = _seed_scope_db(path)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.scope = resolve_scope_for_provider(self.conn, _selection_scope(self.seed, text=""))
        self.sequence = 0

    def retained(self, perspective="close-reader", *, question=QUESTION, scope=None,
                 execution=None, response="Exact synthetic proposal.\n", kept=KEPT,
                 retain=True, prompt=None):
        self.sequence += 1
        metadata = None
        if isinstance(perspective, dict):
            resolved = resolution_from_frame_v2_row(perspective)
            definition, metadata = resolved.definition, resolved.receipt_metadata
        else:
            definition = perspective_definition(perspective)
        scope = deepcopy(self.scope if scope is None else scope)
        run = capture_execution_run(
            definition, question=question, scope_receipt=scope,
            execution=execution or {"provider_id": "synthetic", "model_id": "fixture-v1"},
            response=response, prompt=prompt if prompt is not None else build_perspective_prompt(
                definition, question=question, scope_receipt=scope),
            perspective_metadata=metadata, created_at=START, completed_at=END,
            run_id=str(uuid.UUID(int=self.sequence)),
        )
        return store_retained_execution(self.conn, run, retained_at=kept) if retain else run

    def saved(self, label="Synthetic frame", *, purpose="Inspect exact evidence.",
              questions=None, challenges=None, limitations=None, actor="local_steward",
              predecessor=None):
        row, _ = frame_v2_row_from_draft(
            {"label": label, "purpose": purpose,
             "questions": questions or ["What supports this?"],
             "challenges": challenges or [], "limitations": limitations or []},
            declared_by=actor, declared_date=START,
            predecessor_perspective_id=predecessor["id"] if predecessor else None,
        )
        names = tuple(row)
        self.conn.execute(
            "INSERT INTO perspectives (" + ",".join(names) + ") VALUES (" +
            ",".join("?" for _ in names) + ")", tuple(row.values()),
        )
        if predecessor:
            self.conn.execute("INSERT INTO supersession_relations VALUES (?,?,?,?)",
                (predecessor["id"], row["id"], "Synthetic governed revision", START))
        self.conn.commit()
        return row

    def results(self):
        result = evaluate_perspective_achievements(read_perspective_achievement_evidence(self.conn))
        assert result["schema"] == "hermeneia.perspective-achievement-evaluation/v1"
        assert result["evaluator_version"] == "1.0.0"
        assert [row["achievement_id"] for row in result["achievements"]] == [
            "perspective_explorer", "second_opinion"]
        for row in result["achievements"]:
            assert row["rule_id"] == "achievement." + row["achievement_id"]
            assert row["rule_version"] == "1.0.0"
            assert row["status"] in {EARNED, NO, UNSUPPORTED, INVALID}
            assert isinstance(row["reason_code"], str) and row["reason_code"]
            assert isinstance(row["reason"], str) and row["reason"]
            assert isinstance(row["evidence_refs"], list)
            assert isinstance(row["coverage"], dict)
        return {row["achievement_id"]: row for row in result["achievements"]}


@pytest.fixture
def study(tmp_path):
    value = Study(tmp_path / "synthetic.db")
    try:
        yield value
    finally:
        value.conn.close()


def _assert_status(study, explorer, second):
    result = study.results()
    assert result["perspective_explorer"]["status"] == explorer
    assert result["second_opinion"]["status"] == second
    return result


def test_one_retained_receipt_has_explorer_witness_but_no_second_opinion(study):
    receipt = study.retained()
    rows = _assert_status(study, EARNED, NO)
    assert rows["perspective_explorer"]["qualifying_receipt_ids"] == [receipt["id"]]


def test_covered_empty_category_is_bounded_not_earned(study):
    _assert_status(study, NO, NO)


def test_missing_legacy_category_is_unsupported_and_never_initialized(study):
    study.conn.execute(f"DROP TABLE {TABLE}")
    study.conn.commit()
    before = tuple(study.conn.iterdump())
    _assert_status(study, UNSUPPORTED, UNSUPPORTED)
    assert tuple(study.conn.iterdump()) == before
    assert not study.conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone()


@pytest.mark.parametrize("execution", [None, {"provider_id": "another", "model_id": "another"}])
def test_same_family_repeated_or_with_different_model_is_not_second_opinion(study, execution):
    root = study.saved()
    study.retained(root)
    study.retained(root, execution=execution)
    _assert_status(study, EARNED, NO)


def test_changed_revision_of_same_saved_family_is_not_second_opinion(study):
    root = study.saved()
    study.retained(root)
    child = study.saved(purpose="Challenge exact evidence.", predecessor=root)
    study.retained(child)
    _assert_status(study, EARNED, NO)


@pytest.mark.parametrize("origins", ["builtins", "saved", "mixed"])
def test_distinct_families_with_same_question_scope_and_model_qualify(study, origins):
    if origins == "builtins":
        a, b = "close-reader", "skeptical-reader"
    elif origins == "saved":
        a = study.saved("First frame")
        b = study.saved("Second frame", purpose="Challenge exact evidence.")
    else:
        a = "close-reader"
        b = study.saved("Synthetic distinct method", purpose="Inspect social context.")
    receipts = [study.retained(a), study.retained(b)]
    rows = _assert_status(study, EARNED, EARNED)
    pair = rows["second_opinion"]["qualifying_receipt_ids"]
    assert set(pair) == {receipt["id"] for receipt in receipts}
    assert len(pair) == 2


@pytest.mark.parametrize("question", [
    "What does this evidence justify? ✓",  # paraphrase
    QUESTION + " ",                      # no post-capture trim
    QUESTION.replace("✓", ""),
    "Caf\u00e9?",                       # compared below to decomposed form
])
def test_question_equality_is_exact_captured_utf8(study, question):
    baseline = "Cafe\u0301?" if question == "Caf\u00e9?" else QUESTION
    study.retained("close-reader", question=baseline)
    study.retained("skeptical-reader", question=question)
    _assert_status(study, EARNED, NO)


def test_question_template_strip_does_not_change_exact_question_comparison(study):
    a = study.retained("close-reader", question=QUESTION)
    b = study.retained("skeptical-reader", question="  " + QUESTION + "\n")
    assert a["run"]["question"] != b["run"]["question"]
    _assert_status(study, EARNED, NO)


def test_different_canonical_scope_evidence_does_not_qualify(study):
    study.retained("close-reader")
    alternate = _seed_scope_db(study.path, doc_id="second-doc", id_prefix="second-ex")
    scope = resolve_scope_for_provider(study.conn, _selection_scope(alternate, text=""))
    study.retained("skeptical-reader", scope=scope)
    _assert_status(study, EARNED, NO)


@pytest.mark.parametrize("change", ["filename", "supporting_flags"])
def test_scope_evidence_ids_are_insufficient_when_full_captured_frame_changes(study, change):
    study.retained("close-reader")
    scope = deepcopy(study.scope)
    if change == "filename":
        scope["primary"]["source_document_filename"] = "historical-other-name.pdf"
    else:
        scope_input = _selection_scope(study.seed, text="")
        scope_input["supporting"] = {"current_page": {"include": True}}
        scope = resolve_scope_for_provider(study.conn, scope_input)
    study.retained("skeptical-reader", scope=scope)
    _assert_status(study, EARNED, NO)


def test_same_highlight_ids_with_reversed_captured_order_do_not_qualify(study):
    for identifier in ["mark-a", "mark-b"]:
        study.conn.execute(
            "INSERT INTO reader_highlights(id,source_document_id,page,source_locator,selected_text,created_at,updated_at) "
            "VALUES(?,?,2,'page:2:block:1','Alpha beta begins.',?,?)",
            (identifier, study.seed["doc_id"], START, START))
    study.conn.commit()
    scope_input = _selection_scope(study.seed, text="")
    scope_input["supporting"] = {"highlights": {"include": True, "ids": ["mark-a", "mark-b"]}}
    first = resolve_scope_for_provider(study.conn, scope_input)
    second = deepcopy(first)
    second["supporting"].reverse()
    second["materialization"]["supporting"] = deepcopy(second["supporting"])
    a = study.retained("close-reader", scope=first)
    b = study.retained("skeptical-reader", scope=second)
    assert {part["id"] for part in first["supporting"]} == {part["id"] for part in second["supporting"]}
    assert a["run"]["scope_sha256"] != b["run"]["scope_sha256"]
    _assert_status(study, EARNED, NO)


def test_highlight_packet_compilation_time_remains_inside_full_scope_boundary(study):
    study.conn.execute(
        "INSERT INTO reader_highlights(id,source_document_id,page,source_locator,selected_text,created_at,updated_at) "
        "VALUES('synthetic-mark',?,2,'page:2:block:1','Alpha beta begins.',?,?)",
        (study.seed["doc_id"], START, START))
    study.conn.commit()
    scope_input = _selection_scope(study.seed, text="")
    scope_input["supporting"] = {"highlights": {"include": True, "ids": ["synthetic-mark"]}}
    first = resolve_scope_for_provider(study.conn, scope_input)
    second = deepcopy(first)
    for scope, timestamp in [(first, START), (second, END)]:
        packet = scope["materialization"]["study_packet"]
        packet["compiled_at"] = timestamp
        packet["provenance"]["compiled_at"] = timestamp
    a = study.retained("close-reader", scope=first)
    b = study.retained("skeptical-reader", scope=second)
    assert a["run"]["scope_sha256"] != b["run"]["scope_sha256"]
    assert a["run"]["scope_receipt"]["supporting"] == b["run"]["scope_receipt"]["supporting"]
    _assert_status(study, EARNED, NO)


@pytest.mark.parametrize("activity", ["transient", "discarded", "failed"])
def test_non_retained_activity_cannot_become_a_second_opinion(study, activity):
    study.retained("close-reader")
    transient = study.retained("skeptical-reader", retain=False)
    if activity == "failed":
        transient["status"] = "failed"  # transient fixture; deliberately never stored
    if activity == "discarded":
        del transient
    assert study.conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 1
    _assert_status(study, EARNED, NO)


@pytest.mark.parametrize("copy", ["exact", "label_only", "builtin_adoption"])
def test_exact_or_label_only_methodology_copy_does_not_count(study, copy):
    if copy == "builtin_adoption":
        built = perspective_definition("close-reader")
        a = "close-reader"
        b = study.saved(built.label, purpose=built.purpose, questions=list(built.questions),
                        challenges=list(built.challenges), limitations=list(built.limitations))
    else:
        a = study.saved("First frame", actor="actor-a")
        b = study.saved("First frame" if copy == "exact" else "Renamed copy", actor="actor-b")
    receipts = [study.retained(a), study.retained(b)]
    assert receipts[0]["run"]["perspective"]["id"] != receipts[1]["run"]["perspective"]["id"]
    _assert_status(study, EARNED, NO)


def test_methodology_paraphrase_is_known_exact_field_limitation(study):
    a = study.saved("First", purpose="Inspect exact evidence.")
    b = study.saved("Second", purpose="Examine the precise evidence.")
    study.retained(a)
    study.retained(b)
    _assert_status(study, EARNED, EARNED)


def test_ordered_methodology_list_difference_is_preserved(study):
    a = study.saved("First", questions=["What supports this?", "What is absent?"])
    b = study.saved("Second", questions=["What is absent?", "What supports this?"])
    study.retained(a)
    study.retained(b)
    _assert_status(study, EARNED, EARNED)


@pytest.mark.parametrize("responses", [
    ("Exactly identical proposal.", "Exactly identical proposal."),
    ("Proposal A.", "I disagree with A. Proposal B."),
])
def test_outputs_agreement_and_downstream_use_do_not_determine_qualification(study, responses):
    receipts = [study.retained("close-reader", response=responses[0]),
                study.retained("skeptical-reader", response=responses[1])]
    assert all(receipt["retention"]["actor_identity"] == "unknown" for receipt in receipts)
    assert study.conn.execute("SELECT COUNT(*) FROM interpretations").fetchone()[0] == 0
    _assert_status(study, EARNED, EARNED)


def test_unused_retained_output_qualifies_without_canonical_interpretation(study):
    study.retained(response="The steward may ignore or disagree with this proposal.")
    assert study.conn.execute("SELECT COUNT(*) FROM interpretations").fetchone()[0] == 0
    _assert_status(study, EARNED, NO)


def _ordering(receipt):
    instant = datetime.fromisoformat(receipt["retention"]["retained_at"]).astimezone(timezone.utc)
    return instant, receipt["id"]


def test_three_receipts_with_only_one_qualifying_pair_select_that_pair(study):
    a = study.retained("close-reader", kept="2026-09-30T10:02:00+00:00")
    study.retained("contextual-reader", question="An unrelated question", kept=KEPT)
    c = study.retained("skeptical-reader", kept="2026-09-30T10:03:00+00:00")
    rows = _assert_status(study, EARNED, EARNED)
    assert rows["second_opinion"]["qualifying_receipt_ids"] == [r["id"] for r in sorted([a, c], key=_ordering)]


def test_multiple_pairs_use_lexicographic_retention_utc_and_id_order(study):
    receipts = [
        study.retained("close-reader", kept="2026-09-30T12:02:00+02:00"),
        study.retained("contextual-reader", kept="2026-09-30T10:01:00+00:00"),
        study.retained("skeptical-reader", kept="2026-09-30T06:03:00-04:00"),
    ]
    ordered = sorted(receipts, key=_ordering)
    rows = _assert_status(study, EARNED, EARNED)
    assert rows["perspective_explorer"]["qualifying_receipt_ids"] == [ordered[0]["id"]]
    assert rows["second_opinion"]["qualifying_receipt_ids"] == [r["id"] for r in ordered[:2]]


def test_equal_retention_instants_use_ascii_receipt_id_ties(study):
    receipts = [study.retained("close-reader", kept=KEPT),
                study.retained("contextual-reader", kept="2026-09-30T12:01:00+02:00"),
                study.retained("skeptical-reader", kept="2026-09-30T06:01:00-04:00")]
    rows = _assert_status(study, EARNED, EARNED)
    ids = sorted(receipt["id"] for receipt in receipts)
    assert rows["perspective_explorer"]["qualifying_receipt_ids"] == ids[:1]
    assert rows["second_opinion"]["qualifying_receipt_ids"] == ids[:2]


def test_qualified_evidence_references_exact_typed_lineage_identity_not_profile_labels(study):
    receipt = study.retained()
    expected = next(item for item in project_study_lineage(study.conn)["items"]
                    if item["record"]["table"] == TABLE)
    rows = _assert_status(study, EARNED, NO)
    refs = rows["perspective_explorer"]["evidence_refs"]
    ref = next(ref for ref in refs if ref.get("record") == expected["record"])
    for key in ["record", "event", "record_type", "authorship"]:
        assert ref[key] == expected[key]
    assert ref["record"] == {"table": TABLE, "key": {"id": receipt["id"]}}
    assert ref["authorship"] == "model"


def test_second_opinion_preserves_exact_comparison_and_saved_ancestry_evidence(study):
    root = study.saved("Root method")
    child = study.saved("Revised method", purpose="Challenge evidence.", predecessor=root)
    receipts = [study.retained(child), study.retained("contextual-reader")]
    row = _assert_status(study, EARNED, EARNED)["second_opinion"]
    selected = sorted(receipts, key=_ordering)
    assert row["question_comparison_basis"] == {
        "codec": "exact_utf8", "sha256": selected[0]["run"]["question_sha256"], "bytes_equal": True,
    }
    scope = row["scope_comparison_basis"]
    assert scope["codec"] == "complete_p3_canonical_bytes"
    assert scope["sha256"] == selected[0]["run"]["scope_sha256"]
    assert scope["bytes_equal"] is True
    assert scope["prompt_version"] == "perspective-run/v1"
    distinctness = row["perspective_distinctness_basis"]
    assert distinctness["methodology_fields"] == ["purpose", "questions", "challenges", "limitations"]
    assert distinctness["revision_ids"] == [r["run"]["perspective"]["id"] for r in selected]
    assert distinctness["methodology_bytes_different"] is True
    saved = next(value for value in distinctness["family_evidence"] if value.get("root_id"))
    assert saved["root_id"] == root["id"]
    assert {node["record"]["key"]["id"] for node in saved["perspectives"]} == {root["id"], child["id"]}
    assert saved["supersessions"][0]["record"] == {
        "table": "supersession_relations", "key": {"old_id": root["id"], "new_id": child["id"],
        "reason": "Synthetic governed revision", "ratified_at": START},
    }


def test_evaluator_refuses_caller_authored_lineage_display_json_as_canonical_facts(study):
    study.retained()
    with pytest.raises(TypeError, match="canonical|Canonical|adapter"):
        evaluate_perspective_achievements(project_study_lineage(study.conn))


def test_released_rule_metadata_digest_and_copy_boundary_are_explicit(study):
    expected = "sha256:6b0065fac155c40fc25ce5cc62c53a7c250c0595dd4e49554669bab55e56197c"
    rules = perspective_achievement_rules()
    assert "sha256:" + hashlib.sha256(canonical_bytes(rules)).hexdigest() == expected
    result = evaluate_perspective_achievements(read_perspective_achievement_evidence(study.conn))
    assert result["rules_sha256"] == expected
    for rule, row in zip(rules, result["achievements"]):
        assert row["rule_sha256"] == "sha256:" + hashlib.sha256(canonical_bytes(rule)).hexdigest()
    # Returned metadata is a projection copy, never an editable rule owner.
    rules[0]["validity_checks"].clear()
    rules[1]["methodology_fields"].clear()
    assert "sha256:" + hashlib.sha256(canonical_bytes(perspective_achievement_rules())).hexdigest() == expected


def test_evaluation_does_not_mutate_adapted_input_and_repeats_identically(study):
    study.retained("close-reader")
    study.retained("skeptical-reader")
    evidence = read_perspective_achievement_evidence(study.conn)
    before = deepcopy(evidence)
    first = evaluate_perspective_achievements(evidence)
    assert evidence == before
    assert canonical_bytes(first) == canonical_bytes(evaluate_perspective_achievements(evidence))
    assert "award_id" not in json.dumps(first) and "awarded_at" not in json.dumps(first)


def test_sql_row_order_does_not_change_results(study):
    study.retained("close-reader")
    study.retained("contextual-reader")
    study.retained("skeptical-reader")
    first = study.results()
    study.conn.execute("PRAGMA reverse_unordered_selects=ON")
    assert canonical_bytes(first) == canonical_bytes(study.results())
