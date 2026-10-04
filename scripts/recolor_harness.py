#!/usr/bin/env python3
"""Recolor harness parts inside composed GLBs — pure Python, instant.

A harness material is a flat Principled with baseColorFactor, so new
colours are a JSON-chunk edit (rebuild the container: lengths + padding).
No Blender, 0 credits.

    python3 scripts/recolor_harness.py \\
        --in /tmp/opencode/dog-harness-cream.glb \\
        --outdir data/productimg/prod --stem dog-harness

Writes dog-harness-{cream,golden,chocolate,black,fawn,grey}.glb.
P0 reference: docs/p0-hat-coat.md.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


COLOURS = {
    "cream": (0.93, 0.86, 0.74),
    "golden": (0.90, 0.72, 0.42),
    "chocolate": (0.42, 0.26, 0.16),
    "black": (0.12, 0.11, 0.11),
    "fawn": (0.82, 0.68, 0.52),
    "grey": (0.55, 0.55, 0.56),
}


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--stem", required=True,
                   help="dog-harness or dog-santa-harness")
    return p.parse_args(argv)


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise SystemExit(f"{path} is not a GLB")
    clen, ctype = struct.unpack_from("<I4s", data, 12)
    assert ctype == b"JSON", path
    doc = json.loads(data[20:20 + clen].decode("utf-8"))
    start = 20 + clen
    blen, btype = struct.unpack_from("<I4s", data, start)
    assert btype == b"BIN\x00", path
    blob = data[start + 8:start + 8 + blen]
    return doc, blob


def write_glb(doc: dict, blob: bytes, path: Path) -> None:
    j = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    j += b" " * (-len(j) % 4)
    blob_pad = blob + b"\x00" * (-len(blob) % 4)
    total = 12 + 8 + len(j) + 8 + len(blob_pad)
    out = struct.pack("<4sII", b"glTF", 2, total)
    out += struct.pack("<I4s", len(j), b"JSON") + j
    out += struct.pack("<I4s", len(blob_pad), b"BIN\x00") + blob_pad
    path.write_bytes(out)


def main() -> int:
    args = parse_args(sys.argv[1:])
    src = Path(args.src)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    doc, blob = read_glb(src)
    harness_mats = [m for m in doc.get("materials", [])
                    if (m.get("name") or "").startswith(("harness_", "jacket_"))]
    if not harness_mats:
        raise SystemExit(f"no harness_/jacket_ material in {src}")
    print(f"recolorable materials: {[m.get('name') for m in harness_mats]}")
    for name, rgb in COLOURS.items():
        for m in doc["materials"]:
            mn = m.get("name") or ""
            if mn.startswith("harness_"):
                m["name"] = f"harness_{name}"
                pbr = m.setdefault("pbrMetallicRoughness", {})
                pbr["baseColorFactor"] = [*rgb, 1.0]
            elif mn.startswith("jacket_"):
                m["name"] = f"jacket_{name}"
                pbr = m.setdefault("pbrMetallicRoughness", {})
                pbr["baseColorFactor"] = [*rgb, 1.0]
        dest = outdir / f"{args.stem}-{name}.glb"
        write_glb(doc, blob, dest)
        print(f"{dest.name} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
