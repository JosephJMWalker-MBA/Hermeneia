"""Ollama adapts exact Hermeneia prompts to one provider-native user turn."""
from __future__ import annotations

import json
import sys
import types
from unittest.mock import Mock

import pytest

from hermeneia.narrative.artist_providers import (
    ArtistProvider,
    CONSTITUTIONAL_PROFILE,
    DEFAULT_PROVIDER_REGISTRY,
    OllamaArtistProvider,
    get_provider,
)


MODEL = "test-instruct:latest"
HOST = "http://127.0.0.1:11434"
PROMPT = "  Preserve “quotation” and e\u0301.\r\nNo rewritten framing.\n"
OUTPUT = "  Exact assistant text — unchanged.\n"


def _install_client(monkeypatch, response):
    client = Mock(spec=["chat", "generate", "list"])
    client.chat.return_value = response
    client.generate.side_effect = AssertionError("Flat generate must not be used")
    client.list.return_value = {"models": [{"model": MODEL}]}
    factory = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "ollama", types.SimpleNamespace(Client=factory))
    return client, factory


@pytest.mark.parametrize("response_shape", ["dict", "sdk"])
def test_render_preserves_exact_prompt_and_output_in_one_user_chat(monkeypatch, response_shape):
    response = {"message": {"role": "assistant", "content": OUTPUT}}
    if response_shape == "sdk":
        sdk = pytest.importorskip("ollama")
        response = sdk.ChatResponse(message=sdk.Message(role="assistant", content=OUTPUT))
    client, factory = _install_client(monkeypatch, response)
    provider = OllamaArtistProvider(model=MODEL, host=HOST)

    result = provider.render(PROMPT)

    factory.assert_called_once_with(host=HOST)
    client.chat.assert_called_once_with(
        model=MODEL, messages=[{"role": "user", "content": PROMPT}], stream=False,
    )
    sent = client.chat.call_args.kwargs["messages"][0]["content"]
    assert sent.encode("utf-8") == PROMPT.encode("utf-8")
    assert result.encode("utf-8") == OUTPUT.encode("utf-8")
    client.generate.assert_not_called()
    client.list.assert_not_called()


def test_installed_sdk_serializes_and_decodes_chat_without_network(monkeypatch):
    sdk = pytest.importorskip("ollama")
    httpx = pytest.importorskip("httpx")
    original_client = sdk.Client
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": OUTPUT}})

    def client(**kwargs):
        return original_client(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(sdk, "Client", client)

    assert OllamaArtistProvider(model=MODEL, host=HOST).render(PROMPT) == OUTPUT
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert str(requests[0].url) == HOST + "/api/chat"
    body = json.loads(requests[0].content)
    assert body.pop("tools", []) == []  # SDK 0.6.2 serializes its unset tools as [].
    assert body == {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
    }


def test_execution_config_adds_chat_identity_without_inventing_defaults(monkeypatch):
    _install_client(monkeypatch, {"message": {"content": OUTPUT}})
    monkeypatch.setattr("hermeneia.narrative.artist_providers.importlib.metadata.version", lambda name: "test-sdk")
    provider = OllamaArtistProvider(model=MODEL, host=HOST)

    assert provider.provider_name == f"ollama/{MODEL}"
    assert provider.execution_config() == {
        "provider": "ollama",
        "model_id": MODEL,
        "max_tokens": None,
        "endpoint": HOST,
        "sdk_version": "test-sdk",
        "request_schema_version": "1",
        "request_api": "chat",
        "constitutional_profile": CONSTITUTIONAL_PROFILE,
    }


@pytest.mark.parametrize("provider_id", ["ollama-meta", "ollama-local"])
def test_both_registrations_use_the_chat_adapter(monkeypatch, provider_id):
    client, _factory = _install_client(monkeypatch, {"message": {"content": OUTPUT}})
    model = DEFAULT_PROVIDER_REGISTRY.definition(provider_id).default_model
    provider = get_provider(provider_id, model=model, host=HOST)

    assert isinstance(provider, OllamaArtistProvider)
    assert isinstance(provider, ArtistProvider)
    assert provider.render(PROMPT) == OUTPUT
    client.chat.assert_called_once_with(
        model=model, messages=[{"role": "user", "content": PROMPT}], stream=False,
    )
    client.generate.assert_not_called()


@pytest.mark.parametrize("response_shape", ["dict", "sdk"])
def test_connection_only_lists_installed_models(monkeypatch, response_shape):
    models = {"models": [{"model": MODEL}]}
    if response_shape == "sdk":
        models = pytest.importorskip("ollama").ListResponse(models=[{"model": MODEL}])
    client, _factory = _install_client(monkeypatch, {"message": {"content": OUTPUT}})
    client.list.return_value = models

    OllamaArtistProvider(model=MODEL, host=HOST).test_connection()

    client.list.assert_called_once_with()
    client.chat.assert_not_called()
    client.generate.assert_not_called()


def test_connection_refuses_missing_model_without_generation(monkeypatch):
    client, _factory = _install_client(monkeypatch, {"message": {"content": OUTPUT}})
    client.list.return_value = {"models": []}

    with pytest.raises(RuntimeError, match="not installed"):
        OllamaArtistProvider(model=MODEL, host=HOST).test_connection()

    client.chat.assert_not_called()
    client.generate.assert_not_called()


@pytest.mark.parametrize("content", [None, 42])
def test_non_text_chat_content_fails_instead_of_becoming_prose(monkeypatch, content):
    client, _factory = _install_client(monkeypatch, {"message": {"content": content}})

    with pytest.raises(ValueError, match="assistant text"):
        OllamaArtistProvider(model=MODEL, host=HOST).render(PROMPT)

    assert client.chat.call_count == 1
    client.generate.assert_not_called()


def test_chat_failure_propagates_without_retry_or_generate_fallback(monkeypatch):
    client, _factory = _install_client(monkeypatch, {"message": {"content": OUTPUT}})
    client.chat.side_effect = RuntimeError("local chat unavailable")

    with pytest.raises(RuntimeError, match="local chat unavailable"):
        OllamaArtistProvider(model=MODEL, host=HOST).render(PROMPT)

    assert client.chat.call_count == 1
    client.generate.assert_not_called()
