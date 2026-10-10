"""Theory hard gates: deterministic pre-checks + judge queues."""
from backend.creative import theory as TH


def test_registry_has_gates():
    ts = TH.load_theories()
    assert len(ts) == 25
    assert "superiority" in ts
    for tid, t in ts.items():
        assert t.get("hypothesis"), tid
        assert isinstance(t.get("conditions"), list), tid


def test_superiority_gate_queues_without_butt():
    r = TH.validate_text("Billions of calculations. Not one birdie.", {})
    assert r["theories_checked"] == 25
    assert any(q["theory"] == "superiority" for q in r["judge_queue"])


def test_repetition_hits_deterministically():
    r = TH.validate_text("I told them and I told them and nobody listened", {})
    assert "repetition_variation" in [h["theory"] for h in r["hits"]]


def test_exaggeration_lexicon_hits():
    r = TH.validate_text("Billions of calculations. Not one birdie.", {})
    assert "exaggeration" in [h["theory"] for h in r["hits"]]


def test_set_matrix_and_queue():
    r = TH.validate_set([
        {"id": "j1", "text": "Billions of calculations. Not one birdie.",
         "features": {"butt": "robots"}},
        {"id": "j2", "text": "I came, I saw, I left early.", "features": {}},
    ])
    assert r["ok"] and len(r["items"]) == 2
    assert r["aggregate"].get("exaggeration") == 1
    # every theory queues at most one gate per item
    by_item = {}
    for q in r["judge_queue"]:
        by_item.setdefault((q["item"], q["theory"]), 0)
        by_item[(q["item"], q["theory"])] += 1
    assert all(v == 1 for v in by_item.values())
    assert any(q["theory"] == "superiority" and q["item"] == "j1"
               for q in r["judge_queue"])
