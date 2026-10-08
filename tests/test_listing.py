from backend import config
from backend import listings as L


def test_recipes_match_line_methods():
    for line, rec in L.RECIPES.items():
        if line in config.STUDIO_LINES:
            method = (config.STUDIO_LINES[line].get("personalization") or {}).get("method")
            assert rec["method"] == method, line
        assert (L.PROD / rec["hero"]).is_file(), rec["hero"]


def test_status_split_present():
    for lid, spec in config.STUDIO_LINES.items():
        assert spec.get("production") in ("sample_pending", "verified"), lid
        assert spec.get("etsy") in ("draft", "live"), lid
    # honest today: nothing verified (no production 3MF anywhere yet)
    assert all(s.get("production") == "sample_pending"
               for s in config.STUDIO_LINES.values())


def test_factory_builds_and_gates(tmp_path, monkeypatch):
    import scripts.listing_factory as F
    monkeypatch.setattr(L, "OUT", tmp_path / "listings")
    listing = F.build("ornament", "demo")
    assert listing["ready"] >= 3
    assert (tmp_path / "listings" / "ornament" / "demo" / "02-before_after.png").is_file()
    assert (tmp_path / "listings" / "ornament" / "demo" / "listing.json").is_file()
    assert (tmp_path / "listings" / "ornament" / "demo" / "listing.md").is_file()
    import pytest
    with pytest.raises(ValueError, match="no photos"):
        F.build("golf_marker", "dad")
    with pytest.raises(ValueError, match="refusing --publish"):
        F.build("ornament", "demo", publish=True)


def test_preview_endpoint(tmp_path, monkeypatch):
    import backend.server as S
    monkeypatch.setattr(config, "API_TOKEN", "test-token")
    monkeypatch.setattr(L, "OUT", tmp_path / "listings")
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    r = c.get("/api/products/ornament/preview?subject=demo&token=test-token")
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    d = r.get_json()
    assert d["story"] and d["hero"].endswith("prod-hero.png")
    assert d["status"]["production"] == "sample_pending"
    r2 = c.get("/api/products/ornament/preview?subject=dad&token=test-token")
    assert r2.status_code == 404
    r3 = c.get("/api/products/nope/preview?subject=demo&token=test-token")
    assert r3.status_code == 404
