"""
Blueprint Extractor — derives an Intent Hypothesis from an existing document.

This is the "Start From Existing Work" onboarding path.

Instead of an investigator stating a thesis from scratch, they upload an
existing report, paper, memo, or analysis. The extractor reads it and
produces Hermeneia's best reconstruction of what the investigator is trying
to establish: a proposed NarrativeBlueprint.

The human ratifies or corrects the proposal. A wrong Blueprint is a reading
failure — the gap between AI reconstruction and author intent is itself
informative.

Architecture notes:
  - One LLM call only. No chain of thought, no multi-step.
  - Output is a proposed Blueprint dict, not a stored object.
  - Caller decides whether to persist (after human ratification).
  - Sections are created with empty obs/interp lists; the investigator
    links observations after the normal pipeline runs.
  - This module MUST NOT write to any database.
"""
from __future__ import annotations

import json
import re
from typing import Any

# ── System prompt ──────────────────────────────────────────────────────────────

_EXTRACTION_SYSTEM_PROMPT = """\
You are a reading analyst whose only job is to reconstruct what an investigator \
is trying to establish in a document they have written.

Your task: read the provided document and produce a structured Blueprint that \
captures:
  1. The title — a short, descriptive label for this investigation
  2. The thesis — one sentence stating the core claim the document appears to establish
  3. The sections — 2 to 5 supporting claims, ordered by logical dependency

A section is a discrete supporting claim — not a topic, not a heading, but a \
claim that, if true, would support the thesis.

CRITICAL — claim quality:
Each claim must encode its own semantic commitment in the sentence itself.
The claim text will be parsed for key phrases that become semantic obligations
the Artist must honor. Thin claims produce thin obligations.

Write claims as relational propositions that name a specific mechanism,
contrast, or causal relationship:

  WEAK (topic label): "The green light represents hope."
  STRONG (semantic commitment): "Fitzgerald transforms the green light from a
    navigational signal into the novel's central figure for Gatsby's failure to
    revise his interpretive model as reality changed around him."

  WEAK: "Nick is the narrator."
  STRONG: "Fitzgerald uses Nick's continuous revision of his own understanding
    as the contrasting example that makes Gatsby's interpretive rigidity visible."

Prefer predicates that name relationships:
  "demonstrates that", "reveals how", "makes visible the contrast between",
  "establishes the tension between", "shows why", "transforms X into evidence of Y".

Avoid copula-only claims ("X is Y", "X represents Y") where both X and Y are
noun phrases — these produce lexical tokens rather than semantic commitments
that can be verified in a rendered narrative.

Return ONLY valid JSON in exactly this format:
{
  "title": "Short descriptive title",
  "thesis": "One complete sentence stating the core claim.",
  "sections": [
    {"claim": "First supporting claim as a complete sentence with a specific relational predicate."},
    {"claim": "Second supporting claim as a complete sentence with a specific relational predicate."}
  ]
}

Rules:
- Return ONLY JSON. No explanation, no markdown, no preamble.
- The thesis must be falsifiable — it asserts something that could be wrong.
- Each claim must be a complete sentence with a relational predicate, not a topic heading.
- Between 2 and 5 sections only.
- Do not invent claims not supported by the document.
- If the document is unclear, produce your best reconstruction and note \
  uncertainty in the claim text (e.g. "The document appears to argue that...").
"""

# ── Extraction ─────────────────────────────────────────────────────────────────

def extract_blueprint_from_text(
    text: str,
    provider: Any,
    *,
    max_input_chars: int = 40_000,
) -> dict:
    """Call the provider with the document text and return a proposed Blueprint dict.

    The returned dict has keys: title, thesis, sections.
    Each section has: claim, supporting_observations (empty), supporting_interpretations (empty).

    Raises:
        BlueprintExtractionError if the LLM response cannot be parsed as a valid Blueprint.
    """
    if not text or not text.strip():
        raise BlueprintExtractionError("No text provided for Blueprint extraction.")

    truncated = text[:max_input_chars]
    if len(text) > max_input_chars:
        truncated += "\n\n[Document truncated for extraction]"

    prompt = (
        "Document to analyze:\n\n"
        + truncated
        + "\n\nReturn the Blueprint JSON now."
    )

    raw = _call_provider(provider, _EXTRACTION_SYSTEM_PROMPT, prompt)
    return _parse_and_validate(raw)


def _call_provider(provider: Any, system: str, user: str) -> str:
    """Call the provider's generate method using the same interface as the Artist."""
    name = getattr(provider, "name", None) or getattr(provider, "_name", "unknown")

    # AnthropicArtistProvider uses client.messages.create directly
    if hasattr(provider, "_client") and hasattr(provider._client, "messages"):
        resp = provider._client.messages.create(
            model=provider._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text

    # OpenAI-compatible: provider._client.chat.completions.create
    if hasattr(provider, "_client") and hasattr(provider._client, "chat"):
        resp = provider._client.chat.completions.create(
            model=provider._model,
            max_tokens=1024,
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

    # NullArtistProvider or unknown — return a minimal valid structure for testing
    return json.dumps({
        "title": "Extracted Blueprint",
        "thesis": "The document establishes a central claim.",
        "sections": [
            {"claim": "The document supports its thesis through evidence."},
        ],
    })


def _parse_and_validate(raw: str) -> dict:
    """Parse the LLM response and return a normalized Blueprint dict."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise BlueprintExtractionError(
            f"LLM did not return valid JSON.\nRaw response:\n{raw[:500]}"
        ) from exc

    missing = [k for k in ("title", "thesis", "sections") if k not in data]
    if missing:
        raise BlueprintExtractionError(
            f"Blueprint missing required keys: {missing}\nParsed: {data}"
        )

    if not isinstance(data["sections"], list) or len(data["sections"]) < 1:
        raise BlueprintExtractionError("Blueprint must have at least one section.")

    # Normalize sections: ensure empty obs/interp lists
    normalized_sections = []
    for i, s in enumerate(data["sections"]):
        if "claim" not in s or not str(s["claim"]).strip():
            raise BlueprintExtractionError(f"Section {i} missing 'claim' field.")
        normalized_sections.append({
            "claim": str(s["claim"]).strip(),
            "supporting_observations": [],
            "supporting_interpretations": [],
        })

    return {
        "title": str(data["title"]).strip(),
        "thesis": str(data["thesis"]).strip(),
        "sections": normalized_sections,
    }


class BlueprintExtractionError(ValueError):
    """Raised when the LLM response cannot be parsed into a valid Blueprint."""
