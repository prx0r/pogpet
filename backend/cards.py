"""Owner-scoped saved cards and immutable artwork revisions.

Registered by server.py, sharing its auth gate and SQLite/R2 contracts.
Jobs are bounded, persisted, and recoverable after process interruption.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from PIL import Image, ImageOps

from . import card_scenes as scenes, config, db, storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS card_designs (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, latest INTEGER NOT NULL,
 created_at REAL NOT NULL, updated_at REAL NOT NULL,
 storage_owner TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS card_design_owner ON card_designs(owner,updated_at);
CREATE TABLE IF NOT EXISTS card_revisions (
 design_id TEXT NOT NULL REFERENCES card_designs(id), revision INTEGER NOT NULL,
 spec TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(design_id,revision));
CREATE TABLE IF NOT EXISTS card_jobs (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, design_id TEXT NOT NULL,
 revision INTEGER NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
 error TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS card_cutouts (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, photo_id TEXT NOT NULL,
 crop TEXT NOT NULL, asset_key TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS card_orders (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, design_id TEXT NOT NULL,
 revision INTEGER NOT NULL, qty INTEGER NOT NULL, price_cents INTEGER NOT NULL,
 spec TEXT NOT NULL, export_key TEXT NOT NULL, status TEXT NOT NULL,
 idempotency_key TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(owner,idempotency_key));
"""
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="card-render")
_slots = threading.BoundedSemaphore(8)
ownership_lock = threading.RLock()


class CardError(Exception):
    def __init__(self, message, code=400):
        super().__init__(message); self.code=code


def init():
    with db.connect() as c:
        c.executescript(SCHEMA)
        if "storage_owner" not in {r[1] for r in c.execute("PRAGMA table_info(card_designs)")}:
            c.execute("ALTER TABLE card_designs ADD COLUMN storage_owner TEXT NOT NULL DEFAULT ''")
        if "via" not in {r[1] for r in c.execute("PRAGMA table_info(card_designs)")}:
            c.execute("ALTER TABLE card_designs ADD COLUMN via TEXT NOT NULL DEFAULT ''")
        if "prodigi_ref" not in {r[1] for r in c.execute("PRAGMA table_info(card_orders)")}:
            c.execute("ALTER TABLE card_orders ADD COLUMN prodigi_ref TEXT NOT NULL DEFAULT ''")
        if "shopify_draft_id" not in {r[1] for r in c.execute("PRAGMA table_info(card_orders)")}:
            c.execute("ALTER TABLE card_orders ADD COLUMN shopify_draft_id TEXT NOT NULL DEFAULT ''")
        if "checkout_url" not in {r[1] for r in c.execute("PRAGMA table_info(card_orders)")}:
            c.execute("ALTER TABLE card_orders ADD COLUMN checkout_url TEXT NOT NULL DEFAULT ''")
        if "recipient_json" not in {r[1] for r in c.execute("PRAGMA table_info(card_orders)")}:
            c.execute("ALTER TABLE card_orders ADD COLUMN recipient_json TEXT NOT NULL DEFAULT ''")
        if "shipping_method" not in {r[1] for r in c.execute("PRAGMA table_info(card_orders)")}:
            c.execute("ALTER TABLE card_orders ADD COLUMN shipping_method TEXT NOT NULL DEFAULT 'Standard'")
        if "delivery_option_id" not in {r[1] for r in c.execute("PRAGMA table_info(card_orders)")}:
            c.execute("ALTER TABLE card_orders ADD COLUMN delivery_option_id TEXT NOT NULL DEFAULT ''")
        c.execute("""CREATE TABLE IF NOT EXISTS delivery_options (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, design_id TEXT NOT NULL,
 revision INTEGER NOT NULL, country TEXT NOT NULL DEFAULT 'GB',
 supplier TEXT NOT NULL, sku TEXT NOT NULL, shipping_method TEXT NOT NULL,
 ship_cents INTEGER NOT NULL DEFAULT 0, charge_cents INTEGER NOT NULL DEFAULT 0,
 arrival_from TEXT NOT NULL DEFAULT '', arrival_to TEXT NOT NULL DEFAULT '',
 carrier TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL)""")
        c.execute("UPDATE card_designs SET storage_owner=owner WHERE storage_owner=''")
        c.execute("UPDATE card_jobs SET status='failed',error='Render interrupted. Retry this revision.' WHERE status IN ('queued','running')")
        c.commit()


def json_dump(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def number(x):
    if isinstance(x,bool):
        raise CardError("Crop coordinates must be numbers")
    try:
        n=float(x)
    except (ValueError,TypeError):
        raise CardError("Crop coordinates must be numbers") from None
    if not math.isfinite(n):
        raise CardError("Crop coordinates must be finite")
    return n


def crop_box(x):
    if not isinstance(x,list) or len(x)!=4:
        raise CardError("crop must be [x,y,width,height] between 0 and 1")
    a,b,w,h=map(number,x)
    if a<0 or b<0 or w<.02 or h<.02 or a+w>1.000001 or b+h>1.000001:
        raise CardError("Crop is outside the photo or too small")
    return [a,b,w,h]


def photo(owner,pid):
    with db.connect() as c:
        row=c.execute("SELECT * FROM photos WHERE id=? AND owner=?",(pid,owner)).fetchone()
    if row is None:
        raise CardError("Photo not found",404)
    return dict(row)


def cutout(owner,cid,pid):
    with db.connect() as c:
        row=c.execute("SELECT * FROM card_cutouts WHERE id=? AND owner=? AND photo_id=?",(cid,owner,pid)).fetchone()
    if row is None:
        raise CardError("Cutout does not belong to this photo",404)
    return dict(row)


_MCP_STATUS_CACHE: dict = {"at": 0.0, "value": "unknown"}


def mcp_status() -> str:
    """live|degraded (cached 30s): is the MCP tier reachable? REST callers
    see this so agents know when they're off the main road."""
    import socket as _sock
    import time as _time
    if _time.time() - _MCP_STATUS_CACHE["at"] < 30:
        return _MCP_STATUS_CACHE["value"]
    # Full tier only: primary 8799 + MCP_PORT_FALLBACK replica.
    # :8800 is the PUBLIC tier (different allowlist), never a failover.
    import os as _os
    primary = _os.environ.get("MCP_PORT", "8799")
    fallback = _os.environ.get("MCP_PORT_FALLBACK", "")
    v = "degraded"
    for port in (primary, fallback):
        if not port:
            continue
        try:
            s = _sock.create_connection(("127.0.0.1", int(port)), timeout=1)
            s.close()
            v = "live"
            break
        except (OSError, ValueError):
            continue
    _MCP_STATUS_CACHE.update(at=_time.time(), value=v)
    return v


def save_delivery_option(owner, design_id, revision, country, route,
                         charge_cents, arrival_from, arrival_to) -> dict:
    """Persist one quoted route behind an opaque id. The UI and checkout
    pass only the id; supplier identity never leaves the server."""
    oid = "do_" + uuid.uuid4().hex[:16]
    with db.connect() as c:
        c.execute("INSERT INTO delivery_options (id,owner,design_id,revision,country,supplier,sku,shipping_method,ship_cents,charge_cents,arrival_from,arrival_to,carrier,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (oid, owner, design_id, revision, country, route["supplier"],
                   route.get("sku", ""), route.get("shipping_method", "Standard"),
                   int(round(route.get("supplier_ship", 0) * 100)), charge_cents,
                   arrival_from, arrival_to, route.get("carrier", ""), time.time()))
        c.commit()
    return {"id": oid}


def get_delivery_option(owner, oid, design_id=None, revision=None):
    """Load a saved route if it belongs to this owner (and optionally this
    design+revision). None when unknown, foreign, or mismatched."""
    with db.connect() as c:
        row = c.execute("SELECT * FROM delivery_options WHERE id=? AND owner=?",
                        (oid, owner)).fetchone()
    if not row:
        return None
    d = dict(row)
    if design_id is not None and (d["design_id"] != design_id or int(d["revision"]) != int(revision)):
        return None
    return d


def resolve_delivery_choice(owner, body, did, rev):
    """Validate an incoming delivery_option_id against this design+revision.
    Returns (shipping_method, delivery_option_id). Unknown option → 400.
    Absent option → Standard default (legacy callers keep working)."""
    dopt = str((body or {}).get("delivery_option_id") or "").strip()[:32]
    if not dopt:
        return "Standard", ""
    route = get_delivery_option(owner, dopt, did, rev)
    if route is None:
        raise CardError("unknown delivery option for this card", 400)
    return route["shipping_method"], dopt


# ── card P0 product truth ──────────────────────────────────────────
# One hidden Shopify product, one fixed retail price. Prodigi cost is an
# internal margin variable — the customer never sees EST.
CARD_PRODUCT_ID = "ODD-CARD-5X7"
CARD_PRODUCT_NAME = "OddHobb Personalised 5×7 Greeting Card"
CARD_PRODIGI_SKU = "CLASSIC-GRE-FEDR-7X5-BLA"
CARD_PRICE_CENTS = 299  # £2.99 fixed — envelope included (margin thin: verify pack pricing before scaling)


def card_price() -> dict:
    """Fixed retail truth for cards. Reads PRODIGI_PRODUCTS when present
    so config stays the source, but never floats — falls back to £2.99."""
    try:
        prod = (config.PRODIGI_PRODUCTS.get("greeting_card") or {})
        cents = int(prod.get("price_cents") or CARD_PRICE_CENTS)
        # clamp to the frozen P0 price: config drift must not change checkout
        if cents != CARD_PRICE_CENTS:
            cents = CARD_PRICE_CENTS
    except Exception:
        cents = CARD_PRICE_CENTS
    return {"product_id": CARD_PRODUCT_ID, "name": CARD_PRODUCT_NAME,
            "price_cents": cents, "price": f"£{cents/100:.2f}",
            "currency": "GBP", "price_grade": "FIXED",
            "prodigi_sku": CARD_PRODIGI_SKU}


def public_price() -> dict:
    """Customer-safe price: fixed £2.99 truth with no supplier internals.
    prodigi_sku stays server-side — the shelf never leaks suppliers."""
    p = card_price()
    return {k: p[k] for k in ("product_id", "name", "price_cents",
                              "price", "currency", "price_grade") if k in p}


def card_url_for(did: str, rev: int | None = None) -> str:
    base = (config.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
    if rev:
        return f"{base}/cards/{did}/r{rev}"
    return f"{base}/cards/{did}"


def proof_url_for(did: str) -> str:
    """One stable link per card — always shows the latest revision."""
    base = (config.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
    return f"{base}/proof/{did}"


def contact_sheet(owner, did, rev, *, width: int = 720):
    """Legacy 2×2 JPEG of the four spread faces — kept for the listing view.
    The default glance agents and humans see is now triptych_sheet (front |
    inside | back at one height), where no surface is a miniature."""
    parts = []
    for part in SPREAD_PARTS:
        with Image.open(local_asset(key(owner, did, rev, "spread-" + part.replace("_", "-")))) as im:
            parts.append(im.convert("RGB"))
    w = max(1, width // 2)
    cells = []
    for im in parts:
        r = w / im.width
        cells.append(im.resize((w, round(im.height * r)), Image.Resampling.LANCZOS))
    h = max(c.height for c in cells)
    sheet = Image.new("RGB", (w * 2, h * 2), "#fffdf7")
    for i, cell in enumerate(cells):
        sheet.paste(cell, ((i % 2) * w, (i // 2) * h))
    dest = config.DATA / "cards" / "cache" / f"contact-{did}-r{rev}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, "JPEG", quality=80)
    return dest


# ── generative title zones: render contract, not wishes ──────────────
# A title asset is exact 930×320 RGBA with real transparency. Anything
# else is REJECTED (None) and the card falls back to house serif — a bad
# title is the fallback, never a fudge. Exactness is enforced here at
# composition time; no diffusion model can promise exact pixels.
TITLE_ART_SIZE = (930, 320)


def fit_title_art(img):
    """Enforce the title contract. Returns exact-size RGBA or None."""
    try:
        art = img.convert("RGBA")
    except Exception:
        return None
    fitted = ImageOps.fit(art, TITLE_ART_SIZE, method=Image.Resampling.LANCZOS,
                          centering=(0.5, 0.5))
    if fitted.size != TITLE_ART_SIZE:
        return None
    alpha = list(fitted.getchannel("A").getdata())
    n = len(alpha)
    transparent = sum(1 for v in alpha if v < 128) / max(1, n)
    if transparent < 0.05:
        return None  # effectively opaque — would smother the cover
    return fitted


def generate_copy_llm(profile: dict, tone: str = "funny"):
    """Best-effort server-side inside line from real profile facts.
    Returns (message | None). No key → None. Never raises — the caller
    falls back to caller-supplied hint text, then to template lines."""
    import os as _os
    import json as _json
    import urllib.request as _ul
    key = _os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return None
    try:
        prof = dict(profile or {})
        facts = {k: prof.get(k) for k in
                 ("name", "relationship", "interests", "memories",
                  "personality", "nicknames") if prof.get(k)}
        model = _os.environ.get("OPENROUTER_COPY_MODEL", "openai/gpt-4o-mini")
        payload = _json.dumps({
            "model": model,
            "max_tokens": 80,
            "temperature": 0.9,
            "messages": [
                {"role": "system",
                 "content": ("Write ONE birthday-card inside line (max 200 characters) "
                             "from these recipient facts. Dry and affectionate, never cruel, "
                             "never generic. Reply with only the line, no quotes.")},
                {"role": "user", "content": _json.dumps(facts)[:800]},
            ],
        }).encode()
        req = _ul.Request("https://openrouter.ai/api/v1/chat/completions",
                          data=payload,
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json",
                                   "HTTP-Referer": "https://oddhobb.com",
                                   "X-Title": "OddHobb cards"},
                          method="POST")
        with _ul.urlopen(req, timeout=60) as res:
            data = _json.loads(res.read().decode() or "{}")
        text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        text = str(text).strip().strip("\"'")[:240]
        return text or None
    except Exception:
        return None


def triptych_sheet(owner, did, rev, *, height: int = 1008):
    """Fixed 3-panel preview: front | inside spread | back at one height.

    Surface-first glance for agents and humans — the front renders full-size
    as its own surface, never a subpanel in a collage. Prefers the preview
    singles (front/inside/back); falls back to spread faces when only a
    spread render exists. Requires preview OR spread ready, else 409."""
    from backend import card_scenes as _scenes
    try:
        with Image.open(local_asset(key(owner, did, rev, "preview"))) as im:
            front_img = im.convert("RGB")
        with Image.open(local_asset(key(owner, did, rev, "inside"))) as im:
            inside_img = im.convert("RGB")
    except Exception:
        with Image.open(local_asset(key(owner, did, rev, "spread-front"))) as im:
            front_img = im.convert("RGB")
        with Image.open(local_asset(key(owner, did, rev, "spread-inside-left"))) as im:
            left = im.convert("RGB")
        with Image.open(local_asset(key(owner, did, rev, "spread-inside-right"))) as im:
            right = im.convert("RGB")
        inside_img = Image.new("RGB", (left.width + right.width, max(left.height, right.height)), "#fffdf7")
        inside_img.paste(left, (0, 0))
        inside_img.paste(right, (left.width, 0))
    try:
        with Image.open(local_asset(key(owner, did, rev, "back"))) as im:
            back_img = im.convert("RGB")
    except Exception:
        with Image.open(local_asset(key(owner, did, rev, "spread-back"))) as im:
            back_img = im.convert("RGB")
    sheet = _scenes.triptych(front_img, inside_img, back_img, height=height)
    dest = config.DATA / "cards" / "cache" / f"triptych-{did}-r{rev}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, "JPEG", quality=82)
    return dest


# ── attach-art: third-party / generated art into fullbleed revisions ──
# Faces are validated (aspect + size + face presence), stored under the
# design's owner namespace, and pinned to a NEW revision — attach never
# mutates. Art is normalized to PNG on store (lossless render input);
# print upscaling happens at render time against the live SKU spec.
ART_FACE_SPECS = {
    "front": {"aspect": (5, 7), "face": True},
    "inside": {"aspect": (10, 7), "face": False},
    "back": {"aspect": (5, 7), "face": False},
}
ART_MAX_BYTES = 15 * 1024 * 1024
ART_MIN_SHORT_EDGE = 800
ART_ASPECT_TOL = 0.02

_face_detector = None
_face_detector_ok = None


def _face_detector_get():
    """YuNet DNN face detector (assets/face/*.onnx, CPU). None when cv2 or
    the model file is unavailable — callers degrade to heuristics + warning."""
    global _face_detector, _face_detector_ok
    if _face_detector_ok is not None:
        return _face_detector
    try:
        import cv2 as _cv2
        p = config.ROOT / "assets" / "face" / "face_detection_yunet_2023mar.onnx"
        if not p.is_file():
            raise OSError("no yunet model")
        _face_detector = _cv2.FaceDetectorYN_create(str(p), "", (320, 320))
    except Exception:
        _face_detector = None
    _face_detector_ok = _face_detector is not None
    return _face_detector


def fetch_art_bytes(url: str) -> bytes:
    """Fetch attached art server-side. Short-lived presigned links are copied
    into our own storage immediately by the caller."""
    import urllib.request as _ul
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 2000:
        raise CardError("art URL must be an https link", 400)
    try:
        req = _ul.Request(url, headers={"User-Agent": "OddHobb-attach/1.0"})
        with _ul.urlopen(req, timeout=60) as res:
            ctype = (res.headers.get("Content-Type") or "").lower()
            if not any(t in ctype for t in ("image/png", "image/jpeg", "image/webp", "image/jpg")):
                raise CardError(f"art must be PNG/JPEG/WebP (got {ctype or 'unknown type'})", 400)
            data = res.read(ART_MAX_BYTES + 1)
    except CardError:
        raise
    except Exception as e:
        raise CardError(f"could not fetch art: {str(e)[:120]}", 502) from None
    if len(data) > ART_MAX_BYTES:
        raise CardError("art must be 15 MB or smaller", 400)
    if not data:
        raise CardError("art URL returned no bytes", 400)
    head = data[:12]
    if head[:8] != b"\x89PNG\r\n\x1a\n" and head[:2] != b"\xff\xd8" and \
            not (head[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        raise CardError("art bytes are not PNG/JPEG/WebP", 400)
    return data


def validate_art_image(data: bytes, face: str):
    """Check size + aspect for one card face. Returns (PIL RGB image,
    warnings). Blocks (400) on unreadable, too-small, or wrong-aspect art."""
    spec = ART_FACE_SPECS[face]
    try:
        with Image.open(io.BytesIO(data)) as im:
            img = im.convert("RGB")
    except Exception:
        raise CardError(f"{face} art is unreadable", 400) from None
    if min(img.size) < ART_MIN_SHORT_EDGE:
        raise CardError(f"{face} art is {img.width}x{img.height} — need 800px on the short edge", 400)
    aw, ah = spec["aspect"]
    want = aw / ah
    got = img.width / img.height
    if abs(got - want) / want > ART_ASPECT_TOL:
        raise CardError(f"{face} art is {img.width}x{img.height} — need {aw}:{ah} aspect (±2%)", 400)
    return img, []


def face_presence(img) -> tuple[bool, str, str]:
    """Tiered face gate for attached front art. (found, detail, warning).
    YuNet hit → found. Miss on a near-flat image → no face (caller blocks).
    Miss on textured art → unconfirmed warning (illustrated faces routinely
    miss detection — warn, never block, per the attach contract)."""
    gray = img.convert("L")
    small = gray.copy()
    small.thumbnail((480, 480), Image.Resampling.LANCZOS)
    det = _face_detector_get()
    if det is not None:
        try:
            import cv2 as _cv2
            import numpy as _np
            rgb = _np.asarray(img.convert("RGB"))
            bgr = _cv2.cvtColor(rgb, _cv2.COLOR_RGB2BGR)
            h, w = bgr.shape[:2]
            det.setInputSize((w, h))
            _n, faces = det.detect(bgr)
            hits = [f for f in (faces or []) if float(f[-1]) >= 0.5]
            if hits:
                return True, f"{len(hits)} face(s)", ""
        except Exception:
            pass
    import statistics as _st
    px = list(small.getdata())
    sd = _st.pstdev(px) if len(px) > 1 else 0.0
    if sd < 8.0:
        return False, "near-flat image", ""
    if det is None:
        return False, "no detector available", "face_unconfirmed: no detector on this box — eye-QA the likeness"
    return False, "no detector hit on textured art", \
        "face_unconfirmed: illustrated faces miss detection — eye-QA the likeness"


def attach_art(owner, did, blobs, *, copy, headline_baked=True,
               art_source="", prompt=""):
    """Pin attached art to a NEW fullbleed revision (create the design when
    did is empty). blobs: {face: PIL image}. copy: headline/recipient/sender/
    inside_message. Returns (record, warnings, jobs)."""
    import time as _time
    if not isinstance(copy, dict):
        raise CardError("copy must be headline/recipient/sender/inside_message", 400)
    warnings: list[str] = []
    stored: dict[str, str] = {}
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        if did:
            d = c.execute("SELECT * FROM card_designs WHERE id=?", (did,)).fetchone()
            if d is None or d["owner"] != owner:
                raise CardError("Card not found", 404)
            base = json.loads(c.execute(
                "SELECT spec FROM card_revisions WHERE design_id=? AND revision=?",
                (did, d["latest"])).fetchone()["spec"])
            if base.get("template") != "birthday_fullbleed":
                raise CardError("attach-art is fullbleed only", 400)
            rev = d["latest"] + 1
        else:
            did = "card_" + uuid.uuid4().hex
            t = _time.time()
            base = {"template": "birthday_fullbleed", "format": "5x7", "photos": [],
                    "headline": str(copy.get("headline") or "Happy Birthday!"),
                    "recipient": str(copy.get("recipient") or ""),
                    "sender": str(copy.get("sender") or ""),
                    "inside_message": str(copy.get("inside_message") or "")}
            c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via) VALUES (?,?,?,?,?,?,?)",
                      (did, owner, 0, t, t, owner, "rest"))
            rev = 1
        # store art bytes first so validate() sees resolvable keys
        for face, img in blobs.items():
            dest = cached(f"owners/{storage._slug(owner)}/cards/{did}/r{rev}/art-{face}.png")
            img.save(dest, "PNG")
            skey = f"owners/{storage._slug(owner)}/cards/{did}/r{rev}/art-{face}.png"
            storage.put(dest, skey)
            stored[face] = skey
        new_spec = dict(base)
        for face, skey in stored.items():
            new_spec[{"front": "front_art_key", "inside": "inside_art_key",
                      "back": "back_art_key"}[face]] = skey
        if "front_art_key" not in new_spec or not new_spec.get("front_art_key"):
            raise CardError("Fullbleed needs front art — attach art first (art_required)")
        new_spec["headline_baked"] = bool(headline_baked)
        new_spec["art_source"] = str(art_source or "")[:40]
        new_spec["prompt"] = str(prompt or "")[:2000]
        for k in ("headline", "recipient", "sender", "inside_message"):
            if k in copy and isinstance(copy[k], str):
                new_spec[k] = copy[k]
        spec = validate(owner, new_spec)
        # effective print DPI warning (soft): art below ~200dpi prints soft
        try:
            fw, _fh = blobs["front"].size if "front" in blobs else (0, 0)
            from backend import prodigi as _prodigi
            area = _prodigi.print_area(CARD_PRODIGI_SKU)
            pw = int(area.get("horizontalResolution") or 0)
            if fw and pw and (fw / (pw / 4)) < 0.66:
                warnings.append("Front art is low-resolution for 300dpi print — it will render but may print soft. Regenerate larger.")
        except Exception:
            pass
        c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                  (did, rev, json_dump(spec), _time.time()))
        c.execute("UPDATE card_designs SET latest=?,updated_at=? WHERE id=?",
                  (rev, _time.time(), did))
        c.commit()
    jobs = []
    for kind in ("preview", "spread", "export"):
        try:
            jobs.append(job_payload(enqueue(owner, did, rev, kind)))
        except CardError:
            pass
    return record(owner, did, rev), warnings, jobs


def backfill_gallery_headlines(owner=None, limit=200):
    """One-off: personalize auto-created gallery designs still carrying
    template boilerplate. Only touches latest revisions with empty
    sender+message (never user-edited cards) and mints a NEW revision per
    fix. Returns [(did, old_rev, new_rev)]."""
    from backend import subjects as _sub
    out = []
    with db.connect() as c:
        owners = [owner] if owner else [
            r["owner"] for r in c.execute("SELECT DISTINCT owner FROM card_designs")]
    for ow in owners:
        with db.connect() as c:
            rows = c.execute("SELECT id,latest FROM card_designs WHERE owner=?",
                             (ow,)).fetchall()
        for r in rows:
            if len(out) >= limit:
                return out
            try:
                rec = record(ow, r["id"], r["latest"])
            except CardError:
                continue
            spec = rec["spec"]
            tpl = scenes.TEMPLATES.get(spec.get("template") or "")
            if not tpl or (spec.get("template") or "") not in scenes.BIRTHDAY_TEMPLATES:
                continue
            if spec.get("headline") != tpl["headline"]:
                continue
            if (spec.get("sender") or "") != "" or (spec.get("inside_message") or "") != "":
                continue
            photos = spec.get("photos") or []
            if not photos:
                continue
            with db.connect() as c2:
                hit = _sub.profile_for_photo(c2, ow, photos[0]["photo_id"])
            name = (hit.get("subject") or {}).get("name", "") if hit else ""
            short = str(name).split()[0] if str(name).split() else ""
            if not short:
                continue
            new_spec = dict(spec)
            new_spec["headline"] = f"Happy Birthday, {short}!"[:60]
            new_spec["recipient"] = name
            try:
                fspec = validate(ow, new_spec)
            except CardError:
                continue
            import time as _time
            with db.connect() as c3:
                c3.execute("BEGIN IMMEDIATE")
                cur = c3.execute("SELECT latest FROM card_designs WHERE id=?",
                                 (r["id"],)).fetchone()
                if cur is None or cur["latest"] != rec["revision"]:
                    continue  # someone else moved it; skip, don't clobber
                nrev = rec["revision"] + 1
                c3.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                           (r["id"], nrev, json_dump(fspec), _time.time()))
                c3.execute("UPDATE card_designs SET latest=?,updated_at=? WHERE id=?",
                           (nrev, _time.time(), r["id"]))
                c3.commit()
            try:
                enqueue(ow, r["id"], nrev, "preview")
            except CardError:
                pass
            out.append((r["id"], rec["revision"], nrev))
    return out


# Relationship → what the card actually calls them. The profile stores
# "father"/"mother"; the card says "Dad"/"Mum". Never title() the raw value
# ("Father!") — that reads like a court summons, not a birthday card.
RELATIONSHIP_LABELS = {
    "father": "Dad", "dad": "Dad", "daddy": "Dad", "pa": "Dad", "pop": "Dad",
    "mother": "Mum", "mum": "Mum", "mom": "Mum", "mummy": "Mum", "ma": "Mum",
    "grandfather": "Grandad", "grandad": "Grandad", "grandpa": "Grandad",
    "grandmother": "Grandma", "grandma": "Grandma", "granny": "Granny",
    "nan": "Nan", "nanna": "Nanna",
}


def display_label(name: str = "", relationship: str = "") -> str:
    """Card-safe name: relationship word first, else first name, else them."""
    rel = str(relationship or "").strip().lower()
    if rel in RELATIONSHIP_LABELS:
        return RELATIONSHIP_LABELS[rel]
    short = str(name or "").split()
    return short[0] if short else "them"


def message_lines(profile: dict, tone: str = "funny") -> list[dict]:
    """Smart-text v1 (deterministic): inside lines built from a subject
    profile's name/interests/memories. Each line cites its source fact so
    agents can show their work. Tones: funny (dry aliases too), warm, short.
    No interests → occasion-generic lines, never placeholder-sounding filler."""
    profile = profile or {}
    tone = str(tone or "funny").lower()
    if tone in ("dark", "dry", "sarcastic"):
        tone = "dry"
    elif tone in ("sentimental", "sweet", "warm"):
        tone = "warm"
    elif tone in ("short", "brief"):
        tone = "short"
    else:
        tone = "funny"
    name = str(profile.get("name") or "them")
    interests = [str(x) for x in (profile.get("interests") or []) if isinstance(x, str)][:4]
    memories = [str(x) for x in (profile.get("memories") or []) if isinstance(x, str)][:4]
    rel = str(profile.get("relationship") or "")
    who = name if name != "them" else ("Dad" if rel == "dad" else "them")
    out: list[dict] = []
    if tone == "warm":
        out = [
            (f"To {who} — thank you for every bit of it.", "relationship"),
            (f"Hope your birthday is as lovely as you are.", "occasion"),
        ]
        if interests:
            out.insert(1, (f"For all the {interests[0]} years and counting.", "interest:" + interests[0]))
        if memories:
            out.append((f"Still thinking about {memories[0]}.", "memory"))
    elif tone == "short":
        out = [(f"Happy birthday, {who}!", "name"),
               (f"Have a brilliant day.", "occasion")]
    elif tone == "dry":
        out = [(f"Happy birthday. I kept the receipt for the present.", "occasion"),
               (f"Another year older. The warranty has officially expired.", "occasion")]
        if interests:
            out.append((f"In lieu of a gift, enjoy this card about {interests[0]}.", "interest:" + interests[0]))
    else:  # funny
        if interests:
            first = interests[0]
            out = [
                (f"Happy birthday to the person who takes {first} far too seriously.", "interest:" + first),
                (f"Another year older. Still the reigning {first} champion, allegedly.", "interest:" + first),
            ]
        else:
            out = [
                (f"Happy birthday, {who} — officially a legend for the day.", "name"),
                (f"Make a wish. Something realistic this time.", "occasion"),
            ]
        if memories:
            out.append((f"In honour of the time {memories[0]} — never forget.", "memory"))
        out.append((f"Officially a legend. Unofficially, still {who}.", "name"))
    return [{"text": t[:400], "source": s} for t, s in out[:4]]


def validate(owner,b):
    if not isinstance(b,dict):
        raise CardError("Expected a card design object")
    # Brand locks run in the SAVE handler, not the MCP layer — same
    # validators on every path (mcp|rest|ui). Renderer-owned geometry has
    # no inputs by construction: reject attempts to set it.
    for locked_key in ("back", "fonts", "font", "layout", "bleed", "dpi",
                       "panel_order", "panels", "print_area", "safe_zone",
                       "fold", "sku", "supplier"):
        if locked_key in b:
            raise CardError(f"{locked_key} is renderer-owned — no inputs exist")
    tid=b.get("template","portrait")
    if not isinstance(tid,str) or not isinstance(b.get("format","5x7"),str) or tid not in scenes.TEMPLATES or b.get("format","5x7") not in scenes.FORMATS:
        raise CardError("Unknown card template or format")
    tpl=scenes.TEMPLATES[tid]
    items=b.get("photos",[])
    if not isinstance(items,list) or not tpl["min_photos"]<=len(items)<=tpl["max_photos"]:
        raise CardError(f"This template needs {tpl['min_photos']}–{tpl['max_photos']} photos")
    slots=[]
    for p in items:
        if not isinstance(p,dict):
            raise CardError("Invalid photo slot")
        pid=str(p.get("photo_id",""))
        photo(owner,pid)
        box=crop_box(p.get("crop",[0,0,1,1]))
        focus=p.get("focus",[.5,.5])
        if not isinstance(focus,list) or len(focus)!=2:
            raise CardError("focus must be [x,y]")
        focus=list(map(number,focus))
        if not all(0<=v<=1 for v in focus):
            raise CardError("Photo focus must be between 0 and 1")
        cid=str(p.get("cutout", ""))
        if cid:
            co=cutout(owner,cid,pid)
            if json_dump(box)!=co["crop"]:
                raise CardError("Crop changed. Remove the cutout or cut it out again.")
        slots.append({"photo_id":pid,"crop":box,"focus":focus,"cutout":cid})
    spec={"template":tid,"template_version":scenes.VERSION,"format":b.get("format","5x7"),"photos":slots}
    for field,limit,default in [("headline",60,tpl["headline"]),("recipient",60,""),("sender",80,""),("inside_message",500,"")]:
        value=b.get(field,default)
        if not isinstance(value,str) or len(value)>limit:
            raise CardError(f"{field} must be text up to {limit} characters")
        spec[field]=value.strip()
    if "oddhobb" in (spec["headline"] + " " + spec["recipient"]).lower():
        raise CardError("No wordmark on the front — brand lives on the back only")
    if not spec["headline"]:
        raise CardError("Add a headline")
    # front headline font: registry id only (controlled custom, like coats).
    # Birthday product templates lock their fonts — the agent chooses photos
    # + text only; caller values are overridden, never rejected, never honoured.
    hfont = b.get("headline_font", "fraunces")
    if not isinstance(hfont, str) or hfont not in scenes.CARD_FONT_IDS:
        raise CardError(f"headline_font must be one of {list(scenes.CARD_FONT_IDS)}")
    locked = (tpl.get("fonts") or {})
    if isinstance(locked, dict) and locked.get("headline") in scenes.CARD_FONT_IDS:
        hfont = locked["headline"]
    spec["headline_font"] = hfont
    # inside panels: right message + optional left note, each with
    # font/size/colour/align from closed enums. Legacy inside_message feeds
    # right.message so old revisions keep rendering. Locked templates also
    # fix the inside body font.
    spec["inside"] = _validate_inside(b.get("inside"), spec["inside_message"])
    if isinstance(locked, dict) and locked.get("body") in scenes.CARD_FONT_IDS:
        spec["inside"]["right"]["font"] = locked["body"]
    if tid == "birthday_4photo":
        # canonical product caps (docs/cardspec.md §12): tighter than generic
        if len(spec["headline"]) > 40:
            raise CardError("Canonical headline max 40 characters")
        if len(spec["inside"]["right"]["message"]) > 240:
            raise CardError("Canonical inside message max 240 characters")
        if len(spec["sender"]) > 40:
            raise CardError("Canonical signature max 40 characters")
        vibe = b.get("title_vibe", "playful_balloons")
        if not isinstance(vibe, str) or vibe not in scenes.TITLE_VIBES:
            raise CardError(f"title_vibe must be one of {list(scenes.TITLE_VIBES)}")
        spec["title_vibe"] = vibe
        tkey = b.get("title_art_key", "")
        if tkey and (not isinstance(tkey, str) or len(tkey) > 200):
            raise CardError("title_art_key must be a short storage key")
        spec["title_art_key"] = tkey if isinstance(tkey, str) else ""
    if tid == "birthday_fullbleed":
        # fullbleed product: attached art + bounded copy. Same tight caps;
        # front art is mandatory (attach-art first), other faces optional.
        if len(spec["headline"]) > 40:
            raise CardError("Fullbleed headline max 40 characters")
        if len(spec["inside"]["right"]["message"]) > 240:
            raise CardError("Fullbleed inside message max 240 characters")
        if len(spec["sender"]) > 40:
            raise CardError("Fullbleed signature max 40 characters")
        for akey in ("front_art_key", "inside_art_key", "back_art_key"):
            aval = b.get(akey, "")
            if aval and (not isinstance(aval, str) or len(aval) > 200):
                raise CardError(f"{akey} must be a short storage key")
            spec[akey] = aval if isinstance(aval, str) else ""
        if not spec["front_art_key"]:
            raise CardError("Fullbleed needs front art — attach art first (art_required)")
        hb = b.get("headline_baked", True)
        if not isinstance(hb, bool):
            raise CardError("headline_baked must be true or false")
        spec["headline_baked"] = hb
        src = b.get("art_source", "")
        if not isinstance(src, str) or len(src) > 40:
            raise CardError("art_source must be text up to 40 characters")
        spec["art_source"] = src.strip()
        pr = b.get("prompt", "")
        if not isinstance(pr, str) or len(pr) > 2000:
            raise CardError("prompt must be text up to 2000 characters")
        spec["prompt"] = pr
    # Recipe provenance passes through untouched: which published recipe
    # (and version) compiled this revision. Renderer never reads it.
    if isinstance(b.get("recipe_id"), str) and b["recipe_id"][:80]:
        spec["recipe_id"] = b["recipe_id"][:80]
        if isinstance(b.get("recipe_version"), int):
            spec["recipe_version"] = b["recipe_version"]
    return spec


def _validate_panel(panel, *, text_field, text_limit, default_font):
    panel = panel or {}
    if not isinstance(panel, dict):
        raise CardError("Inside panels must be objects")
    allowed = {"mode", text_field, "font", "size", "colour", "align"}
    for k in panel:
        if k not in allowed:
            raise CardError(f"Inside panel has no field {k!r} — allowed: {sorted(allowed)}")
    out = {}
    mode = panel.get("mode", "blank" if text_field != "message" else "message")
    if mode not in ("blank", "message"):
        raise CardError("Inside panel mode must be blank or message")
    out["mode"] = mode
    text = panel.get(text_field, "")
    if not isinstance(text, str) or len(text) > text_limit:
        raise CardError(f"Inside {text_field} must be text up to {text_limit} characters")
    out[text_field] = text.strip()
    font = panel.get("font", default_font)
    if not isinstance(font, str) or font not in scenes.CARD_FONT_IDS:
        raise CardError(f"Inside font must be one of {list(scenes.CARD_FONT_IDS)}")
    out["font"] = font
    size = panel.get("size", "M")
    if size not in scenes.CARD_SIZES:
        raise CardError(f"Inside size must be one of {list(scenes.CARD_SIZES)}")
    out["size"] = size
    colour = panel.get("colour", "ink")
    if colour not in scenes.CARD_COLOURS:
        raise CardError(f"Inside colour must be one of {list(scenes.CARD_COLOURS)}")
    out["colour"] = colour
    align = panel.get("align", "center")
    if align not in scenes.CARD_ALIGN:
        raise CardError(f"Inside align must be one of {list(scenes.CARD_ALIGN)}")
    out["align"] = align
    return out


def _validate_inside(inside, legacy_message):
    inside = inside or {}
    if not isinstance(inside, dict):
        raise CardError("Inside must be an object with left/right panels")
    for k in inside:
        if k not in ("left", "right"):
            raise CardError(f"Inside has no panel {k!r} — panels: left, right")
    right = _validate_panel(inside.get("right"), text_field="message",
                            text_limit=500, default_font="inter")
    if not right["message"]:
        right["message"] = legacy_message
    left = _validate_panel(inside.get("left"), text_field="text",
                           text_limit=160, default_font="inter")
    return {"left": left, "right": right}


def record(owner,did,revision=None):
    with db.connect() as c:
        d=c.execute("SELECT * FROM card_designs WHERE id=? AND owner=?",(did,owner)).fetchone()
        if d is None:
            raise CardError("Card not found",404)
        rev=revision or d["latest"]
        row=c.execute("SELECT * FROM card_revisions WHERE design_id=? AND revision=?",(did,rev)).fetchone()
        if row is None:
            raise CardError("Card revision not found",404)
    return {"id":did,"revision":rev,"latest":d["latest"],"spec":json.loads(row["spec"]),"updated_at":d["updated_at"],"via":d["via"] if "via" in d.keys() else ""}


def key(owner,did,rev,kind):
    names={"preview":"front.png","inside":"inside.png","back":"back.png","export":"print.pdf","motion":"scene.mp4","spread":"spread-front.png",
           "spread-front":"spread-front.png","spread-inside-left":"spread-inside-left.png",
           "spread-inside-right":"spread-inside-right.png","spread-back":"spread-back.png"}
    with db.connect() as c:
        row=c.execute("SELECT storage_owner FROM card_designs WHERE id=?",(did,)).fetchone()
    if row is None:
        raise CardError("Card not found",404)
    return f"owners/{storage._slug(row[0])}/cards/{did}/r{rev}/{names[kind]}"


SPREAD_PARTS=("front","inside_left","inside_right","back")


def cached(k):
    # Hash the complete key so no owner slug collision can cross local paths.
    p=config.DATA/"cards"/"cache"/(hashlib.sha256(k.encode()).hexdigest()+"."+k.rsplit(".",1)[-1])
    p.parent.mkdir(parents=True,exist_ok=True)
    return p


def local_asset(k):
    p=cached(k)
    if not p.exists():
        storage.get(k,p)
    return p


def assets(owner,spec):
    result={}
    for slot in spec["photos"]:
        p=photo(owner,slot["photo_id"])
        k=cutout(owner,slot["cutout"],slot["photo_id"])["asset_key"] if slot["cutout"] else p["r2_key"]
        with Image.open(local_asset(k)) as im:
            result[slot["photo_id"]]=im.convert("RGBA")
    # fullbleed attached art rides alongside photo assets under reserved keys
    for skey, rkey in (("front_art_key","__front_art__"),("inside_art_key","__inside_art__"),
                       ("back_art_key","__back_art__")):
        if spec.get(skey):
            with Image.open(local_asset(spec[skey])) as im:
                result[rkey]=im.convert("RGBA")
    return result


def render_job(jid):
    with db.connect() as c:
        row=dict(c.execute("SELECT * FROM card_jobs WHERE id=?",(jid,)).fetchone())
        c.execute("UPDATE card_jobs SET status='running' WHERE id=?",(jid,));c.commit()
    temp = None
    try:
        owner,did,rev,kind=[row[k] for k in ("owner","design_id","revision","kind")]
        spec=record(owner,did,rev)["spec"]
        aa=assets(owner,spec)
        dest=cached(key(owner,did,rev,kind))
        # Never expose a partial render, and never overwrite approved revisions.
        temp=dest.with_name(dest.stem+"-"+jid+dest.suffix)
        if kind=="preview":
            scenes.front(spec,aa).save(temp,"PNG")
            inside_path=cached(key(owner,did,rev,"inside"))
            # double width so each inside half reads at full size
            scenes.inside(spec,width=1440,assets=aa).save(inside_path,"PNG")
            storage.put(inside_path,key(owner,did,rev,"inside"))
            back_path=cached(key(owner,did,rev,"back"))
            scenes.back(spec,assets=aa).save(back_path,"PNG")
            storage.put(back_path,key(owner,did,rev,"back"))
        elif kind=="spread":
            # Four agent-showable faces: front, inside halves, back.
            parts={"front":scenes.front(spec,aa),
                   "inside_left":scenes.inside_half(spec,"left",assets=aa),
                   "inside_right":scenes.inside_half(spec,"right",assets=aa),
                   "back":scenes.back(spec,assets=aa)}
            for part,img in parts.items():
                pk=key(owner,did,rev,"spread-"+part.replace("_","-"))
                dest=cached(pk)
                tmp=dest.with_name(dest.stem+"-"+jid+dest.suffix)
                img.convert("RGB").save(tmp,"PNG")
                storage.put(tmp,pk)
                tmp.replace(dest)
                tmp.unlink(missing_ok=True)
            temp=None
        elif kind=="export":
            scenes.print_pdf(spec,aa,temp)
        elif kind=="motion":
            scenes.motion(spec,aa,temp)
        else:
            # spread saved its four faces above; nothing single to publish
            temp=None
        if temp is not None:
            storage.put(temp,key(owner,did,rev,kind))
            temp.replace(dest)
        with db.connect() as c:
            c.execute("UPDATE card_jobs SET status='ready',error='' WHERE id=?",(jid,));c.commit()
    except Exception as e:
        with db.connect() as c:
            c.execute("UPDATE card_jobs SET status='failed',error=? WHERE id=?",(str(e)[:250],jid));c.commit()
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
        _slots.release()


def face_box(owner, pid):
    """Detected face boxes for a photo (mediapipe provenance)."""
    with db.connect() as c:
        try:
            rows = c.execute("SELECT box FROM photo_faces WHERE photo_id=?",
                             (pid,)).fetchall()
            dims = c.execute("SELECT width, height FROM photos WHERE id=?",
                             (pid,)).fetchone()
        except Exception:
            return []
    w = float(dict(dims).get("width") or 0) if dims else 0
    h = float(dict(dims).get("height") or 0) if dims else 0
    boxes = []
    for r in rows:
        try:
            import json as _j
            b = _j.loads(r["box"]) if isinstance(r["box"], str) else list(r["box"])
            if len(b) == 4:
                b = [float(v) for v in b]
                # belt-and-braces: table contract is normalized, but pixel
                # rows have existed — normalize against photo dims
                if max(abs(v) for v in b) > 1.001 and w > 0 and h > 0:
                    b = [b[0] / w, b[1] / h, b[2] / w, b[3] / h]
                boxes.append(b)
        except (ValueError, TypeError):
            continue
    return boxes


def crop_keeps_face(crop, faces) -> bool:
    """True if the crop keeps at least half of any detected face's area."""
    cx, cy, cw, ch = crop
    for fx, fy, fw, fh in faces:
        ix0, iy0 = max(cx, fx), max(cy, fy)
        ix1, iy1 = min(cx + cw, fx + fw), min(cy + ch, fy + fh)
        inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
        if fw * fh > 0 and inter / (fw * fh) >= 0.5:
            return True
    return False


def _compiler_shelf(owner, photos, who, occasion="birthday"):
    """Shelf via matcher+compiler (same engine as oddhobb_make).

    Canonical P0 path: subject → brief → match published recipes →
    compile up to 6 finished buyable revisions. The shelf never invents
    headlines, never hand-builds templates, never picks photos itself —
    the compiler owns all of that. Returns [(did, rev, headline,
    recipient, template, photos_used)]. Empty when nothing resolvable.
    """
    from backend import subjects as _subjects
    from backend.recipes import compiler as _comp
    from backend.recipes import matcher as _match
    from backend.recipes import registry as _reg
    subject = {}
    with db.connect() as c:
        for p in photos:
            try:
                hit = _subjects.profile_for_photo(c, owner, p["id"])
            except Exception:
                continue
            sub = (hit or {}).get("subject") or {}
            if sub.get("id"):
                prof = (hit.get("profile") or {})
                inner = prof.get("profile", {}) if isinstance(
                    prof.get("profile"), dict) else {}
                subject = {"id": sub["id"], "name": sub.get("name", ""),
                           "relationship": prof.get("relationship", ""),
                           "interests": inner.get("interests", []),
                           "memories": inner.get("memories", [])}
                break
    if not subject.get("id"):
        return []
    try:
        pool = _comp._photo_pool(owner, subject["id"])
    except Exception:
        return []
    if not pool:
        return []
    try:
        reg = _reg.published()
    except Exception:
        return []
    brief = _comp.build_brief(subject=subject, occasion=occasion, vibe="",
                              photo_count=len(pool))
    matches = []
    for m in _match.match(brief, reg, limit=12):
        r = reg.get(m["id"])
        if r and not _match.eligible(r, brief):
            matches.append((m, r))
        if len(matches) >= 6:
            break
    if not matches:
        return []
    rknown = {}
    with db.connect() as c:
        for r in c.execute("SELECT id,latest FROM card_designs WHERE owner=?",
                           (owner,)).fetchall():
            try:
                rec = record(owner, r["id"], r["latest"])
                sp = rec["spec"]
                rknown[(sp.get("recipe_id"), sp.get("recipe_version"),
                        tuple(s["photo_id"] for s in sp.get("photos", [])))] = \
                    (r["id"], r["latest"])
            except CardError:
                pass
    tones = ["funny", "warm", "dry", "playful"]
    out = []
    for i, (m, rec) in enumerate(matches):
        need = int(((rec.get("inputs") or {}).get("photos") or {}).get("count", 1))
        use_ids = pool[:need]
        key = (m["id"], rec.get("version", 1), tuple(use_ids))
        if key in rknown:
            did, rev = rknown[key]
        else:
            try:
                res = _comp.compile(owner, m["id"], subject=subject,
                                    occasion=occasion,
                                    tone=tones[i % len(tones)], variation=0,
                                    title_art=False, via="ui")
            except Exception:
                continue
            if not res.get("ok"):
                continue
            did, rev = res["design"]["id"], res["design"]["revision"]
            rknown[key] = (did, rev)
        try:
            spec = record(owner, did, rev)["spec"]
        except CardError:
            continue
        by_id = {p["id"]: p for p in photos}
        uphotos = [by_id[pid] for pid in use_ids if pid in by_id]
        out.append((did, rev, spec.get("headline", ""),
                    spec.get("recipient", ""),
                    spec.get("template", "birthday_4photo"),
                    uphotos or photos[:len(use_ids)]))
    return out


def solo_first(owner, pids: list) -> list:
    """Prefer solo portraits for single-recipient cards: exactly 1 detected
    face first, undetected next (stable order kept), group shots last."""
    counts: dict = {}
    with db.connect() as c:
        for pid in pids:
            try:
                row = c.execute("SELECT COUNT(*) n FROM photo_faces WHERE photo_id=?",
                                (pid,)).fetchone()
                counts[pid] = int(dict(row)["n"]) if row else -1
            except Exception:
                counts[pid] = -1
    return sorted(pids, key=lambda p: (0 if counts.get(p) == 1 else
                                       (2 if (counts.get(p, -1) or 0) > 1 else 1)))


def gate(owner, did, rev) -> dict:
    """Reviewer gate before any render: frozen spec re-validated (photos may
    have been deleted since save), every slot keeps a detected face where
    faces exist. Raises CardError — renders never return ok:true on empties."""
    spec = record(owner, did, rev)["spec"]
    validate(owner, spec)  # photos still exist and belong to caller
    for slot in spec["photos"]:
        faces = face_box(owner, slot["photo_id"])
        if faces and not crop_keeps_face(slot["crop"], faces):
            raise CardError("Crop cuts out every detected face — widen the crop or pick another photo", 422)
    return spec


def enqueue(owner,did,rev,kind):
    if not isinstance(kind,str) or kind not in ("preview","export","motion","spread"):
        raise CardError("Unknown render kind")
    with ownership_lock,db.connect() as c:
        gate(owner,did,rev)
        old=c.execute("SELECT * FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind=? AND status IN ('queued','running','ready') ORDER BY created_at DESC LIMIT 1",(owner,did,rev,kind)).fetchone()
        if old:
            return dict(old)
        if not _slots.acquire(blocking=False):
            raise CardError("Render queue is busy. Try again shortly.",429)
        jid="crj_"+uuid.uuid4().hex
        try:
            c.execute("INSERT INTO card_jobs(id,owner,design_id,revision,kind,status,created_at) VALUES (?,?,?,?,?,'queued',?)",(jid,owner,did,rev,kind,time.time()));c.commit()
            _pool.submit(render_job,jid)
        except Exception:
            _slots.release();raise
        return dict(c.execute("SELECT * FROM card_jobs WHERE id=?",(jid,)).fetchone())


def job_payload(row):
    base={"id":row["id"],"design_id":row["design_id"],"revision":row["revision"],"kind":row["kind"],"status":row["status"],"error":row["error"],"url":f"/api/cards/{row['design_id']}/r{row['revision']}/{row['kind']}" if row["status"]=="ready" and row["kind"]!="spread" else ""}
    if row["kind"]=="spread":
        surf = f"/api/cards/{row['design_id']}/r{row['revision']}"
        urls = {p: f"{surf}/spread/{p}" for p in SPREAD_PARTS} if row["status"]=="ready" else {}
        if row["status"]=="ready":
            urls["listing"]=f"{surf}/listing"
            urls["triptych"]=f"{surf}/triptych"
            # the full inside spread as one surface (needs preview ready;
            # 409s until then, same as any ungated face URL)
            urls["inside"]=f"{surf}/inside"
        base["urls"]=urls
    return base


def _permit(perm: str):
    """Grant gate for delegated agent keys. No key → existing behaviour
    unchanged (anon flows keep working). User keys → full rights. Agent
    keys → need the grant; revoked/unknown → denied. Returns None when
    allowed, else a (json, code) denial."""
    key = request.headers.get("X-API-Key", "").strip() or \
        request.args.get("api_key", "").strip()
    if not key:
        return None
    with db.connect() as c:
        if db.get_user_by_api_key(c, key):
            return None
        a = db.get_agent_by_key(c, key)
        if a and a["status"] == "active" and perm in db.agent_perms(a):
            return None
    return jsonify(ok=False, error=f"this agent key lacks the {perm} grant"), 403


def register(app,owner_denied):
    bp=Blueprint("cards",__name__)

    @bp.before_request
    def auth():
        b=request.get_json(silent=True) or {}
        if not isinstance(b,dict):
            raise CardError("Expected a JSON object")
        owner=str(request.args.get("owner") or b.get("owner") or "anon").strip()[:80]
        request.card_owner=owner
        denied = owner_denied(owner)
        if denied is not None:
            return denied
        # GETs read, POSTs create, order/checkout spend. Keyless callers keep
        # existing behaviour; keyed agents need the matching grant.
        if request.method == "POST":
            perm = "cards:order" if request.path.endswith(("/order", "/checkout")) else "cards:create"
        else:
            perm = "cards:read"
        return _permit(perm)

    @bp.errorhandler(CardError)
    def card_error(e):
        return jsonify(ok=False,error=str(e)),e.code

    @bp.errorhandler(storage.StorageError)
    def storage_error(e):
        return jsonify(ok=False,error="Photo storage unavailable. Try again shortly."),502

    @bp.get("/api/cards/templates")
    def templates():
        return jsonify(ok=True,version=scenes.VERSION,templates=[{"id":k,**v} for k,v in scenes.TEMPLATES.items()],formats=scenes.FORMATS,motion_available=__import__('shutil').which("ffmpeg") is not None,
                      product={**card_price(),
                               "buy_hint": "POST /backend/api/cards/<id>/checkout returns checkout_url — done means a product_url the human can buy from; a preview alone is not done."},
                      mcp_status=mcp_status(),
                      mcp_hint="If degraded, prefer waiting — REST works but is off the main road.")

    @bp.get("/api/cards/fonts")
    def fonts():
        """Curated font registry for agents: pick by vibe + occasion, keep
        the slot's use_for role. Fall back to frances headlines + inter body."""
        return jsonify(ok=True, fonts=scenes.CARD_FONTS,
                       sizes=scenes.CARD_SIZES, colours=scenes.CARD_COLOURS,
                       aligns=scenes.CARD_ALIGN,
                       how="Match brief tone+occasion to vibes/occasions; "
                           "headlines use use_for=headline, inside body uses body.",
                       mcp_status=mcp_status())

    @bp.get("/api/cards/photos")
    def photos():
        owner=request.card_owner
        with db.connect() as c:
            rows=c.execute("SELECT id,orig_name,width,height,person FROM photos WHERE owner=? ORDER BY created_at DESC LIMIT 200",(owner,)).fetchall()
        # anon is the shared demo shelf (seeded Dolphin + sample-dog/Nibble) —
        # strictly owner-scoped, never another live owner's photos. Named
        # owners see only their own uploads.
        demo = (owner == "anon")
        return jsonify(ok=True,demo=demo,
                       demo_note="Shared demo shelf — sign in (POST /backend/api/session) for your own photos." if demo else "",
                       photos=[{**dict(p),"url":f"/api/cards/photos/{p['id']}/image"} for p in rows])

    @bp.get("/api/cards/photos/<pid>/image")
    def image(pid):
        p=photo(request.card_owner,pid)
        res=send_file(local_asset(p["r2_key"]),mimetype=p["mime"],max_age=0)
        res.headers["Cache-Control"]="private, no-store"
        return res

    @bp.post("/api/cards/cutouts")
    def make_cutout():
        # Explicitly crop Dad out of a group before asking foreground segmentation.
        # This is a cutout tool, not an automatic person-recognition claim.
        from dataclasses import replace
        import premesh
        b=request.get_json() or {};owner=request.card_owner
        pid=str(b.get("photo_id", ""));box=crop_box(b.get("crop",[0,0,1,1]))
        p=photo(owner,pid)
        fingerprint=hashlib.sha256((owner+pid+json_dump(box)).encode()).hexdigest()
        cid="cut_"+fingerprint[:32]
        with db.connect() as c:
            old=c.execute("SELECT * FROM card_cutouts WHERE id=? AND owner=?",(cid,owner)).fetchone()
        if old:
            return jsonify(ok=True,cutout_id=cid,url=f"/api/cards/cutouts/{cid}/image")
        with Image.open(local_asset(p["r2_key"])) as im:
            im=scenes.cropped(im,box)
            if min(im.size)<256:
                raise CardError("Choose a larger subject area or a higher-resolution photo")
            buf=io.BytesIO();im.convert("RGB").save(buf,"PNG")
        # Disable generative upscaling: preserve real likeness and avoid new spend.
        recipe=replace(premesh.RECIPES["card"],prelude=(),prelude_below=0)
        try:
            out=premesh.normalize(buf.getvalue(),recipe,zone=config.brand_for(request.host)["host"],timeout=45,retries=0)
        except premesh.TransformError:
            raise CardError("Background removal is unavailable. Your original photo is safe; retry or use it as a photo.",502) from None
        if not out.ok:
            raise CardError("Cutout did not pass quality checks. Tighten the subject crop or use another photo.",422)
        with ownership_lock:
            photo(owner,pid)  # Reject a cutout whose source was claimed while segmentation ran.
            k=f"owners/{storage._slug(owner)}/cards/cutouts/{cid}.png"
            dest=cached(k);dest.write_bytes(out.data);storage.put(dest,k)
            with db.connect() as c:
                c.execute("INSERT OR IGNORE INTO card_cutouts VALUES (?,?,?,?,?,?)",(cid,owner,pid,json_dump(box),k,time.time()));c.commit()
        return jsonify(ok=True,cutout_id=cid,url=f"/api/cards/cutouts/{cid}/image")

    @bp.get("/api/cards/cutouts/<cid>/image")
    def cutout_image(cid):
        with db.connect() as c:
            row=c.execute("SELECT * FROM card_cutouts WHERE id=? AND owner=?",(cid,request.card_owner)).fetchone()
        if not row:
            raise CardError("Cutout not found",404)
        res=send_file(local_asset(row["asset_key"]),mimetype="image/png",max_age=0)
        res.headers["Cache-Control"]="private, no-store";return res

    @bp.route("/api/cards/designs",methods=["GET","POST"])
    def designs():
        owner=request.card_owner
        if request.method=="GET":
            with db.connect() as c:
                rows=c.execute("SELECT id,latest FROM card_designs WHERE owner=? ORDER BY updated_at DESC LIMIT 100",(owner,)).fetchall()
            return jsonify(ok=True,designs=[record(owner,r["id"],r["latest"]) for r in rows],
                           mcp_status=mcp_status(),
                           mcp_hint="If degraded, prefer waiting — REST works but is off the main road.")
        b=request.get_json() or {}
        did=str(b.get("id") or "card_"+uuid.uuid4().hex)
        # Source stamp is transport-derived, not caller-claimed: X-MCP only
        # arrives with the service token on direct MCP→Flask calls (the
        # bridge strips it, so REST/browser cannot spoof via=mcp).
        if request.headers.get("X-MCP", "") == "1":
            via = "mcp"
        else:
            via=str(b.get("via") or "").strip().lower()[:10]
            if via not in ("ui", "rest"):
                via = "rest"
        with db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            spec=validate(owner,b.get("spec",{}))
            old=c.execute("SELECT * FROM card_designs WHERE id=?",(did,)).fetchone()
            if old:
                if old["owner"]!=owner:
                    raise CardError("Card not found",404)
                if b.get("expected_revision")!=old["latest"]:
                    raise CardError("This card changed elsewhere. Reload before saving.",409)
                prev=c.execute("SELECT spec FROM card_revisions WHERE design_id=? AND revision=?",(did,old["latest"])).fetchone()
                if prev["spec"]==json_dump(spec):
                    rev=old["latest"]
                else:
                    rev=old["latest"]+1
                    c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",(did,rev,json_dump(spec),time.time()))
                    c.execute("UPDATE card_designs SET latest=?,updated_at=?,via=? WHERE id=?",(rev,time.time(),via,did))
            else:
                if b.get("id"):
                    raise CardError("Card not found",404)
                rev=1;t=time.time()
                c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via) VALUES (?,?,?,?,?,?,?)",(did,owner,rev,t,t,owner,via))
                c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",(did,rev,json_dump(spec),t))
            c.commit()
        warnings=[]
        locked = (scenes.TEMPLATES.get(spec["template"], {}).get("fonts") or {})
        if isinstance(locked, dict) and locked:
            warnings.append(f"Fonts are template-locked ({locked.get('headline')}/{locked.get('body')}) — you choose photos + text only.")
        count=len(spec["photos"])
        cols=1 if count<=1 else 2
        rows=max(1,math.ceil(count/cols))
        mm=scenes.FORMATS[spec["format"]]["mm"]
        for slot in spec["photos"]:
            p=photo(owner,slot["photo_id"])
            cw,ch=slot["crop"][2:]
            dpi=round(min(p["width"]*cw/(mm[0]*.84/cols/25.4),p["height"]*ch/(mm[1]*.49/rows/25.4)))
            if dpi<200:
                warnings.append(f"Photo {p['orig_name']} is approximately {dpi} dpi in this layout; it may print soft. Use a larger photo or a wider crop.")
        return jsonify(ok=True,design=record(owner,did,rev),warnings=warnings,
                       mcp_status=mcp_status(),
                       mcp_hint="If degraded, prefer waiting — REST works but is off the main road.",
                       card_url=card_url_for(did, rev),
                       proof_url=proof_url_for(did),
                       product={**card_price(),
                                "buy_hint": "Done means a product_url the human can buy from. "
                                            "POST /backend/api/cards/<id>/checkout returns checkout_url; a preview alone is not done."})

    @bp.post("/api/cards/attach-art")
    def attach_art_route():
        """Pin third-party/generated art to a NEW fullbleed revision (creates
        the design when design_id is empty). Auto-enqueues preview + spread so
        views land without a second call."""
        owner = request.card_owner
        b = request.get_json() or {}
        urls = {f: b.get(f"{f}_art_url") or "" for f in ("front", "inside", "back")}
        if not urls["front"]:
            raise CardError("front_art_url is required", 400)
        blobs: dict = {}
        warnings: list[str] = []
        for face, url in urls.items():
            if not url:
                continue
            img, _w = validate_art_image(fetch_art_bytes(url), face)
            blobs[face] = img
        found, detail, warn = face_presence(blobs["front"])
        if not found and not warn:
            raise CardError(f"Front art shows no face ({detail}) — use a portrait composition", 400)
        if warn:
            warnings.append(warn)
        rec, attach_warnings, jobs = attach_art(
            owner, str(b.get("design_id") or ""),
            blobs,
            copy={k: b.get(k, "") for k in ("headline", "recipient", "sender", "inside_message")},
            headline_baked=b.get("headline_baked", True),
            art_source=str(b.get("art_source") or ""),
            prompt=str(b.get("prompt") or ""))
        warnings += attach_warnings
        return jsonify(ok=True, design=rec, warnings=warnings,
                       jobs=[{k: j[k] for k in ("id", "kind", "status")} for j in jobs],
                       card_url=card_url_for(rec["id"], rec["revision"]),
                       proof_url=proof_url_for(rec["id"]),
                       product=card_price(), mcp_status=mcp_status())

    @bp.get("/api/cards/gallery")
    def gallery():
        """Finished buyable cards for the active person — no forms.

        Canonical P0 shelf: ?subject_id= scopes to that person's confirmed
        photos, ?occasion=birthday|christmas|general filters recipes,
        ?photo_ids= uses an explicit user/AI selection. Unscoped = latest
        photos. Every item is an immutable revision with FRONT/INSIDE/BACK
        views and £2.99 fixed price. Designs are created once and reused;
        previews render lazily (bounded per call).
        """
        owner = request.card_owner
        subject_id = (request.args.get("subject_id") or "").strip()[:80]
        occasion = (request.args.get("occasion") or "birthday").strip().lower()[:16]
        if occasion not in ("birthday", "christmas", "general"):
            occasion = "birthday"
        want_pids = [p.strip()[:80] for p in
                     (request.args.get("photo_ids") or "").split(",") if p.strip()][:8]
        scope: dict = {"subject_id": subject_id, "occasion": occasion, "photo_ids": []}
        with db.connect() as c:
            if want_pids:
                # explicit selection (user-picked or AI-picked): keep owned, keep order
                rows = c.execute(
                    "SELECT id FROM photos WHERE owner=?", (owner,)).fetchall()
                owned = {r["id"] for r in rows}
                pids = [p for p in want_pids if p in owned]
                photos = []
                for pid in pids:
                    r = c.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()
                    if r:
                        photos.append(dict(r))
                scope["photo_ids"] = [p["id"] for p in photos]
            elif subject_id:
                # active person: confirmed tags only, newest first
                s = c.execute("SELECT * FROM studio_subjects WHERE id=?", (subject_id,)).fetchone()
                if s is None or dict(s).get("owner") != owner:
                    raise CardError("Unknown person — pick them in Studio first", 404)
                photos = [dict(r) for r in c.execute(
                    "SELECT p.* FROM photos p JOIN photo_subjects ps ON ps.photo_id=p.id"
                    " WHERE p.owner=? AND ps.subject_id=? AND ps.confirmed=1"
                    " ORDER BY p.created_at DESC LIMIT 6", (owner, subject_id)).fetchall()]
                scope["subject_id"] = subject_id
                scope["photo_ids"] = [p["id"] for p in photos]
            else:
                photos = [dict(r) for r in c.execute(
                    "SELECT * FROM photos WHERE owner=? ORDER BY created_at DESC LIMIT 3",
                    (owner,)).fetchall()]
        if photos:
            # solos lead: group shots still qualify, but a Dad card should
            # open on Dad, not the crowd he was standing in
            order = solo_first(owner, [p["id"] for p in photos])
            photos.sort(key=lambda p: order.index(p["id"]))
        if not photos:
            return jsonify(ok=True, items=[], empty=True, scope=scope)
        with db.connect() as c:
            known = {}
            for r in c.execute("SELECT id,latest FROM card_designs WHERE owner=?", (owner,)).fetchall():
                try:
                    rec = record(owner, r["id"], r["latest"])
                    sp = rec["spec"]
                    key = (sp.get("template"), tuple(s["photo_id"] for s in sp.get("photos", [])))
                    known[key] = (r["id"], r["latest"])
                except CardError:
                    pass
        # recipient per photo: confirmed photo_subjects → studio_subject →
        # subject_profile (cardgen §1). A person needs no mesh for cards.
        # Legacy mesh-keyed profiles remain as fallback for unmigrated rows.
        who = {}
        with db.connect() as c:
            from backend import subjects as _sub
            for p in photos:
                hit = _sub.profile_for_photo(c, owner, p["id"])
                if hit and (hit.get("subject") or {}).get("name"):
                    who[p["id"]] = hit["subject"]["name"]
                    continue
                m = c.execute("SELECT id FROM meshes WHERE photo_id=? ORDER BY created_at DESC LIMIT 1",
                              (p["id"],)).fetchone()
                if m:
                    prof = db.get_subject_profile(c, owner, m["id"])
                    if prof.get("name"):
                        who[p["id"]] = prof["name"]

        items, enqueued = [], 0
        # Canonical shelf ONLY: subject → brief → match → compile. The
        # compiler owns headlines, photo choice and composition. No
        # hand-built fallback — assets determine which finished recipes
        # appear, never a photo-count gate, never an occasion mismatch.
        shelf = _compiler_shelf(owner, photos, who, occasion=occasion)
        need_photos = 0
        for (did, rev, headline, name, tid, use) in shelf:
            with db.connect() as c:
                job = c.execute("SELECT * FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='preview' AND status IN ('queued','running','ready') ORDER BY created_at DESC LIMIT 1",
                                (owner, did, rev)).fetchone()
            url, status = "", "missing"
            if job:
                status = job["status"]
                if status == "ready":
                    url = f"/api/cards/{did}/r{rev}/preview"
            elif enqueued < 6:
                try:
                    enqueue(owner, did, rev, "preview")
                    enqueued += 1
                    status = "queued"
                except CardError:
                    pass
            items.append({
                "design_id": did, "revision": rev, "template": tid,
                "template_label": scenes.TEMPLATES.get(tid, {}).get("label", tid),
                "headline": headline,
                "recipient": name, "format": "5x7",
                "price_cents": public_price()["price_cents"],
                "price": public_price()["price"],
                "price_grade": "FIXED",
                "card_url": card_url_for(did, rev),
                "proof_url": proof_url_for(did),
                "photo": {"id": use[0]["id"], "orig_name": use[0].get("orig_name") or "Photo",
                          "url": f"/api/cards/photos/{use[0]['id']}/image"},
                "photos": [{"id": p["id"], "url": f"/api/cards/photos/{p['id']}/image"}
                           for p in use],
                "preview_url": url, "preview_status": status,
                "views": {
                    "front": f"/api/cards/{did}/r{rev}/preview",
                    "inside": f"/api/cards/{did}/r{rev}/inside",
                    "back": f"/api/cards/{did}/r{rev}/back",
                    "triptych": f"/api/cards/{did}/r{rev}/triptych",
                },
            })
        return jsonify(ok=True, items=items, need_photos=need_photos, product=public_price(),
                       scope=scope,
                       mcp_status=mcp_status(),
                       buy_hint="Done means a product_url the human can buy from — "
                                "POST /backend/api/cards/<id>/checkout for checkout_url. Preview alone is not done.")

    @bp.post("/api/cards/<did>/reroll")
    def reroll(did):
        """Same template, different images: rotate the photo set to the next
        disjoint (or least-overlapping) confirmed photos. Fullbleed has no
        photo slots — attach new art instead. Returns the new design pointers;
        the gallery picks it up on refresh."""
        import time as _time
        import uuid as _uuid
        owner = request.card_owner
        b = request.get_json() or {}
        subject_id = str(b.get("subject_id") or "").strip()[:80]
        rec = record(owner, did)
        spec = rec["spec"]
        tid = spec.get("template", "")
        tpl = scenes.TEMPLATES.get(tid, {})
        cur = [s["photo_id"] for s in spec.get("photos", [])]
        if not cur:
            raise CardError("This card has no photo slots — attach new art instead", 400)
        with db.connect() as c:
            if subject_id:
                s = c.execute("SELECT * FROM studio_subjects WHERE id=?", (subject_id,)).fetchone()
                if s is None or dict(s).get("owner") != owner:
                    raise CardError("Unknown person — pick them in Studio first", 404)
                pool = [r["id"] for r in c.execute(
                    "SELECT p.id FROM photos p JOIN photo_subjects ps ON ps.photo_id=p.id"
                    " WHERE p.owner=? AND ps.subject_id=? AND ps.confirmed=1"
                    " ORDER BY p.created_at DESC", (owner, subject_id)).fetchall()]
            else:
                pool = [r["id"] for r in c.execute(
                    "SELECT id FROM photos WHERE owner=? ORDER BY created_at DESC",
                    (owner,)).fetchall()]
        fresh = [p for p in pool if p not in cur]
        need = len(cur)
        if len(fresh) < need:
            # allow minimal overlap rather than refuse, but say so
            fresh += [p for p in pool if p not in fresh]
        if len(fresh) < need:
            raise CardError("Not enough other photos — upload more or select them", 400)
        new_pids = fresh[:need]
        new_spec = dict(spec)
        new_spec["photos"] = [{"photo_id": pid, "crop": [0, 0, 1, 1],
                               "focus": [0.5, 0.5], "cutout": ""} for pid in new_pids]
        if request.headers.get("X-MCP", "") == "1":
            via = "mcp"
        else:
            via = "ui"
        spec = validate(owner, new_spec)
        ndid = "card_" + _uuid.uuid4().hex
        t = _time.time()
        with db.connect() as c:
            c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via) VALUES (?,?,?,?,?,?,?)",
                      (ndid, owner, 1, t, t, owner, via))
            c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                      (ndid, 1, json_dump(spec), t))
            c.commit()
        try:
            job = job_payload(enqueue(owner, ndid, 1, "preview"))
        except CardError:
            job = {"status": "not_rendered"}
        return jsonify(ok=True, design=record(owner, ndid, 1),
                       rotated={"from": cur, "to": new_pids},
                       preview_status=job.get("status", ""),
                       card_url=card_url_for(ndid, 1),
                       proof_url=proof_url_for(ndid),
                       product=card_price(), mcp_status=mcp_status())

    @bp.get("/api/cards/shelf")
    def shelf():
        """Your finished cards as assets: every saved design with its order
        state and the exact images that went into it (photo ids + urls +
        year). The personal-style baseline the future for-you reads from."""
        import datetime as _dt
        owner = request.card_owner
        items = []
        with db.connect() as c:
            designs = [dict(r) for r in c.execute(
                "SELECT * FROM card_designs WHERE owner=? ORDER BY updated_at DESC LIMIT 100",
                (owner,)).fetchall()]
            orders = {}
            for o in c.execute("SELECT * FROM card_orders WHERE owner=?", (owner,)).fetchall():
                orders.setdefault(o["design_id"], []).append(dict(o))
        for d in designs:
            try:
                rec = record(owner, d["id"], d["latest"])
            except CardError:
                continue
            sp = rec["spec"]
            pids = [s["photo_id"] for s in sp.get("photos", [])]
            year = _dt.date.fromtimestamp(d["created_at"]).year
            olist = orders.get(d["id"], [])
            o = olist[-1] if olist else None
            items.append({
                "design_id": d["id"], "revision": rec["revision"],
                "template": sp.get("template", ""), "headline": sp.get("headline", ""),
                "recipient": sp.get("recipient", ""), "year": year,
                "via": d.get("via", ""),
                "photo_ids": pids,
                "photos": [{"id": pid,
                            "url": f"/api/cards/photos/{pid}/image"} for pid in pids],
                "order": ({"id": o["id"], "status": o["status"],
                           "price_cents": o["price_cents"],
                           "checkout_url": o.get("checkout_url", "")} if o else None),
                "card_url": card_url_for(d["id"], rec["revision"]),
                "proof_url": proof_url_for(d["id"]),
            })
        return jsonify(ok=True, items=items, count=len(items),
                       product=card_price(), mcp_status=mcp_status())

    @bp.get("/api/cards/designs/<did>")
    def get_design(did):
        rec = record(request.card_owner,did)
        return jsonify(ok=True,design=rec, card_url=card_url_for(did, rec["revision"]),
                       proof_url=proof_url_for(did),
                       product=card_price(), mcp_status=mcp_status())

    @bp.get("/api/cards/<did>/scene")
    def scene(did):
        owner=request.card_owner
        revision=request.args.get("revision")
        if revision is not None:
            try:
                revision=int(revision)
            except ValueError:
                raise CardError("Choose a saved revision") from None
            if revision<1:
                raise CardError("Choose a saved revision")
        design=record(owner,did,revision)
        rev=design["revision"]
        with db.connect() as c:
            rows=c.execute("SELECT * FROM card_jobs WHERE owner=? AND design_id=? AND revision=? ORDER BY created_at",(owner,did,rev)).fetchall()
        outputs={kind:{"status":"not_rendered","url":""} for kind in ("preview","export","motion")}
        outputs["spread"]={"status":"not_rendered","urls":{}}
        for row in rows:
            outputs[row["kind"]]=job_payload(row)
        return jsonify(ok=True,scene={
            "version":"oddhobb.scene.v1", "id":did, "revision":rev,
            "renderer":"photo_composition", "spec":design["spec"],
            "outputs":outputs,
            "character":None, "performance":None,
            "capabilities":{"card":True,"video":__import__('shutil').which("ffmpeg") is not None,
                            "character_animation":False,"ar":False},
            "poster":{"kind":"preview","url":outputs["preview"]["url"]},
        }, card_url=card_url_for(did, rev),
                       proof_url=proof_url_for(did), product=card_price(),
            mcp_status=mcp_status(),
            buy_hint="Done means a product_url the human can buy from — checkout, not preview.")

    @bp.post("/api/cards/<did>/render")
    def render(did):
        b=request.get_json() or {}
        rev=b.get("revision")
        if not isinstance(rev,int) or isinstance(rev,bool) or rev<1:
            raise CardError("Choose a saved revision")
        return jsonify(ok=True,job=job_payload(enqueue(request.card_owner,did,rev,b.get("kind","preview"))))

    @bp.get("/api/cards/jobs/<jid>")
    def job(jid):
        with db.connect() as c:
            row=c.execute("SELECT * FROM card_jobs WHERE id=? AND owner=?",(jid,request.card_owner)).fetchone()
        if not row:
            raise CardError("Render not found",404)
        return jsonify(ok=True,job=job_payload(row))

    @bp.get("/api/cards/<did>/r<int:rev>/<kind>")
    def artwork(did,rev,kind):
        owner=request.card_owner;record(owner,did,rev)
        if kind=="back":
            # brand back as its own surface: preview render saves it, older
            # revisions fall back to the spread face
            with db.connect() as c:
                ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='preview' AND status='ready'",(owner,did,rev)).fetchone()
                spread=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='spread' AND status='ready'",(owner,did,rev)).fetchone()
            if ready:
                try:
                    p=local_asset(key(owner,did,rev,"back"))
                except Exception:
                    if not spread:
                        raise CardError("Back is not ready — render kind preview first",409)
                    p=local_asset(key(owner,did,rev,"spread-back"))
            elif spread:
                p=local_asset(key(owner,did,rev,"spread-back"))
            else:
                raise CardError("Back is not ready — render kind preview first",409)
            res=send_file(p,mimetype="image/png",max_age=0)
            res.headers["Cache-Control"]="private, no-store";return res
        if kind not in ("preview","inside","export","motion"):
            raise CardError("Unknown artwork — kinds: preview, inside, back, export, motion, triptych; faces: r<rev>/spread/<front|inside_left|inside_right|back>",404)
        jobkind="preview" if kind=="inside" else kind
        with db.connect() as c:
            ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind=? AND status='ready'",(owner,did,rev,jobkind)).fetchone()
        if not ready:
            raise CardError("Artwork is not ready",409)
        p=local_asset(key(owner,did,rev,kind))
        res=send_file(p,mimetype={"preview":"image/png","inside":"image/png","export":"application/pdf","motion":"video/mp4"}[kind],as_attachment=kind=="export",download_name=f"{did}-r{rev}.{p.suffix[1:]}",max_age=0)
        res.headers["Cache-Control"]="private, no-store";return res

    @bp.get("/api/cards/<did>/r<int:rev>/spread/<part>")
    def spread_part(did,rev,part):
        owner=request.card_owner;record(owner,did,rev)
        if part not in SPREAD_PARTS:
            raise CardError("Unknown spread face",404)
        with db.connect() as c:
            ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='spread' AND status='ready'",(owner,did,rev)).fetchone()
        if not ready:
            raise CardError("Spread is not ready — render kind spread first",409)
        p=local_asset(key(owner,did,rev,"spread-"+part.replace("_","-")))
        res=send_file(p,mimetype="image/png",max_age=0)
        res.headers["Cache-Control"]="private, no-store";return res

    @bp.get("/api/cards/<did>/r<int:rev>/listing")
    def listing(did,rev):
        """Fixed 2×2 listing collage (front, inside halves, back) — the
        fourth deterministic view agents hand to humans next to Buy."""
        owner=request.card_owner;record(owner,did,rev)
        with db.connect() as c:
            ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='spread' AND status='ready'",(owner,did,rev)).fetchone()
        if not ready:
            raise CardError("Listing is not ready — render kind spread first",409)
        p=contact_sheet(owner,did,rev)
        res=send_file(p,mimetype="image/jpeg",max_age=0)
        res.headers["Cache-Control"]="private, no-store";return res

    @bp.get("/api/cards/<did>/r<int:rev>/triptych")
    def triptych(did,rev):
        """Fixed 3-panel preview: front | inside spread | back at one height.

        The default glance — every surface full-size, never a miniature in a
        collage. Computed on demand from the preview singles (or spread
        faces); needs preview OR spread ready."""
        owner=request.card_owner;record(owner,did,rev)
        with db.connect() as c:
            ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind IN ('preview','spread') AND status='ready'",(owner,did,rev)).fetchone()
        if not ready:
            raise CardError("Preview is not ready — render kind preview first",409)
        try:
            p=triptych_sheet(owner,did,rev)
        except Exception:
            raise CardError("Preview is not ready — render kind preview first",409)
        res=send_file(p,mimetype="image/jpeg",max_age=0)
        res.headers["Cache-Control"]="private, no-store";return res

    @bp.post("/api/cards/<did>/order")
    def order(did):
        owner=request.card_owner;b=request.get_json() or {}
        qty=b.get("qty",1);rev=b.get("revision");idem=b.get("idempotency_key","")
        if not isinstance(qty,int) or isinstance(qty,bool) or not 1<=qty<=20 or not isinstance(rev,int) or isinstance(rev,bool):
            raise CardError("Choose a valid quantity and saved revision")
        if not isinstance(idem,str) or not 12<=len(idem)<=100:
            raise CardError("An idempotency key is required")
        spec=record(owner,did,rev)["spec"]
        validate(owner,spec)  # photos still exist and belong to caller
        with db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            old=c.execute("SELECT * FROM card_orders WHERE owner=? AND idempotency_key=?",(owner,idem)).fetchone()
            if old:
                if (old["design_id"],old["revision"],old["qty"])!=(did,rev,qty):
                    raise CardError("This order key was used for a different design",409)
                return jsonify(ok=True,order=dict(old),reused=True,
                               card_url=card_url_for(did, rev),
                       proof_url=proof_url_for(did),
                               product=card_price(), mcp_status=mcp_status(),
                               checkout_url=old["checkout_url"] if "checkout_url" in old.keys() else "")
            ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='export' AND status='ready'",(owner,did,rev)).fetchone()
            if not ready:
                raise CardError("Export the saved artwork before reserving this card",409)
            oid="ord_card_"+uuid.uuid4().hex
            price=card_price()["price_cents"]*qty
            c.execute("INSERT INTO card_orders (id,owner,design_id,revision,qty,price_cents,spec,export_key,status,idempotency_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(oid,owner,did,rev,qty,price,json_dump(spec),key(owner,did,rev,"export"),"pending_checkout",idem,time.time()))
            c.commit()
            result=dict(c.execute("SELECT * FROM card_orders WHERE id=?",(oid,)).fetchone())
        fulfil = bool(b.get("fulfil"))
        prodigi: dict = {"attempted": False}
        if fulfil:
            # P0 flaw closed: fulfil=true must NOT print before Shopify payment.
            # Use POST /backend/api/cards/<id>/checkout → Shopify invoiceUrl → paid
            # webhook → Prodigi. Direct Prodigi is gated for internal tests only.
            import os as _os
            if _os.environ.get("ALLOW_DIRECT_PRODIGI", "") != "1":
                raise CardError("Direct fulfil is disabled — use POST /backend/api/cards/<id>/checkout "
                                "for Shopify payment first (Prodigi runs on orders/paid only).", 410)
            from backend import config as _cfg
            fmt = spec.get("format", "5x7")
            product = {"5x7": "greeting_card", "A6": "postcard"}.get(fmt, "greeting_card")
            prod = (_cfg.PRODIGI_PRODUCTS.get(product) or {})
            if not prod.get("sku"):
                raise CardError(f"no Prodigi SKU configured for {product} — pull it from the Prodigi dashboard first", 409)
            recipient = b.get("recipient") or {}
            if not isinstance(recipient, dict) or not all(
                    str(recipient.get(k) or "").strip()
                    for k in ("name", "line1", "town", "postcode", "country")):
                raise CardError("fulfil needs recipient {name, line1, town, postcode, country}", 400)
            from backend import prodigi as _prodigi
            from backend import card_print as _print
            from backend import r2presign as _r2
            spec_full = record(owner, did, rev)["spec"]
            aa = assets(owner, spec_full)
            single = _print.compose(spec_full, aa)
            gaps = _print.preflight(single)
            if gaps:
                raise CardError("print file failed preflight: " + "; ".join(gaps), 500)
            r2key = _r2.put_temp(single)
            try:
                asset_url = _r2.presigned_url(r2key)
            except Exception as e:
                _r2.delete(r2key)
                raise CardError(f"asset delivery failed: {str(e)[:200]}", 502) from None
            try:
                placed = _prodigi.create_order(prod["sku"], qty, asset_url, recipient)
            except Exception as e:
                raise CardError(f"Prodigi refused: {str(e)[:200]}", 502) from None
            with db.connect() as c:
                c.execute("UPDATE card_orders SET status='fulfilled', prodigi_ref=? WHERE id=?",
                          (placed["id"], oid))
                c.commit()
                result = dict(c.execute("SELECT * FROM card_orders WHERE id=?", (oid,)).fetchone())
            prodigi = {"attempted": True, "ok": True, **placed}
        return jsonify(ok=True,order=result,currency="GBP",price_grade="FIXED",
                       card_url=card_url_for(did, rev),
                       proof_url=proof_url_for(did),
                       product=card_price(),
                       mcp_status=mcp_status(),
                       prodigi=prodigi,
                       hint=("Card reserved at £2.99 — use POST /backend/api/cards/<id>/checkout "
                             "for the Shopify payment link. Prodigi runs on orders/paid only.")
                       if not fulfil else "Sent to Prodigi print (internal path only).")

    @bp.post("/api/cards/<did>/checkout")
    def checkout(did):
        """P0 revenue path: freeze revision → Shopify draft → human pays → webhook prints.

        Checks: revision exists + belongs to owner + export ready + preflight
        passed + fixed £2.99. Creates local card_order (awaiting_payment),
        then a Shopify draft with line-item customAttributes
        (oddhobb_order_id, design_id, revision, grammar, prodigi_sku).
        Returns checkout_url (Shopify invoiceUrl) + card_url (OddHobb page).
        Shopify owns payment; Prodigi runs on orders/paid only.
        """
        owner=request.card_owner;b=request.get_json() or {}
        qty=b.get("qty",1);rev=b.get("revision");idem=b.get("idempotency_key","") or \
            f"checkout-{did}-r{rev}-q{qty}"
        ship_method = str(b.get("shipping_method") or "Standard")
        if ship_method not in ("Budget", "Standard", "StandardPlus", "Express", "Overnight"):
            raise CardError("unknown shipping method", 400)
        route = None
        dopt = str(b.get("delivery_option_id") or "").strip()[:32]
        if dopt:
            route = None
            with db.connect() as _c:
                _r = _c.execute("SELECT * FROM delivery_options WHERE id=? AND owner=?",
                                (dopt, owner)).fetchone()
                if _r:
                    _d = dict(_r)
                    if _d["design_id"] == did and int(_d["revision"]) == int(rev):
                        route = _d
            if route is None:
                raise CardError("unknown delivery option for this card", 400)
            ship_method = route["shipping_method"]
        recip = b.get("recipient") or {}
        recip_json = ""
        if isinstance(recip, dict) and any(str(recip.get(k) or "").strip() for k in ("name", "line1", "town", "postcode", "country")):
            if not all(str(recip.get(k) or "").strip() for k in ("name", "line1", "town", "postcode", "country")):
                raise CardError("recipient needs name, line1, town, postcode, country", 400)
            recip_json = json_dump({k: str(recip.get(k) or "")[:100] for k in ("name", "line1", "line2", "town", "postcode", "country", "email")})
        if not isinstance(qty,int) or isinstance(qty,bool) or not 1<=qty<=20 \
                or not isinstance(rev,int) or isinstance(rev,bool):
            raise CardError("Choose a valid quantity and saved revision")
        if not isinstance(idem,str) or not 12<=len(idem)<=100:
            raise CardError("An idempotency key is required")
        rec = record(owner,did,rev)
        spec = rec["spec"]
        validate(owner,spec)
        if spec.get("format", "5x7") != "5x7":
            raise CardError("P0 sells the 5×7 folded card only (£2.99) — re-save as 5x7", 400)
        with db.connect() as c:
            old=c.execute("SELECT * FROM card_orders WHERE owner=? AND idempotency_key=?",
                          (owner,idem)).fetchone()
            if old and old["checkout_url"]:
                return jsonify(ok=True, order=dict(old), reused=True,
                               card_url=card_url_for(did, rev),
                               proof_url=proof_url_for(did),
                               product_url=card_url_for(did, rev),
                               product=card_price(),
                               checkout_url=old["checkout_url"],
                               mcp_status=mcp_status(),
                               hint="Done means a product_url the human can buy from.")
            ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? "
                            "AND revision=? AND kind='export' AND status='ready'",
                            (owner,did,rev)).fetchone()
            if not ready and not (old is not None):
                raise CardError("Export the saved artwork before checkout (render export first)",409)
        # preflight the exact PDF bytes the webhook would print
        from backend import card_print as _print
        aa = assets(owner, spec)
        single = _print.compose(spec, aa)
        gaps = _print.preflight(single)
        if gaps:
            raise CardError("print file failed preflight: " + "; ".join(gaps), 500)
        price = card_price()["price_cents"]*qty
        with db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if old is not None:
                oid = old["id"]
                c.execute("UPDATE card_orders SET qty=?, price_cents=?, recipient_json=?, shipping_method=?, delivery_option_id=? WHERE id=?",
                          (qty, price, recip_json, ship_method, dopt, oid))
            else:
                oid="ord_card_"+uuid.uuid4().hex
                c.execute("INSERT INTO card_orders (id,owner,design_id,revision,qty,price_cents,spec,export_key,status,idempotency_key,created_at,recipient_json,shipping_method,delivery_option_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (oid,owner,did,rev,qty,price,json_dump(spec),key(owner,did,rev,"export"),"awaiting_payment",idem,time.time(),recip_json,ship_method,dopt))
            c.commit()
        # Shopify draft — the payment/order layer, not a second storefront.
        # One hidden product ODD-CARD-5X7; personalisation rides as
        # customAttributes, never as new products. No source photos leave us.
        from backend import shopify_fulfil as _sf
        if not _sf.configured():
            raise CardError("Shopify checkout is not configured — set SHOPIFY_STORE + credentials in .env", 503)
        grammar = spec.get("template", "")
        try:
            draft = _sf.create_card_draft_order(
                qty=qty, price_cents=price, oddhobb_order_id=oid,
                design_id=did, revision=rev, grammar=grammar,
                prodigi_sku=CARD_PRODIGI_SKU)
        except Exception as e:  # noqa: BLE001
            raise CardError(f"Shopify draft failed: {str(e)[:200]}", 502) from None
        if not draft.get("ok"):
            raise CardError(f"Shopify draft failed: {draft.get('error','unknown')[:200]}", 502)
        checkout_url = draft.get("invoice_url") or ""
        if not checkout_url:
            raise CardError("Shopify draft created but returned no checkout URL", 502)
        with db.connect() as c:
            c.execute("UPDATE card_orders SET status='awaiting_payment', shopify_draft_id=?, checkout_url=? WHERE id=?",
                      (str(draft.get("draft_id") or draft.get("name") or ""), checkout_url, oid))
            c.commit()
            result=dict(c.execute("SELECT * FROM card_orders WHERE id=?",(oid,)).fetchone())
        return jsonify(ok=True, order=result,
                       product_id=CARD_PRODUCT_ID, product=card_price(),
                       product_url=card_url_for(did, rev),
                       proof_url=proof_url_for(did),
                       card_url=card_url_for(did, rev),
                       checkout_url=checkout_url,
                       shopify_draft=draft,
                       mcp_status=mcp_status(),
                        hint="Send the human to checkout_url to pay (£2.99). "
                             "Prodigi prints after Shopify orders/paid — preview alone is not done.")

    @bp.post("/api/cards/<did>/shipping")
    def shipping(did):
        """Live shipping options for a card revision: no order, no spend.
        Composes the exact print PDF, stages it on temp R2, quotes
        Budget/Standard/Express against the destination, deletes the temp
        asset, returns per-method totals + carrier. Powers the buy box."""
        owner = request.card_owner
        b = request.get_json() or {}
        rev = b.get("revision")
        country = (b.get("country") or "GB").strip().upper()[:2] or "GB"
        if not isinstance(rev, int) or isinstance(rev, bool):
            raise CardError("revision is required", 400)
        spec = record(owner, did, rev)["spec"]
        validate(owner, spec)
        from backend import card_print as _print
        from backend import r2presign as _r2
        from backend import prodigi as _prodigi
        single = _print.compose(spec, assets(owner, spec))
        gaps = _print.preflight(single)
        if gaps:
            raise CardError("print file failed preflight: " + "; ".join(gaps), 500)
        r2key = _r2.put_temp(single)
        try:
            options = []
            for method in ("Budget", "Standard", "Express"):
                try:
                    q = _prodigi.quote(CARD_PRODIGI_SKU, 1, country,
                                       attrs={}, shipping_method=method)
                    options.append({"method": method, "ok": True,
                                    "total": q.get("total"), "item": q.get("item"),
                                    "shipping": q.get("shipping"), "tax": q.get("tax"),
                                    "carrier": q.get("carrier"),
                                    "currency": q.get("currency", "GBP")})
                except Exception as e:  # noqa: BLE001
                    options.append({"method": method, "ok": False,
                                    "error": str(e)[:160]})
        finally:
            try:
                _r2.delete(r2key)
            except Exception:  # noqa: BLE001
                pass
        return jsonify(ok=True, design_id=did, revision=rev,
                       country=country, options=options,
                       note="Totals are live Prodigi quotes incl. tax where given; "
                            "card prints in the UK within 24h, courier time on top.")

    @bp.get("/api/cards/<did>/delivery")
    def delivery(did):
        """Customer delivery choice: Value vs Speedy with customer shipping
        charges and ESTIMATED arrival ranges. ?revision=&country=GB.
        Returns opaque route ids only — supplier, SKU and method stay
        server-side until checkout freezes them onto the order."""
        from backend import delivery as _dlv
        owner = request.card_owner
        rev = request.args.get("revision", type=int)
        country = (request.args.get("country") or "GB").strip().upper()[:2] or "GB"
        if not isinstance(rev, int) or isinstance(rev, bool):
            raise CardError("revision is required", 400)
        rec = record(owner, did, rev)
        validate(owner, rec["spec"])
        routes = _dlv.build_card(country)
        live = [o for o in routes if o["grade"] == "LIVE"]
        if not live:
            raise CardError("no delivery route is quotable right now", 502)
        std = next((o for o in live if o["shipping_method"] == "Standard"), live[0])
        exp = next((o for o in live if o["shipping_method"] == "Express"), None)
        out = {}

        def _option(route, label):
            charge = _dlv.shipping_charge(route["supplier_ship"])
            prod = route["dispatch"]
            arr_from, arr_to = _dlv.arrival_range(
                prod, route["transit"])
            saved = save_delivery_option(
                owner, did, rev, country, route, charge, arr_from, arr_to)
            return {"id": saved["id"], "label": label,
                    "price_cents": charge,
                    "arrival_from": arr_from, "arrival_to": arr_to}

        out["value"] = _option(std, "Value")
        if exp and exp is not std:
            out["speedy"] = _option(exp, "Speedy")
        else:
            out["speedy"] = _option(std, "Speedy")
            out["speedy"]["note"] = ("only one live route — both options "
                                     "share it for now")
        return jsonify(ok=True, design_id=did, revision=rev, country=country,
                       product=public_price(), **out)

    @bp.post("/api/cart/create")
    def shop_cart_create():
        """Guest-safe Storefront cart: freeze revision → cartCreate with
        design linkage in line attributes. Returns cartId + checkoutUrl.
        No OddHobb account needed; no photos/tokens/URLs in attributes."""
        from backend import shopify_cart as _cart
        owner = request.card_owner
        b = request.get_json() or {}
        did = str(b.get("design_id") or "")
        rev = b.get("revision")
        qty = b.get("qty", 1)
        if not did or not isinstance(rev, int) or isinstance(rev, bool):
            raise CardError("design_id + revision are required", 400)
        if not isinstance(qty, int) or isinstance(qty, bool) or not 1 <= qty <= 20:
            raise CardError("qty 1–20", 400)
        rec = record(owner, did, rev)
        validate(owner, rec["spec"])
        with db.connect() as c:
            ready = c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='export' AND status='ready'", (owner, did, rev)).fetchone()
            if not ready:
                raise CardError("Export the saved artwork before checkout (render export first)", 409)
        oid = "ord_card_" + uuid.uuid4().hex
        ship_method, dopt = resolve_delivery_choice(owner, b, did, rev)
        with db.connect() as c:
            c.execute("INSERT INTO card_orders (id,owner,design_id,revision,qty,price_cents,spec,export_key,status,idempotency_key,created_at,shipping_method,delivery_option_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (oid, owner, did, rev, int(qty), card_price()["price_cents"] * int(qty), json_dump(rec["spec"]), key(owner, did, rev, "export"), "in_cart", f"cart-{did}-r{rev}-{time.time():.0f}", time.time(), ship_method, dopt))
            c.commit()
        res = _cart.cart_create(did, rev, int(qty), oid, shipping_method=ship_method,
                                delivery_option_id=dopt)
        if not res.get("ok"):
            raise CardError(res.get("error", "cart failed"), 502)
        return jsonify(ok=True, order_id=oid, cart=res["cart"],
                       checkout_url=(res["cart"] or {}).get("checkoutUrl", ""),
                       product=card_price())

    @bp.post("/api/cart/lines")
    def shop_cart_lines():
        """Add / update-qty / remove lines on an existing cart. Body:
        {cart_id, action: add|update|remove, design_id?, revision?, qty?,
        line_id?}. Add re-validates design ownership + export."""
        from backend import shopify_cart as _cart
        owner = request.card_owner
        b = request.get_json() or {}
        cart_id = str(b.get("cart_id") or "")
        action = str(b.get("action") or "")
        if not cart_id:
            raise CardError("cart_id is required", 400)
        if action == "add":
            did = str(b.get("design_id") or "")
            rev = b.get("revision")
            qty = int(b.get("qty") or 1)
            if not did or not isinstance(rev, int) or isinstance(rev, bool):
                raise CardError("design_id + revision are required", 400)
            rec = record(owner, did, rev)
            validate(owner, rec["spec"])
            with db.connect() as c:
                ready = c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind='export' AND status='ready'", (owner, did, rev)).fetchone()
                if not ready:
                    raise CardError("Export the saved artwork before checkout", 409)
            oid = "ord_card_" + uuid.uuid4().hex
            ship_method, dopt = resolve_delivery_choice(owner, b, did, rev)
            with db.connect() as c:
                c.execute("INSERT INTO card_orders (id,owner,design_id,revision,qty,price_cents,spec,export_key,status,idempotency_key,created_at,shipping_method,delivery_option_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (oid, owner, did, rev, qty, card_price()["price_cents"] * qty, json_dump(rec["spec"]), key(owner, did, rev, "export"), "in_cart", f"cart-{did}-r{rev}-{time.time():.0f}", time.time(), ship_method, dopt))
                c.commit()
            res = _cart.cart_lines_add(cart_id, did, rev, qty, oid,
                                       shipping_method=ship_method,
                                       delivery_option_id=dopt)
        elif action == "update":
            res = _cart.cart_lines_update(cart_id, str(b.get("line_id") or ""), int(b.get("qty") or 1))
        elif action == "remove":
            res = _cart.cart_lines_remove(cart_id, str(b.get("line_id") or ""))
        else:
            raise CardError("action must be add, update or remove", 400)
        if not res.get("ok"):
            raise CardError(res.get("error", "cart failed"), 502)
        return jsonify(ok=True, cart=res["cart"],
                       checkout_url=(res["cart"] or {}).get("checkoutUrl", ""))

    @bp.get("/api/cart")
    def shop_cart_get():
        """Read a cart (lines carry design_id/revision attributes so the
        frontend renders our own previews, never Shopify's)."""
        from backend import shopify_cart as _cart
        cart_id = (request.args.get("id") or "").strip()
        if not cart_id:
            raise CardError("cart id is required", 400)
        res = _cart.cart_get(cart_id)
        if not res.get("ok"):
            raise CardError(res.get("error", "cart failed"), 502)
        return jsonify(ok=True, cart=res["cart"],
                       checkout_url=(res["cart"] or {}).get("checkoutUrl", ""))

    app.register_blueprint(bp)
