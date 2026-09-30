# Provenance: copied from /home/ubuntu/petsy/engine/usdz.py (prx0r/bwick),
# read-only there. GLB -> USDZ for iOS Quick Look AR.
#!/usr/bin/env python3
"""GLB -> USDZ: the iOS Quick Look AR asset. Headless Blender, no GUI.

model-viewer puts `ios-src` on an AR session only if it can hand iOS a USDZ —
without one, iPhones see the model on the page but cannot place it in the room.
This is the last thing in the repo that needed Blender.

Two builds exist on this box and only one has USD compiled in:
  * Ubuntu's `blender` package — no USD libs shipped (`dpkg -L blender` has
    nothing usd), `bpy.ops.wm.usd_export` does not exist. Useless here.
  * `/home/ubuntu/opt/blender-4.2.9-*/blender` — official tarball, USD export
    present. That is the one this module prefers; `$BLENDER` overrides.

    python3 usdz.py mesh.glb --out mesh.usdz [--blender PATH]

Runs this same file inside Blender, so there is no second script to keep in
sync. Offline: no network, no keys.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from functools import lru_cache
from pathlib import Path


class UsdzError(RuntimeError):
    """No usable Blender, or the conversion failed."""


# ------------------------------------------------------- inside Blender -----

def _in_blender() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except Exception:                              # noqa: BLE001
        return False


def _convert(src: str, dst: str) -> None:
    """Runs inside Blender's Python."""
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src)
    if not bpy.context.scene.objects:
        raise SystemExit(f"glTF import produced no objects: {src}")
    # .usdz on the end makes Blender package it (textures included).
    # Note the import operator is import_scene.gltf, not wm.gltf_import.
    bpy.ops.wm.usd_export(
        filepath=dst,
        export_materials=True,
        export_uvmaps=True,
        export_normals=True,
        generate_preview_surface=True,
        export_textures=True,
        overwrite_textures=True,
        relative_paths=False,
        # The whole point of baking an action into the GLB was that iOS plays
        # animations from inside the file. Exporting the USDZ without its
        # animation curves would hand Quick Look a beautiful static pose.
        export_animation=True,
        selected_objects_only=False,
    )
    if not os.path.exists(dst):
        raise SystemExit(f"usd_export produced nothing at {dst}")


# --------------------------------------------------------- outside ---------

def _candidates() -> list[str]:
    found: list[str] = []
    if os.environ.get("BLENDER"):
        found.append(os.environ["BLENDER"])
    found += [str(p) for p in sorted(
        Path("/home/ubuntu/opt").glob("blender-*/blender"))]
    which = shutil.which("blender")
    if which:
        found.append(which)
    return [p for p in found if Path(p).exists()]


@lru_cache(maxsize=None)
def has_usd(path: str) -> bool:
    """Ubuntu's build has no USD ops at all — check before wasting a run."""
    try:
        # hasattr(bpy.ops.wm, "usd_export") is ALWAYS True — bpy.ops hands
        # back a proxy for any name. Asking for the RNA type is what actually
        # fails when the operator was compiled out.
        probe = ("import bpy\n"
                 "try:\n"
                 "    bpy.ops.wm.usd_export.get_rna_type()\n"
                 "    print('USDZ_OK True')\n"
                 "except Exception:\n"
                 "    print('USDZ_OK False')")
        out = subprocess.run(
            [path, "--background", "--python-expr", probe],
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "USDZ_OK True" in out.stdout


def find_blender() -> str:
    for c in _candidates():
        if has_usd(c):
            return c
    raise UsdzError(
        "no Blender with USD export found. Tried: "
        + (", ".join(_candidates()) or "none")
        + ". Install the official build (Ubuntu's package is compiled without "
        "USD) or set $BLENDER."
    )


# Pixar's USDZ spec (openusd.org/release/spec_usdz.html):
#   * zero compression (STORED), unencrypted
#   * EVERY file's data begins on a 64-byte boundary in the archive
#   * the Default Layer (.usd/.usda/.usdc) is the first file
#   * only usd + png/jpeg/exr/avif + m4a/mp3/wav inside
# Blender's exporter satisfies the first and third but pads nothing — three of
# four entries in its output landed on offsets like 4404293. Quick Look reads
# these files by mmap, so an unaligned payload is exactly the kind of defect
# that fails on a device and nowhere else.
ALLOWED_SUFFIXES = (".usd", ".usda", ".usdc", ".png", ".jpg", ".jpeg",
                    ".exr", ".avif", ".m4a", ".mp3", ".wav")


def _data_start(info: "zipfile.ZipInfo", header_offset: int, raw: bytes) -> int:
    nlen, elen = struct.unpack("<HH", raw[header_offset + 26:header_offset + 30])
    return header_offset + 30 + nlen + elen


def spec_problems(usdz_path: Path | str) -> list[str]:
    """Violations of the USDZ package spec. Empty list means compliant."""
    p = Path(usdz_path)
    problems: list[str] = []
    try:
        zf = zipfile.ZipFile(p)
    except (zipfile.BadZipFile, OSError) as e:
        return [f"not a zip: {e}"]
    blob = p.read_bytes()
    infos = zf.infolist()
    if not infos:
        return ["empty archive"]
    for info in infos:
        if info.compress_type != zipfile.ZIP_STORED:
            problems.append(f"{info.filename}: compressed "
                            f"(type {info.compress_type}) — must be STORED")
        if info.flag_bits & 0x1:
            problems.append(f"{info.filename}: encrypted — must be unencrypted")
        start = _data_start(info, info.header_offset, blob)
        if start % 64:
            problems.append(f"{info.filename}: data starts at {start} "
                            f"(offset {start % 64}) — must be 64-byte aligned")
        if not info.filename.lower().endswith(ALLOWED_SUFFIXES):
            problems.append(f"{info.filename}: file type not allowed in a usdz")
    if not infos[0].filename.lower().endswith((".usd", ".usda", ".usdc")):
        problems.append(f"default layer must be first, got {infos[0].filename}")
    return problems


def repack(usdz_path: Path | str) -> dict:
    """Rewrite a usdz so every payload lands on a 64-byte boundary.

    Padding goes in the local header's extra field, which the zip format
    reserves for exactly this and which `zipfile` will write for us. Contents
    are copied byte for byte — no recompression, no re-export.
    """
    import io
    src = Path(usdz_path)
    zf = zipfile.ZipFile(src)
    entries = [(i.filename, zf.read(i), i.date_time) for i in zf.infolist()]
    zf.close()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as out:
        for name, data, date_time in entries:
            info = zipfile.ZipInfo(filename=name, date_time=date_time)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            # where the local header will start: everything written so far
            pos = buf.tell()
            need = (-(pos + 30 + len(name.encode("utf-8")))) % 64
            if need and need < 4:
                need += 64                     # extra field needs 4 bytes of its own
            if need:
                info.extra = (struct.pack("<HH", 0x1986, need - 4)
                              + b"\0" * (need - 4))
            out.writestr(info, data)
    src.write_bytes(buf.getvalue())
    return {"repacked": str(src), "bytes": src.stat().st_size,
            "entries": len(entries)}


def validate(usdz_path: Path | str, require_animation: bool = False) -> dict:
    """USDZ is a zip with a single scene at/near the root — prove it.

    With `require_animation` we also open it through usd-core (if installed)
    and count time-sampled attributes, because "the animation came across" is
    the difference between an AR moment and a statue.
    """
    p = Path(usdz_path)
    if not p.exists():
        raise UsdzError(f"{p} was not written")
    if not zipfile.is_zipfile(p):
        raise UsdzError(f"{p} is not a zip")
    names = zipfile.ZipFile(p).namelist()
    scenes = [n for n in names if n.lower().endswith((".usd", ".usda", ".usdc"))]
    if not scenes:
        raise UsdzError(f"{p} has no .usd/.usda/.usdc inside (got {names[:8]})")
    bad = spec_problems(p)
    if p.stat().st_size < 64:
        raise UsdzError(f"{p} is suspiciously small")
    if bad:
        raise UsdzError(f"{p} violates the USDZ spec: " + "; ".join(bad[:3])
                        + (f" (+{len(bad) - 3} more)" if len(bad) > 3 else ""))
    info = {"scenes": scenes[:4], "entries": len(names),
            "bytes": p.stat().st_size,
            "spec_ok": not bad, "spec_problems": bad}
    anim = animation_samples(p)
    if anim is not None:
        info["time_sampled_attrs"] = anim
        if require_animation and anim == 0:
            raise UsdzError(f"{p} carries no animation — Quick Look would get "
                            "a static model")
    return info


# usd-core lives outside the repo (it is a 50MB wheel) — installed with
# `pip install --target`. Override with $USD_PYLIBS if it moves.
USD_PYLIBS = Path(os.environ.get("USD_PYLIBS", "/home/ubuntu/opt/pylibs"))


def animation_samples(usdz_path: Path | str) -> int | None:
    """Count time-sampled attributes in the packaged scene, or None if
    usd-core is not installed (the caller decides whether that matters)."""
    try:
        from pxr import Usd                                 # type: ignore
    except Exception:                                       # noqa: BLE001
        if USD_PYLIBS.is_dir() and str(USD_PYLIBS) not in sys.path:
            sys.path.insert(0, str(USD_PYLIBS))
        try:
            from pxr import Usd                             # type: ignore
        except Exception:                                   # noqa: BLE001
            return None
    try:
        stage = Usd.Stage.Open(str(usdz_path))
    except Exception:                                       # noqa: BLE001
        return None
    if stage is None:
        return None
    count = 0
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            try:
                if attr.GetNumTimeSamples() > 0:
                    count += 1
            except Exception:                               # noqa: BLE001
                continue
    return count


def to_usdz(glb: Path | str, out: Path | str, blender: str | None = None) -> dict:
    src, dst = Path(glb).resolve(), Path(out)
    if not src.exists():
        raise UsdzError(f"{src} does not exist")
    dst.parent.mkdir(parents=True, exist_ok=True)
    exe = blender or find_blender()

    proc = subprocess.run(
        [exe, "--background", "--factory-startup",
         "--python", str(Path(__file__).resolve()), "--", str(src), str(dst)],
        capture_output=True, text=True, timeout=900)
    if proc.returncode != 0 or not dst.exists():
        tail = (proc.stderr or proc.stdout or "").strip()[-600:]
        raise UsdzError(f"Blender failed for {src.name}: {tail}")

    before = spec_problems(dst)
    repacked = False
    if before:
        repack(dst)
        repacked = True
    info = validate(dst)
    info.update({"out": str(dst), "blender": exe, "repacked": repacked,
                 "spec_before": before[:3], "glb_bytes": src.stat().st_size})
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("glb")
    ap.add_argument("--out", required=True)
    ap.add_argument("--blender", help="path to a Blender with USD export")
    a = ap.parse_args(argv)
    try:
        print(json.dumps(to_usdz(a.glb, a.out, a.blender), indent=2))
    except UsdzError as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if _in_blender():
        # `blender --python usdz.py -- SRC DST`. Deliberately no sys.exit:
        # Blender reports SystemExit as a failure even when it is zero.
        rest = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        if len(rest) != 2:
            raise SystemExit("usage: blender --python usdz.py -- SRC DST")
        _convert(rest[0], rest[1])
    else:
        sys.exit(main())
