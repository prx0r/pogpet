"""Pogtown experiment science: probes, retention, comments, gold runs."""
from backend.creative import experiments as X


def test_probe_freeze_and_validation():
    m = {"probe_id": "probe_nolan_0041", "experiment_id": "exp_017",
         "hypothesis_id": "H-017", "arm": "treatment",
         "primary_factor": {"name": "jokeblock", "value": "misinterpreted_success@3"},
         "controls": {"character": "nolan@14"},
         "creative": {"joke_blocks": ["misinterpreted_success@3"]},
         "preregistered": {"primary_metric": "specific_positive_comment_rate",
                           "expected_direction": "treatment > control"}}
    assert X.validate_probe(m) == []
    f = X.freeze_probe(m)
    assert len(f["manifest_hash"]) == 16 and "frozen_at" in f
    assert X.validate_probe({}) != []
    bad = dict(m, arm="both")
    assert X.validate_probe(bad) != []


def test_retention_features():
    pts = [(0.0, 1.0), (0.05, 0.8), (0.25, 0.6), (0.5, 0.5),
           (0.75, 0.45), (0.95, 0.4), (1.0, 0.0)]
    f = X.retention_features(pts)
    assert f["ok"] and f["R_05"] == 0.8
    assert f["retention_auc"] > 0 and f["largest_drop"] >= 0
    assert f["closer_retention"] == f["R_95"]
    assert X.retention_features([(0.0, 1.0)])["ok"] is False


def test_comment_taxonomy():
    assert X.classify_comment("bring this dog back please")["label"] == "RETURN_REQUEST"
    assert X.classify_comment("the way he doubles down finished me")["label"] == "JOKE_MECHANISM"
    assert X.classify_comment("that pause was perfect")["label"] == "PERFORMANCE"
    assert X.classify_comment("why did his arm melt")["label"] == "AI_ARTIFACT"
    assert X.classify_comment("lol")["label"] == "GENERIC_POSITIVE"
    c = X.classify_comment("Nolan is killing me, bring him back for episode 12 please")
    assert c["specific"] is True


def test_gold_rates_and_candidate():
    m = {"engaged_views": 2000, "specific_positive": 40,
         "character_positive": 20, "return_requests": 6,
         "quote_adoption": 2, "specific_negative": 4}
    r = X.gold_rates(m)
    assert r["specific_positive_per_k"] == 20.0
    assert r["return_requests_per_k"] == 3.0
    ok, reasons = X.is_gold_candidate(
        {"metrics": {"completion": 0.5, "share_rate": 0.03,
                      "specific_positive_rate": 0.03}},
        {"completion": 0.35, "share_rate": 0.02,
         "specific_positive_rate": 0.02})
    assert ok and set(reasons) == {"completion", "share_rate",
                                   "specific_positive_rate"}
    ok2, _ = X.is_gold_candidate({"metrics": {"completion": 0.1}})
    assert ok2 is False


def test_explanation_plan_seven_lanes():
    p = X.explanation_plan({"gold_run_id": "gold_004", "episode_id": "ep1"})
    assert len(p["plans"]) == 7
    kinds = [x["probe_kind"] for x in p["plans"]]
    assert kinds[0].startswith("E1_replication")
    for x in p["plans"]:
        assert x["varies"] not in x["holds"] and len(x["holds"]) == 6


def test_finding_lifecycle():
    f = X.make_finding(
        {"subject": "misinterpreted_success@3",
         "predicate": "works_better_with", "object": "sincere_low_self_awareness"},
        {"experiments": ["exp_017"], "n_probes": 24,
         "comment_refs": ["c128"], "direction_probability": 0.94})
    assert f["status"] == "provisional"
    assert f["evidence"]["n_probes"] == 24
    try:
        X.make_finding({"subject": "x"}, {})
        assert False
    except ValueError:
        pass


def test_novelty_decay():
    r = X.novelty_decay([{"completion": 0.5}, {"completion": 0.48},
                         {"completion": 0.45}])
    assert r["ok"] and r["survives_debut"] is True
    r2 = X.novelty_decay([{"completion": 0.6}, {"completion": 0.2}])
    assert r2["survives_debut"] is False
    assert X.novelty_decay([{"completion": 1.0}])["ok"] is False
