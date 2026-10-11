"""Any subject -> every Prodigi product: exact print file + listing mockup.

    make_product(owner, subject_id, product_id, *, age=None, recipient=None,
                 style=None, photo_ids=None) -> {print_path, preview_path, picks, ...}
    make_all(owner, subject_id, ...) -> {product_id: result}

Everything product-specific is DATA in backend/product_recipes.json (print size,
photo counts, layout ids, header placement, margins, the five kinds). This module
is the only code path, for every person:

  1. resolve the print size: prodigi.print_area(sku) when it answers, else the
     recipe's documented size (aspect_source says which)
  2. select_photos with the recipe's photo count for the layout's real cells,
     stepping down to the biggest layout the usable photos can fill (and saying so)
  3. compose with the photo_grid primitives (lettering plates, typeset age/name,
     face-safe crops) or the kind's own composer (round sticker, mug band, wrap
     repeat built from background-removed cutouts of DIFFERENT photos)
  4. write the print file at exact print px; separately composite it into the
     product's scene kit (mockup_slots.render_scene) for the listing preview

Fulfilment only ever uses print_path. No generation at render time.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import random
import time
import uuid
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
RECIPES_PATH = ROOT / "product_recipes.json"
KINDS = ("card", "grid", "sticker_round", "mug_band", "wrap_pattern")
ASPECT_SOURCES = ("live", "verified", "assumed")


class ProductArtError(Exception):
    def __init__(self, message: str, code: str = "PRODUCT_ART_FAILED", status: int = 422, extra=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.extra = extra or {}


# ── recipes ──────────────────────────────────────────────────────────────

def validate_recipes(d: dict) -> list[str]:
    """Problems with a recipes document ([] = valid)."""
    errs = []
    lays = d.get("layouts") or {}
    for lid, lay in lays.items():
        for c in lay.get("cells") or []:
            if len(c) != 4 or c[0] + c[2] > lay["cols"] or c[1] + c[3] > lay["rows"]:
                errs.append(f"layout {lid}: cell {c} outside {lay['cols']}x{lay['rows']}")
    prods = d.get("products") or {}
    if not prods:
        errs.append("no products")
    for pid, r in prods.items():
        k = r.get("kind")
        if k not in KINDS:
            errs.append(f"{pid}: kind {k!r} not in {KINDS}")
        px = r.get("print_px")
        if not (isinstance(px, list) and len(px) == 2 and all(isinstance(v, int) and v > 0 for v in px)):
            errs.append(f"{pid}: print_px must be [w, h] ints")
        if r.get("aspect_source") not in ASPECT_SOURCES:
            errs.append(f"{pid}: aspect_source must be one of {ASPECT_SOURCES}")
        ph = r.get("photos") or {}
        if not (1 <= int(ph.get("min", 0)) <= int(ph.get("ideal", 0))):
            errs.append(f"{pid}: photos needs 1 <= min <= ideal")
        if k == "grid":
            lbc = r.get("layouts_by_count") or {}
            if str(ph.get("ideal")) not in lbc:
                errs.append(f"{pid}: no layout for the ideal photo count {ph.get('ideal')}")
            if "1" not in lbc:
                errs.append(f"{pid}: needs a 1-photo layout to step down to")
            for n, lid in lbc.items():
                if lid not in lays:
                    errs.append(f"{pid}: unknown layout {lid}")
                elif len(lays[lid]["cells"]) != int(n):
                    errs.append(f"{pid}: layout {lid} has {len(lays[lid]['cells'])} cells, not {n}")
            if (r.get("header") or {}).get("pos") not in ("top", "left", "none"):
                errs.append(f"{pid}: header.pos must be top|left|none")
        if k == "wrap_pattern":
            for key in ("heads_across", "rows_per_tile", "cols_per_tile", "rotate_deg"):
                if key not in r:
                    errs.append(f"{pid}: wrap needs {key}")
    return errs


@lru_cache(maxsize=1)
def _load(path: str, mtime: float) -> dict:
    d = json.loads(Path(path).read_text())
    errs = validate_recipes(d)
    if errs:
        raise ProductArtError("bad product recipes: " + "; ".join(errs), "BAD_RECIPES", 500)
    return d


def recipes() -> dict:
    return _load(str(RECIPES_PATH), RECIPES_PATH.stat().st_mtime)


def recipe(product_id: str) -> dict:
    r = recipes()["products"].get(product_id)
    if r is None:
        raise ProductArtError(f"unknown product {product_id!r}; have {sorted(recipes()['products'])}",
                              "UNKNOWN_PRODUCT", 404)
    return r


def recipe_version(product_id: str) -> str:
    d = recipes()
    h = hashlib.sha1(json.dumps(d["products"][product_id], sort_keys=True).encode()).hexdigest()[:8]
    return f"{d['version']}.{product_id}.{h}"


def product_ids() -> list[str]:
    return list(recipes()["products"])


def print_size(product_id: str) -> dict:
    """{"px": (w, h), "aspect_source", "note"}: live print area when it answers."""
    r = recipe(product_id)
    w, h = r["print_px"]
    out = {"px": (w, h), "aspect_source": r["aspect_source"], "note": r.get("aspect_note", "")}
    sku = r.get("sku")
    if not sku:
        try:
            from backend import config
            sku = (config.PRODIGI_PRODUCTS.get(product_id) or {}).get("sku")
        except Exception:
            sku = None
    if sku:
        try:
            from backend import config, prodigi
            cache = config.DATA / "prodigi_templates.json"
            cached = json.loads(cache.read_text()) if cache.is_file() else {}
            if sku in cached or prodigi.api_key():
                spec = prodigi.print_area(sku)
                lw, lh = int(spec["horizontalResolution"]), int(spec["verticalResolution"])
                panels = int(r.get("print_panels") or 1)
                lw //= panels
                if lw > 0 and lh > 0:
                    out = {"px": (lw, lh), "aspect_source": "live",
                           "note": f"prodigi print_area({sku})" + (f" / {panels} panels" if panels > 1 else "")}
        except Exception:
            pass
    return out


# ── subject + photos ─────────────────────────────────────────────────────

# a person's photos go to the human segmenter; a character render on a plain backdrop
# keys cleanly off its border colour; a pet photo gets GrabCut (no human prior)
_SEG_FOR_KIND = {"person": None, "character": "flat", "pet": "grabcut"}

_REL_NAME = {"daughter": "", "son": "", "sister": "", "brother": "", "friend": "", "granddaughter": "",
             "grandson": "", "niece": "", "nephew": "", "partner": "", "girlfriend": "", "boyfriend": "",
             **{"mother": "Mum", "mum": "Mum", "mom": "Mom", "mam": "Mam", "father": "Dad", "dad": "Dad",
             "grandmother": "Nan", "grandfather": "Grandad", "wife": "", "husband": ""}}


def subject_info(owner: str, subject_id: str) -> dict:
    from backend import photo_grid_api as PGA
    sub = PGA._subject(owner, subject_id)
    if not sub:
        raise ProductArtError("Unknown person (subject_id)", "UNKNOWN_SUBJECT", 404)
    return sub


def default_recipient(sub: dict) -> str:
    rel = (sub.get("relationship") or "").strip().lower()
    first = (sub.get("name") or "").split(" ")[0]
    if _REL_NAME.get(rel):
        return _REL_NAME[rel]
    if rel and rel not in _REL_NAME:
        return rel.title()
    return first


def _photo_image(owner: str, pid: str, cache: dict) -> Image.Image:
    if pid in cache:
        return cache[pid]
    from backend import cards as C
    from backend import db
    with db.connect() as c:
        row = c.execute("SELECT * FROM photos WHERE id=? AND owner=?", (pid, owner)).fetchone()
    if row is None:
        raise ProductArtError(f"photo {pid} not found", "UNKNOWN_PHOTO", 404)
    with Image.open(C.local_asset(row["r2_key"])) as im:
        up = ImageOps.exif_transpose(im).convert("RGB")
    cache[pid] = up
    return up


@contextlib.contextmanager
def _memo_candidates():
    """make_all: score the photo library once, not once per product."""
    from backend import photo_select as PS
    orig = PS.candidates
    memo: dict = {}

    def cached(owner, subject_id):
        k = (owner, subject_id)
        if k not in memo:
            memo[k] = orig(owner, subject_id)
        c, r = memo[k]
        return [dict(x) for x in c], [dict(x) for x in r]
    PS.candidates = cached
    try:
        yield
    finally:
        PS.candidates = orig


def _steps(r: dict) -> list[int]:
    ph = r["photos"]
    if r["kind"] == "grid":
        s = sorted({int(k) for k in r["layouts_by_count"]}, reverse=True)
    elif ph.get("steps"):
        s = sorted({int(k) for k in ph["steps"]}, reverse=True)
    else:
        s = list(range(int(ph["ideal"]), 0, -1))
    return [n for n in s if int(ph["min"]) <= n <= int(ph["ideal"])] or [int(ph["min"])]


def _select(owner, sid, r, cells_for, *, photo_ids=None, name="them") -> dict:
    """select_photos at the recipe's count, stepping down to a layout the photos fill."""
    from backend import photo_select as PS
    steps = _steps(r)
    want = steps[0]
    pin = [p for p in (photo_ids or []) if p]
    if pin:
        fit = [n for n in steps if n <= len(pin)]
        want = fit[0] if fit else steps[-1]
    sel = PS.select_photos(owner, sid, want, "product", cells=cells_for(want), pin=pin)
    if not sel.get("ok") or not sel.get("picks"):
        raise ProductArtError(sel.get("summary") or f"No usable photos of {name} yet.", "NEEDS_PHOTO", 422,
                              {"rejects": sel.get("rejects") or []})
    got = len(sel["picks"])
    note = ""
    if got < want:
        fit = [n for n in steps if n <= got] or [steps[-1]]
        n_use = fit[0]
        hero_first = sorted(sel["picks"], key=lambda p: (not p["hero"], p["cell"]))
        keep = [p["photo_id"] for p in hero_first][:n_use]
        sel = PS.select_photos(owner, sid, n_use, "product", cells=cells_for(n_use), pin=keep)
        note = (f"Only {got} usable photo{'s' if got != 1 else ''} of {name}, so this uses the "
                f"{n_use}-photo layout (the full design takes {want}).")
        sel["downgraded_from"] = want
    sel["note"] = note
    return sel


def _picks_out(sel: dict) -> list:
    return [{"photo_id": p["photo_id"], "cell": p["cell"], "hero": p["hero"], "reason": p["reason"]}
            for p in sorted(sel["picks"], key=lambda p: p["cell"])]


# ── grid geometry (any aspect) ───────────────────────────────────────────

def grid_geometry(r: dict, W: int, H: int, layout_id: str) -> dict:
    """{"header": rect|None, "cells": [rect...]} in print px. cells[0] is the hero."""
    lay = recipes()["layouts"][layout_id]
    short = min(W, H)
    m = round(short * float(r.get("margin", 0.06)))
    g = max(2, round(short * float(r.get("gutter", 0.016))))
    hd = r.get("header") or {"pos": "none"}
    pos, frac = hd.get("pos", "none"), float(hd.get("frac", 0.25))
    header = None
    if pos == "top":
        hh = round(H * frac)
        header = (m, m, W - 2 * m, hh)
        area = (m, m + hh + 2 * g, W - 2 * m, H - 2 * m - hh - 2 * g)
    elif pos == "left":
        hw = round(W * frac)
        inset = round(H * 0.10)
        header = (m, m + inset, hw, H - 2 * m - 2 * inset)
        area = (m + hw + 2 * g, m, W - 2 * m - hw - 2 * g, H - 2 * m)
    else:
        area = (m, m, W - 2 * m, H - 2 * m)
    ax, ay, aw, ah = area
    cols, rows = lay["cols"], lay["rows"]
    uw = (aw - (cols - 1) * g) / cols
    uh = (ah - (rows - 1) * g) / rows
    cells = [(ax + c * (uw + g), ay + rr * (uh + g), cw * uw + (cw - 1) * g, rh * uh + (rh - 1) * g)
             for c, rr, cw, rh in lay["cells"]]
    return {"header": header, "cells": cells, "margin": m, "gutter": g}


def _cells_spec(rects: list, dpi: float = 300.0, face_frac=None) -> list:
    out = []
    for i, (x, y, w, h) in enumerate(rects):
        out.append({"aspect": w / h, "px_h": h * 300.0 / dpi, "hero": i == 0, "rect": [x, y, w, h],
                    "face_frac": face_frac or (0.30 if len(rects) == 1 or i == 0 else 0.34)})
    return out


def _paste_photo(cv: Image.Image, img: Image.Image, crop: list, rect, radius: int = 0):
    from backend import photo_grid as PG
    x, y, w, h = [round(v) for v in rect]
    x1, y1 = round(rect[0] + rect[2]), round(rect[1] + rect[3])
    tile = PG._cell_photo(img, crop, (x1 - x, y1 - y), radius)
    if PG._pale_edges(tile):
        ImageDraw.Draw(tile).rounded_rectangle((0, 0, tile.width - 1, tile.height - 1), radius=radius,
                                               outline="#dcdcdc", width=max(1, round(min(tile.size) / 300)))
    cv.alpha_composite(tile, (x, y))


def _header(cv: Image.Image, rect, style: str, age: int, recipient: str):
    from backend import photo_grid as PG
    if not rect:
        return
    x, y, w, h = [round(v) for v in rect]
    hd = PG.header_image(style, int(age or 0), recipient or "", (max(1, w), max(1, h)))
    cv.alpha_composite(hd, (x, y))


# ── composers ────────────────────────────────────────────────────────────

def _compose_grid(ctx) -> tuple[Image.Image, dict]:
    r, (W, H) = ctx["recipe"], ctx["px"]
    lbc = r["layouts_by_count"]
    sel = _select(ctx["owner"], ctx["sid"], r,
                  lambda n: _cells_spec(grid_geometry(r, W, H, lbc[str(n)])["cells"], r.get("dpi", 300)),
                  photo_ids=ctx["photo_ids"], name=ctx["name"])
    n = len(sel["picks"])
    geo = grid_geometry(r, W, H, lbc[str(n)])
    cv = Image.new("RGBA", (W, H), "white")
    _header(cv, geo["header"], ctx["style"], ctx["age"], ctx["recipient"])
    rad = round(min(W, H) * float(r.get("radius", 0)))
    for p in sel["picks"]:
        _paste_photo(cv, _photo_image(ctx["owner"], p["photo_id"], ctx["imgs"]), p["crop"],
                     geo["cells"][p["cell"]], rad)
    return cv.convert("RGB"), {"sel": sel, "layout": lbc[str(n)]}


def _compose_card(ctx) -> tuple[Image.Image, dict]:
    from backend import photo_grid as PG
    from backend import photo_select as PS
    r, (W, H) = ctx["recipe"], ctx["px"]
    ideal = int(r["photos"]["ideal"])
    pin = [p for p in ctx["photo_ids"] or [] if p]
    sel = PS.select_photos(ctx["owner"], ctx["sid"], len(pin) if pin else ideal, "card_grid", pin=pin)
    if not sel.get("ok"):
        raise ProductArtError(sel.get("summary") or "No usable photos yet.", "NEEDS_PHOTO", 422,
                              {"rejects": sel.get("rejects") or []})
    sel["note"] = sel.get("summary", "") if sel.get("downgraded_from") else ""
    design = {"grid": sel["layout"], "grid_style": ctx["style"], "age": ctx["age"],
              "recipient": ctx["recipient"],
              "photos": [{"photo_id": p["photo_id"], "crop": p["crop"]}
                         for p in sorted(sel["picks"], key=lambda p: p["cell"])]}
    assets = {p["photo_id"]: _photo_image(ctx["owner"], p["photo_id"], ctx["imgs"]) for p in sel["picks"]}
    return PG.front(design, assets, width=W, height=H), {"sel": sel, "layout": f"card{sel['layout']}"}


def _mug_rects(W: int, H: int, n: int, r: dict) -> dict:
    """Mug band: the camera (and the drinker) sees ~1.28*H in the middle, so the
    lettering and the best photos sit there; extra photos run round the sides."""
    m = round(H * float(r.get("margin", 0.04)))
    g = round(H * float(r.get("gutter", 0.03)))
    cw = round(H * 1.10)      # inside the ~1.28*H window, so the window edges show white paper
    cx0 = (W - cw) // 2
    hh = round(H * float(r.get("header_frac", 0.30)))
    header = (cx0, m, cw, hh)
    below = (cx0, m + hh + g, cw, H - 2 * m - hh - g)
    cells = []
    if n == 1:
        cells.append(below)
    else:
        bw = (below[2] - g) / 2
        cells += [(below[0], below[1], bw, below[3]), (below[0] + bw + g, below[1], bw, below[3])]
    gap = round(H * 0.12)     # keep side photos out of the front window
    side_w = cx0 - gap - 2 * g
    if n >= 4:
        per = 2 if n >= 6 else 1
        ch = (H - 2 * m - (per - 1) * g) / per
        for side_x in (2 * g, cx0 + cw + gap):
            for k in range(per):
                cells.append((side_x, m + k * (ch + g), side_w, ch))
    return {"header": header, "cells": cells}


def _compose_mug(ctx) -> tuple[Image.Image, dict]:
    r, (W, H) = ctx["recipe"], ctx["px"]
    sel = _select(ctx["owner"], ctx["sid"], r, lambda n: _cells_spec(_mug_rects(W, H, n, r)["cells"]),
                  photo_ids=ctx["photo_ids"], name=ctx["name"])
    geo = _mug_rects(W, H, len(sel["picks"]), r)
    cv = Image.new("RGBA", (W, H), "white")
    _header(cv, geo["header"], ctx["style"], ctx["age"], ctx["recipient"])
    for p in sel["picks"]:
        _paste_photo(cv, _photo_image(ctx["owner"], p["photo_id"], ctx["imgs"]), p["crop"], geo["cells"][p["cell"]])
    return cv.convert("RGB"), {"sel": sel, "layout": f"mug{len(sel['picks'])}"}


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _palette(style: str) -> dict:
    pals = recipes().get("wrap_palettes") or {}
    return pals.get(style) or pals.get("classic") or {"bg": "#1d3b6e", "confetti": ["#ffffff"], "text": "#ffffff"}


def _cutouts(ctx, sel, outline_px: int, **cut_kw) -> list:
    """One background-removed head-and-shoulders motif per DISTINCT picked photo."""
    from backend import cutout as CO
    out, dropped = [], []
    for p in sorted(sel["picks"], key=lambda p: p["cell"]):
        img = _photo_image(ctx["owner"], p["photo_id"], ctx["imgs"])
        others = [f for f in (p.get("faces") or []) if f != p.get("subject")]
        cut = CO.head_and_shoulders(img, p["subject"], others, method=ctx.get("seg_method"), **cut_kw)
        q = CO.quality(cut)
        cut.info["quality"] = q
        if not q["ok"] and len(sel["picks"]) > 1:
            dropped.append({"photo_id": p["photo_id"], "reason": q["reason"]})
            continue
        seg = cut.info.get("segmenter")
        cut = CO.outline(cut, outline_px) if outline_px else cut
        cut.info["segmenter"] = seg
        cut.info["photo_id"] = p["photo_id"]
        out.append(cut)
    if not out:                    # every cutout was weak: keep the hero rather than nothing
        p = sorted(sel["picks"], key=lambda p: (not p["hero"], p["cell"]))[0]
        img = _photo_image(ctx["owner"], p["photo_id"], ctx["imgs"])
        cut = CO.head_and_shoulders(img, p["subject"], [f for f in (p.get("faces") or []) if f != p.get("subject")],
                                    method=ctx.get("seg_method"), **cut_kw)
        seg = cut.info.get("segmenter")
        cut = CO.outline(cut, outline_px) if outline_px else cut
        cut.info.update(segmenter=seg, photo_id=p["photo_id"])
        out.append(cut)
    sel["cutouts_dropped"] = dropped
    return out


def _cutout_room(p: dict) -> float:
    """How well a pick cuts out as a single bust: room below the face, nobody close."""
    x, y, w, h = p["subject"]
    below = min(2.6, (1.0 - (y + h)) / max(h, 1e-6))
    near = 0.0
    for f in p.get("faces") or []:
        if f == p["subject"] or f[3] < 0.35 * h:
            continue
        d = abs((f[0] + f[2] / 2) - (x + w / 2)) / max(w, 1e-6)
        near += max(0.0, 2.6 - d)
    return below - 0.8 * near + 0.3 * p.get("score", 0)


def _compose_sticker(ctx) -> tuple[Image.Image, dict]:
    r, (W, H) = ctx["recipe"], ctx["px"]
    pool = int(r.get("choose_from", 1))
    rr = dict(r, photos=dict(r["photos"], ideal=max(pool, int(r["photos"]["ideal"])), steps=list(range(pool, 0, -1))))
    sel = _select(ctx["owner"], ctx["sid"], rr,
                  lambda n: [{"aspect": 0.8, "px_h": H, "hero": i == 0, "face_frac": 0.4} for i in range(n)],
                  photo_ids=ctx["photo_ids"], name=ctx["name"])
    sel.pop("downgraded_from", None)
    sel["note"] = ""
    if len(sel["picks"]) > 1 and not ctx["photo_ids"]:
        best = max(sel["picks"], key=_cutout_room)
        why = (f"best cutout of the {len(sel['picks'])} best photos: most body below the face "
               f"and no one beside them")
        best = dict(best, hero=True, cell=0, reason=why + "; " + best["reason"])
        sel["picks"] = [best]
    pal = _palette(ctx["style"])
    cut = _cutouts(ctx, sel, 0, bottom=2.6, side=2.0, round_bottom=False)[0]
    side = min(W, H)
    b = round(side * float(r.get("border", 0.04)))
    cv = Image.new("RGBA", (W, H), "white")
    disc = Image.new("L", (W, H), 0)
    ImageDraw.Draw(disc).ellipse((b, b, W - b - 1, H - b - 1), fill=255)
    cv.paste(_hex(pal.get("sticker_bg") or pal["bg"]) + (255,), (0, 0), disc)
    # face ~30% of the disc, eyes a little above centre; the body runs off the disc (clipped by it)
    fpx = cut.info.get("face_px") or (cut.width * 0.3, cut.height * 0.25, cut.width * 0.4, cut.height * 0.3)
    k = (side * 0.30) / max(fpx[3], 1)
    c2 = cut.resize((max(1, round(cut.width * k)), max(1, round(cut.height * k))), Image.Resampling.LANCZOS)
    fcx, fcy = (fpx[0] + fpx[2] / 2) * k, (fpx[1] + fpx[3] / 2) * k
    y = round(H * 0.40 - fcy)
    short = (H - b) - (y + c2.height)      # body ends inside the disc (photo bottom)?
    if short > 0:
        grow = min(1.25, (H - b - H * 0.40) / max(c2.height - fcy, 1))
        if grow > 1.0:
            k *= grow
            c2 = cut.resize((max(1, round(cut.width * k)), max(1, round(cut.height * k))), Image.Resampling.LANCZOS)
            fcx, fcy = (fpx[0] + fpx[2] / 2) * k, (fpx[1] + fpx[3] / 2) * k
            y = round(H * 0.40 - fcy)
        short = (H - b) - (y + c2.height)
        if short > 0:
            y += min(short + 2, round(H * 0.12))
    x = round(W / 2 - fcx)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _paste_clipped(layer, c2, x, y)
    import numpy as np
    layer.putalpha(Image.fromarray(np.minimum(np.asarray(layer.getchannel("A")), np.asarray(disc))))
    cv.alpha_composite(layer)
    return cv.convert("RGB"), {"sel": sel, "layout": "round1", "segmenter": cut.info.get("segmenter")}


# ── wrap pattern ─────────────────────────────────────────────────────────

def _star(d: ImageDraw.ImageDraw, cx, cy, r, rot, fill):
    pts = []
    for i in range(10):
        a = rot + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.sin(a), cy - rr * math.cos(a)))
    d.polygon(pts, fill=fill)


def _confetti_piece(rng: random.Random, colors: list, scale: float) -> Image.Image:
    kind = rng.choice(("star", "star", "strip", "strip", "tri"))
    s = int(scale * rng.uniform(0.8, 1.3))
    im = Image.new("RGBA", (s * 3, s * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = _hex(rng.choice(colors)) + (255,)
    c = s * 1.5
    if kind == "star":
        _star(d, c, c, s * 0.75, rng.uniform(0, math.pi), col)
    elif kind == "strip":
        d.rounded_rectangle((c - s * 0.85, c - s * 0.2, c + s * 0.85, c + s * 0.2), radius=max(1, s // 6), fill=col)
        im = im.rotate(rng.uniform(0, 180), resample=Image.Resampling.BICUBIC)
    else:
        a0 = rng.uniform(0, 2 * math.pi)
        d.polygon([(c + s * 0.6 * math.cos(a0 + k * 2.094), c + s * 0.6 * math.sin(a0 + k * 2.094)) for k in range(3)],
                  fill=col)
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def _text_motif(text: str, style: str, color: tuple, width: int) -> Image.Image:
    from backend import photo_grid as PG
    st = PG.STYLES.get(style) or PG.STYLES["classic"]
    font_file = st["name_font"] if style not in ("classic", "botanical") else st["age_font"]
    size = max(12, int(width * 0.3))
    for s in range(size, 10, -2):
        f = PG._font(font_file, s)
        if f.getlength(text) <= width:
            break
    asc, desc = f.getmetrics()
    im = Image.new("RGBA", (int(f.getlength(text)) + 8, asc + desc + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4, 4), text, font=f, fill=color + (255,))
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def wrap_design(ctx, sel) -> dict:
    """The repeat as data: tile size, lattice, and placed elements in tile coords."""
    r, (W, H) = ctx["recipe"], ctx["px"]
    pal = _palette(ctx["style"])
    cols, rows = int(r["cols_per_tile"]), int(r["rows_per_tile"])
    if cols % 2:
        cols += 1    # brick offset needs an even column count to wrap cleanly
    # integer tile, even height: lattice shifts land on whole pixels (exact repeat)
    Tw = round(cols * W / float(r["heads_across"]))
    Th = 2 * round(rows * (Tw / cols) * 1.16 / 2)
    pitch_x, pitch_y = Tw / cols, Th / rows
    seed = int(hashlib.sha1(("|".join(sorted(p["photo_id"] for p in sel["picks"])) + ctx["style"]).encode())
               .hexdigest()[:8], 16)
    rng = random.Random(seed)
    outline_px = max(3, round(pitch_x * float(r.get("head_outline", 0.022))))
    cuts = _cutouts(ctx, sel, outline_px)
    # consistent head size: every face the same height on paper
    face_h = pitch_y * 0.92 / 3.3
    motifs = []
    for c in cuts:
        fpx = c.info.get("face_px") or (0, 0, c.width * 0.4, c.height * 0.3)
        k = face_h / max(fpx[3], 1)
        k = min(k, pitch_x * 0.9 / c.width, pitch_y * 0.95 / c.height)
        m = c.resize((max(1, round(c.width * k)), max(1, round(c.height * k))), Image.Resampling.LANCZOS)
        # soft drop shadow so the cutouts sit on the paper
        sh = Image.new("RGBA", (m.width + 16, m.height + 16), (0, 0, 0, 0))
        sa = m.getchannel("A").point(lambda v: int(v * 0.28))
        sh.paste((0, 0, 0, 255), (8, 12), sa)
        sh = sh.filter(ImageFilter.GaussianBlur(5))
        sh.alpha_composite(m, (8, 8))
        sh.info["photo_id"] = c.info.get("photo_id")
        motifs.append(sh)
    slots = [(ci, ri, (ci + 0.5) * pitch_x, (ri + 0.5 + (0.5 if ci % 2 else 0.0)) * pitch_y)
             for ci in range(cols) for ri in range(rows)]
    n_text = int(r.get("text_per_tile", 1)) if ctx["age"] else 0
    text_slots = set()
    if n_text:
        # spread the text slots: one per tile column pair, staggered rows
        for t in range(n_text):
            text_slots.add(((t * 2 + 1) % cols) * rows + (t * 3 + 1) % rows)

    # lattice: (Tw, Th/2) and (0, Th) — a half-drop repeat. Neighbours are taken
    # across the wraparound, so no two touching heads share a photo anywhere on the roll.
    def neighbours(i):
        x, y = slots[i][2], slots[i][3]
        out = set()
        for j, s in enumerate(slots):
            for a in (-1, 0, 1):
                for b in (-2, -1, 0, 1, 2):
                    dx = s[2] + a * Tw - x
                    dy = s[3] + a * Th / 2 + b * Th - y
                    if (dx or dy) and abs(dx) <= pitch_x * 1.25 and abs(dy) <= pitch_y * 1.25:
                        out.add(j)
        return out
    nbs = [neighbours(i) for i in range(len(slots))]
    heads_i = [i for i in range(len(slots)) if i not in text_slots]
    n_m = len(motifs)
    cap = -(-len(heads_i) // n_m)            # balanced: no photo used more than its share
    assign: dict = {i: "text" for i in text_slots}
    use = [0] * n_m

    def solve(k):                             # small backtracking colouring (16 slots, <=6 photos)
        if k == len(heads_i):
            return True
        i = heads_i[k]
        taken = {assign.get(j) for j in nbs[i]}
        for m in sorted(range(n_m), key=lambda m: (use[m], m)):
            if m in taken or use[m] >= cap:
                continue
            assign[i] = m
            use[m] += 1
            if solve(k + 1):
                return True
            use[m] -= 1
            del assign[i]
        return False
    if not solve(0):                          # too few photos to keep neighbours apart: balance only
        assign = {i: "text" for i in text_slots}
        use = [0] * n_m
        for i in heads_i:
            taken = {assign.get(j) for j in nbs[i]}
            best = min(range(n_m), key=lambda m: (m in taken, use[m], m))
            assign[i] = best
            use[best] += 1
    elems = []
    tmot = None
    if n_text:
        num, suf = __import__("backend.photo_grid", fromlist=["ordinal"]).ordinal(ctx["age"])
        tmot = _text_motif(f"Happy {num}{suf}", ctx["style"], _hex(pal["text"]), round(pitch_x * 0.92))
    for i, (ci, ri, x, y) in enumerate(slots):
        rot = rng.uniform(-float(r["rotate_deg"]), float(r["rotate_deg"]))
        jx, jy = rng.uniform(-0.05, 0.05) * pitch_x, rng.uniform(-0.05, 0.05) * pitch_y
        if assign[i] == "text":
            im = tmot.rotate(rot * 0.6, expand=True, resample=Image.Resampling.BICUBIC)
            elems.append({"im": im, "x": x + jx, "y": y + jy, "kind": "text"})
        else:
            im = motifs[assign[i]].rotate(rot, expand=True, resample=Image.Resampling.BICUBIC)
            elems.append({"im": im, "x": x + jx, "y": y + jy, "kind": "head",
                          "photo_id": motifs[assign[i]].info.get("photo_id")})
    # confetti in the gaps: rejection-sample against an occupancy map (toroidal)
    occ = Image.new("L", (int(math.ceil(Tw)), int(math.ceil(Th))), 0)
    for e in elems:
        a = e["im"].getchannel("A").point(lambda v: 255 if v > 20 else 0)
        for dx, dy in _lattice_offsets(Tw, Th):
            occ.paste(255, (round(e["x"] + dx - a.width / 2), round(e["y"] + dy - a.height / 2)), a)
    occ = occ.filter(ImageFilter.MaxFilter(size=max(3, (round(pitch_x * 0.06) // 2) * 2 + 1)))
    import numpy as np
    occ_a = np.asarray(occ)
    target = int(r.get("confetti_per_tile", 40))
    scale = pitch_x * 0.075
    tries = 0
    placed = []
    while len(placed) < target and tries < target * 60:
        tries += 1
        x, y = rng.uniform(0, Tw), rng.uniform(0, Th)
        if occ_a[int(y) % occ_a.shape[0], int(x) % occ_a.shape[1]]:
            continue
        if any(_torus_d(x, y, px, py, Tw, Th) < scale * 2.6 for px, py in placed):
            continue
        piece = _confetti_piece(rng, pal["confetti"], scale)
        pa = np.asarray(piece.getchannel("A")) > 20
        ys, xs = np.nonzero(pa)
        x0, y0 = int(x - piece.width / 2), int(y - piece.height / 2)
        hit = occ_a[(ys + y0) % occ_a.shape[0], (xs + x0) % occ_a.shape[1]]
        if hit.any():
            continue
        placed.append((x, y))
        elems.insert(0, {"im": piece, "x": x, "y": y, "kind": "confetti"})
    return {"tile": (Tw, Th), "pitch": (pitch_x, pitch_y), "bg": _hex(pal["bg"]), "elems": elems,
            "motif_photos": [m.info.get("photo_id") for m in motifs],
            "segmenter": cuts[0].info.get("segmenter") if cuts else None}


def _torus_d(x, y, px, py, Tw, Th):
    best = 1e9
    for dx, dy in _lattice_offsets(Tw, Th):
        best = min(best, math.hypot(x - (px + dx), y - (py + dy)))
    return best


def _lattice_offsets(Tw, Th, reach: int = 1):
    out = []
    for a in range(-reach, reach + 1):
        for b in range(-reach - 1, reach + 2):
            out.append((a * Tw, a * Th / 2 + b * Th))
    return out


def render_wrap(design: dict, size: tuple, origin: tuple = (0.0, 0.0)) -> Image.Image:
    """Render the infinite half-drop repeat over a size=(w, h) window whose top-left
    sits at `origin` in pattern coordinates. Same design + window = same pixels."""
    W, H = size
    Tw, Th = design["tile"]
    ox, oy = origin
    cv = Image.new("RGBA", (W, H), design["bg"] + (255,))
    a_min = int(math.floor((ox - Tw) / Tw)) - 1
    a_max = int(math.ceil((ox + W + Tw) / Tw)) + 1
    for e in design["elems"]:
        im = e["im"]
        for a in range(a_min, a_max + 1):
            base_x = e["x"] + a * Tw - ox - im.width / 2
            if base_x > W or base_x + im.width < 0:
                continue
            col_shift = a * Th / 2
            b_min = int(math.floor((oy - col_shift - e["y"] - im.height) / Th)) - 1
            b_max = int(math.ceil((oy + H - col_shift - e["y"] + im.height) / Th)) + 1
            for b in range(b_min, b_max + 1):
                y = e["y"] + col_shift + b * Th - oy - im.height / 2
                if y > H or y + im.height < 0:
                    continue
                _paste_clipped(cv, im, round(base_x), round(y))
    return cv.convert("RGB")


def _paste_clipped(cv: Image.Image, im: Image.Image, x: int, y: int):
    """alpha_composite at (x, y), cropping whatever falls outside the canvas."""
    W, H = cv.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    cv.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def _compose_wrap(ctx) -> tuple[Image.Image, dict]:
    r, (W, H) = ctx["recipe"], ctx["px"]
    sel = _select(ctx["owner"], ctx["sid"], r,
                  lambda n: [{"aspect": 0.8, "px_h": 600, "hero": i == 0, "face_frac": 0.4} for i in range(n)],
                  photo_ids=ctx["photo_ids"], name=ctx["name"])
    design = wrap_design(ctx, sel)
    sheet = render_wrap(design, (W, H))
    ctx["wrap_design"] = design
    return sheet, {"sel": sel, "layout": "wrap_halfdrop", "tile_px": [round(v) for v in design["tile"]],
                   "cutouts_dropped": sel.get("cutouts_dropped") or [],
                   "motif_photos": design["motif_photos"], "segmenter": design["segmenter"]}


COMPOSERS = {"card": _compose_card, "grid": _compose_grid, "sticker_round": _compose_sticker,
             "mug_band": _compose_mug, "wrap_pattern": _compose_wrap}


# ── entry points ─────────────────────────────────────────────────────────

def _save(im: Image.Image, path: Path, dpi: int | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    kw = {"dpi": (dpi, dpi)} if dpi else {}
    if path.suffix.lower() in (".jpg", ".jpeg"):
        im.convert("RGB").save(path, "JPEG", quality=94, subsampling=0, optimize=True, **kw)
    else:
        im.save(path, "PNG", **kw)


def default_out_dir(owner: str, subject_id: str) -> Path:
    from backend import config
    return Path(config.DATA) / "product_art" / owner / subject_id


def make_product(owner: str, subject_id: str, product_id: str, *, age=None, recipient=None, style=None,
                 photo_ids=None, out_dir=None, _imgs: dict | None = None) -> dict:
    """Print file (exact print px) + scene mockup for one product, from the subject's photos."""
    from backend import mockup_slots
    from backend import photo_grid as PG
    from backend import photo_grid_api as PGA
    ctx = build_ctx(owner, subject_id, product_id, age=age, recipient=recipient, style=style,
                    photo_ids=photo_ids, _imgs=_imgs)
    return _finish(ctx, out_dir)


def build_ctx(owner: str, subject_id: str, product_id: str, *, age=None, recipient=None, style=None,
              photo_ids=None, _imgs: dict | None = None) -> dict:
    from backend import photo_grid as PG
    from backend import photo_grid_api as PGA
    r = recipe(product_id)
    sub = subject_info(owner, subject_id)
    age = int(age or 0)
    if recipient is None:
        recipient = default_recipient(sub)
    style = (style or r.get("style") or "auto").lower()
    style_reason = "asked for"
    if style == "auto" or style not in PG.STYLE_IDS:
        style, style_reason = PGA.pick_style(relationship=sub.get("relationship", ""),
                                             interests=sub.get("interests") or [], age=age)
    size = print_size(product_id)
    from backend import photo_select as PS
    kind = PS._subject_kind(owner, subject_id)
    ctx = {"owner": owner, "sid": subject_id, "recipe": r, "px": size["px"], "age": age,
           "recipient": str(recipient or "")[:30], "style": style, "photo_ids": list(photo_ids or []),
           "name": sub.get("name") or "them", "imgs": _imgs if _imgs is not None else {},
           "product_id": product_id, "style_reason": style_reason, "size": size,
           "kind_of_subject": kind, "seg_method": _SEG_FOR_KIND.get(kind)}
    return ctx


def _finish(ctx: dict, out_dir) -> dict:
    from backend import mockup_slots
    from backend import photo_grid as PG
    r, size, product_id = ctx["recipe"], ctx["size"], ctx["product_id"]
    owner, subject_id = ctx["owner"], ctx["sid"]
    style, style_reason, age = ctx["style"], ctx["style_reason"], ctx["age"]
    t0 = time.time()
    art, info = COMPOSERS[r["kind"]](ctx)
    if art.size != tuple(size["px"]):
        raise ProductArtError(f"{product_id}: composed {art.size}, print area is {size['px']}", "SIZE_MISMATCH", 500)
    out_dir = Path(out_dir) if out_dir else default_out_dir(owner, subject_id)
    print_path = out_dir / f"{product_id}_print.jpg"
    preview_path = out_dir / f"{product_id}_preview.jpg"
    _save(art, print_path, int(r.get("dpi", 300)))
    # the mockup: separate output, never sent to fulfilment
    prev_art = art
    pv = r.get("preview") or {}
    if pv.get("crop") == "trim":
        tx, ty, tw, th = PG.trim_box(*art.size)
        prev_art = art.crop((tx, ty, tx + tw, ty + th))
    if pv.get("extent") == "landscape" and ctx.get("wrap_design"):
        # the same repeat at the same scale, laid landscape like the scene's sheet
        prev_art = render_wrap(ctx["wrap_design"], (art.height, art.width))
    try:
        mockup_slots.render_scene(product_id, prev_art, preview_path, faces=False)
        preview_ok = True
    except mockup_slots.KitMissing:
        prev_art.thumbnail((1400, 1400))
        _save(prev_art, preview_path)
        preview_ok = False
    sel = info.pop("sel")
    out = {"ok": True, "product_id": product_id, "subject_id": subject_id,
           "print_path": str(print_path), "preview_path": str(preview_path),
           "print_px": list(art.size), "aspect_source": size["aspect_source"], "aspect_note": size["note"],
           "picks": _picks_out(sel), "photos_used": len({p["photo_id"] for p in sel["picks"]}),
           "requested": sel.get("downgraded_from") or sel.get("requested"),
           "style": style, "style_reason": style_reason, "age": age, "recipient": ctx["recipient"],
           "recipe_version": recipe_version(product_id), "kind": r["kind"], "scene_preview": preview_ok,
           "render_s": round(time.time() - t0, 2), **info}
    if info.get("motif_photos"):
        used = set(info["motif_photos"])
        out["picks"] = [p for p in out["picks"] if p["photo_id"] in used]
        out["photos_used"] = len(used)
    if sel.get("note"):
        out["note"] = sel["note"]
    return out


def make_all(owner: str, subject_id: str, *, age=None, recipient=None, style=None, products=None,
             out_dir=None) -> dict:
    """Every product (or `products`) for one subject. Errors are per product, never fatal."""
    res, imgs = {}, {}
    with _memo_candidates():
        for pid in products or product_ids():
            try:
                res[pid] = make_product(owner, subject_id, pid, age=age, recipient=recipient, style=style,
                                        out_dir=out_dir, _imgs=imgs)
            except ProductArtError as e:
                res[pid] = {"ok": False, "product_id": pid, "error_code": e.code, "error": str(e), **e.extra}
    return res


# ── persistence + public proofs (REST/MCP) ───────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS product_makes (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, subject_id TEXT NOT NULL, product_id TEXT NOT NULL,
 print_key TEXT NOT NULL, preview_key TEXT NOT NULL, meta TEXT NOT NULL, created_at REAL NOT NULL
);
"""


def store(owner: str, result: dict) -> dict:
    """Upload print + preview to storage, record them, add public proof URLs."""
    from backend import config, db, storage
    mid = "pm_" + uuid.uuid4().hex
    slug = storage._slug(owner)
    keys = {}
    for kind in ("print", "preview"):
        k = f"owners/{slug}/products/made/{mid}/{result['product_id']}_{kind}.jpg"
        storage.put(Path(result[f"{kind}_path"]), k)
        keys[kind] = k
    meta = {k: v for k, v in result.items() if k not in ("print_path", "preview_path")}
    with db.connect() as c:
        c.executescript(SCHEMA)
        c.execute("INSERT INTO product_makes VALUES (?,?,?,?,?,?,?,?)",
                  (mid, owner, result["subject_id"], result["product_id"], keys["print"], keys["preview"],
                   json.dumps(meta), time.time()))
        c.commit()
    base = (config.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
    out = dict(result)
    out["make_id"] = mid
    out["print_url"] = f"{base}/backend/api/products/proof/{mid}/print.jpg"
    out["preview_url"] = f"{base}/backend/api/products/proof/{mid}/preview.jpg"
    out["fulfilment_asset"] = "print_url"
    out["print_key"], out["preview_key"] = keys["print"], keys["preview"]
    return out


def proof_file(mid: str, kind: str) -> Path | None:
    from backend import cards as C
    from backend import db
    if kind not in ("print", "preview"):
        return None
    with db.connect() as c:
        c.executescript(SCHEMA)
        row = c.execute("SELECT * FROM product_makes WHERE id=?", (mid,)).fetchone()
    if row is None:
        return None
    try:
        return C.local_asset(row[f"{kind}_key"])
    except Exception:
        return None


def library_fingerprint(owner: str, subject_id: str) -> str:
    """Changes when the owner's photos or the subject's confirmed tags change."""
    from backend import db
    parts = []
    try:
        with db.connect() as c:
            parts += [r["id"] for r in c.execute("SELECT id FROM photos WHERE owner=? ORDER BY id", (owner,))]
            try:
                parts += [f"{r['photo_id']}:{r['confirmed']}" for r in c.execute(
                    "SELECT photo_id, confirmed FROM photo_subjects WHERE subject_id=? ORDER BY photo_id",
                    (subject_id,))]
            except Exception:
                pass
    except Exception:
        pass
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def cache_key(owner, subject_id, product_id, *, age=None, recipient=None, style=None, photo_ids=None) -> str:
    raw = json.dumps([recipe_version(product_id), int(age or 0), recipient, style, list(photo_ids or []),
                      library_fingerprint(owner, subject_id)], default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def find_cached(owner: str, subject_id: str, product_id: str, key: str) -> dict | None:
    from backend import config, db
    with db.connect() as c:
        c.executescript(SCHEMA)
        rows = c.execute("SELECT * FROM product_makes WHERE owner=? AND subject_id=? AND product_id=? "
                         "ORDER BY created_at DESC LIMIT 20", (owner, subject_id, product_id)).fetchall()
    base = (config.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
    for r in rows:
        meta = json.loads(r["meta"])
        if meta.get("cache_key") == key:
            meta.update(make_id=r["id"], cached=True, fulfilment_asset="print_url",
                        print_url=f"{base}/backend/api/products/proof/{r['id']}/print.jpg",
                        preview_url=f"{base}/backend/api/products/proof/{r['id']}/preview.jpg",
                        print_key=r["print_key"], preview_key=r["preview_key"])
            return meta
    return None


def make_and_store(owner: str, subject_id: str, products: list, *, age=None, recipient=None, style=None,
                   photo_ids=None, fresh: bool = False) -> dict:
    """REST/MCP entry: make (or reuse) each product and return public proof URLs."""
    import tempfile
    out, failed = [], {}
    imgs: dict = {}
    with _memo_candidates(), tempfile.TemporaryDirectory() as td:
        for pid in products:
            try:
                recipe(pid)
                key = cache_key(owner, subject_id, pid, age=age, recipient=recipient, style=style, photo_ids=photo_ids)
                hit = None if fresh else find_cached(owner, subject_id, pid, key)
                if hit:
                    out.append(hit)
                    continue
                res = make_product(owner, subject_id, pid, age=age, recipient=recipient, style=style,
                                   photo_ids=photo_ids, out_dir=td, _imgs=imgs)
                res["cache_key"] = key
                stored = store(owner, res)
                for k in ("print_path", "preview_path"):
                    stored.pop(k, None)
                out.append(stored)
            except ProductArtError as e:
                failed[pid] = {"error_code": e.code, "error": str(e), **{k: v for k, v in e.extra.items()
                                                                          if k != "rejects"}}
                if e.extra.get("rejects"):
                    failed[pid]["photos_rejected"] = e.extra["rejects"][:12]
    return {"ok": bool(out), "subject_id": subject_id, "products": out, "failed": failed,
            "count": len(out)}
