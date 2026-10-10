"""cardgen engine: the canonical card path, wired to the backend.

    recommend(owner, subject_id, occasion)  -> which templates the photos can make, and why not
    start(owner, subject_id, template_id)    -> job id (runs in a worker thread)
    job(owner, job_id)                        -> status / step / design_id / revision / qa

One card, end to end, using what the backend already has:

  photos + photo_faces + photo_subjects + face_embeddings   (uploads, YuNet, SFace, tagging)
  + photo_labels (L5 expression/framing, vision call)        -> INDEX
  template.wants (cardgen/wants.py)                          -> CAST: real photo ids per role
  OpenRouter copy (template limits)                          -> WRITE
  fal identity_scene with the cast photos as references      -> GENERATE (front art, lettering in art)
  OCR + SFace likeness + face count + vision critic          -> QA, edit_fix up to 2x
  fal spot vignette -> 10:7 inside art (left page)           -> SPOT
  fal upscale when the art is under print width              -> UPSCALE
  cards.attach_art(front, inside, copy)                      -> FREEZE: birthday_fullbleed revision
     -> existing preview/spread/export render jobs, £ price, Shopify checkout, Prodigi.

Spend is fail-closed (no FAL_KEY, no call), and every paid call is logged to the
fal ledger. Nothing here draws a card: the fullbleed renderer in card_scenes owns
the inside message type and the back.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import threading
import time
import traceback
import urllib.request
import uuid
from pathlib import Path

from . import wants as W

TEMPLATES = Path(__file__).parent / "templates"
PAPER = (255, 253, 247)          # card_scenes fullbleed paper #fffdf7
PRINT_W = 1500                   # front art short edge for ~300 dpi at 5x7 trim

ROUTES = {   # capability -> [(fal endpoint, payload builder, est $)]
    "identity_scene": [
        ("fal-ai/nano-banana/edit", lambda p, r: {"prompt": p, "image_urls": r, "num_images": 1, "aspect_ratio": "5:7"}, 0.04),
        ("fal-ai/bytedance/seedream/v4/edit", lambda p, r: {"prompt": p, "image_urls": r, "image_size": {"width": 1500, "height": 2100}}, 0.03),
        ("fal-ai/flux-pro/kontext/max/multi", lambda p, r: {"prompt": p, "image_urls": r, "aspect_ratio": "5:7"}, 0.08),
    ],
    "edit_fix": [
        ("fal-ai/nano-banana/edit", lambda p, r: {"prompt": p, "image_urls": r, "num_images": 1}, 0.04),
    ],
    "spot": [
        ("fal-ai/nano-banana/edit", lambda p, r: {"prompt": p, "image_urls": r, "num_images": 1, "aspect_ratio": "1:1"}, 0.04),
    ],
    "upscale": [
        ("fal-ai/clarity-upscaler", lambda p, r: {"image_url": r[0], "upscale_factor": 2}, 0.03),
        ("fal-ai/esrgan", lambda p, r: {"image_url": r[0], "scale": 2}, 0.01),
    ],
}


class EngineError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


# ── templates ────────────────────────────────────────────────────────────

def templates() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(TEMPLATES.glob("*.json"))]


def template(tid: str) -> dict:
    for t in templates():
        if t["id"] == tid:
            return t
    raise EngineError(f"unknown template {tid}", 404)


# ── index: the backend's photo knowledge for one owner ───────────────────

def index(owner: str, subject_id: str, *, label=True) -> dict:
    """Photos with faces, who each face is, and its L5 labels.

    {"photos": [{id, r2_key, w, h, faces:[{id, box(px), h_px, score, hero, labels}]}],
     "hero_vecs": [[...128]], "hero_faces": n}
    """
    from backend import db, photo_labels as PL
    try:
        from backend import faces as _FC
        _FC.ensure_schema()
    except Exception:
        pass
    PL.ensure_schema()
    out = []
    with db.connect() as c:
        hero_faces = {r["face_id"]: r["photo_id"] for r in c.execute(
            "SELECT photo_id, face_id FROM photo_subjects WHERE subject_id=? AND confirmed=1",
            (subject_id,)) if r["face_id"]}
        hero_photos = {r["photo_id"] for r in c.execute(
            "SELECT photo_id FROM photo_subjects WHERE subject_id=? AND confirmed=1", (subject_id,))}
        rows = [dict(r) for r in c.execute("SELECT * FROM photos WHERE owner=?", (owner,))]
        vecs = []
        for fid in hero_faces:
            r = c.execute("SELECT vec, dim FROM face_embeddings WHERE face_id=?", (fid,)).fetchone()
            if r:
                try:
                    vecs.append(list(struct.unpack(f"{r['dim']}f", r["vec"])))
                except struct.error:
                    pass
        for p in rows:
            faces = [dict(f) for f in c.execute("SELECT * FROM photo_faces WHERE photo_id=?", (p["id"],))]
            if not faces:
                continue
            out.append({"id": p["id"], "r2_key": p["r2_key"], "w": p.get("width") or 0,
                        "h": p.get("height") or 0, "created_at": p.get("created_at") or 0,
                        "faces": faces, "tagged": p["id"] in hero_photos})
    if label and out:
        try:
            PL.ensure(owner, [p["id"] for p in out])
        except Exception:
            pass
    labs = PL.for_photos([p["id"] for p in out]) if out else {}
    for p in out:
        fs = []
        for f in p["faces"]:
            b = PL._box(f["box"], p["w"], p["h"]) or (0, 0, 0, 0)
            fs.append({"id": f["id"], "box": b, "h_px": b[3], "score": float(f.get("score") or 0),
                       "hero": f["id"] in hero_faces,
                       "labels": {k: (labs.get(f["id"]) or {}).get(k, "unknown")
                                  for k in ("expression", "framing", "look")}})
        # a tagged photo with a single face and no face-level tag: that face is the hero
        if p["tagged"] and len(fs) == 1:
            fs[0]["hero"] = True
        p["faces"] = fs
    return {"photos": out, "hero_vecs": vecs, "hero_faces": len(hero_faces)}


# ── cast: template wants -> photo ids ────────────────────────────────────

def _fits(p: dict, role: dict) -> tuple[bool, dict | None, str]:
    from backend import photo_labels as PL
    r = W.norm(role)
    n = len(p["faces"])
    if not (r["people"][0] <= n <= r["people"][1]):
        return False, None, "people"
    big = max(p["faces"], key=lambda f: f["h_px"])
    frac = (big["box"][2] * big["box"][3]) / max(p["w"] * p["h"], 1)
    if not (W.shot_of(n, frac) & set(r["shot"])):
        return False, None, "shot"
    hero = next((f for f in p["faces"] if f["hero"]), None)
    if r["identity"] in ("hero", "with_hero") and hero is None:
        return False, None, "identity"
    focus = hero or big
    if focus["h_px"] < r["min_face_px"]:
        return False, None, "face_px"
    if not PL.satisfies(focus["labels"]["expression"], r["expression"]):
        return False, None, "expression"
    if r["framing"] and focus["labels"]["framing"] not in r["framing"]:
        return False, None, "framing"
    return True, focus, ""


def cast(t: dict, idx: dict) -> dict:
    """{"ok", "roles": {role: photo_id}, "refs": [photo ids], "shortfall": [plain words]}"""
    roles, refs, short, used = {}, [], [], set()
    for name, role in t["wants"].items():
        r = W.norm(role)
        if "pet" in r["shot"]:
            short.append("pet photos aren't detected yet")
            continue
        ranked = []
        for p in idx["photos"]:
            ok, focus, _why = _fits(p, r)
            if ok and p["id"] not in used:
                ranked.append((focus["h_px"] * (0.5 + focus["score"]), p["created_at"], p["id"]))
        ranked.sort(reverse=True)
        if not ranked:
            if not r["optional"]:
                short.append("needs " + W.describe(r))
            continue
        roles[name] = ranked[0][2]
        used.add(ranked[0][2])
        refs.append(ranked[0][2])
    # likeness: add the clearest tagged solos of the hero as extra references
    want_refs = max([W.norm(r)["refs"] for r in t["wants"].values()] + [1])
    solos = sorted(((f["h_px"], p["id"]) for p in idx["photos"] if len(p["faces"]) == 1
                    for f in p["faces"] if f["hero"] and f["labels"]["look"] != "profile"), reverse=True)
    for _h, pid in solos:
        if len(refs) >= min(4, len(roles) + want_refs):
            break
        if pid not in refs:
            refs.append(pid)
    return {"ok": not short and bool(roles), "roles": roles, "refs": refs[:4], "shortfall": short}


def recommend(owner: str, subject_id: str, occasion: str = "birthday",
              profile: dict | None = None, *, label=True) -> dict:
    profile = profile or {}
    idx = index(owner, subject_id, label=label)
    interests = {str(i).lower() for i in profile.get("interests", [])}
    tone = profile.get("tone", "funny")
    ready, blocked = [], []
    for t in templates():
        if occasion not in t["occasions"]:
            continue
        cst = cast(t, idx)
        fit = 1.0 + 2.0 * len(interests & set(t["interests"])) + (0.5 if tone in t["tones"] else 0)
        row = {"template_id": t["id"], "fit": fit, "photos": cst["roles"], "refs": cst["refs"]}
        (ready if cst["ok"] else blocked).append({**row, "shortfall": cst["shortfall"]})
    ready.sort(key=lambda r: -r["fit"])
    tip = None
    if not idx["hero_faces"] and not any(f["hero"] for p in idx["photos"] for f in p["faces"]):
        tip = "No photos are tagged as this person yet. Confirm their face once and every template can cast them."
    return {"ok": True, "subject_id": subject_id, "occasion": occasion, "ready": ready,
            "blocked": blocked, "photos_indexed": len(idx["photos"]), "tip": tip}


# ── copy ─────────────────────────────────────────────────────────────────

def _fill(s: str, ctx: dict) -> str:
    for k, v in ctx.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def write_copy(t: dict, profile: dict, overrides: dict | None = None) -> dict:
    """LLM copy within the template limits; falls back to the template's own anchors."""
    lim = {k: v["max"] for k, v in t["copy"].items()}
    ctx = {"recipient": profile.get("recipient") or profile.get("relationship", "").title() or profile.get("name", ""),
           "SURNAME": (profile.get("surname") or (profile.get("name", "").split() or [""])[-1]).upper(),
           "pet_name": profile.get("pet_name", "")}
    copy = {k: _fill(v["examples"][0], ctx) for k, v in t["copy"].items()}
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if key:
        ask = {"person": {k: profile.get(k) for k in ("name", "relationship", "interests", "memories", "nicknames") if profile.get(k)},
               "occasion": profile.get("occasion", "birthday"), "tone": profile.get("tone", "funny"),
               "template": t["id"], "scene": t["scene"],
               "style_anchors": {k: v["examples"] for k, v in t["copy"].items()},
               "limits_chars": lim}
        body = json.dumps({"model": os.environ.get("OPENROUTER_COPY_MODEL", "openai/gpt-4o-mini"),
                           "temperature": 0.9, "max_tokens": 300, "response_format": {"type": "json_object"},
                           "messages": [{"role": "system", "content":
                                         "You write greeting-card copy for a card whose front art is described. "
                                         "One sharp joke that fits THIS person; affectionate, never cruel, never generic. "
                                         f"Return JSON with exactly the keys {list(lim)} and respect the char limits. "
                                         "'title' and any short keys are lettered INTO the art: uppercase-friendly, no emoji."},
                                        {"role": "user", "content": json.dumps(ask)}]}).encode()
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, method="POST",
                                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                                  "HTTP-Referer": "https://oddhobb.com", "X-Title": "OddHobb cardgen"})
            with urllib.request.urlopen(req, timeout=60) as r:
                txt = json.loads(r.read().decode())["choices"][0]["message"]["content"]
            got = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
            for k, m in lim.items():
                v = str(got.get(k) or "").strip()
                if v and len(v) <= m:
                    copy[k] = v
        except Exception:
            pass
    for k, v in (overrides or {}).items():
        if k in lim and isinstance(v, str) and v.strip():
            copy[k] = v.strip()[: lim[k]]
    return copy


def lettering(t: dict, copy: dict) -> list[str]:
    return [copy[k] for k in t["qa"]["text_only"] if copy.get(k)]


def scene_names(t: dict, profile: dict) -> dict:
    prop = "a golf club" if "golf" in {str(i).lower() for i in profile.get("interests", [])} else "a microphone stand"
    return {"hero": "the person from the reference photos", "partner": "the other person in the couple photo",
            "pet": "the pet from the reference photo", "place": profile.get("place", "the city skyline at dusk"),
            "hero_prop": profile.get("prop", prop), **t.get("names", {})}


def front_prompt(t: dict, copy: dict, profile: dict) -> str:
    names = scene_names(t, profile)
    letters = "; ".join(f'"{x}"' for x in lettering(t, copy))
    return (f"Portrait 5:7 greeting card front, full bleed. {_fill(t['scene'], names)} "
            f"Style: {t['style']}. Every face must keep the exact likeness of the reference photos "
            f"(face shape, eyes, smile, hair, age). The ONLY lettering on the image, designed into the art: "
            f"{letters}. Leave clear space for it near the top. {t['negative']}.")


# ── providers (fal through the backend adapter + spend ledger) ───────────

def _fal_run(capability: str, prompt: str, refs: list[str], owner: str) -> dict:
    key = (os.environ.get("FAL_KEY") or "").strip()
    if not key:
        raise EngineError("FAL_KEY not set: generation is fail-closed", 503)
    from backend.creative.providers import fal as F
    errs = []
    for endpoint, build, cost in ROUTES[capability]:
        try:
            rid = F._submit(endpoint, build(prompt, refs), key)
            res = F._result(endpoint, rid, key)
            d = res.get("response") or res
            imgs = d.get("images") or ([d["image"]] if d.get("image") else [])
            if not imgs:
                raise RuntimeError(f"no image: {json.dumps(d)[:160]}")
            F.log_spend(owner=owner, adapter=f"cardgen.{capability}", endpoint=endpoint,
                        est_cost_usd=cost, request_id=rid)
            return {"url": imgs[0]["url"], "endpoint": endpoint, "request_id": rid}
        except EngineError:
            raise
        except Exception as e:  # noqa: BLE001 - next route
            errs.append(f"{endpoint}: {str(e)[:120]}")
    raise EngineError("all routes failed: " + "; ".join(errs), 502)


def _ref_url(owner: str, photo: dict) -> str:
    """Short-lived URL fal can fetch for one owned photo (R2 presign, image content type)."""
    from backend import cards as C, r2presign as R, config
    local = C.local_asset(photo["r2_key"])
    key = f"tmp/cardgen/{uuid.uuid4().hex}/{Path(local).name}"
    R._client().upload_file(str(local), config.R2_BUCKET, key,
                            ExtraArgs={"ContentType": photo.get("mime") or "image/jpeg"})
    return R.presigned_url(key, 3600)


def _download(url: str):
    from PIL import Image
    with urllib.request.urlopen(url, timeout=120) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


# ── QA ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> list[str]:
    import re
    return re.sub(r"[^A-Z0-9 ]", " ", s.upper()).split()


def ocr_gate(img, expected: list[str]) -> tuple[bool, str]:
    """No confident 4+ letter word outside the copy (tesseract; skipped if absent)."""
    if not shutil.which("tesseract"):
        return True, "ocr skipped (no tesseract)"
    buf = io.BytesIO()
    img.save(buf, "PNG")
    out = subprocess.run(["tesseract", "stdin", "stdout", "--psm", "11", "tsv"], input=buf.getvalue(),
                         capture_output=True).stdout.decode(errors="ignore")
    want = set(_norm(" ".join(expected)))
    extra = []
    for line in out.splitlines()[1:]:
        c = line.split("\t")
        if len(c) == 12 and c[11].strip() and float(c[10] or 0) >= 85:
            extra += [w for w in _norm(c[11]) if len(w) >= 4 and w.isalpha() and w not in want]
    return not extra, f"extra={extra}"


def face_gate(img, hero_vecs: list, expected_faces: int | None, min_sim: float = 0.30) -> tuple[bool, str]:
    """YuNet face count + SFace likeness against the subject's confirmed faces."""
    try:
        import numpy as np
        from backend import faces as FC
        bgr = np.asarray(img)[:, :, ::-1].copy()
        rows = FC.detect_boxes(bgr)
    except Exception as e:  # noqa: BLE001 - cv2 missing in some envs
        return True, f"face gate skipped ({str(e)[:60]})"
    n = len(rows)
    if expected_faces and n and abs(n - expected_faces) > (0 if expected_faces <= 2 else 1):
        return False, f"faces={n} expected={expected_faces}"
    if hero_vecs and rows:
        best = 0.0
        for row in rows:
            v = FC.embed_face(bgr, row)
            if v:
                best = max([best] + [FC.cosine(v, hv) for hv in hero_vecs])
        if best < min_sim:
            return False, f"likeness={best:.2f}<{min_sim}"
        return True, f"faces={n} likeness={best:.2f}"
    return True, f"faces={n}"


def critic_gate(img, expected: list[str]) -> tuple[bool, str]:
    """Vision critic: stray or misspelt lettering, extra limbs, broken faces."""
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return True, "critic skipped (no key)"
    import base64
    small = img.copy()
    small.thumbnail((900, 900))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=85)
    q = ("Check this greeting-card front. The ONLY lettering allowed is exactly: "
         + json.dumps(expected) + ". Reply JSON {\"ok\": bool, \"issues\": [..]}. Fail for: any other text "
         "(taglines, credits, signatures, watermarks), misspelt lettering, malformed faces/hands/eyes, "
         "obvious artefacts.")
    body = json.dumps({"model": os.environ.get("OPENROUTER_VISION_MODEL", "google/gemini-2.5-flash"),
                       "temperature": 0, "max_tokens": 300, "response_format": {"type": "json_object"},
                       "messages": [{"role": "user", "content": [
                           {"type": "text", "text": q},
                           {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}]}]}).encode()
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = json.loads(r.read().decode())["choices"][0]["message"]["content"]
        v = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
        return bool(v.get("ok")), "; ".join(map(str, v.get("issues") or []))[:300]
    except Exception as e:  # noqa: BLE001
        return True, f"critic error ({str(e)[:60]})"


def expected_faces(t: dict, idx: dict, roles: dict) -> int | None:
    if t["qa"].get("faces") == "cast":
        pid = next(iter(roles.values()), None)
        p = next((p for p in idx["photos"] if p["id"] == pid), None)
        return len(p["faces"]) if p else None
    f = t["qa"].get("faces")
    return int(f) if isinstance(f, int) and f > 0 else None


# ── inside art (10:7 spread, spot on the left page, right page blank for live type) ──

def inside_art(spot, width: int = 2100):
    from PIL import Image, ImageDraw, ImageFilter, ImageChops
    h = round(width * 7 / 10)
    img = Image.new("RGB", (width, h), PAPER)
    if spot is None:
        return img
    side = int(h * 0.62)
    sp = spot.convert("RGB")
    s = max(side / sp.width, side / sp.height)
    sp = sp.resize((round(sp.width * s), round(sp.height * s)))
    sp = sp.crop(((sp.width - side) // 2, (sp.height - side) // 2, (sp.width - side) // 2 + side, (sp.height - side) // 2 + side))
    corners = [sp.getpixel((x, y)) for x in (4, side - 5) for y in (4, side - 5)]
    bg = [sorted(c[i] for c in corners)[1] for i in range(3)]
    sp = Image.merge("RGB", [ch.point(lambda v, g=PAPER[i] / max(bg[i], 1): min(255, round(v * g)))
                             for i, ch in enumerate(sp.split())])
    # key out the generated background by distance from paper (no visible oval):
    # alpha ramps 0 -> 255 between 4 and 26 levels of difference, feathered.
    diff = ImageChops.difference(sp, Image.new("RGB", sp.size, PAPER)).convert("L")
    mask = diff.point(lambda v: 0 if v <= 4 else 255 if v >= 26 else int((v - 4) * 255 / 22))
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(2))
    edge = Image.new("L", (side, side), 0)
    ImageDraw.Draw(edge).ellipse((side * .02, side * .02, side * .98, side * .98), fill=255)
    mask = ImageChops.multiply(mask, edge.filter(ImageFilter.GaussianBlur(side * .03)))
    img.paste(sp, ((width // 2 - side) // 2, (h - side) // 2), mask)
    return img


# ── the job ──────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS cardgen_jobs (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, subject_id TEXT NOT NULL, template_id TEXT NOT NULL,
 status TEXT NOT NULL, step TEXT NOT NULL DEFAULT '', design_id TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '', record TEXT NOT NULL DEFAULT '{}',
 created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS cardgen_jobs_owner ON cardgen_jobs(owner, created_at);
"""


def _db():
    from backend import db
    c = db.connect()
    c.executescript(SCHEMA)
    return c


def _set(jid: str, **kw):
    with _db() as c:
        sets = ",".join(f"{k}=?" for k in kw) + ",updated_at=?"
        c.execute(f"UPDATE cardgen_jobs SET {sets} WHERE id=?",
                  [json.dumps(v) if isinstance(v, (dict, list)) else v for v in kw.values()] + [time.time(), jid])
        c.commit()


def job(owner: str, jid: str) -> dict:
    with _db() as c:
        r = c.execute("SELECT * FROM cardgen_jobs WHERE id=? AND owner=?", (jid, owner)).fetchone()
    if not r:
        raise EngineError("job not found", 404)
    d = dict(r)
    d["record"] = json.loads(d["record"] or "{}")
    return d


def start(owner: str, subject_id: str, template_id: str, profile: dict | None = None,
          copy: dict | None = None, *, sync: bool = False) -> str:
    template(template_id)  # 404 early
    if not (os.environ.get("FAL_KEY") or "").strip():
        raise EngineError("FAL_KEY not set: generation is fail-closed", 503)
    if os.environ.get("CARDGEN_LIVE") != "1":
        raise EngineError("cardgen spend is off: set CARDGEN_LIVE=1 to let it generate", 503)
    cap = int(os.environ.get("CARDGEN_DAILY_CAP") or 12)
    t = time.time()
    with _db() as c:
        n = c.execute("SELECT COUNT(*) FROM cardgen_jobs WHERE owner=? AND created_at>?",
                      (owner, t - 86400)).fetchone()[0]
    if n >= cap:
        raise EngineError(f"daily card generation cap reached ({cap}/24h)", 429)
    jid = "cgj_" + uuid.uuid4().hex[:20]
    with _db() as c:
        c.execute("INSERT INTO cardgen_jobs (id,owner,subject_id,template_id,status,created_at,updated_at)"
                  " VALUES (?,?,?,?,?,?,?)", (jid, owner, subject_id, template_id, "queued", t, t))
        c.commit()
    args = (jid, owner, subject_id, template_id, profile or {}, copy or {})
    if sync:
        run(*args)
    else:
        threading.Thread(target=run, args=args, daemon=True, name=jid).start()
    return jid


def run(jid, owner, subject_id, template_id, profile, overrides, *, gen=None, attach=None):
    """The pipeline. gen/attach are injectable for tests (gen(capability, prompt, refs) -> PIL image)."""
    rec = {"template": template_id, "providers": [], "qa": []}
    try:
        t = template(template_id)
        _set(jid, status="running", step="index")
        idx = index(owner, subject_id)
        cst = cast(t, idx)
        if not cst["ok"]:
            raise EngineError("can't cast: " + "; ".join(cst["shortfall"]), 422)
        rec["photos"] = cst
        _set(jid, step="write")
        copy = write_copy(t, profile, overrides)
        rec["copy"] = copy
        letters = lettering(t, copy)
        prompt = front_prompt(t, copy, profile)
        rec["prompt"] = prompt

        if gen is None:
            by_id = {p["id"]: p for p in idx["photos"]}
            from backend import db
            with db.connect() as c:
                mime = {r["id"]: r["mime"] for r in c.execute(
                    "SELECT id, mime FROM photos WHERE owner=?", (owner,))}
            ref_urls = [_ref_url(owner, {**by_id[pid], "mime": mime.get(pid)}) for pid in cst["refs"]]

            def gen(cap, p, refs):
                out = _fal_run(cap, p, refs, owner)
                rec["providers"].append({k: out[k] for k in ("endpoint", "request_id")} | {"capability": cap})
                img = _download(out["url"])
                img.info["url"] = out["url"]
                return img
        else:
            ref_urls = list(cst["refs"])

        _set(jid, step="generate")
        art = gen("identity_scene", prompt, ref_urls)
        nfaces = expected_faces(t, idx, cst["roles"])
        for attempt in range(3):
            _set(jid, step=f"qa{attempt}")
            gates = {"ocr": ocr_gate(art, letters), "faces": face_gate(art, idx["hero_vecs"], nfaces),
                     "critic": critic_gate(art, letters)}
            rec["qa"].append({k: list(v) for k, v in gates.items()})
            bad = [k for k, (ok, _d) in gates.items() if not ok]
            if not bad:
                break
            if attempt == 2:
                raise EngineError("QA failed after 2 fixes: " + json.dumps(rec["qa"][-1]), 422)
            if "faces" in bad and gates["faces"][1].startswith("likeness"):
                fix = ("Edit this exact image: make the main person's face match the reference photos exactly "
                       "(face shape, eyes, smile, hair, age). Keep style, pose, lettering and everything else identical.")
                art = gen("edit_fix", fix, [art.info.get("url", "")] + ref_urls[:2])
            elif bad == ["faces"]:
                art = gen("identity_scene", prompt, ref_urls)   # wrong cast count: regenerate
            else:
                keep = " and ".join(f'"{x}"' for x in letters)
                fix = (f"Edit this exact image: remove every piece of lettering except {keep}, and fix: "
                       f"{gates['critic'][1] or 'stray text'}. Fill removed areas with the surrounding background. "
                       f"Keep everything else identical.")
                art = gen("edit_fix", fix, [art.info.get("url", "")])

        _set(jid, step="spot")
        spot_prompt = (f"Small spot illustration in the exact style of the reference image: "
                       f"{_fill(t['spot'], scene_names(t, profile))}. Centred on a plain flat off-white "
                       f"background #FFFDF7 with lots of empty space. No people, no text, no border.")
        try:
            spot = gen("spot", spot_prompt, [art.info.get("url", "")])
        except EngineError:
            raise
        except Exception:
            spot = None
        if art.width < PRINT_W:
            _set(jid, step="upscale")
            try:
                big = gen("upscale", "", [art.info.get("url", "")])
                if big.width > art.width:
                    art = big
            except EngineError:
                raise
            except Exception:
                pass
        _set(jid, step="freeze")
        inside = inside_art(spot)
        cardcopy = {"headline": copy.get("title", "")[:40],
                    "recipient": profile.get("recipient", ""),
                    "sender": profile.get("sender", ""),
                    "inside_message": copy.get("inside", "")}
        if attach is None:
            from backend import cards as C
            attach = lambda blobs, cc, pr: C.attach_art(owner, "", blobs, copy=cc, headline_baked=True,
                                                        art_source=f"cardgen:{template_id}", prompt=pr)
        design, warnings, _jobs = attach({"front": art, "inside": inside}, cardcopy, prompt)
        buf = io.BytesIO()
        art.save(buf, "PNG")
        rec["art_sha256"] = hashlib.sha256(buf.getvalue()).hexdigest()
        rec["warnings"] = warnings
        _set(jid, status="ready", step="done", design_id=design["id"], revision=design["revision"], record=rec)
    except EngineError as e:
        _set(jid, status="failed", error=str(e)[:500], record=rec)
    except Exception as e:  # noqa: BLE001
        _set(jid, status="failed", error=f"{type(e).__name__}: {str(e)[:300]}",
             record={**rec, "trace": traceback.format_exc()[-1500:]})
