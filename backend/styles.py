"""Style presets — start from a ready-made character. **No Meshy key needed.**

We have real meshes on this box (freaktown's character library and bwick's
mesh-exemplar), so Upload can offer instant styles instead of waiting on a
photo→3D key. Picking one runs the same install path as an uploaded GLB:
portrait rendered, stored under the owner's namespace, products bound,
activated if it's their first.

This is the honest answer to "we don't need Meshy" for the *style* question.
A pet that looks like *your* pet still needs photo→3D — that's the one thing
a mesh library can't fake. Everything downstream of the mesh is free.
"""
from __future__ import annotations

from pathlib import Path

from . import config, install

# Curated, not auto-scanned: these are the ones with usable geometry.
_SOURCES: list[dict] = [
    {"id": "brick-figure", "label": "Brick figure",
     "blurb": "Desk minifig · 75 mm · svatantrya brick A",
     "path": "/home/ubuntu/figgsite/data/uploads/brick-figure-01a0feb8-7c26-7796-be37-b6fddb09d772.glb"},
    {"id": "brick-figure-2", "label": "Brick figure 2",
     "blurb": "Desk minifig · 75 mm · svatantrya brick B",
     "path": "/home/ubuntu/figgsite/data/uploads/brick-figure-01a0ff52-f359-7728-ab0b-28b36f28be0c.glb"},
    {"id": "badger-classic", "label": "Badger",
     "blurb": "The mesh exemplar — 59k tris, textured, printable",
     "path": "/home/ubuntu/freaktown/freaks/badger-001/avatar.glb"},
    {"id": "badger-rigged", "label": "Badger (animated)",
     "blurb": "44 nodes, one baked animation — for the Perform tab",
     "path": "/home/ubuntu/freaktown/freaks/badger-002/avatar.glb"},
    {"id": "buster", "label": "Buster",
     "blurb": "Dachshund, low-poly — the order fixture",
     "path": "/home/ubuntu/freaktown/freaks/buster-68ad29/avatar.glb"},
    {"id": "brenda", "label": "Brenda",
     "blurb": "Freak Town resident",
     "path": "/home/ubuntu/freaktown/freaks/brenda-37659b/avatar.glb"},
    {"id": "todd", "label": "Todd",
     "blurb": "Freak Town resident",
     "path": "/home/ubuntu/freaktown/freaks/todd-4e8ccd/avatar.glb"},
    {"id": "dad", "label": "Dad",
     "blurb": "Rigged human — the VRM demo body",
     "path": "/home/ubuntu/freaktown/freaks/dad-demo-001/avatar.glb"},
    {"id": "test-face", "label": "Test face",
     "blurb": "Minimal geometry, good for pipeline smoke tests",
     "path": "/home/ubuntu/freaktown/freaks/test-face-basic-001/avatar.glb"},
]

READ_ONLY_ROOTS = ("/home/ubuntu/freaktown", "/home/ubuntu/petsy")


def list_styles() -> list[dict]:
    """What's available, with size and whether it's actually on disk."""
    out = []
    for s in _SOURCES:
        p = Path(s["path"])
        ok = p.is_file()
        out.append({
            "id": s["id"], "label": s["label"], "blurb": s["blurb"],
            "available": ok,
            "bytes": p.stat().st_size if ok else 0,
            "path": p.name if ok else "",
            "read_only_source": any(s["path"].startswith(r) for r in READ_ONLY_ROOTS),
        })
    return out


def get_style(style_id: str) -> dict:
    style_id = (style_id or "").strip().lower()
    for s in _SOURCES:
        if s["id"] == style_id:
            if not Path(s["path"]).is_file():
                raise install.InstallError(f"style {style_id!r} has no mesh on disk", 404)
            return s
    raise install.InstallError(
        f"unknown style {style_id!r} — try one of: "
        + ", ".join(s["id"] for s in _SOURCES[:5]) + "…", 404)


def install_style(owner: str, style_id: str) -> dict:
    s = get_style(style_id)
    return install.install_glb(owner, Path(s["path"]),
                               source=f"style:{s['id']}", label=s["label"])
