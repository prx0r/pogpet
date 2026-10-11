"""Canonical card service: one module behind REST and MCP.

ChatGPT decides what's funny. OddHobb guarantees what gets purchased is
exactly what gets printed. Both REST routes and MCP tools call these
functions — never each other — with an authenticated owner context.

P0 scope (frozen):
- jokes are TEMPLATE data: customers pick joke_id, edit inside_message +
  signature only. Per-customer joke writing is P3 (taste), not P0.
- lettering is type/styled only. ai mode is dropped until a spell gate exists.
- revisions are immutable: backend/cards.py already mints card_revisions
  rows and pins revisions on delivery options + orders. This module wraps
  that, it never rebuilds it.

Typed errors carry stable codes so agents recover instead of improvising:
TEXT_TOO_LONG, NEEDS_PHOTO, ART_GENERATION_PENDING, RENDER_QA_FAILED,
CHECKOUT_NOT_READY.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from . import card_scenes as scenes, config, db
from . import cards as _cards


class ServiceError(Exception):
    """Typed card-service failure. code is stable API; message is human."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


# ── templates + slots (jokes are template data) ──────────────────────────

def list_templates() -> list[dict]:
    """Reusable templates (not designs, not orders)."""
    out = []
    for tid, tpl in scenes.TEMPLATES.items():
        out.append({
            "id": tid, "label": tpl.get("label", tid),
            "min_photos": tpl.get("min_photos", 1), "max_photos": tpl.get("max_photos", 1),
            "formats": tpl.get("design_contract", {}).get("formats", ["5x7"]),
            "fonts_locked": tpl.get("fonts") or {},
            "jokes": _template_jokes(tid, tpl),
        })
    return out


def _template_jokes(tid: str, tpl: dict) -> list[dict]:
    """Approved jokes for a template. Customers pick joke_id; writing new
    jokes per customer is P3. PIL scenes ship their default headline as the
    single approved joke; cardgen templates expose their copy anchors."""
    jokes = [{"joke_id": "default", "headline": tpl.get("headline", ""),
              "punchline": "", "inside": ""}]
    return jokes


def cardgen_jokes(template_id: str) -> list[dict]:
    """Approved joke shelf for a cardgen template (copy anchors)."""
    try:
        from cardgen import engine as _eng
        tpl = _eng.template(template_id)
    except Exception as e:  # noqa: BLE001
        raise ServiceError("NEEDS_PHOTO", f"unknown template {template_id!r}", 404) from e
    jokes = []
    titles = (tpl.get("copy", {}).get("title", {}) or {}).get("examples", [])
    subs = (tpl.get("copy", {}).get("sub", {}) or {}).get("examples", [])
    insides = (tpl.get("copy", {}).get("inside", {}) or {}).get("examples", [])
    n = max(len(titles), len(subs), len(insides), 1)
    for i in range(n):
        jokes.append({
            "joke_id": f"{template_id}#{i + 1}",
            "headline": titles[i % len(titles)] if titles else "",
            "punchline": subs[i % len(subs)] if subs else "",
            "inside": insides[i % len(insides)] if insides else "",
        })
    return jokes


def get_slots(template_id: str) -> dict:
    """Editable slots, limits and defaults for a template."""
    tpl = scenes.TEMPLATES.get(template_id)
    if tpl is None:
        # cardgen template: photo wants + joke shelf + inside/signature text
        jokes = cardgen_jokes(template_id)  # raises NEEDS_PHOTO(404) when unknown
        try:
            from cardgen import engine as _eng
            want = (_eng.template(template_id).get("wants", {}) or {})
        except Exception:
            want = {}
        return {"template_id": template_id, "kind": "cardgen",
                "photo": want,
                "text": {"inside_message": {"max": 240}, "signature": {"max": 40}},
                "jokes": jokes}
    return {"template_id": template_id, "kind": "pil",
            "photo": {"min": tpl.get("min_photos", 1), "max": tpl.get("max_photos", 1)},
            "text": {"headline": {"max": 60}, "recipient": {"max": 60},
                     "sender": {"max": 80}, "inside_message": {"max": 500}},
            "jokes": _template_jokes(template_id, tpl)}


def list_styles() -> dict:
    """Allowed lettering presets. type/styled only — ai dropped until a
    spell-check gate exists."""
    return {"modes": ["type", "styled"],
            "fonts": getattr(scenes, "CARD_FONTS", {}),
            "sizes": getattr(scenes, "CARD_SIZES", {}),
            "colours": getattr(scenes, "CARD_COLOURS", {}),
            "aligns": getattr(scenes, "CARD_ALIGN", {}),
            "ai": {"available": False,
                   "reason": "dropped until a spell-check gate exists"}}


# ── designs (instances, not templates) ───────────────────────────────────

def _rec(owner: str, design_id: str, revision: int | None = None,
         code: str = "RENDER_QA_FAILED") -> dict:
    try:
        return _cards.record(owner, design_id, revision)
    except _cards.CardError as e:
        raise ServiceError(code, str(e), 404 if "not found" in str(e).lower() else 400) from e


def create(owner: str, template_id: str, fmt: str = "5x7",
           photos: list | None = None, via: str = "service") -> dict:
    """Instantiate a template as a draft design (revision 1)."""
    if template_id not in scenes.TEMPLATES:
        raise ServiceError("NEEDS_PHOTO", f"unknown PIL template {template_id!r}", 404)
    spec = {"template": template_id, "format": fmt,
            "photos": photos or []}
    tpl = scenes.TEMPLATES[template_id]
    spec.update({"headline": tpl.get("headline", ""), "recipient": "",
                 "sender": "", "inside_message": ""})
    out = save(owner, None, spec, via=via)
    return {"id": out["id"], "revision": 1, "spec": out["spec"]}


def set_slot(owner: str, design_id: str, slot: str, value: str) -> dict:
    """One text change -> a NEW immutable revision. Never mutates.

    Slots: joke_id (approved shelf only), inside_message, signature,
    headline/recipient/sender (PIL text limits). Photos change via the
    media path (NEEDS_PHOTO guidance), never here.
    """
    rec = _rec(owner, design_id)
    spec = dict(rec["spec"])
    if slot == "joke_id":
        joke = _resolve_joke(spec, value)
        spec["headline"] = joke.get("headline", spec.get("headline", ""))
        if joke.get("punchline"):
            spec["recipient"] = spec.get("recipient", "")
        if joke.get("inside"):
            spec["inside_message"] = joke["inside"]
    elif slot in ("inside_message", "signature", "headline", "recipient", "sender"):
        limit = {"inside_message": 500, "signature": 40, "headline": 60,
                 "recipient": 60, "sender": 80}[slot]
        if not isinstance(value, str) or len(value) > limit:
            raise ServiceError("TEXT_TOO_LONG",
                               f"{slot} must be text up to {limit} characters", 400)
        spec[slot] = value.strip()
    elif slot in ("photo", "photos", "front_art", "art"):
        raise ServiceError("NEEDS_PHOTO",
                           "photos change via add_media, not set_slot", 400)
    else:
        raise ServiceError("TEXT_TOO_LONG", f"unknown slot {slot!r}", 400)
    try:
        _cards.validate(owner, spec)
    except _cards.CardError as e:
        raise ServiceError("TEXT_TOO_LONG", str(e), 400) from e
    out = save(owner, design_id, spec, expected_revision=rec["revision"], via="service")
    return {"id": design_id, "revision": out["revision"], "spec": out["spec"],
            "supersedes": rec["revision"]}


def _resolve_joke(spec: dict, joke_id: str) -> dict:
    for j in get_slots(spec.get("template", "")).get("jokes", []):
        if j["joke_id"] == joke_id:
            return j
    # cardgen-backed designs keep template ref in ext
    raise ServiceError("TEXT_TOO_LONG",
                       f"unknown joke {joke_id!r} — pick one of the template's approved jokes", 400)


def save(owner: str, design_id: str | None, spec: dict,
         expected_revision: int | None = None, via: str = "service") -> dict:
    """Persist a full spec: create when design_id is None, else update with
    optimistic locking (409 on stale). Same-spec saves are idempotent.
    This is the single persistence path — the REST designs route and the
    MCP change flow both delegate here."""
    try:
        spec = _cards.validate(owner, spec)
    except _cards.CardError as e:
        msg = str(e)
        raise ServiceError("NEEDS_PHOTO" if "photo" in msg.lower() else "TEXT_TOO_LONG",
                           msg, 400) from e
    now = time.time()
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        if design_id is None:
            did = "card_" + uuid.uuid4().hex
            c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via)"
                      " VALUES (?,?,?,?,?,?,?)", (did, owner, 1, now, now, owner, via))
            c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                      (did, 1, _cards.json_dump(spec), now))
            c.commit()
            return {"id": did, "revision": 1, "spec": spec, "created": True}
        old = c.execute("SELECT * FROM card_designs WHERE id=?", (design_id,)).fetchone()
        if old is None:
            raise ServiceError("RENDER_QA_FAILED", "Card not found", 404)
        if old["owner"] != owner:
            raise ServiceError("RENDER_QA_FAILED", "Card not found", 404)
        if expected_revision != old["latest"]:
            raise ServiceError("CHECKOUT_NOT_READY",
                               "This card changed elsewhere. Reload before saving.", 409)
        prev = c.execute("SELECT spec FROM card_revisions WHERE design_id=? AND revision=?",
                         (design_id, old["latest"])).fetchone()
        if prev["spec"] == _cards.json_dump(spec):
            rev = old["latest"]
            created = False
        else:
            rev = old["latest"] + 1
            c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                      (design_id, rev, _cards.json_dump(spec), now))
            c.execute("UPDATE card_designs SET latest=?,updated_at=?,via=? WHERE id=?",
                      (rev, now, via, design_id))
            created = False
        c.commit()
    return {"id": design_id, "revision": rev,
            "spec": _cards.record(owner, design_id, rev)["spec"], "created": created}


# ── lettering (deterministic render, cached by everything that changes it) ─

def lettering_key(text: str, style_id: str, style_version: str, font_id: str,
                  font_version: str, box: tuple, resolution: int) -> str:
    """Cache key: old lettering must never survive a typography change."""
    raw = json.dumps({"t": text, "s": style_id, "sv": style_version,
                      "f": font_id, "fv": font_version,
                      "box": list(box), "r": resolution}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def lettering_plate(text: str, style_id: str = "type", font_id: str = "fraunces",
                    box: tuple = (1563, 400), resolution: int = 300) -> dict:
    """Type/styled plate with a consistent contract (transparent PNG).
    ai mode is not offered (no spell gate)."""
    if style_id not in ("type", "styled"):
        raise ServiceError("RENDER_QA_FAILED",
                           "ai lettering is unavailable until a spell-check gate exists", 400)
    key = lettering_key(text, style_id, "1", font_id, "1", box, resolution)
    cache = Path(config.DATA) / "cards" / "lettering" / (key + ".png")
    if cache.exists():
        return {"key": key, "path": str(cache), "cached": True}
    img = Image.new("RGBA", (box[0], max(1, box[1])), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((10, 10), text, fill=(20, 20, 20, 255))
    if style_id == "styled":
        d.rectangle([2, 2, box[0] - 3, box[1] - 3], outline=(20, 20, 20, 255), width=3)
    cache.parent.mkdir(parents=True, exist_ok=True)
    img.save(cache)
    return {"key": key, "path": str(cache), "cached": False}


# ── render / order (wrap, never rebuild) ─────────────────────────────────

def render(owner: str, design_id: str, revision: int | None = None) -> dict:
    """Front/inside/back previews for a frozen revision."""
    rec = _rec(owner, design_id, revision, "RENDER_QA_FAILED")
    rev = rec["revision"]
    try:
        gate = _cards.gate(owner, design_id, rev)
    except _cards.CardError as e:
        raise ServiceError("RENDER_QA_FAILED", str(e), 400) from e
    if isinstance(gate, dict) and gate.get("ok") is False:
        raise ServiceError("RENDER_QA_FAILED", str(gate.get("error", "gate failed")), 400)
    base = f"/api/cards/{design_id}/r{rev}"
    return {"id": design_id, "revision": rev,
            "views": {"front": base + "/preview", "inside": base + "/inside",
                      "back": base + "/back"}}


def checkout_ready(owner: str, design_id: str, revision: int) -> dict:
    """Preconditions for money: frozen revision + export ready + gate pass.
    Raises CHECKOUT_NOT_READY otherwise. The route still runs Shopify."""
    rec = _rec(owner, design_id, revision, "CHECKOUT_NOT_READY")
    latest = _rec(owner, design_id, None, "CHECKOUT_NOT_READY")["revision"]
    if revision != latest:
        raise ServiceError("CHECKOUT_NOT_READY",
                           f"revision {revision} is superseded by {latest} — approve the latest", 409)
    try:
        gate = _cards.gate(owner, design_id, revision)
    except _cards.CardError as e:
        raise ServiceError("CHECKOUT_NOT_READY", str(e), 409) from e
    if isinstance(gate, dict) and gate.get("ok") is False:
        raise ServiceError("CHECKOUT_NOT_READY", str(gate.get("error", "not ready")), 409)
    return {"id": design_id, "revision": revision, "frozen": True,
            "price": _cards.card_price()}


def get_order(owner: str, order_id: str) -> dict:
    with db.connect() as c:
        row = c.execute("SELECT * FROM card_orders WHERE id=? AND owner=?",
                        (order_id, owner)).fetchone()
    if row is None:
        raise ServiceError("CHECKOUT_NOT_READY", "unknown order", 404)
    return dict(row)
