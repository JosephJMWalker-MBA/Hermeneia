"""Secure credential-store boundary for Connections.

This module intentionally has no plaintext fallback. A system credential store
is available only when a mature OS/backend integration can actually store the
secret outside Hermeneia files.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Protocol


SERVICE_NAME = "Hermeneia Connections"

_SYSTEM_BACKEND_MARKERS = (
    "keyring.backends.macos",
    "keyring.backends.secretservice",
    "keyring.backends.kwallet",
    "keyring.backends.windows",
)
_INSECURE_BACKEND_MARKERS = (
    "keyring.backends.fail",
    "keyring.backends.null",
    "keyrings.alt",
    "plaintext",
    "plain",
    "file",
    "cryptfile",
    "encryptedfile",
)


class CredentialStoreError(RuntimeError):
    """Base error for credential-store operations."""


class CredentialStoreUnavailable(CredentialStoreError):
    """Raised when no secure system credential backend is available."""


class CredentialStore(Protocol):
    def available(self) -> bool:
        ...

    def status(self) -> dict[str, object]:
        ...

    def set_password(self, provider_id: str, secret: str) -> None:
        ...

    def get_password(self, provider_id: str) -> str | None:
        ...

    def has_password(self, provider_id: str) -> bool:
        ...

    def delete_password(self, provider_id: str) -> None:
        ...


@dataclass
class UnavailableCredentialStore:
    reason: str

    def available(self) -> bool:
        return False

    def status(self) -> dict[str, object]:
        return {
            "available": False,
            "backend": None,
            "message": self.reason,
        }

    def set_password(self, provider_id: str, secret: str) -> None:
        raise CredentialStoreUnavailable(self.reason)

    def get_password(self, provider_id: str) -> str | None:
        raise CredentialStoreUnavailable(self.reason)

    def has_password(self, provider_id: str) -> bool:
        raise CredentialStoreUnavailable(self.reason)

    def delete_password(self, provider_id: str) -> None:
        raise CredentialStoreUnavailable(self.reason)


class KeyringCredentialStore:
    def __init__(self) -> None:
        if importlib.util.find_spec("keyring") is None:
            raise CredentialStoreUnavailable(
                "Python keyring is not installed; system credential store is unavailable."
            )
        import keyring  # type: ignore

        self._keyring = keyring
        try:
            backend = keyring.get_keyring()
        except Exception as exc:
            raise CredentialStoreUnavailable(
                "System credential backend could not be initialized."
            ) from exc
        backend_module = backend.__class__.__module__.lower()
        backend_name = backend.__class__.__name__
        backend_identity = f"{backend_module}.{backend_name.lower()}"
        priority = getattr(backend, "priority", 0)
        if any(marker in backend_identity for marker in _INSECURE_BACKEND_MARKERS):
            raise CredentialStoreUnavailable(
                "Refusing to use a non-system or insecure credential backend."
            )
        if not any(marker in backend_module for marker in _SYSTEM_BACKEND_MARKERS):
            raise CredentialStoreUnavailable(
                "No recognized system credential backend is available for this runtime."
            )
        try:
            if float(priority) <= 0:
                raise CredentialStoreUnavailable(
                    "No usable system credential backend is available for this runtime."
                )
        except (TypeError, ValueError):
            raise CredentialStoreUnavailable(
                "System credential backend priority could not be verified."
            ) from None
        self._backend_name = f"{backend.__class__.__module__}.{backend_name}"

    def available(self) -> bool:
        return True

    def status(self) -> dict[str, object]:
        return {
            "available": True,
            "backend": self._backend_name,
            "message": "System credential store is available.",
        }

    def set_password(self, provider_id: str, secret: str) -> None:
        try:
            self._keyring.set_password(SERVICE_NAME, provider_id, secret)
        except Exception as exc:
            raise CredentialStoreError("System credential store write failed.") from exc

    def get_password(self, provider_id: str) -> str | None:
        try:
            return self._keyring.get_password(SERVICE_NAME, provider_id)
        except Exception as exc:
            raise CredentialStoreError("System credential store read failed.") from exc

    def has_password(self, provider_id: str) -> bool:
        return self.get_password(provider_id) is not None

    def delete_password(self, provider_id: str) -> None:
        if self.get_password(provider_id) is None:
            return
        try:
            self._keyring.delete_password(SERVICE_NAME, provider_id)
        except Exception as exc:
            raise CredentialStoreError("System credential store delete failed.") from exc


def default_credential_store() -> CredentialStore:
    try:
        return KeyringCredentialStore()
    except CredentialStoreUnavailable as exc:
        return UnavailableCredentialStore(str(exc))
    except Exception:
        return UnavailableCredentialStore("System credential store is unavailable.")
