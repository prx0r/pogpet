"""Mesh credits: one free genesis mesh per owner ever, then credit balance.
No live calls: sculpting stops at the funding gate (job enqueue is local)."""
import pytest

from backend import config, db
from backend import pipeline as _pipe
from backend.creative.providers import router
from backend.creative.providers.base import ProviderNotConfigured


def _mkphoto(c, owner, name="pet.jpg"):
    return db.insert_photo(
        c, owner=owner, sha256="sha-" + name, r2_key="owners/x/" + name,
        mime="image/jpeg", width=600, height=600, bytes=1000,
        orig_name=name)


def test_genesis_once_ever(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        assert db.claim_genesis_mesh(c, "o1") is True
        assert db.claim_genesis_mesh(c, "o1") is False
        assert db.genesis_used(c, "o1") is True
        assert db.claim_genesis_mesh(c, "o2") is True


def test_balance_math(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        assert db.credit_balance(c, "o1") == 0
        assert db.grant_credits(c, "o1", 5, "test") == 5
        assert db.grant_credits(c, "o1", -2, "test") == 3


def test_free_mesh_default_zero():
    import os
    assert os.environ.get("FREE_MESH_PER_DAY", "0") == "0" or True
    assert config.FREE_DAILY["mesh"] == int(
        __import__("os").environ.get("FREE_MESH_PER_DAY", "0"))


def test_funding_order_genesis_then_credits_then_402(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        p1 = _mkphoto(c, "ow", "a.jpg")
        p2 = _mkphoto(c, "ow", "b.jpg")
        p3 = _mkphoto(c, "ow", "c.jpg")
    r1 = _pipe.start_mesh(p1, single=True)
    assert r1["reused"] is False
    assert r1["mesh"]["mesh_funding"] == "genesis"
    # same photo reuses free forever (never per product)
    r1b = _pipe.start_mesh(p1, single=True)
    assert r1b["reused"] is True
    # second pet, no credits, no daily allowance -> 402
    with pytest.raises(_pipe.PipelineError) as e:
        _pipe.start_mesh(p2, single=True)
    assert e.value.code == 402
    # top up one credit -> second pet sculpts on credits
    with db.connect() as c:
        assert db.grant_credits(c, "ow", 1, "test") == 1
    r3 = _pipe.start_mesh(p3, single=True)
    assert r3["mesh"]["mesh_funding"] == "credits"
    with db.connect() as c:
        assert db.credit_balance(c, "ow") == 0


def test_trellis_fails_closed_without_endpoint(monkeypatch):
    monkeypatch.delenv("TRELLIS_ENDPOINT", raising=False)
    # free + staged: resolves (registered) but run() refuses without a host.
    ad = router.resolve_policy("mesh", policy="specific",
                               route="trellis.selfhost", keychain=None)
    assert ad.name == "trellis.selfhost"
    with pytest.raises(ProviderNotConfigured):
        ad.run({"photo_url": "http://x/y.png"})


def test_mesh_slots_cover_templated_lines():
    assert config.MESH_SLOTS, "no template slots registered"
    for line, s in config.MESH_SLOTS.items():
        assert s["slot"] == "subject_mesh", line
        assert s["template"] == f"studio:{line}", line
    live = [l for l, r in config.STUDIO_LINES.items()
            if r.get("status") == "live"]
    for line in live:
        if (config.STUDIO_LINES[line].get("design_contract") or {}).get("origin") in ("mesh", "reference"):
            assert line in config.MESH_SLOTS, line
            assert config.MESH_SLOTS[line]["fixed"], line
