from backend.creative import blocks, comics, judge


def test_vetoes_kill_empty():
    assert "NO_ACTUAL_REFRAME" in judge.vetoes({"premise": "hi"})
    assert judge.judge_pair({"premise": "hi"}, {"premise": "yo"})["winner"] == "neither"


def test_pairwise_orders_canonical():
    cs = comics.load_comics()
    a, b = cs["lab_assistants"], cs["reward_optimization"]
    r = judge.judge_pair(a, b)
    assert r["winner"] in ("a", "b", "tie", "neither")
    assert set(r["scores"]) in (set(), {"a", "b"})
    assert 0.5 <= r["confidence"] <= 1.0


def test_taste_prior_lifts_hot_family(tmp_path):
    import backend.creative.performance as perf
    lp = tmp_path / "m.jsonl"
    perf.record_post(premise_id="p", family="door_reveal", platform="x",
                     post_ref="r1", path=lp)
    perf.record_metrics(post_ref="r1", views=10000, likes=1000, shares=500, path=lp)
    perf.record_post(premise_id="q", family="haunted_house_ai", platform="x",
                     post_ref="r2", path=lp)
    perf.record_metrics(post_ref="r2", views=100, likes=1, shares=0, path=lp)
    w = perf.weights(path=lp)
    cold = {"premise": "x" * 60, "family": "haunted_house_ai"}
    hot = {"premise": "x" * 60, "family": "door_reveal"}
    assert judge.taste_multiplier(hot, w) > judge.taste_multiplier(cold, w)


def test_tournament_and_tinder():
    bs = blocks.load_blocks()
    five = comics.select_five(comics.candidates(bs["claude_builds_body"]))
    table = judge.tournament(five)
    assert len(table) == 5
    assert table[0]["tournament_wins"] >= table[-1]["tournament_wins"]
    pairs = judge.tinder_pairs(table, n=3)
    assert len(pairs) == 3


def test_preference_db_and_precision(tmp_path):
    a = {"premise": "aaa"}
    b = {"premise": "bbb"}
    row = judge.record_preference(a, b, "a", context="test", path=tmp_path / "p.jsonl")
    assert row["winner"] == "a"
    assert judge.precision_at_k(["a", "b", "c"], ["a", "c"]) == round(2 / 3, 3)
    assert judge.precision_at_k(["a", "b"], ["z"]) == 0.0


def test_hierarchical_gate():
    from backend.creative import judge
    generic = {"premise": "AI robots are crazy these days!"}
    r = judge.gate_hierarchy(generic)
    assert isinstance(r, list) and len(r) >= 7
    assert judge.gate_passed(r) in (True, False)


def test_swappability_veto():
    from backend.creative import judge, performer
    cs = performer.load_characters()
    nolan = cs["no_nose_nolan"]
    generic = {"premise": "AI robots are crazy these days!"}
    rg = judge.gate_hierarchy(generic, nolan)
    char_gate = [g for g in rg if g["gate"] == "character"][0]
    assert char_gate["pass"] is False
    specific = {"premise": ("No-Nose Nolan insists the suitcase smells guilty. "
                            "Trust me, he says. Definitely.")}
    rs = judge.gate_hierarchy(specific, nolan)
    assert [g for g in rs if g["gate"] == "character"][0]["pass"] is True


def test_contrast_pairs():
    from backend.creative import blocks, performer
    bs = blocks.load_blocks()
    cs = performer.load_characters()
    pair = performer.contrast_pairs(cs["flip_frog"], bs["hf_agent_board"])
    assert pair["winner"] == "b" and pair["source"] == "auto_weak"


def test_view_and_relevance():
    from backend.creative import blocks, performer
    bs = blocks.load_blocks()
    cs = performer.load_characters()
    creature = cs["frankenstein_creature_1818"]
    v = performer.view(creature, bs["claude_builds_body"])
    assert v["character_id"] == "frankenstein_creature_1818"
    assert v["salience"] and v["salience"][0]["weight"] >= 0
    assert "double_interpret" in v["candidate_operators"]
    rel_self = performer.relevance(creature, bs["claude_builds_body"])
    rel_cold = performer.relevance(cs["benny_brine"], bs["plague_lab"])
    assert 0.0 <= rel_cold <= 1.0 and 0.0 <= rel_self <= 1.0
