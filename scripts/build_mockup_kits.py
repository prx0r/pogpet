"""Build assets/mockup_scenes/<product>/ kits from generated magenta scenes. Run ONCE.

  python3 scripts/build_mockup_kits.py SRC_DIR [product ...]

SRC_DIR holds scene_<product>.png (photoreal scene, printable face = pure
#FF00FF) and, for printed-on-surface products, clean_<product>.png (same photo,
plain white product: generated as an edit of the magenta scene). The slot is
keyed from the magenta scene, its corners precomputed, and the render base is
written as scene.jpg: the clean plate (ink products) or the magenta scene with
the face neutralised to grey shading and the key fringe inpainted (opaque
products). Writes scene.jpg, mask.png, kit.json, preview_key.jpg is NOT kept.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "mockup_scenes"
MAX_SIDE = 1600

# product -> mode, surface, print aspect (w/h), fit, corner rotation, note
SPECS = {
    "greeting_card":  dict(mode="quad", surface="opaque", aspect=5 / 7, note="5x7 portrait card front, standing on a table"),
    "postcard":       dict(mode="quad", surface="opaque", aspect=148 / 105, note="A6 landscape postcard on a desk"),
    "sticker":        dict(mode="ellipse", surface="opaque", aspect=1.0, fit="round", note="round die-cut sticker on a laptop lid"),
    "framed_print":   dict(mode="quad", surface="opaque", aspect=3 / 4, note="3:4 portrait print in a black frame with mount"),
    "poster":         dict(mode="quad", surface="opaque", aspect=1 / 2 ** 0.5, note="A-series portrait poster taped to a wall"),
    "photo_tile":     dict(mode="quad", surface="opaque", aspect=1.0, note="square photo tile on a shelf"),
    "canvas":         dict(mode="quad", surface="opaque", aspect=1.0, note="GLOBAL-CAN-10X10 square canvas, white wrap"),
    "cushion":        dict(mode="quad", surface="ink", aspect=1.0, art_soften=0.6, note="square cushion front panel on a sofa"),
    "mug":            dict(mode="cylinder", surface="ink", aspect=2.35, note="11oz mug wrap band, cylinder-mapped (visible window of the wrap)"),
    "tote":           dict(mode="quad", surface="ink", aspect=4 / 5, art_soften=0.6, note="4:5 print on a natural cotton tote"),
    "notebook":       dict(mode="quad", surface="ink", aspect=1 / 2 ** 0.5, note="A5 hardcover notebook front cover"),
    "jigsaw":         dict(mode="quad", surface="ink", aspect=2 ** 0.5, note="assembled landscape jigsaw, piece lines from the clean plate"),
    "wrapping_paper": dict(mode="quad", surface="ink", aspect=None, fit="tile", note="flat wrapping sheet; art is the repeat sheet, cropped to the visible face"),
}
INK = {k for k, v in SPECS.items() if v["surface"] == "ink"}


def key(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (135, 70, 60), (172, 255, 255))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    i = 1 + int(np.argmax(st[1:, 4]))
    m = (lab == i).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    # fill holes
    cnts = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
    filled = np.zeros_like(m)
    cv2.drawContours(filled, [max(cnts, key=cv2.contourArea)], -1, 255, -1)
    return filled, int((st[1:, 4] > 200).sum())


def magenta_any(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (135, 60, 50), (172, 255, 255))


def order(p):
    p = np.asarray(p, np.float32).reshape(4, 2)
    c = p.mean(0)
    ang = np.arctan2(p[:, 1] - c[1], p[:, 0] - c[0])
    p = p[np.argsort(ang)]                      # clockwise in image coords, starting ~left
    tl = int(np.argmin(p.sum(1)))
    return np.roll(p, -tl, axis=0)               # TL, TR, BR, BL


def quad_corners(m):
    c = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
    hull = cv2.convexHull(c)
    peri = cv2.arcLength(hull, True)
    for e in np.linspace(0.005, 0.08, 60):
        a = cv2.approxPolyDP(hull, e * peri, True)
        if len(a) == 4:
            q = order(a)
            break
    else:
        q = order(cv2.boxPoints(cv2.minAreaRect(c)))
    # refine: each side = least-squares line through its contour points, corners = intersections
    pts = c.reshape(-1, 2).astype(np.float32)
    lines = []
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        d = b - a
        L = np.hypot(*d)
        n = np.array([-d[1], d[0]]) / L
        t = ((pts - a) @ d) / (L * L)
        dist = np.abs((pts - a) @ n)
        sel = pts[(t > 0.12) & (t < 0.88) & (dist < 6)]
        if len(sel) < 10:
            lines.append(None)
            continue
        vx, vy, x0, y0 = cv2.fitLine(sel, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x0, y0]), np.array([vx, vy])))
    out = q.copy()
    for i in range(4):
        l1, l2 = lines[(i - 1) % 4], lines[i]
        if l1 is None or l2 is None:
            continue
        A = np.array([l1[1], -l2[1]]).T
        try:
            s = np.linalg.solve(A, l2[0] - l1[0])
        except np.linalg.LinAlgError:
            continue
        p = l1[0] + s[0] * l1[1]
        if np.hypot(*(p - q[i])) < 25:
            out[i] = p
    return out


def ellipse_corners(m):
    c = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
    return order(cv2.boxPoints(cv2.fitEllipse(c)))


def build(src: Path, pid: str) -> dict:
    spec = SPECS[pid]
    S = cv2.imread(str(src / f"scene_{pid}.png"))
    if S is None:
        raise SystemExit(f"missing scene_{pid}.png")
    s = min(1.0, MAX_SIDE / max(S.shape[:2]))
    if s < 1:
        S = cv2.resize(S, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    m, ncomp = key(S)
    H, W = m.shape
    kit = {"product": pid, "mode": spec["mode"], "surface": spec["surface"],
           "aspect": spec["aspect"], "fit": spec.get("fit", "cover"), "note": spec["note"],
           "size": [W, H], "scene": "scene.jpg", "mask": "mask.png",
           "slot_area_frac": round(float((m > 0).mean()), 4), "key_components": ncomp}
    for k in ("art_soften", "shade_max"):
        if k in spec:
            kit[k] = spec[k]
    q = ellipse_corners(m) if spec["mode"] == "ellipse" else quad_corners(m)
    kit["corners"] = [[round(float(x), 2), round(float(y), 2)] for x, y in q]
    if spec["aspect"] is None:   # tile: aspect of the visible face (screen estimate)
        w = (np.hypot(*(q[1] - q[0])) + np.hypot(*(q[2] - q[3]))) / 2
        h = (np.hypot(*(q[3] - q[0])) + np.hypot(*(q[2] - q[1]))) / 2
        kit["aspect"] = round(float(w / h), 4)

    if pid in INK:
        C = cv2.imread(str(src / f"clean_{pid}.png"))
        if C is None:
            raise SystemExit(f"missing clean_{pid}.png")
        C = cv2.resize(C, (W, H), interpolation=cv2.INTER_AREA)
        far = cv2.dilate(m, np.ones((31, 31), np.uint8)) == 0
        kit["clean_align_diff"] = round(float(np.abs(C.astype(int) - S.astype(int))[far].mean()), 2)
        base = C
        alpha = cv2.GaussianBlur(cv2.erode(m, np.ones((3, 3), np.uint8)), (0, 0), 1.0)
        # ink = pure multiply: white in the art leaves the product exactly as photographed
        kit["shade_ref"] = 255.0
    else:
        grow = cv2.dilate(m, np.ones((5, 5), np.uint8))
        alpha = cv2.GaussianBlur(cv2.dilate(m, np.ones((3, 3), np.uint8)), (0, 0), 0.9)
        v = cv2.cvtColor(S, cv2.COLOR_BGR2HSV)[:, :, 2].astype(np.float32)
        inner = cv2.erode(m, np.ones((9, 9), np.uint8)) > 0
        ref = float(np.percentile(v[inner], 90))
        # shading: blurred V inside the face, normalised, baked as grey at 235
        vfill = v.copy()
        vfill[~inner] = 0
        wsum = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), 8)
        vs = cv2.GaussianBlur(vfill, (0, 0), 8) / np.maximum(wsum, 1e-3)
        shade = np.clip(vs / ref, 0.6, 1.04) * 235.0
        base = S.copy()
        g3 = np.repeat(shade[..., None], 3, axis=2).astype(np.uint8)
        base[grow > 0] = g3[grow > 0]
        kit["shade_ref"] = 235.0
    # remove any magenta fringe left around the slot (outside the alpha core)
    ring = cv2.subtract(cv2.dilate(m, np.ones((13, 13), np.uint8)), cv2.erode(alpha, np.ones((3, 3), np.uint8)))
    fringe = cv2.bitwise_and(magenta_any(base), ring)
    fringe = cv2.dilate(fringe, np.ones((3, 3), np.uint8))
    if pid not in INK:
        fringe = cv2.bitwise_and(fringe, cv2.bitwise_not(cv2.dilate(m, np.ones((5, 5), np.uint8))))
    if fringe.any():
        base = cv2.inpaint(base, fringe, 4, cv2.INPAINT_TELEA)
    kit["fringe_px_inpainted"] = int((fringe > 0).sum())
    # anything still magenta anywhere (e.g. loose jigsaw pieces in an opaque scene)
    left = magenta_any(base)
    if pid not in INK:
        left[cv2.dilate(m, np.ones((5, 5), np.uint8)) > 0] = 0
    if left.any():
        base = cv2.inpaint(base, cv2.dilate(left, np.ones((3, 3), np.uint8)), 4, cv2.INPAINT_TELEA)
    kit["stray_magenta_px_inpainted"] = int((left > 0).sum())

    if spec["mode"] == "cylinder":
        hard = m > 0
        xs = np.where(hard.any(axis=0))[0]
        xl, xr = float(xs[0]), float(xs[-1])
        half = (xr - xl) / 2
        r = half / 0.97                      # band reaches ~97% of the visible body half-width
        xc = (xl + xr) / 2
        heights = hard.sum(axis=0)[xs]
        bh = float(np.median(heights))
        arc = r * (np.arcsin(min(1, (xr - xc) / r)) - np.arcsin(max(-1, (xl - xc) / r)))
        kit["cyl"] = {"xc": round(xc, 2), "r": round(r, 2), "xl": xl, "xr": xr,
                      "band_h": bh, "visible_aspect": round(float(arc / bh), 4)}

    d = OUT / pid
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "scene.jpg"), base, [cv2.IMWRITE_JPEG_QUALITY, 88, cv2.IMWRITE_JPEG_OPTIMIZE, 1,
                                             cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    cv2.imwrite(str(d / "mask.png"), alpha, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    (d / "kit.json").write_text(json.dumps(kit, indent=1) + "\n")
    return kit


if __name__ == "__main__":
    src = Path(sys.argv[1])
    ids = sys.argv[2:] or list(SPECS)
    for pid in ids:
        k = build(src, pid)
        print(pid, {x: k[x] for x in ("mode", "surface", "aspect", "corners", "key_components",
                                      "fringe_px_inpainted", "stray_magenta_px_inpainted")},
              k.get("clean_align_diff"), k.get("cyl"))
