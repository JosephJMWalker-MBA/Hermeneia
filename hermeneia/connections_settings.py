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
from hashlib import sha256
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


CONNECTIONS_SETTINGS_SCHEMA = "hermeneia.connections_settings.v1"
CONNECTIONS_SETTINGS_VERSION = 2
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
VALID_CREDENTIAL_SOURCE_KINDS = {"session", "environment", "system_store", "not_required"}


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


def normalized_configuration_parameters(parameters: dict[str, Any] | None) -> dict[str, object]:
    if not isinstance(parameters, dict):
        return {}
    clean: dict[str, object] = {}
    for key, value in sorted(parameters.items()):
        name = str(key or "").strip()
        if not name:
            continue
        if isinstance(value, bool) or value is None:
            clean[name] = value
        elif isinstance(value, int):
            clean[name] = value
        elif isinstance(value, float):
            clean[name] = value
        elif isinstance(value, str):
            clean[name] = value.strip()
    return clean


def model_configuration_revision(
    provider_id: str,
    model_id: str,
    parameters: dict[str, Any] | None,
) -> str:
    payload = {
        "provider_id": provider_id,
        "model_id": model_id,
        "parameters": normalized_configuration_parameters(parameters),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "rev_" + sha256(encoded.encode("utf-8")).hexdigest()[:16]


def model_configuration_fingerprint(
    provider_id: str,
    model_id: str,
    parameters: dict[str, Any] | None,
) -> str:
    payload = {
        "provider_id": provider_id,
        "model_id": model_id,
        "parameters": normalized_configuration_parameters(parameters),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "cfgfp_" + sha256(encoded.encode("utf-8")).hexdigest()[:16]


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


def _coerce_model_configuration(
    provider_id: str,
    config: object,
) -> dict[str, object] | None:
    if not isinstance(config, dict):
        return None
    configuration_id = str(config.get("configuration_id") or "").strip()
    label = str(config.get("label") or "").strip()
    model_id = str(config.get("model_id") or "").strip()
    stored_provider_id = str(config.get("provider_id") or provider_id).strip()
    if not configuration_id or not model_id or stored_provider_id != provider_id:
        return None
    parameters = normalized_configuration_parameters(
        config.get("parameters") if isinstance(config.get("parameters"), dict) else {}
    )
    return {
        "configuration_id": configuration_id,
        "label": label or model_id,
        "provider_id": provider_id,
        "model_id": model_id,
        "parameters": parameters,
        "revision": model_configuration_revision(provider_id, model_id, parameters),
    }


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
    if version not in {1, CONNECTIONS_SETTINGS_VERSION}:
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
            selected_configuration_id = str(
                provider_settings.get("selected_configuration_id") or ""
            ).strip()
            credential_source = provider_settings.get("credential_source")
            clean_provider: dict[str, Any] = {}
            if selected_model:
                clean_provider["selected_model"] = selected_model
            configurations = provider_settings.get("saved_model_configurations")
            clean_configurations: list[dict[str, object]] = []
            if isinstance(configurations, list):
                for config in configurations:
                    clean_config = _coerce_model_configuration(provider_id, config)
                    if clean_config:
                        clean_configurations.append(clean_config)
            if clean_configurations:
                clean_provider["saved_model_configurations"] = clean_configurations
                config_ids = {
                    str(config["configuration_id"])
                    for config in clean_configurations
                }
                if selected_configuration_id in config_ids:
                    clean_provider["selected_configuration_id"] = selected_configuration_id
            if isinstance(credential_source, dict):
                kind = str(credential_source.get("kind") or "").strip()
                environment_variable = str(
                    credential_source.get("environment_variable") or ""
                ).strip()
                service = str(credential_source.get("service") or "").strip()
                account = str(credential_source.get("account") or "").strip()
                configured = bool(credential_source.get("configured"))
                clean_source: dict[str, object] = {}
                if kind in VALID_CREDENTIAL_SOURCE_KINDS:
                    clean_source["kind"] = kind
                if kind == "environment" and environment_variable:
                    clean_source["environment_variable"] = environment_variable
                if kind == "system_store":
                    clean_source["configured"] = configured
                    if service:
                        clean_source["service"] = service
                    if account:
                        clean_source["account"] = account
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


def selected_provider_model(settings: dict[str, Any], provider_id: str) -> str | None:
    providers = settings.get("providers")
    if not isinstance(providers, dict):
        return None
    provider_settings = providers.get(provider_id)
    if not isinstance(provider_settings, dict):
        return None
    selected = str(provider_settings.get("selected_model") or "").strip()
    return selected or None


def saved_model_configurations(
    settings: dict[str, Any],
    provider_id: str,
) -> list[dict[str, object]]:
    providers = settings.get("providers")
    if not isinstance(providers, dict):
        return []
    provider_settings = providers.get(provider_id)
    if not isinstance(provider_settings, dict):
        return []
    configs = provider_settings.get("saved_model_configurations")
    if not isinstance(configs, list):
        return []
    return [
        dict(config)
        for config in configs
        if isinstance(config, dict)
    ]


def saved_model_configuration(
    settings: dict[str, Any],
    provider_id: str,
    configuration_id: str,
) -> dict[str, object] | None:
    for config in saved_model_configurations(settings, provider_id):
        if str(config.get("configuration_id") or "") == configuration_id:
            return config
    return None


def selected_provider_configuration_id(
    settings: dict[str, Any],
    provider_id: str,
) -> str | None:
    providers = settings.get("providers")
    if not isinstance(providers, dict):
        return None
    provider_settings = providers.get(provider_id)
    if not isinstance(provider_settings, dict):
        return None
    selected = str(provider_settings.get("selected_configuration_id") or "").strip()
    return selected or None


def set_selected_provider_model(
    settings: dict[str, Any],
    provider_id: str,
    model: str,
) -> dict[str, Any]:
    next_settings = _coerce_settings(deepcopy(settings))
    provider_settings = next_settings["providers"].setdefault(provider_id, {})
    provider_settings["selected_model"] = model
    provider_settings.pop("selected_configuration_id", None)
    return next_settings


def set_selected_provider_configuration(
    settings: dict[str, Any],
    provider_id: str,
    configuration_id: str | None,
) -> dict[str, Any]:
    next_settings = _coerce_settings(deepcopy(settings))
    provider_settings = next_settings["providers"].setdefault(provider_id, {})
    if configuration_id is None:
        provider_settings.pop("selected_configuration_id", None)
        return next_settings
    config = saved_model_configuration(next_settings, provider_id, configuration_id)
    if config is None:
        raise InvalidConnectionsSettingError("saved configuration does not exist")
    provider_settings["selected_configuration_id"] = configuration_id
    provider_settings["selected_model"] = str(config["model_id"])
    return next_settings


def upsert_saved_model_configuration(
    settings: dict[str, Any],
    provider_id: str,
    config: dict[str, object],
) -> dict[str, Any]:
    next_settings = _coerce_settings(deepcopy(settings))
    provider_settings = next_settings["providers"].setdefault(provider_id, {})
    clean = _coerce_model_configuration(provider_id, config)
    if clean is None:
        raise InvalidConnectionsSettingError("invalid saved model configuration")
    configs = [
        dict(existing)
        for existing in provider_settings.get("saved_model_configurations", [])
        if isinstance(existing, dict)
        and existing.get("configuration_id") != clean["configuration_id"]
    ]
    configs.append(clean)
    configs.sort(key=lambda item: (str(item.get("label") or ""), str(item.get("configuration_id") or "")))
    provider_settings["saved_model_configurations"] = configs
    return next_settings


def delete_saved_model_configuration(
    settings: dict[str, Any],
    provider_id: str,
    configuration_id: str,
) -> dict[str, Any]:
    next_settings = _coerce_settings(deepcopy(settings))
    provider_settings = next_settings["providers"].setdefault(provider_id, {})
    if provider_settings.get("selected_configuration_id") == configuration_id:
        raise InvalidConnectionsSettingError(
            "cannot delete the active saved configuration; select bare model defaults first"
        )
    configs = [
        dict(existing)
        for existing in provider_settings.get("saved_model_configurations", [])
        if isinstance(existing, dict)
        and existing.get("configuration_id") != configuration_id
    ]
    provider_settings["saved_model_configurations"] = configs
    return next_settings


def selected_ollama_model(settings: dict[str, Any], provider_id: str) -> str | None:
    return selected_provider_model(settings, provider_id)


def set_selected_ollama_model(
    settings: dict[str, Any],
    provider_id: str,
    model: str,
) -> dict[str, Any]:
    next_settings = set_selected_provider_model(settings, provider_id, model)
    next_settings["providers"][provider_id]["credential_source"] = {"kind": "not_required"}
    return next_settings


def provider_credential_source(
    settings: dict[str, Any],
    provider_id: str,
) -> dict[str, object] | None:
    providers = settings.get("providers")
    if not isinstance(providers, dict):
        return None
    provider_settings = providers.get(provider_id)
    if not isinstance(provider_settings, dict):
        return None
    source = provider_settings.get("credential_source")
    if not isinstance(source, dict):
        return None
    return dict(source)


def set_provider_credential_source(
    settings: dict[str, Any],
    provider_id: str,
    source: dict[str, object],
) -> dict[str, Any]:
    next_settings = _coerce_settings(deepcopy(settings))
    kind = str(source.get("kind") or "").strip()
    if kind not in VALID_CREDENTIAL_SOURCE_KINDS:
        raise InvalidConnectionsSettingError("unsupported credential source kind")
    provider_settings = next_settings["providers"].setdefault(provider_id, {})
    clean_source: dict[str, object] = {"kind": kind}
    if kind == "environment":
        env_name = str(source.get("environment_variable") or "").strip()
        if not env_name:
            raise InvalidConnectionsSettingError("environment credential source requires an environment variable")
        clean_source["environment_variable"] = env_name
    elif kind == "system_store":
        clean_source["configured"] = bool(source.get("configured"))
        service = str(source.get("service") or "").strip()
        account = str(source.get("account") or "").strip()
        if service:
            clean_source["service"] = service
        if account:
            clean_source["account"] = account
    provider_settings["credential_source"] = clean_source
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
