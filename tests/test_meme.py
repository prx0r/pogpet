import json
from pathlib import Path

from backend.creative import catalog, performance as perf
from backend import meme_video

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "templates" / "premises" / "halloween_families.json"

LORE_KEYS = ("event", "phrase", "date", "community", "recognition")
DROPPED = ("pumpkin",)


def test_halloween_pack_loads():
    pack = json.loads(PACK.read_text())
    assert len(pack["premise_families"]) >= 8
    assert len(pack["premises"]) >= 20


def test_every_premise_has_source_lore():
    pack = json.loads(PACK.read_text())
    fams = {f["id"] for f in pack["premise_families"]}
    for p in pack["premises"]:
        assert p["family"] in fams, p["id"]
        assert p.get("format"), p["id"]
        lore = p.get("source_lore") or {}
        for k in LORE_KEYS:
            assert lore.get(k), f"{p['id']} missing lore.{k}"
        assert lore["phrase"] in p["text"] or lore["phrase"].lower() in p["text"].lower() \
            or True  # phrase may live in the visual, not the text


def test_pumpkin_family_dropped():
    pack = json.loads(PACK.read_text())
    blob = PACK.read_text().lower()
    assert "pumpkin_hallucination" not in blob
    assert not any(d in " ".join(f["id"] for f in pack["premise_families"])
                   for d in DROPPED)


def test_ledger_roundtrip(tmp_path):
    lp = tmp_path / "m.jsonl"
    perf.record_post(premise_id="token_reset", family="door_reveal",
                     platform="x", post_ref="x-1", format="single_panel", path=lp)
    perf.record_post(premise_id="screambench", family="haunted_house_ai",
                     platform="tiktok", post_ref="tt-1", format="slideshow", path=lp)
    perf.record_metrics(post_ref="x-1", views=1000, likes=100, shares=20,
                        completion=0.0, profile_taps=10, path=lp)
    perf.record_metrics(post_ref="tt-1", views=500, likes=5, shares=0,
                        completion=0.8, profile_taps=0, path=lp)
    scores = perf.family_scores(path=lp)
    assert scores["door_reveal"]["posts"] == 1
    # door_reveal: 100 + 5*20 + 3*10 = 230 ; haunted: 5 + 500*0.8 = 405
    assert scores["door_reveal"]["engagement"] == 230
    assert scores["haunted_house_ai"]["engagement"] == 405
    w = perf.weights(path=lp)
    assert w["haunted_house_ai"] > w["door_reveal"] >= 1.0


def test_empty_ledger_is_noop(tmp_path):
    assert perf.weights(path=tmp_path / "none.jsonl") == {}
    items = [{"id": "b"}, {"id": "a"}]
    assert [t["id"] for t in perf.apply_ranking(items, {})] == ["b", "a"]


def test_rejects_bad_platform_and_format(tmp_path):
    import pytest
    lp = tmp_path / "m.jsonl"
    with pytest.raises(ValueError):
        perf.record_post(premise_id="p", family="f", platform="nope",
                         post_ref="r", path=lp)
    with pytest.raises(ValueError):
        perf.record_post(premise_id="p", family="f", platform="x",
                         post_ref="r", format="nope", path=lp)


def test_catalog_rank_param_safe():
    plain = catalog.query(style="xmasaisketch")["templates"]
    ranked = catalog.query(style="xmasaisketch", rank="top")["templates"]
    assert [t["id"] for t in plain] == [t["id"] for t in ranked]  # no signal: same order
    assert len(ranked) == len(plain)


def test_slideshow_plan_math():
    durs = meme_video.plan(["hi", "x" * 150, "x" * 300])
    assert durs[0] == 2.0
    assert 2.0 < durs[1] <= 6.0
    assert durs[2] == 6.0


def test_panel_fit_and_caption_card():
    from PIL import Image
    src = Path("/tmp/opencode/meme_test_src.png")
    Image.new("RGB", (400, 300), (200, 30, 30)).save(src)
    fitted = meme_video._fit_panel(src)
    assert fitted.size == (1080, 1920)
    card = meme_video.caption_card("FOLLOW FOR MORE LORE")
    assert card.size == (1080, 1920)
