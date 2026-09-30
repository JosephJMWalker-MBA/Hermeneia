from __future__ import annotations

from pathlib import Path

INDEX = Path(__file__).parent.parent / 'hermeneia/web/static/index.html'


def test_companion_onboarding_is_persistent_panel_workflow():
    index = INDEX.read_text()
    for required in ('hermeneia_companion_onboarding_v1', 'id="cmp-onboarding-host"',
                     'Companion-led guide', 'Study Cycle', 'Continue later',
                     'Restart study guide', 'Open guide', 'Hide guide',
                     'cmpContinueOnboardingLater', 'cmpRestartOnboarding', 'cmpOpenOnboarding'):
        assert required in index
    assert 'cmp-onboarding-overlay' not in index


def test_companion_onboarding_teaches_method_from_the_server_projection():
    index = INDEX.read_text()
    for required in ('why_it_matters', 'recommended_action', 'evidence_or_state_basis',
                     'history_support', 'Why this matters', 'Current state',
                     'Historical exercise is unsupported; this is not a failure.',
                     'Current material is not proof of a prior study cycle'):
        assert required in index
    assert '_cmpStepComplete' not in index
    assert '_CMP_ONBOARDING_STEPS' not in index


def test_companion_onboarding_reuses_reader_workbench_surfaces():
    index = INDEX.read_text()
    for required in ("_crRailGo('question')", "_crRailGo(candidateContext ? 'capture' : target)",
                     "await _crOpenBottomWorkstation(target)",
                     "await _evidenceBoardSetView('lineage')", 'e10SelectObservation',
                     'No configured model is required for this guide',
                     'localStorage.setItem(_CMP_ONBOARDING_KEY', '/api/guided-study-cycle'):
        assert required in index
    assert '/api/companion/onboarding' not in index


def test_companion_onboarding_is_present_on_first_run_setup():
    index = INDEX.read_text()
    assert 'class="fr-companion-layout"' in index
    assert 'The Companion starts before provider setup' in index
    assert 'It can guide the workbench method in deterministic mode' in index
    assert '<div id="cmp-onboarding-host">${_cmpOnboardingHtml()}</div>' in index
