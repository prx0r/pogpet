#!/usr/bin/env python3
"""Fit engine — attach hats + harness garments to ANY mesh. Free Blender.

The foolproof pattern (industry standard: Roblox attachments, Unity/Unreal
sockets): measure each mesh ONCE into named anchors, author every part
against an anchor, seat by numbers, shrinkwrap garments so intersection is
impossible. No per-mesh hand-tuning, ever.

    # 1. measure any mesh -> anchors sidecar
    blender --background --python scripts/fit_engine.py -- \\
        --in data/uploads/chibi-figure-hook.glb --mode measure \\
        --anchors data/assets/anchors/chibi-figure-hook.json

    # 2. seat the santa hat part on those anchors -> composed GLB
    blender --background --python scripts/fit_engine.py -- \\
        --in data/uploads/chibi-figure-hook.glb \\
        --anchors data/assets/anchors/chibi-figure-hook.json \\
        --hat data/assets/parts/hat-santa.glb --mode compose \\
        --out data/productimg/prod/dog-santa.glb

    # 3. build + fit a harness garment, compose with it
    blender --background --python scripts/fit_engine.py -- \\
        --in data/uploads/chibi-figure-hook.glb \\
        --anchors data/assets/anchors/chibi-figure-hook.json \\
        --harness cream --mode compose \\
        --out data/productimg/prod/dog-harness-cream.glb

Modes: measure | compose. --hat and --harness combine freely.
P0 reference: docs/p0-hat-coat.md. 0 Meshy credits.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--mode", choices=("measure", "compose"), default="measure")
    p.add_argument("--anchors", default="")
    p.add_argument("--hat", default="none", help="hat part GLB or 'none'")
    p.add_argument("--harness", default="none",
                   help="strap-harness colour (cream|golden|chocolate|black|fawn|grey) or 'none'")
    p.add_argument("--jacket", default="none",
                   help="winter jacket colour (cream|golden|chocolate|black|fawn|grey) or 'none'")
    p.add_argument("--gap", type=float, default=0.0,
                   help="garment clearance off the body, metres "
                        "(0 = auto: 1%% of mesh height)")
    p.add_argument("--out", default="")
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    return p.parse_args(argv)


HARNESS_COLOURS = {
    "cream": (0.93, 0.86, 0.74),
    "golden": (0.90, 0.72, 0.42),
    "chocolate": (0.42, 0.26, 0.16),
    "black": (0.12, 0.11, 0.11),
    "fawn": (0.82, 0.68, 0.52),
    "grey": (0.55, 0.55, 0.56),
}

# Provenance: measured on chibi-figure-hook.glb 2026-10-03 (scripts/santa_seat.py).
# Brim must hug the skull BETWEEN the ears (~0.05 wide), never the ear span.
# Head cluster is found top-down: the first flare (band wider than 1.7× the
# narrowest band above it) is the neck/shoulders; the hat seats halfway down
# the cluster. Works for head-up quadrupeds, standing figures and helmets.
TOP_BAND = 0.18       # fallback scan window when no flare is found
FLARE_RATIO = 1.7     # band this much wider than the min above = neck/shoulders
MIN_CLUSTER = 0.06    # head cluster is at least this tall (× height)
TORSO_LO = 0.30       # torso = verts between these height fractions…
TORSO_HI = 0.70       # …(excludes head above, legs/feet below)


def _body_meshes(scene):
    return [o for o in scene.objects if o.type == "MESH"]


def _world_verts(ob):
    mw = ob.matrix_world
    return [mw @ v.co for v in ob.data.vertices]


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def _pct(xs, q):
    s = sorted(xs)
    if not s:
        return 0.0
    i = min(len(s) - 1, max(0, int(q * len(s))))
    return s[i]


def _band_width(pts):
    """Narrow cross-axis spread (p85-p15): the skull width analogue.

    Heads are longer (snout-to-back) than wide; the narrow axis is the
    width and ignores ears, which read wide on the other axis only.
    Symmetric heads (brick sphere) read the same on both axes.
    """
    if len(pts) < 8:
        return 0.0
    xs = sorted(p.x for p in pts)
    ys = sorted(p.y for p in pts)
    n = len(xs)
    lo, hi = n * 15 // 100, min(n - 1, n * 85 // 100)
    return max(min(xs[hi] - xs[lo], ys[hi] - ys[lo]), 1e-6)


def _slice_spread(pts, axis="x"):
    """p85-p15 spread along an axis (robust to thin outliers)."""
    vals = sorted(p.x if axis == "x" else p.y for p in pts)
    n = len(vals)
    if n < 8:
        return 0.0
    return vals[min(n - 1, n * 85 // 100)] - vals[n * 15 // 100]


def _core_spread(pts, axis="x"):
    """p70-p30 spread: the dense core, ignoring thin outlier limbs/ears."""
    vals = sorted(p.x if axis == "x" else p.y for p in pts)
    n = len(vals)
    if n < 8:
        return 0.0
    return max(vals[min(n - 1, n * 70 // 100)] - vals[n * 30 // 100], 1e-6)


def measure(body) -> dict:
    """Body meshes -> anchor dict. All Blender (Z-up) world space."""
    import mathutils
    pts = []
    for ob in body:
        pts.extend(_world_verts(ob))
    zs = [p.z for p in pts]
    zmin, zmax = min(zs), max(zs)
    h = max(zmax - zmin, 1e-6)

    # ── head cluster, found top-down ──
    # Two anatomical signatures, checked in order:
    #   pinch: head narrows into the neck (steep sustained drop) — the
    #     brim sits high on the resulting cluster (dog, brick minifig).
    #   flare: head widens into shoulders (torso much wider than the
    #     narrowest band above) — leaning/bulky heads (badger).
    # De-splinter first: a 3-band smooth stops single-slice slivers
    # (ear tips, studs) from faking a boundary.
    step = 0.02 * h
    prof = []
    z = zmax - MIN_CLUSTER * h
    # Scan deep (0.85h): the true neck sits low; brow/eye taper pinches
    # above it lose to the lowest mass-gated survivor. Sparse leg-split
    # slivers can't fake a pinch (sparse-skip below) and leg masses fail
    # the 10-50% head-mass gate.
    while z > zmax - 0.85 * h:
        band = [p for p in pts if z - step <= p.z <= z]
        prof.append((z, len(band), _band_width(band)))
        z -= step
    # De-splinter: sparse bands inherit (leg-split slivers can't fake
    # anatomy), and a band narrower than 0.75× BOTH second-neighbours is
    # sampling noise (single-band V dips can't be anatomy — real necks
    # persist ≥2 bands).
    sm = []
    peak_n = max((n for _, n, _ in prof), default=1)
    last_w = None
    for i, (zz, n, w) in enumerate(prof):
        if n < 0.02 * peak_n and last_w is not None:
            w = last_w
        else:
            lo = prof[max(0, i - 2)][2]
            hi = prof[min(len(prof) - 1, i + 2)][2]
            if w < 0.75 * lo and w < 0.75 * hi:
                w = 0.5 * (lo + hi)
        sm.append((zz, n, w))
        last_w = w
    print("scan(top-down z, n, width):",
          " ".join(f"{zz:.3f}:{w:.3f}" for zz, n, w in sm[:18]))
    # Collect EVERY pinch+recovery pair, then keep only necks: a neck
    # carries head-like mass above it (10-50% of all verts). Crown
    # slivers (<10% above) and legs/waists (>50% above) are rejected.
    # Lowest survivor wins (closest to the torso). Then shoulder flare.
    # Recovery may be gradual (a long chest widens slowly): accept a jump
    # within 5 bands, else the max over 10 bands.
    total_n = sum(n for _, n, _ in sm) or 1
    cands = []
    peak = 0.0
    for i, (zz, n, w) in enumerate(sm):
        if w > peak:
            peak = w
        nxt = sm[i + 1][2] if i + 1 < len(sm) else w
        if peak > 0 and w < 0.75 * peak and nxt < 0.85 * peak:
            rec = None
            for zz2, n2, w2 in sm[i + 1:i + 6]:
                if w2 > 1.25 * w:
                    rec = zz2
                    break
            if rec is None:
                window = [(zz2, w2) for zz2, _, w2 in sm[i + 1:i + 11]]
                if window and max(w2 for _, w2 in window) > 1.5 * w:
                    for zz2, w2 in window:
                        if w2 > 1.25 * w:
                            rec = zz2
                            break
            if rec is not None:
                above = sum(nn for zzz, nn, _ in sm if zzz > rec)
                cands.append((round(rec, 4), round(w, 4),
                              round(peak, 4),
                              round(above / total_n, 3)))
    print("pinch candidates (rec_z, cand_w, peak, mass_above):", cands)
    survivors = [c[0] for c in cands if 0.10 <= c[3] <= 0.50]
    boundary = min(survivors) if survivors else None
    if boundary is None:
        trough = None
        for zz, n, w in sm:
            if trough is None or w < trough:
                trough = w
            if trough > 0 and w > FLARE_RATIO * trough:
                boundary = zz  # shoulder flare
                break
    if boundary is None:
        boundary = zmax - 0.50 * h
    flare_z = boundary
    cluster_h = max(zmax - boundary, MIN_CLUSTER * h)
    # Brim rides the upper head: proven 0.145 on the dog.
    seat_z = zmax - 0.4 * cluster_h
    # width at the seat slice (tight window: arms/ears live outside it)
    sw = 0.03 * h
    seat_band = [p for p in pts if seat_z - sw <= p.z <= seat_z + sw]
    if len(seat_band) < 8:
        seat_band = [p for p in pts if p.z >= flare_z]
    cx, cy = _median([p.x for p in seat_band]), _median([p.y for p in seat_band])
    # Width = the NARROW cross-axis at seat height. Heads are longer
    # (snout-to-back) than wide; the narrow axis is the skull width and
    # ignores ears, which read wide on the other axis. Symmetric heads
    # (brick sphere) read the same on both axes.
    head_w = max(min(_slice_spread(seat_band, "x"),
                     _slice_spread(seat_band, "y")), 1e-6)
    seat = [cx, cy, seat_z]

    # ── spine: principal horizontal axis of the torso band ──
    torso = [p for p in pts
             if zmin + TORSO_LO * h <= p.z <= zmin + TORSO_HI * h]
    if len(torso) < 32:
        torso = pts
    mx = sum(p.x for p in torso) / len(torso)
    my = sum(p.y for p in torso) / len(torso)
    sxx = sum((p.x - mx) ** 2 for p in torso)
    syy = sum((p.y - my) ** 2 for p in torso)
    sxy = sum((p.x - mx) * (p.y - my) for p in torso)
    # 2x2 PCA, closed form
    tr = sxx + syy
    det = sxx * syy - sxy * sxy
    disc = max(tr * tr / 4 - det, 0.0) ** 0.5
    lam = tr / 2 + disc
    ax = (lam - syy, sxy)
    n = (ax[0] ** 2 + ax[1] ** 2) ** 0.5 or 1.0
    spine = [ax[0] / n, ax[1] / n]
    # biped (brick minifig) or quadruped? Compare torso extents: a standing
    # torso is taller than it is wide; a quadruped torso is longer than tall.
    tx = [p.x for p in torso]
    ty = [p.y for p in torso]
    tz = [p.z for p in torso]
    # Robust extents (p90-p10): thin outlier limbs (splayed arms, tails)
    # must not decide the body plan.
    def _ext(vals):
        s = sorted(vals)
        n = len(s)
        return s[min(n - 1, n * 9 // 10)] - s[n // 10]
    # Stacked (biped) or offset (quadruped)? A stacked head sits above the
    # torso centroid; a quadruped head sticks out past the torso half-width.
    tcx, tcy = _median(tx), _median(ty)
    torso_r = max(_ext(tx), _ext(ty)) / 2
    stacked = ((cx - tcx) ** 2 + (cy - tcy) ** 2) ** 0.5 < 0.7 * torso_r
    vertical = bool(stacked)
    if vertical:
        # biped torso (brick minifig): stations stack along Z
        u, v = [1.0, 0.0], [0.0, 1.0]
        axis = [0.0, 0.0, 1.0]
    else:
        # quadruped: stations run along the spine, rings face it
        u = [-spine[1], spine[0]]          # across
        v = spine[:]                        # along
        axis = [0.0, 0.0, 1.0]

    # ── stations: slice the torso, girth per slice ──
    def coord(p):
        if vertical:
            return p.z
        return p.x * v[0] + p.y * v[1]

    cs = [coord(p) for p in torso]
    cmin, cmax = min(cs), max(cs)
    span = max(cmax - cmin, 1e-6)
    slices = []
    for f in (0.30, 0.40, 0.50, 0.60, 0.70):
        c0 = cmin + f * span
        band = [p for p in torso if abs(coord(p) - c0) <= 0.06 * span]
        if len(band) < 8:
            continue
        # Slice radii hug the dense core (p70-p30): thin outlier limbs
        # (splayed arms, ears) must not size the straps. Shrinkwrap pushes
        # the rings out to the true surface + gap anyway.
        if vertical:
            xw = _core_spread(band, "x")
            yw = _core_spread(band, "y")
            ru, rv = xw / 2, yw / 2
        else:
            au = sorted(p.x * u[0] + p.y * u[1] for p in band)
            zw = sorted(p.z for p in band)
            n = len(au)
            ru = max(au[min(n - 1, n * 70 // 100)] - au[n * 30 // 100], 1e-4) / 2
            n2 = len(zw)
            rv = max(zw[min(n2 - 1, n2 * 70 // 100)] - zw[n2 * 30 // 100], 1e-4) / 2
        slices.append({
            "f": f, "c": c0, "ru": max(ru, 1e-4), "rv": max(rv, 1e-4),
            "cx": _median([p.x for p in band]),
            "cy": _median([p.y for p in band]),
            "cz": _median([p.z for p in band]),
            "girth": max(ru, 1e-4) + max(rv, 1e-4),
        })
    # chest = girthiest slice toward the head end, belly = toward the tail end
    head_end = max(cs) if (cx * v[0] + cy * v[1] if not vertical else 1) >= 0 else min(cs)
    # …simpler + orientation-free: chest = girthiest of the two upper slices,
    # belly = girthiest of the two lower slices (upper = larger coord value)
    ordered = sorted(slices, key=lambda s: s["c"])
    upper = ordered[len(ordered) // 2:]
    lower = ordered[:len(ordered) // 2] or ordered[:1]
    chest = max(upper, key=lambda s: s["girth"])
    belly = max(lower, key=lambda s: s["girth"])

    return {
        "height": h, "zmin": zmin, "zmax": zmax,
        "head": {"center": [round(cx, 5), round(cy, 5)],
                 "width": round(head_w, 5),
                 "seat": [round(x, 5) for x in seat]},
        "cluster": {"bottom": round(flare_z, 5), "top": round(zmax, 5)},
        "spine": [round(x, 4) for x in spine],
        "vertical_torso": bool(vertical),
        "torso_u": [round(x, 4) for x in u],
        "torso_v": [round(x, 4) for x in v],
        "chest": {k: (round(v, 5) if isinstance(v, float) else v)
                  for k, v in chest.items()},
        "belly": {k: (round(v, 5) if isinstance(v, float) else v)
                  for k, v in belly.items()},
    }


def _mat(name, rgb, rough=0.6):
    import bpy
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return m


def seat_hat(hat_objs, anchors, head_obj=None, embed_frac=0.10,
             hat_path=""):
    """Scale + drop hat part onto the head anchor, then seat by CONTACT.

    Coarse: scale the part by head_w / native brim width, translate its
    native seat to the anchor seat. Refine (the foolproof bit): raycast
    straight down from the hat's bottom rim verts onto the head with a BVH;
    rest the rim on the highest contact. Ears outside the rim are ignored,
    so they can never pull the hat off — this is what makes the seat exact
    on any mesh, not just the dog it was tuned on.
    Returns scale applied.
    """
    import bpy
    from mathutils import Vector
    seat = Vector(anchors["head"]["seat"])
    target_w = anchors["head"]["width"]
    # The skull width this part was authored for: sidecar first (exact),
    # else the brim outer width / 1.15 (brims run ~15% wider than the
    # skull they encircle — standard hat ease). Never p90-p10 over the
    # whole part: cone verts near the centre shrink the estimate and the
    # hat blows up (seen: 1.37× on the dog).
    native_w = None
    if hat_path:
        import json as _json
        sc = Path(str(hat_path)).with_suffix(".json")
        try:
            if sc.exists():
                native_w = float(_json.loads(sc.read_text())["head_w"])
                print(f"hat sidecar {sc.name}: native_w={native_w}")
        except Exception as e:  # noqa: BLE001
            print(f"hat sidecar unreadable ({e}), measuring brim")
            native_w = None
    allv = []
    for o in hat_objs:
        allv.extend([o.matrix_world @ v.co for v in o.data.vertices])
    if native_w is None:
        outer = 0.0
        for o in hat_objs:
            wv = [o.matrix_world @ v.co for v in o.data.vertices]
            outer = max(outer, max(p.x for p in wv) - min(p.x for p in wv))
        native_w = max(outer / 1.15, 1e-6)
        print(f"hat measured: brim outer={outer:.4f} native_w={native_w:.4f}")
    s = target_w / native_w
    # native seat = bottom-centre of the part's lowest ring
    lo = min(allv, key=lambda p: p.z)
    bot = [p for p in allv if p.z <= lo.z + 0.15 * (max(p.z for p in allv) - lo.z + 1e-9)]
    native_seat = Vector((_median([p.x for p in bot]),
                          _median([p.y for p in bot]), lo.z))
    # Rigid part transform, EXACT for any scale: M = T(seat)·S(s)·T(-native).
    # (Naive location-then-scale ordering scales about the object origin,
    # which silently offsets the part whenever s≠1 — seen as a 6-unit
    # miss on the brick at s=196.)
    import bpy
    from mathutils import Matrix, Vector
    M = (Matrix.Translation(Vector(seat))
         @ Matrix.Scale(s, 4)
         @ Matrix.Translation(-native_seat))
    print(f"hat XFORM native_seat={list(native_seat)} s={s:.3f} "
          f"seat={list(seat)}")
    for o in hat_objs:
        pre = (o.matrix_world @ Vector((0, 0, 0)))
        o.matrix_world = M @ o.matrix_world
    bpy.context.view_layer.update()
    for o in hat_objs:
        wv = [o.matrix_world @ v.co for v in o.data.vertices]
        print(f"  {o.name}: worldzmin={(min(p.z for p in wv)):.4f} "
              f"loc={tuple(round(x, 3) for x in o.location)}")
    print(f"hat seat: native_w={native_w:.4f} target_w={target_w:.4f} "
          f"s={s:.3f} seat={list(seat)}")

    # ── density × solidity seating (no BVH needed) ──
    # Score every slice of the head CLUSTER by (vert count × midline
    # fraction): domes win (bulk + solid midline); ears/tufts lose
    # (hollow midline); sparse tips lose (few verts). Proven: the dog
    # scores 4160 at z=0.14 vs ~700-1100 elsewhere — shipped brim 0.141.
    # Slice geometry scales with mesh height (a fixed 10mm window is
    # paper-thin on a 47-unit minifig). Exact on any mesh via numpy.
    if head_obj is not None:
        try:
            import numpy as np
            hw = float(target_w)
            hv = np.array([head_obj.matrix_world @ v.co
                           for v in head_obj.data.vertices])
            hgt = float(anchors.get("height") or 1.0)
            cl = anchors.get("cluster") or {}
            top = float(cl.get("top", 0) or 0)
            bot = float(cl.get("bottom", 0) or 0)
            if top <= bot:
                raise ValueError("empty cluster")
            band = hv[(hv[:, 2] >= bot) & (hv[:, 2] <= top)]
            # midline x from the top 30% (symmetric heads centre at 0)
            hi = hv[hv[:, 2] >= top - 0.30 * hgt]
            cx = float(np.median(hi[:, 0]))
            gx = np.sort(hi[:, 0])
            gscale = float(gx[min(len(gx) - 1, len(gx) * 85 // 100)]
                           - gx[len(gx) * 15 // 100]) or hw
            rim = []
            for o in hat_objs:
                wv = [o.matrix_world @ v.co for v in o.data.vertices]
                rim.extend(wv)
            cur_rim = min(p.z for p in rim)
            full_h = max(p.z for p in rim) - cur_rim + 1e-9
            win = 0.025 * hgt
            scored = []
            z = bot
            while z <= top:
                sub = band[(band[:, 2] >= z - win) &
                           (band[:, 2] <= z + win)]
                n = len(sub)
                mid = float((np.abs(sub[:, 0] - cx) < 0.15 * gscale).mean()) \
                    if n else 0.0
                scored.append((z, n, mid, n * mid))
                z += win
            band_n = len(band)
            scored.sort(key=lambda t: t[3])
            top_score = scored[-1][3] if scored else 0
            wins = [zz for zz, n, m, s in scored
                    if s >= 0.9 * top_score and n >= max(8, 0.02 * band_n)]
            if not wins:
                print("hat seat: no solid slice — keeping coarse seat")
                return s
            best_z = max(wins)
            best_n = max(n for zz, n, m, s in scored if zz == best_z)
            # NOTE: no ring rescale here. Scale comes from anchors head_w
            # (sidecar exact, else brim/1.15); resizing to the seat cross
            # broke the proven dog fit (forehead strip reads narrow but the
            # ring saddles the dome below it). Loose rings on crowns read
            # as helmets — correct for minifigs, acceptable elsewhere.
            rim = []
            for o in hat_objs:
                wv = [o.matrix_world @ v.co for v in o.data.vertices]
                rim.extend(wv)
            cur_rim = min(p.z for p in rim)
            full_h = max(p.z for p in rim) - cur_rim + 1e-9
            # Perch, don't wedge: brim rides ~1/3 skull-width ABOVE the
            # densest dome slice. A wedged brim matches one camera angle
            # but ears swallow the hat in orbitable 3D — the classic "hat
            # inside the head" fitting failure. Real santa-on-dog photos
            # perch high with ears outside the ring.
            rest = best_z + 0.35 * hw
            dz = rest - cur_rim
            # safety: never move more than half the hat height
            dz = max(-0.5 * full_h, min(0.5 * full_h, dz))
            for o in hat_objs:
                o.location = (o.location[0], o.location[1],
                              o.location[2] + dz)
            bpy.context.view_layer.update()
            print(f"hat seat: slice {best_z:.4f} n={best_n} "
                  f"rim {cur_rim:.4f} -> {cur_rim + dz:.4f} (dz={dz:+.4f})")
        except Exception as e:  # noqa: BLE001 — refinement is best-effort
            print(f"hat seat: skipped ({e})")
    return s


def _pp(vals, lo=15, hi=85):
    s = sorted(vals)
    n = len(s)
    if n < 8:
        return 0.0
    return s[min(n - 1, n * hi // 100)] - s[n * lo // 100]


def _torso_frames(body, anchors, gap, thick, n=11):
    """Rings from below-belly to above-chest: (center, r_across, r_up).

    Lateral centre + radii come from p90-p10 EXTENT midpoints per station:
    extent midpoints track the symmetric barrel, while medians follow
    asymmetric mass (a dense leg column skewed rings +10mm off-centre and
    grazed a flank). Vertical extent stays anchors-based (legs exit below
    the hem like real coats). 11 rings follow barrel curves.
    """
    import mathutils
    c, b = anchors["chest"], anchors["belly"]
    h = anchors["height"]
    vertical = anchors.get("vertical_torso", False)
    u = anchors.get("torso_u", [1.0, 0.0])
    v = anchors.get("torso_v", [0.0, 1.0])
    pts = []
    for ob in body:
        mw = ob.matrix_world
        pts.extend([mw @ v.co for v in ob.data.vertices])

    def station(f):
        lx = b["cx"] + (c["cx"] - b["cx"]) * f
        ly = b["cy"] + (c["cy"] - b["cy"]) * f
        cz = b["cz"] + (c["cz"] - b["cz"]) * f
        rv0 = b["rv"] + (c["rv"] - b["rv"]) * f
        if vertical:
            slab = [p for p in pts if abs(p.z - cz) <= 0.04 * h]
            if len(slab) < 16:
                return (lx, ly, cz), 0.03 * h, (rv0 * 1.25 + gap + thick)
            xs = sorted(p.x for p in slab)
            ys = sorted(p.y for p in slab)
            nn = len(xs)
            x0, x1 = xs[nn * 10 // 100], xs[min(nn - 1, nn * 90 // 100)]
            y0, y1 = ys[nn * 10 // 100], ys[min(nn - 1, nn * 90 // 100)]
            ru = max((x1 - x0) / 2 * 1.08 + gap + thick, 1e-4)
            rv = max((y1 - y0) / 2 * 1.08 + gap + thick, 1e-4)
            return ((x0 + x1) / 2, (y0 + y1) / 2, cz), ru, rv
        along = [p.x * v[0] + p.y * v[1] for p in pts]
        c0 = lx * v[0] + ly * v[1]
        slab = [p for p, a in zip(pts, along) if abs(a - c0) <= 0.04 * h]
        if len(slab) < 16:
            return (lx, ly, cz), 0.03 * h, (rv0 * 1.25 + gap + thick)
        au = sorted(p.x * u[0] + p.y * u[1] for p in slab)
        nn = len(au)
        a0, a1 = au[nn * 10 // 100], au[min(nn - 1, nn * 90 // 100)]
        amid = (a0 + a1) / 2
        amid0 = lx * u[0] + ly * u[1]
        cx = lx + (amid - amid0) * u[0]
        cy = ly + (amid - amid0) * u[1]
        ru = max((a1 - a0) / 2 * 1.08 + gap + thick, 1e-4)
        rv = max(rv0 * 1.25 + gap + thick, 1e-4)
        return (cx, cy, cz), ru, rv

    frames = []
    # Jacket coverage: mid-belly hem to neck base (winter-coat length).
    # Never extend below belly: hips splay wider than any torso ring and
    # hind legs need holes (out of scope) — legs exit below the hem.
    for k in range(n):
        f = 0.0 + 1.30 * k / max(n - 1, 1)
        frames.append(station(f))
    return frames


def build_jacket(body, anchors, colour, gap, target=None):
    """Physical winter jacket: lofted torso shell + collar + belly strap.

    The shell is generated from torso-slice ellipses (no body surgery, no
    textures to match), so it fits any measured mesh. Solidify gives it a
    real wall; inner wall clears the body by `gap`. Open at neck and hem.
    """
    import bpy
    import mathutils
    rgb = HARNESS_COLOURS[colour]
    mat = _mat(f"jacket_{colour}", rgb, rough=0.85)
    thick = max(0.75 * gap, 1e-4)
    SEG = 28
    frames = _torso_frames(body, anchors, gap, thick)
    for (cx, cy, cz), ru, rv in frames:
        print(f"jacket frame c=({cx:.4f},{cy:.4f},{cz:.4f}) "
              f"ru={ru:.4f} rv={rv:.4f}")
    vertical = anchors.get("vertical_torso", False)
    u = anchors.get("torso_u", [1.0, 0.0])
    v = anchors.get("torso_v", [0.0, 1.0])

    verts, faces = [], []
    for j, ((cx, cy, cz), ru, rv) in enumerate(frames):
        for i in range(SEG):
            import math as _m
            a = 2 * _m.pi * i / SEG
            if vertical:
                verts.append((cx + ru * _m.cos(a), cy + rv * _m.sin(a), cz))
            else:
                verts.append((cx + ru * _m.cos(a) * (-v[1]),
                              cy + ru * _m.cos(a) * (v[0]),
                              cz + rv * _m.sin(a)))
        if j:
            b0, b1 = (j - 1) * SEG, j * SEG
            for i in range(SEG):
                faces.append((b0 + i, b0 + (i + 1) % SEG,
                              b1 + (i + 1) % SEG, b1 + i))
    mesh = bpy.data.meshes.new("jacket_shell")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    shell = bpy.data.objects.new("jacket_body", mesh)
    bpy.context.scene.collection.objects.link(shell)
    shell.data.materials.append(mat)
    for poly in shell.data.polygons:
        poly.use_smooth = True
    # Outward-facing normals first: the wall then builds strictly outward
    # (offset=+1), so the inner wall IS the clearance surface (gap+ease).
    # Centered walls (offset 0) eat 0.75mm of clearance and graze fur.
    bpy.ops.object.select_all(action="DESELECT")
    shell.select_set(True)
    bpy.context.view_layer.objects.active = shell
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    # wall thickness (outward only: inner wall = clearance surface)
    sol = shell.modifiers.new("wall", "SOLIDIFY")
    sol.thickness = thick
    sol.offset = 1.0
    bpy.ops.object.modifier_apply(modifier=sol.name)

    def station_torus(st, name, tube):
        # Same orientation recipe as the harness rings (verified on the
        # dog: thin in the spine direction): quadruped rings stand up
        # facing the spine; vertical torsos take horizontal rings.
        cx, cy, cz = st["cx"], st["cy"], st["cz"]
        rx, ry = st["ru"] + gap + tube, st["rv"] + gap + tube
        import math as _m
        r0 = (rx + ry) / 2
        if vertical:
            bpy.ops.mesh.primitive_torus_add(
                major_radius=r0, minor_radius=tube,
                major_segments=40, minor_segments=10,
                location=(cx, cy, cz))
            ring = bpy.context.active_object
            ring.scale = (rx / r0, ry / r0, 1.0)
        else:
            ang = _m.atan2(v[0], v[1])
            bpy.ops.mesh.primitive_torus_add(
                major_radius=r0, minor_radius=tube,
                major_segments=40, minor_segments=10,
                location=(cx, cy, cz), rotation=(_m.pi / 2, 0, ang))
            ring = bpy.context.active_object
            ring.scale = (1.0, rx / r0, ry / r0)
        ring.name = name
        ring.data.materials.append(mat)
        return ring

    # collar at the neck end + hem at the belly end + belly strap
    top = {"cx": frames[-1][0][0], "cy": frames[-1][0][1],
           "cz": frames[-1][0][2], "ru": frames[-1][1], "rv": frames[-1][2]}
    hemb = {"cx": frames[0][0][0], "cy": frames[0][0][1],
            "cz": frames[0][0][2], "ru": frames[0][1], "rv": frames[0][2]}
    mid = {"cx": (top["cx"] + hemb["cx"]) / 2,
           "cy": (top["cy"] + hemb["cy"]) / 2,
           "cz": (top["cz"] + hemb["cz"]) / 2,
           "ru": (top["ru"] + hemb["ru"]) / 2,
           "rv": (top["rv"] + hemb["rv"]) / 2}
    parts = [shell,
             station_torus(top, "jacket_collar", thick * 1.5),
             station_torus(hemb, "jacket_hem", thick * 1.2),
             station_torus(mid, "jacket_strap", thick * 1.5)]

    # shrinkwrap trims (collar/hem/strap) onto the body: nearest surface
    # + gap. The shell is NOT shrinkwrapped: vacuum-packing would drag
    # the loft onto ribs and curl the open hems; 11 loft rings + ease
    # give it fair clearance by construction (verified ≥1mm on the dog).
    tgt = target or max(body, key=lambda b: len(b.data.vertices))
    for o in parts[1:]:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(scale=True)
        mod = o.modifiers.new("fit", "SHRINKWRAP")
        mod.wrap_method = "NEAREST_SURFACEPOINT"
        mod.offset = gap * 1.5
        mod.target = tgt
        bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"jacket {colour}: {len(frames)} rings, wall={thick:.4f} gap={gap:.4f}")
    return parts


def build_harness(body, anchors, colour, gap, target=None):
    """Parametric winter harness: chest ring + belly ring + back strap,
    shrinkwrapped to the body so intersection is impossible on any mesh."""
    import bpy
    from mathutils import Vector
    rgb = HARNESS_COLOURS[colour]
    mat = _mat(f"harness_{colour}", rgb, rough=0.8)
    body_objs = list(body)

    def station_ring(st, name, tube=0.004):
        cx, cy, cz = st["cx"], st["cy"], st["cz"]
        rx, ry = st["ru"] + gap + tube, st["rv"] + gap + tube
        if anchors["vertical_torso"]:
            # ring in the horizontal plane
            bpy.ops.mesh.primitive_torus_add(
                major_radius=(rx + ry) / 2, minor_radius=tube,
                major_segments=48, minor_segments=12,
                location=(cx, cy, cz))
        else:
            # ring faces the spine: torus axis along spine direction
            import math
            v = anchors["torso_v"]
            ang = math.atan2(v[0], v[1])
            bpy.ops.mesh.primitive_torus_add(
                major_radius=(rx + ry) / 2, minor_radius=tube,
                major_segments=48, minor_segments=12,
                location=(cx, cy, cz), rotation=(math.pi / 2, 0, ang))
        ring = bpy.context.active_object
        ring.name = name
        # ellipse: scale ring to the slice radii (torus is circular)
        r0 = (rx + ry) / 2
        if anchors["vertical_torso"]:
            ring.scale = (rx / r0, ry / r0, 1.0)
        else:
            ring.scale = (1.0, rx / r0, ry / r0)
        ring.data.materials.append(mat)
        return ring

    rings = [station_ring(anchors["chest"], "harness_chest"),
             station_ring(anchors["belly"], "harness_belly")]

    # back strap: thin box along the top between the rings
    c, b = anchors["chest"], anchors["belly"]
    midx, midy = (c["cx"] + b["cx"]) / 2, (c["cy"] + b["cy"]) / 2
    topz = max(c["cz"] + c["rv"], b["cz"] + b["rv"]) + gap
    length = abs(b["c"] - c["c"]) if anchors["vertical_torso"] else (
        ((b["cx"] - c["cx"]) ** 2 + (b["cy"] - c["cy"]) ** 2) ** 0.5)
    import math
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(midx, midy, topz))
    strap = bpy.context.active_object
    strap.name = "harness_back"
    if anchors["vertical_torso"]:
        strap.scale = (0.012, 0.012, max(length, 0.02) / 2 + 0.01)
    else:
        v = anchors["torso_v"]
        ang = math.atan2(v[0], v[1])
        strap.rotation_euler = (0, 0, ang)
        strap.scale = (0.012, max(length, 0.02) / 2 + 0.01, 0.006)
    strap.data.materials.append(mat)
    parts = rings + [strap]

    # shrinkwrap everything onto the body: nearest surface + gap. Foolproof.
    for o in parts:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(scale=True)
        mod = o.modifiers.new("fit", "SHRINKWRAP")
        mod.wrap_method = "NEAREST_SURFACEPOINT"
        mod.offset = gap
        # target = biggest body mesh
        mod.target = target or max(body_objs,
                                     key=lambda b: len(b.data.vertices))
        bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"harness {colour}: chest girth={c['girth']:.4f} "
          f"belly girth={b['girth']:.4f} gap={gap}")
    return parts


def main() -> int:
    args = parse_args(sys.argv)
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(args.src)))
    body = _body_meshes(bpy.context.scene)
    if not body:
        raise SystemExit("no mesh in source GLB")
    # Measure the UNION of all meshes: on multi-mesh files (brick minifig,
    # badger) the biggest single mesh can be the head, not the body.
    biggest = max(body, key=lambda o: len(o.data.vertices))
    print(f"meshes: {len(body)} biggest={biggest.name} "
          f"verts={len(biggest.data.vertices)}")

    if args.mode == "measure":
        anchors = measure(body)
        print(json.dumps(anchors, indent=2))
        if args.anchors:
            p = Path(args.anchors)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(anchors, indent=2))
            print(f"anchors -> {p}")
        return 0

    # ── compose ──
    if not args.out:
        raise SystemExit("--out required for compose mode")
    anchors = {}
    if args.anchors:
        anchors = json.loads(Path(args.anchors).read_text())
    else:
        anchors = measure(body)
        print("measured fresh (no --anchors given)")
    gap = args.gap if args.gap > 0 else 0.01 * anchors["height"]
    print(f"gap={gap:.5f} (auto from height {anchors['height']:.4f})")

    parts = []
    if args.hat and args.hat != "none":
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(Path(args.hat)))
        hat = [o for o in bpy.context.scene.objects
               if o not in before and o.type == "MESH"]
        if not hat:
            raise SystemExit(f"no mesh in hat part {args.hat}")
        head_obj = max(body, key=lambda o: len(o.data.vertices))
        seat_hat(hat, anchors, head_obj=head_obj, hat_path=args.hat)
        for i, o in enumerate(sorted(hat, key=lambda o: o.name)):
            o.name = ["hat_brim", "hat_cone", "hat_pompom"][min(i, 2)] \
                if len(hat) == 3 else f"hat_{i:02d}"
        parts.extend(hat)

    def torso_target():
        # shrinkwrap target = mesh with most verts in the torso band
        # (global biggest can be the head on multi-mesh files)
        zlo = anchors["zmin"] + TORSO_LO * anchors["height"]
        zhi = anchors["zmin"] + TORSO_HI * anchors["height"]
        scored = []
        for o in body:
            mw = o.matrix_world
            n = sum(1 for v in o.data.vertices
                    if zlo <= (mw @ v.co).z <= zhi)
            scored.append((n, o.name))
        scored.sort(reverse=True)
        print(f"torso-band verts per mesh: {scored}")
        return next(o for o in body if o.name == scored[0][1])

    if args.harness and args.harness != "none":
        colour = args.harness.lower()
        if colour not in HARNESS_COLOURS:
            raise SystemExit(f"unknown harness colour {colour!r}")
        parts.extend(build_harness(body, anchors, colour, gap,
                                   target=torso_target()))

    if args.jacket and args.jacket != "none":
        colour = args.jacket.lower()
        if colour not in HARNESS_COLOURS:
            raise SystemExit(f"unknown jacket colour {colour!r}")
        parts.extend(build_jacket(body, anchors, colour, gap,
                                  target=torso_target()))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in body + parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.export_scene.gltf(
        filepath=str(out),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
    )
    print(f"composed -> {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
