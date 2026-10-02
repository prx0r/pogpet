#!/usr/bin/env python3
"""Inject a jawOpen morph target into a dog GLB (freaktown basic_body pattern).

    python3 scripts/add_jaw_morph.py [--in data/uploads/chibi-figure-hook.glb] \
        [--out data/uploads/chibi-figure-hook-jaw.glb]

Picks muzzle vertices (high Y + front Z + near centre X) and writes a glTF
morph target that drops the jaw. Pure numpy + stdlib. 0 credits, 0 GPU.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np


def load_glb(path: Path):
    raw = path.read_bytes()
    magic, ver, total = struct.unpack("<III", raw[:12])
    assert magic == 0x46546C67, "not a GLB"
    clen, _ = struct.unpack("<II", raw[12:20])
    js = json.loads(raw[20 : 20 + clen])
    bin_off = 20 + clen
    blen, _ = struct.unpack("<II", raw[bin_off : bin_off + 8])
    blob = raw[bin_off + 8 : bin_off + 8 + blen]
    return js, blob


def save_glb(path: Path, js: dict, blob: bytes):
    js_b = json.dumps(js, separators=(",", ":")).encode()
    js_b += b" " * ((4 - len(js_b) % 4) % 4)
    pad = b"\x00" * ((4 - len(blob) % 4) % 4)
    blob_p = blob + pad
    total = 12 + 8 + len(js_b) + 8 + len(blob_p)
    out = struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<II", len(js_b), 0x4E4F534A) + js_b
    out += struct.pack("<II", len(blob_p), 0x004E4942) + blob_p
    path.write_bytes(out)


def view_bytes(blob: bytes, bv: dict) -> bytes:
    off = bv.get("byteOffset", 0)
    return blob[off : off + bv["byteLength"]]


def add_jaw(src: Path, dst: Path, drop: float = 0.035) -> dict:
    js, blob = load_glb(src)
    # use first mesh primitive POSITION
    prim = js["meshes"][0]["primitives"][0]
    pos_acc = js["accessors"][prim["attributes"]["POSITION"]]
    bv = js["bufferViews"][pos_acc["bufferView"]]
    raw = view_bytes(blob, bv)
    n = pos_acc["count"]
    pos = np.frombuffer(raw, dtype="<f4", count=n * 3).reshape(n, 3).copy()

    xs, ys, zs = pos[:, 0], pos[:, 1], pos[:, 2]
    # bbox-normalised selection — works at any scale
    def nrm(a):
        lo, hi = float(a.min()), float(a.max())
        return (a - lo) / (hi - lo + 1e-9)

    ny, nz, nx = nrm(ys), nrm(zs), nrm(xs)
    # muzzle: upper head, front-facing, near mid-line
    muzzle = (ny > 0.62) & (nz > 0.55) & (np.abs(nx - 0.5) < 0.28)
    # soften: also catch snout slightly lower
    muzzle |= (ny > 0.48) & (nz > 0.72) & (np.abs(nx - 0.5) < 0.22)
    idx = np.where(muzzle)[0]
    if len(idx) < 20:
        # fallback: top-front 8% of verts
        score = ny + nz
        k = max(20, int(n * 0.08))
        idx = np.argsort(score)[-k:]

    disp = np.zeros((n, 3), dtype=np.float32)
    # scale drop to mesh height so 0.035 is reasonable
    height = float(ys.max() - ys.min()) or 1.0
    jaw = drop * height
    disp[idx, 1] = -jaw
    disp[idx, 2] = jaw * 0.15  # slight forward

    # write target blob + accessor
    disp_b = disp.astype("<f4").tobytes()
    # append to a new bin
    new_blob = blob + disp_b
    acc_idx = len(js["accessors"])
    bv_idx = len(js["bufferViews"])
    js["bufferViews"].append({
        "buffer": 0,
        "byteOffset": len(blob),
        "byteLength": len(disp_b),
    })
    js["accessors"].append({
        "bufferView": bv_idx,
        "componentType": 5126,
        "count": n,
        "type": "VEC3",
        "min": [float(disp[:, 0].min()), float(disp[:, 1].min()), float(disp[:, 2].min())],
        "max": [float(disp[:, 0].max()), float(disp[:, 1].max()), float(disp[:, 2].max())],
    })
    prim["targets"] = [{"POSITION": acc_idx}]
    js["meshes"][0]["extras"] = {"targetNames": ["jawOpen"]}
    # ensure weights exist on mesh
    js["meshes"][0]["weights"] = [0.0]
    js["buffers"][0]["byteLength"] = len(new_blob)

    save_glb(dst, js, new_blob)
    info = {
        "verts": int(n),
        "jaw_verts": int(len(idx)),
        "jaw_mm": round(jaw * 1000, 2),
        "out": str(dst),
        "bytes": dst.stat().st_size,
    }
    print("jawOpen morph:", info)
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="data/uploads/chibi-figure-hook.glb")
    ap.add_argument("--out", dest="dst", default="data/uploads/chibi-figure-hook-jaw.glb")
    ap.add_argument("--drop", type=float, default=0.035)
    args = ap.parse_args()
    src, dst = Path(args.src), Path(args.dst)
    if not src.exists():
        raise SystemExit(f"missing {src}")
    add_jaw(src, dst, args.drop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
