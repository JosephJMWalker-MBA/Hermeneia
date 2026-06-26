from __future__ import annotations

from pathlib import Path


def test_onboarding_ui_uses_existing_project_summary_projection():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    assert "id=\"onboarding\"" in index_html
    assert "onboarding-panel" in index_html
    assert "e10LoadOnboarding" in index_html
    assert "/api/project/summary" in index_html


def test_onboarding_ui_routes_to_existing_demo_surfaces_only():
    index_html = (
        Path(__file__).parent.parent
        / "hermeneia"
        / "web"
        / "static"
        / "index.html"
    ).read_text()

    for target in (
        "e10Go('corpus')",
        "e10Go('lab')",
        "e10Go('architect')",
        "e10Go('reader')",
        "e10Go('critic')",
        "e10Go('lineage')",
    ):
        assert target in index_html

    assert "Observe" in index_html
    assert "Interpret" in index_html
    assert "Organize" in index_html
    assert "Plan" in index_html
    assert "Read" in index_html
    assert "Audit" in index_html
