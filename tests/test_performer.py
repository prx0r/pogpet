from backend.creative import blocks, performer


def test_characters_validate():
    cs = performer.load_characters()
    assert {"benny_brine", "flip_frog", "no_nose_nolan"} <= set(cs)
    for cid, c in cs.items():
        assert performer.validate_character(c) == [], (cid, performer.validate_character(c))


def test_benny_angle_on_rebrand():
    cs = performer.load_characters()
    bs = blocks.load_blocks()
    a = performer.angle(cs["benny_brine"], bs["super_intelligence_rebrand"])
    assert a["character"] == "benny_brine"
    assert a["angles"]
    assert "touch" in str(a["voice_notes"])


def test_flip_angle_uses_species():
    cs = performer.load_characters()
    bs = blocks.load_blocks()
    a = performer.angle(cs["flip_frog"], bs["hf_agent_board"])
    assert a["angles"]


def test_work_sets_and_gate():
    cs = performer.load_characters()
    bs = blocks.load_blocks()
    sets = performer.work_sets(cs["no_nose_nolan"], bs, limit=6)
    assert 1 <= len(sets) <= 6
    passing = performer.gate(sets, min_score=0.0)
    assert isinstance(passing, list)
    strict = performer.gate(sets, min_score=99.0)
    assert strict == []


def test_pogcast_alternates():
    from backend.creative import blocks, performer, pogcast
    cs = performer.load_characters()
    bs = blocks.load_blocks()
    ep = pogcast.cast(cs["benny_brine"], cs["flip_frog"],
                      bs["super_intelligence_rebrand"], turns=6)
    assert len(ep["turns"]) == 6
    speakers = [t["speaker"] for t in ep["turns"]]
    assert speakers == ["benny_brine", "flip_frog"] * 3
    assert all(t["beat"] for t in ep["turns"])
