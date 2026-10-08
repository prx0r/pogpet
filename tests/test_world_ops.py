from backend.creative import world_ops as w


def test_status_invert_claude():
    s = w.blank()
    s["status"] = {"scientists": 3, "claude": 0}
    s["relations"] = [{"subject": "scientists", "object": "claude",
                       "relation": "operate"}]
    r = w.status_invert(s, "scientists", "claude")
    assert r["state"]["status"]["claude"] == 3
    assert r["state"]["relations"][0]["subject"] == "claude"
    assert r["description"] == "claude now directs scientists"


def test_double_interpret_switch():
    r = w.double_interpret(w.blank(), "assay rerun",
                           "scientist is using AI", "scientist works for AI")
    assert r["state"]["frames"]["assay rerun"] == [
        "scientist is using AI", "scientist works for AI"]


def test_rigidify_counts_and_violation_needs_rule():
    s = w.blank()
    r1 = w.rigidify(s, "tool use requires authorization")
    r2 = w.rigidify(r1["state"], "tool use requires authorization")
    assert "2x" in r2["description"]
    v = w.character_violation(w.blank(), "claude", "always agrees")
    assert "never established" in v["description"]
    s2 = w.blank()
    s2["rules"] = [{"rule": "always agrees", "applications": 40}]
    v2 = w.character_violation(s2, "claude", "always agrees")
    assert "BROKEN" in str(v2["state"]["rules"])


def test_split_knowledge_and_mistake_compounds():
    r = w.split_knowledge(w.blank(), "claude directs the lab",
                          "scientist", "I operate claude")
    assert "claude directs the lab" in r["state"]["beliefs"]["audience"]
    m1 = w.mistake_identity(w.blank(), "claude", "intern", cost=1)
    m2 = w.mistake_identity(m1["state"], "claude", "intern", cost=2)
    assert "cost now 3" in m2["description"]


def test_repeat_unmask_literalize_bisociate_blind():
    s = w.blank()
    for i in range(4):
        r = w.repeat_variation(s, "day log", f"mutation {i}")
        s = r["state"]
    assert len([b for b in s["beats"] if b["kind"] == "repeat"]) == 4
    u = w.unmask(s, "lab", "AI safety company", "claude's facility")
    assert u["state"]["revealed"]["lab"]["is"] == "claude's facility"
    lit = w.literalize(s, "tool access", "spoon approval")
    assert lit["state"]["materialized"][0]["material"] == "spoon approval"
    bi = w.bisociate(s, "alignment", "court", "flatter the king")
    assert "alignment x court" in bi["state"]["frames"]
    eb = w.expose_self_blindness(s, "ai", "sycophantic")
    assert "ai is sycophantic" in eb["state"]["beliefs"]["audience"]
    ic = w.identity_contradict(s, "nolan", "sniffer dog", "cannot smell")
    assert ic["state"]["contradictions"][0]["property"] == "cannot smell"
    assert len(w.OPS) == 12


def test_jestry_efficiency():
    from backend.creative import judge
    e = judge.resolution_efficiency(
        "Everyone thought the scientists ran the lab, but it turns out "
        "Claude assigns the experiments, which means the hierarchy flipped.")
    assert e["surprise"] > 0.4 and e["resolution"] > 0.4
    flat = judge.resolution_efficiency("The lab is nice. Science happens here daily.")
    assert flat["efficiency"] < e["efficiency"]
