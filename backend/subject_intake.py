"""Subject intake: any person, pet or character -> a subject with tagged photos,
ready for product_art.make_all. Used by the CLI (scripts/make_products.py), REST
(POST /api/subjects/intake) and MCP (oddhobb_subject_add); zero per-subject code.

    add_subject(app, owner, name, sources, kind="person", relationship="", interests=())

Every photo goes through the real upload route (POST /api/photos: intake checks,
storage, YuNet face detection at upload), then ONE confirmation tag per subject,
exactly what the UI asks the customer to tap:

  person   the largest face in the first photo with exactly one face (else the
           largest face anywhere); photo_select finds them in the rest by SFace likeness
  pet / character
           a detected face is tagged the same way; a photo with no detectable face is
           linked at photo level (face_id ""), which photo_select treats as "this whole
           image is them" and gives a subject region from the image itself, so one or a
           few character images are enough

sources: local files, directories (images inside, sorted), http(s) URLs, or raw
bytes (name, data) tuples, or existing photo ids ("pho_...") of the same owner.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

KINDS = ("person", "pet", "character")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".gif"}
MAX_PHOTOS = 40


class IntakeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def expand_sources(sources) -> list:
    """[(name, bytes) | ("photo_id", pid)] from paths, dirs, urls, bytes, photo ids."""
    out = []
    for s in sources or []:
        if isinstance(s, tuple) and len(s) == 2:
            out.append(s)
            continue
        s = str(s).strip()
        if not s:
            continue
        if s.startswith("pho_"):
            out.append(("photo_id", s))
        elif s.startswith(("http://", "https://")):
            req = urllib.request.Request(s, headers={"User-Agent": "oddhobb-intake/1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                out.append((os.path.basename(s.split("?")[0]) or "photo.jpg", r.read()))
        else:
            p = Path(s).expanduser()
            if p.is_dir():
                for f in sorted(p.iterdir()):
                    if f.suffix.lower() in IMAGE_EXT and f.is_file():
                        out.append((f.name, f.read_bytes()))
            elif p.is_file():
                out.append((p.name, p.read_bytes()))
            else:
                raise IntakeError(f"no such photo source: {s}")
    if not out:
        raise IntakeError("give at least one photo (file, folder, URL or photo id)")
    if len(out) > MAX_PHOTOS:
        raise IntakeError(f"at most {MAX_PHOTOS} photos per intake")
    return out


def _headers(owner: str) -> dict:
    from backend import config
    return {"X-API-Token": config.API_TOKEN, "X-Owner-Sig": config.sign_owner(owner)}


def add_subject(app, owner: str, name: str, sources, *, kind: str = "person", relationship: str = "",
                interests=(), subject_id: str = "") -> dict:
    """Create (or extend, with subject_id) a subject and register + tag its photos."""
    from backend import db
    from backend import subjects as S
    kind = (kind or "person").lower()
    if kind not in KINDS:
        raise IntakeError(f"kind must be one of {KINDS}")
    name = str(name or "").strip()[:80]
    if not name and not subject_id:
        raise IntakeError("name is required")
    items = expand_sources(sources)
    cli = app.test_client()
    H = _headers(owner)
    from backend import studio_library as SL
    SL.init()
    with db.connect() as c:
        S.ensure_tables(c)
        if subject_id:
            sub = S.get_subject(c, owner, subject_id)
            if not sub:
                raise IntakeError("Unknown subject_id", 404)
        else:
            sub = S.create_subject(c, owner, name, kind)
        if relationship or interests:
            S.set_profile(c, owner, sub["id"], relationship=relationship,
                          profile={"name": sub.get("name") or name, "relationship": relationship,
                                   "interests": list(interests or []), "kind": kind})
    sid = sub["id"]
    photos, errors = [], []
    for fname, data in items:
        if fname == "photo_id":
            with db.connect() as c:
                row = c.execute("SELECT id FROM photos WHERE id=? AND owner=?", (data, owner)).fetchone()
            if row:
                photos.append(row["id"])
            else:
                errors.append({"source": data, "error": "photo not found"})
            continue
        import io
        r = cli.post("/api/photos", data={"owner": owner, "photo": (io.BytesIO(data), fname)},
                     headers=H, content_type="multipart/form-data")
        body = r.get_json(silent=True) or {}
        if r.status_code == 200 and body.get("ok"):
            photos.append(body["photo"]["id"])
        else:
            errors.append({"source": fname, "error": body.get("error") or f"HTTP {r.status_code}"})
    photos = list(dict.fromkeys(photos))
    if not photos:
        raise IntakeError("none of the photos could be registered: " + json.dumps(errors)[:300], 422)
    tags = _tag(owner, sid, kind, photos)
    return {"ok": True, "subject": {"id": sid, "name": sub.get("name") or name, "kind": kind,
                                    "relationship": relationship},
            "photos": photos, "tags": tags, "errors": errors,
            "next": f"make_all / POST /api/products/make {{subject_id: {sid!r}, product_id: 'all'}}"}


def _faces(pid: str) -> list:
    from backend import db
    with db.connect() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM photo_faces WHERE photo_id=?", (pid,))]
    out = []
    for r in rows:
        try:
            b = json.loads(r["box"])
            out.append({"id": r["id"], "box": b, "area": float(b[2]) * float(b[3])})
        except Exception:
            continue
    return out


def _link(pid: str, sid: str, face_id: str, provenance: str):
    from backend import db
    with db.connect() as c:
        c.execute("INSERT OR IGNORE INTO photo_subjects (photo_id,subject_id,face_id,confirmed,provenance)"
                  " VALUES (?,?,?,1,?)", (pid, sid, face_id, provenance))
        c.execute("UPDATE photo_subjects SET confirmed=1 WHERE photo_id=? AND subject_id=?", (pid, sid))
        c.commit()


def _tag(owner: str, sid: str, kind: str, photos: list) -> list:
    """One confirmed face tag (the anchor); pets/characters also tag faceless photos."""
    from backend import studio_library as SL
    SL.init()
    faces = {pid: _faces(pid) for pid in photos}
    tags = []
    solo = [pid for pid in photos if len(faces[pid]) == 1]
    anyf = [pid for pid in photos if faces[pid]]
    anchor = solo[0] if solo else (max(anyf, key=lambda p: max(f["area"] for f in faces[p])) if anyf else None)
    if anchor:
        f = max(faces[anchor], key=lambda f: f["area"])
        _link(anchor, sid, f["id"], "intake-anchor")
        tags.append({"photo_id": anchor, "face_id": f["id"], "how": "anchor face: the one the selector matches"})
    if kind in ("pet", "character"):
        for pid in photos:
            if not faces[pid]:
                _link(pid, sid, "", "intake-whole-image")
                tags.append({"photo_id": pid, "face_id": "", "how": "no detectable face: whole image is them"})
    if not tags:
        # a person with no detectable face anywhere: still link, the selector will say why it can't use them
        for pid in photos:
            _link(pid, sid, "", "intake-unverified")
            tags.append({"photo_id": pid, "face_id": "", "how": "no face found (selector will reject with a reason)"})
    return tags
