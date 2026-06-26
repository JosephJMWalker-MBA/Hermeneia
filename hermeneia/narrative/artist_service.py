"""Shared Artist render workflow.

This keeps CLI and web writes on the same identity and audit path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Any

from ..storage.hashing import make_rendered_narrative_id
from .artist_providers import (
    generate_prompt,
    generate_reconstruction_prompt,
    generate_self_critique_prompt,
    get_provider,
)
from .profiles import get_profile


class ArtistRenderError(ValueError):
    """Raised when the Artist render preconditions are not satisfied."""


@dataclass(frozen=True)
class ArtistRenderResult:
    row: dict
    blueprint: dict
    plan: dict
    profile: dict | None
    prompt: str
    created: bool


def _parse_obs_ref(obs_ref: str) -> int:
    ref = obs_ref.upper().strip()
    if ref.startswith("OBS-"):
        ref = ref[4:]
    try:
        return int(ref)
    except ValueError as exc:
        raise ArtistRenderError(f"Invalid obs_ref: {obs_ref}") from exc


def _execute_render(
    provider: Any,
    prompt: str,
    plan_dict: dict,
    paragraphs: list[dict],
    recursive: bool,
    execution_ts: str,
) -> tuple[str, dict]:
    """Core render logic shared by render_for_plan and render_for_observation.

    Returns (text, execution_config).

    When recursive=True, runs the three-pass protocol:
      1. Reconstruction — Artist states Intent Hypothesis for each paragraph
      2. Draft — single-pass render from the ArchitectPlan prompt
      3. Self-Critique + Revision — Artist reviews draft against semantic
         commitments and produces a revised narrative

    Intermediate outputs (Intent Hypothesis and draft) are stored in
    execution_config["recursive_provenance"] for provenance inspection.
    No schema change required.
    """
    if recursive:
        recon_prompt = generate_reconstruction_prompt(plan_dict, paragraphs)
        intent_hypothesis = provider.render(recon_prompt)
        draft = provider.render(prompt)
        critique_prompt = generate_self_critique_prompt(draft, paragraphs)
        text = provider.render(critique_prompt)
        execution_config = provider.execution_config()
        execution_config["execution_timestamp"] = execution_ts
        execution_config["recursive_provenance"] = {
            "protocol": "recursive-v1",
            "intent_hypothesis": intent_hypothesis,
            "draft": draft,
        }
    else:
        text = provider.render(prompt)
        execution_config = provider.execution_config()
        execution_config["execution_timestamp"] = execution_ts

    return text, execution_config


def render_for_plan(
    plan_id: str,
    conn: Connection,
    *,
    provider_name: str = "null",
    profile_slug: str | None = None,
    model: str | None = None,
    provider_kwargs: dict[str, Any] | None = None,
    recursive: bool = False,
) -> ArtistRenderResult:
    """Render a RenderedNarrative directly from an ArchitectPlan ID.

    Used when the caller has already selected a specific plan (e.g. from the
    Architect blueprint manager) rather than arriving via an OBS-N reference.
    """
    plan = conn.execute(
        "SELECT * FROM architect_plans WHERE id = ?", (plan_id,)
    ).fetchone()
    if plan is None:
        raise ArtistRenderError(f"Architect Plan not found: {plan_id}")
    plan_dict = dict(plan)

    blueprint = conn.execute(
        "SELECT * FROM narrative_blueprints WHERE id = ?", (plan_dict["blueprint_id"],)
    ).fetchone()
    if blueprint is None:
        raise ArtistRenderError(f"Narrative Blueprint not found for plan: {plan_id}")
    blueprint_dict = dict(blueprint)

    profile = get_profile(profile_slug, conn) if profile_slug else None
    if profile_slug and profile is None:
        raise ArtistRenderError(f"Expression profile '{profile_slug}' not found.")

    kwargs: dict[str, Any] = dict(provider_kwargs or {})
    if model:
        kwargs["model"] = model
    provider = get_provider(provider_name, **kwargs)

    expression_profile_id = profile["id"] if profile else None
    narrative_id = make_rendered_narrative_id(
        plan_dict["id"],
        provider.provider_name,
        expression_profile_id,
    )

    existing = conn.execute(
        "SELECT * FROM rendered_narratives WHERE id = ?", (narrative_id,)
    ).fetchone()
    if existing is not None:
        return ArtistRenderResult(
            row=dict(existing),
            blueprint=blueprint_dict,
            plan=plan_dict,
            profile=profile,
            prompt=existing["prompt_used"],
            created=False,
        )

    paragraphs = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
            (plan_dict["id"],),
        ).fetchall()
    ]
    prompt = generate_prompt(plan_dict, paragraphs, conn, theme=profile)
    execution_ts = datetime.now(timezone.utc).isoformat()
    text, execution_config = _execute_render(
        provider, prompt, plan_dict, paragraphs, recursive, execution_ts
    )

    row = {
        "id": narrative_id,
        "architect_plan_id": plan_dict["id"],
        "provider": provider.provider_name,
        "expression_profile_id": expression_profile_id,
        "text": text,
        "prompt_used": prompt,
        "execution_config": json.dumps(execution_config),
        "created_at": execution_ts,
    }
    conn.execute(
        """
        INSERT OR IGNORE INTO rendered_narratives
            (id, architect_plan_id, provider, expression_profile_id,
             text, prompt_used, execution_config, created_at)
        VALUES
            (:id, :architect_plan_id, :provider, :expression_profile_id,
             :text, :prompt_used, :execution_config, :created_at)
        """,
        row,
    )
    conn.commit()

    return ArtistRenderResult(
        row=row,
        blueprint=blueprint_dict,
        plan=plan_dict,
        profile=profile,
        prompt=prompt,
        created=True,
    )


def render_for_observation(
    obs_ref: str,
    conn: Connection,
    *,
    provider_name: str = "null",
    profile_slug: str | None = None,
    model: str | None = None,
    provider_kwargs: dict[str, Any] | None = None,
    recursive: bool = False,
) -> ArtistRenderResult:
    """Render and persist a RenderedNarrative for an observation's plan.

    The RenderedNarrative ID is deterministic for the ArchitectPlan, resolved
    provider/model identity, and ExpressionProfile. Existing rows are returned
    without regenerating provider output.
    """
    n = _parse_obs_ref(obs_ref)
    all_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM observations ORDER BY page, paragraph, sentence"
        ).fetchall()
    ]
    if n < 1 or n > len(all_ids):
        raise ArtistRenderError(f"OBS-{n} not found")
    obs_id = all_ids[n - 1]

    blueprint = conn.execute(
        """
        SELECT nb.*
        FROM narrative_blueprints nb
        JOIN blueprint_observation_links bol ON bol.blueprint_id = nb.id
        WHERE bol.observation_id = ?
        ORDER BY nb.created_at
        LIMIT 1
        """,
        (obs_id,),
    ).fetchone()
    if blueprint is None:
        raise ArtistRenderError(f"No Narrative Blueprint cites OBS-{n}.")
    blueprint_dict = dict(blueprint)

    plan = conn.execute(
        "SELECT * FROM architect_plans WHERE blueprint_id = ? ORDER BY created_at DESC LIMIT 1",
        (blueprint["id"],),
    ).fetchone()
    if plan is None:
        raise ArtistRenderError(f"No Architect Plan found for OBS-{n}.")
    plan_dict = dict(plan)

    profile = get_profile(profile_slug, conn) if profile_slug else None
    if profile_slug and profile is None:
        raise ArtistRenderError(f"Expression profile '{profile_slug}' not found.")

    kwargs: dict[str, Any] = dict(provider_kwargs or {})
    if model:
        kwargs["model"] = model
    provider = get_provider(provider_name, **kwargs)

    expression_profile_id = profile["id"] if profile else None
    narrative_id = make_rendered_narrative_id(
        plan_dict["id"],
        provider.provider_name,
        expression_profile_id,
    )

    existing = conn.execute(
        "SELECT * FROM rendered_narratives WHERE id = ?",
        (narrative_id,),
    ).fetchone()
    if existing is not None:
        return ArtistRenderResult(
            row=dict(existing),
            blueprint=blueprint_dict,
            plan=plan_dict,
            profile=profile,
            prompt=existing["prompt_used"],
            created=False,
        )

    paragraphs = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM architect_plan_paragraphs WHERE plan_id = ? ORDER BY order_idx",
            (plan_dict["id"],),
        ).fetchall()
    ]
    prompt = generate_prompt(plan_dict, paragraphs, conn, theme=profile)
    execution_ts = datetime.now(timezone.utc).isoformat()
    text, execution_config = _execute_render(
        provider, prompt, plan_dict, paragraphs, recursive, execution_ts
    )

    row = {
        "id": narrative_id,
        "architect_plan_id": plan_dict["id"],
        "provider": provider.provider_name,
        "expression_profile_id": expression_profile_id,
        "text": text,
        "prompt_used": prompt,
        "execution_config": json.dumps(execution_config),
        "created_at": execution_ts,
    }
    conn.execute(
        """
        INSERT OR IGNORE INTO rendered_narratives
            (id, architect_plan_id, provider, expression_profile_id,
             text, prompt_used, execution_config, created_at)
        VALUES
            (:id, :architect_plan_id, :provider, :expression_profile_id,
             :text, :prompt_used, :execution_config, :created_at)
        """,
        row,
    )
    conn.commit()

    return ArtistRenderResult(
        row=row,
        blueprint=blueprint_dict,
        plan=plan_dict,
        profile=profile,
        prompt=prompt,
        created=True,
    )
