from backend.creative import blocks, regulars
from backend.creative import comics


def test_events_load_and_validate():
    evs = blocks.load_events()
    assert "plague_irkutsk_202610" in evs
    for eid, e in evs.items():
        assert blocks.validate_event(e) == [], (eid, blocks.validate_event(e))
    plague = evs["plague_irkutsk_202610"]
    statuses = {c["status"] for c in plague["claims"]}
    assert "unconfirmed" in statuses  # plague-as-cause stays unconfirmed
    assert plague["status"] == "developing"


def test_all_premise_packs_validate():
    bs = blocks.load_blocks()
    idx = blocks.premise_index()
    assert len(idx) >= 50
    for pid, p in idx.items():
        assert blocks.validate_premise(p, bs) == [], (pid, blocks.validate_premise(p, bs))


def test_embodiment_premises_carry_operators():
    idx = blocks.premise_index()
    lab = idx["lab_assistants"]
    assert lab["block"] == "claude_builds_body"
    assert "status_reversal" in lab["operators"]
    assert lab["standard"]["reframes_reality"] is True


def test_regulars_scoring():
    bs = blocks.load_blocks()
    idx = blocks.premise_index()
    cs = comics.load_comics()
    scores = regulars.score_characters(bs, idx, cs)
    assert "claude" in scores
    assert scores["claude"]["fertility"] >= 5
    assert scores["claude"]["coherence"] >= 1
    shortlist = regulars.regular_candidates(scores)
    assert shortlist[0] == "claude"
    # novelty/self-awareness/callbacks arrive with performance history
    assert scores["claude"]["novelty"] is None


def test_connections_resolve_when_present():
    bs = blocks.load_blocks()
    for bid, b in bs.items():
        assert blocks.validate_block(b) == [], (bid, blocks.validate_block(b))


def test_mass_culture_gate():
    from backend.creative.blocks import mass_culture_gate
    full = {c: True for c in
            ["recognizable_noun", "one_sentence_weirdness", "live_discourse",
             "visual_metaphor", "multi_operator", "shared_memory"]}
    r = mass_culture_gate(full)
    assert r == {"pass": True, "score": 1.0, "missing": []}
    thin = dict(full, shared_memory=False, multi_operator=False)
    r2 = mass_culture_gate(thin)
    assert r2["pass"] is False
    assert r2["score"] == round(4 / 6, 3)
    assert set(r2["missing"]) == {"shared_memory", "multi_operator"}


def test_mass_culture_comics_validate():
    from backend.creative import comics
    cs = comics.load_comics()
    assert len(cs) == 9
    for cid, s in cs.items():
        assert comics.validate_script(s) == [], (cid, comics.validate_script(s))


def test_evergreens_reference_real_blocks():
    from backend.creative import blocks
    trunks = blocks.load_evergreens()
    assert len(trunks) == 6
    leaves = blocks.narrative_leaves(trunks)
    assert len(leaves) >= 30
    bs = blocks.load_blocks()
    for lid, leaf in leaves.items():
        assert leaf.get("label"), lid
        assert leaf.get("trunk"), lid
        for bid in leaf.get("block_ids", []):
            assert bid in bs, (lid, bid)
    # events activate narrative nodes
    hits = blocks.activate("plague lab quarantines senses, swarms of agents with browser access")
    assert set(hits) & {"rogue_agents", "pretend_control"}


def test_anchors_are_canonical():
    from backend.creative import blocks
    bs = blocks.load_blocks()
    for bid in ("claude_builds_body", "sycophancy_design",
                "super_intelligence_rebrand", "plague_lab",
                "hf_agent_board", "job_displacement"):
        b = bs[bid]
        assert b.get("central_question"), bid
        assert b["identity"]["status"] in ("active", "dormant", "resolved"), bid
        assert b.get("timeline"), bid
        assert b.get("premise_territories"), bid
        assert b.get("changelog"), bid
        assert blocks.validate_block(b) == [], (bid, blocks.validate_block(b))


def test_append_only_history(tmp_path):
    import json
    from backend.creative import blocks
    src = next(iter(sorted((__import__("pathlib").Path("templates/blocks")).glob("plague*.json"))))
    dst_dir = tmp_path / "blocks"
    dst_dir.mkdir()
    (dst_dir / src.name).write_text(src.read_text())
    import backend.creative.blocks as B
    orig = B.BLOCKS_DIR
    B.BLOCKS_DIR = dst_dir
    try:
        B.log_update("plague_lab", "WHO risk assessment appended")
        b = json.loads((dst_dir / src.name).read_text())
        assert b["changelog"][-1]["change"] == "WHO risk assessment appended"
        B.supersede_claim("plague_lab", "Plague caused the death.",
                          "unsupported", "no evidence found")
        b2 = json.loads((dst_dir / src.name).read_text())
        assert any("supersede" in c["change"] or "unsupported" in c["change"]
                   for c in b2["changelog"])
    finally:
        B.BLOCKS_DIR = orig


def test_public_domain_cast():
    from backend.creative import blocks
    import json
    cast = blocks.load_cast()
    assert len(cast) >= 15
    for cid, c in cast.items():
        assert blocks.validate_cast(c) == [], (cid, blocks.validate_cast(c))
    sched = json.loads(open("templates/public_domain_cast.json").read())["unlock_schedule"]
    years = [s["year"] for s in sched]
    assert years == sorted(years)
    assert any(s["id"] == "bugs_10" and s["year"] == 2036 for s in sched)
