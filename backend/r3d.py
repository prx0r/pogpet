# Provenance: copied verbatim from /home/ubuntu/petsy/engine/render3d.py
# (prx0r/bwick). Vendored so figgsite renders without a cross-repo import —
# that repo is read-only by its own rule. Pure-Python GLB -> PNG/MP4, no GPU,
# no Blender. See the module docstring for the rendering approach.
#!/usr/bin/env python3
"""Software renderer: GLB -> PNG stills and turntable MP4. No GPU, no Blender.

DEVPLAN P2's turntable renderer was written off as "needs headless Blender".
It doesn't: the mesh path only ever needs *frames*, and frames are arithmetic.

    python3 render3d.py mesh.glb --still hero.png --azimuth 35 --elevation 12
    python3 render3d.py mesh.glb --turntable spin.mp4 --frames 36 --size 512

How it draws (and why it is fast enough):
  * face colours come from the material's base-colour texture, sampled at six
    barycentric points per face — so coat markings survive, which is the whole
    product (identity IS the markings)
  * lambert shading from a fixed key light, so the figure reads as an object
  * painter's algorithm: sort faces far->near, fill with PIL. No z-buffer, and
    PIL's polygon fill is C — ~59k faces/frame in about a second

What it is not: a path tracer, and not a substitute for print photography
(gate G3). This is listing art and video frames, the P2 "proof of object".

Frames go to ffmpeg as h264 (verified installed), same encoder talk.py uses.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesh_export as X  # noqa: E402  (load_glb / collect / measure)

BG = (14, 14, 18)
# Studio rig, in VIEW space so the key light follows the camera: the figure is
# lit the same from every angle of a turntable instead of going dark at 180°.
# Camera looks down -Z, so visible normals point roughly toward +Z.
def _n(v):
    v = np.array(v, dtype=np.float64)
    return v / np.linalg.norm(v)

KEY = _n([-0.45, 0.55, 0.80])      # upper-left, in front
FILL = _n([0.70, -0.15, 0.45])     # lower-right, weaker
RIM = _n([0.1, 0.9, -0.6])         # behind-above: edge separation from the bg
AMBIENT, DIFFUSE, FILL_K, RIM_K = 0.20, 0.85, 0.30, 0.35
GAMMA = 2.2          # shade in linear light, write sRGB — same as model-viewer


class RenderError(ValueError):
    """Cannot render this GLB."""


# ----------------------------------------------------------------- textures ---

def basecolor_images(doc: dict, bin_chunk: bytes) -> dict[int, Image.Image]:
    """material index -> PIL image, from pbrMetallicRoughness.baseColorTexture."""
    out: dict[int, Image.Image] = {}
    images = doc.get("images", [])
    textures = doc.get("textures", [])
    for i, mat in enumerate(doc.get("materials", [])):
        pbr = mat.get("pbrMetallicRoughness", {})
        tex = pbr.get("baseColorTexture")
        if not tex:
            continue
        try:
            src = textures[tex["index"]]["source"]
            spec = images[src]
        except (IndexError, KeyError):
            continue
        if "bufferView" not in spec:                # external URI: not offline
            continue
        view = doc["bufferViews"][spec["bufferView"]]
        off = view.get("byteOffset", 0)
        blob = bin_chunk[off:off + view["byteLength"]]
        try:
            out[i] = Image.open(io.BytesIO(blob)).convert("RGB").copy()
        except Exception:                            # noqa: BLE001
            continue
    return out


def base_colors(geo: dict, doc: dict, bin_chunk: bytes) -> np.ndarray:
    """(triangles, 3) float — texture colour per face. Shading is per frame
    (see shade()) so a turntable stays evenly lit from every angle.

    Order matters: start from each material's baseColorFactor, then overwrite
    the ones that actually have a texture. Doing it the other way round left
    untextured parts of a partly-textured file (an effect sphere beside a
    textured character) at the default grey.
    """
    n = geo["triangles"]
    mats = geo["materials"]
    mids = geo["material_per_tri"]
    factor = np.full((n, 3), 200, dtype=np.float64)

    for i, m in enumerate(mats):
        f = (m.get("pbrMetallicRoughness", {})
                .get("baseColorFactor", [0.8, 0.8, 0.8, 1.0]))
        sel = np.where(mids == i)[0]
        if len(sel):
            factor[sel] = np.array(f[:3], dtype=np.float64) * 255.0

    if geo["uv"] is not None:
        uv = geo["uv"].reshape(n, 3, 2)
        # six barycentric samples so a face spanning texture detail averages
        # instead of taking one arbitrary texel
        bary = np.array([[1/3, 1/3, 1/3], [.6, .2, .2], [.2, .6, .2],
                         [.2, .2, .6], [.5, .25, .25], [.25, .5, .25]])
        samples = np.einsum("kb,tbc->tkc", bary, uv)      # (n, 6, 2)
        flat = samples.reshape(-1, 2)

        imgs = basecolor_images(doc, bin_chunk)
        if imgs:
            per_face = np.zeros((n, 3))
            counted = np.zeros(n, dtype=bool)
            for mi, img in imgs.items():
                sel = np.where(mids == mi)[0]
                if not len(sel):
                    continue
                arr = np.asarray(img, dtype=np.uint8)
                h, w = arr.shape[:2]
                sp = flat.reshape(n, 6, 2)[sel]
                xs = np.clip((sp[..., 0] * (w - 1)).astype(np.int64), 0, w - 1)
                ys = np.clip((sp[..., 1] * (h - 1)).astype(np.int64), 0, h - 1)
                per_face[sel] = arr[ys, xs].mean(axis=1)
                counted[sel] = True
            factor[counted] = per_face[counted]
    return factor


def face_normals(geo: dict) -> np.ndarray:
    """(triangles, 3) unit normals, averaged over the three corners."""
    n = geo["triangles"]
    normals = geo["normals"].reshape(n, 3, 3).mean(axis=1)
    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    return normals / np.where(lens == 0, 1, lens)


def shade(base: np.ndarray, normals: np.ndarray, view: np.ndarray) -> np.ndarray:
    """Key + fill + rim, computed in linear light -> (triangles, 3) uint8.

    Textures are sRGB; multiplying sRGB values by a light factor crushes the
    shadows and is why the first pass came out black. Decode, light, re-encode.
    """
    nv = normals @ view[:3, :3].T
    lens = np.linalg.norm(nv, axis=1, keepdims=True)
    nv = nv / np.where(lens == 0, 1, lens)
    lum = (AMBIENT
           + DIFFUSE * np.clip(nv @ KEY, 0, 1)
           + FILL_K * np.clip(nv @ FILL, 0, 1)
           + RIM_K * np.clip(nv @ RIM, 0, 1))[:, None]

    lin = np.power(base / 255.0, GAMMA) * lum
    out = np.power(np.clip(lin, 0.0, 1.0), 1.0 / GAMMA) * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ camera ---

def look_at(eye: np.ndarray, target: np.ndarray,
            up=np.array([0.0, 1.0, 0.0])) -> np.ndarray:
    fwd = target - eye
    fwd = fwd / np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    right = right / np.linalg.norm(right)
    true_up = np.cross(right, fwd)
    m = np.eye(4)
    m[0, :3] = right
    m[1, :3] = true_up
    m[2, :3] = -fwd
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def camera_for(points: np.ndarray, azimuth: float, elevation: float,
               fov_deg: float = 32.0, fill: float = 0.86):
    """Fit the model to the frame: work out how much of the box the camera can
    see from this angle, then stand back far enough that it fills `fill` of it."""
    lo, hi = points.min(axis=0), points.max(axis=0)
    centre = (lo + hi) / 2
    size = hi - lo
    az, el = math.radians(azimuth), math.radians(elevation)
    # apparent extents from this viewpoint (a box, projected)
    app_h = size[1] * math.cos(el) + size[2] * math.sin(el)
    app_w = size[0] * abs(math.cos(az)) + size[2] * abs(math.sin(az))
    need = max(app_h, app_w, 1e-6) / max(fill, 1e-3)
    tan_half = math.tan(math.radians(fov_deg) / 2)
    dist = need / (2 * tan_half)
    eye = centre + dist * np.array(
        [math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)])
    return look_at(eye, centre), dist


def render_frame(geo: dict, base: np.ndarray, normals: np.ndarray,
                 size: tuple[int, int], azimuth: float = 30.0,
                 elevation: float = 12.0, bg=BG) -> Image.Image:
    w, h = size
    pos = geo["positions"].reshape(-1, 3, 3)
    view, _ = camera_for(geo["positions"], azimuth, elevation)
    colors = shade(base, normals, view)
    hom = np.concatenate([pos, np.ones((*pos.shape[:2], 1))], axis=-1)
    vp = (hom @ view.T)[..., :3]                 # (n,3,3) view space

    z = -vp[..., 2]                                     # depth in front of eye
    centre_z = z.mean(axis=1)
    order = np.argsort(centre_z)[::-1]                  # far first (painter's)

    fov = math.radians(32.0)
    fy = (h / 2) / math.tan(fov / 2)
    fx = fy                                              # square pixels
    safe_z = np.where(z <= 1e-6, 1e-6, z)
    sx = (w / 2) + fx * vp[..., 0] / safe_z
    sy = (h / 2) - fy * vp[..., 1] / safe_z

    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    cols = [tuple(int(c) for c in colors[i]) for i in range(len(colors))]
    polys = [list(zip(sx[i], sy[i])) for i in range(len(sx))]
    behind = centre_z <= 1e-6

    for i in order:
        if behind[i]:
            continue
        draw.polygon(polys[i], fill=cols[i])
    return img


# ------------------------------------------------------------------- output ---

def _load_posed(glb, anim=None, time=0.0):
    """Load the GLB and, if asked, write an animation's pose at `time`."""
    doc, blob = X.load_glb(glb)
    if anim is not None:
        import anim_bake
        anim_bake.evaluate(doc, blob, time, anim)
    return doc, blob


def render_still(glb: Path | str, out: Path | str, size: int = 768,
                 azimuth: float = 30.0, elevation: float = 12.0,
                 anim: str | None = None, time: float = 0.0) -> dict:
    doc, blob = _load_posed(glb, anim, time)
    geo = X.collect(doc, blob)
    base, normals = base_colors(geo, doc, blob), face_normals(geo)
    img = render_frame(geo, base, normals, (size, size), azimuth, elevation)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"out": str(out), "triangles": geo["triangles"],
            "size": [size, size], "bytes": Path(out).stat().st_size}


def render_sequence(glb: Path | str, count: int, size: tuple[int, int],
                    *, anim: str | None = None, orbit: bool = False,
                    azimuth: float = 30.0, elevation: float = 12.0,
                    out_dir: Path | str) -> list[Path]:
    """Render `count` frames into out_dir and return the paths.

    `orbit=True` sweeps 360° (proof of object); `anim=<name>` plays a baked
    action instead with the camera held. Texture colours are sampled once
    because they never change with a pose or an angle.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc, blob = X.load_glb(glb)
    duration = _animation_duration(doc, blob, anim) if anim else None

    paths: list[Path] = []
    base = None
    geo = None
    for i in range(count):
        if anim is not None:
            doc2, blob2 = _load_posed(glb, anim, duration * i / max(count - 1, 1))
            geo = X.collect(doc2, blob2)
            if base is None:
                base = base_colors(geo, doc2, blob2)
            normals = face_normals(geo)
            az = azimuth
        else:
            az = azimuth + (360.0 * i / count if orbit else 0.0)
            if geo is None:
                geo = X.collect(doc, blob)
                base = base_colors(geo, doc, blob)
            normals = face_normals(geo)
        path = out_dir / f"f{i:05d}.png"
        render_frame(geo, base, normals, size, az, elevation).save(path)
        paths.append(path)
    return paths


def _animation_duration(doc: dict, blob: bytes, name: str) -> float:
    """Length of one cycle of a named animation, from its longest input."""
    import anim_bake
    anim = next((a for a in doc.get("animations", []) if a.get("name") == name),
                None)
    if anim is None:
        raise RenderError(f"no animation named {name!r} in this GLB")
    end = 0.0
    for smp in anim["samplers"]:
        times = anim_bake.read_accessor(doc, blob, smp["input"])
        if len(times):
            end = max(end, float(times.max()))
    return end


def turntable(glb: Path | str, out: Path | str, frames: int = 36,
              size: int = 512, fps: int = 12, elevation: float = 12.0,
              anim: str | None = None, azimuth: float = 30.0) -> dict:
    """Orbit (or, with `anim`, play the action through) -> h264 MP4.

    No audio: this is the visual bed that video.py muxes against edge-tts.
    """
    if shutil.which("ffmpeg") is None:
        raise RenderError("ffmpeg not found on PATH")
    with tempfile.TemporaryDirectory(prefix="turntable-") as td:
        render_sequence(glb, frames, (size, size), anim=anim, orbit=anim is None,
                        azimuth=azimuth, elevation=elevation, out_dir=td)
        info = _mux_frames(Path(td), out, frames, fps)
    info.update({"animation": anim,
                 "duration_s": _animation_duration(*X.load_glb(glb), anim)
                 if anim else frames / fps})
    return info


def _mux_frames(frame_dir: Path, out: Path | str, frames: int, fps: int,
                audio: Path | str | None = None) -> dict:
    cmd = ["ffmpeg", "-y", "-framerate", str(fps), "-i", f"{frame_dir}/f%05d.png"]
    if audio:
        cmd += ["-i", str(audio), "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(f"ffmpeg failed: {proc.stderr.strip()[-400:]}")
    return {"out": str(out), "frames": frames, "fps": fps,
            "size": list(Image.open(next(frame_dir.glob("f*.png"))).size),
            "bytes": Path(out).stat().st_size}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("glb")
    ap.add_argument("--still", help="write one PNG")
    ap.add_argument("--turntable", help="write an orbit MP4")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--frames", type=int, default=36)
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--azimuth", type=float, default=30.0)
    ap.add_argument("--elevation", type=float, default=12.0)
    ap.add_argument("--anim", help="play this baked action instead of orbiting")
    ap.add_argument("--time", type=float, default=0.0,
                    help="pose time for --still")
    a = ap.parse_args(argv)

    if not (a.still or a.turntable):
        print(json.dumps(X.measure(a.glb), indent=2))
        return 0
    try:
        if a.still:
            print(json.dumps(render_still(a.glb, a.still, a.size,
                                          a.azimuth, a.elevation,
                                          a.anim, a.time), indent=2))
        if a.turntable:
            print(json.dumps(turntable(a.glb, a.turntable, a.frames, a.size,
                                       a.fps, a.elevation, a.anim,
                                       a.azimuth), indent=2))
    except (RenderError, X.MeshError) as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
