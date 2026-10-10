"""Subject asset resolver — IDs, not the chaotic upload folder.

Scores face candidates (size, centrality, single-face bonus) and body
candidates from a subject's confirmed photos. The creative model receives
validated asset IDs; if no acceptable full body exists, full_body leaves
allowed_compositions and nobody invents Dad.
"""
from __future__ import annotations

from backend import db


def _box_area(box: list, w: float, h: float) -> float:
    try:
        x, y, bw, bh = (float(v) for v in box)
    except (ValueError, TypeError):
        return 0.0
    if w <= 0 or h <= 0:
        return 0.0
    return (bw * bh) / (w * h)


def _centrality(box: list) -> float:
    try:
        x, y, bw, bh = (float(v) for v in box)
    except (ValueError, TypeError):
        return 0.0
    cx, cy = x + bw / 2, y + bh / 2
    return max(0.0, 1.0 - ((cx - 0.5) ** 2 + (cy - 0.42) ** 2) ** 0.5 * 2)


def resolve(subject_id: str, owner: str) -> dict:
    """Deterministic asset shortlist for one subject."""
    import json as _json
    faces, bodies = [], []
    with db.connect() as c:
        links = c.execute(
            "SELECT photo_id, face_id FROM photo_subjects "
            "WHERE subject_id=? AND confirmed=1", (subject_id,)).fetchall()
        pids = {r["photo_id"] for r in links}
        if not pids:
            rows = c.execute("SELECT id FROM photos WHERE owner=? AND person<>''",
                             (owner,)).fetchall()
            pids = {r["id"] for r in rows}
        for pid in sorted(pids):
            p = c.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()
            if not p:
                continue
            p = dict(p)
            w, h = p.get("width") or 0, p.get("height") or 0
            frows = c.execute("SELECT * FROM photo_faces WHERE photo_id=?",
                              (pid,)).fetchall()
            if frows:
                for f in frows:
                    f = dict(f)
                    try:
                        box = _json.loads(f.get("box") or "[]")
                    except ValueError:
                        box = []
                    area = _box_area(box, w, h)
                    faces.append({"asset_id": pid, "face_id": f["id"],
                                  "face_quality": round(min(1.0, area * 6), 3),
                                  "frontal": round(_centrality(box), 3)})
            if w and h:
                bodies.append({"asset_id": pid,
                               "visibility": "full_body"
                               if h >= w * 1.2 else "waist_up",
                               "quality": round(min(1.0, (w * h) / 1_500_000), 3)})
    faces.sort(key=lambda f: (-f["face_quality"], -f["frontal"]))
    bodies.sort(key=lambda b: (-b["quality"], b["asset_id"]))
    allowed = ["waist_up"]
    if any(b["visibility"] == "full_body" and b["quality"] >= 0.5
           for b in bodies):
        allowed.append("three_quarter")
    if any(b["visibility"] == "full_body" and b["quality"] >= 0.8
           for b in bodies):
        allowed.append("full_body")
    return {"subject_id": subject_id, "face_candidates": faces[:5],
            "body_candidates": bodies[:5],
            "allowed_compositions": allowed}


def shot_type(n_faces: int) -> str:
    if n_faces >= 3:
        return "group"
    if n_faces == 2:
        return "couple"
    return "solo"


def _area_frac(box: list, w: float, h: float) -> float:
    """Face area as frame fraction. Handles normalized and pixel boxes —
    the table holds both (YuNet writes pixels, older rows normalized)."""
    try:
        _x, _y, bw, bh = (float(v) for v in box)
    except (ValueError, TypeError):
        return 0.0
    if bw <= 0 or bh <= 0:
        return 0.0
    if max(abs(_x), abs(_y), abs(bw), abs(bh)) <= 1.001:
        return bw * bh
    denom = (w * h) if w > 0 and h > 0 else 1_000_000.0
    return (bw * bh) / denom


# Label layers the selector cannot query yet (docs/photo-labels.md).
# emotions/framing are answered by backend.photo_labels (vision call, cached).
# Requesting them yields shortfall reasons, never silent wrong photos.
RESERVED_LAYERS = ("occasion", "mesh_fit")   # L5 emotions + framing are live (photo_labels)

_SLOT_OF = {"groups": "group", "couples": "couple", "solos": "solo",
            "faces": "face"}


def select_for_template(owner: str, requires: dict, per_slot: int = 1,
                          exclude: tuple = ()) -> dict:
    """Fill template slots from an owner's labelled photos.

    requires: {groups/faces/solos/couples: int, subjects: [names]? (optional),
    min_face_score: float?, emotions: [happy|laughing|silly|shocked|...]?,
    framing: [close_up|head_shoulders|waist_up|full_body]?}. Returns {"slots": {name: pick}, "hero": pick|None,
    "shortfall": [reasons], "candidates": {slot: [picks...]}}. Picks are
    {photo_id, shot_type, score}. Best-first by face score then recency;
    distinct photos per slot (plus `exclude` photo ids, for multi-slot
    templates filled in sequence). per_slot=N returns the ranked shortlist
    behind each slot (carousel: best first, arrows cycle the rest).
    """
    requires = requires or {}
    shortfall = [f"{k} labelling reserved — vision call not wired"
                 for k in RESERVED_LAYERS if requires.get(k)]
    want = {slot: max(0, int(requires.get(k) or 0))
            for k, slot in _SLOT_OF.items()}
    floor = float(requires.get("min_face_score") or 0.0)
    names = [str(n).strip() for n in (requires.get("subjects") or [])
             if str(n).strip()]

    import json as _json
    cands = {"group": [], "couple": [], "solo": [], "face": []}
    with db.connect() as c:
        photos = {r["id"]: dict(r) for r in c.execute(
            "SELECT * FROM photos WHERE owner=?", (owner,)).fetchall()}
        if names:
            allowed = {r["photo_id"] for r in c.execute(
                "SELECT ps.photo_id FROM photo_subjects ps"
                " JOIN studio_subjects s ON s.id=ps.subject_id"
                " WHERE s.owner=? AND s.name IN (%s) AND ps.confirmed=1"
                % ",".join("?" * len(names)), (owner, *names))}
        else:
            allowed = set(photos)
        for pid in sorted(allowed):
            p = photos.get(pid)
            if not p:
                continue
            frows = [dict(f) for f in c.execute(
                "SELECT * FROM photo_faces WHERE photo_id=?", (pid,)).fetchall()]
            if not frows:
                continue
            scored = []
            for f in frows:
                try:
                    box = _json.loads(f.get("box") or "[]")
                except ValueError:
                    continue
                area = _area_frac(box, p.get("width") or 0,
                                  p.get("height") or 0)
                scored.append({"score": float(f.get("score") or 0),
                               "area": area, "face_id": f.get("id")})
            if not scored:
                continue
            best = max(s["score"] for s in scored)
            if best < floor:
                continue
            st = shot_type(len(scored))
            best_face = max(scored, key=lambda s: (s["score"], s["area"]))
            entry = {"photo_id": pid, "shot_type": st, "score": round(best, 3),
                     "face_id": best_face.get("face_id"),
                     "created_at": p.get("created_at") or 0}
            cands[st].append(entry)
            if st == "solo":
                biggest = max(scored, key=lambda s: s["area"])
                if biggest["area"] >= 0.04:  # close-up: face fills the frame
                    cands["face"].append({**entry, "shot_type": "face"})
    emo = [str(e) for e in (requires.get("emotions") or [])]
    frm = [str(f) for f in (requires.get("framing") or [])]
    if emo or frm:
        # L5: label lazily (one vision call per photo, cached), then keep only
        # photos whose chosen face shows what the template asked for.
        from backend import photo_labels as _pl
        pool = sorted({e["photo_id"] for v in cands.values() for e in v})
        try:
            _pl.ensure(owner, pool)
        except Exception as e:  # noqa: BLE001 - labelling never breaks selection
            shortfall.append(f"labels unavailable: {str(e)[:80]}")
        labs = _pl.for_photos(pool)
        def _ok(e):
            lab = labs.get(e.get("face_id") or "") or {}
            return (_pl.satisfies(lab.get("expression", "unknown"), emo)
                    and (not frm or lab.get("framing") in frm))
        for k in cands:
            cands[k] = [dict(e, labels={x: (labs.get(e.get("face_id") or "") or {}).get(x)
                                        for x in ("expression", "framing")})
                        for e in cands[k] if _ok(e)]
    for k in cands:
        cands[k].sort(key=lambda e: (-e["score"], -(e["created_at"] or 0)))

    slots, used = {}, set(exclude)
    candidates = {}
    for key in ("groups", "faces", "solos", "couples"):
        slot = _SLOT_OF[key]
        filled = len([s for s in slots if s.startswith(slot)])
        avail = [e for e in cands[slot] if e["photo_id"] not in used]
        if want[slot] and per_slot > 1:
            candidates[slot] = [
                {k: e[k] for k in ("photo_id", "face_id", "shot_type", "score")}
                for e in avail[:per_slot]]
        for _i in range(want[slot]):
            pick = next((e for e in avail
                         if e["photo_id"] not in used), None)
            if pick is None:
                shortfall.append(f"{slot} {filled}/{want[slot]}")
                break
            filled += 1
            name = f"{slot}_{filled}"
            slots[name] = pick
            used.add(pick["photo_id"])
    hero = slots.get("face_1") or next(iter(slots.values()), None)
    return {"slots": slots, "hero": hero, "shortfall": shortfall,
            "candidates": candidates}


def product_assets(owner: str, kind: str, product_id: str,
                   per_slot: int = 1) -> dict:
    """Match an owner's labelled photos to one product's tag requirements.

    kind: "prodigi" (PRODIGI_PRODUCTS) or "card" (PERSONAL_CARDS). Products
    without a requires declaration need no photo (mesh/mockup path) and
    return empty slots with no shortfall. Result adds product_id + requires.
    """
    from backend import config as _config
    catalog = (_config.PRODIGI_PRODUCTS if kind == "prodigi"
               else _config.PERSONAL_CARDS)
    spec = catalog.get(product_id) or {}
    requires = spec.get("requires") or {}
    out = select_for_template(owner, requires, per_slot=per_slot)
    out["product_id"] = product_id
    out["requires"] = requires
    return out
