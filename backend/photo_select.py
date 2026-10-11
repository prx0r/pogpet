"""Photo selection: pick the N best photos of one person and crop each to a cell.

Reusable (cards now; photobooks and calendars later). Deterministic, CPU only,
no generation calls. Built from parts we already have:

  - YuNet detection + SFace identity (backend/faces.py)
  - confirmed face tags + hero vectors (photo_subjects / face_embeddings, read
    through cardgen.engine.index, the same "photo knowledge" the rest uses)
  - expression / look labels (backend/photo_labels.py, vision or heuristic)

    select_photos(owner, subject_id, n, layout="card_grid")
      -> {"ok", "layout", "requested", "picks": [{photo_id, cell, crop, hero, score, reason}],
          "rejects": [{photo_id, reason}], "shortfall", "downgraded_from"}

A pick's crop is [x, y, w, h] in 0-1 units of the EXIF-upright photo, already at
the aspect of the cell it goes in. The rules, in order:

  1. the subject's face is present: a confirmed tag, or an SFace match to the
     subject's confirmed faces (>= SIM_MIN)
  2. the subject is foreground: their face is at least FOREGROUND x the
     biggest face in the photo (strangers behind them are fine, not the reverse)
  3. the face is sharp (Laplacian variance on the aligned face patch), big
     enough (MIN_FACE_PX, MIN_FACE_FRAC) and the photo is not low-res
  4. no near-duplicates: 64-bit DCT perceptual hash, Hamming <= DUP_HASH; the
     better shot of the pair is kept
  5. variety: the best photo is the hero, then maximal-marginal-relevance picks
     trade quality against sameness (shot type solo/couple/group, setting by
     colour histogram, date when EXIF has it)
  6. smart crop per cell: every foreground face inside with headroom, eyes on
     the upper third, a lone subject on a vertical third line, and no face
     (foreground or background) cut by the cell edge
"""
from __future__ import annotations

import hashlib
import json
import math
import time

SIM_MIN = 0.40          # SFace cosine: same person (OpenCV's own threshold is 0.363)
FOREGROUND = 0.60       # subject face height vs the biggest face in the photo
BACKGROUND_FACE = 0.35  # faces smaller than this x the biggest are "background"
MIN_FACE_PX = 70        # subject face height in upright pixels
MIN_FACE_FRAC = 0.045   # subject face height / photo short side
MIN_SHORT_SIDE = 480    # photo short side in pixels
BLUR_MIN = 35.0         # Laplacian variance on a 128px face patch
DUP_HASH = 12           # pHash Hamming distance: near-duplicate at or below
MIN_CELL_DPI = 140      # a pick must print at least this sharp in its cell
CACHE_VERSION = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS photo_quality (
 photo_id TEXT PRIMARY KEY,
 cache_key TEXT NOT NULL,
 data TEXT NOT NULL,
 created_at REAL NOT NULL
);
"""


# ── per-photo analysis (cached) ──────────────────────────────────────────

def _phash(gray) -> int:
    """64-bit DCT perceptual hash of a grayscale uint8 array."""
    import cv2
    import numpy as np
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(small)[:8, :8].flatten()
    med = float(np.median(d[1:]))
    bits = 0
    for i, v in enumerate(d):
        if i and v > med:
            bits |= 1 << i
    return bits


def hamming(a: int, b: int) -> int:
    return bin(int(a) ^ int(b)).count("1")


def _sharpness(gray, box) -> float:
    """Laplacian variance on the face patch, normalised to 128 px tall."""
    import cv2
    x, y, w, h = [int(round(v)) for v in box]
    H, W = gray.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 0.0
    patch = gray[y0:y1, x0:x1]
    s = 128.0 / patch.shape[0]
    patch = cv2.resize(patch, (max(8, round(patch.shape[1] * s)), 128), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(patch, cv2.CV_64F).var())


def _exif_date(im) -> float:
    try:
        ex = im.getexif()
        raw = ex.get(36867) or (ex.get_ifd(0x8769) or {}).get(36867) or ex.get(306)
        if raw:
            return time.mktime(time.strptime(str(raw)[:19], "%Y:%m:%d %H:%M:%S"))
    except Exception:
        pass
    return 0.0


def _load_upright(path):
    """(PIL RGB upright image, exif date). Same orientation the renderer crops in."""
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        date = _exif_date(im)
        up = ImageOps.exif_transpose(im).convert("RGB")
    return up, date


def analyse_image(img, date: float = 0.0) -> dict:
    """Faces (normalised boxes + SFace vectors), sharpness, pHash, setting histogram."""
    import cv2
    import numpy as np
    from backend import faces as FC
    W, H = img.size
    s = min(1.0, 2048.0 / max(W, H))
    work = img if s == 1.0 else img.resize((round(W * s), round(H * s)))
    bgr = cv2.cvtColor(np.asarray(work), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ww, wh = work.size
    faces = []
    for row in FC.detect_boxes(bgr):
        x, y, w, h = (float(v) for v in row[:4])
        faces.append({"box": [x / ww, y / wh, w / ww, h / wh], "score": float(row[-1]),
                      "sharp": round(_sharpness(gray, (x, y, w, h)), 1),
                      "vec": FC.embed_face(bgr, row)})
    # YuNet misses tilted heads (a laughing selfie): retry rotated, keep new faces only
    for ang in (25, -25, 45, -45):
        M = cv2.getRotationMatrix2D((ww / 2, wh / 2), ang, 1.0)
        cos, sin = abs(M[0, 0]), abs(M[0, 1])
        nw, nh = int(wh * sin + ww * cos), int(wh * cos + ww * sin)
        M[0, 2] += nw / 2 - ww / 2
        M[1, 2] += nh / 2 - wh / 2
        rot = cv2.warpAffine(bgr, M, (nw, nh), borderValue=(255, 255, 255))
        rgray = cv2.cvtColor(rot, cv2.COLOR_BGR2GRAY)
        Mi = cv2.invertAffineTransform(M)
        for row in FC.detect_boxes(rot, min_score=0.6):
            x, y, w, h = (float(v) for v in row[:4])
            cx, cy = x + w / 2, y + h / 2
            ox = Mi[0, 0] * cx + Mi[0, 1] * cy + Mi[0, 2]
            oy = Mi[1, 0] * cx + Mi[1, 1] * cy + Mi[1, 2]
            side = max(w, h) * 1.05   # upright box that holds the tilted face
            box = [(ox - side / 2) / ww, (oy - side / 2) / wh, side / ww, side / wh]
            if box[0] < -0.02 or box[1] < -0.02 or box[0] + box[2] > 1.02 or box[1] + box[3] > 1.02:
                continue
            if any(_iou(box, f["box"]) > 0.2 for f in faces):
                continue
            faces.append({"box": [max(0.0, box[0]), max(0.0, box[1]), min(box[2], 1 - max(0.0, box[0])),
                                  min(box[3], 1 - max(0.0, box[1]))],
                          "score": float(row[-1]), "sharp": round(_sharpness(rgray, (x, y, w, h)), 1),
                          "vec": FC.embed_face(rot, row), "rotated": ang})
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 180, 0, 256])
    hist = (hist / max(float(hist.sum()), 1.0)).flatten().round(5).tolist()
    return {"w": W, "h": H, "faces": faces, "phash": str(_phash(gray)), "hist": hist,
            "date": date, "v": CACHE_VERSION}


def _analysis(photo: dict) -> dict:
    from backend import cards as C
    from backend import db
    key = f"{photo['r2_key']}|{CACHE_VERSION}"
    with db.connect() as c:
        c.executescript(SCHEMA)
        r = c.execute("SELECT cache_key, data FROM photo_quality WHERE photo_id=?",
                      (photo["id"],)).fetchone()
    if r and r["cache_key"] == key:
        return json.loads(r["data"])
    img, date = _load_upright(C.local_asset(photo["r2_key"]))
    a = analyse_image(img, date)
    with db.connect() as c:
        c.execute("INSERT OR REPLACE INTO photo_quality VALUES (?,?,?,?)",
                  (photo["id"], key, json.dumps(a), time.time()))
        c.commit()
    return a


# ── candidates: who is in each photo, and how good it is ─────────────────

_EXPR = {"happy": 1.0, "laughing": 1.0, "silly": 0.8, "shocked": 0.6, "unknown": 0.65,
         "neutral": 0.55, "serious": 0.4, "sleepy": 0.2}
_LOOK = {"frontal": 1.0, "three_quarter": 0.85, "unknown": 0.75, "profile": 0.35}


def _iou(a, b) -> float:
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / max(a[2] * a[3] + b[2] * b[3] - inter, 1e-9)


def _shot(n: int) -> str:
    return "solo" if n <= 1 else ("couple" if n == 2 else "group")


def candidate(pid: str, a: dict, hero_vecs: list, tagged_boxes: list, labels: dict | None = None,
              name: str = "them") -> tuple[dict | None, str]:
    """(candidate, "") or (None, reject reason) for one analysed photo."""
    from backend import faces as FC
    W, H = a["w"], a["h"]
    if min(W, H) < MIN_SHORT_SIDE:
        return None, f"low-res ({W}x{H}px; needs {MIN_SHORT_SIDE}px on the short side)"
    faces = a["faces"]
    if not faces:
        return None, "no face found"
    subj, why, sim = None, "", 0.0
    for tb in tagged_boxes:   # a confirmed tag beats any likeness score
        best = max(faces, key=lambda f: _iou(f["box"], tb))
        if _iou(best["box"], tb) > 0.3:
            subj, why = best, "tagged"
            break
    if subj is None and hero_vecs:
        for f in faces:
            if not f.get("vec"):
                continue
            s = max(FC.cosine(f["vec"], v) for v in hero_vecs)
            if s > sim:
                subj, sim = f, s
        if sim < SIM_MIN:
            return None, f"{name} isn't in this photo (best likeness {sim:.2f} < {SIM_MIN})"
        why = f"likeness {sim:.2f}"
    if subj is None:
        return None, f"{name} isn't tagged in this photo and has no tagged face to match"
    fh_px = subj["box"][3] * H
    top_h = max(f["box"][3] for f in faces)
    if subj["box"][3] < FOREGROUND * top_h:
        return None, f"{name} is in the background ({subj['box'][3] / top_h:.0%} of the biggest face)"
    if fh_px < MIN_FACE_PX or fh_px / min(W, H) < MIN_FACE_FRAC:
        return None, f"face too small ({fh_px:.0f}px, {fh_px / min(W, H):.1%} of the frame)"
    if subj["sharp"] < BLUR_MIN:
        return None, f"blurry (face sharpness {subj['sharp']:.0f} < {BLUR_MIN:.0f})"
    fg = [f for f in faces if f["box"][3] >= BACKGROUND_FACE * top_h]
    lab = labels or {}
    expr = _EXPR.get(lab.get("expression", "unknown"), 0.6)
    look = _LOOK.get(lab.get("look", "unknown"), 0.75)
    size = min(1.0, (fh_px / min(W, H)) / 0.30)
    sharp = min(1.0, subj["sharp"] / 250.0)
    res = min(1.0, min(W, H) / 1400.0)
    n = len(fg)
    score = 0.32 * size + 0.26 * sharp + 0.14 * res + 0.16 * expr + 0.12 * look
    if lab.get("eyes_open") in (0, False):
        score -= 0.2
    hero_score = score + {"solo": 0.18, "couple": 0.04}.get(_shot(n), 0.0)
    return {"photo_id": pid, "w": W, "h": H, "subject": subj["box"], "fg": [f["box"] for f in fg],
            "all": [f["box"] for f in faces], "people": n, "shot": _shot(n),
            "sharp": subj["sharp"], "face_px": round(fh_px), "phash": int(a["phash"]),
            "hist": a["hist"], "date": a.get("date") or 0.0, "score": round(score, 4),
            "hero_score": round(hero_score, 4), "match": why}, ""


def _hist_sim(a: list, b: list) -> float:
    """Bhattacharyya-style overlap of two normalised histograms, 0..1."""
    return sum(math.sqrt(max(x, 0) * max(y, 0)) for x, y in zip(a, b))


def similarity(a: dict, b: dict) -> float:
    s = 0.40 * (a["shot"] == b["shot"]) + 0.45 * max(0.0, (_hist_sim(a["hist"], b["hist"]) - 0.5) * 2)
    if a["date"] and b["date"]:
        s += 0.15 * (abs(a["date"] - b["date"]) < 86400)
    else:
        s += 0.15 * 0.5
    return s


def dedupe(cands: list) -> tuple[list, list]:
    """Keep the better shot of every near-duplicate pair. (kept, rejects)."""
    kept, rejects = [], []
    for c in sorted(cands, key=lambda c: -c["score"]):
        twin = next((k for k in kept if hamming(k["phash"], c["phash"]) <= DUP_HASH), None)
        if twin is not None:
            rejects.append({"photo_id": c["photo_id"],
                            "reason": f"near-duplicate of {twin['photo_id']} "
                                      f"(hash distance {hamming(twin['phash'], c['phash'])})"})
        else:
            kept.append(c)
    return kept, rejects


def diverse(cands: list, n: int, *, pin: list | tuple = (), lam: float = 0.35) -> list:
    """Hero first (best hero_score unless pinned), then MMR: quality minus sameness."""
    by = {c["photo_id"]: c for c in cands}
    picked = [by[p] for p in pin if p in by][:n]
    rest = [c for c in cands if c not in picked]
    if not picked and rest:
        hero = max(rest, key=lambda c: c["hero_score"])
        picked.append(hero)
        rest.remove(hero)
    while rest and len(picked) < n:
        best = max(rest, key=lambda c: c["score"] - lam * max(similarity(c, p) for p in picked))
        picked.append(best)
        rest.remove(best)
    return picked


# ── smart crop ───────────────────────────────────────────────────────────

def _frac_inside(face, crop) -> float:
    fx, fy, fw, fh = face
    cx, cy, cw, ch = crop
    ix = max(0.0, min(fx + fw, cx + cw) - max(fx, cx))
    iy = max(0.0, min(fy + fh, cy + ch) - max(fy, cy))
    return ix * iy / max(fw * fh, 1e-12)


def cut_faces(crop, faces) -> list:
    """Faces the crop edge slices through (partly in, partly out)."""
    return [f for f in faces if 0.02 < _frac_inside(f, crop) < 0.98]


def smart_crop(W: int, H: int, fg: list, every: list, aspect: float, *,
               face_frac: float = 0.26, min_px_h: float = 0.0, subject: list | None = None) -> list:
    """[x, y, w, h] (0-1) of an aspect-`aspect` (w/h, in pixels) crop.

    fg/every/subject are face boxes in 0-1 units. Every foreground face is kept
    whole with headroom; eyes sit on the upper third; a lone subject sits on the
    vertical third nearest them; no face of any size is sliced by the edge."""
    fgp = [(f[0] * W, f[1] * H, f[2] * W, f[3] * H) for f in (fg or [subject])]
    allp = [(f[0] * W, f[1] * H, f[2] * W, f[3] * H) for f in (every or fg)]
    fh = max(f[3] for f in fgp)
    ux0 = min(f[0] for f in fgp)
    uy0 = min(f[1] for f in fgp)
    ux1 = max(f[0] + f[2] for f in fgp)
    uy1 = max(f[1] + f[3] for f in fgp)
    # the region that must survive: faces + hair above + chin/shoulders below
    rx0, ry0 = max(0.0, ux0 - 0.45 * fh), max(0.0, uy0 - 0.55 * fh)
    rx1, ry1 = min(W, ux1 + 0.45 * fh), min(H, uy1 + 0.75 * fh)
    hmax = min(H, W / aspect)
    ch = max(fh / face_frac, ry1 - ry0, (rx1 - rx0) / aspect, min(min_px_h, hmax))
    ch = min(ch, hmax)
    cw = ch * aspect

    def place(cw, ch):
        eye_y = uy0 + 0.42 * (uy1 - uy0 if len(fgp) == 1 else fh)
        y = eye_y - ch / 3.0
        cx = (ux0 + ux1) / 2.0
        if len(fgp) == 1:
            rel = cx / W
            x = cx - cw * (1 / 3 if rel < 0.42 else (2 / 3 if rel > 0.58 else 0.5))
        else:
            x = cx - cw / 2.0
        # keep the required region inside, then the photo
        x = min(max(x, rx1 - cw), rx0) if cw >= rx1 - rx0 else (rx0 + rx1 - cw) / 2
        y = min(max(y, ry1 - ch), ry0) if ch >= ry1 - ry0 else (ry0 + ry1 - ch) / 2
        return min(max(0.0, x), W - cw), min(max(0.0, y), H - ch)

    x, y = place(cw, ch)
    # no sliced faces: nudge sideways/vertically first, then widen, up to the photo
    for _ in range(12):
        crop = (x, y, cw, ch)
        bad = cut_faces(crop, allp)
        if not bad:
            break
        f = bad[0]
        moves = []
        for nx in (f[0] + f[2] - cw + 1, f[0] - 1 - cw, f[0] - 1, f[0] + f[2] + 1):
            # include it (first, fourth-ish) or push it fully out (second, third)
            nx = min(max(0.0, nx), W - cw)
            moves.append((nx, y))
        for ny in (f[1] + f[3] - ch + 1, f[1] - 1, f[1] - 1 - ch, f[1] + f[3] + 1):
            ny = min(max(0.0, ny), H - ch)
            moves.append((x, ny))
        ok = [(abs(mx - x) + abs(my - y), mx, my) for mx, my in moves
              if all(_frac_inside(r, (mx, my, cw, ch)) >= 0.999 for r in fgp)
              and len(cut_faces((mx, my, cw, ch), allp)) < len(bad)]
        if ok:
            _d, x, y = min(ok)
            continue
        if ch >= hmax - 0.5:
            break
        ch = min(hmax, ch * 1.12)
        cw = ch * aspect
        x, y = place(cw, ch)
    return [round(float(x) / W, 5), round(float(y) / H, 5), round(float(cw) / W, 5), round(float(ch) / H, 5)]


# ── the public function ──────────────────────────────────────────────────

def _subject_name(owner: str, subject_id: str) -> str:
    from backend import db
    try:
        with db.connect() as c:
            r = c.execute("SELECT name FROM studio_subjects WHERE id=? AND owner=?",
                          (subject_id, owner)).fetchone()
        return (r["name"] if r else "") or "them"
    except Exception:
        return "them"


def candidates(owner: str, subject_id: str) -> tuple[list, list]:
    """(qualifying candidates, rejects) for every photo the owner has."""
    from backend import db
    from backend import photo_labels as PL
    from cardgen import engine as E
    idx = E.index(owner, subject_id, label=True)
    name = _subject_name(owner, subject_id)
    with db.connect() as c:
        rows = {r["id"]: dict(r) for r in c.execute("SELECT * FROM photos WHERE owner=?", (owner,))}
    labs = PL.for_photos(list(rows)) if rows else {}
    tagged = {}
    for p in idx["photos"]:
        for f in p["faces"]:
            if f["hero"]:
                x, y, w, h = f["box"]
                tagged.setdefault(p["id"], []).append(
                    ({"box": [x / max(p["w"], 1), y / max(p["h"], 1), w / max(p["w"], 1), h / max(p["h"], 1)]},
                     f["id"]))
    cands, rejects = [], []
    for pid, p in sorted(rows.items(), key=lambda kv: kv[1].get("created_at") or 0):
        try:
            a = _analysis(p)
        except Exception as e:  # noqa: BLE001
            rejects.append({"photo_id": pid, "reason": f"could not read photo ({type(e).__name__})"})
            continue
        tb = [t[0]["box"] for t in tagged.get(pid, [])]
        lab = {}
        for _t, fid in tagged.get(pid, []):
            lab = labs.get(fid) or {}
        cnd, why = candidate(pid, a, idx["hero_vecs"], tb, lab, name)
        if cnd:
            cands.append(cnd)
        else:
            rejects.append({"photo_id": pid, "reason": why})
    return cands, rejects


def _reason(c: dict, hero: bool, picked: list) -> str:
    bits = [f"{c['shot']} shot", f"face {c['face_px']}px", f"sharpness {c['sharp']:.0f}",
            f"found by {c['match']}"]
    if hero:
        return "hero: best overall photo of them (" + ", ".join(bits) + ")"
    others = [p for p in picked if p is not c]
    if others:
        near = max(others, key=lambda p: similarity(c, p))
        newshot = all(p["shot"] != c["shot"] for p in others)
        setting = 1 - max(0.0, (_hist_sim(c["hist"], near["hist"]) - 0.5) * 2)
        if newshot:
            return "adds variety: new shot type (" + ", ".join(bits) + ")"
        if setting >= 0.15:
            return f"adds variety: setting differs {setting:.0%} from the closest pick (" + ", ".join(bits) + ")"
        return (f"fills the grid: best remaining photo, similar to {near['photo_id']} so placed apart ("
                + ", ".join(bits) + ")")
    return ", ".join(bits)


CARD_LAYOUTS = (10, 6, 4, 1)


def _adjacent(a: dict, b: dict) -> bool:
    """Cells that touch across a gutter (rects in print px, when the layout gives them)."""
    ra, rb = a.get("rect"), b.get("rect")
    if not ra or not rb:
        return False
    g = 60
    return not (ra[0] > rb[0] + rb[2] + g or rb[0] > ra[0] + ra[2] + g or
                ra[1] > rb[1] + rb[3] + g or rb[1] > ra[1] + ra[3] + g)


def select_photos(owner: str, subject_id: str, n: int, layout: str = "card_grid", *,
                  cells: list | None = None, pin: list | tuple = (), exclude: list | tuple = (),
                  fixed: dict | None = None) -> dict:
    """Pick and crop. layout="card_grid" uses the photo-grid card cells for n
    (1, 4, 6 or 10) and steps down to the biggest grid the photos can fill.
    Other products pass `cells` = [{"aspect": w/h, "px_h": print px tall, "hero": bool}].
    pin keeps those photo ids (in order, first = hero); exclude never uses them.
    fixed {cell_index: photo_id} keeps a photo in its cell (swap one photo)."""
    cands, rejects = candidates(owner, subject_id)
    ex = set(exclude or ())
    for c in [c for c in cands if c["photo_id"] in ex]:
        cands.remove(c)
        rejects.append({"photo_id": c["photo_id"], "reason": "excluded by request"})
    pinned = [p for p in (pin or ()) if p not in ex]
    kept, dups = dedupe(cands)
    # a pinned photo always survives dedupe (the human chose it)
    for d in list(dups):
        if d["photo_id"] in pinned:
            dups.remove(d)
            kept.append(next(c for c in cands if c["photo_id"] == d["photo_id"]))
    rejects += dups
    requested = int(n)
    downgraded = None
    if layout == "card_grid":
        from backend import photo_grid as PG
        n_use = requested if requested in CARD_LAYOUTS else min(CARD_LAYOUTS, key=lambda k: abs(k - requested))
        if len(kept) < n_use:
            fit = [k for k in CARD_LAYOUTS if k <= len(kept)]
            downgraded = n_use
            n_use = max(fit) if fit else 0
        cells = PG.cells_for(n_use) if n_use else []
    else:
        n_use = min(requested, len(kept), len(cells or []))
        cells = (cells or [])[:n_use]
    if not n_use:
        return {"ok": False, "layout": 0, "requested": requested, "picks": [],
                "rejects": rejects, "shortfall": requested,
                "summary": "No usable photos of them yet: add a clear, sharp photo where their face is big."}
    picked = diverse(kept, n_use, pin=pinned)
    hero = picked[0]
    # cells: hero takes the hero cell; wide cells prefer couples/groups, tall/square prefer solos
    order = sorted(range(len(cells)), key=lambda i: (not cells[i].get("hero"), i))
    slots: dict = {}
    fixed = {int(k): v for k, v in (fixed or {}).items()}
    pool = list(picked)
    for i, pid in fixed.items():
        hit = next((c for c in pool if c["photo_id"] == pid), None)
        if hit is not None and i < len(cells):
            slots[i] = hit
            pool.remove(hit)
    for i in order:
        if i in slots or not pool:
            continue
        if cells[i].get("hero") and hero in pool:
            slots[i] = hero
            pool.remove(hero)
            continue
        wide = cells[i]["aspect"] > 1.25
        nbrs = [slots[j] for j in slots if _adjacent(cells[i], cells[j])]
        # shape first (groups in wide cells), then keep look-alikes apart
        best = max(pool, key=lambda c: ((c["people"] >= 2) == wide,
                                        -max([similarity(c, o) for o in nbrs] or [0.0])))
        slots[i] = best
        pool.remove(best)
    picks = []
    for i in range(len(cells)):
        c = slots.get(i)
        if c is None:
            continue
        cell = cells[i]
        crop = smart_crop(c["w"], c["h"], c["fg"], c["all"], cell["aspect"],
                          face_frac=cell.get("face_frac", 0.26),
                          min_px_h=cell.get("px_h", 0) * MIN_CELL_DPI / 300.0,
                          subject=c["subject"])
        dpi = round(crop[3] * c["h"] / max(cell.get("px_h", 1), 1) * 300) if cell.get("px_h") else None
        cut = len(cut_faces(crop, c["all"]))
        picks.append({"photo_id": c["photo_id"], "cell": i, "crop": crop, "hero": c is hero,
                      "score": c["score"], "shot": c["shot"], "dpi": dpi, "cut_faces": cut,
                      "reason": _reason(c, c is hero, picked) + (f"; prints at ~{dpi} dpi" if dpi else "")})
    for c in kept:
        if c not in picked:
            rejects.append({"photo_id": c["photo_id"],
                            "reason": f"good, but not needed for {n_use} (score {c['score']:.2f}, "
                                      f"{c['shot']})"})
    out = {"ok": True, "layout": n_use, "requested": requested, "picks": picks, "rejects": rejects,
           "shortfall": max(0, requested - n_use)}
    if downgraded and downgraded != n_use:
        out["downgraded_from"] = downgraded
        out["summary"] = (f"Only {len(kept)} usable photos of them, so this is the {n_use}-photo grid. "
                          f"Add {downgraded - len(kept)} more for the {downgraded}-photo grid.")
    return out
