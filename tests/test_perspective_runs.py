from __future__ import annotations

from hermeneia.perspective_runs import (
    DEFAULT_ROOM_PERSPECTIVES,
    PERSPECTIVE_DEFINITIONS,
    build_perspective_prompt,
    normalize_reader_selection_scope,
    normalize_transient_perspective_draft,
    perspective_definition,
    perspective_definitions_payload,
    resolve_perspective_request,
    room_perspective_definitions,
    transient_perspective_fingerprint,
)


def test_perspective_definitions_are_frame_semantics_not_execution_or_style() -> None:
    forbidden = {
        "provider",
        "provider_id",
        "model",
        "model_id",
        "temperature",
        "max_tokens",
        "voice",
        "tone",
        "audience",
        "output_language",
        "rhetorical_style",
    }
    for definition in PERSPECTIVE_DEFINITIONS:
        payload = definition.to_dict()
        assert payload["id"]
        assert payload["version"]
        assert payload["purpose"]
        assert payload["questions"]
        assert payload["challenges"]
        assert payload["limitations"]
        assert forbidden.isdisjoint(payload)


def test_builtin_perspective_definitions_payload_is_unchanged_by_transient_builder() -> None:
    assert perspective_definitions_payload() == [
        definition.to_dict() for definition in PERSPECTIVE_DEFINITIONS
    ]
    assert all(
        "origin" not in payload and "definition_fingerprint" not in payload
        for payload in perspective_definitions_payload()
    )


def test_transient_perspective_draft_normalizes_and_fingerprints_frame_semantics() -> None:
    first = normalize_transient_perspective_draft({
        "name": " Institutional Trust Reader ",
        "purpose": " Examine how institutions gain, lose, or borrow legitimacy. ",
        "questions": [
            " What source of authority is assumed here? ",
            "",
            "Who is expected to trust whom?",
        ],
        "challenges": " Challenge unsupported legitimacy claims. \n\n",
        "limitations": [" May overemphasize institutions. "],
    })
    second = normalize_transient_perspective_draft({
        "label": "Institutional Trust Reader",
        "purpose": "Examine how institutions gain, lose, or borrow legitimacy.",
        "questions": [
            "What source of authority is assumed here?",
            "Who is expected to trust whom?",
        ],
        "challenges": ["Challenge unsupported legitimacy claims."],
        "limitations": ["May overemphasize institutions."],
    })

    assert first.definition == second.definition
    assert first.receipt_metadata == second.receipt_metadata
    assert first.definition.label == "Institutional Trust Reader"
    assert first.definition.version == "draft"
    assert first.definition.id.startswith("transient:")
    assert first.receipt_metadata is not None
    assert first.receipt_metadata["origin"] == "user_authored_transient"
    assert first.receipt_metadata["definition_fingerprint"].startswith("sha256:")
    assert first.receipt_metadata["definition"] == {
        "label": "Institutional Trust Reader",
        "purpose": "Examine how institutions gain, lose, or borrow legitimacy.",
        "questions": [
            "What source of authority is assumed here?",
            "Who is expected to trust whom?",
        ],
        "challenges": ["Challenge unsupported legitimacy claims."],
        "limitations": ["May overemphasize institutions."],
    }


def test_transient_perspective_fingerprint_is_only_frame_semantics() -> None:
    base = normalize_transient_perspective_draft({
        "label": "Institutional Trust Reader",
        "purpose": "Examine trust.",
        "questions": ["Who trusts whom?"],
        "challenges": ["Challenge unsupported authority."],
        "limitations": ["May overemphasize institutions."],
    }).definition
    same = normalize_transient_perspective_draft({
        "label": "Institutional Trust Reader",
        "purpose": "Examine trust.",
        "questions": ["Who trusts whom?"],
        "challenges": ["Challenge unsupported authority."],
        "limitations": ["May overemphasize institutions."],
    }).definition
    changed = normalize_transient_perspective_draft({
        "label": "Institutional Trust Reader",
        "purpose": "Examine trust and authority.",
        "questions": ["Who trusts whom?"],
        "challenges": ["Challenge unsupported authority."],
        "limitations": ["May overemphasize institutions."],
    }).definition

    assert transient_perspective_fingerprint(base) == transient_perspective_fingerprint(same)
    assert transient_perspective_fingerprint(base) != transient_perspective_fingerprint(changed)

    scope_a = normalize_reader_selection_scope({"primary": {"text": "A"}})
    scope_b = normalize_reader_selection_scope({"primary": {"text": "B"}})
    assert scope_a != scope_b
    assert transient_perspective_fingerprint(base) == transient_perspective_fingerprint(same)


def test_transient_perspective_requires_name_purpose_and_question() -> None:
    for draft, expected in (
        ({"purpose": "P", "questions": ["Q"]}, "name is required"),
        ({"label": "L", "questions": ["Q"]}, "purpose is required"),
        ({"label": "L", "purpose": "P", "questions": []}, "questions require at least one item"),
    ):
        try:
            normalize_transient_perspective_draft(draft)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("invalid transient Perspective draft was accepted")


def test_transient_perspective_rejects_forbidden_execution_and_style_fields() -> None:
    for field in ("model", "tone", "audience", "provider", "output_language"):
        draft = {
            "label": "Institutional Trust Reader",
            "purpose": "Examine trust.",
            "questions": ["Who trusts whom?"],
            field: "not-frame-semantics",
        }
        try:
            normalize_transient_perspective_draft(draft)
        except ValueError as exc:
            assert str(exc) == f"Unsupported Perspective field: {field}"
        else:
            raise AssertionError(f"{field} was accepted as a transient Perspective field")


def test_resolve_perspective_request_requires_exactly_one_builtin_or_draft() -> None:
    built_in = resolve_perspective_request(perspective_id="close-reader")
    assert built_in.definition.id == "close-reader"
    assert built_in.receipt_metadata is None

    draft = resolve_perspective_request(perspective_draft={
        "label": "Institutional Trust Reader",
        "purpose": "Examine trust.",
        "questions": ["Who trusts whom?"],
    })
    assert draft.definition.id.startswith("transient:")

    for kwargs in (
        {},
        {
            "perspective_id": "close-reader",
            "perspective_draft": {
                "label": "Institutional Trust Reader",
                "purpose": "Examine trust.",
                "questions": ["Who trusts whom?"],
            },
        },
    ):
        try:
            resolve_perspective_request(**kwargs)
        except ValueError as exc:
            assert "exactly one" in str(exc)
        else:
            raise AssertionError("invalid Perspective request shape was accepted")


def test_perspective_identity_is_stable_across_execution_models() -> None:
    definition = perspective_definition("close-reader")
    assert definition is not None
    before = (definition.id, definition.version)

    first = build_perspective_prompt(
        definition,
        question="What tension matters?",
        scope_receipt=normalize_reader_selection_scope({
            "primary": {
                "kind": "reader_selection",
                "text": "The passage itself remains the same.",
            },
        }),
    )
    second = build_perspective_prompt(
        definition,
        question="What tension matters?",
        scope_receipt=normalize_reader_selection_scope({
            "primary": {
                "kind": "reader_selection",
                "text": "The passage itself remains the same.",
            },
        }),
    )

    assert (definition.id, definition.version) == before
    assert "qwen" not in first.lower()
    assert "llama" not in second.lower()


def test_default_room_order_uses_reader_perspectives_without_critic_or_synthesizer() -> None:
    assert DEFAULT_ROOM_PERSPECTIVES == (
        "close-reader",
        "contextual-reader",
        "skeptical-reader",
    )
    definitions = room_perspective_definitions()
    assert [definition.id for definition in definitions] == list(DEFAULT_ROOM_PERSPECTIVES)
    labels = [definition.label for definition in definitions]
    assert labels == ["Close Reader", "Contextual Reader", "Skeptical Reader"]
    assert "Synthesizer" not in labels
    assert "Skeptical Critic" not in labels


def test_prior_room_responses_are_deliberation_context_not_scope() -> None:
    definition = perspective_definition("contextual-reader")
    assert definition is not None
    scope_receipt = normalize_reader_selection_scope({
        "primary": {
            "kind": "reader_selection",
            "text": "Only selected source text.",
        },
    })
    prior = [{
        "perspective": {
            "id": "close-reader",
            "version": "1",
            "label": "Close Reader",
        },
        "response": "Prior proposed reading A.",
    }]

    prompt = build_perspective_prompt(
        definition,
        question="What is being tested?",
        scope_receipt=scope_receipt,
        prior_proposed_readings=prior,
    )

    assert "PRIMARY SOURCE ATTENTION:" in prompt
    assert "Only selected source text." in prompt
    assert "Prior Proposed Readings (Deliberation Context):" in prompt
    assert "not source evidence" in prompt
    assert "may be wrong" in prompt
    assert "Prior proposed reading A." in prompt
    assert "Prior proposed reading A." not in str(scope_receipt)


def test_reader_selection_scope_receipt_is_explicit_primary_and_defaults_supporting_off() -> None:
    receipt = normalize_reader_selection_scope({
        "primary": {
            "kind": "reader_selection",
            "text": "Exact selected text.",
            "source_document_id": "doc-1",
            "page": 7,
            "locator": "reader-span:v1:%7B%7D",
            "source_locators": ["p7:b2"],
            "extraction_ids": ["ex-1"],
        },
    })

    assert receipt["primary"]["text"] == "Exact selected text."
    assert receipt["primary"]["source_document_id"] == "doc-1"
    assert receipt["primary"]["role"] == "primary"
    assert receipt["primary"]["evidence_status"] == "source_evidence"
    assert receipt["primary"]["source_metadata_origin"] == "reader_client"
    assert receipt["included"]["governing_question"] is False
    assert receipt["included"]["current_page"] is False
    assert receipt["supporting"] == []
    assert receipt["excluded"]["governing_question"] is True
    assert receipt["excluded"]["current_page"] is True
    assert receipt["excluded"]["entire_corpus"] is True
    assert receipt["excluded"]["all_notes"] is True
    assert receipt["excluded"]["accepted_interpretations"] is True
    assert receipt["excluded"]["other_documents"] is True


def test_reader_selection_scope_can_explicitly_include_governing_question_and_page() -> None:
    receipt = normalize_reader_selection_scope({
        "primary": {
            "kind": "reader_selection",
            "text": "Exact selected text.",
            "source_document_id": "doc-1",
            "page": 7,
            "locator": "reader-span:v1:%7B%7D",
        },
        "supporting": {
            "governing_question": {
                "include": True,
                "text": "How does aspiration distort perception?",
            },
            "current_page": {
                "include": True,
                "text": "Page source text.",
                "source_document_id": "doc-1",
                "page": 7,
                "source_locators": ["p7:b1", "p7:b2"],
                "extraction_ids": ["ex-1", "ex-2"],
            },
        },
    })

    assert receipt["included"] == {
        "governing_question": True,
        "current_page": True,
    }
    assert receipt["excluded"]["governing_question"] is False
    assert receipt["excluded"]["current_page"] is False
    assert [item["kind"] for item in receipt["supporting"]] == [
        "governing_question",
        "current_page",
    ]
    governing, page = receipt["supporting"]
    assert governing["evidence_status"] == "investigation_context"
    assert governing["text"] == "How does aspiration distort perception?"
    assert page["evidence_status"] == "source_context"
    assert page["text"] == "Page source text."
    assert page["source_locators"] == ["p7:b1", "p7:b2"]
    assert page["extraction_ids"] == ["ex-1", "ex-2"]
    assert page["source_metadata_origin"] == "reader_client"


def test_perspective_prompt_separates_primary_supporting_and_deliberation_context() -> None:
    definition = perspective_definition("skeptical-reader")
    assert definition is not None
    receipt = normalize_reader_selection_scope({
        "primary": {"kind": "reader_selection", "text": "Selected passage."},
        "supporting": {
            "governing_question": {
                "include": True,
                "text": "How does aspiration distort perception?",
            },
            "current_page": {
                "include": True,
                "text": "Current page source text.",
                "page": 21,
            },
        },
    })
    prompt = build_perspective_prompt(
        definition,
        question="What is happening in this sentence?",
        scope_receipt=receipt,
        prior_proposed_readings=[{
            "perspective": {"id": "close-reader", "version": "1", "label": "Close Reader"},
            "response": "Prior model response.",
        }],
    )

    assert "Question: What is happening in this sentence?" in prompt
    assert "PRIMARY SOURCE ATTENTION:" in prompt
    assert "Selected passage." in prompt
    assert "SUPPORTING SOURCE CONTEXT:" in prompt
    assert "Current page 21:" in prompt
    assert "Current page source text." in prompt
    assert "SUPPORTING INVESTIGATION CONTEXT:" in prompt
    assert "This is investigation context, not source evidence" in prompt
    assert "Governing Question:" in prompt
    assert "How does aspiration distort perception?" in prompt
    assert "Prior Proposed Readings (Deliberation Context):" in prompt
    assert "Prior model response." in prompt
    assert "Prior model response." not in str(receipt)


def test_scope_rejects_unsupported_included_material_and_missing_requested_context() -> None:
    for bad_scope, expected in (
        (
            {
                "primary": {"kind": "reader_selection", "text": "Text."},
                "supporting": {"entire_corpus": {"include": True}},
            },
            "Unsupported Scope inclusion",
        ),
        (
            {
                "primary": {"kind": "reader_selection", "text": "Text."},
                "supporting": {"governing_question": {"include": True, "text": " "}},
            },
            "governing question is unavailable",
        ),
        (
            {
                "primary": {"kind": "reader_selection", "text": "Text."},
                "supporting": {"current_page": {"include": True, "text": " "}},
            },
            "current page source text is unavailable",
        ),
    ):
        try:
            normalize_reader_selection_scope(bad_scope)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("invalid Scope request was accepted")


def test_reader_selection_scope_requires_text_and_reader_selection_kind() -> None:
    try:
        normalize_reader_selection_scope({"primary": {"kind": "reader_selection", "text": "   "}})
    except ValueError as exc:
        assert "selected Reader text" in str(exc)
    else:
        raise AssertionError("empty Reader selection was accepted")

    try:
        normalize_reader_selection_scope({"primary": {"kind": "entire_corpus", "text": "Text"}})
    except ValueError as exc:
        assert "Reader selection" in str(exc)
    else:
        raise AssertionError("non-Reader Scope was accepted")
