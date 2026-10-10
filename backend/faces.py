"""Face embeddings + identity suggestions — assembled from portable parts.

Not rewritten: detection is YuNet (already in `assets/face/`, loaded like
`backend/cards.py`), embeddings are SFace/128-d via OpenCV (no new pip
deps — PhotoPrism ships sface as its preferred model for new libraries),
clustering thresholds follow PhotoPrism's sface calibration, and the
incremental suggest-not-confirm flow mirrors Immich (strangers wait as
outliers; a person forms once enough faces agree).

Privacy contract (matches `backend/studio_library.py`): embeddings are a
suggestion signal only. Identity links (`photo_subjects.confirmed`) are
created by explicit user confirm — never by a similarity score, never by
an image hash.

The SFace model (38MB) is gitignored and fetched on first use.
"""
from __future__ import annotations

from pathlib import Path

from . import config, db

YUNET_PATH = config.ROOT / "assets" / "face" / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = config.ROOT / "assets" / "face" / "face_recognition_sface_2021dec.onnx"
SFACE_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_recognition_sface/face_recognition_sface_2021dec.onnx")

MODEL = "sface128"
DIM = 128

# Cosine-similarity thresholds (PhotoPrism sface calibration, adapted).
# SUGGEST is deliberately loose: suggestions cost the user one confirm tap,
# while a missed link hides the feature. Nothing is ever auto-confirmed —
# STRONG only marks "almost certainly the same person" in the UI.
SUGGEST_MIN = 0.50
STRONG_MIN = 0.75
# A person cluster forms once this many faces mutually agree (Immich's
# core-point idea at its default of 3).
CLUSTER_MIN = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS face_embeddings (
 face_id TEXT PRIMARY KEY REFERENCES photo_faces(id),
 photo_id TEXT NOT NULL REFERENCES photos(id),
 owner TEXT NOT NULL DEFAULT '',
 model TEXT NOT NULL DEFAULT 'sface128',
 dim INTEGER NOT NULL DEFAULT 128,
 vec BLOB NOT NULL,
 created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS face_emb_owner ON face_embeddings(owner);
"""


def ensure_schema() -> None:
    with db.connect() as c:
        c.executescript(SCHEMA)


def _sface_path() -> Path:
    if not SFACE_PATH.is_file():
        import urllib.request as _ul
        SFACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SFACE_PATH.with_suffix(".onnx.download")
        with _ul.urlopen(SFACE_URL, timeout=300) as res, open(tmp, "wb") as fh:
            fh.write(res.read())
        tmp.rename(SFACE_PATH)
    return SFACE_PATH


_recognizer = None


def _recognizer_get():
    """SFace embedder (CPU). None when cv2 or the model is unavailable."""
    global _recognizer
    if _recognizer is not None:
        return _recognizer
    try:
        import cv2 as _cv2
        _recognizer = _cv2.FaceRecognizerSF_create(str(_sface_path()), "")
    except Exception:
        _recognizer = None
    return _recognizer


def detect_boxes(bgr, min_score: float = 0.5) -> list:
    """YuNet face rows for one BGR image. Empty list when unavailable."""
    try:
        from backend.cards import _face_detector_get
        det = _face_detector_get()
    except Exception:
        return []
    if det is None:
        return []
    try:
        h, w = bgr.shape[:2]
        det.setInputSize((w, h))
        _n, raw = det.detect(bgr)
    except Exception:
        return []
    if raw is None:
        return []
    try:
        import numpy as _np
        arr = _np.asarray(raw, dtype=_np.float64).reshape(-1, 15)
    except Exception:
        return []
    return [row for row in arr if float(row[-1]) >= min_score]


def embed_face(bgr, face_row) -> list | None:
    """128-d L2-normalized embedding for one YuNet face row. None on failure."""
    rec = _recognizer_get()
    if rec is None:
        return None
    try:
        import numpy as _np
        # alignCrop needs a float32 (1, 15) row. A float64 row (what YuNet rows
        # become after numpy reshaping in detect_boxes) silently aligns a
        # constant grey patch, so EVERY face embedded to the same vector and
        # every suggestion scored ~1.0. Cast explicitly.
        row = _np.asarray(face_row, dtype=_np.float32).reshape(1, 15)
        aligned = rec.alignCrop(bgr, row)
        feat = rec.feature(aligned)
        v = _np.asarray(feat, dtype=_np.float64).ravel()[:DIM]
        n = float((v ** 2).sum() ** 0.5)
        if n <= 0:
            return None
        return (v / n).tolist()
    except Exception:
        return None


def cosine(a: list, b: list) -> float:
    """Cosine similarity of two normalized vectors. Pure python (tested)."""
    s = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na <= 0 or nb <= 0:
        return 0.0
    return max(-1.0, min(1.0, s / (na * nb)))


def store_embedding(face_id: str, photo_id: str, owner: str, vec: list) -> None:
    import sqlite3 as _s3
    import struct as _st
    import time as _t
    blob = _st.pack(f"{len(vec)}f", *[float(v) for v in vec])
    ensure_schema()
    with db.connect() as c:
        c.execute(
            "INSERT INTO face_embeddings (face_id,photo_id,owner,model,dim,vec,created_at)"
            " VALUES (?,?,?,?,?,?,?) ON CONFLICT(face_id) DO UPDATE SET"
            " vec=excluded.vec, created_at=excluded.created_at",
            (face_id, photo_id, owner, MODEL, len(vec), blob, _t.time()),
        )


def _load_owner_vecs(owner: str) -> list:
    """(face_id, photo_id, vec, subject_id|None, name|None) for one owner."""
    import struct as _st
    ensure_schema()
    out = []
    with db.connect() as c:
        rows = c.execute(
            "SELECT face_id, photo_id, vec, dim FROM face_embeddings WHERE owner=?",
            (owner,)).fetchall()
        for r in rows:
            d = dict(r)
            try:
                vec = list(_st.unpack(f"{d['dim']}f", d["vec"]))
            except Exception:
                continue
            link = c.execute(
                "SELECT s.id, s.name FROM photo_subjects ps"
                " JOIN studio_subjects s ON s.id=ps.subject_id"
                " WHERE ps.face_id=? AND ps.confirmed=1 LIMIT 1",
                (d["face_id"],)).fetchone()
            subj, name = ((""+link["id"], ""+link["name"]) if link
                          else (None, None))
            out.append({"face_id": d["face_id"], "photo_id": d["photo_id"],
                        "vec": vec, "subject_id": subj, "name": name})
    return out


def to_unit(box: list, w: float, h: float) -> list:
    """Normalize a face box to 0-1 units. Pixel boxes (YuNet native) are
    divided by frame dims; already-normalized boxes pass through. The
    photo_faces table contract is normalized (studio_library _box)."""
    try:
        x, y, bw, bh = (float(v) for v in box)
    except (ValueError, TypeError):
        return []
    if max(abs(x), abs(y), abs(bw), abs(bh)) <= 1.001:
        return [x, y, bw, bh]
    if w > 0 and h > 0:
        return [x / w, y / h, bw / w, bh / h]
    return []


def suggest(vec: list, owner: str, exclude_photo: str = "") -> dict:
    """Rank known faces for one embedding. Suggest-only — never confirms.

    Returns {"suggestions": [{subject_id, name, face_id, score}],
    "strong": bool, "new_person": bool}. new_person is True when nothing
    reaches SUGGEST_MIN (Immich-style outlier: waits for more faces).
    """
    scored = []
    for known in _load_owner_vecs(owner):
        if exclude_photo and known["photo_id"] == exclude_photo:
            continue
        s = cosine(vec, known["vec"])
        if s >= SUGGEST_MIN:
            scored.append({"subject_id": known["subject_id"],
                           "name": known["name"],
                           "face_id": known["face_id"],
                           "score": round(s, 3)})
    scored.sort(key=lambda r: -r["score"])
    # Prefer already-named subjects, then strongest face.
    scored.sort(key=lambda r: (r["subject_id"] is None, -r["score"]))
    return {"suggestions": scored[:5],
            "strong": bool(scored and scored[0]["score"] >= STRONG_MIN),
            "new_person": not scored}
