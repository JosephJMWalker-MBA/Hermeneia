"""PM human-attention bridge: while a human-gold pass is open no model may run.

Authority: docs/integrations/performance-manuscript-human-attention-bridge.md.
The web app resolves every provider through one gated registry; the deterministic
null provider stays available; local models are refused too. Synthetic fixtures only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from hermeneia.integrations import pm_human_gold as G
from hermeneia.narrative.artist_providers import DEFAULT_PROVIDER_REGISTRY
from hermeneia.narrative.provider_registry import ProviderRegistration, ProviderRegistry
from test_pm_human_gold_bridge import _client, _db, _open, _seal


class _Spy:
    def __init__(self):
        self.created: list[str] = []

    def registry(self) -> ProviderRegistry:
        def factory_for(pid):
            def factory(**_kw):
                self.created.append(pid)
                return DEFAULT_PROVIDER_REGISTRY.create("null")
            return factory
        return ProviderRegistry(registrations=tuple(
            ProviderRegistration(definition=r.definition, factory=factory_for(r.definition.id))
            for r in DEFAULT_PROVIDER_REGISTRY.registrations))


def test_open_pass_blocks_every_provider_including_local(tmp_path):
    db = _db(tmp_path)
    gated = G.GoldGatedRegistry(_Spy().registry(), db)
    c = _client(db)
    pass_id = _open(c)
    for pid in DEFAULT_PROVIDER_REGISTRY.ids():
        if pid == "null":
            gated.create("null")
            continue
        with pytest.raises(G.ProviderExecutionBlocked):
            gated.create(pid)
    _seal(c, pass_id)
    gated.create("ollama-local")                      # machine-assisted work may follow the seal


def test_web_model_routes_create_no_provider_while_open(tmp_path, monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY"):          # fake keys: reach the gate, not a credential error
        monkeypatch.setenv(var, "synthetic-test-key")
    db = _db(tmp_path)
    spy = _Spy()
    c = _client(db, registry=spy.registry())
    pass_id = _open(c)
    r1 = c.post("/api/companion/ask", json={"message": "who calls out?", "provider": "anthropic"})
    r2 = c.post("/api/pipeline/extract-blueprint", json={"text": "synthetic", "provider": "gemini"})
    assert spy.created == [] and r1.status_code >= 400 and r2.status_code >= 400
    assert "blocked" in json.dumps(r1.get_json()) + json.dumps(r2.get_json())
    _seal(c, pass_id)
    c.post("/api/pipeline/extract-blueprint", json={"text": "synthetic", "provider": "gemini"})
    assert spy.created == ["gemini"]


def test_no_web_path_bypasses_the_gated_registry():
    root = Path(__file__).resolve().parents[1] / "hermeneia"
    app_src = (root / "web" / "app.py").read_text()
    calls = re.findall(r"get_provider\([^)]*\)", app_src)
    assert calls and all("registry=active_provider_registry" in call for call in calls)
    assert app_src.count("DEFAULT_PROVIDER_REGISTRY") == 2            # the import and the gated wrapper only
    service = (root / "narrative" / "artist_service.py").read_text()
    assert all("registry=registry" in call for call in re.findall(r"get_provider\([^)]*\)", service))


