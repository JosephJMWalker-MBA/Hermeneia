"""Test-governance boundaries for Hermeneia's default suite."""
from __future__ import annotations

import os
import socket
import threading

import pytest

from conftest import CLOUD_PROVIDER_ENV_VARS, EXTERNAL_NETWORK_DISABLED_MESSAGE
from hermeneia.narrative.provider_registry import ProviderDefinition


def test_ambient_cloud_credentials_are_neutralized_at_test_start() -> None:
    assert {
        name: name in os.environ
        for name in CLOUD_PROVIDER_ENV_VARS
    } == {name: False for name in CLOUD_PROVIDER_ENV_VARS}


def test_controlled_fake_environment_credential_tests_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = ProviderDefinition(
        id="openai",
        display_name="OpenAI",
        provider_type="artist",
        enabled=True,
        capabilities=("text",),
        local_or_remote="remote",
        required_environment="OPENAI_API_KEY",
        default_model="gpt-4o",
    )

    assert definition.configured() is False
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-value")

    assert definition.configured() is True


def test_external_hostname_resolution_is_blocked_before_network_access() -> None:
    with pytest.raises(RuntimeError, match="External network access is disabled"):
        socket.getaddrinfo("example.com", 443)


def test_external_connection_is_blocked_before_network_access() -> None:
    with pytest.raises(RuntimeError) as exc:
        socket.create_connection(("example.com", 443), timeout=0.01)

    assert str(exc.value) == EXTERNAL_NETWORK_DISABLED_MESSAGE


def test_loopback_socket_communication_remains_allowed() -> None:
    ready = threading.Event()
    received: list[bytes] = []

    def server(sock: socket.socket) -> None:
        sock.listen(1)
        ready.set()
        conn, _addr = sock.accept()
        with conn:
            received.append(conn.recv(16))
            conn.sendall(b"ok")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        thread = threading.Thread(target=server, args=(listener,), daemon=True)
        thread.start()
        assert ready.wait(timeout=2)
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            client.sendall(b"hello")
            assert client.recv(16) == b"ok"
        thread.join(timeout=2)

    assert received == [b"hello"]


def test_live_provider_flag_does_not_open_network_for_unmarked_tests(
    request: pytest.FixtureRequest,
) -> None:
    """Even an opted-in run keeps ordinary unmarked tests hermetic."""
    if not request.config.getoption("--live-providers"):
        pytest.skip("requires --live-providers to exercise the opt-in isolation boundary")

    assert request.node.get_closest_marker("live_provider") is None
    with pytest.raises(RuntimeError) as exc:
        socket.create_connection(("example.com", 443), timeout=0.01)

    assert str(exc.value) == EXTERNAL_NETWORK_DISABLED_MESSAGE


@pytest.mark.live_provider
def test_live_provider_marker_requires_explicit_opt_in() -> None:
    """Marker policy test; no paid provider call is made even when opted in."""
    assert True
