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
