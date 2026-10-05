#!/usr/bin/env python3
"""Factory measure: canonical dims + weight for STL masters (stdlib only).

    python3 scripts/factory/measure.py data/3dprint/masters/*.stl

Parses binary STL (uint32 count + 50-byte facets), computes the signed
volume, and reports bbox dims in mm plus estimated print weight for PLA
(1.24 g/cm3) and PETG (1.27 g/cm3), at 100% infill. Real prints use lower
infill, so treat weight as the conservative upper bound — the farm quotes
against it and the customer never sees a heavier parcel than listed.

Outputs one JSON object per file on stdout; --json writes a single file.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

PLA_DENSITY = 1.24  # g / cm3
PETG_DENSITY = 1.27  # g / cm3


def _facets_ascii(raw: bytes) -> list:
    """Parse ASCII STL facets -> [(pa,pb,pc)]. Raises ValueError if not ASCII."""
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        raise ValueError("not ASCII STL")
    if not text.lstrip().lower().startswith("solid"):
        raise ValueError("not ASCII STL")
    facets, cur = [], []
    for line in text.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0] == "vertex" and len(parts) == 4:
            try:
                cur.append((float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError:
                pass
            if len(cur) == 3:
                facets.append(tuple(cur))
                cur = []
    if not facets:
        raise ValueError("ASCII STL with no facets")
    return facets


def stl_volume_dims(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 84:
        raise ValueError(f"{path.name}: too small for STL")
    (n,) = struct.unpack("<I", raw[80:84])
    kind = "binary"
    if len(raw) != 84 + 50 * n:
        # not binary-shaped: try ASCII before giving up (normalize passes
        # ASCII through unchanged, so both shapes circulate in _ingest)
        ascii_facets = _facets_ascii(raw)
        kind = "ascii"
        tris = ascii_facets
        n = len(tris)
        get = lambda i: tris[i]  # noqa: E731
    else:
        get = None
    vol = 0.0
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    if kind == "ascii":
        # NOTE: signed-volume math assumes consistently wound, closed
        # geometry. For dirty reference meshes it can cancel into a
        # believable-but-wrong number — see weight_watertight below.
        for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in tris:
            vol += (ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)) / 6.0
            xs += [ax, bx, cx]
            ys += [ay, by, cy]
            zs += [az, bz, cz]
    else:
        off = 84
        for _ in range(n):
            ax, ay, az, bx, by, bz, cx, cy, cz = struct.unpack("<9f", raw[off + 12:off + 48])
            vol += (ax * (by * cz - bz * cy) + ay * (bz * cx - bx * cz) + az * (bx * cy - by * cx)) / 6.0
            xs += [ax, bx, cx]
            ys += [ay, by, cy]
            zs += [az, bz, cz]
            off += 50
    vol_cm3 = abs(vol) / 1000.0
    dims = [round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1), round(max(zs) - min(zs), 1)]
    return {
        "file": path.name,
        "stl_kind": kind,
        "facets": n,
        "dims_mm": dims,
        "volume_cm3": round(vol_cm3, 2),
        "weight_pla_g": round(vol_cm3 * PLA_DENSITY, 1),
        "weight_petg_g": round(vol_cm3 * PETG_DENSITY, 1),
        # watertight gating: only trust volume if validate.py says PASS.
        # Annotate with --validate-json (path to validate.json); without it
        # the weight stays an unreviewed estimate.
        "weight_watertight": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", default="", help="write combined JSON here")
    ap.add_argument("--validate-json", default="",
                    help="validate.json: mark weight_watertight from Blender verdicts")
    a = ap.parse_args()
    verdicts: dict[str, str] = {}
    if a.validate_json:
        try:
            verdicts = {r.get("file", ""): r.get("verdict", "")
                        for r in json.loads(Path(a.validate_json).read_text())}
        except (OSError, ValueError):
            pass
    out = []
    for f in a.files:
        rec = stl_volume_dims(Path(f))
        if verdicts:
            # match by basename or suffix (validate paths are _ingest-relative)
            v = verdicts.get(rec["file"], "")
            if not v:
                hits = [ver for name, ver in verdicts.items() if name.endswith(rec["file"])]
                v = hits[0] if hits else ""
            rec["weight_watertight"] = (v == "PASS")
        out.append(rec)
    for rec in out:
        print(json.dumps(rec))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(out, indent=2))
        print(f"wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
