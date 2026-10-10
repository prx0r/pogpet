"""Steps 1-2: index the uploaded photos, then cast a template from them.

Reuses the backend's YuNet detector + SFace embedder (backend/faces.py) when it
runs inside the server; standalone it loads the same ONNX models via cv2.
"""
from __future__ import annotations
from dataclasses import dataclass, field

SHOTS = ("solo", "full_body", "couple", "group", "expressive", "pet")


@dataclass
class Face:
    box: tuple            # x, y, w, h in px
    score: float
    vec: list | None      # SFace 128-d, L2-normalised
    who: str | None = None  # subject id when matched
    expr: float = 0.0     # mouth-open / eyes-wide score 0..1


@dataclass
class Photo:
    id: str
    w: int
    h: int
    faces: list[Face] = field(default_factory=list)
    pets: int = 0
    sharp: float = 0.0    # variance of Laplacian on the face crops
    shots: set = field(default_factory=set)


def classify(p: Photo) -> set:
    big = [f for f in p.faces if f.box[2] * f.box[3] >= 0.004 * p.w * p.h and f.box[2] >= 60]
    s = set()
    if p.pets and not big:
        s.add("pet")
    if len(big) == 1:
        f = big[0]
        s.add("solo")
        if f.box[3] < 0.18 * p.h and f.box[1] < 0.35 * p.h:
            s.add("full_body")          # small head high in the frame: body visible
        if f.expr >= 0.6:
            s.add("expressive")
    elif len(big) == 2:
        s.add("couple")
        if any(f.expr >= 0.6 for f in big):
            s.add("expressive")
    elif 3 <= len(big) <= 6:
        s.add("group")
    return s


def match(faces: list[Face], subjects: dict[str, list[list]], thresh: float = 0.36) -> None:
    """Label faces with the subject whose tagged embeddings are closest (SFace cosine)."""
    from math import fsum
    cos = lambda a, b: fsum(x * y for x, y in zip(a, b))
    for f in faces:
        if not f.vec:
            continue
        best, who = thresh, None
        for sid, vecs in subjects.items():
            s = max((cos(f.vec, v) for v in vecs), default=0)
            if s > best:
                best, who = s, sid
        f.who = who


def cast(template: dict, photos: list[Photo], hero: str, others: dict | None = None) -> dict | None:
    """Pick reference photos for each cast role, or None when the template can't be cast.

    Returns {"refs": [photo ids, best first], "roles": {...}}. A template with no
    castable photo is simply not offered: never a collage fallback.
    """
    roles, refs = {}, []
    spec = template["cast"]
    for role, r in spec.items():
        want = r.get("from", [])
        pool = [p for p in photos if p.shots & set(want)]
        if role == "hero" or role == "pet":
            pool = [p for p in pool if any(f.who == hero for f in p.faces)] or (pool if role == "pet" else [])
            if r.get("prefer"):
                pool.sort(key=lambda p: r["prefer"] not in p.shots)
        elif r.get("with") == "hero":
            pool = [p for p in pool if any(f.who == hero for f in p.faces)]
            if not r.get("unnamed_ok"):
                pool = [p for p in pool if all(f.who for f in p.faces)]
            n = r.get("min", 1)
            pool = [p for p in pool if len(p.faces) - 1 >= n]
        else:  # whole family / unnamed group
            lo, hi = r.get("min", 1), r.get("max", 6)
            pool = [p for p in pool if lo <= len(p.faces) <= hi]
        if not pool:
            return None
        pool.sort(key=lambda p: -p.sharp)
        roles[role] = pool[0].id
        refs += [p.id for p in pool[: r.get("refs_max", 1)]]
    # extra solo crops of the hero always help likeness in group scenes
    solos = [p.id for p in sorted(photos, key=lambda p: -p.sharp)
             if "solo" in p.shots and any(f.who == hero for f in p.faces)]
    for pid in solos:
        if len(refs) >= 4:
            break
        if pid not in refs:
            refs.append(pid)
    return {"roles": roles, "refs": list(dict.fromkeys(refs))[:4]}


def index_image(pid: str, path: str) -> Photo:
    """Standalone indexer (the server uses backend.faces for the same thing)."""
    import cv2, numpy as np
    from pathlib import Path
    bgr = cv2.imread(path)
    h, w = bgr.shape[:2]
    p = Photo(pid, w, h)
    models = Path(__file__).parent / "models"
    det = cv2.FaceDetectorYN_create(str(models / "face_detection_yunet_2023mar.onnx"), "", (w, h), 0.6)
    rec = cv2.FaceRecognizerSF_create(str(models / "face_recognition_sface_2021dec.onnx"), "")
    _, rows = det.detect(bgr)
    for row in (rows if rows is not None else []):
        v = rec.feature(rec.alignCrop(bgr, row)).ravel()
        v = (v / np.linalg.norm(v)).tolist()
        x, y, fw, fh = map(int, row[:4])
        crop = cv2.cvtColor(bgr[max(y, 0):y + fh, max(x, 0):x + fw], cv2.COLOR_BGR2GRAY)
        p.sharp = max(p.sharp, float(cv2.Laplacian(crop, cv2.CV_64F).var()) if crop.size else 0)
        # crude expression: mouth corners far apart relative to eye distance
        le, re_, _, ml, mr = row[4:14].reshape(5, 2)
        expr = min(1.0, max(0.0, (np.linalg.norm(mr - ml) / max(np.linalg.norm(re_ - le), 1) - 0.8) / 0.5))
        p.faces.append(Face((x, y, fw, fh), float(row[14]), v, expr=float(expr)))
    p.shots = classify(p)
    return p
