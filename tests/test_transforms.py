"""Transformation library: registry + capability routing. No live calls."""
import pytest

from backend.creative import transform as T
from backend.creative import transforms as reg
from backend.creative.providers import router
from backend.creative.providers.base import BaseAdapter, ProviderNotConfigured


def test_registry_loads_published():
    all_t = reg.load_all()
    assert {"pet_santa_v1", "subject_cutout_v1", "christmas_badge_v1",
            "natural_edit_v1"} <= set(all_t)
    pub = reg.published()
    assert set(pub) == set(all_t)  # all seeds published
    for tid, t in pub.items():
        assert not reg.validate_transform(t), tid


def test_registry_rejects_bad_shape(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"id": "bad_v1", "version": "x"}')
    assert reg.load_all(tmp_path) == {}
    assert reg.get("nope_v1") == {}


def test_new_capabilities_routed():
    for cap in ["subject_cutout", "identity_transform",
                "multi_reference_edit", "brand_style", "text_heavy_art",
                "consistent_image_set", "local_edit", "product_packshot",
                "marketplace_image"]:
        assert cap in router.ROUTES, cap


def test_identity_transform_has_no_free_pretender():
    # local.composite previews only — it must never satisfy this route.
    assert "local.composite" not in router.ROUTES["identity_transform"]


def test_free_policy_fails_closed_without_free_adapter():
    # pet_santa has no free implementation: free policy fails closed,
    # never pretend-success. No network attempted.
    out = T.transform("pet_santa_v1", ["http://x/y.jpg"], owner="anon",
                      policy="free")
    assert out["ok"] is False


def test_paid_without_key_fails_closed(monkeypatch):
    # Hermetic: never inherit ambient provider keys from the shell.
    for k in ("FAL_KEY", "DASHSCOPE_API_KEY", "HIGGSFIELD_API_KEY",
              "DASHSCOPE_WORKSPACE_ID"):
        monkeypatch.delenv(k, raising=False)
    # Pinning a paid adapter with no key must raise, never bill.
    with pytest.raises(ProviderNotConfigured):
        router.resolve_policy("subject_cutout", policy="specific",
                              route="fal.birefnet", keychain=None)
    with pytest.raises(ProviderNotConfigured):
        router.resolve_policy("identity_transform", policy="specific",
                              route="higgsfield.soul", keychain=None)


def test_unknown_transform_and_refs():
    assert T.transform("nope_v1")["ok"] is False
    r = T.transform("pet_santa_v1", [], owner="anon")
    assert r["ok"] is False and "needs 1 reference" in r["error"]


def test_instruction_compiles_from_prompt_file():
    text, source = T.instruction_for(reg.get("pet_santa_v1"))
    assert source == "prompts/xmas/santa-hat-v1"
    assert "Santa hat" in text and "pet" in text.lower()


def test_missing_prompt_file_is_hard_error():
    with pytest.raises(Exception):
        T.instruction_for({"prompt_id": "nope/missing-v9",
                           "instruction": {"template": "x"}})


def test_normalize_contract():
    ok = T.normalize_output({"ok": True, "artifact": {"url": "http://x/a.png"}}, "a")
    assert ok["status"] == "ready"
    run = T.normalize_output({"ok": True, "request_id": "r1"}, "a")
    assert run["status"] == "running" and run["job_id"] == "r1"
    task = T.normalize_output({"ok": True, "task": {"id": "t"}}, "a")
    assert task["status"] == "running"
    # pretend-success: ok with neither artifact nor job is a failure
    bad = T.normalize_output({"ok": True, "mode": "composite2d preview"}, "a")
    assert bad["status"] == "failed"


def test_mechanical_qc():
    from PIL import Image as _I
    import io as _io
    good = _io.BytesIO()
    _I.new("RGBA", (512, 512), (255, 0, 0, 255)).save(good, format="PNG")
    passed, facts, _ = T.mechanical_qc(good.getvalue(), reg.get("pet_santa_v1"))
    assert passed and facts["width"] == 512
    passed, _, reason = T.mechanical_qc(b"not-an-image", reg.get("pet_santa_v1"))
    assert not passed
    tiny = _io.BytesIO()
    _I.new("RGB", (64, 64), "red").save(tiny, format="PNG")
    passed, _, reason = T.mechanical_qc(tiny.getvalue(), reg.get("pet_santa_v1"))
    assert not passed and "256" in reason
    rgb = _io.BytesIO()
    _I.new("RGB", (512, 512), "red").save(rgb, format="PNG")
    t = dict(reg.get("subject_cutout_v1"))
    passed, _, reason = T.mechanical_qc(rgb.getvalue(), t)
    assert not passed and "alpha" in reason


def test_describe():
    d = T.describe("christmas_badge_v1")
    assert d["ok"] and d["transform"]["capability"] == "identity_transform"
    assert T.describe("nope")["ok"] is False


def test_dispatch_and_cache_reuse_with_stub(tmp_path, monkeypatch):
    from backend import config, db
    from PIL import Image as _I

    motif = tmp_path / "motif.png"
    _I.new("RGBA", (512, 512), (255, 0, 0, 255)).save(motif)
    calls = {"n": 0}

    class Stub(BaseAdapter):
        capability = "identity_transform"
        name = "test.stub_transform"
        paid = False

        def run(self, payload):
            calls["n"] += 1
            assert payload["transform_id"] == "pet_santa_v1"
            assert payload["images"] == ["http://x/y.jpg"]
            assert "Santa hat" in payload["prompt"]  # compiled from prompts/
            return {"ok": True, "artifact": {"url": str(motif)}}

    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    router._ADAPTERS["test.stub_transform"] = Stub()
    old = router.ROUTES["identity_transform"]
    router.ROUTES["identity_transform"] = ["test.stub_transform"] + old
    try:
        out = T.transform("pet_santa_v1", ["http://x/y.jpg"], owner="o1",
                          subject_id="sub1")
        assert out["ok"] is True and out["reused"] is False
        assert out["qc_status"] == "passed"
        assert out["provenance"]["prompt_source"] == "prompts/xmas/santa-hat-v1"
        out2 = T.transform("pet_santa_v1", ["http://x/y.jpg"], owner="o1",
                           subject_id="sub1")
        assert out2["ok"] is True and out2.get("reused") is True
        assert calls["n"] == 1, "second call must reuse, not re-run"
        assert out2["artifact"]["id"] == out["artifact"]["id"]
    finally:
        router.ROUTES["identity_transform"] = old
        del router._ADAPTERS["test.stub_transform"]
