import json

import backend.server as S
from backend import config


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "API_TOKEN", "test-token")
    monkeypatch.setattr(config, "DATA", tmp_path)
    S.config.API_TOKEN = "test-token"
    return S.app.test_client()


def test_duel_pair_and_vote(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/creative/duel?token=test-token")
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    d = r.get_json()
    assert d["ok"] and d["a"]["id"] != d["b"]["id"]
    for side in ("a", "b"):
        assert len(d[side]["panels"]) == 4
    v = c.post("/api/creative/duel/vote?token=test-token",
               json={"a_id": d["a"]["id"], "b_id": d["b"]["id"],
                     "winner": d["b"]["id"], "owner": "anon"})
    assert v.status_code == 200, v.get_data(as_text=True)[:200]
    assert v.get_json()["recorded"] is True
    rows = (tmp_path / "comedy_prefs.jsonl").read_text().strip().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["winner"] == "b"


def test_duel_vote_rejects_bad_ids(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/creative/duel/vote?token=test-token",
               json={"a_id": "x", "b_id": "x", "winner": "x"})
    assert r.status_code == 400
    r = c.post("/api/creative/duel/vote?token=test-token",
               json={"a_id": "lab_assistants", "b_id": "hormones",
                     "winner": "everybody"})
    assert r.status_code == 400


def test_duel_needs_token(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/creative/duel").status_code == 401
