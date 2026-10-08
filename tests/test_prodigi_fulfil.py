from backend import config


def _client(tmp_path, monkeypatch):
    import backend.server as S
    monkeypatch.setattr(config, "API_TOKEN", "test-token")
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "figg.db")
    S.config.API_TOKEN = "test-token"
    return S.app.test_client()


def _design(c, owner="fam", sig=None):
    from backend import cards as C
    C.init()
    photos = c.post("/api/cards/designs?token=test-token",
                    json={"spec": {"template": "typography", "format": "5x7",
                                   "headline": "Hi", "photos": []},
                          "owner": owner, "owner_sig": sig}).get_json()["design"]
    did, rev = photos["id"], photos["revision"]
    job = c.post(f"/api/cards/{did}/render?token=test-token",
                 json={"revision": rev, "kind": "export",
                       "owner": owner, "owner_sig": sig}).get_json()["job"]
    import time
    for _ in range(40):
        j = c.get(f"/api/cards/jobs/{job['id']}?owner={owner}&owner_sig={sig}&token=test-token").get_json()["job"]
        if j["status"] in ("ready", "failed"):
            break
        time.sleep(0.5)
    assert j["status"] == "ready", j
    return did, rev


def test_fulfil_gates(tmp_path, monkeypatch):
    from backend import config as C
    c = _client(tmp_path, monkeypatch)
    sig = C.sign_owner("fam")
    did, rev = _design(c, sig=sig)
    base = {"owner": "fam", "owner_sig": sig, "qty": 1, "revision": rev,
            "idempotency_key": "k-1234567890", "fulfil": True}
    monkeypatch.delitem(C.PRODIGI_PRODUCTS["greeting_card"], "sku", raising=False)
    try:
        r = c.post(f"/api/cards/{did}/order?token=test-token", json=base)
        assert r.status_code == 410, r.get_data(as_text=True)[:200]  # direct fulfil gated (use checkout)
    finally:
        C.PRODIGI_PRODUCTS["greeting_card"]["sku"] = "CLASSIC-GRE-FEDR-7X5-BLA"
    monkeypatch.setitem(C.PRODIGI_PRODUCTS["greeting_card"], "sku", "TEST-SKU")
    monkeypatch.setenv("ALLOW_DIRECT_PRODIGI", "1")
    try:
        r2 = c.post(f"/api/cards/{did}/order?token=test-token",
                    json={**base, "idempotency_key": "k-1234567891",
                          "recipient": {"name": "x"}})
        assert r2.status_code == 400  # address required next
    finally:
        C.PRODIGI_PRODUCTS["greeting_card"].pop("sku", None)
        monkeypatch.delenv("ALLOW_DIRECT_PRODIGI", raising=False)


def test_fulfil_happy_path_mocked(tmp_path, monkeypatch):
    from backend import config as C
    from backend import prodigi as P
    from backend import r2presign as R2
    c = _client(tmp_path, monkeypatch)
    sig = C.sign_owner("fam")
    did, rev = _design(c, sig=sig)
    monkeypatch.setitem(C.PRODIGI_PRODUCTS["greeting_card"], "sku", "TEST-SKU")
    monkeypatch.setattr(P, "create_order",
                        lambda *a, **k: {"ok": True, "id": "pro_1",
                                         "status": "received", "sku": a[0],
                                         "copies": a[1]})
    monkeypatch.setattr(R2, "put_temp", lambda local, key=None: "tmp/test.pdf")
    monkeypatch.setattr(R2, "presigned_url",
                        lambda key, expires_s=86400: "https://r2.test/tmp/test.pdf")
    monkeypatch.setenv("ALLOW_DIRECT_PRODIGI", "1")
    try:
        r = c.post(f"/api/cards/{did}/order?token=test-token",
                   json={"owner": "fam", "owner_sig": sig, "qty": 1,
                         "revision": rev, "idempotency_key": "k-mock-123456",
                         "fulfil": True,
                         "recipient": {"name": "Cathy", "line1": "1 Test Rd",
                                       "town": "London", "postcode": "E1 1AA",
                                       "country": "GB"}})
        assert r.status_code == 200, r.get_data(as_text=True)[:300]
        d = r.get_json()
        assert d["order"]["status"] == "fulfilled"
        assert d["order"]["prodigi_ref"] == "pro_1"
        assert d["prodigi"]["ok"] is True
    finally:
        C.PRODIGI_PRODUCTS["greeting_card"].pop("sku", None)
        monkeypatch.delenv("ALLOW_DIRECT_PRODIGI", raising=False)


def test_prodigi_validation_no_network():
    from backend import prodigi as P
    import pytest
    with pytest.raises(P.ProdigiError):
        P.create_order("X", 1, "http://x/y.pdf", {"name": "A"})
