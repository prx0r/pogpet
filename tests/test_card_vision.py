"""Cards vision slice: vibe-clustered fonts, message lines, edit/variants/messages tools."""
import asyncio
import json


def test_fonts_endpoint_clusters():
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    d = c.get("/api/cards/fonts?owner=anon&token=test-token").get_json()
    assert d["ok"] and len(d["fonts"]) >= 5
    for fid, f in d["fonts"].items():
        assert f["vibes"] and f["occasions"] and f["use_for"], fid
    assert "birthday" in d["fonts"]["fraunces"]["occasions"]
    assert "body" in d["fonts"]["courier"]["use_for"]


def test_message_lines():
    from backend.cards import message_lines
    prof = {"name": "Dad", "relationship": "dad",
            "interests": ["golf"], "memories": ["lost three balls in the lake"]}
    funny = message_lines(prof, "funny")
    assert any("golf" in l["text"] for l in funny)
    assert all(l["source"] for l in funny)
    warm = message_lines(prof, "warm")
    assert warm and len(warm[0]["text"]) <= 400
    short = message_lines({}, "short")
    assert short


def test_edit_rejects_bad_panel():
    from backend import mcp_server as M
    d = json.loads(asyncio.run(M.figg_card_edit("card_x", "back", "colour", "ink")))
    assert d["ok"] is False


def test_vision_tools_registered_and_tiered():
    from backend import mcp_server as M
    names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
    for t in ("figg_card_fonts", "figg_card_edit", "figg_card_variants",
              "figg_card_messages"):
        assert t in names, t
    assert "figg_card_fonts" in M.PUBLIC_TOOLS
    assert "figg_card_messages" in M.PUBLIC_TOOLS
    assert "figg_card_edit" not in M.PUBLIC_TOOLS
    assert "figg_card_variants" not in M.PUBLIC_TOOLS
    assert "vibe" in (M.figg_card_fonts.__doc__ or "")


def test_find_subject_aliases_and_nesting():
    from backend.mcp_server import _find_subject
    people = {"ok": True, "people": [
        {"subject": {"id": "p1", "name": "Chris Prior", "relationship": None},
         "profile": {"relationship": "father",
                     "profile": {"name": "Chris Prior", "relationship": "father",
                                 "interests": ["golf"]}}},
        {"subject": {"id": "p2", "name": "Cathy", "relationship": None},
         "profile": {"relationship": "mother",
                     "profile": {"name": "Cathy", "relationship": "mother"}}},
    ]}
    assert _find_subject(people, "Dad", "")["id"] == "p1"
    assert _find_subject(people, "father", "")["id"] == "p1"
    assert _find_subject(people, "Chris Prior", "")["interests"] == ["golf"]
    assert _find_subject(people, "Mum", "")["id"] == "p2"
    assert _find_subject(people, "Nobody", "") == {}


def test_for_person_prefers_confirmed_bodies():
    from backend import subject_assets as SA
    res = SA.resolve("person_9fdc85d6730d43e099dc", "hark-dad-a7a5cc")
    bodies = sorted(res.get("body_candidates") or [],
                    key=lambda c: float(c.get("quality", 0)), reverse=True)
    assert bodies, "Chris needs body candidates from confirmed tags"
    confirmed = {"pho_ec536d6a61d54934a752", "pho_6779ec37a1e84d3fa086",
                 "pho_31f9b76e88ac4512875b", "pho_08cd015f06864fc1b37c",
                 "pho_676d794af4d945d38439"}
    assert bodies[0]["asset_id"] in confirmed


def test_panels_carry_star_photo():
    from backend.renderers import composite2d as C2
    from PIL import Image as _I
    import tempfile as _tf
    contract = {"trim_mm": [127, 178], "bleed_mm": 3, "dpi": 72}
    manifest = {"layout": {"panels": 2}, "slots": {}}
    img0, gaps0 = C2.render_panels(manifest, contract, panels=["", ""])
    assert any("blank" in g for g in gaps0)
    with _tf.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        _I.new("RGB", (400, 500), "#336699").save(tmp.name)
        img1, gaps1 = C2.render_panels(manifest, contract, panels=["setup", "payoff"],
                                       photo_path=tmp.name)
    assert not any("blank" in g for g in gaps1)
    import hashlib as _h
    assert _h.md5(img0.tobytes()).hexdigest() != _h.md5(img1.tobytes()).hexdigest()
