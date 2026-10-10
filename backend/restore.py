"""Photo rescue dispatcher — diagnose the defect, call the specialist.

Follows the fal community restoration recipe: one defect at a time,
chain in order (denoise → deblur → face-fix → upscale). Endpoints are
fal-hosted (needs FAL_KEY — same ask-first gate as Meshy); without a key
every op returns staged-but-unexecuted so the pipeline can plan, show
before/after intent, and record cost estimates without spending.

Spend rule: run() requires approve=True AND FAL_KEY. Originals are never
overwritten — restored copies land beside them with provenance
`restored:<endpoint>` and the photo keeps its original id.
"""
from __future__ import annotations

import os

# Dominant defect → (fal endpoint, default params). Order matters for chains.
# Endpoint details: docs/fal.md (imported from fal.ai model docs 2026-10-10).
DEFECTS = {
    "blur": ("fal-ai/nafnet/deblur", {}),
    "noise": ("fal-ai/nafnet/denoise", {}),
    "haze": ("fal-ai/mix-dehaze-net", {}),
    "face": ("fal-ai/codeformer", {"fidelity": 0.7, "face_upscale": True,
                                   "upscale_factor": 2}),
    "lowres": ("fal-ai/esrgan", {"scale": 2, "model": "RealESRGAN_x4plus"}),
    "matte": ("fal-ai/birefnet", {"model": "Portrait",
                                  "operating_resolution": "1024x1024"}),
}

# Chain order when several defects are present.
CHAIN = ["noise", "blur", "haze", "face", "lowres"]


def fal_key() -> str:
    return (os.environ.get("FAL_KEY") or "").strip()


def plan(signals: dict) -> list:
    """Pure-python planner. signals: {blur, noise, haze, face, lowres: bool}
    plus face_only passthrough. Returns [{defect, endpoint, params}]."""
    ops = []
    for defect in CHAIN:
        if signals.get(defect):
            endpoint, params = DEFECTS[defect]
            ops.append({"defect": defect, "endpoint": endpoint,
                        "params": dict(params)})
    return ops


def estimate(ops: list) -> dict:
    """Rough cost note. CodeFormer bills ~$0.0021/MP; others per-run cents."""
    per_op_cents = {"face": 1, "lowres": 1, "blur": 1, "noise": 1, "haze": 1}
    total = sum(per_op_cents.get(o["defect"], 1) for o in ops)
    return {"ops": len(ops), "est_cents": total,
            "note": "estimates only — fal meters per model/output"}


def run(op: dict, image_url: str, *, approve: bool = False) -> dict:
    """Execute one dispatcher op. Stubbed until FAL_KEY + approve land."""
    key = fal_key()
    if not key or not approve:
        reason = ("approve=True required" if key else "FAL_KEY missing")
        return {"ok": False, "staged": True, "op": op,
                "error": f"not executed: {reason}"}
    import json as _json
    import urllib.request as _ul
    body = {"image_url": image_url, **op.get("params", {})}
    req = _ul.Request(f"https://fal.run/{op['endpoint']}",
                      data=_json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", f"Key {key}")
    req.add_header("Content-Type", "application/json")
    try:
        with _ul.urlopen(req, timeout=300) as res:
            return {"ok": True, "staged": False, "op": op,
                    "result": _json.loads(res.read().decode() or "{}")}
    except Exception as e:
        return {"ok": False, "staged": False, "op": op,
                "error": str(e)[:300]}


def ledger_append(entry: dict) -> None:
    """Append-only spend/intent ledger (mirrors data/meshy_credits.jsonl)."""
    import json as _json
    import time as _t
    from . import config
    entry = {"at": _t.time(), **entry}
    p = config.DATA / "restore_ledger.jsonl"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as fh:
            fh.write(_json.dumps(entry) + "\n")
    except OSError:
        pass
