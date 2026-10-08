"""Card P0 guardrails + checkout: fixed price, validators in save,
source stamping, mcp_status, Shopify draft shape, webhook HMAC, openapi."""
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
    assert M.MCP_VERSION == "1.7.0"


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
        assert set(urls) == {"front", "inside_left", "inside_right", "back"}
        for part in urls:
            r = c.get(f"/api/cards/{did}/r{rev}/spread/{part}?owner=anon&token=test-token")
            assert (r.status_code, r.content_type) == (200, "image/png"), part
    finally:
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM card_jobs WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_revisions WHERE design_id=?", (did,))
            conn.execute("DELETE FROM card_designs WHERE id=?", (did,))
            conn.commit()
