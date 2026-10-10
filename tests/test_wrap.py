"""Wrap vertical slice: repeat renderer + internal compile path. No network."""
import json

import pytest
from PIL import Image as _I

from backend.renderers import wrap as W


def _motif(path, size=256, color=(200, 60, 60, 255)):
    _I.new("RGBA", (size, size), color).save(path)
    return str(path)


def test_sheet_exact_print_px_and_deterministic(tmp_path):
    m = _motif(tmp_path / "m.png")
    a = W.render_sheet(m, sku="WRAP-1-50X70", mode="classic")
    b = W.render_sheet(m, sku="WRAP-1-50X70", mode="classic")
    assert a.size == (2952, 4133)
    assert W.sheet_hash(a) == W.sheet_hash(b)
    c = W.render_sheet(m, sku="WRAP-1-50X70", mode="scattered")
    assert W.sheet_hash(a) != W.sheet_hash(c)
    d = W.render_sheet(m, sku="WRAP-1-50X70", mode="badge")
    assert d.size == (2952, 4133)
    p = W.sheet_preview(a)
    assert max(p.size) == 900


def test_bad_inputs_rejected(tmp_path):
    m = _motif(tmp_path / "m.png")
    with pytest.raises(ValueError):
        W.render_sheet(m, sku="WRAP-NOPE")
    with pytest.raises(ValueError):
        W.render_sheet(m, mode="nope")


def test_compile_wrap_end_to_end_offline(tmp_path, monkeypatch):
    from backend import config, db, studio_library
    from backend.recipes import compiler as C

    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    studio_library.init()
    owner = "wrap_owner"
    with db.connect() as c:
        c.execute("INSERT INTO studio_subjects (id,owner,name,kind,created_at)"
                  " VALUES (?,?,?,?,?)", ("sub_wrap", owner, "Biscuit", "pet", 1.0))
        pid = db.insert_photo(
            c, owner=owner, sha256="sh-wrap", r2_key="owners/x/w.jpg",
            mime="image/jpeg", width=1200, height=900, bytes=1000,
            orig_name="w.jpg")
        c.execute("INSERT INTO photo_subjects VALUES (?,?,?,?,?)",
                  (pid, "sub_wrap", "", 1, "user-confirmed"))
        c.commit()
    motif = _motif(tmp_path / "santa.png")
    # unknown subject rejected, not raised
    assert C.compile_wrap(owner, "wrap_pet_santa_repeat_v1",
                          subject={})["ok"] is False
    r = C.compile_wrap(owner, "wrap_pet_santa_repeat_v1",
                       subject={"id": "sub_wrap", "name": "Biscuit"},
                       motif_path=motif, mode="classic")
    assert r["ok"] is True, r
    w = r["wrap"]
    assert w["sku"] == "WRAP-1-50X70" and w["sheet_px"] == [2952, 4133]
    assert w["price_cents"] == 1499
    import os
    assert os.path.isfile(w["local_sheet"]) and os.path.isfile(w["local_preview"])
    # bad recipe / bad motif fail closed
    assert C.compile_wrap(owner, "nope_v1",
                          subject={"id": "sub_wrap"})["ok"] is False
    assert C.compile_wrap(owner, "wrap_pet_santa_repeat_v1",
                          subject={"id": "sub_wrap"},
                          motif_path=str(tmp_path / "missing.png"))["ok"] is False


def test_wrap_recipe_points_at_transform():
    r = json.load(open("recipes/wrap_pet_santa_repeat_v1.json"))
    assert r["generation"]["motif"]["transform_id"] == "pet_santa_v1"
    assert "capability" not in r["generation"]["motif"]
