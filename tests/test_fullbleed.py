"""Fullbleed attach-art acceptance (Hark spec): template, validation gates,
attach flow, edit-keeps-art, checkout gate, tool registration."""
import io

import pytest

from backend import cards as C
from backend import card_scenes as S


def _png(w, h, color, noise=False):
    from PIL import Image, ImageDraw
    import random
    img = Image.new("RGB", (w, h), color)
    if noise:
        rng = random.Random(7)
        px = img.load()
        for y in range(h):
            for x in range(w):
                if (x + y) % 2:
                    px[x, y] = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_fullbleed_template_registered():
    t = S.TEMPLATES["birthday_fullbleed"]
    assert (t["min_photos"], t["max_photos"]) == (0, 0)
    assert t["fonts"]["headline"] in S.CARD_FONT_IDS
    assert "birthday_fullbleed" not in S.BIRTHDAY_TEMPLATES  # gallery never mints artless cards
    assert set(S.ART_DIRECTIONS["birthday_fullbleed"]) >= {"front", "inside_spot", "back"}


def test_fullbleed_validate_requires_art():
    base = {"template": "birthday_fullbleed", "format": "5x7", "photos": [],
            "headline": "Hi", "recipient": "Dad", "sender": "Me", "inside_message": "x"}
    with pytest.raises(C.CardError) as e:
        C.validate("anon", dict(base))
    assert "art_required" in str(e.value)
    spec = C.validate("anon", {**base, "front_art_key": "k/front.png"})
    assert spec["front_art_key"] == "k/front.png"
    assert spec["headline_baked"] is True
    with pytest.raises(C.CardError):
        C.validate("anon", {**base, "front_art_key": "k/front.png",
                             "headline": "H" * 41})


def test_art_aspect_and_size_gates():
    good = _png(900, 1260, (20, 30, 60))
    img, _w = C.validate_art_image(good, "front")
    assert img.size == (900, 1260)
    with pytest.raises(C.CardError) as e:
        C.validate_art_image(_png(1000, 1000, (20, 30, 60)), "front")
    assert "5:7" in str(e.value)
    with pytest.raises(C.CardError) as e:
        C.validate_art_image(_png(400, 560, (20, 30, 60)), "front")
    assert "800px" in str(e.value)
    with pytest.raises(C.CardError):
        C.validate_art_image(b"not an image", "front")
    # inside wants 10:7
    with pytest.raises(C.CardError):
        C.validate_art_image(good, "inside")
    img2, _ = C.validate_art_image(_png(1400, 980, (250, 247, 240)), "inside")
    assert img2.size == (1400, 980)


def test_face_gate_flat_rejects_textured_warns():
    assert C._face_detector_get() is not None  # vendored YuNet present
    flat = C.validate_art_image(_png(900, 1260, (20, 30, 60)), "front")[0]
    found, detail, warn = C.face_presence(flat)
    assert found is False and warn == ""  # flat → caller blocks 400
    textured = C.validate_art_image(_png(900, 1260, (20, 30, 60), noise=True), "front")[0]
    found2, _d2, warn2 = C.face_presence(textured)
    assert warn2  # illustrated/textured miss → warning, never a block


def test_make_card_fullbleed_409_without_art():
    import asyncio, json
    from backend import mcp_server as M
    out = asyncio.run(M.oddhobb_make_card(
        "person_9fdc85d6730d43e099dc", "birthday", "playful_balloons",
        "funny", "", "Love, Prior x", "hark-dad-a7a5cc", "",
        "", "birthday_fullbleed"))
    body = json.loads(out[0].text)
    assert body["ok"] is False and "art_required" in body["error"]
    assert body.get("http_status") == 409


def test_attach_tool_registered_full_tier_only():
    from backend import mcp_server as M
    names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
    assert "oddhobb_attach_card_art" in names
    assert "oddhobb_attach_card_art" not in M.PUBLIC_TOOLS


def _client():
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as Srv
    Srv.config.API_TOKEN = "test-token"
    return Srv.app.test_client()


def test_attach_flow_and_edit_keeps_art(monkeypatch):
    import time
    front = _png(900, 1260, (20, 30, 60), noise=True)
    inside = _png(1400, 980, (250, 247, 240))
    data = {"front": front, "inside": inside}

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(C, "fetch_art_bytes", lambda url: data["front"] if "front" in url else data["inside"])
    c = _client()
    r = c.post("/api/cards/attach-art?owner=anon&token=test-token", json={
        "owner": "anon", "front_art_url": "https://x/front.png",
        "inside_art_url": "https://x/inside.png", "headline": "ON THE BACK NINE",
        "recipient": "Dad", "sender": "Love, Prior x",
        "inside_message": "You are officially on the back nine.",
        "art_source": "hark", "prompt": "golf dusk"})
    saved = r.get_json()
    assert saved["ok"], saved
    did, rev = saved["design"]["id"], saved["design"]["revision"]
    assert rev == 1
    try:
        for _ in range(40):
            s = c.get(f"/api/cards/{did}/scene?owner=anon&revision={rev}&token=test-token").get_json()["scene"]
            if s["outputs"]["preview"]["status"] == "ready":
                break
            time.sleep(0.5)
        for kind, ct in (("preview", "image/png"), ("inside", "image/png"),
                         ("back", "image/png"), ("triptych", "image/jpeg")):
            rr = c.get(f"/api/cards/{did}/r{rev}/{kind}?owner=anon&token=test-token")
            assert (rr.status_code, rr.content_type) == (200, ct), kind
        # edit message → new revision, art keys unchanged
        e = c.post("/api/cards/designs?owner=anon&token=test-token", json={
            "owner": "anon", "id": did, "expected_revision": rev,
            "spec": {**saved["design"]["spec"], "inside_message": "New message here",
                     "inside": {"left": {"mode": "blank", "text": "", "font": "inter",
                                         "size": "M", "colour": "ink", "align": "center"},
                                "right": {"mode": "message", "message": "New message here",
                                          "font": "fraunces", "size": "M",
                                          "colour": "ink", "align": "center"}}}}).get_json()
        assert e["ok"], e
        assert e["design"]["revision"] == rev + 1
        assert e["design"]["spec"]["front_art_key"] == saved["design"]["spec"]["front_art_key"]
    finally:
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
            conn.commit()


def test_fullbleed_checkout_gate_without_export():
    c = _client()
    d = c.post("/api/cards/designs?owner=anon&token=test-token", json={
        "owner": "anon", "spec": {"template": "birthday_fullbleed", "format": "5x7",
                                 "photos": [], "headline": "Hi", "recipient": "Dad",
                                 "sender": "Me", "inside_message": "x",
                                 "front_art_key": "k/front.png"}}).get_json()
    assert d["ok"], d
    did, rev = d["design"]["id"], d["design"]["revision"]
    try:
        r = c.post(f"/api/cards/{did}/checkout?owner=anon&token=test-token", json={
            "owner": "anon", "revision": rev, "qty": 1,
            "idempotency_key": "fb-gate-12345678"})
        assert r.status_code == 409
    finally:
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
            conn.commit()
