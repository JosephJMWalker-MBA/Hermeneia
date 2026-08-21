"""Governed local Ollama model management.

This module intentionally exposes semantic operations only. It is not a shell
or terminal wrapper.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable


_MODEL_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:/[A-Za-z0-9][A-Za-z0-9._-]*){0,2}"
    r"(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)


class OllamaModelInstallError(RuntimeError):
    """Raised when the governed Ollama model install operation fails."""


class InvalidOllamaModelIdentity(ValueError):
    """Raised when a model identity is not safe or well formed."""


@dataclass(frozen=True)
class OllamaInstallEvent:
    """One non-secret progress event from an Ollama pull operation."""

    status: str
    detail: str | None = None
    completed: int | None = None
    total: int | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"status": self.status}
        if self.detail:
            data["detail"] = self.detail
        if self.completed is not None:
            data["completed"] = self.completed
        if self.total is not None:
            data["total"] = self.total
        return data


def validate_ollama_model_identity(model_id: str) -> str:
    """Return a normalized model identity or raise.

    Ollama model names are data. Keep them narrow so they can never become a
    shell surface if a future backend changes the execution mechanism.
    """
    model = str(model_id or "").strip()
    if not model:
        raise InvalidOllamaModelIdentity("model is required")
    if len(model) > 160:
        raise InvalidOllamaModelIdentity("model identity is too long")
    if not _MODEL_ID_RE.fullmatch(model):
        raise InvalidOllamaModelIdentity(
            "model identity may contain only letters, numbers, '.', '_', '-', '/', and one optional ':tag'"
        )
    return model


def _event_from_chunk(chunk: object) -> OllamaInstallEvent:
    if isinstance(chunk, dict):
        status = str(chunk.get("status") or chunk.get("message") or "working").strip()
        detail = str(chunk.get("digest") or chunk.get("name") or "").strip() or None
        completed = chunk.get("completed")
        total = chunk.get("total")
    else:
        status = str(getattr(chunk, "status", "") or getattr(chunk, "message", "") or "working").strip()
        detail = str(getattr(chunk, "digest", "") or getattr(chunk, "name", "") or "").strip() or None
        completed = getattr(chunk, "completed", None)
        total = getattr(chunk, "total", None)
    clean_status = status[:160] if status else "working"
    try:
        completed_int = int(completed) if completed is not None else None
    except (TypeError, ValueError):
        completed_int = None
    try:
        total_int = int(total) if total is not None else None
    except (TypeError, ValueError):
        total_int = None
    return OllamaInstallEvent(
        status=clean_status,
        detail=detail[:96] if detail else None,
        completed=completed_int,
        total=total_int,
    )


def install_ollama_model(
    *,
    host: str,
    model_id: str,
    client_factory: Callable[..., Any] | None = None,
) -> list[OllamaInstallEvent]:
    """Pull one validated model through the Ollama client API.

    No shell command is accepted or composed. The public operation is
    "install this model identity on this configured runtime."
    """
    model = validate_ollama_model_identity(model_id)
    try:
        if client_factory is None:
            import ollama as _ollama

            client_factory = _ollama.Client
        client = client_factory(host=host)
    except ImportError as exc:
        raise OllamaModelInstallError("Ollama Python package is not installed.") from exc
    except Exception as exc:
        raise OllamaModelInstallError("Ollama runtime client could not be created.") from exc

    try:
        result = client.pull(model, stream=True)
        events: list[OllamaInstallEvent] = [
            OllamaInstallEvent(status="installing", detail=f"pull {model}")
        ]
        if isinstance(result, dict):
            events.append(_event_from_chunk(result))
        else:
            for chunk in result if isinstance(result, Iterable) else (result,):
                events.append(_event_from_chunk(chunk))
        if not events or events[-1].status.lower() not in {"success", "done"}:
            events.append(OllamaInstallEvent(status="success", detail=f"{model} installed"))
        return events
    except Exception as exc:
        raise OllamaModelInstallError("Ollama model install failed. Check runtime connectivity, network access, and disk space.") from exc
