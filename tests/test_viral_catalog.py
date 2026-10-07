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
