"""
Tests for hermeneia/explorer/interpreter.py

Sprint E-III-1: Explorer Phase 1 — generate candidate interpretations via LLM.
"""
from __future__ import annotations

import json

import pytest

from hermeneia.explorer.interpreter import (
    ExplorerError,
    build_explorer_prompt,
    generate_candidate_interpretation,
)


# ── Fake provider helpers ─────────────────────────────────────────────────────

class _NullProvider:
    """Simulates NullArtistProvider — no LLM, returns fallback text."""
    pass


class _AnthropicLikeProvider:
    """Simulates AnthropicArtistProvider interface."""
    def __init__(self, response: str):
        self._model = "claude-test"
        self._client = _FakeAnthropicClient(response)


class _FakeAnthropicClient:
    def __init__(self, response: str):
        self.messages = _FakeMessages(response)


class _FakeMessages:
    def __init__(self, response: str):
        self._response = response

    def create(self, **kwargs):
        return _FakeResponse(self._response)


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [type("C", (), {"text": text})()]


class _OpenAILikeProvider:
    """Simulates OpenAIArtistProvider interface."""
    def __init__(self, response: str):
        self._model = "gpt-test"
        self._client = _FakeOpenAIClient(response)


class _FakeOpenAIClient:
    def __init__(self, response: str):
        self.chat = _FakeChat(response)


class _FakeChat:
    def __init__(self, response: str):
        self.completions = _FakeCompletions(response)


class _FakeCompletions:
    def __init__(self, response: str):
        self._response = response

    def create(self, **kwargs):
        return type("R", (), {
            "choices": [type("C", (), {
                "message": type("M", (), {"content": self._response})()
            })()]
        })()


class _EmptyProvider:
    """Provider that returns empty string — triggers ExplorerError."""
    def _model(self): pass
    # No _client, no _model_obj — falls through to NullArtistProvider path
    # but we override the text to be empty by patching


# ── Prompt builder tests ──────────────────────────────────────────────────────

def test_build_explorer_prompt_includes_perspective():
    prompt = build_explorer_prompt("The green light blinks.", "Literary")
    assert "Literary" in prompt
    assert "The green light blinks." in prompt


def test_build_explorer_prompt_includes_corpus_context_primary():
    ctx = {"primary_work": "The Great Gatsby", "observation_source": "gatsby.pdf", "observation_role": "primary"}
    prompt = build_explorer_prompt("Evidence remains fixed.", "Epistemic", corpus_context=ctx)
    assert "The Great Gatsby" in prompt
    assert "gatsby.pdf" in prompt


def test_build_explorer_prompt_reference_corpus_adds_instruction():
    ctx = {
        "primary_work": "The Great Gatsby",
        "observation_source": "notes.pdf",
        "observation_role": "notes",
    }
    prompt = build_explorer_prompt("An observation from notes.", "Historical", corpus_context=ctx)
    assert "notes" in prompt
    assert "The Great Gatsby" in prompt
    assert "Do not treat it as primary evidence" in prompt


def test_build_explorer_prompt_no_context():
    prompt = build_explorer_prompt("Some text.", "Psychoanalytic")
    assert "Psychoanalytic" in prompt
    assert "Some text." in prompt
    assert "Primary Work" not in prompt


def test_build_explorer_prompt_contains_task_instruction():
    prompt = build_explorer_prompt("Text.", "Literary")
    assert "candidate interpretation" in prompt or "Propose" in prompt


# ── generate_candidate_interpretation tests ───────────────────────────────────

def test_generate_with_anthropic_like_provider():
    expected = "The green light encodes an unreachable future, not an object."
    provider = _AnthropicLikeProvider(expected)
    text, prompt = generate_candidate_interpretation(
        "The green light blinks at the end of the dock.",
        "Epistemic",
        provider,
    )
    assert text == expected
    assert "Epistemic" in prompt
    assert "green light" in prompt


def test_generate_with_openai_like_provider():
    expected = "History does not recede; it accumulates."
    provider = _OpenAILikeProvider(expected)
    text, prompt = generate_candidate_interpretation(
        "Nick traces his family back to the Dukes of Buccleuch.",
        "Historical-Relational",
        provider,
    )
    assert text == expected
    assert "Historical-Relational" in prompt


def test_generate_with_null_provider_returns_fallback():
    provider = _NullProvider()
    text, prompt = generate_candidate_interpretation(
        "The clock stopped.",
        "Processual-Adaptive",
        provider,
    )
    assert isinstance(text, str)
    assert len(text) > 0
    assert "Processual-Adaptive" in text or "perspective" in text.lower()


def test_generate_prompt_is_returned():
    provider = _AnthropicLikeProvider("An interpretation.")
    _, prompt = generate_candidate_interpretation(
        "Some observation text.",
        "Literary",
        provider,
        corpus_context={"primary_work": "Gatsby", "observation_source": "g.pdf", "observation_role": "primary"},
    )
    assert "Literary" in prompt
    assert "Gatsby" in prompt


def test_generate_strips_whitespace_from_response():
    provider = _AnthropicLikeProvider("  The answer.  \n")
    text, _ = generate_candidate_interpretation("Obs.", "Literary", provider)
    assert text == "The answer."


def test_generate_raises_explorer_error_on_empty_response(monkeypatch):
    provider = _AnthropicLikeProvider("")
    with pytest.raises(ExplorerError):
        generate_candidate_interpretation("Obs.", "Literary", provider)


def test_generate_corpus_context_passed_through_to_prompt():
    ctx = {
        "primary_work": "Don Quixote",
        "observation_source": "quixote.pdf",
        "observation_role": "primary",
    }
    provider = _AnthropicLikeProvider("An interpretation.")
    _, prompt = generate_candidate_interpretation("He tilted at windmills.", "Historical", provider, corpus_context=ctx)
    assert "Don Quixote" in prompt


# ── Integration: mode field ───────────────────────────────────────────────────

def test_null_provider_fallback_text_mentions_perspective():
    """Null path fallback should remain perspective-aware."""
    provider = _NullProvider()
    text, _ = generate_candidate_interpretation(
        "Observation text here.",
        "Psychoanalytic",
        provider,
    )
    assert "Psychoanalytic" in text
