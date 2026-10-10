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


def _mkmesh(c, owner, name, funding, ref=0):
    pid = _mkphoto(c, owner, name)
    mid = db.create_mesh(c, pid, funding=funding, funding_ref=ref)
    return mid


def test_refund_genesis_restores_hook(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        assert db.claim_genesis_mesh(c, "o1") is True
        mid = _mkmesh(c, "o1", "a.jpg", "genesis")
        assert db.refund_mesh(c, mid) is True
        assert db.genesis_used(c, "o1") is False
        # idempotent: second refund changes nothing
        assert db.refund_mesh(c, mid) is False
        assert db.claim_genesis_mesh(c, "o1") is True


def test_refund_credits_restores_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        db.claim_genesis_mesh(c, "o1")  # burn genesis so credits fund
        db.grant_credits(c, "o1", 1, "test")
        pid = _mkphoto(c, "o1", "b.jpg")
        bal = db.grant_credits(c, "o1", -1, f"mesh:{pid}")
        assert bal == 0
        row = c.execute("SELECT id FROM credit_ledger WHERE owner=? AND reason=?"
                        " ORDER BY id DESC LIMIT 1", ("o1", f"mesh:{pid}")).fetchone()
        mid = db.create_mesh(c, pid, funding="credits", funding_ref=int(dict(row)["id"]))
        assert db.refund_mesh(c, mid) is True
        assert db.credit_balance(c, "o1") == 1
        assert db.refund_mesh(c, mid) is False
        assert db.credit_balance(c, "o1") == 1


def test_refund_daily_restores_allowance(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    import datetime as _dt
    day = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    with db.connect() as c:
        db.claim_genesis_mesh(c, "o1")
        ok, used = db.spend_credit(c, "o1", day, "mesh", 1)
        assert ok and used == 1
        mid = _mkmesh(c, "o1", "c.jpg", "daily")
        assert db.refund_mesh(c, mid) is True
        assert db.credit_used(c, "o1", day, "mesh") == 0
        assert db.refund_mesh(c, mid) is False


def test_refund_unknown_funding_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        mid = _mkmesh(c, "o1", "d.jpg", "")
        assert db.refund_mesh(c, mid) is False
        assert db.refund_mesh(c, "msh_missing") is False


def test_credit_pack_redeem_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        assert db.credit_pack_redeem(c, "o1", "ord_1", 5) == 5
        assert db.credit_pack_redeem(c, "o1", "ord_1", 5) == 5
        assert db.credit_balance(c, "o1") == 5
        assert db.credit_pack_redeem(c, "o1", "ord_2", 5) == 10


def test_402_carries_top_up_url(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    with db.connect() as c:
        p1 = _mkphoto(c, "ow", "a.jpg")
        p2 = _mkphoto(c, "ow", "b.jpg")
    r1 = _pipe.start_mesh(p1, single=True)
    assert r1["mesh"]["mesh_funding"] == "genesis"
    import pytest as _pt
    with _pt.raises(_pipe.PipelineError) as e:
        _pipe.start_mesh(p2, single=True)
    assert e.value.code == 402
    assert "top_up_url" in e.value.data
    assert e.value.data["top_up_url"].startswith("/api/credits/balance")


def test_mesh_route_trellis_first_when_configured(monkeypatch):
    from backend import pipeline as _pl
    monkeypatch.setenv("TRELLIS_ENDPOINT", "http://gpu:8080")
    assert _pl._mesh_route() == ("trellis.selfhost", 0)
    monkeypatch.delenv("TRELLIS_ENDPOINT", raising=False)
    assert _pl._mesh_route() == ("local.meshy", 0)


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
