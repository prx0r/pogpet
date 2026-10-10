"""Motion library: hook rigs + recipe validation. Blender execution next."""
import pytest

from backend.creative import motion as M


def test_library_loads():
    lib = M.library()
    assert len(lib["hooks"]) == 8
    assert {b["id"] for b in lib["body"]} == {"spin360", "detail"}
    assert {e["id"] for e in lib["end"]} == {"logo"}
    for h in lib["hooks"]:
        assert h["duration"][0] >= 1.0, h["id"]
        assert h["product_enter_s"] <= 0.5, h["id"]


def test_valid_recipe():
    r = {"hook": "rack_focus", "body": ["spin360", "detail"],
         "end": "logo", "mood": "xmas"}
    assert M.validate_recipe(r) == []
    d = M.describe(r)
    assert d["ok"] and d["hook"]["id"] == "rack_focus"


def test_bad_recipe_rejected():
    assert M.validate_recipe({}) != []
    assert M.validate_recipe({"hook": "nope", "body": ["spin360"],
                              "end": "logo", "mood": "xmas"}) != []
    assert M.validate_recipe({"hook": "rack_focus", "body": ["nope"],
                              "end": "logo", "mood": "xmas"}) != []
    assert M.validate_recipe({"hook": "rack_focus", "body": [],
                              "end": "logo", "mood": "xmas"}) != []
    assert M.validate_recipe({"hook": "rack_focus", "body": ["spin360"],
                              "end": "logo", "mood": "nope"}) != []
    assert M.describe({"hook": "nope"})["ok"] is False


def test_cache_key_stable():
    r = {"hook": "push_dolly", "body": ["spin360"], "end": "logo",
         "mood": "birthday"}
    assert M.cache_key("abc", r) == M.cache_key("abc", dict(r))
    assert M.cache_key("abc", r) != M.cache_key("abd", r)
    assert len(M.cache_key("abc", r)) == 16
