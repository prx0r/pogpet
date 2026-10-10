"""Recipe-owned copy: headlines/inside/title_vibe come from the recipe."""
from backend import config, db
from backend import cards as _cards
from backend.recipes import compiler as C
from backend.recipes import registry as R


def _subject_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    from backend import studio_library
    studio_library.init()
    _cards.init()
    with db.connect() as c:
        c.execute("INSERT INTO studio_subjects (id,owner,name,kind,created_at)"
                  " VALUES (?,?,?,?,?)", ("sub_c", "oc", "Dad", "person", 1.0))
        for i in range(4):
            pid = db.insert_photo(
                c, owner="oc", sha256=f"sh-c{i}", r2_key=f"owners/x/c{i}.jpg",
                mime="image/jpeg", width=1200, height=900, bytes=1000,
                orig_name=f"c{i}.jpg")
            c.execute("INSERT INTO photo_subjects VALUES (?,?,?,?,?)",
                      (pid, "sub_c", "", 1, "user-confirmed"))
        c.commit()
    return {"id": "sub_c", "name": "Dad", "relationship": "father",
            "interests": ["golf"], "memories": []}


def test_news_recipe_owns_copy(tmp_path, monkeypatch):
    sub = _subject_db(tmp_path, monkeypatch)
    r = C.compile("oc", "birthday_news_1photo_v2", subject=sub,
                  occasion="birthday", tone="dry", title_art=False, via="ui")
    assert r["ok"], r
    spec = r["design"]["spec"]
    assert spec["headline"] == "Dad Makes Headlines", spec["headline"]
    assert "presses" in spec["inside_message"] or "Extra" in spec["inside_message"]
    assert "Happy Birthday, Dad!" not in spec["headline"]


def test_recipe_copy_overrides_default(tmp_path, monkeypatch):
    sub = _subject_db(tmp_path, monkeypatch)
    r = C.compile("oc", "birthday_dots_1photo_v2", subject=sub,
                  occasion="birthday", tone="funny", title_art=False, via="ui")
    assert r["ok"], r
    assert r["design"]["spec"]["headline"] == "Dots For Dad"


def test_title_vibe_from_recipe(tmp_path, monkeypatch):
    # validate() persists title_vibe on the canonical template and accepts
    # recipe vibes everywhere (used at title-art generation time).
    sub = _subject_db(tmp_path, monkeypatch)
    r = C.compile("oc", "birthday_gold_1photo_v2", subject=sub,
                  occasion="birthday", title_art=False, via="ui")
    assert r["ok"], r  # custom vibe must not raise in validate()
    r4 = C.compile("oc", "birthday_four_photos_party_title_v2", subject=sub,
                   occasion="birthday", title_art=False, via="ui")
    assert r4["ok"], r4
    assert r4["design"]["spec"]["title_vibe"] == "playful_balloons"
