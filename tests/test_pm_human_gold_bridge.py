"""PM human-attention bridge: the bounded human-gold pass.

Authority: docs/integrations/performance-manuscript-human-attention-bridge.md.
Synthetic fixtures only; no manuscript text.

Invariants enforced here:
  - bridge records are append-only (database-level);
  - a gold pass opens only in a workspace in which no model has produced output;
  - sealing is explicit; after it no first-pass gold can be created for that pass;
  - revisions and withdrawals are successor events; the first pass survives;
  - gold events carry no machine reference and no ratify / correct / reject semantics;
  - events persist fingerprint + anchor + judgment, never manuscript prose;
  - the export holds human annotations and provenance only; reads have no side effects;
  - bundle export / restore round-trips the history and re-validates it.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.integrations import pm_human_gold as G
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.workspace.export import export_workspace_bundle
from hermeneia.workspace.restore import RestoreError, restore_workspace

DOC = "d" * 64
DOC2 = "e" * 64
SYNTHETIC = "The lantern hummed. Someone at the gate called out twice."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "hermeneia.db"
    SQLiteStore(db).close()
    conn = sqlite3.connect(db)
    for doc in (DOC, DOC2):
        conn.execute(
            "INSERT INTO source_documents (id, original_filename, file_hash, total_pages, registered_at,"
            " compiler_version, source_role, excluded_from_analysis) VALUES (?,?,?,?,?,?,?,?)",
            (doc, f"synthetic-{doc[0]}.pdf", doc, 3, _now(), "test", "primary", 0))
    conn.commit()
    conn.close()
    return db


def _client(db: Path, registry=None):
    return create_app(db_path=db, provider_registry=registry).test_client()


def _highlight(client, doc=DOC, text=SYNTHETIC, locator="p.1.s.2.§.1") -> str:
    r = client.post("/api/reader/highlights", json={"source_document_id": doc, "page": 1, "source_locator": locator,
                                                    "selected_text": text})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _open(client, doc=DOC) -> str:
    r = client.post("/api/bridge/pm/gold-passes", json={"source_document_id": doc})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["gold_pass_id"]


def _seal(client, pass_id):
    return client.post(f"/api/bridge/pm/gold-passes/{pass_id}/seal", json={"confirm": "seal"})


J1 = {"target_form": "spoken-dialogue", "source_class": "descriptive-non-roster-source",
      "source_identity": "someone at the gate", "performance": {"tone": "urgent", "pauses": ["after 'twice'"]}}
J2 = {"target_form": "spoken-dialogue", "source_class": "unresolved",
      "uncertainty": {"unresolved": True, "note": "two candidates"}}


def _annotate(client, hid, judgment=J1, **kw):
    return client.post("/api/bridge/pm/annotations", json={"highlight_id": hid, "judgment": judgment, **kw})


# ── Lifecycle ───────────────────────────────────────────────────────────────

def test_gold_pass_lifecycle_open_annotate_seal(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    pass_id = _open(c)
    state = c.get("/api/bridge/pm/gold-passes").get_json()
    assert state["open"]["gold_pass_id"] == pass_id and state["open"]["status"] == "GOLD_OPEN"
    assert state["open"]["open"]["actor"] == "owner" and state["open"]["source_fingerprint"] == DOC

    r = _annotate(c, _highlight(c), modality="touch", device_class="tablet")
    assert r.status_code == 201
    e = r.get_json()
    assert (e["mode"], e["action"], e["gold_pass_id"], e["machine_observation_ref"]) == ("human-gold", "annotate",
                                                                                        pass_id, None)
    assert (e["modality"], e["device_class"], e["domain"], e["annotation_schema"]) == (
        "touch", "tablet", "performance-manuscript", "pm-human-gold/1")

    assert c.post(f"/api/bridge/pm/gold-passes/{pass_id}/seal", json={}).status_code == 400   # sealing is explicit
    r = _seal(c, pass_id)
    assert r.status_code == 200 and r.get_json()["status"] == "GOLD_SEALED"
    assert r.get_json()["seal"]["actor"] == "owner"
    assert _seal(c, pass_id).status_code == 409


def test_only_one_open_pass_and_only_its_document_can_be_annotated(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    _open(c, DOC)
    assert c.post("/api/bridge/pm/gold-passes", json={"source_document_id": DOC2}).status_code == 409
    other = _highlight(c, doc=DOC2)
    assert _annotate(c, other).status_code == 409


def test_open_requires_a_workspace_where_no_model_has_run(tmp_path):
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO ai_provenance (id, staged_object_id, generating_model, generation_timestamp, prompt_reference,"
        " prompt_reference_type, created_at) VALUES ('aip-1', 'pi-1', 'synthetic-model', ?, 'h', 'hash', ?)",
        (_now(), _now()))
    conn.commit()
    conn.close()
    r = _client(db).post("/api/bridge/pm/gold-passes", json={"source_document_id": DOC})
    assert r.status_code == 409 and "ai_provenance=1" in r.get_json()["error"]


def test_after_seal_no_first_pass_gold_and_reconsiderations_are_unblinded_successors(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    pass_id = _open(c)
    first = _annotate(c, _highlight(c)).get_json()
    _seal(c, pass_id)

    late = _annotate(c, _highlight(c, locator="p.2.s.1.§.1")).get_json()
    assert late["mode"] == "unblinded" and late["gold_pass_id"] is None

    rev = c.post(f"/api/bridge/pm/annotations/{first['id']}/revise", json={"judgment": J2}).get_json()
    assert (rev["mode"], rev["action"], rev["supersedes"], rev["gold_pass_id"]) == ("unblinded", "revise",
                                                                                  first["id"], pass_id)
    ann = next(a for a in c.get("/api/bridge/pm/annotations").get_json()["annotations"]
               if a["annotation_id"] == first["id"])
    assert ann["first_pass"]["judgment"] == J1 and ann["first_pass"]["mode"] == "human-gold"
    assert ann["current"]["judgment"] == J2 and len(ann["history"]) == 2

    # a gold event can never be written into a sealed pass, even directly
    conn = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO pm_human_attention_events (id, domain, annotation_schema, gold_pass_id, mode, action,"
                     " highlight_id, source_document_id, source_fingerprint, anchor, modality, device_class, judgment,"
                     " actor, created_at) VALUES ('hae-x','performance-manuscript','pm-human-gold/1',?,'human-gold',"
                     "'annotate',?,?,?,'p.3','keyboard','unknown','{}','owner',?)",
                     (pass_id, _highlight(c, locator="p.3.s.1.§.1"), DOC, DOC, _now()))


def test_revise_and_withdraw_preserve_first_pass_and_chain_is_linear(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    _open(c)
    first = _annotate(c, _highlight(c)).get_json()
    rev = c.post(f"/api/bridge/pm/annotations/{first['id']}/revise", json={"judgment": J2}).get_json()
    assert rev["mode"] == "human-gold"                                   # reconsidered while still blind
    assert c.post(f"/api/bridge/pm/annotations/{first['id']}/revise", json={"judgment": J1}).status_code == 409
    wd = c.post(f"/api/bridge/pm/annotations/{rev['id']}/withdraw", json={}).get_json()
    assert wd["action"] == "withdraw"
    assert c.post(f"/api/bridge/pm/annotations/{wd['id']}/revise", json={"judgment": J1}).status_code == 409
    ann = c.get("/api/bridge/pm/annotations").get_json()["annotations"][0]
    assert ann["withdrawn"] and ann["first_pass"]["judgment"] == J1
    assert [e["action"] for e in ann["history"]] == ["annotate", "revise", "withdraw"]


def test_sealing_ends_only_the_blind_phase_new_passages_keep_being_annotated(tmp_path):
    """GOLD_SEALED closes blind gold, never human-attention collection."""
    db = _db(tmp_path)
    c = _client(db)
    pass_id = _open(c)
    gold = _annotate(c, _highlight(c)).get_json()
    assert _seal(c, pass_id).status_code == 200

    fresh = _annotate(c, _highlight(c, locator="p.2.s.4.§.1"), judgment=J2, modality="touch").get_json()
    assert (fresh["mode"], fresh["action"], fresh["gold_pass_id"], fresh["supersedes"]) == ("unblinded", "annotate",
                                                                                          None, None)
    rev = c.post(f"/api/bridge/pm/annotations/{fresh['id']}/revise", json={"judgment": J1})
    assert rev.status_code == 201 and rev.get_json()["mode"] == "unblinded"

    anns = {a["annotation_id"]: a for a in c.get("/api/bridge/pm/export").get_json()["annotations"]}
    assert anns[gold["id"]]["first_pass"]["phase"] == "blind-gold"
    assert anns[fresh["id"]]["first_pass"]["phase"] == "post-gold" and anns[fresh["id"]]["current"]["phase"] == "post-gold"
    assert anns[fresh["id"]]["first_pass"]["judgment"] == J2 and anns[fresh["id"]]["current"]["judgment"] == J1
    assert anns[gold["id"]]["current"]["judgment"] == J1                   # the gold record is untouched


def test_workspace_ineligible_for_blind_gold_still_collects_human_attention(tmp_path):
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO ai_provenance (id, staged_object_id, generating_model, generation_timestamp, prompt_reference,"
        " prompt_reference_type, created_at) VALUES ('aip-1', 'pi-1', 'synthetic-model', ?, 'h', 'hash', ?)",
        (_now(), _now()))
    conn.commit()
    conn.close()
    c = _client(db)
    assert c.post("/api/bridge/pm/gold-passes", json={"source_document_id": DOC}).status_code == 409

    e = _annotate(c, _highlight(c)).get_json()
    assert (e["mode"], e["gold_pass_id"]) == ("unblinded", None)
    c.post(f"/api/bridge/pm/annotations/{e['id']}/revise", json={"judgment": J2})
    ann = c.get("/api/bridge/pm/export").get_json()["annotations"][0]
    assert ann["first_pass"]["phase"] == "no-gold-pass" and ann["first_pass"]["judgment"] == J1
    assert [h["action"] for h in ann["history"]] == ["annotate", "revise"]


# ── Append-only and gold semantics in the database ──────────────────────────

def test_bridge_records_are_append_only(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    _open(c)
    _annotate(c, _highlight(c))
    conn = sqlite3.connect(db)
    for sql in ("UPDATE pm_human_attention_events SET judgment = '{}'", "DELETE FROM pm_human_attention_events",
                "UPDATE pm_gold_pass_events SET actor = 'x'", "DELETE FROM pm_gold_pass_events"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)


def test_gold_events_refuse_machine_reference_and_review_actions(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    pass_id = _open(c)
    hid = _highlight(c)
    conn = sqlite3.connect(db)
    base = ("INSERT INTO pm_human_attention_events (id, domain, annotation_schema, gold_pass_id, mode, action, supersedes,"
            " highlight_id, source_document_id, source_fingerprint, anchor, machine_observation_ref, modality,"
            " device_class, judgment, actor, created_at) VALUES (?,?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?,?)")
    for action, ref in (("annotate", "pm-obs-1"), ("ratify", "pm-obs-1"), ("correct", None)):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(base, (f"hae-{action}", G.DOMAIN, G.ANNOTATION_SCHEMA, pass_id, "human-gold", action, hid,
                                DOC, DOC, "p.1", ref, "keyboard", "unknown", "{}", "owner", _now()))
    # and no unblinded record may be written while the pass is open
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(base, ("hae-u", G.DOMAIN, G.ANNOTATION_SCHEMA, None, "unblinded", "ratify", hid, DOC, DOC, "p.1",
                            "pm-obs-1", "keyboard", "unknown", "{}", "owner", _now()))


def test_events_persist_anchor_and_fingerprint_not_prose(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    _open(c)
    hid = _highlight(c, locator="reader-span:v1:%7B%22page%22%3A1%7D")
    _annotate(c, hid)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM pm_human_attention_events").fetchone())
    assert row["anchor"] == "reader-span:v1:%7B%22page%22%3A1%7D" and row["source_fingerprint"] == DOC
    assert SYNTHETIC not in json.dumps(row)
    # editing the highlight row later does not move the event's anchor
    c.patch(f"/api/reader/highlights/{hid}", json={"source_locator": "p.9.s.9"})
    assert conn.execute("SELECT anchor FROM pm_human_attention_events").fetchone()[0].startswith("reader-span:v1:")


def test_judgment_vocabulary_and_optional_fields(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    _open(c)
    assert _annotate(c, _highlight(c), judgment={"note": "typo: 'teh'"}).status_code == 201     # any single field
    for bad in ({}, {"target_form": "dialogue"}, {"source_class": "descriptive-non-roster-voice"},
                {"speaker": "x"}, {"performance": {"volume": "loud"}}, {"perspective_refs": ["no-such"]},
                {"uncertainty": {"unresolved": "yes"}}):
        r = _annotate(c, _highlight(c, locator=f"p.1.s.{len(json.dumps(bad))}"), judgment=bad)
        assert r.status_code == 400, bad
    assert set(G.TARGET_FORMS) == {"spoken-dialogue", "direct-thought", "character-authored-text",
                                   "embedded-quoted-text", "narrator-prose", "structural-or-metadata", "other"}
    assert len(G.SOURCE_CLASSES) == 6


# ── Exports and reads ───────────────────────────────────────────────────────

def test_export_holds_human_annotations_only_and_is_deterministic(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    _open(c)
    first = _annotate(c, _highlight(c)).get_json()
    c.post(f"/api/bridge/pm/annotations/{first['id']}/revise", json={"judgment": J2})
    a, b = c.get("/api/bridge/pm/export").get_data(), c.get("/api/bridge/pm/export").get_data()
    assert a == b
    data = json.loads(a)
    assert SYNTHETIC not in a.decode() and "machine_observation_ref" not in a.decode()
    ann = data["annotations"][0]
    assert ann["first_pass"]["judgment"] == J1 and ann["current"]["judgment"] == J2
    assert data["gold_passes"][0]["status"] == "GOLD_OPEN"

    plain = c.get("/api/bridge/pm/export.jsonl").get_data(as_text=True)
    private = c.get("/api/bridge/pm/export.jsonl?span_text=1")
    assert SYNTHETIC not in plain and json.loads(plain.splitlines()[0])["contains_manuscript_text"] is False
    lines = private.get_data(as_text=True).splitlines()
    assert json.loads(lines[0])["private"] is True and json.loads(lines[1])["span_text"] == SYNTHETIC
    assert "PRIVATE" in private.headers["Content-Disposition"]


def test_bridge_reads_have_no_side_effects(tmp_path):
    db = _db(tmp_path)
    c = _client(db)
    _open(c)
    _annotate(c, _highlight(c))

    def dump():
        conn = sqlite3.connect(db)
        try:
            return "\n".join(conn.iterdump())
        finally:
            conn.close()
    before = dump()
    for url in ("/api/bridge/pm/gold-passes", "/api/bridge/pm/annotations", f"/api/bridge/pm/annotations?document_id={DOC}",
                "/api/bridge/pm/export", "/api/bridge/pm/export.jsonl?span_text=1"):
        assert c.get(url).status_code == 200
    assert dump() == before


# ── Bundle round trip ───────────────────────────────────────────────────────

def _bundle(db: Path, out: Path) -> dict:
    return export_workspace_bundle(db, out, generated_at="2026-09-27T00:00:00+00:00", workspace_id="ws-test")


def test_bundle_round_trip_replays_and_revalidates_history(tmp_path):
    (tmp_path / "a").mkdir()
    src = _db(tmp_path / "a")
    c = _client(src)
    pass_id = _open(c)
    first = _annotate(c, _highlight(c)).get_json()
    c.post(f"/api/bridge/pm/annotations/{first['id']}/revise", json={"judgment": J2})
    _seal(c, pass_id)
    c.post(f"/api/bridge/pm/annotations/{first['id']}/withdraw", json={})      # refused: not the head
    manifest = _bundle(src, tmp_path / "bundle")
    assert "pm-human-gold-v1" in manifest["required_capabilities"]
    assert manifest["counts"]["pm_human_attention_events"] == 2

    (tmp_path / "b").mkdir()
    dst = tmp_path / "b" / "hermeneia.db"
    restore_workspace(dst, tmp_path / "bundle")
    exp_src = _client(src).get("/api/bridge/pm/export").get_json()
    assert _client(dst).get("/api/bridge/pm/export").get_json() == exp_src

    # a tampered history (gold after seal) is refused on restore
    events = json.loads((tmp_path / "bundle" / "study" / "pm_human_attention_events.json").read_text())
    forged = dict(events[0], id="hae-forged", created_at="2999-01-01T00:00:00+00:00")
    (tmp_path / "bundle" / "study" / "pm_human_attention_events.json").write_text(json.dumps(events + [forged]))
    (tmp_path / "c").mkdir()
    with pytest.raises((RestoreError, sqlite3.IntegrityError)):
        restore_workspace(tmp_path / "c" / "hermeneia.db", tmp_path / "bundle")


def test_bundles_without_bridge_records_are_unchanged(tmp_path):
    db = _db(tmp_path)
    manifest = _bundle(db, tmp_path / "bundle")
    assert "required_capabilities" not in manifest
    assert not any(f["path"].startswith("study/pm_") for f in manifest["files"])
