"""Tests for the recursive Artist protocol (Reconstruction → Draft → Self-Critique → Revision)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from hermeneia.narrative.artist_service import _execute_render


def _make_provider(render_returns: list[str]) -> MagicMock:
    provider = MagicMock()
    provider.render.side_effect = render_returns
    provider.execution_config.return_value = {"provider": "mock"}
    return provider


PLAN_DICT = {"id": "plan-abc", "blueprint_id": "bp-xyz", "title": "Test Plan"}
PARAGRAPHS = [
    {"order_idx": 0, "section_type": "introduction", "required_terms": "[]",
     "suggested_length": 100, "purpose": "Establish the question.", "blueprint_section": ""},
    {"order_idx": 1, "section_type": "body", "required_terms": "[]",
     "suggested_length": 200, "purpose": "Develop the argument.", "blueprint_section": ""},
]


class TestExecuteRenderNonRecursive:
    def test_calls_render_once(self):
        provider = _make_provider(["final text"])
        text, config = _execute_render(provider, "the prompt", PLAN_DICT, PARAGRAPHS, False, "2026-01-01T00:00:00Z")
        assert provider.render.call_count == 1
        assert text == "final text"

    def test_no_recursive_provenance_key(self):
        provider = _make_provider(["final text"])
        _, config = _execute_render(provider, "the prompt", PLAN_DICT, PARAGRAPHS, False, "ts")
        assert "recursive_provenance" not in config

    def test_execution_timestamp_stored(self):
        provider = _make_provider(["text"])
        _, config = _execute_render(provider, "p", PLAN_DICT, PARAGRAPHS, False, "2026-06-25T12:00:00Z")
        assert config["execution_timestamp"] == "2026-06-25T12:00:00Z"


class TestExecuteRenderRecursive:
    def test_calls_render_three_times(self):
        provider = _make_provider(["intent hypothesis", "draft text", "revised text"])
        _execute_render(provider, "the prompt", PLAN_DICT, PARAGRAPHS, True, "ts")
        assert provider.render.call_count == 3

    def test_returns_third_render_as_text(self):
        provider = _make_provider(["intent hypothesis", "draft text", "revised text"])
        text, _ = _execute_render(provider, "the prompt", PLAN_DICT, PARAGRAPHS, True, "ts")
        assert text == "revised text"

    def test_recursive_provenance_keys_present(self):
        provider = _make_provider(["intent hypothesis", "draft text", "revised text"])
        _, config = _execute_render(provider, "the prompt", PLAN_DICT, PARAGRAPHS, True, "ts")
        prov = config["recursive_provenance"]
        assert prov["protocol"] == "recursive-v1"
        assert prov["intent_hypothesis"] == "intent hypothesis"
        assert prov["draft"] == "draft text"

    def test_execution_timestamp_stored(self):
        provider = _make_provider(["a", "b", "c"])
        _, config = _execute_render(provider, "p", PLAN_DICT, PARAGRAPHS, True, "2026-06-25T00:00:00Z")
        assert config["execution_timestamp"] == "2026-06-25T00:00:00Z"

    def test_first_call_is_reconstruction_prompt(self):
        """The first render call must use the reconstruction prompt, not the main prompt."""
        from hermeneia.narrative.artist_providers import generate_reconstruction_prompt
        provider = _make_provider(["intent", "draft", "revised"])
        expected_recon = generate_reconstruction_prompt(PLAN_DICT, PARAGRAPHS)
        _execute_render(provider, "MAIN PROMPT", PLAN_DICT, PARAGRAPHS, True, "ts")
        first_call_arg = provider.render.call_args_list[0][0][0]
        assert first_call_arg == expected_recon
        assert first_call_arg != "MAIN PROMPT"

    def test_second_call_is_main_prompt(self):
        provider = _make_provider(["intent", "draft", "revised"])
        _execute_render(provider, "MAIN PROMPT", PLAN_DICT, PARAGRAPHS, True, "ts")
        second_call_arg = provider.render.call_args_list[1][0][0]
        assert second_call_arg == "MAIN PROMPT"
