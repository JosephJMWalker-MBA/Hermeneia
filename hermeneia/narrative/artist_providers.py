"""
ArtistProvider — the Protocol all rendering backends must implement.

The Artist occupies one box out of nine in the Hermeneia pipeline.
It is responsible only for expression — converting a fully-specified
ArchitectPlan into prose. It invents no meaning: all semantic commitments
come from the epistemic chain above it.

The prompt passed to each provider is generated deterministically from
the ArchitectPlan, so it is itself an inspectable artifact traceable to
the Blueprint, interpretations, and observations that preceded it.

Available providers:
  null        NullArtistProvider       — placeholder; no config required
  anthropic   AnthropicArtistProvider  — pip install anthropic  + ANTHROPIC_API_KEY
  openai      OpenAIArtistProvider     — pip install openai     + OPENAI_API_KEY
  gemini      GeminiArtistProvider     — pip install google-genai + GEMINI_API_KEY
  grok        GrokArtistProvider       — pip install openai     + XAI_API_KEY
  ollama      OllamaArtistProvider     — pip install ollama     + local Ollama service
"""
from __future__ import annotations

import importlib.metadata
import json
import os
import sqlite3
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from .provider_registry import (
    ProviderDefinition,
    ProviderRegistration,
    ProviderRegistry,
)


# ── Constitutional profile ────────────────────────────────────────────────────
# Preserved in every execution_config so future audits can identify the governing
# constitutional regime under which an expression was produced.
CONSTITUTIONAL_PROFILE = {
    "constitution_version": "1.0.0",
    "authority_index_version": "1.0.0",
    "invariant_profile": "CI-001..CI-016",
    "architecture_profile": "v1.0",
}


# ── Protocol ──────────────────────────────────────────────────────────────────

@runtime_checkable
class ArtistProvider(Protocol):
    """All Artist backends must implement this interface."""

    @property
    def provider_name(self) -> str:
        """Short, stable identifier used for storage and display (e.g. 'anthropic')."""
        ...

    def render(self, prompt: str) -> str:
        """Render prose from the generated prompt. Returns the prose text only."""
        ...

    def test_connection(self) -> None:
        """Verify provider access without generating a RenderedNarrative."""
        ...

    def execution_config(self) -> dict[str, Any]:
        """CI-011: Return the full nondeterministic audit record for this invocation.

        Must include at minimum:
          provider, model_id, max_tokens, sdk_version, request_schema_version.
        Optional: temperature, top_p, seed, endpoint.
        """
        ...


# ── Prompt generator ──────────────────────────────────────────────────────────

def generate_prompt(
    plan: dict,
    paragraphs: list[dict],
    conn: sqlite3.Connection,
    theme: dict | None = None,
) -> str:
    """Deterministically generate the Artist's prompt from an ArchitectPlan.

    The prompt is a structured specification, not a creative brief.
    All meaning comes from the plan; the Artist supplies only expression.
    If a theme dict is provided (from system_prompts table) its focus and
    quality_criteria are injected into the system instructions.
    """
    # Build OBS-N index for human-readable references
    all_ids = [
        r[0] for r in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]
    id_to_n = {oid: i + 1 for i, oid in enumerate(all_ids)}

    lines = [
        "You are the Artist.",
        "",
        "You are responsible only for expression.",
        "Do not invent meaning. Do not add claims, evidence, or interpretation.",
        "Every semantic commitment listed below must be communicated — not as vocabulary",
        "to include, but as ideas that must be genuinely present in the prose.",
        "Write clearly. Cite evidence through argument, not footnotes.",
        "",
    ]

    if theme:
        # Support both old (focus/quality_criteria) and new (artist_prompt/critic_expectations) field names
        artist_directive = theme.get("artist_prompt") or theme.get("focus", "")
        lang = theme.get("language", "en")
        lang_note = f"  Language: {lang}" if lang != "en" else ""
        lines += [
            f"Expression Profile: {theme['name']}",
            "",
        ]
        if theme.get("description"):
            lines += [f"  {theme['description']}", ""]
        if lang_note:
            lines += [lang_note, ""]
        if theme.get("audience"):
            lines += [f"  Audience: {theme['audience']}", ""]
        if theme.get("tone") or theme.get("voice"):
            tv = ", ".join(filter(None, [theme.get("tone"), theme.get("voice")]))
            lines += [f"  Register: {tv}", ""]
        lines += [
            f"Directive: {artist_directive}",
            "",
        ]

    lines += [
        f'Title: {plan["title"]}',
        "",
    ]

    for para in paragraphs:
        obs_ids   = json.loads(para["required_observations"])
        interp_ids = json.loads(para["required_interpretations"])
        terms     = json.loads(para["required_terms"])
        forbidden = json.loads(para["forbidden_claims"])

        obs_refs = [f"OBS-{id_to_n.get(oid, '?')}" for oid in obs_ids]
        critical    = [t["term"] for t in terms if t["priority"] == "critical"]
        recommended = [t["term"] for t in terms if t["priority"] == "recommended"]

        lines.append(f"{'─' * 48}")
        lines.append(f"Paragraph {para['order_idx']}")
        lines.append("")
        lines.append(f"Purpose: {para['purpose']}")
        lines.append("")

        if obs_refs:
            lines.append("Required observations:")
            for ref in obs_refs:
                # Fetch the text for context
                obs_n = int(ref.split("-")[1])
                if 1 <= obs_n <= len(all_ids):
                    obs_row = conn.execute(
                        """
                        SELECT COALESCE(od.normalized_text, o.raw_text) AS normalized_text
                        FROM observations o
                        LEFT JOIN observation_derived od ON od.observation_id = o.id
                        WHERE o.id = ?
                        """,
                        (all_ids[obs_n - 1],),
                    ).fetchone()
                    if obs_row:
                        lines.append(f'  {ref}: "{obs_row[0]}"')
                    else:
                        lines.append(f"  {ref}")
                else:
                    lines.append(f"  {ref}")
            lines.append("")

        if critical:
            lines.append(f"Semantic commitments (critical — must appear as communicated ideas):")
            for term in critical:
                lines.append(f"  • {term}")
        if recommended:
            lines.append(f"Semantic commitments (recommended):")
            for term in recommended[:5]:
                lines.append(f"  • {term}")
        if critical or recommended:
            lines.append("")

        if interp_ids:
            lines.append(f"Interpretive commitments: {len(interp_ids)} interpretation(s) must inform this paragraph.")
            lines.append("")

        if forbidden:
            lines.append("Forbidden claims:")
            for fc in forbidden:
                lines.append(f"  - {fc}")
            lines.append("")

    lines.append("─" * 48)
    lines.append("")
    lines.append("Write the essay now. Do not include headers or section labels.")
    lines.append("Each paragraph should be separated by a blank line.")

    return "\n".join(lines)


def generate_reconstruction_prompt(plan: dict, paragraphs: list[dict]) -> str:
    """First pass of the recursive protocol: ask the Artist to state its Intent Hypothesis.

    This is the Witness + Reconstruction stage — before any prose is written,
    the Artist must articulate what each paragraph is attempting to establish.
    Intermediate output is stored in execution_config, not the canonical narrative.
    """
    lines = [
        "You are about to render a section of an investigation.",
        "Before writing any prose, read the following Blueprint sections carefully.",
        "",
        "For each paragraph below, state in one sentence:",
        "  What understanding is this paragraph attempting to produce?",
        "  (Not what it says — what it is trying to establish.)",
        "",
        "Format your response as:",
        "  Paragraph 1 Intent: [one sentence]",
        "  Paragraph 2 Intent: [one sentence]",
        "  ...",
        "",
        f'Investigation: {plan["title"]}',
        "",
    ]
    for para in paragraphs:
        terms = json.loads(para["required_terms"])
        critical = [t["term"] for t in terms if t["priority"] == "critical"]
        lines.append(f"{'─' * 48}")
        lines.append(f"Paragraph {para['order_idx']}")
        lines.append(f"Purpose: {para['purpose']}")
        if critical:
            lines.append(f"Critical commitments: {', '.join(critical)}")
        lines.append("")
    return "\n".join(lines)


def generate_self_critique_prompt(draft: str, paragraphs: list[dict]) -> str:
    """Third pass of the recursive protocol: self-critique against semantic commitments.

    The Artist reviews its own draft and identifies which critical semantic
    commitments are clearly expressed, which are weak, and which are absent.
    It then produces a revised draft that addresses the weaknesses.
    """
    lines = [
        "You have produced the following draft. Now review it against the",
        "semantic commitments it was required to honor.",
        "",
        "For each paragraph:",
        "  1. State which critical commitments are clearly expressed.",
        "  2. State which are weak or absent.",
        "  3. Produce a revised paragraph that corrects the weaknesses.",
        "",
        "Return ONLY the revised essay — no headers, no commentary.",
        "Each paragraph separated by a blank line.",
        "",
        "─" * 48,
        "DRAFT TO REVIEW:",
        "",
        draft,
        "",
        "─" * 48,
        "REQUIRED SEMANTIC COMMITMENTS BY PARAGRAPH:",
        "",
    ]
    for para in paragraphs:
        terms = json.loads(para["required_terms"])
        critical = [t["term"] for t in terms if t["priority"] == "critical"]
        if critical:
            lines.append(f"Paragraph {para['order_idx']} critical commitments:")
            for t in critical:
                lines.append(f"  • {t}")
            lines.append("")
    lines.append("─" * 48)
    lines.append("")
    lines.append("Revised essay:")
    return "\n".join(lines)


# ── NullArtistProvider ────────────────────────────────────────────────────────

class NullArtistProvider:
    """Returns a placeholder. Requires no configuration.

    Use this to verify the pipeline end-to-end before connecting an LLM.
    The RenderedNarrative is stored and the Critic can still inspect
    whether the prompt was generated correctly.
    """

    @property
    def provider_name(self) -> str:
        return "null"

    def render(self, prompt: str) -> str:
        return "[Artist not configured — connect a provider to render prose]"

    def test_connection(self) -> None:
        raise RuntimeError("The null provider has no external connection")

    def execution_config(self) -> dict[str, Any]:
        return {
            "provider": "null",
            "model_id": None,
            "max_tokens": None,
            "sdk_version": None,
            "request_schema_version": "1",
            "constitutional_profile": CONSTITUTIONAL_PROFILE,
        }


# ── AnthropicArtistProvider ───────────────────────────────────────────────────

class AnthropicArtistProvider:
    """Renders prose via Claude.

    Requirements:
      pip install anthropic
      ANTHROPIC_API_KEY environment variable (or pass api_key directly)

    Args:
      model:   Claude model ID (default: claude-sonnet-4-6)
      api_key: Override ANTHROPIC_API_KEY
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
    ) -> None:
        try:
            import anthropic as _anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required: pip install anthropic"
            ) from None

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Export it or pass api_key= to AnthropicArtistProvider."
            )

        self._client = _anthropic.Anthropic(api_key=key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"anthropic/{self._model}"

    def execution_config(self) -> dict[str, Any]:
        try:
            sdk_ver = importlib.metadata.version("anthropic")
        except Exception:
            sdk_ver = None
        return {
            "provider": "anthropic",
            "model_id": self._model,
            "max_tokens": 4096,
            "sdk_version": sdk_ver,
            "request_schema_version": "1",
            "constitutional_profile": CONSTITUTIONAL_PROFILE,
        }

    def render(self, prompt: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def test_connection(self) -> None:
        self._client.models.list(limit=1)


# ── OpenAIArtistProvider ──────────────────────────────────────────────────────

class OpenAIArtistProvider:
    """Renders prose via OpenAI.

    Requirements:
      pip install openai
      OPENAI_API_KEY environment variable (or pass api_key directly)

    Args:
      model:   OpenAI model ID (default: gpt-4o)
      api_key: Override OPENAI_API_KEY
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI as _OpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai") from None

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Export it or pass api_key= to OpenAIArtistProvider."
            )

        self._client = _OpenAI(api_key=key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"openai/{self._model}"

    def execution_config(self) -> dict[str, Any]:
        try:
            sdk_ver = importlib.metadata.version("openai")
        except Exception:
            sdk_ver = None
        return {
            "provider": "openai",
            "model_id": self._model,
            "max_tokens": 4096,
            "sdk_version": sdk_ver,
            "request_schema_version": "1",
            "constitutional_profile": CONSTITUTIONAL_PROFILE,
        }

    def render(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def test_connection(self) -> None:
        self._client.models.list()


# ── GeminiArtistProvider ──────────────────────────────────────────────────────

class GeminiArtistProvider:
    """Renders prose via Google Gemini.

    Requirements:
      pip install google-genai
      GEMINI_API_KEY environment variable (or pass api_key directly)

    Args:
      model:   Gemini model ID (default: gemini-2.0-flash)
      api_key: Override GEMINI_API_KEY
    """

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
    ) -> None:
        try:
            from google import genai as _genai
        except ImportError:
            raise ImportError(
                "google-genai package required: pip install google-genai"
            ) from None

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Export it or pass api_key= to GeminiArtistProvider."
            )

        self._client = _genai.Client(api_key=key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"gemini/{self._model}"

    def execution_config(self) -> dict[str, Any]:
        try:
            sdk_ver = importlib.metadata.version("google-genai")
        except Exception:
            sdk_ver = None
        return {
            "provider": "gemini",
            "model_id": self._model,
            "max_tokens": None,
            "sdk_version": sdk_ver,
            "request_schema_version": "1",
            "constitutional_profile": CONSTITUTIONAL_PROFILE,
        }

    def render(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        return response.text

    def test_connection(self) -> None:
        next(iter(self._client.models.list()))


# ── GrokArtistProvider ────────────────────────────────────────────────────────

class GrokArtistProvider:
    """Renders prose via xAI Grok.

    xAI's API is OpenAI-compatible, so this uses the openai SDK with a
    different base URL.

    Requirements:
      pip install openai
      XAI_API_KEY environment variable (or pass api_key directly)

    Args:
      model:   Grok model ID (default: grok-3)
      api_key: Override XAI_API_KEY
    """

    def __init__(
        self,
        model: str = "grok-3",
        api_key: str | None = None,
    ) -> None:
        try:
            from openai import OpenAI as _OpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai") from None

        key = api_key or os.environ.get("XAI_API_KEY")
        if not key:
            raise ValueError(
                "XAI_API_KEY environment variable not set. "
                "Export it or pass api_key= to GrokArtistProvider."
            )

        self._client = _OpenAI(api_key=key, base_url="https://api.x.ai/v1")
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"grok/{self._model}"

    def execution_config(self) -> dict[str, Any]:
        try:
            sdk_ver = importlib.metadata.version("openai")
        except Exception:
            sdk_ver = None
        return {
            "provider": "grok",
            "model_id": self._model,
            "max_tokens": 4096,
            "endpoint": "https://api.x.ai/v1",
            "sdk_version": sdk_ver,
            "request_schema_version": "1",
            "constitutional_profile": CONSTITUTIONAL_PROFILE,
        }

    def render(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def test_connection(self) -> None:
        self._client.models.list()


# ── OllamaArtistProvider ─────────────────────────────────────────────────────

class OllamaArtistProvider:
    """Renders prose through a local Ollama service.

    Requirements:
      install and run Ollama
      pip install ollama
      pull the selected model before use

    Args:
      model: Ollama model tag (default: llama3.2:3b)
      host: Override OLLAMA_HOST or the default local service
    """

    def __init__(
        self,
        model: str = "llama3.2:3b",
        host: str | None = None,
    ) -> None:
        try:
            import ollama as _ollama
        except ImportError:
            raise ImportError(
                "ollama package required: pip install ollama"
            ) from None

        resolved_host = host or os.environ.get("OLLAMA_HOST")
        self._client = (
            _ollama.Client(host=resolved_host)
            if resolved_host
            else _ollama.Client()
        )
        self._host = resolved_host or "http://localhost:11434"
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"ollama/{self._model}"

    def execution_config(self) -> dict[str, Any]:
        try:
            sdk_ver = importlib.metadata.version("ollama")
        except Exception:
            sdk_ver = None
        return {
            "provider": "ollama",
            "model_id": self._model,
            "max_tokens": None,
            "endpoint": self._host,
            "sdk_version": sdk_ver,
            "request_schema_version": "1",
            "constitutional_profile": CONSTITUTIONAL_PROFILE,
        }

    def render(self, prompt: str) -> str:
        response = self._client.generate(
            model=self._model,
            prompt=prompt,
            stream=False,
        )
        return str(response["response"])

    def test_connection(self) -> None:
        models = self._client.list()
        model_rows = getattr(models, "models", None)
        if model_rows is None and isinstance(models, dict):
            model_rows = models.get("models", [])
        names = {
            str(
                item.get("model", "")
                if isinstance(item, dict)
                else getattr(item, "model", "")
            )
            for item in (model_rows or [])
        }
        if self._model not in names:
            raise RuntimeError(
                f"Ollama is running, but model '{self._model}' is not installed"
            )


# ── Provider registry ─────────────────────────────────────────────────────────
# Definitions are code configuration, not ontology. Capabilities are limited to
# the current ArtistProvider contract: text expression.

DEFAULT_PROVIDER_REGISTRY = ProviderRegistry(
    registrations=(
        ProviderRegistration(
            definition=ProviderDefinition(
                id="null",
                display_name="Not configured",
                provider_type="placeholder",
                enabled=True,
                capabilities=("placeholder",),
                local_or_remote="local",
            ),
            factory=NullArtistProvider,
        ),
        ProviderRegistration(
            definition=ProviderDefinition(
                id="anthropic",
                display_name="Anthropic",
                provider_type="artist",
                enabled=True,
                capabilities=("text",),
                local_or_remote="remote",
                required_environment="ANTHROPIC_API_KEY",
                sdk_module="anthropic",
                default_model="claude-sonnet-4-6",
            ),
            factory=AnthropicArtistProvider,
        ),
        ProviderRegistration(
            definition=ProviderDefinition(
                id="openai",
                display_name="OpenAI",
                provider_type="artist",
                enabled=True,
                capabilities=("text",),
                local_or_remote="remote",
                required_environment="OPENAI_API_KEY",
                sdk_module="openai",
                default_model="gpt-4o",
            ),
            factory=OpenAIArtistProvider,
        ),
        ProviderRegistration(
            definition=ProviderDefinition(
                id="gemini",
                display_name="Google Gemini",
                provider_type="artist",
                enabled=True,
                capabilities=("text",),
                local_or_remote="remote",
                required_environment="GEMINI_API_KEY",
                sdk_module="google.genai",
                default_model="gemini-2.0-flash",
            ),
            factory=GeminiArtistProvider,
        ),
        ProviderRegistration(
            definition=ProviderDefinition(
                id="grok",
                display_name="xAI Grok",
                provider_type="artist",
                enabled=True,
                capabilities=("text",),
                local_or_remote="remote",
                required_environment="XAI_API_KEY",
                sdk_module="openai",
                default_model="grok-3",
            ),
            factory=GrokArtistProvider,
        ),
        ProviderRegistration(
            definition=ProviderDefinition(
                id="ollama-meta",
                display_name="Meta Llama via Ollama",
                provider_type="artist",
                enabled=True,
                capabilities=("text",),
                local_or_remote="local",
                sdk_module="ollama",
                default_model="llama3.2:3b",
            ),
            factory=OllamaArtistProvider,
        ),
        ProviderRegistration(
            definition=ProviderDefinition(
                id="ollama-local",
                display_name="Local Model via Ollama",
                provider_type="artist",
                enabled=True,
                capabilities=("text",),
                local_or_remote="local",
                sdk_module="ollama",
                default_model="qwen3:4b",
            ),
            factory=OllamaArtistProvider,
        ),
    )
)

# Backwards-compatible read-only-style snapshot for callers that only inspect
# available built-in IDs. New code should use DEFAULT_PROVIDER_REGISTRY.
PROVIDERS = MappingProxyType({
    registration.definition.id: (
        registration.factory,
        registration.definition.required_environment,
    )
    for registration in DEFAULT_PROVIDER_REGISTRY.registrations
})


def get_provider(
    name: str = "null",
    *,
    registry: ProviderRegistry | None = None,
    **kwargs: object,
) -> ArtistProvider:
    """Resolve a provider by name.

    Args:
      name: 'null' | 'anthropic' | 'openai' | 'gemini' | 'grok' |
            'ollama-meta' | 'ollama-local'
      **kwargs: passed to the provider constructor (e.g. model=, api_key=)
    """
    active_registry = registry or DEFAULT_PROVIDER_REGISTRY
    provider = active_registry.create(name, **kwargs)
    if not isinstance(provider, ArtistProvider):
        raise TypeError(
            f"Provider '{name}' does not satisfy the ArtistProvider protocol"
        )
    return provider
