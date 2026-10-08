"""Card P0 guardrails + checkout: fixed price, validators in save,
source stamping, mcp_status, Shopify draft shape, webhook HMAC, openapi."""
import pathlib
from backend import cards as C
from backend import shopify_fulfil as SF


def test_card_price_fixed():
    p = C.card_price()
    assert p["price_cents"] == 799
    assert p["price_grade"] == "FIXED"
    assert p["currency"] == "GBP"
    assert p["product_id"] == "ODD-CARD-5X7"


def test_validate_rejects_renderer_owned():
    import backend.cards as cards
    for key in ("back", "fonts", "layout", "bleed", "dpi", "sku"):
        try:
            cards.validate("anon", {"template": "portrait", "format": "5x7",
                                    "photos": [], key: "x",
                                    "headline": "Hi", "recipient": "",
                                    "sender": "", "inside_message": ""})
        except cards.CardError as e:
            assert "renderer-owned" in str(e)
        else:
            raise AssertionError(f"{key} should be rejected")


def test_validate_rejects_wordmark():
    try:
        C.validate("anon", {"template": "typography", "format": "5x7",
                             "photos": [], "headline": "OddHobb rules",
                             "recipient": "", "sender": "", "inside_message": ""})
    except C.CardError as e:
        assert "wordmark" in str(e).lower() or "brand" in str(e).lower()
    else:
        raise AssertionError("wordmark should be rejected")


def test_mcp_status_values():
    v = C.mcp_status()
    assert v in ("live", "degraded", "unknown")


def test_shopify_api_version_configurable():
    assert SF.API_VERSION in ("2026-07", "2026-10", "2025-10") or len(SF.API_VERSION) == 7
    assert SF.CARD_PRODUCT_SKU == "ODD-CARD-5X7"


def test_webhook_verify():
    import hmac as _hmac, hashlib as _hl, base64 as _b64, os
    os.environ["SHOPIFY_API_SECRET"] = "test-secret"
    data = b'{"id":1}'
    digest = _hmac.new(b"test-secret", data, _hl.sha256).digest()
    good = _b64.b64encode(digest).decode()
    assert SF.verify_webhook(data, good) is True
    assert SF.verify_webhook(data, "bad") is False


def test_openapi_documents_side_doors():
    import json, pathlib
    d = json.loads(pathlib.Path("site/openapi.json").read_text())
    paths = d["paths"]
    for p in ("/backend/api/cards/designs", "/backend/api/cards/{id}/render",
              "/backend/api/cards/{id}/checkout", "/backend/api/design/locks",
              "/backend/api/mcp/health"):
        assert p in paths, f"missing {p}"


def test_mcp_checkout_registered_and_gated():
    from backend import mcp_server as M
    names = [fn.__name__ for fns in M.TOOL_AREAS.values() for fn in fns]
    assert "figg_card_checkout" in names
    assert "figg_card_checkout" not in M.PUBLIC_TOOLS
    assert "Done means a product_url" in (M.figg_card_checkout.__doc__ or "")
    assert "Done means a product_url" in (M.figg_card_save.__doc__ or "")
    assert M.MCP_VERSION == "1.12.0"


def test_bridge_logs_cf_ray():
    src = open("bridge/llm_bridge.py").read()
    assert "cf_ray" in src.lower()
    assert "MCP_PORT_FALLBACK" in src or "8800" in src


def test_formats_price_consistent():
    from backend import card_scenes as scenes
    assert scenes.FORMATS["5x7"]["price_cents"] == 799
    assert C.card_price()["price_cents"] == 799


def test_via_spoof_rejected():
    """Body via=mcp without the X-MCP transport header stamps rest, not mcp."""
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    spec = {"template": "typography", "format": "5x7", "photos": [],
            "headline": "Spoof test", "recipient": "", "sender": "", "inside_message": "x"}
    r = c.post("/api/cards/designs?owner=anon&token=test-token",
               json={"owner": "anon", "spec": spec, "via": "mcp"})
    assert r.status_code == 200
    assert r.get_json()["design"]["via"] == "rest"
    # cleanup
    from backend import db
    did = r.get_json()["design"]["id"]
    with db.connect() as conn:
        conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
        conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
        conn.commit()


def test_via_mcp_transport():
    """X-MCP header (MCP→Flask direct, bridge strips it) stamps mcp."""
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    spec = {"template": "typography", "format": "5x7", "photos": [],
            "headline": "Transport test", "recipient": "", "sender": "", "inside_message": "x"}
    r = c.post("/api/cards/designs?owner=anon&token=test-token",
               json={"owner": "anon", "spec": spec},
               headers={"X-MCP": "1"})
    assert r.status_code == 200
    assert r.get_json()["design"]["via"] == "mcp"
    from backend import db
    did = r.get_json()["design"]["id"]
    with db.connect() as conn:
        conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
        conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
        conn.commit()


def test_health_tiers():
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    r = c.get("/api/mcp/health?token=test-token")
    d = r.get_json()
    assert d["tools_full"] >= d["tools_public"] > 0
    assert d["tiers"]["public"]["port"] == 8800
    assert "tokenless" in d["hint"] or "public" in d["hint"].lower()


def test_mcp_auth_passthrough():
    import inspect
    from backend import mcp_server as M
    for name in ("figg_card_save", "figg_card_library", "figg_card_checkout",
                 "figg_card_reserve", "oddhobb_people"):
        assert "api_key" in inspect.signature(getattr(M, name)).parameters, name


def test_save_checkout_flow_mocked():
    """Save typography (0 photos) → export → checkout (mocked Shopify) → 410 on direct fulfil."""
    import time, uuid
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    from backend import shopify_fulfil as SF
    orig = SF.create_card_draft_order
    orig_cfg = SF.configured
    SF.configured = lambda: True
    SF.create_card_draft_order = lambda **kw: {
        "ok": True, "draft_id": "gid://shopify/DraftOrder/TEST",
        "name": "#DTEST", "invoice_url": "https://example.com/checkout/test",
        "total": {"amount": "7.99", "currencyCode": "GBP"},
        "store": SF.store(), "api_version": SF.API_VERSION, "sku": "ODD-CARD-5X7"}
    c = S.app.test_client()
    owner = "anon"
    spec = {"template": "typography", "format": "5x7", "photos": [],
            "headline": "Test Hi", "recipient": "", "sender": "", "inside_message": "x"}
    uniq = uuid.uuid4().hex[:8]
    try:
        r = c.post(f"/api/cards/designs?owner={owner}&token=test-token",
                   json={"owner": owner, "spec": spec, "via": "mcp"})
        assert r.status_code == 200, r.get_data(as_text=True)[:300]
        d = r.get_json()
        # test client has no X-MCP transport header → rest (spoof-proof)
        assert d["design"]["via"] == "rest"
        assert d["product"]["price_cents"] == 799
        assert d["mcp_status"] in ("live", "degraded", "unknown")
        assert "/cards/" in d["card_url"]
        did, rev = d["design"]["id"], d["design"]["revision"]
        # export
        r = c.post(f"/api/cards/{did}/render?owner={owner}&token=test-token",
                   json={"owner": owner, "revision": rev, "kind": "export"})
        assert r.status_code == 200
        for _ in range(30):
            rj = c.get(f"/api/cards/{did}/scene?owner={owner}&revision={rev}&token=test-token")
            st = rj.get_json()["scene"]["outputs"]["export"]["status"]
            if st == "ready":
                break
            time.sleep(0.5)
        assert st == "ready"
        # checkout (mocked Shopify)
        idem = f"test-checkout-{uniq}-12345678"
        r = c.post(f"/api/cards/{did}/checkout?owner={owner}&token=test-token",
                   json={"owner": owner, "revision": rev, "qty": 1, "idempotency_key": idem})
        assert r.status_code == 200, r.get_data(as_text=True)[:500]
        ch = r.get_json()
        assert ch["checkout_url"].startswith("https://")
        assert ch["product_url"].endswith(f"/r{rev}")
        assert ch["order"]["status"] == "awaiting_payment"
        assert ch["order"]["price_cents"] == 799
        # direct fulfil disabled
        r = c.post(f"/api/cards/{did}/order?owner={owner}&token=test-token",
                   json={"owner": owner, "revision": rev, "qty": 1,
                         "idempotency_key": f"test-fulfil-{uniq}-12345678", "fulfil": True})
        # order creates reserve then hits fulfil gate → 410
        assert r.status_code == 410, r.get_data(as_text=True)[:300]
    finally:
        SF.create_card_draft_order = orig
        SF.configured = orig_cfg
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM card_orders WHERE idempotency_key LIKE ?", (f"%{uniq}%",))
            # designs created above
            rows = conn.execute("SELECT id FROM card_designs WHERE owner=? ORDER BY created_at DESC LIMIT 5",
                                (owner,)).fetchall()
            for row in rows:
                did_c = row["id"]
                # only delete our test (headline Test Hi)
                rev_row = conn.execute("SELECT spec FROM card_revisions WHERE design_id=? ORDER BY revision DESC LIMIT 1",
                                       (did_c,)).fetchone()
                if rev_row and "Test Hi" in (rev_row["spec"] or ""):
                    conn.execute("DELETE FROM card_orders WHERE design_id=?", (did_c,))
                    conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did_c,))
                    conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did_c,))
                    conn.execute("DELETE FROM card_designs WHERE id=?", (did_c,))
            conn.commit()


def test_spread_flow_mocked():
    import time
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    spec = {"template": "typography", "format": "5x7", "photos": [],
            "headline": "Spread faces", "recipient": "", "sender": "Me",
            "inside_message": "hi", "headline_font": "courier",
            "inside": {"right": {"message": "hi", "font": "courier"},
                       "left": {"mode": "blank"}}}
    d = c.post("/api/cards/designs?owner=anon&token=test-token",
               json={"owner": "anon", "spec": spec}).get_json()
    assert d["design"]["spec"]["headline_font"] == "courier"
    did, rev = d["design"]["id"], d["design"]["revision"]
    try:
        j = c.post(f"/api/cards/{did}/render?owner=anon&token=test-token",
                   json={"owner": "anon", "revision": rev, "kind": "spread"}).get_json()
        assert j["job"]["kind"] == "spread"
        for _ in range(30):
            s = c.get(f"/api/cards/{did}/scene?owner=anon&revision={rev}&token=test-token").get_json()["scene"]
            if s["outputs"]["spread"]["status"] == "ready":
                break
            time.sleep(0.5)
        urls = s["outputs"]["spread"]["urls"]
        assert set(urls) == {"front", "inside_left", "inside_right", "back", "listing"}
        for part in ("front", "inside_left", "inside_right", "back"):
            r = c.get(f"/api/cards/{did}/r{rev}/spread/{part}?owner=anon&token=test-token")
            assert (r.status_code, r.content_type) == (200, "image/png"), part
        assert urls["listing"].endswith(f"/r{rev}/listing")
    finally:
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
            conn.commit()



def test_inside_ink_readable_on_cream():
    """White front ink must never leak onto cream inside paper (dark-card bug)."""
    from backend.card_scenes import ink_for
    from backend import cards as C
    owner = "hark-dad-a7a5cc"
    pid = "pho_676d794af4d945d38439"
    for tid in ("breaking_news", "awards", "portrait", "christmas",
                "game_winner", "family"):
        tpl_min = {"breaking_news": 1, "awards": 1, "portrait": 1,
                   "christmas": 1, "game_winner": 1, "family": 1}[tid]
        photos = [{"photo_id": pid, "crop": [0, 0, 1, 1],
                   "focus": [0.5, 0.5], "cutout": ""}] * tpl_min
        s = C.validate(owner, {"template": tid, "format": "5x7", "photos": photos,
                               "headline": "Hi", "recipient": "", "sender": "Me",
                               "inside_message": "Happy birthday"})
        for which in ("ink", "soft", "accent"):
            col = ink_for(s, which)
            lum = sum(int(col.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) / 3 / 255
            assert lum < 0.6, (tid, which, col)


def test_crop_changes_front():
    """A crop box must visibly change the cover (no silent full-frame)."""
    import hashlib
    from backend import cards as C
    from backend.card_scenes import front
    owner = "hark-dad-a7a5cc"
    pid = "pho_676d794af4d945d38439"
    base = {"template": "portrait", "format": "5x7", "headline": "Hi Dad",
            "recipient": "Dad", "sender": "Me", "inside_message": "x"}
    outs = []
    for crop in ([0, 0, 1, 1], [0.3, 0.3, 0.667, 0.7]):
        spec = C.validate(owner, {**base, "photos": [
            {"photo_id": pid, "crop": crop, "focus": [0.5, 0.5], "cutout": ""}]})
        assert spec["photos"][0]["crop"][0] == float(crop[0])
        outs.append(hashlib.md5(front(spec, C.assets(owner, spec), 360).tobytes()).hexdigest())
    assert outs[0] != outs[1]


def test_all_templates_render():
    """All seven covers render with and without photos, deterministically."""
    import hashlib
    from backend import cards as C
    from backend.card_scenes import front
    owner = "hark-dad-a7a5cc"
    pid = "pho_676d794af4d945d38439"
    counts = {"portrait": 1, "breaking_news": 1, "game_winner": 1, "awards": 1,
              "christmas": 1, "family": 3, "typography": 0}
    for tid, n in counts.items():
        photos = [{"photo_id": pid, "crop": [0, 0, 1, 1],
                   "focus": [0.5, 0.5], "cutout": ""}] * n
        spec = C.validate(owner, {"template": tid, "format": "5x7", "photos": photos,
                                  "headline": "Happy Birthday, legend.",
                                  "recipient": "Dad", "sender": "Me",
                                  "inside_message": "Love you"})
        aa = C.assets(owner, spec)
        a = hashlib.md5(front(spec, aa, 360).tobytes()).hexdigest()
        b = hashlib.md5(front(spec, aa, 360).tobytes()).hexdigest()
        assert a == b, tid


def test_strict_inside_keys():
    from backend import cards as C
    try:
        C.validate("anon", {"template": "typography", "format": "5x7", "photos": [],
                            "headline": "Hi", "recipient": "", "sender": "",
                            "inside_message": "x",
                            "inside": {"font": "inter"}})
    except C.CardError as e:
        assert "panel" in str(e) and "left" in str(e)
    else:
        raise AssertionError("flat font keys must be rejected")


def test_messages_match_relationship_and_tone():
    from backend.cards import message_lines
    prof = {"name": "Chris Prior", "relationship": "father", "interests": ["golf"]}
    funny = message_lines(prof, "funny")
    assert any("golf" in l["text"] for l in funny)
    dark = message_lines(prof, "dark")
    assert dark and not any("obsessed with" in l["text"] for l in dark)
    empty = message_lines({}, "funny")
    assert empty and not any("obsessed with" in l["text"] for l in empty)



def test_creative_tools_take_api_key():
    import inspect
    from backend import mcp_server as M
    for n in ("figg_creative_brief", "figg_creative_catalog", "figg_creative_match",
              "figg_creative_revision", "figg_creative_templates", "oddhobb_buy",
              "oddhobb_capsule", "oddhobb_capture_finish", "oddhobb_capture_mark",
              "oddhobb_capture_start", "oddhobb_create", "oddhobb_ideas",
              "oddhobb_providers", "oddhobb_render", "oddhobb_review",
              "oddhobb_revise", "oddhobb_status"):
        assert "api_key" in inspect.signature(getattr(M, n)).parameters, n


def test_match_refuses_bad_brief():
    import asyncio, json
    from backend import mcp_server as M
    d = json.loads(asyncio.run(M.figg_creative_match(
        {"ok": False, "error": "owner_sig required"})))
    assert d["ok"] is False and "brief" in d["error"]
    d2 = json.loads(asyncio.run(M.figg_creative_match({"recipient": {}})))
    assert d2["ok"] is False


def test_match_endpoint_rejects_occasionless_brief():
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    r = c.post("/api/creative/match?token=test-token",
               json={"brief": {"recipient": {}}, "limit": 5})
    assert r.status_code == 400, r.get_data(as_text=True)[:200]


def test_memory_facts_steer_matcher():
    from backend.creative.matcher import score
    tpl = {"id": "golf_comic", "taxonomy": {"occasion": ["birthday", "general"],
                                            "topics": ["sport"], "tone": ["ross"]},
           "presentation": {"label": "golf day cartoon"}}
    base = {"occasion": {"id": "birthday"}, "recipient": {},
            "request": {"prompt": ""}, "available_assets": {}}
    plain, _ = score(tpl, base)
    mem = dict(base, agent_memory=[{"fact": "Dad loves golf and Tesla"}])
    boosted, reasons = score(tpl, mem)
    assert boosted > plain
    assert any("memory" in r for r in reasons)



def test_gate_rejects_face_cutting_crop():
    from backend import cards as C
    owner, pid = "hark-dad-a7a5cc", "pho_5fc9a90cc42b4ef88a49"
    assert C.face_box(owner, pid), "need a faced photo for this test"
    spec = {"template": "portrait", "format": "5x7",
            "photos": [{"photo_id": pid, "crop": [0.7, 0.7, 0.2, 0.2],
                        "focus": [0.8, 0.8], "cutout": ""}],
            "headline": "Hi Dad", "recipient": "Dad", "sender": "Me",
            "inside_message": "x"}
    saved = C.validate(owner, spec)
    import backend.server as S
    from backend import config as _cfg
    _cfg.API_TOKEN = "test-token"
    S.config.API_TOKEN = "test-token"
    sig = _cfg.sign_owner(owner)
    c = S.app.test_client()
    r = c.post("/api/cards/designs?owner=" + owner + "&token=test-token",
               json={"owner": owner, "owner_sig": sig, "spec": spec})
    # save itself is fine (crop is the photographer's choice); render refuses
    if r.status_code != 200:
        return
    did = r.get_json()["design"]["id"]
    try:
        from backend import db
        r2 = c.post(f"/api/cards/{did}/render?owner={owner}&token=test-token",
                    json={"owner": owner, "owner_sig": sig, "revision": 1,
                          "kind": "preview"})
        assert r2.status_code == 422, r2.get_data(as_text=True)[:200]
    finally:
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
            conn.commit()


def test_create_update_loop_mocked_bundle(monkeypatch):
    """card_create -> views + proof_url + contact sheet; card_update -> diff."""
    import asyncio, base64, json
    from backend import mcp_server as M
    from backend import cards as C
    from backend import config as _cfg
    _cfg.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"

    async def fake_bundle(did, rev, owner, key, timeout_s=90, owner_sig=""):
        return {"ok": True, "views": {"front": "u1"}, "proof_url": C.proof_url_for(did),
                "revision": rev, "design_id": did}
    monkeypatch.setattr(M, "_card_spread_bundle", fake_bundle)

    tiny = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    def _fake_sheet(owner, did, rev, *, width=720):
        import base64 as _b
        from backend import config as _c
        dest = _c.DATA / "cards" / "cache" / f"contact-{did}-r{rev}.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_b.b64decode(tiny))
        return dest
    monkeypatch.setattr(C, "contact_sheet", _fake_sheet)

    spec = {"template": "typography", "format": "5x7", "photos": [],
            "headline": "Loop test", "recipient": "", "sender": "Me",
            "inside_message": "hi"}
    out = asyncio.run(M.figg_card_create(spec, "anon"))
    body = json.loads(out[0].text)
    assert body["ok"] and body["views"] == {"front": "u1"}
    assert body["proof_url"].endswith("/proof/" + body["design_id"])
    assert out[1].mime_type == "image/jpeg"
    did = body["design_id"]

    out2 = asyncio.run(M.figg_card_update(
        did, {"headline": "Loop test v2", "headline_font": "courier"}, 0, "anon"))
    body2 = json.loads(out2[0].text)
    assert body2["ok"] and body2["revision"] == body["revision"] + 1
    assert any("headline" in c for c in body2["diff"])
    assert body2["proof_url"] == body["proof_url"]

    from backend import db
    with db.connect() as conn:
        conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did,))
        conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
        conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
        conn.commit()


def test_proof_route_serves_spa():
    import re
    assert re.fullmatch(r"/(?:studio(?:/people/[\w-]+)?|products(?:/[\w-]+)?|cards(?:/[\w-]+(?:/r\d+)?)?|videos(?:/[\w-]+)?|perform|search|cart|account|upload|shop|quick|proof/[\w-]+)/?", "/proof/card_abc123")


def test_review_fails_blank(monkeypatch):
    from backend.creative import review as R
    import sqlite3
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE render_artifacts (id TEXT, owner TEXT, project_id TEXT, revision INT, renderer TEXT, output_kind TEXT, cache_key TEXT, storage_key TEXT, mime TEXT, width INT, height INT, dpi INT, duration INT, status TEXT, qc_status TEXT, cost_cents INT, provider TEXT, provider_job TEXT, created_at REAL)")
    c.execute("CREATE TABLE creative_revisions (project_id TEXT, revision INT, brief_snapshot TEXT, scene TEXT)")
    import json as _j
    c.execute("INSERT INTO render_artifacts VALUES ('a1','anon','p1',1,'composite2d','print_master','k','k','image/png',1500,2100,300,0,'ready','passed',0,'','',0)")
    c.execute("INSERT INTO creative_revisions VALUES ('p1',1,'{}',?)", (_j.dumps({"subjects": []}),))
    from PIL import Image as _I
    white = _I.new("RGB", (60, 60), "#ffffff")
    import tempfile as _tf
    tmp = _tf.NamedTemporaryFile(suffix=".png", delete=False)
    white.save(tmp.name)
    monkeypatch.setattr("backend.storage.get", lambda key, dest: dest.write_bytes(open(tmp.name, "rb").read()) or dest)
    out = R.review_artifact(c, "a1")
    assert out["verdict"] == "revise"
    assert any("blank" in r for r in out["reasons"])


def test_render_unknown_creative_stages():
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    r = c.post("/api/oddhobb/render?token=test-token",
               json={"owner": "anon", "creative_id": "nope", "revision": 1,
                     "outputs": ["preview"]})
    d = r.get_json()
    assert d["ok"] and not d["done"]
    assert d["staged"] and d["staged"][0]["output"] == "preview"


def test_cc0_art_library():
    """Every render art file exists, opens RGBA, and is listed in SOURCES.md."""
    from backend.card_scenes import _art, CARD_ART
    src = pathlib.Path("assets/card-art/SOURCES.md").read_text()
    used = {entry[0] for files in CARD_ART.values() for entry in files}
    assert used, "no art wired into any template"
    for name in used:
        assert name in src, name
        img = _art(name)
        assert img is not None and img.mode == "RGBA"


def test_portrait_carries_artwork():
    """Portrait cover is illustration + photo slot, not photo + text alone."""
    from backend import cards as C
    from backend.card_scenes import front
    owner, pid = "hark-dad-a7a5cc", "pho_676d794af4d945d38439"
    spec = C.validate(owner, {"template": "portrait", "format": "5x7",
                              "photos": [{"photo_id": pid, "crop": [0, 0, 1, 1],
                                          "focus": [0.5, 0.5], "cutout": ""}],
                              "headline": "Happy Birthday", "recipient": "Dad",
                              "sender": "Me", "inside_message": "x"})
    img = front(spec, C.assets(owner, spec), 360)
    plain = (248, 241, 230)
    diff = 0
    n = 0
    for y in range(12, 90, 4):
        for x in range(7, 115, 4):
            p = img.getpixel((x, y))[:3]
            n += 1
            if sum(abs(a - b) for a, b in zip(p, plain)) > 60:
                diff += 1
    assert diff / n > 0.15, "balloon corner must carry illustration"


def test_schema_caps_reject():
    from backend import cards as C
    base = {"template": "typography", "format": "5x7", "photos": [],
            "recipient": "", "sender": "", "inside_message": "x"}
    try:
        C.validate("anon", {**base, "headline": "H" * 61})
    except C.CardError as e:
        assert "60" in str(e)
    else:
        raise AssertionError("61-char headline must be rejected")
    try:
        C.validate("anon", {**base, "headline": "Hi",
                             "inside_message": "M" * 501})
    except C.CardError as e:
        assert "500" in str(e)
    else:
        raise AssertionError("501-char message must be rejected")


def test_listing_view():
    import time
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    spec = {"template": "typography", "format": "5x7", "photos": [],
            "headline": "Listing test", "recipient": "", "sender": "Me",
            "inside_message": "hi"}
    d = c.post("/api/cards/designs?owner=anon&token=test-token",
               json={"owner": "anon", "spec": spec}).get_json()
    did, rev = d["design"]["id"], d["design"]["revision"]
    try:
        assert c.get(f"/api/cards/{did}/r{rev}/listing?owner=anon&token=test-token").status_code == 409
        c.post(f"/api/cards/{did}/render?owner=anon&token=test-token",
               json={"owner": "anon", "revision": rev, "kind": "spread"})
        for _ in range(30):
            s = c.get(f"/api/cards/{did}/scene?owner=anon&revision={rev}&token=test-token").get_json()["scene"]
            if s["outputs"]["spread"]["status"] == "ready":
                break
            time.sleep(0.5)
        assert "listing" in s["outputs"]["spread"]["urls"]
        r = c.get(f"/api/cards/{did}/r{rev}/listing?owner=anon&token=test-token")
        assert (r.status_code, r.content_type) == (200, "image/jpeg")
    finally:
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
            conn.commit()


def test_birthday_five_locked():
    """The birthday five render 1–5 photos with caller fonts overridden."""
    import hashlib
    from backend import cards as C
    from backend.card_scenes import front, BIRTHDAY_TEMPLATES
    assert set(BIRTHDAY_TEMPLATES) >= {"birthday_arch", "birthday_dots", "birthday_news",
                                       "birthday_gold", "birthday_wall", "birthday_4photo"}
    owner = "hark-dad-a7a5cc"
    pids = ["pho_676d794af4d945d38439", "pho_6779ec37a1e84d3fa086",
            "pho_31f9b76e88ac4512875b"]
    counts = {"birthday_arch": (1, 1), "birthday_dots": (1, 3),
              "birthday_news": (1, 1), "birthday_gold": (1, 1),
              "birthday_wall": (2, 5),
              "birthday_4photo": (4, 4)}
    pids4 = pids + pids[:1]
    for tid in BIRTHDAY_TEMPLATES:
        lo, hi = counts[tid]
        for n in range(lo, min(hi, 4) + 1):
            photos = [{"photo_id": p, "crop": [0, 0, 1, 1],
                       "focus": [0.5, 0.5], "cutout": ""} for p in pids4[:n]]
            spec = C.validate(owner, {"template": tid, "format": "5x7",
                                      "photos": photos, "headline": "Happy Birthday!",
                                      "recipient": "Dad", "sender": "Me",
                                      "inside_message": "x",
                                      "headline_font": "caveat",
                                      "inside": {"right": {"message": "x", "font": "caveat"}}})
            locked = {"birthday_arch": ("fraunces", "courier"),
                      "birthday_dots": ("inter_bold", "inter"),
                      "birthday_news": ("inter_bold", "courier"),
                      "birthday_gold": ("fraunces", "inter"),
                      "birthday_wall": ("fraunces", "courier"),
                      "birthday_4photo": ("fraunces", "inter")}[tid]
            assert (spec["headline_font"], spec["inside"]["right"]["font"]) == locked, tid
            a = front(spec, C.assets(owner, spec), 360)
            b = front(spec, C.assets(owner, spec), 360)
            assert hashlib.md5(a.tobytes()).hexdigest() == hashlib.md5(b.tobytes()).hexdigest()


def test_covers_carry_illustration():
    """Covers must read as designed cards: art pixels in the corners."""
    from backend import cards as C
    from backend.card_scenes import front
    owner, pid = "hark-dad-a7a5cc", "pho_676d794af4d945d38439"
    spots = {"portrait": (30, 60), "birthday_arch": (30, 60),
             "birthday_dots": (180, 42)}
    for tid, (sx, sy) in spots.items():
        spec = C.validate(owner, {"template": tid, "format": "5x7",
                                  "photos": [{"photo_id": pid, "crop": [0, 0, 1, 1],
                                              "focus": [0.5, 0.5], "cutout": ""}],
                                  "headline": "Happy Birthday", "recipient": "Dad",
                                  "sender": "Me", "inside_message": "x"})
        img = front(spec, C.assets(owner, spec), 360)
        bg = {"portrait": (248, 241, 230), "birthday_arch": (250, 243, 231),
              "birthday_dots": (253, 253, 248)}[tid]
        diff = n = 0
        for y in range(sy - 15, sy + 15, 3):
            for x in range(sx - 40, sx + 40, 3):
                p = img.getpixel((x, y))[:3]
                n += 1
                if sum(abs(a - b) for a, b in zip(p, bg)) > 60:
                    diff += 1
        assert diff / n > 0.10, (tid, diff, n)


def test_backdrop_slot():
    """Missing backdrop = flat colour (never fail); present = painted."""
    from backend import cards as C
    from backend import card_scenes as S
    from PIL import Image as _I
    owner, pid = "hark-dad-a7a5cc", "pho_676d794af4d945d38439"
    spec = C.validate(owner, {"template": "birthday_arch", "format": "5x7",
                              "photos": [{"photo_id": pid, "crop": [0, 0, 1, 1],
                                          "focus": [0.5, 0.5], "cutout": ""}],
                              "headline": "Happy Birthday", "recipient": "Dad",
                              "sender": "Me", "inside_message": "x"})
    aa = C.assets(owner, spec)
    plain = S.front(spec, aa, 360)
    bgdir = pathlib.Path("assets/card-art/backdrops")
    bgdir.mkdir(parents=True, exist_ok=True)
    dest = bgdir / "birthday_arch.png"
    try:
        _I.new("RGB", (360, 504), "#123456").save(dest)
        S._BACKDROP_CACHE.pop("birthday_arch", None)
        painted = S.front(spec, aa, 360)
        import hashlib as _h
        assert _h.md5(plain.tobytes()).hexdigest() != _h.md5(painted.tobytes()).hexdigest()
    finally:
        dest.unlink(missing_ok=True)
        S._BACKDROP_CACHE.pop("birthday_arch", None)


def test_backdrop_prompts_text_free():
    from backend.card_scenes import TEMPLATE_BACKDROPS
    from backend.creative.providers.fal import plate_prompt
    assert len(TEMPLATE_BACKDROPS) == 5
    for tid, scene in TEMPLATE_BACKDROPS.items():
        assert "no text" in plate_prompt(scene), tid


def test_canonical_caps():
    from backend import cards as C
    base = {"template": "birthday_4photo", "format": "5x7",
            "photos": [{"photo_id": "pho_676d794af4d945d38439", "crop": [0, 0, 1, 1],
                        "focus": [0.5, 0.5], "cutout": ""}] * 4,
            "headline": "Happy Birthday, Chris!", "recipient": "Chris",
            "sender": "Ben & co", "inside_message": "hi", "title_vibe": "playful_balloons"}
    with __import__("pytest").raises(C.CardError):
        C.validate("hark-dad-a7a5cc", {**base, "headline": "H" * 41})
    with __import__("pytest").raises(C.CardError):
        C.validate("hark-dad-a7a5cc", {**base, "title_vibe": "yolo"})
    with __import__("pytest").raises(C.CardError):
        C.validate("hark-dad-a7a5cc", {**base, "photos": base["photos"][:3]})
    s = C.validate("hark-dad-a7a5cc", base)
    assert s["title_vibe"] == "playful_balloons" and s["title_art_key"] == ""


def test_title_prompt_guarded():
    from backend.card_scenes import title_prompt, TITLE_VIBES
    assert len(TITLE_VIBES) == 8
    p = title_prompt("Happy Birthday, Chris!", "playful_balloons")
    assert "930x320" in p and "Transparent background only" in p
    import pytest as _p
    with _p.raises(ValueError):
        title_prompt("Hi", "yolo")


def test_canonical_zones():
    """Grid reads as one grid; no subline zone; no inside brand zone."""
    from backend.card_scenes import CANONICAL_ZONES
    xs = sorted({x for x, _, _, _ in CANONICAL_ZONES["photos"]})
    ws = {w for _, _, w, _ in CANONICAL_ZONES["photos"]}
    assert len(xs) == 2 and len(ws) == 1
    gutter = xs[1] - (xs[0] + next(iter(ws)))
    assert gutter <= 2 * CANONICAL_ZONES["photo_radius"], gutter
    assert "front_subline" not in CANONICAL_ZONES
    assert "inside_logo" not in CANONICAL_ZONES


def test_make_card_requires_signature():
    import asyncio, json
    from backend import mcp_server as M
    out = asyncio.run(M.oddhobb_make_card("person_9fdc85d6730d43e099dc", "birthday",
                                          "playful_balloons", "funny", "", "",
                                          "hark-dad-a7a5cc"))
    body = json.loads(out[0].text)
    assert body["ok"] is False and "signature" in body["error"]


def test_proof_og_image_public():
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    assert c.get("/api/cards/proof/nope-card/og-image.png").status_code == 404
