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
from PIL import Image

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
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="card-render")
_slots = threading.BoundedSemaphore(6)
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


# ── card P0 product truth ──────────────────────────────────────────
# One hidden Shopify product, one fixed retail price. Prodigi cost is an
# internal margin variable — the customer never sees EST.
CARD_PRODUCT_ID = "ODD-CARD-5X7"
CARD_PRODUCT_NAME = "OddHobb Personalised 5×7 Greeting Card"
CARD_PRODIGI_SKU = "CLASSIC-GRE-FEDR-7X5-BLA"
CARD_PRICE_CENTS = 799  # £7.99 fixed — envelope included


def card_price() -> dict:
    """Fixed retail truth for cards. Reads PRODIGI_PRODUCTS when present
    so config stays the source, but never floats — falls back to £7.99."""
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


def card_url_for(did: str, rev: int | None = None) -> str:
    base = (config.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
    if rev:
        return f"{base}/cards/{did}/r{rev}"
    return f"{base}/cards/{did}"


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
    for field,limit,default in [("headline",160,tpl["headline"]),("recipient",60,""),("sender",100,""),("inside_message",1200,"")]:
        value=b.get(field,default)
        if not isinstance(value,str) or len(value)>limit:
            raise CardError(f"{field} must be text up to {limit} characters")
        spec[field]=value.strip()
    if "oddhobb" in (spec["headline"] + " " + spec["recipient"]).lower():
        raise CardError("No wordmark on the front — brand lives on the back only")
    if not spec["headline"]:
        raise CardError("Add a headline")
    return spec


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
    names={"preview":"front.png","inside":"inside.png","export":"print.pdf","motion":"scene.mp4"}
    with db.connect() as c:
        row=c.execute("SELECT storage_owner FROM card_designs WHERE id=?",(did,)).fetchone()
    if row is None:
        raise CardError("Card not found",404)
    return f"owners/{storage._slug(row[0])}/cards/{did}/r{rev}/{names[kind]}"


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
            scenes.inside(spec).save(inside_path,"PNG")
            storage.put(inside_path,key(owner,did,rev,"inside"))
        elif kind=="export":
            scenes.print_pdf(spec,aa,temp)
        else:
            scenes.motion(spec,aa,temp)
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


def enqueue(owner,did,rev,kind):
    if not isinstance(kind,str) or kind not in ("preview","export","motion"):
        raise CardError("Unknown render kind")
    with ownership_lock,db.connect() as c:
        record(owner,did,rev)
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
    return {"id":row["id"],"design_id":row["design_id"],"revision":row["revision"],"kind":row["kind"],"status":row["status"],"error":row["error"],"url":f"/api/cards/{row['design_id']}/r{row['revision']}/{row['kind']}" if row["status"]=="ready" else ""}


def register(app,owner_denied):
    bp=Blueprint("cards",__name__)

    @bp.before_request
    def auth():
        b=request.get_json(silent=True) or {}
        if not isinstance(b,dict):
            raise CardError("Expected a JSON object")
        owner=str(request.args.get("owner") or b.get("owner") or "anon").strip()[:80]
        request.card_owner=owner
        return owner_denied(owner)

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
                       product={**card_price(),
                                "buy_hint": "Done means a product_url the human can buy from. "
                                            "POST /backend/api/cards/<id>/checkout returns checkout_url; a preview alone is not done."})

    @bp.get("/api/cards/gallery")
    def gallery():
        """Ready-made cards from your uploaded images — no forms.

        Latest photos × flagship 1-photo templates, auto-composed with
        profile-aware headlines. Designs are created once and reused;
        previews render lazily (bounded per call). Tapping a card previews,
        motion-plays, or reserves it — the editor below stays for tinkerers.
        """
        import datetime as _dt
        owner = request.card_owner
        with db.connect() as c:
            photos = [dict(r) for r in c.execute(
                "SELECT * FROM photos WHERE owner=? ORDER BY created_at DESC LIMIT 4",
                (owner,)).fetchall()]
        if not photos:
            return jsonify(ok=True, items=[], empty=True)
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
        bdays = {}
        with db.connect() as c:
            from backend import subjects as _sub
            for p in photos:
                hit = _sub.profile_for_photo(c, owner, p["id"])
                prof = (hit.get("profile") or {}).get("profile", {})
                if hit and (hit.get("subject") or {}).get("name"):
                    who[p["id"]] = hit["subject"]["name"]
                    if prof.get("birthday") or (hit.get("profile") or {}).get("birthday"):
                        bdays[p["id"]] = prof.get("birthday") or hit["profile"]["birthday"]
                    continue
                m = c.execute("SELECT id FROM meshes WHERE photo_id=? ORDER BY created_at DESC LIMIT 1",
                              (p["id"],)).fetchone()
                if m:
                    prof = db.get_subject_profile(c, owner, m["id"])
                    if prof.get("name"):
                        who[p["id"]] = prof["name"]
                    if prof.get("birthday"):
                        bdays[p["id"]] = prof["birthday"]

        def birthday_soon(mmdd: str, days: int = 45) -> bool:
            try:
                today = _dt.date.today()
                nxt = _dt.date(today.year, int(mmdd[:2]), int(mmdd[3:5]))
                if nxt < today:
                    nxt = _dt.date(today.year + 1, int(mmdd[:2]), int(mmdd[3:5]))
                return 0 <= (nxt - today).days <= days
            except (ValueError, IndexError):
                return False

        items, enqueued = [], 0
        for p in photos:
            name = who.get(p["id"], "")
            for tid in ("portrait", "breaking_news", "christmas"):
                tpl = scenes.TEMPLATES[tid]
                headline = tpl["headline"]
                if name and tid == "portrait" and bdays.get(p["id"]) \
                        and birthday_soon(bdays[p["id"]]):
                    headline = f"Happy Birthday, {name}!"
                key = (tid, (p["id"],))
                if key in known:
                    did, rev = known[key]
                else:
                    spec = validate(owner, {
                        "template": tid, "format": "5x7",
                        "headline": headline, "recipient": name,
                        "sender": "", "inside_message": "",
                        "photos": [{"photo_id": p["id"], "crop": [0, 0, 1, 1],
                                    "focus": [0.5, 0.5], "cutout": ""}]})
                    did, rev = "card_" + uuid.uuid4().hex, 1
                    t = time.time()
                    with db.connect() as c:
                        c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via) VALUES (?,?,?,?,?,?,?)",
                                  (did, owner, rev, t, t, owner, "ui"))
                        c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)",
                                  (did, rev, json_dump(spec), t))
                        c.commit()
                    known[key] = (did, rev)
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
                    "template_label": tpl["label"], "headline": headline,
                    "recipient": name, "format": "5x7",
                    "price_cents": card_price()["price_cents"],
                    "price": card_price()["price"],
                    "price_grade": "FIXED",
                    "card_url": card_url_for(did, rev),
                    "photo": {"id": p["id"], "orig_name": p.get("orig_name") or "Photo",
                              "url": f"/api/cards/photos/{p['id']}/image"},
                    "preview_url": url, "preview_status": status,
                })
        return jsonify(ok=True, items=items, product=card_price(),
                       mcp_status=mcp_status(),
                       buy_hint="Done means a product_url the human can buy from — "
                                "POST /backend/api/cards/<id>/checkout for checkout_url. Preview alone is not done.")

    @bp.get("/api/cards/designs/<did>")
    def get_design(did):
        rec = record(request.card_owner,did)
        return jsonify(ok=True,design=rec, card_url=card_url_for(did, rec["revision"]),
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
        }, card_url=card_url_for(did, rev), product=card_price(),
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
        if kind not in ("preview","inside","export","motion"):
            raise CardError("Unknown artwork",404)
        jobkind="preview" if kind=="inside" else kind
        with db.connect() as c:
            ready=c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND design_id=? AND revision=? AND kind=? AND status='ready'",(owner,did,rev,jobkind)).fetchone()
        if not ready:
            raise CardError("Artwork is not ready",409)
        p=local_asset(key(owner,did,rev,kind))
        res=send_file(p,mimetype={"preview":"image/png","inside":"image/png","export":"application/pdf","motion":"video/mp4"}[kind],as_attachment=kind=="export",download_name=f"{did}-r{rev}.{p.suffix[1:]}",max_age=0)
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
                       product=card_price(),
                       mcp_status=mcp_status(),
                       prodigi=prodigi,
                       hint=("Card reserved at £7.99 — use POST /backend/api/cards/<id>/checkout "
                             "for the Shopify payment link. Prodigi runs on orders/paid only.")
                       if not fulfil else "Sent to Prodigi print (internal path only).")

    @bp.post("/api/cards/<did>/checkout")
    def checkout(did):
        """P0 revenue path: freeze revision → Shopify draft → human pays → webhook prints.

        Checks: revision exists + belongs to owner + export ready + preflight
        passed + fixed £7.99. Creates local card_order (awaiting_payment),
        then a Shopify draft with line-item customAttributes
        (oddhobb_order_id, design_id, revision, grammar, prodigi_sku).
        Returns checkout_url (Shopify invoiceUrl) + card_url (OddHobb page).
        Shopify owns payment; Prodigi runs on orders/paid only.
        """
        owner=request.card_owner;b=request.get_json() or {}
        qty=b.get("qty",1);rev=b.get("revision");idem=b.get("idempotency_key","") or \
            f"checkout-{did}-r{rev}-q{qty}"
        if not isinstance(qty,int) or isinstance(qty,bool) or not 1<=qty<=20 \
                or not isinstance(rev,int) or isinstance(rev,bool):
            raise CardError("Choose a valid quantity and saved revision")
        if not isinstance(idem,str) or not 12<=len(idem)<=100:
            raise CardError("An idempotency key is required")
        rec = record(owner,did,rev)
        spec = rec["spec"]
        validate(owner,spec)
        if spec.get("format", "5x7") != "5x7":
            raise CardError("P0 sells the 5×7 folded card only (£7.99) — re-save as 5x7", 400)
        with db.connect() as c:
            old=c.execute("SELECT * FROM card_orders WHERE owner=? AND idempotency_key=?",
                          (owner,idem)).fetchone()
            if old and old["checkout_url"]:
                return jsonify(ok=True, order=dict(old), reused=True,
                               card_url=card_url_for(did, rev),
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
                c.execute("UPDATE card_orders SET qty=?, price_cents=? WHERE id=?",
                          (qty, price, oid))
            else:
                oid="ord_card_"+uuid.uuid4().hex
                c.execute("INSERT INTO card_orders (id,owner,design_id,revision,qty,price_cents,spec,export_key,status,idempotency_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (oid,owner,did,rev,qty,price,json_dump(spec),key(owner,did,rev,"export"),"awaiting_payment",idem,time.time()))
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
                       card_url=card_url_for(did, rev),
                       checkout_url=checkout_url,
                       shopify_draft=draft,
                       mcp_status=mcp_status(),
                       hint="Send the human to checkout_url to pay (£7.99). "
                            "Prodigi prints after Shopify orders/paid — preview alone is not done.")

    app.register_blueprint(bp)
