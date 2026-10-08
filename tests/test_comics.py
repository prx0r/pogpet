from pathlib import Path

from backend.creative import blocks, comics


def test_canonical_comics_validate():
    cs = comics.load_comics()
    assert len(cs) == 9
    for cid, s in cs.items():
        assert comics.validate_script(s) == [], (cid, comics.validate_script(s))
    claude = [s for s in cs.values() if s["_pack"] == "claude_wetlab_5"]
    assert len(claude) == 5


def test_comic_theory_combos_are_distinct():
    cs = comics.load_comics()
    packs: dict[str, list] = {}
    for s in cs.values():
        packs.setdefault(s["_pack"], []).append(tuple(s["theory_combo"]))
    for pack, combos in packs.items():
        assert len(set(combos)) == len(combos), pack


def test_candidate_selection_picks_five_diverse():
    bs = blocks.load_blocks()
    cands = comics.candidates(bs["claude_builds_body"])
    five = comics.select_five(cands)
    assert len(five) == 5
    assert len({c["operator"] for c in five}) == 5


def test_rank_never_raises_and_is_ordered():
    bs = blocks.load_blocks()
    five = comics.select_five(comics.candidates(bs["plague_lab"]))
    ranked = comics.rank(five)
    assert len(ranked) == 5
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(r["scored_by"] in ("jev", "heuristic") for r in ranked)


def test_video_inputs_and_card(tmp_path):
    cs = comics.load_comics()
    s = cs["lab_assistants"]
    for i in range(4):
        (tmp_path / f"panel_{i}.png").write_bytes(b"fake")
    imgs, caps = comics.to_video_inputs(s, tmp_path)
    assert len(imgs) == 4 and len(caps) == 4
    assert caps[-1].startswith("The scientists eventually")
    card = comics.to_card(s)
    assert card["headline"] == "DAY 12 OF ANTHROPIC'S WET LAB"
    assert card["style_id"] == "original"
