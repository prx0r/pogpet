"""REST for the photo-grid birthday card. Mounted on the cards blueprint (same
owner resolution, key permissions and CardError handling as /api/cards).

  POST /api/cards/photo-grid/select {subject_id, photos?}       dry run: picks + rejects + reasons
  POST /api/cards/photo-grid {subject_id, photos?, style?, age?, recipient?, message?, sender?}
       -> a new design, revision 1, preview + spread queued. Instant: no generation, no daily cap.
  POST /api/cards/photo-grid {design_id, expected_revision, photos?|style?|age?|swap?|message?...}
       -> the same design, a new immutable revision (swap a photo, change the count or style)

Never builds a legacy collage recipe and never paints: when the photos can't make
a grid the answer is a typed NEEDS_PHOTO with the reasons, nothing else.
"""
from __future__ import annotations

import json
import re
import time
import uuid

from flask import jsonify, request

NEEDS_PHOTO = "NEEDS_PHOTO"
NO_SPARE_PHOTO = "NO_SPARE_PHOTO"

_FEMALE = ("mum", "mom", "mother", "nan", "nana", "gran", "grandma", "granny", "wife",
           "sister", "auntie", "aunt", "daughter", "girlfriend", "niece")
_SPORT = ("football", "golf", "rugby", "cricket", "tennis", "cycling", "running", "boxing",
          "darts", "snooker", "swimming", "skiing", "sailing", "fishing", "gym", "sport")
_STYLE_WORDS = (("classic", "classic"), ("gold", "classic"), ("elegant", "classic"),
                ("bold", "bold"), ("modern", "bold"), ("minimal", "bold"),
                ("playful", "playful"), ("fun", "playful"), ("colourful", "playful"),
                ("colorful", "playful"), ("hand-letter", "playful"),
                ("botanical", "botanical"), ("floral", "botanical"), ("flowers", "botanical"),
                ("pretty", "botanical"), ("sport", "sporty"), ("varsity", "sporty"),
                ("kids", "kids"), ("child", "kids"), ("rainbow", "kids"))


def style_from_words(text: str) -> str:
    t = str(text or "").lower()
    for w, s in _STYLE_WORDS:
        if re.search(r"\b" + re.escape(w), t):
            return s
    return ""


def age_from_words(text: str) -> int:
    t = str(text or "").lower()
    m = re.search(r"\b(\d{1,3})\s*(?:st|nd|rd|th)\b", t) or \
        re.search(r"\b(?:turning|turns|aged?|is)\s+(\d{1,3})\b", t) or \
        re.search(r"\b(\d{1,3})\s+(?:today|years? old)\b", t)
    if m and 0 < int(m.group(1)) <= 120:
        return int(m.group(1))
    return 0


def count_from_words(text: str) -> int:
    t = str(text or "").lower()
    if re.search(r"\b(single|one|1)\s+(big\s+)?(photo|picture|pic|hero)\b|\bhero\b", t):
        return 1
    m = re.search(r"\b(\d{1,2}|four|six|ten)\s*(?:-\s*)?(?:photos?|pictures?|pics?)\b", t)
    if m:
        v = {"four": 4, "six": 6, "ten": 10}.get(m.group(1)) or int(m.group(1))
        return v
    return 0


def pick_style(*, relationship: str = "", interests=(), age: int = 0, tone: str = "",
               words: str = "") -> tuple[str, str]:
    """(style, why). The human's word wins; then age, then who it's for."""
    s = style_from_words(words)
    if s:
        return s, "asked for"
    if age and age < 13:
        return "kids", f"a {age}th birthday"
    rel = (relationship or "").lower()
    if any(w in rel for w in _FEMALE):
        return "botanical", f"for {relationship}"
    if age and age >= 30 and age % 10 == 0:
        return "classic", f"a milestone ({age})"
    if any(any(sp in str(i).lower() for sp in _SPORT) for i in interests or ()):
        return "sporty", "sporty interests"
    if tone in ("funny", "silly"):
        return "playful", "funny tone"
    return "bold", "default"


def default_message(recipient: str, age: int) -> str:
    from backend import photo_grid as PG
    who = recipient or "you"
    if age:
        num, suf = PG.ordinal(age)
        return f"Happy {num}{suf} birthday, {who}! Here's to you and all the moments in these photos."
    return f"Happy birthday, {who}! Here's to you and all the moments in these photos."


def _subject(owner: str, subject_id: str) -> dict:
    from backend import db, subjects as S
    with db.connect() as c:
        r = c.execute("SELECT id, name FROM studio_subjects WHERE id=? AND owner=?",
                      (subject_id, owner)).fetchone()
        if not r:
            return {}
        try:
            S.ensure_tables(c)
            prof = S.profile_for(c, owner, subject_id) or {}
        except Exception:
            prof = {}
    inner = prof.get("profile") or {}
    return {"id": r["id"], "name": r["name"],
            "relationship": prof.get("relationship") or inner.get("relationship", ""),
            "interests": inner.get("interests") or []}


def _slots(selection: dict) -> list:
    return [{"photo_id": p["photo_id"], "crop": p["crop"], "focus": [0.5, 0.5], "cutout": ""}
            for p in sorted(selection["picks"], key=lambda p: p["cell"])]


def proof_views(did: str, rev: int) -> dict:
    from backend import config
    base = (config.PUBLIC_BASE or "https://oddhobb.com").rstrip("/")
    p = f"{base}/backend/api/cards/proof/{did}/r{int(rev)}"
    return {"front": f"{p}/front.png", "inside": f"{p}/inside.png", "back": f"{p}/back.png"}


def save_spec(owner: str, did: str, body_spec: dict, *, expected_revision=None, via="rest") -> tuple[str, int]:
    """Validate + store as a new design (did empty) or a new revision of did."""
    from backend import cards as C
    from backend import db
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        spec = C.validate(owner, body_spec)
        t = time.time()
        if did:
            old = c.execute("SELECT * FROM card_designs WHERE id=?", (did,)).fetchone()
            if old is None or old["owner"] != owner:
                raise C.CardError("Card not found", 404)
            if expected_revision is not None and expected_revision != old["latest"]:
                raise C.CardError("This card changed elsewhere. Reload before saving.", 409)
            prev = c.execute("SELECT spec FROM card_revisions WHERE design_id=? AND revision=?",
                             (did, old["latest"])).fetchone()
            if prev["spec"] == C.json_dump(spec):
                c.commit()
                return did, old["latest"]
            rev = old["latest"] + 1
            c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)", (did, rev, C.json_dump(spec), t))
            c.execute("UPDATE card_designs SET latest=?,updated_at=?,via=? WHERE id=?", (rev, t, via, did))
        else:
            did, rev = "card_" + uuid.uuid4().hex, 1
            c.execute("INSERT INTO card_designs (id,owner,latest,created_at,updated_at,storage_owner,via)"
                      " VALUES (?,?,?,?,?,?,?)", (did, owner, rev, t, t, owner, via))
            c.execute("INSERT INTO card_revisions VALUES (?,?,?,?)", (did, rev, C.json_dump(spec), t))
        c.commit()
    return did, rev


def _int(v, lo, hi, name):
    from backend.cards import CardError
    if v in (None, ""):
        return None
    if isinstance(v, bool):
        raise CardError(f"{name} must be a number", 400)
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise CardError(f"{name} must be a number", 400) from None
    if not lo <= v <= hi:
        raise CardError(f"{name} must be {lo}-{hi}", 400)
    return v


def make(owner: str, b: dict, *, via: str = "rest") -> dict:
    """Create or change a photo-grid card. Returns the API body (raises CardError)."""
    from backend import cards as C
    from backend import photo_grid as PG
    from backend import photo_select as PS
    did = str(b.get("design_id") or "").strip()[:80]
    base, changed = {}, []
    if did:
        base = C.record(owner, did)["spec"]
        if base.get("template") != "photo_grid":
            raise C.CardError("Not a photo-grid card", 400)
        sid = base.get("subject_id", "")
    else:
        sid = str(b.get("subject_id") or "").strip()[:80]
    if not sid:
        raise C.CardError("subject_id is required", 400)
    sub = _subject(owner, sid)
    if not sub:
        raise C.CardError("Unknown person (subject_id)", 404)
    n = _int(b.get("photos"), 1, 10, "photos")
    age = _int(b.get("age"), 0, 120, "age")
    style = str(b.get("style") or "").strip().lower()
    if style and style not in PG.STYLE_IDS:
        raise C.CardError(f"style must be one of {list(PG.STYLE_IDS)}", 400)
    rel = sub.get("relationship") or ""
    recipient = b.get("recipient")
    if recipient is None:
        recipient = base.get("recipient") if base else (rel.title() if rel else sub["name"])
    recipient = str(recipient or "").strip()[:30]
    if age is None:
        age = int(base.get("age") or 0) if base else 0
    why_style = ""
    if not style:
        if base:
            style = base.get("grid_style", "classic")
        else:
            style, why_style = pick_style(relationship=rel, interests=sub.get("interests"), age=age,
                                          tone=str(b.get("tone") or ""), words=str(b.get("request") or ""))
    exclude = list(dict.fromkeys([*(base.get("exclude") or []), *[str(x) for x in (b.get("exclude") or [])]]))
    swap = b.get("swap") or []
    if isinstance(swap, (str, int)):
        swap = [swap]
    cur = [s["photo_id"] for s in base.get("photos") or []]
    cur_grid = int(base.get("grid") or len(cur)) if base else 0
    want = n or cur_grid or 4
    selection = None
    if not base or swap or want != cur_grid:
        fixed, pin = {}, []
        if base and swap:
            out = set()
            for s in swap:
                if isinstance(s, int) or str(s).isdigit():
                    i = int(s) - 1   # 1-based for humans and agents
                    if not 0 <= i < len(cur):
                        raise C.CardError(f"swap: photo {s} doesn't exist (1-{len(cur)})", 400)
                    out.add(cur[i])
                elif str(s) in cur:
                    out.add(str(s))
                else:
                    raise C.CardError(f"swap: {s} isn't on this card", 400)
            exclude = list(dict.fromkeys([*exclude, *out]))
            fixed = {i: p for i, p in enumerate(cur) if p not in out}
            pin = [p for p in cur if p not in out]
            want = cur_grid
            changed.append(f"swapped {len(out)} photo{'s' if len(out) > 1 else ''}")
        elif base:
            pin = cur[:want]
        selection = PS.select_photos(owner, sid, want, "card_grid", pin=pin, exclude=exclude, fixed=fixed)
        if base and not swap and selection.get("ok") and selection["layout"] != cur_grid:
            changed.append(f"{selection['layout']}-photo grid")
        if not selection["ok"]:
            return {"ok": False, "error_code": NEEDS_PHOTO, "error": selection["summary"],
                    "selection": selection}
        if base and swap and selection["layout"] < cur_grid:
            return {"ok": False, "error_code": NO_SPARE_PHOTO,
                    "error": f"No other usable photo of {sub['name']} to swap in. Add another photo first.",
                    "selection": selection}
        slots, grid = _slots(selection), selection["layout"]
    else:
        slots, grid = base["photos"], cur_grid
    if base and style != base.get("grid_style"):
        changed.append(f"{style} lettering")
    if base and age != int(base.get("age") or 0):
        changed.append("age")
    if base and recipient != base.get("recipient", ""):
        changed.append("name")
    msg = b.get("message")
    if msg is None:
        old_msg = ((base.get("inside") or {}).get("right") or {}).get("message", "") if base else ""
        auto = (not base) or old_msg == default_message(base.get("recipient", ""), int(base.get("age") or 0))
        msg = default_message(recipient, age) if auto else old_msg
    elif base:
        changed.append("inside message")
    sender = b.get("sender")
    if sender is None:
        sender = base.get("sender", "") if base else ""
    elif base:
        changed.append("signature")
    spec = {"template": "photo_grid", "format": "5x7", "photos": slots, "grid": grid,
            "grid_style": style, "age": age, "recipient": recipient, "headline": "Happy Birthday",
            "sender": str(sender)[:40], "inside_message": str(msg)[:240],
            "inside": {"right": {"message": str(msg)[:240]}},
            "subject_id": sid, "exclude": exclude[:40]}
    did, rev = save_spec(owner, did, spec, expected_revision=b.get("expected_revision"), via=via)
    jobs = []
    for kind in ("preview", "spread", "export"):
        try:
            jobs.append(C.job_payload(C.enqueue(owner, did, rev, kind)))
        except C.CardError:
            pass
    rec = C.record(owner, did, rev)
    base_v = f"/api/cards/{did}/r{rev}"
    body = {"ok": True, "design": rec, "design_id": did, "revision": rev, "template": "photo_grid",
            "grid": grid, "style": style, "style_label": PG.STYLES[style]["label"], "age": age,
            "recipient": recipient, "instant": True, "counts_against_cap": False,
            "views": {"front": f"{base_v}/preview", "inside": f"{base_v}/inside", "back": f"{base_v}/back",
                      "print_pdf": f"{base_v}/export"},
            "proof_views": proof_views(did, rev), "proof_url": C.proof_url_for(did),
            "card_url": C.card_url_for(did, rev), "product": C.card_price(),
            "jobs": [{k: j[k] for k in ("id", "kind", "status")} for j in jobs],
            "buy": f"POST /api/cards/{did}/checkout"}
    if why_style:
        body["style_reason"] = why_style
    if changed:
        body["changed"] = changed
    if selection:
        body["selection"] = {k: selection[k] for k in ("layout", "requested", "picks", "rejects", "shortfall")}
        for k in ("downgraded_from", "summary"):
            if k in selection:
                body["selection"][k] = selection[k]
    return body


def offer(owner: str, subject_id: str) -> dict:
    """What the photo grid can do for this person right now (for /recommend)."""
    from backend import photo_select as PS
    cands, rejects = PS.candidates(owner, subject_id)
    kept, dups = PS.dedupe(cands)
    usable = len(kept)
    layouts = {str(k): usable >= k for k in PS.CARD_LAYOUTS}
    best = max([k for k in PS.CARD_LAYOUTS if usable >= k and k <= 4] or [0])
    return {"template_id": "photo_grid", "instant": True, "counts_against_cap": False,
            "usable_photos": usable, "layouts": layouts, "best_layout": best,
            "ready": usable > 0,
            "rejects": rejects + dups,
            "make": "POST /api/cards/photo-grid {subject_id, photos, style, age}"}


def attach(bp, CardError):
    @bp.post("/api/cards/photo-grid/select")
    def photo_grid_select():
        from backend import photo_select as PS
        b = request.get_json() or {}
        sid = str(b.get("subject_id") or "").strip()[:80]
        if not sid:
            raise CardError("subject_id is required", 400)
        n = _int(b.get("photos"), 1, 10, "photos") or 4
        return jsonify(PS.select_photos(request.card_owner, sid, n, "card_grid"))

    @bp.post("/api/cards/photo-grid")
    def photo_grid_make():
        b = request.get_json() or {}
        via = "mcp" if request.headers.get("X-MCP", "") == "1" else "rest"
        body = make(request.card_owner, b, via=via)
        return jsonify(body), (200 if body.get("ok") else 422)
