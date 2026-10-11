"""Photoreal listing mockups: art composited into a pre-keyed product scene.

Each product has a kit in assets/mockup_scenes/<product_id>/:

  scene.jpg   render base. For paper/board products (card, prints, sticker...)
              it is the photo with the slot neutralised to grey shading; for
              printed-on-surface products (mug, cushion, tote, notebook,
              jigsaw, wrapping paper) it is the clean plate (same photo, plain
              white product) so the art picks up the real fabric/ceramic/paper.
  mask.png    soft alpha of the printable face (8-bit).
  kit.json    corners (TL, TR, BR, BL in scene px), mode, surface, print aspect.

Kits are made ONCE by scripts/build_mockup_kits.py from generated scenes whose
printable face is pure magenta #FF00FF. Nothing is generated here: rendering is
pure OpenCV/PIL, deterministic (same art in, same bytes out).

Modes
  quad      planar face, perspective homography onto the 4 corners
  ellipse   round face (sticker); the art is warped onto the ellipse's box
  cylinder  mug wrap band; column-wise cylindrical mapping between the band's
            left/right edges, rows between its top/bottom curves
Surfaces
  opaque    art replaces the face, scaled by the scene's (blurred) shading
  ink       art multiplied onto the clean plate (texture + tint + shading)
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
KITS = ROOT / "assets" / "mockup_scenes"

# shape (config.PRODIGI_PRODUCTS[...]["shape"]) -> default kit for that shape
SHAPE_KIT = {
    "card": "greeting_card", "postcard": "postcard", "sticker": "sticker",
    "print": "framed_print", "poster": "poster", "photo_tile": "photo_tile",
    "canvas": "canvas", "cushion": "cushion", "mug": "mug", "tote": "tote",
    "notebook": "notebook", "jigsaw": "jigsaw", "paper": "wrapping_paper",
}


class KitMissing(LookupError):
    pass


def kit_ids() -> list[str]:
    if not KITS.is_dir():
        return []
    return sorted(p.name for p in KITS.iterdir() if (p / "kit.json").is_file())


def kit_for(product_id: str | None = None, shape: str | None = None) -> str | None:
    """Kit id for a product (preferred) or a shape; None when no kit exists."""
    have = set(kit_ids())
    if product_id and product_id in have:
        return product_id
    k = SHAPE_KIT.get(shape or "")
    return k if k in have else None


@lru_cache(maxsize=32)
def load_kit(kit_id: str) -> dict:
    d = KITS / kit_id
    if not (d / "kit.json").is_file():
        raise KitMissing(kit_id)
    kit = json.loads((d / "kit.json").read_text())
    base = cv2.imread(str(d / kit.get("scene", "scene.jpg")), cv2.IMREAD_COLOR)
    mask = cv2.imread(str(d / kit.get("mask", "mask.png")), cv2.IMREAD_GRAYSCALE)
    if base is None or mask is None or base.shape[:2] != mask.shape[:2]:
        raise KitMissing(f"{kit_id}: scene/mask missing or mismatched")
    kit["_base"] = base
    kit["_mask"] = mask
    kit["id"] = kit_id
    return kit


# ── art preparation ──────────────────────────────────────────────────
def _flatten(im: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        flat = Image.new("RGB", im.size, bg)
        flat.paste(im, (0, 0), im)
        return flat
    return im.convert("RGB")


def _face_rows(im: Image.Image) -> list:
    try:
        from backend import faces
        bgr = cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR)
        return list(faces.detect_boxes(bgr, 0.6))
    except Exception:
        return []


def face_crop(im: Image.Image, scale: float = 2.3) -> Image.Image:
    """Square crop around the largest face (head and shoulders); centre square if none."""
    rows = _face_rows(im)
    if not rows:
        side = min(im.size)
        return im.crop(((im.width - side) // 2, (im.height - side) // 2,
                        (im.width + side) // 2, (im.height + side) // 2))
    x, y, w, h = [float(v) for v in max(rows, key=lambda r: r[2] * r[3])[:4]]
    side = min(max(w, h) * scale, min(im.size))
    cx = min(max(x + w / 2, side / 2), im.width - side / 2)
    cy = min(max(y + h / 2, side / 2), im.height - side / 2)
    return im.crop((round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2)))


def _face_centre(im: Image.Image) -> tuple[float, float]:
    """(cx, cy) in 0..1 of the faces' bounding box, or the centre."""
    rows = _face_rows(im)
    if not rows:
        return 0.5, 0.5
    x0 = min(r[0] for r in rows); y0 = min(r[1] for r in rows)
    x1 = max(r[0] + r[2] for r in rows); y1 = max(r[1] + r[3] for r in rows)
    return (x0 + x1) / 2 / im.width, (y0 + y1) / 2 / im.height


def fit_cover(im: Image.Image, aspect: float, long_side: int = 1800,
              faces: bool = True) -> Image.Image:
    """Crop to aspect (w/h) without stretching; keeps detected faces in frame."""
    w = long_side if aspect >= 1 else round(long_side * aspect)
    h = round(w / aspect)
    if abs(im.width / im.height - aspect) < 0.01:
        return im.resize((w, h), Image.Resampling.LANCZOS)
    cx, cy = _face_centre(im) if faces else (0.5, 0.5)
    return ImageOps.fit(im, (w, h), method=Image.Resampling.LANCZOS, centering=(cx, cy))


def round_sticker(im: Image.Image, size: int = 1400, border: float = 0.035) -> Image.Image:
    """Square face crop in a circle with a white die-cut border (RGB on white)."""
    sq = fit_cover(im, 1.0, size)
    out = Image.new("RGB", (size, size), (255, 255, 255))
    b = round(size * border)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((b, b, size - b - 1, size - b - 1), fill=255)
    out.paste(sq, (0, 0), m)
    return out


def prepare_art(kit: dict, art: Image.Image, faces: bool = True) -> Image.Image:
    """Art at the kit's print aspect, never stretched."""
    art = _flatten(art)
    fit = kit.get("fit", "cover")
    if fit == "tile":
        # wrapping paper: the art IS the repeat sheet; show a crop of it
        return fit_cover(art, kit["aspect"], 2000, faces=False)
    if fit == "round":
        return round_sticker(art)
    if kit["mode"] == "cylinder":
        return _mug_window(kit, art, faces)
    return fit_cover(art, kit["aspect"], 1800, faces)


def _mug_window(kit: dict, art: Image.Image, faces: bool) -> Image.Image:
    """The part of the wrap band that faces the camera, at its true aspect."""
    cyl = kit["cyl"]
    band_aspect = kit["aspect"]               # full wrap w/h
    art = fit_cover(art, band_aspect, 2400, faces=False)
    vis = cyl["visible_aspect"]               # arc length / band height on screen
    w = min(art.width, round(art.height * vis))
    x0 = (art.width - w) // 2
    return art.crop((x0, 0, x0 + w, art.height))


# ── compositing ──────────────────────────────────────────────────────
def _warp_quad(art_bgr, corners, size):
    h, w = art_bgr.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    H = cv2.getPerspectiveTransform(src, np.float32(corners))
    return cv2.warpPerspective(art_bgr, H, size, flags=cv2.INTER_AREA,
                               borderMode=cv2.BORDER_REPLICATE)


def _warp_cylinder(art_bgr, kit, mask):
    """Column-wise cylinder map. For each scene column x in the band, the angle
    on the cylinder is asin((x - xc) / r); u is that angle across the visible
    span. Rows run from the band's top curve to its bottom curve."""
    H_, W_ = mask.shape
    cyl = kit["cyl"]
    xc, r = cyl["xc"], cyl["r"]
    xl, xr = cyl["xl"], cyl["xr"]
    hard = mask > 127
    cols = np.arange(W_)
    has = hard.any(axis=0)
    top = np.where(has, hard.argmax(axis=0), 0).astype(np.float32)
    bot = np.where(has, H_ - 1 - hard[::-1].argmax(axis=0), 0).astype(np.float32)
    # columns where the key only covers a sliver (the rim notch at the band's edge)
    # would squash the art upward: take the curves from full-height columns only
    span = np.where(has, bot - top, 0)
    if has.any():
        full = has & (span >= 0.85 * float(np.median(span[has])))
        has = full if full.sum() > 8 else has
    # smooth the curves (anti-aliased key edges wobble by a pixel)
    idx = np.where(has)[0]
    if len(idx) > 8:
        k = 9
        for arr in (top, bot):
            v = arr[idx]
            pad = np.pad(v, k, mode="edge")
            arr[idx] = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
        # extend to the replicate border so feathered edge pixels have values
        top[:idx[0]] = top[idx[0]]; top[idx[-1]:] = top[idx[-1]]
        bot[:idx[0]] = bot[idx[0]]; bot[idx[-1]:] = bot[idx[-1]]
    a0 = np.arcsin(np.clip((xl - xc) / r, -1, 1))
    a1 = np.arcsin(np.clip((xr - xc) / r, -1, 1))
    ang = np.arcsin(np.clip((cols - xc) / r, -1, 1))
    u = (ang - a0) / max(a1 - a0, 1e-6)                       # 0..1 per column
    ys = np.arange(H_, dtype=np.float32)[:, None]
    v = (ys - top[None, :]) / np.maximum(bot - top, 1)[None, :]
    ah, aw = art_bgr.shape[:2]
    map_x = np.repeat((u * (aw - 1)).astype(np.float32)[None, :], H_, axis=0)
    map_y = (v * (ah - 1)).astype(np.float32)
    return cv2.remap(art_bgr, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def composite(kit: dict, art: Image.Image) -> np.ndarray:
    base = kit["_base"]
    mask = kit["_mask"]
    size = (base.shape[1], base.shape[0])
    art_bgr = cv2.cvtColor(np.asarray(art.convert("RGB")), cv2.COLOR_RGB2BGR)
    if kit["mode"] == "cylinder":
        warped = _warp_cylinder(art_bgr, kit, mask)
    else:
        warped = _warp_quad(art_bgr, kit["corners"], size)
    if kit.get("art_soften"):
        warped = cv2.GaussianBlur(warped, (0, 0), float(kit["art_soften"]))
    a = (mask.astype(np.float32) / 255.0)[..., None]
    b = base.astype(np.float32)
    ref = float(kit.get("shade_ref", 235.0))
    if kit.get("surface") == "ink":
        shade = np.clip(b / ref, 0.0, 1.0)
    else:
        g = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY).astype(np.float32)
        shade = np.clip(g / ref, 0.55, float(kit.get("shade_max", 1.04)))[..., None]
    lit = warped.astype(np.float32) * shade
    out = b * (1 - a) + lit * a
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def render_scene(product_id: str, art_image, out_path, faces: bool = True) -> Path:
    """Composite `art_image` (path or PIL image) into the product's scene kit.

    Deterministic, no generation. Raises KitMissing when there is no kit.
    """
    kit = load_kit(product_id)
    art = art_image if isinstance(art_image, Image.Image) else Image.open(art_image)
    art = prepare_art(kit, art, faces=faces)
    out = composite(kit, art)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rgb = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    if out_path.suffix.lower() in (".jpg", ".jpeg"):
        rgb.save(out_path, "JPEG", quality=90, optimize=True, progressive=True)
    elif out_path.suffix.lower() == ".webp":
        rgb.save(out_path, "WEBP", quality=88, method=6)
    else:
        rgb.save(out_path, "PNG", compress_level=6)
    return out_path


# ── one source image -> product art (the live /api/products path) ────────
def wrap_motif(src: Image.Image, size: int = 800) -> Image.Image:
    """Round face motif with a white ring, transparent outside (for wrap sheets)."""
    face = fit_cover(face_crop(_flatten(src), 2.0), 1.0, size, faces=False)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((size // 20, size // 20, size - size // 20 - 1, size - size // 20 - 1), fill=255)
    ring = Image.new("L", (size, size), 0)
    ImageDraw.Draw(ring).ellipse((size // 80, size // 80, size - size // 80 - 1, size - size // 80 - 1), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste((255, 255, 255, 255), (0, 0), ring)
    out.paste(face.convert("RGBA"), (0, 0), m)
    return out


def art_from_photo(kit_id: str, src: Image.Image) -> Image.Image:
    """Turn a single photo/render into the product's print art."""
    kit = load_kit(kit_id)
    if kit.get("fit") == "tile":
        import tempfile
        from backend.renderers import wrap
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "motif.png"
            wrap_motif(src).save(p)
            return wrap.render_sheet(str(p), sku="WRAP-1-50X70", mode="scattered", seed=7)
    if kit.get("fit") == "round":
        return face_crop(_flatten(src))
    return _flatten(src)


def render_product(kit_id: str, photo: Path, out_path: Path) -> Path:
    """mockup.render() entry: one source image -> photoreal product scene."""
    src = Image.open(photo)
    return render_scene(kit_id, art_from_photo(kit_id, src), out_path)
