"""Art shelf — browse the art, pick a surface.

One artifact, N wrappers: postcard (impulse), card (occasion), mug (gift),
poster (wall), mp4 (shareable video). No photo, no mesh, no credits.
Personalization is the upsell, not the entrance exam.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from backend import config, db
from backend import meme_video as _mv
from backend import video as _video
from backend.creative import comics as _comics

FORMATS = {
    "postcard": {"label": "Postcard", "price_cents": 399,
                 "blurb": "A6, posted to the door. Cheapest way to own it."},
    "card": {"label": "Greeting card", "price_cents": 599,
             "blurb": "Folded 5x7 with envelope."},
    "mug": {"label": "Mug", "price_cents": 1299,
            "blurb": "Their face on your mornings. Dishwasher-safe."},
    "poster": {"label": "Poster", "price_cents": 1499,
              "blurb": "Big, framable, conversation-starting."},
    "mp4": {"label": "Live MP4", "price_cents": 699,
            "blurb": "The strip as video: panels + deadpan voiceover."},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS art_orders (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, art_id TEXT NOT NULL,
 format TEXT NOT NULL, qty INTEGER NOT NULL, price_cents INTEGER NOT NULL,
 status TEXT NOT NULL, draft_url TEXT NOT NULL DEFAULT '',
 created_at REAL NOT NULL);
"""


def init():
    with db.connect() as c:
        c.executescript(SCHEMA)
        c.commit()


def list_art() -> list[dict]:
    """Every validated comic + its formats. Ranked by ledger taste later;
    insertion order today."""
    out = []
    for s in _comics.load_comics().values():
        out.append({"id": s.get("id"), "title": s.get("title"),
                    "premise": s.get("premise"), "caption": s.get("caption"),
                    "panels": len(s.get("panels") or []),
                    "formats": {k: {"label": v["label"],
                                    "price_cents": v["price_cents"],
                                    "blurb": v["blurb"]}
                                for k, v in FORMATS.items()}})
    return out


def get(art_id: str) -> dict:
    scripts = _comics.load_comics()
    if art_id not in scripts:
        raise KeyError(art_id)
    return scripts[art_id]


def order(owner: str, art_id: str, format: str, qty: int = 1) -> dict:
    """Reserve an art piece on a surface. No charge; Shopify draft when
    configured, local reservation otherwise."""
    script = get(art_id)
    if format not in FORMATS:
        raise ValueError(f"unknown format {format!r}")
    qty = max(1, min(int(qty or 1), 20))
    price = FORMATS[format]["price_cents"] * qty
    oid = "ord_art_" + uuid.uuid4().hex
    draft_url = ""
    try:
        from backend import shopify_fulfil as _sf
        if _sf.configured():
            d = _sf.create_draft_order(
                f"{script.get('title')} ({FORMATS[format]['label']})",
                price, qty, note=f"OddHobb art order {oid}")
            draft_url = ((d.get("draftOrder") or {}).get("invoiceUrl")) or ""
    except Exception:
        draft_url = ""
    init()
    with db.connect() as c:
        c.execute("INSERT INTO art_orders VALUES (?,?,?,?,?,?,?,?,?)",
                  (oid, owner, art_id, format, qty, price,
                   "pending_checkout", draft_url, time.time()))
        c.commit()
        row = dict(c.execute("SELECT * FROM art_orders WHERE id=?", (oid,)).fetchone())
    return {"order": row, "draft_url": draft_url,
            "currency": "GBP", "price_grade": "LIVE" if draft_url else "EST"}


def text_plate(title: str, lines: list[str], caption: str = "") -> Path:
    """Deterministic text plate (offline): the strip as readable cards
    until AI plates land. Same discipline as captions: words stay in code."""
    config.ensure_dirs()
    img = Image.new("RGB", (_mv.VW, _mv.VH), (17, 17, 17))
    d = ImageDraw.Draw(img)
    d.text((_mv.VW // 2, 420), title, font=_video._font(72),
           fill=(250, 250, 248), anchor="mm")
    y = 700
    for ln in lines[:6]:
        d.text((_mv.VW // 2, y), ln[:90], font=_video._font(44),
               fill=(220, 220, 214), anchor="mm")
        y += 110
    if caption:
        d.text((_mv.VW // 2, _mv.VH - 300), caption[:110], font=_video._font(48),
               fill=(214, 170, 85), anchor="mm")
    out = config.DATA / "art" / "plates" / f"plate_{uuid.uuid4().hex[:12]}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out


def mp4_path(art_id: str, voice: str = "ryan") -> Path:
    safe_voice = "".join(ch for ch in voice if ch.isalnum() or ch in "-_:")[:40]
    return config.DATA / "art" / "mp4" / f"{art_id}.{safe_voice or 'ryan'}.mp4"


def make_mp4(art_id: str, voice: str = "ryan",
             out_mp4: Path | str | None = None) -> Path:
    """Art piece -> vertical MP4 via text plates + voiceover. Deterministic
    path, so re-renders are cached, not repeated."""
    script = get(art_id)
    dest = Path(out_mp4) if out_mp4 else mp4_path(art_id, voice)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    panels = script.get("panels") or []
    plates, captions = [], []
    for i, p in enumerate(panels):
        lines = p.get("lines") or []
        plates.append(text_plate(f"{script.get('title', '')}  ·  {i + 1}/{len(panels)}",
                                 [p.get("scene", ""), *lines]))
        captions.append(lines[-1] if lines else p.get("scene", ""))
    captions[-1] = script.get("caption") or captions[-1]
    return _mv.slideshow(plates, captions, voice=voice, out_mp4=out_mp4)
