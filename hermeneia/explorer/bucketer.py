"""
Explorer Bucketer — groups observations into candidate thematic clusters.

Buckets are ephemeral compiler internals. They are never stored as canonical
objects. They function like an Abstract Syntax Tree: built to structure work,
discarded after the interpretation is produced.

The stored artifact is always the speculative Interpretation and its
evidence_observation_ids. The bucket that produced it is not.

One LLM call groups all provided observations. Each bucket becomes one
candidate Interpretation via explorer/interpreter.py.
"""
from __future__ import annotations

import json
import re
from typing import Any


# ── System prompt ─────────────────────────────────────────────────────────────

_BUCKETING_SYSTEM_PROMPT = """\
You are a pattern-recognition assistant performing the first step of a \
disciplined investigation.

Your job: group the provided observations into candidate thematic clusters. \
You are NOT interpreting them. You are asking: what evidence seems to belong \
together before we know what it means?

Rules:
- Each observation may appear in exactly one bucket.
- Create as many buckets as the evidence warrants — do not force unrelated \
  observations together.
- If observations genuinely resist grouping, create singleton buckets rather \
  than forcing false coherence. Forced groupings produce noisy interpretations.
- Do not name the theme or interpret the cluster.

Observations are numbered. Return ONLY valid JSON in exactly this format:
{
  "buckets": [
    {"indices": [1, 3, 7]},
    {"indices": [2, 5]},
    {"indices": [4]}
  ]
}

Rules:
- Return ONLY the JSON. No explanation, no markdown, no preamble.
- Use the integer index numbers shown, not any other identifiers.
- Every index must appear in exactly one bucket.
"""


# ── Bucketer ──────────────────────────────────────────────────────────────────

def generate_candidate_buckets(
    observations: list[dict],
    provider: Any,
) -> list[list[str]]:
    """Group observations into ephemeral thematic clusters.

    Args:
        observations: list of dicts with 'id' and 'raw_text' keys.
        provider: any ArtistProvider instance (Anthropic, OpenAI, Gemini, Null).

    Returns:
        list of buckets, where each bucket is a list of observation IDs.
        Ephemeral — never store these.

    Raises:
        BucketingError if the provider call fails or returns invalid structure.
    """
    if not observations:
        return []
    if len(observations) == 1:
        return [[observations[0]["id"]]]

    # Number observations 1..N — avoids LLM line-wrapping 64-char hex IDs
    index_to_id = {i + 1: obs["id"] for i, obs in enumerate(observations)}
    obs_block = "\n\n".join(
        f"[{i + 1}] {obs['raw_text'].strip()}"
        for i, obs in enumerate(observations)
    )
    user_prompt = (
        f"Group the following {len(observations)} observations into candidate buckets.\n\n"
        + obs_block
        + "\n\nReturn the bucket JSON now."
    )

    raw = _call_provider(provider, _BUCKETING_SYSTEM_PROMPT, user_prompt)
    return parse_and_validate_bucket_response(raw, index_to_id)


def parse_and_validate_bucket_response(raw: str, index_to_id: dict[int, str]) -> list[list[str]]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    # If the model wrapped JSON in prose, extract the first valid JSON object
    data = None
    if not cleaned.startswith("{"):
        m = re.search(r'\{.*"buckets".*\}', cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try repairing truncated JSON by closing open brackets
        repaired = cleaned
        open_brackets = repaired.count("[") - repaired.count("]")
        open_braces = repaired.count("{") - repaired.count("}")
        if open_brackets > 0 or open_braces > 0:
            repaired += "]" * open_brackets + "}" * open_braces
            try:
                data = json.loads(repaired)
            except json.JSONDecodeError:
                data = None
        else:
            data = None

        if data is None:
            # Last resort: find any {...} block that parses
            for m in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL):
                try:
                    data = json.loads(m.group(0))
                    if "buckets" in data:
                        break
                    data = None
                except json.JSONDecodeError:
                    continue
        if data is None:
            raise BucketingError(f"Provider did not return valid JSON: {raw[:300]}")

    if "buckets" not in data or not isinstance(data["buckets"], list):
        raise BucketingError(f"Response missing 'buckets' list: {data}")

    buckets: list[list[str]] = []
    seen_indices: set[int] = set()

    for i, bucket in enumerate(data["buckets"]):
        indices = bucket.get("indices", [])
        if not isinstance(indices, list) or not indices:
            raise BucketingError(f"Bucket {i} has no indices")
        resolved: list[str] = []
        for idx in indices:
            if not isinstance(idx, int) or idx not in index_to_id:
                raise BucketingError(f"Bucket {i} contains unknown index {idx!r}")
            if idx in seen_indices:
                raise BucketingError(f"Index {idx} appears in more than one bucket")
            seen_indices.add(idx)
            resolved.append(index_to_id[idx])
        buckets.append(resolved)

    # Any index not assigned to a bucket gets its own singleton
    for idx, oid in sorted(index_to_id.items()):
        if idx not in seen_indices:
            buckets.append([oid])

    return buckets


def _call_provider(provider: Any, system: str, user: str) -> str:
    """Call the provider. Mirrors the interface in interpreter._call_provider."""

    # AnthropicArtistProvider
    if hasattr(provider, "_client") and hasattr(provider._client, "messages"):
        resp = provider._client.messages.create(
            model=provider._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text

    # Ollama: _client.generate (not chat.completions)
    if hasattr(provider, "_client") and hasattr(provider._client, "generate"):
        full = system + "\n\n" + user
        resp = provider._client.generate(
            model=provider._model, prompt=full, stream=False,
            options={"temperature": 0},
        )
        text = str(resp["response"]) if isinstance(resp, dict) else str(resp.response)
        # Strip reasoning model <think>...</think> blocks (qwen3, deepseek-r1, etc.)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        return text

    # OpenAI-compatible
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

    # Null / unknown — produce one bucket containing all indices
    import re as _re
    indices = [int(m) for m in _re.findall(r'^\[(\d+)\]', user, _re.MULTILINE)]
    if indices:
        return json.dumps({"buckets": [{"indices": indices}]})
    return json.dumps({"buckets": []})


class BucketingError(ValueError):
    """Raised when observations cannot be bucketed into valid clusters."""
