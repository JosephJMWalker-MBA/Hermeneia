from __future__ import annotations

import re
from pathlib import Path


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_function(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    i = brace
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"unbalanced braces extracting {signature!r}")


def _guide_source() -> str:
    return _extract_function(INDEX.read_text(), "function e10LoadGuide(")


def test_guide_begins_from_question_reader_and_corpus() -> None:
    guide = _guide_source()

    assert "Hermeneia begins with a question and a reader" in guide
    assert "read the source directly" in guide
    assert "The Reader is the primary workspace" in guide
    assert "Question Compass gives the work direction without deciding the answer" in guide
    assert "The corpus may support the question, complicate it, challenge it, or force you to revise it" in guide
    assert "not with a report" in guide


def test_guide_teaches_machine_output_as_candidate_comparison_material() -> None:
    guide = _guide_source()
    compact = re.sub(r"\s+", " ", guide)

    assert "machine observations and Perspectives" in guide
    assert "comparison material" in guide
    assert "not automatic meaning" in guide
    assert "AI proposes. Human authority governs what survives." in guide
    assert "Nothing becomes canonical without a human decision." in guide
    assert "build and render only from governed understanding" in compact


def test_guide_stage_model_is_reading_first_and_routes_truthfully() -> None:
    guide = _guide_source()
    stages = re.findall(
        r"num: '(\d+)', label: '([^']+)'.*?nav: '([^']+)'.*?action: '([^']+)'",
        guide,
        re.S,
    )

    assert stages == [
        ("01", "Question", "setup", "Sharpen the question"),
        ("02", "Read", "reader", "Open Reader"),
        ("03", "Mark", "reader", "Mark in Reader"),
        ("04", "Ask", "reader", "Return to Reader"),
        ("05", "Compare", "lab", "Open Lab"),
        ("06", "Steward", "review", "Review proposals"),
        ("07", "Build", "architect", "Open Architect"),
        ("08", "Render", "reports", "Open Render"),
        ("09", "Audit", "critic", "Open Critic"),
        ("10", "Trace", "lineage", "Inspect Lineage"),
    ]
    assert "data-guide-label" in guide
    assert "data-guide-nav" in guide


def test_guide_no_longer_teaches_the_stale_pipeline_first_model() -> None:
    guide = _guide_source()

    assert "Observe → Interpret → Organize → Plan → Read → Audit → Trace" not in guide
    assert "num: '05', label: 'Read'" not in guide
    assert "Render the plan into natural language via any provider" not in guide
    assert "AI providers propose interpretations of selected observations" not in guide
    assert "constitutional substrate for durable understanding" not in guide
    assert "label: 'Upload'" not in guide
    assert "label: 'Segment'" not in guide


def test_guide_navigation_contract_matches_current_surfaces() -> None:
    index = INDEX.read_text()
    guide = _guide_source()
    router = _extract_function(index, "function e10Go(")

    assert "if (id === 'setup')      e10LoadSetup();" in router
    assert "if (id === 'reader')    e10LoadCloseReader();" in router
    assert "if (id === 'lab')" in router
    assert "if (id === 'review')    e10LoadReview();" in router
    assert "if (id === 'architect') e10LoadArchitect();" in router
    assert "if (id === 'reports')   e10LoadReader();" in router
    assert "if (id === 'critic')    e10LoadCriticExplorer();" in router
    assert "if (id === 'lineage')   e10LoadLineageExplorer();" in router
    assert "if (id === 'guide')          e10LoadGuide();" in router
    assert "if (id === 'constitution')   e10LoadConstitution();" in router
    assert 'onclick="e10Go(\'${s.nav}\')"' in guide


def test_guide_preserves_read_aloud_and_constitution_link() -> None:
    index = INDEX.read_text()
    guide_section = index[index.index('<section class="section e10-screen" id="guide">') :]
    guide_section = guide_section[: guide_section.index('<section class="section e10-screen" id="constitution">')]
    guide = _guide_source()

    assert 'id="tts-btn-guide"' in guide_section
    assert "ttsReadEl('guide','guide-panel')" in guide_section
    assert "Read the Constitution" in guide
    assert "e10Go('constitution')" in guide
