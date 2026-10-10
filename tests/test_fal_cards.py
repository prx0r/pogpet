"""fal.ai card plates: no-typography prompts, ask-first gating, ledger receipts."""
import json

from backend.creative.providers import fal as F
from backend.creative.providers.base import ProviderNotConfigured


def test_plate_prompt_guards_typography():
    p = F.plate_prompt("Dad lifting a trophy in a packed stadium")
    assert "Dad lifting a trophy" in p
    for banned in ("no text", "no words", "no letters", "no watermark"):
        assert banned in p
    assert F.plate_prompt("", style="") == F.NO_TEXT_GUARD


def test_plate_needs_scene_and_key(monkeypatch):
    # Hermetic: the key may be configured in .env — this test pins it absent.
    monkeypatch.delenv("FAL_KEY", raising=False)
    try:
        F.FluxPlateAdapter().run({"owner": "anon"})
    except ProviderNotConfigured as e:
        assert "scene" in str(e)
    else:
        raise AssertionError("empty scene should refuse")
    try:
        F.FluxPlateAdapter().run({"owner": "anon", "scene": "a stadium"})
    except ProviderNotConfigured as e:
        assert "FAL_KEY" in str(e)
    else:
        raise AssertionError("missing key must never touch network")


def test_flux_plate_submit_and_ledger(monkeypatch, tmp_path):
    calls = {}

    def fake_submit(endpoint, args, key):
        calls.update(endpoint=endpoint, args=args, key=key)
        assert "no text" in args["prompt"]
        return "req_test123"

    monkeypatch.setattr(F, "_submit", fake_submit)
    out = F.FluxPlateAdapter().run({
        "owner": "test-ledger", "scene": "Mum on a podium, confetti",
        "api_key": "FAL_TEST_KEY"})
    assert out["request_id"] == "req_test123"
    assert calls["endpoint"] == "fal-ai/flux/dev"
    # ledger receipt, then remove our test row
    from pathlib import Path
    ledger = Path(F.__file__).resolve().parent.parent.parent.parent / "data" / "fal_credits.jsonl"
    rows = ledger.read_text().splitlines()
    assert any("req_test123" in r and "test-ledger" in r for r in rows)
    ledger.write_text("\n".join(r for r in rows if "req_test123" not in r) + "\n")


def test_phota_train_gate_and_edit_endpoint(monkeypatch):
    try:
        F.PhotaAdapter().run({"owner": "a", "action": "train", "photos": ["u1"],
                              "api_key": "K"})
    except ProviderNotConfigured as e:
        assert "30-50" in str(e) or "5 photo" in str(e)
    else:
        raise AssertionError("train needs photo set")

    seen = {}

    def fake_submit(endpoint, args, key):
        seen["endpoint"] = endpoint
        return "req_edit1"

    monkeypatch.setattr(F, "_submit", fake_submit)
    out = F.PhotaAdapter().run({"owner": "a", "scene": "Dad as news anchor",
                                "image_urls": ["http://x/y.jpg"], "api_key": "K"})
    assert seen["endpoint"] == "fal-ai/phota/edit"
    assert out["request_id"] == "req_edit1"
    from pathlib import Path
    ledger = Path(F.__file__).resolve().parent.parent.parent.parent / "data" / "fal_credits.jsonl"
    rows = ledger.read_text().splitlines()
    ledger.write_text("\n".join(r for r in rows if "req_edit1" not in r) + "\n")


def test_upscale_needs_url_and_key():
    try:
        F.UpscaleAdapter().run({"owner": "a"})
    except ProviderNotConfigured as e:
        assert "image_url" in str(e)
    else:
        raise AssertionError("upscale needs a URL")


def test_router_routes_and_gating():
    from backend.creative.providers import router as R
    assert "fal.flux_plate" in R.ROUTES["scene_plate"]
    assert "fal.phota" in R.ROUTES["identity_plate"]
    assert R.ROUTES["upscale"] == ["fal.upscale"]
    # no key anywhere → clean refusal, never a bill
    try:
        R.run("scene_plate", {"owner": "anon", "scene": "x"})
    except Exception as e:
        assert "FAL_KEY" in str(e) or "no adapter" in str(e)
    else:
        raise AssertionError("unapproved paid run must refuse")
