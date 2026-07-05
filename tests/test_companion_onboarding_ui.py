from __future__ import annotations

from pathlib import Path


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def test_companion_onboarding_is_persistent_panel_workflow():
    index = INDEX.read_text()

    assert "hermeneia_companion_onboarding_v1" in index
    assert 'id="cmp-onboarding-host"' in index
    assert "Companion-led onboarding" in index
    assert "First Companion workflow" in index
    assert "Continue later" in index
    assert "Restart walkthrough" in index
    assert "Open guide" in index
    assert "cmpContinueOnboardingLater" in index
    assert "cmpRestartOnboarding" in index
    assert "cmpOpenOnboarding" in index
    assert "cmp-onboarding-overlay" not in index


def test_companion_onboarding_teaches_the_requested_method():
    index = INDEX.read_text()

    for label in (
        "Thesis",
        "Read",
        "Observe",
        "Search",
        "Interpret",
        "Blueprint",
        "Critic",
        "Meta-synthesis",
    ):
        assert label in index

    for required_copy in (
        "Hermeneia is a reading workbench",
        "The Reader is the main canvas",
        "Set a governing question",
        "Read a small amount",
        "Make or review one highlight",
        "where else does this idea appear",
        "what have you discovered so far",
        "Interpretation, Blueprint, Critic, and Meta-synthesis come later",
        "Persistent coach",
    ):
        assert required_copy in index


def test_companion_onboarding_reuses_reader_workbench_surfaces():
    index = INDEX.read_text()

    assert "_crRailGo('question')" in index
    assert "_crRailGo('capture')" in index
    assert "openCorpusSearch(_cmpSearchSeed())" in index
    assert "openTimeline()" in index
    assert "document.getElementById('workflow-rail')" in index
    assert "No configured model is required for this guide" in index
    assert "localStorage.setItem(_CMP_ONBOARDING_KEY" in index
    assert "/api/companion/onboarding" not in index


def test_companion_onboarding_is_present_on_first_run_setup():
    index = INDEX.read_text()

    assert 'class="fr-companion-layout"' in index
    assert "The Companion starts before provider setup" in index
    assert "It can guide the workbench method in deterministic mode" in index
    assert '<div id="cmp-onboarding-host">${_cmpOnboardingHtml()}</div>' in index
