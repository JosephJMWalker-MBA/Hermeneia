from __future__ import annotations

from hermeneia.perspective_runs import (
    PERSPECTIVE_DEFINITIONS,
    build_perspective_prompt,
    normalize_reader_selection_scope,
    perspective_definition,
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


def test_reader_selection_scope_receipt_is_explicit_and_excludes_broader_workspace() -> None:
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
    assert receipt["primary"]["source_metadata_origin"] == "reader_client"
    assert receipt["included"]["governing_question"] is False
    assert receipt["excluded"]["entire_corpus"] is True
    assert receipt["excluded"]["all_notes"] is True
    assert receipt["excluded"]["accepted_interpretations"] is True
    assert receipt["excluded"]["other_documents"] is True


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
