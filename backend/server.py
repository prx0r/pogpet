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
import sqlite3
import sys
import threading
import time
import urllib.parse
import uuid
from datetime import date, timezone, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


# ── photos ────────────────────────────────────────────────────────────

@app.post("/api/photos")
def upload_photo():
    owner = (request.form.get("owner") or request.args.get("owner") or "anon").strip()[:80]
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
                f"That's {config.DAILY_UPLOAD_LIMIT} uploads today — the sculpt "
                "credits reset tomorrow. Try a different photo?", 429)

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
    try:
        res = pipeline.start_mesh(photo_id)
    except pipeline.PipelineError as e:
        return _err(str(e), e.code)
    return jsonify({"ok": True, **res})


@app.get("/api/meshes")
def list_meshes():
    """Latest meshes for an owner — what the shop/studio tabs bind to."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
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
    with db.connect() as c:
        prof = db.get_profile(c, owner)
        pogs = db.pogs_for(c, owner)
        active = prof.get("active_mesh_id") or ""
        if not active:
            ok = next((p for p in pogs if p["status"] == "succeeded"), None)
            if ok:
                active = ok["id"]
                db.set_active(c, owner, active)
        roster = [{
            "mesh_id": p["id"], "status": p["status"], "stub": bool(p["stub"]),
            "print_ready": bool(p["print_ready"]), "photo_key": p.get("photo_key", ""),
            "active": p["id"] == active, "created_at": p["created_at"],
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


@app.get("/api/products")
def products():
    """Prodigi catalogue rendered against the owner's ACTIVE pog.

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
            ctag = f"_{concept["id"]}" if concept else ""
            stg = f"_{abs(hash(subject)) % 99999}" if subject else ""
            fname = f"{pid}_{short}{ctag}{stg}.png"
            key = f"owners/{storage._slug(owner)}/products/{fname}"
            try:
                if fname not in have:
                    if src_path is None:
                        failed[pid] = "no source image"
                        continue
                    from backend import mockup   # absolute: this module is __main__
                    tmp = config.LOCAL_TMP / f"mk_{pid}_{owner}.png"
                    mockup.render(spec["shape"], src_path, spec["label"], tmp,
                                  concept=concept, subject=subject)
                    storage.put(tmp, key)
                    rendered += 1
                    tmp.unlink(missing_ok=True)
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
        except Exception:
            pass
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
        products = db.products_for(c, mid)
    if mesh is None:
        return _err("no such mesh", 404)
    return jsonify({"ok": True, "mesh_id": mid, "products": products,
                    "source_glb": mesh["glb_key"]})


@app.get("/api/credits")
def credits():
    """Free-tier balance for an owner: what's left today."""
    owner = (request.args.get("owner") or "anon").strip()[:80]
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
    with db.connect() as c:
        u = db.get_user_by_handle(c, handle)
        if not u or not u["password_hash"] or not db.verify_password(password, u["password_hash"]):
            return _err("wrong handle or password", 401)
        c.execute("UPDATE users SET last_login=? WHERE id=?", (db.now(), u["id"]))
        prof = db.get_profile(c, u["handle"])
        pogs = db.pogs_for(c, u["handle"])
        credits = db.credit_status(c, u["handle"],
                                   datetime.now(timezone.utc).date().isoformat())
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
        ok, used = db.spend_credit(c, owner, day, "video", config.FREE_DAILY["video"])
        if not ok:
            return _err(
                f"That's {config.FREE_DAILY['video']} free videos today — "
                "back tomorrow for more.", 429)
        photo = db.get_photo(c, mesh["photo_id"])
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
    with db.connect() as c:
        rows = c.execute(
            "SELECT id,scene,talent,voice,pet_name,watermarked,duration,bytes,created_at"
            " FROM videos WHERE owner=? ORDER BY created_at DESC LIMIT 50",
            (owner,)).fetchall()
    return jsonify({"ok": True, "owner": owner,
                    "videos": [db.dump(r) for r in rows]})


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


# ── worker ────────────────────────────────────────────────────────────

def _worker(interval: float = 0.4) -> None:
    while not _worker_stop.wait(interval):
        try:
            pipeline.run_all(max_jobs=8)
        except Exception:
            pass


def main() -> None:
    db.init()
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
