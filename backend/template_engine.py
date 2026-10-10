"""Our template engine — one template definition, three provider adapters.

Gelato fills named layers by fileUrl; Printify pins artwork into
placeholder px; Prodigi takes an order asset URL. All three want the same
thing — the right photo in the right slot — so templates are defined once
here against OUR label tags, and each provider gets a payload builder.
Details per provider: docs/provider-templates.md.

Slot fill: each slot declares label `requires` (+ min_px); the engine
fills slots in order via subject_assets (distinct photos across slots),
best-first. Shortfalls are honest (never a wrong photo). Renderers turn
fills into real previews with PIL, 0 credits.
"""
from __future__ import annotations

TEMPLATES = {
    "wrap_solo": {
        "label": "Wrapping paper — hero face",
        "slots": [
            {"name": "HeroFace",
             "requires": {"solos": 1, "min_face_score": 0.5},
             "min_px": 800},
        ],
        "providers": {
            "prodigi": {"sku": "WRAP-1-50X70"},
            "printify": {"blueprint_id": 848, "print_provider_id": 69,
                         "placeholder": "front", "placeholder_px": [5906, 8268]},
            "gelato": {"layer": "HeroFace"},
        },
    },
    "trio_card": {
        "label": "Comedy trio — two groups, one face",
        "slots": [
            {"name": "Group1", "requires": {"groups": 1}, "min_px": 800},
            {"name": "Group2", "requires": {"groups": 1}, "min_px": 800},
            {"name": "HeroFace",
             "requires": {"faces": 1, "min_face_score": 0.5}, "min_px": 400},
        ],
        "providers": {
            "prodigi": {"sku": "CLASSIC-GRE-FEDR-7X5-BLA"},
            "printify": {"note": "pick a card blueprint in the dashboard"},
            "gelato": {"layer": "HeroFace", "note": "groups via card back"},
        },
    },
    "photo_card": {
        "label": "Photo card — one good solo",
        "slots": [
            {"name": "Hero", "requires": {"solos": 1, "min_face_score": 0.5},
             "min_px": 800},
        ],
        "providers": {
            "prodigi": {"sku": "CLASSIC-GRE-FEDR-7X5-BLA"},
            "printify": {"note": "pick a card blueprint in the dashboard"},
            "gelato": {"layer": "HeroFace"},
        },
    },
}


def fill(owner: str, template_id: str, subjects: list | None = None) -> dict:
    """Fill every slot of a template. Returns {template_id, fills:
    {slot: pick|None}, shortfall: [], providers: {...}}.

    subjects: optional name filter applied to every slot (shopping for
    Cathy → her family). min_px enforced against photo dims (print truth).
    """
    from backend import db as _db
    from backend import subject_assets as _sa
    slot_of = _sa._SLOT_OF
    tmpl = TEMPLATES.get(template_id)
    if not tmpl:
        return {"ok": False, "error": f"unknown template {template_id}"}
    subjects = [str(s).strip() for s in (subjects or []) if str(s).strip()]
    fills, shortfall, used = {}, [], set()
    with _db.connect() as c:
        dims = {r["id"]: (r["width"] or 0, r["height"] or 0) for r in
                c.execute("SELECT id, width, height FROM photos WHERE owner=?",
                          (owner,)).fetchall()}
    for slot in tmpl["slots"]:
        req = dict(slot.get("requires") or {})
        if subjects and "subjects" not in req:
            req = {**req, "subjects": subjects}
        r = _sa.select_for_template(owner, req, per_slot=8,
                                    exclude=tuple(used))
        # Walk the ranked pool (best first): first print-big-enough,
        # unused photo wins. min_px is print truth, not a veto on the pool.
        pool = []
        for key in ("groups", "faces", "solos", "couples"):
            if req.get(key):
                pool.extend(r["candidates"].get(slot_of[key], []))
        if not pool:
            pool = list(r["slots"].values())
        need = slot.get("min_px") or 0
        pick, too_small = None, None
        for e in pool:
            if e["photo_id"] in used:
                continue
            w, h = dims.get(e["photo_id"], (0, 0))
            if min(w, h) >= need:
                pick = e
                break
            too_small = (e, w, h)
        if pick is None:
            if too_small:
                _e, w, h = too_small
                shortfall.append({"slot": slot["name"],
                                  "reason": f"too small for print ({w}x{h})"})
            else:
                shortfall.append({"slot": slot["name"],
                                  "reason": (r["shortfall"] or ["no match"])[0]})
            fills[slot["name"]] = None
            continue
        fills[slot["name"]] = pick
        used.add(pick["photo_id"])
        shortfall.extend({"slot": slot["name"], "reason": s}
                         for s in r["shortfall"])
    return {"ok": True, "template_id": template_id,
            "label": tmpl["label"], "fills": fills, "shortfall": shortfall,
            "providers": _provider_payloads(tmpl, fills)}


def _provider_payloads(tmpl: dict, fills: dict) -> dict:
    """Per-provider fill shapes. Artwork fileUrls stage until rendered
    crops are published (trio composite / face crops via renderers below);
    coordinates (photo/face ids) are exact today."""
    art = {name: ({"photo_id": p["photo_id"], "face_id": p.get("face_id"),
                   "fileUrl": None,
                   "note": "render crop, publish, then fill"}
                  if p else None)
           for name, p in fills.items()}
    prov = tmpl.get("providers", {})
    gel = dict(prov.get("gelato", {}))
    if "layer" in gel:
        first = next((a for a in art.values() if a), None)
        gel["imagePlaceholders"] = [
            {"name": gel["layer"],
             "fileUrl": (first or {}).get("fileUrl"),
             "fitMethod": "slice"}]
        gel["staged"] = True
        gel["staged_reason"] = "needs templateId + published artwork"
    pri = dict(prov.get("printify", {}))
    if "placeholder" in pri:
        pri["artwork"] = art
        pri["staged"] = True
        pri["staged_reason"] = "needs PRINTIFY_SHOP_ID + published artwork"
    else:
        pri["staged"] = True
        pri["staged_reason"] = ("no placeholder mapped — pick a blueprint "
                                "in the dashboard")
    pro = dict(prov.get("prodigi", {}))
    if "sku" in pro:
        pro["artwork"] = art
        pro["renderable"] = True
        pro["renderable_note"] = "our scripts render the order asset"
    return {"gelato": gel, "printify": pri, "prodigi": pro}


def render_trio(owner: str, fills: dict, out_path, headline: str = "The gang"):
    """Real trio composite preview (PIL, 0 credits): two groups on top,
    hero face medallion below. Returns out path."""
    from pathlib import Path as _Path

    from PIL import Image as _Image
    from PIL import ImageDraw as _Draw
    from PIL import ImageFont as _Font

    from backend import db as _db
    from backend import pipeline as _pipeline
    W, H = 1270, 1780
    img = _Image.new("RGB", (W, H), (250, 246, 236))
    d = _Draw.Draw(img)

    def _load(pid):
        with _db.connect() as c:
            p = dict(c.execute("SELECT * FROM photos WHERE id=?",
                               (pid,)).fetchone())
        return _Image.open(_pipeline._local_photo(p)).convert("RGB")

    def _cover(im, box):
        side = min(im.size)
        im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                      (im.width + side) // 2, (im.height + side) // 2))
        return im.resize((box[2] - box[0], box[3] - box[1]),
                         _Image.LANCZOS)

    g1, g2, hf = (fills.get("Group1"), fills.get("Group2"),
                  fills.get("HeroFace"))
    if g1:
        img.paste(_cover(_load(g1["photo_id"]), (60, 60, 610, 560)), (60, 60))
    if g2:
        img.paste(_cover(_load(g2["photo_id"]), (660, 60, 1210, 560)), (660, 60))

    def _font(sz):
        for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            try:
                return _Font.truetype(cand, sz)
            except OSError:
                continue
        return _Font.load_default()

    if hf:
        face = _load(hf["photo_id"])
        side = min(face.size)
        face = face.crop(((face.width - side) // 2,
                          (face.height - side) // 2,
                          (face.width + side) // 2,
                          (face.height + side) // 2)).resize((560, 560),
                                                             _Image.LANCZOS)
        mask = _Image.new("L", (560, 560), 0)
        _Draw.Draw(mask).ellipse([0, 0, 560, 560], fill=255)
        img.paste(face, (355, 640), mask)
    d.text([W // 2, 1330], headline, font=_font(110), fill=(158, 26, 38),
           anchor="mm")
    d.text([W // 2, 1480], "two groups, one legend", font=_font(52),
           fill=(90, 84, 96), anchor="mm")
    out = _Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out
