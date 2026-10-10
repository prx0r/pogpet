"""Photo labels L4/L5: expression, framing, look, per face. One vision call per photo.

docs/photo-labels.md reserved L5 (emotion) until a vision call landed. This is
that call. Templates (cards and products) declare what they want, e.g.
`{"expression": ["happy", "laughing"], "framing": ["waist_up", "full_body"]}`,
and the selector matches against these labels instead of guessing.

- Lazy and cached: `ensure(owner, photo_ids)` labels only unlabelled photos,
  so a photo is labelled once and every template reuses it.
- Fail-closed: without OPENROUTER_API_KEY the labels come from a geometric
  heuristic (face size, position and landmarks) with source='heuristic'.
  Heuristic rows never claim an expression they can't see: they return
  'unknown', which matches only templates that don't ask for one.
- Vocabulary is closed (EXPRESSIONS / FRAMINGS / LOOKS). Later layers add
  labels, never rename them.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.request

from backend import db

EXPRESSIONS = ("happy", "laughing", "silly", "shocked", "neutral", "serious",
               "sleepy", "unknown")
FRAMINGS = ("close_up", "head_shoulders", "waist_up", "full_body", "unknown")
LOOKS = ("frontal", "three_quarter", "profile", "unknown")
# expressions that satisfy a broader ask ("happy" is satisfied by "laughing")
IMPLIES = {"happy": {"happy", "laughing"}, "expressive": {"laughing", "silly", "shocked"},
           "funny_face": {"silly", "shocked"}}

SCHEMA = """
CREATE TABLE IF NOT EXISTS photo_labels (
 photo_id TEXT NOT NULL REFERENCES photos(id),
 face_id TEXT NOT NULL DEFAULT '',
 expression TEXT NOT NULL DEFAULT 'unknown',
 framing TEXT NOT NULL DEFAULT 'unknown',
 look TEXT NOT NULL DEFAULT 'unknown',
 eyes_open INTEGER NOT NULL DEFAULT 1,
 sharp REAL NOT NULL DEFAULT 0,
 source TEXT NOT NULL DEFAULT 'heuristic',
 model TEXT NOT NULL DEFAULT '',
 created_at REAL NOT NULL,
 PRIMARY KEY(photo_id, face_id)
);
CREATE INDEX IF NOT EXISTS photo_labels_expr ON photo_labels(expression);
"""


def ensure_schema() -> None:
    with db.connect() as c:
        c.executescript(SCHEMA)


def satisfies(label: str, wanted: list | tuple | None) -> bool:
    """True when `label` meets any wanted expression (empty ask = anything)."""
    if not wanted:
        return True
    ok = set()
    for w in wanted:
        ok |= IMPLIES.get(w, {w})
    return label in ok


# ── heuristic (always available) ──────────────────────────────────────────

def _box(raw, w, h):
    """(x, y, w, h) in px from a stored box (JSON pixels or normalised)."""
    try:
        v = json.loads(raw) if isinstance(raw, str) else list(raw)
        x, y, bw, bh = (float(t) for t in v[:4])
    except Exception:
        return None
    if max(abs(x), abs(y), abs(bw), abs(bh)) <= 1.001:  # normalised rows
        x, y, bw, bh = x * w, y * h, bw * w, bh * h
    return x, y, bw, bh


def heuristic(face_box, w: int, h: int) -> dict:
    b = _box(face_box, w, h)
    if not b or not w or not h:
        return {"expression": "unknown", "framing": "unknown", "look": "unknown"}
    _x, y, bw, bh = b
    frac = bh / h
    if frac >= 0.45:
        framing = "close_up"
    elif frac >= 0.25:
        framing = "head_shoulders"
    elif frac >= 0.12 or y > 0.4 * h:
        framing = "waist_up"
    else:
        framing = "full_body"
    return {"expression": "unknown", "framing": framing, "look": "unknown"}


# ── vision call ───────────────────────────────────────────────────────────

PROMPT = ("You label photos for a personalised-gift printer. For EACH visible human "
          "face, left to right, return JSON: {\"faces\": [{\"x_center\": 0..1, "
          "\"expression\": one of " + json.dumps(EXPRESSIONS[:-1]) + ", "
          "\"framing\": one of " + json.dumps(FRAMINGS[:-1]) + ", "
          "\"look\": one of " + json.dumps(LOOKS[:-1]) + ", \"eyes_open\": true|false}]}. "
          "framing = how much of THAT person's body is in frame. Reply with JSON only.")


def _thumb_b64(path, side: int = 768) -> str:
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((side, side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def vision(path) -> tuple[list, str]:
    """[(x_center, labels)] from the vision model, or ([], '') without a key."""
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return [], ""
    model = os.environ.get("OPENROUTER_VISION_MODEL", "google/gemini-2.5-flash")
    body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 600,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _thumb_b64(path)}}]}],
    }).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json",
                                          "HTTP-Referer": "https://oddhobb.com",
                                          "X-Title": "OddHobb photo labels"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode() or "{}")
        txt = data["choices"][0]["message"]["content"]
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
        faces = json.loads(txt).get("faces") or []
    except Exception:
        return [], ""
    out = []
    for f in faces:
        lab = {"expression": f.get("expression") if f.get("expression") in EXPRESSIONS else "unknown",
               "framing": f.get("framing") if f.get("framing") in FRAMINGS else "unknown",
               "look": f.get("look") if f.get("look") in LOOKS else "unknown",
               "eyes_open": bool(f.get("eyes_open", True))}
        try:
            out.append((float(f.get("x_center")), lab))
        except (TypeError, ValueError):
            continue
    return out, model


def _match_faces(face_rows, w, vis):
    """Pair detected faces (photo_faces) with vision faces by horizontal centre."""
    pairs = {}
    used = set()
    for fr in face_rows:
        b = _box(fr["box"], w or 1, 1000)
        if not b:
            continue
        cx = (b[0] + b[2] / 2) / (w or 1)
        best, bi = 0.18, None
        for i, (vx, _lab) in enumerate(vis):
            if i in used:
                continue
            if abs(vx - cx) < best:
                best, bi = abs(vx - cx), i
        if bi is not None:
            used.add(bi)
            pairs[fr["id"]] = vis[bi][1]
    return pairs


def label_photo(photo: dict, face_rows: list, local_path=None) -> list[dict]:
    """Labels for one photo's faces (no DB writes). local_path enables vision."""
    w, h = int(photo.get("width") or 0), int(photo.get("height") or 0)
    vis, model = (vision(local_path) if local_path else ([], ""))
    paired = _match_faces(face_rows, w, vis) if vis else {}
    out = []
    for fr in face_rows:
        lab = dict(heuristic(fr["box"], w, h))
        src = "heuristic"
        if fr["id"] in paired:
            v = paired[fr["id"]]
            lab.update({k: v[k] for k in ("expression", "look", "eyes_open")})
            if v["framing"] != "unknown":
                lab["framing"] = v["framing"]
            src = "vision"
        out.append({"photo_id": photo["id"], "face_id": fr["id"], "source": src,
                    "model": model if src == "vision" else "", **lab})
    return out


def ensure(owner: str, photo_ids: list[str], fetch=None) -> int:
    """Label every unlabelled photo of `owner` in photo_ids. Returns rows written.

    fetch(photo_row) -> local path (default: cards.local_asset on the r2 key).
    """
    ensure_schema()
    if fetch is None:
        def fetch(p):
            from backend import cards as _cards
            return _cards.local_asset(p["r2_key"])
    n = 0
    with db.connect() as c:
        for pid in photo_ids:
            if c.execute("SELECT 1 FROM photo_labels WHERE photo_id=? LIMIT 1", (pid,)).fetchone():
                continue
            p = c.execute("SELECT * FROM photos WHERE id=? AND owner=?", (pid, owner)).fetchone()
            if not p:
                continue
            p = dict(p)
            faces = [dict(r) for r in c.execute("SELECT * FROM photo_faces WHERE photo_id=?", (pid,))]
            if not faces:
                continue
            try:
                path = fetch(p)
            except Exception:
                path = None
            for row in label_photo(p, faces, path):
                c.execute("INSERT OR REPLACE INTO photo_labels (photo_id,face_id,expression,framing,look,"
                          "eyes_open,sharp,source,model,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (row["photo_id"], row["face_id"], row["expression"], row["framing"],
                           row["look"], int(row.get("eyes_open", True)), 0.0, row["source"],
                           row["model"], time.time()))
                n += 1
        c.commit()
    return n


def for_photos(photo_ids: list[str]) -> dict:
    """{face_id: labels} for the given photos (already labelled ones)."""
    ensure_schema()
    if not photo_ids:
        return {}
    q = ",".join("?" * len(photo_ids))
    with db.connect() as c:
        rows = c.execute(f"SELECT * FROM photo_labels WHERE photo_id IN ({q})", photo_ids).fetchall()
    return {r["face_id"]: dict(r) for r in rows}
