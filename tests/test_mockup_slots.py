"""Photoreal listing mockups (backend/mockup_slots.py): every Prodigi product has a
pre-keyed scene kit, corners are sane, renders are deterministic, carry no magenta,
and mockup.render() still falls back to the flat tile. No network, no generation."""
import hashlib
import json

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend import config, mockup
from backend import mockup_slots as MS


def _art(w=900, h=700, seed=3):
    # blocky photo stand-in from a palette with no magenta, so any magenta in a
    # render can only be key residue from the kit
    pal = np.array([(30, 90, 160), (40, 140, 70), (230, 150, 40), (20, 20, 25), (245, 245, 240),
                    (120, 120, 120), (200, 60, 40), (90, 170, 200)], np.uint8)
    rng = np.random.default_rng(seed)
    a = pal[rng.integers(0, len(pal), (h // 50 + 1, w // 50 + 1))]
    im = Image.fromarray(a).resize((w, h), Image.NEAREST)
    ImageDraw.Draw(im).ellipse((w * .3, h * .2, w * .7, h * .8), fill=(250, 210, 180))
    return im


def _magenta_px(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (140, 120, 120), (165, 255, 255))   # saturated pure-magenta band only
    return int((m > 0).sum())


def test_every_prodigi_product_has_a_kit():
    have = set(MS.kit_ids())
    missing = [p for p in config.PRODIGI_PRODUCTS if p not in have]
    assert not missing, missing
    for pid, spec in config.PRODIGI_PRODUCTS.items():
        assert MS.kit_for(pid, spec["shape"]) == pid


@pytest.mark.parametrize("kid", MS.kit_ids())
def test_kit_loads_and_corners_valid(kid):
    kit = MS.load_kit(kid)
    W, H = kit["size"]
    assert kit["_base"].shape[:2] == (H, W) == kit["_mask"].shape[:2]
    assert max(W, H) <= 1600
    assert kit["mode"] in ("quad", "ellipse", "cylinder")
    assert kit["surface"] in ("opaque", "ink")
    q = np.float32(kit["corners"])
    assert q.shape == (4, 2)
    assert (q[:, 0] >= -2).all() and (q[:, 0] <= W + 2).all()
    assert (q[:, 1] >= -2).all() and (q[:, 1] <= H + 2).all()
    # convex, clockwise TL,TR,BR,BL, non-trivial area
    assert cv2.isContourConvex(q.reshape(-1, 1, 2))
    area = cv2.contourArea(q)
    assert area > 0.01 * W * H
    assert q[0].sum() == min(p.sum() for p in q)                       # TL first
    def _x(u, v):
        return float(u[0] * v[1] - u[1] * v[0])
    cross = [_x(q[(i + 1) % 4] - q[i], q[(i + 2) % 4] - q[(i + 1) % 4]) for i in range(4)]
    assert all(c > 0 for c in cross)                                    # clockwise in image coords
    # the mask actually sits inside the slot quad (key and corners agree)
    hard = kit["_mask"] > 200
    if kit["mode"] == "cylinder":   # band edges bulge past the chord corners by design
        hard = cv2.erode(hard.astype(np.uint8), np.ones((1, 1), np.uint8)) > 0
        hard[: int(q[:, 1].min()) + 40] = False
        hard[int(q[:, 1].max()) - 40:] = False
    inside = np.zeros_like(kit["_mask"])
    cv2.fillConvexPoly(inside, np.round(q).astype(np.int32), 255)
    cv2.dilate(inside, np.ones((25, 25), np.uint8), dst=inside)
    assert (inside[hard] > 0).mean() > 0.97
    assert kit["aspect"] > 0
    if kit["mode"] == "cylinder":
        assert kit["cyl"]["r"] > 0 and kit["cyl"]["xl"] < kit["cyl"]["xr"]
    # the committed render base never contains the magenta key colour
    assert _magenta_px(kit["_base"]) == 0


@pytest.mark.parametrize("kid", MS.kit_ids())
def test_render_no_magenta_and_deterministic(kid, tmp_path):
    art = _art()
    a = MS.render_scene(kid, art, tmp_path / "a.png", faces=False)
    b = MS.render_scene(kid, art, tmp_path / "b.png", faces=False)
    ha = hashlib.sha1(a.read_bytes()).hexdigest()
    assert ha == hashlib.sha1(b.read_bytes()).hexdigest()
    out = cv2.imread(str(a))
    kit = MS.load_kit(kid)
    assert out.shape[:2] == kit["_base"].shape[:2]
    assert _magenta_px(out) == 0
    # the art really landed in the slot: the slot differs from the empty base
    hard = kit["_mask"] > 200
    diff = np.abs(out.astype(int) - kit["_base"].astype(int)).sum(2)
    assert (diff[hard] > 12).mean() > 0.5


def test_art_is_never_stretched():
    kit = MS.load_kit("greeting_card")
    prepped = MS.prepare_art(kit, _art(1600, 900), faces=False)
    assert abs(prepped.width / prepped.height - 5 / 7) < 0.01


def test_mockup_render_uses_scene_when_kit_exists(tmp_path):
    photo = tmp_path / "p.png"
    _art().save(photo)
    spec = config.PRODIGI_PRODUCTS["mug"]
    out = mockup.render(spec["shape"], photo, spec["label"], tmp_path / "m.png", product_id="mug")
    im = Image.open(out)
    assert im.size == tuple(MS.load_kit("mug")["size"])
    assert mockup.cache_tag("mug", "mug").startswith("_s")
    # the label alone also finds the kit (callers that don't pass product_id)
    spec = config.PRODIGI_PRODUCTS["canvas"]
    out = mockup.render(spec["shape"], photo, spec["label"], tmp_path / "c.png")
    assert Image.open(out).size == tuple(MS.load_kit("canvas")["size"])


def test_mockup_render_flat_fallback(tmp_path, monkeypatch):
    photo = tmp_path / "p.png"
    _art().save(photo)
    # unknown shape -> flat tile
    out = mockup.render("generic", photo, "Thing", tmp_path / "g.png")
    assert Image.open(out).size == (mockup.W, mockup.H)
    assert mockup.cache_tag("generic") == ""
    # no source photo -> flat tile
    out = mockup.render("card", None, "Greeting Card", tmp_path / "n.png")
    assert Image.open(out).size == (mockup.W, mockup.H)
    # scene path broken -> flat tile, never an exception
    monkeypatch.setattr(MS, "render_product", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    out = mockup.render("card", photo, "Greeting Card", tmp_path / "f.png", product_id="greeting_card")
    assert Image.open(out).size == (mockup.W, mockup.H)
    # scene=False forces the flat tile
    out = mockup.render("mug", photo, "Mug", tmp_path / "s.png", scene=False)
    assert Image.open(out).size == (mockup.W, mockup.H)


def test_kit_json_is_plain(tmp_path):
    for kid in MS.kit_ids():
        d = json.loads((MS.KITS / kid / "kit.json").read_text())
        assert d["product"] == kid and len(d["corners"]) == 4
