from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


INDEX = Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html"


def _extract_fn(html: str, name: str) -> str:
    match = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", html, re.S)
    assert match, f"could not extract function {name} from index.html"
    return match.group(0)


def test_companion_response_actions_prefill_editable_field_notes_without_saving():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Companion Field Notes UI test")

    html = INDEX.read_text()
    use_response = _extract_fn(html, "cmpUseResponse")
    attribution = _extract_fn(html, "_cmpAttribution")
    assert "flnSave" not in use_response
    assert "fetch(" not in use_response

    harness = (
        "function field(value){return {value,focused:false,selection:null,"
        "focus(){this.focused=true;},"
        "setSelectionRange(start,end){this.selection=[start,end];}};}\n"
        "const understanding=field('My existing draft.');\n"
        "const questions=field('');\n"
        "const fields={'fln-understanding':understanding,'fln-questions':questions};\n"
        "const document={getElementById(id){return fields[id]||null;}};\n"
        "const _cmpTranscript=["
        "{role:'user',text:'Explain this page.'},"
        "{role:'companion',text:'A provisional explanation.\\n\\nWhat changes next?',"
        "provider:'Claude',model:'anthropic/claude',context_used:[]}];\n"
        "let lane='instrument';let trayOpen=false;\n"
        "function flnSetLane(value){lane=value;}\n"
        "function flnToggleTray(value){trayOpen=value;}\n"
        + attribution
        + use_response
        + "cmpUseResponse(1,'understanding');\n"
        + "const first={understanding:understanding.value,focused:understanding.focused,"
        "selection:understanding.selection,lane,trayOpen};\n"
        + "cmpUseResponse(1,'questions');\n"
        + "const second={questions:questions.value,focused:questions.focused,"
        "selection:questions.selection,lane,trayOpen};\n"
        + "process.stdout.write(JSON.stringify({first,second}));\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    behavior = json.loads(result.stdout)
    # Brought in as an attributed quotation naming the model — honest authorship.
    quoted = ('Companion — Claude (anthropic/claude) said:\n'
              '"A provisional explanation.\n\nWhat changes next?"')
    assert behavior["first"] == {
        "understanding": f"My existing draft.\n\n{quoted}",
        "focused": True,
        "selection": [len(f"My existing draft.\n\n{quoted}")] * 2,
        "lane": "corpus",
        "trayOpen": True,
    }
    assert behavior["second"] == {
        "questions": quoted,
        "focused": True,
        "selection": [len(quoted)] * 2,
        "lane": "corpus",
        "trayOpen": True,
    }


def test_only_successful_companion_responses_offer_field_note_actions():
    html = INDEX.read_text()

    assert "Use this response" in html
    assert "Add to current understanding" in html
    assert "Add to pressing questions" in html
    assert "m.provider !== 'error'" in html
    assert "cmpUseResponse(${index}, 'understanding')" in html
    assert "cmpUseResponse(${index}, 'questions')" in html


def test_stub_response_gets_actions_but_error_message_does_not():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for Companion transcript UI test")

    html = INDEX.read_text()
    harness = (
        "function x(value){return String(value==null?'':value);}\n"
        "const host={innerHTML:'',scrollTop:0,scrollHeight:100};\n"
        "const document={getElementById(id){return id==='cmp-transcript'?host:null;}};\n"
        "const _cmpBusy=false;\n"
        "const _cmpTranscript=["
        "{role:'companion',text:'Local provisional reply.',provider:'Claude',model:'anthropic/claude',context_used:[]},"
        "{role:'companion',text:'Provider failed.',provider:'error',context_used:[]}];\n"
        + _extract_fn(html, "_cmpAttribution")
        + _extract_fn(html, "_cmpRenderTranscript")
        + "_cmpRenderTranscript();\n"
        + "process.stdout.write(host.innerHTML);\n"
    )
    result = subprocess.run(
        [node, "-e", harness],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("Use this response") == 1
    assert result.stdout.count("Add to current understanding") == 1
    # The transcript names the model that produced the reply.
    assert "Claude (anthropic/claude)" in result.stdout
    assert "Provider failed." in result.stdout
