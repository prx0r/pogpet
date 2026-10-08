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
