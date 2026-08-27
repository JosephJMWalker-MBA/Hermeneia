"""Default Hermeneia test governance.

The ordinary test suite is hermetic with respect to cloud provider credentials
and external network access. Production credential discovery remains in
production code; this file only governs pytest runs.
"""
from __future__ import annotations

import os
import socket
from ipaddress import ip_address
from typing import Any

import pytest


CLOUD_PROVIDER_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "XAI_API_KEY",
    "XAI_BASE_URL",
)

EXTERNAL_NETWORK_DISABLED_MESSAGE = (
    "External network access is disabled in Hermeneia's default test suite. "
    "Mark intentional live-provider tests with @pytest.mark.live_provider "
    "and run with --live-providers."
)

_CAPTURED_CLOUD_ENV = {
    name: os.environ[name]
    for name in CLOUD_PROVIDER_ENV_VARS
    if name in os.environ
}
for _name in CLOUD_PROVIDER_ENV_VARS:
    os.environ.pop(_name, None)

_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_ORIGINAL_CREATE_CONNECTION = socket.create_connection
_ORIGINAL_SOCKET_CONNECT = socket.socket.connect
_ORIGINAL_SOCKET_CONNECT_EX = socket.socket.connect_ex
_SOCKET_GUARD_INSTALLED = False
_LIVE_PROVIDER_ALLOWED = False


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-providers",
        action="store_true",
        default=False,
        help="allow tests marked live_provider to use ambient cloud credentials and external network",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_provider: intentional live provider/network test; skipped unless --live-providers is supplied",
    )
    _install_socket_guard()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--live-providers"):
        return
    skip_live = pytest.mark.skip(reason="live provider test requires --live-providers")
    for item in items:
        if item.get_closest_marker("live_provider") is not None:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _hermetic_cloud_provider_boundary(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    marked_live = request.node.get_closest_marker("live_provider") is not None
    live_enabled = bool(request.config.getoption("--live-providers") and marked_live)
    if live_enabled:
        for name in CLOUD_PROVIDER_ENV_VARS:
            if name in _CAPTURED_CLOUD_ENV:
                monkeypatch.setenv(name, _CAPTURED_CLOUD_ENV[name])
            else:
                monkeypatch.delenv(name, raising=False)
    else:
        for name in CLOUD_PROVIDER_ENV_VARS:
            monkeypatch.delenv(name, raising=False)
    _set_live_provider_allowed(live_enabled)
    try:
        yield
    finally:
        _set_live_provider_allowed(False)


def pytest_unconfigure(config: pytest.Config) -> None:
    _restore_socket_guard()
    for name in CLOUD_PROVIDER_ENV_VARS:
        if name in _CAPTURED_CLOUD_ENV:
            os.environ[name] = _CAPTURED_CLOUD_ENV[name]
        else:
            os.environ.pop(name, None)


def _set_live_provider_allowed(value: bool) -> None:
    global _LIVE_PROVIDER_ALLOWED
    _LIVE_PROVIDER_ALLOWED = value


def _install_socket_guard() -> None:
    global _SOCKET_GUARD_INSTALLED
    if _SOCKET_GUARD_INSTALLED:
        return
    socket.getaddrinfo = _guarded_getaddrinfo  # type: ignore[assignment]
    socket.create_connection = _guarded_create_connection  # type: ignore[assignment]
    socket.socket.connect = _guarded_socket_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guarded_socket_connect_ex  # type: ignore[method-assign]
    _SOCKET_GUARD_INSTALLED = True


def _restore_socket_guard() -> None:
    global _SOCKET_GUARD_INSTALLED
    if not _SOCKET_GUARD_INSTALLED:
        return
    socket.getaddrinfo = _ORIGINAL_GETADDRINFO  # type: ignore[assignment]
    socket.create_connection = _ORIGINAL_CREATE_CONNECTION  # type: ignore[assignment]
    socket.socket.connect = _ORIGINAL_SOCKET_CONNECT  # type: ignore[method-assign]
    socket.socket.connect_ex = _ORIGINAL_SOCKET_CONNECT_EX  # type: ignore[method-assign]
    _SOCKET_GUARD_INSTALLED = False


def _guarded_getaddrinfo(
    host: Any,
    port: Any,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
) -> list[Any]:
    _require_local_or_live(host)
    return _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)


def _guarded_create_connection(
    address: tuple[Any, ...],
    timeout: float | object = socket._GLOBAL_DEFAULT_TIMEOUT,
    source_address: tuple[Any, ...] | None = None,
) -> socket.socket:
    host = address[0] if address else None
    _require_local_or_live(host)
    return _ORIGINAL_CREATE_CONNECTION(address, timeout, source_address)


def _guarded_socket_connect(self: socket.socket, address: Any) -> None:
    _require_socket_address_local_or_live(address)
    return _ORIGINAL_SOCKET_CONNECT(self, address)


def _guarded_socket_connect_ex(self: socket.socket, address: Any) -> int:
    _require_socket_address_local_or_live(address)
    return _ORIGINAL_SOCKET_CONNECT_EX(self, address)


def _require_socket_address_local_or_live(address: Any) -> None:
    if isinstance(address, tuple) and address:
        _require_local_or_live(address[0])


def _require_local_or_live(host: Any) -> None:
    if _LIVE_PROVIDER_ALLOWED:
        return
    if _is_local_host(host):
        return
    raise RuntimeError(EXTERNAL_NETWORK_DISABLED_MESSAGE)


def _is_local_host(host: Any) -> bool:
    if host in (None, ""):
        return True
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    value = host.strip().lower()
    if value in {"localhost", "localhost.", "::1", "[::1]"}:
        return True
    if value.endswith(".localhost"):
        return True
    bracketless = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    try:
        parsed = ip_address(bracketless)
    except ValueError:
        return False
    return parsed.is_loopback or parsed.is_unspecified
