"""Peer-review items: subsidy gate, async resume, pack domains."""
import json
import os
import shutil
import subprocess
import sys


def test_subsidized_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("SUBSIDIZED_TRANSFORMS_PER_DAY", raising=False)
    from backend.creative import transform as T
    r = T.transform("pet_santa_v1", ["http://x/y.jpg"], owner="o9",
                    policy="subsidized")
    assert r["ok"] is False and "SUBSIDIZED_TRANSFORMS_PER_DAY" in r["error"]


def test_resume_unknown_job():
    from backend.creative import transform as T
    r = T.transform_resume("tj_nope", owner="o9")
    assert r["ok"] is False


def _flat_pack(tmp_path, **over):
    from backend.creative import transforms as _T  # noqa: F401 (import side effect not needed)
    import copy
    base = json.load(open("catalog/packs/CHARM-CROC-PET/product.json"))
    p = copy.deepcopy(base)
    p.update({"sku": "WRAP-TEST-001", "name": "Test wrap", "family": "wrap",
              "domain": "flat_print",
              "print": {"trim_mm": [500, 700], "bleed_mm": 3, "safe_mm": 10,
                        "dpi": 200, "colour_space": "CMYK",
                        "supplier_sku": "WRAP-1-50X70", "print_hash": None},
              "marketing": {"positioning": "Wrap you",
                            "audiences": ["a"], "angles": ["x"],
                            "claims": ["made from your photo"],
                            "forbidden_claims": ["waterproof"],
                            "hero_assets": [], "hooks": [], "motion_recipes": []},
              "generative": {"transform_id": "pet_santa_v1", "transform_version": 1,
                             "prompt_id": "xmas/santa-hat-v1", "prompt_version": 1,
                             "renderer_id": "wrap_repeat_v1", "renderer_version": 1,
                             "qc_contract": "mechanical", "sample_outputs": []}})
    p.update(over)
    d = tmp_path / "WRAP-TEST-001"
    (d / "print").mkdir(parents=True)
    (d / "listing").mkdir(parents=True)
    (d / "product.json").write_text(json.dumps(p))
    return str(d)


def test_flat_print_domain_g05(tmp_path):
    pack = _flat_pack(tmp_path)
    r = subprocess.run([sys.executable, "catalog/tools/validate_pack.py", pack],
                       capture_output=True, text=True, timeout=120)
    out = r.stdout
    assert "G05" in out
    # flat_print G05 checks print block, never volume
    assert "volume" not in out.split("G05")[1].split("G06")[0]


def test_marketing_clash_fails(tmp_path):
    pack = _flat_pack(tmp_path)
    p = json.load(open(f"{pack}/product.json"))
    p["marketing"]["forbidden_claims"] = ["Made From Your Photo"]
    json.dump(p, open(f"{pack}/product.json", "w"))
    r = subprocess.run([sys.executable, "catalog/tools/validate_pack.py", pack],
                       capture_output=True, text=True, timeout=120)
    assert "forbidden" in r.stdout.lower()


def test_generative_unknown_transform_fails(tmp_path):
    pack = _flat_pack(tmp_path)
    p = json.load(open(f"{pack}/product.json"))
    p["generative"]["transform_id"] = "nope_v9"
    json.dump(p, open(f"{pack}/product.json", "w"))
    r = subprocess.run([sys.executable, "catalog/tools/validate_pack.py", pack],
                       capture_output=True, text=True, timeout=120)
    assert "nope_v9" in r.stdout


def test_mesh_packs_unchanged():
    r = subprocess.run([sys.executable, "catalog/tools/validate_pack.py",
                        "catalog/packs/FIG-PETBIG-TUX-80"],
                       capture_output=True, text=True, timeout=180)
    assert "PRINT_READY" in r.stdout
    assert "G05" in r.stdout and "volume" not in r.stdout.split("G05")[1].split("G06")[0]
