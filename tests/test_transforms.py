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


def test_free_policy_never_spends():
    # free policy resolves only $0-to-user adapters or raises — no network.
    out = T.transform("pet_santa_v1", ["http://x/y.jpg"], owner="anon",
                      policy="free")
    assert isinstance(out, dict) and "ok" in out
    if out["ok"]:
        assert out["provenance"]["transform_id"] == "pet_santa_v1"


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


def test_describe():
    d = T.describe("christmas_badge_v1")
    assert d["ok"] and d["transform"]["capability"] == "identity_transform"
    assert T.describe("nope")["ok"] is False


def test_dispatch_shape_with_stub():
    class Stub(BaseAdapter):
        capability = "identity_transform"
        name = "test.stub_transform"
        paid = False

        def run(self, payload):
            assert payload["transform_id"] == "pet_santa_v1"
            assert payload["images"] == ["http://x/y.jpg"]
            return {"ok": True, "artifact": "stub://motif"}

    router._ADAPTERS["test.stub_transform"] = Stub()
    old = router.ROUTES["identity_transform"]
    router.ROUTES["identity_transform"] = ["test.stub_transform"] + old
    try:
        out = T.transform("pet_santa_v1", ["http://x/y.jpg"], owner="anon")
        assert out["ok"] is True
        assert out["artifact"] == "stub://motif"
        assert out["provenance"]["transform_version"] == 1
        assert out["provenance"]["references_used"] == 1
    finally:
        router.ROUTES["identity_transform"] = old
        del router._ADAPTERS["test.stub_transform"]
