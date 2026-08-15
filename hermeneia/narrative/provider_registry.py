"""Non-epistemic Artist provider configuration.

Provider definitions describe adapter availability only. They are not
canonical objects, do not participate in lineage, and convey no semantic
standing. Provider and model identity belong instead to each persisted
RenderedNarrative execution audit record.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Any, Callable


ProviderFactory = Callable[..., Any]


@dataclass(frozen=True)
class ModelCatalogEntry:
    """Non-canonical model metadata exposed by a provider connection."""

    model_id: str
    provider_id: str
    display_label: str | None = None
    family: str | None = None
    snapshot: str | None = None
    availability: str = "available"
    catalog_source: str = "provider_api"
    capabilities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.model_id,
            "model_id": self.model_id,
            "display_label": self.display_label,
            "family": self.family,
            "snapshot": self.snapshot,
            "availability": self.availability,
            "provider": self.provider_id,
            "catalog_source": self.catalog_source,
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True)
class ModelCatalog:
    """Normalized, non-canonical model catalog for one provider connection."""

    provider_id: str
    catalog_source: str
    status: str
    models: tuple[ModelCatalogEntry, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider_id,
            "catalog_source": self.catalog_source,
            "status": self.status,
            "error": self.error,
            "models": [entry.to_dict() for entry in self.models],
        }


def unavailable_model_catalog(provider_id: str, error: str) -> ModelCatalog:
    return ModelCatalog(
        provider_id=provider_id,
        catalog_source="unavailable",
        status="unavailable",
        error=error,
    )


@dataclass(frozen=True)
class ProviderDefinition:
    """Immutable descriptive metadata for one Artist adapter."""

    id: str
    display_name: str
    provider_type: str
    enabled: bool
    capabilities: tuple[str, ...]
    local_or_remote: str
    required_environment: str | None = None
    sdk_module: str | None = None
    default_model: str | None = None

    def configured(self) -> bool:
        """Whether required local configuration is present.

        Environment-variable values are intentionally never returned.
        """
        return (
            self.required_environment is None
            or bool(os.environ.get(self.required_environment))
        )

    def adapter_available(self) -> bool:
        """Whether the adapter's Python dependency is importable."""
        if self.sdk_module is None:
            return True
        try:
            return importlib.util.find_spec(self.sdk_module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    def is_available_artist(self) -> bool:
        """Whether this definition can currently execute as an Artist."""
        return (
            self.provider_type == "artist"
            and self.enabled
            and self.configured()
            and self.adapter_available()
        )

    def metadata(self) -> dict[str, object]:
        """Public ecology metadata with no secret values or quality claims."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "provider_type": self.provider_type,
            "enabled": self.enabled,
            "configured": self.configured(),
            "adapter_available": self.adapter_available(),
            "capabilities": list(self.capabilities),
            "local_or_remote": self.local_or_remote,
            "required_environment": self.required_environment,
            "default_model": self.default_model,
        }


@dataclass(frozen=True)
class ProviderRegistration:
    """One immutable pairing of descriptive metadata and adapter factory."""

    definition: ProviderDefinition
    factory: ProviderFactory


@dataclass(frozen=True)
class ProviderRegistry:
    """Immutable, reconstructible collection of Artist adapter definitions."""

    registrations: tuple[ProviderRegistration, ...] = ()

    def __post_init__(self) -> None:
        ids = [registration.definition.id for registration in self.registrations]
        if len(ids) != len(set(ids)):
            raise ValueError("Provider IDs must be unique")

    def with_provider(
        self,
        definition: ProviderDefinition,
        factory: ProviderFactory,
    ) -> "ProviderRegistry":
        """Return a new registry containing an additional conforming adapter."""
        if definition.id in self.ids():
            raise ValueError(f"Provider already registered: {definition.id}")
        return ProviderRegistry(
            registrations=(
                *self.registrations,
                ProviderRegistration(definition=definition, factory=factory),
            )
        )

    def without(self, *provider_ids: str) -> "ProviderRegistry":
        """Return a new registry without selected adapters."""
        excluded = set(provider_ids)
        return ProviderRegistry(
            registrations=tuple(
                registration
                for registration in self.registrations
                if registration.definition.id not in excluded
            )
        )

    def ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                registration.definition.id
                for registration in self.registrations
            )
        )

    def definition(self, provider_id: str) -> ProviderDefinition:
        for registration in self.registrations:
            if registration.definition.id == provider_id:
                return registration.definition
        raise KeyError(provider_id)

    def create(self, provider_id: str, **kwargs: object) -> Any:
        for registration in self.registrations:
            if registration.definition.id == provider_id:
                return registration.factory(**kwargs)
        available = " | ".join(self.ids())
        raise ValueError(
            f"Unknown provider '{provider_id}'. Available: {available}. "
            "Add a conforming ArtistProvider adapter to the registry."
        )

    def ecology(self) -> dict[str, object]:
        """Read-only provider ecology projection."""
        definitions = sorted(
            (
                registration.definition
                for registration in self.registrations
            ),
            key=lambda definition: definition.id,
        )
        providers = [definition.metadata() for definition in definitions]
        return {
            "providers": providers,
            "available_artists": [
                definition.id
                for definition in definitions
                if definition.is_available_artist()
            ],
            "configured": [
                definition.id
                for definition in definitions
                if definition.configured()
            ],
            "unavailable": [
                definition.id
                for definition in definitions
                if not definition.is_available_artist()
            ],
        }
