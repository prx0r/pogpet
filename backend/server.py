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
import os
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
    # A valid user/agent API key also passes the global gate (it only proves
    # identity — per-action permission checks still apply downstream).
    ukey = _api_key()
    if ukey:
        with db.connect() as c:
            if db.get_user_by_api_key(c, ukey) or db.get_agent_by_key(c, ukey):
                return None
        return jsonify({"ok": False, "error": "unknown API key — create one via POST /api/accounts or the MCP figg_create_account"}), 401
    return jsonify({"ok": False, "error": "bad token — browser/MCP-full needs ?token=<bridge-token>; user keys go in X-API-Key header or ?api_key="}), 401


@app.before_request
def gate():
    if request.path == "/health":
        return None
    # Shopify webhooks carry HMAC, not our token — verified in-handler.
    if request.path.startswith("/api/shopify/webhooks/"):
        return None
    # Public proof images: design ids are unguessable capability URLs.
    if request.path.startswith("/api/cards/proof/"):
        return None
    return _gated()


def _err(message: str, code: int):
    return jsonify({"ok": False, "error": message}), code


from werkzeug.exceptions import HTTPException


@app.errorhandler(HTTPException)
def api_http_error(error):
    if not request.path.startswith('/api/'):
        return error
    return _err('API route unavailable' if error.code == 404 else error.name,
                error.code or 500)


@app.errorhandler(Exception)
def api_unexpected_error(error):
    if not request.path.startswith('/api/'):
        raise error
    app.logger.exception('API request failed')
    return _err('Service temporarily unavailable', 500)


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
        with db.connect() as c:
            a = db.get_agent_by_key(c, key)
        # Delegated agents act as their parent (grants enforced per route);
        # revoked or foreign agents get nothing.
        if a and a["status"] == "active" and a["parent_handle"] == owner:
            return None
        if a:
            return _err("agent key does not match this owner", 403)
        return _err("unknown API key", 401)
    sig = _owner_sig()
    if config.verify_owner(owner, sig):
        return None
    if owner == "anon":
        return None
    return _err(
        "owner_sig required for this owner — POST /api/session first "
        "(via bridge: POST /backend/api/session), then pass your api_key "
        "(X-API-Key header or MCP api_key arg)", 403)


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
        # a valid API key for this handle is proof of ownership too —
        # agents (ChatGPT/Muse) hold keys, not browser sigs
        key = _api_key()
        if key:
            with db.connect() as c:
                u = db.get_user_by_api_key(c, key)
            if u and (u["handle"] or "") == owner:
                return jsonify({"ok": True, "owner": owner,
                                "owner_sig": config.sign_owner(owner)})
        return _err(
            "cannot claim a named owner without a valid owner_sig or API key",
            403)
    return jsonify({"ok": True, "owner": owner,
                    "owner_sig": config.sign_owner(owner)})


# ── photos ────────────────────────────────────────────────────────────

@app.post("/api/photos")
def upload_photo():
    h0, k0, _ = _principal()
    owner = _own(request.form.get("owner") or request.args.get("owner") or "")
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
            src = (request.form.get("source") or request.args.get("source") or "photo")
            pid = db.insert_photo(
                c, owner=owner, sha256=accepted.sha256, r2_key=key, mime=accepted.mime,
                width=accepted.width, height=accepted.height, bytes=accepted.nbytes,
                orig_name=accepted.orig_name, source=src)
        except Exception:
            # Lost a race with a concurrent identical upload — reuse theirs.
            again = db.find_photo_by_hash(c, accepted.sha256, owner)
            if again:
                return jsonify({"ok": True, "reused": True, "photo": db.dump(again)})
            raise
        db.bump_uploads(c, owner, day)
        photo = db.get_photo(c, pid)

    # Preprocess faces at upload (0 credits, CPU): detection is data,
    # linking stays consent — nothing is tagged to anyone here.
    try:
        from backend import faces as _faces
        import cv2 as _cv2
        bgr = _cv2.imread(str(accepted.path))
        if bgr is not None:
            boxes = _faces.detect_boxes(bgr)
            if boxes:
                from backend import studio_library as _sl
                _sl.init()
                h_px, w_px = bgr.shape[:2]
                with db.connect() as c:
                    for f in boxes:
                        x, y, w, h = (float(v) for v in f[:4])
                        box = _faces.to_unit([x, y, w, h], w_px, h_px)
                        if not box:
                            continue
                        c.execute("INSERT OR IGNORE INTO photo_faces (id,photo_id,box,score,source) VALUES (?,?,?,?,?)",
                                  (db.new_id("face"), pid, json.dumps(box), float(f[-1]), "upload"))
    except Exception:
        pass

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
    h, kind, _ = _principal()
    if (photo["owner"] or "anon") == "anon" and kind in ("user", "agent") and h:
        # keyed caller sculpting an anon photo adopts it — uploads and
        # meshes stay under one identity instead of 403ing
        with db.connect() as c:
            c.execute("UPDATE photos SET owner=? WHERE id=?", (h, photo_id))
            c.commit()
        photo = dict(photo)
        photo["owner"] = h
    denied = _owner_denied(photo["owner"] or "anon")
    if denied is not None:
        return denied
    try:
        res = pipeline.start_mesh(photo_id, single=bool(body.get("single")))
    except pipeline.PipelineError as e:
        return _err(str(e), e.code)
    return jsonify({"ok": True, **res})


@app.get("/api/meshes")
def list_meshes():
    """Latest meshes for an owner — what the shop/studio tabs bind to."""
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    try:
        limit = min(int(request.args.get("limit", "10") or 10), 50)
    except (TypeError, ValueError):
        return _err("limit must be a number", 400)
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


# Friend archetypes -> product derivations. The friend is the input,
# products are outputs: pets become minis, people get their name on things.
# Advisory ordering only — checkout never assumes; the customer confirms.
_PET_LINES = ["croc_tag", "clog_charm", "ornament", "keychain", "brick", "brick_keychain"]
_PERSON_LINES = ["golf_marker", "book_holder", "dart_stand", "line_reader",
                 "card_rack", "tcg_stand", "rummy_rack", "domino_racks"]


def _derive_gifts(subject: dict, mesh_id: str) -> list[dict]:
    """Rank product lines for one friend. Pets -> mini figure lines (their
    mesh is the gift); people -> name-emboss lines + cards. Birthday soon
    pulls cards and gift card to the top. Nibble/Dad/Mum are just friends —
    kind + name + interests do the work, no hardcoded people."""
    name = (subject.get("name") or "").strip()
    interests = subject.get("interests", []) or []
    birthday = (subject.get("birthday") or "").strip()
    gifts: list[dict] = []
    # Anyone with a mesh can be a mini — pets and people alike. Nibble the
    # dog and Dad the human take the same path; the mesh is the gift.
    if mesh_id:
        who = name or "your star"
        for lid in _PET_LINES:
            spec = config.STUDIO_LINES.get(lid) or {}
            if spec.get("status") != "live":
                continue
            gifts.append({"line": lid, "label": spec.get("label", lid),
                          "method": "mini",
                          "reason": f"mini {who} — their mesh is the gift",
                          "mesh_id": mesh_id})
    # Anyone with a name can have it put on things — golf balls for Dad,
    # book holders for Mum, same engine.
    if name:
        for lid in _PERSON_LINES:
            spec = config.STUDIO_LINES.get(lid) or {}
            if spec.get("status") != "live":
                continue
            zone_max = ((spec.get("personalization") or {}).get("max_chars")) or 0
            # never truncate silently: Oddy asks when the name won't fit
            fits = not zone_max or len(name) <= zone_max
            gifts.append({"line": lid, "label": spec.get("label", lid),
                          "method": "name",
                          "reason": f"for {name} — their name on it",
                          "text": name if fits else "",
                          "fits": fits,
                          "needs_shorten": not fits})
        gifts.append({"line": "gift_card", "label": "Gift card",
                      "method": "credit",
                      "reason": f"for {name} — credit toward anything",
                      "text": ""})
    try:
        import datetime as _dt
        if birthday and len(birthday) >= 5:
            today = _dt.date.today()
            nxt = _dt.date(today.year, int(birthday[:2]), int(birthday[3:5]))
            if nxt < today:
                nxt = _dt.date(today.year + 1, int(birthday[:2]), int(birthday[3:5]))
            if 0 <= (nxt - today).days <= 45:
                gifts.insert(0, {"line": "gift_card", "label": "Gift card",
                                 "method": "credit",
                                 "reason": f"{name}'s birthday is soon",
                                 "text": ""})
    except (ValueError, IndexError):
        pass
    motif = _suggest_motif(interests)
    if motif:
        for g in gifts:
            g["motif"] = motif["motif"]
    return gifts


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


def _parse_birthday(raw: str):
    """Canonical house format is MM-DD (guide.py writes it). Tolerates
    YYYY-MM-DD and MM/DD; anything else → None. Returns (month, day)."""
    import re as _re
    s = (raw or "").strip()
    m = _re.fullmatch(r"(\d{2})-(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _re.fullmatch(r"\d{4}-(\d{2})-(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _re.fullmatch(r"(\d{2})/(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


@app.get("/api/family/reminders")
def family_reminders():
    """Birthday countdowns: who, when, gift + funny-card suggestions.

    Birthdays are PII — owner-enforced (key, sig, or session), unlike the
    open catalog reads. Email composes but does not send: no mail provider
    key is configured, so the response carries the ready-to-send draft.
    """
    import datetime as _dt
    owner = (request.args.get("owner") or "").strip()[:80]
    try:
        within = max(1, min(120, int(request.args.get("within_days") or 30)))
    except (TypeError, ValueError):
        return _err("within_days must be 1-120", 400)
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    try:
        from backend import card_scenes as _scenes
        templates = list(_scenes.BIRTHDAY_TEMPLATES)
    except Exception:
        templates = ["birthday_4photo", "birthday_wall", "birthday_dots"]
    from backend import subjects as _subjects
    today = _dt.date.today()
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        active = prof.get("active_mesh_id") or ""
        try:
            user = c.execute("SELECT email FROM users WHERE handle=?",
                             (owner,)).fetchone()
            email = (dict(user).get("email") or "") if user else ""
        except Exception:
            email = ""
        out = []
        _subjects.ensure_tables(c)
        for s in _subjects.subjects_for(c, owner):
            full = _subjects.profile_for(c, owner, s["id"])
            parsed = _parse_birthday(full.get("birthday", ""))
            if not parsed:
                continue
            mm, dd = parsed
            try:
                nxt = _dt.date(today.year, mm, dd)
            except ValueError:
                continue
            if nxt < today:
                try:
                    nxt = _dt.date(today.year + 1, mm, dd)
                except ValueError:
                    continue
            days = (nxt - today).days
            if days > within:
                continue
            prof_json = full.get("profile", {}) or {}
            subject = {"name": s["name"],
                       "interests": prof_json.get("interests", []),
                       "birthday": full.get("birthday", "")}
            gifts = _derive_gifts(subject, active)
            try:
                from backend import subject_assets as _sa
                res = _sa.resolve(s["id"], owner)
                hero = (res.get("face_candidates") or [{}])[0].get("asset_id")
            except Exception:
                hero = None
            fams = [r["name"] for r in c.execute(
                "SELECT f.name FROM family_members fm JOIN families f"
                " ON f.id=fm.family_id WHERE fm.subject_id=? AND f.owner=?",
                (s["id"], owner,)).fetchall()]
            name = s["name"] or "someone"
            lines = ", ".join(g["label"] for g in gifts[:3])
            out.append({
                "subject_id": s["id"], "name": s["name"],
                "kind": s.get("kind", "person"),
                "relationship": full.get("relationship", ""),
                "birthday": full.get("birthday", ""),
                "date": nxt.isoformat(), "days_until": days,
                "families": fams, "hero_photo": hero,
                "gifts": gifts, "card_templates": templates,
                "email": {
                    "ready": bool(email),
                    "to": email,
                    "subject": f"{name}'s birthday in {days} day(s) — gift idea inside",
                    "body": (f"{name}'s birthday is {nxt.isoformat()} ({days} day(s)). "
                             f"Top picks: {lines}. "
                             f"Card templates: {', '.join(templates[:3])}. "
                             + ("" if email else "Add an email to this account to receive pings.")),
                    "note": ("staged — no mail provider key configured" if not email
                             else "staged — sending not yet wired to a provider"),
                },
            })
    out.sort(key=lambda r: r["days_until"])
    return jsonify({"ok": True, "owner": owner, "within_days": within,
                    "reminders": out})


@app.get("/api/onboarding/aesthetic")
def onboarding_aesthetic_pairs():
    """Aesthetic picker: 3 A/B/skip pairs for maximal signal (service-gated,
    no owner needed to SEE the pairs; saving needs the owner)."""
    return jsonify({"ok": True, "pairs": config.AESTHETIC_PAIRS,
                    "hint": "pick a, b, or skip per pair — skip means don't care"})


@app.post("/api/onboarding/aesthetic")
def onboarding_aesthetic_save():
    """Save aesthetic picks: {owner, subject_id, picks: {pair_id: a|b|skip}}.
    Tallies coat + pattern votes into profile aesthetic.colors ranked.
    Owner-enforced (profile PII)."""
    from backend import subjects as _subjects
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    sid = (body.get("subject_id") or "").strip()[:80]
    picks = body.get("picks") or {}
    if not owner or not sid or not isinstance(picks, dict):
        return _err("owner, subject_id and picks are required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    valid = {p["id"]: p for p in config.AESTHETIC_PAIRS}
    votes: dict[str, int] = {}
    pat_votes: dict[str, int] = {}
    saved = {}
    for pid, choice in picks.items():
        if pid not in valid or choice not in ("a", "b", "skip"):
            continue
        saved[pid] = choice
        if choice == "skip":
            continue
        side = valid[pid][choice]
        for coat in side.get("coats", []):
            votes[coat] = votes.get(coat, 0) + 1
        for pat in side.get("patterns", []):
            pat_votes[pat] = pat_votes.get(pat, 0) + 1
    colors = sorted(votes, key=lambda c: (-votes[c], c))
    patterns = sorted(pat_votes, key=lambda p: (-pat_votes[p], p))
    with db.connect() as c:
        if not _subjects.get_subject(c, owner, sid):
            return _err("friend not found", 404)
        prof = _subjects.set_profile(
            c, owner, sid,
            profile={"aesthetic": {"colors": colors, "patterns": patterns,
                                   "picks": saved}})
    return jsonify({"ok": True, "subject_id": sid,
                    "aesthetic": (prof.get("profile", {}) or {}).get("aesthetic", {}),
                    "hint": "personalise now auto-picks these colours where lines allow"})


@app.get("/api/objects/<oid>/resolve")
def objects_resolve(oid: str):
    """Resolve for AR clients (QR/NFC scan → this URL with service token).
    No owner needed and no PII in the response: digital asset,
    capabilities, live event state, compatible worlds."""
    from backend import objects as _ob
    rec = _ob.get(oid.strip()[:80])
    if not rec:
        return _err("object not found", 404)
    return jsonify({"ok": True, "object_id": rec["object_id"],
                    "kind": rec["kind"], "digital_asset": rec["digital_asset"],
                    "physical_revision": rec["physical_revision"],
                    "capabilities": rec["capabilities"], "state": rec["state"],
                    "compatible_worlds": rec["compatible_worlds"],
                    "manufacturing_status": rec["manufacturing_status"]})


@app.post("/api/objects")
def objects_register():
    """Register an agent-addressable object. Owner-enforced."""
    from backend import objects as _ob
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    rec = _ob.register(
        owner, kind=str(body.get("kind") or "room"),
        digital_asset=str(body.get("digital_asset") or ""),
        recipe_id=str(body.get("recipe_id") or ""),
        capabilities=body.get("capabilities") if isinstance(
            body.get("capabilities"), list) else [],
        compatible_worlds=body.get("compatible_worlds") if isinstance(
            body.get("compatible_worlds"), list) else [])
    return jsonify({"ok": True, **rec})


@app.post("/api/objects/<oid>/state")
def objects_state(oid: str):
    """Record an agent event (working/finished_artwork/visitor/...).
    Owner-enforced — actuation-adjacent."""
    from backend import objects as _ob
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    r = _ob.set_state(owner, oid.strip()[:80], str(body.get("event") or ""),
                      body.get("detail") if isinstance(body.get("detail"), dict)
                      else None)
    if not r.get("ok"):
        return _err(r.get("error", "state failed"), 400)
    return jsonify(r)


@app.get("/api/orders/track")
def orders_track():
    """Track one order by id: status, lines, price, checkout links.
    Owner-enforced (order PII). Provider tracking refs surface when the
    order note carries them; external carrier tracking stays provider-side.
    """
    owner = (request.args.get("owner") or "").strip()[:80]
    oid = (request.args.get("order_id") or "").strip()[:80]
    if not owner or not oid:
        return _err("owner and order_id are required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        order = None
        row = c.execute("SELECT * FROM orders WHERE id=? AND owner=?",
                        (oid, owner)).fetchone()
        if row:
            order = {"kind": "product", **dict(row)}
        else:
            try:
                cols = [r[1] for r in
                        c.execute("PRAGMA table_info(card_orders)").fetchall()]
                if cols:
                    r2 = c.execute(
                        "SELECT * FROM card_orders WHERE id=? AND owner=?",
                        (oid, owner)).fetchone()
                    if r2:
                        order = {"kind": "card", **dict(r2)}
            except Exception:
                pass
    if not order:
        return _err("order not found", 404)
    return jsonify({"ok": True, "order": order,
                    "note": "provider tracking refs ride in note/checkout_url"})


# ── guided personal shopper ───────────────────────────────────────────
# Person first, no search bar: ramble -> profile -> photos -> mesh -> packs.

CARD_A6_CENTS = 500  # cheapest card format; MP4 greetings are free-tier
SHELF_MAX = 8


def _guide_shelf(state: dict) -> list[dict]:
    """Ranked alternatives with truthful reasons — not bundles.

    Scores the ramble (full log) plus interests against every live line;
    disliked interests veto outright. Sorted best-first, capped.
    """
    rec = state.get("recipient", {})
    suggestion = _suggest_motif(rec.get("interests", []))
    prefs = state.get("prefs", {})
    excluded = set(prefs.get("exclude", []))
    dislikes = set(rec.get("dislikes", []))
    motif = prefs.get("motif") or (suggestion or {}).get("motif", "")
    corpus = " ".join([e.get("turn", "") for e in state.get("log", [])]
                      + rec.get("interests", []) + ([motif] if motif else []))
    shelf = []
    for lid, spec in config.STUDIO_LINES.items():
        if spec.get("status") != "live" or spec.get("fulfilment") == "digital":
            continue
        if lid in excluded:
            continue
        hay = f"{lid} {spec.get('label', '')} {spec.get('blurb', '')} {spec.get('theme', '')}".lower()
        if any(d and d in hay for d in dislikes):
            continue  # stated dislike beats a passing match
        score = _quick_score(hay, corpus)
        if lid.replace("_", " ") in corpus.lower():
            score += 4.0  # named outright mid-ramble
        if score <= 0:
            continue
        why = ""
        if motif:
            why = f"Picked for {rec.get('name') or 'them'}: {motif.replace('_', ' ')}."
        elif suggestion:
            why = (f"Picked for {rec.get('name') or 'them'}: "
                   f"{suggestion['motif'].replace('_', ' ')} "
                   f"({suggestion['interest']}).")
        shelf.append({
            "id": lid, "label": spec.get("label", lid),
            "price_cents": spec.get("price_cents", 0),
            "material": spec.get("material"), "dims_mm": spec.get("dims_mm"),
            "stills": _studio_stills_for(lid, "none", "none"),
            "customization_schema": _custom_schema(lid, spec),
            "motif": motif, "why": why, "score": round(score, 2),
        })
    shelf.sort(key=lambda i: -i["score"])
    return shelf[:SHELF_MAX]


def _guide_bundles(state: dict, shelf: list[dict]) -> list[dict]:
    """Up to 3 purchasable bundles with validated totals.

    Bundle = physical + A6 card + MP4 greeting. Shipping is UNKNOWN until
    checkout, so totals are stated ex-shipping and a bundle is only quoted
    when the known total fits the budget. Unknown delivery stays unknown.
    """
    budget = state.get("budget_cents") or 0
    rec = state.get("recipient", {})
    bundles = []
    for item in shelf:
        total = item["price_cents"] + CARD_A6_CENTS  # MP4 is free-tier
        if budget and total > budget:
            continue
        bundles.append({
            "id": f"pack_{item['id']}",
            "label": f"{rec.get('name') or 'Gift'} pack: {item['label']}",
            "physical": item, "card_format": "A6", "card_cents": CARD_A6_CENTS,
            "mp4_cents": 0, "total_cents": total,
            "shipping": "unknown — added at checkout",
            "within_budget": True,
        })
        if len(bundles) >= 3:
            break
    return bundles


def _guide_pack_items(owner: str, state: dict, active_mesh: str = "") -> list[dict]:
    """Legacy theme groups (kept for the products grid); shelf+bundles are
    the shopper surface. Max 3 per theme — the customer never scrolls."""
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
    owner = _own(body.get("owner") or "")
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
    seq = body.get("seq") or body.get("transcript_seq") or 0
    try:
        seq = int(seq)
    except (ValueError, TypeError):
        seq = 0
    speak = body.get("speak", True)
    if not isinstance(speak, bool):
        speak = True
    with db.connect() as c:
        s = _g.get_session(c, sid, owner)
        if not s:
            return _err("no such session", 404)
        state, stage = s["state"], s["stage"]
        if seq and seq <= int(state.get("last_seq", 0)):
            # stale/async transcript replay: idempotent snapshot, no rework
            return jsonify({"ok": True, "session_id": sid, "stage": stage,
                            "stale": True, "rev": state.get("revision", 0),
                            "recipient": state.get("recipient", {}),
                            "events": state.get("events", [])})
        if seq:
            state["last_seq"] = seq
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
            if state.get("delivery", {}).get("deadline"):
                _g.answer_prompt(state, "deadline")
            if state.get("delivery", {}).get("destination"):
                _g.answer_prompt(state, "destination")
            packs = _guide_pack_items(owner, state)
            reply = ("Done" + (": " + ", ".join(changed) if changed else
                                " — tell me budget, motif, or what to drop") + ".")
            prompt = _g.next_prompt(state)
            _g.save_session(c, sid, owner, "refining", state)
            return jsonify({"ok": True, "session_id": sid, "stage": "refining",
                            "reply": reply, "packs": packs,
                            "prompt": prompt, "speak": speak,
                            "rev": state.get("revision", 0),
                            "events": state.get("events", [])})
        state, prompt = _g.ramble_turn(state, text)
        rec = state.get("recipient", {})
        if rec.get("name") and state.get("occasion") and state.get("budget_cents"):
            stage = "photos"
        if rec.get("name"):
            _g.answer_prompt(state, "who")
        if state.get("occasion"):
            _g.answer_prompt(state, "occasion")
        if state.get("budget_cents"):
            _g.answer_prompt(state, "budget")
        float_prompt = _g.next_prompt(state)
        _g.save_session(c, sid, owner, stage, state)
        return jsonify({"ok": True, "session_id": sid, "stage": stage,
                        "reply": prompt, "recipient": rec,
                        "occasion": state.get("occasion", ""),
                        "budget_cents": state.get("budget_cents", 0),
                        "prompt": float_prompt, "speak": speak,
                        "rev": state.get("revision", 0),
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
        if have:
            _g.answer_prompt(state, "photos")
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
        shelf = _guide_shelf(state)
        bundles = _guide_bundles(state, shelf)
        _g.emit(state, "picks.updated",
                {"shelf": [i["id"] for i in shelf],
                 "bundles": [b["id"] for b in bundles]})
        _g.save_session(c, sid, owner, s["stage"], state)
    return jsonify({"ok": True, "session_id": sid, "packs": packs,
                    "shelf": shelf, "bundles": bundles,
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


@app.get("/privacy", strict_slashes=False)
@app.get("/privacy/")
def privacy_policy():
    """Privacy policy (Google OAuth verification + footer link)."""
    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy — OddHobb</title>
<meta name="description" content="How OddHobb accesses, uses, stores and shares your data, including Google account data.">
<link rel="canonical" href="https://oddhobb.com/privacy">
<style>body{font:16px/1.55 system-ui,sans-serif;max-width:44rem;margin:2rem auto;padding:0 1rem;color:#111}
h1{font-size:1.7rem}h2{font-size:1.15rem;margin-top:1.6rem}li{margin:.3rem 0}}</style>
</head><body>
<p><a href="/">OddHobb</a> / privacy</p>
<h1>Privacy Policy</h1>
<p>Last updated: 7 October 2026. OddHobb (oddhobb.com, support@oddhobb.com)
makes personalised gifts from your photos. This page discloses what data we
access, use, store and share — including Google user data.</p>
<h2>Google account data</h2>
<p>When you choose “Continue with Google” we request three scopes only:
<code>openid</code>, <code>email</code> and <code>profile</code>. Google sends us
your verified email address, your name, and your Google subject ID. We use the
email to find or create your OddHobb account (so work you made anonymously is
adopted, never lost) and the name as your display name. We do not request or
receive your contacts, calendar, Drive files, or any other Google data. We do
not use Google data for advertising, and we do not sell it.</p>
<h2>What you create</h2>
<ul>
<li>Photos you upload, meshes and cards you make, people profiles you name.</li>
<li>Voice reference audio and enrollment consents, only when you explicitly
enroll a voice — revocable at any time.</li>
<li>Bring-your-own provider keys, encrypted server-side and never shown to
agents or stored in revisions.</li>
</ul>
<h2>What we share, and with whom</h2>
<ul>
<li><b>Meshy</b> receives uploaded photo bytes solely to sculpt your mesh.</li>
<li><b>Print/fulfilment suppliers</b> (e.g. Shopify drafts, print farms) receive
only what an order needs — product, quantity and note. Drafts carry no email address.</li>
<li><b>Creative providers you connect</b> (fal, Higgsfield, Alibaba) receive
only the job inputs, billed to your own account with them — never ours.</li>
<li>We never sell personal data to anyone.</li>
</ul>
<h2>Storage and retention</h2>
<p>Data lives in our UK/EU-hosted store. API keys are shown once. Delete your
account and its data any time by writing to support@oddhobb.com from your
account email; provider connections and voice consents are revoked first.</p>
<h2>Contact</h2>
<p>Questions about this policy: support@oddhobb.com.</p>
</body></html>"""
    return Response(html, content_type="text/html; charset=utf-8")


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
    urls = ["/", "/learn/", "/privacy", "/llms.txt", "/api/seo/products.json",
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
    owner = _own(request.args.get("owner") or "")
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
    """Legacy view of explicit labels only. Image hashes cannot identify people."""
    owner=(request.args.get("owner") or request.form.get("owner") or "anon").strip()[:80]
    denied=_owner_denied(owner)
    if denied is not None: return denied
    with db.connect() as c:
        rows=[dict(r) for r in c.execute("SELECT id,r2_key,person,mime FROM photos WHERE owner=? ORDER BY created_at",(owner,))]
        meshes={r["photo_id"]:r["id"] for r in c.execute("SELECT m.id,m.photo_id FROM meshes m JOIN photos p ON p.id=m.photo_id WHERE p.owner=?",(owner,))}
    groups={}
    for row in rows:
        name=row["person"] or ""
        if re.fullmatch(r"Person\s+\d+",name,re.I): name=""
        key=name or row["id"]
        g=groups.setdefault(key,{"person":name or "Unassigned","needs_name":not bool(name),"photos":[]})
        g["photos"].append({"id":row["id"],"mime":row["mime"],"r2_key":row["r2_key"],"has_mesh":row["id"] in meshes,"mesh_id":meshes.get(row["id"])})
    return jsonify(ok=True,owner=owner,groups=list(groups.values()),count=len(rows),strategy="explicit_labels_only")


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
    claim = (b.get("claim_owner") or "").strip()
    if claim:
        denied=_owner_denied(claim)
        if denied is not None:
            return denied

    try:
        with card_api.ownership_lock, db.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if claim and c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND status IN ('queued','running') LIMIT 1",(claim,)).fetchone():
                return _err("Your card is still rendering. Finish the render, then sign up again.",409)
            if not _auth_rate("signup", ip):
                return _err("too many account attempts — try again later",429)
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
            storage.claim_owner(claim, user["handle"], preserve_photos=bool(claimed.get("card_designs") or claimed.get("card_cutouts")))
        except Exception:
            pass   # rows keep their old keys, which still resolve
    starters = []
    ref = (b.get("ref") or "").strip()[:80]
    if ref:
        # viral funnel: shared clip -> signup -> starter meshes to modify
        # cheaply -> first upload -> own sets. Prompt+script already live
        # on the video row; starters are free styles, 0 credits.
        from backend import styles as _styles
        for sid in ("buster", "badger-classic"):
            try:
                m = _styles.install_style(user["handle"], sid)
                starters.append({"style": sid, "mesh_id": (m.get("mesh") or {}).get("id", "")})
            except Exception:
                pass

    return jsonify({"ok": True, "handle": user["handle"],
                    "api_key": user["api_key"],        # shown once
                    "password_set": bool(password),
                    "claimed_from": claim or None,
                    "claimed": claimed,
                    "referred_by_video": ref or None,
                    "starter_meshes": starters,
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
    claimed = {}
    claim = (b.get("claim_owner") or "").strip()
    if claim and claim != u["handle"]:
        denied = _owner_denied(claim)
        if denied is not None:
            return denied
        with card_api.ownership_lock, db.connect() as c:
            if c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND status IN ('queued','running') LIMIT 1", (claim,)).fetchone():
                return _err("Your card is still rendering. Finish the render, then sign in again.", 409)
            claimed = db.claim_assets(c, claim, u["handle"])
        try:
            storage.claim_owner(claim, u["handle"], preserve_photos=True)
        except Exception:
            pass
    _auth_rate_reset("login", f"{ip}:{handle.lower()}")
    return jsonify({"ok": True, "handle": u["handle"],
                    "display_name": u["display_name"], "api_key": u["api_key"],
                    "claimed_from": claim or None, "claimed": claimed,
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


def _own(raw: str = "") -> str:
    """Owner for this call: explicit owner wins, else the key holder's
    handle, else anon. Lets keyed callers omit ?owner= without 403ing."""
    raw = (raw or "").strip()[:80]
    if raw:
        return raw
    h, kind, _ = _principal()
    if kind in ("user", "agent") and h:
        return h
    return "anon"


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
    if not perms:
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

_OAUTH_CLAIM: dict[str, str] = {}
_OAUTH_RETURN: dict[str, str] = {}
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
    claim = request.args.get('claim_owner','')
    if claim:
        denied=_owner_denied(claim)
        if denied is not None: return denied
        with db.connect() as c:
            if c.execute("SELECT 1 FROM card_jobs WHERE owner=? AND status IN ('queued','running')",(claim,)).fetchone(): return _err('Finish the current card render before signing in.',409)
            if db.get_user_by_handle(c,claim) or c.execute('SELECT 1 FROM agents WHERE agent_handle=?',(claim,)).fetchone(): claim=''
    st = gauth.make_state()
    _OAUTH_CLAIM[st]=claim
    _OAUTH_STATE[st] = time.time()
    dest=request.args.get("return_to", "/")
    if not re.fullmatch(r"/(?:studio(?:/people/[\w-]+)?|products(?:/[\w-]+)?|cards(?:/[\w-]+)?|videos(?:/[\w-]+)?|perform|search|cart|account)?(?:\?[^#\r\n]*)?",dest): dest="/"
    _OAUTH_RETURN[st]=dest
    # keep the dict from growing forever
    for k, t in list(_OAUTH_STATE.items()):
        if time.time() - t > 600:
            _OAUTH_STATE.pop(k, None)
            _OAUTH_RETURN.pop(k, None)
            _OAUTH_CLAIM.pop(k, None)
    return redirect(gauth.authorize_url(st), code=302)


@app.get("/api/auth/google/callback")
def google_callback():
    code = request.args.get("code", "")
    st = request.args.get("state", "")
    if not code:
        return _err(f"google returned no code: {request.args.get('error', '')}", 400)
    if not _OAUTH_STATE.pop(st, None):
        return _err("bad or expired sign-in state — try again", 400)
    return_to = _OAUTH_RETURN.pop(st, "/")
    claim = _OAUTH_CLAIM.pop(st, "")
    try:
        profile = gauth.exchange(code)
    except Exception as e:
        return _err(f"google sign-in failed: {str(e)[:250]}", 502)
    if not profile.get("email"):
        return _err("google did not return an email address", 403)
    try:
        user = _ensure_google_user(profile)
        if claim and claim != user['handle']:
            with card_api.ownership_lock, db.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                db.claim_assets(c,claim,user['handle'])
                prof=db.get_profile(c,claim)
                if prof.get('active_mesh_id'): db.set_active(c,user['handle'],prof['active_mesh_id'])
                c.commit()
            # Photo keys remain immutable, as do pinned card revisions.
            try:
                storage.claim_owner(claim,user['handle'],preserve_photos=True)
            except Exception:
                pass  # DB-owned immutable keys still resolve without a copy.
    except Exception as e:
        return _err(f"could not open an account: {str(e)[:250]}", 500)
    # hand the key back to the SPA, which stores it and strips it from the URL
    sep = "&" if "?" in return_to else "?"
    dest = f"{config.PUBLIC_BASE.rstrip('/')}{return_to}{sep}auth={urllib.parse.quote(user['api_key'])}" \
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
    from backend import qwen_voice as _qv
    qwen = [{"key": "qwen:iris", "label": "Iris — Qwen clone-ready (needs HF token)",
             "id": "qwen3-tts", "needs_token": True, "live": _qv.configured()},
            {"key": "qwen:hero", "label": "Hero — Qwen deep (needs HF token)",
             "id": "qwen3-tts", "needs_token": True, "live": _qv.configured()}]
    return jsonify({"ok": True,
                    "voices": [{"key": k, "label": v["label"], "id": v["id"]}
                               for k, v in video.VOICES.items()] + qwen,
                    "scenes": [{"key": k, "label": v, "free": True}
                               for k, v in config.SCENES.items()]})


@app.post("/api/videos")
def make_video():
    """The wedge: free talking/comedy video. Spends a video credit first."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or request.args.get("owner") or "")
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
        face_box = None
        if photo:
            try:
                import json as _json
                frow = c.execute("SELECT box FROM photo_faces WHERE photo_id=? LIMIT 1",
                                 (photo["id"],)).fetchone()
                if frow:
                    face_box = _json.loads(dict(frow)["box"])
            except Exception:  # noqa: BLE001 — crop falls back to top-weighted
                face_box = None
        if photo and mesh and not face_box:
            # prefer the mesh's own front render over the photo: the performer
            # is the 3D character, not a circle-cropped upload
            try:
                import json as _json2
                thumbs = _json2.loads(mesh.get("thumb_keys") or "[]")
            except Exception:  # noqa: BLE001
                thumbs = []
            for tk in thumbs[:1]:
                try:
                    dest = config.LOCAL_TMP / f"vidmesh_{mesh_id}.png"
                    storage.get(tk, dest)
                    photo_path = dest
                    break
                except Exception:  # noqa: BLE001
                    continue

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
            face_box=face_box,
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
            "script,lines,watermarked,duration,bytes,path,created_at,"
            "creative_project_id,creative_revision,renderer)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vid, owner, mesh_id, rec["scene"], rec.get("talent", "comedy"),
             rec["voice"],
             str(body.get("pet_name") or "your pet")[:40], topic,
             rec["script"], json.dumps(rec["lines"]), 1 if rec["watermarked"] else 0,
             rec["duration"], rec["bytes"], rec["file"], db.now(),
             str(body.get("project_id") or ""), int(body.get("revision") or 0),
             str(body.get("renderer") or "")),
        )
        left = config.FREE_DAILY["video"] - db.credit_used(c, owner, day, "video")
        try:
            import hashlib as _hl
            from backend import subjects as _subs
            _subs.register_asset(c, owner, "video",
                                 _hl.sha256(f"{vid}".encode()).hexdigest(),
                                 rec["file"],
                                 metadata={"video_id": vid, "mesh_id": mesh_id,
                                           "duration": rec["duration"]},
                                 provenance="perform")
        except Exception:  # noqa: BLE001 — registry must never break renders
            pass

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
            "script,lines,watermarked,duration,bytes,path,created_at,"
            "creative_project_id,creative_revision,renderer)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vid, owner, mesh_id, rec["scene"], "greeting", rec["voice"],
             speaker, message,
             rec["script"], json.dumps(rec["lines"]), 1 if rec["watermarked"] else 0,
             rec["duration"], rec["bytes"], rec["file"], db.now(),
             str(body.get("project_id") or ""), int(body.get("revision") or 0),
             str(body.get("renderer") or "")),
        )
        left = config.FREE_DAILY["video"] - db.credit_used(c, owner, day, "video")

    return jsonify({"ok": True, "video": {**rec, "id": vid, "file": None},
                    "download": f"/api/videos/{vid}/file",
                    "credits_remaining": left,
                    "cost": 0})


@app.get("/api/voice/models")
def voice_models():
    """Swappable voice brains: active provider + model ids. No secrets."""
    from backend import voice_chat as _vc
    prov = _vc.active_provider()
    return jsonify({"ok": True, "provider": prov.name,
                    "configured": prov.is_configured(),
                    "models": prov.list_models(),
                    "override": "GEMINI_VOICE_PROVIDER / GEMINI_VOICE_MODEL"})


@app.post("/api/voice/session")
def voice_session():
    """Open a voice-shopper session. Live provider mints an ephemeral browser
    token (single-use, 30 min); stub returns typed-turn sessions offline."""
    from backend import voice_chat as _vc
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    try:
        sess = _vc.active_provider().create_session(
            owner, body.get("tools") or None)
    except _vc.VoiceError as e:
        return _err(str(e), 503)
    # The token goes to the authenticated owner in-band (that IS the design);
    # it is never written to logs, disk, or error messages.
    return jsonify({**sess,
                    "connect": "wss with ephemeral_token as the API key"})


@app.post("/api/voice/room")
def voice_room():
    """Bind a LiveKit room to a guide session for one authenticated shopper.

    Verifies existing owner proof, creates or resumes the session, assigns a
    private room, and stores the binding server-side. The browser receives its
    room token; model tools receive a scoped server-side capability bound to
    the session owner — the model never chooses the owner. Worker dispatch
    stays pending until LiveKit credentials exist (see docs/voice-room.md).
    """
    from backend import guide as _g
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "").strip()[:80]
    sid = (body.get("session_id") or "").strip()
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        if sid:
            s = _g.get_session(c, sid, owner)
            if not s:
                return _err("no such session", 404)
        else:
            sid = _g.new_id()
            _g.save_session(c, sid, owner, "ramble", _g.blank_state())
            s = _g.get_session(c, sid, owner)
        state = s["state"]
        room = (state.get("room") or {})
        if not room.get("id"):
            room = {"id": f"shop-{sid}", "created_at":
                    datetime.now(timezone.utc).timestamp(),
                    "worker": "pending-no-worker"}
            state["room"] = room
            _g.emit(state, "render.updated", {"room": room["id"]})
            _g.save_session(c, sid, owner, s["stage"], state)
    return jsonify({"ok": True, "room": room["id"], "session_id": sid,
                    "owner": owner, "rev": state.get("revision", 0),
                    "worker": room.get("worker"),
                    "capability": "session-owner-scoped: model tools act for "
                                  "this session's owner only",
                    "shelf_modes": "ramble listens (no speech); dialogue speaks"})


@app.get("/api/guide/feed")
def guide_feed():
    """Structured UI events since a revision (reconnect-safe polling)."""
    from backend import guide as _g
    owner = (request.args.get("owner") or "").strip()[:80]
    sid = (request.args.get("session_id") or "").strip()
    try:
        since = int(request.args.get("since_rev") or 0)
    except (ValueError, TypeError):
        since = 0
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        s = _g.get_session(c, sid, owner)
        if not s:
            return _err("no such session", 404)
        evs = [e for e in s["state"].get("feed", []) if e.get("rev", 0) > since]
    return jsonify({"ok": True, "session_id": sid, "rev": s["state"].get("revision", 0),
                    "events": evs})


@app.get("/api/guide/snapshot")
def guide_snapshot():
    """Full session snapshot for reconnect: state, packs, shelf, bundles."""
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
        shelf = _guide_shelf(state)
        bundles = _guide_bundles(state, shelf)
    return jsonify({"ok": True, "session_id": sid, "stage": s["stage"],
                    "rev": state.get("revision", 0), "state": state,
                    "shelf": shelf, "bundles": bundles,
                    "prompt": _g.next_prompt(state, record=False)})


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


@app.post("/api/jokes/premise")
def jokes_premise():
    """Writing help from pogtown's room: one premise for the perform tab."""
    from backend import jokes as _jokes
    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()[:200]
    if not topic:
        return _err("give me the bit first", 400)
    try:
        out = _jokes.call("pog_premise", {"topic": topic,
                                          "persona": str(body.get("persona") or "")[:60]})
    except _jokes.JokeRoomDown as e:
        return _err(str(e), 502)
    return jsonify({"ok": True, **out})


@app.post("/api/jokes/riff")
def jokes_riff():
    """Tags and alts for one line, from the writing room."""
    from backend import jokes as _jokes
    body = request.get_json(silent=True) or {}
    line = (body.get("line") or "").strip()[:300]
    if not line:
        return _err("give me the line first", 400)
    try:
        out = _jokes.call("pog_riff", {"line": line})
    except _jokes.JokeRoomDown as e:
        return _err(str(e), 502)
    return jsonify({"ok": True, **out})


@app.post("/api/videos/<vid>/share")
def video_share(vid: str):
    """One-click share: link to the clip tab carrying ?ref=. The prompt and
    script already live on the video row, so shared sets are replayable.
    Signup with the ref installs free starter meshes."""
    with db.connect() as c:
        row = c.execute("SELECT id,topic,talent,mesh_id FROM videos WHERE id=?", (vid,)).fetchone()
    if row is None:
        return _err("no such video", 404)
    return jsonify({"ok": True, "share_url": f"/videos/{vid}?ref={vid}",                    "topic": row["topic"], "talent": row["talent"],
                    "hint": "Send the link. Signup with ?ref= installs starter meshes."})


@app.post("/api/videos/<vid>/clips")
def video_clips(vid: str):
    """Viral cut-list for a finished clip: full, hook, social, tail reveal.
    Time-based cuts (no fake laugh detection); pass {"render": true} to also
    write the MP4s. Shares point at cuts via /videos/<vid>?clip=<id>."""
    from backend import clips as _clips
    from pathlib import Path as _Path
    body = request.get_json(silent=True) or {}
    with db.connect() as c:
        row = c.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    if row is None:
        return _err("no such video", 404)
    d = db.dump(row)
    src = _Path(d.get("path") or "")
    if not src.is_file():
        return _err("clip file missing", 404)
    plan = _clips.plan(_clips.probe_duration(src))
    out = []
    if body.get("render"):
        for cut in plan["cuts"]:
            dest = src.parent / f"{src.stem}-{cut['id']}.mp4"
            try:
                _clips.render_cut(src, cut["start"], cut["end"], dest)
                out.append({**cut, "file": f"/api/videos/{vid}/clip/{cut['id']}",
                            "ready": True})
            except Exception as e:  # noqa: BLE001
                out.append({**cut, "ready": False, "error": str(e)[:150]})
    else:
        out = [{**c, "file": f"/api/videos/{vid}/clip/{c['id']}", "ready": False}
               for c in plan["cuts"]]
    return jsonify({"ok": True, "video_id": vid, "plan": plan, "clips": out})


@app.get("/api/videos/<vid>/clip/<cid>")
def video_clip_file(vid: str, cid: str):
    """Fetch a rendered cut."""
    import re as _re
    if not _re.fullmatch(r"[a-z0-9-]+", cid or ""):
        return _err("bad clip", 400)
    with db.connect() as c:
        row = c.execute("SELECT path FROM videos WHERE id=?", (vid,)).fetchone()
    if row is None:
        return _err("no such video", 404)
    from pathlib import Path as _Path
    src = _Path(row["path"])
    target = (src.parent / f"{src.stem}-{cid}.mp4").resolve()
    if not str(target).startswith(str(src.parent.resolve())) or not target.is_file():
        return _err("cut not rendered yet — POST clips with render:true", 404)
    data = target.read_bytes()
    resp = Response(data)
    resp.headers["Content-Type"] = "video/mp4"
    resp.headers["Content-Length"] = str(len(data))
    return resp


@app.get("/api/videos/<vid>/file")
def video_file(vid: str):
    with db.connect() as c:
        row = c.execute("SELECT path FROM videos WHERE id=?", (vid,)).fetchone()
    if row is None or not row["path"]:
        return _err("no such video", 404)
    p = Path(row["path"])
    if not p.is_file():
        return _err("render missing", 404)
    size = p.stat().st_size
    rng = (request.headers.get("Range") or "").strip()
    if rng.startswith("bytes="):
        try:
            spec = rng[6:].split("-", 1)
            start = int(spec[0] or 0)
            end = int(spec[1]) if len(spec) > 1 and spec[1] else size - 1
            start = max(0, min(start, size - 1))
            end = max(start, min(end, size - 1))
            with p.open("rb") as f:
                f.seek(start)
                chunk = f.read(end - start + 1)
            return Response(chunk, status=206, content_type="video/mp4",
                            headers={"Content-Range": f"bytes {start}-{end}/{size}",
                                     "Accept-Ranges": "bytes",
                                     "Content-Length": str(end - start + 1),
                                     "Cache-Control": "private, max-age=3600"})
        except (ValueError, OSError):
            pass
    return Response(p.read_bytes(), content_type="video/mp4",
                    headers={"Content-Disposition": f'inline; filename="{vid}.mp4"',
                             "Accept-Ranges": "bytes",
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
    try:
        limit = max(1, min(40, int(request.args.get("limit") or 12)))
    except (TypeError, ValueError):
        limit = 12
    with db.connect() as c:
        rows = c.execute(
            """SELECT id,owner,scene,talent,voice,pet_name,topic,watermarked,
                      duration,bytes,created_at
               FROM videos
               WHERE path IS NOT NULL AND path != ''
               ORDER BY created_at DESC LIMIT ?""", (limit,)).fetchall()
    items = []
    for r in rows:
        d = db.dump(r)
        d["src"] = f"/api/videos/{d['id']}/file"
        d["poster"] = ""
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
    out_mp4 = config.DATA / "videos" / f"p0_standup_{uuid.uuid4().hex[:8]}.mp4"
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
    # Card namespaces survive account claiming. Serve these only through the
    # card routes, which check the current database owner rather than the key.
    if "cards" in key.split("/"):
        return _err("use the authenticated card download route", 403)
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


def _check_text(line: str, text: str) -> tuple[str | None, dict | None]:
    """Validate emboss text against TEXT_PERSONALIZATION. Returns
    (clean_text_or_None, error_response_or_None). Uppercase, registry only —
    no remesh, no freeform decal."""
    text = (text or "").strip()
    spec = config.TEXT_PERSONALIZATION.get(line)
    if not text:
        return None, None
    if not spec:
        return None, _err(f"{line} takes no text personalisation", 400)
    clean = text.upper()[: spec.get("max_chars", 14)]
    if len(text.strip()) > spec.get("max_chars", 14):
        return None, _err(f"text over {spec['max_chars']} chars for {line}", 400)
    allowed = set(spec.get("charset", ""))
    if any(ch not in allowed for ch in clean):
        return None, _err(f"text uses characters outside {line} charset", 400)
    if not clean:
        return None, None
    return clean, None


def _text_preview(line: str, text: str) -> str | None:
    """Cheap name preview: flat PIL text on the line hero still, cached by
    hash. Preview grade only — the farm embosses at print time."""
    import hashlib as _hl
    from PIL import Image as _Image, ImageDraw as _Draw, ImageFont as _Font
    stills = _studio_stills_for(line, "none", "none")
    hero = (stills.get("hero") or "").replace("/img/prod/", "")
    src = config.DATA / "productimg" / config.STUDIO_STILL_DIR / hero
    if not hero or not src.is_file():
        return None
    digest = _hl.sha1(f"{line}:{text}".encode()).hexdigest()[:12]
    out = config.DATA / "productimg" / "text" / f"{line}-{digest}.png"
    if out.is_file():
        return f"/img/text/{out.name}"
    try:
        im = _Image.open(src).convert("RGB")
        d = _Draw.Draw(im)
        try:
            font = _Font.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                max(24, im.width // 12))
        except OSError:
            font = _Font.load_default()
        band_h = int(im.height * 0.16)
        band = _Image.new("RGB", (im.width, band_h), (250, 246, 236))
        im.paste(band, (0, im.height - band_h))
        d = _Draw.Draw(im)
        d.text([im.width // 2, im.height - band_h // 2], text, font=font,
               fill=(158, 26, 38), anchor="mm")
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "PNG", optimize=True)
        return f"/img/text/{out.name}"
    except Exception:
        return None


def _slot_preview(line: str, resolved: dict) -> str | None:
    """True-perspective slot composite over a blank plate (<1s, no re-render).
    Plates: data/productimg/plates/<line>/<base>-<view>.png + .json.
    Missing plates → None (caller falls back to the flat PIL preview)."""
    import hashlib as _hl
    import subprocess as _sp
    base = (resolved.get("base") or "midnight").lower().replace(" ", "-")
    plate = config.DATA / "productimg" / "plates" / line / f"{base}-hero.png"
    if not plate.is_file() or not plate.with_suffix(".json").is_file():
        return None
    digest = _hl.sha1(json.dumps(resolved, sort_keys=True).encode()).hexdigest()[:12]
    out = config.DATA / "productimg" / "text" / f"{line}-slot-{digest}.png"
    if out.is_file():
        return f"/img/text/{out.name}"
    accent_hex = "#D7B25A"
    try:
        from backend import slots as _slots
        pal = ((_slots.load_spec(line).get("colours") or {}).get("accent")
               or {}).get("palette", {})
        accent_hex = pal.get(resolved.get("accent", ""), accent_hex)
    except Exception:
        pass
    params = {"name": resolved.get("name", ""),
              "tagline": resolved.get("tagline", ""),
              "arc": resolved.get("arc", ""),
              "accent": accent_hex}
    try:
        r = _sp.run([sys.executable, "scripts/slot_compose.py", str(plate),
                     json.dumps(params), str(out)],
                    capture_output=True, text=True, timeout=30, cwd=".")
        if r.returncode != 0 or not out.is_file():
            return None
        return f"/img/text/{out.name}"
    except Exception:
        return None


def _aesthetic_coat(owner: str, subject_id: str, spec: dict) -> str | None:
    """First profile-preferred coat the line allows. None = no opinion."""
    if not subject_id:
        return None
    try:
        from backend import subjects as _subjects
        with db.connect() as c:
            if not _subjects.get_subject(c, owner, subject_id):
                return None
            prof = _subjects.profile_for(c, owner, subject_id)
        colors = ((prof.get("profile") or {}).get("aesthetic") or {}).get("colors") or []
        allowed = set((spec.get("assets") or {}).get("coats") or ["none"])
        for coat in colors:
            if coat in allowed and coat != "none":
                return coat
    except Exception:
        pass
    return None


def _resolve_subject(owner: str, subject_id: str) -> str:
    """Explicit subject, else the owner's studio-selected friend."""
    if subject_id:
        return subject_id
    try:
        with db.connect() as c:
            sel = c.execute("SELECT subject_id FROM studio_selection WHERE owner=?",
                            (owner,)).fetchone()
            return (dict(sel).get("subject_id") if sel else "") or ""
    except Exception:
        return ""


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


@app.get("/api/cards/copy/<card_id>")
def card_copy(card_id: str):
    """Person-aware card copy. The catalog defaults are pet-flavoured
    ("[pet name] says woof"); pass name + kind and the copy comes back
    for a person instead of a pet."""
    cards = config.PERSONAL_CARDS or {}
    if card_id not in cards:
        return _err("unknown card — valid ids: " + ", ".join(sorted(cards)), 404)
    name = (request.args.get("name") or "").strip()[:60]
    kind = (request.args.get("kind") or "pet").strip().lower()
    out = dict(cards[card_id])
    if kind == "person":
        who = name or "them"
        subs = {
            "[pet name] says woof": f"with love, {who}",
            "[pet name]": who,
            " says woof": "",
        }
        for k in ("message", "sub", "blurb"):
            if isinstance(out.get(k), str):
                for old, new in subs.items():
                    out[k] = out[k].replace(old, new)
        for k in ("label", "etsy_title"):
            if isinstance(out.get(k), str):
                out[k] = out[k].replace("Dog ", "").replace("Pet ", "").replace("  ", " ").strip()
        if isinstance(out.get("tags"), list):
            out["tags"] = [t.replace("dog ", "").replace("pet ", "").strip() or t for t in out["tags"]]
    elif name:
        for k in ("message", "sub", "blurb"):
            if isinstance(out.get(k), str):
                out[k] = out[k].replace("[pet name]", name)
    return jsonify(ok=True, id=card_id, kind=kind, name=name, card=out)


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
    def _evidence(lid: str, hay_text: str) -> int:
        """Query tokens actually found in this line: ranking strength, not
        understanding certainty. 'blahblah gift' ~= 1 hit, never 97%.
        Stopwords and recipient names never count; a token inside the line id
        counts double (naming the thing beats mentioning it)."""
        stop = {"for", "my", "a", "an", "the", "and", "or", "to", "of",
                "in", "on", "is", "it", "me", "dad", "mum", "mom", "grandma",
                "grandad", "grandpa"}
        n = 0
        for tok in q.split():
            tok = tok.strip(",.!?").lower()
            if not tok or tok in stop:
                continue
            if tok in hay_text or any(p.startswith(tok) for p in hay_text.split()):
                n += 1
                if tok in lid:
                    n += 1
        return n

    for m in scored:
        spec = config.STUDIO_LINES.get(m["id"], {})
        hay = " ".join([m["id"], spec.get("label", ""), spec.get("blurb", ""),
                        spec.get("theme", "")]).lower()
        hits = _evidence(m["id"], hay)
        conf = min(0.97, 0.20 + 0.10 * hits)
        if m["id"] in boosts:
            conf = min(0.97, conf + 0.15)  # customer-pointed counts as evidence
        if m["status"] != "live":
            conf = min(conf, 0.4)
        m["confidence"] = round(conf, 2)
        m["evidence_hits"] = hits
    scored.sort(key=lambda m: (-m["confidence"], -m["score"], m["label"]))
    best = scored[0]
    strong = best["confidence"] >= 0.5 and best.get("evidence_hits", 0) >= 2
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
                if strong else
                f"Best guess: {best['label']} "
                f"({best.get('evidence_hits', 0)} matching words) — say more for a surer pick."
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
            "ChatGPT/MCP (public tier, no token): call figg_quick_map with the customer's words, "
            "show the top 2–3 matches with confidence. Custom geometry goes base-first: "
            "figg_design_base → design inside it → figg_design_validate → figg_design_save "
            "(base_first flag) → figg_design_order reserve. fulfil, uploads, sculpts and "
            "renders need the bridge token or the caller's own API key. "
            "Always show price before order."
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
            "design_base": "/api/design/base/<line>",
            "design_save": "/api/design/save",
            "design_order": "/api/design/order",
            "adopt_style": "/api/meshes/style",
            "perform": "/api/videos",
            "acts": "/api/acts",
            "mcp": "https://mcp.oddhobb.com/mcp",
        },
        "chatgpt_script": (
            "1) Listen to the ramble. 2) figg_quick_map(text) — show top matches + confidence. "
            "3) Custom design goes base-first: figg_design_base → validate → figg_design_save "
            "(check base_first) → figg_design_order reserve. fulfil, uploads, sculpts and renders "
            "need your own API key (figg_create_account) or the bridge token. "
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
            """SELECT product,status,price_cents FROM product_bindings
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


@app.get("/api/products/<line>/preview")
def product_preview(line: str):
    """Canonical preview: subject + product personalization method +
    fixture assets -> rendered preview artifact. Same images power the
    website tile, Etsy listing, Shopify image and agent previews."""
    from backend import listings as _list
    try:
        rec = _list.recipe_for(line)
    except KeyError:
        return _err("unknown line — valid ids: " + ", ".join(sorted(_list.RECIPES)), 404)
    subject = (request.args.get("subject") or rec["fixture"]).strip()[:80]
    photos = _list.fixture_photos(subject)
    if not photos:
        return jsonify(ok=False, error=f"fixture {subject!r} has no photos yet",
                       hint=f"add to data/fixtures/{subject}/photos/"), 404
    spec = config.STUDIO_LINES.get(line, {})
    stills = {}
    for name in [rec["hero"], *rec["angles"]]:
        p = _list.PROD / name
        if p.is_file():
            stills[name] = f"/img/prod/{name}"
    outdir = _list.OUT / line / subject
    listing = {}
    lp = outdir / "listing.json"
    if lp.is_file():
        try:
            listing = json.loads(lp.read_text())
        except ValueError:
            listing = {}
    return jsonify(ok=True, line=line, subject=subject, story=rec["story"],
                   text=rec["text"], hero=f"/img/prod/{rec['hero']}",
                   stills=stills, price_cents=spec.get("price_cents", 0),
                   status={"catalog": spec.get("status", "soon"),
                           "production": spec.get("production", "sample_pending"),
                           "etsy": spec.get("etsy", "draft")},
                   listing=listing)


@app.get("/api/products/for/<subject>")
def products_for_subject(subject: str):
    """Rank product lines for someone we know: their interests, motifs and
    occasions against each line's theme, blurb and occasion. Prints the
    reasoning so an agent can explain the pick, not just take it."""
    from backend import subjects as _subjects
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        sub = _subjects.get_subject(c, owner, subject)
        if not sub:
            sub = _subjects.find_subject_by_name(c, owner, subject)
        if not sub:
            return _err("unknown friend — add them in Studio first", 404)
        prof = _subjects.profile_for(c, owner, sub["id"]).get("profile", {})
    interests = [str(x).lower() for x in (prof.get("interests") or [])
                 if isinstance(x, str)]
    notes = f"{prof.get('notes') or ''} {prof.get('relationship') or ''}".lower()
    from backend import listings as _list
    ranked = _list.rank_for(interests, notes)
    return jsonify(ok=True, subject=sub.get("name", subject),
                   interests=prof.get("interests") or [],
                   lines=ranked)


@app.get("/api/quotes/compare")
def quotes_compare():
    """Value / speed / balanced across suppliers for one product line.

    ?line=<id>&country=GB. Picks derive value (cheapest live total),
    speed (quickest dispatch) and balanced (best cost-per-day ratio).
    Speed carries an order-by countdown (cutoff- or open-mode, business
    days, dispatch dates — delivery per carrier). Mapped lines only.
    """
    line = (request.args.get("line") or "").strip()
    country = (request.args.get("country") or "GB").strip()[:2]
    from backend import delivery as _dlv
    if line not in _dlv.ROUTES:
        return _err("no supplier mapping for line (mapped: %s)"
                    % ", ".join(sorted(_dlv.ROUTES)), 400)
    built = _dlv.build(line, country)
    return jsonify({"ok": True, "line": line, "country": country,
                    "options": built["options"], "picks": built["picks"],
                    "matrix": built["matrix"],
                    "duty_note": "US: quote excludes sales tax; de-minimis "
                                 "ended Aug 2025 — confirm landed cost at checkout"})


@app.get("/api/recipes/check")
def recipes_check():
    """Can this warehouse build N boxes today? ?recipe=&warehouse=&qty=."""
    from backend import components as _comp
    recipe = (request.args.get("recipe") or "").strip()
    warehouse = (request.args.get("warehouse") or "Shenzhen").strip()[:40]
    try:
        qty = max(1, min(500, int(request.args.get("qty") or 1)))
    except (TypeError, ValueError):
        return _err("qty must be 1-500", 400)
    if not recipe:
        return _err("recipe is required", 400)
    r = _comp.check_recipe(recipe, warehouse, qty)
    if not r.get("ok"):
        return _err(r.get("error", "check failed"), 400)
    return jsonify(r)


@app.post("/api/gifts/compile")
def gifts_compile():
    """Compile a gift recipe: resolve lines, apply the postage rule, score
    feasibility. Body: {recipe, warehouse?, ship_cents?}."""
    from backend import components as _comp
    from backend import feasibility as _fea
    body = request.get_json(silent=True) or {}
    recipe = str(body.get("recipe") or "")
    warehouse = str(body.get("warehouse") or "Shenzhen")[:40]
    ship = body.get("ship_cents")
    try:
        ship_cents = None if ship is None else max(0, int(ship))
    except (TypeError, ValueError):
        return _err("ship_cents must be a number", 400)
    if not recipe:
        return _err("recipe is required", 400)
    safety = body.get("safety_flags") if isinstance(body.get("safety_flags"), list) else []
    r = _comp.compile_gift(recipe, warehouse, ship_cents)
    if not r.get("ok"):
        return _err(r.get("error", "compile failed"), 400)
    r["feasibility"] = _fea.score_gift(r, [str(s) for s in safety][:6])
    return jsonify(r)


@app.post("/api/projects/check")
def projects_check():
    """Run a kit idea through every supplier lane: parts_3d[] (live
    estimates), paper_skus[] (live Prodigi quotes), components_std[]
    (AliExpress staged), kitting (US station staged). Verdict: producible
    / staged / blocked. Paste an idea, get the manufacturing truth."""
    body = request.get_json(silent=True) or {}
    idea = body.get("idea") or body
    if not isinstance(idea, dict) or not idea:
        return _err("idea object is required", 400)
    from backend import project_check as _pc
    return jsonify(_pc.check_idea(idea))


@app.get("/api/templates/fill")
def templates_fill():
    """Fill a layout template (wrap_solo/trio_card/photo_card) from an
    owner's labelled photos. ?owner=&template_id=&subjects=a,b (optional).
    Photo PII — owner-enforced."""
    owner = (request.args.get("owner") or "").strip()[:80]
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    template_id = (request.args.get("template_id") or "").strip()
    if not template_id:
        return _err("template_id is required", 400)
    subjects = [s.strip()[:60] for s in
                (request.args.get("subjects") or "").split(",") if s.strip()]
    from backend import template_engine as _te
    r = _te.fill(owner, template_id, subjects=subjects or None)
    if not r.get("ok"):
        return _err(r.get("error", "fill failed"), 400)
    return jsonify({"ok": True, "owner": owner, **r})


@app.get("/api/products/candidates")
def products_candidates():
    """Ranked photo shortlist behind one product line's tag requirements.

    ?owner=&kind=prodigi|card&line=<id>&n=8. Best first by label score
    (quality/emotion layers as they land); the arrow UI cycles the rest.
    Photo PII — owner-enforced.
    """
    owner = (request.args.get("owner") or "").strip()[:80]
    if not owner:
        return _err("owner is required", 400)
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    kind = (request.args.get("kind") or "prodigi").strip()
    if kind not in ("prodigi", "card"):
        return _err("kind must be prodigi|card", 400)
    line = (request.args.get("line") or "").strip()
    if not line:
        return _err("line is required", 400)
    try:
        n = max(1, min(20, int(request.args.get("n") or 8)))
    except (TypeError, ValueError):
        return _err("n must be 1-20", 400)
    from backend import subject_assets as _sa
    return jsonify({"ok": True,
                    **_sa.product_assets(owner, kind, line, per_slot=n)})


@app.get("/api/mcp/health")
def mcp_health():
    """MCP tier health: version, tool count, process uptime, port checks.
    A tunnel 502 with healthy Flask shows up here as backend unreachable;
    a fresh restart shows up as low uptime. No secrets.
    Cf-Ray matching: bridge logs cf_ray on every 502 to ~/.figg_mcp_proxy.log
    so agent timestamps + ray IDs map to process logs."""
    import socket
    import time as _time
    from backend import mcp_server as _mcp
    tools_full = sum(len(v) for v in _mcp.TOOL_AREAS.values()) + 1
    # Public tier allowlist lives on the same module: recompute without
    # reimporting (import-time filter when PUBLIC_MCP=1). Agents on the
    # tokenless tier see tools_public, not tools_full — don't quote full.
    try:
        _public = set(getattr(_mcp, "PUBLIC_TOOLS", set()))
        # +1: figg_tools rides alongside every tier (self-describing library)
        tools_public = sum(1 for v in _mcp.TOOL_AREAS.values()
                           for fn in v if fn.__name__ in _public) + 1
    except Exception:
        tools_public = 0
    tools = tools_full
    version = getattr(_mcp, "MCP_VERSION", "unversioned")

    def _uptime(pattern: str):
        try:
            import subprocess as _sp
            out = _sp.run(["pgrep", "-f", pattern], capture_output=True,
                          text=True, timeout=5).stdout.strip().split()
            if not out:
                return None
            # oldest matching PID = main process (stable across forks)
            pid = sorted(out, key=int)[0]
            stat = open(f"/proc/{pid}/stat").read().split()
            clk = os.sysconf("SC_CLK_TCK")
            boot = float(open("/proc/stat").read().split("btime")[1].split()[0])
            started = boot + float(stat[21]) / clk
            return round(_time.time() - started)
        except Exception:
            return None

    mcp_uptime_s = _uptime("backend.mcp_server")
    flask_uptime_s = _uptime("backend.server")
    ports = {}
    for port in (8799, 8800):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=2)
            s.close()
            ports[str(port)] = "open"
        except OSError:
            ports[str(port)] = "closed"
    return jsonify(ok=True, version=version, tools=tools,
                   tools_full=tools_full, tools_public=tools_public,
                   uptime_s=mcp_uptime_s, flask_uptime_s=flask_uptime_s,
                   ports=ports,
                   tiers={"full": {"port": 8799, "tools": tools_full},
                          "public": {"port": 8800, "tools": tools_public}},
                   degraded=ports.get("8799") != "open",
                   cf_ray_log="~/.figg_mcp_proxy.log (bridge logs cf_ray on every 502)",
                   hint="Handshake first: GET this. tools_full needs the bridge token; "
                        "tokenless callers see tools_public only. If degraded, prefer waiting — "
                        "REST works but is off the main road (see mcp_status).")


@app.get("/api/cards/proof/<did>/og-image.png")
def card_proof_image(did):
    """Public card preview for link unfurls (og:image). Design ids are
    unguessable, so the link itself is the capability — no owner needed."""
    from backend import cards as _cards
    with db.connect() as c:
        row = c.execute("SELECT * FROM card_designs WHERE id=?", (did,)).fetchone()
    if row is None:
        return _err("Card not found", 404)
    d = dict(row)
    try:
        p = _cards.local_asset(_cards.key(d["owner"], did, d["latest"], "preview"))
    except Exception:
        try:
            p = _cards.local_asset(_cards.key(d["owner"], did, d["latest"], "spread-front"))
        except Exception:
            return _err("Preview not rendered yet", 404)
    res = send_file(p, mimetype="image/png", max_age=3600)
    res.headers["Cache-Control"] = "public, max-age=3600"
    return res


def _fulfil_route(order, line_attrs=None):
    """Resolve the frozen fulfilment route for a paid order.

    Precedence: saved delivery_option_id row → the order row's own
    shipping_method (checkout path) → Shopify line attributes → Standard.
    Returns (shipping_method, route_or_None). Never raises.
    """
    try:
        dopt = (order.get("delivery_option_id") or "").strip()
        if dopt:
            from backend import cards as _cards
            route = _cards.get_delivery_option(order.get("owner", ""), dopt,
                                               order.get("design_id"),
                                               order.get("revision"))
            if route:
                return route["shipping_method"], route
        own = (order.get("shipping_method") or "").strip()
        if own and own != "Standard":
            return own, None
        if isinstance(line_attrs, dict):
            dopt2 = str(line_attrs.get("delivery_option_id") or "").strip()
            if dopt2:
                from backend import cards as _cards
                route = _cards.get_delivery_option(order.get("owner", ""), dopt2)
                if route:
                    return route["shipping_method"], route
            sm = str(line_attrs.get("shipping_method") or "").strip()
            if sm:
                return sm, None
    except Exception:
        pass
    return "Standard", None


@app.post("/api/shopify/webhooks/orders-paid")
def shopify_orders_paid():
    """Shopify orders/paid → Prodigi fulfilment. Idempotent.

    Fast-ack design (Shopify gives webhooks ~5s): verify HMAC, resolve the
    order, answer 202 immediately; the slow block (compose → preflight →
    R2 → Prodigi → DB) runs on a daemon thread. Retries are safe: rows
    already fulfilled short-circuit before any work.
    Invariant: Prodigi is never called until Shopify says paid.
    Verifies X-Shopify-Hmac-Sha256, finds oddhobb_order_id in line-item
    customAttributes/properties (or note_attributes/note), skips if already
    fulfilled, else composes the frozen revision's exact Prodigi PDF,
    preflights, presigns via R2, and calls Prodigi create_order with the
    customer's shipping address. Shopify retries are safe (idempotent).
    Blocked until CARD_PANEL_CONFIRMED=1 (panel order vs Prodigi template).
    """
    from backend import shopify_fulfil as _sf
    raw = request.get_data() or b""
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if not _sf.verify_webhook(raw, hmac_header):
        return _err("bad webhook signature", 401)
    try:
        payload = json.loads(raw.decode() or "{}")
    except (ValueError, UnicodeDecodeError):
        return _err("bad webhook JSON", 400)
    # find our order id — customAttributes first, then properties, notes
    oid = ""
    line_items = payload.get("line_items") or payload.get("lineItems") or []
    for li in line_items:
        for attr in (li.get("customAttributes") or li.get("custom_attributes") or []):
            if isinstance(attr, dict) and str(attr.get("key") or "").lower() == "oddhobb_order_id":
                oid = str(attr.get("value") or "")
        for prop in (li.get("properties") or []):
            if isinstance(prop, dict) and str(prop.get("name") or prop.get("key") or "").lower() == "oddhobb_order_id":
                oid = str(prop.get("value") or "")
    if not oid:
        for na in (payload.get("note_attributes") or payload.get("noteAttributes") or []):
            if isinstance(na, dict) and str(na.get("name") or na.get("key") or "").lower() == "oddhobb_order_id":
                oid = str(na.get("value") or "")
    if not oid:
        import re as _re
        m = _re.search(r"ord_card_[0-9a-f]{16,}", str(payload.get("note") or ""))
        if m:
            oid = m.group(0)
    if not oid:
        return jsonify(ok=False, error="no oddhobb_order_id in webhook"), 200
    with db.connect() as c:
        row = c.execute("SELECT * FROM card_orders WHERE id=?", (oid,)).fetchone()
    if row is None:
        return jsonify(ok=False, error="unknown oddhobb order"), 200
    order = dict(row)
    if order.get("status") == "fulfilled" and order.get("prodigi_ref"):
        return jsonify(ok=True, reused=True, order_id=oid,
                       prodigi_ref=order.get("prodigi_ref")), 200
    if os.environ.get("CARD_PANEL_CONFIRMED", "") != "1":
        return _err("card panel order not confirmed against Prodigi template yet "
                    "(CARD_PANEL_CONFIRMED=1 blocks live print)", 409)
    # Fast-ack: everything above is cheap; the slow fulfilment block runs
    # on a daemon thread AFTER we answer, so Shopify never times out.
    import threading as _th

    def _fulfil(payload=payload, oid=oid):
        with db.connect() as c:
            row = c.execute("SELECT * FROM card_orders WHERE id=?", (oid,)).fetchone()
        if row is None:
            return
        order = dict(row)
        if order.get("status") == "fulfilled" and order.get("prodigi_ref"):
            return
        # Frozen fulfilment route: the customer's delivery choice travels
        # with the order (delivery_option_id row → row method → line attrs).
        line_attrs = {}
        try:
            for li in (payload.get("line_items") or payload.get("lineItems") or []):
                props = li.get("customAttributes") or li.get("properties") or []
                vals = {str(p.get("key") or p.get("name") or ""): str(p.get("value") or "")
                        for p in props if isinstance(p, dict)}
                if vals.get("oddhobb_order_id") == oid:
                    line_attrs = vals
                    break
        except Exception:
            line_attrs = {}
        ship_method, _route = _fulfil_route(order, line_attrs)
        # shipping address from Shopify → Prodigi recipient
        ship = payload.get("shipping_address") or payload.get("shippingAddress") or {}
        recipient = {
            "name": str(ship.get("name") or f"{ship.get('first_name','')} {ship.get('last_name','')}".strip() or "OddHobb customer")[:60],
            "line1": str(ship.get("address1") or ship.get("line1") or "")[:100],
            "line2": str(ship.get("address2") or ship.get("line2") or "")[:100],
            "town": str(ship.get("city") or ship.get("town") or "")[:60],
            "postcode": str(ship.get("zip") or ship.get("postcode") or "")[:20],
            "country": str(ship.get("country_code") or ship.get("country") or "GB")[:2].upper(),
            "email": str(payload.get("email") or payload.get("contact_email") or "")[:120],
        }
        if not all(recipient[k].strip() for k in ("name", "line1", "town", "postcode", "country")):
            return
        try:
            from backend import cards as _cards
            from backend import card_print as _print
            from backend import r2presign as _r2
            from backend import prodigi as _prodigi
            spec = json.loads(order["spec"])
            owner, did, rev = order["owner"], order["design_id"], order["revision"]
            # frozen revision must still validate + belong to owner
            _cards.validate(owner, spec)
            aa = _cards.assets(owner, spec)
            single = _print.compose(spec, aa)
            gaps = _print.preflight(single)
            if gaps:
                return
            r2key = _r2.put_temp(single)
            try:
                asset_url = _r2.presigned_url(r2key)
            except Exception:  # noqa: BLE001
                _r2.delete(r2key)
                return
            placed = _prodigi.create_order(_cards.CARD_PRODIGI_SKU, order["qty"],
                                           asset_url, recipient,
                                           shipping_method=ship_method)
        except Exception:  # noqa: BLE001
            return
        with db.connect() as c:
            c.execute("UPDATE card_orders SET status='fulfilled', prodigi_ref=? WHERE id=?",
                      (placed["id"], oid))
            c.commit()

    _th.Thread(target=_fulfil, daemon=True, name="shopify-fulfil").start()
    return jsonify(ok=True, order_id=oid, accepted=True,
                   hint="paid accepted; fulfilment runs in background")


@app.post("/api/shopify/webhooks/register")
def shopify_webhook_register():
    """Register orders/paid → our webhook. Needs SHOPIFY creds + PUBLIC_BASE.
    Idempotent: reuses existing subscription for the same address."""
    from backend import shopify_fulfil as _sf
    if not _sf.configured():
        return _err("Shopify not configured", 503)
    address = (config.PUBLIC_BASE or "").rstrip("/") + "/backend/api/shopify/webhooks/orders-paid"
    query = """
    mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
      webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
        webhookSubscription { id endpoint { __typename ... on WebhookHttpEndpoint { callbackUrl } } }
        userErrors { field message }
      }
    }
    """
    try:
        data = _sf.gql(query, {"topic": "ORDERS_PAID",
                               "webhookSubscription": {"callbackUrl": address,
                                                       "format": "JSON"}})
    except Exception as e:  # noqa: BLE001
        return _err(f"webhook register failed: {str(e)[:200]}", 502)
    res = ((data.get("data") or {}).get("webhookSubscriptionCreate")) or {}
    if res.get("userErrors"):
        return _err(str(res["userErrors"][0].get("message", "webhook failed"))[:200], 502)
    sub = res.get("webhookSubscription") or {}
    return jsonify(ok=True, subscription=sub, address=address,
                   api_version=_sf.API_VERSION)


@app.post("/api/products/personalise")
def products_personalise():
    """Controlled personalise: coat colour + pattern + hat + text on a product line."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    line = (body.get("line") or "ornament").strip()
    coat = (body.get("coat") or body.get("coat_color") or "none").strip().lower()
    hat = (body.get("hat") or body.get("hat_id") or "none").strip().lower()
    pattern = (body.get("pattern") or body.get("coat_pattern") or "solid").strip().lower()
    mesh_id = (body.get("mesh_id") or "").strip()
    texture_note = (body.get("texture") or body.get("texture_note") or "")[:200]
    subject_id = _resolve_subject(owner, (body.get("subject_id") or "").strip()[:80])
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    spec = config.STUDIO_LINES[line]
    allowed = spec.get("assets") or {}
    if coat not in (allowed.get("coats") or ["none"]):
        return _err(f"coat {coat!r} is not allowed on {line}", 400)
    if coat == "none":
        # profile-driven colour: the friend's aesthetic picks when they have one
        auto = _aesthetic_coat(owner, subject_id, spec)
        if auto:
            coat = auto
    if hat not in (allowed.get("hats") or ["none"]):
        return _err(f"hat {hat!r} is not allowed on {line}", 400)
    if pattern not in (allowed.get("patterns") or ["solid"]):
        return _err(f"pattern {pattern!r} is not allowed on {line}", 400)
    if pattern != "solid" and coat == "none":
        # pattern without a coat colour is meaningless on as-printed fur
        coat = "cream"
    text, text_err = _check_text(line, body.get("text") or "")
    if text_err:
        return text_err
    # Slot primitive (spec-faithful): slots{name,tagline,arc,colours} validated
    # against backend/slot_specs; autofill from the family profile when the
    # agent omits fields. Legacy `text` also validates as slots.name.
    slot_resolved = None
    if isinstance(body.get("slots"), dict):
        try:
            from backend import slots as _slots
            incoming = dict(body["slots"])
            if "name" not in incoming and subject_id:
                auto = _slots.autofill(owner, subject_id)
                if auto.get("ok"):
                    for k, v in auto["slots"].items():
                        if k != "_name_fallbacks":
                            incoming.setdefault(k, v)
            slot_resolved = _slots.validate(line, incoming)["resolved"]
            text = text or slot_resolved.get("name")
        except ValueError as e:
            return _err(f"slot rejected: {e} — retry a nickname or initials", 400)
    elif text:
        try:
            from backend import slots as _slots
            if _slots.load_spec(line):
                slot_resolved = _slots.validate(line, {"name": text})["resolved"]
        except ValueError as e:
            return _err(f"slot rejected: {e} — retry a nickname or initials", 400)
    if spec.get("status") != "live":
        return _err(f"{line} is not live yet", 409)
    stills = _studio_stills_for(line, coat, hat)
    text_preview = None
    if slot_resolved:
        text_preview = _slot_preview(line, slot_resolved)
    if not text_preview and text:
        text_preview = _text_preview(line, text)
    if text_preview:
        stills = {**stills, "text_hero": text_preview, "hero": text_preview}
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
        "subject_id": subject_id,
        "text": text,
        "text_preview": text_preview,
        "slots": slot_resolved,
        "texture_note": texture_note,
        "stills": stills,
        "available": available,
        "price_cents": spec.get("price_cents", 0),
        "fulfilment": spec.get("fulfilment"),
        "policy": "controlled",
        "hint": "Registry-only custom. Coat is a preview grade — multi-colour print is a live farm quote. "
                "Order via POST /api/products/order or figg_checkout.",
    })


@app.post("/api/design/validate")
def design_validate():
    """Validate a candidate design against a line's design contract.

    Body: {line, dims_mm:[x,y,z] mm (x=width, y=depth, z=height/up), material, colors, text, volume_cm3}.
    Checks envelope fit, locked material/colours, text length vs the
    personalisation zone, and rough cost at makr3d + printie.
    Geometry truth (manifold, interface dims) is verified at sample, not here.
    """
    from backend import suppliers as _sup
    body = request.get_json(silent=True) or {}
    line = (body.get("line") or "").strip()
    if line not in config.STUDIO_LINES:
        return _err("unknown line — valid ids: " + ", ".join(sorted(config.STUDIO_LINES)), 400)
    spec = config.STUDIO_LINES[line]
    contract = spec.get("design_contract") or {}
    gaps = []
    dims = body.get("dims_mm")
    envelope = contract.get("envelope_mm") or []
    if dims is not None:
        if (not isinstance(dims, (list, tuple)) or len(dims) != 3
                or any(isinstance(x, bool) for x in dims)):
            return _err("dims_mm must be [x, y, z] numbers", 400)
        try:
            dims = [float(x) for x in dims]
            if any(v < 0 for v in dims):
                return _err("dims_mm must be [x, y, z] numbers", 400)
        except (TypeError, ValueError):
            return _err("dims_mm must be [x, y, z] numbers", 400)
        if envelope:
            for got, maxv, ax in zip(dims, envelope, "XYZ"):
                if got > maxv:
                    gaps.append(f"{ax} {got}mm exceeds envelope {maxv}mm")
    material = (body.get("material") or contract.get("material") or "PLA").strip()
    if not isinstance(material, str):
        return _err("material must be a string", 400)
    KNOWN_MATS = ("PLA", "PETG", "TPU", "ASA", "PAPER", "DIGITAL")
    if material.upper() in KNOWN_MATS:
        material = material.upper()
    else:
        gaps.append(f"unknown material '{material}' — stocked: {', '.join(KNOWN_MATS)}")
    try:
        colors = int(body.get("colors") or 1)
    except (TypeError, ValueError):
        return _err("colors must be a number", 400)
    if isinstance(body.get("colors"), bool):
        return _err("colors must be a number", 400)
    cmax = contract.get("colors_max")
    if cmax and colors > int(cmax):
        gaps.append(f"{colors} colours > max {cmax}")
    text = str(body.get("text") or "")
    zone_max = ((spec.get("personalization") or {}).get("max_chars")) if isinstance(spec.get("personalization"), dict) else 0
    try:
        ad = json.loads((Path("scripts/factory/adapters") / f"{line}.json").read_text())
        zone_max = int(ad.get("text", {}).get("max_chars") or zone_max or 0)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if zone_max and len(text) > zone_max:
        gaps.append(f"text {len(text)} chars > zone max {zone_max}")
    volume = body.get("volume_cm3")
    try:
        volume = float(volume) if volume is not None else contract.get("volume_cm3_est")
    except (TypeError, ValueError):
        volume = contract.get("volume_cm3_est")
    options = [o for o in _sup.options_for(
        material=material, colors=colors,
        dims_mm=(list(dims) if dims else envelope) or None,
        volume_cm3=volume, weight_g=spec.get("weight_g"))
        if o["supplier"] in ("makr3d", "printie")]
    feasible = not gaps and any(o["feasible"] for o in options)
    return jsonify({
        "ok": True,
        "line": line,
        "feasible": feasible,
        "gaps": gaps,
        "axes": "[x, y, z] mm (x=width, y=depth, z=height/up)",
        "locked": contract.get("locked", []),
        "verify": contract.get("verify", []),
        "options": options,
        "note": "Dims/material/text check only. Interface dims + manifold verified at sample.",
    })


def _design_base(line: str) -> Path | None:
    """3D base version of a line: own master STL for reference lines,
    canonical dog GLB for mesh lines. The thing a model plays with.

    An adapter with a modelled base always wins when present — e.g. croc_tag
    is a face_swap (mini) line that ALSO carries a standard pin base for
    relief/text motifs, so agents emboss onto our geometry instead of
    free-modelling (and re-breaking) the locked interfaces."""
    for cand in (Path("scripts/factory/adapters") / f"{line}.json",):
        try:
            ad = json.loads(cand.read_text())
            base = Path("data/3dprint") / ad["base"]
            if base.is_file():
                return base
        except (OSError, ValueError, KeyError):
            pass
    spec = config.STUDIO_LINES.get(line) or {}
    method = ((spec.get("personalization") or {}).get("method")
              if isinstance(spec.get("personalization"), dict) else "")
    if method in ("emboss", "relief"):
        return None
    if method == "face_swap":
        dog = Path("data/uploads/chibi-figure-hook.glb")
        return dog if dog.is_file() else None
    return None


@app.get("/api/design/base/<line>")
def design_base(line: str):
    """Download the 3D base version: master STL (reference lines) or the
    canonical dog GLB (mesh lines). Locked interfaces included as modelled.

    ?format=json returns metadata + base64 for MCP/agents (binary STL/GLB
    cannot travel inside JSON otherwise): {bytes, md5, units, axes, dims_mm}.
    Units are millimetres, axes are [x, y, z] (x = width, y = depth, z = up).
    GLB bases are metres, Z up, thin along X — scale ×1000 for mm."""
    base = _design_base(line)
    if base is None or not base.is_file():
        return _err("no base modelled for this line yet", 404)
    owner = (request.args.get("owner") or "anon").strip()[:80]
    try:
        _design_tables()
        with db.connect() as c:
            c.execute("INSERT INTO design_base_fetches VALUES (?,?,?)",
                      (owner, line, time.time()))
            c.commit()
    except Exception:  # noqa: BLE001 — logging must never break the download
        pass
    if (request.args.get("format") or "") == "json":
        import base64
        import hashlib
        data = base.read_bytes()
        contract = (config.STUDIO_LINES.get(line) or {}).get("design_contract", {})
        dims = list(contract.get("envelope_mm") or [])
        try:
            ad = json.loads((Path("scripts/factory/adapters") / f"{line}.json").read_text())
        except (OSError, ValueError):
            ad = {}
        measured = ad.get("measured_mm") or dims
        units = "mm" if base.suffix == ".stl" else "m"
        meta = {"ok": True, "line": line,
                "filename": f"oddhobb-{line}-base{base.suffix}",
                "mime": "model/stl" if base.suffix == ".stl" else "model/gltf-binary",
                "bytes": len(data), "md5": hashlib.md5(data).hexdigest(),
                "units": units, "axes": "[x, y, z]",
                "dims_mm": measured, "envelope_mm": dims,
                "mount": ad.get("mount"), "stem": ad.get("stem")}
        if len(data) > 2_000_000:
            # mesh bases (dog GLB) are too big for inline JSON — download it
            meta.update({"base64": None, "download": f"/api/design/base/{line}",
                         "note": "too big for inline base64 — GET the download URL"})
            return jsonify(meta)
        meta["base64"] = base64.b64encode(data).decode()
        return jsonify(meta)
    ctype = {"stl": "model/stl", "glb": "model/gltf-binary"}.get(
        base.suffix.lstrip("."), "application/octet-stream")
    data = base.read_bytes()
    resp = Response(data)
    resp.headers["Content-Type"] = ctype
    resp.headers["Content-Length"] = str(len(data))
    resp.headers["Content-Disposition"] = f"attachment; filename=oddhobb-{line}-base{base.suffix}"
    return resp


def _design_tables():
    with db.connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS design_drafts (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, line TEXT NOT NULL,
            spec TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS design_base_fetches (
            owner TEXT NOT NULL, line TEXT NOT NULL, created_at REAL NOT NULL)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_base_fetches
            ON design_base_fetches(owner, line)""")
        c.commit()


def _base_first(owner: str, line: str) -> bool:
    """Did this owner fetch the line base before designing? Base-first is how
    locked interfaces survive: the model plays with our geometry, never its own."""
    try:
        with db.connect() as c:
            row = c.execute("SELECT 1 FROM design_base_fetches WHERE owner=? AND line=?",
                            (owner, line)).fetchone()
            return row is not None
    except Exception:  # noqa: BLE001 — table missing on old DBs: treat as no
        return False


@app.get("/api/design/locks")
def design_locks_all():
    """Every locked constraint, all lines. Agents read this BEFORE
    designing: locked geometry, brand rules, and what save enforces."""
    from backend import locks as _locks
    return jsonify(ok=True, **_locks.all_locks())


@app.get("/api/design/locks/<line>")
def design_locks(line: str):
    from backend import locks as _locks
    try:
        return jsonify(ok=True, **_locks.locks_for(line.strip()))
    except KeyError:
        return _err("unknown line", 404)


@app.post("/api/design/save")
def design_save():
    """A model plays with the base, saves the design: validated spec stored
    as a draft. Returns design_id for figg_design_order.

    Pass stl_base64 (≤32MB STL of the finished design; aliases stl and
    geometry_b64 also accepted) and the geometry is
    CHECKED, not trusted: envelope fit, manifoldness, stem lock vs the
    adapter, and base-preserved proof set base_first from evidence instead
    of the fetch log. Measured dims/volume override reported numbers."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    line = (body.get("line") or "").strip()
    if line not in config.STUDIO_LINES:
        return _err("unknown line — valid ids: " + ", ".join(sorted(config.STUDIO_LINES)), 400)
    spec = config.STUDIO_LINES[line]
    contract = spec.get("design_contract") or {}
    dims = body.get("dims_mm") or contract.get("envelope_mm") or []
    material = (body.get("material") or contract.get("material") or "PLA")
    colors = body.get("colors", 1)
    text = str(body.get("text") or "")
    volume = body.get("volume_cm3", contract.get("volume_cm3_est"))
    geo_gaps: list[str] = []
    geo_proof = False
    similarity = None
    stl_b64 = (body.get("stl_base64") or body.get("stl") or body.get("geometry_b64") or "").strip()
    ignored = sorted(k for k in body
                     if k not in ("owner", "line", "dims_mm", "material", "colors", "text",
                                  "volume_cm3", "stl_base64", "stl", "geometry_b64")
                     and any(s in k.lower() for s in ("stl", "geom", "model", "mesh", "brep", "step")))
    if stl_b64:
        from backend import geometry as _geo
        try:
            import base64 as _b64
            tris = _geo.parse_stl(_b64.b64decode(stl_b64, validate=True))
        except Exception:  # noqa: BLE001
            return _err("stl_base64 is not a parseable STL (binary or ASCII, ≤32MB)", 400)
        envelope = contract.get("envelope_mm") or []
        if envelope:
            for got, maxv, ax in zip(_geo.bbox(tris), envelope, "XYZ"):
                if got > maxv:
                    geo_gaps.append(f"geometry {ax} {got}mm exceeds envelope {maxv}mm")
        geo_gaps += _geo.manifold_gaps(tris)
        try:
            ad = json.loads((Path("scripts/factory/adapters") / f"{line}.json").read_text())
            geo_gaps += _geo.stem_gaps(tris, ad.get("stem") or {})
            base_path = Path("data/3dprint") / ad.get("base", "")
            if base_path.is_file():
                base_tris = _geo.parse_stl(base_path.read_bytes())
                similarity = _geo.base_match(tris, base_tris)
                geo_gaps += _geo.base_preserved_gaps(tris, base_tris)
        except (OSError, ValueError, KeyError):
            pass
        if not geo_gaps:
            geo_proof = True
            dims = _geo.bbox(tris)
            volume = _geo.volume_cm3(tris)
    # reuse the validator by direct call shape
    with app.test_request_context(json={"line": line, "dims_mm": dims, "material": material,
                                        "colors": colors, "text": text, "volume_cm3": volume}):
        resp = design_validate()
    out = resp.get_json()
    if not out.get("ok") or not out.get("feasible"):
        return jsonify({"ok": False, "feasible": False,
                        "gaps": out.get("gaps", ["invalid"]),
                        "hint": "Fix the gaps against the contract, then save again."}), 400
    _design_tables()
    did = "dsn_" + uuid.uuid4().hex[:12]
    first = geo_proof or _base_first(owner, line)
    with db.connect() as c:
        c.execute("INSERT INTO design_drafts VALUES (?,?,?,?,?)",
                  (did, owner, line, json.dumps({"dims_mm": dims, "material": material,
                                                 "colors": colors, "text": text,
                                                 "volume_cm3": volume,
                                                 "base_first": first,
                                                 "geometry_proof": geo_proof}), time.time()))
        c.commit()
    if geo_gaps:
        return jsonify({"ok": False, "feasible": False, "gaps": geo_gaps,
                        "hint": "Geometry failed against the base — fix the model, not the numbers."}), 400
    out_hint = ("Saved with geometry proof — stem, envelope and base all verified."
                if geo_proof else
                "Saved. Order it with POST /api/design/order."
                if first else
                "Saved WITHOUT the line base — fulfil will refuse until you "
                "fetch GET /backend/api/design/base/<line>?owner=<you> and save again. "
                "Free-modelling voids the interface warranty.")
    return jsonify({"ok": True, "design_id": did, "line": line,
                    "base_first": first, "geometry_proof": geo_proof,
                    "measured_dims_mm": dims if geo_proof else None,
                    "measured_volume_cm3": volume if geo_proof else None,
                    "base_similarity": similarity,
                    "ignored_keys": ignored,
                    "options": out.get("options", []),
                    "hint": out_hint})


@app.post("/api/design/make")
def design_make():
    """Run Blender headless on our farm box: emboss text onto the line's
    master via its adapter, return the STL + manifold verdict. This is how
    a remote agent (ChatGPT) uses Blender through us — no local install,
    no viewport, same contracts. Sync; takes ~1-2 min."""
    import subprocess
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    line = (body.get("line") or "").strip()
    text = str(body.get("text") or "")
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    adapter = Path("scripts/factory/adapters") / f"{line}.json"
    if not adapter.is_file():
        # legacy names predate the convention
        legacy = {"card_rack": "card_hand_rack.json", "tcg_stand": "slab_stand.json",
                  "straw_charm": "straw_ring.json"}.get(line)
        adapter = Path("scripts/factory/adapters") / (legacy or "")
    if not adapter.is_file():
        return _err("no emboss adapter for this line yet", 400)
    outdir = Path("data/designs")
    outdir.mkdir(parents=True, exist_ok=True)
    job = f"{line}-{uuid.uuid4().hex[:8]}.stl"
    try:
        proc = subprocess.run(
            [str(Path.home() / "blender" / "blender"), "--background",
             "--python", "scripts/factory/personalize.py", "--",
             "--adapter", str(adapter), "--text", text,
             "--out", str(outdir / job)],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return _err("Blender timed out — try a shorter text", 504)
    if proc.returncode != 0 or not (outdir / job).is_file():
        tail = (proc.stderr or proc.stdout or "")[-300:]
        return _err(f"Blender failed: {tail}", 500)
    preview_url = ""
    try:
        import subprocess as _sp
        import tempfile as _tf
        import shutil as _sh
        tmp = Path(_tf.mkdtemp(prefix="makeprev-"))
        r = _sp.run(
            [str(Path.home() / "blender" / "blender"), "--background",
             "--python", "scripts/factory/stills.py", "--",
             "--in", str(outdir / job), "--out", str(tmp),
             "--size", "512", "--samples", "16"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True, timeout=600)
        hero = tmp / "hero.png"
        views = {}
        if r.returncode == 0:
            destdir = Path("data/designs/previews") / Path(job).stem
            destdir.mkdir(parents=True, exist_ok=True)
            for name in ("hero", "front", "side", "back"):
                src = tmp / f"{name}.png"
                if src.is_file():
                    _sh.copyfile(src, destdir / f"{name}.png")
                    views[name] = f"/backend/api/design/preview/{Path(job).stem}/{name}"
        _sh.rmtree(tmp, ignore_errors=True)
        preview_url = views.get("hero", "")
    except Exception:
        preview_url = ""
    return jsonify({"ok": True, "line": line, "text": text,
                    "stl_url": f"/backend/api/design/file/{job}",
                    "preview_url": preview_url, "views": views,
                    "log": (proc.stdout or "")[-500:],
                    "hint": "Watertight STL from the line master. Validate dims via /api/design/validate."})


@app.get("/api/design/preview/<stem>/<view>")
def design_preview_view(stem: str, view: str):
    """Fetch one persisted make-view: hero/front/side/back per design."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", stem or ""):
        return _err("bad design", 400)
    if view not in ("hero", "front", "side", "back"):
        return _err("view must be hero, front, side or back", 400)
    target = (Path("data/designs/previews") / stem / f"{view}.png").resolve()
    base = Path("data/designs/previews").resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        return _err("not found", 404)
    res = send_file(target, mimetype="image/png", max_age=3600)
    res.headers["Cache-Control"] = "private, no-store"
    return res


@app.get("/api/design/preview/<name>")
def design_preview(name: str):
    """Fetch a made-STL preview PNG."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", name or ""):
        return _err("bad name", 400)
    target = (Path("data/designs/previews") / name).resolve()
    if not str(target).startswith(str(Path("data/designs/previews").resolve())) \
            or not target.is_file():
        return _err("not found", 404)
    res = send_file(target, mimetype="image/png", max_age=3600)
    res.headers["Cache-Control"] = "private, no-store"
    return res


@app.get("/api/design/file/<name>")
def design_file(name: str):
    """Fetch a made STL."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.stl", name or ""):
        return _err("bad name", 400)
    target = (Path("data/designs") / name).resolve()
    if not str(target).startswith(str((Path("data/designs")).resolve())) or not target.is_file():
        return _err("not found", 404)
    data = target.read_bytes()
    resp = Response(data)
    resp.headers["Content-Type"] = "model/stl"
    resp.headers["Content-Length"] = str(len(data))
    return resp


@app.post("/api/design/order")
def design_order():
    """Order a saved design: re-validates, reserves, optional Shopify draft.
    No card charge from this endpoint."""
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    did = (body.get("design_id") or "").strip()
    try:
        qty = max(1, min(20, int(body.get("qty") or 1)))
    except (TypeError, ValueError):
        return _err("qty must be 1-20", 400)
    fulfil = bool(body.get("fulfil") or body.get("shopify"))
    _design_tables()
    with db.connect() as c:
        row = c.execute("SELECT * FROM design_drafts WHERE id=?", (did,)).fetchone()
    if row is None:
        return _err("no such design", 404)
    d = dict(row)
    if d["owner"] != owner:
        return _err("not your design", 403)
    draft = json.loads(d["spec"])
    spec = config.STUDIO_LINES.get(d["line"]) or {}
    price = int(spec.get("price_cents") or 0) * qty
    if fulfil and not draft.get("base_first"):
        return _err("fulfil refused: this draft was saved without fetching the line base. "
                    "GET /api/design/base/<line>, design inside it, save again — "
                    "locked interfaces must come from our geometry.", 400)
    with db.connect() as c:
        order = db.create_order(
            c, owner=owner, line=d["line"], mesh_id=str(body.get("mesh_id") or ""),
            coat="none", hat="none", qty=qty, price_cents=price,
            note=f"design {did} ({draft.get('material')}/{draft.get('text') or 'no text'})"[:200],
            design_id=did,
        )
    shopify: dict = {"attempted": False}
    if fulfil:
        shopify["attempted"] = True
        try:
            from backend import shopify_fulfil as sf
            if not sf.configured():
                shopify = {"attempted": True, "ok": False, "error": "Shopify not configured"}
            else:
                res = sf.create_draft_order(f"{spec.get('label', d['line'])} (design {did})",
                                            price // max(1, qty), qty,
                                            note=f"design {did}", email="")
                shopify.update(res)
        except Exception as e:  # noqa: BLE001
            shopify = {"attempted": True, "ok": False, "error": str(e)[:300]}
    return jsonify({"ok": True, "order": order, "design_id": did,
                    "status": "pending_checkout", "shopify": shopify,
                    "hint": "Reserved. Shopify draft only if fulfil=true."})


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
    try:
        qty = max(1, min(20, int(body.get("qty") or 1)))
    except (TypeError, ValueError):
        return _err("qty must be 1-20", 400)
    note = (body.get("note") or "")[:200]
    email = (body.get("email") or "").strip()[:120]
    amount_cents = body.get("amount_cents")
    fulfil = bool(body.get("fulfil") or body.get("shopify"))
    if line not in config.STUDIO_LINES:
        return _err("unknown line", 400)
    spec = config.STUDIO_LINES[line]
    if spec.get("status") != "live":
        return _err(f"{line} is not orderable yet", 409)
    text, text_err = _check_text(line, body.get("text") or "")
    if text_err:
        return text_err
    slot_resolved = None
    if isinstance(body.get("slots"), dict):
        try:
            from backend import slots as _slots
            slot_resolved = _slots.validate(line, body["slots"])["resolved"]
            text = text or slot_resolved.get("name")
        except ValueError as e:
            return _err(f"slot rejected: {e} — retry a nickname or initials", 400)
    if line == "gift_card":
        amounts = spec.get("amounts_cents") or [spec.get("price_cents", 2500)]
        if amount_cents is None:
            amount_cents = amounts[0]
        try:
            amount_cents = int(amount_cents)
        except (TypeError, ValueError):
            return _err(f"amount_cents must be one of {amounts}", 400)
        if amount_cents not in amounts:
            return _err(f"amount_cents must be one of {amounts}", 400)
        price = amount_cents * qty
    else:
        price = int(spec.get("price_cents") or 0) * qty
    label = f"{spec.get('label', line)}"
    if text:
        label = f"{text} {spec.get('label', line)}"
    if line != "gift_card":
        extras = []
        if coat != "none":
            extras.append(f"coat:{coat}")
        if pattern != "solid":
            extras.append(f"pattern:{pattern}")
        if hat != "none":
            extras.append(f"hat:{hat}")
        if text:
            extras.append(f"text:{text}")
        if extras:
            label += " (" + ", ".join(extras) + ")"
    # Remix royalty: designing with someone else's mesh adds a flat $1,
    # always, to them. Recorded on the order; the bank of designs pays out.
    REMIX_CENTS = 100
    remix_of = body.get("remix_of") or {}
    remix_designer, remix_design = "", ""
    if isinstance(remix_of, dict):
        remix_designer = str(remix_of.get("designer") or "")[:60]
        remix_design = str(remix_of.get("design") or "")[:80]
    if remix_designer and line != "gift_card":
        price += REMIX_CENTS * qty
    custom_note = note
    if line != "gift_card":
        custom_note = (custom_note + " | " if custom_note else "") + \
            f"custom coat={coat} pattern={pattern} hat={hat}"
        if text:
            custom_note = (custom_note + " | " if custom_note else "") + \
                f"emboss text={text}"
        if slot_resolved:
            custom_note = (custom_note + " | " if custom_note else "") + \
                f"slots base={slot_resolved.get('base')} " \
                f"accent={slot_resolved.get('accent')} " \
                f"tagline={slot_resolved.get('tagline') or '-'} " \
                f"arc={slot_resolved.get('arc') or '-'}"
    if remix_designer and line != "gift_card":
        custom_note = (custom_note + " | " if custom_note else "") + \
            f"remix $1 to {remix_designer}" + (f" for {remix_design}" if remix_design else "")
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
                        try:
                            cols = [r[1] for r in c.execute("PRAGMA table_info(orders)").fetchall()]
                        except Exception:
                            cols = []
                        if "checkout_url" not in cols:
                            try:
                                c.execute("ALTER TABLE orders ADD COLUMN checkout_url TEXT NOT NULL DEFAULT ''")
                            except Exception:
                                pass
                        try:
                            c.execute(
                                "UPDATE orders SET note=?, checkout_url=? WHERE id=?",
                                ((custom_note + f" | shopify:{draft.get('draft_id') or draft.get('name')}")[:200],
                                 draft.get("invoice_url") or "", order.get("id")),
                            )
                        except Exception:
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
        "checkout_url": (shopify.get("invoice_url") if isinstance(shopify, dict) else "") or "",
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
    try:
        qty = max(1, min(20, int(body.get("qty") or 1)))
    except (TypeError, ValueError):
        return _err("qty must be 1-20", 400)
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


def _supplier_options(spec: dict) -> list[dict]:
    """Full per-supplier options (server-side routing only — never served)."""
    from backend import suppliers as _sup
    mat = spec.get("material") or "PLA"
    weight = spec.get("weight_g")
    vol = round(weight / 1.24, 2) if isinstance(weight, (int, float)) else None
    if vol is None:
        vol = (spec.get("design_contract") or {}).get("volume_cm3_est")
    dims = spec.get("dims_mm") or (spec.get("design_contract") or {}).get("envelope_mm")
    return _sup.options_for(material=mat, colors=1,
                            dims_mm=dims, volume_cm3=vol,
                            weight_g=weight)


def _fulfilment_options(spec: dict) -> dict:
    """What the customer (and agents) may see: capabilities, never names.

    Suppliers stay invisible. Shoppers customise freely; we pick the optimal
    physical implementation server-side and propose adjustments ("make it
    this big") when close to a better fit.
    """
    from backend import suppliers as _sup
    opts = [o for o in _supplier_options(spec) if o["feasible"]]
    if not opts:
        return {"printable": False, "note": "No farm fits this design yet."}
    mats, colors, ships, disp = set(), 0, set(), []
    for o in opts:
        s = _sup.SUPPLIERS[o["supplier"]]
        mats.update(s["materials"])
        colors = max(colors, s["colors_max"])
        ships.update(s["ships"])
        disp.append(s["dispatch_days"])
    lo = min(d[0] for d in disp)
    hi = max(d[1] for d in disp)
    return {"printable": True, "materials": sorted(mats),
            "colors_max": colors, "ships": sorted(ships),
            "dispatch_days": [lo, hi],
            "options_count": len(opts)}


@app.get("/api/suppliers")
def supplier_list():
    """Supplier registry + estimator. Estimates are bands, live quotes win."""
    from backend import suppliers as _sup
    return jsonify({"ok": True, "suppliers": [
        {"id": sid, **{k: v for k, v in spec.items() if k != "est"},
         "pricing": spec["est"]} for sid, spec in _sup.SUPPLIERS.items()]})


@app.get("/api/products/studio")
def products_studio():
    """Products tab catalog: studio lines + relevant assets + stills + prices."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        active = prof.get("active_mesh_id") or ""
        subject = db.get_subject_profile(c, owner, active) if active else {}
        if not subject:
            # fall back to the Studio library: selected friend, else first
            # named friend, paired with the active mesh. Nibble resolves here.
            try:
                sel = c.execute(
                    "SELECT * FROM studio_selection WHERE owner=?", (owner,)).fetchone()
                sid = (dict(sel).get("subject_id") if sel else "") or ""
                if not sid:
                    row = c.execute(
                        "SELECT * FROM studio_subjects WHERE owner=? ORDER BY created_at LIMIT 1",
                        (owner,)).fetchone()
                    sid = row["id"] if row else ""
                if sid:
                    srow = c.execute(
                        "SELECT * FROM studio_subjects WHERE id=?", (sid,)).fetchone()
                    if srow:
                        subject = {"name": srow["name"], "interests": [],
                                   "birthday": "", "kind": srow["kind"] if "kind" in srow.keys() else ""}
            except Exception:
                pass
    suggestion = _suggest_motif(subject.get("interests", [])) if subject else None
    gifts = _derive_gifts(subject, active) if subject else []
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
        if lid == "clog_charm":
            # Nibble proof: first real personalised product photo on the line
            stills = {"hero": config.STUDIO_NIBBLE_JIBBIT_PORTRAIT,
                      "front": config.STUDIO_NIBBLE_JIBBIT_PORTRAIT}
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
            "glb_url": (config.STUDIO_BRICK_GLB if lid == "brick"
                        else config.STUDIO_NIBBLE_JIBBIT_GLB if lid in ("clog_charm", "croc_tag") else ""),
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
            "fulfilment_options": _fulfilment_options(spec),
            "design_contract": spec.get("design_contract"),
            "supplier_options": (_supplier_options(spec)
                                 if (request.args.get("design") == "1") else None),
        })
    return jsonify({
        "ok": True,
        "owner": owner,
        "active_mesh_id": active,
        "subject": subject or None,
        "suggestion": suggestion,
        "gifts": gifts,
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

@app.post("/api/gift-packs")
def gift_pack():
    """Oddy's game: best gift for the cheapest price inside a budget.

    Body: {owner, budget_cents, line? (exact thing), mesh_id?, recipient?,
           occasion?}. Occasion must be one of: birthday, wedding, christmas,
    fathers_day, mothers_day, valentine, anniversary, thank_you, new_job,
    baby, retirement.
    A pack is usually physical + card + free video addon. Exact requests are
    honoured with cheap addons while they fit; otherwise Oddy picks the best
    physical that leaves room for a card, video always free.
    """
    from backend import card_scenes as _scenes
    body = request.get_json(silent=True) or {}
    owner = (body.get("owner") or "anon").strip()[:80]
    try:
        budget = int(body.get("budget_cents") or 0)
    except (TypeError, ValueError):
        return _err("budget_cents must be a number", 400)
    if budget <= 0:
        return _err("tell Oddy the budget first", 400)
    occasion = (body.get("occasion") or "").strip().lower()
    if occasion and occasion not in ("birthday", "wedding", "christmas",
                                     "fathers_day", "mothers_day", "valentine",
                                     "anniversary", "thank_you", "new_job", "baby",
                                     "retirement", "new_baby", "graduation",
                                     "just_because"):
        return _err("unknown occasion — valid: birthday, wedding, christmas, "
                    "fathers_day, mothers_day, valentine, anniversary, "
                    "thank_you, new_job, baby, retirement, new_baby, "
                    "graduation, just_because", 400)
    want = (body.get("line") or "").strip()
    if want and want not in config.STUDIO_LINES:
        return _err("unknown line — valid ids: " + ", ".join(sorted(config.STUDIO_LINES)), 400)
    mesh_id = (body.get("mesh_id") or "").strip()
    recipient = (body.get("recipient") or "").strip()[:60]
    card_floor = min(v["price_cents"] for v in _scenes.FORMATS.values())
    card_format = min(_scenes.FORMATS.items(), key=lambda kv: kv[1]["price_cents"])[0]
    card_label = _scenes.FORMATS[card_format]["label"]
    # card truth: the shelf postcard (£3.99 Prodigi) undercuts our A6 print
    # cost — quote the cheaper one honestly, and pick a folded greeting for
    # card occasions whenever it fits
    folded_occasions = ("birthday", "wedding", "valentine", "anniversary",
                        "mothers_day", "fathers_day", "christmas", "retirement")
    _greet = config.PRODIGI_PRODUCTS.get("greeting_card", {})
    _post = config.PRODIGI_PRODUCTS.get("postcard", {})

    def _pick_card(room_cents: int):
        if occasion in folded_occasions and int(_greet.get("price_cents") or 0) <= room_cents:
            return {"template": "portrait", "format": "greeting",
                    "label": _greet.get("label", "Greeting Card"),
                    "price_cents": int(_greet["price_cents"])}
        if int(_post.get("price_cents") or 0) <= room_cents:
            return {"template": "portrait", "format": "postcard",
                    "label": _post.get("label", "Postcard"),
                    "price_cents": int(_post["price_cents"])}
        if card_floor <= room_cents:
            return {"template": "portrait", "format": card_format,
                    "label": card_label, "price_cents": card_floor}
        return None
    live = [(lid, s) for lid, s in config.STUDIO_LINES.items()
            if s.get("status") == "live" and (s.get("fulfilment") or "") == "print_farm"]
    # recipient-aware pick: a named friend with known interests steers Oddy
    # toward their motif; otherwise the recipient text itself is scanned for
    # known interests ("dad, loves golf" → golf) before falling back to
    # dearest-that-fits
    motif = ""
    if recipient:
        try:
            with db.connect() as c:
                prow = c.execute("SELECT interests FROM subject_profiles WHERE owner=? AND name=?",
                                 (owner, recipient)).fetchone()
                interests = json.loads((dict(prow).get("interests") or "[]")) if prow else []
        except Exception:  # noqa: BLE001
            interests = []
        if not interests:
            low = recipient.lower()
            interests = [k for k in config.INTEREST_MOTIFS
                         if re.search(r"\b" + re.escape(k) + r"\b", low)]
        if interests:
            motif = (_suggest_motif(interests) or {}).get("motif", "")

    def _rank_key(item):
        price, lid = item
        s = config.STUDIO_LINES[lid]
        hay = f"{lid} {s.get('label', '')} {s.get('theme', '')}".lower()
        loved = 0 if (motif and motif.replace("_", " ") in hay) else 1
        return (loved, -price)

    pack: dict = {"video": {"kind": "motion", "label": "Matching video",
                            "price_cents": 0,
                            "note": "rendered from the card scene, free" +
                                    ("" if mesh_id else " — needs a mesh: upload a photo first")}}
    if want:
        spec = config.STUDIO_LINES[want]
        price = int(spec.get("price_cents") or 0)
        if price > budget:
            return _err(f"{want} alone is over budget", 400)
        pack["physical"] = {"line": want, "label": spec.get("label", want),
                            "price_cents": price}
        rest = budget - price
        card = _pick_card(rest)
        if card:
            card["note"] = "cheap add-on inside the budget"
            pack["card"] = card
    else:
        cheapest_card = min(card_floor, int(_post.get("price_cents") or card_floor))
        room = budget - cheapest_card
        cands = sorted(((int(s.get("price_cents") or 0), lid)
                        for lid, s in live), key=_rank_key)
        pick = next(((p, lid) for p, lid in cands if p <= room), None)
        if not pick:
            cheapest = min(cands, key=lambda t: t[0]) if cands else None
            if not cheapest:
                return _err("nothing orderable yet", 400)
            pack["physical"] = {"line": cheapest[1], "price_cents": cheapest[0],
                                "note": "over budget alone — card dropped"}
        else:
            price, lid = pick
            spec = config.STUDIO_LINES[lid]
            pack["physical"] = {"line": lid, "label": spec.get("label", lid),
                                "price_cents": price}
            if motif:
                pack["physical"]["reason"] = f"picked for {recipient}: {motif.replace('_', ' ')}"
            card = _pick_card(budget - price)
            if card:
                pack["card"] = card
    total = sum(v.get("price_cents", 0) for v in pack.values())
    pack["total_cents"] = total
    pack["remaining_cents"] = budget - total
    leftover = budget - total
    others = sorted(((int(s.get("price_cents") or 0), lid) for lid, s in live
                     if lid != (pack.get("physical") or {}).get("line")),
                    key=_rank_key)
    addon = next(((p, lid) for p, lid in others if p <= leftover), None)
    if addon:
        price, lid = addon
        pack["suggested_addon"] = {"line": lid,
                                   "label": config.STUDIO_LINES[lid].get("label", lid),
                                   "price_cents": price,
                                   "note": "fits the unspent remainder"}
    pack["recipient"] = recipient
    if occasion:
        pack["occasion"] = occasion
    pack["mesh_id"] = mesh_id
    return jsonify({"ok": True, "pack": pack,
                    "hint": "Reserve each part (products/order, cards/order); video renders free from the card."})


@app.get("/api/studio/demo")
def studio_demo():
    """Nibble: the demo friend every new visitor meets. Her original photo,
    her mesh, and her derived gifts — try the shelf before uploading."""
    with db.connect() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id,r2_key,person,mime FROM photos WHERE owner='anon' AND person='Nibble' ORDER BY created_at LIMIT 1")]
        if not rows:
            return jsonify({"ok": True, "demo": None})
        ph = rows[0]
        m = c.execute("SELECT id FROM meshes WHERE photo_id=? ORDER BY created_at DESC LIMIT 1",
                      (ph["id"],)).fetchone()
        mesh_id = m["id"] if m else ""
    subject = {"name": "Nibble", "interests": [], "birthday": ""}
    return jsonify({"ok": True, "demo": {
        "name": "Nibble",
        "photo": {"id": ph["id"], "url": "/api/artifacts/" + ph["r2_key"]},
        "mesh_id": mesh_id,
        "gifts": _derive_gifts(subject, mesh_id),
    }})


@app.get("/api/studio/orders")
def studio_orders():
    owner = (request.args.get("owner") or "anon").strip()[:80]
    denied = _owner_denied(owner)
    if denied is not None: return denied
    with db.connect() as c:
        rows = db.orders_for(c, owner)
    return jsonify({"ok": True, "owner": owner, "orders": rows, "count": len(rows)})


def short_mesh_label(mesh_id: str) -> str:
    if not mesh_id:
        return "no mesh"
    return "mesh " + mesh_id.replace("msh_", "")[:6]


from backend import cards as card_api
card_api.register(app, _owner_denied)
from backend import studio_library
studio_library.register(app, _owner_denied)


# ── creative compiler (cardgen.md) ─────────────────────────────────────
# Person graph → brief → ranked versioned templates → immutable scene →
# renderer DAG → validated artifacts. AI fills fields, never pixels.

from backend.creative import artifacts as _art
from backend.creative import briefs as _briefs
from backend.creative import jobs as _cjobs
from backend.creative import matcher as _matcher
from backend.creative import projects as _cproj
from backend.creative import templates as _ctmpl
from backend.creative import catalog as _ccatalog
from backend import subjects as _subjects


def _creative_tables():
    with db.connect() as c:
        from backend import studio_library as _sl
        c.executescript(_sl.SCHEMA)
        _subjects.ensure_tables(c)
        _cproj.ensure_tables(c)
        _art.ensure_tables(c)


@app.get("/api/creative/templates")
def creative_templates():
    _creative_tables()
    reg = _ctmpl.load_all()
    return jsonify({"ok": True, "count": len(reg),
                    "templates": [
                        {**{k: t[k] for k in ("id", "version", "taxonomy", "requirements",
                                             "slots", "renderers")},
                         **({"presentation": t.get("presentation", {})}
                            if t.get("presentation") else {})}
                        for t in reg.values()]})


def _brief_asset_counts(c, owner: str, subject_id: str = "") -> dict:
    """Assets for THIS subject — never the whole account (a Mum with ten
    photos must not qualify a photo-less Dad). Missing tables (fresh DBs)
    count as zero, never 500."""
    def one(sql, args):
        try:
            row = c.execute(sql, args).fetchone()
            return dict(row)["n"] if row else 0
        except sqlite3.Error:
            return 0
    if subject_id:
        photos = one("SELECT COUNT(DISTINCT p.id) n FROM photos p"
                     " JOIN photo_subjects ps ON ps.photo_id=p.id"
                     " WHERE p.owner=? AND ps.subject_id=?", (owner, subject_id))
        faces = one("SELECT COUNT(*) n FROM photo_subjects WHERE subject_id=? AND confirmed=1",
                    (subject_id,))
        meshes = one("SELECT COUNT(*) n FROM mesh_subjects WHERE subject_id=?", (subject_id,))
        try:
            voice = c.execute("SELECT 1 FROM voice_consents WHERE owner=? AND subject_id=?"
                              " AND revoked_at=0", (owner, subject_id)).fetchone()
        except sqlite3.Error:
            voice = None
    else:
        photos = one("SELECT COUNT(*) n FROM photos WHERE owner=?", (owner,))
        faces = one("SELECT COUNT(*) n FROM photo_subjects ps JOIN photos p ON p.id=ps.photo_id"
                    " WHERE p.owner=? AND ps.confirmed=1", (owner,))
        meshes = one("SELECT COUNT(*) n FROM meshes m JOIN photos p ON p.id=m.photo_id"
                     " WHERE p.owner=? AND m.status='succeeded'", (owner,))
        voice = None
    return {"photos": photos, "confirmed_face_photos": faces,
            "meshes": meshes, "voice": bool(voice)}


@app.get("/api/creative/catalog")
def creative_catalog():
    """The viral-format library used by both storefront browsing and agents."""
    return jsonify(_ccatalog.query(
        style=(request.args.get("style") or "").strip(),
        occasion=(request.args.get("occasion") or "").strip(),
        audience=(request.args.get("audience") or "").strip(),
        tone=(request.args.get("tone") or "").strip(),
        q=(request.args.get("q") or "").strip(),
        rank=(request.args.get("rank") or "").strip(),
    ))


@app.get("/api/creative/catalog/preview")
def creative_catalog_preview():
    """One rail tile with the viewer's photo already applied (the Moonpig
    shelf): template look + headline + example caption composited over the
    given photo. Content-cached; ghosts stay client-side on any failure."""
    from backend.renderers import composite2d as _c2d
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    tid = (request.args.get("template_id") or "").strip()[:80]
    pid = (request.args.get("photo_id") or "").strip()[:80]
    item = _ccatalog.by_id().get(tid)
    if not item:
        return _err("unknown template", 404)
    with db.connect() as c:
        row = c.execute("SELECT * FROM photos WHERE id=? AND owner=?",
                        (pid, owner)).fetchone()
    if row is None:
        return _err("photo not found", 404)
    try:
        import hashlib as _hl
        key = _hl.sha256(f"{tid}|{dict(row).get('r2_key', '')}".encode()).hexdigest()[:24]
        dest = config.DATA / "catalog-previews" / f"{tid}-{key}.jpg"
        if not dest.is_file():
            from backend import pipeline as _pipe
            photo_path = str(_pipe._local_photo(dict(row)))
            img = _c2d.render_card(
                photo_path=photo_path,
                headline=str(item.get("label") or tid),
                subheadline=str(item.get("example_caption") or "")[:90],
                style_id=str(item.get("style") or "generic"))
            # style geometry is authored at print scale — downscale for tiles
            img = img.resize((600, 840), _c2d.Image.Resampling.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "JPEG", quality=75)
    except Exception as e:  # noqa: BLE001 — rail tiles degrade to ghosts
        return _err(f"preview failed: {str(e)[:120]}", 500)
    res = send_file(dest, mimetype="image/jpeg", max_age=86400)
    res.headers["Cache-Control"] = "public, max-age=86400"
    return res


@app.get("/api/creative/duel")
def creative_duel():
    """Two comics, pick the funnier one. Trains the ComedyJudge: every
    vote lands in the preference DB next to social engagement."""
    from backend.creative import comics as _comics
    try:
        a, b = _comics.duel_pair()
    except ValueError as e:
        return _err(str(e), 503)
    slim = lambda s: {"id": s.get("id"), "title": s.get("title"),
                      "premise": s.get("premise"), "panels": s.get("panels"),
                      "caption": s.get("caption")}
    return jsonify(ok=True, a=slim(a), b=slim(b))


@app.post("/api/creative/duel/vote")
def creative_duel_vote():
    """Record a duel vote. winner is one of the two ids or 'neither'."""
    from backend.creative import comics as _comics
    from backend.creative import judge as _judge
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    scripts = {s.get("id"): s for s in _comics.load_comics().values()}
    aid, bid = str(body.get("a_id") or ""), str(body.get("b_id") or "")
    winner = str(body.get("winner") or "")
    if aid not in scripts or bid not in scripts or aid == bid:
        return _err("pass two different comic ids", 400)
    if winner not in (aid, bid, "neither"):
        return _err("winner must be one of the two ids or 'neither'", 400)
    row = _judge.record_preference(scripts[aid], scripts[bid],
                                   "a" if winner == aid else
                                   "b" if winner == bid else "neither",
                                   user=owner, context="duel")
    return jsonify(ok=True, recorded=bool(row.get("ts")))


@app.get("/api/creative/art")
def creative_art():
    """The art shelf: browse finished pieces, pick a surface."""
    from backend.creative import art as _art
    return jsonify(ok=True, formats={k: {"label": v["label"],
                                          "price_cents": v["price_cents"],
                                          "blurb": v["blurb"]}
                                      for k, v in _art.FORMATS.items()},
                   items=_art.list_art())


@app.post("/api/creative/art/order")
def creative_art_order():
    """Reserve an art piece on a surface. No charge from our API."""
    from backend.creative import art as _art
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    try:
        qty = int(body.get("qty") or 1)
    except (ValueError, TypeError):
        return _err("qty must be a number", 400)
    try:
        return jsonify(ok=True, **_art.order(
            owner, str(body.get("art_id") or ""),
            str(body.get("format") or ""), qty))
    except KeyError:
        return _err("unknown art piece", 404)
    except ValueError as e:
        return _err(str(e), 400)


@app.post("/api/creative/art/mp4")
def creative_art_mp4():
    """Render an art piece as a vertical MP4 (text plates + voiceover)."""
    from backend.creative import art as _art
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    try:
        dest = _art.make_mp4(str(body.get("art_id") or ""),
                             str(body.get("voice") or "ryan"))
    except KeyError:
        return _err("unknown art piece", 404)
    except Exception as e:
        return _err(f"render failed: {str(e)[:200]}", 500)
    return jsonify(ok=True, mp4_url=f"/api/creative/art/mp4/{dest.name}")


@app.get("/api/creative/art/mp4/<name>")
def creative_art_mp4_file(name: str):
    from backend.creative import art as _art
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_.")[:80]
    dest = config.DATA / "art" / "mp4" / safe
    if dest.suffix != ".mp4" or not dest.is_file():
        return _err("not ready", 404)
    res = send_file(dest, mimetype="video/mp4", max_age=0)
    res.headers["Cache-Control"] = "private, no-store"
    return res


@app.post("/api/creative/brief")
def creative_brief():
    """Compile the creative brief: occasion + recipient (subject graph) +
    available assets + ask. Thrown at the matcher, never a renderer."""
    from backend import guide as _gde
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    with db.connect() as c:
        sub = _subjects.get_subject(c, owner, (body.get("subject_id") or ""))
        if not sub and body.get("name"):
            sub = _subjects.find_subject_by_name(c, owner, body.get("name"))
        prof = _subjects.profile_for(c, owner, sub.get("id", "")) if sub else {}
        counts = _brief_asset_counts(c, owner, sub.get("id", "") if sub else "")
    brief = _briefs.build(occasion=(body.get("occasion") or "general"),
                          occasion_date=str(body.get("occasion_date") or ""),
                          subject=sub, profile=prof, asset_counts=counts,
                          tone=str(body.get("tone") or "funny"),
                          budget_cents=int(body.get("budget_cents") or 0),
                          request=str(body.get("request") or ""))
    return jsonify({"ok": True, "brief": brief})


@app.post("/api/creative/match")
def creative_match():
    """Deterministic template ranking for a brief: eligibility filter +
    weighted score + reasons. LLM explains; it never decides."""
    body = request.get_json(silent=True) or {}
    brief = body.get("brief") or {}
    if not brief and body.get("subject_id"):
        return _err("pass a brief (POST /api/creative/brief first)", 400)
    if brief and not brief.get("occasion"):
        return _err("brief has no occasion — rebuild it via POST /api/creative/brief", 400)
    _creative_tables()
    reg = _ctmpl.load_all()
    return jsonify({"ok": True, "matches": _matcher.match(
        brief, reg, limit=int(body.get("limit") or 5))})


@app.post("/api/creative/projects")
def creative_project_create():
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    with db.connect() as c:
        p = _cproj.create_project(c, owner, str(body.get("subject_id") or ""),
                                  str(body.get("template_id") or ""))
    return jsonify({"ok": True, "project": p})


@app.post("/api/creative/revisions")
def creative_revision_save():
    """Fill template FIELDS (§5), QC the copy, freeze a revision (§8)."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    reg = _ctmpl.load_all()
    tid = str(body.get("template_id") or "")
    t = reg.get(tid)
    if t is None:
        return _err("unknown template — valid: " + ", ".join(sorted(reg)), 400)
    filled, gaps = _cjobs.fill_slots(t, body.get("fields") or {})
    gaps += _art.qc_card_copy(filled, t)
    if gaps:
        return jsonify({"ok": False, "gaps": gaps,
                        "hint": "Fix the fields — geometry stays in the template."}), 400
    with db.connect() as c:
        sid = str(body.get("subject_id") or "")
        proj = None
        if body.get("project_id"):
            row = c.execute("SELECT * FROM creative_projects WHERE id=? AND owner=?",
                            (body.get("project_id") or "", owner)).fetchone()
            proj = dict(row) if row else None
        if proj is None:
            proj = _cproj.find_project(c, owner, sid, tid)
        if not proj:
            p = _cproj.create_project(c, owner, sid, tid)
            pid = p["id"]
        else:
            pid = proj["id"]
            if proj.get("subject_id") and sid and proj["subject_id"] != sid:
                return _err("project belongs to another subject — start a new one", 400)
        try:
            rev = _cproj.save_revision(
                c, pid, tid, int(t.get("version", 1)), body.get("brief") or {}, {
                    "scene_version": "oddhobb.scene.v2",
                    "template": {"id": tid, "version": t.get("version", 1)},
                    "subjects": body.get("subjects") or [],
                    "copy": filled,
                    "render_intent": body.get("render_intent") or {}},
                expected_revision=body.get("expected_revision"))
        except (KeyError, ValueError) as e:
            return _err(str(e)[:200], 400 if "stale" in str(e) or "lineage" in str(e) else 404)
    return jsonify({"ok": True, "revision": rev,
                    "hint": "Immutable — edits create new revisions; orders pin one."})


@app.post("/api/creative/render")
def creative_render():
    """Manifest-driven render → preview + print_master artifacts + real QC.
    Paid renderers staged."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    data, code = _render_revision(owner, str(body.get("project_id") or ""),
                                  int(body.get("revision") or 0),
                                  str(body.get("print_contract") or "card_5x7_folded_v1"))
    return jsonify(data), code


def _render_revision(owner: str, project_id: str, revision: int,
                     contract_id: str = "card_5x7_folded_v1") -> tuple[dict, int]:
    """Shared render core (endpoints call this directly — never nest HTTP)."""
    _creative_tables()
    with db.connect() as c:
        rev = _cproj.get_revision(c, project_id, revision)
    if not rev:
        return {"ok": False, "error": "no such revision"}, 404
    from backend.renderers import composite2d as _c2d
    scene = rev.get("scene") or {}
    cp = scene.get("copy") or {}
    photo_path = None
    for s in scene.get("subjects") or []:
        aids = s.get("asset_ids") or []
        if not aids:
            break
        with db.connect() as c2:
            row = c2.execute("SELECT * FROM photos WHERE id=? AND owner=?",
                             (aids[0], owner)).fetchone()
        if row:
            try:
                photo_path = str(pipeline._local_photo(dict(row)))
            except Exception:  # noqa: BLE001
                photo_path = None
        break
    reg = _ctmpl.load_all()
    tid = (scene.get("template") or {}).get("id", "")
    manifest = reg.get(tid, {})
    contract = _art.PRINT_CONTRACTS.get(contract_id, _art.PRINT_CONTRACTS["card_5x7_folded_v1"])
    from backend.creative import review as _revmod
    pal = _revmod.PALETTES.get((scene.get("render_intent") or {}).get("palette", ""), None)
    style_id = str(((manifest.get("taxonomy") or {}).get("styles") or ["generic"])[0])
    if pal is None:
        pal = dict(zip(("bg", "ink", "accent"),
                       _c2d.PALETTES.get(style_id, _c2d.PALETTES["generic"])))
    if (manifest.get("format") == "comic_strip" or
            (manifest.get("layout") or {}).get("panels")):
        beats = manifest.get("beats") or ["setup", "escalation", "reversal", "payoff"]
        caps = [str(cp.get(f"panel_{i + 1}", "")) for i in range(len(beats))]
        master, gaps = _c2d.render_panels(manifest, contract, panels=caps,
                                          palette=pal, photo_path=photo_path)
    else:
        master, gaps = _c2d.render_from_manifest(
            manifest, contract, photo_path=photo_path, copy=cp, palette=pal)
    if gaps:
        return ({"ok": False, "gaps": gaps,
                 "hint": "Render QC failed — fix fields/assets, not the template."}, 400)
    key = f"owners/{owner}/creative/{rev['project_id']}-r{rev['revision']}-print.png"
    tmp = config.LOCAL_TMP / f"cr_{rev['project_id']}_r{rev['revision']}-print.png"
    master.save(tmp)
    storage.put(tmp, key)
    tmp.unlink(missing_ok=True)
    cache = _art.content_key(scene={**scene, "contract": contract["id"]},
                             renderer="composite2d", renderer_version=1,
                             output_contract="print_master",
                             provider_params={})
    with db.connect() as c:
        hit = _art.by_cache(c, cache, owner)
        if hit:
            return {"ok": True, "cached": True, "artifact": hit}, 200
        art = _art.record(c, owner, rev["project_id"], int(rev["revision"]),
                          "composite2d", "print_master", cache, key,
                          mime="image/png", width=master.width,
                          height=master.height,
                          dpi=int(contract.get("dpi") or 300))
        _art.mark_qc(c, art["id"], True)
    return {"ok": True, "cached": False,
            "artifact": {**art, "url": storage.public_url(key)}}, 200


@app.post("/api/creative/review")
def creative_review():
    """Agent eyes: verdict + scores + concrete fix ops for an artifact.
    Reads only, $0. Feed artifact_id from render/status calls."""
    from backend.creative import review as _rev
    aid = ((request.get_json(silent=True) or {}).get("artifact_id") or "").strip()
    if not aid:
        return _err("artifact_id is required", 400)
    _creative_tables()
    with db.connect() as c:
        out = _rev.review_artifact(c, aid)
    if not out.get("ok"):
        return _err(out.get("error", "no such artifact"), 404)
    return jsonify(out)


@app.post("/api/creative/revise")
def creative_revise():
    """Agent hands: apply ops to a revision → new immutable revision.
    ops: {copy: {headline,…}, mood: happier|funnier|warmer|classier,
          voice, act, render_intent: {...}}. render:true also renders it."""
    from backend.creative import review as _rev
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    pid, rev_n = str(body.get("project_id") or ""), int(body.get("revision") or 0)
    with db.connect() as c:
        base = _cproj.get_revision(c, pid, rev_n)
        if not base:
            return _err("no such revision", 404)
    proj_owner = None
    with db.connect() as c:
        prow = c.execute("SELECT owner FROM creative_projects WHERE id=?", (pid,)).fetchone()
        proj_owner = dict(prow)["owner"] if prow else None
    if proj_owner != owner:
        return _err("no such revision", 404)
    ops = body.get("ops") or {}
    scene = dict(base.get("scene") or {})
    cp = dict(scene.get("copy") or {})
    for k, v in (ops.get("copy") or {}).items():
        cp[str(k)[:40]] = str(v)[:500]
    render_opts: dict = {}
    if ops.get("mood"):
        cp, render_opts = _rev.apply_mood(cp, str(ops["mood"]))
    ri = dict(scene.get("render_intent") or {})
    for k in ("voice", "act", "palette", "expression"):
        if ops.get(k) is not None:
            ri[k] = str(ops[k])[:60]
    for k, v in (ops.get("render_intent") or {}).items():
        ri[str(k)[:40]] = str(v)[:200]
    if render_opts:
        ri.update({k: v for k, v in render_opts.items() if k != "caption_hint"})
    scene = {**scene, "copy": cp, "render_intent": ri}
    tid = (scene.get("template") or {}).get("id", "")
    reg = _ctmpl.load_all()
    t = reg.get(tid, {})
    filled, gaps = _cjobs.fill_slots(t, cp) if t else (cp, [])
    gaps += _art.qc_card_copy(filled, t) if t else []
    if gaps:
        return jsonify({"ok": False, "gaps": gaps,
                        "hint": "Revise breaks copy QC — shorten or fill fields."}), 400
    with db.connect() as c:
        try:
            saved = _cproj.save_revision(
                c, pid, tid, int((scene.get("template") or {}).get("version", 1)),
                base.get("brief_snapshot") or {}, scene)
        except (KeyError, ValueError) as e:
            return _err(str(e)[:200], 400)
    out = {"ok": True, "revision": saved,
           "hint": "New immutable revision. Render it to see the change."}
    if body.get("render"):
        data, code = _render_revision(owner, pid, saved["revision"])
        out["render"] = data
        if code != 200:
            out["render_note"] = "revision saved; render needs attention"
    return jsonify(out)


@app.post("/api/creative/order")
def creative_order():
    """Reserve a creative revision: requires a QC-passed artifact for that
    exact revision. Orders pin revisions; editing creates new ones."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    pid, rev = str(body.get("project_id") or ""), int(body.get("revision") or 0)
    with db.connect() as c:
        r = _cproj.get_revision(c, pid, rev)
        if not r:
            return _err("no such revision", 404)
        ok_art = c.execute("SELECT * FROM render_artifacts WHERE project_id=? AND revision=? AND qc_status='passed'"
                           " AND output_kind='print_master'", (pid, rev)).fetchone()
    if not ok_art:
        return _err("no QC-passed print_master for this revision — render first", 400)
    try:
        qty = max(1, min(20, int(body.get("qty") or 1)))
    except (TypeError, ValueError):
        return _err("qty must be 1-20", 400)
    with db.connect() as c:
        order = db.create_order(
            c, owner=owner, line="greeting_card", mesh_id="", coat="none", hat="none",
            qty=qty, price_cents=799 * qty,
            note=f"creative {pid} r{rev} ({r.get('template_id')})"[:200])
    return jsonify({"ok": True, "order": order, "status": "pending_checkout",
                    "hint": "Reserved the pinned revision. No card charge from this API."})


# ── provider keys (BYO) + voice consent ───────────────────────────────
# Free-first: everything resolves $0 without these. Paid adapters use the
# owner's key when present, server key as fallback — never the reverse.

@app.post("/api/providers/keys")
def provider_key_set():
    """Deprecated alias: stores into the encrypted vault (provider_connections).
    The old plaintext provider_keys table is migrated then dropped."""
    from backend import voice_chat as _vc
    from backend import vault as _vault
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    provider = (body.get("provider") or "").strip()[:40]
    secret = (body.get("secret") or "").strip()
    if not secret:
        return _err("secret is required", 400)
    with db.connect() as c:
        _vc.ensure_consent_tables(c)
        _vault.ensure_tables(c)
        _vault.migrate_plaintext(c)
        try:
            rec = _vault.connect(c, owner, provider, secret,
                                 {"label": str(body.get("label") or "")})
        except ValueError as e:
            return _err(str(e), 400)
    return jsonify({"ok": True, "provider": provider,
                    "credential_id": rec["credential_id"],
                    "hint": "Stored encrypted. Paid runs use your key first; free defaults unchanged."})


@app.get("/api/providers/keys")
def provider_key_list():
    """Deprecated alias: masked vault listing, no secrets ever."""
    from backend import voice_chat as _vc
    from backend import vault as _vault
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        _vc.ensure_consent_tables(c)
        _vault.ensure_tables(c)
        _vault.migrate_plaintext(c)
        rows = [{"provider": p, "label": "", "connected": True}
                for p in sorted(_vault.connected(c, owner))]
    return jsonify({"ok": True, "keys": rows})


@app.post("/api/voice/consent")
def voice_consent():
    """Explicit enrollment consent: whose voice, which audio. Required before
    any provider_voice_id is stored or a clone runs."""
    from backend import voice_chat as _vc
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    subject_id = (body.get("subject_id") or "").strip()
    audio_sha = (body.get("audio_sha") or "").strip()
    if not subject_id or not audio_sha:
        return _err("subject_id and audio_sha are required — consent names whose voice", 400)
    cid = "vcs_" + uuid.uuid4().hex[:12]
    with db.connect() as c:
        _vc.ensure_consent_tables(c)
        c.execute("INSERT INTO voice_consents (id,owner,subject_id,audio_sha,created_at)"
                  " VALUES (?,?,?,?,?)", (cid, owner, subject_id, audio_sha, time.time()))
        c.commit()
    return jsonify({"ok": True, "consent_id": cid,
                    "hint": "Pass consent_id to cloned runs. Revoke by deleting it."})


# ── six high-level agent tools (devplan-2026-10-07) ───────────────────
# One surface for ChatGPT, Muse Connector, Muse Code, Claude, OpenCode,
# Oddy. Each fans out to the figg_* machinery; Muse never names a provider.

@app.get("/api/oddhobb/people")
def oddhobb_people():
    """Whose world is this: subjects + profile facts for an owner."""
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    with db.connect() as c:
        out = []
        for s in _subjects.subjects_for(c, owner):
            out.append({"subject": s, "profile": _subjects.profile_for(c, owner, s["id"])})
    return jsonify({"ok": True, "owner": owner, "people": out})


@app.post("/api/oddhobb/ideas")
def oddhobb_ideas():
    """Person + occasion + request (+ agent_memory context) → ranked ideas."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    with db.connect() as c:
        sub = _subjects.get_subject(c, owner, str(body.get("subject_id") or ""))
        if not sub and body.get("person"):
            sub = _subjects.find_subject_by_name(c, owner, str(body.get("person")))
        prof = _subjects.profile_for(c, owner, sub.get("id", "")) if sub else {}
        counts = _brief_asset_counts(c, owner, sub.get("id", "") if sub else "")
    ctx = body.get("context") or []
    memos = [str(f.get("fact") or "")[:200] for f in ctx
             if isinstance(f, dict) and f.get("fact")]
    brief = _briefs.build(occasion=str(body.get("occasion") or "general"),
                          subject=sub, profile=prof, asset_counts=counts,
                          tone=str(body.get("tone") or "funny"),
                          budget_cents=int(body.get("budget_cents") or 0),
                          request=str(body.get("request") or ""))
    if memos:
        brief["agent_memory"] = [{"fact": m, "source": "agent_memory"} for m in memos[:8]]
    reg = _ctmpl.load_all()
    matches = _matcher.match(brief, reg, limit=3)
    ideas = [{"idea_id": f"idea_{m['id']}", "template_id": m["id"],
              "version": m["version"], "score": m["score"],
              "why": "; ".join(m["reasons"])} for m in matches]
    return jsonify({"ok": True, "brief": brief, "ideas": ideas,
                    "hint": "oddhobb_create with an idea_id to make it real."})


@app.post("/api/oddhobb/create")
def oddhobb_create():
    """Idea → brief → match → frozen revision. Fifteen ops, one call."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    idea = str(body.get("idea_id") or "")
    tid = idea[5:] if idea.startswith("idea_") else str(body.get("template_id") or "")
    reg = _ctmpl.load_all()
    t = reg.get(tid)
    if t is None:
        return _err("unknown idea — valid: " + ", ".join(sorted(reg)), 400)
    overrides = body.get("overrides") or {}
    fields = dict(overrides)
    with db.connect() as c:
        sub = _subjects.get_subject(c, owner, str(body.get("subject_id") or ""))
        if not sub and body.get("person"):
            sub = _subjects.find_subject_by_name(c, owner, str(body.get("person")))
        sid = sub.get("id", "") if sub else ""
        if "star" in (t.get("slots") or {}) and "star" not in fields and sid:
            fields["star"] = sid
        proj = _cproj.find_project(c, owner, sid, tid)
        pid = proj["id"] if proj else _cproj.create_project(c, owner, sid, tid)["id"]
        filled, gaps = _cjobs.fill_slots(t, fields)
        gaps += _art.qc_card_copy(filled, t)
        if gaps:
            return jsonify({"ok": False, "gaps": gaps,
                            "hint": "Pass overrides for the missing/short fields."}), 400
        try:
            rev = _cproj.save_revision(c, pid, tid, int(t.get("version", 1)),
                                       body.get("brief") or {}, {
                                           "scene_version": "oddhobb.scene.v2",
                                           "template": {"id": tid, "version": t.get("version", 1)},
                                           "subjects": ([{"slot": "star", "subject_id": sid,
                                                          "asset_ids": []}] if sid else []),
                                           "copy": filled, "render_intent": {}},
                                       expected_revision=body.get("expected_revision"))
        except (KeyError, ValueError) as e:
            return _err(str(e)[:200], 400)
    return jsonify({"ok": True, "creative_id": pid, "revision": rev["revision"],
                    "template_id": tid,
                    "hint": "oddhobb_render to realize it, oddhobb_buy to reserve it."})


@app.post("/api/oddhobb/render")
def oddhobb_render():
    """Realize a revision: preview now (free); paid outputs route through
    the vault (BYO key) or come back staged with the reason."""
    from backend.creative.providers import router as _router
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    policy = str(body.get("policy") or "free")
    if policy not in ("free", "use-mine", "best", "specific"):
        return _err("unknown policy — free, use-mine, best, specific", 400)
    outputs = body.get("outputs") or ["preview"]
    done, staged = {}, []
    if "preview" in outputs:
        data, _ = _render_revision(owner, str(body.get("creative_id") or ""),
                                   int(body.get("revision") or 1))
        if data.get("ok"):
            done["preview"] = data["artifact"]
        else:
            staged.append({"output": "preview", "status": "staged",
                           "reason": "; ".join(data.get("gaps") or [data.get("error", "render refused")])[:300]})
    paid_wants = {"photoreal": "identity_image", "video": "video_scene",
                  "lipsync": "lip_sync"}
    for o in outputs:
        if o == "preview" or o not in paid_wants:
            continue
        if policy == "free":
            staged.append({"output": o, "status": "staged",
                           "reason": "free policy — set policy use-mine/best with a connected provider"})
            continue
        try:
            got = _router.run_for_owner(
                paid_wants[o], owner,
                {"prompt": f"premium {o} pass"},
                policy=policy,
                route=str((body.get("routes") or {}).get(o) or ""))
            done[o] = got
        except Exception as e:  # noqa: BLE001 — staged, never 500
            staged.append({"output": o, "status": "staged", "reason": str(e)[:200]})
    return jsonify({"ok": True, "done": done, "staged": staged})


@app.get("/api/oddhobb/status/<creative_id>")
def oddhobb_status(creative_id):
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    with db.connect() as c:
        proj = c.execute("SELECT * FROM creative_projects WHERE id=? AND owner=?",
                         (creative_id, owner)).fetchone()
        if proj is None:
            return _err("no such creative", 404)
        p = dict(proj)
        arts = [dict(r) for r in c.execute(
            "SELECT id,revision,renderer,output_kind,qc_status,created_at"
            " FROM render_artifacts WHERE project_id=? ORDER BY revision DESC", (creative_id,))]
    return jsonify({"ok": True, "creative_id": creative_id,
                    "latest_revision": p["latest_revision"], "artifacts": arts})


@app.post("/api/oddhobb/buy")
def oddhobb_buy():
    """Reserve a QC-passed revision. No card charge from this endpoint."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    _creative_tables()
    with db.connect() as c:
        r = _cproj.get_revision(c, str(body.get("creative_id") or ""),
                                int(body.get("revision") or 0))
        if not r:
            return _err("no such revision", 404)
        ok_art = c.execute("SELECT 1 FROM render_artifacts WHERE project_id=? AND revision=? AND qc_status='passed'"
                           " AND output_kind='print_master'",
                           (r["project_id"], r["revision"])).fetchone()
    if not ok_art:
        return _err("render first — only QC-passed print revisions are buyable", 400)
    with db.connect() as c:
        order = db.create_order(
            c, owner=owner, line=str(body.get("product") or "greeting_card"),
            mesh_id="", coat="none", hat="none", qty=max(1, min(20, int(body.get("qty") or 1))),
            price_cents=799, note=f"oddhobb {r['project_id']} r{r['revision']}"[:200])
    return jsonify({"ok": True, "order": order, "status": "pending_checkout"})


# ── provider vault (BYOC) + capture sessions ──────────────────────────

@app.post("/api/providers/connect")
def provider_connect():
    """Connect a BYO creative provider: secret goes to the vault encrypted,
    agents only ever see {fal: true}. Body: {owner, provider, secret}."""
    from backend import vault as _vault
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        _vault.ensure_tables(c)
        try:
            rec = _vault.connect(c, owner, str(body.get("provider") or ""),
                                 str(body.get("secret") or ""),
                                 {"label": str(body.get("label") or "")})
        except ValueError as e:
            return _err(str(e), 400)
    return jsonify({"ok": True, "connection": rec})


@app.get("/api/providers")
def provider_status():
    """Agent-safe view: which providers are on, free always true. No secrets."""
    from backend import vault as _vault
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        _vault.ensure_tables(c)
        view = _vault.agent_view(c, owner)
    return jsonify({"ok": True, "providers": view,
                    "policies": ["free", "use-mine", "best", "specific"]})


@app.post("/api/providers/disconnect")
def provider_disconnect():
    from backend import vault as _vault
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        _vault.ensure_tables(c)
        ok = _vault.disconnect(c, owner, str(body.get("provider") or ""))
    return jsonify({"ok": True, "revoked": ok})


@app.get("/api/capsule/<subject_id>")
def capsule_get(subject_id):
    """Person Capsule: identity/voice/behaviour/spatial/knowledge/provenance
    assembled from existing stores. Input to every template."""
    from backend import capsule as _cap
    owner = _own(request.args.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        cap = _cap.build(c, owner, subject_id)
    if not cap:
        return _err("no such subject", 404)
    return jsonify({"ok": True, "capsule": cap})


@app.post("/api/capture/start")
def capture_start():
    """Begin a guided person capture (Qwen-Omni-directed onboarding later)."""
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS capture_sessions (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, subject_id TEXT NOT NULL DEFAULT '',
          marks TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'open',
          created_at REAL NOT NULL)""")
        cid = "cap_" + uuid.uuid4().hex[:12]
        c.execute("INSERT INTO capture_sessions VALUES (?,?,?,?,?,?)",
                  (cid, owner, str(body.get("subject_id") or ""), "[]", "open", time.time()))
        c.commit()
    return jsonify({"ok": True, "capture_id": cid,
                    "script": ["turn head slowly", "step back, full body",
                               "say something natural", "your most Dad-like shrug"]})


@app.post("/api/capture/asset")
def capture_asset():
    """Attach the raw capture video: multipart (video) + capture_id. The file
    is the first-class identity reference — stills/keyframes derive from it,
    it is never thrown away. Also registers a video asset row."""
    from backend import subjects as _subs
    capture_id = (request.form.get("capture_id") or request.args.get("capture_id") or "")
    with db.connect() as c:
        row = c.execute("SELECT * FROM capture_sessions WHERE id=?", (capture_id,)).fetchone()
    if row is None:
        return _err("no such capture", 404)
    d = dict(row)
    denied = _owner_denied(d.get("owner") or "anon")
    if denied is not None:
        return denied
    f = request.files.get("video") or request.files.get("file")
    if f is None:
        return _err("attach the capture video in the 'video' field", 400)
    blob = f.read(256 * 1024 * 1024 + 1)
    if len(blob) > 256 * 1024 * 1024:
        return _err("capture too large (256MB max)", 400)
    import hashlib
    sha = hashlib.sha256(blob).hexdigest()
    key = f"owners/{d['owner']}/captures/{capture_id}.mp4"
    tmp = config.LOCAL_TMP / f"cap_{capture_id}.mp4"
    tmp.write_bytes(blob)
    try:
        storage.put(tmp, key)
    finally:
        tmp.unlink(missing_ok=True)
    with db.connect() as c:
        asset = _subs.register_asset(c, d["owner"], "video", sha, key,
                                     metadata={"capture_id": capture_id,
                                               "bytes": len(blob)},
                                     provenance="capture")
        c.execute("UPDATE capture_sessions SET status=? WHERE id=?",
                  ("has_video", capture_id))
        try:
            c.execute("ALTER TABLE capture_sessions ADD COLUMN asset_id TEXT NOT NULL DEFAULT ''")
        except sqlite3.Error:
            pass
        try:
            c.execute("UPDATE capture_sessions SET asset_id=? WHERE id=?", (asset["id"], capture_id))
        except sqlite3.Error:
            pass
        c.commit()
    return jsonify({"ok": True, "asset": asset,
                    "hint": "keyframes/audio/motion derive from this file later"})


@app.post("/api/capture/mark")
def capture_mark():
    """Timestamp a moment: {capture_id, kind, note, t_media?} — oddhobb.capture_mark.
    t_media is seconds into the capture media; when omitted it derives from
    capture start (wall clock), so marks stay media-relative, not wall-clock."""
    body = request.get_json(silent=True) or {}
    with db.connect() as c:
        row = c.execute("SELECT * FROM capture_sessions WHERE id=?",
                        (str(body.get("capture_id") or ""),)).fetchone()
        if row is None:
            return _err("no such capture", 404)
        d = dict(row)
        marks = json.loads(d.get("marks") or "[]")
        t_media = body.get("t_media")
        if t_media is None:
            try:
                t_media = round(time.time() - float(d.get("created_at") or time.time()), 2)
            except (TypeError, ValueError):
                t_media = 0.0
        marks.append({"t_media": float(t_media),
                      "kind": str(body.get("kind") or "note"),
                      "note": str(body.get("note") or "")[:300]})
        c.execute("UPDATE capture_sessions SET marks=? WHERE id=?",
                  (json.dumps(marks), d["id"]))
        c.commit()
    return jsonify({"ok": True, "marks": len(marks)})


@app.post("/api/capture/finish")
def capture_finish():
    """Close the capture → mannerism manifest skeleton on the subject profile."""
    from backend import subjects as _subs
    body = request.get_json(silent=True) or {}
    owner = _own(body.get("owner") or "")
    denied = _owner_denied(owner)
    if denied is not None:
        return denied
    with db.connect() as c:
        row = c.execute("SELECT * FROM capture_sessions WHERE id=? AND owner=?",
                        (str(body.get("capture_id") or ""), owner)).fetchone()
        if row is None:
            return _err("no such capture", 404)
        d = dict(row)
        marks = json.loads(d.get("marks") or "[]")
        c.execute("UPDATE capture_sessions SET status='done' WHERE id=?", (d["id"],))
        if d.get("subject_id"):
            prof = _subs.profile_for(c, owner, d["subject_id"]).get("profile", {})
            have = set(prof.get("mannerisms", []))
            for m in marks:
                if m.get("note"):
                    have.add(m["note"][:120])
            _subs.set_profile(c, owner, d["subject_id"],
                              profile={**prof, "mannerisms": sorted(have)[:20]})
        c.commit()
    return jsonify({"ok": True, "marks": len(marks),
                    "hint": "raw capture stays a first-class reference — never thrown away"})



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
    from backend import logscrub as _logscrub
    _logscrub.install("werkzeug")
    threading.Thread(target=_worker, daemon=True, name="figg-worker").start()
    print(f"figgsite backend  http://127.0.0.1:{config.API_TOKEN and 8798}")
    print("  token   : set (never printed — see .token, 0600)")
    print(f"  meshy   : {'STUB (set MESHY_API_KEY for live)' if meshy.is_stub() else 'LIVE'}")
    print(f"  r2      : {config.R2_BUCKET} via rclone remote")
    print(f"  products: {', '.join(config.PRODUCTS)}")
    app.run(host="127.0.0.1", port=int(__import__('os').environ.get('BACKEND_PORT', 8798)),
            threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
