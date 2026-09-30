"""Mesh → image / video. The link between a Meshy GLB and every template.

    mesh.glb ──► render.png (RGBA) ──► mockup.render(shape, …) ──► product card
               └► turntable.mp4 (36 frames, h264)

Rendering is **pure Python** — vendored from `petsy/engine/render3d.py`
(see backend/r3d.py). No GPU, no Blender, no key:

    still 512    1.2s     (Blender was ~12.8s)
    spin 36f     19.3s    (Blender was 78–200s → Cloudflare HTTP 524)

which matters because Cloudflare's free proxy times out origins at 100s.

Cache rule borrowed from freaktown/renderers.py: render once per
(mesh, variant), share forever — "sending to 100 friends never re-renders."
"""
from __future__ import annotations

from pathlib import Path

from . import config, storage
from . import r3d


class RenderError(Exception):
    pass


def render_glb(glb_path: Path, out_png: Path, size: int = 512,
               azimuth: float = 30.0, elevation: float = 12.0) -> Path:
    """One PNG still of the mesh. Raises RenderError if it can't draw."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    try:
        r3d.render_still(glb_path, out_png, size=size,
                         azimuth=azimuth, elevation=elevation)
    except Exception as e:
        raise RenderError(f"still failed: {str(e)[:300]}") from None
    if not out_png.exists() or out_png.stat().st_size == 0:
        raise RenderError("renderer produced no file")
    return out_png


def turntable(glb_path: Path, out_mp4: Path, frames: int = 36,
              size: int = 512, fps: int = 12, **_ignored) -> Path:
    """360° orbit → h264 MP4. `bg` is accepted and ignored — the renderer
    draws its own ground/shadow, so there's nothing to composite onto."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    try:
        r3d.turntable(glb_path, out_mp4, frames=frames, size=size, fps=fps)
    except Exception as e:
        raise RenderError(f"turntable failed: {str(e)[:300]}") from None
    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
        raise RenderError("turntable produced no file")
    return out_mp4


def mesh_render_key(owner: str, mesh_id: str, variant: str = "front") -> str:
    return f"owners/{storage._slug(owner)}/meshes/{mesh_id}/renders/{variant}.png"


def _local_glb(mesh_id: str, glb_key: str) -> Path:
    local = config.LOCAL_MESH / mesh_id / "model.glb"
    if not local.exists():
        storage.get(glb_key, local)
    return local


def get_mesh_render(owner: str, mesh_id: str, glb_key: str,
                    variant: str = "front", size: int = 512) -> str | None:
    """Rendered PNG key for a mesh, cached in R2. None if it can't render.

    One render per (mesh, variant) — the second caller pays nothing.
    """
    if not glb_key:
        return None
    key = mesh_render_key(owner, mesh_id, variant)
    try:
        if storage.exists(key):
            return key
    except storage.StorageError:
        pass
    try:
        out = config.LOCAL_MESH / mesh_id / f"render_{variant}.png"
        render_glb(_local_glb(mesh_id, glb_key), out, size)
        storage.put(out, key)
        out.unlink(missing_ok=True)
        return key
    except Exception:
        return None


def get_turntable(owner: str, mesh_id: str, glb_key: str) -> str | None:
    """Turntable MP4 key, cached in R2. None if it can't render."""
    if not glb_key:
        return None
    key = f"owners/{storage._slug(owner)}/meshes/{mesh_id}/turntable.mp4"
    try:
        if storage.exists(key):
            return key
    except storage.StorageError:
        pass
    try:
        out = config.LOCAL_MESH / mesh_id / "turntable.mp4"
        turntable(_local_glb(mesh_id, glb_key), out)
        storage.put(out, key)
        return key
    except Exception:
        return None
