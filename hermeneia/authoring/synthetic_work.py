"""Build a synthetic, verified Publication Compositor work for S1 fixtures.

Run with a configured Publication Compositor Python (it imports only the
Compositor package, never Hermeneia)::

    <compositor-python> synthetic_work.py OUTPUT_DIR

Every artifact is produced by Compositor's own builders and verified before it
is written. The text is synthetic; no manuscript content is involved. Two body
paragraphs share identical wording so tests can prove that an edit targets one
exact unit identity rather than a textual match.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

WORK_MANIFEST = "compositor-work.json"
WORK_MANIFEST_SCHEMA = "hermeneia-compositor-work/0.1"
FONT_FAMILY = "Synthetic Test Serif"
TEXTS = (
    ("Synthetic Heading", "SECTION_HEADING"),
    ("The lamp glows.", "BODY"),
    ("The lamp glows.", "BODY"),
    ("A closing paragraph.", "BODY"),
)


def _font(path: Path) -> Path:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    characters = "".join(chr(code) for code in range(32, 127))
    glyph_order = list(dict.fromkeys([".notdef", "space"] + [
        f"uni{ord(c):04X}" for c in characters if c != " "
    ]))
    cmap = {ord(c): ("space" if c == " " else f"uni{ord(c):04X}") for c in characters}
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    glyphs, metrics = {}, {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        if name not in {".notdef", "space"}:
            pen.moveTo((80, 0)); pen.lineTo((520, 0)); pen.lineTo((520, 700)); pen.lineTo((80, 700)); pen.closePath()
        glyphs[name] = pen.glyph()
        metrics[name] = (600, 0)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({
        "familyName": FONT_FAMILY,
        "styleName": "Regular",
        "uniqueFontIdentifier": "Hermeneia-SyntheticTestSerif-Regular",
        "fullName": f"{FONT_FAMILY} Regular",
        "psName": "SyntheticTestSerif-Regular",
    })
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200, usWeightClass=400)
    builder.setupPost()
    builder.setupMaxp()
    builder.save(path)
    return path


def _document():
    from publication_compositor.ir import (
        BoundingBox, DocumentIR, SourceBlock, SourceCharacter, SourceLine,
        SourceManifest, SourcePage, SourceSpan, StructuralRole,
    )

    characters, spans, lines, blocks = [], [], [], []
    for index, (text, role_name) in enumerate(TEXTS, start=1):
        role = getattr(StructuralRole, role_name)
        cid, lid, bid = f"p0001-c{index:06d}", f"p0001-l{index:04d}", f"p0001-b{index:04d}"
        sid = f"{lid}-s001"
        top = 80.0 + index * 40.0
        bbox = BoundingBox(x0=60.0, y0=top, x1=320.0, y1=top + 12.0)
        characters.append(SourceCharacter(id=cid, value=text, page_number=1, bbox=bbox, font_name="Synthetic", font_size=10.0))
        spans.append(SourceSpan(id=sid, page_number=1, character_ids=(cid,), text=text, bbox=bbox, font_name="Synthetic", font_size=10.0))
        lines.append(SourceLine(id=lid, page_number=1, span_ids=(sid,), character_ids=(cid,), text=text, bbox=bbox))
        blocks.append(SourceBlock(
            id=bid, page_number=1, line_ids=(lid,), span_ids=(sid,), character_ids=(cid,), text=text,
            bbox=bbox, inferred_role=role, role_confidence=0.99, role_evidence=(f"synthetic role={role.value}",),
        ))
    page = SourcePage(
        page_number=1, width=432.0, height=648.0,
        character_ids=tuple(c.id for c in characters), span_ids=tuple(s.id for s in spans),
        line_ids=tuple(line.id for line in lines), block_ids=tuple(b.id for b in blocks),
    )
    return DocumentIR(
        pages=(page,), blocks=tuple(blocks), lines=tuple(lines), spans=tuple(spans),
        characters=tuple(characters),
        manifest=SourceManifest(
            source_filename="hermeneia-s1-synthetic.pdf",
            source_pdf_sha256=hashlib.sha256(b"hermeneia-s1-synthetic-source").hexdigest(),
            page_count=1,
            ordered_character_ids=tuple(item.id for item in characters),
            ordered_block_ids=tuple(item.id for item in blocks),
            canonical_text_sha256=SourceManifest.hash_text("".join(text for text, _role in TEXTS)),
        ),
    )


def _profile():
    from publication_compositor.construction import PresentationStyleToken
    from publication_compositor.profiles import PageProfile, PaginationProfile, PublicationProfile, StyleRule

    return PublicationProfile(
        profile_id="hermeneia-s1-6x9",
        revision="1",
        language="en",
        page=PageProfile(width_pt=432.0, height_pt=648.0, margin_top_pt=54.0, margin_bottom_pt=54.0, margin_inner_pt=63.0, margin_outer_pt=45.0),
        pagination=PaginationProfile(show_folios=False, show_running_headers=False, toc_locators=False),
        styles=(
            StyleRule(
                style_token=PresentationStyleToken.SECTION_HEADING, font_families=(FONT_FAMILY,), font_size_pt=14.0,
                leading_em=0.2, weight="regular", italic=False, alignment="left",
            ),
            StyleRule(
                style_token=PresentationStyleToken.BODY, font_families=(FONT_FAMILY,), font_size_pt=10.0,
                leading_em=0.2, weight="regular", italic=False, alignment="left",
            ),
        ),
    )


def build(output_dir: Path) -> dict:
    from publication_compositor.canonical import (
        build_canonical_publication, propose_text_preserving_dispositions, verify_canonical_publication,
    )
    from publication_compositor.construction import (
        NavigationEmissionMode, build_canonical_construction_plan, verify_construction_plan,
    )
    from publication_compositor.profiles import resolve_layout_plan, verify_resolved_layout_plan
    from publication_compositor.renderers.typst import build_typst_renderer_environment
    from publication_compositor.renderers.typst.fonts import hash_typst_renderer_environment

    output_dir.mkdir(parents=True, exist_ok=False)
    source = _document()
    c0 = build_canonical_publication(source, propose_text_preserving_dispositions(source))
    if not verify_canonical_publication(source, c0).export_ready:
        raise SystemExit("synthetic C0 did not verify")
    base = build_canonical_construction_plan(c0)
    construction = base.model_copy(update={"manifest": base.manifest.model_copy(
        update={"navigation_emission_mode": NavigationEmissionMode.COMPLETE})})
    if not verify_construction_plan(source, c0, construction).passed:
        raise SystemExit("synthetic construction did not verify")
    profile = _profile()
    resolved = resolve_layout_plan(source, c0, construction, profile)
    if not verify_resolved_layout_plan(source, c0, construction, profile, resolved).passed:
        raise SystemExit("synthetic resolved layout did not verify")
    (output_dir / "fonts").mkdir()
    font = _font(output_dir / "fonts" / "SyntheticTestSerif-Regular.ttf")
    environment = build_typst_renderer_environment(resolved, [font], profile=profile)

    files = {
        "source_ir": ("source_ir.json", source.model_dump_json()),
        "canonical_c0": ("canonical_c0.json", c0.model_dump_json()),
        "construction": ("construction.json", construction.model_dump_json()),
        "profile": ("profile.json", profile.model_dump_json()),
        "resolved_layout": ("resolved_layout.json", resolved.model_dump_json()),
    }
    inputs = {}
    for kind, (name, text) in files.items():
        data = text.encode("utf-8")
        (output_dir / name).write_bytes(data)
        inputs[kind] = {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
    inputs["fonts"] = [{"path": "fonts/" + font.name, "sha256": hashlib.sha256(font.read_bytes()).hexdigest()}]
    manifest = {
        "schema": WORK_MANIFEST_SCHEMA,
        "label": "Synthetic S1 work",
        "synthetic": True,
        "inputs": inputs,
        "renderer_environment_sha256": hash_typst_renderer_environment(environment),
        "profile": {"id": profile.profile_id, "revision": profile.revision, "page_pt": [432.0, 648.0]},
    }
    (output_dir / WORK_MANIFEST).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1])), sort_keys=True))
