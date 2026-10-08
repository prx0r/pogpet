#!/usr/bin/env python3
"""Listing factory — (subject fixture x product line) -> Etsy-ready pack.

    python3 scripts/listing_factory.py --fixture demo --line ornament
    python3 scripts/listing_factory.py --all
    python3 scripts/listing_factory.py --all --publish   # refuses unless production==verified

Output: data/listings/<line>/<fixture>/01-hero.png ... 10-packaging.png
        + listing.json + listing.md. Slots without source imagery are
        recorded as todo with a reason — draft media, never fake media.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config
from backend import listings as _list
from PIL import Image, ImageDraw

OUT = _list.OUT
PROD = _list.PROD
FIX = _list.FIX

# line -> demo recipe. personalization must match the line's real method.
RECIPES = _list.RECIPES

SLOTS = ["hero", "before_after", "lifestyle", "detail", "scale",
         "variants", "process", "measurements", "second_person", "packaging"]


def fixture_photos(name: str) -> list[Path]:
    return _list.fixture_photos(name)


def before_after(source: Path, product: Path, dest: Path,
                label: str = "") -> Path:
    """The persuasive image: THIS PHOTO -> THIS THING. 2000x1000."""
    a = Image.open(source).convert("RGB")
    b = Image.open(product).convert("RGB")
    H = 1000
    a = a.resize((H, H))
    b = b.resize((H, H))
    canvas = Image.new("RGB", (2000 + 200, H + 120), (250, 248, 243))
    canvas.paste(a, (0, 60))
    canvas.paste(b, (1100, 60))
    d = ImageDraw.Draw(canvas)
    d.text((1000, H // 2), "->", fill=(139, 106, 47))
    if label:
        d.text((40, 8), label[:80], fill=(60, 55, 50))
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, "PNG")
    return dest


def build(line: str, fixture: str, publish: bool = False) -> dict:
    from backend import config as _c
    spec = _c.STUDIO_LINES.get(line)
    if spec is None and line != "xmas_card":
        raise ValueError(f"unknown line {line}")
    if line in _c.STUDIO_LINES:
        method = (spec.get("personalization") or {}).get("method", "")
        if RECIPES[line]["method"] != method:
            raise ValueError(f"recipe method {RECIPES[line]['method']} != line method {method}")
        production = spec.get("production", "sample_pending")
        if publish and production != "verified":
            raise ValueError(f"refusing --publish: {line} production={production} (need verified)")
    photos = fixture_photos(fixture)
    if not photos:
        raise ValueError(f"fixture {fixture!r} has no photos — "
                         f"add to data/fixtures/{fixture}/photos/ first")
    rec = RECIPES[line]
    hero = _list.PROD / rec["hero"]
    if not hero.is_file():
        raise ValueError(f"missing hero still {rec['hero']}")
    outdir = _list.OUT / line / fixture
    outdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}

    def put(slot: str, src: Path | None, note: str = ""):
        dest = outdir / f"{SLOTS.index(slot) + 1:02d}-{slot}.png"
        if src and src.is_file():
            Image.open(src).convert("RGB").save(dest, "PNG")
            manifest[slot] = {"status": "ready", "file": dest.name}
        else:
            manifest[slot] = {"status": "todo", "reason": note or "no source imagery yet"}

    put("hero", hero)
    put("before_after", None)
    before_after(photos[0], hero, outdir / "02-before_after.png",
                 f"{fixture} -> {line}")
    manifest["before_after"] = {"status": "ready", "file": "02-before_after.png"}
    angles = [_list.PROD / a for a in rec["angles"] if (_list.PROD / a).is_file()]
    put("lifestyle", angles[0] if angles else None, "needs lifestyle shoot")
    put("detail", angles[1] if len(angles) > 1 else None, "needs macro still")
    put("scale", None, "needs scale reference render")
    put("variants", angles[0] if angles else None, "single variant until combos render")
    put("process", None, "needs upload->design->print diagram")
    put("measurements", None, "needs dimension overlay render")
    put("second_person", None, "needs second fixture subject")
    put("packaging", None, "needs pack shot")
    listing = {
        "line": line, "fixture": fixture,
        "title": (_c.ETSY_LISTINGS.get(line, {}).get("title")
                  if line in _c.ETSY_LISTINGS else f"Personalised {line}"),
        "price_cents": (spec or {}).get("price_cents", 0),
        "story": rec["story"], "text": rec["text"],
        "status": {"catalog": (spec or {}).get("status", "soon"),
                   "production": (spec or {}).get("production", "sample_pending"),
                   "etsy": (spec or {}).get("etsy", "draft")},
        "slots": manifest,
        "ready": sum(1 for v in manifest.values() if v["status"] == "ready"),
    }
    (outdir / "listing.json").write_text(json.dumps(listing, indent=2))
    md = [f"# {listing['title']}", "", f"*{rec['story']}*", "",
          f"Price: GBP {listing['price_cents'] / 100:.2f} (EST until live quote)", ""]
    for slot in SLOTS:
        v = manifest[slot]
        md.append(f"- [{slot}] {v['status']}" +
                  (f" — {v.get('file')}" if v.get("file") else f" ({v.get('reason')})"))
    (outdir / "listing.md").write_text("\n".join(md) + "\n")
    return listing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default="")
    ap.add_argument("--line", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()
    targets = list(RECIPES) if args.all else [args.line]
    for line in targets:
        if not line:
            ap.error("--line or --all required")
        fx = args.fixture or RECIPES[line]["fixture"]
        try:
            listing = build(line, fx, publish=args.publish)
            print(f"{line}/{fx}: {listing['ready']}/10 slots ready "
                  f"(production={listing['status']['production']})")
        except ValueError as e:
            print(f"{line}/{fx}: SKIP — {e}")


if __name__ == "__main__":
    main()
