import backend.server as S
from backend import config
from backend.creative import art


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_TOKEN", "test-token")
    monkeypatch.setattr(config, "DATA", tmp_path)
    S.config.API_TOKEN = "test-token"
    return S.app.test_client()


def test_formats_and_list():
    assert art.FORMATS["postcard"]["price_cents"] == 399
    assert art.FORMATS["mp4"]["price_cents"] == 699
    items = art.list_art()
    assert len(items) == 9
    assert all("formats" in i and "postcard" in i["formats"] for i in items)


def test_art_endpoints(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/creative/art?token=test-token")
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] and len(d["items"]) == 9
    o = c.post("/api/creative/art/order?token=test-token",
               json={"art_id": "lab_assistants", "format": "postcard",
                     "qty": 2, "owner": "anon"})
    assert o.status_code == 200, o.get_data(as_text=True)[:200]
    od = o.get_json()
    assert od["order"]["price_cents"] == 798
    assert od["order"]["status"] == "pending_checkout"
    bad = c.post("/api/creative/art/order?token=test-token",
                 json={"art_id": "lab_assistants", "format": "yacht", "owner": "anon"})
    assert bad.status_code == 400
    missing = c.post("/api/creative/art/order?token=test-token",
                     json={"art_id": "nope", "format": "mug", "owner": "anon"})
    assert missing.status_code == 404


def test_plates_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    p = art.text_plate("DAY 1", ["Focus group worried.", "Government rebrands."],
                       "Did you try Friendly Computer?")
    assert p.exists() and p.stat().st_size > 1000
    from PIL import Image
    assert Image.open(p).size == (1080, 1920)
    assert str(art.mp4_path("lab_assistants")).endswith("lab_assistants.ryan.mp4")
