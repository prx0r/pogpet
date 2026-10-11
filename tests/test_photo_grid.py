"""Photo-grid birthday card: selection (dedupe, faces, variety, crops), renderer
(bleed, margins, plates), REST make/change revisions, public proof URLs, MCP
make/change, and no legacy collage fallback. Temp DB, no network, no keys.

Real-photo selection is exercised by the local harness (photo_grid/harness);
here the face detector is replaced by synthetic candidates so the tests run
without models."""
import asyncio
import io
import json
import time

import pytest
from PIL import Image, ImageDraw, ImageFilter

from backend import cards, db
from backend import photo_grid as PG
from backend import photo_select as PS
from tests.test_public_six import _client_call, _no_legacy, _upload, env  # noqa: F401


# ── selection units ────────────────────────────────────────────────────

def _cand(pid, *, score=0.8, shot="solo", phash=0, hist=None, w=1200, h=1600, fg=None, every=None,
          date=0.0, people=None):
    fg = fg or [[0.4, 0.3, 0.2, 0.18]]
    hist = hist or ([1.0] + [0.0] * 47)
    return {"photo_id": pid, "w": w, "h": h, "subject": fg[0], "fg": fg, "all": every or fg,
            "people": people or len(fg), "shot": shot, "sharp": 300.0, "face_px": 300, "phash": phash,
            "hist": hist, "date": date, "score": score,
            "hero_score": score + {"solo": 0.18, "couple": 0.04}.get(shot, 0), "match": "tagged"}


def _textured(seed: int, size=(640, 480)) -> Image.Image:
    import random
    rng = random.Random(seed)
    im = Image.new("RGB", size, (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        d.ellipse((x, y, x + rng.randrange(20, 160), y + rng.randrange(20, 160)),
                  fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    return im


def test_phash_dedupe_keeps_the_better_shot_and_says_why():
    import cv2
    import numpy as np
    a = _textured(1)
    a2 = a.resize((500, 375)).filter(ImageFilter.GaussianBlur(1))   # re-saved / resized copy
    b = _textured(2)
    h = [PS._phash(cv2.cvtColor(np.asarray(x), cv2.COLOR_RGB2GRAY)) for x in (a, a2, b)]
    assert PS.hamming(h[0], h[1]) <= PS.DUP_HASH
    assert PS.hamming(h[0], h[2]) > PS.DUP_HASH
    kept, rej = PS.dedupe([_cand("copy", score=0.7, phash=h[1]), _cand("orig", score=0.9, phash=h[0]),
                           _cand("other", score=0.5, phash=h[2])])
    assert [k["photo_id"] for k in kept] == ["orig", "other"]
    assert rej[0]["photo_id"] == "copy" and "near-duplicate of orig" in rej[0]["reason"]


def test_candidate_rejects_with_reasons():
    vec = [1.0] + [0.0] * 127
    other = [0.0, 1.0] + [0.0] * 126
    def an(faces, w=1600, h=1200):
        return {"w": w, "h": h, "faces": faces, "phash": "0", "hist": [0.0] * 48, "date": 0}
    face = lambda box, sharp=300.0, v=vec: {"box": box, "score": 0.9, "sharp": sharp, "vec": v}
    c, why = PS.candidate("p", an([face([0.4, 0.3, 0.2, 0.25])]), [vec], [], {}, "Dad")
    assert c and c["shot"] == "solo" and why == ""
    assert "isn't in this photo" in PS.candidate("p", an([face([0.4, 0.3, 0.2, 0.25], v=other)]), [vec], [], {}, "Dad")[1]
    assert "blurry" in PS.candidate("p", an([face([0.4, 0.3, 0.2, 0.25], sharp=5.0)]), [vec], [], {}, "Dad")[1]
    assert "too small" in PS.candidate("p", an([face([0.4, 0.3, 0.02, 0.03])]), [vec], [], {}, "Dad")[1]
    bg = an([face([0.1, 0.1, 0.4, 0.5], v=other), face([0.7, 0.2, 0.08, 0.1])])
    assert "background" in PS.candidate("p", bg, [vec], [], {}, "Dad")[1]
    assert "low-res" in PS.candidate("p", an([face([0.4, 0.3, 0.2, 0.25])], 400, 300), [vec], [], {}, "Dad")[1]
    # a confirmed tag wins even without vectors
    c, _ = PS.candidate("p", an([face([0.4, 0.3, 0.2, 0.25], v=None)]), [], [[0.41, 0.31, 0.2, 0.25]], {}, "Dad")
    assert c and c["match"] == "tagged"


def test_variety_hero_is_best_solo_then_new_shots():
    same = [1.0] + [0.0] * 47
    other = [0.0] * 47 + [1.0]
    cs = [_cand("couple_a", score=0.92, shot="couple", hist=same, people=2),
          _cand("couple_b", score=0.91, shot="couple", hist=same, people=2),
          _cand("solo", score=0.85, shot="solo", hist=same),
          _cand("group", score=0.80, shot="group", hist=other, people=4)]
    picked = [c["photo_id"] for c in PS.diverse(cs, 3)]
    assert picked[0] == "solo"                       # hero: the clear solo, not the sharper couple
    assert "group" in picked and picked.count("couple_a") + picked.count("couple_b") == 1


def test_smart_crop_keeps_faces_whole_on_thirds_and_in_bounds():
    W, H = 2048, 1536
    # couple in the middle, a stranger's face sliced at the right
    fg = [[0.30, 0.25, 0.12, 0.16], [0.46, 0.27, 0.12, 0.16]]
    stranger = [0.80, 0.30, 0.06, 0.08]
    for aspect in (1.0, 0.7, 2.0, 0.9):
        cr = PS.smart_crop(W, H, fg, fg + [stranger], aspect, face_frac=0.3)
        x, y, w, h = cr
        assert x >= 0 and y >= 0 and x + w <= 1.00001 and y + h <= 1.00001
        assert abs((w * W) / (h * H) - aspect) < 0.01
        assert PS.cut_faces(cr, fg + [stranger]) == []
        for f in fg:
            assert PS._frac_inside(f, cr) > 0.999
    # lone subject left of centre lands near the left third, eyes in the upper third
    solo = [[0.20, 0.30, 0.10, 0.13]]
    x, y, w, h = PS.smart_crop(W, H, solo, solo, 0.8, face_frac=0.3)
    cx = (0.25 - x) / w
    eye = (0.30 + 0.42 * 0.13 - y) / h
    assert 0.2 < cx < 0.45 and 0.2 < eye < 0.42


def test_layout_geometry_even_margins_and_hero_first():
    for n in PG.GRIDS:
        lay = PG.layout(n)
        cells = lay["cells"]
        assert len(cells) == n
        assert min(c[0] for c in cells) == PG.MARGIN
        assert round(max(c[0] + c[2] for c in cells)) == PG.TRIM[0] - PG.MARGIN
        assert round(max(c[1] + c[3] for c in cells)) == PG.TRIM[1] - PG.MARGIN
        assert cells[0][2] * cells[0][3] == max(c[2] * c[3] for c in cells)   # hero is the biggest
        for i, a in enumerate(cells):                                         # no overlaps
            for b in cells[i + 1:]:
                assert a[0] + a[2] <= b[0] + 0.5 or b[0] + b[2] <= a[0] + 0.5 or \
                    a[1] + a[3] <= b[1] + 0.5 or b[1] + b[3] <= a[1] + 0.5


def test_plates_exist_with_alpha_and_ordinals():
    for st in PG.STYLE_IDS:
        p = PG.plate(st)
        assert p.mode == "RGBA" and p.getchannel("A").getextrema() == (0, 255)
    assert len(PG.STYLE_IDS) <= 6
    assert [PG.ordinal(n)[1] for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 70, 101, 111)] == \
        ["st", "nd", "rd", "th", "th", "th", "th", "st", "nd", "th", "st", "th"]


def _photo_assets(n):
    out, slots = {}, []
    for i in range(n):
        out[f"p{i}"] = _textured(10 + i, (900, 1200)).convert("RGBA")
        slots.append({"photo_id": f"p{i}", "crop": [0, 0, 1, 1200 / 1200], "focus": [0.5, 0.5], "cutout": ""})
    return out, slots


@pytest.mark.parametrize("n,style", [(1, "playful"), (4, "classic"), (6, "bold"), (10, "kids")])
def test_render_print_panel_bleed_white_and_safe(n, style):
    import numpy as np
    assets, slots = _photo_assets(n)
    d = {"template": "photo_grid", "format": "5x7", "photos": slots, "grid": n, "grid_style": style,
         "age": 70, "recipient": "Dad", "sender": "Tom", "inside": {"right": {"message": "Happy birthday"}}}
    img = PG.front(d, assets, 1530, 2160)
    a = np.asarray(img.convert("L"))
    assert a[:30].min() == 255 and a[-30:].min() == 255 and a[:, :15].min() == 255 and a[:, -15:].min() == 255
    ys, xs = np.where(a < 250)
    assert xs.min() - 15 >= 89 and 1500 - (xs.max() - 15) - 1 >= 89 and 2100 - (ys.max() - 30) - 1 >= 89
    assert PG.front(d, assets, 720).size == (720, 1008)
    from backend import card_scenes as S
    assert S.front(d, assets, 720).size == (720, 1008)          # dispatched through the card stack
    assert S.inside(d, 1440).size == (1440, 1008)


# ── REST + MCP integration (synthetic faces, real Flask + render queue) ────

def _subject(env, n=7):
    from backend import subjects as sub
    pids = [_upload(env, "grid") for _ in range(n)]
    with db.connect() as conn:
        s = sub.create_subject(conn, env["owner"], "Chris")
        sub.set_profile(conn, env["owner"], s["id"], relationship="dad", profile={"interests": []})
        conn.commit()
    return s, pids


@pytest.fixture()
def fake_faces(monkeypatch):
    """candidates() without models: every uploaded photo is a distinct solo of the subject."""
    state = {"pids": [], "rejects": []}

    def cands(owner, subject_id):
        out = []
        for i, pid in enumerate(state["pids"]):
            hist = [0.0] * 48
            hist[i % 48] = 1.0
            shot = ["solo", "couple", "group"][i % 3]
            fg = [[0.35, 0.25, 0.2, 0.2]] if shot == "solo" else [[0.2, 0.25, 0.18, 0.18], [0.55, 0.27, 0.18, 0.18]]
            out.append(_cand(pid, score=0.9 - i * 0.03, shot=shot, phash=__import__("random").Random(i).getrandbits(64),
                             hist=hist, w=800, h=1000, fg=fg, people=len(fg)))
        return out, list(state["rejects"])
    monkeypatch.setattr(PS, "candidates", cands)
    return state


def _wait_ready(did, rev, kind="preview", t=60):
    t0 = time.time()
    while time.time() - t0 < t:
        with db.connect() as c:
            r = c.execute("SELECT status,error FROM card_jobs WHERE design_id=? AND revision=? AND kind=?",
                          (did, rev, kind)).fetchone()
        if r and r["status"] in ("ready", "failed"):
            return dict(r)
        time.sleep(0.3)
    return {"status": "timeout"}


def test_rest_make_change_revisions_and_public_proof(env, fake_faces, monkeypatch):
    _no_legacy(monkeypatch)
    s, pids = _subject(env)
    fake_faces["pids"] = pids
    cli, H, o = env["client"], env["headers"], env["owner"]
    r = cli.post("/api/cards/photo-grid", json={"owner": o, "subject_id": s["id"], "photos": 4, "age": 70,
                                                "style": "classic"}, headers=H)
    b = r.get_json()
    assert r.status_code == 200 and b["ok"], b
    assert b["template"] == "photo_grid" and b["grid"] == 4 and b["revision"] == 1
    assert b["counts_against_cap"] is False and b["instant"] is True
    assert all(p["reason"] for p in b["selection"]["picks"]) and b["selection"]["picks"][0]["hero"]
    assert all(p["cut_faces"] == 0 for p in b["selection"]["picks"])
    did = b["design_id"]
    spec = cards.record(o, did, 1)["spec"]
    assert spec["template"] == "photo_grid" and "recipe_id" not in spec
    assert spec["recipient"] == "Dad" and spec["age"] == 70 and spec["headline"] == "Happy Birthday"
    assert _wait_ready(did, 1)["status"] == "ready"
    # public proof faces: no key, no owner
    for face in ("front", "inside", "back"):
        pr = cli.get(f"/api/cards/proof/{did}/r1/{face}.png")
        assert pr.status_code == 200 and pr.mimetype == "image/png", face
        assert Image.open(io.BytesIO(pr.data)).size[0] in (720, 1440)
    assert cli.get(f"/api/cards/proof/{did}/r9/front.png").status_code == 404
    assert b["proof_views"]["front"].endswith(f"/backend/api/cards/proof/{did}/r1/front.png")
    # swap photo 2: new revision, the other three stay in their cells
    cur = [p["photo_id"] for p in spec["photos"]]
    r = cli.post("/api/cards/photo-grid", json={"owner": o, "design_id": did, "expected_revision": 1,
                                                "swap": [2]}, headers=H)
    b2 = r.get_json()
    assert b2["ok"] and b2["revision"] == 2, b2
    new = [p["photo_id"] for p in cards.record(o, did, 2)["spec"]["photos"]]
    assert new[0] == cur[0] and new[2:] == cur[2:] and new[1] != cur[1] and new[1] not in cur
    # count change: 1 hero (keeps the hero), then style change
    b3 = cli.post("/api/cards/photo-grid", json={"owner": o, "design_id": did, "photos": 1}, headers=H).get_json()
    assert b3["revision"] == 3 and b3["grid"] == 1
    assert cards.record(o, did, 3)["spec"]["photos"][0]["photo_id"] == cur[0]
    b4 = cli.post("/api/cards/photo-grid", json={"owner": o, "design_id": did, "style": "bold"}, headers=H).get_json()
    sp4 = cards.record(o, did, 4)["spec"]
    assert b4["revision"] == 4 and sp4["grid_style"] == "bold" and sp4["photos"] == cards.record(o, did, 3)["spec"]["photos"]
    # the swapped-out photo never comes back
    b5 = cli.post("/api/cards/photo-grid", json={"owner": o, "design_id": did, "photos": 6}, headers=H).get_json()
    assert cur[1] not in [p["photo_id"] for p in cards.record(o, did, b5["revision"])["spec"]["photos"]]


def test_rest_downgrades_when_photos_run_short_and_says_so(env, fake_faces):
    s, pids = _subject(env, 5)
    fake_faces["pids"] = pids
    b = env["client"].post("/api/cards/photo-grid", json={"owner": env["owner"], "subject_id": s["id"],
                                                          "photos": 10}, headers=env["headers"]).get_json()
    assert b["ok"] and b["grid"] == 4
    assert b["selection"]["downgraded_from"] == 10 and "Add 5 more" in b["selection"]["summary"]


def test_no_photos_is_typed_needs_photo_never_legacy(env, fake_faces, monkeypatch):
    _no_legacy(monkeypatch)
    s, pids = _subject(env, 2)
    fake_faces["pids"] = []
    fake_faces["rejects"] = [{"photo_id": pids[0], "reason": "blurry (face sharpness 9 < 35)"}]
    with db.connect() as c:
        before = c.execute("SELECT COUNT(*) FROM card_designs").fetchone()[0]
    r = env["client"].post("/api/cards/photo-grid", json={"owner": env["owner"], "subject_id": s["id"]},
                           headers=env["headers"])
    b = r.get_json()
    assert r.status_code == 422 and b["error_code"] == "NEEDS_PHOTO"
    assert b["selection"]["rejects"][0]["reason"].startswith("blurry")
    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM card_designs").fetchone()[0] == before
        # nothing legacy was made: no birthday_* collage revisions exist
        specs = [json.loads(r[0]) for r in c.execute("SELECT spec FROM card_revisions")]
    assert not [x for x in specs if str(x.get("template", "")).startswith("birthday_")]


def test_validate_rejects_bad_grid_specs(env, fake_faces):
    s, pids = _subject(env, 4)
    base = {"template": "photo_grid", "format": "5x7", "grid": 4, "grid_style": "classic",
            "photos": [{"photo_id": p, "crop": [0, 0, 1, 1]} for p in pids]}
    assert cards.validate(env["owner"], base)["grid"] == 4
    for bad in ({"grid": 5}, {"grid_style": "neon"}, {"age": 300}, {"grid": 1},
                {"photos": [{"photo_id": pids[0], "crop": [0, 0, 1, 1]}] * 4}):
        with pytest.raises(cards.CardError):
            cards.validate(env["owner"], {**base, **bad})


def _mcp_call(env):
    real = _client_call(env)

    async def call(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/oddhobb/people"):
            from backend import subjects as sub
            with db.connect() as c:
                rows = c.execute("SELECT id,name FROM studio_subjects WHERE owner=?", (env["owner"],)).fetchall()
            return {"ok": True, "people": [{"subject": {"id": r["id"], "name": r["name"],
                                                        "relationship": "dad"}} for r in rows]}
        return await real(method, path, body, api_key, owner_sig)
    return call


def test_mcp_make_and_change_photo_grid_no_cardgen(env, fake_faces, monkeypatch):
    from backend import mcp_server as M
    from cardgen import engine as E
    _no_legacy(monkeypatch)
    monkeypatch.setattr(E, "start", lambda *a, **k: (_ for _ in ()).throw(AssertionError("cardgen called")))
    s, pids = _subject(env)
    fake_faces["pids"] = pids
    monkeypatch.setattr(M, "_call", _mcp_call(env))
    body = json.loads(asyncio.run(M.oddhobb_make(
        person="Chris", request="birthday card for Dad, he's turning 70", photos=4, style="classic",
        owner=env["owner"]))[0].text)
    assert body["ok"] and body["status"] == "ready", body
    assert body["template"] == "photo_grid" and body["age"] == 70 and body["counts_against_cap"] is False
    assert body["options"][0]["template"] == "photo_grid"
    assert len(body["photos_picked"]) == 4 and body["photos_picked"][0]["hero"]
    assert body["views"]["front"].endswith("/r1/front.png")
    did = body["design_id"]
    ch = json.loads(asyncio.run(M.oddhobb_change(
        design_id=did, instruction="swap photo 3 please", owner=env["owner"]))[0].text)
    assert ch["ok"] and ch["revision"] == 2 and "swapped 1 photo" in ch["changed"], ch
    ch2 = json.loads(asyncio.run(M.oddhobb_change(
        design_id=did, instruction="make it the playful style with ten photos", owner=env["owner"]))[0].text)
    assert ch2["revision"] == 3 and ch2["style"] == "playful" and ch2["grid"] == 6   # 7 photos -> 6-grid
    ch3 = json.loads(asyncio.run(M.oddhobb_change(
        design_id=did, instruction="change the inside message to 'Happy 70th Dad. Lots of love, Tom'",
        owner=env["owner"]))[0].text)
    assert ch3["inside_message"] == "Happy 70th Dad." and ch3["signature"] == "Lots of love, Tom"
    assert ch3["template"] == "photo_grid" and ch3["grid"] == 6


def test_request_words_parse():
    from backend import photo_grid_api as A
    assert A.age_from_words("birthday card for Dad, he's turning 70") == 70
    assert A.age_from_words("his 65th birthday") == 65
    assert A.count_from_words("a 10 photo card") == 10 and A.count_from_words("one big photo") == 1
    assert A.style_from_words("bold modern please") == "bold"
    assert A.pick_style(relationship="mum")[0] == "botanical"
    assert A.pick_style(age=7)[0] == "kids" and A.pick_style(age=70)[0] == "classic"
