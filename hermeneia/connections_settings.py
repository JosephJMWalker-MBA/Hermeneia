"""Machine/user-scoped non-secret Connections settings.

This store is deliberately separate from Hermeneia investigation databases and
workspace-adjacent calibration. It may record local runtime preferences, but it
must never contain API keys, corpus text, calibration history, or canonical
research objects.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from copy import deepcopy
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CONNECTIONS_SETTINGS_SCHEMA = "hermeneia.connections_settings.v1"
CONNECTIONS_SETTINGS_VERSION = 1
DEFAULT_OLLAMA_HOST = "http://localhost:11434"


class UnsupportedConnectionsSettingsError(RuntimeError):
    """Raised when a valid Hermeneia settings file is newer than this binary."""


class UnreadableConnectionsSettingsError(RuntimeError):
    """Raised when an existing settings file cannot be safely read."""


class InvalidConnectionsSettingError(ValueError):
    """Raised when a proposed non-secret setting violates its boundary."""


def connections_settings_path() -> Path:
    explicit = os.environ.get("HERMENEIA_CONNECTIONS_SETTINGS_PATH")
    if explicit:
        return Path(explicit).expanduser()

    config_home = os.environ.get("HERMENEIA_CONFIG_HOME") or os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / "hermeneia" / "connections.json"

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata).expanduser() / "Hermeneia" / "connections.json"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Hermeneia" / "connections.json"

    return Path.home() / ".config" / "hermeneia" / "connections.json"


def empty_connections_settings() -> dict[str, Any]:
    return {
        "schema": CONNECTIONS_SETTINGS_SCHEMA,
        "version": CONNECTIONS_SETTINGS_VERSION,
        "ollama": {},
        "providers": {},
    }


def _is_hermeneia_connections_schema(value: object) -> bool:
    return isinstance(value, str) and value.startswith("hermeneia.connections_settings.")


def _is_valid_dns_hostname(hostname: str) -> bool:
    if not hostname or len(hostname) > 253:
        return False
    if hostname.endswith("."):
        hostname = hostname[:-1]
    if not hostname:
        return False
    labels = hostname.split(".")
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
        if not all(ch.isalnum() or ch == "-" for ch in label):
            return False
    return True


def _normalized_host(hostname: str) -> str:
    try:
        parsed_ip = ip_address(hostname)
    except ValueError:
        if not _is_valid_dns_hostname(hostname):
            raise InvalidConnectionsSettingError("host must include a valid hostname or IP address")
        return hostname.lower().rstrip(".")
    if parsed_ip.version == 6:
        return f"[{parsed_ip.compressed}]"
    return parsed_ip.compressed


def validate_ollama_host(host: str) -> str:
    value = str(host or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise InvalidConnectionsSettingError("host must begin with http:// or https://")
    if not parsed.hostname:
        raise InvalidConnectionsSettingError("host must include a hostname")
    if any(ch.isspace() for ch in parsed.hostname):
        raise InvalidConnectionsSettingError("host must not contain whitespace")
    if parsed.username or parsed.password:
        raise InvalidConnectionsSettingError("host must not include username or password")
    if parsed.query or parsed.fragment:
        raise InvalidConnectionsSettingError("host must not include query strings or fragments")
    if parsed.path not in {"", "/"}:
        raise InvalidConnectionsSettingError("host must be an Ollama origin, not a URL path")
    if parsed.params:
        raise InvalidConnectionsSettingError("host must not include URL parameters")
    try:
        port = parsed.port
    except ValueError as exc:
        raise InvalidConnectionsSettingError("host port is invalid") from exc
    netloc = _normalized_host(parsed.hostname)
    if port is not None:
        netloc = f"{netloc}:{port}"
    return f"{parsed.scheme}://{netloc}"


def _coerce_settings(raw: object, *, allow_unsupported: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return empty_connections_settings()
    schema = raw.get("schema")
    version = raw.get("version")
    if schema != CONNECTIONS_SETTINGS_SCHEMA:
        if _is_hermeneia_connections_schema(schema) and not allow_unsupported:
            raise UnsupportedConnectionsSettingsError(
                f"Unsupported Hermeneia Connections settings schema: {schema}"
            )
        return empty_connections_settings()
    if version != CONNECTIONS_SETTINGS_VERSION:
        if not allow_unsupported:
            raise UnsupportedConnectionsSettingsError(
                f"Unsupported Hermeneia Connections settings version: {version}"
            )
        return empty_connections_settings()
    settings = empty_connections_settings()
    ollama = raw.get("ollama")
    if isinstance(ollama, dict):
        host = str(ollama.get("host") or "").strip()
        if host:
            try:
                settings["ollama"]["host"] = validate_ollama_host(host)
            except InvalidConnectionsSettingError:
                pass
    providers = raw.get("providers")
    if isinstance(providers, dict):
        for provider_id, provider_settings in providers.items():
            if not isinstance(provider_id, str) or not isinstance(provider_settings, dict):
                continue
            selected_model = str(provider_settings.get("selected_model") or "").strip()
            credential_source = provider_settings.get("credential_source")
            clean_provider: dict[str, Any] = {}
            if selected_model:
                clean_provider["selected_model"] = selected_model
            if isinstance(credential_source, dict):
                kind = str(credential_source.get("kind") or "").strip()
                environment_variable = str(
                    credential_source.get("environment_variable") or ""
                ).strip()
                clean_source: dict[str, str] = {}
                if kind:
                    clean_source["kind"] = kind
                if environment_variable:
                    clean_source["environment_variable"] = environment_variable
                if clean_source:
                    clean_provider["credential_source"] = clean_source
            if clean_provider:
                settings["providers"][provider_id] = clean_provider
    return settings


def load_connections_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or connections_settings_path()
    try:
        raw = json.loads(settings_path.read_text())
    except FileNotFoundError:
        return empty_connections_settings()
    except json.JSONDecodeError:
        return empty_connections_settings()
    except OSError as exc:
        raise UnreadableConnectionsSettingsError(
            "Connections settings file exists but could not be read. "
            "Fix file permissions or move the unreadable file before changing Connections settings."
        ) from exc
    return _coerce_settings(raw)


def save_connections_settings(settings: dict[str, Any], path: Path | None = None) -> None:
    settings_path = path or connections_settings_path()
    clean = _coerce_settings(settings)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{settings_path.name}.",
        suffix=".tmp",
        dir=str(settings_path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(clean, tmp, indent=2, ensure_ascii=False, sort_keys=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        Path(tmp_name).replace(settings_path)
    except Exception:
        try:
            Path(tmp_name).unlink()
        except OSError:
            pass
        raise


def selected_ollama_model(settings: dict[str, Any], provider_id: str) -> str | None:
    providers = settings.get("providers")
    if not isinstance(providers, dict):
        return None
    provider_settings = providers.get(provider_id)
    if not isinstance(provider_settings, dict):
        return None
    selected = str(provider_settings.get("selected_model") or "").strip()
    return selected or None


def set_selected_ollama_model(
    settings: dict[str, Any],
    provider_id: str,
    model: str,
) -> dict[str, Any]:
    next_settings = _coerce_settings(deepcopy(settings))
    provider_settings = next_settings["providers"].setdefault(provider_id, {})
    provider_settings["selected_model"] = model
    provider_settings["credential_source"] = {"kind": "not_required"}
    return next_settings


def ollama_host_from_settings(settings: dict[str, Any]) -> str | None:
    ollama = settings.get("ollama")
    if not isinstance(ollama, dict):
        return None
    host = str(ollama.get("host") or "").strip()
    return host or None


def set_ollama_host(settings: dict[str, Any], host: str) -> dict[str, Any]:
    next_settings = _coerce_settings(deepcopy(settings))
    next_settings["ollama"]["host"] = validate_ollama_host(host)
    return next_settings
