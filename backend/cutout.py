"""Head-and-shoulders cutouts of ONE person in a photo (background removed).

    head_and_shoulders(img, face_box, other_faces=()) -> RGBA PIL image, tight to the ink

face_box / other_faces are [x, y, w, h] in 0-1 units of the upright photo (the
same boxes photo_select hands out). The cutout is:

  1. a crop around the face: hair above, shoulders below
  2. a foreground matte from the best segmenter available (`segmenter()`):
       premesh  Cloudflare `segment=foreground` (BiRefNet) via the repo's premesh
                package, only when PREMESH_CUTOUTS=1 and the zone is reachable
       rembg    local u2net_human_seg (pip install "rembg[cpu]"), when importable
       grabcut  OpenCV GrabCut seeded by the face box (always available)
     ODD_SEGMENTER=premesh|rembg|grabcut forces one.
  3. restricted to THIS person: a bust-shaped prior (head ellipse + rounded
     shoulders) multiplied in, other people's faces carved out, and only the
     connected blob that holds the face kept, so neighbours in a group selfie and
     street background never come along.

Deterministic for a given segmenter. No generation.
"""
from __future__ import annotations

import io
import os
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageOps

# crop around the face box, in face heights (h) / widths (w)
TOP = 0.95        # hair above the box top
BOTTOM = 1.25     # shoulders below the box bottom
SIDE = 1.35       # shoulders either side of the box centre, in face widths
WORK_SIDE = 640   # segment at this long side (speed; the matte is upsampled)


@lru_cache(maxsize=1)
def _rembg_session():
    from rembg import new_session
    return new_session("u2net_human_seg")


def segmenter() -> str:
    forced = (os.environ.get("ODD_SEGMENTER") or "").strip().lower()
    if forced in ("premesh", "rembg", "grabcut", "flat"):
        return forced
    if os.environ.get("PREMESH_CUTOUTS") == "1":
        try:
            import premesh  # noqa: F401
            return "premesh"
        except Exception:
            pass
    try:
        import rembg  # noqa: F401
        import onnxruntime  # noqa: F401
        return "rembg"
    except Exception:
        return "grabcut"


def _matte_premesh(rgb: Image.Image) -> np.ndarray:
    from dataclasses import replace
    import premesh
    buf = io.BytesIO()
    rgb.save(buf, "PNG")
    recipe = replace(premesh.RECIPES["card"], prelude=(), prelude_below=0)
    out = premesh.normalize(buf.getvalue(), recipe, timeout=45, retries=0)
    if not out.ok:
        raise RuntimeError("premesh cutout failed QC")
    cut = Image.open(io.BytesIO(out.data)).convert("RGBA")
    # premesh trims the border: put the matte back on the crop's canvas
    a = np.asarray(cut.getchannel("A"))
    if cut.size != rgb.size:
        a = cv2.resize(a, rgb.size, interpolation=cv2.INTER_LINEAR)
    return a


def _matte_rembg(rgb: Image.Image) -> np.ndarray:
    from rembg import remove
    out = remove(rgb, session=_rembg_session(), only_mask=True)
    return np.asarray(out.convert("L"))


def _matte_flat(rgb: Image.Image) -> np.ndarray:
    """Character art on a plain backdrop: everything that differs from the border colour."""
    a = np.asarray(rgb).astype(np.int32)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    diff = np.abs(a - bg).sum(axis=2)
    thr = max(40.0, float(np.percentile(np.abs(border - bg).sum(axis=1), 95)) + 20)
    m = (diff > thr).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # fill holes (a white shirt on a white backdrop): flood the background from the border
    ff = m.copy()
    h, w = ff.shape
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, mask, (0, 0), 128)
    m[ff != 128] = 255
    # a lit backdrop is a gradient, not one colour: let GrabCut settle the edge
    try:
        bgr = np.ascontiguousarray(np.asarray(rgb)[:, :, ::-1])
        gm = np.where(m > 0, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
        k = max(2, min(h, w) // 50)
        gm[:k, :] = gm[-k:, :] = cv2.GC_BGD
        gm[:, :k] = gm[:, -k:] = cv2.GC_BGD
        core = cv2.erode(m, np.ones((15, 15), np.uint8))
        gm[core > 0] = cv2.GC_FGD
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(bgr, gm, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
        m = np.where((gm == cv2.GC_FGD) | (gm == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except Exception:
        pass
    return cv2.GaussianBlur(m, (0, 0), 1.0)


def _matte_grabcut(rgb: Image.Image, face_px) -> np.ndarray:
    a = np.asarray(rgb)[:, :, ::-1].copy()
    H, W = a.shape[:2]
    fx, fy, fw, fh = face_px
    mask = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
    # border = background; bust prior = probable foreground; inner face = foreground
    prior = _bust_prior(W, H, face_px, soft=False)
    mask[prior > 0] = cv2.GC_PR_FGD
    k = max(2, W // 60)
    mask[:k, :] = cv2.GC_BGD
    mask[:, :k] = cv2.GC_BGD
    mask[:, -k:] = cv2.GC_BGD
    cx, cy = fx + fw / 2, fy + fh / 2
    cv2.ellipse(mask, (int(cx), int(cy)), (max(2, int(fw * 0.32)), max(2, int(fh * 0.38))), 0, 0, 360,
                cv2.GC_FGD, -1)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(a, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    return cv2.GaussianBlur(fg, (0, 0), 1.2)


def _bust_prior(W: int, H: int, face_px, soft: bool = True, side: float = SIDE, round_bottom: bool = True) -> np.ndarray:
    """Head ellipse + rounded shoulders, 0..255. Everything outside is never kept."""
    fx, fy, fw, fh = face_px
    cx = fx + fw / 2
    m = np.zeros((H, W), np.uint8)
    # head: a little wider than the box, hair above
    cv2.ellipse(m, (int(cx), int(fy + fh * 0.40)), (int(fw * 0.80), int(fh * 0.98)), 0, 0, 360, 255, -1)
    # neck
    cv2.rectangle(m, (int(cx - fw * 0.42), int(fy + fh * 0.6)), (int(cx + fw * 0.42), int(fy + fh * 1.45)), 255, -1)
    # shoulders: a wide ellipse whose top sits under the chin, cut off at the crop bottom
    sh_y = int(fy + fh * 1.25 + fh * 1.05)
    cv2.ellipse(m, (int(cx), sh_y), (int(fw * side * 1.02), int(fh * 1.05)), 0, 180, 360, 255, -1)
    cv2.rectangle(m, (int(cx - fw * side * 1.02), sh_y), (int(cx + fw * side * 1.02), H), 255, -1)
    if not round_bottom:
        # open body (round sticker): everything below the chin within the shoulders,
        # the disc does the shaping; segmentation and the neighbour cut do the rest
        t, sl = fy + fh * 0.95, fy + fh * 2.1      # shoulders slope out from the neck
        poly = np.array([[cx - fw * 0.95, t], [cx + fw * 0.95, t], [cx + fw * side, sl], [cx + fw * side, H],
                         [cx - fw * side, H], [cx - fw * side, sl]], np.int32)
        cv2.fillPoly(m, [poly], 255)
        return cv2.GaussianBlur(m, (0, 0), max(1.0, fw * 0.03)) if soft else m
    # round the bottom: an arc so the bust ends like a sticker, not a hard ruler line
    bot = np.zeros_like(m)
    by = int(H - fh * 1.15)
    cv2.ellipse(bot, (int(cx), by), (int(fw * side * 0.98), int(fh * 1.1)), 0, 0, 360, 255, -1)
    cv2.rectangle(bot, (0, 0), (W, by), 255, -1)
    m = cv2.bitwise_and(m, bot)
    if soft:
        m = cv2.GaussianBlur(m, (0, 0), max(1.0, fw * 0.03))
    return m


def _keep_face_blob(alpha: np.ndarray, face_px) -> np.ndarray:
    fx, fy, fw, fh = face_px
    hard = (alpha > 96).astype(np.uint8)
    n, lab = cv2.connectedComponents(hard, connectivity=8)
    if n <= 2:
        return alpha
    cx, cy = int(fx + fw / 2), int(fy + fh / 2)
    cx = min(max(cx, 0), alpha.shape[1] - 1)
    cy = min(max(cy, 0), alpha.shape[0] - 1)
    keep = lab[cy, cx]
    if keep == 0:   # face centre fell in a hole: take the largest blob overlapping the face box
        sub = lab[int(fy):int(fy + fh), int(fx):int(fx + fw)]
        vals, counts = np.unique(sub[sub > 0], return_counts=True)
        if not len(vals):
            return alpha
        keep = vals[np.argmax(counts)]
    blob = (lab == keep).astype(np.uint8) * 255
    blob = cv2.dilate(blob, np.ones((5, 5), np.uint8))
    return np.minimum(alpha, blob)


def crop_box(W: int, H: int, face, *, top=TOP, bottom=BOTTOM, side=SIDE):
    """Pixel crop (x0, y0, x1, y1) of the head-and-shoulders region (clamped)."""
    fx, fy, fw, fh = face[0] * W, face[1] * H, face[2] * W, face[3] * H
    cx = fx + fw / 2
    x0, x1 = cx - fw * side, cx + fw * side
    y0, y1 = fy - fh * top, fy + fh + fh * bottom
    return (max(0, int(x0)), max(0, int(y0)), min(W, int(round(x1))), min(H, int(round(y1))))


_MATTE_CACHE: dict = {}


def _full_matte(img: Image.Image, method: str) -> np.ndarray:
    """Whole-photo person matte at the photo's size (segmenters see the whole
    scene: a tight crop confuses them). Cached per image content."""
    import hashlib
    key = (method, hashlib.sha1(img.resize((64, 64)).tobytes()).hexdigest(), img.size)
    if key in _MATTE_CACHE:
        return _MATTE_CACHE[key]
    s = min(1.0, 1024 / max(img.size))
    work = img if s == 1.0 else img.resize((round(img.width * s), round(img.height * s)), Image.Resampling.LANCZOS)
    a = _matte_premesh(work) if method == "premesh" else _matte_rembg(work)
    a = cv2.resize(a, img.size, interpolation=cv2.INTER_LINEAR)
    if len(_MATTE_CACHE) > 16:
        _MATTE_CACHE.clear()
    _MATTE_CACHE[key] = a
    return a


def _neighbour_cut(W: int, H: int, fpx, others_px) -> np.ndarray:
    """0/1 mask: pixels nearer (in face-size units) to the subject than to any
    comparable neighbour. Keeps a neighbour's head and shoulders out of the bust."""
    keep = np.ones((H, W), np.float32)
    sx, sy = fpx[0] + fpx[2] / 2, fpx[1] + fpx[3] / 2
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ds = np.hypot((xx - sx) / fpx[2], (yy - sy) / fpx[3] * 0.8)
    for ox, oy, ow, oh in others_px:
        if ow < fpx[2] * 0.35:
            continue   # a small face far behind: the matte already drops background people
        cx, cy = ox + ow / 2, oy + oh / 2
        if abs(cx - sx) < fpx[2] * 0.3 and abs(cy - sy) < fpx[3] * 0.3:
            continue   # the subject's own box
        do = np.hypot((xx - cx) / ow, (yy - cy) / oh * 0.8)
        keep *= (ds <= do * 1.05).astype(np.float32)
    return cv2.GaussianBlur(keep, (0, 0), max(1.0, fpx[2] * 0.02))


def head_and_shoulders(img: Image.Image, face, other_faces=(), *, method: str | None = None,
                       bottom: float = BOTTOM, side: float = SIDE, round_bottom: bool = True) -> Image.Image:
    """RGBA cutout of the person whose face box is `face` (0-1 units). bottom/side
    widen the bust (a round sticker wants the body to run off the disc)."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    W, H = img.size
    x0, y0, x1, y1 = crop_box(W, H, face, bottom=bottom, side=side)
    crop = img.crop((x0, y0, x1, y1))
    s = min(1.0, WORK_SIDE / max(crop.size))
    work = crop if s == 1.0 else crop.resize((max(1, round(crop.width * s)), max(1, round(crop.height * s))),
                                             Image.Resampling.LANCZOS)
    ww, wh = work.size
    fpx = ((face[0] * W - x0) * s, (face[1] * H - y0) * s, face[2] * W * s, face[3] * H * s)
    method = method or segmenter()
    try:
        if method in ("premesh", "rembg"):
            full = _full_matte(img, method)
            alpha = cv2.resize(full[y0:y1, x0:x1], (ww, wh), interpolation=cv2.INTER_AREA)
        elif method == "flat":
            s2 = min(1.0, 1024 / max(img.size))
            full = _matte_flat(img if s2 == 1.0 else img.resize((round(img.width * s2), round(img.height * s2))))
            full = cv2.resize(full, img.size, interpolation=cv2.INTER_LINEAR)
            alpha = cv2.resize(full[y0:y1, x0:x1], (ww, wh), interpolation=cv2.INTER_AREA)
        else:
            alpha = _matte_grabcut(work, fpx)
    except Exception:
        method = "grabcut"
        alpha = _matte_grabcut(work, fpx)
    others_px = [((o[0] * W - x0) * s, (o[1] * H - y0) * s, o[2] * W * s, o[3] * H * s) for o in other_faces or ()]
    prior = _bust_prior(ww, wh, fpx, side=side, round_bottom=round_bottom)
    alpha = (alpha.astype(np.float32) * (prior.astype(np.float32) / 255.0)
             * _neighbour_cut(ww, wh, fpx, others_px))
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)
    alpha = _keep_face_blob(alpha, fpx)
    # clean speckle and pinholes, then a soft edge
    hard = (alpha > 110).astype(np.uint8) * 255
    hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    hard = cv2.morphologyEx(hard, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    alpha = cv2.GaussianBlur(hard, (0, 0), 0.9)
    a_full = Image.fromarray(alpha).resize(crop.size, Image.Resampling.LANCZOS)
    out = crop.convert("RGBA")
    out.putalpha(a_full)
    bb = a_full.point(lambda v: 255 if v > 24 else 0).getbbox()
    out = out.crop(bb) if bb else out
    out.info["segmenter"] = method
    # where the face sits inside the cutout (for consistent head sizing)
    fx_px = face[0] * W - x0 - (bb[0] if bb else 0)
    fy_px = face[1] * H - y0 - (bb[1] if bb else 0)
    out.info["face_px"] = (fx_px, fy_px, face[2] * W, face[3] * H)
    return out


def outline(cut: Image.Image, px: int, color=(255, 255, 255)) -> Image.Image:
    """Sticker-style solid outline around a cutout (pads the canvas by px)."""
    pad = px + 2
    a = np.asarray(cut.getchannel("A"))
    a = np.pad(a, pad)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    ring = cv2.dilate((a > 40).astype(np.uint8) * 255, k)
    ring = cv2.GaussianBlur(ring, (0, 0), 0.9)
    base = Image.new("RGBA", (a.shape[1], a.shape[0]), (*color, 0))
    base.putalpha(Image.fromarray(ring))
    body = Image.new("RGBA", base.size, (0, 0, 0, 0))
    body.paste(cut, (pad, pad))
    base.alpha_composite(body)
    fp = cut.info.get("face_px")
    if fp:
        base.info["face_px"] = (fp[0] + pad, fp[1] + pad, fp[2], fp[3])
    return base


# a cutout is only worth printing if the face reads: enough of the face box kept
# by the matte, and the face itself neither crushed to a silhouette nor flat
MIN_FACE_KEPT = 0.55
MIN_FACE_LUMA = 70.0
MIN_FACE_STD = 16.0
MAX_DARK_FRAC = 0.42     # share of the head (hair + face) that is near-black: a silhouette, not a face


def quality(cut: Image.Image) -> dict:
    """{"ok", "reason", "face_kept", "face_luma", "face_std"} for a head_and_shoulders cutout."""
    fp = cut.info.get("face_px")
    if not fp:
        return {"ok": True, "reason": "", "face_kept": None}
    x, y, w, h = [int(round(v)) for v in fp]
    # inner face (eyes to mouth): sunglasses and hair edges excluded as far as a box can
    x0, y0 = max(0, x + w // 6), max(0, y + h // 5)
    x1, y1 = min(cut.width, x + w - w // 6), min(cut.height, y + h - h // 8)
    if x1 <= x0 or y1 <= y0:
        return {"ok": False, "reason": "face outside the cutout", "face_kept": 0.0}
    a = np.asarray(cut.getchannel("A"))[y0:y1, x0:x1].astype(np.float32) / 255.0
    rgb = np.asarray(cut.convert("RGB"))[y0:y1, x0:x1].astype(np.float32)
    luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    kept = float(a.mean())
    m = a > 0.5
    fl = float(luma[m].mean()) if m.any() else 0.0
    fs = float(luma[m].std()) if m.any() else 0.0
    hb = min(cut.height, int(y + h * 1.05))           # the head only: clothes may be dark
    A = np.asarray(cut.getchannel("A"))[:hb] > 128
    L = np.asarray(cut.convert("L"))[:hb]
    dark = float((L[A] < 55).mean()) if A.any() else 1.0
    out = {"face_kept": round(kept, 3), "face_luma": round(fl, 1), "face_std": round(fs, 1),
           "dark_frac": round(dark, 3)}
    if dark > MAX_DARK_FRAC:
        return {"ok": False, "reason": f"reads as a dark silhouette ({dark:.0%} near-black)", **out}
    if kept < MIN_FACE_KEPT:
        return {"ok": False, "reason": f"segmentation lost the face ({kept:.0%} kept)", **out}
    if fl < MIN_FACE_LUMA:
        return {"ok": False, "reason": f"face too dark to read as a cutout (luma {fl:.0f})", **out}
    if fs < MIN_FACE_STD:
        return {"ok": False, "reason": f"face too flat (contrast {fs:.0f})", **out}
    return {"ok": True, "reason": "", **out}
