from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from .blender_utils import bbox_objects, robust_extent, robust_mid, world_vertices


def _pct(values, q):
    xs = sorted(float(x) for x in values)
    if not xs:
        return 0.0
    return xs[min(len(xs) - 1, max(0, int((len(xs) - 1) * q)))]


def _named_hand(body, side, center_x, zmin, h):
    key = side.lower()
    candidates = []
    for ob in body:
        name = (ob.name or "").lower().replace(" ", "")
        if key in name and ("arm" in name or "hand" in name):
            pts = world_vertices(ob)
            if pts:
                candidates.extend(pts)
    if candidates:
        zlo = _pct([p.z for p in candidates], 0.05)
        zhi = _pct([p.z for p in candidates], 0.45)
        hand = [p for p in candidates if zlo <= p.z <= zhi] or candidates
        arm_cx = median([p.x for p in hand])
        # "Outer" means farther away from the body's centre, independent of
        # glTF/Blender handedness or whether anatomical Right lands at -X.
        x = min(p.x for p in hand) if arm_cx < center_x else max(p.x for p in hand)
        y = median([p.y for p in hand])
        z = median([p.z for p in hand])
        return [float(x), float(y), float(z)]
    return None


def analyse_target(body, overrides: dict | None = None) -> dict:
    """Measure semantic sockets from arbitrary Blender mesh objects.

    Output deliberately stays JSON-compatible so each generated customer mesh can
    cache this once under data/assets/anchors/ and never be re-analysed unless the
    source mesh changes.
    """
    pts = [p for ob in body for p in world_vertices(ob)]
    if not pts:
        raise ValueError("target contains no vertices")
    mn, mx = bbox_objects(body)
    h = max(mx.z - mn.z, 1e-6)
    w = max(mx.x - mn.x, 1e-6)
    d = max(mx.y - mn.y, 1e-6)
    cx = 0.5 * (mn.x + mx.x)
    cy = 0.5 * (mn.y + mx.y)

    names = " ".join((o.name or "").lower() for o in body)
    is_brick = any(k in names for k in ("minifig", "brick", "right arm", "left arm", "rightarm", "leftarm"))

    # Head is the dense upper mass. The lower edge of this window intentionally
    # includes a little forehead so ears/hair do not become the only measurements.
    upper = [p for p in pts if p.z >= mn.z + 0.64 * h]
    if len(upper) < 16:
        upper = [p for p in pts if p.z >= mn.z + 0.55 * h]
    hcx = median([p.x for p in upper])
    hcy = median([p.y for p in upper])
    head_top = max(p.z for p in upper)

    # Find a brim seat from cross sections, preferring the widest solid slice in
    # the upper third but excluding the very top (hair/ears/pompom-like outliers).
    slices = []
    step = 0.025 * h
    z = mn.z + 0.67 * h
    while z <= mn.z + 0.94 * h:
        band = [p for p in pts if abs(p.z - z) <= step]
        if len(band) >= 12:
            ex = robust_extent([p.x for p in band], .15, .85)
            ey = robust_extent([p.y for p in band], .15, .85)
            solidity = len(band) * min(ex, ey) / max(max(ex, ey), 1e-6)
            slices.append((solidity, z, band, ex, ey))
        z += step
    if slices:
        _, seat_z, seat_band, head_w, head_d = max(slices, key=lambda t: t[0])
        hcx = robust_mid([p.x for p in seat_band], .15, .85)
        hcy = robust_mid([p.y for p in seat_band], .15, .85)
    else:
        seat_z = mn.z + 0.82 * h
        head_w = robust_extent([p.x for p in upper], .15, .85)
        head_d = robust_extent([p.y for p in upper], .15, .85)

    torso_pts = [p for p in pts if mn.z + .27*h <= p.z <= mn.z + .70*h]
    if len(torso_pts) < 24:
        torso_pts = pts
    tx0, tx1 = _pct([p.x for p in torso_pts], .08), _pct([p.x for p in torso_pts], .92)
    ty0, ty1 = _pct([p.y for p in torso_pts], .08), _pct([p.y for p in torso_pts], .92)
    tz0, tz1 = _pct([p.z for p in torso_pts], .08), _pct([p.z for p in torso_pts], .92)
    tcx, tcy, tcz = 0.5*(tx0+tx1), 0.5*(ty0+ty1), 0.5*(tz0+tz1)

    # Head stacked over torso => biped/brick. Head offset laterally => quadruped.
    torso_r = max(tx1-tx0, ty1-ty0, 1e-6) * 0.5
    stacked = ((hcx-tcx)**2 + (hcy-tcy)**2) ** 0.5 < 0.62 * torso_r
    body_class = "brick" if is_brick else ("biped" if stacked else "quadruped")

    right = _named_hand(body, "right", cx, mn.z, h)
    left = _named_hand(body, "left", cx, mn.z, h)
    # Generic fallback: take robust side extrema at arm/hand height.
    mid = [p for p in pts if mn.z + .28*h <= p.z <= mn.z + .67*h]
    if mid:
        if right is None:
            side = sorted(mid, key=lambda p: p.x)[:max(8, len(mid)//20)]
            right = [median([p.x for p in side]), median([p.y for p in side]), median([p.z for p in side])]
        if left is None:
            side = sorted(mid, key=lambda p: p.x)[-max(8, len(mid)//20):]
            left = [median([p.x for p in side]), median([p.y for p in side]), median([p.z for p in side])]

    sockets = {
        "head_top": {"position": [hcx, hcy, head_top], "rotation_euler_deg": [0,0,0]},
        "headwear": {"position": [hcx, hcy, seat_z], "rotation_euler_deg": [0,0,0]},
        "hand_right": {"position": right, "rotation_euler_deg": [0,0,0]},
        "hand_left": {"position": left, "rotation_euler_deg": [0,0,0]},
        "chest": {"position": [tcx, tcy, tcz + .15*(tz1-tz0)], "rotation_euler_deg": [0,0,0]},
        "back": {"position": [tcx, ty1, tcz], "rotation_euler_deg": [90,0,0]},
        "ground": {"position": [cx, cy, mn.z], "rotation_euler_deg": [0,0,0]},
        "feet_center": {"position": [cx, cy, mn.z + .015*h], "rotation_euler_deg": [0,0,0]},
    }
    profile = {
        "version": 2,
        "body_class": body_class,
        "height": h,
        "bbox": {"min": list(mn), "max": list(mx), "width": w, "depth": d},
        "head": {"center": [hcx,hcy], "seat_z": seat_z, "top_z": head_top,
                 "width": max(head_w, .05*w), "depth": max(head_d, .05*d)},
        "torso": {"center": [tcx,tcy,tcz], "width": tx1-tx0, "depth": ty1-ty0,
                  "height": tz1-tz0, "min": [tx0,ty0,tz0], "max": [tx1,ty1,tz1]},
        "sockets": sockets,
    }
    if overrides:
        # Deliberately shallow for top-level fields, deep only for sockets: manual
        # authoring remains obvious instead of silently merging arbitrary schemas.
        for k, v in overrides.items():
            if k == "sockets" and isinstance(v, dict):
                profile["sockets"].update(v)
            else:
                profile[k] = v
    return profile


def load_overrides(path: str | Path | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}
