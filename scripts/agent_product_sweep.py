"""Agent product sweep: every line + cards, Dad profile, no spend.

Walks each STUDIO_LINES entry the way Hark would (public paths where they
exist, keyed calls otherwise — same endpoints either way):
  quick_map → studio item → personalise → design validate → design base →
  gift_pack → reserve order (fulfil NEVER true)
plus cards: templates → save → preview → reserve.
Soon lines must 409 honestly. Run: python3 scripts/agent_product_sweep.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config, db  # noqa: E402

tmp = tempfile.TemporaryDirectory()
root = Path(tmp.name)
_patches = [patch.object(config, 'DATA', root),
            patch.object(config, 'DB_PATH', root / 't.db'),
            patch.object(config, 'LOCAL_TMP', root / 'tmp'),
            patch.object(config, 'LOCAL_MESH', root / 'meshes'),
            patch.object(config, 'UPLOAD_DIR', root / 'uploads')]
for _p in _patches:
    _p.start()
db.init()
import backend.cards as card_api  # noqa: E402
card_api.init()

from backend.server import app  # noqa: E402

OWNER = "sweep_dad"
c = app.test_client()
H = {'X-API-Token': config.API_TOKEN, 'X-Owner-Sig': config.sign_owner(OWNER)}


def post(path, body):
    b = dict(body or {})
    b.setdefault("owner", OWNER)
    r = c.post("/api" + path, json=b, headers=H)
    return r.status_code, r.json


def get(path):
    r = c.get("/api" + path, query_string={"owner": OWNER}, headers=H)
    return r.status_code, r.json


results = []
# Dad profile: subject + interests (mesh-free, as specced)
with db.connect() as _c:
    from backend import subjects as _sub
    try:
        from backend import studio_library as _sl
        _c.executescript(_sl.SCHEMA)
    except Exception:  # noqa: BLE001
        pass
    s = _sub.create_subject(_c, OWNER, "Dad")
    _sub.set_profile(_c, OWNER, s["id"], relationship="dad", birthday="06-15",
                     profile={"interests": ["golf"], "humour": {"dry": 0.8}})

fails = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    if not cond:
        fails.append(f"{name}: {detail}")


# 1. quick_map finds lines for a dad-golf brief
sc, qm = post("/quick/map", {"text": "croc jibbitz for my dad, loves golf"})
check("quick_map ok", sc == 200 and qm.get("ok"), f"http={sc}")
got = {m["id"] for m in (qm.get("matches") or [])}
check("quick_map finds croc+golf", {"croc_tag", "golf_marker"} <= got, sorted(got)[:6])

# Dad photo (synthetic): unlocks photo-bound paths for the sweep
from PIL import Image, ImageDraw
import io as _io
img = Image.new("RGB", (800, 1000), "#f4e8cd")
_dd = ImageDraw.Draw(img)
_dd.rectangle((70, 150, 730, 850), fill=(50, 80, 110))
_dd.ellipse((260, 190, 540, 470), fill="#dfb295")
_buf = _io.BytesIO()
img.save(_buf, "JPEG")
_buf.seek(0)
r = c.post("/api/photos", data={"owner": OWNER, "photo": (_buf, "dad.jpg")},
           headers=H)
PHOTO_ID = r.json["photo"]["id"] if r.status_code == 200 else ""
check("dad photo upload", bool(PHOTO_ID), f"http={r.status_code}")

# 2. per-line sweep
sc, studio = get("/products/studio")
items = {i["id"]: i for i in (studio.get("items") or [])}
for lid, spec in config.STUDIO_LINES.items():
    live = spec.get("status") == "live"
    it = items.get(lid)
    check(f"{lid} listed", it is not None, "missing from studio")
    # personalise (line-appropriate coat: mesh lines take coats, reference don't)
    coats = ((spec.get("assets") or {}).get("coats") or ["none"])
    coat = "golden" if "golden" in [co.get("id", co) if isinstance(co, dict) else co
                                    for co in coats] else "none"
    sc, p = post("/products/personalise", {"line": lid, "coat": coat})
    if live and spec.get("fulfilment") != "digital":
        check(f"{lid} personalise", sc == 200 and p.get("ok"), f"http={sc} {str(p.get('error', ''))[:60]}")
    else:
        check(f"{lid} personalise", sc in (200, 409), f"http={sc}")
    # design validate with contract dims
    contract = spec.get("design_contract") or {}
    dims = contract.get("envelope_mm") or None
    sc, v = post("/design/validate", {"line": "nope"})
    check("validate unknown line lists ids", sc == 400 and "croc_tag" in v.get("error", ""))
    body = {"line": lid, "material": contract.get("material") or "PLA"}
    if dims:
        body["dims_mm"] = dims
    sc, v = post("/design/validate", body)
    check(f"{lid} validate", sc == 200 and v.get("ok"), f"http={sc}")
    # design base
    r = c.get(f"/api/design/base/{lid}", query_string={"owner": OWNER}, headers=H)
    if live and (spec.get("personalization") or {}).get("method") in ("emboss", "relief"):
        check(f"{lid} base served", r.status_code == 200, f"http={r.status_code}")
    # gift pack with exact line
    sc, g = post("/gift-packs", {"budget_cents": 5000, "line": lid,
                                 "recipient": "Dad", "occasion": "birthday"})
    if live:
        check(f"{lid} gift pack", sc == 200 and g.get("ok"), f"http={sc} {str(g.get('error', ''))[:60]}")
    # reserve (never fulfil)
    sc, o = post("/products/order", {"line": lid, "qty": 1})
    if live:
        check(f"{lid} reserve", sc == 200 and o.get("ok"), f"http={sc} {str(o.get('error', ''))[:60]}")
    else:
        check(f"{lid} soon refuses order", sc == 409, f"http={sc}")

# 3. cards: templates → save (photo + typography) → preview
sc, t = get("/cards/templates")
check("card templates", sc == 200 and len(t.get("templates", [])) >= 5, f"http={sc}")
sc, d = post("/cards/designs", {"spec": {"template": "portrait", "format": "5x7",
                                         "headline": "Happy birthday Dad",
                                         "photos": [{"photo_id": PHOTO_ID,
                                                     "crop": [0, 0, 1, 1],
                                                     "focus": [.5, .5]}]}})
check("card save", sc == 200 and d.get("design", {}).get("id"), f"http={sc} {str(d)[:100]}")
if d.get("design", {}).get("id"):
    did, rev = d["design"]["id"], d["design"]["revision"]
    sc, rj = post(f"/cards/{did}/render", {"revision": rev, "kind": "preview"})
    check("card preview", sc == 200, f"http={sc}")

# 4. gift pack variants for Dad
sc, g = post("/gift-packs", {"budget_cents": 2500, "recipient": "Dad"})
check("gift pack open brief", sc == 200 and g.get("pack", {}).get("physical"), f"http={sc}")

print(f"\n{sum(1 for _, ok, _ in results if ok)}/{len(results)} checks passed")
for name, ok, detail in results:
    if not ok:
        print("FAIL", name, detail)
sys.exit(1 if fails else 0)
