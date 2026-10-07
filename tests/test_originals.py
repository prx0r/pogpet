import json
from pathlib import Path

from backend.creative import catalog, templates

ROOT = Path(__file__).resolve().parents[1]


def test_original_style_exists():
    cat = catalog.load()
    ids = [s["id"] for s in cat["styles"]]
    assert "original" in ids


def test_original_template_is_executable():
    reg = templates.load_all()
    assert "superintelligence_rebrand" in reg
    m = reg["superintelligence_rebrand"]
    assert m["taxonomy"]["styles"] == ["original"]
    assert m["requirements"]["subjects"] == 0
    assert m["requirements"]["face_photos_min"] == 0


def test_original_template_queryable():
    r = catalog.query(style="original")
    assert r["count"] >= 1
    assert all(x["style"] == "original" for x in r["templates"])


def test_original_premise_pack_loads():
    pack = json.loads((ROOT / "templates" / "premises" / "original_families.json").read_text())
    fams = {f["id"] for f in pack["premise_families"]}
    assert {"elf_displacement", "agent_overload", "hallucination", "slop_parody",
            "overoptimization", "bureaucratic_christmas", "rebrand_theatre"} <= fams
    assert len(pack["premises"]) >= 20


def test_original_bible_saved():
    bible = (ROOT / "docs" / "original-premise-bible.md").read_text()
    assert "80% is premise quality" in bible
    assert "elf_displacement" in bible
    assert "Same sleigh, bigger vision." in bible
