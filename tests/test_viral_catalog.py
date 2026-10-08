from backend.creative import catalog, templates

def test_viral_catalog_has_styles_and_templates():
    cat = catalog.load()
    assert len(cat["styles"]) >= 7
    assert len(cat["templates"]) >= 20
    assert any(t["id"] == "goblin_hallucination" for t in cat["templates"])

def test_catalog_templates_are_executable():
    reg = templates.load_all()
    assert "agent_managers" in reg
    assert "four_panel_family" in reg
    assert reg["four_panel_family"]["presentation"]["style"] == "comicstory"

def test_catalog_filter():
    r = catalog.query(style="sportspresser", occasion="fathers_day")
    assert r["count"] >= 2
    assert all(x["style"] == "sportspresser" for x in r["templates"])


def test_catalog_preview_renders_with_photo():
    import io
    from PIL import Image, ImageDraw
    from backend import config
    config.API_TOKEN = "test-token"
    import backend.server as S
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    img = Image.new("RGB", (800, 1000), "#f4e8cd")
    d = ImageDraw.Draw(img)
    d.rectangle((70, 150, 730, 850), fill=(60, 90, 120))
    d.ellipse((260, 190, 540, 470), fill="#dfb295")
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    buf.seek(0)
    up = c.post("/api/photos?owner=anon&token=test-token",
                data={"owner": "anon", "photo": (buf, "rail.jpg")},
                content_type="multipart/form-data").get_json()
    assert up["ok"], up
    pid = up["photo"]["id"]
    try:
        r = c.get(f"/api/creative/catalog/preview?template_id=breaking_news&photo_id={pid}&owner=anon&token=test-token")
        assert (r.status_code, r.content_type) == (200, "image/jpeg"), r.status_code
        assert len(r.data) > 5000
        # cached second hit serves the same bytes without re-rendering
        r2 = c.get(f"/api/creative/catalog/preview?template_id=breaking_news&photo_id={pid}&owner=anon&token=test-token")
        assert (r2.status_code, r2.data) == (200, r.data)
        assert c.get(f"/api/creative/catalog/preview?template_id=nope&photo_id={pid}&owner=anon&token=test-token").status_code == 404
        assert c.get(f"/api/creative/catalog/preview?template_id=breaking_news&photo_id=nope&owner=anon&token=test-token").status_code == 404
    finally:
        from backend import db
        with db.connect() as conn:
            conn.execute("DELETE FROM photos WHERE id=?", (pid,))
            conn.commit()
