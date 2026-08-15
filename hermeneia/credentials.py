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
        backend = keyring.get_keyring()
        backend_module = backend.__class__.__module__.lower()
        backend_name = backend.__class__.__name__
        priority = getattr(backend, "priority", 0)
        if "keyring.backends.fail" in backend_module:
            raise CredentialStoreUnavailable(
                "No system credential backend is available for this runtime."
            )
        if "keyring.backends.null" in backend_module or "plaintext" in backend_module:
            raise CredentialStoreUnavailable(
                "Refusing to use an insecure plaintext credential backend."
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
        self._keyring.set_password(SERVICE_NAME, provider_id, secret)

    def get_password(self, provider_id: str) -> str | None:
        return self._keyring.get_password(SERVICE_NAME, provider_id)

    def delete_password(self, provider_id: str) -> None:
        try:
            self._keyring.delete_password(SERVICE_NAME, provider_id)
        except Exception as exc:
            if exc.__class__.__name__ == "PasswordDeleteError":
                return
            raise


def default_credential_store() -> CredentialStore:
    try:
        return KeyringCredentialStore()
    except CredentialStoreUnavailable as exc:
        return UnavailableCredentialStore(str(exc))
