"""Ported Machine-Lens anchoring mechanics evaluator (reconstruction).

The original frozen evaluator was not available locally; these fixtures are
rebuilt from the task's written fixture descriptions. Oracle = exact machine
mark display offsets per block (plus human marks where relevant). The same
oracle is applied to any repo root passed as argv[1].

Usage: python3 mechanics_eval.py <repo_root> [out.json]
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

from hermeneia.storage.sqlite import SQLiteStore  # noqa: E402
from hermeneia.web.app import create_app  # noqa: E402
from hermeneia.compiler.sentence_splitter import split_sentences  # noqa: E402

HTML = (ROOT / "hermeneia/web/static/index.html").read_text()
NOW = "2026-01-01T00:00:00+00:00"

REQUIRED_FNS = [
    "_crStringList", "_crUniqueStringList", "_crProjectionExtractionIds",
    "_crProjectionSourceLocators", "_crReaderBlockContext",
    "_crInlineHighlightClass", "_crIsReaderSpanLocator", "_crDecodeReaderSpanLocator",
    "_crFiniteNumber", "_crTextOffset", "_crHasAnyValue", "_crHasComparableProvenance",
    "_crSpanHasProvenance", "_crBlockProvenanceWithinSpan", "_crBlockMatchesSpan",
    "_crBlockMatchesSpanPoint", "_crSpanRangeForBlock", "_crPushNonOverlappingRange",
    "_crHighlightSortKey", "_crSortedHighlightsForSegment", "_crHumanHighlightTitle",
    "_crHumanSegmentsFromRanges", "_crRenderTextWithHighlights", "_crMachineHighlightClass",
]
OPTIONAL_FNS = [
    "_crSourceOffset", "_crSourceSpanMatchesProvenance", "_crDisplaySourceSpansForProvenance",
    "_crLegacySpanEligibleSourceSpans", "_crDisplaySourceSpanForPoint",
    "_crSpanPointOffsetInBlock", "_crSpanUsesProjectedOffsets",
    "_crProjectSourceBoundary", "_crWithoutWhitespace", "_crMachineRangeForBlock",
]


def _fn(name: str, optional: bool = False) -> str:
    m = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", HTML, re.S)
    if not m:
        if optional:
            return ""
        raise SystemExit(f"missing function {name}")
    return m.group(0)


HARNESS = (
    "function x(s){return String(s==null?'':s).replace(/&/g,'&amp;')"
    ".replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}\n"
    "function _crHighlightTags(h){return (h&&h.tags)||[];}\n"
    "const _CR_READER_SPAN_LOCATOR_PREFIX='reader-span:v1:';\nlet _crPage=1;\n"
    + "".join(_fn(n) for n in REQUIRED_FNS)
    + "".join(_fn(n, optional=True) for n in OPTIONAL_FNS)
    + "const jobs=JSON.parse(require('fs').readFileSync(0,'utf8'));\n"
      "process.stdout.write(JSON.stringify(jobs.map(j=>_crRenderTextWithHighlights("
      "j.text,j.highlights,j.obs,j.ctx!==undefined?j.ctx:_crReaderBlockContext(j.ex,j.idx,j.page)))));\n"
)


def render(jobs: list[dict]) -> list[str]:
    out = subprocess.run([shutil.which("node"), "-e", HARNESS], input=json.dumps(jobs),
                         capture_output=True, text=True, timeout=60)
    if out.returncode:
        raise SystemExit(out.stderr)
    return json.loads(out.stdout)


_TAG = re.compile(r"<span ([^>]*)>|</span>|[^<]+")


def parse_marks(markup: str) -> tuple[str, list, list]:
    """Return (plain text, machine marks, human marks) in display coordinates."""
    plain, machine, human, stack = "", [], [], []
    for m in _TAG.finditer(markup):
        tok = m.group(0)
        if tok.startswith("<span "):
            attrs = m.group(1)
            mid = re.search(r'data-machine-obs="([^"]*)"', attrs)
            hid = re.search(r'data-highlight-ids?="([^"]*)"', attrs)
            stack.append(("machine", htmllib.unescape(mid.group(1))) if mid
                         else ("human", htmllib.unescape(hid.group(1)) if hid else ""))
            stack[-1] = stack[-1] + (len(plain),)
        elif tok == "</span>":
            kind, ident, start = stack.pop()
            (machine if kind == "machine" else human).append([start, len(plain), ident])
        else:
            plain += htmllib.unescape(tok)
    return plain, machine, human


class Fx:
    def __init__(self, tmp: Path):
        self.db = tmp / "fx.db"
        SQLiteStore(self.db).close()
        self.conn = sqlite3.connect(self.db)
        self.ext_text: dict[str, str] = {}

    def doc(self, doc_id: str, pages: int = 3):
        self.conn.execute(
            "INSERT INTO source_documents (id, original_filename, file_hash, total_pages,"
            " registered_at, compiler_version, source_role, excluded_from_analysis)"
            " VALUES (?,?,?,?,?,?,?,0)", (doc_id, doc_id[:6] + ".pdf", doc_id, pages, NOW, "t", "primary"))

    def ext(self, ext_id: str, doc_id: str, page: int, block: int, raw: str):
        self.ext_text[ext_id] = raw
        self.conn.execute(
            "INSERT INTO source_extractions (id, document_id, page, region, raw_text, parser,"
            " parser_version, coordinates, source_locator, source_hash, hash, extracted_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (ext_id, doc_id, page, f"block:{block}", raw, "t", "1", "{}",
             f"page:{page}:block:{block}", doc_id, ext_id, NOW))

    def obs(self, obs_id: str, doc_id: str, ext_id: str, page: int, sentence: int, raw: str | None = None):
        raw = raw if raw is not None else split_sentences(self.ext_text[ext_id])[sentence - 1]
        self.conn.execute(
            "INSERT INTO observations (id, epistemic_class, source_document_id, source_extraction_id,"
            " raw_text, source_locator, semantic_hash, page, paragraph, sentence, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (obs_id, "Evidence", doc_id, ext_id, raw, f"p{page}s{sentence}", obs_id, page, 1, sentence, NOW))

    def review(self, obs_id: str, status: str):
        self.conn.execute(
            "INSERT INTO observation_reviews (id, observation_id, review_status, created_at, updated_at)"
            " VALUES (?,?,?,?,?)", ("r-" + obs_id, obs_id, status, NOW, NOW))

    def highlight(self, hid: str, doc_id: str, page: int, selected: str):
        self.conn.execute(
            "INSERT INTO reader_highlights (id, source_document_id, page, selected_text, created_at,"
            " updated_at) VALUES (?,?,?,?,?,?)", (hid, doc_id, page, selected, NOW, NOW))

    def done(self):
        self.conn.commit()
        self.conn.close()


CANONICAL_TABLES = ["source_documents", "source_extractions", "observations", "provenance"]


def canonical_digest(db: Path) -> str:
    conn = sqlite3.connect(db)
    h = hashlib.sha256()
    for t in CANONICAL_TABLES:
        for row in conn.execute(f"SELECT * FROM {t} ORDER BY 1"):
            h.update(repr(row).encode())
    conn.close()
    return h.hexdigest()


def reader_page(db: Path, doc_id: str, page: int, lens: bool = True) -> list[dict]:
    """Mirror the Reader: /pages projection + /related-observations lens source."""
    client = create_app(db_path=db).test_client()
    pages = client.get(f"/api/reader/documents/{doc_id}/pages").get_json()["pages"]
    pd = next(p for p in pages if p["page"] == page)
    obs = client.get(f"/api/reader/documents/{doc_id}/related-observations?page={page}").get_json()["observations"]
    page_obs = [o for o in obs if int(o["page"]) == page] if lens else []
    highlights = [h for h in pd.get("highlights", []) if int(h.get("page") or 0) == page]
    exs = pd["extractions"]
    jobs = [{"text": ex.get("text") or "", "highlights": highlights, "obs": page_obs,
             "ex": ex, "idx": i, "page": page} for i, ex in enumerate(exs)]
    blocks = []
    for i, (ex, markup) in enumerate(zip(exs, render(jobs))):
        plain, machine, human = parse_marks(markup)
        blocks.append({"block": i, "text": ex.get("text") or "", "plain_ok": plain == (ex.get("text") or ""),
                       "machine": machine, "human": human, "markup": markup})
    return blocks


def machine_marks(blocks):
    return sorted([b["block"], s, e, i] for b in blocks for s, e, i in b["machine"])


def human_marks(blocks):
    return sorted([b["block"], s, e] for b in blocks for s, e, _ in b["human"])


# ── fixtures ─────────────────────────────────────────────────────────────────
A, B = "a" * 64, "b" * 64
FIXTURES = []


def fixture(name, family):
    def deco(f):
        FIXTURES.append((name, family, f))
        return f
    return deco


def _one(fx, raw, sentence, obs_id="o1"):
    fx.doc(A); fx.ext("e1", A, 1, 1, raw); fx.obs(obs_id, A, "e1", 1, sentence)


@fixture("unique_direct_match", "protected")
def f01(fx):
    _one(fx, "Gatsby looked at the light. Nick watched.", 2); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [[0, 28, 41, "o1"]], b


@fixture("html_escaped_text", "protected")
def f02(fx):
    # Fixture text corrected: "& C." ends in a single-letter "initial", which
    # the compiler's splitter never treats as a boundary.
    _one(fx, "Tom said A < B & that. Daisy laughed.", 1); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [[0, 0, 22, "o1"]] and "A &lt; B &amp; that" in b[0]["markup"], b


@fixture("drop_cap_continuation", "protected")
def f03(fx):
    fx.doc(A); fx.ext("e1", A, 1, 2, "I"); fx.ext("e2", A, 1, 3, "n my younger years my father gave me advice.")
    fx.obs("o1", A, "e2", 1, 1); fx.done()
    b = reader_page(fx.db, A, 1)
    return len(b) == 1 and machine_marks(b) == [[0, 1, len(b[0]["text"]), "o1"]], b


@fixture("unique_prose_merge_continuation", "protected")
def f04(fx):
    fx.doc(A); fx.ext("e1", A, 1, 1, "The old house stood on the hill where")
    fx.ext("e2", A, 1, 2, "nobody went anymore. Birds sang."); fx.obs("o1", A, "e2", 1, 1); fx.done()
    b = reader_page(fx.db, A, 1)
    return len(b) == 1 and machine_marks(b) == [[0, 38, 58, "o1"]], b


@fixture("unchanged_substring_after_offset_shift", "protected")
def f05(fx):
    _one(fx, "Intro  \n  wraps here. The bell rang.", 2); fx.done()
    b = reader_page(fx.db, A, 1)
    return b[0]["text"] == "Intro wraps here. The bell rang." and machine_marks(b) == [[0, 18, 32, "o1"]], b


@fixture("document_filtering", "protected")
def f06(fx):
    fx.doc(A); fx.doc(B); fx.ext("eA", A, 1, 1, "Nick watched the bay."); fx.ext("eB", B, 1, 1, "Nick watched the bay.")
    fx.obs("oB", B, "eB", 1, 1); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [], b


@fixture("neighboring_page_filtering", "protected")
def f07(fx):
    fx.doc(A); fx.ext("e1", A, 1, 1, "The bay was dark."); fx.ext("e2", A, 2, 1, "The bay was dark.")
    fx.obs("o2", A, "e2", 2, 1); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [], b


@fixture("rejected_observation_hidden", "protected")
def f08(fx):
    _one(fx, "Gatsby looked at the light. Nick watched.", 2); fx.review("o1", "rejected"); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [], b


@fixture("ordinary_human_precedence", "protected")
def f09(fx):
    _one(fx, "Gatsby looked at the light. Nick watched.", 1); fx.highlight("h1", A, 1, "the light"); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [] and human_marks(b) == [[0, 17, 26]], b


@fixture("lens_off_on_reconstruction", "protected")
def f10(fx):
    _one(fx, "Gatsby looked at the light. Nick watched.", 2); fx.done()
    off1 = reader_page(fx.db, A, 1, lens=False)
    on = reader_page(fx.db, A, 1, lens=True)
    off2 = reader_page(fx.db, A, 1, lens=False)
    ok = (machine_marks(off1) == [] and machine_marks(on) == [[0, 28, 41, "o1"]]
          and off1[0]["markup"] == off2[0]["markup"] and all(x["plain_ok"] for x in off1 + on + off2))
    return ok, on


@fixture("wrong_repeated_occurrence", "failure_family_1")
def f11(fx):
    _one(fx, "Echo. Echo.", 2); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [[0, 6, 11, "o1"]], b


@fixture("same_text_two_source_extractions", "failure_family_2")
def f12(fx):
    fx.doc(A); fx.ext("e1", A, 1, 1, "The lamp glows."); fx.ext("e2", A, 1, 2, "The lamp glows.")
    fx.obs("o1", A, "e2", 1, 1); fx.done()
    b = reader_page(fx.db, A, 1)
    return len(b) == 2 and machine_marks(b) == [[1, 0, 15, "o1"]], b


@fixture("projected_soft_wrap", "failure_family_3")
def f13(fx):
    _one(fx, "The quiet\nriver flows.", 1); fx.done()
    b = reader_page(fx.db, A, 1)
    return b[0]["text"] == "The quiet river flows." and machine_marks(b) == [[0, 0, 22, "o1"]], b


@fixture("offset_adjustment_inside_transformed_sentence", "failure_family_4")
def f14(fx):
    _one(fx, "First line\n  wraps. The quiet\n  river flows now.", 2); fx.done()
    b = reader_page(fx.db, A, 1)
    return (b[0]["text"] == "First line wraps. The quiet river flows now."
            and machine_marks(b) == [[0, 18, 44, "o1"]]), b


@fixture("human_overlap_suppresses_not_relocates", "failure_family_5")
def f15(fx):
    _one(fx, "Echo. Echo.", 1); fx.highlight("h1", A, 1, "Echo."); fx.done()
    b = reader_page(fx.db, A, 1)
    return machine_marks(b) == [] and human_marks(b) == [[0, 0, 5]], b


# ── renderer-boundary diagnostics (deliberately injected renderer inputs) ────
CTX = {"block_index": 0, "page": 1, "source_locator": "page:1:block:1",
       "source_locators": ["page:1:block:1"], "extraction_ids": ["e-A"], "display_source_spans": []}
BOUNDARY = [
    ("identity_less_injected_observation",
     {"text": "The lamp glows.", "highlights": [], "ctx": CTX,
      "obs": [{"id": "o1", "page": 1, "raw_text": "The lamp glows."}]}),
    ("misattributed_extraction_identity",
     {"text": "Echo. Echo.", "highlights": [], "ctx": CTX,
      "obs": [{"id": "o1", "page": 1, "raw_text": "Echo.", "canonical_span":
               {"source_extraction_id": "e-B", "start": 6, "end": 11, "text": "Echo."}}]}),
    ("out_of_range_canonical_span",
     {"text": "Echo. Echo.", "highlights": [], "ctx": CTX,
      "obs": [{"id": "o1", "page": 1, "raw_text": "Echo.", "canonical_span":
               {"source_extraction_id": "e-A", "start": 40, "end": 45, "text": "Echo."}}]}),
]


def run_all() -> dict:
    results = []
    for name, family, f in FIXTURES:
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fx(Path(tmp))
            # digest is taken right after seeding (inside f, before reads) via wrapper
            orig_done = fx.done
            state = {}

            def done():
                orig_done()
                state["before"] = canonical_digest(fx.db)
                state["bytes_before"] = hashlib.sha256(fx.db.read_bytes()).hexdigest()
            fx.done = done
            ok, blocks = f(fx)
            after = canonical_digest(fx.db)
            results.append({
                "fixture": name, "family": family, "path": "real_api_renderer",
                "pass": bool(ok) and all(b["plain_ok"] for b in blocks),
                "machine": machine_marks(blocks), "human": human_marks(blocks),
                "canonical_unchanged": state["before"] == after,
                "db_bytes_unchanged": state["bytes_before"] == hashlib.sha256(fx.db.read_bytes()).hexdigest(),
            })
    outs = render([job for _, job in BOUNDARY])
    for (name, _), markup in zip(BOUNDARY, outs):
        _plain, machine, _h = parse_marks(markup)
        results.append({"fixture": name, "family": "renderer_boundary", "path": "renderer_boundary",
                        "pass": machine == [], "machine": machine})
    api = [r for r in results if r["path"] == "real_api_renderer"]
    bnd = [r for r in results if r["path"] == "renderer_boundary"]
    return {
        "root_commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                      capture_output=True, text=True).stdout.strip(),
        "api_pass": sum(r["pass"] for r in api), "api_total": len(api),
        "boundary_pass": sum(r["pass"] for r in bnd), "boundary_total": len(bnd),
        "total_pass": sum(r["pass"] for r in results), "total": len(results),
        "canonical_unchanged_all": all(r.get("canonical_unchanged", True) for r in results),
        "db_bytes_unchanged_all": all(r.get("db_bytes_unchanged", True) for r in results),
        "results": results,
    }


if __name__ == "__main__":
    first = json.dumps(run_all(), indent=1, sort_keys=True)
    second = json.dumps(run_all(), indent=1, sort_keys=True)
    data = json.loads(first)
    data["second_run_byte_identical"] = first == second
    text = json.dumps(data, indent=1, sort_keys=True)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text)
    print(f"API {data['api_pass']}/{data['api_total']}  boundary {data['boundary_pass']}/{data['boundary_total']}"
          f"  total {data['total_pass']}/{data['total']}  canonical_unchanged={data['canonical_unchanged_all']}"
          f"  db_bytes_unchanged={data['db_bytes_unchanged_all']}  rerun_identical={data['second_run_byte_identical']}")
    for r in data["results"]:
        print(("PASS " if r["pass"] else "FAIL ") + r["family"].ljust(18) + r["fixture"], r["machine"])
