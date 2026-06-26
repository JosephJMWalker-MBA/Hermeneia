"""
Explorer — generate a candidate interpretation from a bucket of observations.

Design constraints (Sprint E-III-1):
  - Input: a bucket (list of related observations), produced by bucketer.py.
  - Output: one speculative Interpretation text + the prompt used.
  - No new tables. No schema changes. Output goes into proposed_interpretations
    via the existing staging pathway.
  - evidential_status is always 'speculative'. The Steward decides everything else.
  - The prompt is an inspectable artifact stored in prompt_reference.
  - This module MUST NOT write to any database.

Provider interface mirrors blueprint_extractor._call_provider: any ArtistProvider
instance works (Anthropic, OpenAI, Gemini, Grok, Ollama, Null).

Naming note:
  generate_interpretation_from_bucket — Explorer's primary entry point.
    Takes a bucket (multiple observations) → one candidate interpretation.

  generate_candidate_interpretation — single-observation utility.
    Not Explorer's job. Used by the E10 Lab's per-observation view only.
    Retained for backward compatibility with existing tests and the E10 endpoint.
"""
from __future__ import annotations

from typing import Any


# ── System prompts ────────────────────────────────────────────────────────────

_BUCKET_SYSTEM_PROMPT = """\
You are the Explorer.

You have been given a group of related observations that a pattern-recognition \
pass has placed together. Your job is to propose one candidate interpretation \
that accounts for why these observations might belong together.

You are NOT the Architect. You do not reconstruct the investigation's full claim. \
You propose a reading worthy of scrutiny — one that a human investigator can \
accept, amend, or reject.

Rules:
- Ground your reading in the observations provided. Do not import meaning from \
  outside them.
- Speak from the named investigative perspective.
- Be specific. Name the relationship or tension the observations share.
- Be honest about uncertainty. This is a candidate, not a conclusion.
- Write one paragraph. No headers, no bullet points, no preamble.
- Do not begin with "These observations" or "This group." Begin with the idea.

The human investigator will accept, amend, or reject your proposal.
"""

_SINGLE_OBS_SYSTEM_PROMPT = """\
You are the Explorer.

Your only job is to surface one candidate interpretation of an observation for \
a human investigator to review. You do not establish meaning. You propose a \
reading that is worthy of scrutiny.

Rules:
- Anchor your reading to the observation text. Do not import meaning from outside it.
- Speak from the named investigative perspective.
- Be specific. Vague readings are not useful.
- Be honest about uncertainty. You are producing a candidate, not a conclusion.
- Write one paragraph. No headers, no bullet points, no preamble.
- Do not begin with "This observation." Begin with the idea.

The human investigator will accept, amend, or reject your proposal.
"""


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_bucket_prompt(
    bucket_observations: list[dict],
    perspective_label: str,
    corpus_context: dict | None = None,
) -> str:
    """Build the prompt for a bucket of observations. Stored as prompt_reference."""
    role_descriptions = {
        "primary":    "the primary work — the subject of interpretation",
        "reference":  "a reference work — comparative context, not primary evidence",
        "notes":      "supplementary notes — background context only",
        "commentary": "critical commentary — external perspective on the primary work",
    }

    lines = ["Investigative Perspective: " + perspective_label]

    if corpus_context:
        primary = corpus_context.get("primary_work")
        obs_role = corpus_context.get("observation_role", "primary")
        if primary:
            lines.append(f"Primary Work: {primary}")
        if obs_role != "primary" and primary:
            lines.append(
                f"Note: observations come from a {obs_role} source. "
                f"Interpret how they illuminate or contrast with {primary}. "
                f"Do not treat them as primary evidence about {primary}."
            )

    lines.append("")
    lines.append(f"Observations ({len(bucket_observations)}):")
    for i, obs in enumerate(bucket_observations, 1):
        lines.append(f"\n[{i}] {obs['raw_text'].strip()}")

    lines.append("")
    lines.append(
        "Propose one candidate interpretation that accounts for why these "
        "observations might belong together. One paragraph. Begin with the idea."
    )

    return "\n".join(lines)


def build_explorer_prompt(
    observation_text: str,
    perspective_label: str,
    corpus_context: dict | None = None,
) -> str:
    """Build the prompt for a single observation. Stored as prompt_reference."""
    role_descriptions = {
        "primary":    "the primary work — the subject of interpretation",
        "reference":  "a reference work — comparative context, not primary evidence",
        "notes":      "supplementary notes — background context only",
        "commentary": "critical commentary — external perspective on the primary work",
    }

    lines = ["Investigative Perspective: " + perspective_label]

    if corpus_context:
        primary = corpus_context.get("primary_work")
        obs_name = corpus_context.get("observation_source")
        obs_role = corpus_context.get("observation_role", "primary")

        if primary:
            lines.append(f"Primary Work: {primary}")
        if obs_name:
            lines.append(
                f"Observation Source: {obs_name}"
                f" ({role_descriptions.get(obs_role, obs_role)})"
            )
        if obs_role != "primary" and primary:
            lines.append(
                f"Note: this observation comes from a {obs_role} source. "
                f"Interpret how it illuminates or contrasts with {primary}. "
                f"Do not treat it as primary evidence about {primary}."
            )

    lines.append("")
    lines.append("Observation:")
    lines.append(observation_text)
    lines.append("")
    lines.append(
        "Propose one candidate interpretation from the perspective named above. "
        "One paragraph. Begin with the idea, not with 'This observation.'"
    )

    return "\n".join(lines)


# ── Explorer primary entry point ──────────────────────────────────────────────

def generate_interpretation_from_bucket(
    bucket_observations: list[dict],
    perspective_label: str,
    provider: Any,
    corpus_context: dict | None = None,
) -> tuple[str, str]:
    """Generate a candidate interpretation from a bucket of related observations.

    This is Explorer's primary cognitive act: given observations that seem to
    belong together, propose what might connect them.

    Args:
        bucket_observations: list of dicts with 'id' and 'raw_text' keys.
        perspective_label: the named investigative framework.
        provider: any ArtistProvider instance.
        corpus_context: optional dict with primary_work, observation_role, etc.

    Returns:
        (interpretation_text, prompt_used)

    Raises:
        ExplorerError if the provider returns empty text.
    """
    if not bucket_observations:
        raise ExplorerError("Bucket is empty — cannot generate interpretation.")

    if len(bucket_observations) == 1:
        # Single-observation bucket: fall through to single-obs path
        return generate_candidate_interpretation(
            bucket_observations[0]["raw_text"],
            perspective_label,
            provider,
            corpus_context,
        )

    prompt = build_bucket_prompt(bucket_observations, perspective_label, corpus_context)
    text = _call_provider(provider, _BUCKET_SYSTEM_PROMPT, prompt)

    text = text.strip()
    if not text:
        raise ExplorerError("Provider returned an empty response.")

    return text, prompt


# ── Single-observation utility (E10 Lab, backward compat) ────────────────────

def generate_candidate_interpretation(
    observation_text: str,
    perspective_label: str,
    provider: Any,
    corpus_context: dict | None = None,
) -> tuple[str, str]:
    """Generate a candidate interpretation from a single observation.

    Not Explorer's primary job — Explorer works with buckets of observations.
    Retained for the E10 Lab's per-observation view and backward compatibility.
    """
    prompt = build_explorer_prompt(observation_text, perspective_label, corpus_context)
    text = _call_provider(provider, _SINGLE_OBS_SYSTEM_PROMPT, prompt)

    text = text.strip()
    if not text:
        raise ExplorerError("Provider returned an empty response.")

    return text, prompt


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_provider(provider: Any, system: str, user: str) -> str:
    """Call the provider using the same interface as blueprint_extractor."""

    # AnthropicArtistProvider
    if hasattr(provider, "_client") and hasattr(provider._client, "messages"):
        resp = provider._client.messages.create(
            model=provider._model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text

    # Ollama: _client.generate (not chat.completions)
    if hasattr(provider, "_client") and hasattr(provider._client, "generate"):
        full = system + "\n\n" + user
        resp = provider._client.generate(model=provider._model, prompt=full, stream=False)
        return str(resp["response"]) if isinstance(resp, dict) else str(resp.response)

    # OpenAI-compatible (OpenAI, Grok)
    if hasattr(provider, "_client") and hasattr(provider._client, "chat"):
        resp = provider._client.chat.completions.create(
            model=provider._model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content

    # Gemini
    if hasattr(provider, "_model_obj"):
        full = system + "\n\n" + user
        resp = provider._model_obj.generate_content(full)
        return resp.text

    # Null / unknown — minimal valid candidate for testing.
    perspective = "the named"
    for line in user.splitlines():
        if line.startswith("Investigative Perspective:"):
            perspective = line.split(":", 1)[1].strip()
            break
    return (
        f"From a {perspective} perspective, these observations share a candidate "
        f"site of meaning whose significance the investigator should evaluate directly."
    )


class ExplorerError(ValueError):
    """Raised when the Explorer cannot produce a valid candidate interpretation."""
