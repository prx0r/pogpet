"""Deal-four acceptance: one call → four varied buyable cards + prompt fill."""
import asyncio
import json


def test_reference_prompt_fills_clean():
    from backend import card_scenes as S
    out = S.reference_prompt("birthday_fullbleed", scene="a dusk golf course",
                             headline="ON THE BACK NINE")
    assert out["front"] and "ON THE BACK NINE" in out["front"]
    assert "deep navy" in out["front"]  # default golf_dusk palette
    assert out["inside_spot"] and "no text" in out["inside_spot"]
    assert out["back"] and "no text" in out["back"]
    for v in out.values():
        assert "{" not in v and "}" not in v


def _fake_call_factory(saved_ids):
    async def _fake(method, path, body=None, api_key="", owner_sig=""):
        if path.startswith("/api/oddhobb/people"):
            return {"ok": True, "people": [
                {"subject": {"id": "sub_dad", "name": "Chris",
                             "relationship": "dad"},
                 "profile": {"profile": {"name": "Chris", "relationship": "dad",
                                         "interests": ["golf"], "memories": []}}}]}
        if path == "/api/cards/designs":
            did = f"card_deal_{len(saved_ids):02d}"
            saved_ids.append((did, (body.get("spec") or {}).get("template")))
            return {"ok": True,
                    "design": {"id": did, "revision": 1,
                               "spec": body.get("spec") or {}},
                    "proof_url": f"https://oddhobb.com/proof/{did}"}
        raise AssertionError(f"unexpected call {method} {path}")
    return _fake


def test_deal_four_varied_cards(monkeypatch):
    from backend import mcp_server as M
    import backend.subject_assets as SA
    saved_ids: list = []
    monkeypatch.setattr(M, "_call", _fake_call_factory(saved_ids))

    async def fake_bundle(design_id, revision, owner, api_key, timeout_s=90, owner_sig=""):
        return {"ok": True, "views": {"front": "u1", "triptych": "u2"},
                "proof_url": f"https://oddhobb.com/proof/{design_id}",
                "revision": revision, "design_id": design_id}
    monkeypatch.setattr(M, "_card_spread_bundle", fake_bundle)
    monkeypatch.setattr(
        SA, "resolve",
        lambda sid, owner: {"face_candidates": [
            {"asset_id": f"pho_deal_{i}", "face_quality": 0.9 - i * 0.05}
            for i in range(4)], "body_candidates": []})

    out = asyncio.run(M.oddhobb_deal_cards(
        person="Dad", occasion="birthday", tone="funny",
        signature="Love, Prior x", owner="hark-dad-a7a5cc"))
    body = json.loads(out[0].text)
    assert body["ok"], body
    assert len(body["cards"]) == 4
    tids = [c["template_id"] for c in body["cards"]]
    assert len(set(tids)) == 4  # distinct templates = visual variety
    assert tids[0] == "birthday_4photo"  # 4 photos → flagship first
    assert {c["tone"] for c in body["cards"]} >= {"funny", "warm", "dry"}
    for c in body["cards"]:
        assert c["proof_url"].endswith("/proof/" + c["design_id"])
        assert c["headline"] == "Happy Birthday, Dad!"  # relationship label, never full name


def test_deal_requires_signature_and_photos(monkeypatch):
    from backend import mcp_server as M
    out = asyncio.run(M.oddhobb_deal_cards(person="Dad", signature=""))
    assert json.loads(out[0].text)["ok"] is False

    import backend.subject_assets as SA
    monkeypatch.setattr(M, "_call", _fake_call_factory([]))
    monkeypatch.setattr(M, "_card_spread_bundle",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no renders expected")))
    monkeypatch.setattr(SA, "resolve",
                        lambda sid, owner: {"face_candidates": [], "body_candidates": []})
    out = asyncio.run(M.oddhobb_deal_cards(person="Dad", signature="Love, Prior x",
                                           owner="hark-dad-a7a5cc"))
    body = json.loads(out[0].text)
    assert body["ok"] is False and "photo" in body["error"]


def test_deal_tool_registered_full_tier_only():
    from backend import mcp_server as M
    names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
    assert "oddhobb_deal_cards" in names
    assert "oddhobb_deal_cards" not in M.PUBLIC_TOOLS
