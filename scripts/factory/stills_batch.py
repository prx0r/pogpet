#!/usr/bin/env python3
"""Factory stills batch: render + finish every line with source geometry.

    python3 scripts/factory/stills_batch.py [--lines clog_charm,book_holder]

Uses ~/blender/blender (4.2.5 LTS — system 4.0.2 lacks OpenImageDenoiser).
Renders hero/front/side/back per line into data/productimg/prod/ as
<line>-*.png, which _studio_stills_for() serves once "{line}-" is tried first.

wind_indicator has no geometry yet and is skipped (keeps fallback stills).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
P3D = ROOT / "data" / "3dprint"
ING = P3D / "_ingest"
BLENDER = str(Path.home() / "blender" / "blender")

SOURCES = {
    "clog_charm": ING / "heart-croc-jibbitz" / "heart-croc-jibbitz.stl",
    "bag_charm": ING / "croc-jibbit-base" / "croc-jibbit-base.stl",
    "brick_keychain": ROOT / "data" / "productimg" / "prod" / "brick-figure.glb",
    "keycap": P3D / "masters" / "mx_keycap.stl",
    "shoelace_charm": ING / "shoelace-tag-charms" / "shoe-lace-tag.stl",
    "book_holder": P3D / "masters" / "book_holder.stl",
    "golf_marker": ING / "golf-golf-ball-marker-assorted" / "converted" / "marker-template--3dmodel.stl",
    "straw_charm": P3D / "masters" / "straw_ring.stl",
    "controller_stand": ING / "minimalistic-xbox-controller-stand" / "stand.stl",
    "train_station": ING / "mexican-train-tray-domino-tray" / "Mexican Train Holder.stl",
    "domino_racks": ING / "mexican-domino-train-hub-and-case" / "Domino Case Bottom.stl",
    "line_reader": P3D / "masters" / "line_reader.stl",
    "rummy_rack": P3D / "masters" / "rummy_rack.stl",
    "card_rack": P3D / "masters" / "card_hand_rack.stl",
    "tcg_stand": P3D / "masters" / "slab_stand.stl",
    "cribbage_pegs": P3D / "Cribbage_peg_5.stl",
    "dart_stand": ING / "dart-stand" / "dart_stand.stl",
}


def run(line: str, src: Path, size: int, samples: int) -> bool:
    if not src.is_file():
        print(f"  SKIP {line}: missing {src}")
        return False
    tmp = Path(tempfile.mkdtemp(prefix=f"stills-{line}-"))
    try:
        r = subprocess.run(
            [BLENDER, "--background", "--python", str(ROOT / "scripts" / "factory" / "stills.py"),
             "--", "--in", str(src), "--out", str(tmp), "--size", str(size), "--samples", str(samples)],
            capture_output=True, text=True, timeout=1200)
        if "shot: hero" not in r.stdout:
            print(f"  FAIL {line} render:\n{r.stderr[-800:]}")
            return False
        r2 = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "factory" / "stills_finish.py"),
             str(tmp), "--line", line, "--dest", str(ROOT / "data" / "productimg" / "prod")],
            capture_output=True, text=True, timeout=300)
        print(f"  done {line}:\n" + "\n".join("   " + l for l in r2.stdout.strip().splitlines()))
        return True
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT {line}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", default="", help="comma list, default all")
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--samples", type=int, default=32)
    a = ap.parse_args()
    want = [l.strip() for l in a.lines.split(",") if l.strip()] or sorted(SOURCES)
    ok, bad = 0, []
    for line in want:
        if line not in SOURCES:
            print(f"  UNKNOWN {line}")
            bad.append(line)
            continue
        print(f"rendering {line} ...", flush=True)
        if run(line, SOURCES[line], a.size, a.samples):
            ok += 1
        else:
            bad.append(line)
    print(f"{ok}/{len(want)} lines rendered" + (f" — failed: {bad}" if bad else ""))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
