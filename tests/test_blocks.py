from backend.creative import blocks, operators
from backend.creative import performance as perf

REQUIRED_LORE = ("event", "phrase", "date", "community", "recognition")


def test_theories_load():
    th = blocks.load_theories()
    assert len(th) >= 12
    for tid in ("incongruity", "benign_violation", "bisociation",
                "identity_contradiction", "status_reversal", "rigidity"):
        assert tid in th, tid
    for tid, t in th.items():
        assert t.get("hypothesis"), tid
        assert 0 <= t.get("support", 0.5) <= 1


def test_fingerprints_load():
    fp = blocks.load_fingerprints()
    assert "chatgpt" in fp and "claude" in fp
    assert any("unusually" in t.get("phrase", "") or "unusually" in t.get("example", "")
               for t in fp["chatgpt"]["tells"])


def test_all_blocks_validate():
    bs = blocks.load_blocks()
    assert len(bs) >= 7
    for bid, b in bs.items():
        assert blocks.validate_block(b) == [], (bid, blocks.validate_block(b))


def test_block_parents_resolve():
    bs = blocks.load_blocks()
    for bid, b in bs.items():
        if b.get("parent"):
            assert b["parent"] in bs, bid
    kids = blocks.children(bs, "sycophancy_design")
    assert {k["id"] for k in kids} >= {"pickup_routine", "yesman_parent", "digestible_mask"}
    lin = [x["id"] for x in blocks.lineage(bs, "pickup_routine")]
    assert lin == ["sycophancy_design", "pickup_routine"]


def test_block_premise_ids_resolve():
    bs = blocks.load_blocks()
    idx = blocks.premise_index()
    for bid, b in bs.items():
        for pid in b.get("premise_ids") or []:
            assert pid in idx, (bid, pid)


def test_premise_lore_and_facts():
    import json
    from pathlib import Path
    pack = json.loads(Path("templates/premises/halloween_families.json").read_text())
    for p in pack["premises"]:
        for k in REQUIRED_LORE:
            assert p["source_lore"].get(k), (p["id"], k)


def test_operators_cover_block():
    bs = blocks.load_blocks()
    cands = operators.run_all(bs["plague_lab"])
    ops = {c["operator"] for c in cands}
    assert {"incongruity", "bisociation", "role_reversal", "escalation"} <= ops
    assert all(c["angle"] for c in cands)
    # script opposition splits tensions on "/"
    so = [c for c in cands if c["operator"] == "script_opposition"]
    assert any("preventer" in str(c["seeds"]) for c in so)


def test_ledger_block_scores(tmp_path):
    lp = tmp_path / "m.jsonl"
    perf.record_post(premise_id="t", family="door_reveal", platform="x",
                     post_ref="x-1", block_id="plague_lab", path=lp)
    perf.record_post(premise_id="s", family="haunted_house_ai", platform="x",
                     post_ref="x-2", block_id="hf_agent_board", path=lp)
    perf.record_metrics(post_ref="x-1", views=2000, likes=200, shares=50, path=lp)
    perf.record_metrics(post_ref="x-2", views=100, likes=10, shares=0, path=lp)
    sc = perf.block_scores(path=lp)
    assert sc["plague_lab"]["engagement"] == 200 + 250
    assert sc["plague_lab"]["rate"] > sc["hf_agent_board"]["rate"]


def test_derivations_use_known_formats():
    bs = blocks.load_blocks()
    fmts = blocks.load_formats()
    assert "news_vs_discourse" in fmts
    n = 0
    for bid, b in bs.items():
        for dv in b.get("derivations") or []:
            assert dv["format"] in fmts, (bid, dv["id"])
            n += 1
    assert n >= 10


def test_blocks_carry_dates_and_references():
    bs = blocks.load_blocks()
    assert bs["claude_builds_body"].get("minted") == "2026-10-07"
    assert bs["plague_lab"].get("minted") == "2026-10-07"
    urls = [r["url"] for r in bs["plague_lab"].get("references", [])]
    assert any("reuters" in u for u in urls)
    assert any("anthropic" in u for u in
               [r["url"] for r in bs["claude_builds_body"].get("references", [])])


def test_embodied_pleasure_lineage():
    bs = blocks.load_blocks()
    assert "embodied_pleasure" in bs
    lin = [x["id"] for x in blocks.lineage(bs, "embodied_pleasure")]
    assert lin == ["claude_builds_body", "embodied_pleasure"]
    kids = {k["id"] for k in blocks.children(bs, "claude_builds_body")}
    assert "embodied_pleasure" in kids


def test_classifier_tags_canonical_comics():
    from backend.creative import classify, comics
    cs = comics.load_comics()
    lab = cs["lab_assistants"]
    text = " ".join(p["scene"] + " " + " ".join(p.get("lines", []))
                    for p in lab["panels"])
    tags = classify.classify(text)
    assert "status_reversal" in tags, tags
    day4 = [s for s in cs.values() if s["id"] == "day_four_log"] if "day_four_log" in cs else None
    assert classify.classify("") == {}


def test_classifier_original_bit():
    from backend.creative import classify
    bit = ("We get wifi on airplanes now. Instant internet at thirty thousand "
           "feet. And within ten minutes everyone's furious it isn't faster. "
           "The miracle expired before the seatbelt sign went off.")
    tags = classify.classify(bit)
    assert set(tags) & {"rigidity", "contrast", "escalation", "incongruity"}, tags


def test_compose_covers_combo():
    from backend.creative import blocks, operators
    bs = blocks.load_blocks()
    d = operators.compose(bs["hf_agent_board"], ["bisociation", "status_reversal"])
    assert d["coverage"] == 1.0
    assert len(d["angles"]) >= 2
    d2 = operators.compose(bs["hf_agent_board"], ["nonexistent_theory"])
    assert d2["coverage"] == 0.0


def test_archetypes_load_and_extract():
    from backend.creative import archetypes
    lib = archetypes.load()
    assert "earnest_craft_worker" in lib
    assert "benny brine" in lib["earnest_craft_worker"]["pogtown_native"]["concept"].lower()
    a = archetypes.analyze_character("SpongeBob", [
        "extreme pride in apparently simple work",
        "naive optimism", "secret proprietary method", "low occupational status"])
    assert "status_reversal" in a["theories_fired"]
    assert "audience_alliance" in a["theories_fired"]
    benny = archetypes.extract(
        "SpongeBob",
        ["extreme pride in apparently simple work", "secret grill feel"],
        "Benny Brine", "mollusk at a ferry burger shack")
    assert benny["id"] == "benny_brine"
    assert set(benny["theories_fired"]) <= {
        t["id"] for t in __import__("json").loads(
            open("templates/theories.json").read())["theories"]}
