#!/usr/bin/env python3
"""Generate template backdrops ONCE per template (fal.ai, ask-first spend).

The template keeps rigid slots. fal paints only the backdrop: a text-free
party texture. One paid generation per template, reused for every card.

    FAL_KEY=... python3 scripts/generate_template_art.py --template birthday_arch
    FAL_KEY=... python3 scripts/generate_template_art.py --all  # all 5, ~$0.15 total

Refuses without FAL_KEY. Every spend appends to data/fal_credits.jsonl.
Review the PNG in assets/card-art/backdrops/ before it goes live — bad
backdrops get deleted, never shipped.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.card_scenes import TEMPLATE_BACKDROPS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if not os.environ.get("FAL_KEY"):
        print("Refusing: no FAL_KEY. Backdrop generation spends real money — set FAL_KEY explicitly.")
        return 2
    tids = sorted(TEMPLATE_BACKDROPS) if args.all else [args.template]
    if not tids or any(t not in TEMPLATE_BACKDROPS for t in tids):
        print(f"Unknown template. Valid: {sorted(TEMPLATE_BACKDROPS)}")
        return 2
    from backend.creative.providers import router as R
    from backend.creative.providers.fal import plate_prompt
    outdir = ROOT / "assets" / "card-art" / "backdrops"
    outdir.mkdir(parents=True, exist_ok=True)
    for tid in tids:
        prompt = plate_prompt(TEMPLATE_BACKDROPS[tid])
        assert "no text" in prompt, "beauty prompt must carry the no-typography guard"
        print(f"[{tid}] submitting scene_plate…")
        got = R.run("scene_plate", {"scene": TEMPLATE_BACKDROPS[tid], "owner": "studio",
                                    "image_size": "portrait_4_3"},
                    policy="best")
        rid = got.get("request_id", "")
        print(f"[{tid}] request {rid} — poll fal queue, then save to {outdir / (tid + '.png')}")
        # Fetch-on-complete: resolve the queue result and store the first image.
        from backend.creative.providers import fal as _fal
        import json as _json
        key = os.environ["FAL_KEY"]
        res = _fal._result("fal-ai/flux/dev", rid, key)
        imgs = ((res.get("response") or res) .get("images") or [])
        if not imgs:
            print(f"[{tid}] FAILED: {str(res)[:200]}")
            return 1
        url = imgs[0]["url"]
        dest = outdir / f"{tid}.png"
        urllib.request.urlretrieve(url, dest)
        print(f"[{tid}] saved {dest} ({dest.stat().st_size} bytes) — REVIEW BEFORE SHIPPING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
