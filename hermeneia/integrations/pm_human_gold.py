"""Performance Manuscript human-attention bridge: the bounded human-gold pass.

Governing authority: ``docs/integrations/performance-manuscript-human-attention-bridge.md``
(active integration design, experimental / bounded). These are **bridge-local**
records, not constitutional objects: they add no epistemic class and no pipeline
stage. The PM vocabulary lives only under ``annotation_schema = pm-human-gold/1``.

Lifecycle of a gold pass (one document, one workspace):

    GOLD_OPEN    no provider/model execution (local models included); machine
                 proposals and confidence hidden; first-pass human-gold events only
    GOLD_SEALED  explicit append-only human act; ends the blind phase only: no new
                 first-pass gold for the pass, but new annotations on new passages
                 keep being accepted as ``unblinded`` (phase ``post-gold``), and
                 reconsiderations of gold are successor events

Sealing never closes human-attention collection:

    human attention collection   continuously open
    blind independent gold       bounded and sealable
    model training / promotion   separately gated and versioned (outside Hermeneia)

Every record is append-only. The database enforces the lifecycle with triggers,
so the rules hold for any writer, not only this module. Human judgments are kept
apart from source evidence: events persist the source fingerprint, the durable
Reader anchor and the judgment, never manuscript prose.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DOMAIN = "performance-manuscript"
ANNOTATION_SCHEMA = "pm-human-gold/1"
EXPORT_SCHEMA = "pm-human-gold-export/1"

TARGET_FORMS = ("spoken-dialogue", "direct-thought", "character-authored-text", "embedded-quoted-text",
                "narrator-prose", "structural-or-metadata", "other")
SOURCE_CLASSES = ("roster-member", "named-person-missing-from-roster", "descriptive-non-roster-source",
                  "narrator", "structural", "unresolved")
MODALITIES = ("keyboard", "touch", "voice", "audio-review")
DEVICE_CLASSES = ("desktop", "tablet", "phone", "unknown")
MODES = ("human-gold", "unblinded")
GOLD_ACTIONS = ("annotate", "revise", "withdraw")
REVIEW_ACTIONS = ("ratify", "correct", "reject")   # need a visible machine proposal; never in a gold pass

# Tables whose rows mean a model has produced output in this workspace.
MACHINE_OUTPUT_TABLES = ("ai_provenance", "proposed_interpretations", "rendered_narratives", "critic_reports",
                         "findings", "authoring_proposals", "authoring_drafts")

_PERFORMANCE_TEXT = ("tone", "pace", "intensity")
_PERFORMANCE_LISTS = ("emphasis", "pauses", "pronunciation")
_JUDGMENT_KEYS = ("target_form", "source_class", "source_identity", "point_of_view", "perspective_refs",
                  "performance", "uncertainty", "note")

BRIDGE_DDL = """
-- PM human-attention bridge (bridge-local, experimental). Not constitutional ontology.
CREATE TABLE IF NOT EXISTS pm_gold_pass_events (
    id                  TEXT PRIMARY KEY,
    gold_pass_id        TEXT NOT NULL,
    event               TEXT NOT NULL CHECK(event IN ('open','seal')),
    source_document_id  TEXT NOT NULL REFERENCES source_documents(id),
    source_fingerprint  TEXT NOT NULL,
    domain              TEXT NOT NULL,
    annotation_schema   TEXT NOT NULL,
    actor               TEXT NOT NULL CHECK(length(trim(actor)) > 0),
    note                TEXT,
    created_at          TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_gold_pass_once ON pm_gold_pass_events(gold_pass_id, event);

CREATE TRIGGER IF NOT EXISTS pm_gold_pass_events_no_update
BEFORE UPDATE ON pm_gold_pass_events
BEGIN SELECT RAISE(ABORT, 'gold pass events are immutable'); END;

CREATE TRIGGER IF NOT EXISTS pm_gold_pass_events_no_delete
BEFORE DELETE ON pm_gold_pass_events
BEGIN SELECT RAISE(ABORT, 'gold pass events are immutable'); END;

CREATE TRIGGER IF NOT EXISTS pm_gold_pass_open_rules
BEFORE INSERT ON pm_gold_pass_events
WHEN NEW.event = 'open' AND (
    EXISTS (SELECT 1 FROM pm_gold_pass_events o WHERE o.event = 'open' AND NOT EXISTS (
        SELECT 1 FROM pm_gold_pass_events s WHERE s.gold_pass_id = o.gold_pass_id AND s.event = 'seal'))
    OR NOT EXISTS (SELECT 1 FROM source_documents d
                   WHERE d.id = NEW.source_document_id AND d.file_hash = NEW.source_fingerprint))
BEGIN SELECT RAISE(ABORT, 'a gold pass is already open, or the source fingerprint does not match'); END;

CREATE TRIGGER IF NOT EXISTS pm_gold_pass_seal_rules
BEFORE INSERT ON pm_gold_pass_events
WHEN NEW.event = 'seal' AND NOT EXISTS (
    SELECT 1 FROM pm_gold_pass_events o
    WHERE o.gold_pass_id = NEW.gold_pass_id AND o.event = 'open'
      AND o.source_document_id = NEW.source_document_id AND o.source_fingerprint = NEW.source_fingerprint)
BEGIN SELECT RAISE(ABORT, 'only an open gold pass can be sealed'); END;

CREATE TABLE IF NOT EXISTS pm_human_attention_events (
    id                      TEXT PRIMARY KEY,
    domain                  TEXT NOT NULL,
    annotation_schema       TEXT NOT NULL,
    gold_pass_id            TEXT,
    mode                    TEXT NOT NULL CHECK(mode IN ('human-gold','unblinded')),
    action                  TEXT NOT NULL
        CHECK(action IN ('annotate','revise','withdraw','ratify','correct','reject')),
    supersedes              TEXT REFERENCES pm_human_attention_events(id),
    highlight_id            TEXT NOT NULL REFERENCES reader_highlights(id),
    source_document_id      TEXT NOT NULL REFERENCES source_documents(id),
    source_fingerprint      TEXT NOT NULL,
    anchor                  TEXT NOT NULL CHECK(length(trim(anchor)) > 0),
    page                    INTEGER,
    machine_observation_ref TEXT,
    modality                TEXT NOT NULL CHECK(modality IN ('keyboard','touch','voice','audio-review')),
    device_class            TEXT NOT NULL CHECK(device_class IN ('desktop','tablet','phone','unknown')),
    judgment                TEXT NOT NULL CHECK(json_valid(judgment)),
    actor                   TEXT NOT NULL CHECK(length(trim(actor)) > 0),
    created_at              TEXT NOT NULL,
    CHECK ((action = 'annotate') = (supersedes IS NULL)),
    CHECK (mode <> 'human-gold' OR (gold_pass_id IS NOT NULL AND machine_observation_ref IS NULL
                                    AND action IN ('annotate','revise','withdraw'))),
    CHECK (action NOT IN ('ratify','correct','reject') OR machine_observation_ref IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_hae_one_chain_per_highlight
    ON pm_human_attention_events(highlight_id) WHERE action = 'annotate';
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_hae_linear_chain
    ON pm_human_attention_events(supersedes) WHERE supersedes IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pm_hae_document ON pm_human_attention_events(source_document_id, created_at);

CREATE TRIGGER IF NOT EXISTS pm_human_attention_events_no_update
BEFORE UPDATE ON pm_human_attention_events
BEGIN SELECT RAISE(ABORT, 'human attention events are immutable'); END;

CREATE TRIGGER IF NOT EXISTS pm_human_attention_events_no_delete
BEFORE DELETE ON pm_human_attention_events
BEGIN SELECT RAISE(ABORT, 'human attention events are immutable'); END;

CREATE TRIGGER IF NOT EXISTS pm_hae_anchor_rules
BEFORE INSERT ON pm_human_attention_events
WHEN NOT EXISTS (SELECT 1 FROM reader_highlights h
                 WHERE h.id = NEW.highlight_id AND h.source_document_id = NEW.source_document_id)
  OR NOT EXISTS (SELECT 1 FROM source_documents d
                 WHERE d.id = NEW.source_document_id AND d.file_hash = NEW.source_fingerprint)
BEGIN SELECT RAISE(ABORT, 'event must anchor to a highlight on its fingerprinted source document'); END;

CREATE TRIGGER IF NOT EXISTS pm_hae_gold_requires_open_pass
BEFORE INSERT ON pm_human_attention_events
WHEN NEW.mode = 'human-gold' AND (
    NOT EXISTS (SELECT 1 FROM pm_gold_pass_events o
                WHERE o.gold_pass_id = NEW.gold_pass_id AND o.event = 'open'
                  AND o.source_document_id = NEW.source_document_id)
    OR EXISTS (SELECT 1 FROM pm_gold_pass_events s
               WHERE s.gold_pass_id = NEW.gold_pass_id AND s.event = 'seal'))
BEGIN SELECT RAISE(ABORT, 'human-gold events require the open gold pass of their document'); END;

CREATE TRIGGER IF NOT EXISTS pm_hae_no_unblinded_while_open
BEFORE INSERT ON pm_human_attention_events
WHEN NEW.mode = 'unblinded' AND EXISTS (
    SELECT 1 FROM pm_gold_pass_events o WHERE o.event = 'open' AND NOT EXISTS (
        SELECT 1 FROM pm_gold_pass_events s WHERE s.gold_pass_id = o.gold_pass_id AND s.event = 'seal'))
BEGIN SELECT RAISE(ABORT, 'no unblinded events while a gold pass is open'); END;

CREATE TRIGGER IF NOT EXISTS pm_hae_successor_rules
BEFORE INSERT ON pm_human_attention_events
WHEN NEW.supersedes IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM pm_human_attention_events p
    WHERE p.id = NEW.supersedes AND p.highlight_id = NEW.highlight_id AND p.action <> 'withdraw'
      AND (NEW.mode <> 'human-gold' OR p.gold_pass_id = NEW.gold_pass_id))
BEGIN SELECT RAISE(ABORT, 'a successor must follow a live event of the same annotation (and pass)'); END;
"""


class BridgeError(ValueError):
    """A request the bridge refuses; ``status`` is the HTTP status to report."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class ProviderExecutionBlocked(RuntimeError):
    """Raised when provider/model execution is attempted while a gold pass is open."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def ensure_pm_bridge_schema(conn: sqlite3.Connection) -> None:
    """Create the bridge tables (write path only; idempotent)."""
    conn.executescript(BRIDGE_DDL)
    conn.commit()


def bridge_ready(conn: sqlite3.Connection) -> bool:
    return _table_exists(conn, "pm_gold_pass_events") and _table_exists(conn, "pm_human_attention_events")


# ── Gold pass lifecycle ──────────────────────────────────────────────────────

def gold_passes(conn: sqlite3.Connection) -> list[dict]:
    """Every pass with its open / seal provenance and derived status (read-only)."""
    if not bridge_ready(conn):
        return []
    rows = [dict(r) for r in conn.execute("SELECT * FROM pm_gold_pass_events ORDER BY created_at, id")]
    passes: dict[str, dict] = {}
    for r in rows:
        p = passes.setdefault(r["gold_pass_id"], {"gold_pass_id": r["gold_pass_id"],
                                                  "source_document_id": r["source_document_id"],
                                                  "source_fingerprint": r["source_fingerprint"],
                                                  "domain": r["domain"], "annotation_schema": r["annotation_schema"],
                                                  "open": None, "seal": None})
        p[r["event"]] = {"event_id": r["id"], "actor": r["actor"], "note": r["note"], "at": r["created_at"]}
    for p in passes.values():
        p["status"] = "GOLD_SEALED" if p["seal"] else "GOLD_OPEN"
    return list(passes.values())


def current_open_pass(conn: sqlite3.Connection) -> dict | None:
    return next((p for p in gold_passes(conn) if p["status"] == "GOLD_OPEN"), None)


def open_pass_at(db_path: str | Path) -> dict | None:
    """The open pass of a workspace database, read through a read-only connection."""
    path = Path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return current_open_pass(conn)
    finally:
        conn.close()


def machine_output_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in MACHINE_OUTPUT_TABLES if _table_exists(conn, t)}


def open_gold_pass(conn: sqlite3.Connection, source_document_id: str, actor: str = "owner",
                   note: str | None = None, now: str | None = None) -> dict:
    """GOLD_OPEN: only in a workspace where no model has produced output."""
    doc = conn.execute("SELECT id, file_hash FROM source_documents WHERE id = ?", (source_document_id,)).fetchone()
    if not doc:
        raise BridgeError("unknown source document", 404)
    if current_open_pass(conn):
        raise BridgeError("a gold pass is already open in this workspace", 409)
    dirty = {t: n for t, n in machine_output_counts(conn).items() if n}
    if dirty:
        raise BridgeError("a gold pass needs a workspace in which no model has produced output; found: "
                          + ", ".join(f"{t}={n}" for t, n in sorted(dirty.items())), 409)
    pass_id = f"gp-{uuid.uuid4().hex}"
    conn.execute(
        "INSERT INTO pm_gold_pass_events (id, gold_pass_id, event, source_document_id, source_fingerprint, domain,"
        " annotation_schema, actor, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f"gpe-{uuid.uuid4().hex}", pass_id, "open", source_document_id, doc["file_hash"], DOMAIN,
         ANNOTATION_SCHEMA, actor, note, now or _now()))
    conn.commit()
    return next(p for p in gold_passes(conn) if p["gold_pass_id"] == pass_id)


def seal_gold_pass(conn: sqlite3.Connection, gold_pass_id: str, actor: str = "owner",
                   note: str | None = None, now: str | None = None) -> dict:
    """GOLD_SEALED: an explicit, append-only human act."""
    p = next((x for x in gold_passes(conn) if x["gold_pass_id"] == gold_pass_id), None)
    if not p:
        raise BridgeError("unknown gold pass", 404)
    if p["status"] != "GOLD_OPEN":
        raise BridgeError("gold pass is already sealed", 409)
    conn.execute(
        "INSERT INTO pm_gold_pass_events (id, gold_pass_id, event, source_document_id, source_fingerprint, domain,"
        " annotation_schema, actor, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f"gpe-{uuid.uuid4().hex}", gold_pass_id, "seal", p["source_document_id"], p["source_fingerprint"],
         DOMAIN, ANNOTATION_SCHEMA, actor, note, now or _now()))
    conn.commit()
    return next(x for x in gold_passes(conn) if x["gold_pass_id"] == gold_pass_id)


# ── Judgments (pm-human-gold/1) ──────────────────────────────────────────────

def _opt_text(v) -> bool:
    return v is None or isinstance(v, str)


def validate_judgment(judgment: Any, conn: sqlite3.Connection | None = None) -> list[str]:
    """Every field is optional; at least one must carry something. Unknown keys are refused."""
    if not isinstance(judgment, dict):
        return ["judgment must be an object"]
    errs = [f"unknown field: {k}" for k in judgment if k not in _JUDGMENT_KEYS]
    tf, sc = judgment.get("target_form"), judgment.get("source_class")
    if tf is not None and tf not in TARGET_FORMS:
        errs.append("target_form is not one of the seven target forms")
    if sc is not None and sc not in SOURCE_CLASSES:
        errs.append("source_class is not one of the six source classes")
    for k in ("source_identity", "point_of_view", "note"):
        if not _opt_text(judgment.get(k)):
            errs.append(f"{k} must be text")
    refs = judgment.get("perspective_refs", [])
    if not isinstance(refs, list) or not all(isinstance(r, str) and r.strip() for r in refs):
        errs.append("perspective_refs must be a list of Perspective ids")
    elif refs and conn is not None and _table_exists(conn, "perspectives"):
        known = {r[0] for r in conn.execute(
            f"SELECT id FROM perspectives WHERE id IN ({','.join('?' * len(refs))})", refs)}
        errs += [f"unknown Perspective: {r}" for r in refs if r not in known]
    perf = judgment.get("performance", {})
    if not isinstance(perf, dict):
        errs.append("performance must be an object")
    else:
        errs += [f"unknown performance field: {k}" for k in perf if k not in _PERFORMANCE_TEXT + _PERFORMANCE_LISTS]
        errs += [f"performance.{k} must be text" for k in _PERFORMANCE_TEXT if not _opt_text(perf.get(k))]
        errs += [f"performance.{k} must be a list of text" for k in _PERFORMANCE_LISTS
                 if not (isinstance(perf.get(k, []), list) and all(isinstance(x, str) for x in perf.get(k, [])))]
    unc = judgment.get("uncertainty", {})
    if not isinstance(unc, dict) or set(unc) - {"unresolved", "note"} \
            or not isinstance(unc.get("unresolved", False), bool) or not _opt_text(unc.get("note")):
        errs.append("uncertainty must be {unresolved: bool, note: text}")
    if not errs and not _has_content(judgment):
        errs.append("an annotation needs at least one field")
    return errs


def _has_content(j: Mapping) -> bool:
    def filled(v):
        if isinstance(v, str):
            return bool(v.strip())
        if isinstance(v, list):
            return any(filled(x) for x in v)
        if isinstance(v, dict):
            return any(filled(x) for x in v.values())
        return v is True
    return any(filled(j.get(k)) for k in _JUDGMENT_KEYS)


def _canonical(judgment: Mapping) -> str:
    return json.dumps(judgment, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ── Events ───────────────────────────────────────────────────────────────────

def _insert_event(conn, *, mode, action, gold_pass_id, supersedes, highlight, judgment, modality, device_class,
                  actor, now) -> dict:
    if modality not in MODALITIES:
        raise BridgeError(f"modality must be one of {', '.join(MODALITIES)}")
    if device_class not in DEVICE_CLASSES:
        raise BridgeError(f"device_class must be one of {', '.join(DEVICE_CLASSES)}")
    doc = conn.execute("SELECT file_hash FROM source_documents WHERE id = ?",
                       (highlight["source_document_id"],)).fetchone()
    event_id = f"hae-{uuid.uuid4().hex}"
    try:
        conn.execute(
            "INSERT INTO pm_human_attention_events (id, domain, annotation_schema, gold_pass_id, mode, action,"
            " supersedes, highlight_id, source_document_id, source_fingerprint, anchor, page,"
            " machine_observation_ref, modality, device_class, judgment, actor, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,?)",
            (event_id, DOMAIN, ANNOTATION_SCHEMA, gold_pass_id, mode, action, supersedes, highlight["id"],
             highlight["source_document_id"], doc["file_hash"] if doc else "", highlight["source_locator"],
             highlight["page"], modality, device_class, _canonical(judgment), actor, now or _now()))
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise BridgeError(f"refused by the event store: {exc}", 409) from exc
    conn.commit()
    return event(conn, event_id)


def _mode_for(conn, source_document_id: str) -> tuple[str, str | None]:
    open_p = current_open_pass(conn)
    if open_p:
        if open_p["source_document_id"] != source_document_id:
            raise BridgeError("a gold pass is open on another document; only that document can be annotated", 409)
        return "human-gold", open_p["gold_pass_id"]
    return "unblinded", None


def annotate(conn: sqlite3.Connection, highlight_id: str, judgment: Mapping, *, modality: str = "keyboard",
             device_class: str = "unknown", actor: str = "owner", now: str | None = None) -> dict:
    """First-pass annotation on a highlight: human-gold inside an open pass, otherwise unblinded."""
    errs = validate_judgment(judgment, conn)
    if errs:
        raise BridgeError("; ".join(errs))
    h = conn.execute("SELECT id, source_document_id, source_locator, page FROM reader_highlights WHERE id = ?",
                     (highlight_id,)).fetchone()
    if not h:
        raise BridgeError("unknown highlight", 404)
    if not (h["source_locator"] or "").strip():
        raise BridgeError("the highlight has no durable source locator to anchor to")
    mode, pass_id = _mode_for(conn, h["source_document_id"])
    return _insert_event(conn, mode=mode, action="annotate", gold_pass_id=pass_id, supersedes=None, highlight=h,
                         judgment=judgment, modality=modality, device_class=device_class, actor=actor, now=now)


def _successor(conn, event_id, action, judgment, modality, device_class, actor, now) -> dict:
    prev = conn.execute("SELECT * FROM pm_human_attention_events WHERE id = ?", (event_id,)).fetchone()
    if not prev:
        raise BridgeError("unknown event", 404)
    head = chain_head(conn, prev["highlight_id"])
    if head["id"] != event_id:
        raise BridgeError("only the current head of an annotation can be superseded", 409)
    if prev["action"] == "withdraw":
        raise BridgeError("a withdrawn annotation cannot be revised; annotate again instead", 409)
    h = conn.execute("SELECT id, source_document_id, source_locator, page FROM reader_highlights WHERE id = ?",
                     (prev["highlight_id"],)).fetchone()
    # Keep the event's own anchor even if the highlight row was edited later.
    h = dict(h, source_locator=prev["anchor"], page=prev["page"])
    mode, pass_id = _mode_for(conn, prev["source_document_id"])
    if mode == "human-gold" and prev["gold_pass_id"] != pass_id:
        raise BridgeError("this annotation was not made in the open gold pass", 409)
    if mode == "unblinded":
        pass_id = prev["gold_pass_id"]          # keep the linkage; the successor itself is not gold
    return _insert_event(conn, mode=mode, action=action, gold_pass_id=pass_id, supersedes=event_id, highlight=h,
                         judgment=judgment, modality=modality, device_class=device_class, actor=actor, now=now)


def revise(conn: sqlite3.Connection, event_id: str, judgment: Mapping, *, modality: str = "keyboard",
           device_class: str = "unknown", actor: str = "owner", now: str | None = None) -> dict:
    errs = validate_judgment(judgment, conn)
    if errs:
        raise BridgeError("; ".join(errs))
    return _successor(conn, event_id, "revise", judgment, modality, device_class, actor, now)


def withdraw(conn: sqlite3.Connection, event_id: str, *, modality: str = "keyboard", device_class: str = "unknown",
             actor: str = "owner", now: str | None = None) -> dict:
    return _successor(conn, event_id, "withdraw", {}, modality, device_class, actor, now)


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["judgment"] = json.loads(d["judgment"])
    return d


def event_phase(e: Mapping, seal_times: list[str]) -> str:
    """Derived provenance phase (never stored): blind-gold, post-gold or no-gold-pass."""
    if e["mode"] == "human-gold":
        return "blind-gold"
    if e["gold_pass_id"] or any(t <= e["created_at"] for t in seal_times):
        return "post-gold"
    return "no-gold-pass"


def event(conn: sqlite3.Connection, event_id: str) -> dict:
    return _row(conn.execute("SELECT * FROM pm_human_attention_events WHERE id = ?", (event_id,)).fetchone())


def chain_head(conn: sqlite3.Connection, highlight_id: str) -> dict:
    rows = {r["id"]: r for r in conn.execute(
        "SELECT * FROM pm_human_attention_events WHERE highlight_id = ?", (highlight_id,))}
    superseded = {r["supersedes"] for r in rows.values() if r["supersedes"]}
    heads = [r for i, r in rows.items() if i not in superseded]
    return _row(heads[0]) if heads else None


def annotations(conn: sqlite3.Connection, source_document_id: str | None = None) -> list[dict]:
    """One record per annotation chain: first pass, current head, full history (read-only)."""
    if not bridge_ready(conn):
        return []
    sql = "SELECT * FROM pm_human_attention_events"
    args: tuple = ()
    if source_document_id:
        sql += " WHERE source_document_id = ?"
        args = (source_document_id,)
    rows = [_row(r) for r in conn.execute(sql + " ORDER BY created_at, id", args)]
    seals: dict[str, list[str]] = {}
    for p in gold_passes(conn):
        if p["seal"]:
            seals.setdefault(p["source_document_id"], []).append(p["seal"]["at"])
    for r in rows:
        r["phase"] = event_phase(r, seals.get(r["source_document_id"], []))
    by_id = {r["id"]: r for r in rows}
    successor = {r["supersedes"]: r["id"] for r in rows if r["supersedes"]}
    out = []
    for root in (r for r in rows if r["action"] == "annotate"):
        history, cur = [root], root
        while cur["id"] in successor:
            cur = by_id[successor[cur["id"]]]
            history.append(cur)
        out.append({"annotation_id": root["id"], "highlight_id": root["highlight_id"],
                    "source_document_id": root["source_document_id"], "source_fingerprint": root["source_fingerprint"],
                    "anchor": root["anchor"], "page": root["page"], "gold_pass_id": root["gold_pass_id"],
                    "first_pass": root, "current": cur, "withdrawn": cur["action"] == "withdraw",
                    "history": history})
    return out


# ── Exports ──────────────────────────────────────────────────────────────────

_EVENT_EXPORT_FIELDS = ("id", "mode", "phase", "action", "supersedes", "gold_pass_id", "modality", "device_class",
                        "judgment", "actor", "created_at")


def _export_event(e: Mapping) -> dict:
    return {k: e[k] for k in _EVENT_EXPORT_FIELDS}


def export_human_gold(conn: sqlite3.Connection) -> dict:
    """Human annotations and provenance only: no machine fields, no manuscript prose. Deterministic."""
    anns = annotations(conn)
    return {
        "export_schema": EXPORT_SCHEMA, "domain": DOMAIN, "annotation_schema": ANNOTATION_SCHEMA,
        "gold_passes": gold_passes(conn),
        "annotations": [{
            "annotation_id": a["annotation_id"], "highlight_id": a["highlight_id"],
            "source_document_id": a["source_document_id"], "source_fingerprint": a["source_fingerprint"],
            "anchor": a["anchor"], "page": a["page"], "gold_pass_id": a["gold_pass_id"],
            "first_pass": _export_event(a["first_pass"]), "current": _export_event(a["current"]),
            "withdrawn": a["withdrawn"], "history": [_export_event(e) for e in a["history"]],
        } for a in anns],
    }


def export_pm_jsonl(conn: sqlite3.Connection, include_span_text: bool = False) -> str:
    """Derived, private, PM-oriented export: one line per annotation.

    With ``include_span_text`` the selected text is resolved from the highlight so PM can match it
    against its own extraction. That output contains manuscript text: it is private local material
    and never Git material.
    """
    data = export_human_gold(conn)
    spans = {}
    if include_span_text:
        spans = {r["id"]: r["selected_text"] for r in conn.execute("SELECT id, selected_text FROM reader_highlights")}
    lines = [json.dumps({"record": "manifest", "export_schema": EXPORT_SCHEMA + "+jsonl", "derived": True,
                         "private": True, "contains_manuscript_text": bool(include_span_text),
                         "gold_passes": data["gold_passes"]}, sort_keys=True, ensure_ascii=False)]
    for a in data["annotations"]:
        rec = {"record": "annotation", **a}
        if include_span_text:
            rec["span_text"] = spans.get(a["highlight_id"])
        lines.append(json.dumps(rec, sort_keys=True, ensure_ascii=False))
    return "\n".join(lines) + "\n"


# ── Bundle export / restore (append-only replay) ─────────────────────────────

def bundle_rows(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    if not bridge_ready(conn):
        return [], []
    passes = [dict(r) for r in conn.execute("SELECT * FROM pm_gold_pass_events ORDER BY created_at, id")]
    events = [dict(r) for r in conn.execute("SELECT * FROM pm_human_attention_events ORDER BY created_at, id")]
    return passes, events


_PASS_COLS = ("id", "gold_pass_id", "event", "source_document_id", "source_fingerprint", "domain",
              "annotation_schema", "actor", "note", "created_at")
_EVENT_COLS = ("id", "domain", "annotation_schema", "gold_pass_id", "mode", "action", "supersedes", "highlight_id",
               "source_document_id", "source_fingerprint", "anchor", "page", "machine_observation_ref", "modality",
               "device_class", "judgment", "actor", "created_at")


def replay_bundle_rows(conn: sqlite3.Connection, passes: list[dict], events: list[dict]) -> tuple[int, int]:
    """Restore by replaying the append-only history in time order, so every trigger re-validates it."""
    if not bridge_ready(conn):
        raise BridgeError("bridge tables are missing in the restore target")
    order ={"open": 0, "event": 1, "seal": 2}
    items = [(p["created_at"], order[p["event"]], p["id"], "pass", p) for p in passes]
    items += [(e["created_at"], order["event"], e["id"], "event", e) for e in events]
    for _at, _o, _id, kind, row in sorted(items, key=lambda t: (t[0], t[1], t[2])):
        cols = _PASS_COLS if kind == "pass" else _EVENT_COLS
        table = "pm_gold_pass_events" if kind == "pass" else "pm_human_attention_events"
        conn.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                     [row.get(c) for c in cols])
    return len(passes), len(events)


# ── Provider gate ────────────────────────────────────────────────────────────

class GoldGatedRegistry:
    """Delegates to a provider registry but refuses model execution while a gold pass is open.

    Only the deterministic ``null`` provider remains available. Local models are refused too:
    the pass must be independent of any machine proposal, not merely private.
    """

    def __init__(self, inner: Any, db_path: str | Path, on_block: Any = None):
        self._inner = inner
        self._db_path = Path(db_path)
        self._on_block = on_block

    def create(self, provider_id: str, **kwargs: object) -> Any:
        try:
            refuse_if_gold_open(self._db_path, provider_id)
        except ProviderExecutionBlocked as exc:
            if self._on_block is not None:
                self._on_block(exc)     # lets the web layer report a clean refusal
            raise
        return self._inner.create(provider_id, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def refuse_if_gold_open(db_path: str | Path, provider_id: str) -> None:
    if provider_id == "null":
        return
    p = open_pass_at(db_path)
    if p:
        raise ProviderExecutionBlocked(
            f"model execution is blocked while human-gold pass {p['gold_pass_id']} is open; "
            "seal the pass before any machine-assisted work")
