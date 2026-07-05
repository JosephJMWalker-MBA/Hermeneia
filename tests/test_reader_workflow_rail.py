"""Bottom workflow rail (PR 4).

A compact, persistent strip of interpretive steps beneath the Reader — tabs, not
prev/next. Jump to any step; the Reader stays the anchor. These tests guard the
rail's markup, the step set, the active-state wiring, and that the old prev/next
stepper is superseded.
"""
from __future__ import annotations

from pathlib import Path

INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _index() -> str:
    return INDEX.read_text()


def test_workflow_rail_markup_present():
    index = _index()
    assert 'id="workflow-rail"' in index
    assert "class=\"workflow-rail\"" in index
    assert "_wfGo(" in index
    assert "_renderWorkflowRail" in index


def test_workflow_rail_has_the_interpretive_steps():
    index = _index()
    for stage in ("reader", "corpus", "lab", "review", "architect", "reports",
                  "critic", "lineage"):
        assert f"_wfGo('{stage}')" in index, stage
    for label in ("Read", "Corpus", "Interpret", "Review", "Blueprint",
                  "Render", "Critic", "Lineage"):
        assert f">{label}</button>" in index, label


def test_active_step_is_synced_to_the_current_stage():
    index = _index()
    # The rail highlight is driven by the existing stage tracker.
    assert "_renderWorkflowRail(id)" in index
    assert "b.classList.toggle('active', b.dataset.stage === activeId)" in index


def test_steps_reuse_existing_navigation():
    index = _index()
    # _wfGo routes through the existing e10Go handler; no new routing system.
    assert "function _wfGo(stage) { e10Go(stage); }" in index


def test_old_prev_next_stepper_is_superseded():
    index = _index()
    # The old stage-nav-bar is hidden in favor of the rail.
    assert ".stage-nav-bar { display: none; }" in index


def test_rail_shown_only_once_a_workspace_exists():
    index = _index()
    # Rendered hidden; revealed in mount when a database is present.
    assert 'id="workflow-rail" hidden' in index
    assert "getElementById('workflow-rail')?.removeAttribute('hidden')" in index
    assert "has-workflow-rail" in index
