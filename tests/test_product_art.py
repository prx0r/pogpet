"""Product pipeline: recipes as data, make_product/make_all for ANY subject with the
same code, exact print sizes, a seamless wrap repeat built from distinct photos,
separate print vs mockup outputs, no magenta, fallbacks, REST + MCP + public proofs.

Temp DB, no network, no keys. The face detector is replaced by synthetic candidates
(as in test_photo_grid) and cutouts use the OpenCV GrabCut segmenter, so the tests
run without the rembg model. Real-photo runs: product_pipeline/harness."""
import asyncio
import io
import json

import numpy as np
import pytest
from PIL import Image

from backend import config, db
from backend import mockup_slots
from backend import photo_select as PS
from backend import product_art as PA
from backend.photo_grid import STYLE_IDS as PG_STYLES
from tests.test_public_six import _client_call, _upload, env  # noqa: F401


# ── fixtures ────────────────────────────────────────────────────────────

def _cand(pid, i):
    hist = [0.0] * 48
    hist[(i * 7) % 48] = 1.0
    shot = ["solo", "couple", "group"][i % 3]
    face = [0.33, 0.19, 0.35, 0.28]          # the synthetic upload's skin ellipse, roughly
    fg = [face] if shot == "solo" else [face, [0.75, 0.6, 0.12, 0.1]]
    return {"photo_id": pid, "w": 800, "h": 1000, "subject": face, "fg": fg[:1], "all": fg,
            "people": 1 if shot == "solo" else 2, "shot": shot, "sharp": 300.0, "face_px": 280,
            "phash": __import__("random").Random(pid).getrandbits(64), "hist": hist, "date": 0.0,
            "score": round(0.9 - i * 0.02, 3), "hero_score": round(0.9 - i * 0.02 + (0.18 if shot == "solo" else 0), 3),
            "match": "tagged"}


@pytest.fixture()
def family(env, monkeypatch):
    """Two different people in one owner's library, with disjoint photos."""
    from backend import subjects as sub
    monkeypatch.setenv("ODD_SEGMENTER", "grabcut")
    people = {}
    with db.connect() as c:
        for name, rel, n in (("Chris", "father", 7), ("Cathy", "mother", 5)):
            s = sub.create_subject(c, env["owner"], name)
            sub.set_profile(c, env["owner"], s["id"], relationship=rel,
                            profile={"name": name, "relationship": rel, "interests": []})
            c.commit()
            people[name] = {"id": s["id"], "n": n}
    from tests import test_public_six as T6
    seq0 = T6._SEQ[0]
    for name, p in people.items():
        p["pids"] = [_upload(env, tag=name) for _ in range(p["n"])]
    T6._SEQ[0] = seq0          # the shared synthetic-upload counter must not run out for other tests
    by_sid = {p["id"]: p["pids"] for p in people.values()}

    def cands(owner, subject_id):
        return [_cand(pid, i) for i, pid in enumerate(by_sid.get(subject_id, []))], []
    monkeypatch.setattr(PS, "candidates", cands)
    # the synthetic "faces" are flat ellipses: the face-visibility gate is tested on its own below
    from backend import cutout as CO
    monkeypatch.setattr(CO, "quality", lambda cut: {"ok": True, "reason": ""})
    env["people"] = people
    env["by_sid"] = by_sid
    return env


def _no_magenta(path) -> bool:
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    mag = (a[..., 0] > 225) & (a[..., 1] < 50) & (a[..., 2] > 225)
    return int(mag.sum()) == 0


# ── recipes ─────────────────────────────────────────────────────────────

def test_recipes_load_and_validate():
    d = PA.recipes()
    assert PA.validate_recipes(d) == []
    assert set(d["products"]) == set(config.PRODIGI_PRODUCTS)          # every product has a recipe
    assert set(d["products"]) <= set(mockup_slots.kit_ids())           # ...and a scene kit
    kinds = {r["kind"] for r in d["products"].values()}
    assert {"grid", "sticker_round", "mug_band", "wrap_pattern"} <= kinds
    for pid, r in d["products"].items():
        assert r["aspect_source"] in ("verified", "assumed", "live")
        assert PA.recipe_version(pid).startswith(d["version"] + "." + pid)
    # validation catches bad data
    bad = json.loads(json.dumps(d))
    bad["products"]["poster"]["kind"] = "painted"
    bad["products"]["tote"]["layouts_by_count"]["4"] = "g6"
    bad["products"]["mug"]["print_px"] = [0, "x"]
    errs = " | ".join(PA.validate_recipes(bad))
    assert "poster: kind" in errs and "tote: layout g6 has 6 cells" in errs and "mug: print_px" in errs


def test_print_size_falls_back_to_recipe_without_a_key(env):
    s = PA.print_size("postcard")
    assert s["px"] == (1748, 1240) and s["aspect_source"] == "assumed"
    s = PA.print_size("wrapping_paper")
    assert s["px"] == (2952, 4133) and s["aspect_source"] == "verified"


def test_print_size_uses_live_print_area_when_cached(env):
    (config.DATA / "prodigi_templates.json").write_text(json.dumps(
        {"CLASSIC-GRE-FEDR-7X5-BLA": {"sku": "x", "horizontalResolution": 6120, "verticalResolution": 2160}}))
    s = PA.print_size("greeting_card")
    assert s["px"] == (1530, 2160) and s["aspect_source"] == "live"     # one of four panels


# ── make_product: same code, any subject ────────────────────────────────

def test_two_subjects_same_code_different_picks(family, tmp_path):
    ch, ca = family["people"]["Chris"], family["people"]["Cathy"]
    a = PA.make_product(family["owner"], ch["id"], "poster", age=70, out_dir=tmp_path / "a")
    b = PA.make_product(family["owner"], ca["id"], "poster", out_dir=tmp_path / "b")
    pa, pb = {p["photo_id"] for p in a["picks"]}, {p["photo_id"] for p in b["picks"]}
    assert pa and pb and not (pa & pb)
    assert pa <= set(ch["pids"]) and pb <= set(ca["pids"])
    assert a["recipe_version"] == b["recipe_version"]                  # one recipe, one code path
    assert a["recipient"] == "Dad" and b["recipient"] == "Mum"
    assert a["style"] == "classic" and b["style"] == "botanical"       # picked for them, not hardcoded
    assert all(p["reason"] for p in a["picks"] + b["picks"])
    assert a["photos_used"] == 6 and b["photos_used"] == 4             # Cathy has 5: steps down to 4
    assert "Only 5 usable photos" in b["note"] and b["requested"] == 6


def test_every_product_print_matches_recipe_and_preview_is_separate(family, tmp_path):
    ch = family["people"]["Chris"]
    res = PA.make_all(family["owner"], ch["id"], age=70, out_dir=tmp_path)
    assert set(res) == set(PA.product_ids())
    for pid, r in res.items():
        assert r["ok"], (pid, r)
        want = PA.print_size(pid)["px"]
        with Image.open(r["print_path"]) as im:
            assert im.size == tuple(want), pid
        assert r["print_path"] != r["preview_path"]
        with Image.open(r["preview_path"]) as pv:
            assert pv.size != tuple(want) or pid == "sticker"            # the scene, not the print
        assert r["scene_preview"] is True
        assert _no_magenta(r["print_path"]) and _no_magenta(r["preview_path"]), pid


def test_wrap_repeat_is_seamless_with_distinct_photos(family):
    ch = family["people"]["Chris"]
    ctx = PA.build_ctx(family["owner"], ch["id"], "wrapping_paper", age=70)
    sheet, info = PA._compose_wrap(ctx)
    d = ctx["wrap_design"]
    assert sheet.size == (2952, 4133)
    # >= N distinct source photos (6 wanted, Chris has 7 usable)
    assert len(set(info["motif_photos"])) == 6 == len(info["motif_photos"])
    heads = [e for e in d["elems"] if e["kind"] == "head"]
    assert len({e["photo_id"] for e in heads}) == 6
    texts = [e for e in d["elems"] if e["kind"] == "text"]
    assert texts                                                        # "Happy 70th" motif when age given
    # about 8-10 heads across the 50cm sheet
    Tw, Th = d["tile"]
    assert 8 <= 2952 / d["pitch"][0] <= 10
    assert float(Tw).is_integer() and float(Th / 2).is_integer()
    # exact half-drop repeat: shifting the window by a lattice vector changes nothing
    w0 = np.asarray(PA.render_wrap(d, (700, 700), (100, 200)))
    w1 = np.asarray(PA.render_wrap(d, (700, 700), (100 + Tw, 200 + Th // 2)))
    w2 = np.asarray(PA.render_wrap(d, (700, 700), (100, 200 + Th)))
    assert (w0 == w1).all() and (w0 == w2).all()
    # the tile alone, laid as a half-drop, rebuilds the sheet: nothing clipped at tile edges
    tile = PA.render_wrap(d, (int(Tw), int(Th)))
    big = np.asarray(PA.render_wrap(d, (2 * int(Tw), int(Th))))
    lay = Image.new("RGB", (2 * int(Tw), int(Th)))
    for x, y in ((0, 0), (int(Tw), Th // 2), (int(Tw), Th // 2 - Th)):
        lay.paste(tile, (x, y))
    assert (np.asarray(lay) == big).all()
    # no neighbouring slots share a photo (within one pitch, across the wraparound too)
    px, py = d["pitch"]
    for i, e in enumerate(heads):
        for f in heads[i + 1:]:
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    dx = f["x"] + a * Tw - e["x"]
                    dy = f["y"] + a * Th / 2 + b * Th - e["y"]
                    if abs(dx) < px * 1.2 and abs(dy) < py * 1.2:
                        assert e["photo_id"] != f["photo_id"]


def test_wrap_reuses_photos_only_when_it_must(family):
    ca = family["people"]["Cathy"]
    ctx = PA.build_ctx(family["owner"], ca["id"], "wrapping_paper")
    _sheet, info = PA._compose_wrap(ctx)
    assert len(set(info["motif_photos"])) == 5                          # all five of hers, none twice
    assert not [e for e in ctx["wrap_design"]["elems"] if e["kind"] == "text"]   # no age, no text


def test_sticker_is_a_cutout_on_a_disc(family, tmp_path):
    ch = family["people"]["Chris"]
    r = PA.make_product(family["owner"], ch["id"], "sticker", out_dir=tmp_path)
    assert r["segmenter"] == "grabcut" and len(r["picks"]) == 1 and r["picks"][0]["hero"]
    a = np.asarray(Image.open(r["print_path"]).convert("RGB")).astype(int)
    assert (a[5, 5] > 245).all() and (a[600, 40] > 0).all()            # white outside the die line


# ── fallbacks ───────────────────────────────────────────────────────────

def test_few_photos_steps_down_and_says_so(family, monkeypatch, tmp_path):
    ch = family["people"]["Chris"]
    two = family["by_sid"][ch["id"]][:2]
    monkeypatch.setattr(PS, "candidates", lambda o, s: ([_cand(p, i) for i, p in enumerate(two)], []))
    r = PA.make_product(family["owner"], ch["id"], "framed_print", out_dir=tmp_path)
    assert r["photos_used"] == 1 and r["requested"] == 4 and "Only 2 usable photos" in r["note"]
    with Image.open(r["print_path"]) as im:
        assert im.size == (3600, 4800)


def test_no_photos_is_typed_needs_photo(family, monkeypatch, tmp_path):
    ch = family["people"]["Chris"]
    monkeypatch.setattr(PS, "candidates", lambda o, s: ([], [{"photo_id": "x", "reason": "no face found"}]))
    with pytest.raises(PA.ProductArtError) as e:
        PA.make_product(family["owner"], ch["id"], "mug", out_dir=tmp_path)
    assert e.value.code == "NEEDS_PHOTO"
    res = PA.make_all(family["owner"], ch["id"], products=["mug", "tote"], out_dir=tmp_path)
    assert all(not v["ok"] and v["error_code"] == "NEEDS_PHOTO" for v in res.values())


def test_quality_gate_drops_silhouettes_and_lost_faces():
    from backend import cutout as CO
    rng = np.random.default_rng(1)
    face = (rng.integers(90, 220, (300, 240, 3))).astype(np.uint8)       # a face with texture
    good = Image.fromarray(face).convert("RGBA")
    good.info["face_px"] = (40, 60, 160, 180)
    assert CO.quality(good)["ok"]
    dark = Image.fromarray((face // 6).astype(np.uint8)).convert("RGBA")  # hair + sunglasses at night
    dark.info["face_px"] = (40, 60, 160, 180)
    q = CO.quality(dark)
    assert not q["ok"] and "silhouette" in q["reason"]
    lost = good.copy()
    a = np.zeros((300, 240), np.uint8)
    a[:, :60] = 255                                                       # the matte kept only a sliver
    lost.putalpha(Image.fromarray(a))
    lost.info["face_px"] = (40, 60, 160, 180)
    assert "lost the face" in CO.quality(lost)["reason"]


def test_segmenter_falls_back_to_grabcut(monkeypatch):
    from backend import cutout as CO
    img = Image.new("RGB", (600, 800), (40, 120, 60))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.ellipse((220, 160, 380, 360), fill=(225, 180, 150))
    d.rectangle((150, 380, 450, 800), fill=(30, 30, 90))
    def boom(*a, **k):
        raise RuntimeError("no model")
    monkeypatch.setattr(CO, "_full_matte", boom)
    cut = CO.head_and_shoulders(img, [0.37, 0.2, 0.27, 0.25], method="rembg")
    assert cut.info["segmenter"] == "grabcut" and cut.mode == "RGBA"
    a = np.asarray(cut.getchannel("A"))
    assert a.max() == 255 and (a == 0).mean() > 0.05                   # background really removed


def test_mockup_render_uses_product_art_then_falls_back(family, tmp_path):
    from backend import mockup
    ch = family["people"]["Chris"]
    out = tmp_path / "m.png"
    mockup.render("mug", None, "Mug", out, product_id="mug", owner=family["owner"], subject_id=ch["id"])
    assert out.is_file() and (tmp_path / "m_print.jpg").is_file()
    with Image.open(tmp_path / "m_print.jpg") as im:
        assert im.size == PA.print_size("mug")["px"]
    # unknown person -> the single-photo scene path still renders
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (600, 800), (200, 150, 120)).save(photo)
    out2 = tmp_path / "m2.png"
    mockup.render("mug", photo, "Mug", out2, product_id="mug", owner=family["owner"], subject_id="nobody")
    assert out2.is_file() and not (tmp_path / "m2_print.jpg").exists()


# ── REST + MCP + public proofs ──────────────────────────────────────────

def test_rest_make_one_and_all_with_public_proofs(family):
    cli, H, o = family["client"], family["headers"], family["owner"]
    ca = family["people"]["Cathy"]
    r = cli.post("/api/products/make", json={"owner": o, "subject_id": ca["id"], "product_id": "cushion"}, headers=H)
    b = r.get_json()
    assert r.status_code == 200 and b["ok"] and b["count"] == 1, b
    p = b["products"][0]
    assert p["print_url"].endswith("/print.jpg") and p["preview_url"].endswith("/preview.jpg")
    assert "/backend/api/products/proof/pm_" in p["print_url"] and p["fulfilment_asset"] == "print_url"
    mid = p["make_id"]
    pr = cli.get(f"/api/products/proof/{mid}/print.jpg")                # no key, no owner
    assert pr.status_code == 200 and pr.mimetype == "image/jpeg"
    assert Image.open(io.BytesIO(pr.data)).size == tuple(p["print_px"])
    assert cli.get(f"/api/products/proof/{mid}/preview.jpg").status_code == 200
    assert cli.get("/api/products/proof/pm_nope/print.jpg").status_code == 404
    # same inputs again: served from the cache, same make
    again = cli.post("/api/products/make", json={"owner": o, "subject_id": ca["id"], "product_id": "cushion"},
                     headers=H).get_json()
    assert again["products"][0]["make_id"] == mid and again["products"][0]["cached"] is True
    # errors are typed
    assert cli.post("/api/products/make", json={"owner": o, "subject_id": ca["id"], "product_id": "golf_art"},
                    headers=H).status_code == 400
    assert cli.post("/api/products/make", json={"owner": o, "product_id": "mug"}, headers=H).status_code == 400
    assert cli.post("/api/products/make", json={"owner": o, "subject_id": "nobody", "product_id": "mug"},
                    headers=H).status_code == 404
    # the live grid path: /api/products?subject_id= designs every product
    g = cli.get(f"/api/products?owner={o}&subject_id={ca['id']}", headers=H).get_json()
    assert g["ok"] and g["count"] == len(PA.product_ids()) and not g["failed"]
    assert all(i["image"].endswith("preview.jpg") and i["print_image"].endswith("print.jpg") for i in g["items"])


def test_mcp_make_product_all_and_one(family, monkeypatch):
    from backend import mcp_server as M
    ch = family["people"]["Chris"]
    call = _client_call(family)

    async def fake(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/oddhobb/people"):
            return {"ok": True, "people": [{"subject": {"id": ch["id"], "name": "Chris", "relationship": "father"},
                                            "profile": {}}]}
        return await call(method, path, body, api_key, owner_sig)
    monkeypatch.setattr(M, "_call", fake)
    out = asyncio.run(M.oddhobb_make(person="Chris", product="mug", request="presents for Dad, he's turning 70",
                                     owner=family["owner"]))
    env = json.loads(out[0].text)
    assert env["ok"] and env["status"] == "ready" and len(env["products"]) == 1, env
    p = env["products"][0]
    assert p["product_id"] == "mug" and p["print_url"] and p["preview_url"] and p["photos_picked"]
    out = asyncio.run(M.oddhobb_product_make(person="Chris", product="nope", owner=family["owner"]))
    assert json.loads(out[0].text)["error_code"] == "UNKNOWN_PRODUCT"
    out = asyncio.run(M.oddhobb_product_make(person="Chris", product="sticker", owner=family["owner"]))
    assert json.loads(out[0].text)["products"][0]["product_id"] == "sticker"


# ── intake: any person, pet or character ────────────────────────────────

def _character_png(seed=0, size=(640, 900)) -> bytes:
    from PIL import ImageDraw
    im = Image.new("RGB", size, (200, 205, 210) if seed % 2 == 0 else (230, 200, 200))
    d = ImageDraw.Draw(im)
    for i in range(seed % 7 + 2):           # a different backdrop pattern per image (no near-duplicates)
        d.ellipse((20 + i * 70, 800 - (i * seed) % 90, 60 + i * 70, 840 - (i * seed) % 90), fill=(60 + 20 * i, 90, 40))
    d.rounded_rectangle((220 + seed * 3, 120, 420, 330), radius=40, fill=(250, 215, 60))   # head
    d.ellipse((270, 200, 290, 220), fill=(20, 20, 20))
    d.ellipse((350, 200, 370, 220), fill=(20, 20, 20))
    d.arc((285, 240, 355, 290), 10, 170, fill=(20, 20, 20), width=6)
    d.rectangle((170, 340, 470, 760), fill=(120, 160, 230) if seed % 2 == 0 else (220, 90, 120))   # body
    d.polygon([(470, 360), (600 - seed * 5, 200 + seed * 20), (470, 420)], fill=(250, 215, 60))   # a waving arm
    if seed % 2:                            # a second pose: figure off to one side, smaller
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        small = im.resize((size[0] * 3 // 4, size[1] * 3 // 4))
        im = Image.new("RGB", size, (230, 200, 200))
        im.paste(small, (0, size[1] // 4))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def test_intake_character_from_two_images_then_products(env, monkeypatch, tmp_path):
    """No face detector knows a cartoon: whole-image tags + the same selector + make_product."""
    from backend import faces as FC
    from backend import subject_intake as SI
    from backend.server import app
    monkeypatch.setenv("ODD_SEGMENTER", "grabcut")
    monkeypatch.setattr(FC, "detect_boxes", lambda *a, **k: [])
    res = SI.add_subject(app, env["owner"], "Jenny", [("a.png", _character_png(0)), ("b.png", _character_png(5))],
                         kind="character", relationship="daughter")
    sid = res["subject"]["id"]
    assert res["ok"] and len(res["photos"]) == 2 and res["subject"]["kind"] == "character"
    assert all(t["face_id"] == "" for t in res["tags"])                  # whole-image tags
    cands, rejects = PS.candidates(env["owner"], sid)
    assert len(cands) == 2 and all(c["match"] == "tagged (whole image)" for c in cands), rejects
    r = PA.make_product(env["owner"], sid, "sticker", out_dir=tmp_path)
    assert r["ok"] and r["recipient"] == "Jenny" and r["style"] in PG_STYLES
    r = PA.make_product(env["owner"], sid, "mug", out_dir=tmp_path)
    assert r["photos_used"] == 2 and "Only 2 usable photos" in r["note"]


def test_intake_person_tags_one_anchor_face(env, monkeypatch):
    from backend import faces as FC
    from backend import subject_intake as SI
    from backend.server import app
    monkeypatch.setattr(FC, "detect_boxes", lambda *a, **k: [[200.0, 150.0, 300.0, 330.0, 0.95]])
    res = SI.add_subject(app, env["owner"], "Jenny", [("a.png", _character_png(1)), ("b.png", _character_png(2))],
                         kind="person")
    assert len(res["tags"]) == 1 and res["tags"][0]["face_id"].startswith("face")
    with pytest.raises(SI.IntakeError):
        SI.add_subject(app, env["owner"], "X", [], kind="person")
    with pytest.raises(SI.IntakeError):
        SI.add_subject(app, env["owner"], "X", [("a.png", b"x")], kind="robot")


def test_rest_and_mcp_intake(env, monkeypatch):
    import base64  # noqa: F401
    from backend import faces as FC
    from backend import mcp_server as M
    monkeypatch.setattr(FC, "detect_boxes", lambda *a, **k: [])
    cli, H, o = env["client"], env["headers"], env["owner"]
    r = cli.post("/api/subjects/intake", headers=H, content_type="multipart/form-data",
                 data={"owner": o, "name": "Robo", "kind": "character",
                       "photos": [(io.BytesIO(_character_png(3)), "r.png")]})
    b = r.get_json()
    assert r.status_code == 200 and b["ok"] and b["subject"]["name"] == "Robo", b
    pid = b["photos"][0]
    # JSON with existing photo ids: a second subject over the same library
    b2 = cli.post("/api/subjects/intake", json={"owner": o, "name": "Robo2", "kind": "character",
                                                "photo_ids": [pid]}, headers=H).get_json()
    assert b2["ok"] and b2["photos"] == [pid]
    assert cli.post("/api/subjects/intake", json={"owner": o, "name": "x"}, headers=H).status_code == 400
    monkeypatch.setattr(M, "_call", _client_call(env))
    out = asyncio.run(M.oddhobb_subject_add(name="Robo3", kind="character", photo_ids=[pid], owner=o))
    e = json.loads(out[0].text)
    assert e["ok"] and e["subject"]["kind"] == "character" and e["id"].startswith("sub_")


def test_cli_add_subject_and_run(env, monkeypatch, tmp_path, capsys):
    import importlib.util
    from backend import faces as FC
    monkeypatch.setenv("ODD_SEGMENTER", "grabcut")
    monkeypatch.setattr(FC, "detect_boxes", lambda *a, **k: [])
    spec = importlib.util.spec_from_file_location("make_products", config.ROOT / "scripts" / "make_products.py")
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    d = tmp_path / "pics"
    d.mkdir()
    (d / "a.png").write_bytes(_character_png(4))
    (d / "b.png").write_bytes(_character_png(6))
    assert mp.main(["--owner", env["owner"], "add-subject", "--name", "Jenny", "--kind", "character",
                    "--photos", str(d)]) == 0
    sid = json.loads(capsys.readouterr().out)["subject"]["id"]
    out = tmp_path / "out"
    assert mp.main(["--owner", env["owner"], "run", "--subject", sid, "--products", "sticker,postcard",
                    "--age", "7", "--out", str(out)]) == 0
    res = json.loads(capsys.readouterr().out)
    assert set(res["products"]) == {"sticker", "postcard"} and all(v["ok"] for v in res["products"].values())
    assert (out / "postcard_print.jpg").is_file() and (out / "sticker_preview.jpg").is_file()
