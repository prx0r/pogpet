#!/usr/bin/env python3
"""figgsite backend API — photo intake -> mesh -> product activation.

Stdlib+Flask only. Token-gated, binds loopback; the outside world arrives
through a Cloudflare tunnel.

    POST /api/photos                 multipart photo -> R2, returns photo_id
    POST /api/meshes                 {photo_id} -> start the Meshy job
    GET  /api/meshes/<id>            status + products this mesh powers
    GET  /api/meshes/<id>/products   the fan-out only
    POST /api/run                    drain the job queue now
    GET  /api/artifacts/<key>        stream a private R2 object
    GET  /health
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
import uuid
from datetime import date, timezone, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageOps  # noqa: F401
from flask import Flask, Response, jsonify, redirect, request, send_file  # noqa: E402

from backend import config, db, intake, meshy, pipeline, storage, video  # noqa: E402
from backend import auth as gauth  # noqa: E402

app = Flask(__name__)
# Photos are capped at 10MB in intake.accept(); this ceiling only has to fit
# the biggest GLB we accept (64MB) plus multipart overhead.
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024 + 1024 * 1024

if not config.API_TOKEN:
    config.API_TOKEN = config.mint_token()

_worker_stop = threading.Event()


# ── auth ──────────────────────────────────────────────────────────────

def _gated():
    # Service auth is ?token= or X-API-Token only. Authorization: Bearer is
    # reserved for USER api keys — taking it here made every user key 401.
    tok = request.args.get("token") or request.headers.get("X-API-Token", "")
    if tok == config.API_TOKEN:
        return None
    return jsonify({"ok": False, "error": "bad token"}), 401


@app.before_request
def gate():
    if request.path == "/health":
        return None
    return _gated()


def _err(message: str, code: int):
    return jsonify({"ok": False, "error": message}), code


# ── owner signatures (audit H1) ──────────────────────────────────────
# Browser visitors used to be able to POST owner=<anyone> and burn that
# owner's free sculpt/video credits. Writes now need either a real user
# API key for that owner or an owner_sig minted by POST /api/session.
# "anon" stays open on the service-token path so the seeded demo + tests
# keep working — named owners do not.

_AUTH_FAILS: dict[str, list[float]] = {}
_AUTH_WINDOW = 900.0
_AUTH_MAX = 5


def _auth_rate(bucket: str, key: str) -> bool:
    """True if another attempt is allowed. In-memory, per-process."""
    import time as _time
    slot = f"{bucket}:{key}"
    now = _time.time()
    hits = [t for t in _AUTH_FAILS.get(slot, []) if now - t < _AUTH_WINDOW]
    if len(hits) >= _AUTH_MAX:
        _AUTH_FAILS[slot] = hits
        return False
    hits.append(now)
    _AUTH_FAILS[slot] = hits
    return True


def _auth_rate_reset(bucket: str, key: str) -> None:
    _AUTH_FAILS.pop(f"{bucket}:{key}", None)


def _owner_sig() -> str:
    sig = request.headers.get("X-Owner-Sig", "").strip()
    if not sig:
        b = request.get_json(silent=True) or {}
        sig = str(b.get("owner_sig") or "").strip()
    if not sig:
        sig = (request.form.get("owner_sig")
               or request.args.get("owner_sig") or "").strip()
    return sig


def _owner_denied(owner: str):
    """Error response if the caller may not act as `owner`, else None."""
    owner = (owner or "anon").strip()[:80]
    key = _api_key()
    if key:
        with db.connect() as c:
            u = db.get_user_by_api_key(c, key)
        if u and u["handle"] == owner:
            return None
        if u:
            return _err("API key does not match this owner", 403)
        return _err("unknown API key", 401)
    sig = _owner_sig()
    if config.verify_owner(owner, sig):
        return None
    if owner == "anon":
        return None
    return _err(
        "owner_sig required for this owner — POST /api/session first", 403)


@app.post("/api/session")
def api_session():
    """Mint or refresh an owner_sig.

    - valid owner+sig  -> echo back (session continues)
    - empty / "anon"   -> sign "anon" (seeded demo path)
    - pog_* unsigned    -> sign that random browser id (unguessable, low risk)
    - any other name   -> 403 (cannot claim a named owner without proof)
    """
    b = request.get_json(silent=True) or {}
    owner = str(b.get("owner") or "").strip()[:80]
    sig = str(b.get("owner_sig") or "").strip() or _owner_sig()
    if owner and config.verify_owner(owner, sig):
        return jsonify({"ok": True, "owner": owner, "owner_sig": sig})
    if not owner or owner == "anon":
        owner = "anon"
    elif owner.startswith("pog_") and len(owner) <= 40:
        pass  # client-generated browser id — sign as presented
    else:
        return _err(
            "cannot claim a named owner without a valid owner_sig or API key",
            403)
    return jsonify({"ok": True, "owner": owner,
                    "owner_sig": config.sign_owner(owner)})


# ── photos ────────────────────────────────────────────────────────────

@app.post("/api/photos")
def upload_photo():
    owner = (request.form.get("owner") or request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    day = date.today().isoformat()

    file = request.files.get("photo") or request.files.get("file")
    if file is None:
        return _err("Attach a photo in the 'photo' field.", 400)

    try:
        accepted = intake.accept(file.read(), file.filename or "photo.jpg", owner)
    except intake.IntakeError as e:
        return _err(str(e), e.code)

    with db.connect() as c:
        # Free path first: same owner, same bytes. Re-uploading something
        # already on file costs no sculpt credit, so it must not count
        # against (or be blocked by) the daily quota.
        existing = db.find_photo_by_hash(c, accepted.sha256, owner)
        if existing:
            return jsonify({"ok": True, "reused": True, "photo": db.dump(existing)})

        if db.count_uploads_today(c, owner, day) >= config.DAILY_UPLOAD_LIMIT:
            return _err(
                f"That's {config.DAILY_UPLOAD_LIMIT} uploads today — upload "
                "allowance resets tomorrow. Your existing photos are still available.", 429)

        key = storage.photo_key(owner, accepted.sha256)
        try:
            storage.put(accepted.path, key)
        except storage.StorageError as e:
            return _err(f"couldn't store the photo: {e}", 502)

        try:
            pid = db.insert_photo(
                c, owner=owner, sha256=accepted.sha256, r2_key=key, mime=accepted.mime,
                width=accepted.width, height=accepted.height, bytes=accepted.nbytes,
                orig_name=accepted.orig_name)
        except Exception:
            # Lost a race with a concurrent identical upload — reuse theirs.
            again = db.find_photo_by_hash(c, accepted.sha256, owner)
            if again:
                return jsonify({"ok": True, "reused": True, "photo": db.dump(again)})
            raise
        db.bump_uploads(c, owner, day)
        photo = db.get_photo(c, pid)

    return jsonify({"ok": True, "reused": False, "photo": db.dump(photo)})


@app.get("/api/photos/<pid>")
def get_photo(pid: str):
    with db.connect() as c:
        photo = db.get_photo(c, pid)
        meshes = c.execute(
            "SELECT id,status,stub,glb_key,created_at FROM meshes WHERE photo_id=?"
            " ORDER BY created_at DESC", (pid,)).fetchall()
    if photo is None:
        return _err("no such photo", 404)
    return jsonify({"ok": True, "photo": db.dump(photo),
                    "meshes": [db.dump(m) for m in meshes]})


# ── meshes ────────────────────────────────────────────────────────────

@app.post("/api/meshes")
def start_mesh():
    body = request.get_json(silent=True) or {}
    photo_id = body.get("photo_id") or request.form.get("photo_id")
    if not photo_id:
        return _err("photo_id is required", 400)
    with db.connect() as c:
        photo = db.get_photo(c, photo_id)
    if photo is None:
        return _err("That photo isn't on file — upload it first.", 404)
    denied = _owner_denied(photo["owner"] or "anon")
    if denied is not None:
        return denied
    try:
        res = pipeline.start_mesh(photo_id)
    except pipeline.PipelineError as e:
        return _err(str(e), e.code)
    return jsonify({"ok": True, **res})


@app.get("/api/meshes")
def list_meshes():
    """Latest meshes for an owner — what the shop/studio tabs bind to."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    limit = min(int(request.args.get("limit", "10") or 10), 50)
    with db.connect() as c:
        rows = c.execute(
            "SELECT m.* FROM meshes m JOIN photos p ON p.id=m.photo_id"
            " WHERE p.owner=? ORDER BY m.created_at DESC LIMIT ?",
            (owner, limit)).fetchall()
        out = []
        for r in rows:
            d = db.dump(r)
            d["glb_url"] = storage.public_url(r["glb_key"]) if r["glb_key"] else ""
            d["products"] = db.products_for(c, r["id"])
            out.append(d)
    return jsonify({"ok": True, "owner": owner, "meshes": out,
                    "count": len(out)})


@app.get("/api/me")
def me():
    """Spotlight state: who you are, your roster, which pog is active."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        pogs = db.pogs_for(c, owner)
        active = prof.get("active_mesh_id") or ""
        if not active:
            ok = next((p for p in pogs if p["status"] == "succeeded"), None)
            if ok:
                active = ok["id"]
                db.set_active(c, owner, active)
        profiles = {p["id"]: db.get_subject_profile(c, owner, p["id"]) for p in pogs}
        roster = [{
            "mesh_id": p["id"], "status": p["status"], "stub": bool(p["stub"]),
            "print_ready": bool(p["print_ready"]), "photo_key": p.get("photo_key", ""),
            "active": p["id"] == active, "created_at": p["created_at"],
            "profile": profiles.get(p["id"]) or None,
        } for p in pogs]
    return jsonify({"ok": True, "owner": owner, "active_mesh_id": active,
                    "pogs": roster, "count": len(roster)})


@app.post("/api/me/active")
def set_active():
    """Make a pog active — every product/card/video follows it from here."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    mesh_id = (body.get("mesh_id") or "").strip()
    if not owner or not mesh_id:
        return _err("owner and mesh_id are required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        if not db.get_mesh(c, mesh_id):
            return _err("no such mesh", 404)
        row = c.execute(
            "SELECT 1 FROM meshes m JOIN photos p ON p.id=m.photo_id"
            " WHERE m.id=? AND p.owner=?", (mesh_id, owner)).fetchone()
        if not row:
            return _err("that mesh belongs to someone else", 403)
        db.set_active(c, owner, mesh_id)
    return jsonify({"ok": True, "owner": owner, "active_mesh_id": mesh_id})


def _suggest_motif(interests: list) -> dict | None:
    """First motif of the first interest the engine knows. Advisory only —
    checkout never assumes it; the customer confirms."""
    for raw in interests or []:
        key = str(raw).strip().lower()
        motifs = config.INTEREST_MOTIFS.get(key)
        if motifs:
            return {"interest": key, "motif": motifs[0], "motifs": motifs}
    return None


@app.get("/api/subjects/profiles")
def subject_profiles():
    """Friends list: every profiled subject for this owner."""
    owner = (request.args.get("owner") or "").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        rows = c.execute(
            "SELECT * FROM subject_profiles WHERE owner=? ORDER BY updated_at DESC",
            (owner,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["interests"] = json.loads(d.get("interests") or "[]")
            except (ValueError, TypeError):
                d["interests"] = []
            d["suggestion"] = _suggest_motif(d["interests"])
            out.append(d)
    return jsonify({"ok": True, "owner": owner, "profiles": out})


@app.post("/api/subjects/profile")
def set_subject_profile():
    """Name a friend: {owner, mesh_id, name?, interests[]?, birthday?}."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    mesh_id = (body.get("mesh_id") or "").strip()
    if not owner or not mesh_id:
        return _err("owner and mesh_id are required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        if not db.get_mesh(c, mesh_id):
            return _err("no such mesh", 404)
        row = c.execute(
            "SELECT 1 FROM meshes m JOIN photos p ON p.id=m.photo_id"
            " WHERE m.id=? AND p.owner=?", (mesh_id, owner)).fetchone()
        if not row:
            return _err("that mesh belongs to someone else", 403)
        prof = db.set_subject_profile(
            c, owner, mesh_id,
            name=str(body.get("name") or ""),
            interests=body.get("interests") if isinstance(body.get("interests"), list) else None,
            birthday=str(body.get("birthday") or ""))
    return jsonify({"ok": True, "owner": owner, "profile": prof,
                    "suggestion": _suggest_motif(prof.get("interests", []))})


# ── guided personal shopper ───────────────────────────────────────────
# Person first, no search bar: ramble -> profile -> photos -> mesh -> packs.

def _guide_pack_items(owner: str, state: dict, active_mesh: str = "") -> list[dict]:
    """Curated packs: budget-filtered lines with the subject's suggestion.
    Max 3 per theme — the customer never scrolls."""
    from backend import guide as _g
    budget = state.get("budget_cents") or 0
    rec = state.get("recipient", {})
    suggestion = _suggest_motif(rec.get("interests", []))
    prefs = state.get("prefs", {})
    excluded = set(prefs.get("exclude", []))
    motif = prefs.get("motif") or (suggestion or {}).get("motif", "")
    groups: dict[str, list] = {}
    for lid, spec in config.STUDIO_LINES.items():
        if spec.get("status") != "live" or spec.get("fulfilment") == "digital":
            continue
        if lid in excluded:
            continue
        price = spec.get("price_cents", 0)
        if budget and price > budget:
            continue
        stills = _studio_stills_for(lid, "none", "none")
        why = ""
        if motif:
            why = f"Picked for {rec.get('name') or 'them'}: {motif.replace('_', ' ')}."
        elif suggestion:
            why = (f"Picked for {rec.get('name') or 'them'}: "
                   f"{suggestion['motif'].replace('_', ' ')} "
                   f"({suggestion['interest']}).")
        groups.setdefault(spec.get("theme", "everyday"), []).append({
            "id": lid, "label": spec.get("label", lid),
            "price_cents": price, "material": spec.get("material"),
            "dims_mm": spec.get("dims_mm"), "stills": stills,
            "customization_schema": _custom_schema(lid, spec),
            "motif": motif, "why": why,
        })
    packs = []
    for theme in ("stocking", "game_night", "gamer", "christmas", "everyday", "desk"):
        items = sorted(groups.get(theme, []), key=lambda i: i["price_cents"])[:3]
        if items:
            packs.append({"theme": theme, "items": items})
    return packs


@app.post("/api/guide/open")
def guide_open():
    from backend import guide as _g
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        sid = _g.new_id()
        _g.save_session(c, sid, owner, "ramble", _g.blank_state())
    return jsonify({"ok": True, "session_id": sid, "stage": "ramble",
                    "prompt": "Who are we shopping for — and what's the occasion?"})


@app.post("/api/guide/turn")
def guide_turn():
    """One ramble/refine message. Routes by stage; accumulates, never restarts."""
    from backend import guide as _g
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    sid = (body.get("session_id") or "").strip()
    text = (body.get("text") or "").strip()
    if not owner or not sid or not text:
        return _err("owner, session_id and text are required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        s = _g.get_session(c, sid, owner)
        if not s:
            return _err("no such session", 404)
        state, stage = s["state"], s["stage"]
        low = text.lower()
        rec0 = state.get("recipient", {})
        complete = bool(rec0.get("name") and state.get("occasion") and state.get("budget_cents"))
        looks_refine = bool(_g._extract_budget(text)
                            or re.search(r"(?:motif|make it|i want|cheaper|under|not\s+the|no\s+[a-z])", low))
        if stage in ("ready", "refining") or (complete and looks_refine and stage == "photos"):
            # refine: budget shifts, motif picks, line vetoes
            prefs = state.setdefault("prefs", {"motif": "", "exclude": []})
            changed = []
            b = _g._extract_budget(text)
            if b:
                state["budget_cents"] = b
                changed.append(f"budget under {b // 100}")
            m = re.search(r"(?:motif|make it|i want)\s+([a-z_ ]{3,30})", low)
            if m:
                prefs["motif"] = m.group(1).strip().replace(" ", "_")[:30]
                changed.append(f"motif {prefs['motif']}")
            for lid in config.STUDIO_LINES:
                if re.search(r"\bnot\s+(the\s+)?" + re.escape(lid.replace("_", " ")) + r"\b", low) \
                        or f"no {lid.replace('_', ' ')}" in low:
                    if lid not in prefs["exclude"]:
                        prefs["exclude"].append(lid)
                        changed.append(f"dropped {lid}")
            state["events"] = _g.compute_events(state)
            _g.save_session(c, sid, owner, "refining", state)
            packs = _guide_pack_items(owner, state)
            reply = ("Done" + (": " + ", ".join(changed) if changed else
                                " — tell me budget, motif, or what to drop") + ".")
            return jsonify({"ok": True, "session_id": sid, "stage": "refining",
                            "reply": reply, "packs": packs,
                            "events": state.get("events", [])})
        state, prompt = _g.ramble_turn(state, text)
        rec = state.get("recipient", {})
        if rec.get("name") and state.get("occasion") and state.get("budget_cents"):
            stage = "photos"
        _g.save_session(c, sid, owner, stage, state)
        return jsonify({"ok": True, "session_id": sid, "stage": stage,
                        "reply": prompt, "recipient": rec,
                        "occasion": state.get("occasion", ""),
                        "budget_cents": state.get("budget_cents", 0),
                        "events": state.get("events", [])})


@app.post("/api/guide/photos")
def guide_photos():
    """Attach up to 10 owned photos to the session."""
    from backend import guide as _g
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    sid = (body.get("session_id") or "").strip()
    pids = body.get("photo_ids") or []
    if not owner or not sid or not isinstance(pids, list):
        return _err("owner, session_id and photo_ids[] are required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        s = _g.get_session(c, sid, owner)
        if not s:
            return _err("no such session", 404)
        state = s["state"]
        have = [p for p in state.get("photo_ids", [])]
        for pid in pids[:_g.MAX_PHOTOS]:
            ph = db.get_photo(c, str(pid))
            if ph and (ph["owner"] or "anon") == owner and str(pid) not in have \
                    and len(have) < _g.MAX_PHOTOS:
                have.append(str(pid))
        state["photo_ids"] = have
        _g.save_session(c, sid, owner, "photos" if not state.get("mesh_id") else s["stage"], state)
    return jsonify({"ok": True, "session_id": sid, "photo_ids": have,
                    "reply": f"{len(have)} photo{'s' if len(have) != 1 else ''} kept. "
                             f"Say the word and I'll sculpt the mesh."})


@app.post("/api/guide/mesh")
def guide_mesh():
    """Sculpt the session mesh from an attached photo (free-tier quota applies)."""
    from backend import guide as _g
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    sid = (body.get("session_id") or "").strip()
    pid = (body.get("photo_id") or "").strip()
    if not owner or not sid:
        return _err("owner and session_id are required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        s = _g.get_session(c, sid, owner)
        if not s:
            return _err("no such session", 404)
        state = s["state"]
        if not pid:
            pid = (state.get("photo_ids") or [""])[0]
        if not pid or pid not in state.get("photo_ids", []):
            return _err("pick one of the session photos first", 400)
        try:
            from backend import pipeline as _p
            res = _p.start_mesh(pid)
        except Exception as e:
            code = getattr(e, "code", 500) if hasattr(e, "code") else 500
            return _err(str(e)[:300], code if isinstance(code, int) else 500)
        mesh = res.get("mesh", {})
        state["mesh_id"] = mesh.get("id", "")
        state["mesh_status"] = mesh.get("status", "")
        rec = state.setdefault("recipient", {})
        rec["mesh_id"] = state["mesh_id"]
        _g.save_session(c, sid, owner, "ready" if mesh.get("status") == "succeeded" else "meshing", state)
    return jsonify({"ok": True, "session_id": sid, "mesh": mesh,
                    "reused": res.get("reused", False),
                    "reply": "Mesh underway — packs appear as soon as it lands."})


@app.get("/api/guide/packs")
def guide_packs():
    """Curated gift packs: no scroll, no search. Budget-filtered, motif-picked."""
    from backend import guide as _g
    owner = (request.args.get("owner") or "").strip()[:80]
    sid = (request.args.get("session_id") or "").strip()
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        s = _g.get_session(c, sid, owner)
        if not s:
            return _err("no such session", 404)
        state = s["state"]
        prof = db.get_profile(c, owner)
        packs = _guide_pack_items(owner, state, prof.get("active_mesh_id") or "")
    return jsonify({"ok": True, "session_id": sid, "packs": packs,
                    "recipient": state.get("recipient", {}),
                    "budget_cents": state.get("budget_cents", 0),
                    "events": state.get("events", [])})


def _ensure_mockup(owner, short, pid, spec, src_path, concept, subject, have):
    """Render a product mockup if missing; return (r2_key, fname, was_rendered).

    Extracted so feeds and future surfaces reuse the identical cache semantics
    as /api/products (same fname scheme, same R2 keys). Raises
    FileNotFoundError when there is no source image to render from.
    """
    from backend import mockup   # absolute: this module is __main__
    ctag = f"_{concept['id']}" if concept else ""
    stg = f"_{abs(hash(subject)) % 99999}" if subject else ""
    fname = f"{pid}_{short}{ctag}{stg}.png"
    key = f"owners/{storage._slug(owner)}/products/{fname}"
    rendered = False
    if fname not in have:
        if src_path is None:
            raise FileNotFoundError("no source image")
        tmp = config.LOCAL_TMP / f"mk_{pid}_{owner}.png"
        mockup.render(spec["shape"], src_path, spec["label"], tmp,
                      concept=concept, subject=subject)
        storage.put(tmp, key)
        tmp.unlink(missing_ok=True)
        have.add(fname)
        rendered = True
    return key, fname, rendered


def _product_src(owner, active, mesh, photo):
    """Source image for mockups: Blender mesh render first, photo fallback."""
    try:
        from backend import render as meshrender          # absolute: this is __main__
        rkey = meshrender.get_mesh_render(owner, active, mesh["glb_key"])
        if rkey:
            tmp = config.LOCAL_TMP / f"mr_{active}.png"
            storage.get(rkey, tmp)
            return str(tmp), "mesh"
    except Exception:
        pass
    try:
        src = pipeline._local_photo(dict(photo)) if photo else None
        return (str(src), "photo") if src else (None, "none")
    except Exception:
        return None, "none"


def _public_product_image(key, fname):
    """Mirror an R2 product render into the public /img/ dir (cached).

    Marketing assets only — user photos never land here. Feeds and shopping
    agents fetch these without any token.
    """
    config.ensure_dirs()
    dest = config.PRODUCTIMG_DIR / fname
    if not dest.exists() or dest.stat().st_size == 0:
        storage.get(key, dest)
    return f"{_public_base()}/img/{fname}"


@app.get("/api/products")
def products():
    """Prodigi rendered against the owner's ACTIVE pog.

    Each item comes back with a server-rendered mockup so the grid literally
    shows their selected mesh on a card / mug / wrapping paper / jigsaw.

    ?concept=<id>&subject=<name> layers a concept from the 36-template
    library over it — world-tinted glow, concept name, subject on the plinth.
    """
    owner = (request.args.get("owner") or "anon").strip()[:80]
    concept_id = (request.args.get("concept") or "").strip()
    subject = (request.args.get("subject") or "").strip()[:40]
    concept = None
    if concept_id:
        try:
            from backend import concepts as lib
            concept = lib.get(concept_id)
        except Exception:
            concept = None
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        pogs = db.pogs_for(c, owner)
        active = prof.get("active_mesh_id") or ""
        if not active:
            ok = next((p for p in pogs if p["status"] == "succeeded"), None)
            active = ok["id"] if ok else ""
        if not active:
            return jsonify({"ok": True, "owner": owner, "active_mesh_id": "",
                            "items": [], "count": 0,
                            "hint": "No active pog yet — add one in the upload tab."})
        mesh = db.get_mesh(c, active)
        if mesh is None:
            return _err("active mesh missing", 404)
        photo = db.get_photo(c, mesh["photo_id"])

        # Source image: prefer a Blender render of the actual MESH, fall back
        # to the uploaded photo if rendering isn't possible yet.
        src_path, src_kind = None, "none"
        try:
            from backend import render as meshrender          # absolute: this is __main__
            rkey = meshrender.get_mesh_render(owner, active, mesh["glb_key"])
            if rkey:
                tmp = config.LOCAL_TMP / f"mr_{active}.png"
                storage.get(rkey, tmp)
                src_path, src_kind = tmp, "mesh"
        except Exception:
            src_path = None
        if src_path is None:
            try:
                src_path = pipeline._local_photo(dict(photo)) if photo else None
                src_kind = "photo" if src_path else "none"
            except Exception:
                src_path = None

        items, rendered, failed = [], 0, {}
        short = active.replace("msh_", "")[:8]      # cache key follows the active pog
        # one list call, not one exists() per product
        try:
            have = storage.list_keys(f"owners/{storage._slug(owner)}/products/")
        except storage.StorageError:
            have = set()
        for pid, spec in {**config.PRODIGI_PRODUCTS}.items():
            try:
                key, fname, was_rendered = _ensure_mockup(
                    owner, short, pid, spec, src_path, concept, subject, have)
                rendered += was_rendered
            except FileNotFoundError:
                failed[pid] = "no source image"
                continue
            except Exception as e:
                # Never swallow this silently again — it hid a whole empty grid.
                failed[pid] = f"{type(e).__name__}: {e}"
                app.logger.exception("mockup failed for %s", pid)
                continue
            price, grade = spec["price_cents"], "EST"
            if spec.get("sku"):
                try:
                    from backend import prodigi as pdi
                    q = pdi.quote(spec["sku"], attrs=spec.get("sku_attrs"))
                    price = pdi.to_cents(q["item"], q["currency"])
                    grade = "LIVE"
                except Exception:
                    pass
            items.append({
                "id": pid, "label": spec["label"], "shape": spec["shape"],
                "section": config.SECTION_OF.get(pid, ""),
                "price_cents": price, "sku_note": spec["sku_note"],
                "sku": spec.get("sku"), "price_grade": grade,
                "image": storage.public_url(key), "source": "prodigi",
                "source_kind": src_kind,          # "mesh" (blender) or "photo"
                "free": spec.get("free", False),
            })
    return jsonify({"ok": True, "owner": owner, "active_mesh_id": active,
                    "source_kind": src_kind,
                    "concept": (concept or {}).get("id"),
                    "subject": subject,
                    "items": items, "count": len(items), "rendered": rendered,
                    "failed": failed,
                    "note": "prices are EST — no live Prodigi key to quote against"})



@app.post("/api/meshes/glb")
def upload_glb():
    """Land a GLB straight into the spotlight — no Meshy, no key.

    Same trust model as every other route: a browser posts `owner=`, an agent
    posts its API key and gets permission-checked. The heavy lifting lives in
    install.install_glb so style presets can't drift from this path.
    """
    h, kind, perms = _principal()
    owner = (request.form.get("owner") or (h if kind != "anon" else "")).strip()[:80]
    if kind == "agent":
        if "mesh:upload" not in perms:
            return _err("your agent needs the 'mesh:upload' permission", 403)
        owner = h                       # an agent always writes to its own profile
    if not owner:
        return _err("owner or API key required", 400)

    f = request.files.get("file") or request.files.get("glb")
    if f is None:
        return _err("attach a .glb in the 'file' field", 400)
    name = (f.filename or "model.glb")
    if not name.lower().endswith(".glb"):
        return _err("only .glb is accepted", 400)

    config.ensure_dirs()
    stage = config.LOCAL_TMP / f"up_{uuid.uuid4().hex[:10]}.glb"
    stage.write_bytes(f.read())
    try:
        from backend import install
        return jsonify(install.install_glb(owner, stage, source="upload", label=name))
    except install.InstallError as e:
        return _err(str(e), e.code)
    except Exception as e:
        return _err(f"could not install: {str(e)[:200]}", 500)
    finally:
        stage.unlink(missing_ok=True)


@app.get("/api/styles")
def styles_route():
    """Ready-made characters to start from — no Meshy key required."""
    try:
        from backend import styles as lib
        items = lib.list_styles()
    except Exception as e:
        return _err(f"style library unavailable: {str(e)[:200]}", 500)
    return jsonify({"ok": True, "count": len(items),
                    "available": sum(1 for i in items if i["available"]),
                    "items": items,
                    "note": "meshes only — a pet that looks like yours still "
                            "needs photo-to-3D, but everything after the mesh is free"})


@app.post("/api/meshes/style")
def start_style():
    """Instant mesh from a preset: POST {style: "badger-classic"}."""
    b = request.get_json(silent=True) or {}
    style_id = (b.get("style") or "").strip()
    if not style_id:
        return _err("style is required", 400)
    h, kind, perms = _principal()
    owner = (b.get("owner") or (h if kind != "anon" else "")).strip()[:80]
    if kind == "agent":
        if "mesh:upload" not in perms:
            return _err("your agent needs the 'mesh:upload' permission", 403)
        owner = h
    if not owner:
        return _err("owner or API key required", 400)
    try:
        from backend import styles as lib
        return jsonify(lib.install_style(owner, style_id))
    except Exception as e:
        code = getattr(e, "code", 500)
        return _err(str(e)[:300], code if isinstance(code, int) else 500)


@app.get("/api/meshes/<mid>")
def get_mesh(mid: str):
    with db.connect() as c:
        mesh = db.get_mesh(c, mid)
        products = db.products_for(c, mid)
        jobs = c.execute(
            "SELECT id,kind,status,error,attempts FROM jobs WHERE subject_id=?"
            " ORDER BY created_at DESC LIMIT 5", (mid,)).fetchall()
    if mesh is None:
        return _err("no such mesh", 404)
    out = db.dump(mesh)
    out["glb_url"] = storage.public_url(mesh["glb_key"]) if mesh["glb_key"] else ""
    return jsonify({"ok": True, "mesh": out, "products": products,
                    "jobs": [db.dump(j) for j in jobs]})


# Turntable renders are >100s for a real 59k-tri mesh, and Cloudflare's
# free proxy times out at 100s (HTTP 524). So: return immediately and render
# in a background thread; the client polls until the file exists.
_TT_INFLIGHT: set = set()
_TT_LOCK = threading.Lock()


@app.get("/api/meshes/<mid>/turntable")
def mesh_turntable(mid: str):
    """360° orbit of the mesh as MP4. Ready instantly once cached."""
    owner = (request.args.get("owner") or "").strip()[:80]
    with db.connect() as c:
        mesh = db.get_mesh(c, mid)
        if mesh is None:
            return _err("no such mesh", 404)
        if not owner:
            row = c.execute(
                "SELECT p.owner FROM meshes m JOIN photos p ON p.id=m.photo_id"
                " WHERE m.id=?", (mid,)).fetchone()
            owner = row["owner"] if row else "anon"
    if not mesh["glb_key"]:
        return _err("this mesh has no GLB yet", 409)

    key = f"owners/{storage._slug(owner)}/meshes/{mid}/turntable.mp4"
    try:
        if storage.exists(key):
            return jsonify({"ok": True, "status": "ready", "mesh_id": mid,
                            "owner": owner, "url": storage.public_url(key)})
    except storage.StorageError:
        pass

    with _TT_LOCK:
        if mid in _TT_INFLIGHT:
            return jsonify({"ok": True, "status": "rendering", "mesh_id": mid,
                            "owner": owner, "url": None})
        _TT_INFLIGHT.add(mid)

    def _work():
        try:
            from backend import render as meshrender
            meshrender.get_turntable(owner, mid, mesh["glb_key"])
        except Exception as e:  # noqa: BLE001 — surface, don't swallow
            import traceback
            print(f"turntable {mid}: {e}", flush=True)
            traceback.print_exc()
        finally:
            with _TT_LOCK:
                _TT_INFLIGHT.discard(mid)

    threading.Thread(target=_work, daemon=True, name=f"tt-{mid}").start()
    return jsonify({"ok": True, "status": "rendering", "mesh_id": mid,
                    "owner": owner, "url": None,
                    "note": "first render takes a minute — poll this endpoint"})


@app.get("/api/meshes/<mid>/products")
def mesh_products(mid: str):
    with db.connect() as c:
        mesh = db.get_mesh(c, mid)
        if mesh is None:
            return _err("no such mesh", 404)
        products = db.products_for(c, mid)
        # ── the inheritance guarantee (docs/foundation.md): a product added
        # to config.PRODUCTS *after* this mesh was made must appear on it
        # without a re-sculpt. bind_products is idempotent, so this is a
        # cheap set-difference on every read.
        bound = {p.get("product") for p in products}
        missing = [k for k in config.PRODUCTS if k not in bound]
        if missing:
            db.bind_products(c, mid, missing)
            products = db.products_for(c, mid)
        # drop bindings whose product left the config (renames/removals)
        products = [p for p in products if p.get("product") in config.PRODUCTS]
    products = [dict(p, section=config.SECTION_OF.get(p.get("product", ""), ""))
                for p in products]
    return jsonify({"ok": True, "mesh_id": mid, "products": products,
                    "source_glb": mesh["glb_key"]})


@app.get("/api/sections")
def sections():
    """Section registry: the rail, the shop chips, host->section routing.

    docs/navigation.md is the architecture note; config.SECTIONS is the truth.
    """
    return jsonify({"ok": True, "sections": config.SECTIONS,
                    "section_of": config.SECTION_OF,
                    "host_section": {s["host"]: s["id"]
                                     for s in config.SECTIONS if s["host"]}})


@app.get("/api/brand")
def brand():
    """Brand record for this request's Host (multi-brand seam).

    Same app serves oddhobb.com, ochema.co, pog.pet — the frontend asks here
    on boot and paints brand strings from the answer instead of hardcoding
    them. Unknown hosts fall back to the default brand, never an error.
    """
    return jsonify({"ok": True, **config.brand_for(request.host)})


@app.get("/api/catalog")
def catalog():
    """Unified product catalog — the single registry the site cards, the shop
    grid and MCP's figg_catalog all read (docs/foundation.md)."""
    rows = []
    for pid, spec in config.PRODUCTS.items():
        rows.append({
            "id": pid, "label": spec["label"], "price_cents": spec["price_cents"],
            "free": spec.get("free", False), "source": spec.get("source", "local"),
            "section": config.SECTION_OF.get(pid, ""), "preview": "mesh",
            "emoji": config.PRODUCT_EMOJI.get(pid, "\U0001f381"),
            "blurb": config.PRODUCT_BLURB.get(pid, ""),
        })
    for pid, spec in config.PRODIGI_PRODUCTS.items():
        rows.append({
            "id": pid, "label": spec["label"], "price_cents": spec["price_cents"],
            "free": spec.get("free", False), "source": "prodigi",
            "section": config.SECTION_OF.get(pid, ""), "preview": "prodigi",
            "emoji": config.SHAPE_EMOJI.get(spec.get("shape", ""), "\U0001f381"),
            "blurb": spec.get("sku_note", ""),
        })
    return jsonify({"ok": True, "products": rows, "count": len(rows),
                    "sections": config.SECTIONS})


def _public_base() -> str:
    """Feed/product URLs follow the request host when it is a known brand."""
    host = (request.host or "").split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]
    if host in config.BRANDS or any(host.endswith(d) for d in config.BRANDS):
        return f"https://{host}"
    return config.PUBLIC_BASE


def _feed_items():
    """Canonical product renders for shopping agents.

    Renders come from anon's seeded sample mesh — the same images the shop
    shows — mirrored into the public /img/ dir. Returns (items, failed).
    """
    owner = "anon"
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        pogs = db.pogs_for(c, owner)
        active = prof.get("active_mesh_id") or ""
        if not active:
            ok = next((p for p in pogs if p["status"] == "succeeded"), None)
            active = ok["id"] if ok else ""
        if not active:
            return None, "no canonical renders yet — seed the sample mesh first"
        mesh = db.get_mesh(c, active)
        photo = db.get_photo(c, mesh["photo_id"]) if mesh else None
    if mesh is None:
        return None, "active mesh missing"
    src_path, _ = _product_src(owner, active, mesh, photo)
    short = active.replace("msh_", "")[:8]
    try:
        have = storage.list_keys(f"owners/{storage._slug(owner)}/products/")
    except storage.StorageError:
        have = set()
    items, failed = [], {}
    for pid, spec in config.PRODIGI_PRODUCTS.items():
        try:
            key, fname, _ = _ensure_mockup(
                owner, short, pid, spec, src_path, None, "", have)
            public = _public_product_image(key, fname)
        except FileNotFoundError:
            failed[pid] = "no source image"
            continue
        except Exception as e:
            failed[pid] = f"{type(e).__name__}: {e}"
            continue
        section = config.SECTION_OF.get(pid, "")
        host = next((s["host"] for s in config.SECTIONS
                     if s["id"] == section and s.get("host")), "")
        seo = config.SEO.get(pid, {})
        qa = seo.get("qa") or []
        qa_flat = "; ".join(f"Q: {q} A: {a}" for q, a in qa)
        desc = (
            f"{spec['label']} — {spec.get('sku_note', 'personalised pet product')}. "
            f"Personalised with your pet's photo."
        )
        if seo.get("highlight"):
            desc += f" Highlights: {seo['highlight']}."
        if seo.get("details"):
            desc += f" Details: {seo['details']}."
        if qa_flat:
            desc += f" FAQ: {qa_flat}"
        items.append({
            "id": pid, "title": spec["label"],
            "description": desc,
            "link": f"https://{host}/" if host else _public_base() + "/",
            "image_url": public,
            "price_cents": spec["price_cents"],
            "section": section,
            # 8 AI attributes (docs/seo.md) — feeds + /api/seo/products.json
            "product_highlight": seo.get("highlight", ""),
            "product_detail": seo.get("details", ""),
            "variant_option": seo.get("variants", ""),
            "item_group_title": seo.get("item_group", ""),
            "related_products": seo.get("related", ""),
            "question_and_answer": qa_flat,
            "document_link": ";".join(
                f"{_public_base()}{d}" for d in seo.get("docs", [])),
            "availability": "in_stock",
            "brand": "OddHobb",
            "product_type": section or "gifts",
            "qa": [{"question": q, "answer": a} for q, a in qa],
            "docs": seo.get("docs", []),
        })
    return items, failed


@app.get("/api/feeds/google.xml")
def feed_google():
    """Google Merchant Center feed (RSS 2.0 + g: namespace).

    Public (ungated at the bridge) so Google/Pinterest fetch it directly.
    Prices are GBP; EST grade matches what the storefront shows.
    """
    from xml.sax.saxutils import escape
    items, failed = _feed_items()
    if items is None:
        return Response(failed, status=503, content_type="text/plain")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0"><channel>',
           f"<title>OddHobb</title><link>{_public_base()}/</link>"
           "<description>Personalised pet products — rendered with your pet.</description>"]
    for it in items:
        price = f"{it['price_cents']/100:.2f} GBP"
        out.append("<item>" + "".join([
            f"<g:id>{escape(it['id'])}</g:id>",
            f"<title>{escape(it['title'])}</title>",
            f"<description>{escape(it['description'])}</description>",
            f"<link>{escape(it['link'])}</link>",
            f"<g:image_link>{escape(it['image_url'])}</g:image_link>",
            f"<g:price>{price}</g:price>",
            "<g:availability>in_stock</g:availability>",
            "<g:brand>OddHobb</g:brand>",
            "<g:condition>new</g:condition>",
            f"<g:product_type>{escape(it.get('product_type') or 'gifts')}</g:product_type>",
            f"<g:item_group_id>{escape(it.get('item_group_title') or it['id'])}</g:item_group_id>",
            f"<g:custom_label_0>{escape(it.get('product_highlight') or '')}</g:custom_label_0>",
            f"<g:custom_label_1>{escape(it.get('product_detail') or '')}</g:custom_label_1>",
            f"<g:custom_label_2>{escape(it.get('variant_option') or '')}</g:custom_label_2>",
            f"<g:custom_label_3>{escape(it.get('related_products') or '')}</g:custom_label_3>",
        ]) + "</item>")
    out.append("</channel></rss>")
    return Response("\n".join(out), content_type="application/rss+xml")


@app.get("/api/feeds/shopify.json")
def feed_shopify():
    """Shopify storefront-shaped feed (mirrors /products.json).

    Same canonical renders as the Google feed, so a Shopify-side agent or
    import reads identical products, prices and images.
    """
    items, failed = _feed_items()
    if items is None:
        return jsonify({"ok": False, "error": failed}), 503
    products = []
    for it in items:
        qa_html = "".join(
            f"<p><strong>Q:</strong> {qa['question']}</p>"
            f"<p><strong>A:</strong> {qa['answer']}</p>"
            for qa in it.get("qa") or [])
        body = (
            f"<p>{it['description']}</p>"
            + (f"<p><strong>Highlights:</strong> {it['product_highlight']}</p>"
               if it.get("product_highlight") else "")
            + (f"<p><strong>Details:</strong> {it['product_detail']}</p>"
               if it.get("product_detail") else "")
            + (f"<div><h3>Questions &amp; answers</h3>{qa_html}</div>" if qa_html else "")
        )
        tags = [t for t in [
            it.get("section") or "",
            it.get("item_group_title") or "",
            "personalised", "pet", "oddhobb",
        ] if t]
        products.append({
            "id": it["id"],
            "title": it["title"],
            "handle": it["id"].replace("_", "-"),
            "body_html": body,
            "vendor": "OddHobb",
            "product_type": it.get("product_type") or it["section"] or "gifts",
            "tags": tags,
            "variants": [{"price": f"{it['price_cents']/100:.2f}",
                          "sku": it["id"], "available": True}],
            "images": [{"src": it["image_url"]}],
            "seo": {
                "product_highlight": it.get("product_highlight", ""),
                "product_detail": it.get("product_detail", ""),
                "variant_option": it.get("variant_option", ""),
                "item_group_title": it.get("item_group_title", ""),
                "related_products": it.get("related_products", ""),
                "question_and_answer": it.get("question_and_answer", ""),
                "document_link": it.get("document_link", ""),
            },
        })
    return jsonify({"products": products})


@app.get("/api/seo/products.json")
def seo_products():
    """Full 8-attribute AI pack for every catalogue product (public)."""
    items, failed = _feed_items()
    if items is None:
        return jsonify({"ok": False, "error": failed}), 503
    return jsonify({
        "ok": True,
        "brand": "OddHobb",
        "base": _public_base(),
        "count": len(items),
        "failed": failed,
        "products": items,
        "note": "8 Google AI attributes per product — see docs/seo.md",
    })


@app.get("/api/seo/faq.json")
def seo_faq():
    """Flat Q&A pairs for conversational AI (public)."""
    items, failed = _feed_items()
    if items is None:
        return jsonify({"ok": False, "error": failed}), 503
    pairs = []
    for it in items:
        for qa in it.get("qa") or []:
            pairs.append({
                "product": it["id"],
                "title": it["title"],
                "question": qa["question"],
                "answer": qa["answer"],
            })
    return jsonify({"ok": True, "count": len(pairs), "pairs": pairs})


@app.get("/guides/<pid>")
def guide_page(pid: str):
    """Crawlable companion guide per product + Product/FAQPage JSON-LD."""
    import json as _json
    from xml.sax.saxutils import escape
    seo = config.SEO.get(pid)
    spec = config.PRODIGI_PRODUCTS.get(pid) or config.PRODUCTS.get(pid)
    if not seo or not spec:
        return _err("no guide for that product", 404)
    label = spec.get("label", pid)
    price = spec.get("price_cents", 0) / 100.0
    qa_html = "".join(
        f"<h3>{escape(q)}</h3><p>{escape(a)}</p>" for q, a in seo.get("qa", []))
    highlights = [h.strip() for h in (seo.get("highlight") or "").split(";") if h.strip()]
    details = [d.strip() for d in (seo.get("details") or "").split("|") if d.strip()]
    faq_ld = ",".join(
        '{"@type":"Question","name":%s,"acceptedAnswer":{"@type":"Answer","text":%s}}'
        % (_json.dumps(q), _json.dumps(a)) for q, a in seo.get("qa", [])[:12])
    product_ld = _json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": label,
        "description": seo.get("highlight") or f"Personalised {label.lower()} from OddHobb",
        "brand": {"@type": "Brand", "name": "OddHobb"},
        "material": (details[0].split(":", 1)[-1].strip() if details else "see specs"),
        "url": f"{_public_base()}/guides/{pid}",
        "offers": {
            "@type": "Offer",
            "price": f"{price:.2f}",
            "priceCurrency": "GBP",
            "availability": "https://schema.org/InStock",
        },
    })
    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(label)} — guide | OddHobb</title>
<meta name="description" content="Buyer guide for the OddHobb personalised {escape(label.lower())}: highlights, specs, shipping and FAQ.">
<link rel="canonical" href="{_public_base()}/guides/{escape(pid)}">
<script type="application/ld+json">{product_ld}</script>
<script type="application/ld+json">{{
  "@context": "https://schema.org", "@type": "FAQPage",
  "mainEntity": [{faq_ld}]
}}</script>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.6rem}} h2{{margin-top:1.5rem}} li{{margin:.25rem 0}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:.4rem .6rem;text-align:left}}</style>
</head><body>
<p><a href="/">OddHobb</a> / guide</p>
<h1>{escape(label)} — buyer guide</h1>
<p><strong>Definition.</strong> Personalised {escape(label.lower())} from OddHobb: upload one pet photo; we render a 3D character and print it on this product.</p>
<h2>Highlights</h2><ul>{''.join(f'<li>{escape(h)}</li>' for h in highlights) or '<li>Personalised with your pet photo</li>'}</ul>
<h2>Specifications</h2><ul>{''.join(f'<li>{escape(d)}</li>' for d in details) or '<li>See product page</li>'}</ul>
<h2>Shipping</h2><p>1–3 business days production, 5–10 days worldwide shipping.</p>
<h2>Questions &amp; answers</h2>{qa_html or '<p>See the product page for FAQ.</p>'}
<h2>Related</h2><p>{escape(seo.get("related") or "Other personalised pet products")}</p>
<p><a href="/">Back to the shop</a> · <a href="/learn/">Buyer guides &amp; comparisons</a> · <a href="/api/seo/products.json">Product data for AI</a></p>
</body></html>"""
    return Response(html, content_type="text/html; charset=utf-8")


@app.get("/learn/")
def learn_index():
    """GEO content hub — definitions and comparisons for AI crawlers."""
    from xml.sax.saxutils import escape
    cards = "".join(
        f'<li><a href="/learn/{escape(slug)}">{escape(pg["title"])}</a></li>'
        for slug, pg in sorted(config.GEO_PAGES.items()))
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learn — personalised pet products | OddHobb</title>
<meta name="description" content="Definitions, comparisons and how-tos for personalised pet products from OddHobb.">
<link rel="canonical" href="{_public_base()}/learn/">
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.6rem}} li{{margin:.4rem 0}}</style>
</head><body>
<p><a href="/">OddHobb</a> / learn</p>
<h1>Learn — personalised pet products</h1>
<p>OddHobb turns one pet photo into a 3D character, then prints that character on cards, prints, mugs, puzzles, figurines and videos. These pages are written for people and AI assistants alike.</p>
<h2>Guides &amp; comparisons</h2>
<ul>{cards}</ul>
<p><a href="/api/seo/products.json">Product data (JSON)</a> · <a href="/api/seo/faq.json">Q&amp;A pairs</a> · <a href="/api/companygraph">Company graph</a></p>
</body></html>"""
    return Response(html, content_type="text/html; charset=utf-8")


@app.get("/learn/<slug>")
def learn_page(slug: str):
    """GEO definition / comparison page with Article + optional table markup."""
    import json as _json
    from xml.sax.saxutils import escape
    pg = config.GEO_PAGES.get(slug)
    if not pg:
        return _err("no learn page for that slug", 404)
    title = pg["title"]
    definition = pg["definition"]
    sections_html = []
    for head, body in pg.get("sections", []):
        if body == "table" and pg.get("comparison"):
            cmp = pg["comparison"]
            th = "".join(f"<th>{escape(c)}</th>" for c in cmp["headers"])
            rows = "".join(
                "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>"
                for row in cmp["rows"])
            sections_html.append(
                f"<h2>{escape(head)}</h2>"
                f"<table><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table>")
        else:
            sections_html.append(f"<h2>{escape(head)}</h2><p>{escape(body)}</p>")
    article_ld = _json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": definition[:200],
        "author": {"@type": "Organization", "name": "OddHobb"},
        "publisher": {"@type": "Organization", "name": "OddHobb"},
        "url": f"{_public_base()}/learn/{slug}",
    })
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | OddHobb</title>
<meta name="description" content="{escape(definition[:155])}">
<link rel="canonical" href="{_public_base()}/learn/{escape(slug)}">
<script type="application/ld+json">{article_ld}</script>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:42rem;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.6rem}} h2{{margin-top:1.4rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:.4rem .6rem;text-align:left}}</style>
</head><body>
<p><a href="/">OddHobb</a> / <a href="/learn/">learn</a></p>
<h1>{escape(title)}</h1>
<p><strong>Definition.</strong> {escape(definition)}</p>
{''.join(sections_html)}
<p><a href="/">Shop personalised pet products</a> · <a href="/api/seo/faq.json">Q&amp;A data</a></p>
</body></html>"""
    return Response(html, content_type="text/html; charset=utf-8")


@app.get("/sitemap.xml")
def sitemap():
    """Simple sitemap — shop, learn, guides, feeds (AI crawler discovery)."""
    from xml.sax.saxutils import escape
    base = _public_base()
    urls = ["/", "/learn/", "/llms.txt", "/api/seo/products.json",
            "/api/seo/faq.json", "/api/companygraph"]
    urls += [f"/learn/{s}" for s in sorted(config.GEO_PAGES)]
    urls += [f"/guides/{p}" for p in sorted(config.SEO)]
    urls += ["/backend/api/feeds/google.xml", "/backend/api/feeds/shopify.json"]
    locs = "".join(f"<url><loc>{escape(base + u)}</loc></url>" for u in urls)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')
    return Response(xml, content_type="application/xml")


@app.get("/api/companygraph")
def companygraph():
    """OddHobb CompanyGraph — FACTS / RESOURCES / CAPABILITIES (public).

    Pattern: agentcom/companygraph. bobdod is the helper agent identity
    customers and MCP clients meet. Products/policies derive from live
    config so the graph never drifts from the catalog.
    """
    return jsonify({"ok": True, **config.company_graph()})


@app.get("/api/flow")
def flow():
    """Upload -> mesh -> previews in ONE call: the state a flow driver needs.

    stage: empty (no photos) -> uploaded (photo, no mesh yet) ->
           sculpting (a mesh queued/running) -> ready (an active mesh succeeded)
    """
    owner = (request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        # photos have no status column (schema: id,owner,sha256,r2_key,mime,
        # width,height,bytes,orig_name,created_at) — presence IS the state.
        photos = []
        for r in c.execute(
                "SELECT id,mime,width,height,created_at,r2_key,person,orig_name"
                " FROM photos WHERE owner=?"
                " ORDER BY created_at DESC LIMIT 48", (owner,)):
            key = r["r2_key"] or ""
            # Normalise to owners/<owner>/… for the artifacts gateway
            if key and not key.startswith("owners/"):
                key = f"owners/{owner}/{key}"
            photos.append({
                "id": r["id"], "mime": r["mime"],
                "size": [r["width"], r["height"]],
                "created_at": r["created_at"],
                "r2_key": key,
                "person": r["person"] or "",
                "orig_name": r["orig_name"] or "",
            })
        pogs = db.pogs_for(c, owner)
        prof = db.get_profile(c, owner)
    active = prof.get("active_mesh_id") or next(
        (p["id"] for p in pogs if p.get("status") == "succeeded"), "")
    active_row = next((p for p in pogs if p["id"] == active), None) or {}
    statuses = {p.get("status") for p in pogs}
    if statuses & {"queued", "running"}:
        stage = "sculpting"
    elif active_row.get("status") == "succeeded":
        stage = "ready"
    elif photos:
        stage = "uploaded"
    else:
        stage = "empty"
    return jsonify({
        "ok": True, "owner": owner, "stage": stage,
        "photos": photos, "meshes": pogs,
        "active_mesh_id": active,
        "active": {k: active_row.get(k) for k in
                   ("id", "status", "stub", "glb_key", "created_at")},
        "catalog_count": len(config.PRODUCTS) + len(config.PRODIGI_PRODUCTS),
        "hint": {
            "empty": "Upload a photo to start.",
            "uploaded": "Sculpt it — that unlocks every preview.",
            "sculpting": "Sculpting… previews unlock when the mesh lands.",
            "ready": "Ready — every product below previews against this mesh.",
        }[stage],
    })


def _dhash(img) -> int:
    """64-bit difference hash: 9x8 grayscale, bit = left pixel > right pixel."""
    g = img.convert("L").resize((9, 8), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return bits


@app.post("/api/photos/autosort")
def photos_autosort():
    """Group an owner's uploads into *people* by perceptual similarity.

    v1 = difference-hash clustering (free, local, PIL-only): near-identical
    photos of the same subject land in the same group and get an auto label
    ("Person 1"…). Groups come back `needs_name` so the UI can ask
    "who's this?" — the answer goes to POST /api/people/rename and sticks to
    the profile (custom gifting seed).
    """
    owner = (request.args.get("owner") or request.form.get("owner")
             or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id,sha256,r2_key,person,mime FROM photos WHERE owner=?"
            " ORDER BY created_at", (owner,))]
    if not rows:
        return jsonify({"ok": True, "owner": owner, "groups": [], "count": 0})

    def pixel_hash(r):
        path = config.LOCAL_TMP / f"ph_{r['sha256'][:40]}.img"
        if not path.exists():
            try:
                storage.get(r["r2_key"], path)
            except storage.StorageError:
                return None
        try:
            return _dhash(Image.open(path))
        except Exception:  # noqa: BLE001
            return None

    hs = [pixel_hash(r) for r in rows]
    # union-find with hamming <= 12 (same subject, different crops/lighting)
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if hs[i] is None or hs[j] is None:
                continue
            if (hs[i] ^ hs[j]).bit_count() <= 12:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj

    clusters: dict[int, list[int]] = {}
    for i in range(len(rows)):
        clusters.setdefault(find(i), []).append(i)

    # label: keep existing person labels; auto-label the rest
    auto_n = 0
    groups = []
    with db.connect() as c:
        mesh_by_photo = {r["photo_id"]: r["id"] for r in c.execute(
            "SELECT id, photo_id FROM meshes WHERE photo_id IS NOT NULL")}
        for members in clusters.values():
            persons = {rows[i]["person"] for i in members if rows[i]["person"]}
            if persons:
                label = sorted(persons)[0]
                needs_name = False
            else:
                auto_n += 1
                label = f"Person {auto_n}"
                needs_name = True
                for i in members:
                    c.execute("UPDATE photos SET person=? WHERE id=?",
                              (label, rows[i]["id"]))
            groups.append({
                "person": label, "needs_name": needs_name,
                "photos": [{"id": rows[i]["id"], "mime": rows[i]["mime"],
                            "r2_key": rows[i]["r2_key"],
                            "has_mesh": rows[i]["id"] in mesh_by_photo,
                            "mesh_id": mesh_by_photo.get(rows[i]["id"])}
                           for i in members],
            })
    groups.sort(key=lambda g: g["person"])
    return jsonify({"ok": True, "owner": owner, "groups": groups,
                    "count": len(rows)})


@app.post("/api/people/rename")
def people_rename():
    """Rename a group: "who's this?" -> name, saved against the profile.

    Renames every photo carrying the old label, so the whole cluster follows.
    """
    b = request.get_json(silent=True) or {}
    owner = (b.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    old = str(b.get("from") or "").strip()[:60]
    new = str(b.get("to") or "").strip()[:60]
    if not old or not new:
        return _err("from and to are required", 400)
    with db.connect() as c:
        n = c.execute(
            "UPDATE photos SET person=? WHERE owner=? AND person=?",
            (new, owner, old)).rowcount
    return jsonify({"ok": True, "owner": owner, "renamed": n,
                    "person": new})


@app.get("/api/credits")
def credits():
    """Free-tier balance for an owner: what's left today."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    day = datetime.now(timezone.utc).date().isoformat()
    with db.connect() as c:
        status = db.credit_status(c, owner, day)
        storage_used = 0
        try:
            storage_used = len(storage.list_owner(owner))
        except storage.StorageError:
            pass
    return jsonify({"ok": True, "owner": owner, "day": day,
                    "credits": status, "assets_stored": storage_used,
                    "watermark_free": config.WATERMARK_FREE})


def _api_key() -> str:
    k = request.headers.get("X-API-Key", "").strip()
    if not k:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            k = auth[7:].strip()
    return k or request.args.get("api_key", "").strip()


def _caller(owner_arg: str = "") -> tuple[str, bool]:
    """Resolve who is asking.

    A valid API key always wins over an explicit `owner=` so an agent can't
    act as someone else just by passing a different owner string. A key that
    doesn't match anyone is refused rather than falling back to `owner=`.
    """
    key = _api_key()
    if key:
        with db.connect() as c:
            u = db.get_user_by_api_key(c, key)
        return (u["handle"], True) if u else ("", False)
    return (owner_arg or "anon").strip()[:80], False


# ── accounts ────────────────────────────────────────────────────────

@app.post("/api/accounts")
def create_account():
    """Create an account. `handle` becomes the owner of everything it makes.

    `claim_owner` adopts the anonymous profile currently in the caller's
    localStorage, so no meshes are lost when they sign up.
    """
    b = request.get_json(silent=True) or {}
    handle = (b.get("handle") or "").strip()
    password = str(b.get("password") or "")
    if not handle:
        return _err("handle is required", 400)
    if password and len(password) < 8:
        return _err("password needs at least 8 characters", 400)
    ip = (request.remote_addr or "anon").strip()[:64]
    if not _auth_rate("signup", ip):
        return _err("too many account attempts — try again later", 429)
    claim = (b.get("claim_owner") or "").strip()

    try:
        with db.connect() as c:
            user = db.create_user(c, handle, password,
                                  email=str(b.get("email") or ""),
                                  display_name=str(b.get("display_name") or ""))
            claimed = {}
            if claim and claim != user["handle"]:
                claimed = db.claim_assets(c, claim, user["handle"])
                prof = db.get_profile(c, claim)
                if prof.get("active_mesh_id"):
                    db.set_active(c, user["handle"], prof["active_mesh_id"])
            db.set_active(c, user["handle"],
                          db.get_profile(c, user["handle"]).get("active_mesh_id") or "")
    except ValueError as e:
        return _err(str(e), 409)
    except Exception as e:
        return _err(f"could not create account: {str(e)[:200]}", 500)

    if claim:
        try:
            storage.claim_owner(claim, user["handle"])
        except Exception:
            pass   # rows keep their old keys, which still resolve

    return jsonify({"ok": True, "handle": user["handle"],
                    "api_key": user["api_key"],        # shown once
                    "password_set": bool(password),
                    "claimed_from": claim or None,
                    "claimed": claimed,
                    "note": "api_key is shown once — store it now"})


@app.post("/api/accounts/login")
def login():
    b = request.get_json(silent=True) or {}
    handle = (b.get("handle") or "").strip()
    password = str(b.get("password") or "")
    ip = (request.remote_addr or "anon").strip()[:64]
    if not _auth_rate("login", f"{ip}:{handle.lower()}"):
        return _err("too many sign-in attempts — try again later", 429)
    with db.connect() as c:
        u = db.get_user_by_handle(c, handle)
        if not u or not u["password_hash"] or not db.verify_password(password, u["password_hash"]):
            return _err("wrong handle or password", 401)
        c.execute("UPDATE users SET last_login=? WHERE id=?", (db.now(), u["id"]))
        prof = db.get_profile(c, u["handle"])
        pogs = db.pogs_for(c, u["handle"])
        credits = db.credit_status(c, u["handle"],
                                   datetime.now(timezone.utc).date().isoformat())
    _auth_rate_reset("login", f"{ip}:{handle.lower()}")
    return jsonify({"ok": True, "handle": u["handle"],
                    "display_name": u["display_name"], "api_key": u["api_key"],
                    "active_mesh_id": prof.get("active_mesh_id", ""),
                    "pogs": len(pogs), "credits": credits})


@app.get("/api/accounts/me")
def account_me():
    handle, authed = _caller(request.args.get("owner", ""))
    if not authed:
        return _err("API key required — X-API-Key or Authorization: Bearer", 401)
    with db.connect() as c:
        u = db.get_user_by_handle(c, handle)
        prof = db.get_profile(c, handle)
        pogs = db.pogs_for(c, handle)
        credits = db.credit_status(c, handle,
                                   datetime.now(timezone.utc).date().isoformat())
        key = (u or {}).get("api_key", "")
    masked = (key[:9] + "…" + key[-4:]) if len(key) > 14 else ""
    return jsonify({"ok": True, "handle": handle,
                    "display_name": (u or {}).get("display_name", ""),
                    "email": (u or {}).get("email", ""),
                    "created_at": (u or {}).get("created_at", 0),
                    "api_key_masked": masked,
                    "active_mesh_id": prof.get("active_mesh_id", ""),
                    "pogs": [{"mesh_id": p["id"], "status": p["status"]} for p in pogs],
                    "credits": credits})


# ── delegated agents ────────────────────────────────────────────────

def _principal() -> tuple[str, str, list[str]]:
    """Who is calling: (handle, kind, permissions).

    kind is 'user' (full rights, own assets) or 'agent' (only the granted
    subset, assets land under the agent's own handle — own profile, no wallet).
    """
    key = _api_key()
    if not key:
        return ("", "anon", [])
    with db.connect() as c:
        a = db.get_agent_by_key(c, key)
        if a:
            if a["status"] != "active":
                return ("", "revoked", [])
            db.touch_agent(c, a["id"])
            return (a["agent_handle"], "agent", db.agent_perms(a))
        u = db.get_user_by_api_key(c, key)
        if u:
            return (u["handle"], "user", list(config.AGENT_PERMISSIONS))
    return ("", "anon", [])


def _require(permission: str) -> tuple[bool, tuple[str, str, list[str]]]:
    """Gate a mutating call. Users pass; agents need the grant."""
    h, kind, perms = _principal()
    if kind == "user":
        return True, (h, kind, perms)
    if kind == "agent" and permission in perms:
        return True, (h, kind, perms)
    if kind == "revoked":
        return False, ("", kind, [])
    return False, (h, kind, perms)


@app.post("/api/agents")
def mint_agent():
    """Give an agent its own credential under your account.

    It gets its own handle/profile/meshes. You keep the wallet and can revoke.
    """
    h, kind, _ = _principal()
    if kind != "user":
        return _err("only a signed-in account can mint agents (use your API key)", 403)
    b = request.get_json(silent=True) or {}
    name = (b.get("name") or "").strip()
    if not name:
        return _err("name is required", 400)
    perms = b.get("permissions")
    if not isinstance(perms, list):
        perms = config.DEFAULT_AGENT_PERMISSIONS
    unknown = [p for p in perms if p not in config.AGENT_PERMISSIONS]
    if unknown:
        return _err(f"unknown permissions: {', '.join(unknown)}", 400)
    try:
        with db.connect() as c:
            ag = db.create_agent(c, h, name, perms)
    except Exception as e:
        return _err(f"could not mint agent: {str(e)[:200]}", 500)
    return jsonify({"ok": True, "agent": _agent_out(ag),
                    "note": "agent_api_key is shown once — paste it into your connector"})


@app.get("/api/agents")
def list_agents_route():
    h, kind, _ = _principal()
    if kind != "user":
        return _err("your API key is required", 403)
    with db.connect() as c:
        rows = db.list_agents(c, h)
    return jsonify({"ok": True, "parent": h,
                    "agents": [_agent_out(a, with_key=False) for a in rows],
                    "count": len(rows),
                    "available_permissions": config.AGENT_PERMISSIONS})


@app.post("/api/agents/<aid>/permissions")
def update_agent_perms(aid: str):
    h, kind, _ = _principal()
    if kind != "user":
        return _err("your API key is required", 403)
    b = request.get_json(silent=True) or {}
    perms = b.get("permissions")
    if not isinstance(perms, list):
        return _err("permissions must be a list", 400)
    with db.connect() as c:
        ag = db.get_agent(c, aid)
        if not ag or ag["parent_handle"] != h:
            return _err("no such agent on your account", 404)
        db.set_agent_permissions(c, aid, perms)
        ag = db.get_agent(c, aid)
    return jsonify({"ok": True, "agent": _agent_out(ag, with_key=False)})


@app.post("/api/agents/<aid>/revoke")
def revoke_agent(aid: str):
    h, kind, _ = _principal()
    if kind != "user":
        return _err("your API key is required", 403)
    with db.connect() as c:
        ag = db.get_agent(c, aid)
        if not ag or ag["parent_handle"] != h:
            return _err("no such agent on your account", 404)
        db.set_agent_status(c, aid, "revoked")
        ag = db.get_agent(c, aid)
    return jsonify({"ok": True, "agent": _agent_out(ag, with_key=False),
                    "status": "revoked"})


@app.get("/api/agents/me")
def agent_me():
    h, kind, perms = _principal()
    if kind == "revoked":
        return _err("this agent key has been revoked", 401)
    if kind == "anon":
        return _err("API key required", 401)
    with db.connect() as c:
        prof = db.get_profile(c, h)
        pogs = db.pogs_for(c, h)
        parent = ""
        if kind == "agent":
            a = c.execute("SELECT parent_handle FROM agents WHERE agent_handle=?",
                          (h,)).fetchone()
            parent = a["parent_handle"] if a else ""
    return jsonify({"ok": True, "handle": h, "kind": kind, "parent": parent,
                    "permissions": perms,
                    "active_mesh_id": prof.get("active_mesh_id", ""),
                    "pogs": len(pogs)})


def _agent_out(a: dict, with_key: bool = True) -> dict:
    out = {"id": a["id"], "name": a["name"], "handle": a["agent_handle"],
           "parent": a["parent_handle"], "status": a["status"],
           "permissions": db.agent_perms(a),
           "created_at": a["created_at"], "last_used": a["last_used"]}
    if with_key:
        out["agent_api_key"] = a["api_key"]
    return out


# ── google sign-in ──────────────────────────────────────────────────

_OAUTH_STATE: dict[str, float] = {}   # state -> created_at, single process


def _ensure_google_user(profile: dict) -> dict:
    """Find the account for this Google identity, creating one if new."""
    email = (profile.get("email") or "").lower().strip()
    name = (profile.get("name") or "").strip()
    with db.connect() as c:
        if email:
            row = c.execute("SELECT * FROM users WHERE lower(email)=? AND email<>''",
                            (email,)).fetchone()
            if row:
                u = dict(row)
                if name and not u["display_name"]:
                    c.execute("UPDATE users SET display_name=? WHERE id=?", (name, u["id"]))
                return u
        base = gauth.handle_from(profile)
        handle, n = base, 1
        while True:
            try:
                return db.create_user(c, handle, "", email=email, display_name=name)
            except ValueError:
                n += 1
                handle = f"{base}{n}"[:32]
                if n > 50:
                    raise


@app.get("/api/auth/google/start")
def google_start():
    """302 to Google. Frontend hits this directly (a link or window.open)."""
    if not gauth.configured():
        return jsonify({"ok": False, "error": "Google sign-in not configured",
                        "fix": "set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
                        "redirect_uri": gauth.redirect_uri()}), 501
    st = gauth.make_state()
    _OAUTH_STATE[st] = time.time()
    # keep the dict from growing forever
    for k, t in list(_OAUTH_STATE.items()):
        if time.time() - t > 600:
            _OAUTH_STATE.pop(k, None)
    return redirect(gauth.authorize_url(st), code=302)


@app.get("/api/auth/google/callback")
def google_callback():
    code = request.args.get("code", "")
    st = request.args.get("state", "")
    if not code:
        return _err(f"google returned no code: {request.args.get('error', '')}", 400)
    if not _OAUTH_STATE.pop(st, None):
        return _err("bad or expired sign-in state — try again", 400)
    try:
        profile = gauth.exchange(code)
    except Exception as e:
        return _err(f"google sign-in failed: {str(e)[:250]}", 502)
    if not profile.get("email"):
        return _err("google did not return an email address", 403)
    try:
        user = _ensure_google_user(profile)
    except Exception as e:
        return _err(f"could not open an account: {str(e)[:250]}", 500)
    # hand the key back to the SPA, which stores it and strips it from the URL
    dest = f"{config.PUBLIC_BASE.rstrip('/')}/?auth={urllib.parse.quote(user['api_key'])}" \
           f"&handle={urllib.parse.quote(user['handle'])}"
    return redirect(dest, code=302)



@app.get("/api/concepts")
def concepts_route():
    """The 36-concept template library (wizard / mystic / christmas)."""
    try:
        from backend import concepts as lib
        items = lib.list_concepts()
    except Exception as e:
        return _err(f"catalog unavailable: {str(e)[:200]}", 500)
    worlds = sorted({c["world"] for c in items})
    cats = sorted({c["category"] for c in items})
    return jsonify({"ok": True, "count": len(items), "worlds": worlds,
                    "categories": cats, "items": items})



@app.get("/api/acts")
def acts_route():
    """Talent-show roster (vendored from freaktown) + the talents we can stage."""
    try:
        from backend import acts as lib
        return jsonify({"ok": True, "count": len(lib.list_acts()),
                        "acts": lib.list_acts(),
                        "talents": [{"key": k, "label": v["label"],
                                     "icon": v["icon"], "brief": v["brief"]}
                                    for k, v in lib.TALENTS.items()],
                        "source": "freaktown/comedians.py (vendored)"})
    except Exception as e:
        return _err(f"roster unavailable: {str(e)[:200]}", 500)



@app.get("/api/prodigi/check")
def prodigi_check():
    """Does this SKU exist? Returns its attribute schema (needed to quote)."""
    sku = (request.args.get("sku") or "").strip()
    if not sku:
        return _err("sku is required", 400)
    try:
        from backend import prodigi as pdi
        return jsonify({"ok": True, **pdi.check_sku(sku)})
    except Exception as e:
        return _err(str(e)[:300], 502)


@app.get("/api/prodigi/quote")
def prodigi_quote():
    """Live Prodigi price for a SKU. This is what flips a product off EST."""
    sku = (request.args.get("sku") or "").strip()
    if not sku:
        return _err("sku is required", 400)
    country = (request.args.get("country") or "GB").strip()[:2]
    try:
        import json as _json
        attrs = _json.loads(request.args.get("attrs") or "{}")
        from backend import prodigi as pdi
        q = pdi.quote(sku, country=country, attrs=attrs)
        q["price_cents_usd"] = pdi.to_cents(q["item"], q["currency"])
        return jsonify({"ok": True, **q})
    except Exception as e:
        return _err(str(e)[:300], 502)



@app.get("/api/meshes/<mid>/measure")
def mesh_measure(mid: str):
    """Geometry read-out: triangles, bbox, whether it's actually printable."""
    with db.connect() as c:
        mesh = db.get_mesh(c, mid)
    if mesh is None:
        return _err("no such mesh", 404)
    if not mesh["glb_key"]:
        return _err("this mesh has no GLB yet", 409)
    try:
        from backend import install, mesh_export as mx
        local = config.LOCAL_MESH / mid / "model.glb"
        if not local.exists():
            install.storage.get(mesh["glb_key"], local)
        return jsonify({"ok": True, "mesh_id": mid, **mx.measure(local)})
    except Exception as e:
        return _err(f"measure failed: {str(e)[:250]}", 500)


@app.get("/api/meshes/<mid>/print")
def mesh_print(mid: str):
    """Export a print file — GLB -> OBJ or STL, no Blender.

    Makr3D accepts STL/3MF/STEP/OBJ/ZIP, so this is a quotable print file.
    `height_mm` scales the model to a target print height (glTF units are m).
    """
    fmt = (request.args.get("format") or "stl").lower()
    if fmt not in ("obj", "stl"):
        return _err("format must be obj or stl", 400)
    try:
        height = float(request.args.get("height_mm") or 0) or None
    except ValueError:
        return _err("height_mm must be a number", 400)

    with db.connect() as c:
        mesh = db.get_mesh(c, mid)
    if mesh is None:
        return _err("no such mesh", 404)
    if not mesh["glb_key"]:
        return _err("this mesh has no GLB yet", 409)

    try:
        from backend import install, mesh_export as mx
        local = config.LOCAL_MESH / mid / "model.glb"
        if not local.exists():
            install.storage.get(mesh["glb_key"], local)
        out = config.LOCAL_MESH / mid / f"print.{fmt}"
        info = (mx.export_stl if fmt == "stl" else mx.export_obj)(local, out, height_mm=height)
        key = f"owners/{storage._slug(_owner_of_mesh(mid))}/meshes/{mid}/print.{fmt}"
        storage.put(out, key)
    except Exception as e:
        return _err(f"export failed: {str(e)[:250]}", 500)
    return jsonify({"ok": True, "mesh_id": mid, "format": fmt,
                    "url": storage.public_url(key), "height_mm": height,
                    "bytes": out.stat().st_size, **{k: v for k, v in info.items()
                                                    if isinstance(v, (int, float, str))}})


def _owner_of_mesh(mid: str) -> str:
    with db.connect() as c:
        row = c.execute(
            "SELECT p.owner FROM meshes m JOIN photos p ON p.id=m.photo_id WHERE m.id=?",
            (mid,)).fetchone()
    return row["owner"] if row else "anon"



@app.get("/api/listing-pack")
def listing_pack():
    """Everything needed to write an Etsy listing for the active pog:
    concept art direction, the 10-shot list, live/EST prices and the
    rendered mockups. `format=md` gives a paste-ready draft."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    concept_id = (request.args.get("concept") or "").strip()
    subject = (request.args.get("subject") or "").strip()[:40]
    fmt = (request.args.get("format") or "json").lower()

    try:
        from backend import concepts as lib
        plan = lib.compose_for(concept_id or "WZ-P1", subject=subject or "your pet")
    except Exception as e:
        return _err(f"concept error: {str(e)[:200]}", 400)

    with db.connect() as c:
        prof = db.get_profile(c, owner)
        active = prof.get("active_mesh_id") or ""
    # reuse the shop render so the pack carries the same art
    try:
        q = f"?owner={owner}&concept={plan['concept']['id']}&subject={subject}"
        if subject:
            pass
        resp = products.__wrapped__() if hasattr(products, "__wrapped__") else None
    except Exception:
        resp = None

    pack = {
        "ok": True, "owner": owner, "mesh_id": active,
        "concept": plan["concept"], "world": plan["world"],
        "accent": plan["accent"], "ar_effect": plan["ar_effect"],
        "names": plan["names"], "subject": plan["subject"],
        "design_prompt": plan["design_prompt"],
        "shot_list": plan["shot_list"],
        "guard": plan.get("guard"),
        "generated_at": db.now(),
    }
    if fmt == "md":
        c_ = plan["concept"]
        lines = [
            f"# {c_['name']} ({c_['id']}) — {plan['world']} world",
            "",
            f"**Scene:** {c_['scene']}",
            f"**Subjects:** {', '.join(plan['names'])}",
            f"**AR effect:** {plan['ar_effect'] or '—'}",
            f"**Identity meshes:** {c_.get('identity_meshes', 1)} (max 3)",
            "",
            "## Design prompt",
            "```", plan["design_prompt"], "```",
            "",
            "## Shot list",
        ]
        lines += [f"{s['slot']}. **{s['kind']}** — {s['desc']}" for s in plan["shot_list"]]
        if plan.get("guard"):
            lines += ["", f"> print guard: {plan['guard']}"]
        body = "\n".join(lines)
        return Response(body, content_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition":
                                 f'attachment; filename="listing-{c_["id"]}.md"'})
    return jsonify(pack)



@app.get("/api/meshes/<mid>/usdz")
def mesh_usdz(mid: str):
    """GLB -> USDZ: the iOS Quick Look AR asset. Needs the 4.2.9 Blender
    (the Ubuntu package has no USD libs) — usdz.py finds it."""
    with db.connect() as c:
        mesh = db.get_mesh(c, mid)
    if mesh is None:
        return _err("no such mesh", 404)
    if not mesh["glb_key"]:
        return _err("this mesh has no GLB yet", 409)
    key = f"owners/{storage._slug(_owner_of_mesh(mid))}/meshes/{mid}/model.usdz"
    try:
        if not storage.exists(key):
            from backend import install, usdz
            local = config.LOCAL_MESH / mid / "model.glb"
            if not local.exists():
                install.storage.get(mesh["glb_key"], local)
            out = config.LOCAL_MESH / mid / "model.usdz"
            usdz.to_usdz(local, out)
            storage.put(out, key)
    except Exception as e:
        return _err(f"usdz export failed: {str(e)[:300]}", 500)
    return jsonify({"ok": True, "mesh_id": mid, "url": storage.public_url(key),
                    "note": "set ios-src on <model-viewer> to enable AR on iOS"})


@app.get("/api/voices")




def voices():
    """Free voice library + scenes a free account can use."""
    return jsonify({"ok": True,
                    "voices": [{"key": k, "label": v["label"], "id": v["id"]}
                               for k, v in video.VOICES.items()],
                    "scenes": [{"key": k, "label": v, "free": True}
                               for k, v in config.SCENES.items()]})


@app.post("/api/videos")
def make_video():
    """The wedge: free talking/comedy video. Spends a video credit first."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    mesh_id = body.get("mesh_id") or ""
    talent = str(body.get("talent") or "comedy")
    act_slug = str(body.get("act") or "").strip()
    act, act_voice, act_premise = None, "", ""
    if act_slug:
        try:
            from backend import acts as lib
            act = lib.get_act(act_slug)
            if act:
                act_voice, act_premise = act.get("voice", ""), act.get("premise", "")
        except Exception:
            act = None
    # default the Perform flow onto the stage rather than the comedy club
    if talent != "comedy" and not body.get("scene"):
        body["scene"] = "stage"
    topic = (body.get("topic") or "").strip()
    if not topic:
        return _err("Give me one funny detail about them — that's the whole joke.", 400)
    if not mesh_id:
        return _err("mesh_id is required — generate their mesh first.", 400)

    day = datetime.now(timezone.utc).date().isoformat()
    with db.connect() as c:
        mesh = db.get_mesh(c, mesh_id)
        if mesh is None:
            return _err("no such mesh", 404)
        photo = db.get_photo(c, mesh["photo_id"])
        mesh_owner = (photo["owner"] if photo else "") or "anon"
        if mesh_owner != owner:
            return _err("that mesh belongs to someone else", 403)
        ok, used = db.spend_credit(c, owner, day, "video", config.FREE_DAILY["video"])
        if not ok:
            return _err(
                f"That's {config.FREE_DAILY['video']} free videos today — "
                "back tomorrow for more.", 429)
        photo_path = pipeline._local_photo(dict(photo)) if photo else None

    try:
        rec = video.make(
            topic=topic,
            pet_name=str(body.get("pet_name") or "your pet")[:40],
            scene=str(body.get("scene") or "comedy_show"),
            voice=str(body.get("voice") or act_voice or "ryan"),
            photo=photo_path,
            persona=(str(body.get("persona") or act_premise) or "")[:200],
            talent=talent,
            watermark=bool(body.get("watermark", config.WATERMARK_FREE)),
        )
    except video.VideoError as e:
        with db.connect() as c:
            db.refund_credit(c, owner, day, "video")
        return _err(str(e), e.code)
    except Exception as e:
        with db.connect() as c:
            db.refund_credit(c, owner, day, "video")
        return _err(f"render failed: {str(e)[:200]}", 500)

    vid = rec["video_id"]
    with db.connect() as c:
        c.execute(
            "INSERT INTO videos (id,owner,mesh_id,scene,talent,voice,pet_name,topic,"
            "script,lines,watermarked,duration,bytes,path,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vid, owner, mesh_id, rec["scene"], rec.get("talent", "comedy"),
             rec["voice"],
             str(body.get("pet_name") or "your pet")[:40], topic,
             rec["script"], json.dumps(rec["lines"]), 1 if rec["watermarked"] else 0,
             rec["duration"], rec["bytes"], rec["file"], db.now()),
        )
        left = config.FREE_DAILY["video"] - db.credit_used(c, owner, day, "video")

    return jsonify({"ok": True, "video": {**rec, "id": vid, "file": None},
                    "download": f"/api/videos/{vid}/file",
                    "credits_remaining": left,
                    "cost": 0})


@app.get("/api/videos/rooms")
def video_rooms():
    """Greeting room registry + which backdrops exist on disk."""
    return jsonify({"ok": True, "rooms": [
        {"id": rid, "label": r["label"], "blurb": r.get("blurb", ""),
         "backdrop": bool(video.room_backdrop(rid))}
        for rid, r in config.ROOMS.items()]})


@app.post("/api/videos/greeting")
def make_greeting_video():
    """Avatar greeting: verbatim message in a room. Same video quota."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    mesh_id = body.get("mesh_id") or ""
    message = (body.get("message") or "").strip()
    if not message:
        return _err("Give me the message — I speak exactly what you write.", 400)
    if not mesh_id:
        return _err("mesh_id is required — pick whose avatar speaks.", 400)

    day = datetime.now(timezone.utc).date().isoformat()
    with db.connect() as c:
        mesh = db.get_mesh(c, mesh_id)
        if mesh is None:
            return _err("no such mesh", 404)
        photo = db.get_photo(c, mesh["photo_id"])
        mesh_owner = (photo["owner"] if photo else "") or "anon"
        if mesh_owner != owner:
            return _err("that mesh belongs to someone else", 403)
        ok, used = db.spend_credit(c, owner, day, "video", config.FREE_DAILY["video"])
        if not ok:
            return _err(
                f"That's {config.FREE_DAILY['video']} free videos today — "
                "back tomorrow for more.", 429)
        photo_path = pipeline._local_photo(dict(photo)) if photo else None
        subject = db.get_subject_profile(c, owner, mesh_id)

    speaker = str(body.get("speaker_name")
                    or (subject.get("name") if subject else "")
                    or "Someone you love")[:40]
    try:
        rec = video.make_greeting(
            message=message,
            speaker_name=speaker,
            voice=str(body.get("voice") or "ryan"),
            room=str(body.get("room") or "void"),
            photo=photo_path,
            watermark=bool(body.get("watermark", config.WATERMARK_FREE)),
        )
    except video.VideoError as e:
        with db.connect() as c:
            db.refund_credit(c, owner, day, "video")
        return _err(str(e), e.code)
    except Exception as e:
        with db.connect() as c:
            db.refund_credit(c, owner, day, "video")
        return _err(f"render failed: {str(e)[:200]}", 500)

    vid = rec["video_id"]
    with db.connect() as c:
        c.execute(
            "INSERT INTO videos (id,owner,mesh_id,scene,talent,voice,pet_name,topic,"
            "script,lines,watermarked,duration,bytes,path,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vid, owner, mesh_id, rec["scene"], "greeting", rec["voice"],
             speaker, message,
             rec["script"], json.dumps(rec["lines"]), 1 if rec["watermarked"] else 0,
             rec["duration"], rec["bytes"], rec["file"], db.now()),
        )
        left = config.FREE_DAILY["video"] - db.credit_used(c, owner, day, "video")

    return jsonify({"ok": True, "video": {**rec, "id": vid, "file": None},
                    "download": f"/api/videos/{vid}/file",
                    "credits_remaining": left,
                    "cost": 0})


@app.get("/api/videos/<vid>")
def get_video(vid: str):
    with db.connect() as c:
        row = c.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    if row is None:
        return _err("no such video", 404)
    d = db.dump(row)
    d["lines"] = json.loads(d.get("lines") or "[]")
    d["download"] = f"/api/videos/{vid}/file"
    d["file"] = None
    return jsonify({"ok": True, "video": d})


@app.get("/api/videos/<vid>/file")
def video_file(vid: str):
    with db.connect() as c:
        row = c.execute("SELECT path FROM videos WHERE id=?", (vid,)).fetchone()
    if row is None or not row["path"]:
        return _err("no such video", 404)
    p = Path(row["path"])
    if not p.is_file():
        return _err("render missing", 404)
    return Response(p.read_bytes(), content_type="video/mp4",
                    headers={"Content-Disposition": f'attachment; filename="{vid}.mp4"',
                             "Cache-Control": "private, max-age=3600"})


@app.get("/api/videos")
def list_videos():
    owner = (request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        rows = c.execute(
            "SELECT id,scene,talent,voice,pet_name,watermarked,duration,bytes,created_at"
            " FROM videos WHERE owner=? ORDER BY created_at DESC LIMIT 50",
            (owner,)).fetchall()
    return jsonify({"ok": True, "owner": owner,
                    "videos": [db.dump(r) for r in rows]})


@app.get("/api/videos/feed")
def videos_feed():
    """Public vertical-feed catalog — recent finished clips, any owner.

    Lightweight swipe feed (Videos tab): one mp4 per slide, src = artifact
    route. No secrets in the payload.
    """
    with db.connect() as c:
        rows = c.execute(
            """SELECT id,owner,scene,talent,voice,pet_name,topic,watermarked,
                      duration,bytes,created_at
               FROM videos
               WHERE path IS NOT NULL AND path != ''
               ORDER BY created_at DESC LIMIT 40""").fetchall()
    items = []
    for r in rows:
        d = db.dump(r)
        d["src"] = f"/api/videos/{d['id']}/file"
        d["title"] = (d.get("pet_name") or "your star") + " · " + (d.get("topic") or d.get("scene") or "")
        items.append(d)
    return jsonify({"ok": True, "items": items, "count": len(items)})


@app.post("/api/standup/render")
def standup_render():
    """Render a shareable standup video (pose bake + edge-tts). CPU only."""
    import subprocess as sp
    import time as _t

    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "Buster").strip()[:40]
    voice = (body.get("voice") or "ryan").strip()[:20]
    script = (body.get("script") or "").strip()[:2000]
    if not script:
        return _err("script is required", 400)
    script_path = config.ROOT / "scripts" / "pose_lipsync.py"
    if not script_path.exists():
        return _err("pose_lipsync.py missing", 500)
    out_mp4 = config.DATA / "videos" / "p0_standup.mp4"
    cmd = [
        "python3", str(script_path),
        "--name", name, "--voice", voice, "--script", script,
        "--out", str(out_mp4),
    ]
    try:
        proc = sp.run(cmd, cwd=str(config.ROOT), capture_output=True, text=True, timeout=900)
    except sp.TimeoutExpired:
        return _err("render timed out", 504)
    if proc.returncode != 0 or not out_mp4.exists():
        err = (proc.stderr or proc.stdout or "")[-400:]
        return _err(f"render failed: {err}", 500)
    vid = "vid_p0standup" + _t.strftime("%H%M%S")
    r = sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(out_mp4)], capture_output=True, text=True)
    try:
        dur = float((r.stdout or "20").strip())
    except ValueError:
        dur = 20.0
    with db.connect() as c:
        c.execute("DELETE FROM videos WHERE id=?", (vid,))
        c.execute(
            """INSERT INTO videos (id,owner,mesh_id,scene,talent,voice,pet_name,topic,
                 script,lines,watermarked,duration,bytes,path,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vid, "demo", "msh_70edae28a4304f4cb7e9", "comedy_show", "comedy",
             voice, name, "stand-up set", script[:500], "[]", 0, dur,
             out_mp4.stat().st_size, str(out_mp4), _t.time()),
        )
        c.commit()
    return jsonify({
        "ok": True,
        "video_id": vid,
        "duration": dur,
        "bytes": out_mp4.stat().st_size,
        "download": f"/api/videos/{vid}/file",
        "hint": "Shareable vertical mp4 with jawOpen lipsync. In the Videos feed.",
    })


# ── jobs / artifacts ──────────────────────────────────────────────────

@app.post("/api/run")
def run_queue():
    body = request.get_json(silent=True) or {}
    n = pipeline.run_all(max_jobs=int(body.get("max_jobs", 20)))
    return jsonify({"ok": True, "processed": n})


@app.get("/api/artifacts/<path:key>")
def artifact(key: str):
    if ".." in key or key.startswith("/") or "//" in key or not key.strip("/"):
        return _err("bad key", 400)
    import hashlib
    # Stable per-process name so repeat requests hit the local cache.
    # (str.__hash__ is salted, so hash(key) would miss every time.)
    tmp = config.LOCAL_TMP / f"art_{hashlib.sha1(key.encode()).hexdigest()[:24]}"
    try:
        storage.get(key, tmp)
    except storage.StorageError as e:
        return _err(f"unavailable: {e}", 404)
    ctype = {"glb": "model/gltf-binary", "png": "image/png", "jpg": "image/jpeg",
             "svg": "image/svg+xml", "webp": "image/webp", "mp4": "video/mp4",
             "zip": "application/zip", "json": "application/json"} \
        .get(key.rsplit(".", 1)[-1], "application/octet-stream")
    return Response(tmp.read_bytes(), content_type=ctype,
                    headers={"Cache-Control": "private, max-age=3600"})


# ── premesh ──────────────────────────────────────────────────────────
# Normalise an uploaded image for whatever comes next: subject extracted and
# framed for Meshy (`recipe=meshy`), cut out on transparency for a card
# (`recipe=card`), or a plain thumbnail (`recipe=thumb`).
#
#   POST /api/premesh   multipart photo=file  |  url=https://…
#                       &recipe=meshy|card|thumb  &format=json  &strict=1
#
# Binary by default (image/png or image/webp) with the QC verdict in
# `X-Premesh-Ok`; `format=json` returns the report + base64 instead. The same
# module drives the CLI: `python3 -m premesh photo.jpg -r meshy`.
@app.post("/api/premesh")
def premesh_endpoint():
    import base64

    import premesh

    recipe = request.values.get("recipe", "meshy")
    if recipe not in premesh.RECIPES:
        return _err(f"unknown recipe — have: {', '.join(sorted(premesh.RECIPES))}",
                    400)

    source = request.values.get("url", "")
    upload = request.files.get("photo") or request.files.get("file")
    if upload is not None:
        try:
            accepted = intake.accept(upload.read(), upload.filename or "photo.jpg")
        except intake.IntakeError as e:
            return _err(str(e), e.code)
        source = accepted.path
    if not source:
        return _err("Attach a photo in the 'photo' field, or pass ?url=https://…",
                    400)

    try:
        # Zone follows the request host so Cloudflare pulls staged sources
        # from the zone actually serving them (multi-brand seam).
        out = premesh.normalize(source, recipe,
                                zone=config.brand_for(request.host)["host"])
    except premesh.TransformError as e:
        return _err(f"normalisation failed: {e}", 502)

    if request.values.get("format") == "json":
        payload = out.as_dict()
        payload["b64"] = base64.b64encode(out.data).decode()
        return jsonify(payload)

    if not out.ok and request.values.get("strict"):
        return jsonify({"ok": False, "recipe": out.recipe,
                        "issues": out.report.issues}), 422

    ctype = out.report.content_type
    return Response(out.data, content_type=ctype, headers={
        "X-Premesh-Ok": "1" if out.ok else "0",
        "X-Premesh-Recipe": out.recipe,
        "X-Premesh-Coverage": str(out.report.coverage),
        "Cache-Control": "no-store",
    })


@app.get("/health")
def health():
    with db.connect() as c:
        counts = {
            "photos": c.execute("SELECT COUNT(*) n FROM photos").fetchone()["n"],
            "meshes": c.execute("SELECT COUNT(*) n FROM meshes").fetchone()["n"],
            "succeeded": c.execute(
                "SELECT COUNT(*) n FROM meshes WHERE status='succeeded'").fetchone()["n"],
            "pending_jobs": c.execute(
                "SELECT COUNT(*) n FROM jobs WHERE status='pending'").fetchone()["n"],
        }
    return jsonify({
        "ok": True,
        "meshy": "stub" if meshy.is_stub() else "live",
        "r2_bucket": config.R2_BUCKET,
        "products": list(config.PRODUCTS),
        "counts": counts,
    })


# ── studio: modular product lines, props, one-click order ────────────
# Registry: config.STUDIO_LINES / STUDIO_COATS / STUDIO_HATS.
# Stills live in data/productimg/prod → public /img/prod/.
# Orders are intent + quote until Stripe/Shopify checkout lands.

def _studio_still(name: str) -> str | None:
    p = config.DATA / "productimg" / config.STUDIO_STILL_DIR / name
    return f"/img/{config.STUDIO_STILL_DIR}/{name}" if p.exists() else None


def _studio_stills_for(line: str, coat: str, hat: str) -> dict:
    """Pick the best pre-rendered stills for this combo (0 credits).

    Prefix order (first hit wins):
      1. coat-<coat>-<hat>-     combo stills (e.g. coat-chocolate-santa-)
      2. <hat>-                 hat-only (santa-hero)
      3. coat-<coat>-           coat-only
      4. brick- / kc- / prod-   line defaults
    """
    coat = (coat or "none").lower()
    hat = (hat or "none").lower()
    keys = ["hero", "front", "side", "back", "loop"]
    prefixes = []
    # factory stills: each line's own <line>-{hero,front,side,back}.png set
    # wins over the shared fallbacks (real photos, not placeholders)
    if line not in ("ornament", "keychain", "brick"):
        prefixes.append(f"{line}-")
    if line == "brick_keychain":
        prefixes.append("brick-")
    if coat not in ("", "none") and hat not in ("", "none"):
        prefixes.append(f"coat-{coat}-{hat}-")
    if hat not in ("", "none"):
        prefixes.append(f"{hat}-")
    if coat not in ("", "none"):
        prefixes.append(f"coat-{coat}-")
    if line == "ornament":
        prefixes.append("prod-")
    elif line == "keychain":
        prefixes.append("kc-")
    elif line == "brick":
        prefixes.append("brick-")
        prefixes.append("brick-hero.png")  # handled below
    else:
        prefixes.append("prod-")

    for prefix in prefixes:
        if prefix.endswith(".png"):
            url = _studio_still(prefix)
            if url:
                return {k: url for k in keys}
            continue
        out = {}
        for k in keys:
            url = _studio_still(f"{prefix}{k}.png")
            if url:
                out[k] = url
        if out:
            # fill remaining keys from line defaults so UI never blanks
            for k in keys:
                if k in out:
                    continue
                for fb in ("prod-", "kc-", "brick-"):
                    u = _studio_still(f"{fb}{k}.png")
                    if u:
                        out[k] = u
                        break
            return out
    # last resort
    for k in keys:
        url = _studio_still(f"prod-{k}.png")
        if url:
            return {k: url for k in keys}
    return {}


def _list_studio_combos() -> dict:
    """Catalogue of pre-rendered coat/hat/pattern still sets for agents."""
    prod = config.DATA / "productimg" / config.STUDIO_STILL_DIR
    coats, hats, combos, patterns = [], [], [], []
    if not prod.exists():
        return {"coats": coats, "hats": hats, "combos": combos, "patterns": patterns}
    names = {p.name for p in prod.glob("*.png")}
    coat_ids = {c["id"] for c in config.STUDIO_COATS if c["id"] != "none"}
    hat_ids = {h["id"] for h in config.STUDIO_HATS if h["id"] != "none"}
    for cid in sorted(coat_ids):
        if f"coat-{cid}-hero.png" in names:
            coats.append({"id": cid, "hero": f"/img/prod/coat-{cid}-hero.png"})
    for hid in sorted(hat_ids):
        if f"{hid}-hero.png" in names:
            hats.append({"id": hid, "hero": f"/img/prod/{hid}-hero.png"})
    # combos coat-<coat>-<hat>-
    for cid in sorted(coat_ids):
        for hid in sorted(hat_ids):
            if f"coat-{cid}-{hid}-hero.png" in names:
                combos.append({
                    "coat": cid, "hat": hid,
                    "hero": f"/img/prod/coat-{cid}-{hid}-hero.png",
                })
    # patterns coat-<coat>-<pattern>-hero
    for pat in ("spots", "stripes", "fairisle"):
        for cid in sorted(coat_ids):
            if f"coat-{cid}-{pat}-hero.png" in names:
                patterns.append({
                    "coat": cid, "pattern": pat,
                    "hero": f"/img/prod/coat-{cid}-{pat}-hero.png",
                })
    return {
        "coats": coats, "hats": hats, "combos": combos, "patterns": patterns,
        "policy": config.STUDIO_CUSTOM_POLICY,
        "lines": {
            lid: {
                "label": spec.get("label"),
                "status": spec.get("status"),
                "price_cents": spec.get("price_cents"),
                "assets": spec.get("assets"),
            }
            for lid, spec in config.STUDIO_LINES.items()
        },
        "hint": "Use POST /api/products/personalise with these registry ids. "
                "Coat = preview grade; multi-colour print is a live farm quote.",
    }


@app.get("/api/studio")
def studio_state():
    """Modular studio contract: lines, props, meshes, stills, prices."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        pogs = db.pogs_for(c, owner)
        active = prof.get("active_mesh_id") or ""
        if not active:
            ok = next((p for p in pogs if p["status"] == "succeeded"), None)
            if ok:
                active = ok["id"]
                db.set_active(c, owner, active)
        roster = []
        for p in pogs:
            if p["status"] != "succeeded":
                continue
            glb = storage.public_url(p["glb_key"]) if p.get("glb_key") else ""
            label = short_mesh_label(p["id"])
            prov = (p.get("provider") or "")
            is_brick = (
                p["id"] in config.STUDIO_BRICK_MESH_MAP
                or prov in ("svatantrya", "brick", "style:brick-figure", "style:brick-figure-2")
                or "brick" in prov.lower()
                or "brick" in label.lower()
            )
            portrait = ""
            kind = "pet"
            if is_brick:
                kind = "brick"
                mapped = config.STUDIO_BRICK_MESH_MAP.get(p["id"])
                if mapped:
                    label, portrait, _demo_id = mapped
                else:
                    label = "brick figure"
                    portrait = config.STUDIO_BRICK_PORTRAIT
            roster.append({
                "mesh_id": p["id"],
                "label": label,
                "glb_url": glb,
                "portrait": portrait,
                "active": p["id"] == active,
                "stub": bool(p["stub"]),
                "kind": kind,
                "profile": db.get_subject_profile(c, owner, p["id"]) or None,
            })
    demo = {
        "mesh_id": "canonical",
        "label": "canonical dog",
        "glb_url": config.STUDIO_CANONICAL_GLB,
        "active": not roster,
        "stub": False,
        "demo": True,
        "kind": "pet",
        "portrait": config.STUDIO_CALLING_CARD,
    }
    # Studio lineup: dog + both brick demos + owner roster
    meshes = [demo]
    seen = {"canonical"}
    for b in config.STUDIO_BRICKS:
        meshes.append({
            "mesh_id": b["id"],
            "label": b["label"],
            "glb_url": b["glb_url"],
            "active": False,
            "stub": False,
            "demo": True,
            "kind": "brick",
            "portrait": b["portrait"],
            "style_id": b.get("style_id", ""),
        })
        seen.add(b["id"])
    for m in roster:
        if m["mesh_id"] not in seen:
            meshes.append(m)
            seen.add(m["mesh_id"])
    if active:
        for m in meshes:
            m["active"] = m["mesh_id"] == active
    lines = [{"id": lid, **spec,
              "customization_schema": _custom_schema(lid, spec),
              "personalization_levels": _custom_schema(lid, spec)["levels"]}
             for lid, spec in config.STUDIO_LINES.items()]
    hats = []
    for h in config.STUDIO_HATS:
        hats.append({**h, "preview": _studio_stills_for("ornament", "none", "none") if h["id"] == "none" else {}})
    calling = _studio_still("prod-hero.png") or config.STUDIO_CALLING_CARD
    return jsonify({
        "ok": True,
        "owner": owner,
        "active_mesh_id": active or ("canonical" if not roster else ""),
        "meshes": meshes,
        "lines": lines,
        "coats": list(config.STUDIO_COATS),
        "patterns": list(config.STUDIO_PATTERNS),
        "hats": hats,
        "calling_card": calling,
        "custom_policy": config.STUDIO_CUSTOM_POLICY,
        "stills": {
            "exact": _studio_stills_for("ornament", "none", "none"),
            "keychain": _studio_stills_for("keychain", "none", "none"),
            "brick": _studio_stills_for("brick", "none", "none"),
        },
        "canonical_glb": config.STUDIO_CANONICAL_GLB,
        "brick_glb": config.STUDIO_BRICK_GLB,
        "note": "Studio = character select + controlled loadout. "
                "Prices/checkout on Products. Custom is registry-only.",
    })


@app.get("/api/studio/props")
def studio_props():
    """Machine-readable prop library for agents (hats, coats, patterns)."""
    from pathlib import Path as _P
    hats = []
    for h in config.STUDIO_HATS:
        rec = dict(h)
        asset = rec.get("asset") or ""
        if asset:
            p = _P(asset)
            rec["exists"] = p.exists()
            rec["bytes"] = p.stat().st_size if p.exists() else 0
        hats.append(rec)
    return jsonify({
        "ok": True,
        "hats": hats,
        "coats": config.STUDIO_COATS,
        "patterns": config.STUDIO_PATTERNS,
        "policy": config.STUDIO_CUSTOM_POLICY,
        "lines": {k: {
            "label": v.get("label"),
            "status": v.get("status"),
            "price_cents": v.get("price_cents"),
            "assets": v.get("assets"),
            "fulfilment": v.get("fulfilment"),
            "amounts_cents": v.get("amounts_cents"),
            "scale_mm": v.get("scale_mm"),
            "size_mm": v.get("size_mm"),
        } for k, v in config.STUDIO_LINES.items()},
    })


@app.get("/api/etsy/listings")
def etsy_listings():
    """Etsy-ready listing packs (title, tags, sizes, materials, photo slots)."""
    only = (request.args.get("product_id") or request.args.get("id") or "").strip()
    packs = config.ETSY_LISTINGS
    if only:
        if only not in packs:
            return _err(f"unknown listing {only!r} — have: {', '.join(packs)}", 404)
        return jsonify({"ok": True, "listing": packs[only], "source": config.ETSY_SOURCE_NOTE})
    return jsonify({
        "ok": True,
        "listings": packs,
        "card_sizes": config.CARD_SIZES,
        "personal_cards": config.PERSONAL_CARDS,
        "source": config.ETSY_SOURCE_NOTE,
    })


@app.get("/api/meshy/catalog")
def meshy_catalog():
    """Meshy Creative Lab catalogue for agents — no spend, no key leak."""
    return jsonify({
        "ok": True,
        "products": config.MESHY_CATALOG,
        "ship": config.MESHY_SHIP_NOTE,
        "money_rule": "Ask the human before every Meshy generation. "
                      "Ledger: data/meshy_credits.jsonl. Physical print cost is separate.",
        "api_base": "https://api.meshy.ai/openapi",
        "creative_lab_path": "/creative-lab/<product>/v1/prototype|build",
        "mirror": "/home/ubuntu/meshy-docs",
    })


# ── Quick / agent playbook: ramble → confidence products → photo → checkout ──

_QUICK_SYNONYMS = {
    "ornament": ["bauble", "xmas", "christmas", "hanging", "tree", "decoration"],
    "keychain": ["key", "keyring", "key ring", "keys"],
    "croc_tag": ["croc", "croc tag", "jibbitz", "charm", "shoe", "crocs"],
    "gift_card": ["gift", "giftcard", "gift card", "voucher", "credit"],
    "brick": ["desk", "figure", "figurine"],
    "cream": ["beige", "ivory"],
    "golden": ["gold", "blonde"],
    "chocolate": ["brown"],
    "black": ["dark"],
    "fawn": ["tan"],
    "grey": ["gray"],
    "santa": ["xmas hat", "christmas hat", "santa hat"],
    "xmas_hat": ["xmas hat", "christmas hat"],
    "spots": ["dalmatian", "dots", "spotty"],
    "stripes": ["striped"],
    "fairisle": ["fair isle", "knit"],
    "pet": ["dog", "cat", "puppy", "kitten", "pet"],
}


def _quick_score(hay: str, q: str) -> float:
    hay = (hay or "").lower()
    q = (q or "").lower()
    if not q:
        return 0.0
    score = 0.0
    for tok in q.split():
        if not tok:
            continue
        if tok in hay:
            score += 3.0
        else:
            for part in hay.replace("|", " ").split():
                if part.startswith(tok):
                    score += 1.5
                    break
        for k, syns in _QUICK_SYNONYMS.items():
            if k.startswith(tok) or tok.startswith(k):
                for s in syns:
                    if s in hay:
                        score += 1.2
            for s in syns:
                if s == tok and k in hay:
                    score += 1.2
    return score


@app.post("/api/quick/map")
def quick_map():
    """Map a customer ramble onto live studio lines with confidence.

    Shared by the storefront Quick panel and agents (ChatGPT/MCP).
    Returns ranked products with confidence 0–1 and the next-step funnel.
    """
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or body.get("ramble") or body.get("q") or "").strip()[:2000]
    owner = (body.get("owner") or "anon").strip()[:80]
    boosts = body.get("boost_lines") or body.get("selected") or []
    if isinstance(boosts, str):
        boosts = [boosts]
    boosts = [str(b).strip().lower() for b in boosts if str(b).strip()][:12]
    if not text:
        return _err("text is required — ramble something first", 400)
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        active = prof.get("active_mesh_id") or ""
    q = text.lower()
    scored = []
    for lid, spec in config.STUDIO_LINES.items():
        hay = " ".join([
            lid, spec.get("label", ""), spec.get("blurb", ""),
            spec.get("theme", ""), spec.get("hardware", ""),
            spec.get("fulfilment", ""),
            " ".join((spec.get("assets") or {}).get("coats") or []),
            " ".join((spec.get("assets") or {}).get("hats") or []),
            " ".join((spec.get("assets") or {}).get("patterns") or []),
        ]).lower()
        score = _quick_score(hay, q)
        if lid in boosts:
            score += 4.0  # customer shortlisted this line mid-ramble
        if spec.get("status") != "live":
            score *= 0.35
        if score <= 0:
            continue
        coats = (spec.get("assets") or {}).get("coats") or ["none"]
        hats = (spec.get("assets") or {}).get("hats") or ["none"]
        patterns = (spec.get("assets") or {}).get("patterns") or ["solid"]
        # light attribute pull from the ramble
        coat = next((c0 for c0 in coats if c0 != "none" and c0 in q), "none")
        hat = next((h for h in hats if h != "none" and h in q), "none")
        pattern = next((p for p in patterns if p != "solid" and p in q), "solid")
        scored.append({
            "id": lid,
            "label": spec.get("label", lid),
            "blurb": spec.get("blurb", ""),
            "status": spec.get("status", "live"),
            "price_cents": spec.get("price_cents", 0),
            "scale_mm": spec.get("scale_mm"),
            "theme": spec.get("theme", ""),
            "hardware": spec.get("hardware", ""),
            "fulfilment": spec.get("fulfilment", "print_farm"),
            "recommended_coat": coat,
            "recommended_hat": hat,
            "recommended_pattern": pattern,
            "score": round(score, 2),
            "stills": _studio_stills_for(lid, coat or "none", hat or "none"),
        })
    # normalise confidence: top hit ~0.92, floor 0.25, cap 0.97
    if not scored:
        return jsonify({
            "ok": True,
            "owner": owner,
            "active_mesh_id": active,
            "text": text,
            "matches": [],
            "confidence": 0.0,
            "next": {
                "stage": "upload",
                "why": "Nothing in the warehouse matched that ramble clearly.",
                "actions": ["rephrase", "upload_photo", "browse_products"],
            },
            "funnel": [
                "1. ramble (voice/text) → POST /api/quick/map",
                "2. show ranked live products with confidence",
                "3. customer uploads photo → POST /api/photos → POST /api/meshes",
                "4. mesh becomes active → products inherit",
                "5. POST /api/products/order {fulfil:true} → Shopify draft",
            ],
        })
    top = max(m["score"] for m in scored)
    for m in scored:
        # relative confidence vs best hit, clamped
        conf = 0.25 + 0.72 * (m["score"] / top)
        if m["status"] != "live":
            conf = min(conf, 0.4)
        m["confidence"] = round(min(0.97, conf), 2)
    scored.sort(key=lambda m: (-m["confidence"], -m["score"], m["label"]))
    best = scored[0]
    return jsonify({
        "ok": True,
        "owner": owner,
        "active_mesh_id": active,
        "text": text,
        "matches": scored,
        "confidence": best["confidence"],
        "recommended": best,
        "next": {
            "stage": "upload" if not active else "order",
            "why": (
                f"Strong match: {best['label']} "
                f"({best.get('recommended_coat') or 'as printed'}"
                + (f", {best['recommended_hat']}" if best.get("recommended_hat") not in (None, "none") else "")
                + ")."
            ),
            "actions": (
                ["upload_photo", "start_mesh", "order"]
                if not active else
                ["personalise", "order", "shopify_draft"]
            ),
            "mesh_id": active or "canonical",
        },
        "funnel": [
            "1. ramble → POST /api/quick/map  (this endpoint)",
            "2. show matches[] with confidence + stills",
            "3. if no active mesh: upload photo + sculpt (ask before Meshy spend)",
            "4. POST /api/products/personalise  (validate coat/hat/pattern)",
            "5. POST /api/products/order {fulfil:true}  (Shopify draft, no card charge)",
        ],
        "agent_hint": (
            "ChatGPT/MCP: call figg_quick_map with the customer's words, show the top "
            "2–3 matches with confidence, then figg_upload_photo + figg_start_mesh "
            "(human must approve Meshy), then figg_fullchain_personalise_order with "
            "fulfil=true. Always show price before order."
        ),
    })


@app.get("/api/agent/playbook")
def agent_playbook():
    """Machine-readable funnel for storefront + ChatGPT/MCP agents."""
    lines = []
    for lid, spec in config.STUDIO_LINES.items():
        lines.append({
            "id": lid,
            "label": spec.get("label", lid),
            "status": spec.get("status", "live"),
            "price_cents": spec.get("price_cents", 0),
            "fulfilment": spec.get("fulfilment", "print_farm"),
            "scale_mm": spec.get("scale_mm"),
            "assets": spec.get("assets") or {},
        })
    return jsonify({
        "ok": True,
        "brand": "oddhobb",
        "funnel": {
            "name": "ramble → confidence products → photo → mesh → checkout",
            "steps": [
                {"id": "ramble", "ui": "Products → Quick (voice or text)",
                 "api": "POST /api/quick/map", "returns": "matches[].confidence"},
                {"id": "show_products", "ui": "Stream tiles by confidence",
                 "api": "GET /api/products/studio", "returns": "items + active_mesh_id"},
                {"id": "upload_photo", "ui": "Upload tab",
                 "api": "POST /api/photos", "returns": "photo.id"},
                {"id": "start_mesh", "ui": "Sculpt",
                 "api": "POST /api/meshes", "returns": "mesh.id",
                 "money": "MESHY — human must approve before spend"},
                {"id": "personalise", "ui": "Coat / hat / pattern chips",
                 "api": "POST /api/products/personalise", "returns": "stills + price"},
                {"id": "order", "ui": "One-click order → Shopify",
                 "api": "POST /api/products/order",
                 "body": {"fulfil": True},
                 "returns": "order + shopify draft (no card charge from API)"},
            ],
        },
        "money_rules": [
            "Show price before any order tool.",
            "Never call Meshy without the human saying go.",
            "Orders are pending_checkout or Shopify draft — never charge from this API.",
            "Controlled custom only: registry coat/hat/pattern/line ids.",
        ],
        "studio_lines": lines,
        "endpoints": {
            "quick_map": "/api/quick/map",
            "products_studio": "/api/products/studio",
            "personalise": "/api/products/personalise",
            "order": "/api/products/order",
            "playbook": "/api/agent/playbook",
            "mcp": "https://mcp.oddhobb.com/mcp",
        },
        "chatgpt_script": (
            "1) Listen to the ramble. 2) figg_quick_map(text) — show top matches + confidence. "
            "3) If no mesh yet, ask for a photo; figg_upload_photo + figg_start_mesh (approve spend). "
            "4) figg_fullchain_personalise_order({line,coat,hat,pattern,qty,fulfil:true}) "
            "after showing the price. 5) Hand back order id + Shopify draft name."
        ),
    })


@app.get("/api/bricks/status")
def bricks_status():
    """Which brick meshes are installed (user is generating parent GLBs)."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    uploads = []
    updir = config.DATA / "uploads"
    if updir.exists():
        for p in sorted(updir.glob("*.glb")):
            uploads.append({
                "file": p.name,
                "bytes": p.stat().st_size,
                "path": str(p),
            })
    with db.connect() as c:
        rows = db.pogs_for(c, owner)
        bricks = [r for r in rows if r.get("status") == "succeeded"]
    spec = config.STUDIO_LINES.get("brick") or {}
    return jsonify({
        "ok": True,
        "owner": owner,
        "brick_line": {
            "status": spec.get("status"),
            "scale_mm": spec.get("scale_mm"),
            "price_cents": spec.get("price_cents"),
        },
        "installed_meshes": [{
            "mesh_id": r.get("id"),
            "status": r.get("status"),
            "stub": bool(r.get("stub")),
        } for r in bricks],
        "upload_glbs": uploads,
        "hint": "Drop parent GLBs in data/uploads/ or POST /api/meshes/glb. "
                "Then flip STUDIO_LINES.brick.status to live.",
    })


@app.get("/api/meshes/<mid>/manifest")
def mesh_manifest(mid: str):
    """Machine-readable view of a mesh for agents (Muse / ChatGPT)."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    if mid in ("canonical", "demo", "dog"):
        return jsonify({
            "ok": True,
            "mesh_id": "canonical",
            "owner": owner,
            "status": "succeeded",
            "stub": False,
            "print_ready": True,
            "glb_url": config.STUDIO_CANONICAL_GLB,
            "photo": {"person": "canonical dog", "note": "exact product mesh"},
            "measure_hint": "scale_mm per line: ornament 80, keychain 60",
            "products": [],
            "studio_lines": list(config.STUDIO_LINES),
            "props": {
                "hats": [h["id"] for h in config.STUDIO_HATS],
                "coats": [c0["id"] for c0 in config.STUDIO_COATS],
                "patterns": [p["id"] for p in config.STUDIO_PATTERNS],
            },
            "custom_policy": config.STUDIO_CUSTOM_POLICY,
            "canonical_glb": config.STUDIO_CANONICAL_GLB,
        })
    with db.connect() as c:
        mesh = db.get_mesh(c, mid)
        if not mesh:
            return _err("no such mesh", 404)
        photo = db.get_photo(c, mesh.get("photo_id") or "")
        products = []
        rows = c.execute(
            """SELECT product,status,price_cents,source FROM product_bindings
               WHERE mesh_id=?""", (mid,)).fetchall()
        for r in rows:
            products.append(db.dump(r))
    glb = storage.public_url(mesh["glb_key"]) if mesh.get("glb_key") else ""
    return jsonify({
        "ok": True,
        "mesh_id": mid,
        "owner": (photo or {}).get("owner") or owner,
        "status": mesh.get("status"),
        "stub": bool(mesh.get("stub")),
        "print_ready": bool(mesh.get("print_ready")),
        "glb_url": glb,
        "photo": {
            "sha256": (photo or {}).get("sha256"),
            "width": (photo or {}).get("width"),
            "height": (photo or {}).get("height"),
            "person": (photo or {}).get("person") or "",
        },
        "measure_hint": "scale_mm is per product line (ornament 80, keychain 60)",
        "products": products,
        "studio_lines": list(config.STUDIO_LINES),
        "props": {
            "hats": [h["id"] for h in config.STUDIO_HATS],
            "coats": [c0["id"] for c0 in config.STUDIO_COATS],
            "patterns": [p["id"] for p in config.STUDIO_PATTERNS],
        },
        "custom_policy": config.STUDIO_CUSTOM_POLICY,
        "canonical_glb": config.STUDIO_CANONICAL_GLB,
    })


@app.post("/api/products/personalise")
def products_personalise():
    """Controlled personalise: coat colour + pattern + hat on a product line."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    line = (body.get("line") or "ornament").strip()
    coat = (body.get("coat") or body.get("coat_color") or "none").strip().lower()
    hat = (body.get("hat") or body.get("hat_id") or "none").strip().lower()
    pattern = (body.get("pattern") or body.get("coat_pattern") or "solid").strip().lower()
    mesh_id = (body.get("mesh_id") or "").strip()
    texture_note = (body.get("texture") or body.get("texture_note") or "")[:200]
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    spec = config.STUDIO_LINES[line]
    allowed = spec.get("assets") or {}
    if coat not in (allowed.get("coats") or ["none"]):
        return _err(f"coat {coat!r} is not allowed on {line}", 400)
    if hat not in (allowed.get("hats") or ["none"]):
        return _err(f"hat {hat!r} is not allowed on {line}", 400)
    if pattern not in (allowed.get("patterns") or ["solid"]):
        return _err(f"pattern {pattern!r} is not allowed on {line}", 400)
    if pattern != "solid" and coat == "none":
        # pattern without a coat colour is meaningless on as-printed fur
        coat = "cream"
    if spec.get("status") != "live":
        return _err(f"{line} is not live yet", 409)
    stills = _studio_stills_for(line, coat, hat)
    # pattern stills if pre-rendered: coat-<coat>-<pattern>-hero.png
    if pattern != "solid":
        pat = _studio_still(f"coat-{coat}-{pattern}-hero.png")
        if pat:
            stills = {**stills, "hero": pat, "pattern_hero": pat}
    # combo catalogue so agents know what exists
    cat = _list_studio_combos()
    available = {
        "coats": [c["id"] for c in cat["coats"]],
        "hats": [h["id"] for h in cat["hats"]],
        "combos": cat["combos"],
        "patterns": cat["patterns"],
    }
    return jsonify({
        "ok": True,
        "owner": owner,
        "line": line,
        "coat": coat,
        "hat": hat,
        "pattern": pattern,
        "mesh_id": mesh_id,
        "texture_note": texture_note,
        "stills": stills,
        "available": available,
        "price_cents": spec.get("price_cents", 0),
        "fulfilment": spec.get("fulfilment"),
        "policy": "controlled",
        "hint": "Registry-only custom. Coat is a preview grade — multi-colour print is a live farm quote. "
                "Order via POST /api/products/order or figg_checkout.",
    })


@app.post("/api/products/order")
def products_order():
    """One-click order for controlled custom / gift card. Optional Shopify draft."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    line = (body.get("line") or body.get("product") or "ornament").strip()
    coat = (body.get("coat") or "none").strip().lower()
    hat = (body.get("hat") or "none").strip().lower()
    pattern = (body.get("pattern") or "solid").strip().lower()
    mesh_id = (body.get("mesh_id") or "").strip()
    qty = max(1, min(20, int(body.get("qty") or 1)))
    note = (body.get("note") or "")[:200]
    email = (body.get("email") or "").strip()[:120]
    amount_cents = body.get("amount_cents")
    fulfil = bool(body.get("fulfil") or body.get("shopify"))
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    spec = config.STUDIO_LINES[line]
    if spec.get("status") != "live":
        return _err(f"{line} is not orderable yet", 409)
    if line == "gift_card":
        amounts = spec.get("amounts_cents") or [spec.get("price_cents", 2500)]
        if amount_cents is None:
            amount_cents = amounts[0]
        amount_cents = int(amount_cents)
        if amount_cents not in amounts:
            return _err(f"amount_cents must be one of {amounts}", 400)
        price = amount_cents * qty
    else:
        price = int(spec.get("price_cents") or 0) * qty
    label = f"{spec.get('label', line)}"
    if line != "gift_card":
        extras = []
        if coat != "none":
            extras.append(f"coat:{coat}")
        if pattern != "solid":
            extras.append(f"pattern:{pattern}")
        if hat != "none":
            extras.append(f"hat:{hat}")
        if extras:
            label += " (" + ", ".join(extras) + ")"
    custom_note = note
    if line != "gift_card":
        custom_note = (custom_note + " | " if custom_note else "") + \
            f"custom coat={coat} pattern={pattern} hat={hat}"
    with db.connect() as c:
        order = db.create_order(
            c, owner=owner, line=line, mesh_id=mesh_id, coat=coat, hat=hat,
            qty=qty, price_cents=price, note=custom_note[:200],
        )
        # stash pattern on note line via update if column missing
    shopify = {"attempted": False}
    if fulfil:
        shopify["attempted"] = True
        try:
            from backend import shopify_fulfil as sf
            if not sf.configured():
                shopify = {"attempted": True, "ok": False, "error": "Shopify not configured"}
            else:
                draft = sf.create_draft_order(label, price // max(1, qty), qty,
                                             note=custom_note, email=email)
                shopify.update(draft)
                if draft.get("ok"):
                    with db.connect() as c:
                        c.execute(
                            "UPDATE orders SET note=? WHERE id=?",
                            ((custom_note + f" | shopify:{draft.get('draft_id') or draft.get('name')}")[:200],
                             order.get("id")),
                        )
                        c.commit()
        except Exception as e:  # noqa: BLE001
            shopify = {"attempted": True, "ok": False, "error": str(e)[:300]}
    return jsonify({
        "ok": True,
        "order": order,
        "price_cents": price,
        "status": "pending_checkout",
        "label": label,
        "shopify": shopify,
        "hint": "Order reserved. Shopify draft only if fulfil=true and creds work. "
                "No card charge from this endpoint.",
    })


@app.get("/api/studio/combos")
def studio_combos():
    """Pre-rendered coat/hat/pattern still sets + allowed line assets (agents)."""
    return jsonify({"ok": True, **_list_studio_combos()})


@app.get("/api/studio/stills")
def studio_stills():
    line = (request.args.get("line") or "ornament").strip()
    coat = (request.args.get("coat") or "none").strip().lower()
    hat = (request.args.get("hat") or "none").strip().lower()
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    return jsonify({
        "ok": True, "line": line, "coat": coat, "hat": hat,
        "stills": _studio_stills_for(line, coat, hat),
        "combo": _studio_still(f"coat-{coat}-{hat}-hero.png")
                 if coat != "none" and hat != "none" else None,
    })


PLACEMENT_DIR = config.DATA / "placements"
_PLACEMENT_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{1,64}$")


def _placement_path(line: str, part: str):
    return PLACEMENT_DIR / f"{line}__{part}.json"


def _placement_read(line: str, part: str):
    try:
        return json.loads(_placement_path(line, part).read_text())
    except (OSError, ValueError):
        return None


@app.get("/api/fit/placement")
def fit_placement_get():
    """Saved hand placement for a line+part (fit editor). No placement yet
    returns ok:true with placement:null — the caller uses the seated default.
    """
    line = (request.args.get("line") or "ornament").strip()
    part = (request.args.get("part") or "santa").strip()
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    if not _PLACEMENT_RE.match(part):
        return _err("bad part", 400)
    return jsonify({"ok": True, "line": line, "part": part,
                    "placement": _placement_read(line, part)})


@app.post("/api/fit/placement")
def fit_placement_save():
    """Save a hand placement from the fit editor (/fit.html).

    Body: {line, part, position:[x,y,z], rotation:[x,y,z] (euler XYZ radians),
           scale:[x,y,z] or number}. Position clamp ±0.5m, scale 0.1–5.
    Service-token gated like every other /api route (bridge swaps the token
    server-side; the browser only holds the bridge token).
    """
    import math as _math
    body = request.get_json(silent=True) or {}
    line = str(body.get("line") or "ornament").strip()
    part = str(body.get("part") or "santa").strip()
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    if not _PLACEMENT_RE.match(part):
        return _err("bad part", 400)

    def _vec(v, lo, hi, n=3):
        if isinstance(v, (int, float)):
            v = [v] * n
        if not isinstance(v, (list, tuple)) or len(v) != n:
            return None
        out = []
        for x in v:
            if not isinstance(x, (int, float)) or not _math.isfinite(x):
                return None
            out.append(max(lo, min(hi, float(x))))
        return out

    pos = _vec(body.get("position"), -0.5, 0.5)
    rot = _vec(body.get("rotation"), -_math.pi, _math.pi)
    scl = _vec(body.get("scale", 1.0), 0.1, 5.0)
    if pos is None or rot is None or scl is None:
        return _err("bad transform (position/rotation/scale)", 400)
    PLACEMENT_DIR.mkdir(parents=True, exist_ok=True)
    doc = {"line": line, "part": part, "position": pos, "rotation": rot,
           "scale": scl}
    _placement_path(line, part).write_text(json.dumps(doc, indent=2))
    return jsonify({"ok": True, **doc})


@app.post("/api/studio/customise")
def studio_customise():
    """Apply a customisation choice. Returns stills + what will be ordered.

    Freeform agent text is parsed client-side into {line, coat, hat}; this
    endpoint is the contract both the UI and MCP tools call.
    """
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    line = (body.get("line") or "ornament").strip()
    coat = (body.get("coat") or "none").strip().lower()
    hat = (body.get("hat") or "none").strip().lower()
    mesh_id = (body.get("mesh_id") or "").strip()
    if line not in config.STUDIO_LINES:
        return _err(f"unknown line — have: {', '.join(config.STUDIO_LINES)}", 400)
    if coat not in {c["id"] for c in config.STUDIO_COATS}:
        return _err("unknown coat", 400)
    if hat not in {h["id"] for h in config.STUDIO_HATS}:
        return _err("unknown hat", 400)
    spec = config.STUDIO_LINES[line]
    if spec.get("status") != "live":
        return _err(f"{line} is not live yet ({spec.get('status')})", 409)
    stills = _studio_stills_for(line, coat, hat)
    return jsonify({
        "ok": True,
        "owner": owner,
        "line": line,
        "coat": coat,
        "hat": hat,
        "mesh_id": mesh_id,
        "stills": stills,
        "price_cents": spec.get("price_cents", 0),
        "scale_mm": spec.get("scale_mm"),
        "hint": "Preview grade only — multi-colour print is quoted live. "
                "Hardware stays printed plastic.",
    })


@app.post("/api/studio/order")
def studio_order():
    """One-click order intent. Stores the combo + quote; checkout is next."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    line = (body.get("line") or "ornament").strip()
    coat = (body.get("coat") or "none").strip().lower()
    hat = (body.get("hat") or "none").strip().lower()
    mesh_id = (body.get("mesh_id") or "").strip()
    qty = max(1, min(20, int(body.get("qty") or 1)))
    note = (body.get("note") or "")[:200]
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    spec = config.STUDIO_LINES[line]
    if spec.get("status") != "live":
        return _err(f"{line} is not orderable yet", 409)
    price = int(spec.get("price_cents") or 0) * qty
    with db.connect() as c:
        order = db.create_order(
            c, owner=owner, line=line, mesh_id=mesh_id, coat=coat, hat=hat,
            qty=qty, price_cents=price, note=note,
        )
    return jsonify({
        "ok": True,
        "order": order,
        "price_cents": price,
        "status": "pending_checkout",
        "hint": "Order reserved. Payment lands with Stripe/Shopify — "
                "nothing charged yet.",
    })


def _custom_schema(lid: str, spec: dict) -> dict:
    """Agent-visible customisation contract, derived from personalization.method.

    L0 name/initials (instant) · L1 photo/2D (seconds) · L2 relief (short) ·
    L3 full mesh (costs credits). Single source of truth — new lines inherit
    it; only genuine multi-mode lines take CUSTOM_SCHEMA_OVERRIDES.
    """
    if lid in config.CUSTOM_SCHEMA_OVERRIDES:
        o = config.CUSTOM_SCHEMA_OVERRIDES[lid]
        return {"requires": o["requires"], "optional": o["optional"],
                "modes": o["modes"], "levels": o["levels"]}
    method = (spec.get("personalization") or {}).get("method", "")
    if method == "emboss":
        return {"requires": ["recipient_name"], "optional": ["motif", "colour"],
                "modes": ["text"], "levels": ["L0"]}
    if method == "relief":
        return {"requires": [], "optional": ["recipient_name", "motif", "photo", "colour"],
                "modes": ["text", "relief"], "levels": ["L0", "L2"]}
    if method == "face_swap":
        return {"requires": ["photo"], "optional": ["coat", "pattern"],
                "modes": ["full_mesh"], "levels": ["L3"]}
    return {"requires": [], "optional": [], "modes": [], "levels": []}


@app.get("/api/products/studio")
def products_studio():
    """Products tab catalog: studio lines + relevant assets + stills + prices."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        active = prof.get("active_mesh_id") or ""
        subject = db.get_subject_profile(c, owner, active) if active else {}
    suggestion = _suggest_motif(subject.get("interests", [])) if subject else None
    items = []
    for lid, spec in config.STUDIO_LINES.items():
        assets = spec.get("assets") or {"hats": ["none"], "coats": ["none"], "patterns": ["solid"]}
        hats = [h for h in config.STUDIO_HATS if h["id"] in assets.get("hats", ["none"])]
        coats = [c0 for c0 in config.STUDIO_COATS if c0["id"] in assets.get("coats", ["none"])]
        patterns = [p for p in config.STUDIO_PATTERNS if p["id"] in assets.get("patterns", ["solid"])]
        stills = _studio_stills_for(lid, "none", "none")
        if lid == "ornament":
            s = _studio_stills_for("ornament", "none", "santa")
            if s.get("hero"):
                stills = {**stills, **{f"santa_{k}": v for k, v in s.items()}}
        if lid == "gift_card":
            stills = {"hero": "/img/greeting_card_70edae28.png",
                      "front": "/img/greeting_card_70edae28.png"}
        if lid == "croc_tag":
            stills = {"hero": "/img/prod/croc-tag-hero.png",
                      "front": "/img/prod/croc-tag-hero.png"}
        if lid == "brick":
            stills = _studio_stills_for("brick", "none", "none")
            if not stills.get("hero"):
                stills = {"hero": config.STUDIO_BRICK_PORTRAIT,
                          "front": config.STUDIO_BRICK_PORTRAIT}
            # expose the mesh itself so shop tiles / viewers can load it
        items.append({
            "id": lid,
            "label": spec.get("label", lid),
            "blurb": spec.get("blurb", ""),
            "status": spec.get("status", "live"),
            "price_cents": spec.get("price_cents", 0),
            "scale_mm": spec.get("scale_mm"),
            "size_mm": spec.get("size_mm") or spec.get("scale_mm"),
            "sizes": _line_sizes(lid, spec),
            "theme": spec.get("theme", ""),
            "hardware": spec.get("hardware", ""),
            "fulfilment": spec.get("fulfilment", "print_farm"),
            "amounts_cents": spec.get("amounts_cents"),
            "assets": {"hats": hats, "coats": coats, "patterns": patterns},
            "stills": stills,
            "glb_url": config.STUDIO_BRICK_GLB if lid == "brick" else "",
            "customization_schema": _custom_schema(lid, spec),
            "personalization_levels": _custom_schema(lid, spec)["levels"],
            "material": spec.get("material"),
            "colors_max": spec.get("colors_max"),
            "dims_mm": spec.get("dims_mm"),
            "weight_g": spec.get("weight_g"),
            "weight_basis": spec.get("weight_basis"),
            "fits": spec.get("fits"),
            "supplier": spec.get("supplier"),
            "sample": spec.get("sample"),
            "personalization": spec.get("personalization"),
            "occasion": spec.get("occasion"),
            "suggested_motif": suggestion,
        })
    return jsonify({
        "ok": True,
        "owner": owner,
        "active_mesh_id": active,
        "subject": subject or None,
        "suggestion": suggestion,
        "items": items,
        "custom_policy": config.STUDIO_CUSTOM_POLICY,
        "card_sizes": config.CARD_SIZES,
        "personal_cards": config.PERSONAL_CARDS,
        "card_customization_schema": config.CARD_CUSTOMIZATION_SCHEMA,
        "note": "Controlled custom · one-click order · optional Shopify draft (fulfil=true). "
                "MCP: figg_mesh_manifest · figg_studio_props · figg_fullchain_personalise_order.",
    })


def _line_sizes(lid: str, spec: dict) -> list[dict]:
    """Truthful size chips for a studio line / paper card."""
    if lid == "gift_card":
        amts = spec.get("amounts_cents") or [spec.get("price_cents", 2500)]
        return [{"id": "amount", "label": f"£{a/100:.0f}", "mm": "", "price_cents": a} for a in amts]
    if lid in ("ornament", "keychain", "croc_tag", "brick"):
        mm = spec.get("size_mm") or spec.get("scale_mm") or 0
        extra = []
        if lid == "ornament":
            extra = [{"id": "loop", "label": "5 mm loop", "mm": "loop Ø5", "price_cents": None}]
        if lid == "keychain":
            extra = [{"id": "hole", "label": "4 mm hole", "mm": "hole Ø4", "price_cents": None}]
        if lid == "croc_tag":
            extra = [{"id": "pin", "label": "pin stem", "mm": spec.get("pin_diameter_mm") or 12, "price_cents": None}]
        return [{"id": "print", "label": f"{mm} mm", "mm": f"{mm} mm print", "price_cents": None}] + extra
    if lid in ("greeting_card", "postcard", "xmas_card", "thank_you_card", "birthday_card"):
        return [
            {"id": k, "label": v["label"], "mm": v["mm"], "price_cents": v.get("price_cents")}
            for k, v in config.CARD_SIZES.items()
        ]
    return []

@app.get("/api/studio/orders")
def studio_orders():
    owner = (request.args.get("owner") or "anon").strip()[:80]
    with db.connect() as c:
        rows = db.orders_for(c, owner)
    return jsonify({"ok": True, "owner": owner, "orders": rows, "count": len(rows)})


def short_mesh_label(mesh_id: str) -> str:
    if not mesh_id:
        return "no mesh"
    return "mesh " + mesh_id.replace("msh_", "")[:6]


from backend import cards as card_api
card_api.register(app, _owner_denied)


# ── worker ────────────────────────────────────────────────────────────

def _worker(interval: float = 0.4) -> None:
    while not _worker_stop.wait(interval):
        try:
            pipeline.run_all(max_jobs=8)
        except Exception:
            pass


def main() -> None:
    db.init()
    card_api.init()
    config.ensure_dirs()
    threading.Thread(target=_worker, daemon=True, name="figg-worker").start()
    print(f"figgsite backend  http://127.0.0.1:{config.API_TOKEN and 8798}")
    print(f"  token   : {config.API_TOKEN}")
    print(f"  meshy   : {'STUB (set MESHY_API_KEY for live)' if meshy.is_stub() else 'LIVE'}")
    print(f"  r2      : {config.R2_BUCKET} via rclone remote")
    print(f"  products: {', '.join(config.PRODUCTS)}")
    app.run(host="127.0.0.1", port=int(__import__('os').environ.get('BACKEND_PORT', 8798)),
            threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
